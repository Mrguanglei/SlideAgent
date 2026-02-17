"""
Slide visual review and refinement service.

Implements a lightweight PPTAgent-style feedback loop:
1) render a slide into an image,
2) score visual quality with a multimodal model,
3) optionally rewrite layout HTML when score is below threshold.
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import re
import zipfile
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Optional, Tuple

from PIL import Image

from services.export_client import ExportToolClient, EXPORT_TOOL_URL, EXPORT_TOOL_URL_DEV
from services.llm import call_llm_api_with_config
from utils.config import Config

logger = logging.getLogger(__name__)

_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)
_HTML_BLOCK_RE = re.compile(r"```(?:html)?\s*([\s\S]*?)```", re.IGNORECASE)
_DATA_URI_RE = re.compile(r"data:image/[^;]+;base64,[A-Za-z0-9+/=]+", re.IGNORECASE)


def _strip_json_markdown(text: str) -> str:
    if not text:
        return ""
    match = _JSON_BLOCK_RE.search(text)
    if match:
        return match.group(1).strip()
    return text.strip()


def _strip_html_markdown(text: str) -> str:
    if not text:
        return ""
    match = _HTML_BLOCK_RE.search(text)
    if match:
        return match.group(1).strip()
    return text.strip()


def _extract_first_image_from_zip(blob: bytes) -> Tuple[Optional[bytes], Optional[str]]:
    if not blob:
        return None, None
    try:
        with zipfile.ZipFile(io.BytesIO(blob), "r") as zf:
            names = [
                name
                for name in zf.namelist()
                if Path(name).suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
            ]
            if not names:
                return None, None
            names.sort()
            name = names[0]
            return zf.read(name), Path(name).suffix.lower()
    except Exception as exc:
        logger.warning("Failed to read rendered image zip: %s", exc)
        return None, None


def _compress_for_vision(image_bytes: bytes, ext: Optional[str]) -> Tuple[bytes, str]:
    if not image_bytes:
        return image_bytes, "image/png"

    suffix = (ext or ".png").lower()
    mime = "image/png"
    if suffix in {".jpg", ".jpeg"}:
        mime = "image/jpeg"
    elif suffix == ".webp":
        mime = "image/webp"

    # Keep payload small for multimodal requests.
    if len(image_bytes) <= 480_000:
        return image_bytes, mime

    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            rgb = img.convert("RGB")
            rgb.thumbnail((1280, 720))
            out = io.BytesIO()
            rgb.save(out, format="JPEG", quality=72, optimize=True)
            return out.getvalue(), "image/jpeg"
    except Exception as exc:
        logger.warning("Failed to compress review screenshot: %s", exc)
        return image_bytes, mime


def _to_data_uri(image_bytes: bytes, mime: str) -> str:
    return f"data:{mime};base64,{base64.b64encode(image_bytes).decode('utf-8')}"


def _clean_html_for_model(html: str) -> str:
    if not html:
        return ""
    # Avoid sending huge base64 blobs to text model during rewrite.
    cleaned = _DATA_URI_RE.sub("data:image/placeholder;base64,__omitted__", html)
    return cleaned


async def _render_slide_image_data_uri(
    html: str,
    timeout_seconds: float,
) -> Optional[str]:
    image_bytes, ext = await _render_slide_image_bytes(html, timeout_seconds)
    if not image_bytes:
        return None
    compressed, mime = _compress_for_vision(image_bytes, ext)
    return _to_data_uri(compressed, mime)


async def _render_slide_image_bytes(
    html: str,
    timeout_seconds: float,
) -> Tuple[Optional[bytes], Optional[str]]:
    if not html:
        return None, None

    clients = [
        ExportToolClient(EXPORT_TOOL_URL),
        ExportToolClient(EXPORT_TOOL_URL_DEV),
    ]

    zip_blob: Optional[bytes] = None
    last_exc: Optional[Exception] = None
    for client in clients:
        try:
            zip_blob, _ = await asyncio.wait_for(
                client.export([html], format="png", title="visual_review"),
                timeout=max(5.0, float(timeout_seconds)),
            )
            if zip_blob:
                break
        except Exception as exc:
            last_exc = exc
            continue

    if not zip_blob:
        if last_exc:
            logger.warning("Visual review render unavailable: %s", last_exc)
        return None, None

    image_bytes, ext = _extract_first_image_from_zip(zip_blob)
    if not image_bytes:
        return None, None

    return image_bytes, ext


def _compose_side_by_side_data_uri(
    left_image_bytes: bytes,
    left_ext: Optional[str],
    right_image_bytes: bytes,
    right_ext: Optional[str],
) -> Optional[str]:
    if not left_image_bytes or not right_image_bytes:
        return None

    try:
        with Image.open(io.BytesIO(left_image_bytes)) as left_img, Image.open(
            io.BytesIO(right_image_bytes)
        ) as right_img:
            left_rgb = left_img.convert("RGB")
            right_rgb = right_img.convert("RGB")
            left_rgb.thumbnail((960, 720))
            right_rgb.thumbnail((960, 720))

            gap = 24
            canvas_width = left_rgb.width + right_rgb.width + gap
            canvas_height = max(left_rgb.height, right_rgb.height)
            canvas = Image.new("RGB", (canvas_width, canvas_height), color=(248, 248, 248))
            canvas.paste(left_rgb, (0, (canvas_height - left_rgb.height) // 2))
            canvas.paste(
                right_rgb,
                (left_rgb.width + gap, (canvas_height - right_rgb.height) // 2),
            )

            out = io.BytesIO()
            canvas.save(out, format="JPEG", quality=72, optimize=True)
            return _to_data_uri(out.getvalue(), "image/jpeg")
    except Exception as exc:
        logger.warning("Failed to compose deck style review image: %s", exc)
        # fallback: review current slide only
        compressed, mime = _compress_for_vision(right_image_bytes, right_ext)
        return _to_data_uri(compressed, mime)


def _extract_style_anchor_hint(anchor_html: str) -> str:
    if not anchor_html:
        return ""
    colors = re.findall(r"#[0-9a-fA-F]{3,8}", anchor_html)
    deduped_colors = []
    for color in colors:
        normalized = color.lower()
        if normalized not in deduped_colors:
            deduped_colors.append(normalized)
    color_hint = ", ".join(deduped_colors[:10])

    fonts = re.findall(
        r"font-family\s*:\s*([^;\"']+|\"[^\"]+\"|'[^']+')",
        anchor_html,
        flags=re.IGNORECASE,
    )
    deduped_fonts = []
    for font in fonts:
        cleaned = str(font).strip()
        if cleaned and cleaned not in deduped_fonts:
            deduped_fonts.append(cleaned)
    font_hint = ", ".join(deduped_fonts[:6])

    style_blocks = re.findall(
        r"<style[^>]*>([\s\S]*?)</style>",
        anchor_html,
        flags=re.IGNORECASE,
    )
    style_excerpt = " ".join(style_blocks[:2]).strip()
    style_excerpt = re.sub(r"\s+", " ", style_excerpt)[:1000]

    return (
        f"主色候选: {color_hint or '未提取到'}\n"
        f"字体候选: {font_hint or '未提取到'}\n"
        f"样式片段: {style_excerpt or '未提取到'}"
    )


def _normalize_review_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    score_raw = payload.get("score", 0)
    try:
        score = int(score_raw)
    except Exception:
        score = 0
    score = max(0, min(100, score))

    issues = payload.get("issues") or []
    normalized_issues = []
    if isinstance(issues, list):
        for issue in issues[:6]:
            if not isinstance(issue, dict):
                continue
            normalized_issues.append(
                {
                    "severity": str(issue.get("severity") or "medium")[:12],
                    "problem": str(issue.get("problem") or "")[:180],
                    "fix": str(issue.get("fix") or "")[:180],
                }
            )

    rewrite_instruction = str(payload.get("rewrite_instruction") or "").strip()[:1600]
    summary = str(payload.get("summary") or "").strip()[:300]

    return {
        "score": score,
        "issues": normalized_issues,
        "summary": summary,
        "rewrite_instruction": rewrite_instruction,
    }


async def review_slide_visual_quality(
    html_for_render: str,
    topic: str,
    page_description: str,
    page_number: int,
) -> Optional[Dict[str, Any]]:
    if not Config.VISUAL_REVIEW_ENABLED:
        return None
    if not Config.IMAGE_REFERENCE_API_KEY or not Config.IMAGE_REFERENCE_BASE_URL:
        return None

    image_data_uri = await _render_slide_image_data_uri(
        html_for_render,
        timeout_seconds=Config.VISUAL_REVIEW_TIMEOUT_SECONDS,
    )
    if not image_data_uri:
        return None

    prompt = f"""
