import importlib.util
import sys
import types
from pathlib import Path


def _load_ppt_generator_module(monkeypatch):
    fake_services_pkg = types.ModuleType("services")
    fake_services_pkg.__path__ = []

    fake_image_reference_module = types.ModuleType("services.image_reference")

    async def _placeholder_build_image_reference_strategy(*args, **kwargs):
        return None

    fake_image_reference_module.build_image_reference_strategy = _placeholder_build_image_reference_strategy

    fake_quality_module = types.ModuleType("services.ppt_quality")
    fake_quality_module.build_quality_guardrail = lambda **kwargs: "guardrail"
    fake_quality_module.enhance_outline_with_functional_layouts = (
        lambda topic, outline_content: outline_content
    )
    fake_quality_module.estimate_length_factor = lambda text: 1.0

    fake_utils_pkg = types.ModuleType("utils")
    fake_utils_pkg.__path__ = []
    fake_config_module = types.ModuleType("utils.config")

    class _FakeConfig:
        DEEPPRESENTER_AVAILABLE = False

    fake_config_module.Config = _FakeConfig

    monkeypatch.setitem(sys.modules, "services", fake_services_pkg)
    monkeypatch.setitem(sys.modules, "services.image_reference", fake_image_reference_module)
    monkeypatch.setitem(sys.modules, "services.ppt_quality", fake_quality_module)
    monkeypatch.setitem(sys.modules, "utils", fake_utils_pkg)
    monkeypatch.setitem(sys.modules, "utils.config", fake_config_module)

    module_path = Path(__file__).resolve().parent / "services" / "ppt_generator.py"
    spec = importlib.util.spec_from_file_location("services.ppt_generator", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_enforce_slide_layout_bounds_clamps_inline_positions(monkeypatch):
    ppt_generator = _load_ppt_generator_module(monkeypatch)

    raw_html = """
<!DOCTYPE html>
<html>
<head><title>test</title></head>
<body>
  <div style="position:absolute; left:-40px; top:760px; width:1600px; height:900px;">A</div>
</body>
</html>
"""

    normalized = ppt_generator.enforce_slide_layout_bounds(raw_html)

    assert "slide-boundary-guard" in normalized
    assert "left:0px" in normalized
    assert "top:720px" in normalized
    assert "width:1280px" in normalized
    assert "height:720px" in normalized


def test_resolve_slide_index_avoids_update_page_inflation(monkeypatch):
    ppt_generator = _load_ppt_generator_module(monkeypatch)

    resolved_insert = ppt_generator._resolve_slide_index(
        tool_name_lower="insert_page",
        candidate_index=3,
        file_path=None,
        current_max=2,
    )
    resolved_update = ppt_generator._resolve_slide_index(
        tool_name_lower="update_page",
        candidate_index=None,
        file_path=None,
        current_max=5,
    )

    assert resolved_insert == 3
    assert resolved_update == 5


def test_replace_image_placeholders_prefers_recommended_image_ids(monkeypatch):
    ppt_generator = _load_ppt_generator_module(monkeypatch)

    monkeypatch.setattr(
        ppt_generator,
        "_image_to_data_uri",
        lambda local_path: f"data://{Path(local_path).name}",
    )

    html = '<img src="https://example.com/cover.jpg" alt="医疗封面图">'
    usage_counter = {}
    replaced = ppt_generator.replace_image_placeholders(
        html,
        image_results=[
            {
                "local_path": "/tmp/img_1.jpg",
                "description": "普通插图",
                "width": 1024,
                "height": 768,
            },
            {
                "local_path": "/tmp/img_2.jpg",
                "description": "医疗创新封面背景",
                "width": 1920,
                "height": 1080,
            },
        ],
        preferred_image_ids=[2],
        usage_counter=usage_counter,
        page_number=1,
        page_description="封面 医疗创新",
    )

    assert "data://img_2.jpg" in replaced
    assert usage_counter.get(2, 0) >= 1


def test_replace_image_placeholders_rewrites_external_image_by_semantics(monkeypatch):
    ppt_generator = _load_ppt_generator_module(monkeypatch)

    monkeypatch.setattr(
        ppt_generator,
        "_image_to_data_uri",
        lambda local_path: f"data://{Path(local_path).name}",
    )

    html = '<img src="https://cdn.example.org/random.png" alt="临床案例">'
    usage_counter = {}
    replaced = ppt_generator.replace_image_placeholders(
        html,
        image_results=[
            {
                "local_path": "/tmp/finance.jpg",
                "description": "企业财务图表",
                "width": 1280,
                "height": 720,
            },
            {
                "local_path": "/tmp/clinical.jpg",
                "description": "医疗临床案例 病例分析",
                "width": 1200,
                "height": 800,
            },
        ],
        usage_counter=usage_counter,
        page_number=3,
        page_description="临床案例页",
    )

    assert "data://clinical.jpg" in replaced
    assert usage_counter.get(2, 0) >= 1
