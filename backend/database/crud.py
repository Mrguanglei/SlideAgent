"""
PPTAgent 数据库 CRUD 操作

提供对话、消息、工具调用、PPT 等数据的增删改查操作
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

from sqlalchemy import select, update, delete, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .models import (
    Conversation, Message, ToolCall,
    SearchRound, SearchResult, TaskPlan,
    PPTProject, PPTVersion, PPTSlide,
    Share, Session, PPTExport, MessageAttachment,
    KnowledgeDocument
)

logger = logging.getLogger(__name__)


# ==================== 对话相关操作 ====================

async def create_conversation(
    db: AsyncSession,
    title: str = "新对话",
    user_id: Optional[int] = None
) -> Conversation:
    """创建新对话"""
    conversation = Conversation(
        title=title,
        user_id=user_id
    )
    db.add(conversation)
    await db.flush()
    await db.refresh(conversation)
    logger.info(f"Created conversation: {conversation.id}")
    return conversation


async def get_conversation(
    db: AsyncSession,
    conversation_id: int,
    include_messages: bool = False,
    include_ppt: bool = False
) -> Optional[Conversation]:
    """获取对话详情（通过数字 ID）"""
    query = select(Conversation).where(Conversation.id == conversation_id)

    if include_messages:
        query = query.options(
            selectinload(Conversation.messages).selectinload(Message.tool_calls)
        )

    if include_ppt:
        query = query.options(
            selectinload(Conversation.ppt_projects).selectinload(PPTProject.versions).selectinload(PPTVersion.slides)
        )

    result = await db.execute(query)
    return result.scalar_one_or_none()


async def get_conversation_by_uuid(
    db: AsyncSession,
    conversation_uuid: str,
    include_messages: bool = False,
    include_ppt: bool = False
) -> Optional[Conversation]:
    """获取对话详情（通过 UUID）"""
    query = select(Conversation).where(Conversation.uuid == conversation_uuid)

    if include_messages:
        query = query.options(
            selectinload(Conversation.messages).selectinload(Message.tool_calls)
        )

    if include_ppt:
        query = query.options(
            selectinload(Conversation.ppt_projects).selectinload(PPTProject.versions).selectinload(PPTVersion.slides)
        )

    result = await db.execute(query)
    return result.scalar_one_or_none()


async def get_conversations_list(
    db: AsyncSession,
    user_id: Optional[int] = None,
    limit: int = 50,
    offset: int = 0
) -> List[Conversation]:
    """获取对话列表（用于侧边栏）"""
    query = select(Conversation).order_by(desc(Conversation.updated_at))
    
    if user_id is not None:
        query = query.where(Conversation.user_id == user_id)
    
    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    return list(result.scalars().all())


async def update_conversation_title(
    db: AsyncSession,
    conversation_id: int,
    title: str
) -> bool:
    """更新对话标题"""
    stmt = update(Conversation).where(
        Conversation.id == conversation_id
    ).values(title=title, updated_at=datetime.utcnow())
    result = await db.execute(stmt)
    return result.rowcount > 0


async def delete_conversation(
    db: AsyncSession,
    conversation_id: int
) -> bool:
    """删除对话（级联删除所有关联数据）"""
    stmt = delete(Conversation).where(Conversation.id == conversation_id)
    result = await db.execute(stmt)
    return result.rowcount > 0


# ==================== 消息相关操作 ====================

async def create_message(
    db: AsyncSession,
    conversation_id: int,
    role: str,
    content: Optional[str] = None
) -> Message:
    """创建消息"""
    message = Message(
        conversation_id=conversation_id,
        role=role,
        content=content
    )
    db.add(message)
    await db.flush()
    await db.refresh(message)
    
    # 更新对话的 updated_at
    await db.execute(
        update(Conversation).where(Conversation.id == conversation_id).values(updated_at=datetime.utcnow())
    )
    
    return message


async def get_messages_by_conversation(
    db: AsyncSession,
    conversation_id: int,
    include_tool_calls: bool = True
) -> List[Message]:
    """获取对话的所有消息"""
    query = select(Message).where(
        Message.conversation_id == conversation_id
    ).order_by(Message.created_at)
    
    if include_tool_calls:
        query = query.options(
            selectinload(Message.tool_calls),
            selectinload(Message.attachments)
        )
    
    result = await db.execute(query)
    return list(result.scalars().all())


async def update_message_content(
    db: AsyncSession,
    message_id: int,
    content: str
) -> bool:
    """更新消息内容"""
    stmt = update(Message).where(Message.id == message_id).values(content=content)
    result = await db.execute(stmt)
    return result.rowcount > 0


async def create_message_attachment(
    db: AsyncSession,
    message_id: int,
    filename: str,
    file_path: str,
    file_size: int = 0,
    content_type: Optional[str] = None
) -> MessageAttachment:
    """创建消息附件"""
    attachment = MessageAttachment(
        message_id=message_id,
        filename=filename,
        file_path=file_path,
        file_size=file_size,
        content_type=content_type
    )
    db.add(attachment)
    await db.flush()
    await db.refresh(attachment)
    return attachment


async def get_message_attachments(
    db: AsyncSession,
    message_id: int
) -> List[MessageAttachment]:
    """获取消息的所有附件"""
    query = select(MessageAttachment).where(
        MessageAttachment.message_id == message_id
    )
    result = await db.execute(query)
    return list(result.scalars().all())


# ==================== 工具调用相关操作 ====================

async def create_tool_call(
    db: AsyncSession,
    message_id: int,
    tool_type: str,
    tool_name: str,
    status: str = "pending",
    arguments_json: Optional[Dict] = None,
    result_json: Optional[Dict] = None
) -> ToolCall:
    """创建工具调用记录"""
    tool_call = ToolCall(
        message_id=message_id,
        tool_type=tool_type,
        tool_name=tool_name,
        status=status,
        arguments_json=arguments_json,
        result_json=result_json
    )
    db.add(tool_call)
    await db.flush()
    await db.refresh(tool_call)
    return tool_call


async def update_tool_call_status(
    db: AsyncSession,
    tool_call_id: int,
    status: str,
    result_json: Optional[Dict] = None
) -> bool:
    """更新工具调用状态"""
    values = {"status": status}
    if result_json is not None:
        values["result_json"] = result_json
    
    stmt = update(ToolCall).where(ToolCall.id == tool_call_id).values(**values)
    result = await db.execute(stmt)
    return result.rowcount > 0


async def get_tool_calls_by_message(
    db: AsyncSession,
    message_id: int
) -> List[ToolCall]:
    """获取消息的所有工具调用"""
    query = select(ToolCall).where(
        ToolCall.message_id == message_id
    ).order_by(ToolCall.created_at)
    result = await db.execute(query)
    return list(result.scalars().all())


# ==================== 搜索相关操作 ====================

async def create_search_round(
    db: AsyncSession,
    tool_call_id: int,
    query: str,
    round_number: int = 1
) -> SearchRound:
    """创建搜索轮次"""
    search_round = SearchRound(
        tool_call_id=tool_call_id,
        query=query,
        round_number=round_number
    )
    db.add(search_round)
    await db.flush()
    await db.refresh(search_round)
    return search_round


async def create_search_results(
    db: AsyncSession,
    search_round_id: int,
    results: List[Dict[str, str]]
) -> List[SearchResult]:
    """批量创建搜索结果"""
    search_results = []
    for result in results:
        # 支持 snippet 和 content 两种字段名
        content = result.get("snippet", "") or result.get("content", "")
        sr = SearchResult(
            search_round_id=search_round_id,
            title=result.get("title", ""),
            url=result.get("url", ""),
            content=content
        )
        db.add(sr)
        search_results.append(sr)
    
    await db.flush()
    return search_results


async def get_search_rounds_by_tool_call(
    db: AsyncSession,
    tool_call_id: int
) -> List[SearchRound]:
    """获取工具调用的所有搜索轮次"""
    query = select(SearchRound).where(
        SearchRound.tool_call_id == tool_call_id
    ).options(
        selectinload(SearchRound.search_results)
    ).order_by(SearchRound.round_number)
    result = await db.execute(query)
    return list(result.scalars().all())


# ==================== 任务规划相关操作 ====================

async def create_task_plan(
    db: AsyncSession,
    tool_call_id: int,
    plan_content: Optional[str] = None,
    steps_json: Optional[List[Dict]] = None
) -> TaskPlan:
    """创建任务规划"""
    task_plan = TaskPlan(
        tool_call_id=tool_call_id,
        plan_content=plan_content,
        steps_json=steps_json
    )
    db.add(task_plan)
    await db.flush()
    await db.refresh(task_plan)
    return task_plan


async def get_task_plan_by_tool_call(
    db: AsyncSession,
    tool_call_id: int
) -> Optional[TaskPlan]:
    """获取工具调用的任务规划"""
    query = select(TaskPlan).where(TaskPlan.tool_call_id == tool_call_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()


# ==================== PPT 项目相关操作 ====================

async def create_ppt_project(
    db: AsyncSession,
    conversation_id: int,
    title: str,
    outline_content: Optional[str] = None
) -> PPTProject:
    """创建 PPT 项目"""
    project = PPTProject(
        conversation_id=conversation_id,
        title=title,
        outline_content=outline_content
    )
    db.add(project)
    await db.flush()
    await db.refresh(project)
    return project


async def get_ppt_project_by_conversation(
    db: AsyncSession,
    conversation_id: int
) -> Optional[PPTProject]:
    """获取对话关联的最新 PPT 项目（兼容旧逻辑）"""
    query = select(PPTProject).where(
        PPTProject.conversation_id == conversation_id
    ).options(
        selectinload(PPTProject.versions).selectinload(PPTVersion.slides)
    ).order_by(PPTProject.created_at.desc())
    result = await db.execute(query)
    return result.scalars().first()


async def get_ppt_projects_by_conversation(
    db: AsyncSession,
    conversation_id: int
) -> list:
    """获取对话下所有 PPT 项目列表（按创建时间升序）"""
    query = select(PPTProject).where(
        PPTProject.conversation_id == conversation_id
    ).options(
        selectinload(PPTProject.versions)
    ).order_by(PPTProject.created_at.asc())
    result = await db.execute(query)
    return list(result.scalars().all())


# ==================== PPT 版本相关操作 ====================

async def create_ppt_version(
    db: AsyncSession,
    project_id: int,
    version_number: int = 1,
    version_name: Optional[str] = None
) -> PPTVersion:
    """创建 PPT 版本"""
    # 将其他版本设为非当前
    await db.execute(
        update(PPTVersion).where(PPTVersion.project_id == project_id).values(is_current=False)
    )
    
    version = PPTVersion(
        project_id=project_id,
        version_number=version_number,
        version_name=version_name,
        is_current=True
    )
    db.add(version)
    await db.flush()
    await db.refresh(version)
    return version


async def create_ppt_sub_version(
    db: AsyncSession,
    project_id: int,
    parent_version_id: int,
    version_number: int,
    version_name: str,
) -> PPTVersion:
    """创建手动编辑子版本（不改变其他版本的 is_current 状态）"""
    version = PPTVersion(
        project_id=project_id,
        version_number=version_number,
        version_name=version_name,
        is_current=False,
        parent_version_id=parent_version_id,
    )
    db.add(version)
    await db.flush()
    await db.refresh(version)
    return version


async def get_current_ppt_version(
    db: AsyncSession,
    project_id: int
) -> Optional[PPTVersion]:
    """获取项目的当前版本"""
    query = select(PPTVersion).where(
        PPTVersion.project_id == project_id,
        PPTVersion.is_current == True
    ).options(selectinload(PPTVersion.slides))
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def get_ppt_version(
    db: AsyncSession,
    version_id: int
) -> Optional[PPTVersion]:
    """获取单个版本（按 ID）"""
    result = await db.execute(select(PPTVersion).where(PPTVersion.id == version_id))
    return result.scalar_one_or_none()


async def get_ppt_versions_by_project(
    db: AsyncSession,
    project_id: int
) -> List[PPTVersion]:
    """获取项目的所有版本"""
    query = select(PPTVersion).where(
        PPTVersion.project_id == project_id
    ).order_by(PPTVersion.version_number)
    result = await db.execute(query)
    return list(result.scalars().all())


# ==================== PPT 幻灯片相关操作 ====================

async def create_ppt_slide(
    db: AsyncSession,
    version_id: int,
    page_number: int,
    html_content: str,
    page_title: Optional[str] = None,
    editable_elements_json: Optional[Dict] = None
) -> PPTSlide:
    """创建幻灯片"""
    slide = PPTSlide(
        version_id=version_id,
        page_number=page_number,
        page_title=page_title,
        html_content=html_content,
        editable_elements_json=editable_elements_json
    )
    db.add(slide)
    await db.flush()
    await db.refresh(slide)
    return slide


async def create_ppt_slides_batch(
    db: AsyncSession,
    version_id: int,
    slides_data: List[Dict[str, Any]]
) -> List[PPTSlide]:
    """批量创建幻灯片"""
    slides = []
    for data in slides_data:
        slide = PPTSlide(
            version_id=version_id,
            page_number=data.get("page_number"),
            page_title=data.get("page_title"),
            html_content=data.get("html_content"),
            editable_elements_json=data.get("editable_elements_json")
        )
        db.add(slide)
        slides.append(slide)
    
    await db.flush()
    return slides


async def get_slides_by_version(
    db: AsyncSession,
    version_id: int
) -> List[PPTSlide]:
    """获取版本的所有幻灯片"""
    query = select(PPTSlide).where(
        PPTSlide.version_id == version_id
    ).order_by(PPTSlide.page_number)
    result = await db.execute(query)
    return list(result.scalars().all())


async def update_slide_content(
    db: AsyncSession,
    slide_id: int,
    html_content: str,
    editable_elements_json: Optional[Dict] = None
) -> bool:
    """更新幻灯片内容（用于编辑功能）"""
    values = {"html_content": html_content, "updated_at": datetime.utcnow()}
    if editable_elements_json is not None:
        values["editable_elements_json"] = editable_elements_json
    
    stmt = update(PPTSlide).where(PPTSlide.id == slide_id).values(**values)
    result = await db.execute(stmt)
    return result.rowcount > 0


# ==================== 补充的 CRUD 函数 ====================

async def get_conversations(
    db: AsyncSession,
    user_id: str = "default_user",
    skip: int = 0,
    limit: int = 50
) -> List[Conversation]:
    """获取用户的对话列表"""
    query = select(Conversation).where(
        Conversation.user_id == user_id
    ).order_by(desc(Conversation.updated_at)).offset(skip).limit(limit)
    result = await db.execute(query)
    return list(result.scalars().all())


async def update_conversation(
    db: AsyncSession,
    conversation_id: int,
    title: Optional[str] = None
) -> Optional[Conversation]:
    """更新对话"""
    conversation = await get_conversation(db, conversation_id)
    if not conversation:
        return None
    
    if title is not None:
        conversation.title = title
    conversation.updated_at = datetime.utcnow()
    
    await db.flush()
    await db.refresh(conversation)
    return conversation


async def get_messages(
    db: AsyncSession,
    conversation_id: int
) -> List[Message]:
    """获取对话的所有消息"""
    return await get_messages_by_conversation(db, conversation_id)


async def get_search_results_by_round(
    db: AsyncSession,
    search_round_id: int
) -> List[SearchResult]:
    """获取搜索轮次的所有结果"""
    query = select(SearchResult).where(
        SearchResult.search_round_id == search_round_id
    )
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_ppt_project(
    db: AsyncSession,
    project_id: int
) -> Optional[PPTProject]:
    """获取 PPT 项目"""
    query = select(PPTProject).where(PPTProject.id == project_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def get_ppt_projects(
    db: AsyncSession,
    user_id: str = "default_user",
    skip: int = 0,
    limit: int = 50
) -> List[PPTProject]:
    """获取用户的 PPT 项目列表"""
    # 通过 conversation 关联获取用户的项目
    query = select(PPTProject).join(
        Conversation, PPTProject.conversation_id == Conversation.id
    ).where(
        Conversation.user_id == user_id
    ).order_by(desc(PPTProject.updated_at)).offset(skip).limit(limit)
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_latest_ppt_version(
    db: AsyncSession,
    project_id: int
) -> Optional[PPTVersion]:
    """获取项目的最新版本"""
    query = select(PPTVersion).where(
        PPTVersion.project_id == project_id
    ).order_by(desc(PPTVersion.version_number)).limit(1)
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def get_ppt_versions(
    db: AsyncSession,
    project_id: int
) -> List[PPTVersion]:
    """获取项目的所有版本"""
    return await get_ppt_versions_by_project(db, project_id)


async def get_ppt_slides(
    db: AsyncSession,
    version_id: int
) -> List[PPTSlide]:
    """获取版本的所有幻灯片"""
    return await get_slides_by_version(db, version_id)


async def update_ppt_slide(
    db: AsyncSession,
    slide_id: int,
    html_content: Optional[str] = None,
    page_title: Optional[str] = None
) -> Optional[PPTSlide]:
    """更新幻灯片"""
    query = select(PPTSlide).where(PPTSlide.id == slide_id)
    result = await db.execute(query)
    slide = result.scalar_one_or_none()

    if not slide:
        return None

    if html_content is not None:
        slide.html_content = html_content
    if page_title is not None:
        slide.page_title = page_title
    slide.updated_at = datetime.utcnow()

    await db.flush()
    await db.refresh(slide)
    return slide


async def delete_ppt_slide_by_page(
    db: AsyncSession,
    version_id: int,
    page_number: int,
) -> bool:
    """按页码删除幻灯片"""
    query = select(PPTSlide).where(
        PPTSlide.version_id == version_id,
        PPTSlide.page_number == page_number,
    )
    result = await db.execute(query)
    slide = result.scalar_one_or_none()
    if not slide:
        return False
    await db.delete(slide)
    await db.flush()
    return True


async def delete_ppt_project(
    db: AsyncSession,
    project_id: int
) -> bool:
    """删除 PPT 项目"""
    stmt = delete(PPTProject).where(PPTProject.id == project_id)
    result = await db.execute(stmt)
    return result.rowcount > 0


# ==================== 搜索相关操作 ====================

async def search_conversations(
    db: AsyncSession,
    user_id: str = "default_user",
    query: str = "",
    limit: int = 20
) -> List[Conversation]:
    """搜索对话（按标题模糊匹配）"""
    stmt = select(Conversation).where(
        Conversation.user_id == user_id,
        Conversation.title.ilike(f"%{query}%")
    ).order_by(desc(Conversation.updated_at)).limit(limit)
    
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def search_ppt_projects(
    db: AsyncSession,
    user_id: str = "default_user",
    query: str = "",
    limit: int = 20
) -> List[PPTProject]:
    """搜索 PPT 项目（按标题模糊匹配）"""
    stmt = select(PPTProject).join(
        Conversation, PPTProject.conversation_id == Conversation.id
    ).where(
        Conversation.user_id == user_id,
        PPTProject.title.ilike(f"%{query}%")
    ).order_by(desc(PPTProject.updated_at)).limit(limit)
    
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_conversations(
    db: AsyncSession,
    user_id: str = "default_user",
    skip: int = 0,
    limit: int = 50
) -> List[Conversation]:
    """获取用户的对话列表"""
    stmt = select(Conversation).where(
        Conversation.user_id == user_id
    ).order_by(desc(Conversation.updated_at)).offset(skip).limit(limit)
    
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_messages(
    db: AsyncSession,
    conversation_id: int
) -> List[Message]:
    """获取对话的消息列表"""
    stmt = select(Message).where(
        Message.conversation_id == conversation_id
    ).order_by(Message.created_at)

    # 异步环境下避免懒加载附件
    stmt = stmt.options(selectinload(Message.attachments))
    
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_tool_calls_by_message(
    db: AsyncSession,
    message_id: int
) -> List[ToolCall]:
    """获取消息的工具调用列表"""
    stmt = select(ToolCall).where(
        ToolCall.message_id == message_id
    ).order_by(ToolCall.created_at)
    
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_search_rounds_by_tool_call(
    db: AsyncSession,
    tool_call_id: int
) -> List[SearchRound]:
    """获取工具调用的搜索轮次"""
    stmt = select(SearchRound).where(
        SearchRound.tool_call_id == tool_call_id
    ).order_by(SearchRound.round_number)
    
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_task_plan_by_tool_call(
    db: AsyncSession,
    tool_call_id: int
) -> Optional[TaskPlan]:
    """获取工具调用的任务计划"""
    stmt = select(TaskPlan).where(
        TaskPlan.tool_call_id == tool_call_id
    )
    
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def update_conversation(
    db: AsyncSession,
    conversation_id: int,
    title: Optional[str] = None
) -> Optional[Conversation]:
    """更新对话"""
    stmt = select(Conversation).where(Conversation.id == conversation_id)
    result = await db.execute(stmt)
    conversation = result.scalar_one_or_none()
    
    if not conversation:
        return None
    
    if title is not None:
        conversation.title = title
    conversation.updated_at = datetime.utcnow()
    
    await db.flush()
    await db.refresh(conversation)
    return conversation


# ==================== 分享相关操作 ====================

async def create_share(
    db: AsyncSession,
    share_id: str,
    conversation_id: int,
    expires_at: datetime
) -> Share:
    """创建分享链接"""
    share = Share(
        share_id=share_id,
        conversation_id=conversation_id,
        expires_at=expires_at
    )
    db.add(share)
    await db.flush()
    await db.refresh(share)
    logger.info(f"Created share: {share_id} for conversation {conversation_id}")
    return share


async def get_share_by_id(
    db: AsyncSession,
    share_id: str
) -> Optional[Share]:
    """根据share_id获取分享"""
    query = select(Share).where(Share.share_id == share_id)
    result = await db.execute(query)
    share = result.scalar_one_or_none()

    if share:
        # 检查是否过期
        if datetime.utcnow() > share.expires_at:
            logger.warning(f"Share expired: {share_id}")
            return None

        # 增加访问计数
        share.view_count += 1
        await db.flush()

    return share


async def delete_share(
    db: AsyncSession,
    share_id: str
) -> bool:
    """删除分享链接"""
    stmt = delete(Share).where(Share.share_id == share_id)
    result = await db.execute(stmt)
    return result.rowcount > 0


async def get_shares_by_conversation(
    db: AsyncSession,
    conversation_id: int
) -> List[Share]:
    """获取对话的所有分享链接"""
    query = select(Share).where(
        Share.conversation_id == conversation_id
    ).order_by(desc(Share.created_at))
    result = await db.execute(query)
    return list(result.scalars().all())


async def cleanup_expired_shares(
    db: AsyncSession
) -> int:
    """清理过期的分享链接"""
    stmt = delete(Share).where(Share.expires_at < datetime.utcnow())
    result = await db.execute(stmt)
    count = result.rowcount
    if count > 0:
        logger.info(f"Cleaned up {count} expired shares")
    return count


# ==================== Session 相关操作 ====================

async def create_session(
    db: AsyncSession,
    session_id: str,
    topic: str,
    conversation_id: Optional[int] = None,
    stage: str = "init",
    task_status: str = "idle"
) -> Session:
    """创建 session"""
    session = Session(
        id=session_id,
        topic=topic,
        conversation_id=conversation_id,
        stage=stage,
        task_status=task_status
    )
    db.add(session)
    await db.flush()
    await db.refresh(session)
    logger.info(f"Created session: {session_id}")
    return session


async def get_session(
    db: AsyncSession,
    session_id: str
) -> Optional[Session]:
    """获取 session"""
    query = select(Session).where(Session.id == session_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def update_session(
    db: AsyncSession,
    session_id: str,
    stage: Optional[str] = None,
    task_status: Optional[str] = None,
    topic: Optional[str] = None,
    conversation_id: Optional[int] = None,
    supplement_data: Optional[Dict[str, Any]] = None,
    search_results: Optional[List[Dict]] = None,
    outline_content: Optional[str] = None,
    deep_thinking_content: Optional[str] = None
) -> Optional[Session]:
    """更新 session 状态和数据"""
    values = {"updated_at": datetime.utcnow()}
    
    if stage is not None:
        values["stage"] = stage
    if task_status is not None:
        values["task_status"] = task_status
    if topic is not None:
        values["topic"] = topic
    if conversation_id is not None:
        values["conversation_id"] = conversation_id
    if supplement_data is not None:
        values["supplement_data"] = supplement_data
    if search_results is not None:
        values["search_results"] = search_results
    if outline_content is not None:
        values["outline_content"] = outline_content
    if deep_thinking_content is not None:
        values["deep_thinking_content"] = deep_thinking_content
    
    stmt = update(Session).where(Session.id == session_id).values(**values)
    result = await db.execute(stmt)
    
    if result.rowcount > 0:
        session = await get_session(db, session_id)
        
        # 同步更新 Conversation 的 task_status
        if session and session.conversation_id and task_status is not None:
            try:
                await db.execute(
                    update(Conversation)
                    .where(Conversation.id == session.conversation_id)
                    .values(task_status=task_status)
                )
                logger.info(f"Synced task_status '{task_status}' to conversation {session.conversation_id}")
            except Exception as e:
                logger.error(f"Failed to sync task_status to conversation: {e}")
                
        return session
    return None


async def delete_session(
    db: AsyncSession,
    session_id: str
) -> bool:
    """删除 session"""
    stmt = delete(Session).where(Session.id == session_id)
    result = await db.execute(stmt)
    return result.rowcount > 0


async def get_or_create_session(
    db: AsyncSession,
    session_id: str,
    topic: str,
    conversation_id: Optional[int] = None
) -> tuple[Session, bool]:
    """
    获取或创建 session
    
    返回: (session, is_new) - session 对象和是否新创建的标志
    """
    existing = await get_session(db, session_id)
    if existing:
        return existing, False
    
    new_session = await create_session(
        db, session_id, topic, conversation_id, stage="init"
    )
    return new_session, True


async def get_sessions_by_status(
    db: AsyncSession,
    task_status: str
) -> List[Session]:
    """获取指定任务状态的所有 session"""
    query = select(Session).where(Session.task_status == task_status)
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_session_by_conversation(
    db: AsyncSession,
    conversation_id: int
) -> Optional[Session]:
    """获取对话关联的 session"""
    query = select(Session).where(Session.conversation_id == conversation_id).order_by(Session.updated_at.desc())
    result = await db.execute(query)
    return result.scalars().first()


# ==================== Export Records ====================

async def get_ppt_export(
    db: AsyncSession,
    version_id: int,
    format: str
) -> Optional[PPTExport]:
    """获取指定版本+格式的最新导出记录"""
    query = select(PPTExport).where(
        PPTExport.version_id == version_id,
        PPTExport.format == format
    ).order_by(desc(PPTExport.created_at)).limit(1)
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def create_ppt_export(
    db: AsyncSession,
    project_id: int,
    version_id: int,
    format: str,
    file_path: str,
    filename: str,
    file_size: int = 0,
    file_data: bytes = None
) -> PPTExport:
    """创建导出记录（追加历史，不覆盖旧记录）"""
    export = PPTExport(
        project_id=project_id,
        version_id=version_id,
        format=format,
        file_path=file_path,
        filename=filename,
        file_size=file_size,
        file_data=file_data
    )
    db.add(export)
    await db.commit()
    await db.refresh(export)
    return export


async def delete_ppt_export(
    db: AsyncSession,
    version_id: int,
    format: str
) -> bool:
    """删除指定版本+格式的导出记录"""
    stmt = delete(PPTExport).where(
        PPTExport.version_id == version_id,
        PPTExport.format == format
    )
    result = await db.execute(stmt)
    return result.rowcount > 0


async def get_knowledge_document(
    db: AsyncSession,
    document_id: int
) -> Optional[KnowledgeDocument]:
    """获取知识库文档"""
    query = select(KnowledgeDocument).where(KnowledgeDocument.id == document_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()
