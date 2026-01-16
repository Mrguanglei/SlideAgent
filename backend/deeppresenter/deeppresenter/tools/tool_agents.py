import base64
import os
from pathlib import Path

import httpx
from appcore import mcp
from PIL import Image

from deeppresenter.utils.config import DeepPresenterConfig
from deeppresenter.utils.log import debug, info

LLM_CONFIG = DeepPresenterConfig.load_from_file(os.getenv("LLM_CONFIG_FILE"))


@mcp.tool()
async def image_generation(prompt: str, width: int, height: int, path: str) -> str:
    """
    Generate an image and save it to the specified path.

    Args:
        prompt: Text description of the image to generate, should be detailed and specific.
        width: Width of the image, in pixels
        height: Height of the image, in pixels
        path: Full path where the image should be saved
    """

    response = await LLM_CONFIG.t2i_model.generate_image(
        prompt=prompt, width=width, height=height
    )

    image_b64 = response.data[0].b64_json
    image_url = response.data[0].url

    # Create directory if it doesn't exist
    Path(path).parent.mkdir(parents=True, exist_ok=True)

    if image_b64:
        # Decode base64 image data
        image_bytes = base64.b64decode(image_b64)
    elif image_url:
        async with httpx.AsyncClient() as client:
            response = await client.get(image_url)
            response.raise_for_status()
            image_bytes = response.content
    else:
        raise ValueError("Empty Response")

    # Save image to specified path
    with open(path, "wb") as file:
        file.write(image_bytes)

    info(
        f"Image generated: prompt='{prompt}', size=({width}x{height}), saved to '{path}'"
    )
    return "Image generated successfully, saved to " + path


_CAPTION_SYSTEM = """
You are a helpful assistant that can describe the main content of the image in less than 50 words, avoiding unnecessary details or comments.
Additionally, classify the image as 'Table', 'Chart', 'Landscape', 'Diagram', 'Banner', 'Background', 'Icon', 'Logo', etc. or 'Picture' if it cannot be classified as one of the above.
Give your answer in the following format:
<type>:<description>
Example Output:
Chart: Bar graph showing quarterly revenue growth over five years. Color-coded bars represent different product lines. Notable spike in Q4 of the most recent year, with a dotted line indicating industry average for comparison
Now give your answer in one sentence only, without line breaks:
"""


@mcp.tool()
async def image_caption(image_path: str) -> dict:
    """
    Generate a caption for the image, including its type and a brief description.

    Args:
        image_path: The path to the image to caption.

    Returns:
        The caption and size for the image
    """
    if not Path(image_path).exists():
        return {"error": f"Image path {image_path} does not exist"}
    image_b64 = f"data:image/jpeg;base64,{base64.b64encode(open(image_path, 'rb').read()).decode('utf-8')}"
    response = await LLM_CONFIG.vision_model.run(
        messages=[
            {"role": "system", "content": _CAPTION_SYSTEM},
            {
                "role": "user",
                "content": [{"type": "image_url", "image_url": {"url": image_b64}}],
            },
        ],
    )

    info(
        f"Image captioned: path='{image_path}', caption='{response.choices[0].message.content}'"
    )
    return {
        "size": Image.open(image_path).size,
        "caption": response.choices[0].message.content,
    }


_SUMMARY_SYSTEM = """
You are a professional document analyst that generates reports based on specific tasks

Instructions:
1. Thoroughly analyze the provided document and extract key information relevant to the specified task.
2. Create a comprehensive yet concise summary report, prioritizing presenting key methodologies, critical findings, and relevant data points to support an in-depth understanding.
3. Use clear Markdown formatting with logical headers and structure.

Important: Only respond with content directly related to the task and document analysis. Do not add external information, or offer any additional advice and help.
"""


@mcp.tool()
async def document_analyze(task: str, document_path: str) -> str:
    """
    Generate a report according to the given task and long document.

    Args:
        task: The specific task or objective for the report
        document_path: Path to the pure text document to be analyzed, should be endswith like .txt or .md

    Returns:
        A structured summary report in Markdown format based on the task and document content
    """
    if not Path(document_path).exists():
        return "Document path does not exist"
    if Path(document_path).suffix.lower() not in [".txt", ".md"]:
        return "Document must be a text file with .txt or .md extension"
    document = open(document_path, encoding="utf-8").read()
    response = await LLM_CONFIG.long_context_model.run(
        messages=[
            {"role": "system", "content": _SUMMARY_SYSTEM},
            {
                "role": "user",
                "content": f"Task: {task}\nDocument: {document}",
            },
        ],
    )
    report = response.choices[0].message.content
    debug(
        f"Document analyzed: path='{document_path}', task='{task}', report='{report}'"
    )
    return report


if __name__ == "__main__":
    import asyncio

    asyncio.run(
        image_generation(
            "A beautiful landscape with mountains and a river",
            512,
            512,
            "/tmp/test_image.jpg",
        )
    )
