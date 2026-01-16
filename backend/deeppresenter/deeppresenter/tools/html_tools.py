"""
智谱清言风格的HTML幻灯片生成工具

这个模块提供了类似智谱清言的工具接口：
- think: 内部思考和规划（对用户不可见）
- initialize_design: 初始化PPT设计
- insert_page: 插入HTML页面
- update_page: 修改已有页面
- remove_pages: 删除页面
"""

import json
from pathlib import Path

from appcore import mcp

# 全局状态管理
_design_state = {
    "initialized": False,
    "slide_name": None,
    "title": None,
    "description": None,
    "width": 1280,
    "height": 720,
    "slide_num": 0,
    "slides": [],  # 存储所有生成的HTML页面
    "workspace": None,
}


@mcp.tool()
def think(thought_content: str) -> str:
    """
    ⚠️ 内部深度思考工具 - 这不是走形式！必须进行真实的深度规划！

    这个工具的输出对用户不可见，但你必须在其中进行真实的深度思考和规划。
    在调用 initialize_design 或 insert_page 之前，**必须使用这个工具按照完整模板进行规划**。

    前端显示"正在思考"时，你必须真正在进行以下完整的规划流程！

    ## 📋 必须遵循的完整规划模板

    **每次调用此工具时，你必须按照以下结构进行完整、详细的思考和规划：**

    ### 一、需求分析

    #### 核心主题
    - 用户需求：[详细描述用户的具体需求]
    - 核心主题：[提炼出的核心主题]
    - 情感基调：[正式/活泼/专业/复古等]

    #### 内容范围
    - 时间跨度：[如果适用，从xx到xx]
    - 主要内容：[列出主要涵盖的内容领域]
    - 关键节点：[列出必须包含的关键信息点]

    #### 用户特殊要求
    - 页数要求：[xx页左右]
    - 风格要求：[正式/简约/中国风/现代等]
    - 配色偏好：[红色/金色/深蓝等，或用户指定]
    - 视觉元素：[时间轴/地图/图表/图片等]

    ---

    ### 二、视觉风格设计

    #### 整体风格
    - 设计风格：[商务/复古/现代/活泼等]
    - 情感氛围：[庄重/活泼/专业/轻松等]
    - 视觉语言：[简约大气/华丽精致/科技未来等]

    #### 配色方案选择
    **从预设配色组中选择一个（必须严格遵守）：**
    - 暖色现代（背景：#F4F1E9 主色：#15857A 强调色：#FF6A3B）
    - 暖色现代（背景：#111111 主色：#15857A 强调色：#FF6A3B）
    - 暖色现代（背景：#111111 主色：#7C3D5E 强调色：#FF7E5E）
    - 冷色现代（背景：#FEFEFE 主色：#44B54B 强调色：#1399FF）
    - 冷色现代（背景：#09325E 主色：#FFFFFF 强调色：#7DE545）
    - 冷色现代（背景：#FEFEFE 主色：#1284BA 强调色：#FF862F）
    - 冷色现代（背景：#FEFEFE 主色：#133EFF 强调色：#00CD82）
    - 深色矿物（背景：#162235 主色：#FFFFFF 强调色：#37DCF2）
    - 深色矿物（背景：#193328 主色：#FFFFFF 强调色：#E7E950）
    - 柔和中性（背景：#F7F3E6 主色：#E7F177 强调色：#106188）
    - 柔和中性（背景：#EBDCEF 主色：#73593C 强调色：#B13DC6）
    - 柔和中性（背景：#8B9558 主色：#262626 强调色：#E1DE2D）
    - 极简主义（背景：#F3F1ED 主色：#000000 强调色：#D6C096）
    - 极简主义（背景：#FFFFFF 主色：#000000 强调色：#A6C40D）
    - 极简主义（背景：#F3F1ED 主色：#393939 强调色：#FFFFFF）
    - 暖色复古（背景：#F4EEEA 主色：#882F1C 强调色：#FEE79B）
    - 暖色复古（背景：#F4F1E9 主色：#2A4A3A 强调色：#C89F62）
    - 暖色复古（背景：#554737 主色：#FFFFFF 强调色：#66D4FF）

    **最终选择**：[配色组名称]
    - 背景色：#[HEX代码]
    - 主色：#[HEX代码]  （≥80% 使用比例）
    - 强调色：#[HEX代码]  （≤5% 使用比例）

    #### 字体方案选择
    **根据风格选择字体方案：**
    - 商务风格（中文：MiSans；英文：Source Code Pro + Roboto Flex）
    - 复古精致（中文：Source Han Serif SC + MiSans；英文：Spectral + Quattrocento Sans）
    - 活力未来（中文：抖音黑体Bold + MiSans；英文：BioRhyme + Archivo 或 Press Start 2P + Archivo）

    **最终选择**：[字体方案名称]
    - 标题字体：[具体字体名称]
    - 正文字体：[具体字体名称]
    - 数字字体：[具体字体名称]

    ---

    ### 三、页面结构规划

    #### 总页数规划
    - 封面页：1页
    - 目录/引言页：1页（必须有）
    - 正文内容页：xx页
    - 结束/展望页：1页
    - **总计**：xx页

    #### 每页详细规划

    **第1页：封面页**
    - 页面类型：封面页
    - 主标题：[标题内容]
    - 副标题：[副标题内容]
    - 布局方式：[居中（推荐）/左对齐]
    - 背景处理：[渐变背景 / 背景图片+半透明遮罩]
    - 装饰元素：[圆形装饰 / 线条装饰 / 图标装饰]
    - 配色应用：背景色 + 主色（标题）+ 强调色（关键数据）
    - 字体：标题使用[字体名称] [50-70px]，副标题使用[字体名称] [20px]

    **第2页：目录页（必须）**
    - 页面类型：目录页
    - 标题：[目录/Contents/大纲等]
    - 内容结构：章节1、章节2、章节3...
    - 布局方式：[垂直列表 / 卡片网格 / 双栏布局]
    - 图标使用：为每个章节配图标

    **第3页-第N-1页：内容页**
    每一页都要规划：
    - 页面类型：内容页 / 章节页 / 图表页
    - 标题：[页面标题]
    - 核心内容：要点1、要点2、要点3（不超过20字/要点）
    - 视觉元素：[Material Icons 图标 / 图片 / 图表类型]
    - 布局方式：[左文右图 / 卡片网格 / 上下布局]

    **第N页：结束页**
    - 主标题：[感谢观看/谢谢等]
    - 副标题：[展望/联系方式等]
    - 布局方式：居中
    - 装饰元素：[与封面页呼应]

    ---

    ### 四、HTML/CSS技术实现要点

    #### 页面尺寸规范（严格遵守）
    - **封面页**：width: 1280px; height: 720px; （固定高度）
    - **内容页**：width: 1280px; min-height: 720px; （最小高度）
    - **重要**：内容必须尽量控制在720px高度内，避免溢出
    - **重要**：使用 flex 布局确保内容填充页面高度

    #### 布局技术选择
    - **主容器**：使用 display: flex; flex-direction: column;
    - **内容区**：使用 flex-grow: 1; 填充剩余空间
    - **对齐方式**：使用 flexbox 的 justify-content 和 align-items
    - **避免**：过度使用嵌套的 div 和复杂的网格系统

    #### 遵循瑞士平面设计原则
    - **统一性**：将视口视为一个单一、连贯的画布
    - **负空间**：使用空白作为分隔内容的主要元素
    - **排版**：层次结构通过字体大小/粗细建立
    - **避免**：不要创建内部视觉边界，元素应浮动在全局背景上

    #### 颜色应用规范
    - **背景色**：仅用于页面背景，所有页面统一
    - **主色**：用于标题、页眉、框架、内容块（≥80%）
    - **强调色**：极少使用（≤5%），仅用于高亮关键点

    #### 字体大小规范
    - **封面标题**：50-70px
    - **封面副标题**：20px
    - **页面标题**：40px（标题区高度85px）
    - **主要文本**：24px
    - **最小文本**：20px

    #### 必须引入的资源
    - Material Icons: <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
    - Google Fonts: 根据字体方案引入
    - Chart.js（如需图表）: <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

    #### 封面页技术要点
    - 使用 height: 100vh 或 height: 720px 确保固定高度
    - 使用 display: flex; justify-content: center; align-items: center; 实现居中
    - 背景使用 linear-gradient 或 background-image + 半透明遮罩
    - 装饰元素使用 position: absolute 定位

    #### 内容页技术要点
    - 标题区：固定高度85px，不添加上 padding
    - 主内容区：使用 flex-grow: 1 填充剩余空间
    - 卡片/模块：使用 box-shadow 和 border-radius 增强视觉效果
    - 图标：必须使用 Material Icons，配合主色或强调色

    ---

    ### 五、质量检查清单

    #### 全局一致性检查
    - [ ] 配色方案统一（所有页面使用同一组配色）
    - [ ] 字体方案统一（标题、正文、数字字体保持一致）
    - [ ] 布局风格协调
    - [ ] 图标风格统一（都使用 Material Icons）

    #### 禁止事项
    - ❌ 禁止使用 Reveal.js
    - ❌ 禁止创建图形化时间线结构（使用图片代替）
    - ❌ 禁止在代码中绘制地图
    - ❌ 禁止使用 SVG 绘制复杂图形（除非用户明确要求）
    - ❌ 禁止纯白色背景 + 纯黑色文字的简单页面

    ---

    ### 六、下一步行动计划

    **完成以上所有分析后，明确下一步行动：**
    1. 调用 initialize_design 创建PPT框架
    2. 逐页调用 insert_page 插入HTML页面（从第1页到第N页）
    3. 每页生成后向用户报告进度

    ---

    **以上是你必须完整、详细思考的内容！不要跳过任何步骤！**

    Args:
        thought_content (str): 你的完整思考内容，必须按照上述模板逐项填写

    Returns:
        str: 确认消息
    """
    # 思考内容不需要持久化，仅用于AI的规划过程
    # 这里可以选择性地记录思考内容用于调试
    _ = thought_content  # 保留参数以符合函数签名
    return "Thinking recorded. This content is internal and not visible to the user."


