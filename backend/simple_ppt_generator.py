"""
PPT 生成器 - 完整实现智谱清言的 PPT 生成流程
使用完整的系统提示词和工具定义
"""

import json
import logging
import re
from typing import AsyncGenerator, Dict, List, Optional, Callable

# 导入优化后的系统提示词
from optimized_system_prompt import (
    OPTIMIZED_SYSTEM_PROMPT,
    COVER_SLIDE_PROMPT,
    CONTENT_SLIDE_PROMPT,
    TOC_SLIDE_PROMPT,
    CHART_SLIDE_PROMPT,
    ENDING_SLIDE_PROMPT
)

logger = logging.getLogger(__name__)


# 使用优化后的系统提示词
SYSTEM_PROMPT = OPTIMIZED_SYSTEM_PROMPT


# HTML 模板 - 封面页
COVER_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
    <link href="https://cdn.cn.font.mi.com/font/css?family=MiSans:300,400,500,600,700:Chinese_Simplify,Latin&display=swap" rel="stylesheet">
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: 'MiSans', 'Microsoft YaHei', sans-serif;
            background: {bg_color};
            width: 1280px;
            height: 720px;
            overflow: hidden;
        }}
        .slide {{
            width: 1280px;
            height: 720px;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            padding: 60px 80px;
            position: relative;
        }}
        .title {{
            font-size: {title_size}px;
            font-weight: 700;
            color: {primary_color};
            text-align: center;
            margin-bottom: 24px;
            line-height: 1.3;
        }}
        .subtitle {{
            font-size: 24px;
            color: {primary_color};
            opacity: 0.8;
            text-align: center;
            margin-bottom: 40px;
        }}
        .divider {{
            width: 120px;
            height: 4px;
            background: {accent_color};
            margin-bottom: 40px;
        }}
        .meta {{
            font-size: 18px;
            color: {primary_color};
            opacity: 0.6;
            text-align: center;
        }}
        .decoration {{
            position: absolute;
            width: 200px;
            height: 200px;
            border: 3px solid {accent_color};
            opacity: 0.2;
            border-radius: 50%;
        }}
        .decoration-1 {{
            top: -50px;
            right: -50px;
        }}
        .decoration-2 {{
            bottom: -80px;
            left: -80px;
            width: 300px;
            height: 300px;
        }}
    </style>
</head>
<body>
    <div class="slide">
        <div class="decoration decoration-1"></div>
        <div class="decoration decoration-2"></div>
        <h1 class="title">{title}</h1>
        <div class="divider"></div>
        <p class="subtitle">{subtitle}</p>
        <p class="meta">{meta}</p>
    </div>
</body>
</html>"""


# HTML 模板 - 目录页
TOC_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
    <link href="https://cdn.cn.font.mi.com/font/css?family=MiSans:300,400,500,600,700:Chinese_Simplify,Latin&display=swap" rel="stylesheet">
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: 'MiSans', 'Microsoft YaHei', sans-serif;
            background: {bg_color};
            width: 1280px;
            height: 720px;
            overflow: hidden;
        }}
        .slide {{
            width: 1280px;
            height: 720px;
            padding: 0;
        }}
        .header {{
            height: 85px;
            background: {primary_color};
            display: flex;
            align-items: center;
            padding: 0 60px;
        }}
        .header-title {{
            font-size: 36px;
            font-weight: 600;
            color: {bg_color};
        }}
        .content {{
            padding: 50px 80px;
            display: flex;
            flex-wrap: wrap;
            gap: 30px;
            justify-content: center;
        }}
        .toc-item {{
            width: calc(50% - 20px);
            display: flex;
            align-items: center;
            padding: 25px 30px;
            background: rgba(0,0,0,0.03);
            border-radius: 12px;
            border-left: 4px solid {accent_color};
            transition: all 0.3s ease;
        }}
        .toc-number {{
            font-size: 48px;
            font-weight: 700;
            color: {accent_color};
            margin-right: 25px;
            opacity: 0.8;
        }}
        .toc-text {{
            font-size: 22px;
            color: {primary_color};
            font-weight: 500;
        }}
    </style>
</head>
<body>
    <div class="slide">
        <div class="header">
            <h2 class="header-title">目录</h2>
        </div>
        <div class="content">
            {toc_items}
        </div>
    </div>
</body>
</html>"""


