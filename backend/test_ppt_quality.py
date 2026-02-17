import importlib.util
from pathlib import Path


def _load_ppt_quality_module():
    module_path = Path(__file__).resolve().parent / "services" / "ppt_quality.py"
    spec = importlib.util.spec_from_file_location("ppt_quality", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


ppt_quality = _load_ppt_quality_module()


def test_enhance_outline_injects_functional_slides_when_missing():
    outline = """
    行业痛点分析
    核心技术能力
    商业模式设计
    落地计划
    """
    enhanced = ppt_quality.enhance_outline_with_functional_layouts("AI医疗创新", outline)

    assert "封面页：" in enhanced
    assert "目录页：" in enhanced
    assert "结束页：" in enhanced


def test_enhance_outline_preserves_existing_functional_slides():
    outline = """
    封面页：AI医疗创新
    目录页：章节导航
    第一章：行业现状
    结束页：谢谢
    """
    enhanced = ppt_quality.enhance_outline_with_functional_layouts("AI医疗创新", outline)

    assert enhanced.count("封面页：AI医疗创新") == 1
    assert enhanced.count("目录页：章节导航") == 1
    assert enhanced.count("结束页：谢谢") == 1


def test_estimate_length_factor_prefers_compact_for_cjk():
    cjk_factor = ppt_quality.estimate_length_factor("人工智能医疗创新与落地")
    latin_factor = ppt_quality.estimate_length_factor("AI healthcare innovation roadmap")

    assert cjk_factor < latin_factor


def test_build_quality_guardrail_contains_length_factor():
    text = ppt_quality.build_quality_guardrail(length_factor=0.75, has_images=True)
    assert "0.75" in text
    assert "功能页结构" in text
