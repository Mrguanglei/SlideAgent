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
import json
import uuid
import logging
import asyncio
import tempfile
import re
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, AsyncGenerator
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


def normalize_conversation_title(text: str, max_len: int = 32) -> str:
    """清洗/截断标题"""
    if not text:
        return "新对话"
    # 移除可能泄露的思考标签
    title = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.IGNORECASE)
    title = re.sub(r"<think>[\s\S]*$", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\s+", " ", title).strip()
    title = title.strip("“”\"'`")
    title = title.lstrip("：:，,。. ")
    if len(title) > max_len:
        title = title[:max_len].rstrip()
    return title if title else "新对话"


def strip_think_tags(text: str) -> str:
    """移除 <think> 标签及其内容，不截断长度。"""
    if not text:
        return ""
    cleaned = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.IGNORECASE)
    cleaned = re.sub(r"<think>[\s\S]*$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = cleaned.lstrip("：:，,。. ")
    return cleaned


def clean_title_simple(text: str, max_len: int = 32, fallback: str = "未命名") -> str:
    """轻量清洗标题，不依赖正则。"""
    if not text:
        return fallback
    title = " ".join(str(text).split()).strip()
    title = title.strip("“”\"'` ")
    while title and title[0] in "：:，,。. ":
        title = title[1:].lstrip()
    if len(title) > max_len:
        title = title[:max_len].rstrip()
    return title or fallback


async def generate_conversation_title_llm(text: str, max_len: int = 32) -> str:
    """用模型生成简短主题标题，失败时回退规则提取"""
    if not text:
        return "新对话"
    prompt = f"""请根据用户输入生成一个简短、明确的PPT主题标题。
- 只输出标题，不要解释
- 不要包含“PPT/演示文稿/幻灯片/帮我/请”等指令词
- 尽量≤{max_len}个字
用户输入：{text[:200]}
"""
    try:
        response = await asyncio.wait_for(
            call_llm_api_with_config(
                messages=[
                    {"role": "system", "content": "你是标题提炼助手，只输出标题。"},
                    {"role": "user", "content": prompt},
                ],
                model=Config.LLM_MODEL,
                base_url=Config.LLM_BASE_URL,
                api_key=Config.LLM_API_KEY,
                temperature=0.3,
                timeout_seconds=12.0,
                max_retries=1,
            ),
            timeout=14.0,
        )
        if response:
            title = normalize_conversation_title(response, max_len=max_len)
            if title:
                return title
    except Exception as e:
        logger.warning(f"Failed to generate title with LLM: {e}")

    fallback = extract_core_topic(text)
    return normalize_conversation_title(fallback, max_len=max_len)


async def generate_ppt_title_llm(
    instruction: str,
    outline_content: str = "",
    supplement_topic: str = "",
    max_len: int = 32
) -> str:
    """用模型生成 PPT 标题，失败时回退到用户指令/补充主题。"""
    parts: List[str] = []
    if supplement_topic:
        parts.append(f"补充主题：{supplement_topic}")
    if outline_content:
        outline_snippet = outline_content[:1200]
        parts.append(f"PPT 大纲：\n{outline_snippet}")
    if instruction:
        parts.append(f"用户需求：{instruction}")
    context = "\n".join(parts)
    prompt = f"""请根据以下信息生成一个简短、明确的PPT标题。
- 只输出标题，不要解释
- 不要包含“PPT/演示文稿/幻灯片/帮我/请”等指令词
- 尽量≤{max_len}个字
{context}
"""
    try:
        response = await asyncio.wait_for(
            call_llm_api_with_config(
                messages=[
                    {"role": "system", "content": "你是标题提炼助手，只输出标题。"},
                    {"role": "user", "content": prompt},
                ],
                model=Config.LLM_MODEL,
                base_url=Config.LLM_BASE_URL,
                api_key=Config.LLM_API_KEY,
                temperature=0.3,
                timeout_seconds=15.0,
                max_retries=1,
            ),
            timeout=18.0,
        )
        title = clean_title_simple(response or "", max_len=max_len, fallback="")
        if title:
            return title
    except Exception as e:
        logger.warning(f"Failed to generate PPT title with LLM: {e}")
    fallback = supplement_topic or instruction or "未命名"
    return clean_title_simple(fallback, max_len=max_len, fallback="未命名")

# 导入配置
from utils.config import Config

# 导入数据库
from database.connection import init_db, get_db, get_db_session
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

# 导入文档解析服务
from services.knowledge.document_parser import DocumentParser

# 导入服务
from services.llm import (
    call_llm_api,
    call_llm_api_stream,
    call_llm_api_with_config,
    extract_core_topic,
)
from services.search import (
    generate_search_queries,
    should_use_web_search,
    execute_search,
    search_and_download_images,
    stream_search_thinking,
    stream_deep_thinking
)
from services.task_planner import (
    check_ppt_intent,
    generate_supplement_info_with_llm,
    stream_task_plan_with_llm,
    stream_outline_generation,
    analyze_user_intent_for_paused_session
)
from services.ppt_generator import (
    create_tool_call,
    parse_num_pages,
    run_slide_design_agent,
    replace_image_placeholders,
    enforce_slide_layout_bounds,
)
from services.resource_inliner import inline_all_resources
from services.visual_review import (
    refine_slide_with_visual_review,
    refine_slide_with_deck_style_review,
)
from services.style_consistency import (
    extract_style_anchor,
    apply_style_anchor,
)
from services.session_guard import (
    SessionBindingError,
    resolve_confirm_session_binding,
)


# ==================== 应用生命周期 ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    logger.info("=" * 60)
    logger.info("PPTAgent API Server Starting...")
    logger.info("=" * 60)
    
    # 加载配置
    Config.load()
    
    # 初始化数据库
    await init_db()
    logger.info("✓ Database initialized")

    # 启动收敛：防止异常中断后残留 running 状态导致多会话“绿点”污染
    async with get_db_session() as startup_db:
        paused_count = await crud.pause_running_sessions(startup_db)
        if paused_count > 0:
            await startup_db.commit()
            logger.warning(
                "Paused %d stale running sessions during startup recovery",
                paused_count,
            )
    
    # 初始化知识库任务队列
    from routers.knowledge import init_knowledge_queue
    await init_knowledge_queue()
    logger.info("✓ Knowledge task queue initialized")
    
    yield
    
    # 关闭时
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

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=Config.CORS_ALLOWED_ORIGINS,
    allow_credentials=Config.CORS_ALLOW_CREDENTIALS,
    allow_methods=Config.CORS_ALLOWED_METHODS,
    allow_headers=Config.CORS_ALLOWED_HEADERS,
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
    """聊天请求"""
    instruction: str
    session_id: Optional[str] = None
    conversation_id: Optional[int] = None  # 新增：关联对话 ID
    conversation_uuid: Optional[str] = None
    supplement_data: Optional[Dict[str, Any]] = None
    attachments: Optional[List[Dict[str, Any]]] = None
    num_pages: Optional[str] = None
    template: Optional[str] = None
    powerpoint_type: Optional[str] = "16:9 Widescreen"
    convert_type: Optional[str] = "slide_design"
    deep_thinking_mode: Optional[bool] = False  # 新增：深度思考模式
    search_mode: Optional[str] = "auto"  # auto | on | off


class ConfirmRequest(BaseModel):
    """确认补充信息请求"""
    session_id: Optional[str] = None
    conversation_id: Optional[int] = None
    conversation_uuid: Optional[str] = None
    supplement_data: Dict[str, Any]
    search_mode: Optional[str] = None


async def _mark_session_not_running_if_needed(
    session_id: Optional[str],
    fallback_status: str = "paused",
) -> None:
    """Best-effort cleanup to avoid stale running sessions after stream interruption."""
    if not session_id:
        return

    try:
        async with get_db_session() as cleanup_db:
            current = await crud.get_session(cleanup_db, session_id)
            if current and current.task_status == "running":
                await crud.update_session(cleanup_db, session_id, task_status=fallback_status)
                logger.warning(
                    "Session %s marked as %s after interrupted stream",
                    session_id,
                    fallback_status,
                )
    except Exception as exc:
        logger.error("Failed to cleanup stale running session %s: %s", session_id, exc)


async def _stream_with_session_guard(
    stream: AsyncGenerator[str, None],
    session_id: Optional[str],
    conversation_id: Optional[int] = None,
    conversation_uuid: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """Wrap stream generator and ensure running status is cleared on abnormal exit."""
    def _inject_scope(chunk: str) -> str:
        if not chunk.startswith("data: "):
            return chunk
        payload = chunk[6:].strip()
        if not payload:
            return chunk
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return chunk
        if not isinstance(data, dict):
            return chunk
        if session_id:
            data.setdefault("session_id", session_id)
        if conversation_id:
            data.setdefault("conversation_id", conversation_id)
        if conversation_uuid:
            data.setdefault("conversation_uuid", conversation_uuid)
        return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

    try:
        async for chunk in stream:
            yield _inject_scope(chunk)
    except asyncio.CancelledError:
        logger.warning("SSE stream cancelled for session %s", session_id)
        await asyncio.shield(
            _mark_session_not_running_if_needed(session_id, fallback_status="paused")
        )
        raise
    except Exception:
        logger.exception("SSE stream failed for session %s", session_id)
        await asyncio.shield(
            _mark_session_not_running_if_needed(session_id, fallback_status="paused")
        )
        raise


async def _refresh_conversation_title_async(conversation_id: int, instruction: str) -> None:
    """Best-effort async title refinement after conversation is created."""
    try:
        title = await generate_conversation_title_llm(instruction)
        if not title:
            return
        async with get_db_session() as db:
            await crud.update_conversation_title(db, conversation_id, title)
            await db.commit()
    except Exception as exc:
        logger.warning(
            "Failed to refresh conversation title for %s: %s",
            conversation_id,
            exc,
        )


# ==================== 核心流式生成函数 ====================

async def stream_ppt_generation(
    instruction: str,
    session_id: str,
    conversation_id: Optional[int] = None,
    conversation_uuid: Optional[str] = None,
    is_new_conversation: bool = False,
    supplement_data: Optional[Dict[str, Any]] = None,
    attachments: Optional[List[Dict[str, Any]]] = None,
    num_pages: Optional[str] = None,
    template: Optional[str] = None,
    powerpoint_type: str = "16:9 Widescreen",
    convert_type: str = "slide_design",
    search_mode: Optional[str] = None,
    db: Optional[AsyncSession] = None,
    save_user_message: bool = True,
    search_results: list = None, 
    deep_thinking_content: str = None, 
    outline_content: str = None
):
    """流式生成 PPT 的核心函数"""
    if db is None:
        async with get_db_session() as managed_db:
            async for chunk in stream_ppt_generation(
                instruction=instruction,
                session_id=session_id,
                conversation_id=conversation_id,
                conversation_uuid=conversation_uuid,
                is_new_conversation=is_new_conversation,
                supplement_data=supplement_data,
                attachments=attachments,
                num_pages=num_pages,
                template=template,
                powerpoint_type=powerpoint_type,
                convert_type=convert_type,
                search_mode=search_mode,
                db=managed_db,
                save_user_message=save_user_message,
                search_results=search_results,
                deep_thinking_content=deep_thinking_content,
                outline_content=outline_content,
            ):
                yield chunk
        return

    logger.info(f"[stream_ppt_generation] START - session={session_id}, conversation={conversation_id}")
    logger.info(f"[stream_ppt_generation] instruction={instruction}, supplement_data={supplement_data}")

    # 定义检查暂停的内部函数
    async def check_pause():
        if not db or not session_id:
            return False
        
        # 重新获取 session 状态
        current_session = await crud.get_session(db, session_id)
        if current_session and current_session.task_status == "paused":
            logger.info(f"[stream_ppt_generation] Task paused by user: {session_id}")
            return True
        return False

    # 如果是新创建的对话，发送 conversation_created 事件
    if is_new_conversation and conversation_uuid:
        logger.info(f"[stream_ppt_generation] Sending conversation_created event")
        yield f"data: {json.dumps({'type': 'conversation_created', 'conversation_id': conversation_id, 'conversation_uuid': conversation_uuid}, ensure_ascii=False)}\n\n"

    # 从数据库获取或创建会话
    session = None
    conversation_user_id: Optional[str] = None
    if db and conversation_id:
        conversation_obj = await crud.get_conversation(db, conversation_id)
        if conversation_obj and conversation_obj.user_id:
            conversation_user_id = conversation_obj.user_id

    if db:
        existing_session = await crud.get_session(db, session_id)
        if existing_session:
            session = {
                "topic": existing_session.topic,
                "stage": existing_session.stage,
                "search_results": existing_session.search_results or [],
                "outline_content": existing_session.outline_content or "",
                "deep_thinking_content": existing_session.deep_thinking_content or "",
                "supplement_data": existing_session.supplement_data or {},
                "conversation_id": existing_session.conversation_id or conversation_id,
                "image_results": [],
                "workspace_dir": str(Path(Config.WORKSPACE_BASE) / session_id),
            }
            # 更新任务状态为 running
            await crud.update_session(db, session_id, task_status="running")
            await db.commit()
        else:
            # 创建新 session，状态为 running
            await crud.create_session(
                db, session_id, instruction, conversation_id, stage="init", task_status="running"
            )
            await db.commit()
            session = {
                "topic": instruction,
                "stage": "init",
                "search_results": [],
                "outline_content": "",
                "deep_thinking_content": "",
                "supplement_data": supplement_data or {},
                "conversation_id": conversation_id,
                "image_results": [],
                "workspace_dir": str(Path(Config.WORKSPACE_BASE) / session_id),
            }

        # 二次收敛并发 running 状态：覆盖“并发请求同时创建 session”导致的竞态
        await crud.pause_running_sessions(
            db,
            keep_session_id=session_id,
            user_id=conversation_user_id,
        )
        await db.commit()
    else:
        # 没有数据库连接时使用临时会话（兜底）
        session = {
            "topic": instruction,
            "stage": "init",
            "search_results": [],
            "outline_content": "",
            "deep_thinking_content": "",
            "supplement_data": supplement_data or {},
            "conversation_id": conversation_id,
            "image_results": [],
            "workspace_dir": str(Path(Config.WORKSPACE_BASE) / session_id),
        }
    
    # 如果提供了 supplement_data，更新会话（即使是空字典也要更新）
    if supplement_data is not None:
        logger.info(f"[stream_ppt_generation] Updating session with supplement_data: {supplement_data}")
        # CRITICAL FIX: Merge with existing supplement_data to preserve file_context and skip_search
        if session["supplement_data"] is None:
            session["supplement_data"] = {}
        session["supplement_data"].update(supplement_data)  # Merge instead of replace!
        session["stage"] = "confirmed"
        if db:
            await crud.update_session(
                db, session_id, 
                stage="confirmed", 
                supplement_data=session["supplement_data"]  # Save merged data
            )
            await db.commit()
        logger.info(f"[stream_ppt_generation] Session stage updated to 'confirmed'")

    # 记录搜索模式（不影响 stage 流转）
    if search_mode:
        normalized_mode = str(search_mode).strip().lower()
        if normalized_mode in ("auto", "on", "off"):
            if session["supplement_data"] is None:
                session["supplement_data"] = {}
            session["supplement_data"]["search_mode"] = normalized_mode
            if db:
                await crud.update_session(
                    db, session_id,
                    supplement_data=session["supplement_data"]
                )
                await db.commit()
    
    # 保存用户消息到数据库（只在需要时保存，避免重复）
    if db and conversation_id and save_user_message:
        try:
            logger.info(f"[stream_ppt_generation] Saving user message to database")
            user_msg = await crud.create_message(db, conversation_id, "user", instruction)
            
            # 保存附件
            if attachments:
                for attachment in attachments:
                    try:
                        await crud.create_message_attachment(
                            db, 
                            user_msg.id, 
                            filename=attachment.get("filename", "unknown"),
                            file_path=attachment.get("file_path", ""),
                            file_size=attachment.get("size", 0),
                            content_type=attachment.get("content_type")
                        )
                    except Exception as e:
                        logger.error(f"Failed to save attachment {attachment}: {e}")

            await db.commit()
        except Exception as e:
            logger.error(f"Failed to save user message: {e}")
    elif not save_user_message:
        logger.info(f"[stream_ppt_generation] Skipping user message save (already saved)")
    
    # ==================== 处理附件内容 (File Context) ====================
    file_context = ""
    if attachments:
        logger.info(f"[stream_ppt_generation] Processing attachments: {len(attachments)}")
        extracted_texts = []
        for att in attachments:
            file_path = att.get("file_path")
            knowledge_id = att.get("knowledge_document_id")

            # 如果是知识库文档，从数据库获取文件路径
            if knowledge_id and not file_path and db:
                try:
                    k_doc = await crud.get_knowledge_document(db, int(knowledge_id))
                    if k_doc:
                        file_path = k_doc.file_path
                        # 更新 filename 以匹配知识库文档名（可选）
                        if not att.get("filename"):
                            att["filename"] = k_doc.filename
                except Exception as e:
                    logger.error(f"Failed to get knowledge document {knowledge_id}: {e}")

            if file_path and os.path.exists(file_path):
                try:
                    # 使用 DocumentParser 解析文件
                    text, meta = await DocumentParser.parse(file_path)
                    extracted_texts.append(f"--- 文件: {att.get('filename', 'unknown')} ---\n{text}\n")
                    logger.info(f"Parsed attachment {att.get('filename')}: {meta}")
                except Exception as e:
                    logger.error(f"Failed to parse attachment {file_path}: {e}")
            else:
                logger.warning(f"Attachment file not found: {file_path}")
        
        if extracted_texts:
            file_context = "\n".join(extracted_texts)
            
            # 确保 supplement_data 初始化
            if "supplement_data" not in session or session["supplement_data"] is None:
                session["supplement_data"] = {}
                
            # 将文件内容存入 supplement_data
            if "file_context" not in session["supplement_data"]:
                session["supplement_data"]["file_context"] = file_context
                # 标记需要跳过搜索
                session["supplement_data"]["skip_search"] = True
                
                # 再次更新数据库，确保 file_context 和 skip_search 被保存
                if db:
                    await crud.update_session(
                        db, session_id, 
                        supplement_data=session["supplement_data"]
                    )
                    await db.commit()
    
    # ==================== 阶段 1: 检查 PPT 意图 ====================
    
    if session["stage"] == "init":
        is_ppt_request = await check_ppt_intent(instruction)
        
        if not is_ppt_request:
            # 非 PPT 请求，直接对话
            response_text = ""
            # 对非 PPT 请求做轻量“平滑流式”，避免模型一次性返回导致前端看起来不流式
            stream_chunk_size = 12
            stream_chunk_delay = 0.01
            async for chunk in call_llm_api_stream([
                {"role": "system", "content": "你是 SlideAgent，一个专业的 PPT 制作助手。用户似乎没有明确的 PPT 制作需求，请友好地回应并引导用户。"},
                {"role": "user", "content": instruction}
            ]):
                response_text += chunk
                if not chunk:
                    continue
                # 构建消息数据（必要时切分大块输出）
                if len(chunk) <= stream_chunk_size:
                    message_data = {
                        'type': 'message',
                        'content': chunk,
                        'role': 'assistant',
                        'streaming': True,
                        'created_at': datetime.now().isoformat()
                    }
                    yield f"data: {json.dumps(message_data, ensure_ascii=False)}\n\n"
                else:
                    for idx in range(0, len(chunk), stream_chunk_size):
                        piece = chunk[idx:idx + stream_chunk_size]
                        message_data = {
                            'type': 'message',
                            'content': piece,
                            'role': 'assistant',
                            'streaming': True,
                            'created_at': datetime.now().isoformat()
                        }
                        yield f"data: {json.dumps(message_data, ensure_ascii=False)}\n\n"
                        # 小延迟让前端渲染出“流式”效果
                        if idx + stream_chunk_size < len(chunk):
                            await asyncio.sleep(stream_chunk_delay)
            
            # 保存助手消息
            if db and conversation_id:
                try:
                    await crud.create_message(db, conversation_id, "assistant", response_text)
                    await db.commit()
                except Exception as e:
                    logger.error(f"Failed to save assistant message: {e}")

            # 更新数据库中的 session 状态（任务完成）
            if db:
                await crud.update_session(db, session_id, task_status="completed")
                await db.commit()

            # 发送完成事件
            yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
            return
        
        # 是 PPT 请求，进入补充信息阶段
        session["stage"] = "supplement_info"
    
    # ==================== 阶段 2: 生成补充信息选项 ====================
    
    if session["stage"] == "supplement_info":
        # 流式发送提示消息（打字机效果）
        greeting_message = '让我先核对下本轮任务的目标和重点偏好，正在梳理您的需求~'
        for char in greeting_message:
            message_data = {
                'type': 'message',
                'content': char,
                'role': 'assistant',
                'streaming': True,
                'created_at': datetime.now().isoformat()
            }
            yield f"data: {json.dumps(message_data, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.03)  # 控制打字速度

        # 发送消息完成标记
        complete_data = {
            'type': 'message',
            'content': '',
            'role': 'assistant',
            'streaming': False
        }
        yield f"data: {json.dumps(complete_data, ensure_ascii=False)}\n\n"

        # 生成补充信息选项
        supplement_info = await generate_supplement_info_with_llm(instruction)
        if isinstance(supplement_info, dict):
            raw_topic = supplement_info.get("topic")
            if isinstance(raw_topic, str):
                cleaned_topic = strip_think_tags(raw_topic) or raw_topic
                supplement_info["topic"] = cleaned_topic
        generated_topic = supplement_info.get("topic") if isinstance(supplement_info, dict) else None

        session["stage"] = "waiting_supplement"
        # 先落库会话状态，避免前端在收到补充信息后立即 confirm 触发 stage 竞态
        if db:
            await crud.update_session(
                db,
                session_id,
                stage="waiting_supplement",
                task_status="idle",
            )
            await db.commit()

        # 发送补充信息工具调用事件
        tool_call_data = {
            'type': 'tool_call',
            'tool_type': 'supplement_info',
            'tool_name': '补充信息',
            'status': 'pending',
            'data': supplement_info
        }
        yield f"data: {json.dumps(tool_call_data, ensure_ascii=False)}\n\n"
        
        # 保存到数据库
        if db and conversation_id:
            try:
                if generated_topic:
                    await crud.update_conversation_title(
                        db, conversation_id, normalize_conversation_title(generated_topic)
                    )
                msg = await crud.create_message(db, conversation_id, "assistant", "让我先核对下本轮任务的目标和重点偏好，正在梳理您的需求~")
                await crud.create_tool_call(
                    db, msg.id, "supplement_info", "补充信息", "pending",
                    arguments_json=supplement_info
                )
                await db.commit()
            except Exception as e:
                logger.error(f"Failed to save supplement info: {e}")
        return
    
    # ==================== 阶段 3: 任务规划 ====================
    
    if session["stage"] == "confirmed":
        logger.info(f"[stream_ppt_generation] Entering confirmed stage, starting task planning")
        # 发送任务规划工具调用
        task_plan_data = None
        task_plan_content = ""

        async for chunk, data in stream_task_plan_with_llm(instruction, session["supplement_data"]):
            if chunk:
                task_plan_content += chunk
                # 流式输出任务规划内容
                stream_data = {
                    'type': 'task_plan_stream',
                    'content': chunk
                }
                yield f"data: {json.dumps(stream_data, ensure_ascii=False)}\n\n"
            if data:
                task_plan_data = data

        if task_plan_data:
            task_plan_data["streamContent"] = task_plan_content

        # 发送任务规划完成事件
        complete_data = {
            'type': 'task_plan_complete',
            'data': task_plan_data or {"content": task_plan_content}
        }
        yield f"data: {json.dumps(complete_data, ensure_ascii=False)}\n\n"

        # 发送任务规划工具调用事件（用于左侧胶囊显示）
        tool_call_data = {
            'type': 'tool_call',
            'tool_type': 'task_plan',
            'tool_name': '任务执行规划',
            'status': 'completed',
            'data': task_plan_data or {"content": task_plan_content}
        }
        yield f"data: {json.dumps(tool_call_data, ensure_ascii=False)}\n\n"
        
        # 保存到数据库
        if db and conversation_id:
            try:
                msg = await crud.create_message(db, conversation_id, "assistant", "")
                tc = await crud.create_tool_call(
                    db, msg.id, "task_plan", "任务执行规划", "completed",
                    result_json=task_plan_data
                )
                if task_plan_data:
                    await crud.create_task_plan(
                        db, tc.id,
                        plan_content=task_plan_content,
                        steps_json=task_plan_data.get("steps")
                    )
                await db.commit()
            except Exception as e:
                logger.error(f"Failed to save task plan: {e}")
        
        # 根据搜索模式决定是否进入搜索阶段
        search_mode = (session.get("supplement_data") or {}).get("search_mode", "auto")
        search_mode = str(search_mode).strip().lower()
        if search_mode not in ("auto", "on", "off"):
            search_mode = "auto"

        if search_mode == "off":
            logger.info("Search disabled by user preference")
            session["stage"] = "outline"
            session["search_results"] = []
            session["deep_thinking_content"] = ""
        elif search_mode == "on":
            logger.info("Search forced on by user preference")
            session["stage"] = "searching"
        else:
            logger.info("Auto search mode enabled, deciding whether to search")
            should_search = await should_use_web_search(instruction, session.get("supplement_data") or {})
            session["stage"] = "searching" if should_search else "outline"
            if not should_search:
                session["search_results"] = []
                session["deep_thinking_content"] = ""

        # 更新数据库中的 session 状态
        if db:
            await crud.update_session(
                db,
                session_id,
                stage=session["stage"],
                search_results=session.get("search_results"),
                deep_thinking_content=session.get("deep_thinking_content"),
            )
            await db.commit()
    
    # ==================== 阶段 4: 搜索 ====================
    
    if session["stage"] == "searching":
        # 检查暂停
        if await check_pause():
            return

        # 生成搜索关键词
        search_queries = await generate_search_queries(instruction, session["supplement_data"])
        logger.info(f"Generated search queries: {search_queries}")
        all_search_results = []

        for round_num, query in enumerate(search_queries, 1):
            # Check pause before each search round
            if await check_pause():
                logger.info("Paused during search phase")
                return
                
            logger.info(f"Search round {round_num}: query = '{query}'")
            # 发送搜索开始事件
            search_start_data = {
                'type': 'search_start',
                'round': round_num,
                'query': query,
                'total_rounds': len(search_queries)
            }
            yield f"data: {json.dumps(search_start_data, ensure_ascii=False)}\n\n"
            
            # 执行文字搜索和图片搜索（并行）
            search_task = execute_search(query)
            image_task = search_and_download_images(query, session["workspace_dir"])
            results, image_results = await asyncio.gather(search_task, image_task)
            all_search_results.extend(results)
            session["image_results"].extend(image_results)
            if image_results:
                logger.info(f"Found {len(image_results)} images for query: {query}")
            image_payload = [
                {
                    "url": img.get("url"),
                    "description": img.get("description", ""),
                    "width": img.get("width"),
                    "height": img.get("height"),
                }
                for img in image_results
            ]
            
            # 发送每个搜索结果
            for result in results[:]:
                search_result_data = {
                    'type': 'search_result',
                    'round': round_num,
                    'result': result
                }
                yield f"data: {json.dumps(search_result_data, ensure_ascii=False)}\n\n"
            
            # 发送搜索完成事件
            search_complete_data = {
                'type': 'search_complete',
                'round': round_num,
                'query': query,
                'results_count': len(results[:])
            }
            yield f"data: {json.dumps(search_complete_data, ensure_ascii=False)}\n\n"
            
            # 同时发送工具调用事件（用于左侧胶囊显示）
            search_tool_data = {
                'type': 'tool_call',
                'tool_type': 'web_search',
                'tool_name': '搜索网页',
                'status': 'completed',
                'data': {
                    "query": query,
                    "round": round_num,
                    "total_rounds": len(search_queries),
                    "results": results[:]
                }
            }
            logger.info(f"Sending tool_call event with query: '{query}'")
            yield f"data: {json.dumps(search_tool_data, ensure_ascii=False)}\n\n"

            # 发送图片搜索工具调用事件
            image_tool_data = {
                'type': 'tool_call',
                'tool_type': 'image_search',
                'tool_name': '搜索图片',
                'status': 'completed',
                'data': {
                    "query": query,
                    "round": round_num,
                    "total_rounds": len(search_queries),
                    "images": image_payload
                }
            }
            yield f"data: {json.dumps(image_tool_data, ensure_ascii=False)}\n\n"
            
            # 保存到数据库
            if db and conversation_id:
                try:
                    msg = await crud.create_message(db, conversation_id, "assistant", "")
                    tc = await crud.create_tool_call(
                        db, msg.id, "web_search", "搜索网页", "completed",
                        arguments_json={"query": query, "round": round_num, "total_rounds": len(search_queries)},
                        result_json={"results": results[:]}
                    )
                    sr = await crud.create_search_round(db, tc.id, query, round_num)
                    await crud.create_search_results(db, sr.id, results[:])
                    await crud.create_tool_call(
                        db, msg.id, "image_search", "搜索图片", "completed",
                        arguments_json={"query": query, "round": round_num, "total_rounds": len(search_queries)},
                        result_json={"images": image_payload}
                    )
                    await db.commit()
                except Exception as e:
                    logger.error(f"Failed to save search results: {e}")
            
            # 流式输出搜索思考（简短总结）到对话区
            thinking_text = ""
            async for chunk in stream_search_thinking(query, results, round_num, len(search_queries)):
                thinking_text += chunk
                message_data = {
                    'type': 'message',
                    'role': 'assistant',
                    'content': chunk,
                    'streaming': True
                }
                yield f"data: {json.dumps(message_data, ensure_ascii=False)}\n\n"

            # 发送思考完成标记
            complete_data = {
                'type': 'message',
                'role': 'assistant',
                'content': '',
                'streaming': False
            }
            yield f"data: {json.dumps(complete_data, ensure_ascii=False)}\n\n"

            # 保存搜索思考到数据库
            if db and conversation_id and thinking_text:
                try:
                    await crud.create_message(db, conversation_id, "assistant", thinking_text)
                    await db.commit()
                except Exception as e:
                    logger.error(f"Failed to save thinking message: {e}")
        
        session["search_results"] = all_search_results
        session["stage"] = "deep_thinking"
        # 更新数据库中的 session 状态和搜索结果
        if db:
            await crud.update_session(
                db, session_id, 
                stage="deep_thinking",
                search_results=all_search_results
            )
            await db.commit()
    
    # ==================== 阶段 5: 深度思考 ====================

    if session["stage"] == "deep_thinking":
        # 检查暂停
        if await check_pause():
            return

        # 发送深度思考开始标记
        start_data = {
            'type': 'deep_thinking_start',
            'content': '正在整理和分析搜索结果...'
        }
        yield f"data: {json.dumps(start_data, ensure_ascii=False)}\n\n"

        deep_thinking_content = ""
        async for chunk in stream_deep_thinking(instruction, session["search_results"]):
            # Check pause during streaming
            if await check_pause():
                logger.info("Paused during deep thinking stream")
                return
            deep_thinking_content += chunk
            # 使用 deep_thinking_stream 类型，前端会正确处理
            message_data = {
                'type': 'deep_thinking_stream',
                'content': chunk
            }
            yield f"data: {json.dumps(message_data, ensure_ascii=False)}\n\n"

        # 发送深度思考完成标记
        complete_data = {
            'type': 'deep_thinking_complete',
            'content': deep_thinking_content
        }
        yield f"data: {json.dumps(complete_data, ensure_ascii=False)}\n\n"

        session["deep_thinking_content"] = deep_thinking_content

        # 保存深度思考内容到最后一个搜索轮次
        if db and conversation_id and deep_thinking_content:
            try:
                # 获取该对话的所有消息
                messages = await crud.get_messages_by_conversation(db, conversation_id)
                # 从后往前查找最后一个搜索工具调用
                for msg in reversed(messages):
                    tool_calls = await crud.get_tool_calls_by_message(db, msg.id)
                    for tc in reversed(tool_calls):
                        if tc.tool_type == "web_search":
                            # 找到该工具调用的所有搜索轮次
                            search_rounds = await crud.get_search_rounds_by_tool_call(db, tc.id)
                            if search_rounds:
                                # 获取最后一个搜索轮次
                                last_round = search_rounds[-1]
                                # 更新其 thinking_content
                                from sqlalchemy import update
                                from database.models import SearchRound
                                await db.execute(
                                    update(SearchRound)
                                    .where(SearchRound.id == last_round.id)
                                    .values(thinking_content=deep_thinking_content)
                                )
                                await db.commit()
                                logger.info(f"Saved deep thinking to search round {last_round.id}")
                                break
                    else:
                        continue
                    break
            except Exception as e:
                logger.error(f"Failed to save deep thinking: {e}")

        session["stage"] = "outline"
        session["deep_thinking_content"] = deep_thinking_content
        # 更新数据库中的 session 状态
        if db:
            await crud.update_session(
                db, session_id,
                stage="outline",
                deep_thinking_content=deep_thinking_content
            )
            await db.commit()
    
    # ==================== 阶段 6: 生成大纲 ====================
    
    if session["stage"] == "outline":
        # 检查暂停
        if await check_pause():
            return
            
        outline_content = ""
        async for chunk in stream_outline_generation(
            instruction,
            session["search_results"],
            session["deep_thinking_content"],
            session["supplement_data"]
        ):
            outline_content += chunk
            # 流式输出大纲内容
            stream_data = {
                'type': 'ppt_outline_stream',
                'content': chunk
            }
            yield f"data: {json.dumps(stream_data, ensure_ascii=False)}\n\n"

        session["outline_content"] = outline_content

        # 发送大纲完成事件
        complete_data = {
            'type': 'ppt_outline_complete',
            'content': outline_content
        }
        yield f"data: {json.dumps(complete_data, ensure_ascii=False)}\n\n"

        # 发送大纲工具调用事件（用于左侧胶囊显示）
        outline_tool_data = {
            'type': 'tool_call',
            'tool_type': 'ppt_outline',
            'tool_name': 'PPT 大纲目录',
            'status': 'completed',
            'data': {"content": outline_content}
        }
        yield f"data: {json.dumps(outline_tool_data, ensure_ascii=False)}\n\n"
        
        # 保存到数据库
        if db and conversation_id:
            try:
                msg = await crud.create_message(db, conversation_id, "assistant", "")
                await crud.create_tool_call(
                    db, msg.id, "ppt_outline", "PPT 大纲目录", "completed",
                    result_json={"content": outline_content}
                )
                await db.commit()
            except Exception as e:
                logger.error(f"Failed to save outline: {e}")
        
        session["stage"] = "generating"
        session["outline_content"] = outline_content
        logger.info(f"[Stage 6 Complete] Outline generated, moving to stage 7 (generating)")
        # 更新数据库中的 session 状态
        if db:
            await crud.update_session(
                db, session_id,
                stage="generating",
                outline_content=outline_content
            )
            await db.commit()

    # ==================== 阶段 7: 生成 PPT ====================

    if session["stage"] == "generating":
        # 检查暂停
        if await check_pause():
            return

        logger.info(f"[Stage 7 Start] Starting PPT generation")
        actual_num_pages = parse_num_pages(session["supplement_data"])
        logger.info(f"[Stage 7] Parsed num_pages: {actual_num_pages}")
        
        # 创建 PPT 项目
        ppt_project = None
        ppt_version = None
        if db and conversation_id:
            try:
                supplement_topic = session.get("supplement_data", {}).get("topic", "")
                outline_content = session.get("outline_content", "")
                project_title = session.get("ppt_title") or await generate_ppt_title_llm(
                    instruction=instruction,
                    outline_content=outline_content,
                    supplement_topic=supplement_topic,
                    max_len=32
                )
                project_title = strip_think_tags(project_title) or project_title
                session["ppt_title"] = project_title
                ppt_project = await crud.create_ppt_project(
                    db, conversation_id, project_title, outline_content
                )
                ppt_version = await crud.create_ppt_version(
                    db, ppt_project.id, 1, "V1"
                )
                await db.commit()
            except Exception as e:
                logger.error(f"Failed to create PPT project: {e}")
        
        # 运行 SlideDesign agent
        slide_count = 0
        generation_failed = False
        generation_error_message: Optional[str] = None
        completion_emitted = False
        seen_slide_signatures: Dict[int, str] = {}
        saved_slide_ids: Dict[int, int] = {}
        image_usage_counter: Dict[int, int] = {}
        style_anchor_tokens: Optional[Dict[str, str]] = None
        style_anchor_raw_html: Optional[str] = None
        style_anchor_description: str = ""

        stage7_event_timeout_seconds = 180
        agent_stream = run_slide_design_agent(
            topic=instruction,
            outline_content=session["outline_content"],
            search_results=session["search_results"],
            deep_thinking_content=session["deep_thinking_content"],
            supplement_data=session["supplement_data"],
            num_pages=actual_num_pages,
            powerpoint_type=powerpoint_type,
            image_results=session.get("image_results", []),
            workspace_dir=session.get("workspace_dir", ""),
        )

        while True:
            try:
                event = await asyncio.wait_for(
                    agent_stream.__anext__(),
                    timeout=stage7_event_timeout_seconds,
                )
            except StopAsyncIteration:
                break
            except asyncio.TimeoutError:
                logger.error(
                    "[Stage 7] No event for %ss. session=%s slides=%s",
                    stage7_event_timeout_seconds,
                    session_id,
                    slide_count,
                )
                if (
                    actual_num_pages
                    and slide_count >= actual_num_pages
                    and not completion_emitted
                ):
                    completion_emitted = True
                    project_data = None
                    if ppt_project:
                        project_data = {
                            'id': ppt_project.id,
                            'conversation_id': ppt_project.conversation_id,
                            'title': ppt_project.title,
                            'outline_content': ppt_project.outline_content,
                            'created_at': ppt_project.created_at.isoformat() if ppt_project.created_at else None,
                            'updated_at': ppt_project.updated_at.isoformat() if ppt_project.updated_at else None,
                        }
                    completion_text = f"PPT生成完成！共 {slide_count} 页。"
                    complete_msg_data = {
                        'type': 'ppt_complete',
                        'role': 'assistant',
                        'content': completion_text,
                        'streaming': False,
                        'project': project_data
                    }
                    yield f"data: {json.dumps(complete_msg_data, ensure_ascii=False)}\n\n"
                    if db and conversation_id:
                        try:
                            await crud.create_message(db, conversation_id, "assistant", completion_text)
                            await db.commit()
                        except Exception as e:
                            logger.error(f"Failed to save timeout-complete message: {e}")
                    break
                generation_failed = True
                generation_error_message = (
                    f"PPT生成在 {stage7_event_timeout_seconds} 秒内无进展，"
                    "请重试或减少页数后再生成。"
                )
                error_data = {
                    'type': 'error',
                    'role': 'assistant',
                    'content': generation_error_message
                }
                yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
                break

            # 生成中也要响应暂停
            if await check_pause():
                logger.info("[Stage 7] Paused during PPT generation, stopping stream")
                return
            event_type = event.get("type")

            if event_type == "slide":
                slide_count = event["slide_count"]
                raw_html_content = event["html_content"]
                description = event.get("description", f"第 {slide_count} 页")
                image_preferences = [
                    idx
                    for idx in (event.get("image_preferences") or [])
                    if isinstance(idx, int) and idx > 0
                ]

                async def _prepare_slide_html(
                    source_html: str,
                    usage_counter_ref: Dict[int, int],
                    stage_label: str,
                ) -> str:
                    prepared_html = source_html

                    # 替换图片占位符（{{img_N}}）和假 URL 为本地图片 base64
                    try:
                        prepared_html = replace_image_placeholders(
                            prepared_html,
                            session.get("image_results", []),
                            preferred_image_ids=image_preferences,
                            usage_counter=usage_counter_ref,
                            page_number=slide_count,
                            page_description=description,
                        )
                    except Exception as e:
                        logger.error(
                            "[Stage 7] Failed to replace image placeholders for slide %s (%s): %s",
                            slide_count,
                            stage_label,
                            e,
                        )

                    # 约束元素布局边界，避免明显超出 1280x720 画布
                    try:
                        prepared_html = enforce_slide_layout_bounds(prepared_html)
                    except Exception as e:
                        logger.error(
                            "[Stage 7] Failed to enforce layout bounds for slide %s (%s): %s",
                            slide_count,
                            stage_label,
                            e,
                        )

                    # 内联外部资源（图片等）
                    try:
                        logger.info(
                            "[Stage 7] Inlining resources for slide %s (%s)...",
                            slide_count,
                            stage_label,
                        )
                        prepared_html = await inline_all_resources(prepared_html, timeout=30)
                        logger.info(
                            "[Stage 7] Resources inlined for slide %s (%s)",
                            slide_count,
                            stage_label,
                        )
                    except Exception as e:
                        logger.error(
                            "[Stage 7] Failed to inline resources for slide %s (%s): %s",
                            slide_count,
                            stage_label,
                            e,
                        )
                        # 内联失败不影响整体流程，继续使用原 HTML
                    return prepared_html

                review_meta: Optional[Dict[str, Any]] = None
                refined_raw_html = raw_html_content
                if Config.VISUAL_REVIEW_ENABLED:
                    review_usage_counter = dict(image_usage_counter)
                    refined_raw_html, review_meta = await refine_slide_with_visual_review(
                        raw_html=raw_html_content,
                        topic=instruction,
                        page_description=description,
                        page_number=slide_count,
                        prepare_for_render=lambda base_html: _prepare_slide_html(
                            base_html,
                            review_usage_counter,
                            "visual-review",
                        ),
                    )
                    if review_meta:
                        logger.info(
                            "[Stage 7] Visual review slide=%s score=%s optimized=%s round=%s",
                            slide_count,
                            review_meta.get("score"),
                            review_meta.get("optimized"),
                            review_meta.get("round"),
                        )
                        if review_meta.get("optimized"):
                            review_notice = {
                                "type": "message",
                                "role": "assistant",
                                "content": (
                                    f"第 {slide_count} 页已执行视觉优化，"
                                    f"当前评分 {review_meta.get('score', 0)}。"
                                ),
                                "streaming": False,
                            }
                            yield f"data: {json.dumps(review_notice, ensure_ascii=False)}\n\n"

                deck_style_meta: Optional[Dict[str, Any]] = None
                if not style_anchor_raw_html:
                    style_anchor_raw_html = refined_raw_html
                    style_anchor_description = description
                elif getattr(Config, "DECK_STYLE_REVIEW_ENABLED", True):
                    deck_review_usage_counter = dict(image_usage_counter)
                    refined_raw_html, deck_style_meta = await refine_slide_with_deck_style_review(
                        raw_html=refined_raw_html,
                        topic=instruction,
                        page_description=description,
                        page_number=slide_count,
                        anchor_raw_html=style_anchor_raw_html,
                        anchor_page_description=style_anchor_description or "风格锚点页",
                        prepare_for_render=lambda base_html: _prepare_slide_html(
                            base_html,
                            deck_review_usage_counter,
                            "deck-style-review",
                        ),
                    )
                    if deck_style_meta:
                        logger.info(
                            "[Stage 7] Deck style review slide=%s score=%s optimized=%s round=%s",
                            slide_count,
                            deck_style_meta.get("score"),
                            deck_style_meta.get("optimized"),
                            deck_style_meta.get("round"),
                        )
                        if deck_style_meta.get("optimized"):
                            deck_notice = {
                                "type": "message",
                                "role": "assistant",
                                "content": (
                                    f"第 {slide_count} 页已执行跨页风格一致性优化，"
                                    f"当前一致性评分 {deck_style_meta.get('score', 0)}。"
                                ),
                                "streaming": False,
                            }
                            yield f"data: {json.dumps(deck_notice, ensure_ascii=False)}\n\n"

                if style_anchor_tokens and slide_count > 1:
                    refined_raw_html = apply_style_anchor(refined_raw_html, style_anchor_tokens)

                html_content = await _prepare_slide_html(
                    refined_raw_html,
                    image_usage_counter,
                    "final",
                )

                if slide_count == 1 and not style_anchor_tokens:
                    style_anchor_tokens = extract_style_anchor(html_content)

                content_signature = hashlib.sha1(
                    html_content.encode("utf-8", errors="ignore")
                ).hexdigest()
                if seen_slide_signatures.get(slide_count) == content_signature:
                    logger.info(
                        "[Stage 7] Skip duplicated slide event for page %s",
                        slide_count,
                    )
                    continue
                seen_slide_signatures[slide_count] = content_signature
                
                # 注意：静态化已移除，只在导出时进行
                # 生成时保留动态内容，以便前端预览

                # 发送幻灯片工具调用事件
                slide_tool_data = {
                    'type': 'tool_call',
                    'tool_type': 'ppt_generate',
                    'tool_name': f'创建幻灯片 {slide_count}',
                    'status': 'completed',
                    'data': {
                        "pageNumber": slide_count,
                        "html": html_content,
                        "content": html_content,
                        "description": description
                    }
                }
                yield f"data: {json.dumps(slide_tool_data, ensure_ascii=False)}\n\n"

                # 发送 ppt_slide 事件用于更新预览
                ppt_slide_data = {
                    'type': 'ppt_slide',
                    'html': html_content,
                    'slide_count': slide_count
                }
                yield f"data: {json.dumps(ppt_slide_data, ensure_ascii=False)}\n\n"

                # 保存幻灯片到数据库
                if db and ppt_version:
                    try:
                        slide_id = saved_slide_ids.get(slide_count)
                        if slide_id:
                            await crud.update_ppt_slide(
                                db,
                                slide_id,
                                html_content=html_content,
                                page_title=description,
                            )
                        else:
                            existing_slide = await crud.get_ppt_slide_by_page(
                                db,
                                ppt_version.id,
                                slide_count,
                            )
                            if existing_slide:
                                saved_slide_ids[slide_count] = existing_slide.id
                                await crud.update_ppt_slide(
                                    db,
                                    existing_slide.id,
                                    html_content=html_content,
                                    page_title=description,
                                )
                            else:
                                created_slide = await crud.create_ppt_slide(
                                    db, ppt_version.id, slide_count, html_content, description
                                )
                                saved_slide_ids[slide_count] = created_slide.id
                        await db.commit()
                    except Exception as e:
                        logger.error(f"Failed to save slide: {e}")

                # 保存幻灯片工具调用到数据库（创建独立消息）
                if db and conversation_id:
                    try:
                        # 为每个幻灯片创建一条独立消息，模拟流式输出
                        slide_msg = await crud.create_message(
                            db, conversation_id, "assistant", ""  # 内容为空，仅作为工具调用的载体
                        )
                        await crud.create_tool_call(
                            db, slide_msg.id, "ppt_generate", f'创建幻灯片 {slide_count}', "completed",
                            result_json={
                                "pageNumber": slide_count,
                                "html": html_content,
                                "description": description
                            }
                        )
                        await db.commit()
                    except Exception as e:
                        logger.error(f"Failed to save ppt_generate tool call: {e}")

            elif event_type == "thinking":
                # thinking_messages.append(event["content"])  # 不再收集，直接保存
                
                # 保存思考消息到数据库（独立消息）
                if db and conversation_id:
                    try:
                        await crud.create_message(db, conversation_id, "assistant", event["content"])
                        await db.commit()
                    except Exception as e:
                        logger.error(f"Failed to save thinking message: {e}")
                thinking_data = {
                    'type': 'message',
                    'role': 'assistant',
                    'content': event["content"],
                    'streaming': False
                }
                yield f"data: {json.dumps(thinking_data, ensure_ascii=False)}\n\n"

                # 目标页数已达成时，主动收尾，避免底层 agent 延迟 finalize 造成前端长时间 loading
                if (
                    actual_num_pages
                    and slide_count >= actual_num_pages
                    and "已达到目标页数" in (event.get("content") or "")
                    and not completion_emitted
                ):
                    completion_emitted = True
                    project_data = None
                    if ppt_project:
                        project_data = {
                            'id': ppt_project.id,
                            'conversation_id': ppt_project.conversation_id,
                            'title': ppt_project.title,
                            'outline_content': ppt_project.outline_content,
                            'created_at': ppt_project.created_at.isoformat() if ppt_project.created_at else None,
                            'updated_at': ppt_project.updated_at.isoformat() if ppt_project.updated_at else None,
                        }
                    completion_text = f"PPT生成完成！共 {slide_count} 页。"
                    complete_msg_data = {
                        'type': 'ppt_complete',
                        'role': 'assistant',
                        'content': completion_text,
                        'streaming': False,
                        'project': project_data
                    }
                    yield f"data: {json.dumps(complete_msg_data, ensure_ascii=False)}\n\n"
                    if db and conversation_id:
                        try:
                            await crud.create_message(db, conversation_id, "assistant", completion_text)
                            await db.commit()
                        except Exception as e:
                            logger.error(f"Failed to save forced-complete message: {e}")
                    break
            
            elif event_type == "message":
                msg_data = {
                    'type': 'message',
                    'role': event.get('role', 'assistant'),
                    'content': event["content"],
                    'streaming': False
                }
                yield f"data: {json.dumps(msg_data, ensure_ascii=False)}\n\n"
            
            elif event_type == "complete":
                completion_emitted = True
                # 准备 project 数据
                project_data = None
                if ppt_project:
                    project_data = {
                        'id': ppt_project.id,
                        'conversation_id': ppt_project.conversation_id,
                        'title': ppt_project.title,
                        'outline_content': ppt_project.outline_content,
                        'created_at': ppt_project.created_at.isoformat() if ppt_project.created_at else None,
                        'updated_at': ppt_project.updated_at.isoformat() if ppt_project.updated_at else None,
                    }

                complete_msg_data = {
                    'type': 'ppt_complete',
                    'role': 'assistant',
                    'content': event["content"],
                    'streaming': False,
                    'project': project_data
                }
                yield f"data: {json.dumps(complete_msg_data, ensure_ascii=False)}\n\n"

                # 保存完成消息
                if db and conversation_id:
                    try:
                        await crud.create_message(db, conversation_id, "assistant", event["content"])
                        await db.commit()
                    except Exception as e:
                        logger.error(f"Failed to save complete message: {e}")
            
            elif event_type == "error":
                generation_failed = True
                generation_error_message = event.get("content") or "生成PPT时出错"
                error_data = {
                    'type': 'error',
                    'role': 'assistant',
                    'content': generation_error_message
                }
                yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
                break

        try:
            await agent_stream.aclose()
        except Exception:
            pass

        if generation_failed or slide_count <= 0 or not completion_emitted:
            if not generation_error_message:
                generation_error_message = "PPT生成未产出有效页面，请稍后重试。"
                error_data = {
                    'type': 'error',
                    'role': 'assistant',
                    'content': generation_error_message
                }
                yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"

            logger.error(
                "[Stage 7] PPT generation failed. session=%s slides=%s completion_emitted=%s error=%s",
                session_id,
                slide_count,
                completion_emitted,
                generation_error_message,
            )
            if db:
                await crud.update_session(
                    db,
                    session_id,
                    stage="generating",
                    task_status="paused",
                )
                await db.commit()
            return

        session["stage"] = "completed"
        # 更新数据库中的 session 状态（任务完成）
        if db:
            await crud.update_session(db, session_id, stage="completed", task_status="completed")
            await db.commit()
        
        yield f"data: {json.dumps({'type': 'done'})}\n\n"


# ==================== API 端点 ====================

@app.post("/api/chat")
async def chat(request: ChatRequest):
    """聊天接口 - 流式返回（支持暂停恢复和上下文理解）"""
    logger.info(f"Chat endpoint called: {request.instruction[:50]}...")

    session_id = request.session_id or str(uuid.uuid4())
    conversation_id = request.conversation_id
    conversation_uuid = request.conversation_uuid
    conversation_user_id = "default_user"
    is_new_conversation = False
    effective_instruction = request.instruction

    async with get_db_session() as db:
        # 绑定并校验会话上下文
        if conversation_id:
            conversation = await crud.get_conversation(db, conversation_id)
            if not conversation:
                raise HTTPException(status_code=404, detail="Conversation not found")
            if conversation_uuid and conversation_uuid != conversation.uuid:
                raise HTTPException(status_code=409, detail="对话标识不匹配，请刷新后重试")
            conversation_uuid = conversation.uuid
            if conversation.user_id:
                conversation_user_id = conversation.user_id
        else:
            # 先快速创建对话，避免标题模型抖动导致“新建后列表不出现”
            fallback_topic = extract_core_topic(request.instruction)
            conversation_title = normalize_conversation_title(
                fallback_topic,
                max_len=32,
            )
            conversation = await crud.create_conversation(
                db, title=conversation_title, user_id="default_user"
            )
            conversation_id = conversation.id
            conversation_uuid = conversation.uuid
            if conversation.user_id:
                conversation_user_id = conversation.user_id
            is_new_conversation = True
            # 异步优化标题，不阻塞首包和会话创建
            asyncio.create_task(
                _refresh_conversation_title_async(conversation_id, request.instruction)
            )

        # 优先使用请求中的 session；不匹配则退回当前对话活跃 session
        existing_session = None
        if request.session_id:
            request_session = await crud.get_session(db, request.session_id)
            if request_session and request_session.conversation_id == conversation_id:
                existing_session = request_session
            elif request_session:
                logger.warning(
                    "Ignoring mismatched request session_id=%s for conversation_id=%s",
                    request.session_id,
                    conversation_id,
                )

        if not existing_session and conversation_id:
            existing_session = await crud.get_active_session_by_conversation(db, conversation_id)
        if not existing_session and conversation_id:
            existing_session = await crud.get_session_by_conversation(db, conversation_id)

        if existing_session and existing_session.task_status == "running":
            # 避免并发活跃流导致跨会话渲染和脏状态
            await crud.update_session(db, existing_session.id, task_status="paused")
            existing_session.task_status = "paused"
            logger.warning(
                "Session %s was running when a new chat arrived; marked paused first",
                existing_session.id,
            )

        if existing_session and existing_session.task_status == "paused":
            logger.info(
                "Found paused session for conversation %s, analyzing intent...",
                conversation_id,
            )
            intent_result = await analyze_user_intent_for_paused_session(
                user_message=request.instruction,
                current_topic=existing_session.topic,
                current_stage=existing_session.stage,
                supplement_data=existing_session.supplement_data,
            )
            action = intent_result.get("action", "resume")
            new_topic = intent_result.get("new_topic", existing_session.topic)
            logger.info("Intent analysis: action=%s, new_topic=%s", action, new_topic)

            if action == "restart":
                effective_instruction = new_topic or request.instruction
                await crud.update_session(
                    db,
                    existing_session.id,
                    topic=effective_instruction,
                    stage="init",
                    task_status="running",
                    supplement_data=None,
                    search_results=None,
                    outline_content=None,
                    deep_thinking_content=None,
                )
                session_id = existing_session.id
            elif action == "adjust":
                effective_instruction = new_topic or request.instruction
                await crud.update_session(
                    db,
                    existing_session.id,
                    topic=effective_instruction,
                    task_status="running",
                )
                session_id = existing_session.id
            else:  # resume
                effective_instruction = existing_session.topic
                await crud.update_session(
                    db,
                    existing_session.id,
                    task_status="running",
                )
                session_id = existing_session.id
        elif existing_session and existing_session.stage != "completed":
            # 非 paused 的历史活跃状态中，用户发起新 chat 时强制起新 session，避免串阶段
            session_id = str(uuid.uuid4())
            effective_instruction = request.instruction

        await crud.pause_running_sessions(
            db,
            keep_session_id=session_id,
            user_id=conversation_user_id,
        )

        await db.commit()

    stream = stream_ppt_generation(
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
        db=None,
    )
    guarded_stream = _stream_with_session_guard(
        stream,
        session_id=session_id,
        conversation_id=conversation_id,
        conversation_uuid=conversation_uuid,
    )

    return StreamingResponse(
        guarded_stream,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Session-Id": session_id,
            "X-Conversation-Id": str(conversation_id) if conversation_id else "",
            "X-Conversation-UUID": conversation_uuid or "",
        },
    )


@app.post("/api/confirm")
async def confirm(request: ConfirmRequest):
    """确认补充信息接口"""
    logger.info(f"Confirm endpoint called: session={request.session_id}, conversation={request.conversation_id}")
    session_id = request.session_id or ""
    conversation_id: Optional[int] = request.conversation_id
    conversation_uuid = request.conversation_uuid
    conversation_user_id = "default_user"
    session_topic = ""

    async with get_db_session() as db:
        # 检查对话是否已经完成（已有 PPT 项目）
        if request.conversation_id:
            existing_project = await crud.get_ppt_project_by_conversation(db, request.conversation_id)
            if existing_project:
                logger.warning(
                    "Conversation %s already has PPT project, rejecting duplicate confirmation",
                    request.conversation_id,
                )
                raise HTTPException(
                    status_code=400,
                    detail="此对话已经完成 PPT 生成，无法重复确认",
                )

        session_from_request = None
        if request.session_id:
            session_from_request = await crud.get_session(db, request.session_id)

        session_from_conversation = None
        if request.conversation_id:
            session_from_conversation = await crud.get_session_by_conversation(db, request.conversation_id)

        try:
            db_session, session_id, conversation_id, corrected = resolve_confirm_session_binding(
                request_session_id=request.session_id,
                request_conversation_id=request.conversation_id,
                session_from_request=session_from_request,
                session_from_conversation=session_from_conversation,
            )
        except SessionBindingError as e:
            raise HTTPException(status_code=e.status_code, detail=e.detail) from e

        if corrected:
            logger.warning(
                "Confirm session mismatch detected. request.session_id=%s, conversation_id=%s -> resolved session_id=%s",
                request.session_id,
                request.conversation_id,
                session_id,
            )

        if conversation_id:
            conversation = await crud.get_conversation(db, conversation_id)
            if not conversation:
                raise HTTPException(status_code=404, detail="Conversation not found")
            if conversation_uuid and conversation_uuid != conversation.uuid:
                raise HTTPException(status_code=409, detail="对话标识不匹配，请刷新后重试")
            conversation_uuid = conversation.uuid
            if conversation.user_id:
                conversation_user_id = conversation.user_id

        # 检查 session 状态是否允许确认
        if db_session.stage != "waiting_supplement":
            logger.warning(
                "Session %s is in stage %s, not waiting_supplement",
                session_id,
                db_session.stage,
            )
            raise HTTPException(
                status_code=400,
                detail=f"当前状态不允许确认（状态：{db_session.stage}）",
            )

        session_topic = db_session.topic

        generated_topic = request.supplement_data.get("topic")
        if isinstance(generated_topic, str):
            generated_topic = strip_think_tags(generated_topic) or generated_topic
        if generated_topic and generated_topic != session_topic:
            logger.info("Using AI-generated topic: %s (original: %s)", generated_topic, session_topic)
            session_topic = generated_topic
            await crud.update_session(db, session_id, topic=generated_topic)

            if conversation_id:
                try:
                    await crud.update_conversation_title(
                        db,
                        conversation_id,
                        normalize_conversation_title(generated_topic),
                    )
                    logger.info("Updated conversation title to: %s", generated_topic)
                except Exception as e:
                    logger.error("Failed to update conversation title: %s", e)

        # 更新补充信息工具调用状态
        if conversation_id:
            try:
                messages = await crud.get_messages_by_conversation(db, conversation_id)
                for msg in reversed(messages):
                    if msg.role != "assistant":
                        continue
                    tool_calls = await crud.get_tool_calls_by_message(db, msg.id)
                    for tc in tool_calls:
                        if tc.tool_type == "supplement_info" and tc.status == "pending":
                            await crud.update_tool_call_status(
                                db, tc.id, "confirmed", result_json=request.supplement_data
                            )
                            logger.info("Updated tool call %s status to confirmed", tc.id)
                            break
                    break
            except Exception as e:
                logger.error("Failed to update tool call status: %s", e)

        await crud.pause_running_sessions(
            db,
            keep_session_id=session_id,
            user_id=conversation_user_id,
        )

        await db.commit()

    logger.info("Starting stream_ppt_generation for session %s, conversation %s", session_id, conversation_id)
    logger.info("Topic: %s", session_topic)
    logger.info("Supplement data: %s", request.supplement_data)

    stream = stream_ppt_generation(
        instruction=session_topic,
        session_id=session_id,
        conversation_id=conversation_id,
        conversation_uuid=conversation_uuid,
        supplement_data=request.supplement_data,
        search_mode=request.search_mode,
        db=None,
        save_user_message=False,
    )
    guarded_stream = _stream_with_session_guard(
        stream,
        session_id=session_id,
        conversation_id=conversation_id,
        conversation_uuid=conversation_uuid,
    )

    return StreamingResponse(
        guarded_stream,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Session-Id": session_id,
            "X-Conversation-Id": str(conversation_id) if conversation_id else "",
            "X-Conversation-UUID": conversation_uuid or "",
        },
    )


@app.post("/api/ppt/confirm")
async def confirm_ppt_compat(request: ConfirmRequest):
    """向后兼容：保留 /api/ppt/confirm 别名，内部复用统一确认逻辑。"""
    return await confirm(request)


@app.post("/api/sessions/{session_id}/pause")
async def pause_session(session_id: str, db: AsyncSession = Depends(get_db)):
    """暂停正在运行的任务"""
    logger.info(f"Pause session request: {session_id}")
    
    # 获取 session
    session = await crud.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # 只有 running 状态才能暂停
    if session.task_status != "running":
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot pause session in {session.task_status} status"
        )
    
    # 更新状态为 paused
    await crud.update_session(db, session_id, task_status="paused")
    await db.commit()
    
    logger.info(f"Session {session_id} paused at stage {session.stage}")
    return {
        "status": "ok",
        "session_id": session_id,
        "task_status": "paused",
        "stage": session.stage
    }


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
