from os.path import join

import pytest
from src.document import Document
from src.multimodal import ImageLabler
from src.pptgen import PPTAgent
from src.presentation import Presentation

from test.conftest import test_config


@pytest.mark.asyncio
@pytest.mark.llm
async def test_pptgen():
    pptgen = PPTAgent(
        language_model=test_config.language_model,
        vision_model=test_config.vision_model,
    ).set_reference(
        presentation=Presentation.from_file(
            join(test_config.template, "source.pptx"), test_config.config
        ),
        slide_induction=test_config.get_slide_induction(),
    )
    labeler = ImageLabler(pptgen.presentation, test_config.config)
    labeler.apply_stats(test_config.get_image_stats())

    document = Document(**test_config.get_document_json())
    await pptgen.generate_pres(document, 3)
