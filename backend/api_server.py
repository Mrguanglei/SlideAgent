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
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
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
from routers import conversations_router, ppt_router, export_router, knowledge_router

# 导入服务
from services.llm import call_llm_api, call_llm_api_stream
from services.search import (
    generate_search_queries,
    execute_search,
    stream_search_thinking,
    stream_deep_thinking
)
from services.task_planner import (
    check_ppt_intent,
    generate_supplement_info_with_llm,
    stream_task_plan_with_llm,
    stream_outline_generation
)
from services.ppt_generator import (
    create_tool_call,
    parse_num_pages,
    run_slide_design_agent
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


# ==================== Pydantic Models ====================

class ChatRequest(BaseModel):
    """聊天请求"""
    instruction: str
    session_id: Optional[str] = None
    conversation_id: Optional[int] = None  # 新增：关联对话 ID
    supplement_data: Optional[Dict[str, Any]] = None
    attachments: Optional[List[str]] = None
    num_pages: Optional[str] = None
    template: Optional[str] = None
    powerpoint_type: Optional[str] = "16:9 Widescreen"
    convert_type: Optional[str] = "slide_design"


class ConfirmRequest(BaseModel):
    """确认补充信息请求"""
    session_id: Optional[str] = None
    conversation_id: Optional[int] = None
    supplement_data: Dict[str, Any]


# ==================== 内存会话存储（临时，后续迁移到数据库） ====================

sessions: Dict[str, Dict[str, Any]] = {}


# ==================== 核心流式生成函数 ====================

async def stream_ppt_generation(
    instruction: str,
    session_id: str,
    conversation_id: Optional[int] = None,
    conversation_uuid: Optional[str] = None,
    is_new_conversation: bool = False,
    supplement_data: Optional[Dict[str, Any]] = None,
    attachments: Optional[List[str]] = None,
    num_pages: Optional[str] = None,
    template: Optional[str] = None,
    powerpoint_type: str = "16:9 Widescreen",
    convert_type: str = "slide_design",
    db: Optional[AsyncSession] = None,
):
    """流式生成 PPT 的核心函数"""

    # 如果是新创建的对话，发送 conversation_created 事件
    if is_new_conversation and conversation_uuid:
        yield f"data: {json.dumps({'type': 'conversation_created', 'conversation_id': conversation_id, 'conversation_uuid': conversation_uuid}, ensure_ascii=False)}\n\n"

    # 获取或创建会话
    if session_id not in sessions:
        sessions[session_id] = {
            "topic": instruction,
            "stage": "init",
            "messages": [],
            "search_results": [],
            "outline_content": "",
            "deep_thinking_content": "",
            "supplement_data": supplement_data or {},
            "conversation_id": conversation_id,
        }
    
    session = sessions[session_id]
    
    # 如果提供了 supplement_data，更新会话
    if supplement_data:
        session["supplement_data"] = supplement_data
        session["stage"] = "confirmed"
    
    # 保存用户消息到数据库
    if db and conversation_id:
        try:
            await crud.create_message(db, conversation_id, "user", instruction)
            await db.commit()
        except Exception as e:
            logger.error(f"Failed to save user message: {e}")
    
    # ==================== 阶段 1: 检查 PPT 意图 ====================
    
    if session["stage"] == "init":
        is_ppt_request = await check_ppt_intent(instruction)
        
        if not is_ppt_request:
            # 非 PPT 请求，直接对话
            response_text = ""
            async for chunk in call_llm_api_stream([
                {"role": "system", "content": "你是 SlideAgent，一个专业的 PPT 制作助手。用户似乎没有明确的 PPT 制作需求，请友好地回应并引导用户。"},
                {"role": "user", "content": instruction}
            ]):
                response_text += chunk
                # 构建消息数据
                message_data = {
                    'type': 'message',
                    'content': chunk,
                    'role': 'assistant',
                    'streaming': True,
                    'created_at': datetime.now().isoformat()
                }
                yield f"data: {json.dumps(message_data, ensure_ascii=False)}\n\n"
            
            # 保存助手消息
            if db and conversation_id:
                try:
                    await crud.create_message(db, conversation_id, "assistant", response_text)
                    await db.commit()
                except Exception as e:
                    logger.error(f"Failed to save assistant message: {e}")

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
                msg = await crud.create_message(db, conversation_id, "assistant", "让我先核对下本轮任务的目标和重点偏好，正在梳理您的需求~")
                await crud.create_tool_call(
                    db, msg.id, "supplement_info", "补充信息", "pending",
                    arguments_json=supplement_info
                )
                await db.commit()
            except Exception as e:
                logger.error(f"Failed to save supplement info: {e}")
        
        session["stage"] = "waiting_supplement"
        return
    
    # ==================== 阶段 3: 任务规划 ====================
    
    if session["stage"] == "confirmed":
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
        
        session["stage"] = "searching"
    
    # ==================== 阶段 4: 搜索 ====================
    
    if session["stage"] == "searching":
        # 生成搜索关键词
        search_queries = await generate_search_queries(instruction, session["supplement_data"])
        logger.info(f"Generated search queries: {search_queries}")
        all_search_results = []

        for round_num, query in enumerate(search_queries, 1):
            logger.info(f"Search round {round_num}: query = '{query}'")
            # 发送搜索开始事件
            search_start_data = {
                'type': 'search_start',
                'round': round_num,
                'query': query,
                'total_rounds': len(search_queries)
            }
            yield f"data: {json.dumps(search_start_data, ensure_ascii=False)}\n\n"
            
            # 执行搜索
            results = await execute_search(query)
            all_search_results.extend(results)
            
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
    
    # ==================== 阶段 5: 深度思考 ====================

    if session["stage"] == "deep_thinking":
        # 发送深度思考开始标记
        start_data = {
            'type': 'deep_thinking_start',
            'content': '正在整理和分析搜索结果...'
        }
        yield f"data: {json.dumps(start_data, ensure_ascii=False)}\n\n"

        deep_thinking_content = ""
        async for chunk in stream_deep_thinking(instruction, session["search_results"]):
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
    
    # ==================== 阶段 6: 生成大纲 ====================
    
    if session["stage"] == "outline":
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
        logger.info(f"[Stage 6 Complete] Outline generated, moving to stage 7 (generating)")

    # ==================== 阶段 7: 生成 PPT ====================

    if session["stage"] == "generating":
        logger.info(f"[Stage 7 Start] Starting PPT generation")
        actual_num_pages = parse_num_pages(session["supplement_data"])
        logger.info(f"[Stage 7] Parsed num_pages: {actual_num_pages}")
        
        # 创建 PPT 项目
        ppt_project = None
        ppt_version = None
        if db and conversation_id:
            try:
                ppt_project = await crud.create_ppt_project(
                    db, conversation_id, instruction, session["outline_content"]
                )
                ppt_version = await crud.create_ppt_version(
                    db, ppt_project.id, 1, "V1"
                )
                await db.commit()
            except Exception as e:
                logger.error(f"Failed to create PPT project: {e}")
        
        # 运行 SlideDesign agent
        slide_count = 0
        thinking_messages = []  # 收集所有 thinking 消息
        
        # 在生成PPT之前创建一条assistant消息，所有幻灯片工具调用都关联到这条消息
        ppt_generation_message = None
        if db and conversation_id:
            try:
                ppt_generation_message = await crud.create_message(
                    db, conversation_id, "assistant", "正在生成PPT幻灯片..."
                )
                await db.commit()
            except Exception as e:
                logger.error(f"Failed to create PPT generation message: {e}")
        
        async for event in run_slide_design_agent(
            topic=instruction,
            outline_content=session["outline_content"],
            search_results=session["search_results"],
            deep_thinking_content=session["deep_thinking_content"],
            supplement_data=session["supplement_data"],
            num_pages=actual_num_pages,
            powerpoint_type=powerpoint_type,
        ):
            event_type = event.get("type")

            if event_type == "slide":
                slide_count = event["slide_count"]
                html_content = event["html_content"]
                description = event.get("description", f"第 {slide_count} 页")

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
                        await crud.create_ppt_slide(
                            db, ppt_version.id, slide_count, html_content, description
                        )
                        await db.commit()
                    except Exception as e:
                        logger.error(f"Failed to save slide: {e}")

                # 保存幻灯片工具调用到数据库（关联到同一条消息）
                if db and ppt_generation_message:
                    try:
                        await crud.create_tool_call(
                            db, ppt_generation_message.id, "ppt_generate", f'创建幻灯片 {slide_count}', "completed",
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
                thinking_messages.append(event["content"])
                thinking_data = {
                    'type': 'message',
                    'role': 'assistant',
                    'content': event["content"],
                    'streaming': True
                }
                yield f"data: {json.dumps(thinking_data, ensure_ascii=False)}\n\n"
            
            elif event_type == "message":
                msg_data = {
                    'type': 'message',
                    'role': event.get('role', 'assistant'),
                    'content': event["content"],
                    'streaming': False
                }
                yield f"data: {json.dumps(msg_data, ensure_ascii=False)}\n\n"
            
            elif event_type == "complete":
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
                error_data = {
                    'type': 'error',
                    'role': 'assistant',
                    'content': event["content"]
                }
                yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"

        # 保存所有 thinking 消息到数据库
        if db and conversation_id and thinking_messages:
            try:
                # 合并所有 thinking 消息为一条
                combined_thinking = "\n".join(thinking_messages)
                await crud.create_message(db, conversation_id, "assistant", combined_thinking)
                await db.commit()
            except Exception as e:
                logger.error(f"Failed to save thinking messages: {e}")

        session["stage"] = "completed"


# ==================== API 端点 ====================

@app.post("/api/chat")
async def chat(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    """聊天接口 - 流式返回"""
    logger.info(f"Chat endpoint called: {request.instruction[:50]}...")
    
    session_id = request.session_id or str(uuid.uuid4())
    conversation_id = request.conversation_id
    conversation_uuid = None
    is_new_conversation = False

    # 如果没有 conversation_id，创建新对话
    if not conversation_id:
        try:
            conversation = await crud.create_conversation(
                db, title=request.instruction[:50], user_id="default_user"
            )
            conversation_id = conversation.id
            conversation_uuid = conversation.uuid
            is_new_conversation = True
            await db.commit()
        except Exception as e:
            logger.error(f"Failed to create conversation: {e}")

    return StreamingResponse(
        stream_ppt_generation(
            instruction=request.instruction,
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
            db=db,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Session-Id": session_id,
            "X-Conversation-Id": str(conversation_id) if conversation_id else "",
        }
    )


@app.post("/api/confirm")
async def confirm(request: ConfirmRequest, db: AsyncSession = Depends(get_db)):
    """确认补充信息接口"""
    logger.info(f"Confirm endpoint called: session={request.session_id}, conversation={request.conversation_id}")

    # 检查对话是否已经完成（已有 PPT 项目）
    if request.conversation_id:
        existing_project = await crud.get_ppt_project_by_conversation(db, request.conversation_id)
        if existing_project:
            logger.warning(f"Conversation {request.conversation_id} already has PPT project, rejecting duplicate confirmation")
            raise HTTPException(
                status_code=400,
                detail="此对话已经完成 PPT 生成，无法重复确认"
            )

    # 如果没有 session_id，尝试从 conversation_id 获取或创建新 session
    session_id = request.session_id
    if not session_id:
        # 生成新的 session_id
        session_id = str(uuid.uuid4())
        logger.info(f"Generated new session_id: {session_id}")

    # 如果 session 不存在，说明是历史对话，不允许确认
    if session_id not in sessions:
        logger.warning(f"Session {session_id} not found, rejecting confirmation from history")
        raise HTTPException(
            status_code=400,
            detail="无法确认历史对话，请创建新对话"
        )

    session = sessions[session_id]

    # 检查 session 状态是否允许确认
    if session.get("stage") != "waiting_supplement":
        logger.warning(f"Session {session_id} is in stage {session.get('stage')}, not waiting_supplement")
        raise HTTPException(
            status_code=400,
            detail=f"当前状态不允许确认（状态：{session.get('stage')}）"
        )

    conversation_id = request.conversation_id or session.get("conversation_id")

    # 从 supplement_data 中提取 AI 生成的主题（如果有）
    generated_topic = request.supplement_data.get("topic")
    if generated_topic and generated_topic != session["topic"]:
        logger.info(f"Using AI-generated topic: {generated_topic} (original: {session['topic']})")
        # 更新 session 中的 topic
        session["topic"] = generated_topic

        # 更新对话标题
        if conversation_id and db:
            try:
                await crud.update_conversation_title(db, conversation_id, generated_topic)
                await db.commit()
                logger.info(f"Updated conversation title to: {generated_topic}")
            except Exception as e:
                logger.error(f"Failed to update conversation title: {e}")

    # 更新补充信息工具调用的状态为 confirmed
    if conversation_id and db:
        try:
            # 获取该对话的所有消息
            messages = await crud.get_messages_by_conversation(db, conversation_id)
            # 找到最后一条 assistant 消息
            for msg in reversed(messages):
                if msg.role == "assistant":
                    # 获取该消息的工具调用
                    tool_calls = await crud.get_tool_calls_by_message(db, msg.id)
                    # 找到 supplement_info 类型的工具调用
                    for tc in tool_calls:
                        if tc.tool_type == "supplement_info" and tc.status == "pending":
                            # 更新状态为 confirmed
                            await crud.update_tool_call_status(
                                db, tc.id, "confirmed", result_json=request.supplement_data
                            )
                            await db.commit()
                            logger.info(f"Updated tool call {tc.id} status to confirmed")
                            break
                    break
        except Exception as e:
            logger.error(f"Failed to update tool call status: {e}")

    # 返回流式响应继续生成
    return StreamingResponse(
        stream_ppt_generation(
            instruction=session["topic"],
            session_id=session_id,
            conversation_id=conversation_id,
            supplement_data=request.supplement_data,
            db=db,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


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
