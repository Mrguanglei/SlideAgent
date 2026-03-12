import asyncio
import os
from typing import Any, Literal

import aiohttp
from fake_useragent import UserAgent

from deeppresenter.utils.constants import MAX_RETRY_INTERVAL, RETRY_TIMES
from deeppresenter.utils.log import warning

FAKE_UA = UserAgent()
TAVILY_API_URL = "https://api.tavily.com/search"


async def tavily_request(params: dict) -> dict[str, Any]:
    """发送 Tavily API 请求"""
    headers = {"Content-Type": "application/json", "User-Agent": FAKE_UA.random}

    async with aiohttp.ClientSession() as session:
        async with session.post(
            TAVILY_API_URL, headers=headers, json=params
        ) as response:
            if response.status == 429:
                warning("TAVILY rate limit exceeded, waiting...")
                await asyncio.sleep(MAX_RETRY_INTERVAL)
            if response.status != 200:
                warning(
                    f"TAVILY Error [{response.status}] headers={dict(response.headers)} body={await response.text()}"
                )
            response.raise_for_status()
            return await response.json()


async def search_with_fallback(**kwargs) -> dict[str, Any]:
    api_keys = [os.getenv("TAVILY_API_KEY")]
    if backup_key := os.getenv("TAVILY_BACKUP"):
        api_keys.append(backup_key)

    last_error = None
    for idx in range(RETRY_TIMES):
        for api_key in api_keys:
            await asyncio.sleep(min(2**idx - 1, MAX_RETRY_INTERVAL))
            try:
                params = {**kwargs, "api_key": api_key}
                return await tavily_request(params)
            except Exception as e:
                warning(f"TAVILY search error with key {api_key[:16]}...: {e}")
                last_error = e

    raise RuntimeError(
        f"TAVILY search failed after {RETRY_TIMES} retries"
    ) from last_error


async def search_web(
    query: str,
    max_results: int = 3,
    time_range: Literal["month", "year"] | None = None,
) -> dict:
    """
    Search the web

    Args:
        query: Search keywords
        max_results: Maximum number of search results, default 3
        time_range: Time range filter for search results, can be "month", "year", or None

    Returns:
        dict: Dictionary containing search results
    """
    kwargs = {"query": query, "max_results": max_results, "include_images": False}
    if time_range:
        kwargs["time_range"] = time_range

    result = await search_with_fallback(**kwargs)

    results = [
        {
            "title": item.get("title", ""),
            "url": item["url"],
            "content": item["content"],
        }
        for item in result.get("results", [])
    ]

    return {
        "query": query,
        "total_results": len(results),
        "results": results,
    }


async def search_images(query: str) -> dict:
    """
    Search for web images
    """
    result = await search_with_fallback(
        query=query,
        max_results=4,
        include_images=True,
        include_image_descriptions=True,
    )

    images = [
        {
            "url": img["url"],
            "description": img["description"],
        }
        for img in result.get("images", [])
    ]

    return {
        "query": query,
        "total_results": len(images),
        "images": images,
    }


# ==================== Tool Registry ====================

TOOL_REGISTRY = {
    "search_web": search_web,
    "search_images": search_images,
}

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Search the web for information.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search keywords"},
                    "max_results": {"type": "integer", "description": "Maximum number of results, default 3", "default": 3},
                    "time_range": {"type": "string", "enum": ["month", "year"], "description": "Optional time range filter"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_images",
            "description": "Search for web images.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Image search keywords"},
                },
                "required": ["query"],
            },
        },
    },
]


if __name__ == "__main__":
    result = asyncio.run(search_web('Google Gemini model "Gemini 3 Pro" features'))
    print(result)
