import pytest
from src.document import Document

from test.conftest import test_config


@pytest.mark.asyncio
@pytest.mark.llm
async def test_document():
    with open(f"{test_config.document}/source.md", encoding="utf-8") as f:
        markdown_content = f.read()
    cutoff = markdown_content.find("## When (and when not) to use agents")
    image_dir = test_config.document
    await Document.from_markdown(
        markdown_content[:cutoff],
        test_config.language_model,
        test_config.vision_model,
        image_dir,
    )


def test_document_from_dict():
    document = Document(**test_config.get_document_json())
    document.get_overview(include_summary=True)
    document.metainfo
