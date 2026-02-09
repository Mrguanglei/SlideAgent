"""
PPTAgent PPT 生成服务模块

提供 PPT 生成核心功能
"""

import base64
import json
import logging
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, Optional, Dict, List, Tuple

from utils.config import Config
from services.llm import call_llm_api

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


async def generate_slide_thinking(slide_count: int, topic: str) -> Optional[str]:
    """生成幻灯片创建后的 AI 思考文字"""
    try:
        thinking_prompt = f"""你刚刚完成了第 {slide_count} 页幻灯片的创建。
请用一句话简短说明下一步要做什么，例如：
- "第1页封面已创建成功。现在开始创建第2页 - 产品概述..."
- "第3页核心功能已完成。接下来创建第4页 - 应用场景..."

当前主题：{topic}
当前页码：{slide_count}

请直接输出一句话，不要添加任何前缀或后缀。"""
        
        thinking_response = await call_llm_api([
            {"role": "system", "content": "你是一个 PPT 生成助手，请用简短的一句话说明下一步要做什么。"},
            {"role": "user", "content": thinking_prompt}
        ])
        
        return thinking_response.strip() if thinking_response else None
    except Exception as e:
        logger.warning(f"Failed to generate AI thinking: {e}")
        return None


def _image_to_data_uri(local_path: str) -> Optional[str]:
    """将本地图片文件转为 base64 data URI"""
    try:
        path = Path(local_path)
        if not path.exists():
            return None
        data = path.read_bytes()
        ext = path.suffix.lower().lstrip(".")
        mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
                "webp": "image/webp", "gif": "image/gif"}.get(ext, "image/jpeg")
        b64 = base64.b64encode(data).decode()
        return f"data:{mime};base64,{b64}"
    except Exception as e:
        logger.warning(f"Failed to convert image to data URI: {local_path}: {e}")
        return None


_BACKGROUND_EXCLUDE_KEYWORDS = [
    "chart", "graph", "table", "diagram", "infographic", "schema", "workflow",
    "screenshot", "dashboard", "ui", "icon", "logo", "banner",
    "图表", "表格", "示意", "流程图", "架构", "数据", "截图", "界面", "仪表盘",
]

_HTML_HINT_RE = re.compile(r"<!DOCTYPE html>|<html\\b|<body\\b", re.IGNORECASE)
_SLIDE_NARRATION_RE = re.compile(
    r"(第\\s*\\d+\\s*页|第\\s*[一二三四五六七八九十]+\\s*页|封面|目录|新增页面|开始\\s*创建|现在开始|接下来|下一页|已完成)",
    re.IGNORECASE,
)


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


def _is_background_candidate(img: Dict) -> bool:
    """判断图片是否适合作为整页背景（启发式）"""
    desc = (img.get("description") or "").lower()
    url = (img.get("url") or "").lower()
    text = f"{desc} {url}"

    if any(keyword in text for keyword in _BACKGROUND_EXCLUDE_KEYWORDS):
        return False

    width = img.get("width") or 0
    height = img.get("height") or 0
    if not width or not height:
        return False

    if width < 900 or height < 500:
        return False

    ratio = width / height if height else 0
    if ratio < 1.2 or ratio > 2.2:
        return False

    return True


def replace_image_placeholders(html: str, image_results: List[Dict]) -> str:
    """替换 HTML 中的图片占位符和假 URL 为本地图片的 base64 data URI

    处理策略（按优先级）：
    1. 替换 {{img_N}} 占位符为对应图片的 base64
    2. 替换 example.com 等虚假 URL 为可用图片的 base64
    3. 替换其他无法访问的外部图片 URL 为可用图片的 base64
    """
    if not image_results:
        return html

    # 构建占位符 → data_uri 映射
    placeholder_map = {}
    data_uris = []
    for i, img in enumerate(image_results):
        local_path = img.get("local_path", "")
        data_uri = _image_to_data_uri(local_path)
        if data_uri:
            placeholder_map[f"{{{{img_{i + 1}}}}}"] = data_uri
            data_uris.append(data_uri)

    if not data_uris:
        return html

    # 第一步：替换占位符 {{img_N}}
    for placeholder, data_uri in placeholder_map.items():
        html = html.replace(placeholder, data_uri)

    # 第二步：替换假 URL（example.com 等明显的占位地址）
    fake_url_pattern = re.compile(
        r'src="(https?://(?:example\.com|placeholder\.com|via\.placeholder\.com|placehold\.it|picsum\.photos|dummyimage\.com)[^"]*)"'
    )
    used_idx = 0
    def _replace_fake(match):
        nonlocal used_idx
        if used_idx < len(data_uris):
            replacement = data_uris[used_idx]
            used_idx += 1
            return f'src="{replacement}"'
        return match.group(0)

    html = fake_url_pattern.sub(_replace_fake, html)

    return html


