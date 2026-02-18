import asyncio
import base64
import importlib.util
import sys
import types
from pathlib import Path


def _load_image_reference_module(monkeypatch):
    fake_services_pkg = types.ModuleType("services")
    fake_services_pkg.__path__ = []

    fake_llm_module = types.ModuleType("services.llm")

    async def _placeholder_call_llm_api_with_config(*args, **kwargs):
        return "{}"

    fake_llm_module.call_llm_api_with_config = _placeholder_call_llm_api_with_config

    fake_utils_pkg = types.ModuleType("utils")
    fake_utils_pkg.__path__ = []
    fake_config_module = types.ModuleType("utils.config")

    class _FakeConfig:
        IMAGE_REFERENCE_MODEL = "gemini-3-pro-high"
        IMAGE_REFERENCE_API_KEY = "test-key"
        IMAGE_REFERENCE_BASE_URL = "http://test-llm.local/v1"
        IMAGE_REFERENCE_MAX_IMAGES = 12
        IMAGE_REFERENCE_CONCURRENCY = 3
        IMAGE_REFERENCE_TIMEOUT_SECONDS = 35
        IMAGE_REFERENCE_RETRIES = 1

    fake_config_module.Config = _FakeConfig

    monkeypatch.setitem(sys.modules, "services", fake_services_pkg)
    monkeypatch.setitem(sys.modules, "services.llm", fake_llm_module)
    monkeypatch.setitem(sys.modules, "utils", fake_utils_pkg)
    monkeypatch.setitem(sys.modules, "utils.config", fake_config_module)

    module_path = Path(__file__).resolve().parent / "services" / "image_reference.py"
    spec = importlib.util.spec_from_file_location("services.image_reference", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _write_test_png(path: Path):
    png_bytes = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO5f7XgAAAAASUVORK5CYII="
    )
    path.write_bytes(png_bytes)


def test_build_image_reference_strategy_with_model_output(monkeypatch, tmp_path):
    image_reference = _load_image_reference_module(monkeypatch)

    image_path = tmp_path / "img_1.png"
    _write_test_png(image_path)

    async def fake_call_llm_api_with_config(messages, **kwargs):
        user_content = messages[1]["content"]
        if isinstance(user_content, str) and "section_assignments" in user_content:
            return '{"section_assignments":[{"section":"封面页","primary":[1],"backup":[]}]}'
        return (
            '{"type":"Background","description":"医疗AI抽象背景","relevance":9,'
            '"background_fit":9,"usage":"cover_background","reason":"主题高度相关"}'
        )

    monkeypatch.setattr(
        image_reference, "call_llm_api_with_config", fake_call_llm_api_with_config
    )

    strategy = asyncio.run(
        image_reference.build_image_reference_strategy(
            topic="AI医疗创新",
            outline_content="封面页：主题\n技术页：模型方案",
            image_results=[
                {
                    "local_path": str(image_path),
                    "description": "hospital ai innovation",
                    "width": 1920,
                    "height": 1080,
                }
            ],
        )
    )

    assert strategy is not None
    assert strategy["cover_candidates"] == [1]
    assert "视觉模型参考" in strategy["markdown"]
    assert "{{img_1}}" in strategy["instruction"]


def test_build_image_reference_strategy_returns_none_without_endpoint(monkeypatch):
    image_reference = _load_image_reference_module(monkeypatch)
    monkeypatch.setattr(image_reference.Config, "IMAGE_REFERENCE_API_KEY", None, raising=False)

    strategy = asyncio.run(
        image_reference.build_image_reference_strategy(
            topic="AI医疗创新",
            outline_content="封面页：主题",
            image_results=[{"local_path": "/tmp/not-exist.png"}],
        )
    )

    assert strategy is None


def test_build_image_block_prefers_remote_url(monkeypatch):
    image_reference = _load_image_reference_module(monkeypatch)

    block = image_reference._build_image_block(
        {"url": "https://example.com/a.jpg", "local_path": "/tmp/not-used.jpg"}
    )

    assert block is not None
    assert block["image_url"]["url"] == "https://example.com/a.jpg"


def test_build_image_block_prefers_local_data_uri_when_available(monkeypatch, tmp_path):
    image_reference = _load_image_reference_module(monkeypatch)
    image_path = tmp_path / "local.png"
    _write_test_png(image_path)

    block = image_reference._build_image_block(
        {"url": "https://example.com/remote.jpg", "local_path": str(image_path)}
    )

    assert block is not None
    assert block["image_url"]["url"].startswith("data:image/png;base64,")


