"""
PPTAgent 对话路由模块

提供对话历史管理 API
"""

import logging
import re
from typing import Optional, List
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from database.connection import get_db
from database import crud

logger = logging.getLogger(__name__)
STALE_RUNNING_TIMEOUT = timedelta(minutes=20)


def _strip_think_tags(text: Optional[str]) -> str:
    if not text:
        return ""
    cleaned = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.IGNORECASE)
    cleaned = re.sub(r"<think>[\s\S]*$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = cleaned.lstrip("：:，,。. ")
    return cleaned


def _normalize_task_status(session) -> str:
    """Normalize session task status for UI consumption."""
    if not session:
        return "idle"

    task_status = session.task_status or "idle"
    stage = getattr(session, "stage", None)

    # waiting_supplement means waiting for user input, not actively running.
    if stage == "waiting_supplement" and task_status == "running":
        return "idle"

    # Defensive fallback for stale data.
    if stage == "completed" and task_status == "running":
        return "completed"

    # Defensive fallback: avoid stale "running" dots after disconnected/failed streams.
    if task_status == "running":
        updated_at = getattr(session, "updated_at", None)
        if isinstance(updated_at, datetime):
            normalized_updated_at = (
                updated_at if updated_at.tzinfo else updated_at.replace(tzinfo=timezone.utc)
            )
            if datetime.now(timezone.utc) - normalized_updated_at > STALE_RUNNING_TIMEOUT:
                return "paused"

    return task_status


async def _resolve_conversation_session_state(
    db: AsyncSession,
    conversation_id: int,
) -> tuple[str, Optional[str], Optional[str], bool]:
    """返回对话状态视图: (task_status, active_session_id, active_stage, changed)."""
    session = await crud.get_active_session_by_conversation(db, conversation_id)
    if not session:
        session = await crud.get_session_by_conversation(db, conversation_id)
    if not session:
        return "idle", None, None, False

    normalized_status = _normalize_task_status(session)
    changed = False
    if normalized_status != (session.task_status or "idle"):
        await crud.update_session(db, session.id, task_status=normalized_status)
        changed = True

    return normalized_status, session.id, session.stage, changed

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
    changed = False
    kept_running_session_id, paused_running_count = await crud.ensure_single_running_session_for_user(db, user_id)
    if paused_running_count > 0:
        changed = True
        logger.warning(
            "Paused %d redundant running sessions for user %s, kept session %s",
            paused_running_count,
            user_id,
            kept_running_session_id,
        )

    stale_count = await crud.pause_stale_running_sessions(
        db,
        stale_before=datetime.utcnow() - STALE_RUNNING_TIMEOUT,
    )
    if stale_count > 0:
        changed = True
        logger.info("Paused %d stale running sessions before listing conversations", stale_count)

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
        
        task_status, active_session_id, active_stage, state_changed = await _resolve_conversation_session_state(
            db, conv.id
        )
        conv_dict["task_status"] = task_status
        conv_dict["active_session_id"] = active_session_id
        conv_dict["active_stage"] = active_stage
        changed = changed or state_changed
        
        # 检查是否有 PPT 项目
        ppt_project = await crud.get_ppt_project_by_conversation(db, conv.id)
        conv_dict["has_ppt"] = ppt_project is not None
        
        result.append(conv_dict)

    if changed:
        await db.commit()

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
    # 显式提交，避免调用方在下一请求中立即读取时出现可见性竞态
    await db.commit()
    await db.refresh(conversation)
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

    stale_count = await crud.pause_stale_running_sessions(
        db,
        stale_before=datetime.utcnow() - STALE_RUNNING_TIMEOUT,
        conversation_id=conversation_id,
    )
    session = await crud.get_active_session_by_conversation(db, conversation_id)
    if not session:
        session = await crud.get_session_by_conversation(db, conversation_id)
    task_status = _normalize_task_status(session)
    if session and task_status != (session.task_status or "idle"):
        await crud.update_session(db, session.id, task_status=task_status)
        stale_count += 1
    if stale_count > 0:
        await db.commit()
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
        clean_title = _strip_think_tags(ppt_project.title) or (ppt_project.title or "")
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
            "title": clean_title,
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
        "active_session_id": session.id if session else None,
        "active_stage": session.stage if session else None,
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

    stale_count = await crud.pause_stale_running_sessions(
        db,
        stale_before=datetime.utcnow() - STALE_RUNNING_TIMEOUT,
        conversation_id=conversation_id,
    )
    session = await crud.get_active_session_by_conversation(db, conversation_id)
    if not session:
        session = await crud.get_session_by_conversation(db, conversation_id)
    task_status = _normalize_task_status(session)
    if session and task_status != (session.task_status or "idle"):
        await crud.update_session(db, session.id, task_status=task_status)
        stale_count += 1
    if stale_count > 0:
        await db.commit()
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
        clean_title = _strip_think_tags(ppt_project.title) or (ppt_project.title or "")
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
            "title": clean_title,
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
        "active_session_id": session.id if session else None,
        "active_stage": session.stage if session else None,
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
