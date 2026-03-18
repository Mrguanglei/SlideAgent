"""
PPTAgent 辅助工具函数

从 api_server.py 中提取的通用辅助函数
"""

import re
import logging

logger = logging.getLogger(__name__)


def normalize_conversation_title(text: str, max_len: int = 32) -> str:
    """清洗/截断标题"""
    if not text:
        return "新对话"
    title = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.IGNORECASE)
    title = re.sub(r"<think>[\s\S]*$", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\s+", " ", title).strip()
    title = title.strip("\u201c\u201d\"'`")
    title = title.lstrip("\uff1a:\uff0c,\u3002. ")
    if len(title) > max_len:
        title = title[:max_len].rstrip()
    return title if title else "新对话"


def strip_think_tags(text: str) -> str:
    """移除 <think> 标签及其内容，不截断长度。"""
    if not text:
        return ""
    cleaned = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.IGNORECASE)
    cleaned = re.sub(r"<think>[\s\S]*$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = cleaned.lstrip("\uff1a:\uff0c,\u3002. ")
    return cleaned


def clean_title_simple(text: str, max_len: int = 32, fallback: str = "未命名") -> str:
    """轻量清洗标题，不依赖正则。"""
    if not text:
        return fallback
    title = " ".join(str(text).split()).strip()
    title = title.strip("\u201c\u201d\"'` ")
    while title and title[0] in "\uff1a:\uff0c,\u3002. ":
        title = title[1:].lstrip()
    if len(title) > max_len:
        title = title[:max_len].rstrip()
    return title or fallback


def extract_color_preference(text: str) -> str:
    """从用户输入中提取配色偏好（简单规则）"""
    if not text:
        return ""
    hex_match = re.search(r"#?[0-9a-fA-F]{6}", text)
    if hex_match:
        color = hex_match.group(0)
        return color if color.startswith("#") else f"#{color}"

    candidates = [
        "深蓝", "深蓝色", "蓝", "蓝色",
        "红", "红色",
        "绿", "绿色",
        "橙", "橙色",
        "紫", "紫色",
        "黑", "黑色",
        "白", "白色",
        "灰", "灰色",
        "金", "金色",
        "银", "银色",
        "黄", "黄色",
        "青", "青色",
    ]
    for cand in candidates:
        if cand in text:
            return cand
    return ""


def extract_style_preference(text: str) -> str:
    """从用户输入中提取风格偏好，映射到系统内置选项"""
    if not text:
        return ""
    if any(k in text for k in ["简约", "极简", "现代", "清爽", "清新"]):
        return "简约现代"
    if any(k in text for k in ["商务", "企业", "正式", "专业"]):
        return "专业商务"
    if any(k in text for k in ["创意", "设计", "酷炫", "视觉"]):
        return "创意设计"
    if any(k in text for k in ["学术", "科研", "论文", "研究"]):
        return "学术风格"
    return ""


def estimate_num_pages_range(file_context: str) -> str:
    """根据文档内容粗略估计页数范围"""
    if not file_context:
        return "11-15页"

    page_markers = re.findall(r"\[第\s*\d+\s*页\]", file_context)
    if page_markers:
        count = len(page_markers)
        if count <= 5:
            return "8-10页"
        if count <= 10:
            return "11-15页"
        if count <= 20:
            return "16-20页"
        return "21-25页"

    length = len(file_context)
    if length <= 3000:
        return "8-10页"
    if length <= 8000:
        return "11-15页"
    if length <= 15000:
        return "16-20页"
    return "21-25页"


def check_ppt_intent_by_keyword(instruction: str, has_attachments: bool = False) -> bool:
    """通过关键词判断用户输入是否是 PPT 制作需求（不调用LLM）"""
    if has_attachments:
        return True

    text = instruction.lower().strip()

    # 纯问候语直接返回 False
    greetings = ["你好", "您好", "hi", "hello", "嗨", "在吗", "早安", "晚安", "早上好", "晚上好"]
    cleaned = text.replace("！", "").replace("!", "")
    if cleaned in greetings:
        return False

    # PPT 相关关键词
    ppt_keywords = [
        "ppt", "幻灯片", "演示", "slide", "presentation",
        "制作", "生成", "帮我做", "做一个",
    ]
    # 疑问词（排除纯询问）
    negative_keywords = ["什么", "怎么", "如何", "功能", "能力", "会", "可以吗", "能不能"]

    has_keyword = any(kw in text for kw in ppt_keywords)
    has_negative = any(nkw in text for nkw in negative_keywords)

    return has_keyword and not has_negative


def generate_supplement_info(topic: str, template_name: str = "") -> dict:
    """生成固定模板的补充信息选项（不调用LLM）"""
    has_template = bool(str(template_name or "").strip())
    result = {
        "topic": topic,
        "audienceQuestion": "这份PPT的目标受众是？",
        "audienceOptions": ["专业人士", "普通公众", "学生群体", "企业客户"],
        "modulesQuestion": "PPT中需要包含哪些内容模块？",
        "modulesOptions": ["背景介绍", "核心内容", "案例分析", "数据展示", "总结建议", "Q&A"],
        "numPagesQuestion": "您期望的PPT页数范围是？",
        "numPagesOptions": ["8-10页", "11-15页", "16-20页", "21-25页"],
        "emphasisQuestion": "是否有特定内容需要重点突出？",
        "emphasisPlaceholder": "例如：某个关键点、特定数据、核心结论等",
    }
    if has_template:
        result["selectedTemplate"] = template_name
        result["templateLocked"] = True
    else:
        result["styleQuestion"] = "你期望的PPT设计风格是？"
        result["styleOptions"] = ["简约现代", "专业商务", "创意设计", "学术风格"]
    return result
