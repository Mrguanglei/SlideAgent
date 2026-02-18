"""
图像参考策略服务

使用独立视觉模型分析候选图片，为 PPT 设计阶段提供可执行的图片选择建议。
"""

import asyncio
import base64
import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse

from PIL import Image

from services.llm import call_llm_api_with_config
from utils.config import Config

logger = logging.getLogger(__name__)

_AVOID_TYPES = {"chart", "diagram", "table", "logo", "icon", "banner"}
_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)
_TOKEN_RE = re.compile(r"[A-Za-z0-9]{2,}|[\u4e00-\u9fff]{2,}")
_CHART_HINTS = (
    "chart", "graph", "table", "diagram", "flow", "plot", "dashboard",
    "图表", "表格", "流程", "架构", "示意", "数据",
)
_ICON_HINTS = ("icon", "logo", "badge", "watermark", "标识", "图标")
_BACKGROUND_HINTS = ("background", "封面", "背景", "wallpaper", "hero", "banner")
_STOPWORDS = {
    "ppt", "page", "slide", "主题", "内容", "章节", "介绍", "分析", "总结", "方案",
    "the", "and", "for", "with", "from", "into", "using", "about",
}


def _strip_json_markdown(text: str) -> str:
    if not text:
        return ""
    match = _JSON_BLOCK_RE.search(text)
    if match:
        return match.group(1).strip()
    return text.strip()


def _safe_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _image_to_data_uri(local_path: str) -> Optional[str]:
    try:
        path = Path(local_path)
        if not path.exists():
            return None
        data = path.read_bytes()
        ext = path.suffix.lower().lstrip(".")
        mime = {
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "webp": "image/webp",
            "gif": "image/gif",
        }.get(ext, "image/jpeg")
        return f"data:{mime};base64,{base64.b64encode(data).decode()}"
    except Exception as exc:
        logger.warning("Failed to read image for reference model: %s (%s)", local_path, exc)
        return None


def _build_image_block(image: Dict) -> Optional[Dict]:
    # Prefer local data URI to avoid upstream model failing to fetch public URLs.
    data_uri = _image_to_data_uri(image.get("local_path", ""))
    if data_uri:
        return {"type": "image_url", "image_url": {"url": data_uri}}

    remote_url = str(image.get("url") or "").strip()
    if remote_url.startswith("http://") or remote_url.startswith("https://"):
        return {"type": "image_url", "image_url": {"url": remote_url}}
    return None


def _extract_outline_sections(outline_content: str, max_sections: int = 12) -> List[str]:
    sections: List[str] = []
    if not outline_content:
        return sections
    for line in outline_content.splitlines():
        text = line.strip().lstrip("-").strip()
        if not text:
            continue
        if len(text) < 4:
            continue
        if "：" in text:
            sections.append(text.split("：", 1)[0].strip())
        else:
            sections.append(text[:32])
        if len(sections) >= max_sections:
            break
    deduped: List[str] = []
    for item in sections:
        if item not in deduped:
            deduped.append(item)
    return deduped


def _tokenize(text: str) -> List[str]:
    if not text:
        return []
    tokens = [tok.lower() for tok in _TOKEN_RE.findall(text)]
    return [tok for tok in tokens if tok not in _STOPWORDS and len(tok) >= 2]


def _keyword_overlap_score(topic: str, sections: List[str], image_text: str) -> float:
    target = set(_tokenize(f"{topic} {' '.join(sections[:8])}"))
    source = set(_tokenize(image_text))
    if not target or not source:
        return 0.0
    overlap = len(target & source)
    return min(1.0, overlap / max(1, min(len(target), 6)))


def _infer_type_from_text(desc: str, url: str, width: int, height: int) -> str:
    text = f"{desc} {url}".lower()
    if any(h in text for h in _CHART_HINTS):
        return "Chart"
    if any(h in text for h in _ICON_HINTS):
        return "Icon"
    ratio = (width / height) if height else 0.0
    if width >= 1200 and height >= 620 and 1.25 <= ratio <= 2.2:
        if any(h in text for h in _BACKGROUND_HINTS):
            return "Background"
        return "Picture"
    return "Picture"


