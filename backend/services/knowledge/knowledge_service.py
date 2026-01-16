"""
知识库主服务

整合文档解析、文本分块、LLM 处理和向量存储的完整流程。
"""

import os
import uuid
import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path

import aiofiles
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_

from database.models import (
    KnowledgeFolder, 
    KnowledgeDocument, 
    KnowledgeChunk
)
from .document_parser import DocumentParser
from .text_splitter import TokenTextSplitter
from .llm_processor import LLMProcessor, EmbeddingProcessor


# 文件存储目录
UPLOAD_DIR = os.getenv("KNOWLEDGE_UPLOAD_DIR", "/tmp/knowledge_uploads")


class KnowledgeService:
    """知识库服务 - 管理文档的完整生命周期"""
    
    def __init__(self, db: AsyncSession):
        """
        初始化知识库服务
        
        Args:
            db: 数据库会话
        """
        self.db = db
        self.parser = DocumentParser()
        self.splitter = TokenTextSplitter(chunk_size=512, chunk_overlap=50)
        self.llm_processor = LLMProcessor()
        self.embedding_processor = EmbeddingProcessor()
        
        # 确保上传目录存在
        os.makedirs(UPLOAD_DIR, exist_ok=True)
    
    async def close(self):
        """关闭资源"""
        await self.llm_processor.close()
        await self.embedding_processor.close()
    
    # ==================== 文件夹管理 ====================
    
    async def create_folder(
        self,
        name: str,
        parent_id: Optional[int] = None,
        user_id: str = "default_user"
    ) -> KnowledgeFolder:
        """创建文件夹"""
        # 检查同一目录下是否已存在同名文件夹
        existing = await self.db.execute(
            select(KnowledgeFolder).where(
                and_(
                    KnowledgeFolder.user_id == user_id,
                    KnowledgeFolder.parent_id == parent_id,
                    KnowledgeFolder.name == name
                )
            )
        )
        if existing.scalar_one_or_none():
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail=f"文件夹 '{name}' 已存在")

        folder = KnowledgeFolder(
            name=name,
            parent_id=parent_id,
            user_id=user_id,
        )
        self.db.add(folder)
        await self.db.commit()
        await self.db.refresh(folder)
        return folder
    
    async def get_folders(
        self, 
        parent_id: Optional[int] = None,
        user_id: str = "default_user"
    ) -> List[KnowledgeFolder]:
        """获取文件夹列表"""
        query = select(KnowledgeFolder).where(
            and_(
                KnowledgeFolder.user_id == user_id,
                KnowledgeFolder.parent_id == parent_id
            )
        ).order_by(KnowledgeFolder.created_at.desc())
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def rename_folder(self, folder_id: int, new_name: str) -> bool:
        """重命名文件夹"""
        await self.db.execute(
            update(KnowledgeFolder)
            .where(KnowledgeFolder.id == folder_id)
            .values(name=new_name, updated_at=datetime.utcnow())
        )
        await self.db.commit()
        return True
    
    async def delete_folder(self, folder_id: int) -> bool:
        """删除文件夹（级联删除子文件夹和文档）"""
        await self.db.execute(
            delete(KnowledgeFolder).where(KnowledgeFolder.id == folder_id)
        )
        await self.db.commit()
        return True
    
    # ==================== 文档上传 ====================
    
    async def upload_file(
        self,
        file_content: bytes,
        filename: str,
        user_id: str = "default_user",
        folder_id: Optional[int] = None,
    ) -> KnowledgeDocument:
        """
        上传文件
        
        Args:
            file_content: 文件内容
            filename: 原始文件名
            user_id: 用户 ID
            folder_id: 文件夹 ID
            
        Returns:
            创建的文档记录
        """
        # 检查文件类型
        file_type = DocumentParser.get_file_type(filename)
        if not file_type:
            raise ValueError(f"不支持的文件格式: {filename}")

        # 检查同一文件夹下是否已存在同名文件
        existing = await self.db.execute(
            select(KnowledgeDocument).where(
                and_(
                    KnowledgeDocument.user_id == user_id,
                    KnowledgeDocument.folder_id == folder_id,
                    KnowledgeDocument.filename == filename
                )
            )
        )
        if existing.scalar_one_or_none():
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail=f"文件 '{filename}' 已存在")

        # 生成存储路径
        file_id = str(uuid.uuid4())
        file_ext = Path(filename).suffix
        stored_filename = f"{file_id}{file_ext}"
        file_path = os.path.join(UPLOAD_DIR, stored_filename)
        
        # 保存文件
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(file_content)
        
        # 创建文档记录
        document = KnowledgeDocument(
            user_id=user_id,
            folder_id=folder_id,
            filename=filename,
            display_name=Path(filename).stem,
            file_type=file_type,
            file_size=len(file_content),
            file_path=file_path,
            parse_status="pending",
        )
        
        self.db.add(document)
        await self.db.commit()
        await self.db.refresh(document)
        
        return document
    
    async def upload_url(
        self,
        url: str,
        user_id: str = "default_user",
        folder_id: Optional[int] = None,
    ) -> KnowledgeDocument:
        """
        添加网页 URL
        
        Args:
            url: 网页 URL
            user_id: 用户 ID
            folder_id: 文件夹 ID
            
        Returns:
            创建的文档记录
        """
        # 从 URL 提取标题作为显示名称
        from urllib.parse import urlparse
        parsed = urlparse(url)
        display_name = parsed.netloc + parsed.path[:30]
        
        document = KnowledgeDocument(
            user_id=user_id,
            folder_id=folder_id,
            filename=url,
            display_name=display_name,
            file_type="url",
            source_url=url,
            parse_status="pending",
        )
        
        self.db.add(document)
        await self.db.commit()
        await self.db.refresh(document)
        
        return document
    
    async def upload_text(
        self,
        text: str,
        title: str = "文本内容",
        user_id: str = "default_user",
        folder_id: Optional[int] = None,
    ) -> KnowledgeDocument:
        """
        添加纯文本内容
        
        Args:
            text: 文本内容
            title: 标题
            user_id: 用户 ID
            folder_id: 文件夹 ID
            
        Returns:
            创建的文档记录
        """
        document = KnowledgeDocument(
            user_id=user_id,
            folder_id=folder_id,
            filename=f"{title}.txt",
            display_name=title,
            file_type="text",
            file_size=len(text.encode('utf-8')),
            raw_content=text,
            parse_status="pending",
        )
        
        self.db.add(document)
        await self.db.commit()
        await self.db.refresh(document)
        
        return document
    
    # ==================== 文档解析和处理 ====================
    
    async def process_document(self, document_id: int) -> KnowledgeDocument:
        """
        处理文档：解析 -> 清洗 -> 分块 -> 向量化
        
        Args:
            document_id: 文档 ID
            
        Returns:
            更新后的文档记录
        """
        # 获取文档
        result = await self.db.execute(
            select(KnowledgeDocument).where(KnowledgeDocument.id == document_id)
        )
        document = result.scalar_one_or_none()
        
        if not document:
            raise ValueError(f"文档不存在: {document_id}")
        
        try:
            # 更新状态为解析中
            document.parse_status = "parsing"
            await self.db.commit()
            
            # 1. 解析文档
            text, metadata = await self._parse_document(document)
            
            # 2. 数据清洗（可选，使用 LLM）
            # text = await self.llm_processor.clean_and_enhance_text(text)

            # 3. 文本分块
            chunks = self.splitter.split(text)

            # 4. 向量化
            chunk_dicts = [{"content": c.content, "index": c.index} for c in chunks]
            embedded_chunks = await self.embedding_processor.embed_chunks(chunk_dicts)

            # 5. 保存分块到数据库
            await self._save_chunks(document.id, embedded_chunks)

            # 6. 更新文档信息（先标记为已完成，让用户看到）
            document.raw_content = text
            document.chunk_count = len(chunks)
            document.parse_status = "completed"
            document.parsed_at = datetime.utcnow()
            document.metadata_json = {
                **metadata,
                "keywords": [],
                "summary": "",
            }

            await self.db.commit()
            await self.db.refresh(document)

            # 7. 异步生成关键字和摘要（不阻塞，后台执行）
            asyncio.create_task(self._generate_metadata_async(document.id, text))

            return document
            
        except Exception as e:
            # 更新状态为失败
            document.parse_status = "failed"
            document.parse_error = str(e)
            await self.db.commit()
            raise
    
    async def _parse_document(self, document: KnowledgeDocument) -> Tuple[str, Dict[str, Any]]:
        """解析文档内容"""
        if document.file_type == "url":
            return await self.parser.parse_url(document.source_url)
        elif document.file_type == "text":
            return await self.parser.parse_text_content(document.raw_content or "")
        elif document.file_path:
            return await self.parser.parse(document.file_path, document.file_type)
        else:
            raise ValueError("文档没有可解析的内容")
    
    async def _save_chunks(self, document_id: int, chunks: List[Dict[str, Any]]):
        """保存文本块到数据库"""
        # 先删除旧的分块
        await self.db.execute(
            delete(KnowledgeChunk).where(KnowledgeChunk.document_id == document_id)
        )
        
        # 保存新的分块
        for chunk in chunks:
            db_chunk = KnowledgeChunk(
                document_id=document_id,
                chunk_index=chunk.get("index", 0),
                content=chunk.get("content", ""),
                token_count=len(chunk.get("content", "").split()),  # 简单估算
                embedding_status="completed" if chunk.get("embedding") else "pending",
                embedding_vector=chunk.get("embedding"),
                embedding_model=self.embedding_processor.config.embedding_model,
            )
            self.db.add(db_chunk)

        await self.db.commit()

    async def _generate_metadata_async(self, document_id: int, text: str):
        """异步生成关键字和摘要（后台任务）"""
        # 创建新的数据库会话和处理器（因为是后台任务）
        from database.connection import async_session_factory

        async with async_session_factory() as new_db:
            try:
                # 创建新的 LLM 处理器
                llm_processor = LLMProcessor()

                # 生成关键字和摘要
                keywords = await llm_processor.extract_keywords(text)
                summary = await llm_processor.generate_summary(text)

                # 获取文档
                result = await new_db.execute(
                    select(KnowledgeDocument).where(KnowledgeDocument.id == document_id)
                )
                document = result.scalar_one_or_none()

                if document:
                    # 更新 metadata
                    current_metadata = document.metadata_json or {}
                    current_metadata["keywords"] = keywords
                    current_metadata["summary"] = summary

                    document.metadata_json = current_metadata
                    await new_db.commit()

                # 关闭处理器
                await llm_processor.close()

            except Exception as e:
                print(f"后台生成元数据失败 [document_id={document_id}]: {e}")

    # ==================== 文档管理 ====================
    
    async def get_documents(
        self,
        user_id: str = "default_user",
        folder_id: Optional[int] = None,
    ) -> List[KnowledgeDocument]:
        """获取文档列表"""
        query = select(KnowledgeDocument).where(
            and_(
                KnowledgeDocument.user_id == user_id,
                KnowledgeDocument.folder_id == folder_id
            )
        ).order_by(KnowledgeDocument.created_at.desc())
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def get_document(self, document_id: int) -> Optional[KnowledgeDocument]:
        """获取单个文档"""
        result = await self.db.execute(
            select(KnowledgeDocument).where(KnowledgeDocument.id == document_id)
        )
        return result.scalar_one_or_none()
    
    async def rename_document(self, document_id: int, new_name: str) -> bool:
        """重命名文档"""
        await self.db.execute(
            update(KnowledgeDocument)
            .where(KnowledgeDocument.id == document_id)
            .values(display_name=new_name, updated_at=datetime.utcnow())
        )
        await self.db.commit()
        return True
    
    async def move_document(self, document_id: int, folder_id: Optional[int]) -> bool:
        """移动文档到指定文件夹"""
        await self.db.execute(
            update(KnowledgeDocument)
            .where(KnowledgeDocument.id == document_id)
            .values(folder_id=folder_id, updated_at=datetime.utcnow())
        )
        await self.db.commit()
        return True
    
    async def delete_document(self, document_id: int) -> bool:
        """删除文档"""
        # 获取文档信息
        document = await self.get_document(document_id)
        if document and document.file_path:
            # 删除文件
            try:
                os.remove(document.file_path)
            except:
                pass
        
        # 删除数据库记录（级联删除分块）
        await self.db.execute(
            delete(KnowledgeDocument).where(KnowledgeDocument.id == document_id)
        )
        await self.db.commit()
        return True
    
    # ==================== 搜索和检索 ====================
    
    async def search_similar(
        self,
        query: str,
        user_id: str = "default_user",
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        搜索相似文档块
        
        Args:
            query: 查询文本
            user_id: 用户 ID
            top_k: 返回的最大结果数
            
        Returns:
            相似文档块列表
        """
        # 生成查询向量
        query_embedding = await self.embedding_processor.embed_text(query)
        
        if not query_embedding:
            return []
        
        # 获取用户的所有文档块
        query_stmt = (
            select(KnowledgeChunk, KnowledgeDocument)
            .join(KnowledgeDocument)
            .where(
                and_(
                    KnowledgeDocument.user_id == user_id,
                    KnowledgeChunk.embedding_status == "completed",
                    KnowledgeChunk.embedding_vector.isnot(None)
                )
            )
        )
        
        result = await self.db.execute(query_stmt)
        rows = result.all()
        
        # 计算相似度并排序
        similarities = []
        for chunk, document in rows:
            if chunk.embedding_vector:
                similarity = self._cosine_similarity(query_embedding, chunk.embedding_vector)
                similarities.append({
                    "chunk_id": chunk.id,
                    "document_id": document.id,
                    "document_name": document.display_name or document.filename,
                    "content": chunk.content,
                    "similarity": similarity,
                })
        
        # 按相似度排序
        similarities.sort(key=lambda x: x["similarity"], reverse=True)
        
        return similarities[:top_k]
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """计算余弦相似度"""
        if not vec1 or not vec2 or len(vec1) != len(vec2):
            return 0.0
        
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(b * b for b in vec2) ** 0.5
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
