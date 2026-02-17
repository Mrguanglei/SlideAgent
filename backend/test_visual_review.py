import asyncio
import importlib.util
import sys
import types
from pathlib import Path


def _load_visual_review_module(monkeypatch):
    fake_services_pkg = types.ModuleType("services")
    fake_services_pkg.__path__ = []

    fake_export_client_module = types.ModuleType("services.export_client")
    fake_export_client_module.EXPORT_TOOL_URL = "http://export_tool:8017/api/export_tool"
    fake_export_client_module.EXPORT_TOOL_URL_DEV = "http://localhost:8017/api/export_tool"

    class _FakeExportToolClient:
        def __init__(self, base_url: str):
            self.base_url = base_url

        async def export(self, slides_html, format: str, title: str = "presentation"):
            return b"", "empty.zip"

    fake_export_client_module.ExportToolClient = _FakeExportToolClient

    fake_llm_module = types.ModuleType("services.llm")

    async def _placeholder_call_llm_api_with_config(*args, **kwargs):
        return "{}"

    fake_llm_module.call_llm_api_with_config = _placeholder_call_llm_api_with_config

    fake_utils_pkg = types.ModuleType("utils")
    fake_utils_pkg.__path__ = []
    fake_config_module = types.ModuleType("utils.config")

    class _FakeConfig:
        VISUAL_REVIEW_ENABLED = True
        VISUAL_REVIEW_MIN_SCORE = 78
        VISUAL_REVIEW_MAX_ROUNDS = 1
        VISUAL_REVIEW_TIMEOUT_SECONDS = 30
        VISUAL_REWRITE_TIMEOUT_SECONDS = 40
        DECK_STYLE_REVIEW_ENABLED = True
        DECK_STYLE_START_PAGE = 2
        DECK_STYLE_MIN_SCORE = 75
        DECK_STYLE_MAX_ROUNDS = 1
        DECK_STYLE_REVIEW_TIMEOUT_SECONDS = 28
        DECK_STYLE_REWRITE_TIMEOUT_SECONDS = 35
        IMAGE_REFERENCE_MODEL = "gemini-3-pro-high"
        IMAGE_REFERENCE_API_KEY = "test-key"
        IMAGE_REFERENCE_BASE_URL = "http://test-llm.local/v1"
        PPTAGENT_MODEL = "gemini-3-pro-high"
        PPTAGENT_API_BASE = "http://test-llm.local/v1"
        PPTAGENT_API_KEY = "test-key"

    fake_config_module.Config = _FakeConfig

    monkeypatch.setitem(sys.modules, "services", fake_services_pkg)
    monkeypatch.setitem(sys.modules, "services.export_client", fake_export_client_module)
    monkeypatch.setitem(sys.modules, "services.llm", fake_llm_module)
    monkeypatch.setitem(sys.modules, "utils", fake_utils_pkg)
    monkeypatch.setitem(sys.modules, "utils.config", fake_config_module)

    module_path = Path(__file__).resolve().parent / "services" / "visual_review.py"
    spec = importlib.util.spec_from_file_location("services.visual_review", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_normalize_review_payload_clamps_and_filters(monkeypatch):
    visual_review = _load_visual_review_module(monkeypatch)

    payload = {
        "score": "145",
        "summary": "A" * 500,
        "issues": [
            {"severity": "high", "problem": "p1", "fix": "f1"},
            "invalid",
        ],
        "rewrite_instruction": "B" * 2000,
    }

    normalized = visual_review._normalize_review_payload(payload)

    assert normalized["score"] == 100
    assert len(normalized["issues"]) == 1
    assert normalized["issues"][0]["severity"] == "high"
    assert len(normalized["summary"]) == 300
    assert len(normalized["rewrite_instruction"]) == 1600


def test_refine_slide_visual_review_short_circuit_when_disabled(monkeypatch):
    visual_review = _load_visual_review_module(monkeypatch)
    monkeypatch.setattr(
        visual_review.Config, "VISUAL_REVIEW_ENABLED", False, raising=False
    )

    observed = {"prepare_called": 0}

    async def _prepare(html: str) -> str:
        observed["prepare_called"] += 1
        return html

    raw_html = "<html><body>original</body></html>"
    refined_html, meta = asyncio.run(
        visual_review.refine_slide_with_visual_review(
            raw_html=raw_html,
            topic="test",
            page_description="desc",
            page_number=1,
            prepare_for_render=_prepare,
        )
    )

    assert refined_html == raw_html
    assert meta is None
    assert observed["prepare_called"] == 0


def test_refine_slide_visual_review_short_circuit_when_image_reference_not_configured(
    monkeypatch,
):
    visual_review = _load_visual_review_module(monkeypatch)
    monkeypatch.setattr(
        visual_review.Config, "VISUAL_REVIEW_ENABLED", True, raising=False
    )
    monkeypatch.setattr(
        visual_review.Config, "IMAGE_REFERENCE_API_KEY", None, raising=False
    )
    monkeypatch.setattr(
        visual_review.Config,
        "IMAGE_REFERENCE_BASE_URL",
        "http://example.invalid/v1",
        raising=False,
    )

    observed = {"prepare_called": 0}

    async def _prepare(html: str) -> str:
        observed["prepare_called"] += 1
        return html

    raw_html = "<html><body>original</body></html>"
    refined_html, meta = asyncio.run(
        visual_review.refine_slide_with_visual_review(
            raw_html=raw_html,
            topic="test",
            page_description="desc",
            page_number=1,
            prepare_for_render=_prepare,
        )
    )

    assert refined_html == raw_html
    assert meta is None
    assert observed["prepare_called"] == 0


def test_refine_slide_visual_review_rewrite_flow(monkeypatch):
    visual_review = _load_visual_review_module(monkeypatch)
    monkeypatch.setattr(
        visual_review.Config, "VISUAL_REVIEW_ENABLED", True, raising=False
    )
    monkeypatch.setattr(visual_review.Config, "VISUAL_REVIEW_MAX_ROUNDS", 1, raising=False)
    monkeypatch.setattr(visual_review.Config, "VISUAL_REVIEW_MIN_SCORE", 78, raising=False)

    observed = {"prepare_inputs": [], "review_round": 0}

    async def _prepare(html: str) -> str:
        observed["prepare_inputs"].append(html)
        return html

    async def _fake_review(**kwargs):
        observed["review_round"] += 1
        if observed["review_round"] == 1:
            return {
                "score": 62,
                "summary": "layout crowded",
                "issues": [{"severity": "high", "problem": "crowded", "fix": "reflow"}],
                "rewrite_instruction": "increase whitespace and align blocks",
            }
        return {
            "score": 86,
            "summary": "improved",
            "issues": [],
            "rewrite_instruction": "",
        }

    async def _fake_rewrite(**kwargs):
        return "<html><body>rewritten</body></html>"

    monkeypatch.setattr(visual_review, "review_slide_visual_quality", _fake_review)
    monkeypatch.setattr(visual_review, "rewrite_slide_html_with_feedback", _fake_rewrite)

    refined_html, meta = asyncio.run(
        visual_review.refine_slide_with_visual_review(
            raw_html="<html><body>original</body></html>",
            topic="AI医疗创新",
            page_description="技术路径页",
            page_number=3,
            prepare_for_render=_prepare,
        )
    )

    assert refined_html == "<html><body>rewritten</body></html>"
    assert meta is not None
    assert meta["score"] == 86
    assert meta["optimized"] is True
    assert observed["prepare_inputs"] == [
        "<html><body>original</body></html>",
        "<html><body>rewritten</body></html>",
    ]


def test_review_slide_visual_quality_returns_none_without_image_reference_config(
    monkeypatch,
):
    visual_review = _load_visual_review_module(monkeypatch)
    monkeypatch.setattr(
        visual_review.Config, "VISUAL_REVIEW_ENABLED", True, raising=False
    )
    monkeypatch.setattr(
        visual_review.Config, "IMAGE_REFERENCE_API_KEY", None, raising=False
    )
    monkeypatch.setattr(
        visual_review.Config,
        "IMAGE_REFERENCE_BASE_URL",
        "http://example.invalid/v1",
        raising=False,
    )

    observed = {"render_called": 0}

    async def _fake_render(*args, **kwargs):
        observed["render_called"] += 1
        return "data:image/png;base64,abc"

    monkeypatch.setattr(visual_review, "_render_slide_image_data_uri", _fake_render)

    result = asyncio.run(
        visual_review.review_slide_visual_quality(
            html_for_render="<html><body>test</body></html>",
            topic="topic",
            page_description="desc",
            page_number=1,
        )
    )

    assert result is None
    assert observed["render_called"] == 0


def test_refine_slide_with_deck_style_review_short_circuit_when_disabled(monkeypatch):
    visual_review = _load_visual_review_module(monkeypatch)
    monkeypatch.setattr(
        visual_review.Config, "DECK_STYLE_REVIEW_ENABLED", False, raising=False
    )

    observed = {"prepare_called": 0}

    async def _prepare(html: str) -> str:
        observed["prepare_called"] += 1
        return html

    raw_html = "<html><body>original</body></html>"
    refined_html, meta = asyncio.run(
        visual_review.refine_slide_with_deck_style_review(
            raw_html=raw_html,
            topic="test",
            page_description="desc",
            page_number=3,
            anchor_raw_html="<html><body>anchor</body></html>",
            anchor_page_description="封面页",
            prepare_for_render=_prepare,
        )
    )

    assert refined_html == raw_html
    assert meta is None
    assert observed["prepare_called"] == 0


def test_refine_slide_with_deck_style_review_rewrite_flow(monkeypatch):
    visual_review = _load_visual_review_module(monkeypatch)
    monkeypatch.setattr(
        visual_review.Config, "DECK_STYLE_REVIEW_ENABLED", True, raising=False
    )
    monkeypatch.setattr(visual_review.Config, "DECK_STYLE_START_PAGE", 2, raising=False)
    monkeypatch.setattr(visual_review.Config, "DECK_STYLE_MAX_ROUNDS", 1, raising=False)
    monkeypatch.setattr(visual_review.Config, "DECK_STYLE_MIN_SCORE", 75, raising=False)

    observed = {"prepare_inputs": [], "review_round": 0}

    async def _prepare(html: str) -> str:
        observed["prepare_inputs"].append(html)
        return html

    async def _fake_deck_review(**kwargs):
        observed["review_round"] += 1
        if observed["review_round"] == 1:
            return {
                "score": 63,
                "summary": "style mismatch",
                "issues": [{"severity": "medium", "problem": "color drift", "fix": "align palette"}],
                "rewrite_instruction": "align palette and spacing to anchor",
            }
        return {
            "score": 84,
            "summary": "style aligned",
            "issues": [],
            "rewrite_instruction": "",
        }

    async def _fake_style_rewrite(**kwargs):
        return "<html><body>deck-rewritten</body></html>"

    monkeypatch.setattr(
        visual_review, "review_slide_deck_style_consistency", _fake_deck_review
    )
    monkeypatch.setattr(
        visual_review, "rewrite_slide_html_with_style_anchor", _fake_style_rewrite
    )

    refined_html, meta = asyncio.run(
        visual_review.refine_slide_with_deck_style_review(
            raw_html="<html><body>original</body></html>",
            topic="AI医疗创新",
            page_description="技术路径页",
            page_number=3,
            anchor_raw_html="<html><body>anchor</body></html>",
            anchor_page_description="封面页",
            prepare_for_render=_prepare,
        )
    )

    assert refined_html == "<html><body>deck-rewritten</body></html>"
    assert meta is not None
    assert meta["score"] == 84
    assert meta["optimized"] is True
    # 1 次锚点预处理 + 2 次当前页预处理（重写前后）
    assert observed["prepare_inputs"] == [
        "<html><body>anchor</body></html>",
        "<html><body>original</body></html>",
        "<html><body>deck-rewritten</body></html>",
    ]
