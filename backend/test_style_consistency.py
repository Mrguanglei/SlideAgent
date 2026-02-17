import importlib.util
from pathlib import Path


def _load_style_consistency_module():
    module_path = Path(__file__).resolve().parent / "services" / "style_consistency.py"
    spec = importlib.util.spec_from_file_location("style_consistency", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


style_consistency = _load_style_consistency_module()


def test_extract_style_anchor_reads_font_color_and_tokens():
    html = """
    <html><head><style>
      body { font-family: "PingFang SC", "Microsoft YaHei", sans-serif; }
      .card { border-radius: 16px; box-shadow: 0 12px 24px rgba(0,0,0,.15); }
      h1 { color: #1A4ED8; }
    </style></head><body></body></html>
    """

    anchor = style_consistency.extract_style_anchor(html)

    assert anchor is not None
    assert "PingFang SC" in anchor["font_family"]
    assert anchor["primary_color"].lower() == "#1a4ed8"
    assert anchor["radius"] == "16px"
    assert "0 12px 24px" in anchor["shadow"]


def test_apply_style_anchor_injects_style_guard_once():
    html = "<html><head></head><body><h1>Title</h1></body></html>"
    anchor = {
        "font_family": '"PingFang SC","Microsoft YaHei",sans-serif',
        "primary_color": "#0f172a",
        "radius": "12px",
        "shadow": "0 8px 20px rgba(15,23,42,.18)",
    }

    first = style_consistency.apply_style_anchor(html, anchor)
    second = style_consistency.apply_style_anchor(first, anchor)

    assert 'id="deck-style-consistency-guard"' in first
    assert second.count('id="deck-style-consistency-guard"') == 1
    assert "font-family" in first
    assert "#0f172a" in first
