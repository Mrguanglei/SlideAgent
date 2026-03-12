"""
PPTAgent 聊天处理服务

从 api_server.py 中提取的核心流式生成逻辑
"""

import os
import json
import logging
import asyncio
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from sqlalchemy import select as sa_select
from sqlalchemy.ext.asyncio import AsyncSession

from utils.config import Config
from utils.helpers import (
    normalize_conversation_title,
    strip_think_tags,
    clean_title_simple,
    extract_color_preference,
    extract_style_preference,
    estimate_num_pages_range,
    check_ppt_intent_by_keyword,
    generate_supplement_info,
)
from database import crud
from services.llm import call_llm_api, call_llm_api_stream, extract_core_topic
from services.search import (
    generate_search_queries,
    should_use_web_search,
    execute_search,
    stream_search_thinking,
    stream_deep_thinking,
)
from services.task_planner import (
    stream_outline_generation,
    build_task_steps,
    generate_execution_plan,
    build_plan_stream_chunks,
)
from services.ppt_generator import (
    parse_num_pages,
    run_slide_design_agent,
    run_slide_edit_agent,
    replace_image_placeholders,
)
from services.resource_inliner import inline_all_resources
from services.knowledge.document_parser import DocumentParser
from database.crud import delete_ppt_slide_by_page
from database.models import Session as SessionModel

logger = logging.getLogger(__name__)

async def resolve_instruction_with_context(
    instruction: str,
    conversation_id: Optional[int],
    db: Optional[AsyncSession],
    max_messages: int = 8,
) -> str:
    """
    用对话上下文解析当前用户意图，必要时把“模糊跟进句”重写为完整任务指令。
    """
    if not instruction or not db or not conversation_id:
        return instruction

    try:
        messages = await crud.get_messages_by_conversation(db, conversation_id)
        if not messages:
            return instruction

        # 仅保留最近若干条有效内容，控制提示词长度
        recent = []
        for msg in messages[-max_messages:]:
            content = strip_think_tags(msg.content or "").strip()
            if not content:
                continue
            role = "用户" if msg.role == "user" else "助手"
            recent.append(f"{role}: {content[:300]}")
        if len(recent) < 2:
            return instruction

        history_text = "\n".join(recent)
        prompt = f"""你是对话任务解析器。请结合历史上下文，判断当前用户输入是否是在延续上一个主题，并输出结构化 JSON。

历史对话（最近）：
{history_text}

当前用户输入：
{instruction}

请严格输出 JSON（不要输出其它内容）：
{{
  "should_inherit_context": true 或 false,
  "resolved_instruction": "重写后的完整任务指令（若无需重写则保持原句）",
  "resolved_topic": "提炼出的主题（若无则空字符串）",
  "confidence": 0 到 1 的小数
}}

规则：
1. 如果当前输入是“可以、看你的来、按你来、继续、开始做”等跟进语义，且历史里有明确主题，should_inherit_context=true，并把主题补全到 resolved_instruction。
2. 如果当前输入明显切换了新主题，则 should_inherit_context=false，不要继承旧主题。
3. 允许保留当前输入中的风格/页数/偏好约束，并与继承主题合并。
4. 不要编造新事实。"""

        raw = await call_llm_api([
            {"role": "system", "content": "你是严谨的任务解析器，只返回 JSON。"},
            {"role": "user", "content": prompt},
        ])

        match = re.search(r"\{[\s\S]*\}", raw or "")
        if not match:
            return instruction
        data = json.loads(match.group(0))
        resolved = strip_think_tags(str(data.get("resolved_instruction", "")).strip())
        confidence = float(data.get("confidence", 0) or 0)
        should_inherit = bool(data.get("should_inherit_context", False))

        if should_inherit and resolved and confidence >= 0.55:
            return resolved
    except Exception as e:
        logger.warning(f"Failed to resolve instruction with context: {e}")

    return instruction


async def infer_topic_from_file_llm(file_context: str, fallback: str = "未命名") -> str:
    """从文件内容中提炼主题标题（LLM）"""
    if not file_context:
        return fallback
    prompt = f"""请根据以下文档内容提炼一个简短、明确的PPT主题标题：
- 只输出标题，不要解释
- 不要包含"PPT/演示文稿/幻灯片/帮我/请"等指令词
- 尽量≤32个字

文档内容：
{file_context}
"""
    try:
        response = await call_llm_api([
            {"role": "system", "content": "你是标题提炼助手，只输出标题。"},
            {"role": "user", "content": prompt},
        ])
        title = clean_title_simple(response or "", max_len=32, fallback="")
        if title:
            return title
    except Exception as e:
        logger.warning(f"Failed to infer topic from file: {e}")
    return clean_title_simple(fallback, max_len=32, fallback="未命名")


async def generate_conversation_title_llm(text: str, max_len: int = 32) -> str:
    """用模型生成简短主题标题，失败时回退规则提取"""
    if not text:
        return "新对话"
    prompt = f"""请根据用户输入生成一个简短、明确的PPT主题标题。
- 只输出标题，不要解释
- 不要包含"PPT/演示文稿/幻灯片/帮我/请"等指令词
- 尽量≤{max_len}个字
用户输入：{text[:200]}
"""
    try:
        response = await call_llm_api([
            {"role": "system", "content": "你是标题提炼助手，只输出标题。"},
            {"role": "user", "content": prompt},
        ])
        if response:
            title = normalize_conversation_title(response, max_len=max_len)
            if title:
                return title
    except Exception as e:
        logger.warning(f"Failed to generate title with LLM: {e}")

    fallback = extract_core_topic(text)
    return normalize_conversation_title(fallback, max_len=max_len)