@mcp.tool()
def initialize_design(
    slide_name: str,
    title: str,
    description: str,
    slide_num: int,
    width: int = 1280,
    height: int = 720,
) -> dict:
    """
    初始化PPT设计 - 设置HTML幻灯片的基本属性。

    这是生成PPT的第一步，必须在插入页面之前调用。

    Args:
        slide_name (str): HTML幻灯片文件名（不包含扩展名）
        title (str): PPT标题
        description (str): PPT简要描述和概要，应包括设计风格
        slide_num (int): 计划生成的总页数
        width (int): 页面宽度，默认 1280px
        height (int): 页面高度，默认 720px

    Returns:
        dict: 包含初始化状态和下一步指引的消息
    """
    global _design_state

    # 创建工作目录
    workspace = Path("slides")
    workspace.mkdir(exist_ok=True)

    _design_state.update({
        "initialized": True,
        "slide_name": slide_name,
        "title": title,
        "description": description,
        "width": width,
        "height": height,
        "slide_num": slide_num,
        "slides": [],
        "workspace": str(workspace.absolute()),
    })

    return {
        "message": f"PPT '{title}' initialized successfully",
        "details": {
            "slide_name": slide_name,
            "title": title,
            "description": description,
            "slide_num": slide_num,
            "dimensions": f"{width}x{height}",
            "workspace": str(workspace.absolute()),
        },
        "next_steps": f"Now you can start inserting pages (1 to {slide_num}) using the insert_page tool. Each page should be complete HTML with proper styling.",
    }


