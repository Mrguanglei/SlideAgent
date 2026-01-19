"""
PPTAgent HTML 解析器

解析 HTML 幻灯片，提取可转换为 PPTX 的元素：
- 文本元素（标题、段落、列表）
- 形状元素（矩形、圆角矩形）
- 图片元素
- 背景颜色/渐变

核心策略：
1. 只提取"叶子文本节点" - 即直接包含文本的最内层元素
2. 避免父子元素重复提取同一文本
3. 正确处理嵌套的 span、div 等元素
"""

import re
import logging
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Page

logger = logging.getLogger(__name__)

# 常量
PX_PER_INCH = 96  # 标准 DPI
PT_PER_PX = 0.75  # 1px = 0.75pt


@dataclass
class Position:
    """元素位置（英寸）"""
    x: float
    y: float
    w: float
    h: float


@dataclass
class TextStyle:
    """文本样式"""
    font_size: float = 12  # 点
    font_family: str = "Arial"
    color: str = "#000000"
    bold: bool = False
    italic: bool = False
    underline: bool = False
    align: str = "left"  # left, center, right
    valign: str = "top"  # top, middle, bottom
    line_spacing: float = 1.0


@dataclass
class ShapeStyle:
    """形状样式"""
    fill_color: Optional[str] = None
    border_color: Optional[str] = None
    border_width: float = 0
    border_radius: float = 0
    opacity: float = 1.0


@dataclass
class SlideElement:
    """幻灯片元素"""
    type: str  # text, shape, image, list
    position: Position
    content: Any = None
    style: Any = None
    src: Optional[str] = None  # 图片URL
    items: Optional[List[str]] = None  # 列表项


@dataclass
class SlideData:
    """幻灯片数据"""
    background: Dict[str, Any] = field(default_factory=lambda: {"type": "color", "value": "#FFFFFF"})
    elements: List[SlideElement] = field(default_factory=list)


