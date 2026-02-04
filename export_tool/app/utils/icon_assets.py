"""
Material icon asset helpers.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


DEFAULT_MATERIAL_SYMBOLS_MOUNT = "/material-design-icons/symbols/web"


def get_material_symbols_dir() -> Optional[Path]:
    """Resolve a local directory for Material Symbols SVG assets."""
    env_dir = os.getenv("MATERIAL_SYMBOLS_DIR")
    candidates = []
    if env_dir:
        candidates.append(Path(env_dir))
    candidates.extend(
        [
            Path("/usr/share/nginx/html/material-design-icons/symbols/web"),
            Path(__file__).resolve().parents[2]
            / "dom-to-pptx"
            / "material-design-icons"
            / "symbols"
            / "web",
        ]
    )

    for candidate in candidates:
        try:
            if candidate and candidate.exists():
                return candidate
        except OSError:
            continue
    return None


def get_material_symbols_base_url() -> Optional[str]:
    """Return a base URL for Material Symbols assets if available."""
    env_base = os.getenv("MATERIAL_SYMBOLS_BASE_URL")
    if env_base:
        return env_base.rstrip("/")

    if not get_material_symbols_dir():
        return None

    port = os.getenv("PORT", "8017")
    return f"http://127.0.0.1:{port}{DEFAULT_MATERIAL_SYMBOLS_MOUNT}"
