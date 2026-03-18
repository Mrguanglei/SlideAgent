"""
聊天附件解析服务

用于：
1. 上传后立即解析附件，返回前端可展示的解析状态
2. 将解析结果缓存到本地，避免发送消息时重复解析
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from services.knowledge.document_parser import DocumentParser

logger = logging.getLogger(__name__)


def get_chat_parse_cache_path(file_path: str) -> Path:
    return Path(f"{file_path}.chatparse.json")


def load_chat_parse_cache(file_path: str) -> Optional[Dict[str, Any]]:
    cache_path = get_chat_parse_cache_path(file_path)
    if not cache_path.exists():
        return None

    try:
        return json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Failed to load chat parse cache for %s: %s", file_path, exc)
        return None


def _write_chat_parse_cache(file_path: str, payload: Dict[str, Any]) -> None:
    cache_path = get_chat_parse_cache_path(file_path)
    cache_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


async def ensure_chat_file_parsed(
    file_path: str,
    filename: Optional[str] = None,
    force: bool = False,
) -> Dict[str, Any]:
    cache = None if force else load_chat_parse_cache(file_path)
    if cache:
        return cache

    file_name = filename or Path(file_path).name
    file_type = DocumentParser.get_file_type(file_name) or DocumentParser.get_file_type(file_path)

    if not file_type:
        payload = {
            "parse_status": "unsupported",
            "parse_message": "该文件类型暂不做文本解析",
            "file_type": None,
            "content_length": 0,
            "extracted_text": "",
            "meta": {},
        }
        _write_chat_parse_cache(file_path, payload)
        return payload

    try:
        text, meta = await DocumentParser.parse(file_path, file_type=file_type)
        payload = {
            "parse_status": "completed",
            "parse_message": f"解析完成，已提取 {len(text)} 个字符",
            "file_type": file_type,
            "content_length": len(text),
            "extracted_text": text,
            "meta": meta or {},
        }
    except Exception as exc:
        payload = {
            "parse_status": "failed",
            "parse_message": str(exc),
            "file_type": file_type,
            "content_length": 0,
            "extracted_text": "",
            "meta": {},
        }

    _write_chat_parse_cache(file_path, payload)
    return payload