def test_build_image_reference_strategy_respects_timeout_and_retry_config(monkeypatch, tmp_path):
    image_reference = _load_image_reference_module(monkeypatch)

    image_path = tmp_path / "img_timeout.png"
    _write_test_png(image_path)

    monkeypatch.setattr(image_reference.Config, "IMAGE_REFERENCE_TIMEOUT_SECONDS", 21, raising=False)
    monkeypatch.setattr(image_reference.Config, "IMAGE_REFERENCE_RETRIES", 2, raising=False)
    monkeypatch.setattr(image_reference.Config, "IMAGE_REFERENCE_CONCURRENCY", 2, raising=False)

    observed = {"timeout": None, "retries": None}

    async def fake_call_llm_api_with_config(messages, **kwargs):
        user_content = messages[1]["content"]
        if isinstance(user_content, list):
            observed["timeout"] = kwargs.get("timeout_seconds")
            observed["retries"] = kwargs.get("max_retries")
            return (
                '{"type":"Picture","description":"封面插图","relevance":8,'
                '"background_fit":6,"usage":"content_illustration","reason":"清晰可用"}'
            )
        return '{"section_assignments":[]}'

    monkeypatch.setattr(
        image_reference, "call_llm_api_with_config", fake_call_llm_api_with_config
    )

    strategy = asyncio.run(
        image_reference.build_image_reference_strategy(
            topic="企业创新",
            outline_content="封面页：主题\n第一章：背景",
            image_results=[
                {
                    "local_path": str(image_path),
                    "description": "innovation",
                    "width": 1280,
                    "height": 720,
                }
            ],
        )
    )

    assert strategy is not None
    assert observed["timeout"] == 21.0
    assert observed["retries"] == 2


def test_build_image_reference_strategy_falls_back_to_rule_based_section_assignments(
    monkeypatch, tmp_path
):
    image_reference = _load_image_reference_module(monkeypatch)

    image_path = tmp_path / "img_rule.png"
    _write_test_png(image_path)

    async def fake_call_llm_api_with_config(messages, **kwargs):
        user_content = messages[1]["content"]
        if isinstance(user_content, list):
            return (
                '{"type":"Picture","description":"医疗团队协作","relevance":8,'
                '"background_fit":7,"usage":"content_illustration","reason":"语义相关"}'
            )
        raise RuntimeError("planner unavailable")

    monkeypatch.setattr(
        image_reference, "call_llm_api_with_config", fake_call_llm_api_with_config
    )

    strategy = asyncio.run(
        image_reference.build_image_reference_strategy(
            topic="AI医疗创新",
            outline_content="封面页：主题\n技术路径：模型方案\n总结页：结论",
            image_results=[
                {
                    "local_path": str(image_path),
                    "description": "medical team innovation",
                    "width": 1920,
                    "height": 1080,
                }
            ],
        )
    )

    assert strategy is not None
    assert strategy["section_assignments"]
    assert strategy["section_assignments"][0]["section"] == "封面页"


def test_content_candidates_fallback_keeps_cover_when_it_is_only_usable_image(
    monkeypatch, tmp_path
):
    image_reference = _load_image_reference_module(monkeypatch)

    image_path = tmp_path / "img_single.png"
    _write_test_png(image_path)

    async def fake_call_llm_api_with_config(messages, **kwargs):
        user_content = messages[1]["content"]
        if isinstance(user_content, list):
            return (
                '{"type":"Background","description":"医疗封面图","relevance":9,'
                '"background_fit":9,"usage":"cover_background","reason":"清晰"}'
            )
        return '{"section_assignments":[]}'

    monkeypatch.setattr(
        image_reference, "call_llm_api_with_config", fake_call_llm_api_with_config
    )

    strategy = asyncio.run(
        image_reference.build_image_reference_strategy(
            topic="AI医疗创新",
            outline_content="封面页：主题\n技术页：模型",
            image_results=[
                {
                    "local_path": str(image_path),
                    "description": "medical ai hero image",
                    "width": 1920,
                    "height": 1080,
                }
            ],
        )
    )

    assert strategy is not None
    assert strategy["cover_candidates"] == [1]
    assert strategy["content_candidates"] == [1]
