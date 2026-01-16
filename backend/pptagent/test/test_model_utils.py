import tempfile
from os.path import exists, join

import pytest
from src.model_utils import parse_pdf

from test.conftest import test_config


@pytest.mark.parse
@pytest.mark.asyncio
async def test_parse_pdf():
    with tempfile.TemporaryDirectory(delete=False) as temp_dir:
        await parse_pdf(
            join(test_config.document, "source.pdf"),
            temp_dir,
        )
        assert exists(join(temp_dir, "source.md"))
