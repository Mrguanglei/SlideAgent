"""
PPTAgent 路由模块
"""

from .conversations import router as conversations_router
from .ppt import router as ppt_router
from .export import router as export_router
from .knowledge import router as knowledge_router

__all__ = [
    "conversations_router", 
    "ppt_router", 
    "export_router",
    "knowledge_router",
]
