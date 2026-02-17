"""
PPT quality helpers adapted from PPTAgent design ideas.

This module keeps the current pipeline unchanged while injecting:
1) functional slide structure hints,
2) text-length control hints by language family,
3) layout usage guidance for text vs multimodal slides.
"""

import re
from typing import List


_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_LATIN_RE = re.compile(r"[A-Za-z]")

_OPENING_KEYWORDS = ("封面", "标题页", "opening", "title slide")
_TOC_KEYWORDS = ("目录", "contents", "table of contents", "toc")
_SECTION_KEYWORDS = ("章节", "section", "过渡页", "section outline")
_ENDING_KEYWORDS = ("结束", "总结", "致谢", "thank", "ending")


def _normalize_outline_lines(outline_content: str) -> List[str]:
    lines = []
    for raw in (outline_content or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        line = re.sub(r"^[\-\*\d\.\)\s]+", "", line).strip()
        if line:
            lines.append(line)
    return lines


def estimate_length_factor(text: str) -> float:
    """Estimate target text length factor inspired by PPTAgent language-family logic."""
    content = text or ""
    cjk_count = len(_CJK_RE.findall(content))
    latin_count = len(_LATIN_RE.findall(content))

    # Assume the template language family is Latin-like in most public templates.
    # CJK output should usually be more compact than Latin output.
    if cjk_count >= latin_count:
        return 0.75
    return 1.20


def enhance_outline_with_functional_layouts(topic: str, outline_content: str) -> str:
    """Ensure outline includes opening/toc/section/ending functional layouts."""
    lines = _normalize_outline_lines(outline_content)
    if not lines:
        lines = [f"{topic}概览"]

    joined = "\n".join(lines).lower()
    has_opening = any(k in joined for k in _OPENING_KEYWORDS)
    has_toc = any(k in joined for k in _TOC_KEYWORDS)
    has_section = any(k in joined for k in _SECTION_KEYWORDS)
    has_ending = any(k in joined for k in _ENDING_KEYWORDS)

    enhanced: List[str] = []
    if not has_opening:
        enhanced.append(f"封面页：{topic}")
    if not has_toc:
        enhanced.append("目录页：核心章节导航")

    enhanced.extend(lines)

    if not has_section and len(lines) >= 4:
        insert_at = min(2, len(enhanced))
        enhanced.insert(insert_at, "章节过渡页：主题章节导入")

    if not has_ending:
        enhanced.append("结束页：结论与致谢")

    # Keep order stable and remove duplicates while preserving first occurrence.
    deduped: List[str] = []
    seen = set()
    for line in enhanced:
        key = line.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(line)

    return "\n".join(deduped)


def build_quality_guardrail(length_factor: float, has_images: bool) -> str:
    image_policy = (
        "优先选择图文混排布局，图片用于内容支撑，避免整页纯装饰图片。"
        if has_images
        else "优先选择信息密度清晰的文本布局，避免空白过多或装饰性元素堆叠。"
    )
    return f"""
- 必须保持功能页结构：封面、目录、章节过渡页、结束页。
- 文本长度控制：以模板同类元素文本容量为基准，目标系数约 {length_factor:.2f}。
- 单页文字过长时，拆分到后续页面，不要挤压字体到不可读。
- {image_policy}
- 每页标题必须直观表达该页结论，不使用模糊标题。
""".strip()
