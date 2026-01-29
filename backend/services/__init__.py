"""
PPTAgent 服务模块
"""

from .llm import (
    call_llm_api,
    call_llm_api_stream,
    clean_json_response,
    extract_core_topic
)
from .search import (
    tavily_search_standalone,
    generate_search_queries,
    execute_search,
    stream_search_thinking,
    stream_deep_thinking
)
from .task_planner import (
    check_ppt_intent,
    generate_supplement_info_with_llm,
    stream_task_plan_with_llm,
    stream_outline_generation,
    analyze_user_intent_for_paused_session
)
from .ppt_generator import (
    create_tool_call,
    parse_num_pages,
    generate_slide_thinking,
    run_slide_design_agent
)
from .export_client import export_client
from .share import create_share, get_share, delete_share, get_conversation_shares

__all__ = [
    # LLM
    "call_llm_api",
    "call_llm_api_stream",
    "clean_json_response",
    "extract_core_topic",
    # Search
    "tavily_search_standalone",
    "generate_search_queries",
    "execute_search",
    "stream_search_thinking",
    "stream_deep_thinking",
    # Task Planner
    "check_ppt_intent",
    "generate_supplement_info_with_llm",
    "stream_task_plan_with_llm",
    "stream_outline_generation",
    "analyze_user_intent_for_paused_session",
    # PPT Generator
    "create_tool_call",
    "parse_num_pages",
    "generate_slide_thinking",
    "run_slide_design_agent",
    # Export Client
    "export_client",
    # Share
    "create_share",
    "get_share",
    "delete_share",
    "get_conversation_shares",
]
