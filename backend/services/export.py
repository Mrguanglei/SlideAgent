"""
PPTAgent 导出服务模块

支持将 PPT 导出为：
- PDF 文件
- PNG 图片（打包为 ZIP）
- PPTX 文件（使用 python-pptx 生成可编辑的 PPTX）

更新日志：
- 2026-01-17: 重构 PPTX 导出
  - 使用 Python + python-pptx 替代 Node.js html2pptx
  - 通过 HTML 解析生成可编辑的 PPTX（文本、形状、图片）
  - 解决了 PPTX 文件损坏问题
  - 简化了依赖（不再需要 Node.js 和 pptxgenjs）
- 2026-01-17: 添加导出优化功能
  - 添加 HTML 验证和导出前预检
  - 添加导出质量报告
  - 优化 Playwright 等待时间
  - 优化字体处理
"""

import os
import io
import uuid
import zipfile
import logging
import asyncio
from typing import List, Optional, Tuple, Dict, Any
from pathlib import Path
from datetime import datetime

# PDF 生成
from weasyprint import HTML, CSS
from weasyprint.text.fonts import FontConfiguration

# 图片生成
from playwright.async_api import async_playwright

# PPTX 生成（新方案：HTML 解析 + python-pptx）
from services.pptx_generator import generate_pptx

