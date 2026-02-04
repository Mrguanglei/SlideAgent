"""
SlideAgent 数据库模型定义

表结构：
- conversations: 对话表
- messages: 消息表
- tool_calls: 工具调用表
- search_rounds: 搜索轮次表
- search_results: 搜索结果表
- task_plans: 任务规划表
- ppt_projects: PPT项目表
- ppt_versions: PPT版本表
- ppt_slides: 幻灯片表
- sessions: 会话状态表（PPT生成流程状态）
"""

from datetime import datetime
from typing import Optional, List
import uuid as uuid_lib
from sqlalchemy import (
    Column, Integer, BigInteger, String, Text, DateTime,
    ForeignKey, JSON, Boolean, Index, LargeBinary
)
from sqlalchemy.orm import relationship, DeclarativeBase
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    """SQLAlchemy 基类"""
    pass


class Conversation(Base):
    """对话表 - 存储对话会话"""
    __tablename__ = "conversations"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    uuid = Column(String(36), unique=True, nullable=False, index=True, default=lambda: str(uuid_lib.uuid4()))  # UUID 标识符
    user_id = Column(String(100), nullable=True, index=True, default="default_user")  # 用户 ID
    title = Column(String(255), nullable=False, default="新对话")
    task_status = Column(String(20), nullable=False, default="idle")  # idle, running, paused, completed (同步自 Session)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # 关系
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")
    ppt_projects = relationship("PPTProject", back_populates="conversation", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_conversation_user_updated", "user_id", "updated_at"),
        Index("idx_conversation_uuid", "uuid"),
    )


