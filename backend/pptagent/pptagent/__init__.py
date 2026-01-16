"""PPTAgent: Generating and Evaluating Presentations Beyond Text-to-Slides.

This package provides tools to automatically generate presentations from documents,
following a two-phase approach of Analysis and Generation.

For more information, visit: https://github.com/icip-cas/PPTAgent
"""

__version__ = "0.2.16"
__author__ = "Hao Zheng"
__email__ = "wszh712811@gmail.com"


# __init__.py
from .document import Document
from .llms import LLM, AsyncLLM
from .mcp_server import PPTAgentServer
from .model_utils import ModelManager
from .multimodal import ImageLabler
from .pptgen import PPTAgent
from .presentation import Presentation
from .utils import Config, Language

__all__ = [
    "__version__",
    "__author__",
    "__email__",
    "PPTAgent",
    "PPTAgentServer",
    "Document",
    "Presentation",
    "Config",
    "Language",
    "ModelManager",
    "ImageLabler",
    "LLM",
    "AsyncLLM",
]
