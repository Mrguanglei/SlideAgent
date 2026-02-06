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

    # 0. 快速预判断：如果是纯问候语，直接返回 False，不需要问 LLM
    greetings = ["你好", "您好", "hi", "hello", "嗨", "在吗", "早安", "晚安", "早上好", "晚上好"]
    cleaned_instruction = instruction.lower().strip().replace("！", "").replace("!", "")
    if cleaned_instruction in greetings:
        logger.info(f"Intent check: '{instruction}' identified as greeting, skipping LLM.")
        return False

    try:
        # 1. 强制 system prompt 简单粗暴，防止废话
        prompt = f"""你是一个 PPT 制作助手的意图识别模块。判断用户输入是否需要**立即生成 PPT**。

用户输入：{instruction}

**核心规则**：
- 必须包含**具体主题**（如"包含AI"、"关于华为"）才算PPT需求。
- 询问功能、问候、闲聊、或者"你会做什么"统统不算。

请只回答一个字："是" 或 "否"。"""

        response = await call_llm_api([
            {"role": "system", "content": "只回答'是'或'否'。不要输出任何思考过程！不要输出标点符号！"},
            {"role": "user", "content": prompt}
        ])

        # 2. 清理响应内容（移除 <think> 标签和多余空格）
        import re
        clean_result = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL).strip()
        # 移除可能的 markdown 标记
        clean_result = clean_result.replace("**", "").replace("`", "").replace('"', "").replace("'", "")
        
        # 3. 严格判断
        # 只有当结果明确是 "是" 或 "yes" 时才返回 True
        # 避免 "是否"、"是不是" 等词其中的 "是" 导致误判
        is_ppt_request = clean_result == "是" or clean_result.lower() == "yes"
        
        logger.info(f"Intent check raw: {repr(response)}")
        logger.info(f"Intent check clean: {repr(clean_result)} -> {is_ppt_request}")
        
        return is_ppt_request

    except Exception as e:
        logger.error(f"Intent check failed: {e}, falling back to keyword matching")
        # 降级策略：关键词匹配，但要排除询问词
        keywords = ["ppt", "幻灯片", "演示", "slide", "presentation", "制作", "生成", "帮我做", "做一个", "介绍", "讲解", "分析"]
        negative_keywords = ["什么", "怎么", "如何", "功能", "能力", "会"]
        
        has_keyword = any(kw in instruction.lower() for kw in keywords)
        has_negative = any(nkw in instruction.lower() for nkw in negative_keywords)
        
        # 如果有关键词，且没有明显的疑问词，才认为是PPT需求
        return has_keyword and not has_negative


