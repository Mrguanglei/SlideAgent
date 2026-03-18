"""
PPTAgent PPT 生成服务模块

提供 PPT 生成核心功能
"""

import json
import logging
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, Optional, Dict, List, Tuple

from utils.config import Config
from services.template_presets import build_template_prompt_block

logger = logging.getLogger(__name__)


def create_tool_call(tool_type: str, tool_name: str, status: str, data: dict) -> dict:
    """创建工具调用对象"""
    return {
        "type": tool_type,
        "name": tool_name,
        "status": status,
        "data": data
    }


def parse_num_pages(supplement_data: dict, default: int = 15) -> int:
    """从 supplement_data 中解析页数"""
    if not supplement_data:
        return default
    
    num_pages_range = supplement_data.get("num_pages", "")
    logger.info(f"User selected page range: {num_pages_range}")

    if isinstance(num_pages_range, str):
        if "8-10" in num_pages_range:
            return 10
        elif "11-15" in num_pages_range:
            return 15
        elif "16-20" in num_pages_range:
            return 20
        elif "21-25" in num_pages_range:
            return 25
        else:
            return default
    elif isinstance(num_pages_range, int):
        return num_pages_range
    
    return default


def generate_slide_thinking(slide_count: int, topic: str) -> Optional[str]:
    """生成幻灯片创建后的固定模板思考文字（不调用LLM）"""
    return f"第 {slide_count} 页已完成，正在继续生成下一页..."

_HTML_HINT_RE = re.compile(r"<!DOCTYPE html>|<html\\b|<body\\b", re.IGNORECASE)
_SLIDE_NARRATION_RE = re.compile(
    r"(第\\s*\\d+\\s*页|第\\s*[一二三四五六七八九十]+\\s*页|封面|目录|新增页面|开始\\s*创建|现在开始|接下来|下一页|已完成)",
    re.IGNORECASE,
)

_NOTICE_RE = re.compile(r"<NOTICE>.*?</NOTICE>", re.IGNORECASE | re.DOTALL)
_INLINE_TOOL_JSON_RE = re.compile(
    r"\{[^{}]*(\"message\"|\"progress\"|\"html_file\"|\"next_steps\"|\"details\"|\"error\"|\"errors\")[^{}]*\}",
    re.IGNORECASE | re.DOTALL,
)
_PROGRESS_LINE_RE = re.compile(
    r"^.*(第\\s*\\d+\\s*页已完成|接下来创建第\\s*\\d+\\s*页|Page\\s*\\d+.*inserted|Continue inserting pages).*?$",
    re.IGNORECASE | re.MULTILINE,
)


def _sanitize_agent_text(text: str) -> str:
    if not text:
        return ""
    cleaned = _NOTICE_RE.sub("", text)
    cleaned = _INLINE_TOOL_JSON_RE.sub("", cleaned)
    cleaned = _PROGRESS_LINE_RE.sub("", cleaned)
    cleaned = re.sub(r"\\n{3,}", "\\n\\n", cleaned)
    return cleaned.strip()


def _looks_like_html(text: str) -> bool:
    if not text:
        return False
    return bool(_HTML_HINT_RE.search(text[:4000]))


def _looks_like_slide_narration(text: str) -> bool:
    if not text:
        return False
    snippet = text.strip()[:400]
    return bool(_SLIDE_NARRATION_RE.search(snippet))


def _extract_slide_index_from_path(file_path: str) -> Optional[int]:
    if not file_path:
        return None
    match = re.search(r"(?:slide|page)[_-]?0*(\\d+)", file_path, re.IGNORECASE)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return None
    return None


def _normalize_slide_index(candidate: Optional[int], current: int) -> int:
    if isinstance(candidate, int) and candidate > 0:
        if candidate <= current:
            return current + 1
        return candidate
    return current + 1


def _extract_html_from_tool_args(tool_args: Dict) -> Tuple[str, Optional[str], Optional[int], Optional[str]]:
    if not isinstance(tool_args, dict):
        return "", None, None, None
    html_content = (
        tool_args.get("html", "") or
        tool_args.get("content", "") or
        tool_args.get("html_content", "") or
        tool_args.get("code", "")
    )
    file_path = tool_args.get("file_path") or tool_args.get("path")
    index = tool_args.get("index") or tool_args.get("page") or tool_args.get("page_number")
    description = tool_args.get("action_description") or tool_args.get("description")
    try:
        if index is not None:
            index = int(index)
    except Exception:
        index = None
    return html_content, file_path, index, description


