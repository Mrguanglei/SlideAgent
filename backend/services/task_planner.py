"""
PPTAgent 任务规划服务模块

提供补充信息生成、任务规划生成、大纲生成等功能
"""

import json
import logging
from typing import Dict, Optional, AsyncGenerator, Tuple

from services.llm import call_llm_api, call_llm_api_stream, clean_json_response
from utils.config import Config

logger = logging.getLogger(__name__)


async def check_ppt_intent(instruction: str) -> bool:
    """检查用户输入是否是 PPT 制作需求"""
    if not Config.LLM_API_KEY:
        # 如果没有配置 API,则回退到简单关键词判断
        keywords = ["ppt", "幻灯片", "演示", "slide", "presentation", "制作", "生成", "帮我做", "做一个", "介绍", "讲解", "分析"]
        return any(kw in instruction.lower() for kw in keywords)

    try:
        prompt = f"""你是一个 PPT 制作助手的意图识别模块。判断用户输入是否需要制作 PPT。

用户输入：{instruction}

**重要上下文**：
- 用户正在使用专门的 PPT 制作助手
- 用户说"介绍XX"、"讲解XX"、"分析XX"等，都应该理解为需要制作演示材料（PPT）
- 只有明显的问候、闲聊才不是 PPT 需求

**是 PPT 需求** 的情况（判断为"是"）：
- 明确提到：PPT、幻灯片、演示文稿、presentation
- 要求介绍/讲解/分析某个主题、产品、公司、技术等
- 要求制作、生成、创建演示内容
- 描述性需求，如"帮我详细介绍XX"、"讲一下XX"

**不是 PPT 需求** 的情况（判断为"否"）：
- 纯问候：你好、hi、hello、嗨
- 纯闲聊：怎么样、在吗、最近如何
- 单纯的疑问句且没有制作意图：你能做什么？你是什么？

只回答"是"或"否",不要有其他内容。"""

        response = await call_llm_api([
            {"role": "system", "content": "你是一个意图识别助手。记住：用户在使用PPT制作助手，所以'介绍XX'、'讲解XX'都应该理解为需要制作PPT。只需要回答'是'或'否'。"},
            {"role": "user", "content": prompt}
        ])

        result = response.strip().lower()
        is_ppt_request = "是" in result or "yes" in result
        logger.info(f"Intent check for '{instruction[:30]}...': {is_ppt_request} (response: {result})")
        return is_ppt_request

    except Exception as e:
        logger.error(f"Intent check failed: {e}, falling back to keyword matching")
        keywords = ["ppt", "幻灯片", "演示", "slide", "presentation", "制作", "生成", "帮我做", "做一个", "介绍", "讲解", "分析"]
        return any(kw in instruction.lower() for kw in keywords)


async def generate_supplement_info_with_llm(topic: str) -> dict:
    """使用 LLM 分析用户意图，动态生成补充信息选项"""
    logger.info(f"Using LLM to analyze topic: {topic}")
    
    prompt = f"""分析用户的PPT制作需求，生成补充信息选项。

用户输入：{topic}

请根据用户输入的主题，生成以下内容（JSON格式）：
1. 分析用户可能的目标受众（4个选项）
2. 分析PPT可能需要的内容模块（6个选项）
3. 分析适合的设计风格（4个选项）
4. 生成一个引导用户补充重点内容的问题

请严格按照以下JSON格式输出：
{{
    "topic": "用户主题的简洁描述",
    "audienceQuestion": "这份PPT的目标受众是？",
    "audienceOptions": ["选项1", "选项2", "选项3", "选项4"],
    "modulesQuestion": "PPT中需要包含哪些内容模块？",
    "modulesOptions": ["模块1", "模块2", "模块3", "模块4", "模块5", "模块6"],
    "styleQuestion": "你期望的PPT设计风格是？",
    "styleOptions": ["风格1", "风格2", "风格3", "风格4"],
    "emphasisQuestion": "是否有特定内容需要重点突出？",
    "emphasisPlaceholder": "例如：具体的提示内容"
}}

只输出JSON，不要有其他内容。"""

    try:
        response = await call_llm_api([
            {"role": "system", "content": "你是一个专业的PPT制作助手，擅长分析用户需求并提供合适的选项。请只输出JSON格式的结果。"},
            {"role": "user", "content": prompt}
        ])
        
        # 解析 JSON
        response = clean_json_response(response)
        result = json.loads(response)
        
        # 添加页数选项
        result["numPagesQuestion"] = "您期望的PPT页数范围是？"
        result["numPagesOptions"] = ["8-10页", "11-15页", "16-20页", "21-25页"]
        logger.info(f"LLM generated supplement info: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Failed to generate supplement info with LLM: {e}")
        # 回退到基础选项
        return {
            "topic": topic,
            "audienceQuestion": "这份PPT的目标受众是？",
            "audienceOptions": ["专业人士", "普通公众", "学生群体", "企业客户"],
            "modulesQuestion": "PPT中需要包含哪些内容模块？",
            "modulesOptions": ["背景介绍", "核心内容", "案例分析", "数据展示", "总结建议", "Q&A"],
            "styleQuestion": "你期望的PPT设计风格是？",
            "styleOptions": ["简约现代", "专业商务", "创意设计", "学术风格"],
            "numPagesQuestion": "您期望的PPT页数范围是？",
            "numPagesOptions": ["8-10页", "11-15页", "16-20页", "21-25页"],
            "emphasisQuestion": "是否有特定内容需要重点突出？",
            "emphasisPlaceholder": "例如：某个关键点、特定数据、核心结论等"
        }