@mcp.tool()
def insert_page(
    index: int,
    html: str,
    action_description: str,
) -> dict:
    """
    插入一页HTML幻灯片。

    Args:
        index (int): 插入位置的页码（从1开始）
        html (str): 完整的HTML代码，必须包含 <!DOCTYPE html>、<head> 和 <body>
                   - 必须设置固定尺寸（1280px × 720px）
                   - 必须包含完整的样式定义
                   - 图片路径必须是绝对路径或有效的URL
        action_description (str): 对这一页内容的简要描述

    Returns:
        dict: 包含成功消息和当前进度的信息
    """
    global _design_state

    if not _design_state["initialized"]:
        return {
            "error": "PPT not initialized. Please call initialize_design first."
        }

    if index < 1 or index > _design_state["slide_num"] + 1:
        return {
            "error": f"Invalid index {index}. Must be between 1 and {_design_state['slide_num'] + 1}"
        }

    # 验证HTML包含必要的元素
    if not html.strip().startswith("<!DOCTYPE html>"):
        return {
            "error": "HTML must start with <!DOCTYPE html>. Please provide complete HTML document."
        }

    # 插入到指定位置（index-1 因为列表从0开始）
    insert_pos = index - 1
    slide_data = {
        "index": index,
        "html": html,
        "description": action_description,
    }

    if insert_pos >= len(_design_state["slides"]):
        # 追加到末尾
        _design_state["slides"].append(slide_data)
    else:
        # 插入到指定位置
        _design_state["slides"].insert(insert_pos, slide_data)

    # 重新编号
    for i, slide in enumerate(_design_state["slides"]):
        slide["index"] = i + 1

    # 保存HTML文件
    workspace = Path(_design_state["workspace"])
    html_file = workspace / f"slide_{index:02d}.html"
    html_file.write_text(html, encoding="utf-8")

    current_count = len(_design_state["slides"])
    progress = f"{current_count}/{_design_state['slide_num']}"

    return {
        "message": f"Page {index} inserted successfully: {action_description}",
        "progress": progress,
        "html_file": str(html_file.absolute()),
        "next_steps": (
            f"Continue inserting pages ({progress} completed)"
            if current_count < _design_state["slide_num"]
            else "All pages completed. You can now finalize the presentation."
        ),
    }