async def run_slide_edit_agent(
    instruction: str,
    existing_slides: List[Dict],  # [{"page_number": 1, "html_content": "..."}]
    workspace_dir: Optional[str] = None,
    powerpoint_type: str = "16:9 Widescreen",
) -> AsyncGenerator[dict, None]:
    """运行 SlideDesign agent 修改已有 PPT 的指定页面"""

    if not Config.DEEPPRESENTER_AVAILABLE:
        yield {"type": "error", "content": "DeepPresenter 模块未加载，无法修改PPT。"}
        return

    try:
        from deeppresenter.agents.slide_design_agent import SlideDesign
        from deeppresenter.agents.tool_executor import AgentEnv
        from deeppresenter.utils.typings import InputRequest, PowerPointType, ConvertType, ChatMessage
        from deeppresenter.utils.config import DeepPresenterConfig

        if workspace_dir:
            workspace = Path(workspace_dir)
            workspace.mkdir(parents=True, exist_ok=True)
        else:
            workspace = Path(tempfile.mkdtemp(prefix="ppt_edit_"))

        # 将现有幻灯片写入工作区，供 agent 读取
        slides_summary = ""
        for slide in sorted(existing_slides, key=lambda s: s.get("page_number", 0)):
            page_num = slide.get("page_number", 0)
            html = slide.get("html_content", "")
            slide_file = workspace / f"slide_{page_num}.html"
            slide_file.write_text(html, encoding="utf-8")
            slides_summary += f"- 第 {page_num} 页：{slide_file}\n"

        md_file = workspace / "manuscript.md"
        md_content = f"""# PPT 修改任务

## 现有幻灯片文件
{slides_summary}

## 修改指令
{instruction}
"""
        md_file.write_text(md_content, encoding="utf-8")

        ppt_type = PowerPointType.WIDE_SCREEN if "16:9" in powerpoint_type else PowerPointType.STANDARD

        # 将所有页面的完整 HTML 嵌入 instruction
        slides_context = ""
        for slide in sorted(existing_slides, key=lambda s: s.get("page_number", 0)):
            page_num = slide.get("page_number", 0)
            html = slide.get("html_content", "") or ""
            slides_context += f"\n### 第 {page_num} 页\n```html\n{html}\n```\n"

        enhanced_instruction = f"""你正在修改一个已有的 PPT，共 {len(existing_slides)} 页。

## 用户修改指令
{instruction}

## 当前所有幻灯片完整 HTML
{slides_context}

⭐ 重要说明：
- PPT 已初始化完毕，直接调用 update_page 修改指定页面即可
- 不要调用 initialize_design（已初始化）
- 修改时必须基于上面提供的原始 HTML，只改用户要求的部分，保留其他所有样式和内容
- 只修改用户要求的页面，不要修改其他页面
- 修改完成后调用 finalize
"""

        input_request = InputRequest(
            instruction=enhanced_instruction,
            attachments=[],
            num_pages=None,
            template=None,
            powerpoint_type=ppt_type,
            convert_type=ConvertType.SLIDE_DESIGN,
        )

        deep_presenter_config = DeepPresenterConfig.load_from_file()

        async with AgentEnv(workspace, deep_presenter_config) as agent_env:
            # 预加载现有幻灯片到 _design_state，使 update_page 可直接使用
            from deeppresenter.tools.html_tools import load_existing_slides
            load_existing_slides(existing_slides, title="PPT编辑", total=len(existing_slides))

            slide_agent = SlideDesign(
                config=deep_presenter_config,
                agent_env=agent_env,
                workspace=workspace,
                language="zh",
                allow_reflection=False,
            )

            updated_pages: Dict[int, str] = {}

            async for message in slide_agent.loop(input_request, str(md_file)):
                if isinstance(message, ChatMessage):
                    content_text = ""
                    if isinstance(message.content, str):
                        content_text = message.content
                    elif isinstance(message.content, list):
                        for block in message.content:
                            if isinstance(block, dict) and block.get("type") == "text":
                                content_text += block.get("text", "")

                    skip_content = False
                    if content_text:
                        content_text = _sanitize_agent_text(content_text)
                        if not content_text:
                            skip_content = True
                        else:
                            skip_patterns = [
                                "<NOTICE>", "File downloaded", "Outcome file", "does not exist",
                                "resolution:", "Todo ", "DeepPresenter running", "File written to",
                                "manuscript.md", "markdown", "playwright", "BrowserType.launch",
                                "chromium", "chrome-headless-shell", "playwright install",
                                "PPT not initialized", "initialize_design", "get_slides_summary",
                                "backend-", "httpx - INFO", "INFO - HTTP Request",
                                "DeprecationWarning", "Tool already exists", "Config file",
                            ]
                            for pattern in skip_patterns:
                                if pattern in content_text:
                                    skip_content = True
                                    break
                            if not skip_content:
                                stripped = content_text.strip()
                                if stripped.startswith("{") and stripped.endswith("}"):
                                    try:
                                        json.loads(stripped)
                                        if any(key in stripped for key in ['"message":', '"details":', '"next_steps":', '"progress":', '"html_file":', '"error":', '"errors":']):
                                            skip_content = True
                                    except Exception:
                                        pass

                    if message.tool_calls:
                        for tc in message.tool_calls:
                            tool_name = tc.function.name if hasattr(tc, 'function') else str(tc)
                            tool_args = tc.function.arguments if hasattr(tc, 'function') else {}
                            if isinstance(tool_args, str):
                                try:
                                    tool_args = json.loads(tool_args)
                                except Exception:
                                    tool_args = {"data": tool_args}

                            tool_name_lower = tool_name.lower()
                            if tool_name_lower == "update_page":
                                html_content, file_path, index, action_description = _extract_html_from_tool_args(tool_args)
                                if not html_content and file_path:
                                    try:
                                        if str(file_path).lower().endswith(".html") and Path(file_path).exists():
                                            html_content = Path(file_path).read_text(encoding="utf-8", errors="ignore")
                                    except Exception:
                                        pass
                                if html_content and index:
                                    updated_pages[int(index)] = html_content
                                    logger.info(f"Updated slide page {index}, HTML length: {len(html_content)}")
                                    yield {
                                        "type": "slide_update",
                                        "page_number": int(index),
                                        "html_content": html_content,
                                        "description": action_description or f"第 {index} 页已更新",
                                    }
                            elif tool_name_lower == "remove_pages":
                                indexes = tool_args.get("indexes", [])
                                action_description = tool_args.get("action_description", "")
                                if indexes:
                                    logger.info(f"Removed slide pages: {indexes}")
                                    yield {
                                        "type": "slide_remove",
                                        "page_numbers": [int(i) for i in indexes],
                                        "description": action_description or f"已删除第 {indexes} 页",
                                    }

                    if content_text and not skip_content:
                        yield {"type": "message", "content": content_text, "role": "assistant"}

            yield {
                "type": "complete",
                "updated_pages": list(updated_pages.keys()),
                "content": f"修改完成！共更新了 {len(updated_pages)} 页。",
            }

    except Exception as e:
        logger.error(f"Error in PPT edit: {e}")
        import traceback
        traceback.print_exc()
        yield {"type": "error", "content": f"修改PPT时出错：{str(e)}"}