你是资深演示文稿视觉评审专家。请根据截图评审该页质量。

主题：{topic}
页码：{page_number}
页面说明：{page_description}

评分标准（0-100）：
- 信息层级清晰、视觉焦点明确
- 对齐与留白合理，不拥挤
- 颜色与对比度可读
- 图文关系自然，非装饰性堆砌
- 元素无明显越界、重叠、裁切

仅输出 JSON：
{{
  "score": 0-100,
  "summary": "一句话结论",
  "issues": [
    {{"severity":"high|medium|low","problem":"问题","fix":"修复建议"}}
  ],
  "rewrite_instruction": "给排版模型的具体改写指令（可执行，100-300字）"
}}
""".strip()

    try:
        response = await call_llm_api_with_config(
            messages=[
                {"role": "system", "content": "你是严格的 JSON 输出助手。"},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_data_uri}},
                    ],
                },
            ],
            model=Config.IMAGE_REFERENCE_MODEL,
            base_url=Config.IMAGE_REFERENCE_BASE_URL,
            api_key=Config.IMAGE_REFERENCE_API_KEY,
            response_format={"type": "json_object"},
            temperature=0.1,
            timeout_seconds=Config.VISUAL_REVIEW_TIMEOUT_SECONDS,
            max_retries=1,
        )
        payload = json.loads(_strip_json_markdown(response))
        return _normalize_review_payload(payload if isinstance(payload, dict) else {})
    except Exception as exc:
        logger.warning("Visual review scoring failed on slide %s: %s", page_number, exc)
        return None


async def rewrite_slide_html_with_feedback(
    raw_html: str,
    review_payload: Dict[str, Any],
    topic: str,
    page_description: str,
    page_number: int,
) -> Optional[str]:
    if not raw_html or not review_payload:
        return None

    rewrite_instruction = str(review_payload.get("rewrite_instruction") or "").strip()
    if not rewrite_instruction:
        return None

    cleaned_html = _clean_html_for_model(raw_html)
    prompt = f"""
