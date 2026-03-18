"""
模板风格预设

把前端选择的模板名称转换为后端可执行的风格约束，
用于在生成 HTML 幻灯片时尽量贴近指定模板视觉表现。
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Optional


TemplatePreset = Dict[str, Any]


TEMPLATE_PRESETS: Dict[str, TemplatePreset] = {
    "AI医疗创新": {
        "style": "简约现代",
        "color_preference": "白底 + 浅灰底衬托，主色为医疗科技蓝绿色，强调色克制使用",
        "summary": "科技医疗风，明亮留白，理性专业，强调创新感与可信度。",
        "cover_layout": "封面大标题居左或居中，配合干净的医疗/实验室氛围大图，整体通透。",
        "content_layout": "内容页以大标题 + 2~4 个信息模块为主，模块边界轻、卡片感弱，重排版轻装饰。",
        "typography": "标题偏粗，正文简洁，数字和关键词需要更突出。",
        "visual_rules": [
            "优先使用白色、浅灰、医疗蓝绿等清洁感配色",
            "减少厚重阴影和复杂渐变，保持高级感与科技感",
            "适合使用数据卡片、医疗图示、流程概览等现代布局",
            "强调专业可信，不要做成互联网海报风或过于花哨",
        ],
    },
    "中国医疗创新": {
        "style": "专业商务",
        "color_preference": "浅蓝、深蓝与白色为主，局部可加入稳重的青色强调",
        "summary": "政策研究与行业报告风格，稳重、正式、偏汇报感。",
        "cover_layout": "封面建议左侧标题、右侧辅助信息，视觉重心稳，适合报告型开场。",
        "content_layout": "内容页多采用双栏、三栏、数据概览和政策解读模块，信息层次清楚。",
        "typography": "标题要正式、克制，正文清晰可读，适合汇报和行业分析。",
        "visual_rules": [
            "整体要像医疗行业研究报告，不要像营销海报",
            "可以使用数据摘要条、政策要点框、趋势分析卡片",
            "颜色对比要稳，强调色控制在少量重点数据上",
            "适合加入中国市场、产业趋势、创新路径等报告型结构",
        ],
    },
    "战略规划": {
        "style": "专业商务",
        "color_preference": "深紫、白色、深灰为主，少量高亮强调战略重点",
        "summary": "高层战略汇报风格，成熟、稳重、清晰、有决策感。",
        "cover_layout": "封面强调大标题和一句战略口号，整体偏高管汇报视觉。",
        "content_layout": "适合使用矩阵、分层卡片、章节页、关键路径页等经典咨询式版式。",
        "typography": "标题强势，正文精炼，适合呈现框架与结论。",
        "visual_rules": [
            "页面结构要清晰，像咨询公司战略汇报",
            "避免花哨装饰，突出逻辑与重点结论",
            "适合模块化信息展示与章节节奏",
            "关键结论、数字、行动项需要一眼可见",
        ],
    },
    "商业转型": {
        "style": "专业商务",
        "color_preference": "深灰、深蓝、白色为主，整体稳重现代",
        "summary": "企业转型与业务升级风格，适合讲变革路径、业务重塑和战略升级。",
        "cover_layout": "封面可采用深色背景叠加商务场景图，标题突出转型主题。",
        "content_layout": "适合采用路线拆解、转型支柱、能力升级等咨询式页面。",
        "typography": "标题需要有力量感，正文保持专业和简洁。",
        "visual_rules": [
            "风格更像企业咨询汇报，不是营销提案",
            "适合深色背景与简洁白字，但必须保证清晰可读",
            "用结构化布局讲清楚现状、挑战、路径、成果",
            "突出关键动作、阶段目标、价值收益",
        ],
    },
    "律师事务所": {
        "style": "专业商务",
        "color_preference": "深棕、金棕、白色或米白色，体现权威与高端",
        "summary": "法律与专业服务风格，讲究权威、秩序与可信赖感。",
        "cover_layout": "封面适合左对齐标题 + 高级建筑/律政背景图，整体高端正式。",
        "content_layout": "多用清晰分区、规整卡片、案例与服务模块，版式要稳定。",
        "typography": "标题正式，适合高端专业服务机构的语气。",
        "visual_rules": [
            "避免互联网感和活泼色彩，整体要沉稳",
            "适合使用细线条、低饱和背景、整齐分栏",
            "重点突出专业能力、服务领域、案例经验",
            "不要用过多圆润可爱的元素",
        ],
    },
    "企业卓越": {
        "style": "专业商务",
        "color_preference": "橙色、白色、深灰色组合，现代而有能量",
        "summary": "企业品牌与组织能力展示风格，偏现代商务、带一点增长感。",
        "cover_layout": "封面可以大标题配城市/办公场景图，视觉热度比普通商务模板稍高。",
        "content_layout": "适合能力模块、成果数字、文化价值观、业务板块页面。",
        "typography": "标题简洁直接，强调品牌与增长。",
        "visual_rules": [
            "整体更现代、更明快，但仍然要商务专业",
            "橙色只做强调，不要满屏高饱和",
            "适合用数字成绩、里程碑、能力标签来增强说服力",
            "保持企业展示感，不要做成科技极客风",
        ],
    },
    "研究报告": {
        "style": "学术风格",
        "color_preference": "灰白、深灰、蓝灰为主，克制、理性、研究感强",
        "summary": "学术研报风格，内容导向，强调结论、证据与清晰结构。",
        "cover_layout": "封面可简洁大标题配研究类背景图，整体偏论文答辩/研究论坛风格。",
        "content_layout": "内容页适合用结论先行、数据支持、研究发现、图表分析等布局。",
        "typography": "标题清晰，正文略正式，适合较强的信息密度。",
        "visual_rules": [
            "学术感要明显，减少装饰性视觉",
            "适合使用图表、研究要点、方法说明、结论总结",
            "信息密度可以略高，但必须保持层次清楚",
            "不要做成营销推广风或商业海报风",
        ],
    },
    "酒店介绍": {
        "style": "创意设计",
        "color_preference": "暖灰、深棕、米色、白色，营造高端酒店质感",
        "summary": "高端品牌展示风格，偏体验感与空间美学。",
        "cover_layout": "封面应突出视觉氛围，大图、留白和高级排版很重要。",
        "content_layout": "内容页适合图文混排、体验亮点、空间展示、服务特色模块。",
        "typography": "标题更有设计感，正文保持精炼。",
        "visual_rules": [
            "要像高端品牌画册，不要像普通企业汇报",
            "重视图片与留白的氛围感，避免过满的内容块",
            "适合使用大图、局部放大、体验关键词",
            "强调质感、优雅、空间美学与服务体验",
        ],
    },
}


def normalize_template_name(template_name: Optional[str]) -> str:
    return str(template_name or "").strip()


def get_template_preset(template_name: Optional[str]) -> Optional[TemplatePreset]:
    normalized = normalize_template_name(template_name)
    if not normalized:
        return None
    preset = TEMPLATE_PRESETS.get(normalized)
    return deepcopy(preset) if preset else None


def apply_template_to_supplement_data(
    supplement_data: Optional[Dict[str, Any]],
    template_name: Optional[str],
) -> Dict[str, Any]:
    data = deepcopy(supplement_data or {})
    normalized = normalize_template_name(template_name)
    if not normalized:
        return data

    preset = get_template_preset(normalized)
    data["selected_template"] = normalized

    if preset:
        data["template_style"] = preset.get("style")
        data["template_color_preference"] = preset.get("color_preference")
        data["template_summary"] = preset.get("summary", "")
    return data


def build_template_prompt_block(template_name: Optional[str]) -> str:
    normalized = normalize_template_name(template_name)
    if not normalized:
        return ""

    preset = get_template_preset(normalized)
    if not preset:
        return f"""
模板风格要求（必须尽量贴近）：
- 当前选择模板：{normalized}
- 请将该模板视为主要风格参考，保证整套 PPT 的封面、配色、标题样式、内容页结构保持一致
- 不要随机更换主色或主版式
- 如果没有足够信息，请优先输出稳健、统一、现代的商务演示风格
""".strip()

    visual_rules = "\n".join(
        f"- {rule}" for rule in preset.get("visual_rules", []) if str(rule).strip()
    ) or "- 保持统一、稳定的模板风格"

    return f"""
模板风格要求（必须尽量贴近）：
- 当前选择模板：{normalized}
- 模板风格概述：{preset.get("summary", "")}
- 建议设计风格：{preset.get("style", "")}
- 建议配色方向：{preset.get("color_preference", "")}
- 封面布局要求：{preset.get("cover_layout", "")}
- 内容页布局要求：{preset.get("content_layout", "")}
- 排版要求：{preset.get("typography", "")}
- 具体视觉规则：
{visual_rules}
- 整套 PPT 必须保持统一模板语言，不要每页都换风格
""".strip()