class Message(Base):
    """消息表 - 存储对话中的每条消息"""
    __tablename__ = "messages"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    conversation_id = Column(BigInteger, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # user, assistant, system
    content = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    
    # 关系
    conversation = relationship("Conversation", back_populates="messages")
    attachments = relationship("MessageAttachment", back_populates="message", cascade="all, delete-orphan")
    tool_calls = relationship("ToolCall", back_populates="message", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("idx_message_conversation_created", "conversation_id", "created_at"),
    )


class MessageAttachment(Base):
    """消息附件表 - 存储聊天中上传的文件"""
    __tablename__ = "message_attachments"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid_lib.uuid4()))
    message_id = Column(BigInteger, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(BigInteger, default=0)
    content_type = Column(String(100), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    # 关系
    message = relationship("Message", back_populates="attachments")


class ToolCall(Base):
    """工具调用表 - 记录所有工具调用，用于恢复状态"""
    __tablename__ = "tool_calls"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    message_id = Column(BigInteger, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, index=True)
    tool_type = Column(String(50), nullable=False)  # search, task_plan, ppt_generate, supplement_info, ppt_outline
    tool_name = Column(String(100), nullable=False)  # 显示名称
    status = Column(String(20), nullable=False, default="pending")  # pending, running, completed, failed
    arguments_json = Column(JSON, nullable=True)  # 工具调用参数
    result_json = Column(JSON, nullable=True)  # 工具返回结果
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    
    # 关系
    message = relationship("Message", back_populates="tool_calls")
    search_rounds = relationship("SearchRound", back_populates="tool_call", cascade="all, delete-orphan")
    task_plan = relationship("TaskPlan", back_populates="tool_call", uselist=False, cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("idx_tool_call_message_type", "message_id", "tool_type"),
    )


class SearchRound(Base):
    """搜索轮次表 - 分轮存储搜索"""
    __tablename__ = "search_rounds"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tool_call_id = Column(BigInteger, ForeignKey("tool_calls.id", ondelete="CASCADE"), nullable=False, index=True)
    round_number = Column(Integer, nullable=False, default=1)
    query = Column(String(500), nullable=False)
    thinking_content = Column(Text, nullable=True)  # 深度思考内容（最后一轮搜索后的整合分析）
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    # 关系
    tool_call = relationship("ToolCall", back_populates="search_rounds")
    search_results = relationship("SearchResult", back_populates="search_round", cascade="all, delete-orphan")


class SearchResult(Base):
    """搜索结果表 - 存储具体搜索结果"""
    __tablename__ = "search_results"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    search_round_id = Column(BigInteger, ForeignKey("search_rounds.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    url = Column(Text, nullable=True)
    content = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    
    # 关系
    search_round = relationship("SearchRound", back_populates="search_results")


class TaskPlan(Base):
    """任务规划表 - 存储任务执行规划"""
    __tablename__ = "task_plans"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tool_call_id = Column(BigInteger, ForeignKey("tool_calls.id", ondelete="CASCADE"), nullable=False, unique=True)
    plan_content = Column(Text, nullable=True)  # 规划文本内容
    steps_json = Column(JSON, nullable=True)  # 步骤列表 JSON
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    
    # 关系
    tool_call = relationship("ToolCall", back_populates="task_plan")


class PPTProject(Base):
    """PPT项目表 - 存储项目基本信息"""
    __tablename__ = "ppt_projects"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    conversation_id = Column(BigInteger, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    outline_content = Column(Text, nullable=True)  # PPT 大纲内容
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # 关系
    conversation = relationship("Conversation", back_populates="ppt_projects")
    versions = relationship("PPTVersion", back_populates="project", cascade="all, delete-orphan")


class PPTVersion(Base):
    """PPT版本表 - 支持 V1, V2... 版本管理"""
    __tablename__ = "ppt_versions"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    project_id = Column(BigInteger, ForeignKey("ppt_projects.id", ondelete="CASCADE"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False, default=1)
    version_name = Column(String(100), nullable=True)  # 如 "初稿", "修改版"
    is_current = Column(Boolean, default=True)  # 是否为当前版本
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    
    # 关系
    project = relationship("PPTProject", back_populates="versions")
    slides = relationship("PPTSlide", back_populates="version", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("idx_version_project_number", "project_id", "version_number"),
    )


class PPTSlide(Base):
    """幻灯片表 - 存储每页 HTML，支持编辑"""
    __tablename__ = "ppt_slides"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    version_id = Column(BigInteger, ForeignKey("ppt_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    page_number = Column(Integer, nullable=False)
    page_title = Column(String(255), nullable=True)  # 页面标题，如 "封面", "目录"
    html_content = Column(Text, nullable=False)  # 完整 HTML 源码
    editable_elements_json = Column(JSON, nullable=True)  # 可编辑元素 JSON（预留）
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # 关系
    version = relationship("PPTVersion", back_populates="slides")
    
    __table_args__ = (
        Index("idx_slide_version_page", "version_id", "page_number"),
    )


# ==================== 知识库相关表 ====================

class KnowledgeFolder(Base):
    """知识库文件夹表 - 支持文件夹组织"""
    __tablename__ = "knowledge_folders"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(String(100), nullable=True, index=True, default="default_user")
    name = Column(String(255), nullable=False)
    parent_id = Column(BigInteger, ForeignKey("knowledge_folders.id", ondelete="CASCADE"), nullable=True, index=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # 关系
    parent = relationship("KnowledgeFolder", remote_side=[id], backref="children")
    documents = relationship("KnowledgeDocument", back_populates="folder", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("idx_folder_user_parent", "user_id", "parent_id"),
    )


class KnowledgeDocument(Base):
    """
    知识库文档表 - 存储上传的文档信息
    
    支持的文件类型：
    - PDF, Word (doc/docx), Excel (xls/xlsx)
    - HTML, XML, TXT, Markdown
    - 网页链接 (URL)
    - 纯文本内容
    """
    __tablename__ = "knowledge_documents"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(String(100), nullable=True, index=True, default="default_user")
    folder_id = Column(BigInteger, ForeignKey("knowledge_folders.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # 文件基本信息
    filename = Column(String(255), nullable=False)  # 原始文件名
    display_name = Column(String(255), nullable=True)  # 显示名称（可重命名）
    file_type = Column(String(50), nullable=False)  # pdf, docx, xlsx, html, txt, md, url, text
    file_size = Column(BigInteger, nullable=True)  # 文件大小（字节）
    file_path = Column(String(500), nullable=True)  # 存储路径
    source_url = Column(Text, nullable=True)  # 如果是网页链接
    
    # 解析状态
    parse_status = Column(String(20), default="pending")  # pending, parsing, completed, failed
    parse_error = Column(Text, nullable=True)  # 解析错误信息
    parsed_at = Column(DateTime, nullable=True)  # 解析完成时间
    
    # 解析结果
    raw_content = Column(Text, nullable=True)  # 原始提取的文本内容
    chunk_count = Column(Integer, default=0)  # 分块数量
    
    # 元数据
    metadata_json = Column(JSON, nullable=True)  # 额外元数据（页数、作者等）
    
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # 关系
    folder = relationship("KnowledgeFolder", back_populates="documents")
    chunks = relationship("KnowledgeChunk", back_populates="document", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("idx_document_user_folder", "user_id", "folder_id"),
        Index("idx_document_status", "parse_status"),
    )


class KnowledgeChunk(Base):
    """
    知识库文本块表 - 存储分块后的文本

    使用 TokenTextSplitter 分块策略：
    - 按 token 数量分块（默认 512 tokens）
    - 保留重叠（默认 50 tokens）以保持上下文连贯性
    """
    __tablename__ = "knowledge_chunks"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    document_id = Column(BigInteger, ForeignKey("knowledge_documents.id", ondelete="CASCADE"), nullable=False, index=True)

    # 分块信息
    chunk_index = Column(Integer, nullable=False)  # 分块索引（0, 1, 2...）
    content = Column(Text, nullable=False)  # 分块文本内容
    token_count = Column(Integer, nullable=True)  # token 数量

    # 向量嵌入
    embedding_status = Column(String(20), default="pending")  # pending, processing, completed, failed
    embedding_vector = Column(JSON, nullable=True)  # 向量数据（JSON 数组）
    embedding_model = Column(String(100), nullable=True)  # 使用的嵌入模型

    # 元数据
    metadata_json = Column(JSON, nullable=True)  # 分块元数据（页码、段落等）

    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    # 关系
    document = relationship("KnowledgeDocument", back_populates="chunks")

    __table_args__ = (
        Index("idx_chunk_document_index", "document_id", "chunk_index"),
        Index("idx_chunk_embedding_status", "embedding_status"),
    )


# ==================== 分享相关表 ====================

class Share(Base):
    """分享表 - 存储 PPT 分享链接（包含完整对话历史）"""
    __tablename__ = "shares"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    share_id = Column(String(36), unique=True, nullable=False, index=True)  # 分享短 ID
    conversation_id = Column(BigInteger, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)

    # 统计信息
    view_count = Column(Integer, default=0, nullable=False)  # 查看次数

    # 时间信息
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    expires_at = Column(DateTime, nullable=False)  # 过期时间

    __table_args__ = (
        Index("idx_share_conversation", "conversation_id"),
        Index("idx_share_expires", "expires_at"),
    )


# ==================== 会话状态表 ====================

class Session(Base):
    """
    会话状态表 - 存储 PPT 生成流程的会话状态
    
    用于在后端重启后恢复用户的 PPT 生成进度，解决内存中 session 数据丢失的问题。
    
    stage 状态流转（流程阶段）：
    - init: 初始状态，检查 PPT 意图
    - supplement_info: 生成补充信息选项
    - waiting_supplement: 等待用户确认补充信息
    - confirmed: 用户已确认，进入任务规划
    - searching: 搜索网页信息
    - deep_thinking: 深度思考分析
    - outline: 生成 PPT 大纲
    - generating: 生成 PPT 幻灯片
    - completed: 生成完成
    
    task_status 任务状态：
    - idle: 空闲，等待用户输入
    - running: 正在执行 Agent 任务
    - paused: 用户暂停或意外中断
    - completed: 任务完成
    """
    __tablename__ = "sessions"

    id = Column(String(36), primary_key=True)  # UUID，与前端传递的 session_id 对应
    conversation_id = Column(BigInteger, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=True, index=True)
    topic = Column(Text, nullable=False)  # 用户输入的主题/指令
    stage = Column(String(50), nullable=False, default="init")
    task_status = Column(String(20), nullable=False, default="idle")  # idle, running, paused, completed
    supplement_data = Column(JSON, nullable=True)  # 用户确认的补充信息
    search_results = Column(JSON, nullable=True)  # 搜索结果（JSON 数组）
    outline_content = Column(Text, nullable=True)  # PPT 大纲内容
    deep_thinking_content = Column(Text, nullable=True)  # 深度思考内容
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # 关系
    conversation = relationship("Conversation", backref="sessions")

    __table_args__ = (
        Index("idx_session_conversation", "conversation_id"),
        Index("idx_session_stage", "stage"),
        Index("idx_session_task_status", "task_status"),
    )


class PPTExport(Base):
    """PPT 导出记录表 - 用于缓存导出文件"""
    __tablename__ = "ppt_exports"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    project_id = Column(BigInteger, ForeignKey("ppt_projects.id", ondelete="CASCADE"), nullable=False, index=True)
    version_id = Column(BigInteger, ForeignKey("ppt_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    format = Column(String(20), nullable=False)  # pdf, html, pptx, images
    file_path = Column(String(500), nullable=True)  # 改为可选，因为文件现在存储在数据库中
    filename = Column(String(255), nullable=False)
    file_size = Column(BigInteger, default=0)
    file_data = Column(LargeBinary, nullable=True)  # 存储文件的二进制数据
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("idx_export_version_format", "version_id", "format"),
    )

