"""
PPTAgent 导出服务模块

支持将 PPT 导出为：
- PDF 文件
- PNG 图片（打包为 ZIP）
- PPTX 文件
"""

import os
import io
import uuid
import zipfile
import logging
import asyncio
from typing import List, Optional, Tuple
from pathlib import Path
from datetime import datetime

# PDF 生成
from weasyprint import HTML, CSS
from weasyprint.text.fonts import FontConfiguration

# 图片生成
from PIL import Image
from playwright.async_api import async_playwright

# PPTX 生成
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

logger = logging.getLogger(__name__)

# 导出文件存储目录
EXPORT_DIR = Path("/tmp/ppt_exports")
EXPORT_DIR.mkdir(parents=True, exist_ok=True)


class PPTExporter:
    """PPT 导出器"""
    
    def __init__(self):
        self.slide_width = 1280
        self.slide_height = 720
        
    async def export_to_pdf(
        self, 
        slides_html: List[str], 
        title: str = "presentation"
    ) -> Tuple[str, str]:
        """
        将 HTML 幻灯片导出为 PDF
        
        Args:
            slides_html: HTML 幻灯片列表
            title: 文件标题
            
        Returns:
            (文件路径, 文件名)
        """
        try:
            # 生成唯一文件名
            filename = f"{title}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            filepath = EXPORT_DIR / filename
            
            # 合并所有幻灯片为一个 HTML 文档
            combined_html = self._create_pdf_html(slides_html)
            
            # 使用 WeasyPrint 生成 PDF
            font_config = FontConfiguration()

            # 自定义 CSS 样式
            css = CSS(string='''
                @page {
                    size: 1280px 720px;
                    margin: 0;
                }
                body {
                    margin: 0;
                    padding: 0;
                }
                .slide-page {
                    width: 1280px;
                    height: 720px;
                    page-break-after: always;
                    overflow: hidden;
                }
                .slide-page:last-child {
                    page-break-after: auto;
                }
            ''')

            html = HTML(string=combined_html)
            html.write_pdf(str(filepath), stylesheets=[css], font_config=font_config)
            
            logger.info(f"PDF exported: {filepath}")
            return str(filepath), filename
            
        except Exception as e:
            logger.error(f"Failed to export PDF: {e}")
            raise
    
    def _create_pdf_html(self, slides_html: List[str]) -> str:
        """创建用于 PDF 导出的 HTML 文档"""
        slides_content = []
        
        for i, slide_html in enumerate(slides_html):
            # 提取 body 内容
            body_content = self._extract_body_content(slide_html)
            style_content = self._extract_style_content(slide_html)
            
            slides_content.append(f'''
                <div class="slide-page">
                    <style>{style_content}</style>
                    {body_content}
                </div>
            ''')
        
        return f'''
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@300;400;500;600;700&display=swap" rel="stylesheet">
            <style>
                * {{
                    box-sizing: border-box;
                    font-family: 'Noto Sans SC', 'Microsoft YaHei', sans-serif;
                }}
            </style>
        </head>
        <body>
            {''.join(slides_content)}
        </body>
        </html>
        '''
    
    def _extract_body_content(self, html: str) -> str:
        """从 HTML 中提取 body 内容"""
        import re
        body_match = re.search(r'<body[^>]*>(.*?)</body>', html, re.DOTALL | re.IGNORECASE)
        if body_match:
            return body_match.group(1)
        return html
    
    def _extract_style_content(self, html: str) -> str:
        """从 HTML 中提取 style 内容"""
        import re
        styles = []
        for match in re.finditer(r'<style[^>]*>(.*?)</style>', html, re.DOTALL | re.IGNORECASE):
            styles.append(match.group(1))
        return '\n'.join(styles)
    
    async def export_to_images(
        self, 
        slides_html: List[str], 
        title: str = "presentation",
        format: str = "png"
    ) -> Tuple[str, str]:
        """
        将 HTML 幻灯片导出为图片（打包为 ZIP）
        
        Args:
            slides_html: HTML 幻灯片列表
            title: 文件标题
            format: 图片格式 (png/jpg)
            
        Returns:
            (文件路径, 文件名)
        """
        try:
            # 生成唯一文件名
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            zip_filename = f"{title}_{timestamp}_images.zip"
            zip_filepath = EXPORT_DIR / zip_filename
            
            # 使用 Playwright 截图
            async with async_playwright() as p:
                browser = await p.chromium.launch()
                page = await browser.new_page(viewport={'width': self.slide_width, 'height': self.slide_height})
                
                # 创建 ZIP 文件
                with zipfile.ZipFile(zip_filepath, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for i, slide_html in enumerate(slides_html):
                        # 设置页面内容
                        await page.set_content(slide_html)
                        await page.wait_for_load_state('networkidle')
                        
                        # 截图
                        screenshot = await page.screenshot(type=format)
                        
                        # 添加到 ZIP
                        image_filename = f"slide_{i+1:02d}.{format}"
                        zipf.writestr(image_filename, screenshot)
                        
                        logger.info(f"Screenshot captured: {image_filename}")
                
                await browser.close()
            
            logger.info(f"Images exported: {zip_filepath}")
            return str(zip_filepath), zip_filename
            
        except Exception as e:
            logger.error(f"Failed to export images: {e}")
            raise
    
    async def export_to_pptx(
        self, 
        slides_html: List[str], 
        title: str = "presentation"
    ) -> Tuple[str, str]:
        """
        将 HTML 幻灯片导出为 PPTX
        
        注意：由于 HTML 到 PPTX 的转换复杂，这里采用截图方式
        将每页 HTML 渲染为图片后插入 PPTX
        
        Args:
            slides_html: HTML 幻灯片列表
            title: 文件标题
            
        Returns:
            (文件路径, 文件名)
        """
        try:
            # 生成唯一文件名
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            pptx_filename = f"{title}_{timestamp}.pptx"
            pptx_filepath = EXPORT_DIR / pptx_filename
            
            # 创建 PPTX
            prs = Presentation()
            
            # 设置幻灯片尺寸 (16:9)
            prs.slide_width = Inches(13.333)  # 1280px at 96dpi
            prs.slide_height = Inches(7.5)    # 720px at 96dpi
            
            # 使用 Playwright 截图并插入 PPTX
            async with async_playwright() as p:
                browser = await p.chromium.launch()
                page = await browser.new_page(viewport={'width': self.slide_width, 'height': self.slide_height})
                
                for i, slide_html in enumerate(slides_html):
                    # 设置页面内容
                    await page.set_content(slide_html)
                    await page.wait_for_load_state('networkidle')
                    
                    # 截图
                    screenshot_bytes = await page.screenshot(type='png')
                    
                    # 保存临时图片
                    temp_image_path = EXPORT_DIR / f"temp_slide_{i}.png"
                    with open(temp_image_path, 'wb') as f:
                        f.write(screenshot_bytes)
                    
                    # 添加空白幻灯片
                    blank_layout = prs.slide_layouts[6]  # 空白布局
                    slide = prs.slides.add_slide(blank_layout)
                    
                    # 插入图片（全屏）
                    slide.shapes.add_picture(
                        str(temp_image_path),
                        Inches(0), Inches(0),
                        width=prs.slide_width,
                        height=prs.slide_height
                    )
                    
                    # 删除临时图片
                    os.remove(temp_image_path)
                    
                    logger.info(f"Slide {i+1} added to PPTX")
                
                await browser.close()
            
            # 保存 PPTX
            prs.save(str(pptx_filepath))
            
            logger.info(f"PPTX exported: {pptx_filepath}")
            return str(pptx_filepath), pptx_filename
            
        except Exception as e:
            logger.error(f"Failed to export PPTX: {e}")
            raise


# 单例实例
exporter = PPTExporter()


async def export_ppt(
    slides_html: List[str],
    format: str,
    title: str = "presentation"
) -> Tuple[str, str]:
    """
    导出 PPT
    
    Args:
        slides_html: HTML 幻灯片列表
        format: 导出格式 (pdf/png/pptx)
        title: 文件标题
        
    Returns:
        (文件路径, 文件名)
    """
    if format == "pdf":
        return await exporter.export_to_pdf(slides_html, title)
    elif format in ["png", "jpg", "images"]:
        return await exporter.export_to_images(slides_html, title, "png")
    elif format == "pptx":
        return await exporter.export_to_pptx(slides_html, title)
    else:
        raise ValueError(f"Unsupported format: {format}")
