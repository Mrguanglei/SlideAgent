"""
PPTAgent PPT 生成服务模块

提供 PPT 生成核心功能
"""

import json
import logging
import tempfile
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, Optional, Dict, List

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


async def run_slide_design_agent(
    topic: str,
    outline_content: str,
    search_results: List[Dict],
    deep_thinking_content: str,
    supplement_data: dict,
    num_pages: int,
    powerpoint_type: str = "16:9 Widescreen",
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
        
        # 创建临时工作空间
        workspace = Path(tempfile.mkdtemp(prefix="ppt_"))
        md_file = workspace / "manuscript.md"
        
        md_content = f"""# {topic}

## PPT大纲

{outline_content}

## 参考资料

{search_summary}

## 深度分析

{deep_thinking_content[:2000] if deep_thinking_content else '无'}
"""
        md_file.write_text(md_content, encoding="utf-8")
        logger.info(f"Created markdown file at: {md_file}")
        
        # 创建 InputRequest
        ppt_type = PowerPointType.WIDE_SCREEN if "16:9" in powerpoint_type else PowerPointType.STANDARD
        
        # 将大纲内容直接嵌入到 instruction 中
        enhanced_instruction = f"""{topic}

⭐⭐⭐ 重要：请严格按照以下已生成的 PPT 大纲来创建幻灯片！⭐⭐⭐

{outline_content}

⭐⭐⭐ 请严格遵循上述大纲结构，不要重新规划内容！⭐⭐⭐
- 每一页的标题和要点已经在大纲中明确列出
- 你的任务是：基于大纲内容，设计精美的 HTML 幻灯片
- 不要修改大纲中的页面数量和结构
- 不要添加大纲中没有的页面
- 专注于视觉设计和排版，让内容更加美观
"""
        
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
                            
                            # 检测幻灯片生成工具
                            if "insert" in tool_name.lower() or "page" in tool_name.lower():
                                slide_count += 1
                                html_content = ""
                                if isinstance(tool_args, dict):
                                    html_content = (
                                        tool_args.get("html", "") or
                                        tool_args.get("content", "") or
                                        tool_args.get("html_content", "") or
                                        tool_args.get("code", "")
                                    )
                                
                                if not html_content:
                                    html_content = str(tool_args)
                                
                                logger.info(f"Created slide {slide_count}, HTML length: {len(html_content)}")
                                
                                # 提取页面描述
                                page_description = content_text[:100] if content_text else f"第 {slide_count} 页"
                                
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
                            
                            elif tool_name.lower() == "finalize":
                                logger.info("Detected finalize tool call - PPT generation will complete soon")
                    
                    # 发送文本消息
                    if content_text and not skip_content:
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
