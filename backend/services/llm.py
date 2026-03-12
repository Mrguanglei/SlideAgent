"""
PPTAgent LLM 服务模块

提供通用 LLM API 调用功能，支持豆包、千问、GLM等所有兼容OpenAI API的模型
"""

import json
import logging
import asyncio
import re
from typing import AsyncGenerator, Optional

import httpx
from fastapi import HTTPException

from utils.config import Config

logger = logging.getLogger(__name__)

def _extract_chunk_text(chunk: dict) -> Optional[str]:
    """兼容多种 OpenAI 流式/非流式返回格式，提取文本内容"""
    if not isinstance(chunk, dict):
        return None
    choices = chunk.get("choices") or []
    if choices:
        choice = choices[0] or {}
        # 标准 chat.completions 流式格式
        delta = choice.get("delta") or {}
        if isinstance(delta, dict):
            content = delta.get("content")
            if content:
                return content
        # 非流式 chat.completions
        message = choice.get("message") or {}
        if isinstance(message, dict):
            content = message.get("content")
            if content:
                return content
        # 兼容 completions
        text = choice.get("text")
        if text:
            return text
    # 兜底
    content = chunk.get("content")
    if isinstance(content, str) and content:
        return content
    return None


def _iter_text_chunks(text: str, size: int = 32):
    for idx in range(0, len(text), size):
        yield text[idx:idx + size]


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
            content_type = response.headers.get("content-type", "")
            # 如果服务端不返回 SSE，则改为一次性读取并“伪流式”输出
            if "text/event-stream" not in content_type.lower():
                try:
                    data = await response.json()
                except Exception:
                    raw = await response.aread()
                    try:
                        data = json.loads(raw.decode("utf-8", errors="ignore"))
                    except json.JSONDecodeError:
                        return
                content = _extract_chunk_text(data) or ""
                for piece in _iter_text_chunks(content):
                    yield piece
                    await asyncio.sleep(0.01)
                return
            async for line in response.aiter_lines():
                if not line:
                    continue
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    content = _extract_chunk_text(chunk)
                    if content:
                        for piece in _iter_text_chunks(content):
                            yield piece
                    continue
                # 兼容某些服务直接返回 JSON 行
                if line.startswith("{"):
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    content = _extract_chunk_text(chunk)
                    if content:
                        for piece in _iter_text_chunks(content):
                            yield piece



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
    """提取核心主题，尽量剥离“帮我生成一份…PPT吧”这类指令包装。"""
    if not topic:
        return ""

    text = str(topic).strip()
    text = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"\s+", "", text)
    if not text:
        return ""

    # 优先从常见句式中提取“主题主体”
    patterns = [
        r"(?:关于|围绕|以)([^，。！？!?；;：:]{2,48}?)(?:的)?(?:PPT|演示文稿|幻灯片)",
        r"(?:做|制作|生成|写|整理|准备)(?:一份|一个|一套)?(?:关于|围绕|以)?([^，。！？!?；;：:]{2,48}?)(?:的)?(?:PPT|演示文稿|幻灯片)",
        r"(?:介绍|讲解|讲讲|说明|分析)(?:一下)?([^，。！？!?；;：:]{2,48})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            candidate = match.group(1).strip("《》“”\"'：:，,。.！？!?；;~ ")
            if candidate:
                return candidate

    # 回退规则：轻量清理首尾包装词
    cleaned = re.sub(r"^(请你|请帮我|帮我|麻烦你|麻烦|我想|我要|给我)", "", text)
    cleaned = re.sub(r"(做个|做一份|制作一份|生成一份|写一份|做一套|制作一套)", "", cleaned)
    cleaned = re.sub(r"(?:关于|围绕|以)", "", cleaned, count=1)
    cleaned = re.sub(r"(?:的)?(?:PPT|演示文稿|幻灯片)(?:吧|呀|啊|呢|吗)?$", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.strip("《》“”\"'：:，,。.！？!?；;~ ")
    return cleaned or text