async def run_slide_design_agent(
    topic: str,
    outline_content: str,
    search_results: List[Dict],
    deep_thinking_content: str,
    supplement_data: dict,
    num_pages: int,
    powerpoint_type: str = "16:9 Widescreen",
    workspace_dir: Optional[str] = None,
    execution_plan: Optional[Dict] = None,
) -> AsyncGenerator[dict, None]:
    """运行 SlideDesign agent 生成 PPT"""
    
    if not Config.DEEPPRESENTER_AVAILABLE:
        yield {
            "type": "error",
            "content": "DeepPresenter 模块未加载，无法生成PPT。"
        }
        return
    
    try:
        # 导入必要模块
        from deeppresenter.agents.slide_design_agent import SlideDesign
        from deeppresenter.agents.tool_executor import AgentEnv
        from deeppresenter.utils.typings import InputRequest, PowerPointType, ConvertType, ChatMessage
        from deeppresenter.utils.config import DeepPresenterConfig
        
        # 构建 Markdown 内容
        search_summary = ""
        for i, result in enumerate(search_results[:10], 1):
            title = result.get("title", "")
            snippet = result.get("snippet", "")[:200]
            search_summary += f"{i}. {title}\n   {snippet}\n\n"
        
        # 使用传入的 workspace 或创建临时工作空间
        if workspace_dir:
            workspace = Path(workspace_dir)
            workspace.mkdir(parents=True, exist_ok=True)
        else:
            workspace = Path(tempfile.mkdtemp(prefix="ppt_"))
        md_file = workspace / "manuscript.md"

        md_content = f"""# {topic}

## PPT大纲

{outline_content}

## 参考资料

{search_summary}

## 深度分析

{deep_thinking_content[:2000] if deep_thinking_content else '无'}

## 设计限制

- 禁止使用任何图片（包括 `<img>`、`background-image: url(...)`、外链图片、占位符图片）
- 仅使用文字、形状、配色、边框、渐变完成视觉表达
"""
        md_file.write_text(md_content, encoding="utf-8")
        logger.info(f"Created markdown file at: {md_file}")
        
        # 创建 InputRequest
        ppt_type = PowerPointType.WIDE_SCREEN if "16:9" in powerpoint_type else PowerPointType.STANDARD
        
        template_name = supplement_data.get("selected_template") or supplement_data.get("template")
        has_template = bool(str(template_name or "").strip())
        style_pref = "" if has_template else supplement_data.get("style", "")
        color_pref = "" if has_template else (supplement_data.get("color_preference") or supplement_data.get("theme_color") or "")
        template_prompt_block = build_template_prompt_block(template_name)
        preference_lines = []
        if style_pref:
            preference_lines.append(f"设计风格偏好：{style_pref}")
        if color_pref:
            preference_lines.append(f"配色偏好：{color_pref}")
        preference_block = "\n".join(preference_lines)
        if preference_block:
            preference_block = f"\n{preference_block}\n"

        plan = execution_plan or {}
        plan_outline_directives = plan.get("outlineDirectives") or []
        plan_design_directives = plan.get("designDirectives") or []
        plan_core_requirement = str(plan.get("coreRequirement") or "").strip()
        plan_block = ""
        if plan_core_requirement or plan_outline_directives or plan_design_directives:
            outline_directives_text = "\n".join(
                [f"- {str(item).strip()}" for item in plan_outline_directives if str(item).strip()]
            ) or "- 无"
            design_directives_text = "\n".join(
                [f"- {str(item).strip()}" for item in plan_design_directives if str(item).strip()]
            ) or "- 无"
            plan_block = f"""
执行规划约束（必须遵守）：
- 核心目标：{plan_core_requirement or "无"}
- 大纲执行约束：
{outline_directives_text}
- 设计执行约束：
{design_directives_text}
"""

        template_block = f"\n{template_prompt_block}\n" if template_prompt_block else ""

        enhanced_instruction = f"""{topic}{preference_block}{template_block}

⭐⭐⭐ 重要：请严格按照以下已生成的 PPT 大纲来创建幻灯片！⭐⭐⭐

{outline_content}
{plan_block}

⭐⭐⭐ 请严格遵循上述大纲结构，不要重新规划内容！⭐⭐⭐
- 每一页的标题和要点已经在大纲中明确列出
- 你的任务是：基于大纲内容，设计精美的 HTML 幻灯片
- 不要修改大纲中的页面数量和结构
- 不要添加大纲中没有的页面
- 内容必须详细、全面覆盖文档关键点
- 若页面为重点内容页，请提供更完整的要点与说明
- 每个内容页至少 3 条要点，重点页建议 4-6 条
- 专注于视觉设计和排版，让内容更加美观
- 禁止使用任何图片：不要输出 `<img>`，不要使用 `background-image: url(...)`"""
        
        input_request = InputRequest(
            instruction=enhanced_instruction,
            attachments=[],
            num_pages=str(num_pages) if num_pages else None,
            template=None,
            powerpoint_type=ppt_type,
            convert_type=ConvertType.SLIDE_DESIGN,
        )
        logger.info(f"InputRequest created with enhanced instruction")
        
        # 加载 DeepPresenter 配置对象
        deep_presenter_config = DeepPresenterConfig.load_from_file()
        
        # 创建 AgentEnv 和 SlideDesign agent
        async with AgentEnv(workspace, deep_presenter_config) as agent_env:
            slide_agent = SlideDesign(
                config=deep_presenter_config,
                agent_env=agent_env,
                workspace=workspace,
                language="zh",
                allow_reflection=False,
            )
            
            # 运行并流式返回消息
            slide_count = 0
            
            async for message in slide_agent.loop(input_request, str(md_file)):
                if isinstance(message, ChatMessage):
                    # 提取文本内容
                    content_text = ""
                    if isinstance(message.content, str):
                        content_text = message.content
                    elif isinstance(message.content, list):
                        for block in message.content:
                            if isinstance(block, dict) and block.get("type") == "text":
                                content_text += block.get("text", "")
                    
                    # 过滤不需要的消息
                    skip_content = False
                    if content_text:
                        content_text = _sanitize_agent_text(content_text)
                        if not content_text:
                            skip_content = True
                        
                        # 过滤特定模式的消息
                        skip_patterns = [
                            "<NOTICE>",
                            "File downloaded",
                            "Outcome file",
                            "does not exist",
                            "resolution:",
                            "Todo ",
                            "DeepPresenter running",
                            "File written to",
                            "manuscript.md",
                            "markdown",
                            "playwright",
                            "BrowserType.launch",
                            "chromium",
                            "chrome-headless-shell",
                            "playwright install",
                            "PPT not initialized",
                            "initialize_design",
                            "get_slides_summary",
                            "backend-",
                            "httpx - INFO",
                            "INFO - HTTP Request",
                            "DeprecationWarning",
                            "Tool already exists",
                            "Config file",
                        ]
                        for pattern in skip_patterns:
                            if pattern in content_text:
                                skip_content = True
                                break

                        # 过滤 MCP 工具的 JSON 响应消息
                        if not skip_content:
                            stripped = content_text.strip()
                            if stripped.startswith("{") and stripped.endswith("}"):
                                try:
                                    json.loads(stripped)
                                    # 如果是有效的 JSON，检查是否包含 MCP 工具响应的特征字段
                                    if any(key in stripped for key in ['"message":', '"details":', '"next_steps":', '"progress":', '"html_file":', '"error":', '"errors":']):
                                        skip_content = True
                                except:
                                    pass
                    
                    # 处理工具调用
                    has_slide_tool_call = False
                    if message.tool_calls:
                        for tc in message.tool_calls:
                            tool_name = tc.function.name if hasattr(tc, 'function') else str(tc)
                            tool_args = tc.function.arguments if hasattr(tc, 'function') else {}

                            if isinstance(tool_args, str):
                                try:
                                    tool_args = json.loads(tool_args)
                                except:
                                    tool_args = {"data": tool_args}

                            logger.info(f"Tool call: {tool_name}")

                            tool_name_lower = tool_name.lower()
                            is_slide_tool = tool_name_lower in {"insert_page", "update_page", "write_file"} or (
                                "insert" in tool_name_lower and "page" in tool_name_lower
                            )
                            if is_slide_tool:
                                has_slide_tool_call = True

                            if is_slide_tool:
                                html_content, file_path, index, action_description = _extract_html_from_tool_args(tool_args)

                                if tool_name_lower == "write_file":
                                    # write_file 可能写入非 HTML 文件，需严格过滤
                                    if not html_content:
                                        try:
                                            if file_path and str(file_path).lower().endswith(".html") and Path(file_path).exists():
                                                html_content = Path(file_path).read_text(encoding="utf-8", errors="ignore")
                                        except Exception:
                                            html_content = ""
                                    if not _looks_like_html(html_content):
                                        continue
                                else:
                                    if not html_content:
                                        html_content = str(tool_args)

                                if not html_content:
                                    continue

                                if index is None and file_path:
                                    index = _extract_slide_index_from_path(str(file_path))

                                slide_count = _normalize_slide_index(index, slide_count)

                                logger.info(f"Created slide {slide_count}, HTML length: {len(html_content)}")

                                # 提取页面描述
                                page_description = action_description or (content_text[:100] if content_text else f"第 {slide_count} 页")

                                yield {
                                    "type": "slide",
                                    "slide_count": slide_count,
                                    "html_content": html_content,
                                    "description": page_description
                                }

                                # 生成 AI 思考文字
                                thinking = generate_slide_thinking(slide_count, topic)
                                if thinking:
                                    yield {
                                        "type": "thinking",
                                        "content": thinking
                                    }

                            elif tool_name_lower == "finalize":
                                logger.info("Detected finalize tool call - PPT generation will complete soon")

                    # 发送文本消息
                    if content_text and not skip_content:
                        # 避免与幻灯片进度类文案重复，保留关键说明类文本
                        if has_slide_tool_call and _looks_like_slide_narration(content_text):
                            continue
                        yield {
                            "type": "message",
                            "content": content_text,
                            "role": message.role.value if hasattr(message.role, 'value') else str(message.role)
                        }
            
            # 完成消息
            yield {
                "type": "complete",
                "slide_count": slide_count,
                "content": f"PPT生成完成！共 {slide_count} 页。"
            }
    
    except Exception as e:
        logger.error(f"Error in PPT generation: {e}")
        import traceback
        traceback.print_exc()
        yield {
            "type": "error",
            "content": f"生成PPT时出错：{str(e)}"
        }
