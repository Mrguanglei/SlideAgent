"""
PPTAgent PPT 路由模块

提供 PPT 项目管理、版本管理、幻灯片编辑等 API
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

router = APIRouter(prefix="/api/ppt", tags=["ppt"])


# ==================== Pydantic Models ====================

class SlideUpdate(BaseModel):
    """更新幻灯片请求"""
    html_content: str
    page_title: Optional[str] = None


class PPTVersionCreate(BaseModel):
    """创建新版本请求"""
    project_id: int
    version_name: Optional[str] = None


class PPTProjectResponse(BaseModel):
    """PPT 项目响应"""
    id: int
    conversation_id: int
    title: str
    outline_content: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class PPTVersionResponse(BaseModel):
    """PPT 版本响应"""
    id: int
    project_id: int
    version_number: int
    version_name: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class SlideResponse(BaseModel):
    """幻灯片响应"""
    id: int
    version_id: int
    page_number: int
    page_title: Optional[str]
    html_content: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# ==================== API Endpoints ====================

@router.get("/projects", response_model=List[PPTProjectResponse])
async def list_ppt_projects(
    user_id: str = "default_user",
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """获取 PPT 项目列表（文件面板用）"""
    projects = await crud.get_ppt_projects(db, user_id=user_id, skip=skip, limit=limit)
    return projects


@router.get("/projects/{project_id}")
async def get_ppt_project(
    project_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取 PPT 项目详情（包含所有版本）"""
    project = await crud.get_ppt_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="PPT project not found")
    
    # 获取所有版本
    versions = await crud.get_ppt_versions(db, project_id)
    versions_list = []
    for v in versions:
        # 获取该版本的幻灯片
        slides = await crud.get_ppt_slides(db, v.id)
        versions_list.append({
            "id": v.id,
            "version_number": v.version_number,
            "version_name": v.version_name,
            "created_at": v.created_at.isoformat(),
            "slide_count": len(slides),
            "slides": [
                {
                    "id": s.id,
                    "page_number": s.page_number,
                    "page_title": s.page_title,
                    "html_content": s.html_content
                }
                for s in slides
            ]
        })
    
    return {
        "id": project.id,
        "conversation_id": project.conversation_id,
        "title": project.title,
        "outline_content": project.outline_content,
        "created_at": project.created_at.isoformat(),
        "updated_at": project.updated_at.isoformat(),
        "versions": versions_list
    }


@router.get("/projects/{project_id}/versions/{version_id}/slides")
async def get_slides(
    project_id: int,
    version_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取指定版本的所有幻灯片"""
    slides = await crud.get_ppt_slides(db, version_id)
    return [
        {
            "id": s.id,
            "page_number": s.page_number,
            "page_title": s.page_title,
            "html_content": s.html_content,
            "created_at": s.created_at.isoformat(),
            "updated_at": s.updated_at.isoformat()
        }
        for s in slides
    ]


@router.patch("/slides/{slide_id}")
async def update_slide(
    slide_id: int,
    request: SlideUpdate,
    db: AsyncSession = Depends(get_db)
):
    """更新单个幻灯片（编辑功能）"""
    slide = await crud.update_ppt_slide(
        db,
        slide_id,
        html_content=request.html_content,
        page_title=request.page_title
    )
    if not slide:
        raise HTTPException(status_code=404, detail="Slide not found")
    
    return {
        "id": slide.id,
        "page_number": slide.page_number,
        "page_title": slide.page_title,
        "html_content": slide.html_content,
        "updated_at": slide.updated_at.isoformat()
    }


@router.post("/projects/{project_id}/versions")
async def create_new_version(
    project_id: int,
    request: PPTVersionCreate,
    db: AsyncSession = Depends(get_db)
):
    """创建新版本（基于当前版本复制）"""
    # 获取项目
    project = await crud.get_ppt_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="PPT project not found")
    
    # 获取当前最新版本
    latest_version = await crud.get_latest_ppt_version(db, project_id)
    if not latest_version:
        raise HTTPException(status_code=400, detail="No existing version to copy from")
    
    # 创建新版本
    new_version_number = latest_version.version_number + 1
    version_name = request.version_name or f"V{new_version_number}"
    
    new_version = await crud.create_ppt_version(
        db,
        project_id=project_id,
        version_number=new_version_number,
        version_name=version_name
    )
    
    # 复制所有幻灯片到新版本
    old_slides = await crud.get_ppt_slides(db, latest_version.id)
    for slide in old_slides:
        await crud.create_ppt_slide(
            db,
            version_id=new_version.id,
            page_number=slide.page_number,
            page_title=slide.page_title,
            html_content=slide.html_content
        )
    
    return {
        "id": new_version.id,
        "version_number": new_version.version_number,
        "version_name": new_version.version_name,
        "created_at": new_version.created_at.isoformat(),
        "slide_count": len(old_slides)
    }


@router.delete("/projects/{project_id}")
async def delete_ppt_project(
    project_id: int,
    db: AsyncSession = Depends(get_db)
):
    """删除 PPT 项目"""
    success = await crud.delete_ppt_project(db, project_id)
    if not success:
        raise HTTPException(status_code=404, detail="PPT project not found")
    return {"status": "ok", "message": "PPT project deleted"}