def _calc_quality_score(width: int, height: int) -> float:
    if width <= 0 or height <= 0:
        return 0.0
    pixels = width * height
    # 1600x900 roughly marks "high enough for full-slide visuals".
    res_score = min(1.0, pixels / (1600 * 900)) * 4.5
    ratio = width / height if height else 0.0
    ratio_score = max(0.0, 1.0 - min(abs(ratio - (16 / 9)) / 1.2, 1.0)) * 3.0
    size_score = min(1.0, width / 1200) * 1.25 + min(1.0, height / 675) * 1.25
    return max(0.0, min(10.0, res_score + ratio_score + size_score))


def _build_signature(image: Dict) -> str:
    local_path = str(image.get("local_path") or "").strip()
    if local_path:
        path = Path(local_path)
        if path.exists():
            try:
                with Image.open(path) as img:
                    resized = img.convert("L").resize((8, 8))
                    values = list(resized.getdata())
                avg = sum(values) / max(1, len(values))
                bits = "".join("1" if v >= avg else "0" for v in values)
                return f"ah:{int(bits, 2):016x}"
            except Exception:
                pass

    digest_src = (
        str(image.get("url") or "")
        + "|"
        + str(image.get("description") or "")
        + "|"
        + str(image.get("width") or 0)
        + "x"
        + str(image.get("height") or 0)
    )
    return "md:" + hashlib.md5(digest_src.encode("utf-8", errors="ignore")).hexdigest()[:16]


def _hamming_hex(sig_a: str, sig_b: str) -> int:
    if not sig_a or not sig_b:
        return 64
    if not (sig_a.startswith("ah:") and sig_b.startswith("ah:")):
        return 64
    try:
        a = int(sig_a[3:], 16)
        b = int(sig_b[3:], 16)
    except Exception:
        return 64
    return (a ^ b).bit_count()


def _heuristic_analysis(topic: str, outline_sections: List[str], image: Dict, index: int) -> Dict:
    width = _safe_int(image.get("width"), 0)
    height = _safe_int(image.get("height"), 0)
    ratio = (width / height) if height else 0
    desc = str(image.get("description") or "")
    url = str(image.get("url") or "")
    type_name = _infer_type_from_text(desc, url, width, height)
    quality_score = _calc_quality_score(width, height)
    semantic_score = _keyword_overlap_score(topic, outline_sections, f"{desc} {url}")
    is_bg = width >= 1100 and height >= 620 and 1.25 <= ratio <= 2.1

    relevance = int(round(3 + semantic_score * 5 + quality_score * 0.25))
    relevance = max(1, min(10, relevance))
    if type_name in {"Chart", "Diagram", "Table"}:
        relevance = max(3, relevance - 1)

    background_fit = int(round((quality_score * 0.45) + ((1.0 - min(abs(ratio - (16 / 9)), 1.2) / 1.2) * 4.5)))
    if not is_bg:
        background_fit = min(background_fit, 5)
    if type_name in {"Chart", "Diagram", "Table", "Logo", "Icon", "Banner"}:
        background_fit = min(background_fit, 3)
    background_fit = max(0, min(10, background_fit))

    usage = "content_illustration"
    if background_fit >= 7 and type_name not in {"Chart", "Diagram", "Table", "Logo", "Icon"}:
        usage = "cover_background"
    if type_name.lower() in _AVOID_TYPES:
        usage = "avoid"

    return {
        "index": index,
        "type": type_name,
        "description": desc or "图片",
        "relevance": relevance,
        "background_fit": background_fit,
        "usage": usage,
        "quality_score": round(quality_score, 2),
        "semantic_score": round(semantic_score, 2),
        "source_domain": urlparse(url).netloc if url else "",
        "signature": _build_signature(image),
        "reason": "heuristic_analysis",
    }


def _fallback_analysis(image: Dict, index: int) -> Dict:
    return _heuristic_analysis("", [], image, index)


