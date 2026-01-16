"""
PPTAgent 数据库模块

提供数据库连接、模型定义和 CRUD 操作
"""

from .connection import (
    engine,
    async_session_factory,
    init_db,
    close_db,
    get_db_session,
    get_db,
    DATABASE_URL
)

from .migrations import run_migrations, drop_knowledge_tables

from .models import (
    Base,
    Conversation,
    Message,
    ToolCall,
    SearchRound,
    SearchResult,
    TaskPlan,
    PPTProject,
    PPTVersion,
    PPTSlide,
    KnowledgeFolder,
    KnowledgeDocument,
    KnowledgeChunk,
)

from .crud import (
    # 对话
    create_conversation,
    get_conversation,
    get_conversations_list,
    update_conversation_title,
    delete_conversation,
    # 消息
    create_message,
    get_messages_by_conversation,
    update_message_content,
    # 工具调用
    create_tool_call,
    update_tool_call_status,
    get_tool_calls_by_message,
    # 搜索
    create_search_round,
    create_search_results,
    get_search_rounds_by_tool_call,
    # 任务规划
    create_task_plan,
    get_task_plan_by_tool_call,
    # PPT 项目
    create_ppt_project,
    get_ppt_project_by_conversation,
    # PPT 版本
    create_ppt_version,
    get_current_ppt_version,
    get_ppt_versions_by_project,
    # PPT 幻灯片
    create_ppt_slide,
    create_ppt_slides_batch,
    get_slides_by_version,
    update_slide_content
)

__all__ = [
    # 连接
    "engine",
    "async_session_factory",
    "init_db",
    "close_db",
    "get_db_session",
    "get_db",
    "DATABASE_URL",
    # 模型
    "Base",
    "Conversation",
    "Message",
    "ToolCall",
    "SearchRound",
    "SearchResult",
    "TaskPlan",
    "PPTProject",
    "PPTVersion",
    "PPTSlide",
    "KnowledgeFolder",
    "KnowledgeDocument",
    "KnowledgeChunk",
    # CRUD
    "create_conversation",
    "get_conversation",
    "get_conversations_list",
    "update_conversation_title",
    "delete_conversation",
    "create_message",
    "get_messages_by_conversation",
    "update_message_content",
    "create_tool_call",
    "update_tool_call_status",
    "get_tool_calls_by_message",
    "create_search_round",
    "create_search_results",
    "get_search_rounds_by_tool_call",
    "create_task_plan",
    "get_task_plan_by_tool_call",
    "create_ppt_project",
    "get_ppt_project_by_conversation",
    "create_ppt_version",
    "get_current_ppt_version",
    "get_ppt_versions_by_project",
    "create_ppt_slide",
    "create_ppt_slides_batch",
    "get_slides_by_version",
    "update_slide_content"
]
