"""
HTML幻灯片生成工具

工具接口：
- think: 内部思考和规划（对用户不可见）
- initialize_design: 初始化PPT设计
- insert_page: 插入HTML页面
- update_page: 修改已有页面
- remove_pages: 删除页面
- get_slides_summary: 获取幻灯片摘要
- finalize: 完成生成
"""

import json
from pathlib import Path

# 全局状态管理（每个 workspace 独立）
_design_state = {
    "initialized": False,
    "slide_name": None,
    "title": None,
    "description": None,
    "width": 1280,
    "height": 720,
    "slide_num": 0,
    "slides": [],
    "workspace": None,
    "edit_mode": False,  # 编辑模式下 initialize_design 不清空已有幻灯片
}


def think(thought_content: str) -> str:
    _ = thought_content
    return "Thinking recorded. This content is internal and not visible to the user."


def initialize_design(
    slide_name: str,
    title: str,
    description: str,
    slide_num: int,
    width: int = 1280,
    height: int = 720,
) -> dict:
    global _design_state

    workspace = Path(_design_state.get("workspace") or "slides")
    workspace.mkdir(parents=True, exist_ok=True)

    # 编辑模式下保留已有幻灯片，不重置
    if _design_state.get("edit_mode"):
        _design_state.update({
            "initialized": True,
            "slide_name": slide_name,
            "title": title,
            "description": description,
            "width": width,
            "height": height,
            "workspace": str(workspace.absolute()),
        })
        return {
            "message": f"PPT '{title}' re-initialized in edit mode (existing slides preserved)",
            "details": {
                "slide_name": slide_name,
                "title": title,
                "slide_num": len(_design_state["slides"]),
                "dimensions": f"{width}x{height}",
                "workspace": str(workspace.absolute()),
            },
            "next_steps": "Use update_page to modify existing pages.",
        }

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
        "next_steps": f"Now you can start inserting pages (1 to {slide_num}) using the insert_page tool.",
    }


def insert_page(index: int, html: str, action_description: str) -> dict:
    global _design_state

    if not _design_state["initialized"]:
        return {"error": "PPT not initialized. Please call initialize_design first."}

    if index < 1 or index > _design_state["slide_num"] + 1:
        return {"error": f"Invalid index {index}. Must be between 1 and {_design_state['slide_num'] + 1}"}

    if not html.strip().startswith("<!DOCTYPE html>"):
        return {"error": "HTML must start with <!DOCTYPE html>."}

    insert_pos = index - 1
    slide_data = {"index": index, "html": html, "description": action_description}

    if insert_pos >= len(_design_state["slides"]):
        _design_state["slides"].append(slide_data)
    else:
        _design_state["slides"].insert(insert_pos, slide_data)

    for i, slide in enumerate(_design_state["slides"]):
        slide["index"] = i + 1

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


def update_page(index: int, html: str, action_description: str) -> dict:
    global _design_state

    if not _design_state["initialized"]:
        return {"error": "PPT not initialized. Please call initialize_design first."}

    if index < 1 or index > len(_design_state["slides"]):
        return {"error": f"Invalid index {index}. Page does not exist."}

    _design_state["slides"][index - 1]["html"] = html
    _design_state["slides"][index - 1]["description"] = action_description

    workspace = Path(_design_state["workspace"])
    html_file = workspace / f"slide_{index:02d}.html"
    html_file.write_text(html, encoding="utf-8")

    return {
        "message": f"Page {index} updated successfully: {action_description}",
        "html_file": str(html_file.absolute()),
    }


def remove_pages(indexes: list, action_description: str) -> dict:
    global _design_state

    if not _design_state["initialized"]:
        return {"error": "PPT not initialized. Please call initialize_design first."}

    for idx in indexes:
        if idx < 1 or idx > len(_design_state["slides"]):
            return {"error": f"Invalid index {idx}. Page does not exist."}

    for idx in sorted(indexes, reverse=True):
        del _design_state["slides"][idx - 1]
        workspace = Path(_design_state["workspace"])
        html_file = workspace / f"slide_{idx:02d}.html"
        if html_file.exists():
            html_file.unlink()

    for i, slide in enumerate(_design_state["slides"]):
        slide["index"] = i + 1

    return {
        "message": f"Deleted {len(indexes)} page(s): {action_description}",
        "remaining_pages": len(_design_state["slides"]),
        "deleted_indexes": indexes,
    }


def get_slides_summary() -> dict:
    global _design_state

    if not _design_state["initialized"]:
        return {"error": "PPT not initialized. Please call initialize_design first."}

    return {
        "title": _design_state["title"],
        "description": _design_state["description"],
        "total_pages": len(_design_state["slides"]),
        "planned_pages": _design_state["slide_num"],
        "workspace": _design_state["workspace"],
        "pages": [
            {"index": s["index"], "description": s["description"], "html_length": len(s["html"])}
            for s in _design_state["slides"]
        ],
    }