@mcp.tool()
def update_page(
    index: int,
    html: str,
    action_description: str,
) -> dict:
    """
    修改已存在的HTML页面。

    Args:
        index (int): 要修改的页码（从1开始）
        html (str): 修改后的完整HTML代码
        action_description (str): 修改的简要描述

    Returns:
        dict: 包含成功消息的信息
    """
    global _design_state

    if not _design_state["initialized"]:
        return {
            "error": "PPT not initialized. Please call initialize_design first."
        }

    if index < 1 or index > len(_design_state["slides"]):
        return {
            "error": f"Invalid index {index}. Page does not exist."
        }

    # 更新指定页面
    _design_state["slides"][index - 1]["html"] = html
    _design_state["slides"][index - 1]["description"] = action_description

    # 保存HTML文件
    workspace = Path(_design_state["workspace"])
    html_file = workspace / f"slide_{index:02d}.html"
    html_file.write_text(html, encoding="utf-8")

    return {
        "message": f"Page {index} updated successfully: {action_description}",
        "html_file": str(html_file.absolute()),
    }


@mcp.tool()
def remove_pages(
    indexes: list[int],
    action_description: str,
) -> dict:
    """
    删除指定的HTML页面。

    Args:
        indexes (list[int]): 要删除的页码列表（从1开始）
        action_description (str): 删除操作的简要描述

    Returns:
        dict: 包含成功消息的信息
    """
    global _design_state

    if not _design_state["initialized"]:
        return {
            "error": "PPT not initialized. Please call initialize_design first."
        }

    # 验证所有索引
    for idx in indexes:
        if idx < 1 or idx > len(_design_state["slides"]):
            return {
                "error": f"Invalid index {idx}. Page does not exist."
            }

    # 按降序排序，从后往前删除，避免索引变化
    for idx in sorted(indexes, reverse=True):
        del _design_state["slides"][idx - 1]

        # 删除HTML文件
        workspace = Path(_design_state["workspace"])
        html_file = workspace / f"slide_{idx:02d}.html"
        if html_file.exists():
            html_file.unlink()

    # 重新编号
    for i, slide in enumerate(_design_state["slides"]):
        slide["index"] = i + 1

    remaining = len(_design_state["slides"])

    return {
        "message": f"Deleted {len(indexes)} page(s): {action_description}",
        "remaining_pages": remaining,
        "deleted_indexes": indexes,
    }


