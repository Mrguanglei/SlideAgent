"""
PPTAgent PPT 生成服务模块

提供 PPT 生成核心功能
"""

import base64
import asyncio
import hashlib
import json
import logging
import re
import tempfile
from datetime import datetime
from pathlib import Path
from time import monotonic
from typing import AsyncGenerator, Optional, Dict, List, Tuple

from utils.config import Config
from services.image_reference import build_image_reference_strategy
from services.ppt_quality import (
    build_quality_guardrail,
    enhance_outline_with_functional_layouts,
    estimate_length_factor,
)

logger = logging.getLogger(__name__)


def create_tool_call(tool_type: str, tool_name: str, status: str, data: dict) -> dict:
    """创建工具调用对象"""
    return {
        "type": tool_type,
        "name": tool_name,
        "status": status,
        "data": data
    }


def parse_num_pages(supplement_data: dict, default: int = 15) -> int:
    """从 supplement_data 中解析页数"""
    if not supplement_data:
        return default
    
    num_pages_range = supplement_data.get("num_pages", "")
    logger.info(f"User selected page range: {num_pages_range}")

    if isinstance(num_pages_range, str):
        if "8-10" in num_pages_range:
            return 10
        elif "11-15" in num_pages_range:
            return 15
        elif "16-20" in num_pages_range:
            return 20
        elif "21-25" in num_pages_range:
            return 25
        else:
            return default
    elif isinstance(num_pages_range, int):
        return num_pages_range
    
    return default


async def generate_slide_thinking(slide_count: int, topic: str) -> Optional[str]:
    """生成幻灯片创建后的进度文案（本地生成，避免额外 LLM 请求放大限流）"""
    if slide_count <= 0:
        return None
    next_page = slide_count + 1
    topic_text = (topic or "当前主题").strip()
    return f"第{slide_count}页已完成。继续围绕“{topic_text}”构建第{next_page}页内容。"


def _image_to_data_uri(local_path: str) -> Optional[str]:
    """将本地图片文件转为 base64 data URI"""
    try:
        path = Path(local_path)
        if not path.exists():
            return None
        data = path.read_bytes()
        ext = path.suffix.lower().lstrip(".")
        mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
                "webp": "image/webp", "gif": "image/gif"}.get(ext, "image/jpeg")
        b64 = base64.b64encode(data).decode()
        return f"data:{mime};base64,{b64}"
    except Exception as e:
        logger.warning(f"Failed to convert image to data URI: {local_path}: {e}")
        return None


_BACKGROUND_EXCLUDE_KEYWORDS = [
    "chart", "graph", "table", "diagram", "infographic", "schema", "workflow",
    "screenshot", "dashboard", "ui", "icon", "logo", "banner",
    "图表", "表格", "示意", "流程图", "架构", "数据", "截图", "界面", "仪表盘",
]

_HTML_HINT_RE = re.compile(
    r"<!DOCTYPE html>|<html\\b|<body\\b|<(?:div|section|main|article|header|footer|img|svg)\\b",
    re.IGNORECASE,
)
_SLIDE_NARRATION_RE = re.compile(
    r"(第\\s*\\d+\\s*页|第\\s*[一二三四五六七八九十]+\\s*页|封面|目录|新增页面|开始\\s*创建|现在开始|接下来|下一页|已完成)",
    re.IGNORECASE,
)
_INLINE_STYLE_RE = re.compile(r'style=(["\'])(.*?)\1', re.IGNORECASE | re.DOTALL)
_IMG_TAG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
_ATTR_RE_TEMPLATE = r'\b{attr}\s*=\s*(["\'])(.*?)\1'
_WORD_RE = re.compile(r"[A-Za-z0-9]{2,}|[\u4e00-\u9fff]{2,}")
_BACKGROUND_HINT_RE = re.compile(
    r"(cover|background|hero|封面|背景)",
    re.IGNORECASE,
)


def _looks_like_html(text: str) -> bool:
    if not text:
        return False
    snippet = text[:6000].strip()
    if not snippet:
        return False
    if _HTML_HINT_RE.search(snippet):
        return True
    if snippet.startswith("<") and "</" in snippet and ">" in snippet:
        return True
    return False


def _looks_like_slide_narration(text: str) -> bool:
    if not text:
        return False
    snippet = text.strip()[:400]
    return bool(_SLIDE_NARRATION_RE.search(snippet))


def _extract_slide_index_from_path(file_path: str) -> Optional[int]:
    if not file_path:
        return None
    match = re.search(r"(?:slide|page)[_-]?0*(\\d+)", file_path, re.IGNORECASE)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return None
    return None


def _normalize_slide_index(candidate: Optional[int], current: int) -> int:
    if isinstance(candidate, int) and candidate > 0:
        if candidate <= current:
            return current + 1
        return candidate
    return current + 1


