"""
知识库 API 路由

提供知识库的 RESTful API 接口：
- 文件夹管理
- 文档上传和管理（支持批量上传）
- 文档解析和处理（任务队列）
- 相似度搜索
"""

import os
import asyncio
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from database.connection import get_db, async_session_factory
from services.knowledge import KnowledgeService, DocumentParser
from services.knowledge.task_queue import task_queue, TaskPriority


router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


# ==================== Pydantic 模型 ====================

class FolderCreate(BaseModel):
    """创建文件夹请求"""
    name: str
    parent_id: Optional[int] = None


class FolderRename(BaseModel):
    """重命名文件夹请求"""
    name: str


class FolderResponse(BaseModel):
    """文件夹响应"""
    id: int
    name: str
    parent_id: Optional[int]
    created_at: datetime
    
    class Config:
        from_attributes = True


class DocumentResponse(BaseModel):
    """文档响应"""
    id: int
    filename: str
    display_name: Optional[str]
    file_type: str
    file_size: Optional[int]
    parse_status: str
    parse_error: Optional[str]
    chunk_count: int
    keywords: Optional[List[str]] = None
    summary: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class DocumentRename(BaseModel):
    """重命名文档请求"""
    name: str


class DocumentMove(BaseModel):
    """移动文档请求"""
    folder_id: Optional[int] = None


class UrlUpload(BaseModel):
    """URL 上传请求"""
    url: str
    folder_id: Optional[int] = None


class TextUpload(BaseModel):
    """文本上传请求"""
    text: str
    title: str = "文本内容"
    folder_id: Optional[int] = None


class BatchUrlUpload(BaseModel):
    """批量 URL 上传请求"""
    urls: List[str]
    folder_id: Optional[int] = None


class SearchRequest(BaseModel):
    """搜索请求"""
    query: str
    top_k: int = 5


class SearchResult(BaseModel):
    """搜索结果"""
    chunk_id: int
    document_id: int
    document_name: str
    content: str
    similarity: float


class QueueStatusResponse(BaseModel):
    """队列状态响应"""
    pending: int
    processing: int
    total_tasks: int
    max_concurrent: int
    queues: dict
    processing_tasks: List[str]


class BatchUploadResponse(BaseModel):
    """批量上传响应"""
    success: bool
    uploaded_count: int
    documents: List[DocumentResponse]
    errors: List[dict] = []


# ==================== 文件夹 API ====================

@router.post("/folders", response_model=FolderResponse)
async def create_folder(
    data: FolderCreate,
    db: AsyncSession = Depends(get_db),
):
    """创建文件夹"""
    service = KnowledgeService(db)
    try:
        folder = await service.create_folder(
            name=data.name,
            parent_id=data.parent_id,
        )
        return folder
    finally:
        await service.close()