async def stream_task_plan_with_llm(topic: str, supplement_data: dict) -> AsyncGenerator[Tuple[str, Optional[dict]], None]:
    """流式生成任务规划，返回 (文本块, 完整数据或None)"""
    logger.info(f"Streaming task plan for: {topic}")

    audience = supplement_data.get("audience", "专业人士")
    modules = supplement_data.get("modules", [])
    style = supplement_data.get("style", "简约现代")
    keywords = supplement_data.get("keywords", "")

    prompt = f"""用户询问"{topic}"，请分析这个请求并生成详细的任务执行规划。

目标受众：{audience}
内容模块：{', '.join(modules) if modules else '待定'}
设计风格：{style}
重点内容：{keywords if keywords else '无特别要求'}

请按以下格式分析（使用纯文本，不要使用JSON）：

用户询问"{topic}"，我需要分析这个请求：

1. 核心问题识别：
• [分析这个主题是什么]
• [用户需要了解什么信息]
• [可能涉及的相关领域]

2. 信息收集维度：
• 基本定义和功能定位
• 主要特点和核心功能
• 技术特点和创新点
• 应用场景和目标用户
• 发展背景和所属机构
• 市场表现和用户评价

3. 搜索策略：
• 首先搜索"{topic}"了解基本信息
• 搜索可能相关的关键词
• 可能需要访问官网或权威媒体了解详细信息
• 收集最新动态和用户反馈

4. 时间范围：
• 由于这是一个产品/主题介绍，需要了解最新信息
• 不应该限制搜索时间范围，以确保获取全面信息

现在开始执行搜索计划。

请根据用户的具体主题"{topic}"，生成针对性的分析内容，保持上述格式。"""

    full_text = ""
    try:
        async for chunk in call_llm_api_stream([
            {"role": "system", "content": "你是一个专业的PPT制作助手，擅长分析用户需求并规划任务步骤。请按照用户要求的格式输出分析结果。"},
            {"role": "user", "content": prompt}
        ]):
            full_text += chunk
            yield (chunk, None)  # 流式输出文本块

        # 最后解析并返回结构化数据
        task_plan_data = parse_task_plan_text(full_text, topic, supplement_data)
        yield ("", task_plan_data)  # 最后返回完整数据

    except Exception as e:
        logger.error(f"Failed to stream task plan: {e}")
        # 回退到基础规划
        fallback_data = {
            "coreRequirement": f"制作一份关于「{topic}」的PPT，面向{audience}，采用{style}风格",
            "streamContent": f'用户询问「{topic}」，我需要分析这个请求：\n\n1. 核心问题识别：\n• 「{topic}」是需要分析的主题\n• 用户需要了解这个主题的详细信息\n• 可能需要收集相关数据和案例',
            "steps": [
                {"id": 1, "text": "搜索相关资料和数据", "status": "pending"},
                {"id": 2, "text": "整理内容大纲", "status": "pending"},
                {"id": 3, "text": "设计页面布局", "status": "pending"},
                {"id": 4, "text": "生成各页幻灯片", "status": "pending"},
                {"id": 5, "text": "优化和导出PPT", "status": "pending"},
            ]
        }
        yield ("", fallback_data)