def _merge_vision_with_heuristic(heuristic: Dict, model_result: Dict) -> Dict:
    merged = dict(heuristic)
    merged_type = str(model_result.get("type", heuristic.get("type", "Picture"))).strip() or "Picture"
    merged_usage = str(model_result.get("usage", heuristic.get("usage", "content_illustration"))).strip()
    model_relevance = max(0, min(10, _safe_int(model_result.get("relevance"), heuristic.get("relevance", 5))))
    model_bg = max(
        0, min(10, _safe_int(model_result.get("background_fit"), heuristic.get("background_fit", 4)))
    )

    merged["type"] = merged_type
    merged["usage"] = merged_usage
    merged["description"] = str(model_result.get("description") or heuristic.get("description") or "图片")[:60]
    merged["reason"] = str(model_result.get("reason") or "vision+heuristic")[:120]
    merged["relevance"] = max(0, min(10, int(round(model_relevance * 0.65 + heuristic.get("relevance", 5) * 0.35))))
    merged["background_fit"] = max(
        0, min(10, int(round(model_bg * 0.65 + heuristic.get("background_fit", 4) * 0.35)))
    )
    if merged_type.lower() in _AVOID_TYPES:
        merged["usage"] = "avoid"
    return merged


def _select_diverse_candidates(
    analyzed_images: List[Dict], ordered_indexes: List[int], limit: int, excluded: Optional[set] = None
) -> List[int]:
    excluded = excluded or set()
    by_index = {item["index"]: item for item in analyzed_images}
    selected: List[int] = []
    selected_signatures: List[str] = []
    selected_domains: set = set()

    for idx in ordered_indexes:
        if idx in excluded:
            continue
        item = by_index.get(idx)
        if not item:
            continue
        signature = str(item.get("signature") or "")
        domain = str(item.get("source_domain") or "")

        duplicate_signature = any(_hamming_hex(signature, exist_sig) <= 6 for exist_sig in selected_signatures)
        if duplicate_signature:
            continue

        # Prefer domain diversity when possible.
        if domain and domain in selected_domains and len(selected) >= 2:
            continue

        selected.append(idx)
        if signature:
            selected_signatures.append(signature)
        if domain:
            selected_domains.add(domain)
        if len(selected) >= limit:
            break

    return selected


def _rule_based_section_assignments(
    sections: List[str], analyzed_images: List[Dict], cover_candidates: List[int], content_candidates: List[int]
) -> List[Dict]:
    by_index = {item["index"]: item for item in analyzed_images}
    used_primary: set = set()
    result: List[Dict] = []
    content_cursor = 0
    content_list = [idx for idx in content_candidates if idx in by_index]

    for section in sections[:12]:
        section_lower = section.lower()
        primary: List[int] = []
        backup: List[int] = []

        if any(key in section_lower for key in ("封面", "标题", "opening", "title")) and cover_candidates:
            for idx in cover_candidates:
                if idx not in used_primary:
                    primary = [idx]
                    used_primary.add(idx)
                    break
            backup = [idx for idx in cover_candidates if idx not in primary][:2]
        elif any(key in section_lower for key in ("目录", "contents", "toc")):
            # TOC page often does not need heavy imagery.
            primary = []
            backup = content_list[:2]
        else:
            while content_cursor < len(content_list):
                candidate = content_list[content_cursor]
                content_cursor += 1
                if candidate in used_primary:
                    continue
                primary = [candidate]
                used_primary.add(candidate)
                break
            backup = [idx for idx in content_list if idx not in primary][:2]

        result.append(
            {
                "section": section,
                "primary": primary[:1],
                "backup": backup[:2],
            }
        )
    return result