def _resolve_slide_index(
    tool_name_lower: str,
    candidate_index: Optional[int],
    file_path: Optional[str],
    current_max: int,
) -> Optional[int]:
    index = candidate_index
    if index is None and file_path:
        index = _extract_slide_index_from_path(str(file_path))
    if isinstance(index, int) and index > 0:
        return index

    is_insert_like = tool_name_lower in {"insert_page", "create_page", "add_page"} or (
        "insert" in tool_name_lower and "page" in tool_name_lower
    )
    if is_insert_like:
        return current_max + 1 if current_max > 0 else 1

    if tool_name_lower in {"update_page", "write_file"}:
        # update/write 场景如果缺失页号，不盲目新增页，避免重复页
        return current_max if current_max > 0 else None

    return current_max + 1 if current_max > 0 else 1


def _extract_html_from_tool_args(tool_args: Dict) -> Tuple[str, Optional[str], Optional[int], Optional[str]]:
    if not isinstance(tool_args, dict):
        return "", None, None, None
    html_content = (
        tool_args.get("html", "") or
        tool_args.get("content", "") or
        tool_args.get("html_content", "") or
        tool_args.get("code", "")
    )
    file_path = tool_args.get("file_path") or tool_args.get("path")
    index = tool_args.get("index") or tool_args.get("page") or tool_args.get("page_number")
    description = tool_args.get("action_description") or tool_args.get("description")
    try:
        if index is not None:
            index = int(index)
    except Exception:
        index = None
    return html_content, file_path, index, description


def _extract_json_payload(content_text: str) -> Optional[Dict]:
    if not content_text:
        return None
    stripped = content_text.strip()
    if not (stripped.startswith("{") and stripped.endswith("}")):
        return None
    try:
        payload = json.loads(stripped)
        if isinstance(payload, dict):
            return payload
    except Exception:
        return None
    return None


def _extract_slide_candidate_from_payload(payload: Dict, current_slide_count: int) -> Optional[Dict]:
    if not isinstance(payload, dict):
        return None

    file_path = payload.get("html_file") or payload.get("file_path") or payload.get("path")
    if not file_path or not str(file_path).lower().endswith(".html"):
        return None

    html_path = Path(str(file_path))
    if not html_path.exists():
        return None

    try:
        html_content = html_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None

    if not _looks_like_html(html_content):
        return None

    index = payload.get("page_number") or payload.get("page") or payload.get("index")
    try:
        if index is not None:
            index = int(index)
    except Exception:
        index = None

    if index is None:
        progress = str(payload.get("progress") or "")
        progress_match = re.match(r"\s*(\d+)\s*/", progress)
        if progress_match:
            try:
                index = int(progress_match.group(1))
            except Exception:
                index = None

    if index is None:
        index = _extract_slide_index_from_path(str(file_path))

    slide_index = _normalize_slide_index(index, current_slide_count)
    description = (
        payload.get("action_description")
        or payload.get("description")
        or payload.get("message")
        or f"第 {slide_index} 页"
    )
    return {
        "slide_count": slide_index,
        "html_content": html_content,
        "description": description,
        "file_path": str(file_path),
    }


def _tokenize_words(text: str) -> set[str]:
    if not text:
        return set()
    return {tok.lower() for tok in _WORD_RE.findall(text)}


def _extract_attr(tag: str, attr: str) -> str:
    pattern = re.compile(_ATTR_RE_TEMPLATE.format(attr=re.escape(attr)), re.IGNORECASE | re.DOTALL)
    match = pattern.search(tag)
    if not match:
        return ""
    return (match.group(2) or "").strip()


def _replace_src(tag: str, new_src: str) -> str:
    pattern = re.compile(_ATTR_RE_TEMPLATE.format(attr="src"), re.IGNORECASE | re.DOTALL)
    match = pattern.search(tag)
    if not match:
        return tag
    return f"{tag[:match.start(2)]}{new_src}{tag[match.end(2):]}"


def _is_background_img_tag(tag: str) -> bool:
    merged = " ".join(
        [
            _extract_attr(tag, "class"),
            _extract_attr(tag, "alt"),
            _extract_attr(tag, "title"),
            _extract_attr(tag, "style"),
        ]
    )
    if _BACKGROUND_HINT_RE.search(merged):
        return True
    style = _extract_attr(tag, "style").lower()
    return "position:absolute" in style and ("width:100%" in style or "height:100%" in style)


def _semantic_overlap_score(text_a: str, text_b: str) -> float:
    words_a = _tokenize_words(text_a)
    words_b = _tokenize_words(text_b)
    token_score = 0.0
    if words_a and words_b:
        overlap = len(words_a & words_b)
        base = max(1, min(len(words_a), len(words_b), 8))
        token_score = overlap / base

    # Chinese text often needs finer-grained matching than whole-token overlap.
    def _cjk_bigrams(text: str) -> set[str]:
        chars = [ch for ch in text if "\u4e00" <= ch <= "\u9fff"]
        if len(chars) < 2:
            return set()
        return {f"{chars[i]}{chars[i + 1]}" for i in range(len(chars) - 1)}

    bigrams_a = _cjk_bigrams(text_a)
    bigrams_b = _cjk_bigrams(text_b)
    bigram_score = 0.0
    if bigrams_a and bigrams_b:
        bigram_score = len(bigrams_a & bigrams_b) / max(1, min(len(bigrams_a), len(bigrams_b), 10))

    return max(token_score, bigram_score * 0.9)