def finalize(outcome: str = None, agent_name: str = "") -> dict:
    global _design_state

    if not _design_state["initialized"]:
        return {"error": "PPT not initialized. Please call initialize_design first."}

    if len(_design_state["slides"]) == 0:
        return {"error": "No slides generated. Please insert at least one page."}

    final_outcome = outcome or _design_state["workspace"]

    result = {
        "message": "PPT generation completed successfully!",
        "title": _design_state["title"],
        "total_pages": len(_design_state["slides"]),
        "workspace": _design_state["workspace"],
        "outcome": final_outcome,
        "slides": [
            {
                "index": slide["index"],
                "description": slide["description"],
                "html_file": str(Path(_design_state["workspace"]) / f"slide_{slide['index']:02d}.html"),
            }
            for slide in _design_state["slides"]
        ],
    }

    metadata_file = Path(_design_state["workspace"]) / "metadata.json"
    metadata_file.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

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


def set_workspace(workspace: str):
    """在 agent 启动时设置工作目录"""
    global _design_state
    _design_state["workspace"] = workspace


def load_existing_slides(slides: list, title: str = "PPT", total: int = None):
    """将已有幻灯片加载到 _design_state，使 update_page 可以直接使用。
    slides: [{"page_number": 1, "html_content": "..."}]
    """
    global _design_state
    slide_list = [
        {"index": s["page_number"], "html": s["html_content"], "description": f"第 {s['page_number']} 页"}
        for s in sorted(slides, key=lambda x: x["page_number"])
    ]
    _design_state.update({
        "initialized": True,
        "edit_mode": True,
        "slide_name": "edit",
        "title": title,
        "description": "编辑模式",
        "width": 1280,
        "height": 720,
        "slide_num": total or len(slide_list),
        "slides": slide_list,
    })


# ==================== Tool Registry ====================

TOOL_REGISTRY = {
    "think": think,
    "initialize_design": initialize_design,
    "insert_page": insert_page,
    "update_page": update_page,
    "remove_pages": remove_pages,
    "get_slides_summary": get_slides_summary,
    "finalize": finalize,
}

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "think",
            "description": "内部深度思考工具，用于规划和分析。输出对用户不可见。",
            "parameters": {
                "type": "object",
                "properties": {
                    "thought_content": {"type": "string", "description": "完整的思考内容"}
                },
                "required": ["thought_content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "initialize_design",
            "description": "初始化PPT设计，必须在插入页面之前调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "slide_name": {"type": "string", "description": "幻灯片文件名（不含扩展名）"},
                    "title": {"type": "string", "description": "PPT标题"},
                    "description": {"type": "string", "description": "PPT简要描述，包括设计风格"},
                    "slide_num": {"type": "integer", "description": "计划生成的总页数"},
                    "width": {"type": "integer", "description": "页面宽度，默认1280", "default": 1280},
                    "height": {"type": "integer", "description": "页面高度，默认720", "default": 720},
                },
                "required": ["slide_name", "title", "description", "slide_num"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "insert_page",
            "description": "插入一页HTML幻灯片。HTML必须以<!DOCTYPE html>开头，尺寸固定1280x720px。",
            "parameters": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer", "description": "插入位置页码（从1开始）"},
                    "html": {"type": "string", "description": "完整HTML代码，必须包含<!DOCTYPE html>、<head>和<body>"},
                    "action_description": {"type": "string", "description": "对这一页内容的简要描述"},
                },
                "required": ["index", "html", "action_description"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_page",
            "description": "修改已存在的HTML页面。",
            "parameters": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer", "description": "要修改的页码（从1开始）"},
                    "html": {"type": "string", "description": "修改后的完整HTML代码"},
                    "action_description": {"type": "string", "description": "修改的简要描述"},
                },
                "required": ["index", "html", "action_description"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remove_pages",
            "description": "删除指定的HTML页面。",
            "parameters": {
                "type": "object",
                "properties": {
                    "indexes": {"type": "array", "items": {"type": "integer"}, "description": "要删除的页码列表（从1开始）"},
                    "action_description": {"type": "string", "description": "删除操作的简要描述"},
                },
                "required": ["indexes", "action_description"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_slides_summary",
            "description": "获取当前所有幻灯片的摘要信息。",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finalize",
            "description": "完成PPT生成，返回生成结果。所有页面插入完毕后调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "outcome": {"type": "string", "description": "输出路径（可选）"},
                    "agent_name": {"type": "string", "description": "Agent名称（可选）"},
                },
                "required": [],
            },
        },
    },
]