async def _analyze_single_image(
    topic: str,
    outline_sections: List[str],
    image: Dict,
    index: int,
    heuristic: Dict,
    semaphore: asyncio.Semaphore,
    timeout_seconds: float,
    max_retries: int,
) -> Dict:
    async with semaphore:
        image_block = _build_image_block(image)
        if not image_block:
            return heuristic

        section_text = "、".join(outline_sections[:8]) if outline_sections else "封面、核心内容、总结"
        prompt = f"""
你是PPT图像策展助手。请判断该图片在主题《{topic}》PPT中的可用性。
PPT章节关键词：{section_text}

只输出 JSON，不要输出其他文本。格式：
{{
  "type": "Background|Picture|Chart|Diagram|Table|Logo|Icon|Banner|Other",
  "description": "一句中文描述（20字以内）",
  "relevance": 0-10,
  "background_fit": 0-10,
  "usage": "cover_background|content_illustration|avoid",
  "reason": "一句理由（30字以内）"
}}
"""
        try:
            response = await call_llm_api_with_config(
                messages=[
                    {"role": "system", "content": "你是严格的JSON输出助手。"},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt.strip()},
                            image_block,
                        ],
                    },
                ],
                model=Config.IMAGE_REFERENCE_MODEL,
                base_url=Config.IMAGE_REFERENCE_BASE_URL,
                api_key=Config.IMAGE_REFERENCE_API_KEY,
                temperature=0.1,
                timeout_seconds=timeout_seconds,
                max_retries=max_retries,
            )
            payload = json.loads(_strip_json_markdown(response))
            model_result = {
                "index": index,
                "type": str(payload.get("type", "Other")).strip() or "Other",
                "description": str(payload.get("description", "图片")).strip()[:60],
                "relevance": max(0, min(10, _safe_int(payload.get("relevance"), 5))),
                "background_fit": max(0, min(10, _safe_int(payload.get("background_fit"), 4))),
                "usage": str(payload.get("usage", "content_illustration")).strip(),
                "reason": str(payload.get("reason", "")).strip()[:80],
            }
            return _merge_vision_with_heuristic(heuristic, model_result)
        except Exception as exc:
            detail = ""
            response = getattr(exc, "response", None)
            if response is not None:
                try:
                    detail = f" body={response.text[:240]}"
                except Exception:
                    detail = ""
            logger.warning("Image reference model failed on img_%s: %s%s", index, exc, detail)
            failed = dict(heuristic)
            failed["reason"] = f"vision_failed: {heuristic.get('reason')}"
            return failed


async def _plan_section_assignments(
    topic: str, sections: List[str], analyzed_images: List[Dict]
) -> List[Dict]:
    if not sections or not analyzed_images:
        return []

    candidates = [
        {
            "index": item["index"],
            "type": item["type"],
            "description": item["description"],
            "relevance": item["relevance"],
            "background_fit": item["background_fit"],
            "usage": item["usage"],
        }
        for item in analyzed_images
    ]
    prompt = f"""
你是PPT图像分配助手。请为主题《{topic}》按章节分配图片候选。
章节：{sections}
候选图片：{candidates}

只输出 JSON，不要输出其他内容。格式：
{{
  "section_assignments": [
    {{"section": "章节名", "primary": [1], "backup": [2]}}
  ]
}}
要求：
1) 每个章节 primary 最多1张，backup 最多2张
2) 尽量使用 relevance 高且 usage != avoid 的图片
3) 禁止把 Chart/Diagram/Table/Logo/Icon 放到封面背景
"""
    try:
        response = await call_llm_api_with_config(
            messages=[
                {"role": "system", "content": "你是严格的JSON输出助手。"},
                {"role": "user", "content": prompt.strip()},
            ],
            model=Config.IMAGE_REFERENCE_MODEL,
            base_url=Config.IMAGE_REFERENCE_BASE_URL,
            api_key=Config.IMAGE_REFERENCE_API_KEY,
            temperature=0.1,
        )
        payload = json.loads(_strip_json_markdown(response))
        assignments = payload.get("section_assignments") or []
        normalized: List[Dict] = []
        for item in assignments:
            section = str(item.get("section", "")).strip()
            if not section:
                continue
            primary = [x for x in (item.get("primary") or []) if isinstance(x, int)]
            backup = [x for x in (item.get("backup") or []) if isinstance(x, int)]
            normalized.append(
                {
                    "section": section,
                    "primary": primary[:1],
                    "backup": backup[:2],
                }
            )
        return normalized
    except Exception as exc:
        logger.warning("Failed to build section assignments with reference model: %s", exc)
        return []


