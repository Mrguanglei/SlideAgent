import json
import warnings
from os.path import join

from src.model_utils import ModelManager
from src.utils import Config


# warning of zipfile indicates that presentation save failed
def pytest_configure():
    warnings.filterwarnings("error", module=r"zipfile")


# Common test configuration
class TestConfig:
    def __init__(self):
        self.template = join("runs", "pptx", "default_template")
        self.document = join("runs", "pdf", "57b32a38d68d1e62908a3d4fe77441c2")
        self.ppt = join("test", "test.pptx")
        self.models = ModelManager()

        # Configuration object
        self.config = Config(self.template)

    def get_slide_induction(self):
        """Load slide induction data"""
        return json.load(
            open(join(self.template, "slide_induction.json"), encoding="utf-8")
        )

    def get_document_json(self):
        """Load document JSON"""
        return json.load(
            open(join(self.document, "refined_doc.json"), encoding="utf-8")
        )

    def get_image_stats(self):
        """Load captions data"""
        return json.load(
            open(join(self.template, "image_stats.json"), encoding="utf-8")
        )

    @property
    def language_model(self):
        return self.models.language_model

    @property
    def vision_model(self):
        return self.models.vision_model

    @property
    def image_model(self):
        return self.models.image_model


# Create a global instance
test_config = TestConfig()
