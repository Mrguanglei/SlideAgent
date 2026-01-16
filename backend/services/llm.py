"""
PPTAgent LLM 服务模块

提供豆包 API 调用功能
"""

import json
import logging
from typing import AsyncGenerator, Optional

import httpx
from fastapi import HTTPException

from utils.config import Config

logger = logging.getLogger(__name__)


async def call_doubao_api(messages: list, response_format: dict = None) -> str:
    """调用豆包 API（非流式）"""
    if not Config.DOUBAO_API_KEY:
        raise HTTPException(status_code=500, detail="Doubao API not configured")

    headers = {
        "Authorization": f"Bearer {Config.DOUBAO_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": Config.DOUBAO_MODEL,
        "messages": messages,
        "temperature": 0.7,
    }

    if response_format:
        payload["response_format"] = response_format

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{Config.DOUBAO_BASE_URL}/chat/completions",
            headers=headers,
            json=payload
        )
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"]


async def call_doubao_api_stream(messages: list) -> AsyncGenerator[str, None]:
    """流式调用豆包 API"""
    if not Config.DOUBAO_API_KEY:
        raise HTTPException(status_code=500, detail="Doubao API not configured")

    headers = {
        "Authorization": f"Bearer {Config.DOUBAO_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": Config.DOUBAO_MODEL,
        "messages": messages,
        "temperature": 0.7,
        "stream": True,
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream(
            "POST",
            f"{Config.DOUBAO_BASE_URL}/chat/completions",
            headers=headers,
            json=payload
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        if chunk.get("choices") and chunk["choices"][0].get("delta", {}).get("content"):
                            yield chunk["choices"][0]["delta"]["content"]
                    except json.JSONDecodeError:
                        continue


def clean_json_response(response: str) -> str:
    """清理 LLM 返回的 JSON 响应，移除 markdown 代码块标记"""
    response = response.strip()
    if response.startswith("```json"):
        response = response[7:]
    if response.startswith("```"):
        response = response[3:]
    if response.endswith("```"):
        response = response[:-3]
    return response.strip()


def extract_core_topic(topic: str) -> str:
    """提取核心主题，去掉描述性词语"""
    # 去掉常见的描述性前缀
    prefixes_to_remove = ["帮我", "请", "介绍一下", "介绍", "详细的", "制作一个关于", "制作", "关于"]
    core_topic = topic
    for prefix in prefixes_to_remove:
        core_topic = core_topic.replace(prefix, "").strip()

    # 去掉常见的描述性后缀
    suffixes_to_remove = ["的PPT", "的演示文稿", "的幻灯片", "PPT", "演示文稿", "幻灯片"]
    for suffix in suffixes_to_remove:
        core_topic = core_topic.replace(suffix, "").strip()

    return core_topic if core_topic else topic
