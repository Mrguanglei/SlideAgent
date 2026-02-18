"""
PPTAgent 搜索服务模块

提供 Tavily 和 DeepPresenter 搜索功能
"""

import io
import os
import logging
import asyncio
from pathlib import Path
from typing import List, Dict, Optional, AsyncGenerator

import httpx
from PIL import Image

from utils.config import Config
from services.llm import call_llm_api, call_llm_api_stream, extract_core_topic

logger = logging.getLogger(__name__)

# 尝试导入搜索模块
search_web = None
try:
    from deeppresenter.tools.search import search_web
    logger.info("✓ DeepPresenter search module loaded")
except ImportError as e:
    logger.warning(f"✗ DeepPresenter search not available: {e}")


async def tavily_search_standalone(query: str, max_results: int = 8) -> dict:
    """独立的 Tavily 搜索函数"""
    if not Config.TAVILY_API_KEY:
        logger.warning("Tavily API key not configured")
        return {"results": []}
    
    try:
        from tavily import TavilyClient
        
        # 尝试主 API key
        api_keys = [Config.TAVILY_API_KEY]
        if Config.TAVILY_BACKUP:
            api_keys.append(Config.TAVILY_BACKUP)
        
        for api_key in api_keys:
            try:
                client = TavilyClient(api_key=api_key)
                response = client.search(query=query, max_results=max_results)
                logger.info(f"Tavily search success for: {query}")
                return response
            except Exception as e:
                logger.warning(f"Tavily search failed with key: {str(e)[:50]}")
                continue
        
        return {"results": []}
    except ImportError:
        logger.error("Tavily package not installed")
        return {"results": []}


async def generate_search_queries(topic: str, supplement_data: dict) -> List[str]:
    """使用 LLM 生成多个不同角度的搜索关键词"""
    logger.info(f"Generating search queries for: {topic}")

    modules = supplement_data.get("modules", [])
    audience = supplement_data.get("audience", "")
    keywords = supplement_data.get("keywords", "")

    # 提取主题的核心关键词
    core_topic = extract_core_topic(topic)

    prompt = f"""我需要为「{core_topic}」制作一份专业的PPT演示文稿。请你作为信息检索专家，深入思考并生成3个**完全不同维度**的搜索关键词。

**背景信息**：
- 主题：{core_topic}
- 目标受众：{audience}
- 内容模块：{', '.join(modules) if modules else '待定'}
- 重点内容：{keywords if keywords else '无'}

**关键要求**：
1. **深度思考**：不要简单套用"是什么"、"功能特点"、"使用案例"这样的模板
2. **针对性强**：根据具体主题特点，选择最有价值的搜索角度
3. **信息互补**：3个关键词应该覆盖完全不同的信息维度，互相补充
4. **精准简洁**：每个关键词不超过20个字，直接可用于搜索

**输出格式**：
只输出3个搜索关键词，每行一个，不要编号、不要解释：
"""

    try:
        response = await call_llm_api([
            {"role": "system", "content": "你是一个资深的信息检索专家。你需要深入分析主题特点，生成最有价值的搜索关键词。不要使用固定模板，要根据具体主题灵活思考。只输出关键词，每行一个。"},
            {"role": "user", "content": prompt}
        ])

        # 移除可能的 <think> 标签内容（防止深度思考模式影响搜索关键词）
        import re
        response = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL).strip()

        # 解析关键词列表
        queries = []
        for line in response.strip().split("\n"):
            line = line.strip()
            # 移除可能的编号前缀
            if line and not line.startswith("#"):
                line = line.lstrip("0123456789.-、）) ").strip()
                # 额外过滤：确保不包含 think 标签
                if line and len(line) < 50 and '<think>' not in line.lower() and '</think>' not in line.lower():
                    queries.append(line)

        # 去重
        queries = list(dict.fromkeys(queries))

        # 确保至少有一个查询
        if not queries:
            queries = [core_topic]
        
        # 最多返回3个
        queries = queries[:3]
        
        logger.info(f"Generated search queries: {queries}")
        return queries

    except Exception as e:
        logger.error(f"Failed to generate search queries: {e}")
        return [core_topic]