def _build_markdown(
    model_name: str,
    cover_candidates: List[int],
    content_candidates: List[int],
    analyzed_images: List[Dict],
    section_assignments: List[Dict],
) -> str:
    lines: List[str] = []
    lines.append(f"### 视觉模型参考（{model_name}）")
    lines.append("以下结论由视觉模型对图片逐张分析得到：")
    lines.append("")

    if analyzed_images:
        for item in analyzed_images:
            idx = item["index"]
            lines.append(
                (
                    f"- {{{{img_{idx}}}}}: 类型={item['type']}，相关度={item['relevance']}/10，"
                    f"背景适配={item['background_fit']}/10，建议={item['usage']}，说明={item['description']}"
                )
            )
    else:
        lines.append("- 无可分析图片")
    lines.append("")

    if cover_candidates:
        lines.append(
            "封面背景优先："
            + "、".join(f"{{{{img_{idx}}}}}" for idx in cover_candidates[:3])
        )
    else:
        lines.append("封面背景优先：无（建议使用纯色或渐变背景）")

    if content_candidates:
        lines.append(
            "内容配图优先："
            + "、".join(f"{{{{img_{idx}}}}}" for idx in content_candidates[:6])
        )
    else:
        lines.append("内容配图优先：无")

    if section_assignments:
        lines.append("")
        lines.append("章节配图建议：")
        for assignment in section_assignments[:8]:
            section = assignment["section"]
            primary = "、".join(f"{{{{img_{idx}}}}}" for idx in assignment["primary"]) or "无"
            backup = "、".join(f"{{{{img_{idx}}}}}" for idx in assignment["backup"]) or "无"
            lines.append(f"- {section}：主选={primary}，备选={backup}")

    return "\n".join(lines) + "\n"


def _build_instruction_boost(
    cover_candidates: List[int], content_candidates: List[int], section_assignments: List[Dict]
) -> str:
    section_hint = ""
    if section_assignments:
        section_hint = "\n- 优先按“章节配图建议”中的主选图片分配到对应页面。"
    cover_hint = (
        "、".join(f"{{{{img_{idx}}}}}" for idx in cover_candidates[:3]) if cover_candidates else "无"
    )
    content_hint = (
        "、".join(f"{{{{img_{idx}}}}}" for idx in content_candidates[:8]) if content_candidates else "无"
    )
    return f"""
- 请优先使用视觉模型推荐的图片：
  - 封面背景候选：{cover_hint}
  - 内容配图候选：{content_hint}{section_hint}
- 若页面主题与推荐图片不匹配，可跳过，不要强行插图。
""".strip()