# HTML 模板 - 内容页（带图标列表）
CONTENT_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
    <link href="https://cdn.cn.font.mi.com/font/css?family=MiSans:300,400,500,600,700:Chinese_Simplify,Latin&display=swap" rel="stylesheet">
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: 'MiSans', 'Microsoft YaHei', sans-serif;
            background: {bg_color};
            width: 1280px;
            height: 720px;
            overflow: hidden;
        }}
        .slide {{
            width: 1280px;
            height: 720px;
            display: flex;
            flex-direction: column;
        }}
        .header {{
            height: 85px;
            background: {primary_color};
            display: flex;
            align-items: center;
            padding: 0 60px;
            flex-shrink: 0;
        }}
        .header-title {{
            font-size: 36px;
            font-weight: 600;
            color: {bg_color};
        }}
        .content {{
            flex: 1;
            padding: 40px 60px;
            display: flex;
            flex-direction: column;
            gap: 25px;
        }}
        .item {{
            display: flex;
            align-items: flex-start;
            padding: 20px 25px;
            background: rgba(0,0,0,0.02);
            border-radius: 12px;
            border-left: 4px solid {accent_color};
        }}
        .item-icon {{
            width: 50px;
            height: 50px;
            background: {accent_color};
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-right: 20px;
            flex-shrink: 0;
        }}
        .item-icon i {{
            font-size: 28px;
            color: white;
        }}
        .item-content {{
            flex: 1;
        }}
        .item-title {{
            font-size: 22px;
            font-weight: 600;
            color: {primary_color};
            margin-bottom: 8px;
        }}
        .item-desc {{
            font-size: 18px;
            color: {primary_color};
            opacity: 0.7;
            line-height: 1.5;
        }}
        .page-number {{
            position: absolute;
            bottom: 20px;
            right: 40px;
            font-size: 14px;
            color: {primary_color};
            opacity: 0.5;
        }}
    </style>
</head>
<body>
    <div class="slide">
        <div class="header">
            <h2 class="header-title">{title}</h2>
        </div>
        <div class="content">
            {items}
        </div>
        <span class="page-number">{page_number}</span>
    </div>
</body>
</html>"""


# HTML 模板 - 结束页
END_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
    <link href="https://cdn.cn.font.mi.com/font/css?family=MiSans:300,400,500,600,700:Chinese_Simplify,Latin&display=swap" rel="stylesheet">
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: 'MiSans', 'Microsoft YaHei', sans-serif;
            background: {bg_color};
            width: 1280px;
            height: 720px;
            overflow: hidden;
        }}
        .slide {{
            width: 1280px;
            height: 720px;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            position: relative;
        }}
        .thank-you {{
            font-size: 72px;
            font-weight: 700;
            color: {primary_color};
            margin-bottom: 30px;
        }}
        .divider {{
            width: 150px;
            height: 4px;
            background: {accent_color};
            margin-bottom: 30px;
        }}
        .contact {{
            font-size: 20px;
            color: {primary_color};
            opacity: 0.7;
            text-align: center;
        }}
        .decoration {{
            position: absolute;
            width: 250px;
            height: 250px;
            border: 3px solid {accent_color};
            opacity: 0.15;
            border-radius: 50%;
        }}
        .decoration-1 {{
            top: -100px;
            left: -100px;
        }}
        .decoration-2 {{
            bottom: -100px;
            right: -100px;
        }}
    </style>
</head>
<body>
    <div class="slide">
        <div class="decoration decoration-1"></div>
        <div class="decoration decoration-2"></div>
        <h1 class="thank-you">感谢观看</h1>
        <div class="divider"></div>
        <p class="contact">{contact}</p>
    </div>
</body>
</html>"""


# 配色方案
COLOR_SCHEMES = {
    "warm_modern": {
        "bg": "#F4F1E9",
        "primary": "#15857A",
        "accent": "#FF6A3B"
    },
    "cool_modern": {
        "bg": "#FEFEFE",
        "primary": "#1284BA",
        "accent": "#FF862F"
    },
    "dark_mineral": {
        "bg": "#162235",
        "primary": "#FFFFFF",
        "accent": "#37DCF2"
    },
    "minimalist": {
        "bg": "#F3F1ED",
        "primary": "#000000",
        "accent": "#D6C096"
    },
    "warm_retro": {
        "bg": "#F4EEEA",
        "primary": "#882F1C",
        "accent": "#FEE79B"
    }
}


# Material Icons 映射
ICONS = [
    "lightbulb", "star", "check_circle", "trending_up", "insights",
    "psychology", "auto_awesome", "rocket_launch", "verified", "workspace_premium",
    "emoji_objects", "tips_and_updates", "grade", "thumb_up", "favorite"
]


