"""
PPTAgent 对话路由模块

提供对话历史管理 API
"""

import logging
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from database.connection import get_db
from database import crud

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


# ==================== Pydantic Models ====================

class ConversationCreate(BaseModel):
    """创建对话请求"""
    title: Optional[str] = None
    user_id: Optional[str] = "default_user"


class ConversationUpdate(BaseModel):
    """更新对话请求"""
    title: Optional[str] = None


class ConversationResponse(BaseModel):
    """对话响应"""
    id: int
    uuid: str
    user_id: str
    title: Optional[str]
    created_at: datetime
    updated_at: datetime
    task_status: Optional[str] = "idle"  # 任务状态

    class Config:
        from_attributes = True


class MessageResponse(BaseModel):
    """消息响应"""
    id: int
    conversation_id: int
    role: str
    content: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


class ToolCallResponse(BaseModel):
    """工具调用响应"""
    id: int
    message_id: int
    tool_type: str
    tool_name: str
    status: str
    arguments: Optional[dict]
    result: Optional[dict]
    created_at: datetime
    
    class Config:
        from_attributes = True


class ConversationDetailResponse(BaseModel):
    """对话详情响应（包含消息和工具调用）"""
    conversation: ConversationResponse
    messages: List[dict]  # 包含消息和关联的工具调用
    ppt_project: Optional[dict] = None  # 关联的 PPT 项目


# ==================== API Endpoints ====================