# HTML 验证
from services.html_validator import validate_html

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
        style_content = '\n'.join(styles)
        
        # 替换字体为 PDF 导出友好的字体
        style_content = self._replace_fonts_for_pdf(style_content)
        
        return style_content
    
    def _replace_fonts_for_pdf(self, css: str) -> str:
        """替换字体为 PDF 导出友好的字体"""
        # 字体映射表
        font_replacements = {
            "MiSans": "Microsoft YaHei",
            "Noto Sans SC": "Microsoft YaHei",
            "Source Han Serif SC": "SimSun",
            "Roboto Flex": "Arial",
            "Source Code Pro": "Courier New",
            "抖音黑体": "Microsoft YaHei",
        }
        
        for web_font, pdf_font in font_replacements.items():
            css = css.replace(web_font, pdf_font)
        
        # 移除 @import 语句（WeasyPrint 可能无法加载）
        import re
        css = re.sub(r'@import\s+url\([^)]+\);?', '', css)
        
        return css
    
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
                browser = await p.chromium.launch(
                    headless=True,
                    args=['--no-sandbox', '--disable-setuid-sandbox']
                )
                page = await browser.new_page(viewport={'width': self.slide_width, 'height': self.slide_height})
                
                # 创建 ZIP 文件
                with zipfile.ZipFile(zip_filepath, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for i, slide_html in enumerate(slides_html):
                        # 设置页面内容
                        await page.set_content(slide_html)
                        await page.wait_for_load_state('networkidle')
                        
                        # 额外等待字体和图片加载
                        await asyncio.sleep(0.5)
                        
                        # 等待所有图片加载完成
                        await page.evaluate('''
                            () => {
                                return Promise.all(
                                    Array.from(document.images)
                                        .filter(img => !img.complete)
                                        .map(img => new Promise(resolve => {
                                            img.onload = img.onerror = resolve;
                                        }))
                                );
                            }
                        ''')
                        
                        # 截图
                        screenshot = await page.screenshot(type=format, full_page=False)
                        
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
        将 HTML 幻灯片导出为可编辑的 PPTX 文件
        
        技术方案（参考智谱清言）：
        1. 使用 Playwright 渲染 HTML，提取元素位置和样式
        2. 使用 python-pptx 创建 PPTX 文件
        3. 将每个元素转换为对应的 PPTX 元素（文本框、形状、图片）
        
        优点：
        - 文本可编辑
        - 形状可编辑
        - 保持原始布局
        
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
            
            # 使用新的 PPTX 生成器（HTML 解析 + python-pptx）
            await generate_pptx(
                slides_html=slides_html,
                output_path=str(pptx_filepath),
                title=title
            )
            
            # 验证文件是否生成成功
            if not pptx_filepath.exists():
                raise Exception(f"PPTX 文件未生成: {pptx_filepath}")
            
            # 验证文件大小（确保不是空文件）
            file_size = pptx_filepath.stat().st_size
            if file_size < 1000:  # 小于 1KB 可能是损坏的文件
                raise Exception(f"PPTX 文件可能损坏，大小只有 {file_size} 字节")
            
            logger.info(f"PPTX exported successfully: {pptx_filepath} ({file_size} bytes)")
            return str(pptx_filepath), pptx_filename
            
        except Exception as e:
            logger.error(f"Failed to export PPTX: {e}")
            raise


# 单例实例
exporter = PPTExporter()


async def pre_export_check(slides_html: List[str]) -> Dict[str, Any]:
    """
    导出前预检
    
    Args:
        slides_html: HTML 幻灯片列表
        
    Returns:
        预检结果 {
            "passed": bool,
            "slides_count": int,
            "issues": List[str],
            "warnings": List[str],
            "external_resources_count": int,
            "external_resources": List[str]
        }
    """
    all_issues = []
    all_warnings = []
    all_resources = []
    
    for i, html in enumerate(slides_html):
        result = validate_html(html)
        
        if result["issues"]:
            all_issues.extend([f"第{i+1}页: {issue}" for issue in result["issues"]])
        
        if result["warnings"]:
            all_warnings.extend([f"第{i+1}页: {warning}" for warning in result["warnings"]])
        
        all_resources.extend(result["external_resources"])
    
    return {
        "passed": len(all_issues) == 0,
        "slides_count": len(slides_html),
        "issues": all_issues,
        "warnings": all_warnings,
        "external_resources_count": len(set(all_resources)),
        "external_resources": list(set(all_resources))
    }


async def generate_export_report(
    slides_html: List[str],
    export_format: str,
    output_path: str,
    pre_check_result: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    生成导出质量报告
    
    Args:
        slides_html: HTML 幻灯片列表
        export_format: 导出格式
        output_path: 输出文件路径
        pre_check_result: 预检结果
        
    Returns:
        质量报告
    """
    report = {
        "format": export_format,
        "output_path": output_path,
        "slides_count": len(slides_html),
        "export_time": datetime.now().isoformat(),
        "file_exists": os.path.exists(output_path),
        "file_size": 0,
        "issues": [],
        "warnings": [],
        "quality_score": 1.0
    }
    
    # 检查文件是否存在
    if not report["file_exists"]:
        report["issues"].append("导出文件不存在")
        report["quality_score"] = 0
        return report
    
    # 获取文件大小
    report["file_size"] = os.path.getsize(output_path)
    
    # 检查文件大小
    if report["file_size"] < 1000:
        report["issues"].append(f"文件大小异常（{report['file_size']} 字节）")
        report["quality_score"] -= 0.5
    
    # 检查 PPTX 文件完整性
    if export_format == "pptx":
        try:
            from pptx import Presentation
            prs = Presentation(output_path)
            report["slides_in_pptx"] = len(prs.slides)
            
            if report["slides_in_pptx"] != report["slides_count"]:
                report["warnings"].append(
                    f"PPTX 幻灯片数量不匹配：期望 {report['slides_count']}，实际 {report['slides_in_pptx']}"
                )
                report["quality_score"] -= 0.2
            
            # 检查每页是否有内容
            empty_slides = []
            for i, slide in enumerate(prs.slides):
                if len(slide.shapes) == 0:
                    empty_slides.append(i + 1)
            
            if empty_slides:
                report["warnings"].append(f"第 {', '.join(map(str, empty_slides))} 页没有内容")
                report["quality_score"] -= 0.1 * len(empty_slides)
        
        except Exception as e:
            report["issues"].append(f"PPTX 文件可能损坏: {e}")
            report["quality_score"] -= 0.5
    
    # 添加预检结果
    if pre_check_result:
        if pre_check_result.get("issues"):
            report["warnings"].extend(pre_check_result["issues"])
        if pre_check_result.get("warnings"):
            report["warnings"].extend(pre_check_result["warnings"])
    
    # 确保质量分数在 0-1 之间
    report["quality_score"] = max(0, min(1, report["quality_score"]))
    
    return report


async def export_ppt(
    slides_html: List[str],
    format: str,
    title: str = "presentation",
    skip_validation: bool = False
) -> Tuple[str, str]:
    """
    导出 PPT（增加预检功能）
    
    Args:
        slides_html: HTML 幻灯片列表
        format: 导出格式 (pdf/png/pptx)
        title: 文件标题
        skip_validation: 是否跳过验证
        
    Returns:
        (文件路径, 文件名)
    """
    # 导出前预检
    if not skip_validation:
        check_result = await pre_export_check(slides_html)
        
        if not check_result["passed"]:
            logger.warning(f"导出预检发现问题: {check_result['issues']}")
            # 可以选择抛出异常或继续导出
            # raise ValueError(f"导出预检失败: {check_result['issues']}")
        
        if check_result["warnings"]:
            logger.warning(f"导出预检警告: {check_result['warnings']}")
    
    # 原有的导出逻辑
    if format == "pdf":
        return await exporter.export_to_pdf(slides_html, title)
    elif format in ["png", "jpg", "images"]:
        return await exporter.export_to_images(slides_html, title, "png")
    elif format == "pptx":
        return await exporter.export_to_pptx(slides_html, title)
    else:
        raise ValueError(f"Unsupported format: {format}")