class HtmlParser:
    """
    HTML 解析器
    
    使用 Playwright 渲染 HTML 并提取元素的精确位置和样式。
    核心策略：只提取叶子文本节点，避免重复。
    """
    
    # 幻灯片尺寸
    SLIDE_WIDTH_PX = 1280
    SLIDE_HEIGHT_PX = 720
    SLIDE_WIDTH_INCH = 10
    SLIDE_HEIGHT_INCH = 5.625
    
    def __init__(self):
        self.browser = None
        self.page: Optional[Page] = None
    
    async def parse(self, html: str) -> SlideData:
        """
        解析 HTML 幻灯片
        
        Args:
            html: HTML 内容
            
        Returns:
            SlideData 对象
        """
        async with async_playwright() as p:
            # 启动浏览器
            browser = await p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-setuid-sandbox']
            )
            
            # 创建页面
            page = await browser.new_page(
                viewport={
                    'width': self.SLIDE_WIDTH_PX,
                    'height': self.SLIDE_HEIGHT_PX
                }
            )
            
            try:
                # 设置页面内容
                await page.set_content(html, wait_until='networkidle')
                await page.wait_for_load_state('networkidle')
                await asyncio.sleep(0.3)  # 等待字体加载
                
                # 提取数据
                slide_data = await self._extract_slide_data(page)
                
                return slide_data
                
            finally:
                await browser.close()
    
    async def _extract_slide_data(self, page: Page) -> SlideData:
        """从页面提取幻灯片数据"""
        
        # 提取背景
        background = await self._extract_background(page)
        
        # 提取所有元素
        elements = await self._extract_elements(page)
        
        return SlideData(background=background, elements=elements)
    
    async def _extract_background(self, page: Page) -> Dict[str, Any]:
        """提取背景颜色"""
        bg_info = await page.evaluate('''() => {
            const body = document.body;
            const style = window.getComputedStyle(body);
            const bgColor = style.backgroundColor;
            const bgImage = style.backgroundImage;
            
            return {
                backgroundColor: bgColor,
                backgroundImage: bgImage
            };
        }''')
        
        bg_color = self._parse_color(bg_info.get('backgroundColor', 'rgb(255,255,255)'))
        
        if bg_info.get('backgroundImage') and bg_info['backgroundImage'] != 'none':
            # 有背景图片或渐变
            return {"type": "gradient", "value": bg_info['backgroundImage']}
        else:
            return {"type": "color", "value": bg_color}
    
    async def _extract_elements(self, page: Page) -> List[SlideElement]:
        """提取所有可见元素"""
        
        # 在浏览器中执行 JavaScript 提取元素信息
        # 核心策略：使用 TreeWalker 遍历文本节点，然后找到其父元素
        elements_data = await page.evaluate('''() => {
            const PX_PER_INCH = 96;
            const PT_PER_PX = 0.75;
            
            function pxToInch(px) {
                return px / PX_PER_INCH;
            }
            
            function pxToPt(px) {
                return px * PT_PER_PX;
            }
            
            function rgbToHex(rgb) {
                if (!rgb || rgb === 'transparent' || rgb === 'rgba(0, 0, 0, 0)') {
                    return null;
                }
                const match = rgb.match(/rgba?\\((\\d+),\\s*(\\d+),\\s*(\\d+)/);
                if (!match) return null;
                return '#' + match.slice(1, 4).map(n => parseInt(n).toString(16).padStart(2, '0')).join('').toUpperCase();
            }
            
            // 检查元素是否可见
            function isVisible(el) {
                const rect = el.getBoundingClientRect();
                if (rect.width === 0 || rect.height === 0) return false;
                const style = window.getComputedStyle(el);
                if (style.display === 'none' || style.visibility === 'hidden') return false;
                if (parseFloat(style.opacity) === 0) return false;
                return true;
            }
            
            // 检查元素是否有直接的文本子节点（不包括子元素中的文本）
            function getDirectTextContent(el) {
                let text = '';
                for (const node of el.childNodes) {
                    if (node.nodeType === Node.TEXT_NODE) {
                        text += node.textContent;
                    }
                }
                return text.trim();
            }
            
            // 检查元素是否是"叶子文本容器"
            // 叶子文本容器：有文本内容，且没有包含文本的子元素
            function isLeafTextContainer(el) {
                const text = el.innerText?.trim();
                if (!text) return false;
                
                // 检查是否有子元素也包含文本
                for (const child of el.children) {
                    const childText = child.innerText?.trim();
                    if (childText && childText.length > 0) {
                        // 如果子元素包含相同的文本，则当前元素不是叶子
                        return false;
                    }
                }
                
                return true;
            }
            
            // 获取文本元素信息
            function getTextElementInfo(el) {
                const rect = el.getBoundingClientRect();
                const style = window.getComputedStyle(el);
                const text = el.innerText?.trim();
                
                if (!text) return null;
                
                return {
                    type: 'text',
                    position: {
                        x: pxToInch(rect.left),
                        y: pxToInch(rect.top),
                        w: pxToInch(rect.width),
                        h: pxToInch(rect.height)
                    },
                    content: text,
                    style: {
                        font_size: pxToPt(parseFloat(style.fontSize)),
                        font_family: style.fontFamily.split(',')[0].replace(/['"]/g, '').trim() || 'Arial',
                        color: rgbToHex(style.color) || '#000000',
                        bold: parseInt(style.fontWeight) >= 600,
                        italic: style.fontStyle === 'italic',
                        underline: style.textDecoration.includes('underline'),
                        align: style.textAlign === 'start' ? 'left' : (style.textAlign || 'left'),
                        line_spacing: parseFloat(style.lineHeight) / parseFloat(style.fontSize) || 1.2
                    }
                };
            }
            
            // 获取图片元素信息
            function getImageElementInfo(el) {
                const rect = el.getBoundingClientRect();
                
                return {
                    type: 'image',
                    position: {
                        x: pxToInch(rect.left),
                        y: pxToInch(rect.top),
                        w: pxToInch(rect.width),
                        h: pxToInch(rect.height)
                    },
                    src: el.src
                };
            }
            
            // 获取形状元素信息（有背景色但没有文本的元素）
            function getShapeElementInfo(el) {
                const rect = el.getBoundingClientRect();
                const style = window.getComputedStyle(el);
                
                const bgColor = rgbToHex(style.backgroundColor);
                if (!bgColor || bgColor === '#FFFFFF') return null;
                
                // 检查是否有文本
                const text = el.innerText?.trim();
                if (text) return null;
                
                const borderRadius = parseFloat(style.borderRadius) || 0;
                
                return {
                    type: 'shape',
                    position: {
                        x: pxToInch(rect.left),
                        y: pxToInch(rect.top),
                        w: pxToInch(rect.width),
                        h: pxToInch(rect.height)
                    },
                    style: {
                        fill_color: bgColor,
                        border_color: rgbToHex(style.borderColor),
                        border_width: parseFloat(style.borderWidth) || 0,
                        border_radius: pxToInch(borderRadius)
                    }
                };
            }
            
            const results = [];
            const processedRects = new Set();  // 用于去重
            
            // 1. 首先提取所有图片
            const images = document.querySelectorAll('img');
            for (const img of images) {
                if (!isVisible(img)) continue;
                const info = getImageElementInfo(img);
                if (info) {
                    results.push(info);
                }
            }
            
            // 2. 提取形状（有背景色但没有文本的元素）
            const allElements = document.body.querySelectorAll('*');
            for (const el of allElements) {
                if (!isVisible(el)) continue;
                if (el.tagName === 'IMG') continue;
                
                const info = getShapeElementInfo(el);
                if (info) {
                    const key = `shape_${info.position.x.toFixed(2)}_${info.position.y.toFixed(2)}_${info.position.w.toFixed(2)}_${info.position.h.toFixed(2)}`;
                    if (!processedRects.has(key)) {
                        processedRects.add(key);
                        results.push(info);
                    }
                }
            }
            
            // 3. 提取文本 - 只提取叶子文本容器
            // 策略：从最内层开始，标记已处理的文本区域
            const textElements = [];
            const processedTextAreas = [];  // 已处理的文本区域
            
            // 收集所有可能的文本元素
            for (const el of allElements) {
                if (!isVisible(el)) continue;
                if (el.tagName === 'IMG' || el.tagName === 'SCRIPT' || el.tagName === 'STYLE') continue;
                
                // 检查是否是叶子文本容器
                if (isLeafTextContainer(el)) {
                    const info = getTextElementInfo(el);
                    if (info && info.content) {
                        textElements.push({
                            element: el,
                            info: info,
                            area: info.position.w * info.position.h
                        });
                    }
                }
            }
            
            // 按面积从小到大排序（先处理小元素，避免大元素覆盖）
            textElements.sort((a, b) => a.area - b.area);
            
            // 去重：检查是否与已处理的区域重叠
            for (const item of textElements) {
                const pos = item.info.position;
                const content = item.info.content;
                
                // 检查是否与已处理的文本重叠
                let isDuplicate = false;
                for (const processed of processedTextAreas) {
                    // 检查位置是否重叠
                    const overlapX = Math.abs(pos.x - processed.x) < 0.1;
                    const overlapY = Math.abs(pos.y - processed.y) < 0.1;
                    
                    // 检查内容是否相同或包含
                    const contentMatch = content === processed.content || 
                                        processed.content.includes(content) ||
                                        content.includes(processed.content);
                    
                    if (overlapX && overlapY && contentMatch) {
                        isDuplicate = true;
                        break;
                    }
                }
                
                if (!isDuplicate) {
                    results.push(item.info);
                    processedTextAreas.push({
                        x: pos.x,
                        y: pos.y,
                        w: pos.w,
                        h: pos.h,
                        content: content
                    });
                }
            }
            
            return results;
        }''')
        
        # 转换为 SlideElement 对象
        elements = []
        for data in elements_data:
            position = Position(**data['position'])
            
            if data['type'] == 'text':
                style = TextStyle(**data['style']) if data.get('style') else TextStyle()
                element = SlideElement(
                    type='text',
                    position=position,
                    content=data.get('content', ''),
                    style=style
                )
            elif data['type'] == 'shape':
                style = ShapeStyle(**data['style']) if data.get('style') else ShapeStyle()
                element = SlideElement(
                    type='shape',
                    position=position,
                    style=style
                )
            elif data['type'] == 'image':
                element = SlideElement(
                    type='image',
                    position=position,
                    src=data.get('src')
                )
            else:
                continue
            
            elements.append(element)
        
        return elements
    
    def _parse_color(self, color_str: str) -> str:
        """将 RGB 颜色转换为十六进制"""
        if not color_str or color_str == 'transparent':
            return '#FFFFFF'
        
        match = re.match(r'rgba?\((\d+),\s*(\d+),\s*(\d+)', color_str)
        if match:
            r, g, b = int(match.group(1)), int(match.group(2)), int(match.group(3))
            return f'#{r:02X}{g:02X}{b:02X}'
        
        return '#FFFFFF'


# 单例实例
html_parser = HtmlParser()


async def parse_html(html: str) -> SlideData:
    """
    解析 HTML 幻灯片的便捷函数
    
    Args:
        html: HTML 内容
        
    Returns:
        SlideData 对象
    """
    return await html_parser.parse(html)
