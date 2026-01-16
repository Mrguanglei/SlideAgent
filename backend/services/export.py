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


def sanitize_html_for_pptx(html: str) -> str:
    """
    清理 HTML 以符合 html2pptx 的要求

    html2pptx 要求所有文本必须包装在 <p>, <h1>-<h6>, <ul>, 或 <ol> 标签中
    这个函数会将 DIV 中的裸文本包装在 <p> 标签中
    同时确保内容不会溢出并保持适当的底部边距
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, 'html.parser')

    # 查找所有可能包含裸文本的元素
    for element in soup.find_all(['div', 'span', 'section', 'article']):
        # 检查直接子节点中是否有文本节点
        for child in list(element.children):
            if isinstance(child, str) and child.strip():
                # 找到裸文本，用 <p> 包装
                new_p = soup.new_tag('p')
                new_p.string = child.strip()
                child.replace_with(new_p)

    # 添加或修改 style 标签以确保适当的边距和防止溢出
    style_tag = soup.find('style')
    if not style_tag:
        style_tag = soup.new_tag('style')
        if soup.head:
            soup.head.append(style_tag)
        else:
            # 如果没有 head 标签，创建一个
            head_tag = soup.new_tag('head')
            soup.insert(0, head_tag)
            head_tag.append(style_tag)

    # 添加防溢出和边距的 CSS
    overflow_prevention_css = """
    /* 严格限制 html 和 body 尺寸 - 16:9 幻灯片 */
    html, body {
        width: 960pt !important;  /* 10 inches * 96 pt/inch */
        height: 540pt !important;  /* 5.625 inches * 96 pt/inch */
        max-width: 960pt !important;
        max-height: 540pt !important;
        margin: 0 !important;
        padding: 0 !important;
        box-sizing: border-box !important;
        overflow: hidden !important;
    }

    /* 内容区域：留出安全边距 */
    body {
        padding: 36pt 48pt 48pt 48pt !important;  /* 上36pt 左右48pt 下48pt */
    }

    /* 确保所有内容容器不超出 */
    body > div,
    body > section,
    body > article {
        max-width: 100% !important;
        max-height: 100% !important;
        overflow: hidden !important;
        box-sizing: border-box !important;
    }

    /* 防止所有元素溢出 */
    * {
        box-sizing: border-box !important;
        max-width: 100% !important;
        word-wrap: break-word !important;
        overflow-wrap: break-word !important;
    }

    /* 调整字体大小和行高 */
    body {
        font-size: 14pt !important;
        line-height: 1.4 !important;
    }

    /* 标题尺寸 - 更保守 */
    h1 {
        font-size: 24pt !important;
        line-height: 1.2 !important;
        margin: 12pt 0 8pt 0 !important;
        padding: 0 !important;
    }
    h2 {
        font-size: 20pt !important;
        line-height: 1.2 !important;
        margin: 10pt 0 6pt 0 !important;
        padding: 0 !important;
    }
    h3 {
        font-size: 18pt !important;
        line-height: 1.2 !important;
        margin: 8pt 0 6pt 0 !important;
        padding: 0 !important;
    }
    h4 {
        font-size: 16pt !important;
        line-height: 1.2 !important;
        margin: 6pt 0 4pt 0 !important;
        padding: 0 !important;
    }
    h5, h6 {
        font-size: 14pt !important;
        line-height: 1.2 !important;
        margin: 6pt 0 4pt 0 !important;
        padding: 0 !important;
    }

    /* 段落间距 */
    p {
        margin: 6pt 0 !important;
        padding: 0 !important;
        line-height: 1.4 !important;
    }

    /* 列表样式 */
    ul, ol {
        margin: 8pt 0 !important;
        padding-left: 24pt !important;
    }

    li {
        margin: 3pt 0 !important;
        padding: 0 !important;
        line-height: 1.3 !important;
    }

    /* 表格样式 */
    table {
        margin: 8pt 0 !important;
        max-width: 100% !important;
        table-layout: fixed !important;
    }

    td, th {
        padding: 4pt 6pt !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
    }

    /* 图片和媒体 */
    img, video, iframe {
        max-width: 100% !important;
        max-height: 400pt !important;
        height: auto !important;
    }

    /* 最后一个元素的底部边距 */
    body > *:last-child {
        margin-bottom: 0 !important;
        padding-bottom: 0 !important;
    }
    """

    # 将新的 CSS 添加到现有 style 中
    if style_tag.string:
        style_tag.string = str(style_tag.string) + "\n" + overflow_prevention_css
    else:
        style_tag.string = overflow_prevention_css

    return str(soup)


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
        将 HTML 幻灯片导出为可编辑的 PPTX
        
        使用 html2pptx 工具将 HTML 转换为真正的 PPTX（不是图片）
        生成的 PPTX 文件中的文本、形状、表格等元素都可以编辑
        
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
            
            # 创建临时目录存放 HTML 文件
            temp_dir = EXPORT_DIR / f"temp_{uuid.uuid4().hex[:8]}"
            temp_dir.mkdir(parents=True, exist_ok=True)
            
            try:
                # 将每张幻灯片保存为 HTML 文件
                html_files = []
                for i, slide_html in enumerate(slides_html):
                    # 清理 HTML 以符合 html2pptx 要求
                    cleaned_html = sanitize_html_for_pptx(slide_html)

                    html_file = temp_dir / f"slide_{i+1:02d}.html"
                    with open(html_file, 'w', encoding='utf-8') as f:
                        f.write(cleaned_html)
                    html_files.append(str(html_file))
                    logger.info(f"HTML file created: {html_file}")
                
                # 调用 html2pptx 工具
                html2pptx_dir = Path(__file__).parent.parent / "html2pptx"
                html2pptx_cli = html2pptx_dir / "html2pptx_cli.js"
                
                # 构建命令
                cmd = [
                    "node",
                    str(html2pptx_cli),
                    "--output", str(pptx_filepath),
                    "--layout", "16:9",
                    "--skip-validation"  # 跳过验证，允许内容溢出
                ]
                
                # 添加所有 HTML 文件
                for html_file in html_files:
                    cmd.extend(["--html", html_file])
                
                logger.info(f"Running html2pptx: {' '.join(cmd)}")
                
                # 执行命令
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                stdout, stderr = await process.communicate()
                
                if process.returncode != 0:
                    error_msg = stderr.decode('utf-8') if stderr else "Unknown error"
                    logger.error(f"html2pptx failed: {error_msg}")
                    # 失败时保留临时文件用于调试
                    logger.info(f"Temporary HTML files preserved for debugging: {temp_dir}")
                    raise Exception(f"html2pptx conversion failed: {error_msg}")
                
                # 成功后等待一下，确保PPTX文件写入完成
                await asyncio.sleep(0.5)
                
                # 检查PPTX文件是否生成
                if not os.path.exists(pptx_filepath):
                    logger.error(f"PPTX file not found: {pptx_filepath}")
                    # 清理临时文件
                    import shutil
                    if temp_dir.exists():
                        shutil.rmtree(temp_dir)
                    raise Exception(f"PPTX file not generated: {pptx_filepath}")
                
                logger.info(f"PPTX exported: {pptx_filepath}")
                
                # 清理临时文件
                import shutil
                if temp_dir.exists():
                    shutil.rmtree(temp_dir)
                    logger.info(f"Temp directory cleaned: {temp_dir}")
                
                return str(pptx_filepath), pptx_filename
                
            except Exception as e:
                # 发生错误时也要清理临时文件
                import shutil
                if temp_dir.exists():
                    shutil.rmtree(temp_dir)
                    logger.info(f"Temp directory cleaned after error: {temp_dir}")
                raise
            
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
