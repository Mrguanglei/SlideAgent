import importlib.util
from pathlib import Path


def _load_text_splitter_module():
    module_path = Path(__file__).resolve().parent / "services" / "knowledge" / "text_splitter.py"
    spec = importlib.util.spec_from_file_location("text_splitter", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_token_text_splitter_falls_back_when_tiktoken_encoding_unavailable(monkeypatch):
    text_splitter = _load_text_splitter_module()

    class BrokenTikToken:
        @staticmethod
        def get_encoding(_name):
            raise RuntimeError("encoding download failed")

    monkeypatch.setattr(text_splitter, "HAS_TIKTOKEN", True)
    monkeypatch.setattr(text_splitter, "tiktoken", BrokenTikToken)

    splitter = text_splitter.TokenTextSplitter(chunk_size=10, chunk_overlap=0)

    assert splitter.encoder is None
    chunks = splitter.split("这是一个用于离线回退测试的文本。它应该被正常分块。")
    assert len(chunks) >= 1
    assert all(chunk.token_count >= 0 for chunk in chunks)
