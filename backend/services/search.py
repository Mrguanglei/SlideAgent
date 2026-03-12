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


async def generate_search_queries(
    topic: str,
    supplement_data: dict,
    execution_plan: Optional[Dict] = None,
) -> List[str]:
    """使用 LLM 生成多个不同角度的搜索关键词"""
    logger.info(f"Generating search queries for: {topic}")

    modules = supplement_data.get("modules", [])
    audience = supplement_data.get("audience", "")
    keywords = supplement_data.get("keywords", "")
    execution_plan = execution_plan or {}
    plan_dimensions = (execution_plan.get("informationDimensions") or {}).get("items", [])
    plan_strategy = (execution_plan.get("searchStrategy") or {}).get("items", [])
    seeded_queries = execution_plan.get("recommendedSearchQueries") or execution_plan.get("recommended_search_queries") or []

    # 若规划已明确查询词，优先严格按规划执行
    if isinstance(seeded_queries, list):
        normalized_seeded = []
        for item in seeded_queries:
            q = str(item or "").strip()
            if q:
                normalized_seeded.append(q[:80])
        normalized_seeded = list(dict.fromkeys(normalized_seeded))[:8]
        if normalized_seeded:
            logger.info(f"Use seeded queries from execution plan: {normalized_seeded}")
            return normalized_seeded

    # 提取主题的核心关键词
    core_topic = extract_core_topic(topic)

    prompt = f"""我需要为「{core_topic}」制作一份专业的PPT演示文稿。请你作为信息检索专家，深入思考并生成**足够数量**的搜索关键词，确保内容全面覆盖。

**背景信息**：
- 主题：{core_topic}
- 目标受众：{audience}
- 内容模块：{', '.join(modules) if modules else '待定'}
- 重点内容：{keywords if keywords else '无'}
- 规划信息维度：{'; '.join(plan_dimensions) if isinstance(plan_dimensions, list) and plan_dimensions else '无'}
- 规划搜索策略：{'; '.join(plan_strategy) if isinstance(plan_strategy, list) and plan_strategy else '无'}

**关键要求**：
1. **自主判断数量**：根据主题复杂度决定搜索词数量（简单主题5个，复杂主题可达8个），确保内容全面
2. **深度思考**：不要简单套用"是什么"、"功能特点"、"使用案例"这样的模板
3. **针对性强**：根据具体主题特点，选择最有价值的搜索角度
4. **信息互补**：每个关键词覆盖完全不同的信息维度，互相补充，不重复
5. **精准简洁**：每个关键词不超过20个字，直接可用于搜索
6. **优先遵循规划**：若给出“规划信息维度/规划搜索策略”，搜索词必须覆盖这些维度

**输出格式**：
只输出搜索关键词，每行一个，不要编号、不要解释：
"""

    try:
        response = await call_llm_api([
            {"role": "system", "content": "你是一个资深的信息检索专家。你需要深入分析主题特点，根据主题复杂度自主决定搜索词数量（5-8个），生成最有价值的搜索关键词，确保内容全面覆盖。不要使用固定模板，要根据具体主题灵活思考。只输出关键词，每行一个。"},
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

    # 若已明确跳过搜索，直接返回 False
    if skip_search_flag:
        return False

    file_excerpt = ""
    if isinstance(file_context, str) and file_context.strip():
        file_excerpt = file_context.strip()

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
- 文件内容（如有）：{file_excerpt or '无'}

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
            search_response = await search_web(query=query, max_results=max_results)
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
    """流式生成搜索思考内容"""
    logger.info(f"Streaming search thinking for round {round_num}/{total_rounds}: {query}")

    # 构建搜索结果摘要
    results_summary = ""
    for i, result in enumerate(search_results[:4], 1):
        title = result.get("title", "")
        snippet = result.get("snippet", "")[:500]
        results_summary += f"{i}. {title}: {snippet}...\n"

    prompt = f"""我刚完成了第 {round_num}/{total_rounds} 轮搜索，关键词是「{query}」。

搜索结果摘要：
{results_summary}

请用1-2句话简短总结这轮搜索的收获，并说明下一步计划。格式如：
"已获取关于XXX的信息，包括XXX。{'接下来将搜索XXX以补充更多信息。' if round_num < total_rounds else '搜索完成，开始整理信息。'}"

直接输出总结，不要有其他内容。"""

    try:
        async for chunk in call_llm_api_stream([
            {"role": "system", "content": "你是一个信息整理助手，请简短总结搜索结果。"},
            {"role": "user", "content": prompt}
        ]):
            yield chunk
    except Exception as e:
        logger.error(f"Search thinking error: {e}")
        yield f"已获取关于「{query}」的 {len(search_results)} 条相关信息。"


async def stream_deep_thinking(topic: str, search_results: list) -> AsyncGenerator[str, None]:
    """流式生成深度思考分析"""
    logger.info(f"Starting deep thinking for: {topic}")

    # 构建搜索结果摘要
    results_summary = ""
    for i, result in enumerate(search_results[:], 1):
        title = result.get("title", "")
        snippet = result.get("snippet", "")[:500]
        results_summary += f"{i}. {title}\n   {snippet}\n\n"

    prompt = f"""基于以下搜索结果，对「{topic}」进行深度分析和整理。

搜索结果：
{results_summary}

请按以下格式进行分析（使用纯文本）：

通过搜索，我已经获得了关于「{topic}」的相关信息。让我整理和分析已获取的信息：

已获取的关键信息：
1. [第一个搜索结果的核心信息和价值]
2. [第二个搜索结果的核心信息和价值]
3. [第三个搜索结果的核心信息和价值]

信息整合分析：
• [对搜索结果的综合分析]
• [关键发现和洞察]
• [信息之间的关联]

接下来，我将基于这些信息开始撰写PPT内容...

请根据实际搜索结果内容进行分析，不要编造信息。"""

    try:
        async for chunk in call_llm_api_stream([
            {"role": "system", "content": "你是一个专业的信息分析助手，擅长从搜索结果中提取关键信息并进行深度分析。请按照用户要求的格式输出分析结果。"},
            {"role": "user", "content": prompt}
        ]):
            yield chunk
    except Exception as e:
        logger.error(f"Deep thinking error: {e}")
        # 回退到简单输出
        fallback = f"""通过搜索，我已经获得了关于「{topic}」的相关信息。让我整理和分析已获取的信息：

已获取的关键信息：
"""
        for i, result in enumerate(search_results[:3], 1):
            fallback += f"{i}. {result.get('title', '未知标题')}\n   {result.get('snippet', '')[:100]}...\n\n"
        fallback += "\n接下来，我将基于这些信息开始撰写PPT内容..."
        yield fallback
