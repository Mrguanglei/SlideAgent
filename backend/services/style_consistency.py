"""
Deterministic deck style consistency helpers.

These helpers provide a non-LLM fallback to reduce style drift across slides:
1) extract style anchor tokens from the first slide,
2) inject a global consistency guard into later slides.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Dict, Optional


_HEX_COLOR_RE = re.compile(r"#[0-9a-fA-F]{3,8}")
_FONT_RE = re.compile(
    r"font-family\s*:\s*([^;\"']+|\"[^\"]+\"|'[^']+')",
    re.IGNORECASE,
)
_RADIUS_RE = re.compile(r"border-radius\s*:\s*([0-9]+(?:\.[0-9]+)?px)", re.IGNORECASE)
_SHADOW_RE = re.compile(r"box-shadow\s*:\s*([^;]+);?", re.IGNORECASE)


def _normalize_color(value: str) -> str:
    color = (value or "").strip().lower()
    if len(color) == 4 and color.startswith("#"):
        # #abc -> #aabbcc
        color = "#" + "".join(ch * 2 for ch in color[1:])
    return color


def _pick_primary_color(html: str) -> Optional[str]:
    colors = [_normalize_color(c) for c in _HEX_COLOR_RE.findall(html or "")]
    if not colors:
        return None
    ignored = {"#ffffff", "#fff", "#000000", "#000", "#f5f5f5", "#f8f8f8", "#fafafa"}
    ranked = [c for c in colors if c not in ignored]
    if not ranked:
        ranked = colors
    counter = Counter(ranked)
    return counter.most_common(1)[0][0] if counter else None


def _pick_font_family(html: str) -> Optional[str]:
    matches = _FONT_RE.findall(html or "")
    if not matches:
        return None
    normalized = []
    for item in matches:
        text = str(item).strip().strip("\"' ")
        if not text:
            continue
        normalized.append(text)
    if not normalized:
        return None
    return Counter(normalized).most_common(1)[0][0]


def _pick_radius(html: str) -> Optional[str]:
    matches = _RADIUS_RE.findall(html or "")
    if not matches:
        return None
    return Counter(matches).most_common(1)[0][0]


def _pick_shadow(html: str) -> Optional[str]:
    matches = [m.strip() for m in _SHADOW_RE.findall(html or "") if str(m).strip()]
    if not matches:
        return None
    return Counter(matches).most_common(1)[0][0]


def extract_style_anchor(html: str) -> Optional[Dict[str, str]]:
    if not html:
        return None
    font_family = _pick_font_family(html)
    primary_color = _pick_primary_color(html)
    radius = _pick_radius(html)
    shadow = _pick_shadow(html)

    anchor: Dict[str, str] = {}
    if font_family:
        anchor["font_family"] = font_family
    if primary_color:
        anchor["primary_color"] = primary_color
    if radius:
        anchor["radius"] = radius
    if shadow:
        anchor["shadow"] = shadow
    return anchor or None


def _insert_style_guard(html: str, style_guard: str) -> str:
    if not html:
        return html
    if 'id="deck-style-consistency-guard"' in html:
        return html
    if "</head>" in html:
        return html.replace("</head>", style_guard + "\n</head>", 1)
    if "<body" in html:
        return html.replace("<body", style_guard + "\n<body", 1)
    return style_guard + "\n" + html


def apply_style_anchor(html: str, anchor: Optional[Dict[str, str]]) -> str:
    if not html or not anchor:
        return html

    font_family = anchor.get("font_family")
    primary_color = anchor.get("primary_color")
    radius = anchor.get("radius")
    shadow = anchor.get("shadow")

    css_lines = ['<style id="deck-style-consistency-guard">']
    if font_family:
        css_lines.append(
            f"html, body, body * {{ font-family: {font_family} !important; }}"
        )
    if primary_color:
        css_lines.append(
            "h1, h2, h3, [class*='title'], [class*='heading'], "
            "[class*='subtitle'] { color: "
            + primary_color
            + " !important; }"
        )
        css_lines.append(
            "[class*='accent'], [class*='highlight'], .badge, .chip, "
            "button { border-color: "
            + primary_color
            + " !important; }"
        )
    if radius:
        css_lines.append(
            ".card, .panel, [class*='card'], [class*='panel'], "
            "[class*='tile'] { border-radius: "
            + radius
            + " !important; }"
        )
    if shadow:
        css_lines.append(
            ".card, .panel, [class*='card'], [class*='panel'], "
            "[class*='tile'] { box-shadow: "
            + shadow
            + " !important; }"
        )
    css_lines.append("</style>")

    style_guard = "\n".join(css_lines)
    return _insert_style_guard(html, style_guard)