@router.get("/folders", response_model=List[FolderResponse])
async def list_folders(
    parent_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    """获取文件夹列表"""
    service = KnowledgeService(db)
    try:
        folders = await service.get_folders(parent_id=parent_id)
        return folders
    finally:
        await service.close()


@router.put("/folders/{folder_id}")
async def rename_folder(
    folder_id: int,
    data: FolderRename,
    db: AsyncSession = Depends(get_db),
):
    """重命名文件夹"""
    service = KnowledgeService(db)
    try:
        await service.rename_folder(folder_id, data.name)
        return {"success": True}
    finally:
        await service.close()


@router.delete("/folders/{folder_id}")
async def delete_folder(
    folder_id: int,
    db: AsyncSession = Depends(get_db),
):
    """删除文件夹"""
    service = KnowledgeService(db)
    try:
        await service.delete_folder(folder_id)
        return {"success": True}
    finally:
        await service.close()


# ==================== 文档上传 API ====================

@router.post("/documents/upload", response_model=DocumentResponse)
async def upload_file(
    file: UploadFile = File(...),
    folder_id: Optional[int] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    """上传单个文件"""
    # 检查文件类型
    if not DocumentParser.is_supported(file.filename):
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式: {file.filename}"
        )
    
    # 读取文件内容
    content = await file.read()
    
    service = KnowledgeService(db)
    try:
        document = await service.upload_file(
            file_content=content,
            filename=file.filename,
            folder_id=folder_id,
        )
        
        # 添加到任务队列
        await task_queue.add_task(document.id, TaskPriority.NORMAL)
        
        return _document_to_response(document)
    finally:
        await service.close()


@router.post("/documents/upload-batch", response_model=BatchUploadResponse)
async def upload_files_batch(
    files: List[UploadFile] = File(...),
    folder_id: Optional[int] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    """批量上传文件"""
    uploaded_docs = []
    errors = []
    
    service = KnowledgeService(db)
    try:
        for file in files:
            try:
                # 检查文件类型
                if not DocumentParser.is_supported(file.filename):
                    errors.append({
                        "filename": file.filename,
                        "error": f"不支持的文件格式"
                    })
                    continue
                
                # 读取文件内容
                content = await file.read()
                
                # 上传文件
                document = await service.upload_file(
                    file_content=content,
                    filename=file.filename,
                    folder_id=folder_id,
                )
                
                # 添加到任务队列
                await task_queue.add_task(document.id, TaskPriority.NORMAL)
                
                uploaded_docs.append(_document_to_response(document))
                
            except Exception as e:
                errors.append({
                    "filename": file.filename,
                    "error": str(e)
                })
        
        return BatchUploadResponse(
            success=len(uploaded_docs) > 0,
            uploaded_count=len(uploaded_docs),
            documents=uploaded_docs,
            errors=errors,
        )
    finally:
        await service.close()


@router.post("/documents/url", response_model=DocumentResponse)
async def upload_url(
    data: UrlUpload,
    db: AsyncSession = Depends(get_db),
):
    """添加网页 URL"""
    service = KnowledgeService(db)
    try:
        document = await service.upload_url(
            url=data.url,
            folder_id=data.folder_id,
        )
        
        # 添加到任务队列
        await task_queue.add_task(document.id, TaskPriority.NORMAL)
        
        return _document_to_response(document)
    finally:
        await service.close()


@router.post("/documents/url-batch", response_model=BatchUploadResponse)
async def upload_urls_batch(
    data: BatchUrlUpload,
    db: AsyncSession = Depends(get_db),
):
    """批量添加网页 URL"""
    uploaded_docs = []
    errors = []
    
    service = KnowledgeService(db)
    try:
        for url in data.urls:
            try:
                document = await service.upload_url(
                    url=url,
                    folder_id=data.folder_id,
                )
                
                # 添加到任务队列
                await task_queue.add_task(document.id, TaskPriority.NORMAL)
                
                uploaded_docs.append(_document_to_response(document))
                
            except Exception as e:
                errors.append({
                    "url": url,
                    "error": str(e)
                })
        
        return BatchUploadResponse(
            success=len(uploaded_docs) > 0,
            uploaded_count=len(uploaded_docs),
            documents=uploaded_docs,
            errors=errors,
        )
    finally:
        await service.close()


@router.post("/documents/text", response_model=DocumentResponse)
async def upload_text(
    data: TextUpload,
    db: AsyncSession = Depends(get_db),
):
    """添加纯文本内容"""
    service = KnowledgeService(db)
    try:
        document = await service.upload_text(
            text=data.text,
            title=data.title,
            folder_id=data.folder_id,
        )
        
        # 添加到任务队列
        await task_queue.add_task(document.id, TaskPriority.NORMAL)
        
        return _document_to_response(document)
    finally:
        await service.close()


# ==================== 文档管理 API ====================

@router.get("/documents", response_model=List[DocumentResponse])
async def list_documents(
    folder_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    """获取文档列表"""
    service = KnowledgeService(db)
    try:
        documents = await service.get_documents(folder_id=folder_id)
        return [_document_to_response(doc) for doc in documents]
    finally:
        await service.close()


@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
):
    """获取单个文档"""
    service = KnowledgeService(db)
    try:
        document = await service.get_document(document_id)
        if not document:
            raise HTTPException(status_code=404, detail="文档不存在")
        return _document_to_response(document)
    finally:
        await service.close()


@router.put("/documents/{document_id}/rename")
async def rename_document(
    document_id: int,
    data: DocumentRename,
    db: AsyncSession = Depends(get_db),
):
    """重命名文档"""
    service = KnowledgeService(db)
    try:
        await service.rename_document(document_id, data.name)
        return {"success": True}
    finally:
        await service.close()


@router.put("/documents/{document_id}/move")
async def move_document(
    document_id: int,
    data: DocumentMove,
    db: AsyncSession = Depends(get_db),
):
    """移动文档"""
    service = KnowledgeService(db)
    try:
        await service.move_document(document_id, data.folder_id)
        return {"success": True}
    finally:
        await service.close()


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
):
    """删除文档"""
    service = KnowledgeService(db)
    try:
        await service.delete_document(document_id)
        return {"success": True}
    finally:
        await service.close()


@router.get("/documents/{document_id}/download")
async def download_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
):
    """下载文档"""
    service = KnowledgeService(db)
    try:
        document = await service.get_document(document_id)
        if not document:
            raise HTTPException(status_code=404, detail="文档不存在")
        
        if not document.file_path or not os.path.exists(document.file_path):
            raise HTTPException(status_code=404, detail="文件不存在")
        
        return FileResponse(
            document.file_path,
            filename=document.filename,
            media_type="application/octet-stream",
        )
    finally:
        await service.close()


