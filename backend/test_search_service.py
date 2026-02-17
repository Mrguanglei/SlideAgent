import asyncio
import importlib.util
import sys
import types
from pathlib import Path


def _load_search_module(monkeypatch):
    fake_services_pkg = types.ModuleType("services")
    fake_services_pkg.__path__ = []

    fake_llm_module = types.ModuleType("services.llm")

    async def _placeholder_call_llm_api(*args, **kwargs):
        return ""

    fake_llm_module.call_llm_api = _placeholder_call_llm_api
    fake_llm_module.call_llm_api_stream = None
    fake_llm_module.extract_core_topic = lambda topic: topic

    monkeypatch.setitem(sys.modules, "services", fake_services_pkg)
    monkeypatch.setitem(sys.modules, "services.llm", fake_llm_module)

    module_path = Path(__file__).resolve().parent / "services" / "search.py"
    spec = importlib.util.spec_from_file_location("services.search", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_generate_search_queries_returns_at_most_three_items(monkeypatch):
    search = _load_search_module(monkeypatch)

    async def fake_call_llm_api(*args, **kwargs):
        return "1. alpha\n2. beta\n3. gamma\n4. delta\n2. beta"

    monkeypatch.setattr(search, "call_llm_api", fake_call_llm_api)
    monkeypatch.setattr(search, "extract_core_topic", lambda _: "topic")

    result = asyncio.run(search.generate_search_queries("anything", {}))

    assert result == ["alpha", "beta", "gamma"]
    assert len(result) == 3


def test_execute_search_supports_function_tool_fn(monkeypatch):
    search = _load_search_module(monkeypatch)

    class FakeFunctionTool:
        @staticmethod
        async def fn(query: str, max_results: int = 10):
            return {
                "results": [
                    {
                        "title": f"title-{query}",
                        "url": "https://example.com/item",
                        "content": "content body",
                    }
                ]
            }

    monkeypatch.setattr(search, "search_web", FakeFunctionTool())
    monkeypatch.setattr(search.Config, "TAVILY_AVAILABLE", False)

    result = asyncio.run(search.execute_search("ai医疗", max_results=5))

    assert len(result) == 1
    assert result[0]["title"] == "title-ai医疗"
    assert result[0]["url"] == "https://example.com/item"


def test_stream_search_thinking_uses_local_summary(monkeypatch):
    search = _load_search_module(monkeypatch)

    async def _collect():
        chunks = []
        async for chunk in search.stream_search_thinking(
            query="AI 医疗",
            search_results=[{"title": "案例A"}, {"title": "案例B"}],
            round_num=1,
            total_rounds=3,
        ):
            chunks.append(chunk)
        return "".join(chunks)

    result = asyncio.run(_collect())

    assert "第 1/3 轮已获得 2 条信息" in result
    assert "案例A" in result
    assert "继续下一轮检索" in result


def test_stream_deep_thinking_does_not_call_llm_stream(monkeypatch):
    search = _load_search_module(monkeypatch)

    async def _should_not_be_called(*args, **kwargs):
        raise AssertionError("call_llm_api_stream should not be called")

    monkeypatch.setattr(search, "call_llm_api_stream", _should_not_be_called)

    async def _collect():
        chunks = []
        async for chunk in search.stream_deep_thinking(
            topic="AI 医疗创新",
            search_results=[{"title": "行业报告", "snippet": "覆盖市场规模和临床落地进展"}],
        ):
            chunks.append(chunk)
        return "".join(chunks)

    result = asyncio.run(_collect())

    assert "AI 医疗创新" in result
    assert "行业报告" in result
    assert "下一步进入大纲生成与页面设计阶段" in result