@mcp.tool()
def get_slides_summary() -> dict:
    """
    获取当前所有幻灯片的摘要信息。

    Returns:
        dict: 包含所有幻灯片的概览
    """
    global _design_state

    if not _design_state["initialized"]:
        return {
            "error": "PPT not initialized. Please call initialize_design first."
        }

    summary = {
        "title": _design_state["title"],
        "description": _design_state["description"],
        "total_pages": len(_design_state["slides"]),
        "planned_pages": _design_state["slide_num"],
        "workspace": _design_state["workspace"],
        "pages": [
            {
                "index": slide["index"],
                "description": slide["description"],
                "html_length": len(slide["html"]),
            }
            for slide in _design_state["slides"]
        ],
    }

    return summary


@mcp.tool()
def finalize(outcome: str = None, agent_name: str = "") -> dict:
    """
    完成PPT生成，返回生成结果。

    Args:
        outcome (str, optional): 输出路径，通常是slides目录的路径。如果不提供，将使用当前workspace路径。
        agent_name (str, optional): Agent名称（兼容参数，不使用）。

    Returns:
        dict: 包含所有生成的幻灯片信息，包括outcome路径
    """
    global _design_state

    if not _design_state["initialized"]:
        return {
            "error": "PPT not initialized. Please call initialize_design first."
        }

    if len(_design_state["slides"]) == 0:
        return {
            "error": "No slides generated. Please insert at least one page."
        }

    # 使用提供的outcome或默认使用workspace路径
    final_outcome = outcome or _design_state["workspace"]

    # 准备返回结果
    result = {
        "message": "PPT generation completed successfully!",
        "title": _design_state["title"],
        "total_pages": len(_design_state["slides"]),
        "workspace": _design_state["workspace"],
        "outcome": final_outcome,  # 添加outcome字段
        "slides": [
            {
                "index": slide["index"],
                "description": slide["description"],
                "html_file": str(
                    Path(_design_state["workspace"]) / f"slide_{slide['index']:02d}.html"
                ),
            }
            for slide in _design_state["slides"]
        ],
    }

    # 保存元数据
    metadata_file = Path(_design_state["workspace"]) / "metadata.json"
    metadata = {
        "title": _design_state["title"],
        "description": _design_state["description"],
        "slide_num": len(_design_state["slides"]),
        "dimensions": {
            "width": _design_state["width"],
            "height": _design_state["height"],
        },
        "outcome": final_outcome,
        "slides": result["slides"],
    }
    metadata_file.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")

    # 保存outcome信息，以便Agent可以获取
    result["outcome"] = final_outcome

    # 重置状态
    _design_state.update({
        "initialized": False,
        "slide_name": None,
        "title": None,
        "description": None,
        "width": 1280,
        "height": 720,
        "slide_num": 0,
        "slides": [],
        "workspace": None,
    })

    return result