@router.post("/documents/{document_id}/reprocess")
async def reprocess_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
):
    """重新处理文档"""
    service = KnowledgeService(db)
    try:
        document = await service.get_document(document_id)
        if not document:
            raise HTTPException(status_code=404, detail="文档不存在")
        
        # 添加到任务队列（高优先级）
        await task_queue.add_task(document_id, TaskPriority.HIGH)
        
        return {"success": True, "message": "已加入处理队列"}
    finally:
        await service.close()


# ==================== 任务队列 API ====================

@router.get("/queue/status", response_model=QueueStatusResponse)
async def get_queue_status():
    """获取任务队列状态"""
    return task_queue.get_queue_status()


@router.get("/queue/tasks")
async def get_queue_tasks():
    """获取所有任务状态"""
    return task_queue.get_all_tasks()


# ==================== 搜索 API ====================

@router.post("/search", response_model=List[SearchResult])
async def search_documents(
    data: SearchRequest,
    db: AsyncSession = Depends(get_db),
):
    """搜索相似文档"""
    service = KnowledgeService(db)
    try:
        results = await service.search_similar(
            query=data.query,
            top_k=data.top_k,
        )
        return results
    finally:
        await service.close()


# ==================== 支持的格式 API ====================

@router.get("/formats")
async def get_supported_formats():
    """获取支持的文件格式"""
    return {
        "formats": DocumentParser.SUPPORTED_EXTENSIONS,
        "max_file_size": 50 * 1024 * 1024,  # 50MB
        "max_batch_size": 20,  # 单次最多上传 20 个文件
    }


# ==================== 辅助函数 ====================

def _document_to_response(document) -> DocumentResponse:
    """将文档模型转换为响应"""
    metadata = document.metadata_json or {}
    return DocumentResponse(
        id=document.id,
        filename=document.filename,
        display_name=document.display_name,
        file_type=document.file_type,
        file_size=document.file_size,
        parse_status=document.parse_status,
        parse_error=document.parse_error,
        chunk_count=document.chunk_count or 0,
        keywords=metadata.get("keywords"),
        summary=metadata.get("summary"),
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


async def process_document_task(document_id: int):
    """后台任务：处理文档（被任务队列调用）"""
    async with async_session_factory() as db:
        service = KnowledgeService(db)
        try:
            await service.process_document(document_id)
        except Exception as e:
            print(f"文档处理失败 [{document_id}]: {e}")
            raise
        finally:
            await service.close()


# 初始化任务队列处理器
async def init_knowledge_queue():
    """初始化知识库任务队列"""
    from services.knowledge.task_queue import init_task_queue
    await init_task_queue(process_document_task)
