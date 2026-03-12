"""
PPTAgent API 服务器

主入口文件，负责：
1. 初始化 FastAPI 应用
2. 加载配置
3. 初始化数据库
4. 注册路由
5. 提供核心的 /api/chat 流式端点
"""

import os
import sys
import uuid
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

# 添加路径
sys.path.insert(0, str(Path(__file__).parent))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 导入配置
from utils.config import Config

# 导入数据库
from database.connection import init_db, get_db
from database import crud

# 导入路由
from routers import (
    conversations_router,
    ppt_router,
    export_router,
    knowledge_router,
    files_router,
    demo_router,
)

# 导入聊天处理服务
from services.chat_handler import (
    stream_ppt_generation,
    generate_conversation_title_llm,
)
from utils.helpers import (
    normalize_conversation_title,
    strip_think_tags,
)


# ==================== 应用生命周期 ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("=" * 60)
    logger.info("PPTAgent API Server Starting...")
    logger.info("=" * 60)

    Config.load()

    await init_db()
    logger.info("✓ Database initialized")

    from routers.knowledge import init_knowledge_queue
    await init_knowledge_queue()
    logger.info("✓ Knowledge task queue initialized")

    yield

    from services.knowledge.task_queue import shutdown_task_queue
    await shutdown_task_queue()
    logger.info("✓ Knowledge task queue stopped")
    logger.info("PPTAgent API Server Shutting down...")


# ==================== FastAPI 应用 ====================

app = FastAPI(
    title="PPTAgent API",
    description="智能 PPT 生成服务",
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(conversations_router)
app.include_router(ppt_router)
app.include_router(export_router)
app.include_router(knowledge_router)
app.include_router(files_router)
app.include_router(demo_router)


# ==================== Pydantic Models ====================

class ChatRequest(BaseModel):
    instruction: str
    session_id: Optional[str] = None
    conversation_id: Optional[int] = None
    supplement_data: Optional[Dict[str, Any]] = None
    attachments: Optional[List[Dict[str, Any]]] = None
    num_pages: Optional[str] = None
    template: Optional[str] = None
    powerpoint_type: Optional[str] = "16:9 Widescreen"
    convert_type: Optional[str] = "slide_design"
    search_mode: Optional[str] = "auto"


class ConfirmRequest(BaseModel):
    session_id: Optional[str] = None
    conversation_id: Optional[int] = None
    supplement_data: Dict[str, Any]
    search_mode: Optional[str] = None


# ==================== API 端点 ====================

@app.post("/api/chat")
async def chat(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    """聊天接口 - 流式返回"""
    logger.info(f"Chat endpoint called: {request.instruction[:50]}...")

    session_id = request.session_id or str(uuid.uuid4())
    conversation_id = request.conversation_id
    conversation_uuid = None
    is_new_conversation = False
    effective_instruction = request.instruction

    # 如果没有 conversation_id，创建新对话
    if not conversation_id:
        try:
            conversation = await crud.create_conversation(
                db, title=request.instruction[:50] or "新对话", user_id="default_user"
            )
            conversation_id = conversation.id
            conversation_uuid = conversation.uuid
            is_new_conversation = True
            await db.commit()
        except Exception as e:
            logger.error(f"Failed to create conversation: {e}")

    return StreamingResponse(
        stream_ppt_generation(
            instruction=effective_instruction,
            session_id=session_id,
            conversation_id=conversation_id,
            conversation_uuid=conversation_uuid,
            is_new_conversation=is_new_conversation,
            supplement_data=request.supplement_data,
            attachments=request.attachments,
            num_pages=request.num_pages,
            template=request.template,
            powerpoint_type=request.powerpoint_type,
            convert_type=request.convert_type,
            search_mode=request.search_mode,
            db=db,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Session-Id": session_id,
            "X-Conversation-Id": str(conversation_id) if conversation_id else "",
        }
    )


@app.post("/api/confirm")
async def confirm(request: ConfirmRequest, db: AsyncSession = Depends(get_db)):
    """确认补充信息接口"""
    logger.info(f"Confirm endpoint called: session={request.session_id}, conversation={request.conversation_id}")

    # 检查对话是否已经完成
    if request.conversation_id:
        existing_project = await crud.get_ppt_project_by_conversation(db, request.conversation_id)
        if existing_project:
            raise HTTPException(status_code=400, detail="此对话已经完成 PPT 生成，无法重复确认")

    session_id = request.session_id
    if not session_id:
        session_id = str(uuid.uuid4())

    db_session = await crud.get_session(db, session_id)
    if not db_session:
        raise HTTPException(status_code=400, detail="无法确认历史对话，请创建新对话")

    if db_session.stage != "waiting_supplement":
        raise HTTPException(status_code=400, detail=f"当前状态不允许确认（状态：{db_session.stage}）")

    conversation_id = request.conversation_id or db_session.conversation_id
    session_topic = db_session.topic

    # 从 supplement_data 中提取 AI 生成的主题
    generated_topic = request.supplement_data.get("topic")
    if isinstance(generated_topic, str):
        generated_topic = strip_think_tags(generated_topic) or generated_topic
    if generated_topic and generated_topic != session_topic:
        session_topic = generated_topic
        await crud.update_session(db, session_id, topic=generated_topic)
        await db.commit()
        if conversation_id:
            try:
                await crud.update_conversation_title(db, conversation_id, normalize_conversation_title(generated_topic))
                await db.commit()
            except Exception as e:
                logger.error(f"Failed to update conversation title: {e}")

    # 更新补充信息工具调用的状态为 confirmed
    if conversation_id:
        try:
            messages = await crud.get_messages_by_conversation(db, conversation_id)
            for msg in reversed(messages):
                if msg.role == "assistant":
                    tool_calls = await crud.get_tool_calls_by_message(db, msg.id)
                    for tc in tool_calls:
                        if tc.tool_type == "supplement_info" and tc.status == "pending":
                            await crud.update_tool_call_status(db, tc.id, "confirmed", result_json=request.supplement_data)
                            await db.commit()
                            break
                    break
        except Exception as e:
            logger.error(f"Failed to update tool call status: {e}")

    return StreamingResponse(
        stream_ppt_generation(
            instruction=session_topic,
            session_id=session_id,
            conversation_id=conversation_id,
            supplement_data=request.supplement_data,
            search_mode=request.search_mode,
            db=db,
            save_user_message=False,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@app.post("/api/sessions/{session_id}/pause")
async def pause_session(session_id: str, db: AsyncSession = Depends(get_db)):
    """暂停正在运行的任务"""
    session = await crud.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.task_status != "running":
        raise HTTPException(status_code=400, detail=f"Cannot pause session in {session.task_status} status")

    await crud.update_session(db, session_id, task_status="paused")
    await db.commit()
    return {"status": "ok", "session_id": session_id, "task_status": "paused", "stage": session.stage}


@app.get("/api/health")
async def health():
    """健康检查"""
    return {
        "status": "ok",
        "deeppresenter_available": Config.DEEPPRESENTER_AVAILABLE,
        "llm_api_configured": Config.LLM_API_KEY is not None,
        "database_configured": True,
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/models")
async def get_models():
    """获取可用模型列表"""
    return {
        "models": [
            {"id": "pptagent", "name": "PPTAgent", "description": "智能PPT生成"},
            {"id": "design", "name": "Design Mode", "description": "设计模式"},
        ]
    }


# ==================== 主入口 ====================

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
