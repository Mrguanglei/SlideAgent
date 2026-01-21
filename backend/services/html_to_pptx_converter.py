"""
HTML 到 PPTX 转换器

基于 suna 项目的实现方案：
1. 使用 Playwright 渲染 HTML 幻灯片
2. 提取并截图视觉元素（背景、图片、图表等）
3. 提取文本元素的位置和样式信息
4. 使用 python-pptx 重构 PPTX 文件

优点：
- 视觉保真：复杂的背景、阴影、图片等以高质量 PNG 图像形式保留
- 可编辑性：文本内容是可编辑的文本框，用户可以在 PowerPoint 中直接修改

日期：2026-01-21
"""

import os
import io
import logging
import asyncio
import tempfile
import shutil
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from datetime import datetime

from playwright.async_api import async_playwright, Browser, Page
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR

logger = logging.getLogger(__name__)


class HTMLToPPTXConverter:
    """
    HTML 到 PPTX 转换器
    
    将 HTML 幻灯片转换为可编辑的 PPTX 文件。
    """
    
    # 幻灯片尺寸（16:9）
    SLIDE_WIDTH_PX = 1920
    SLIDE_HEIGHT_PX = 1080
    SLIDE_WIDTH_INCH = 10
    SLIDE_HEIGHT_INCH = 5.625
    
    def __init__(self):
        self.temp_dir: Optional[Path] = None
        self.slides_info: List[Dict] = []
        self.metadata: Dict[str, Any] = {}
        
    async def convert(
        self,
        slides_html: List[str],
        output_path: str,
        title: str = "Presentation"
    ) -> str:
        """
        转换 HTML 幻灯片为 PPTX 文件
        
        Args:
            slides_html: HTML 幻灯片列表
            output_path: 输出文件路径
            title: 演示文稿标题
            
        Returns:
            生成的 PPTX 文件路径
        """
        # 创建临时目录
        self.temp_dir = Path(tempfile.mkdtemp(prefix="html2pptx_"))
        self.metadata = {"presentation_name": title}
        self.slides_info = []
        
        try:
            logger.info(f"开始转换 {len(slides_html)} 张幻灯片...")
            
            # 保存 HTML 文件到临时目录
            html_files = []
            for i, html in enumerate(slides_html):
                html_file = self.temp_dir / f"slide_{i+1:02d}.html"
                
                # 确保 HTML 包含完整的文档结构
                if not html.strip().startswith('<!DOCTYPE') and not html.strip().startswith('<html'):
                    html = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ margin: 0; padding: 0; width: {self.SLIDE_WIDTH_PX}px; height: {self.SLIDE_HEIGHT_PX}px; }}
    </style>
