import json
import warnings
from pathlib import Path

import pytest

pytest.importorskip("bs4")

from pptagent.model_utils import ModelManager
from pptagent.utils import Config


# warning of zipfile indicates that presentation save failed
def pytest_configure():
    warnings.filterwarnings("error", module=r"zipfile")


# Common test configuration
class TestConfig:
    def __init__(self):
        base_dir = Path(__file__).resolve().parent
        package_dir = base_dir.parent / "pptagent"

        self.template = str(package_dir / "templates" / "default")
        self.document = str(base_dir / "fixtures" / "document")
        self.ppt = str(base_dir / "test.pptx")
        self.models = None

        # Configuration object
        self.config = Config(self.template)
        self._ensure_document_fixture()

    def _ensure_document_fixture(self):
        fixture_dir = Path(self.document)
        fixture_dir.mkdir(parents=True, exist_ok=True)

        source_md = fixture_dir / "source.md"
        if not source_md.exists():
            source_md.write_text(
                "# 示例文档\n\n## 背景\n这是用于单元测试的文档内容。\n",
                encoding="utf-8",
            )

        refined_doc = fixture_dir / "refined_doc.json"
        if not refined_doc.exists():
            refined_doc.write_text(
                json.dumps(
                    {
                        "image_dir": str(fixture_dir),
                        "language": {"lid": "zh"},
                        "metadata": {"title": "测试文档"},
                        "sections": [
                            {
                                "title": "背景",
                                "summary": "背景概述",
                                "markdown_content": "## 背景\n这是用于测试的段落。",
                                "content": [
                                    {
                                        "title": "问题定义",
                                        "content": "这是一个测试子章节内容。",
                                    }
                                ],
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

    def _get_models(self):
        if self.models is not None:
            return self.models
        try:
            self.models = ModelManager()
        except Exception as exc:
            pytest.skip(f"LLM models are not available in current environment: {exc}")
        return self.models

    def get_slide_induction(self):
        """Load slide induction data"""
        return json.loads(
            Path(self.template, "slide_induction.json").read_text(encoding="utf-8")
        )

    def get_document_json(self):
        """Load document JSON"""
        return json.loads(
            Path(self.document, "refined_doc.json").read_text(encoding="utf-8")
        )

    def get_image_stats(self):
        """Load captions data"""
        return json.loads(
            Path(self.template, "image_stats.json").read_text(encoding="utf-8")
        )

    @property
    def language_model(self):
        return self._get_models().language_model

    @property
    def vision_model(self):
        return self._get_models().vision_model

    @property
    def image_model(self):
        return self._get_models().image_model


# Create a global instance
test_config = TestConfig()