async def generate_supplement_info_llm(topic: str) -> dict:
    """用 LLM 根据主题动态生成补充信息表单选项，失败时回退到固定模板"""
    from utils.helpers import generate_supplement_info
    prompt = f"""你是一个PPT策划专家。用户想制作关于「{topic}」的PPT。
请根据这个主题，生成最合适的补充信息表单选项，以JSON格式输出：

{{
  "topic": "提炼后的简洁主题标题（≤20字）",
  "audienceOptions": ["最相关的受众1", "受众2", "受众3", "受众4"],
  "modulesOptions": ["最相关的内容模块1", "模块2", "模块3", "模块4", "模块5", "模块6"],
  "styleOptions": ["简约现代", "专业商务", "创意设计", "学术风格"],
  "numPagesOptions": ["8-10页", "11-15页", "16-20页", "21-25页"]
}}

要求：
- audienceOptions：根据主题推荐最可能的目标受众，4个选项
- modulesOptions：根据主题内容推荐最相关的内容模块，6个选项，要具体贴合主题
- styleOptions 和 numPagesOptions 保持固定选项不变
- 只输出JSON，不要解释"""

    try:
        import re as _re
        response = await call_llm_api([
            {"role": "system", "content": "你是PPT策划专家，只输出JSON。"},
            {"role": "user", "content": prompt},
        ])
        # 提取 JSON
        json_match = _re.search(r'\{[\s\S]*\}', response)
        if json_match:
            import json as _json
            data = _json.loads(json_match.group(0))
            return {
                "topic": data.get("topic", topic),
                "audienceQuestion": "这份PPT的目标受众是？",
                "audienceOptions": data.get("audienceOptions", ["专业人士", "普通公众", "学生群体", "企业客户"]),
                "modulesQuestion": "PPT中需要包含哪些内容模块？",
                "modulesOptions": data.get("modulesOptions", ["背景介绍", "核心内容", "案例分析", "数据展示", "总结建议", "Q&A"]),
                "styleQuestion": "你期望的PPT设计风格是？",
                "styleOptions": data.get("styleOptions", ["简约现代", "专业商务", "创意设计", "学术风格"]),
                "numPagesQuestion": "您期望的PPT页数范围是？",
                "numPagesOptions": data.get("numPagesOptions", ["8-10页", "11-15页", "16-20页", "21-25页"]),
                "emphasisQuestion": "是否有特定内容需要重点突出？",
                "emphasisPlaceholder": "例如：某个关键点、特定数据、核心结论等",
            }
    except Exception as e:
        logger.warning(f"Failed to generate supplement info with LLM: {e}")
    return generate_supplement_info(topic)


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
- 不要包含"PPT/演示文稿/幻灯片/帮我/请"等指令词
- 尽量≤{max_len}个字
{context}
"""
    try:
        response = await call_llm_api([
            {"role": "system", "content": "你是标题提炼助手，只输出标题。"},
            {"role": "user", "content": prompt},
        ])
        title = clean_title_simple(response or "", max_len=max_len, fallback="")
        if title:
            return title
    except Exception as e:
        logger.warning(f"Failed to generate PPT title with LLM: {e}")
    fallback = supplement_topic or instruction or "未命名"
    return clean_title_simple(fallback, max_len=max_len, fallback="未命名")


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
    outline_content: str = None,
):
    """流式生成 PPT 的核心函数（新版：关键词判断意图 + 固定补充信息模板）"""
    logger.info(f"[stream_ppt_generation] START - session={session_id}, conversation={conversation_id}")

    # 检查暂停的内部函数（直接查询 task_status，避免 ORM 缓存导致读到旧值）
    async def check_pause():
        if not db or not session_id:
            return False
        try:
            result = await db.execute(
                sa_select(SessionModel.task_status).where(SessionModel.id == session_id)
            )
            status = result.scalar_one_or_none()
            if status == "paused":
                logger.info(f"[stream_ppt_generation] Task paused by user: {session_id}")
                return True
        except Exception as e:
            logger.warning(f"[stream_ppt_generation] pause check failed: {e}")
        return False

    # ==================== 编辑已有 PPT 的快速路径 ====================
    # 如果当前对话已有 PPT 项目，直接走编辑流程，跳过意图识别和重新生成
    if db and conversation_id:
        try:
            existing_project = await crud.get_ppt_project_by_conversation(db, conversation_id)
            if existing_project:
                latest_version = await crud.get_latest_ppt_version(db, existing_project.id)
                if latest_version:
                    slides = await crud.get_ppt_slides(db, latest_version.id)
                    if slides:
                        existing_slides = [
                            {"page_number": s.page_number, "html_content": s.html_content or ""}
                            for s in sorted(slides, key=lambda x: x.page_number)
                        ]
                        workspace_dir = str(Path(Config.WORKSPACE_BASE) / session_id)

                        # 保存用户消息
                        if save_user_message:
                            try:
                                await crud.create_message(db, conversation_id, "user", instruction)
                                await db.commit()
                            except Exception as e:
                                logger.error(f"Failed to save user message: {e}")

                        # 编辑前自动创建新版本（保留历史）
                        new_version = None
                        try:
                            new_version_number = latest_version.version_number + 1
                            new_version = await crud.create_ppt_version(
                                db, existing_project.id,
                                version_number=new_version_number,
                                version_name=f"V{new_version_number}",
                            )
                            # 复制当前版本所有 slides 到新版本
                            slides_data = [
                                {"page_number": s.page_number, "html_content": s.html_content or "",
                                 "page_title": getattr(s, "page_title", None)}
                                for s in sorted(slides, key=lambda x: x.page_number)
                            ]
                            await crud.create_ppt_slides_batch(db, new_version.id, slides_data)
                            await db.commit()
                            # 后续操作在新版本上进行
                            new_slides = await crud.get_ppt_slides(db, new_version.id)
                            slides = new_slides
                            latest_version = new_version
                            logger.info(f"Created new version V{new_version_number} for project {existing_project.id}")
                        except Exception as e:
                            logger.error(f"Failed to create new version: {e}")
                            # 版本创建失败则继续在原版本上操作

                        # 提前创建 assistant 消息，用于挂载工具调用
                        edit_msg_id = None
                        try:
                            edit_msg = await crud.create_message(db, conversation_id, "assistant", "")
                            await db.commit()
                            edit_msg_id = edit_msg.id
                        except Exception as e:
                            logger.error(f"Failed to create edit assistant message: {e}")

                        async for event in run_slide_edit_agent(
                            instruction=instruction,
                            existing_slides=existing_slides,
                            workspace_dir=workspace_dir,
                            powerpoint_type=powerpoint_type,
                        ):
                            if await check_pause():
                                return
                            event_type = event.get("type")

                            if event_type == "slide_update":
                                page_number = event["page_number"]
                                html_content = event["html_content"]
                                description = event.get("description", f"第 {page_number} 页已更新")

                                # 更新数据库中对应页面
                                try:
                                    target_slide = next(
                                        (s for s in slides if s.page_number == page_number), None
                                    )
                                    if target_slide:
                                        await crud.update_ppt_slide(db, target_slide.id, html_content=html_content)
                                        await db.commit()
                                except Exception as e:
                                    logger.error(f"Failed to update slide {page_number}: {e}")

                                # 保存工具调用到数据库
                                if edit_msg_id:
                                    try:
                                        await crud.create_tool_call(
                                            db, edit_msg_id, "ppt_edit",
                                            f"更新页面 {page_number}", "completed",
                                            arguments_json={"pageNumber": page_number, "description": description},
                                            result_json={"pageNumber": page_number, "description": description},
                                        )
                                        await db.commit()
                                    except Exception as e:
                                        logger.error(f"Failed to save ppt_edit tool call: {e}")

                                slide_tool_data = {
                                    "type": "tool_call",
                                    "tool_type": "ppt_edit",
                                    "tool_name": f"更新页面 {page_number}",
                                    "status": "completed",
                                    "data": {
                                        "pageNumber": page_number,
                                        "html": html_content,
                                        "content": html_content,
                                        "description": description,
                                    },
                                }
                                yield f"data: {json.dumps(slide_tool_data, ensure_ascii=False)}\n\n"
                                yield f"data: {json.dumps({'type': 'ppt_slide_update', 'html': html_content, 'page_number': page_number}, ensure_ascii=False)}\n\n"

                            elif event_type == "slide_remove":
                                page_numbers = event.get("page_numbers", [])
                                description = event.get("description", f"删除第 {page_numbers} 页")
                                for page_number in page_numbers:
                                    try:
                                        await delete_ppt_slide_by_page(db, latest_version.id, page_number)
                                        await db.commit()
                                    except Exception as e:
                                        logger.error(f"Failed to delete slide {page_number}: {e}")

                                # 保存工具调用到数据库
                                if edit_msg_id:
                                    try:
                                        await crud.create_tool_call(
                                            db, edit_msg_id, "ppt_remove",
                                            f"删除页面 {page_numbers}", "completed",
                                            arguments_json={"pageNumbers": page_numbers, "description": description},
                                            result_json={"pageNumbers": page_numbers, "description": description},
                                        )
                                        await db.commit()
                                    except Exception as e:
                                        logger.error(f"Failed to save ppt_remove tool call: {e}")

                                remove_tool_data = {
                                    "type": "tool_call",
                                    "tool_type": "ppt_remove",
                                    "tool_name": f"删除页面 {page_numbers}",
                                    "status": "completed",
                                    "data": {
                                        "pageNumbers": page_numbers,
                                        "description": description,
                                    },
                                }
                                yield f"data: {json.dumps(remove_tool_data, ensure_ascii=False)}\n\n"
                                yield f"data: {json.dumps({'type': 'ppt_slide_remove', 'page_numbers': page_numbers}, ensure_ascii=False)}\n\n"

                            elif event_type == "message":
                                yield f"data: {json.dumps({'type': 'message', 'role': 'assistant', 'content': event['content'], 'streaming': False}, ensure_ascii=False)}\n\n"

                            elif event_type == "complete":
                                yield f"data: {json.dumps({'type': 'ppt_edit_complete', 'role': 'assistant', 'content': event['content'], 'streaming': False}, ensure_ascii=False)}\n\n"
                                try:
                                    if edit_msg_id:
                                        await crud.update_message_content(db, edit_msg_id, event["content"])
                                    else:
                                        await crud.create_message(db, conversation_id, "assistant", event["content"])
                                    await db.commit()
                                except Exception:
                                    pass

                            elif event_type == "error":
                                yield f"data: {json.dumps({'type': 'error', 'role': 'assistant', 'content': event['content']}, ensure_ascii=False)}\n\n"

                        yield f"data: {json.dumps({'type': 'done'})}\n\n"
                        return
        except Exception as e:
            logger.error(f"Failed to check existing PPT project: {e}")
            # 出错则继续走正常生成流程

    # 发送 conversation_created 事件
    if is_new_conversation and conversation_uuid:
        yield f"data: {json.dumps({'type': 'conversation_created', 'conversation_id': conversation_id, 'conversation_uuid': conversation_uuid}, ensure_ascii=False)}\n\n"

    # ==================== 初始化 session ====================
    session = None
    if db:
        existing_session = await crud.get_session(db, session_id)
        if existing_session:
            # 如果旧 session 已完成/等待，新消息应重置为 init 并使用新 instruction
            old_stage = existing_session.stage
            if old_stage in ("completed", "waiting_supplement", "init"):
                effective_topic = instruction
                effective_stage = "init"
                await crud.update_session(db, session_id, stage="init", topic=instruction, task_status="running")
            else:
                effective_topic = existing_session.topic
                effective_stage = old_stage
                await crud.update_session(db, session_id, task_status="running")
            await db.commit()
            session = {
                "topic": effective_topic,
                "stage": effective_stage,
                "search_results": existing_session.search_results or [],
                "outline_content": existing_session.outline_content or "",
                "deep_thinking_content": existing_session.deep_thinking_content or "",
                "supplement_data": existing_session.supplement_data or {},
                "execution_plan": (existing_session.supplement_data or {}).get("execution_plan", {}),
                "conversation_id": existing_session.conversation_id or conversation_id,
                "image_results": [],
                "workspace_dir": str(Path(Config.WORKSPACE_BASE) / session_id),
            }
        else:
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
                "execution_plan": {},
                "conversation_id": conversation_id,
                "image_results": [],
                "workspace_dir": str(Path(Config.WORKSPACE_BASE) / session_id),
            }
    else:
        session = {
            "topic": instruction,
            "stage": "init",
            "search_results": [],
            "outline_content": "",
            "deep_thinking_content": "",
            "supplement_data": supplement_data or {},
            "execution_plan": {},
            "conversation_id": conversation_id,
            "image_results": [],
            "workspace_dir": str(Path(Config.WORKSPACE_BASE) / session_id),
        }

    # 合并 supplement_data
    if supplement_data is not None:
        if session["supplement_data"] is None:
            session["supplement_data"] = {}
        session["supplement_data"].update(supplement_data)
        session["stage"] = "confirmed"
        if db:
            await crud.update_session(
                db, session_id,
                stage="confirmed",
                supplement_data=session["supplement_data"]
            )
            await db.commit()

    # 记录搜索模式
    if search_mode:
        normalized_mode = str(search_mode).strip().lower()
        if normalized_mode in ("auto", "on", "off"):
            if session["supplement_data"] is None:
                session["supplement_data"] = {}
            session["supplement_data"]["search_mode"] = normalized_mode
            if db:
                await crud.update_session(db, session_id, supplement_data=session["supplement_data"])
                await db.commit()

    # 保存用户消息
    if db and conversation_id and save_user_message:
        try:
            user_msg = await crud.create_message(db, conversation_id, "user", instruction)
            if attachments:
                for attachment in attachments:
                    try:
                        await crud.create_message_attachment(
                            db, user_msg.id,
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

    # ==================== 处理附件 ====================
    file_context = ""
    if attachments:
        extracted_texts = []
        for att in attachments:
            file_path = att.get("file_path")
            knowledge_id = att.get("knowledge_document_id")
            if knowledge_id and not file_path and db:
                try:
                    k_doc = await crud.get_knowledge_document(db, int(knowledge_id))
                    if k_doc:
                        file_path = k_doc.file_path
                        if not att.get("filename"):
                            att["filename"] = k_doc.filename
                except Exception as e:
                    logger.error(f"Failed to get knowledge document {knowledge_id}: {e}")
            if file_path and os.path.exists(file_path):
                try:
                    text, meta = await DocumentParser.parse(file_path)
                    extracted_texts.append(f"--- 文件: {att.get('filename', 'unknown')} ---\n{text}\n")
                except Exception as e:
                    logger.error(f"Failed to parse attachment {file_path}: {e}")
        if extracted_texts:
            file_context = "\n".join(extracted_texts)
            if session["supplement_data"] is None:
                session["supplement_data"] = {}
            if "file_context" not in session["supplement_data"]:
                session["supplement_data"]["file_context"] = file_context
                session["supplement_data"]["skip_search"] = True
                if db:
                    await crud.update_session(db, session_id, supplement_data=session["supplement_data"])
                    await db.commit()

    # ==================== 上下文指令解析（智能体逻辑） ====================
    task_instruction = instruction
    if session.get("stage") == "init":
        resolved_instruction = await resolve_instruction_with_context(
            instruction=instruction,
            conversation_id=conversation_id,
            db=db,
        )
        if resolved_instruction and resolved_instruction != instruction:
            task_instruction = resolved_instruction
            session["topic"] = resolved_instruction
            logger.info(
                "[stream_ppt_generation] Resolved follow-up instruction by context: "
                f"raw='{instruction[:80]}' -> resolved='{resolved_instruction[:120]}'"
            )
            if db:
                await crud.update_session(db, session_id, topic=resolved_instruction)
                await db.commit()

    # ==================== 阶段 1: 关键词判断 PPT 意图 ====================

    if session["stage"] == "init":
        file_context = (session.get("supplement_data") or {}).get("file_context", "")
        has_attachments = bool(attachments) or (isinstance(file_context, str) and file_context.strip())
        is_ppt_request = check_ppt_intent_by_keyword(task_instruction, has_attachments=has_attachments)

        if not is_ppt_request:
            # 非 PPT 请求，直接 LLM 流式回复
            response_text = ""
            async for chunk in call_llm_api_stream([
                {"role": "system", "content": "你是 SlideAgent，一个专业的 PPT 制作助手。用户似乎没有明确的 PPT 制作需求，请友好地回应并引导用户。"},
                {"role": "user", "content": task_instruction}
            ]):
                if await check_pause():
                    return
                response_text += chunk
                if not chunk:
                    continue
                message_data = {
                    'type': 'message',
                    'content': chunk,
                    'role': 'assistant',
                    'streaming': True,
                    'created_at': datetime.now().isoformat()
                }
                yield f"data: {json.dumps(message_data, ensure_ascii=False)}\n\n"

            if db and conversation_id:
                try:
                    await crud.create_message(db, conversation_id, "assistant", response_text)
                    await db.commit()
                except Exception as e:
                    logger.error(f"Failed to save assistant message: {e}")
            if db:
                await crud.update_session(db, session_id, task_status="completed")
                await db.commit()
            yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
            return

        # 是 PPT 请求 → 检查是否有文件上传（跳过补充信息）
        file_context = (session.get("supplement_data") or {}).get("file_context", "")
        if isinstance(file_context, str) and file_context.strip():
            auto_updates: Dict[str, Any] = {}
            current_supplement = session.get("supplement_data") or {}
            if not current_supplement.get("topic"):
                auto_updates["topic"] = await infer_topic_from_file_llm(file_context, fallback=task_instruction or "未命名")
            if not current_supplement.get("num_pages"):
                auto_updates["num_pages"] = estimate_num_pages_range(file_context)
            if not current_supplement.get("style"):
                style_pref = extract_style_preference(task_instruction or "")
                auto_updates["style"] = style_pref or "简约现代"
            if not current_supplement.get("color_preference"):
                color_pref = extract_color_preference(task_instruction or "")
                if color_pref:
                    auto_updates["color_preference"] = color_pref
            if auto_updates:
                if session["supplement_data"] is None:
                    session["supplement_data"] = {}
                session["supplement_data"].update(auto_updates)
            session["stage"] = "confirmed"
            if db:
                await crud.update_session(db, session_id, stage="confirmed", supplement_data=session["supplement_data"])
                await db.commit()
            if db and conversation_id:
                try:
                    topic_title = (session.get("supplement_data") or {}).get("topic")
                    if topic_title:
                        await crud.update_conversation_title(db, conversation_id, normalize_conversation_title(topic_title))
                        await db.commit()
                except Exception as e:
                    logger.error(f"Failed to update conversation title: {e}")
        else:
            session["stage"] = "supplement_info"

    # ==================== 阶段 2: 发送固定补充信息表单 ====================

    if session["stage"] == "supplement_info":
        greeting_message = '让我先核对下本轮任务的目标和重点偏好，正在梳理您的需求~'
        for char in greeting_message:
            message_data = {
                'type': 'message', 'content': char, 'role': 'assistant',
                'streaming': True, 'created_at': datetime.now().isoformat()
            }
            yield f"data: {json.dumps(message_data, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.03)

        yield f"data: {json.dumps({'type': 'message', 'content': '', 'role': 'assistant', 'streaming': False}, ensure_ascii=False)}\n\n"

        # 使用 LLM 动态生成补充信息
        supplement_info = await generate_supplement_info_llm(task_instruction)

        tool_call_data = {
            'type': 'tool_call', 'tool_type': 'supplement_info',
            'tool_name': '补充信息', 'status': 'pending', 'data': supplement_info
        }
        yield f"data: {json.dumps(tool_call_data, ensure_ascii=False)}\n\n"

        if db and conversation_id:
            try:
                msg = await crud.create_message(db, conversation_id, "assistant", greeting_message)
                await crud.create_tool_call(db, msg.id, "supplement_info", "补充信息", "pending", arguments_json=supplement_info)
                await db.commit()
            except Exception as e:
                logger.error(f"Failed to save supplement info: {e}")

        session["stage"] = "waiting_supplement"
        if db:
            await crud.update_session(db, session_id, stage="waiting_supplement")
            await db.commit()
        return

    # ==================== 阶段 3: 直接进入大纲生成（跳过任务规划） ====================

    if session["stage"] == "confirmed":
        logger.info(f"[stream_ppt_generation] Confirmed stage, skipping task plan, going to search/outline")

        # 发送任务执行规划面板
        task_plan_start_event = {
            "type": "task_plan_stream",
            "content": "正在基于你的输入和补充信息，生成任务执行规划...\n",
        }
        yield "data: " + json.dumps(task_plan_start_event, ensure_ascii=False) + "\n\n"
        if await check_pause():
            return

        try:
            task_plan_data = await generate_execution_plan(
                topic=task_instruction,
                supplement_data=session.get("supplement_data") or {},
            )
        except Exception as e:
            logger.warning(f"Failed to generate execution plan, fallback to default steps: {e}")
            task_steps = build_task_steps(session.get("supplement_data") or {})
            task_plan_data = {
                "steps": task_steps,
                "plan_content": "",
                "streamContent": "",
                "recommendedSearchQueries": [],
                "outlineDirectives": [],
                "designDirectives": [],
                "shouldSearch": True,
            }

        for chunk in build_plan_stream_chunks(task_plan_data):
            if await check_pause():
                return
            yield f"data: {json.dumps({'type': 'task_plan_stream', 'content': chunk}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.015)

        session["execution_plan"] = task_plan_data
        if session["supplement_data"] is None:
            session["supplement_data"] = {}
        session["supplement_data"]["execution_plan"] = task_plan_data

        if db and conversation_id:
            try:
                plan_msg = await crud.create_message(db, conversation_id, "assistant", "")
                plan_tool_call = await crud.create_tool_call(
                    db,
                    plan_msg.id,
                    "task_plan",
                    "任务执行规划",
                    "completed",
                    result_json=task_plan_data,
                )
                await crud.create_task_plan(
                    db,
                    plan_tool_call.id,
                    plan_content=task_plan_data.get("plan_content", ""),
                    steps_json=task_plan_data.get("steps", []),
                )
                await db.commit()
            except Exception as e:
                logger.error(f"Failed to save task plan: {e}")
        yield f"data: {json.dumps({'type': 'tool_call', 'tool_type': 'task_plan', 'tool_name': '任务执行规划', 'status': 'completed', 'data': task_plan_data}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'type': 'task_plan_complete', 'data': task_plan_data}, ensure_ascii=False)}\n\n"

        # 根据搜索模式决定下一阶段
        sm = (session.get("supplement_data") or {}).get("search_mode", "auto")
        sm = str(sm).strip().lower()
        if sm not in ("auto", "on", "off"):
            sm = "auto"

        if sm == "off":
            session["stage"] = "outline"
            session["search_results"] = []
            session["deep_thinking_content"] = ""
        elif sm == "on":
            session["stage"] = "searching"
        else:
            should_search = await should_use_web_search(task_instruction, session.get("supplement_data") or {})
            session["stage"] = "searching" if should_search else "outline"
            if not should_search:
                session["search_results"] = []
                session["deep_thinking_content"] = ""

        if db:
            await crud.update_session(
                db, session_id,
                stage=session["stage"],
                supplement_data=session.get("supplement_data"),
                search_results=session.get("search_results"),
                deep_thinking_content=session.get("deep_thinking_content"),
            )
            await db.commit()

    # ==================== 阶段 4: 搜索 ====================

    if session["stage"] == "searching":
        if await check_pause():
            return

        execution_plan = session.get("execution_plan") or (session.get("supplement_data") or {}).get("execution_plan", {})
        plan_queries = []
        if isinstance(execution_plan, dict):
            raw_queries = execution_plan.get("recommendedSearchQueries") or execution_plan.get("recommended_search_queries") or []
            if isinstance(raw_queries, list):
                for q in raw_queries:
                    sq = str(q or "").strip()
                    if sq:
                        plan_queries.append(sq[:80])
        plan_queries = list(dict.fromkeys(plan_queries))[:8]

        if plan_queries:
            search_queries = plan_queries
            logger.info(f"Using execution plan search queries: {search_queries}")
        else:
            search_queries = await generate_search_queries(
                task_instruction,
                session["supplement_data"],
                execution_plan=execution_plan if isinstance(execution_plan, dict) else None,
            )
        all_search_results = []

        for round_num, query in enumerate(search_queries, 1):
            if await check_pause():
                return

            yield f"data: {json.dumps({'type': 'search_start', 'round': round_num, 'query': query, 'total_rounds': len(search_queries)}, ensure_ascii=False)}\n\n"

            results = await execute_search(query)
            if await check_pause():
                return
            all_search_results.extend(results)

            for result in results:
                if await check_pause():
                    return
                yield f"data: {json.dumps({'type': 'search_result', 'round': round_num, 'result': result}, ensure_ascii=False)}\n\n"

            yield f"data: {json.dumps({'type': 'search_complete', 'round': round_num, 'query': query, 'results_count': len(results)}, ensure_ascii=False)}\n\n"

            yield f"data: {json.dumps({'type': 'tool_call', 'tool_type': 'web_search', 'tool_name': '搜索网页', 'status': 'completed', 'data': {'query': query, 'round': round_num, 'total_rounds': len(search_queries), 'results': results}}, ensure_ascii=False)}\n\n"

            if db and conversation_id:
                try:
                    msg = await crud.create_message(db, conversation_id, "assistant", "")
                    tc = await crud.create_tool_call(
                        db, msg.id, "web_search", "搜索网页", "completed",
                        arguments_json={"query": query, "round": round_num, "total_rounds": len(search_queries)},
                        result_json={"results": results}
                    )
                    sr = await crud.create_search_round(db, tc.id, query, round_num)
                    await crud.create_search_results(db, sr.id, results)
                    await db.commit()
                except Exception as e:
                    logger.error(f"Failed to save search results: {e}")

            thinking_text = ""
            async for chunk in stream_search_thinking(query, results, round_num, len(search_queries)):
                if await check_pause():
                    return
                thinking_text += chunk
                yield f"data: {json.dumps({'type': 'message', 'role': 'assistant', 'content': chunk, 'streaming': True}, ensure_ascii=False)}\n\n"

            yield f"data: {json.dumps({'type': 'message', 'role': 'assistant', 'content': '', 'streaming': False}, ensure_ascii=False)}\n\n"

            if db and conversation_id and thinking_text:
                try:
                    await crud.create_message(db, conversation_id, "assistant", thinking_text)
                    await db.commit()
                except Exception as e:
                    logger.error(f"Failed to save thinking message: {e}")

        session["search_results"] = all_search_results
        session["stage"] = "deep_thinking"
        if db:
            await crud.update_session(db, session_id, stage="deep_thinking", search_results=all_search_results)
            await db.commit()

    # ==================== 阶段 5: 深度思考 ====================

    if session["stage"] == "deep_thinking":
        if await check_pause():
            return

        yield f"data: {json.dumps({'type': 'deep_thinking_start', 'content': '正在整理和分析搜索结果...'}, ensure_ascii=False)}\n\n"

        deep_thinking_content = ""
        async for chunk in stream_deep_thinking(task_instruction, session["search_results"]):
            if await check_pause():
                return
            deep_thinking_content += chunk
            yield f"data: {json.dumps({'type': 'deep_thinking_stream', 'content': chunk}, ensure_ascii=False)}\n\n"

        yield f"data: {json.dumps({'type': 'deep_thinking_complete', 'content': deep_thinking_content}, ensure_ascii=False)}\n\n"

        session["deep_thinking_content"] = deep_thinking_content

        if db and conversation_id and deep_thinking_content:
            try:
                messages = await crud.get_messages_by_conversation(db, conversation_id)
                for msg in reversed(messages):
                    tool_calls = await crud.get_tool_calls_by_message(db, msg.id)
                    for tc in reversed(tool_calls):
                        if tc.tool_type == "web_search":
                            search_rounds = await crud.get_search_rounds_by_tool_call(db, tc.id)
                            if search_rounds:
                                last_round = search_rounds[-1]
                                from sqlalchemy import update as sa_update
                                from database.models import SearchRound
                                await db.execute(
                                    sa_update(SearchRound).where(SearchRound.id == last_round.id).values(thinking_content=deep_thinking_content)
                                )
                                await db.commit()
                                break
                    else:
                        continue
                    break
            except Exception as e:
                logger.error(f"Failed to save deep thinking: {e}")

        session["stage"] = "outline"
        if db:
            await crud.update_session(db, session_id, stage="outline", deep_thinking_content=deep_thinking_content)
            await db.commit()

    # ==================== 阶段 6: 生成大纲 ====================

    if session["stage"] == "outline":
        if await check_pause():
            return

        outline_content = ""
        async for chunk in stream_outline_generation(
            task_instruction, session["search_results"],
            session["deep_thinking_content"], session["supplement_data"],
            execution_plan=session.get("execution_plan") or (session.get("supplement_data") or {}).get("execution_plan", {}),
        ):
            if await check_pause():
                return
            outline_content += chunk
            yield f"data: {json.dumps({'type': 'ppt_outline_stream', 'content': chunk}, ensure_ascii=False)}\n\n"

        session["outline_content"] = outline_content

        yield f"data: {json.dumps({'type': 'ppt_outline_complete', 'content': outline_content}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'type': 'tool_call', 'tool_type': 'ppt_outline', 'tool_name': 'PPT 大纲目录', 'status': 'completed', 'data': {'content': outline_content}}, ensure_ascii=False)}\n\n"

        if db and conversation_id:
            try:
                msg = await crud.create_message(db, conversation_id, "assistant", "")
                await crud.create_tool_call(db, msg.id, "ppt_outline", "PPT 大纲目录", "completed", result_json={"content": outline_content})
                await db.commit()
            except Exception as e:
                logger.error(f"Failed to save outline: {e}")

        session["stage"] = "generating"
        if db:
            await crud.update_session(db, session_id, stage="generating", outline_content=outline_content)
            await db.commit()

    # ==================== 阶段 7: 生成 PPT ====================

    if session["stage"] == "generating":
        if await check_pause():
            return

        actual_num_pages = parse_num_pages(session["supplement_data"])

        ppt_project = None
        ppt_version = None
        if db and conversation_id:
            try:
                supplement_topic = session.get("supplement_data", {}).get("topic", "")
                ol_content = session.get("outline_content", "")
                project_title = session.get("ppt_title") or await generate_ppt_title_llm(
                    instruction=task_instruction, outline_content=ol_content,
                    supplement_topic=supplement_topic, max_len=32
                )
                project_title = strip_think_tags(project_title) or project_title
                session["ppt_title"] = project_title
                ppt_project = await crud.create_ppt_project(db, conversation_id, project_title, ol_content)
                ppt_version = await crud.create_ppt_version(db, ppt_project.id, 1, "V1")
                await db.commit()
            except Exception as e:
                logger.error(f"Failed to create PPT project: {e}")

        slide_count = 0

        async for event in run_slide_design_agent(
            topic=task_instruction,
            outline_content=session["outline_content"],
            search_results=session["search_results"],
            deep_thinking_content=session["deep_thinking_content"],
            supplement_data=session["supplement_data"],
            num_pages=actual_num_pages,
            powerpoint_type=powerpoint_type,
            image_results=session.get("image_results", []),
            workspace_dir=session.get("workspace_dir", ""),
            execution_plan=session.get("execution_plan") or (session.get("supplement_data") or {}).get("execution_plan", {}),
        ):
            if await check_pause():
                return
            event_type = event.get("type")

            if event_type == "slide":
                slide_count = event["slide_count"]
                html_content = event["html_content"]
                description = event.get("description", f"第 {slide_count} 页")

                try:
                    html_content = replace_image_placeholders(html_content, session.get("image_results", []))
                except Exception as e:
                    logger.error(f"Failed to replace image placeholders for slide {slide_count}: {e}")

                try:
                    html_content = await inline_all_resources(html_content, timeout=30)
                except Exception as e:
                    logger.error(f"Failed to inline resources for slide {slide_count}: {e}")

                slide_tool_data = {
                    'type': 'tool_call', 'tool_type': 'ppt_generate',
                    'tool_name': f'创建幻灯片 {slide_count}', 'status': 'completed',
                    'data': {"pageNumber": slide_count, "html": html_content, "content": html_content, "description": description}
                }
                yield f"data: {json.dumps(slide_tool_data, ensure_ascii=False)}\n\n"
                yield f"data: {json.dumps({'type': 'ppt_slide', 'html': html_content, 'slide_count': slide_count}, ensure_ascii=False)}\n\n"

                if db and ppt_version:
                    try:
                        await crud.create_ppt_slide(db, ppt_version.id, slide_count, html_content, description)
                        await db.commit()
                    except Exception as e:
                        logger.error(f"Failed to save slide: {e}")

                if db and conversation_id:
                    try:
                        slide_msg = await crud.create_message(db, conversation_id, "assistant", "")
                        await crud.create_tool_call(
                            db, slide_msg.id, "ppt_generate", f'创建幻灯片 {slide_count}', "completed",
                            result_json={"pageNumber": slide_count, "html": html_content, "description": description}
                        )
                        await db.commit()
                    except Exception as e:
                        logger.error(f"Failed to save ppt_generate tool call: {e}")

            elif event_type == "thinking":
                if db and conversation_id:
                    try:
                        await crud.create_message(db, conversation_id, "assistant", event["content"])
                        await db.commit()
                    except Exception as e:
                        logger.error(f"Failed to save thinking message: {e}")
                yield f"data: {json.dumps({'type': 'message', 'role': 'assistant', 'content': event['content'], 'streaming': False}, ensure_ascii=False)}\n\n"

            elif event_type == "message":
                yield f"data: {json.dumps({'type': 'message', 'role': event.get('role', 'assistant'), 'content': event['content'], 'streaming': False}, ensure_ascii=False)}\n\n"

            elif event_type == "complete":
                project_data = None
                if ppt_project:
                    latest_version = await crud.get_latest_ppt_version(db, ppt_project.id) if db else None
                    project_data = {
                        'id': ppt_project.id, 'conversation_id': ppt_project.conversation_id,
                        'title': ppt_project.title, 'outline_content': ppt_project.outline_content,
                        'created_at': ppt_project.created_at.isoformat() if ppt_project.created_at else None,
                        'updated_at': ppt_project.updated_at.isoformat() if ppt_project.updated_at else None,
                        'current_version': {
                            'id': latest_version.id if latest_version else None,
                            'version_number': latest_version.version_number if latest_version else 1,
                            'version_name': latest_version.version_name if latest_version else None,
                        },
                    }
                yield f"data: {json.dumps({'type': 'ppt_complete', 'role': 'assistant', 'content': event['content'], 'streaming': False, 'project': project_data}, ensure_ascii=False)}\n\n"
                if db and conversation_id:
                    try:
                        await crud.create_message(db, conversation_id, "assistant", event["content"])
                        await db.commit()
                    except Exception as e:
                        logger.error(f"Failed to save complete message: {e}")

            elif event_type == "error":
                yield f"data: {json.dumps({'type': 'error', 'role': 'assistant', 'content': event['content']}, ensure_ascii=False)}\n\n"

        session["stage"] = "completed"
        if db:
            await crud.update_session(db, session_id, stage="completed", task_status="completed")
            await db.commit()

        yield f"data: {json.dumps({'type': 'done'})}\n\n"
