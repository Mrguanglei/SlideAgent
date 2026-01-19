"""
PPTAgent 导出和分享路由模块

提供 PPT 导出（PDF/图片/PPTX）和分享链接 API
"""

import os
import logging
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, Response
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from database.connection import get_db
from database import crud
from services.export import export_ppt, pre_export_check, generate_export_report
from services.share import create_share, get_share, delete_share, get_conversation_shares

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ppt", tags=["export"])


# ==================== Pydantic Models ====================

class ExportRequest(BaseModel):
    """导出请求"""
    project_id: int
    version_id: Optional[int] = None  # 不指定则使用最新版本
    format: str  # pdf, png, pptx


class ExportReportRequest(BaseModel):
    """导出报告请求"""
    project_id: int
    version_id: Optional[int] = None
    format: str
    output_path: str


class ShareRequest(BaseModel):
    """分享请求"""
    project_id: int  # 保留用于获取conversation_id
    expire_days: Optional[int] = 7


class ShareResponse(BaseModel):
    """分享响应"""
    share_id: str
    share_url: str
    expires_at: str
    expire_days: int


# ==================== 导出 API ====================

@router.post("/export")
async def export_ppt_file(
    request: ExportRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    导出 PPT 文件
    
    支持格式：
    - pdf: 导出为 PDF 文件
    - png/images: 导出为图片（ZIP 打包）
    - pptx: 导出为 PowerPoint 文件
    """
    try:
        # 获取项目
        project = await crud.get_ppt_project(db, request.project_id)
        if not project:
            raise HTTPException(status_code=404, detail="PPT project not found")
        
        # 获取版本
        if request.version_id:
            versions = await crud.get_ppt_versions(db, request.project_id)
            version = next((v for v in versions if v.id == request.version_id), None)
            if not version:
                raise HTTPException(status_code=404, detail="PPT version not found")
        else:
            version = await crud.get_latest_ppt_version(db, request.project_id)
            if not version:
                raise HTTPException(status_code=404, detail="No version found")
        
        # 获取幻灯片
        slides = await crud.get_ppt_slides(db, version.id)
        if not slides:
            raise HTTPException(status_code=404, detail="No slides found")
        
        # 提取 HTML 内容
        slides_html = [slide.html_content for slide in sorted(slides, key=lambda s: s.page_number)]
        
        # 清理标题（用于文件名）- 只保留ASCII字符避免编码问题
        import re
        from urllib.parse import quote
        
        # 移除所有非-ASCII字符，只保留英文字母、数字、空格、连字符和下划线
        safe_title = re.sub(r'[^a-zA-Z0-9\s\-_]', '', project.title).strip()
        # 将多个空格替换为单个下划线
        safe_title = re.sub(r'\s+', '_', safe_title)
        safe_title = safe_title[:50] or "presentation"
        
        # 导出
        filepath, filename = await export_ppt(slides_html, request.format, safe_title)
        
        # 返回文件下载
        media_type_map = {
            "pdf": "application/pdf",
            "html": "text/html",
            "png": "application/zip",
            "images": "application/zip",
            "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        }
        
        return FileResponse(
            filepath,
            media_type=media_type_map.get(request.format, "application/octet-stream"),
            filename=filename
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Export failed: {e}")
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@router.get("/export/formats")
async def get_export_formats():
    """获取支持的导出格式"""
    return {
        "formats": [
            {"id": "pdf", "name": "PDF 文档", "extension": ".pdf", "description": "适合打印和分享"},
            {"id": "html", "name": "HTML 网页", "extension": ".html", "description": "可以在浏览器中查看"},
             # png 移除，因为用户说先不处理图片
            {"id": "pptx", "name": "PowerPoint", "extension": ".pptx", "description": "可在 Office 中编辑"}
        ]
    }


@router.post("/export/pre-check")
async def api_pre_export_check(
    request: ExportRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    导出前预检
    
    检查 HTML 是否符合导出要求，提前发现潜在问题。
    
    返回：
    - passed: 是否通过验证
    - issues: 严重问题列表
    - warnings: 警告信息列表
    - external_resources: 外部资源列表
    """
    try:
        # 获取项目
        project = await crud.get_ppt_project(db, request.project_id)
        if not project:
            raise HTTPException(status_code=404, detail="PPT project not found")
        
        # 获取版本
        if request.version_id:
            versions = await crud.get_ppt_versions(db, request.project_id)
            version = next((v for v in versions if v.id == request.version_id), None)
            if not version:
                raise HTTPException(status_code=404, detail="PPT version not found")
        else:
            version = await crud.get_latest_ppt_version(db, request.project_id)
            if not version:
                raise HTTPException(status_code=404, detail="No version found")
        
        # 获取幻灯片
        slides = await crud.get_ppt_slides(db, version.id)
        if not slides:
            raise HTTPException(status_code=404, detail="No slides found")
        
        # 提取 HTML 内容
        slides_html = [slide.html_content for slide in sorted(slides, key=lambda s: s.page_number)]
        
        # 执行预检
        result = await pre_export_check(slides_html)
        
        return {
            "success": True,
            "result": result
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Pre-export check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Pre-export check failed: {str(e)}")


class ExportReportRequest(BaseModel):
    """导出报告请求"""
    project_id: int
    version_id: Optional[int] = None
    format: str
    output_path: str


@router.post("/export/report")
async def api_export_report(
    request: ExportReportRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    获取导出质量报告
    
    在导出后调用，评估导出质量。
    
    返回：
    - quality_score: 质量分数 (0-1)
    - issues: 严重问题列表
    - warnings: 警告信息列表
    - file_size: 文件大小
    - slides_count: 幻灯片数量
    """
    try:
        # 获取项目
        project = await crud.get_ppt_project(db, request.project_id)
        if not project:
            raise HTTPException(status_code=404, detail="PPT project not found")
        
        # 获取版本
        if request.version_id:
            versions = await crud.get_ppt_versions(db, request.project_id)
            version = next((v for v in versions if v.id == request.version_id), None)
            if not version:
                raise HTTPException(status_code=404, detail="PPT version not found")
        else:
            version = await crud.get_latest_ppt_version(db, request.project_id)
            if not version:
                raise HTTPException(status_code=404, detail="No version found")
        
        # 获取幻灯片
        slides = await crud.get_ppt_slides(db, version.id)
        if not slides:
            raise HTTPException(status_code=404, detail="No slides found")
        
        # 提取 HTML 内容
        slides_html = [slide.html_content for slide in sorted(slides, key=lambda s: s.page_number)]
        
        # 检查输出文件是否存在
        if not os.path.exists(request.output_path):
            raise HTTPException(status_code=404, detail="Output file not found")
        
        # 生成报告
        report = await generate_export_report(
            slides_html=slides_html,
            export_format=request.format,
            output_path=request.output_path
        )
        
        return {
            "success": True,
            "report": report
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Generate export report failed: {e}")
        raise HTTPException(status_code=500, detail=f"Generate export report failed: {str(e)}")


# ==================== 分享 API ====================

@router.post("/share", response_model=ShareResponse)
async def create_share_link(
    request: ShareRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    创建分享链接（分享完整对话历史）

    分享链接包含：
    - 用户原始输入
    - AI 思考过程
    - 搜索结果
    - 任务规划
    - PPT 大纲
    - 最终生成的 PPT
    """
    try:
        # 获取项目
        project = await crud.get_ppt_project(db, request.project_id)
        if not project:
            raise HTTPException(status_code=404, detail="PPT project not found")

        # 获取对话 ID
        conversation_id = project.conversation_id

        # 创建分享（只需要 conversation_id 和过期天数）
        share_info = await create_share(
            db,
            conversation_id=conversation_id,
            expire_days=request.expire_days
        )

        # 构建分享 URL（前端路由）
        share_url = f"/share/{share_info['share_id']}"

        return ShareResponse(
            share_id=share_info["share_id"],
            share_url=share_url,
            expires_at=share_info["expires_at"],
            expire_days=share_info["expire_days"]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create share failed: {e}")
        raise HTTPException(status_code=500, detail=f"Create share failed: {str(e)}")


@router.get("/share/{share_id}")
async def get_share_data(share_id: str, db: AsyncSession = Depends(get_db)):
    """
    获取分享数据（返回完整对话历史）

    返回数据包含：
    - conversation: 对话基本信息
    - messages: 所有消息（包含工具调用）
    - ppt_project: PPT 项目和幻灯片
    - share_info: 分享信息（访问次数、创建时间等）
    """
    share_data = await get_share(db, share_id)

    if not share_data:
        raise HTTPException(status_code=404, detail="Share not found or expired")

    return share_data


@router.delete("/share/{share_id}")
async def delete_share_link(share_id: str, db: AsyncSession = Depends(get_db)):
    """删除分享链接"""
    success = await delete_share(db, share_id)
    if not success:
        raise HTTPException(status_code=404, detail="Share not found")
    return {"status": "ok", "message": "Share deleted"}


@router.get("/projects/{project_id}/shares")
async def get_project_share_links(project_id: int, db: AsyncSession = Depends(get_db)):
    """获取项目的所有分享链接"""
    # 获取项目以获得 conversation_id
    project = await crud.get_ppt_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="PPT project not found")

    # 通过 conversation_id 获取分享链接
    shares = await get_conversation_shares(db, project.conversation_id)
    return {"shares": shares}


# ==================== 分享页面 ====================

@router.get("/view/{share_id}", response_class=HTMLResponse)
async def view_shared_ppt(share_id: str, db: AsyncSession = Depends(get_db)):
    """
    查看分享的 PPT（独立页面）

    这是一个独立的 HTML 页面，可以直接在浏览器中查看
    注意：这个页面只显示 PPT 幻灯片，不显示完整对话历史
    完整对话历史请使用前端 ShareView 组件
    """
    share_data = await get_share(db, share_id)

    if not share_data:
        return HTMLResponse(
            content="""
            <!DOCTYPE html>
            <html>
            <head>
                <title>分享链接已失效</title>
                <meta charset="UTF-8">
                <style>
                    body {
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        height: 100vh;
                        margin: 0;
                        background: #f5f5f5;
                    }
                    .error {
                        text-align: center;
                        padding: 40px;
                        background: white;
                        border-radius: 12px;
                        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                    }
                    h1 { color: #333; margin-bottom: 10px; }
                    p { color: #666; }
                </style>
            </head>
            <body>
                <div class="error">
                    <h1>😔 分享链接已失效</h1>
                    <p>该链接可能已过期或被删除</p>
                </div>
            </body>
            </html>
            """,
            status_code=404
        )

    # 从新的数据格式中提取幻灯片和标题
    ppt_project = share_data.get("ppt_project")
    if not ppt_project or not ppt_project.get("slides"):
        return HTMLResponse(
            content="""
            <!DOCTYPE html>
            <html>
            <head>
                <title>PPT 不存在</title>
                <meta charset="UTF-8">
                <style>
                    body {
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        height: 100vh;
                        margin: 0;
                        background: #f5f5f5;
                    }
                    .error {
                        text-align: center;
                        padding: 40px;
                        background: white;
                        border-radius: 12px;
                        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                    }
                    h1 { color: #333; margin-bottom: 10px; }
                    p { color: #666; }
                </style>
            </head>
            <body>
                <div class="error">
                    <h1>😔 PPT 不存在</h1>
                    <p>该分享链接没有关联的 PPT 项目</p>
                </div>
            </body>
            </html>
            """,
            status_code=404
        )

    title = ppt_project.get("title", "未命名 PPT")
    slides = ppt_project.get("slides", [])
    slides_html = [slide["html_content"] for slide in sorted(slides, key=lambda s: s["page_number"])]

    # 构建幻灯片 HTML
    slides_frames = []
    for i, slide in enumerate(slides_html):
        # 转义 HTML 用于 srcdoc
        escaped_slide = slide.replace('"', '&quot;').replace("'", "&#39;")
        slides_frames.append(f'''
            <div class="slide-container" id="slide-{i}">
                <div class="slide-number">第 {i+1} 页 / 共 {len(slides_html)} 页</div>
                <div class="slide-wrapper">
                    <iframe srcdoc="{escaped_slide}" scrolling="no"></iframe>
                </div>
            </div>
        ''')
    
    return HTMLResponse(content=f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>{title} - PPTAgent 分享</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            * {{
                box-sizing: border-box;
                margin: 0;
                padding: 0;
            }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: #1a1a1a;
                color: white;
                min-height: 100vh;
            }}
            .header {{
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                height: 60px;
                background: rgba(0,0,0,0.8);
                backdrop-filter: blur(10px);
                display: flex;
                align-items: center;
                justify-content: space-between;
                padding: 0 24px;
                z-index: 100;
            }}
            .header h1 {{
                font-size: 18px;
                font-weight: 500;
            }}
            .header .info {{
                font-size: 14px;
                color: #888;
            }}
            .slides-container {{
                padding: 80px 24px 24px;
                max-width: 1000px;
                margin: 0 auto;
            }}
            .slide-container {{
                margin-bottom: 32px;
            }}
            .slide-number {{
                font-size: 12px;
                color: #666;
                margin-bottom: 8px;
            }}
            .slide-wrapper {{
                position: relative;
                width: 100%;
                padding-top: 56.25%; /* 16:9 */
                background: white;
                border-radius: 8px;
                overflow: hidden;
                box-shadow: 0 4px 20px rgba(0,0,0,0.3);
            }}
            .slide-wrapper iframe {{
                position: absolute;
                top: 0;
                left: 0;
                width: 1280px;
                height: 720px;
                border: none;
                transform-origin: top left;
                transform: scale(calc(100% / 1280 * var(--container-width, 952)));
            }}
            @media (max-width: 768px) {{
                .slides-container {{
                    padding: 70px 16px 16px;
                }}
                .header {{
                    padding: 0 16px;
                }}
                .header h1 {{
                    font-size: 14px;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>{title}</h1>
            <div class="info">由 PPTAgent 生成</div>
        </div>
        <div class="slides-container">
            {''.join(slides_frames)}
        </div>
        <script>
            // 计算缩放比例
            function updateScale() {{
                const containers = document.querySelectorAll('.slide-wrapper');
                containers.forEach(container => {{
                    const width = container.offsetWidth;
                    const scale = width / 1280;
                    const iframe = container.querySelector('iframe');
                    if (iframe) {{
                        iframe.style.transform = `scale(${{scale}})`;
                    }}
                    container.style.paddingTop = `${{720 * scale}}px`;
                }});
            }}
            window.addEventListener('load', updateScale);
            window.addEventListener('resize', updateScale);
        </script>
    </body>
    </html>
    ''')