async def run_slide_design_agent(
    topic: str,
    outline_content: str,
    search_results: List[Dict],
    deep_thinking_content: str,
    supplement_data: dict,
    num_pages: int,
    powerpoint_type: str = "16:9 Widescreen",
    image_results: Optional[List[Dict]] = None,
    workspace_dir: Optional[str] = None,
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
        from deeppresenter.agents.slide_design import SlideDesign
        from deeppresenter.agents.env import AgentEnv
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

        # 构建图片素材章节（使用占位符）
        image_section = ""
        if image_results:
            image_section = "\n## 可用图片素材\n以下图片已验证可用。在 HTML 的 <img> 标签中，使用 {{img_N}} 作为 src 的值。\n\n"

            indexed_images = list(enumerate(image_results, 1))
            background_candidates = [(i, img) for i, img in indexed_images if _is_background_candidate(img)]
            content_images = [(i, img) for i, img in indexed_images if not _is_background_candidate(img)]

            image_section += "### 背景候选（仅用于封面/整页背景）\n"
            if background_candidates:
                for i, img in background_candidates:
                    desc = img.get("description", "图片") or "图片"
                    w = img.get("width", 0)
                    h = img.get("height", 0)
                    image_section += f"{i}. {{{{img_{i}}}}} — {desc} ({w}×{h})\n"
            else:
                image_section += "无\n"

            image_section += "\n### 内容配图（用于插图/示意，不作背景）\n"
            if content_images:
                for i, img in content_images:
                    desc = img.get("description", "图片") or "图片"
                    w = img.get("width", 0)
                    h = img.get("height", 0)
                    image_section += f"{i}. {{{{img_{i}}}}} — {desc} ({w}×{h})\n"
            else:
                image_section += "无\n"

            image_section += "\n示例：<img src=\"{{img_1}}\" alt=\"描述\">\n\n"
            logger.info(f"Added {len(image_results)} image placeholders to markdown")

        md_content = f"""# {topic}

## PPT大纲

{outline_content}

## 参考资料

{search_summary}

## 深度分析

{deep_thinking_content[:2000] if deep_thinking_content else '无'}
{image_section}"""
        md_file.write_text(md_content, encoding="utf-8")
        logger.info(f"Created markdown file at: {md_file}")
        
        # 创建 InputRequest
        ppt_type = PowerPointType.WIDE_SCREEN if "16:9" in powerpoint_type else PowerPointType.STANDARD
        
        # 将大纲内容直接嵌入到 instruction 中
        image_instruction = ""
        if image_results:
            image_instruction = """
⚠️ 重要：markdown 文件中提供了可用图片素材，使用 {{img_N}} 占位符引用。
- 必须使用 <img> 标签引用图片，例如：<img src="{{img_1}}" alt="描述">
- ⛔ 严禁使用 CSS background-image: url() 引用图片（导出 PPTX 时会丢失）
- 背景优先使用纯色或渐变；只有在“背景候选”列表中存在合适图片时才可作为背景
- “内容配图”仅用于插图/示意，禁止用于整页背景
- 封面背景图请用绝对定位 <img> + 半透明遮罩 div 实现
- 严禁编造任何图片 URL，只能使用 {{img_N}} 占位符
- 内容页可在相关内容旁配图以增强视觉效果
"""

        enhanced_instruction = f"""{topic}

⭐⭐⭐ 重要：请严格按照以下已生成的 PPT 大纲来创建幻灯片！⭐⭐⭐

{outline_content}

⭐⭐⭐ 请严格遵循上述大纲结构，不要重新规划内容！⭐⭐⭐
- 每一页的标题和要点已经在大纲中明确列出
- 你的任务是：基于大纲内容，设计精美的 HTML 幻灯片
- 不要修改大纲中的页面数量和结构
- 不要添加大纲中没有的页面
- 专注于视觉设计和排版，让内容更加美观
{image_instruction}"""
        
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
                        # 过滤特定模式的消息
                        skip_patterns = ["File downloaded", "Outcome file", "does not exist", "resolution:", "Todo ", "DeepPresenter running"]
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
                                    if any(key in stripped for key in ['"message":', '"details":', '"next_steps":', '"progress":', '"html_file":']):
                                        skip_content = True
                                        logger.info(f"Skipping MCP tool JSON response: {stripped[:100]}...")
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
                                thinking = await generate_slide_thinking(slide_count, topic)
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