async def analyze_user_intent_for_paused_session(
    user_message: str, 
    current_topic: str,
    current_stage: str,
    supplement_data: dict = None
) -> dict:
    """
    分析暂停后用户发送的消息，判断用户意图
    
    返回:
    - action: "restart" | "adjust" | "resume"
    - new_topic: 如果是 restart 或 adjust，返回新主题
    - adjustment: 如果是 adjust，返回调整说明
    """
    logger.info(f"Analyzing user intent for paused session: {user_message[:50]}...")
    
    # 快速判断明确的继续意图
    continue_keywords = ["继续", "恢复", "接着", "go on", "continue", "resume", "没问题", "好的继续", "确定"]
    if any(kw in user_message.lower() for kw in continue_keywords) and len(user_message) < 20:
        return {"action": "resume", "new_topic": current_topic}
    
    # 快速判断明确的重新开始意图
    restart_keywords = ["换个主题", "重新开始", "换一个", "不要这个", "改成", "算了", "从头开始"]
    if any(kw in user_message.lower() for kw in restart_keywords):
        # 提取新主题
        new_topic = user_message
        for kw in restart_keywords:
            new_topic = new_topic.replace(kw, "").strip()
        if not new_topic or len(new_topic) < 3:
            new_topic = None
        return {"action": "restart", "new_topic": new_topic}
    
    # 使用 LLM 判断复杂意图
    try:
        prompt = f"""你是一个PPT制作助手的意图分析模块。用户之前正在制作一份关于"{current_topic}"的PPT，目前处于{current_stage}阶段，但任务被暂停了。

用户现在发送了新消息："{user_message}"

请分析用户的意图，返回JSON格式：

如果用户想**完全更换主题**（制作一个全新的PPT）：
{{"action": "restart", "new_topic": "新主题内容"}}

如果用户想**调整当前主题**（深入某个方向、调整侧重点等，但还是这个主题）：
{{"action": "adjust", "new_topic": "调整后的主题", "adjustment": "调整说明"}}

如果用户想**继续执行**（无需修改，继续之前的任务）：
{{"action": "resume", "new_topic": "{current_topic}"}}

请只输出JSON，不要有其他内容。"""

        response = await call_llm_api([
            {"role": "system", "content": "你是一个意图分析助手，善于理解用户在对话上下文中的真实意图。请只输出JSON格式的结果。"},
            {"role": "user", "content": prompt}
        ])
        
        response = clean_json_response(response)
        result = json.loads(response)
        logger.info(f"LLM intent analysis result: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Intent analysis failed: {e}, defaulting to resume")
        return {"action": "resume", "new_topic": current_topic}


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
        response = clean_json_response(response or "")
        if not response.strip():
            raise ValueError("Empty response from LLM")
        try:
            result = json.loads(response)
        except json.JSONDecodeError:
            # 容错：尝试从文本中提取 JSON
            start = response.find("{")
            end = response.rfind("}")
            if start != -1 and end != -1 and end > start:
                result = json.loads(response[start:end + 1])
            else:
                raise
        
        # 添加页数选项
        result["numPagesQuestion"] = "您期望的PPT页数范围是？"
        result["numPagesOptions"] = ["8-10页", "11-15页", "16-20页", "21-25页"]
        logger.info(f"LLM generated supplement info: {result}")
        return result
        
    except Exception as e:
        logger.warning(f"Failed to generate supplement info with LLM: {e}")
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

    file_context = supplement_data.get("file_context", "")

    # 根据是否有文件内容生成不同的提示
    if file_context:
        prompt = f"""用户提供了上传的文件内容，要求基于文件制作关于"{topic}"的PPT。请分析文件内容并生成详细的任务执行规划。

文件内容上下文：
{file_context[:3000]}... (已截断)

目标受众：{audience}
内容模块：{', '.join(modules) if modules else '根据文件内容规划'}
设计风格：{style}
重点内容：{keywords if keywords else '无特别要求'}

请按以下格式分析（使用纯文本，不要使用JSON）：

用户要求基于文件制作"{topic}"的PPT，我需要分析文件并规划：

1. 核心内容识别：
• [分析文件的主题]
• [提取文件中的关键信息]
• [确定PPT的核心逻辑]

2. 信息提取维度：
• 按照文件结构提取章节
• 整理关键数据和结论
• 提炼核心观点
• 梳理案例或证明材料

3. 执行策略：
• **直接使用提供的文件内容作为主要来源**
• 无需进行外部搜索（除非文件内容严重缺失）
• 重点是对文件内容进行结构化整理和可视化呈现

4. 结构规划：
• 基于文件目录或逻辑生成PPT大纲
• 确保覆盖文件中的所有关键点

现在开始执行规划。

请根据文件内容和主题"{topic}"，生成针对性的分析内容，保持上述格式。"""
    else:
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

    file_context = supplement_data.get("file_context", "")
    
    # 构造上下文内容
    context_str = ""
    if file_context:
        context_str = f"""
文件内容（主要依据）：
{file_context[:5000]}
"""
    else:
        context_str = f"""
搜索结果摘要：
{results_summary}

深度分析内容：
{deep_thinking_content[:1500] if deep_thinking_content else '无'}
"""

    prompt = f"""基于以下信息，为「{topic}」生成PPT大纲目录。

目标受众：{audience}
内容模块：{', '.join(modules) if modules else '自动规划'}
设计风格：{style}
**必须生成的页数：{num_pages}页（严格遵守，不能多也不能少）**

{context_str}

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