@router.get("")
async def list_conversations(
    user_id: str = "default_user",
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """获取对话列表（侧边栏用）- 包含任务状态"""
    conversations = await crud.get_conversations(db, user_id=user_id, skip=skip, limit=limit)
    
    # 为每个对话查询关联的 session 获取 task_status
    result = []
    for conv in conversations:
        conv_dict = {
            "id": conv.id,
            "uuid": conv.uuid,
            "user_id": conv.user_id,
            "title": conv.title,
            "created_at": conv.created_at.isoformat() if conv.created_at else None,
            "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
            "task_status": "idle",  # 默认状态
        }
        
        # 查询对话的 session 获取 task_status
        session = await crud.get_session_by_conversation(db, conv.id)
        if session:
            conv_dict["task_status"] = session.task_status
        
        # 检查是否有 PPT 项目
        ppt_project = await crud.get_ppt_project_by_conversation(db, conv.id)
        conv_dict["has_ppt"] = ppt_project is not None
        
        result.append(conv_dict)
    
    return result


@router.post("", response_model=ConversationResponse)
async def create_conversation(
    request: ConversationCreate,
    db: AsyncSession = Depends(get_db)
):
    """创建新对话"""
    conversation = await crud.create_conversation(
        db,
        user_id=request.user_id,
        title=request.title
    )
    return conversation


@router.get("/{conversation_id}")
async def get_conversation(
    conversation_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取单个对话详情（通过数字 ID）"""
    conversation = await crud.get_conversation(db, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # 获取 Session 状态
    session = await crud.get_session_by_conversation(db, conversation_id)
    task_status = session.task_status if session else "idle"
    search_mode = "auto"
    if session and isinstance(session.supplement_data, dict):
        raw_mode = session.supplement_data.get("search_mode")
        if isinstance(raw_mode, str) and raw_mode.strip().lower() in ("auto", "on", "off"):
            search_mode = raw_mode.strip().lower()

    # 获取消息列表
    messages = await crud.get_messages(db, conversation_id)

    # 为每条消息获取关联的工具调用
    messages_with_tools = []
    for msg in messages:
        msg_dict = {
            "id": msg.id,
            "conversation_id": msg.conversation_id,
            "role": msg.role,
            "content": msg.content,
            "created_at": msg.created_at.isoformat(),
            "tool_calls": []
        }

        # 获取该消息的工具调用
        tool_calls = await crud.get_tool_calls_by_message(db, msg.id)
        for tc in tool_calls:
            tc_dict = {
                "id": tc.id,
                "tool_type": tc.tool_type,
                "tool_name": tc.tool_name,
                "status": tc.status,
                "arguments": tc.arguments_json,
                "result": tc.result_json,
                "created_at": tc.created_at.isoformat()
            }

            # 根据工具类型加载关联数据
            if tc.tool_type == "web_search" or tc.tool_type == "search":
                search_rounds = await crud.get_search_rounds_by_tool_call(db, tc.id)
                tc_dict["search_rounds"] = []
                for sr in search_rounds:
                    sr_dict = {
                        "id": sr.id,
                        "round_number": sr.round_number,
                        "query": sr.query,
                        "thinking": sr.thinking_content or "",  # 包含深度思考内容
                        "results": []
                    }
                    results = await crud.get_search_results_by_round(db, sr.id)
                    sr_dict["results"] = [
                        {
                            "id": r.id,
                            "title": r.title,
                            "url": r.url,
                            "snippet": r.content[:200] if r.content else ""
                        }
                        for r in results
                    ]
                    tc_dict["search_rounds"].append(sr_dict)

            elif tc.tool_type == "task_plan":
                task_plan = await crud.get_task_plan_by_tool_call(db, tc.id)
                if task_plan:
                    tc_dict["task_plan"] = {
                        "id": task_plan.id,
                        "plan_content": task_plan.plan_content,
                        "steps": task_plan.steps_json
                    }

            msg_dict["tool_calls"].append(tc_dict)

        messages_with_tools.append(msg_dict)

    # 获取关联的 PPT 项目
    ppt_project = await crud.get_ppt_project_by_conversation(db, conversation_id)
    ppt_project_dict = None
    if ppt_project:
        # 获取最新版本
        latest_version = await crud.get_latest_ppt_version(db, ppt_project.id)
        slides = []
        if latest_version:
            slides_list = await crud.get_ppt_slides(db, latest_version.id)
            slides = [
                {
                    "id": s.id,
                    "page_number": s.page_number,
                    "page_title": s.page_title,
                    "html_content": s.html_content
                }
                for s in slides_list
            ]

        ppt_project_dict = {
            "id": ppt_project.id,
            "title": ppt_project.title,
            "outline_content": ppt_project.outline_content,
            "current_version": latest_version.version_number if latest_version else 1,
            "version_name": latest_version.version_name if latest_version else "V1",
            "slides": slides
        }

    return {
        "conversation": {
            "id": conversation.id,
            "uuid": conversation.uuid,
            "user_id": conversation.user_id,
            "title": conversation.title,
            "created_at": conversation.created_at.isoformat(),
            "updated_at": conversation.updated_at.isoformat(),
            "task_status": task_status
        },
        "search_mode": search_mode,
        "messages": messages_with_tools,
        "ppt_project": ppt_project_dict
    }


@router.get("/uuid/{conversation_uuid}")
async def get_conversation_by_uuid(
    conversation_uuid: str,
    db: AsyncSession = Depends(get_db)
):
    """获取单个对话详情（通过 UUID）"""
    conversation = await crud.get_conversation_by_uuid(db, conversation_uuid)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # 使用 conversation.id 获取其他数据
    conversation_id = conversation.id

    # 获取 Session 状态
    session = await crud.get_session_by_conversation(db, conversation_id)
    task_status = session.task_status if session else "idle"
    search_mode = "auto"
    if session and isinstance(session.supplement_data, dict):
        raw_mode = session.supplement_data.get("search_mode")
        if isinstance(raw_mode, str) and raw_mode.strip().lower() in ("auto", "on", "off"):
            search_mode = raw_mode.strip().lower()

    # 获取消息列表
    messages = await crud.get_messages(db, conversation_id)

    # 为每条消息获取关联的工具调用
    messages_with_tools = []
    for msg in messages:
        msg_dict = {
            "id": msg.id,
            "conversation_id": msg.conversation_id,
            "role": msg.role,
            "content": msg.content,
            "created_at": msg.created_at.isoformat(),
            "tool_calls": []
        }

        # 获取该消息的工具调用
        tool_calls = await crud.get_tool_calls_by_message(db, msg.id)
        for tc in tool_calls:
            tc_dict = {
                "id": tc.id,
                "tool_type": tc.tool_type,
                "tool_name": tc.tool_name,
                "status": tc.status,
                "arguments": tc.arguments_json,
                "result": tc.result_json,
                "created_at": tc.created_at.isoformat()
            }

            # 根据工具类型加载关联数据
            if tc.tool_type == "web_search" or tc.tool_type == "search":
                search_rounds = await crud.get_search_rounds_by_tool_call(db, tc.id)
                tc_dict["search_rounds"] = []
                for sr in search_rounds:
                    sr_dict = {
                        "id": sr.id,
                        "round_number": sr.round_number,
                        "query": sr.query,
                        "thinking": sr.thinking_content or "",  # 包含深度思考内容
                        "results": []
                    }
                    results = await crud.get_search_results_by_round(db, sr.id)
                    sr_dict["results"] = [
                        {
                            "id": r.id,
                            "title": r.title,
                            "url": r.url,
                            "snippet": r.content[:200] if r.content else ""
                        }
                        for r in results
                    ]
                    tc_dict["search_rounds"].append(sr_dict)

            elif tc.tool_type == "task_plan":
                task_plan = await crud.get_task_plan_by_tool_call(db, tc.id)
                if task_plan:
                    tc_dict["task_plan"] = {
                        "id": task_plan.id,
                        "plan_content": task_plan.plan_content,
                        "steps": task_plan.steps_json
                    }

            msg_dict["tool_calls"].append(tc_dict)

        messages_with_tools.append(msg_dict)

    # 获取关联的 PPT 项目
    ppt_project = await crud.get_ppt_project_by_conversation(db, conversation_id)
    ppt_project_dict = None
    if ppt_project:
        # 获取最新版本
        latest_version = await crud.get_latest_ppt_version(db, ppt_project.id)
        slides = []
        if latest_version:
            slides_list = await crud.get_ppt_slides(db, latest_version.id)
            slides = [
                {
                    "id": s.id,
                    "page_number": s.page_number,
                    "page_title": s.page_title,
                    "html_content": s.html_content
                }
                for s in slides_list
            ]

        ppt_project_dict = {
            "id": ppt_project.id,
            "title": ppt_project.title,
            "outline_content": ppt_project.outline_content,
            "current_version": latest_version.version_number if latest_version else 1,
            "version_name": latest_version.version_name if latest_version else "V1",
            "slides": slides
        }

    return {
        "conversation": {
            "id": conversation.id,
            "uuid": conversation.uuid,
            "user_id": conversation.user_id,
            "title": conversation.title,
            "created_at": conversation.created_at.isoformat(),
            "updated_at": conversation.updated_at.isoformat()
        },
        "session_id": session.id if session else None,
        "task_status": task_status,
        "search_mode": search_mode,
        "messages": messages_with_tools,
        "ppt_project": ppt_project_dict
    }


@router.patch("/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_id: int,
    request: ConversationUpdate,
    db: AsyncSession = Depends(get_db)
):
    """更新对话（如修改标题）"""
    conversation = await crud.update_conversation(
        db,
        conversation_id,
        title=request.title
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: int,
    db: AsyncSession = Depends(get_db)
):
    """删除对话"""
    success = await crud.delete_conversation(db, conversation_id)
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"status": "ok", "message": "Conversation deleted"}


@router.get("/search/global")
async def search_global(
    q: str,
    user_id: str = "default_user",
    limit: int = 20,
    db: AsyncSession = Depends(get_db)
):
    """
    全局搜索 - 搜索对话标题和 PPT 项目
    
    返回两类结果：
    - conversations: 匹配的对话列表
    - ppt_projects: 匹配的 PPT 项目列表
    """
    if not q or len(q.strip()) == 0:
        return {"conversations": [], "ppt_projects": []}
    
    query = q.strip()
    
    # 搜索对话
    conversations = await crud.search_conversations(db, user_id=user_id, query=query, limit=limit)
    
    # 搜索 PPT 项目
    ppt_projects = await crud.search_ppt_projects(db, user_id=user_id, query=query, limit=limit)
    
    # 格式化结果
    conv_results = [
        {
            "id": conv.id,
            "title": conv.title,
            "type": "conversation",
            "has_ppt": hasattr(conv, 'ppt_project') and conv.ppt_project is not None,
            "created_at": conv.created_at.isoformat(),
            "updated_at": conv.updated_at.isoformat()
        }
        for conv in conversations
    ]
    
    ppt_results = [
        {
            "id": ppt.id,
            "title": ppt.title,
            "type": "ppt",
            "conversation_id": ppt.conversation_id,
            "slide_count": ppt.slide_count if hasattr(ppt, 'slide_count') else 0,
            "created_at": ppt.created_at.isoformat()
        }
        for ppt in ppt_projects
    ]
    
    return {
        "conversations": conv_results,
        "ppt_projects": ppt_results
    }