async def build_image_reference_strategy(
    topic: str,
    outline_content: str,
    image_results: List[Dict],
) -> Optional[Dict]:
    """分析候选图并返回模型参考策略。"""
    if not image_results:
        return None
    if not Config.IMAGE_REFERENCE_API_KEY or not Config.IMAGE_REFERENCE_BASE_URL:
        logger.warning("Image reference model not configured, skip visual reference analysis")
        return None

    max_images = max(1, min(len(image_results), int(Config.IMAGE_REFERENCE_MAX_IMAGES or 12)))
    analysis_concurrency = max(
        1, min(8, _safe_int(getattr(Config, "IMAGE_REFERENCE_CONCURRENCY", 3), 3))
    )
    analysis_timeout_seconds = max(
        8.0, min(90.0, float(getattr(Config, "IMAGE_REFERENCE_TIMEOUT_SECONDS", 35) or 35))
    )
    analysis_max_retries = max(
        1, min(3, _safe_int(getattr(Config, "IMAGE_REFERENCE_RETRIES", 1), 1))
    )
    logger.info(
        (
            "Image reference strategy enabled: model=%s, candidates=%s, max_images=%s, "
            "concurrency=%s, timeout=%ss, retries=%s"
        ),
        Config.IMAGE_REFERENCE_MODEL,
        len(image_results),
        max_images,
        analysis_concurrency,
        analysis_timeout_seconds,
        analysis_max_retries,
    )
    scoped_images = image_results[:max_images]
    sections = _extract_outline_sections(outline_content)
    heuristic_results = [
        _heuristic_analysis(topic=topic, outline_sections=sections, image=img, index=idx)
        for idx, img in enumerate(scoped_images, 1)
    ]

    # Vision budget: reduce model pressure and keep quality stable under rate limits.
    vision_budget = max(4, min(len(scoped_images), 8))
    pre_ranked = sorted(
        heuristic_results,
        key=lambda item: (
            item.get("relevance", 0),
            item.get("background_fit", 0),
            item.get("quality_score", 0.0),
        ),
        reverse=True,
    )
    vision_indexes = {item["index"] for item in pre_ranked[:vision_budget]}

    semaphore = asyncio.Semaphore(analysis_concurrency)

    tasks = []
    for idx, img in enumerate(scoped_images, 1):
        heuristic = heuristic_results[idx - 1]
        if idx in vision_indexes:
            tasks.append(
                _analyze_single_image(
                    topic,
                    sections,
                    img,
                    idx,
                    heuristic,
                    semaphore,
                    analysis_timeout_seconds,
                    analysis_max_retries,
                )
            )
        else:
            tasks.append(asyncio.sleep(0, result=heuristic))

    analyzed_images = await asyncio.gather(*tasks)
    analyzed_images = sorted(analyzed_images, key=lambda item: item["index"])

    cover_ranked = sorted(
        [
            item
            for item in analyzed_images
            if item["usage"] != "avoid" and str(item["type"]).lower() not in _AVOID_TYPES
        ],
        key=lambda x: (
            x.get("background_fit", 0),
            x.get("relevance", 0),
            x.get("quality_score", 0.0),
        ),
        reverse=True,
    )
    cover_order = [item["index"] for item in cover_ranked if item.get("background_fit", 0) >= 6]
    if not cover_order:
        cover_order = [item["index"] for item in cover_ranked[:3]]
    cover_candidates = _select_diverse_candidates(analyzed_images, cover_order, limit=3)

    content_ranked = sorted(
        [item for item in analyzed_images if item["usage"] != "avoid"],
        key=lambda x: (
            x.get("relevance", 0),
            x.get("quality_score", 0.0),
            x.get("semantic_score", 0.0),
            x.get("background_fit", 0),
        ),
        reverse=True,
    )
    content_order = [item["index"] for item in content_ranked]
    content_candidates = _select_diverse_candidates(
        analyzed_images, content_order, limit=10, excluded=set(cover_candidates[:1])
    )
    if not content_candidates:
        # If only one usable image exists and it is also the cover, keep it as content fallback.
        content_candidates = _select_diverse_candidates(
            analyzed_images, content_order, limit=10, excluded=set()
        )
    if not content_candidates:
        # Last resort: retain at least one image for downstream page composition.
        fallback_order = [item["index"] for item in analyzed_images]
        content_candidates = _select_diverse_candidates(
            analyzed_images, fallback_order, limit=3, excluded=set()
        )

    section_assignments = await _plan_section_assignments(topic, sections, analyzed_images)
    if not section_assignments:
        section_assignments = _rule_based_section_assignments(
            sections=sections,
            analyzed_images=analyzed_images,
            cover_candidates=cover_candidates,
            content_candidates=content_candidates,
        )

    markdown = _build_markdown(
        model_name=Config.IMAGE_REFERENCE_MODEL,
        cover_candidates=cover_candidates,
        content_candidates=content_candidates,
        analyzed_images=analyzed_images,
        section_assignments=section_assignments,
    )
    instruction = _build_instruction_boost(
        cover_candidates=cover_candidates,
        content_candidates=content_candidates,
        section_assignments=section_assignments,
    )
    return {
        "model": Config.IMAGE_REFERENCE_MODEL,
        "markdown": markdown,
        "instruction": instruction,
        "analyzed_images": analyzed_images,
        "cover_candidates": cover_candidates,
        "content_candidates": content_candidates,
        "section_assignments": section_assignments,
    }