def _resolve_image_preferences_for_slide(
    page_number: int,
    page_description: str,
    image_reference_strategy: Optional[Dict],
) -> List[int]:
    if not image_reference_strategy:
        return []
    cover_candidates = [idx for idx in (image_reference_strategy.get("cover_candidates") or []) if isinstance(idx, int)]
    content_candidates = [idx for idx in (image_reference_strategy.get("content_candidates") or []) if isinstance(idx, int)]
    section_assignments = image_reference_strategy.get("section_assignments") or []

    ordered: List[int] = []
    if page_number <= 1:
        ordered.extend(cover_candidates[:2])

    desc_text = (page_description or "").strip().lower()
    if section_assignments and desc_text:
        best = None
        best_score = 0.0
        for item in section_assignments:
            section = str(item.get("section") or "")
            score = _semantic_overlap_score(desc_text, section.lower())
            if section and section in desc_text:
                score += 1.0
            if score > best_score:
                best_score = score
                best = item
        if best and best_score >= 0.2:
            ordered.extend([idx for idx in best.get("primary", []) if isinstance(idx, int)])
            ordered.extend([idx for idx in best.get("backup", []) if isinstance(idx, int)])

    ordered.extend(content_candidates[:8])
    ordered.extend(cover_candidates[:1])

    deduped: List[int] = []
    for idx in ordered:
        if idx not in deduped:
            deduped.append(idx)
    return deduped


def _is_background_candidate(img: Dict) -> bool:
    """判断图片是否适合作为整页背景（启发式）"""
    desc = (img.get("description") or "").lower()
    url = (img.get("url") or "").lower()
    text = f"{desc} {url}"

    if any(keyword in text for keyword in _BACKGROUND_EXCLUDE_KEYWORDS):
        return False

    width = img.get("width") or 0
    height = img.get("height") or 0
    if not width or not height:
        return False

    if width < 900 or height < 500:
        return False

    ratio = width / height if height else 0
    if ratio < 1.2 or ratio > 2.2:
        return False

    return True