请直接重写下面这页幻灯片 HTML，提升视觉质量。

主题：{topic}
页码：{page_number}
页面说明：{page_description}
视觉评分：{review_payload.get("score", 0)}
评审要点：{rewrite_instruction}

硬约束：
1. 只输出完整 HTML，不要解释，不要 markdown 代码块。
2. 保持页面尺寸 1280x720，所有元素在可视范围内。
3. 保留页面语义和核心信息，不要删掉关键结论。
4. 若存在 {{img_N}} 占位符，必须保留且可正常渲染。
5. 不要新增外部依赖脚本和随机图片 URL。

原始 HTML：
{cleaned_html}
""".strip()

    try:
        rewritten = await call_llm_api_with_config(
            messages=[
                {"role": "system", "content": "你是严谨的前端排版工程师，只输出可执行 HTML。"},
                {"role": "user", "content": prompt},
            ],
            model=Config.PPTAGENT_MODEL,
            base_url=Config.PPTAGENT_API_BASE,
            api_key=Config.PPTAGENT_API_KEY,
            temperature=0.2,
            timeout_seconds=Config.VISUAL_REWRITE_TIMEOUT_SECONDS,
            max_retries=1,
        )
        candidate = _strip_html_markdown(rewritten).strip()
        lowered = candidate.lower()
        if "<html" not in lowered or "</html>" not in lowered:
            return None
        if len(candidate) < max(500, int(len(raw_html) * 0.35)):
            return None
        if len(candidate) > max(32000, int(len(raw_html) * 2.6)):
            return None
        return candidate
    except Exception as exc:
        logger.warning("Visual rewrite failed on slide %s: %s", page_number, exc)
        return None


async def review_slide_deck_style_consistency(
    anchor_html_for_render: str,
    current_html_for_render: str,
    topic: str,
    page_description: str,
    page_number: int,
) -> Optional[Dict[str, Any]]:
    if not getattr(Config, "DECK_STYLE_REVIEW_ENABLED", True):
        return None
    if not Config.IMAGE_REFERENCE_API_KEY or not Config.IMAGE_REFERENCE_BASE_URL:
        return None

    timeout_seconds = float(
        getattr(
            Config,
            "DECK_STYLE_REVIEW_TIMEOUT_SECONDS",
            getattr(Config, "VISUAL_REVIEW_TIMEOUT_SECONDS", 30),
        )
    )
    anchor_bytes, anchor_ext = await _render_slide_image_bytes(
        anchor_html_for_render,
        timeout_seconds=timeout_seconds,
    )
    current_bytes, current_ext = await _render_slide_image_bytes(
        current_html_for_render,
        timeout_seconds=timeout_seconds,
    )
    if not current_bytes:
        return None

    image_data_uri = _compose_side_by_side_data_uri(
        anchor_bytes or b"",
        anchor_ext,
        current_bytes,
        current_ext,
    )
    if not image_data_uri:
        return None

    prompt = f"""