def parse_task_plan_text(text: str, topic: str, supplement_data: dict) -> dict:
    """将流式文本解析为结构化数据"""
    audience = supplement_data.get("audience", "专业人士")
    style = supplement_data.get("style", "简约现代")

    return {
        "coreRequirement": f"制作一份关于「{topic}」的PPT，面向{audience}，采用{style}风格",
        "streamContent": text,  # 保存流式内容
        "steps": [
            {"id": 1, "text": "搜索相关资料和数据", "status": "pending"},
            {"id": 2, "text": "整理内容大纲", "status": "pending"},
            {"id": 3, "text": "设计页面布局", "status": "pending"},
            {"id": 4, "text": "生成各页幻灯片", "status": "pending"},
            {"id": 5, "text": "优化和导出PPT", "status": "pending"},
        ]
    }


async def stream_outline_generation(topic: str, search_results: list, deep_thinking_content: str, supplement_data: dict) -> AsyncGenerator[str, None]:
    """流式生成 PPT 大纲目录"""
    logger.info(f"Starting outline generation for: {topic}")

    # 构建搜索结果摘要
    results_summary = ""
    for i, result in enumerate(search_results[:8], 1):
        title = result.get("title", "")
        snippet = result.get("snippet", "")[:200]
        results_summary += f"{i}. {title}\n   {snippet}\n\n"

    # 获取补充信息
    audience = supplement_data.get("audience", "专业人士")
    modules = supplement_data.get("modules", [])
    style = supplement_data.get("style", "简约现代")
    num_pages_range = supplement_data.get("num_pages", "8-10页")

    # 将页数范围转换为具体数字（取中间值）
    if isinstance(num_pages_range, str):
        if "8-10" in num_pages_range:
            num_pages = 9
        elif "11-15" in num_pages_range:
            num_pages = 13
        elif "16-20" in num_pages_range:
            num_pages = 18
        elif "21-25" in num_pages_range:
            num_pages = 23
        else:
            num_pages = 10
    else:
        num_pages = num_pages_range

    prompt = f"""基于以下信息，为「{topic}」生成PPT大纲目录。

目标受众：{audience}
内容模块：{', '.join(modules) if modules else '自动规划'}
设计风格：{style}
**必须生成的页数：{num_pages}页（严格遵守，不能多也不能少）**

搜索结果摘要：
{results_summary}

深度分析内容：
{deep_thinking_content[:1500] if deep_thinking_content else '无'}

请生成一份**内容充实、结构合理**的PPT大纲，格式如下：

# PPT大纲：[根据内容生成的专业标题]

## 第1页：封面
- 标题：[根据搜索结果生成的专业标题]
- 副标题：[简短的产品定位或核心价值]

## 第2页：目录
- 列出所有内容章节的标题

## 第3页：[章节标题] - 概述
- 详细内容描述
- 具体数据或案例
- 核心价值点

[继续生成其他内容页面，确保总页数为{num_pages}页...]

## 第{num_pages}页：总结与展望
- 核心价值回顾
- 未来发展方向

**重要要求**：页数必须严格为 {num_pages} 页！"""

    try:
        async for chunk in call_llm_api_stream([
            {"role": "system", "content": "你是一个专业的PPT内容策划师，擅长根据搜索结果生成结构化的PPT大纲。请严格按照用户要求的格式和页数输出。"},
            {"role": "user", "content": prompt}
        ]):
            yield chunk
    except Exception as e:
        logger.error(f"Outline generation error: {e}")
        # 回退到简单大纲
        fallback = f"""# PPT大纲：{topic}

## 第1页：封面
- 标题：{topic}
- 副标题：专业介绍

## 第2页：目录
- 概述
- 核心内容
- 总结

## 第3页：概述
- 背景介绍
- 核心要点

## 第{num_pages}页：总结
- 核心要点回顾
"""
        yield fallback
