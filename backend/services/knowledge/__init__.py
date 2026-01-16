"""
知识库服务模块

提供文档解析、文本分块、LLM 处理、向量存储和任务队列功能。
"""

from .document_parser import DocumentParser
from .text_splitter import TokenTextSplitter, SentenceSplitter, TextChunk
from .llm_processor import (
    LLMConfig,
    LLMProcessor,
    EmbeddingProcessor,
    extract_keywords,
    generate_summary,
    embed_text,
)
from .knowledge_service import KnowledgeService
from .task_queue import (
    task_queue,
    DocumentTaskQueue,
    TaskPriority,
    TaskStatus,
    Task,
    init_task_queue,
    shutdown_task_queue,
)

__all__ = [
    # 文档解析
    "DocumentParser",
    
    # 文本分块
    "TokenTextSplitter",
    "SentenceSplitter",
    "TextChunk",
    
    # LLM 处理
    "LLMConfig",
    "LLMProcessor",
    "EmbeddingProcessor",
    "extract_keywords",
    "generate_summary",
    "embed_text",
    
    # 主服务
    "KnowledgeService",
    
    # 任务队列
    "task_queue",
    "DocumentTaskQueue",
    "TaskPriority",
    "TaskStatus",
    "Task",
    "init_task_queue",
    "shutdown_task_queue",
]
