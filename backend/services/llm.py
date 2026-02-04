"""
PPTAgent LLM 服务模块

提供通用 LLM API 调用功能，支持豆包、千问、GLM等所有兼容OpenAI API的模型
"""

import json
import logging
from typing import AsyncGenerator, Optional

import httpx
from fastapi import HTTPException

from utils.config import Config

logger = logging.getLogger(__name__)


async def call_llm_api(messages: list, response_format: dict = None, deep_thinking_mode: bool = False) -> str:
    """调用 LLM API（非流式）- 支持豆包、千问、GLM等所有模型"""
    if not Config.LLM_API_KEY:
        raise HTTPException(status_code=500, detail="LLM API not configured")

    headers = {
        "Authorization": f"Bearer {Config.LLM_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": Config.LLM_MODEL,
        "messages": messages,
        "temperature": 0.7,
    }

    if response_format:
        payload["response_format"] = response_format
    
    # 如果启用深度思考模式，可以调整 temperature 或添加特殊提示
    if deep_thinking_mode:
        # 可以根据具体模型调整参数，例如设置更低的 temperature 以获得更严谨的思考
        payload["temperature"] = 0.3
        # 某些模型可能支持特殊的思考模式参数，可以在这里添加
        # payload["enable_search"] = True  # 示例

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{Config.LLM_BASE_URL}/chat/completions",
            headers=headers,
            json=payload
        )
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"]


async def call_llm_api_stream(messages: list, deep_thinking_mode: bool = False) -> AsyncGenerator[str, None]:
    """流式调用 LLM API - 支持豆包、千问、GLM等所有模型"""
    if not Config.LLM_API_KEY:
        raise HTTPException(status_code=500, detail="LLM API not configured")

    headers = {
        "Authorization": f"Bearer {Config.LLM_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": Config.LLM_MODEL,
        "messages": messages,
        "temperature": 0.7,
        "stream": True,
    }
    
    # 如果启用深度思考模式，调整参数
    if deep_thinking_mode:
        payload["temperature"] = 0.3
    else:
        # 如果未启用深度思考模式，明确在 System Prompt 中禁止输出思维过程
        # 检查是否已有 system prompt，如果有则追加，没有则插入
        system_instruction = "IMPORTANT: Do NOT output internal thought processes or <think> tags. Directly output the final response."
        
        has_system = False
        for msg in messages:
            if msg.get("role") == "system":
                msg["content"] += f"\n\n{system_instruction}"
                has_system = True
                break
        
        if not has_system:
            messages.insert(0, {"role": "system", "content": system_instruction})

    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream(
            "POST",
            f"{Config.LLM_BASE_URL}/chat/completions",
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
        response = response[:-3:]
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