def replace_image_placeholders(
    html: str,
    image_results: List[Dict],
    preferred_image_ids: Optional[List[int]] = None,
    usage_counter: Optional[Dict[int, int]] = None,
    page_number: Optional[int] = None,
    page_description: str = "",
) -> str:
    """替换 HTML 中的图片占位符和假 URL 为本地图片的 base64 data URI

    处理策略（按优先级）：
    1. 替换 {{img_N}} 占位符为对应图片的 base64
    2. 按页面语义和推荐图片优先级替换 fake/external URL，避免无效外链
    3. 使用 usage_counter 限制重复用同一张图，提升页面多样性
    """
    if not image_results:
        return html

    usage_counter = usage_counter if usage_counter is not None else {}
    preferred_set = {
        int(idx)
        for idx in (preferred_image_ids or [])
        if isinstance(idx, int) and idx > 0
    }

    # 构建候选池
    candidates: List[Dict] = []
    for i, img in enumerate(image_results, 1):
        local_path = img.get("local_path", "")
        data_uri = _image_to_data_uri(local_path)
        if data_uri:
            candidates.append(
                {
                    "id": i,
                    "data_uri": data_uri,
                    "description": str(img.get("description") or ""),
                    "url": str(img.get("url") or ""),
                    "is_background": _is_background_candidate(img),
                    "width": int(img.get("width") or 0),
                    "height": int(img.get("height") or 0),
                }
            )

    if not candidates:
        return html

    by_id = {item["id"]: item for item in candidates}
    page_text = " ".join(
        part for part in [page_description or "", f"第{page_number}页" if page_number else ""] if part
    )

    def _score_candidate(item: Dict, context: str, prefer_background: bool) -> float:
        score = 0.0
        if item["id"] in preferred_set:
            # 推荐列表中的顺序前置
            try:
                order_bonus = max(0.0, 1.2 - 0.1 * (preferred_image_ids or []).index(item["id"]))
            except Exception:
                order_bonus = 0.8
            score += order_bonus
        if prefer_background and item.get("is_background"):
            score += 0.6
        if (not prefer_background) and (not item.get("is_background")):
            score += 0.3
        score += _semantic_overlap_score(context, f"{item.get('description', '')} {item.get('url', '')}")
        pixels = int(item.get("width", 0)) * int(item.get("height", 0))
        score += min(0.3, pixels / float(1920 * 1080 * 4))
        score -= 0.35 * float(usage_counter.get(item["id"], 0))
        return score

    def _pick_candidate(context: str, prefer_background: bool) -> Optional[Dict]:
        ranked = sorted(
            candidates,
            key=lambda item: _score_candidate(item, context, prefer_background),
            reverse=True,
        )
        return ranked[0] if ranked else None

    # 第一步：替换占位符 {{img_N}} 并计数
    placeholder_pattern = re.compile(r"\{\{img_(\d+)\}\}")

    def _replace_placeholder(match):
        idx = int(match.group(1))
        chosen = by_id.get(idx)
        if chosen:
            usage_counter[idx] = usage_counter.get(idx, 0) + 1
            return chosen["data_uri"]
        fallback = _pick_candidate(page_text, prefer_background=(page_number == 1))
        if not fallback:
            return match.group(0)
        usage_counter[fallback["id"]] = usage_counter.get(fallback["id"], 0) + 1
        return fallback["data_uri"]

    html = placeholder_pattern.sub(_replace_placeholder, html)

    # 第二步：替换外部 URL（含 fake URL / 随机外链）
    fake_domains = (
        "example.com",
        "placeholder.com",
        "via.placeholder.com",
        "placehold.it",
        "picsum.photos",
        "dummyimage.com",
    )

    def _replace_img_tag(match):
        tag = match.group(0)
        src = _extract_attr(tag, "src")
        if not src:
            return tag
        src_lower = src.lower()
        if src_lower.startswith("data:") or src_lower.startswith("blob:"):
            return tag

        is_external = src_lower.startswith("http://") or src_lower.startswith("https://")
        is_fake = any(domain in src_lower for domain in fake_domains)
        if not (is_external or is_fake):
            return tag

        context = " ".join(
            [
                page_text,
                _extract_attr(tag, "alt"),
                _extract_attr(tag, "title"),
                _extract_attr(tag, "class"),
            ]
        )
        prefer_background = _is_background_img_tag(tag) or page_number == 1
        chosen = _pick_candidate(context, prefer_background=prefer_background)
        if not chosen:
            return tag
        usage_counter[chosen["id"]] = usage_counter.get(chosen["id"], 0) + 1
        return _replace_src(tag, chosen["data_uri"])

    html = _IMG_TAG_RE.sub(_replace_img_tag, html)

    return html


def _clamp_inline_style_px(style_text: str, prop: str, min_value: float, max_value: float) -> str:
    pattern = re.compile(rf"({prop}\s*:\s*)(-?\d+(?:\.\d+)?)px", re.IGNORECASE)

    def _replace(match):
        raw_value = match.group(2)
        try:
            numeric = float(raw_value)
        except Exception:
            return match.group(0)
        clamped = max(min_value, min(max_value, numeric))
        if abs(clamped - round(clamped)) < 0.01:
            value_text = str(int(round(clamped)))
        else:
            value_text = f"{clamped:.2f}".rstrip("0").rstrip(".")
        return f"{match.group(1)}{value_text}px"

    return pattern.sub(_replace, style_text)


def enforce_slide_layout_bounds(html: str, width: int = 1280, height: int = 720) -> str:
    """约束常见定位样式，避免元素明显超出幻灯片画布。"""
    if not html:
        return html

    def _fix_style(match):
        quote = match.group(1)
        style_text = match.group(2)
        fixed = style_text
        fixed = _clamp_inline_style_px(fixed, "left", 0, width)
        fixed = _clamp_inline_style_px(fixed, "top", 0, height)
        fixed = _clamp_inline_style_px(fixed, "right", 0, width)
        fixed = _clamp_inline_style_px(fixed, "bottom", 0, height)
        fixed = _clamp_inline_style_px(fixed, "width", 1, width)
        fixed = _clamp_inline_style_px(fixed, "height", 1, height)
        fixed = _clamp_inline_style_px(fixed, "max-width", 1, width)
        fixed = _clamp_inline_style_px(fixed, "max-height", 1, height)
        return f"style={quote}{fixed}{quote}"

    normalized_html = _INLINE_STYLE_RE.sub(_fix_style, html)

    boundary_style = f"""
<style id="slide-boundary-guard">
html, body {{
  width: {width}px !important;
  height: {height}px !important;
  margin: 0 !important;
  padding: 0 !important;
  overflow: hidden !important;
}}
body {{
  position: relative !important;
}}
img, svg, canvas, video {{
  max-width: 100% !important;
  max-height: 100% !important;
}}
</style>
""".strip()
    if "slide-boundary-guard" in normalized_html:
        return normalized_html
    if "</head>" in normalized_html:
        return normalized_html.replace("</head>", boundary_style + "\n</head>")
    if "<body" in normalized_html:
        return normalized_html.replace("<body", boundary_style + "\n<body", 1)
    return boundary_style + "\n" + normalized_html


