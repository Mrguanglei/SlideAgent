"""
PPTAgent 任务规划服务模块

保留：
- build_task_steps() — 生成任务步骤
- generate_execution_plan() — 生成结构化执行规划
- stream_outline_generation() — 流式生成 PPT 大纲

已删除（不再需要）：
- check_ppt_intent() → 改用 utils/helpers.py 中的关键词判断
- generate_task_steps_with_llm() → 纯展示用，删除
- stream_task_plan_with_llm() → 纯展示用，删除
- parse_task_plan_text() → 配套函数，删除
- generate_supplement_info_with_llm() → 改用 utils/helpers.py 中的固定模板
- analyze_user_intent_for_paused_session() → 删除
"""

import json
import logging
import re
from typing import AsyncGenerator, Dict, List, Optional

from services.llm import call_llm_api, call_llm_api_stream, extract_core_topic
from utils.text_excerpt import build_prompt_context

logger = logging.getLogger(__name__)


def _resolve_num_pages(num_pages_range) -> int:
    if isinstance(num_pages_range, str):
        if "8-10" in num_pages_range:
            return 9
        if "11-15" in num_pages_range:
            return 13
        if "16-20" in num_pages_range:
            return 18
        if "21-25" in num_pages_range:
            return 23
        m = re.search(r"\d+", num_pages_range)
        if m:
            return max(6, min(30, int(m.group(0))))
        return 10
    try:
        return max(6, min(30, int(num_pages_range)))
    except Exception:
        return 10


def _should_search(supplement_data: dict) -> bool:
    supplement_data = supplement_data or {}
    search_mode = str(supplement_data.get("search_mode", "auto")).strip().lower()
    if search_mode not in ("auto", "on", "off"):
        search_mode = "auto"
    skip_search = bool(supplement_data.get("skip_search", False))
    file_context = supplement_data.get("file_context", "")

    should_search = True
    if search_mode == "off":
        should_search = False
    elif search_mode == "on":
        should_search = True
    else:
        if skip_search or (isinstance(file_context, str) and file_context.strip()):
            should_search = False

    return should_search


def _clean_json_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.IGNORECASE)
    return text.strip()


def _normalize_string_list(items, max_items: int = 6) -> List[str]:
    if not isinstance(items, list):
        return []
    result: List[str] = []
    for item in items:
        s = str(item or "").strip()
        if not s:
            continue
        result.append(s[:120])
        if len(result) >= max_items:
            break
    return result


def _ensure_dict(value) -> Dict:
    return value if isinstance(value, dict) else {}


def build_task_steps(supplement_data: dict, plan: Optional[Dict] = None) -> list:
    """根据补充信息与规划结果生成执行步骤"""
    should_search = _should_search(supplement_data or {})
    default_first = "按规划策略检索证据与数据" if should_search else "梳理已有资料并提取关键证据"
    default_steps = [
        {"id": 1, "text": default_first, "status": "pending"},
        {"id": 2, "text": "构建页面故事线与章节结构", "status": "pending"},
        {"id": 3, "text": "生成逐页大纲并标注重点页", "status": "pending"},
        {"id": 4, "text": "按大纲完成版式设计与内容填充", "status": "pending"},
        {"id": 5, "text": "一致性校对与交付优化", "status": "pending"},
    ]

    raw_steps = (plan or {}).get("steps")
    if not isinstance(raw_steps, list) or not raw_steps:
        return default_steps

    normalized_steps = []
    for i, step in enumerate(raw_steps[:8], 1):
        if isinstance(step, dict):
            text = str(step.get("text") or step.get("name") or "").strip()
        else:
            text = str(step or "").strip()
        if not text:
            continue
        normalized_steps.append({"id": i, "text": text[:120], "status": "pending"})

    return normalized_steps or default_steps


def _build_plan_markdown(plan: Dict) -> str:
    lines = []
    thinking = str(plan.get("thinkingNarrative") or "").strip()
    if thinking:
        lines.append("规划思考：")
        lines.append(thinking)

    core = str(plan.get("coreRequirement") or "").strip()
    if core:
        lines.append(f"核心需求：{core}")

    problem_items = ((plan.get("problemAnalysis") or {}).get("items") or [])[:4]
    if problem_items:
        lines.append("关键问题：")
        lines.extend([f"- {str(x).strip()}" for x in problem_items if str(x).strip()])

    info_items = ((plan.get("informationDimensions") or {}).get("items") or [])[:5]
    if info_items:
        lines.append("信息维度：")
        lines.extend([f"- {str(x).strip()}" for x in info_items if str(x).strip()])

    search_items = ((plan.get("searchStrategy") or {}).get("items") or [])[:5]
    if search_items:
        lines.append("检索策略：")
        lines.extend([f"- {str(x).strip()}" for x in search_items if str(x).strip()])

    return "\n".join(lines).strip()