你是资深演示文稿视觉总监。左图是风格锚点页，右图是当前页。请评审“跨页视觉一致性”。

主题：{topic}
当前页码：{page_number}
当前页面说明：{page_description}

评分标准（0-100）：
- 色彩体系与风格调性是否一致
- 字体/字号层级是否一致
- 栅格、间距、圆角、阴影等视觉语言是否一致
- 版式是否保持同一套设计系统，而非随机跳变

仅输出 JSON：
{{
  "score": 0-100,
  "summary": "一句话结论",
  "issues": [
    {{"severity":"high|medium|low","problem":"问题","fix":"修复建议"}}
  ],
  "rewrite_instruction": "给排版模型的具体改写指令（可执行，100-300字）"
}}
""".strip()

    try:
        response = await call_llm_api_with_config(
            messages=[
                {"role": "system", "content": "你是严格的 JSON 输出助手。"},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_data_uri}},
                    ],
                },
            ],
            model=Config.IMAGE_REFERENCE_MODEL,
            base_url=Config.IMAGE_REFERENCE_BASE_URL,
            api_key=Config.IMAGE_REFERENCE_API_KEY,
            response_format={"type": "json_object"},
            temperature=0.1,
            timeout_seconds=timeout_seconds,
            max_retries=1,
        )
        payload = json.loads(_strip_json_markdown(response))
        return _normalize_review_payload(payload if isinstance(payload, dict) else {})
    except Exception as exc:
        logger.warning(
            "Deck style review failed on slide %s: %s",
            page_number,
            exc,
        )
        return None


async def rewrite_slide_html_with_style_anchor(
    raw_html: str,
    anchor_raw_html: str,
    anchor_page_description: str,
    review_payload: Dict[str, Any],
    topic: str,
    page_description: str,
    page_number: int,
) -> Optional[str]:
    if not raw_html or not anchor_raw_html or not review_payload:
        return None
    rewrite_instruction = str(review_payload.get("rewrite_instruction") or "").strip()
    if not rewrite_instruction:
        return None

    cleaned_current_html = _clean_html_for_model(raw_html)
    anchor_style_hint = _extract_style_anchor_hint(_clean_html_for_model(anchor_raw_html))
    prompt = f"""
请重写当前页 HTML，使其与风格锚点页视觉一致，同时保留当前页语义内容。

主题：{topic}
当前页码：{page_number}
当前页面说明：{page_description}
锚点页说明：{anchor_page_description}
一致性评审评分：{review_payload.get("score", 0)}
一致性修正要求：{rewrite_instruction}

锚点页风格线索：
{anchor_style_hint}

硬约束：
1. 只输出完整 HTML，不要解释，不要 markdown。
2. 保持页面尺寸 1280x720，所有元素在可视范围内。
3. 保留当前页核心信息结构，不要改写事实内容。
4. 若存在 {{img_N}} 占位符，必须保留。
5. 保持同一设计系统：颜色、字体、卡片样式、间距、圆角和阴影语法一致。