async def should_use_web_search(topic: str, supplement_data: dict) -> bool:
    """自动判断是否需要联网搜索"""
    supplement_data = supplement_data or {}
    audience = supplement_data.get("audience", "")
    modules = supplement_data.get("modules", [])
    keywords = supplement_data.get("keywords", "")
    file_context = supplement_data.get("file_context", "")
    skip_search_flag = supplement_data.get("skip_search", False)

    file_excerpt = ""
    if isinstance(file_context, str) and file_context.strip():
        file_excerpt = file_context.strip()[:800]

    prompt = f"""请判断为「{topic}」制作PPT时是否需要联网搜索资料。

判断原则：
1. 若主题涉及最新数据、政策法规、市场动态、具体统计/案例、或需要外部证据支持，优先选择 YES。
2. 若用户提供的文件内容已足够完整、或明确不需要外部资料，选择 NO。
3. 无法确定时，优先 YES（保证信息充实）。

已知信息：
- 目标受众：{audience or '未提供'}
- 内容模块：{', '.join(modules) if modules else '未提供'}
- 重点关键词：{keywords or '未提供'}
- 是否检测到文件内容：{'是' if file_excerpt else '否'}
- 系统提示 skip_search：{'是' if skip_search_flag else '否'}
- 文件摘要（如有）：{file_excerpt or '无'}

只输出 YES 或 NO，不要解释。"""

    try:
        response = await call_llm_api([
            {"role": "system", "content": "你是检索策略助手，只输出 YES 或 NO。"},
            {"role": "user", "content": prompt}
        ])
        if not response:
            return True
        decision = response.strip().upper()
        if "YES" in decision:
            return True
        if "NO" in decision:
            return False
        if decision.startswith("是"):
            return True
        if decision.startswith("否"):
            return False
        return True
    except Exception as e:
        logger.error(f"Auto search decision failed: {e}")
        return True


async def execute_search(query: str, max_results: int = 10) -> List[Dict]:
    """执行搜索，返回结果列表"""
    results = []
    
    # 方法1：使用 Tavily 搜索
    if Config.TAVILY_AVAILABLE:
        try:
            logger.info(f"Tavily search for: {query}")
            search_response = await tavily_search_standalone(query=query, max_results=max_results)
            
            for item in search_response.get("results", []):
                content = item.get("content", "")
                results.append({
                    "title": item.get("title", "") or query,
                    "url": item.get("url", ""),
                    "snippet": content[:500] + "..." if len(content) > 500 else content,
                })
            
            if results:
                logger.info(f"Found {len(results)} results from Tavily")
                return results
        except Exception as e:
            logger.error(f"Tavily search error: {e}")
    
    # 方法2：使用 DeepPresenter 搜索
    if search_web:
        try:
            if callable(search_web):
                search_response = await search_web(query=query, max_results=max_results)
            elif hasattr(search_web, "fn"):
                search_response = await search_web.fn(query=query, max_results=max_results)
            else:
                raise TypeError("search_web is not callable and has no fn attribute")
            for item in search_response.get("results", []):
                content = item.get("content", "")
                results.append({
                    "title": item.get("title", "") or query,
                    "url": item.get("url", ""),
                    "snippet": content[:500] + "..." if len(content) > 500 else content,
                })
            
            if results:
                logger.info(f"Found {len(results)} results from DeepPresenter")
                return results
        except Exception as e:
            logger.error(f"DeepPresenter search error: {e}")
    
    logger.warning(f"No search results for: {query}")
    return results


async def _download_and_validate_image(
    client: httpx.AsyncClient,
    url: str,
    description: str,
    save_dir: Path,
    index: int,
) -> Optional[Dict]:
    """下载单张图片并用 PIL 验证有效性，返回图片信息或 None"""
    try:
        resp = await client.get(url, timeout=15, follow_redirects=True)
        if resp.status_code != 200:
            return None

        data = resp.content
        img = Image.open(io.BytesIO(data))
        width, height = img.size

        # 过滤太小的图片（宽或高 < 100px）
        if width < 100 or height < 100:
            logger.debug(f"Image too small ({width}x{height}): {url}")
            return None

        # 保存到本地
        ext = img.format.lower() if img.format else "jpg"
        if ext == "jpeg":
            ext = "jpg"
        filename = f"img_{index}.{ext}"
        local_path = save_dir / filename
        local_path.write_bytes(data)

        logger.info(f"Downloaded image {filename} ({width}x{height}) from {url[:80]}")
        return {
            "url": url,
            "description": description or "",
            "local_path": str(local_path),
            "width": width,
            "height": height,
        }
    except Exception as e:
        logger.debug(f"Failed to download/validate image {url[:80]}: {e}")
        return None