</head>
<body>
{html}
</body>
</html>'''
                
                html_file.write_text(html, encoding='utf-8')
                html_files.append(html_file)
                self.slides_info.append({
                    'slide_number': i + 1,
                    'html_path': str(html_file)
                })
            
            # 使用 Playwright 渲染并提取元素
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=['--no-sandbox', '--disable-setuid-sandbox']
                )
                
                try:
                    all_slide_analyses = await self._analyze_all_slides(browser)
                finally:
                    await browser.close()
            
            # 构建 PPTX 演示文稿
            presentation = Presentation()
            presentation.slide_width = Inches(self.SLIDE_WIDTH_INCH)
            presentation.slide_height = Inches(self.SLIDE_HEIGHT_INCH)
            
            # 移除默认幻灯片
            if len(presentation.slides) > 0:
                xml_slides = presentation.slides._sldIdLst
                xml_slides.remove(xml_slides[0])
            
            # 构建每张幻灯片
            for i, slide_analysis in enumerate(all_slide_analyses, 1):
                try:
                    if 'error' in slide_analysis and slide_analysis['error']:
                        # 创建错误占位幻灯片
                        blank_slide_layout = presentation.slide_layouts[6]
                        slide = presentation.slides.add_slide(blank_slide_layout)
                        
                        textbox = slide.shapes.add_textbox(Inches(1), Inches(4), Inches(18), Inches(2))
                        text_frame = textbox.text_frame
                        text_frame.clear()
                        p = text_frame.paragraphs[0]
                        p.text = f"Error processing slide: {slide_analysis['error']}"
                        p.font.size = Pt(18)
                        p.font.color.rgb = RGBColor(255, 0, 0)
                    else:
                        await self._build_slide_from_analysis(presentation, slide_analysis, self.temp_dir)
                        logger.info(f"幻灯片 {i} 构建完成")
                        
                except Exception as e:
                    logger.error(f"构建幻灯片 {i} 失败: {e}")
                    # 创建错误占位幻灯片
                    blank_slide_layout = presentation.slide_layouts[6]
                    slide = presentation.slides.add_slide(blank_slide_layout)
                    
                    textbox = slide.shapes.add_textbox(Inches(1), Inches(4), Inches(18), Inches(2))
                    text_frame = textbox.text_frame
                    text_frame.clear()
                    p = text_frame.paragraphs[0]
                    p.text = f"Error building slide: {str(e)}"
                    p.font.size = Pt(18)
                    p.font.color.rgb = RGBColor(255, 0, 0)
            
            # 设置文档属性
            presentation.core_properties.title = title
            presentation.core_properties.author = "PPTAgent"
            presentation.core_properties.comments = "Generated by PPTAgent"
            
            # 保存 PPTX 文件
            presentation.save(output_path)
            logger.info(f"PPTX 文件已保存: {output_path}")
            
            return output_path
            
        finally:
            # 清理临时目录
            if self.temp_dir and self.temp_dir.exists():
                shutil.rmtree(self.temp_dir)
                logger.info(f"临时目录已清理: {self.temp_dir}")
    
    async def _analyze_all_slides(self, browser: Browser) -> List[Dict]:
        """分析所有幻灯片，提取视觉元素和文本元素"""
        all_slide_analyses = []
        
        for slide_info in self.slides_info:
            try:
                logger.info(f"分析幻灯片 {slide_info['slide_number']}...")
                
                page = await browser.new_page(
                    viewport={'width': self.SLIDE_WIDTH_PX, 'height': self.SLIDE_HEIGHT_PX}
                )
                
                try:
                    # 加载 HTML 文件
                    await page.goto(f"file://{slide_info['html_path']}", wait_until='networkidle', timeout=60000)
                    await page.wait_for_timeout(1000)
                    
                    # 提取背景截图
                    background_path = self.temp_dir / f"slide_{slide_info['slide_number']}_bg.png"
                    await page.screenshot(path=str(background_path), full_page=False)
                    
                    # 提取文本元素
                    text_elements = await self._extract_text_elements(page)
                    
                    # 提取视觉元素（图片、图表等）
                    visual_elements = await self._extract_visual_elements(page, slide_info['slide_number'])
                    
                    slide_analysis = {
                        'slide_info': slide_info,
                        'background_path': background_path,
                        'text_elements': text_elements,
                        'visual_elements': visual_elements
                    }
                    
                    all_slide_analyses.append(slide_analysis)
                    logger.info(f"幻灯片 {slide_info['slide_number']} 分析完成: {len(text_elements)} 个文本元素, {len(visual_elements)} 个视觉元素")
                    
                finally:
                    await page.close()
                    
            except Exception as e:
                logger.error(f"分析幻灯片 {slide_info['slide_number']} 失败: {e}")
                all_slide_analyses.append({
                    'slide_info': slide_info,
                    'error': str(e)
                })
        
        return all_slide_analyses
    
    async def _extract_text_elements(self, page: Page) -> List[Dict]:
        """提取文本元素的位置和样式"""
        text_elements = await page.evaluate('''() => {
            const elements = [];
            const PX_TO_INCH = 1 / 96;
            
            function pxToInch(px) {
                return px * PX_TO_INCH;
            }
            
            function rgbToHex(rgb) {
                if (!rgb || rgb === 'transparent') return '#000000';
                const match = rgb.match(/rgba?\\((\\d+),\\s*(\\d+),\\s*(\\d+)/);
                if (!match) return '#000000';
                return '#' + match.slice(1, 4).map(n => parseInt(n).toString(16).padStart(2, '0')).join('').toUpperCase();
            }
            
            function isVisible(el) {
                const rect = el.getBoundingClientRect();
                if (rect.width === 0 || rect.height === 0) return false;
                const style = window.getComputedStyle(el);
                if (style.display === 'none' || style.visibility === 'hidden') return false;
                if (parseFloat(style.opacity) === 0) return false;
                return true;
            }
            
            function isLeafTextContainer(el) {
                const text = el.innerText?.trim();
                if (!text) return false;
                
                for (const child of el.children) {
                    const childText = child.innerText?.trim();
                    if (childText && childText.length > 0) {
                        return false;
                    }
                }
                
                return true;
            }
            
            const allElements = document.body.querySelectorAll('*');
            for (const el of allElements) {
                if (!isVisible(el)) continue;
                if (el.tagName === 'IMG' || el.tagName === 'SCRIPT' || el.tagName === 'STYLE') continue;
                
                if (isLeafTextContainer(el)) {
                    const rect = el.getBoundingClientRect();
                    const style = window.getComputedStyle(el);
                    const text = el.innerText?.trim();
                    
                    if (text) {
                        elements.push({
                            type: 'text',
                            content: text,
                            x: pxToInch(rect.left),
                            y: pxToInch(rect.top),
                            width: pxToInch(rect.width),
                            height: pxToInch(rect.height),
                            font_size: parseFloat(style.fontSize) * 0.75,  // px to pt
                            font_family: style.fontFamily.split(',')[0].replace(/['"]/g, '').trim() || 'Arial',
                            color: rgbToHex(style.color),
                            bold: parseInt(style.fontWeight) >= 600,
                            italic: style.fontStyle === 'italic',
                            align: style.textAlign === 'start' ? 'left' : (style.textAlign || 'left')
                        });
                    }
                }
            }
            
            return elements;
        }''')
        
        return text_elements
    
    async def _extract_visual_elements(self, page: Page, slide_number: int) -> List[Dict]:
        """提取视觉元素（图片、Canvas 等）"""
        visual_elements = []
        
        # 提取图片元素
        images = await page.query_selector_all('img')
        for i, img in enumerate(images):
            try:
                rect = await img.bounding_box()
                if rect and rect['width'] > 0 and rect['height'] > 0:
                    # 截图图片元素
                    img_path = self.temp_dir / f"slide_{slide_number}_img_{i+1}.png"
                    await img.screenshot(path=str(img_path))
                    
                    visual_elements.append({
                        'type': 'image',
                        'x': rect['x'] / 96,
                        'y': rect['y'] / 96,
                        'width': rect['width'] / 96,
                        'height': rect['height'] / 96,
                        'image_path': img_path
                    })
            except Exception as e:
                logger.warning(f"提取图片元素失败: {e}")
        
        # 提取 Canvas 元素（图表）
        canvases = await page.query_selector_all('canvas')
        for i, canvas in enumerate(canvases):
            try:
                rect = await canvas.bounding_box()
                if rect and rect['width'] > 0 and rect['height'] > 0:
                    # 截图 Canvas 元素
                    canvas_path = self.temp_dir / f"slide_{slide_number}_canvas_{i+1}.png"
                    await canvas.screenshot(path=str(canvas_path))
                    
                    visual_elements.append({
                        'type': 'canvas',
                        'x': rect['x'] / 96,
                        'y': rect['y'] / 96,
                        'width': rect['width'] / 96,
                        'height': rect['height'] / 96,
                        'image_path': canvas_path
                    })
            except Exception as e:
                logger.warning(f"提取 Canvas 元素失败: {e}")
        
        return visual_elements
    
    async def _build_slide_from_analysis(self, presentation: Presentation, slide_analysis: Dict, temp_dir: Path) -> None:
        """从分析结果构建 PowerPoint 幻灯片"""
        slide_info = slide_analysis['slide_info']
        background_path = slide_analysis['background_path']
        text_elements = slide_analysis['text_elements']
        visual_elements = slide_analysis['visual_elements']
        
        # 添加空白幻灯片
        blank_slide_layout = presentation.slide_layouts[6]
        slide = presentation.slides.add_slide(blank_slide_layout)
        
        # 步骤 1: 添加背景图片作为底层
        if background_path and background_path.exists():
            try:
                slide.shapes.add_picture(
                    str(background_path),
                    Inches(0),
                    Inches(0),
                    width=Inches(self.SLIDE_WIDTH_INCH),
                    height=Inches(self.SLIDE_HEIGHT_INCH)
                )
            except Exception as e:
                logger.warning(f"添加背景图片失败: {e}")
        
        # 步骤 2: 添加视觉元素（图片、Canvas）
        for visual_element in visual_elements:
            try:
                if visual_element['image_path'].exists():
                    slide.shapes.add_picture(
                        str(visual_element['image_path']),
                        Inches(visual_element['x']),
                        Inches(visual_element['y']),
                        width=Inches(visual_element['width']),
                        height=Inches(visual_element['height'])
                    )
            except Exception as e:
                logger.warning(f"添加视觉元素失败: {e}")
        
        # 步骤 3: 添加可编辑的文本框
        for text_element in text_elements:
            try:
                self._create_text_box(slide, text_element)
            except Exception as e:
                logger.warning(f"添加文本框失败: {e}")
    
    def _create_text_box(self, slide, text_element: Dict) -> None:
        """创建文本框"""
        # 创建文本框
        textbox = slide.shapes.add_textbox(
            Inches(text_element['x']),
            Inches(text_element['y']),
            Inches(text_element['width']),
            Inches(text_element['height'])
        )
        
        # 设置文本框属性
        tf = textbox.text_frame
        tf.word_wrap = True
        tf.margin_left = Inches(0.05)
        tf.margin_right = Inches(0.05)
        tf.margin_top = Inches(0.02)
        tf.margin_bottom = Inches(0.02)
        
        # 添加段落
        p = tf.paragraphs[0]
        
        # 设置段落对齐
        if text_element.get('align') == 'center':
            p.alignment = PP_ALIGN.CENTER
        elif text_element.get('align') == 'right':
            p.alignment = PP_ALIGN.RIGHT
        else:
            p.alignment = PP_ALIGN.LEFT
        
        # 添加文本运行
        run = p.add_run()
        run.text = text_element['content']
        
        # 设置字体样式
        if text_element.get('font_size'):
            run.font.size = Pt(text_element['font_size'])
        
        if text_element.get('font_family'):
            font_name = text_element['font_family'].strip().strip('"').strip("'")
            if font_name.lower() not in ['sans-serif', 'serif', 'monospace']:
                run.font.name = font_name
            else:
                run.font.name = 'Microsoft YaHei'
        else:
            run.font.name = 'Microsoft YaHei'
        
        if text_element.get('color'):
            try:
                color_hex = text_element['color'].lstrip('#')
                r = int(color_hex[0:2], 16)
                g = int(color_hex[2:4], 16)
                b = int(color_hex[4:6], 16)
                run.font.color.rgb = RGBColor(r, g, b)
            except Exception:
                pass
        
        if text_element.get('bold'):
            run.font.bold = True
        
        if text_element.get('italic'):
            run.font.italic = True


# 单例实例
converter = HTMLToPPTXConverter()


async def convert_html_to_pptx(
    slides_html: List[str],
    output_path: str,
    title: str = "Presentation"
) -> str:
    """
    转换 HTML 幻灯片为 PPTX 文件的便捷函数
    
    Args:
        slides_html: HTML 幻灯片列表
        output_path: 输出文件路径
        title: 演示文稿标题
        
    Returns:
        生成的 PPTX 文件路径
    """
    return await converter.convert(slides_html, output_path, title)