当前页原始 HTML：
{cleaned_current_html}
""".strip()

    timeout_seconds = float(
        getattr(
            Config,
            "DECK_STYLE_REWRITE_TIMEOUT_SECONDS",
            getattr(Config, "VISUAL_REWRITE_TIMEOUT_SECONDS", 40),
        )
    )
    try:
        rewritten = await call_llm_api_with_config(
            messages=[
                {
                    "role": "system",
                    "content": "你是严谨的前端排版工程师，只输出可执行 HTML。",
                },
                {"role": "user", "content": prompt},
            ],
            model=Config.PPTAGENT_MODEL,
            base_url=Config.PPTAGENT_API_BASE,
            api_key=Config.PPTAGENT_API_KEY,
            temperature=0.2,
            timeout_seconds=timeout_seconds,
            max_retries=1,
        )
        candidate = _strip_html_markdown(rewritten).strip()
        lowered = candidate.lower()
        if "<html" not in lowered or "</html>" not in lowered:
            return None
        if len(candidate) < max(500, int(len(raw_html) * 0.35)):
            return None
        if len(candidate) > max(32000, int(len(raw_html) * 2.6)):
            return None
        return candidate
    except Exception as exc:
        logger.warning("Deck style rewrite failed on slide %s: %s", page_number, exc)
        return None


async def refine_slide_with_visual_review(
    raw_html: str,
    topic: str,
    page_description: str,
    page_number: int,
    prepare_for_render: Callable[[str], Awaitable[str]],
) -> Tuple[str, Optional[Dict[str, Any]]]:
    """
    Run visual review loop and return possibly refined raw HTML.
    """
    if not Config.VISUAL_REVIEW_ENABLED:
        return raw_html, None
    if not Config.IMAGE_REFERENCE_API_KEY or not Config.IMAGE_REFERENCE_BASE_URL:
        return raw_html, None

    max_rounds = max(0, min(2, int(Config.VISUAL_REVIEW_MAX_ROUNDS or 0)))
    min_score = max(0, min(100, int(Config.VISUAL_REVIEW_MIN_SCORE or 0)))

    current_raw_html = raw_html
    last_meta: Optional[Dict[str, Any]] = None
    optimized_any = False

    for round_index in range(max_rounds + 1):
        try:
            render_html = await prepare_for_render(current_raw_html)
        except Exception as exc:
            logger.warning("Visual review prepare failed on slide %s: %s", page_number, exc)
            break

        review_payload = await review_slide_visual_quality(
            html_for_render=render_html,
            topic=topic,
            page_description=page_description,
            page_number=page_number,
        )
        if not review_payload:
            break

        score = int(review_payload.get("score", 0))
        last_meta = {
            "score": score,
            "issues": review_payload.get("issues") or [],
            "summary": review_payload.get("summary") or "",
            "optimized": optimized_any,
            "round": round_index,
        }
        if score >= min_score or round_index >= max_rounds:
            break

        rewritten = await rewrite_slide_html_with_feedback(
            raw_html=current_raw_html,
            review_payload=review_payload,
            topic=topic,
            page_description=page_description,
            page_number=page_number,
        )
        if not rewritten or rewritten.strip() == current_raw_html.strip():
            break

        current_raw_html = rewritten
        optimized_any = True
        last_meta["optimized"] = True

    return current_raw_html, last_meta


async def refine_slide_with_deck_style_review(
    raw_html: str,
    topic: str,
    page_description: str,
    page_number: int,
    anchor_raw_html: str,
    anchor_page_description: str,
    prepare_for_render: Callable[[str], Awaitable[str]],
) -> Tuple[str, Optional[Dict[str, Any]]]:
    """
    Run deck-level style consistency review loop and return possibly refined raw HTML.
    """
    if not getattr(Config, "DECK_STYLE_REVIEW_ENABLED", True):
        return raw_html, None
    if not Config.IMAGE_REFERENCE_API_KEY or not Config.IMAGE_REFERENCE_BASE_URL:
        return raw_html, None
    if not raw_html or not anchor_raw_html:
        return raw_html, None

    start_page = max(2, int(getattr(Config, "DECK_STYLE_START_PAGE", 2) or 2))
    if int(page_number or 0) < start_page:
        return raw_html, None

    max_rounds = max(
        0,
        min(2, int(getattr(Config, "DECK_STYLE_MAX_ROUNDS", 1) or 0)),
    )
    min_score = max(
        0,
        min(100, int(getattr(Config, "DECK_STYLE_MIN_SCORE", 75) or 0)),
    )

    current_raw_html = raw_html
    last_meta: Optional[Dict[str, Any]] = None
    optimized_any = False

    try:
        anchor_render_html = await prepare_for_render(anchor_raw_html)
    except Exception as exc:
        logger.warning("Deck style anchor prepare failed on slide %s: %s", page_number, exc)
        return raw_html, None

    for round_index in range(max_rounds + 1):
        try:
            render_html = await prepare_for_render(current_raw_html)
        except Exception as exc:
            logger.warning("Deck style prepare failed on slide %s: %s", page_number, exc)
            break

        review_payload = await review_slide_deck_style_consistency(
            anchor_html_for_render=anchor_render_html,
            current_html_for_render=render_html,
            topic=topic,
            page_description=page_description,
            page_number=page_number,
        )
        if not review_payload:
            break

        score = int(review_payload.get("score", 0))
        last_meta = {
            "score": score,
            "issues": review_payload.get("issues") or [],
            "summary": review_payload.get("summary") or "",
            "optimized": optimized_any,
            "round": round_index,
            "mode": "deck_style",
        }
        if score >= min_score or round_index >= max_rounds:
            break

        rewritten = await rewrite_slide_html_with_style_anchor(
            raw_html=current_raw_html,
            anchor_raw_html=anchor_raw_html,
            anchor_page_description=anchor_page_description,
            review_payload=review_payload,
            topic=topic,
            page_description=page_description,
            page_number=page_number,
        )
        if not rewritten or rewritten.strip() == current_raw_html.strip():
            break

        current_raw_html = rewritten
        optimized_any = True
        last_meta["optimized"] = True

    return current_raw_html, last_meta