def build_plan_stream_chunks(plan: Dict, chunk_size: int = 80) -> List[str]:
    """将规划内容拆成可流式推送的文本块。"""
    text = str(plan.get("plan_content") or "").strip()
    if not text:
        text = _build_plan_markdown(plan)
    if not text:
        return []

    chunks: List[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        line = f"{line}\n"
        if len(line) <= chunk_size:
            chunks.append(line)
            continue
        for i in range(0, len(line), chunk_size):
            chunks.append(line[i:i + chunk_size])
    return chunks


async def generate_execution_plan(topic: str, supplement_data: dict) -> Dict:
    """生成结构化执行规划，供面板展示并驱动后续执行链路"""
    supplement_data = supplement_data or {}
    should_search = _should_search(supplement_data)
    num_pages = _resolve_num_pages(supplement_data.get("num_pages", "8-10页"))

    normalized_topic = extract_core_topic(str(supplement_data.get("topic") or "").strip() or (topic or ""))
    audience = supplement_data.get("audience", "")
    modules = supplement_data.get("modules", [])
    style = supplement_data.get("style", "")
    emphasis = supplement_data.get("keywords") or supplement_data.get("emphasis") or ""
    file_context = supplement_data.get("file_context", "")
    file_excerpt = build_prompt_context(file_context, max_chars=1200)

    prompt = f"""你是资深演示策略顾问。请为「{normalized_topic or topic}」生成“可执行的任务规划”，并严格输出 JSON。

输入信息：
- 目标受众：{audience or "未提供"}
- 内容模块：{", ".join(modules) if isinstance(modules, list) and modules else "未提供"}
- 风格偏好：{style or "未提供"}
- 页数目标：{num_pages} 页
- 重点要求：{emphasis or "未提供"}
- 是否需要联网搜索：{"是" if should_search else "否"}
- 已有资料摘要：{file_excerpt or "无"}

输出 JSON Schema：
{{
  "coreRequirement": "一句话概括任务目标",
  "thinkingNarrative": "2-4句思考过程，说明你如何理解需求、先查什么、为什么这么查",
  "problemAnalysis": {{"title": "核心问题识别", "items": ["问题1", "问题2", "..."]}},
  "informationDimensions": {{"title": "信息需求维度", "items": ["维度1", "维度2", "..."]}},
  "searchStrategy": {{"title": "搜索策略", "items": ["策略1", "策略2", "..."]}},
  "recommendedSearchQueries": ["搜索词1", "搜索词2", "..."],
  "outlineDirectives": ["大纲执行约束1", "..."],
  "designDirectives": ["设计执行约束1", "..."],
  "steps": [
    {{"text": "步骤1（必须可执行且可交付）"}},
    {{"text": "步骤2"}},
    {{"text": "步骤3"}},
    {{"text": "步骤4"}},
    {{"text": "步骤5"}}
  ]
}}

规则：
1. 步骤必须体现“先分析再执行”，不能泛化成空话。
2. 若“是否需要联网搜索=否”，recommendedSearchQueries 返回空数组，searchStrategy 聚焦“已有资料校验与补证”。
3. 步骤数 5-7，按真实执行顺序写。
4. 不要输出 markdown，不要解释，只输出 JSON。"""

    fallback = {
        "coreRequirement": f"围绕「{normalized_topic or topic}」构建一份可直接交付的 {num_pages} 页演示稿，确保信息准确且结构清晰。",
        "thinkingNarrative": (
            f"用户想了解「{normalized_topic or topic}」，先要确认它的准确定义与应用边界。"
            "我会先做基础检索建立事实底座，再按功能、场景、使用流程与价值维度补齐证据，"
            "最后把信息压缩成适合演示的页面结构。"
        ),
        "problemAnalysis": {
            "title": "核心问题识别",
            "items": [
                "需要明确受众关注点与决策场景",
                "需要确保关键结论有依据支撑",
                "需要控制页数与信息密度平衡",
            ],
        },
        "informationDimensions": {
            "title": "信息需求维度",
            "items": [
                "背景与现状",
                "核心方案/能力",
                "数据或案例证据",
                "落地路径与价值总结",
            ],
        },
        "searchStrategy": {
            "title": "搜索策略",
            "items": [
                "优先检索权威来源并交叉验证",
                "按模块补齐数据、案例和定义口径",
                "提炼可直接入页的事实与结论",
            ] if should_search else [
                "以用户提供资料为主线拆分章节证据",
                "补齐资料缺口并标注不确定信息",
                "统一术语与结论口径，避免歧义",
            ],
        },
        "recommendedSearchQueries": ([normalized_topic or topic] if should_search else []),
        "outlineDirectives": [
            "目录与正文一一映射，避免跳页",
            "重点页必须包含结论+证据+行动建议",
            f"总页数严格控制在 {num_pages} 页",
        ],
        "designDirectives": [
            "同一章节保持统一版式与视觉层级",
            "每页仅一个主结论，避免信息堆叠",
            "图文比例按信息密度动态调整",
        ],
    }

    try:
        raw = await call_llm_api([
            {"role": "system", "content": "你是任务规划器，只输出合法 JSON。"},
            {"role": "user", "content": prompt},
        ])
        matched = re.search(r"\{[\s\S]*\}", _clean_json_text(raw or ""))
        if matched:
            parsed = json.loads(matched.group(0))
            if isinstance(parsed, dict):
                fallback.update(parsed)
    except Exception as e:
        logger.warning(f"Failed to generate execution plan with LLM: {e}")

    problem_analysis = _ensure_dict(fallback.get("problemAnalysis"))
    info_dimensions = _ensure_dict(fallback.get("informationDimensions"))
    search_strategy = _ensure_dict(fallback.get("searchStrategy"))

    fallback["problemAnalysis"] = {
        "title": str(problem_analysis.get("title") or "核心问题识别")[:30],
        "items": _normalize_string_list(problem_analysis.get("items"), max_items=6),
    }
    fallback["informationDimensions"] = {
        "title": str(info_dimensions.get("title") or "信息需求维度")[:30],
        "items": _normalize_string_list(info_dimensions.get("items"), max_items=6),
    }
    fallback["searchStrategy"] = {
        "title": str(search_strategy.get("title") or "搜索策略")[:30],
        "items": _normalize_string_list(search_strategy.get("items"), max_items=6),
    }
    fallback["recommendedSearchQueries"] = _normalize_string_list(
        fallback.get("recommendedSearchQueries"),
        max_items=8,
    ) if should_search else []
    fallback["outlineDirectives"] = _normalize_string_list(fallback.get("outlineDirectives"), max_items=6)
    fallback["designDirectives"] = _normalize_string_list(fallback.get("designDirectives"), max_items=6)
    fallback["coreRequirement"] = str(fallback.get("coreRequirement") or "").strip()[:240]
    fallback["thinkingNarrative"] = str(fallback.get("thinkingNarrative") or "").strip()[:600]
    fallback["shouldSearch"] = should_search
    fallback["steps"] = build_task_steps(supplement_data, fallback)
    fallback["plan_content"] = _build_plan_markdown(fallback)
    fallback["streamContent"] = ""

    return fallback


async def stream_outline_generation(
    topic: str,
    search_results: list,
    deep_thinking_content: str,
    supplement_data: dict,
    execution_plan: Optional[Dict] = None,
) -> AsyncGenerator[str, None]:
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
    num_pages = _resolve_num_pages(num_pages_range)

    file_context = supplement_data.get("file_context", "")
    file_excerpt = build_prompt_context(file_context)
    plan = execution_plan or {}
    plan_core = str(plan.get("coreRequirement") or "").strip()
    plan_dimensions = ((plan.get("informationDimensions") or {}).get("items") or [])[:6]
    plan_outline_directives = (plan.get("outlineDirectives") or [])[:6]
    plan_design_directives = (plan.get("designDirectives") or [])[:6]

    plan_str = ""
    if plan_core or plan_dimensions or plan_outline_directives or plan_design_directives:
        plan_str = (
            "\n执行规划约束（必须遵循）：\n"
            f"- 核心目标：{plan_core or '无'}\n"
            f"- 信息维度：{'; '.join([str(x) for x in plan_dimensions]) if plan_dimensions else '无'}\n"
            f"- 大纲约束：{'; '.join([str(x) for x in plan_outline_directives]) if plan_outline_directives else '无'}\n"
            f"- 设计约束：{'; '.join([str(x) for x in plan_design_directives]) if plan_design_directives else '无'}\n"
        )

    # 构造上下文内容
    if file_excerpt:
        context_str = f"\n文件内容（主要依据）：\n{file_excerpt}\n{plan_str}"
    else:
        context_str = f"""
搜索结果摘要：
{results_summary}

深度分析内容：
{deep_thinking_content  if deep_thinking_content else '无'}
{plan_str}
"""

    prompt = f"""基于以下信息，为「{topic}」生成PPT大纲目录。

目标受众：{audience}
内容模块：{', '.join(modules) if modules else '自动规划'}
设计风格：{style}
**必须生成的页数：{num_pages}页（严格遵守，不能多也不能少）**

{context_str}

请生成一份**内容详细、覆盖全面、结构合理**的PPT大纲，格式如下：

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

**重要要求**：
1. 页数必须严格为 {num_pages} 页！
2. **必须覆盖文档中的所有章节/关键点，不得遗漏**
3. 若文档存在明确目录/章节标题，需逐一映射到大纲页面
4. 重点页面需包含更详细的要点与数据/结论（如文档中有）
5. **每个内容页至少 3 条要点，重点页建议 4-6 条**
6. 若给出了“执行规划约束”，请优先按约束组织页面结构与重点分配。"""

    try:
        async for chunk in call_llm_api_stream([
            {"role": "system", "content": "你是一个专业的PPT内容策划师，擅长根据搜索结果生成结构化的PPT大纲。请严格按照用户要求的格式和页数输出。"},
            {"role": "user", "content": prompt}
        ]):
            yield chunk
    except Exception as e:
        logger.error(f"Outline generation error: {e}")
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