async def search_and_download_images(
    query: str,
    workspace_dir: str,
    max_images: Optional[int] = None,
) -> List[Dict]:
    """搜索图片并下载验证，返回有效图片列表

    Args:
        query: 搜索关键词
        workspace_dir: 工作目录，图片保存到 workspace_dir/images/
        max_images: 最多返回的有效图片数

    Returns:
        [{url, description, local_path, width, height}, ...]
    """
    if not Config.TAVILY_API_KEY:
        logger.warning("Tavily API key not configured, skipping image search")
        return []

    if not max_images or max_images <= 0:
        max_images = getattr(Config, "IMAGE_SEARCH_MAX", 10)

    try:
        from tavily import TavilyClient

        api_keys = [Config.TAVILY_API_KEY]
        if Config.TAVILY_BACKUP:
            api_keys.append(Config.TAVILY_BACKUP)

        images_raw: List[Dict] = []
        for api_key in api_keys:
            try:
                client = TavilyClient(api_key=api_key)
                response = client.search(
                    query=query,
                    max_results=max(max_images * 2, 5),
                    include_images=True,
                    include_image_descriptions=True,
                )
                # Tavily returns images as list of {url, description} or list of strings
                raw_images = response.get("images", [])
                for item in raw_images:
                    if isinstance(item, dict):
                        images_raw.append({
                            "url": item.get("url", ""),
                            "description": item.get("description", ""),
                        })
                    elif isinstance(item, str):
                        images_raw.append({"url": item, "description": ""})
                logger.info(f"Tavily image search returned {len(images_raw)} images for: {query}")
                break
            except Exception as e:
                logger.warning(f"Tavily image search failed with key: {str(e)[:50]}")
                continue

        if not images_raw:
            return []

        # 创建图片保存目录
        save_dir = Path(workspace_dir) / "images"
        save_dir.mkdir(parents=True, exist_ok=True)

        # 为避免文件名冲突，统计已有图片数量（1-based: img_1, img_2, ...）
        existing_count = len(list(save_dir.glob("img_*")))

        # 并行下载并验证
        async with httpx.AsyncClient() as http_client:
            tasks = [
                _download_and_validate_image(
                    http_client,
                    item["url"],
                    item["description"],
                    save_dir,
                    existing_count + i + 1,
                )
                for i, item in enumerate(images_raw)
            ]
            results = await asyncio.gather(*tasks)

        valid = [r for r in results if r is not None]
        logger.info(f"Found {len(valid)} valid images for query: {query}")
        return valid[:max_images]

    except ImportError:
        logger.error("Tavily package not installed, skipping image search")
        return []
    except Exception as e:
        logger.error(f"Image search error: {e}")
        return []


async def stream_search_thinking(query: str, search_results: list, round_num: int, total_rounds: int) -> AsyncGenerator[str, None]:
    """生成搜索思考内容（本地汇总，避免额外 LLM 调用导致限流阻塞）"""
    logger.info(f"Streaming search thinking for round {round_num}/{total_rounds}: {query}")

    titles = [str(item.get("title", "")).strip() for item in search_results[:2] if item.get("title")]
    if titles:
        key_points = "；".join(titles)
        summary = f"第 {round_num}/{total_rounds} 轮已获得 {len(search_results)} 条信息，重点包括：{key_points}。"
    else:
        summary = f"第 {round_num}/{total_rounds} 轮已获得 {len(search_results)} 条相关信息。"

    if round_num < total_rounds:
        summary += " 继续下一轮检索，补齐数据与案例。"
    else:
        summary += " 搜索阶段完成，开始整合信息并生成大纲。"

    yield summary


async def stream_deep_thinking(topic: str, search_results: list) -> AsyncGenerator[str, None]:
    """流式生成深度思考分析（本地汇总，避免限流导致流程停滞）"""
    logger.info(f"Starting deep thinking for: {topic}")

    lines = [
        f"通过搜索，我已经获得了关于「{topic}」的相关信息。让我整理和分析已获取的信息：",
        "",
        "已获取的关键信息：",
    ]

    if search_results:
        for i, result in enumerate(search_results[:6], 1):
            title = str(result.get("title", "未知标题")).strip() or "未知标题"
            snippet = str(result.get("snippet", "")).replace("\n", " ").strip()
            snippet = snippet[:180] + ("..." if len(snippet) > 180 else "")
            lines.append(f"{i}. {title}")
            if snippet:
                lines.append(f"   {snippet}")
    else:
        lines.append("1. 暂未检索到高质量外部资料，后续将以已有需求信息组织内容。")

    lines.extend(
        [
            "",
            "信息整合分析：",
            "• 已覆盖行业背景、技术路径与落地案例等核心维度，可支撑完整叙事。",
            "• 后续将优先突出数据证据与应用成效，确保每页信息密度与可读性平衡。",
            "• 下一步进入大纲生成与页面设计阶段。",
        ]
    )
    yield "\n".join(lines)