async def run_slide_design_agent(
    topic: str,
    outline_content: str,
    search_results: List[Dict],
    deep_thinking_content: str,
    supplement_data: dict,
    num_pages: int,
    powerpoint_type: str = "16:9 Widescreen",
    image_results: Optional[List[Dict]] = None,
    workspace_dir: Optional[str] = None,
) -> AsyncGenerator[dict, None]:
    """运行 SlideDesign agent 生成 PPT"""
    
    if not Config.DEEPPRESENTER_AVAILABLE:
        yield {
            "type": "error",
            "content": "DeepPresenter 模块未加载，无法生成PPT。"
        }
        return
    
    try:
        target_slide_count: Optional[int] = None
        try:
            parsed_pages = int(num_pages) if num_pages is not None else 0
            if parsed_pages > 0:
                target_slide_count = parsed_pages
        except Exception:
            target_slide_count = None

        yield {
            "type": "thinking",
            "content": "已进入幻灯片生成阶段，正在准备设计环境。"
        }

        optimized_outline_content = enhance_outline_with_functional_layouts(
            topic=topic,
            outline_content=outline_content,
        )
        length_factor = estimate_length_factor(f"{topic}\n{optimized_outline_content}")

        # 导入必要模块
        from deeppresenter.agents.slide_design import SlideDesign
        from deeppresenter.agents.env import AgentEnv
        from deeppresenter.utils.typings import InputRequest, PowerPointType, ConvertType, ChatMessage
        from deeppresenter.utils.config import DeepPresenterConfig
        
        # 构建 Markdown 内容
        search_summary = ""
        for i, result in enumerate(search_results[:10], 1):
            title = result.get("title", "")
            snippet = result.get("snippet", "")[:200]
            search_summary += f"{i}. {title}\n   {snippet}\n\n"
        
        # 使用传入的 workspace 或创建临时工作空间
        if workspace_dir:
            workspace = Path(workspace_dir)
            workspace.mkdir(parents=True, exist_ok=True)
        else:
            workspace = Path(tempfile.mkdtemp(prefix="ppt_"))
        md_file = workspace / "manuscript.md"

        # 构建图片素材章节（使用占位符）
        image_section = ""
        image_reference_strategy: Optional[Dict] = None
        if image_results:
            yield {
                "type": "thinking",
                "content": f"正在分析 {len(image_results)} 张候选图片，并生成章节配图建议。"
            }
            try:
                strategy_task = asyncio.create_task(
                    build_image_reference_strategy(
                        topic=topic,
                        outline_content=optimized_outline_content,
                        image_results=image_results,
                    )
                )
                started_at = monotonic()
                last_notice = 0
                while not strategy_task.done():
                    await asyncio.sleep(1.0)
                    elapsed = int(monotonic() - started_at)
                    if elapsed >= 12 and elapsed - last_notice >= 12:
                        last_notice = elapsed
                        yield {
                            "type": "thinking",
                            "content": f"图片策略分析进行中（约 {elapsed} 秒），完成后立即开始逐页生成。"
                        }

                image_reference_strategy = await strategy_task
                if image_reference_strategy:
                    logger.info(
                        "Image reference strategy ready: model=%s, cover=%s, content=%s",
                        image_reference_strategy.get("model"),
                        len(image_reference_strategy.get("cover_candidates") or []),
                        len(image_reference_strategy.get("content_candidates") or []),
                    )
                    yield {
                        "type": "thinking",
                        "content": "图片策略分析完成，正在合并到生成指令中。"
                    }
            except Exception as exc:
                logger.warning("Failed to build image reference strategy: %s", exc)
                yield {
                    "type": "thinking",
                    "content": "图片策略分析未完成，将继续使用基础图片规则生成。"
                }

            image_section = "\n## 可用图片素材\n以下图片已验证可用。在 HTML 的 <img> 标签中，使用 {{img_N}} 作为 src 的值。\n\n"
            index_to_img = {idx: img for idx, img in enumerate(image_results, 1)}

            if image_reference_strategy:
                background_ids = image_reference_strategy.get("cover_candidates") or []
                content_ids = image_reference_strategy.get("content_candidates") or []
                background_candidates = [
                    (idx, index_to_img[idx]) for idx in background_ids if idx in index_to_img
                ]
                content_images = [
                    (idx, index_to_img[idx]) for idx in content_ids if idx in index_to_img
                ]
            else:
                background_candidates = []
                content_images = []

            if not background_candidates and not content_images:
                indexed_images = list(index_to_img.items())
                background_candidates = [
                    (i, img) for i, img in indexed_images if _is_background_candidate(img)
                ]
                content_images = [
                    (i, img) for i, img in indexed_images if not _is_background_candidate(img)
                ]

            image_section += "### 背景候选（仅用于封面/整页背景）\n"
            if background_candidates:
                for i, img in background_candidates:
                    desc = img.get("description", "图片") or "图片"
                    w = img.get("width", 0)
                    h = img.get("height", 0)
                    image_section += f"{i}. {{{{img_{i}}}}} — {desc} ({w}×{h})\n"
            else:
                image_section += "无\n"

            image_section += "\n### 内容配图（用于插图/示意，不作背景）\n"
            if content_images:
                for i, img in content_images:
                    desc = img.get("description", "图片") or "图片"
                    w = img.get("width", 0)
                    h = img.get("height", 0)
                    image_section += f"{i}. {{{{img_{i}}}}} — {desc} ({w}×{h})\n"
            else:
                image_section += "无\n"

            if image_reference_strategy:
                image_section += "\n"
                image_section += image_reference_strategy.get("markdown", "")

            image_section += "\n示例：<img src=\"{{img_1}}\" alt=\"描述\">\n\n"
            logger.info(f"Added {len(image_results)} image placeholders to markdown")

        md_content = f"""# {topic}

## PPT大纲

{optimized_outline_content}

## 参考资料

{search_summary}

## 深度分析

{deep_thinking_content[:2000] if deep_thinking_content else '无'}
{image_section}"""
        md_file.write_text(md_content, encoding="utf-8")
        logger.info(f"Created markdown file at: {md_file}")
        
        # 创建 InputRequest
        ppt_type = PowerPointType.WIDE_SCREEN if "16:9" in powerpoint_type else PowerPointType.STANDARD
        
        # 将大纲内容直接嵌入到 instruction 中
        image_instruction = ""
        if image_results:
            image_instruction = """
⚠️ 重要：markdown 文件中提供了可用图片素材，使用 {{img_N}} 占位符引用。
- 必须使用 <img> 标签引用图片，例如：<img src="{{img_1}}" alt="描述">
- ⛔ 严禁使用 CSS background-image: url() 引用图片（导出 PPTX 时会丢失）
- 背景优先使用纯色或渐变；只有在“背景候选”列表中存在合适图片时才可作为背景
- “内容配图”仅用于插图/示意，禁止用于整页背景
- 封面背景图请用绝对定位 <img> + 半透明遮罩 div 实现
- 严禁编造任何图片 URL，只能使用 {{img_N}} 占位符
- 内容页可在相关内容旁配图以增强视觉效果
"""
            if image_reference_strategy:
                image_instruction += "\n" + image_reference_strategy.get("instruction", "")

        quality_guardrail = build_quality_guardrail(
            length_factor=length_factor,
            has_images=bool(image_results),
        )

        layout_guardrail = """
- 所有页面画布固定为 1280x720，任何元素都必须完整落在画布内。
- 禁止把元素定位到画布外：left/top 不得为负，right/bottom 不得导致越界。
- 单元素宽度不得超过 1200px，高度不得超过 680px，避免遮挡和裁切。
- 关键文本块必须可见，避免超出边界或被容器裁剪。
"""

        enhanced_instruction = f"""{topic}

⭐⭐⭐ 重要：请严格按照以下已生成的 PPT 大纲来创建幻灯片！⭐⭐⭐

{optimized_outline_content}

⭐⭐⭐ 请严格遵循上述大纲结构，不要重新规划内容！⭐⭐⭐
- 每一页的标题和要点已经在大纲中明确列出
- 你的任务是：基于大纲内容，设计精美的 HTML 幻灯片
- 不要修改大纲中的页面数量和结构
- 不要添加大纲中没有的页面
- 专注于视觉设计和排版，让内容更加美观
- 质量约束：
{quality_guardrail}
- 版式边界约束：
{layout_guardrail}
{image_instruction}"""
        
        input_request = InputRequest(
            instruction=enhanced_instruction,
            attachments=[],
            num_pages=str(num_pages) if num_pages else None,
            template=None,
            powerpoint_type=ppt_type,
            convert_type=ConvertType.SLIDE_DESIGN,
        )
        logger.info(f"InputRequest created with enhanced instruction")
        yield {
            "type": "thinking",
            "content": "素材准备完成，开始逐页生成幻灯片。"
        }
        
        # 加载 DeepPresenter 配置对象
        deep_presenter_config = DeepPresenterConfig.load_from_file()
        
        # 创建 AgentEnv 和 SlideDesign agent
        async with AgentEnv(workspace, deep_presenter_config) as agent_env:
            slide_agent = SlideDesign(
                config=deep_presenter_config,
                agent_env=agent_env,
                workspace=workspace,
                language="zh",
                allow_reflection=False,
            )
            
            # 运行并流式返回消息
            slide_count = 0
            stop_generation = False
            saw_slide_tool_call_any = False
            emitted_page_signatures: Dict[int, str] = {}
            emitted_file_signatures: Dict[str, str] = {}
            thinking_reported_pages = set()
            logger.info("SlideDesign loop started. workspace=%s", workspace)
            
            async for message in slide_agent.loop(input_request, str(md_file)):
                if isinstance(message, ChatMessage):
                    # 提取文本内容
                    content_text = ""
                    if isinstance(message.content, str):
                        content_text = message.content
                    elif isinstance(message.content, list):
                        for block in message.content:
                            if isinstance(block, dict) and block.get("type") == "text":
                                content_text += block.get("text", "")
                    payload = _extract_json_payload(content_text) if content_text else None
                    
                    # 过滤不需要的消息
                    skip_content = False
                    if content_text:
                        # 过滤特定模式的消息
                        skip_patterns = [
                            "File downloaded",
                            "Outcome file",
                            "does not exist",
                            "resolution:",
                            "Todo ",
                            "DeepPresenter running",
                            "File written to",
                            "manuscript.md",
                            "markdown",
                            "playwright",
                            "BrowserType.launch",
                            "chromium",
                            "chrome-headless-shell",
                            "playwright install",
                            "PPT not initialized",
                            "initialize_design",
                            "get_slides_summary",
                            "backend-",
                            "httpx - INFO",
                            "INFO - HTTP Request",
                            "DeprecationWarning",
                            "Tool already exists",
                            "Config file",
                        ]
                        for pattern in skip_patterns:
                            if pattern in content_text:
                                skip_content = True
                                break

                        # 过滤 MCP 工具的 JSON 响应消息
                        if not skip_content and payload:
                            if any(
                                key in payload
                                for key in ("message", "details", "next_steps", "progress", "html_file", "error", "errors")
                            ):
                                skip_content = True
                                logger.info(
                                    "Skipping MCP tool JSON response: %s...",
                                    content_text.strip()[:100],
                                )
                    
                    # 处理工具调用
                    has_slide_tool_call = False
                    if message.tool_calls:
                        for tc in message.tool_calls:
                            tool_name = tc.function.name if hasattr(tc, 'function') else str(tc)
                            tool_args = tc.function.arguments if hasattr(tc, 'function') else {}

                            if isinstance(tool_args, str):
                                try:
                                    tool_args = json.loads(tool_args)
                                except:
                                    tool_args = {"data": tool_args}

                            logger.info(f"Tool call: {tool_name}")

                            tool_name_lower = tool_name.lower()
                            is_slide_tool = tool_name_lower in {"insert_page", "update_page", "write_file", "create_page", "add_page"} or (
                                "insert" in tool_name_lower and "page" in tool_name_lower
                            )
                            if is_slide_tool:
                                has_slide_tool_call = True
                                saw_slide_tool_call_any = True

                            if is_slide_tool:
                                html_content, file_path, index, action_description = _extract_html_from_tool_args(tool_args)

                                if tool_name_lower == "write_file":
                                    # write_file 可能写入非 HTML 文件，需严格过滤
                                    if not html_content:
                                        try:
                                            if file_path and str(file_path).lower().endswith(".html") and Path(file_path).exists():
                                                html_content = Path(file_path).read_text(encoding="utf-8", errors="ignore")
                                        except Exception:
                                            html_content = ""
                                    if not _looks_like_html(html_content):
                                        continue
                                else:
                                    if not html_content:
                                        html_content = str(tool_args)

                                if not html_content:
                                    continue

                                page_number = _resolve_slide_index(
                                    tool_name_lower=tool_name_lower,
                                    candidate_index=index,
                                    file_path=str(file_path) if file_path else None,
                                    current_max=slide_count,
                                )
                                if page_number is None:
                                    logger.info(
                                        "Skip slide tool without resolvable page index: tool=%s file=%s",
                                        tool_name_lower,
                                        file_path,
                                    )
                                    continue

                                content_signature = hashlib.sha1(
                                    html_content.encode("utf-8", errors="ignore")
                                ).hexdigest()
                                normalized_file_path = None
                                if file_path and str(file_path).lower().endswith(".html"):
                                    try:
                                        normalized_file_path = str(Path(str(file_path)).resolve())
                                    except Exception:
                                        normalized_file_path = str(file_path)

                                if emitted_page_signatures.get(page_number) == content_signature:
                                    logger.info(
                                        "Skip duplicated slide content for page %s (tool=%s)",
                                        page_number,
                                        tool_name_lower,
                                    )
                                    continue
                                if (
                                    normalized_file_path
                                    and emitted_file_signatures.get(normalized_file_path) == content_signature
                                ):
                                    logger.info(
                                        "Skip duplicated slide content from file %s",
                                        normalized_file_path,
                                    )
                                    continue

                                emitted_page_signatures[page_number] = content_signature
                                if normalized_file_path:
                                    emitted_file_signatures[normalized_file_path] = content_signature

                                if page_number > slide_count:
                                    slide_count = page_number

                                logger.info(f"Created/updated slide {page_number}, HTML length: {len(html_content)}")

                                # 提取页面描述
                                page_description = action_description or (content_text[:100] if content_text else f"第 {page_number} 页")
                                image_preferences = _resolve_image_preferences_for_slide(
                                    page_number=page_number,
                                    page_description=page_description,
                                    image_reference_strategy=image_reference_strategy,
                                )

                                yield {
                                    "type": "slide",
                                    "slide_count": page_number,
                                    "html_content": html_content,
                                    "description": page_description,
                                    "image_preferences": image_preferences,
                                }

                                if target_slide_count and slide_count >= target_slide_count:
                                    yield {
                                        "type": "thinking",
                                        "content": f"已达到目标页数（{target_slide_count} 页），正在完成收尾。"
                                    }
                                    logger.info(
                                        "Reached target slide count %s, stopping further slide generation",
                                        target_slide_count,
                                    )
                                    stop_generation = True
                                    break
                                # 生成 AI 思考文字
                                if page_number not in thinking_reported_pages:
                                    thinking_reported_pages.add(page_number)
                                    thinking = await generate_slide_thinking(page_number, topic)
                                else:
                                    thinking = None
                                if thinking:
                                    yield {
                                        "type": "thinking",
                                        "content": thinking
                                    }

                            elif tool_name_lower == "finalize":
                                logger.info("Detected finalize tool call - PPT generation will complete soon")

                    if stop_generation:
                        break

                    # 工具调用缺失时，尝试从 JSON 消息提取 html_file 兜底解析
                    if (
                        payload
                        and not has_slide_tool_call
                        and not message.tool_calls
                        and not saw_slide_tool_call_any
                    ):
                        fallback_slide = _extract_slide_candidate_from_payload(payload, slide_count)
                        if fallback_slide:
                            fallback_page_number = fallback_slide["slide_count"]
                            fallback_file_path = fallback_slide.get("file_path")
                            fallback_signature = hashlib.sha1(
                                fallback_slide["html_content"].encode("utf-8", errors="ignore")
                            ).hexdigest()
                            normalized_fallback_file = None
                            if fallback_file_path and str(fallback_file_path).lower().endswith(".html"):
                                try:
                                    normalized_fallback_file = str(Path(str(fallback_file_path)).resolve())
                                except Exception:
                                    normalized_fallback_file = str(fallback_file_path)

                            if emitted_page_signatures.get(fallback_page_number) == fallback_signature:
                                logger.info("Skip duplicated fallback slide for page %s", fallback_page_number)
                                continue
                            if (
                                normalized_fallback_file
                                and emitted_file_signatures.get(normalized_fallback_file) == fallback_signature
                            ):
                                logger.info("Skip duplicated fallback slide file %s", normalized_fallback_file)
                                continue

                            emitted_page_signatures[fallback_page_number] = fallback_signature
                            if normalized_fallback_file:
                                emitted_file_signatures[normalized_fallback_file] = fallback_signature

                            if fallback_page_number > slide_count:
                                slide_count = fallback_page_number
                            logger.info(
                                "Recovered slide %s from JSON payload html_file fallback",
                                fallback_page_number,
                            )
                            yield {
                                "type": "slide",
                                "slide_count": fallback_page_number,
                                "html_content": fallback_slide["html_content"],
                                "description": fallback_slide["description"],
                                "image_preferences": _resolve_image_preferences_for_slide(
                                    page_number=fallback_page_number,
                                    page_description=fallback_slide["description"],
                                    image_reference_strategy=image_reference_strategy,
                                ),
                            }

                            if target_slide_count and slide_count >= target_slide_count:
                                yield {
                                    "type": "thinking",
                                    "content": f"已达到目标页数（{target_slide_count} 页），正在完成收尾。"
                                }
                                logger.info(
                                    "Reached target slide count %s via fallback payload, stopping generation",
                                    target_slide_count,
                                )
                                stop_generation = True
                                break
                            if slide_count not in thinking_reported_pages:
                                thinking_reported_pages.add(slide_count)
                                thinking = await generate_slide_thinking(slide_count, topic)
                            else:
                                thinking = None
                            if thinking:
                                yield {
                                    "type": "thinking",
                                    "content": thinking
                                }
                            continue

                    # 发送文本消息
                    if content_text and not skip_content:
                        # 避免与幻灯片进度类文案重复，保留关键说明类文本
                        if has_slide_tool_call and _looks_like_slide_narration(content_text):
                            continue
                        yield {
                            "type": "message",
                            "content": content_text,
                            "role": message.role.value if hasattr(message.role, 'value') else str(message.role)
                        }

                if stop_generation:
                    break
            
            # 完成消息
            yield {
                "type": "complete",
                "slide_count": slide_count,
                "content": f"PPT生成完成！共 {slide_count} 页。"
            }
    
    except Exception as e:
        logger.error(f"Error in PPT generation: {e}")
        import traceback
        traceback.print_exc()
        yield {
            "type": "error",
            "content": f"生成PPT时出错：{str(e)}"
        }
