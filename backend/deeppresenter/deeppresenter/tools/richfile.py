import asyncio
import base64
import os
import re
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Literal

import httpx
from .appcore import mcp
from fake_useragent import UserAgent
from mcp.types import ImageContent
from mistune import html as markdown_to_html
from PIL import Image
from pptagent.utils import get_html_table_image, ppt_to_images

from deeppresenter.utils.config import RETRY_TIMES, DeepPresenterConfig
from deeppresenter.utils.critic import slide_oversight
from deeppresenter.utils.webview import convert_html_to_pptx

# 不使用语言检测模型，统一使用中文
LID_MODEL = None

FAKE_UA = UserAgent()
LLM_CONFIG = DeepPresenterConfig.load_from_file(os.getenv("LLM_CONFIG_FILE"))


@mcp.tool()
def write_file(content: str, file_path: str) -> str:
    """
    Write text content to a file.

    Args:
        content (str): The text content to write
        file_path (str): The path where the file will be saved

    Returns:
        str: Confirmation message with the path to the saved file
    """
    # Create directory if it doesn't exist
    Path(file_path).parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    return f"File written to {file_path}"


@mcp.tool()
async def download_file(url: str, output_path: str) -> str:
    """
    Download a file from a URL and save it to a local path.
    """
    # Create directory if it doesn't exist
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    for retry in range(RETRY_TIMES):
        try:
            await asyncio.sleep(retry)
            async with httpx.AsyncClient(
                headers={"User-Agent": FAKE_UA.random},
                follow_redirects=True,
                verify=False,
            ) as client:
                async with client.stream("GET", url) as response:
                    response.raise_for_status()
                    with open(output_path, "wb") as f:
                        async for chunk in response.aiter_bytes(8192):
                            f.write(chunk)
                    break
        except:
            pass
    else:
        return f"Failed to download file from {url}"

    result = f"File downloaded to {output_path}"
    if output_path.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")):
        try:
            with Image.open(output_path) as img:
                width, height = img.size
                result += f" (resolution: {width}x{height})"
        except Exception as e:
            return f"The provided URL does not point to a valid image file: {e}"
    return result


@mcp.tool()
def markdown_table_to_image(markdown_table: str, path: str, css: str) -> str:
    """
    Convert a markdown table to an image and save it to the specified path.

    Args:
        markdown_table (str): The markdown table content to convert
        path (str): The file path where the image will be saved
        css (str): Custom CSS styles for the table. Use class selectors
                            (table, thead, th, td) to style the table elements. Avoid
                            changing background colors outside the table area.

    Returns:
        str: Confirmation message with the path to the saved image
    """
    html = markdown_to_html(markdown_table)
    get_html_table_image(html, path, css)
    return f"Markdown table converted to image and saved to {path}"


ASPECT_RATIO_MAPPING = {
    "16:9": "widescreen",
    "4:3": "normal",
}


@mcp.tool()
async def inspect_slide(
    html_file: str,
    aspect_ratio: Literal["widescreen", "normal", "A1", "16:9", "4:3"] = "widescreen",
) -> ImageContent | str:
    """
    Read the HTML file as an image.

    Args:
        html_file (str): The path to the HTML file
        aspect_ratio (Literal["widescreen", "normal", "A1"]): The slide aspect ratio

    Returns:
        ImageContent: The slide as an image content
        str: Error message if inspection fails
    """
    if aspect_ratio in ASPECT_RATIO_MAPPING:
        aspect_ratio = ASPECT_RATIO_MAPPING[aspect_ratio]
    html_path = Path(html_file).absolute()
    if not (html_path.exists() and html_path.suffix == ".html"):
        return f"HTML path {html_path} does not exist or is not an HTML file"
    if aspect_ratio not in ["widescreen", "normal", "A1"]:
        return "aspect_ratio should be one of 'widescreen', 'normal', 'A1'"
    try:
        pptx_path = convert_html_to_pptx(html_path, aspect_ratio=aspect_ratio)
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir)
            ppt_to_images(str(pptx_path), str(output_dir))
            image_path = output_dir / "slide_0001.jpg"
            image_data = image_path.read_bytes()
        base64_data = (
            f"data:image/jpeg;base64,{base64.b64encode(image_data).decode('utf-8')}"
        )

        if (
            LLM_CONFIG.critic_agent is not None
            and not LLM_CONFIG.design_agent.is_multimodal
        ):
            critic = await slide_oversight(
                LLM_CONFIG.critic_agent,
                base64_data,
                html_path.read_text(encoding="utf-8"),
            )
            return critic.content
        return ImageContent(
            type="image",
            data=base64_data,
            mimeType="image/jpeg",
        )
    except Exception as e:
        return e


@mcp.tool()
def inspect_manuscript(md_file: str) -> dict:
    """
    Inspect the markdown manuscript for general statistics and image asset validation.
    Args:
        md_file (str): The path to the markdown file
    """
    md_path = Path(md_file)
    if not md_path.exists():
        return {"error": f"file does not exist: {md_file}"}
    if not md_file.lower().endswith(".md"):
        return {"error": f"file is not a markdown file: {md_file}"}

    with open(md_file, encoding="utf-8") as f:
        markdown = f.read()

    pages = [p for p in markdown.split("\n---\n") if p.strip()]
    result = defaultdict(list)
    result["num_pages"] = len(pages)

    # 语言检测 - 如果模型未加载则默认为中文
    if LID_MODEL is not None:
        try:
            label = LID_MODEL.predict(markdown[:1000].replace("\n", " "))
            result["language"] = label[0][0].replace("__label__", "")
        except Exception as e:
            print(f"Warning: Language detection failed: {e}, defaulting to 'zh'")
            result["language"] = "zh"
    else:
        # 模型未加载，默认为中文
        result["language"] = "zh"

    seen_images = set()
    for match in re.finditer(r"!\[(.*?)\]\((.*?)\)", markdown):
        label, path = match.group(1), match.group(2)
        path = path.split()[0].strip("\"'")

        if path in seen_images:
            continue
        seen_images.add(path)

        if re.match(r"https?://", path):
            result["warnings"].append(
                f"External link detected: {match.group(0)}, consider downloading to local storage."
            )
            continue

        if not (md_path.parent / path).exists() and not Path(path).exists():
            result["warnings"].append(f"Image file does not exist: {path}")

        if not label.strip():
            result["warnings"].append(f"Image {path} is missing alt text.")

        count = markdown.count(path)
        if count > 1:
            result["warnings"].append(
                f"Image {path} used {count} times in the whole presentation manuscript."
            )

    if len(result["warnings"]) == 0:
        result["success"].append(
            "Image asset validation passed: all referenced images exist."
        )

    return result