class PPTGenerator:
    """PPT 生成器 - 完整实现智谱清言的流程"""
    
    def __init__(
        self,
        llm_client: Callable,
        topic: str,
        outline_data: dict,
        supplement_data: dict,
        search_results: List[dict] = None
    ):
        """
        初始化生成器
        
        Args:
            llm_client: LLM 客户端（用于调用豆包 API）
            topic: PPT 主题
            outline_data: 大纲数据
            supplement_data: 补充信息（受众、风格等）
            search_results: 搜索结果
        """
        self.llm_client = llm_client
        self.topic = topic
        self.outline_data = outline_data
        self.supplement_data = supplement_data
        self.search_results = search_results or []
        
        # 设计参数
        self.width = 1280
        self.height = 720
        
        # 选择配色方案
        style = supplement_data.get("style", "简约现代")
        self.color_scheme = self._select_color_scheme(style)
        
        # 从大纲中解析页面
        self.pages = self._parse_outline()
        self.total_pages = len(self.pages)
        
        logger.info(f"初始化 PPT 生成器：主题={topic}, 页数={self.total_pages}, 配色={self.color_scheme}")
    
    def _select_color_scheme(self, style: str) -> dict:
        """根据风格选择配色方案"""
        style_lower = style.lower()
        
        if "深色" in style_lower or "dark" in style_lower or "科技" in style_lower:
            return COLOR_SCHEMES["dark_mineral"]
        elif "复古" in style_lower or "传统" in style_lower or "中国风" in style_lower:
            return COLOR_SCHEMES["warm_retro"]
        elif "暖" in style_lower or "warm" in style_lower:
            return COLOR_SCHEMES["warm_modern"]
        elif "冷" in style_lower or "cool" in style_lower or "商务" in style_lower:
            return COLOR_SCHEMES["cool_modern"]
        else:
            return COLOR_SCHEMES["minimalist"]
    
    def _parse_outline(self) -> List[Dict]:
        """从大纲数据中解析页面信息"""
        pages = []
        
        # 第 1 页：封面
        pages.append({
            "index": 1,
            "type": "cover",
            "title": self.topic,
            "subtitle": self.supplement_data.get("audience", "专业介绍"),
            "meta": ""
        })
        
        # 从大纲中提取章节
        outline_content = self.outline_data.get("content", "")
        sections = self._extract_sections(outline_content)
        
        # 如果有多个章节，添加目录页
        if len(sections) >= 3:
            pages.append({
                "index": 2,
                "type": "toc",
                "title": "目录",
                "sections": sections[:8]  # 最多显示 8 个章节
            })
        
        # 为每个章节创建内容页
        for i, section in enumerate(sections[:10], start=len(pages) + 1):  # 最多 10 个内容页
            # 为每个章节生成要点
            points = self._generate_points(section)
            
            pages.append({
                "index": i,
                "type": "content",
                "title": section,
                "points": points
            })
        
        # 结束页
        pages.append({
            "index": len(pages) + 1,
            "type": "end",
            "title": "感谢观看",
            "contact": f"主题：{self.topic}"
        })
        
        logger.info(f"从大纲解析出 {len(pages)} 页")
        return pages
    
    def _extract_sections(self, content: str) -> List[str]:
        """从大纲内容中提取章节标题"""
        sections = []
        
        if not content:
            # 如果没有大纲内容，生成默认章节
            return [
                "产品概述",
                "核心功能",
                "技术特点",
                "应用场景",
                "竞争优势",
                "未来展望"
            ]
        
        # 按行分割
        lines = content.split("\n")
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 移除 Markdown 标记
            clean_line = re.sub(r'^[#\-\*\d\.\s]+', '', line).strip()
            
            # 过滤掉太短或太长的行
            if 2 <= len(clean_line) <= 30:
                sections.append(clean_line)
        
        # 如果解析出的章节太少，添加默认章节
        if len(sections) < 3:
            sections.extend([
                "核心功能",
                "技术特点",
                "应用场景"
            ])
        
        return sections[:10]  # 最多 10 个章节
    
    def _generate_points(self, section_title: str) -> List[Dict]:
        """为章节生成要点"""
        # 根据章节标题生成相关要点
        default_points = [
            {"title": "核心优势", "desc": "提供行业领先的解决方案"},
            {"title": "技术创新", "desc": "采用最新的技术架构"},
            {"title": "用户体验", "desc": "简洁直观的操作界面"},
            {"title": "安全可靠", "desc": "多重安全保障机制"}
        ]
        
        # 从搜索结果中提取相关内容
        if self.search_results:
            points = []
            for i, result in enumerate(self.search_results[:4]):
                title = result.get("title", "")[:20]
                snippet = result.get("snippet", result.get("description", ""))[:50]
                if title and snippet:
                    points.append({
                        "title": title,
                        "desc": snippet
                    })
            
            if len(points) >= 2:
                return points[:4]
        
        return default_points[:4]
    
    def _generate_cover_html(self, page: dict) -> str:
        """生成封面页 HTML"""
        title = page.get("title", self.topic)
        subtitle = page.get("subtitle", "")
        meta = page.get("meta", "")
        
        # 根据标题长度调整字体大小
        title_size = 60 if len(title) <= 15 else 48 if len(title) <= 25 else 40
        
        return COVER_TEMPLATE.format(
            bg_color=self.color_scheme["bg"],
            primary_color=self.color_scheme["primary"],
            accent_color=self.color_scheme["accent"],
            title=title,
            subtitle=subtitle,
            meta=meta,
            title_size=title_size
        )
    
    def _generate_toc_html(self, page: dict) -> str:
        """生成目录页 HTML"""
        sections = page.get("sections", [])
        
        toc_items_html = ""
        for i, section in enumerate(sections, start=1):
            toc_items_html += f"""
            <div class="toc-item">
                <span class="toc-number">{i:02d}</span>
                <span class="toc-text">{section}</span>
            </div>
            """
        
        return TOC_TEMPLATE.format(
            bg_color=self.color_scheme["bg"],
            primary_color=self.color_scheme["primary"],
            accent_color=self.color_scheme["accent"],
            toc_items=toc_items_html
        )
    
    def _generate_content_html(self, page: dict) -> str:
        """生成内容页 HTML"""
        title = page.get("title", "")
        points = page.get("points", [])
        page_number = page.get("index", 1)
        
        items_html = ""
        for i, point in enumerate(points):
            icon = ICONS[i % len(ICONS)]
            items_html += f"""
            <div class="item">
                <div class="item-icon">
                    <i class="material-icons">{icon}</i>
                </div>
                <div class="item-content">
                    <h3 class="item-title">{point.get('title', '')}</h3>
                    <p class="item-desc">{point.get('desc', '')}</p>
                </div>
            </div>
            """
        
        return CONTENT_TEMPLATE.format(
            bg_color=self.color_scheme["bg"],
            primary_color=self.color_scheme["primary"],
            accent_color=self.color_scheme["accent"],
            title=title,
            items=items_html,
            page_number=f"{page_number} / {self.total_pages}"
        )
    
    def _generate_end_html(self, page: dict) -> str:
        """生成结束页 HTML"""
        contact = page.get("contact", "")
        
        return END_TEMPLATE.format(
            bg_color=self.color_scheme["bg"],
            primary_color=self.color_scheme["primary"],
            accent_color=self.color_scheme["accent"],
            contact=contact
        )
    
    async def generate_slide_html(self, page: dict) -> str:
        """
        生成单页 HTML 代码
        
        Args:
            page: 页面信息
            
        Returns:
            HTML 代码字符串
        """
        page_type = page.get("type", "content")
        page_number = page.get("index", 1)
        
        logger.info(f"生成第 {page_number} 页，类型: {page_type}")
        
        try:
            if page_type == "cover":
                return self._generate_cover_html(page)
            elif page_type == "toc":
                return self._generate_toc_html(page)
            elif page_type == "end":
                return self._generate_end_html(page)
            else:
                return self._generate_content_html(page)
                
        except Exception as e:
            logger.error(f"生成第 {page_number} 页 HTML 失败: {e}")
            return self._generate_error_html(page_number, str(e))
    
    def _generate_error_html(self, page_number: int, error: str) -> str:
        """生成错误页面 HTML"""
        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{
            width: 1280px;
            height: 720px;
            margin: 0;
            display: flex;
            justify-content: center;
            align-items: center;
            background: #f0f0f0;
            font-family: sans-serif;
        }}
        .error {{
            text-align: center;
            color: #666;
        }}
    </style>
</head>
<body>
    <div class="error">
        <h1>生成失败</h1>
        <p>第 {page_number} 页生成时出错</p>
        <p style="font-size: 12px; color: #999;">{error}</p>
    </div>
</body>
</html>"""
    
    async def generate_all_slides(self) -> AsyncGenerator[Dict, None]:
        """
        逐页生成所有幻灯片
        
        Yields:
            包含页码和 HTML 代码的字典
        """
        logger.info(f"开始生成 {self.total_pages} 页幻灯片")
        
        for page in self.pages:
            page_number = page["index"]
            page_type = page.get("type", "content")
            
            # 生成 HTML
            html_code = await self.generate_slide_html(page)
            
            logger.info(f"完成第 {page_number}/{self.total_pages} 页，HTML 长度: {len(html_code)}")
            
            # 返回结果
            yield {
                "page_number": page_number,
                "total_pages": self.total_pages,
                "html": html_code,
                "title": page.get("title", ""),
                "type": page_type
            }
        
        logger.info("所有幻灯片生成完成")


# 为了向后兼容，保留 SimplePPTGenerator 别名
SimplePPTGenerator = PPTGenerator
