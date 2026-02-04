"""
Font asset helpers for PPTX embedding.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Optional


DEFAULT_FONTS_MOUNT = "/fonts"


def get_font_dir() -> Optional[Path]:
    env_dir = os.getenv("FONT_DIR") or os.getenv("FONTS_DIR")
    candidates = []
    if env_dir:
        candidates.append(Path(env_dir))
    candidates.append(Path(__file__).resolve().parents[2] / "fonts")

    for candidate in candidates:
        try:
            if candidate and candidate.exists():
                return candidate
        except OSError:
            continue
    return None


def get_font_base_url() -> Optional[str]:
    env_base = os.getenv("FONT_BASE_URL")
    if env_base:
        return env_base.rstrip("/")

    if not get_font_dir():
        return None

    port = os.getenv("PORT", "8017")
    return f"http://127.0.0.1:{port}{DEFAULT_FONTS_MOUNT}"


def load_font_manifest() -> List[Dict[str, str]]:
    font_dir = get_font_dir()
    if not font_dir:
        return []
    manifest_path = font_dir / "fonts.json"
    if not manifest_path.exists():
        return []
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    entries = data.get("fonts", data if isinstance(data, list) else [])
    results = []
    for entry in entries:
        name = entry.get("name")
        file = entry.get("file")
        if not name or not file:
            continue
        results.append({"name": str(name), "file": str(file)})
    return results


def resolve_font_configs(html: str, css: str) -> List[Dict[str, str]]:
    entries = load_font_manifest()
    if not entries:
        return []
    base_url = get_font_base_url()
    if not base_url:
        return []

    haystack = f"{html}\n{css}".lower()
    matched = [e for e in entries if e["name"].lower() in haystack]
    if not matched:
        matched = entries

    font_dir = get_font_dir()
    configs = []
    for entry in matched:
        rel_file = entry["file"].replace("\\", "/")
        file_path = Path(rel_file)
        if font_dir and not file_path.is_absolute():
            file_path = font_dir / file_path
        if font_dir and not file_path.exists():
            continue
        configs.append({"name": entry["name"], "url": f"{base_url}/{rel_file}"})
    return configs
