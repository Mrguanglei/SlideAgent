"""Session/conversation binding helpers for confirm flow."""

from dataclasses import dataclass
from typing import Any, Optional, Tuple


@dataclass
class SessionBindingError(Exception):
    status_code: int
    detail: str


def resolve_confirm_session_binding(
    request_session_id: Optional[str],
    request_conversation_id: Optional[int],
    session_from_request: Any,
    session_from_conversation: Any,
) -> Tuple[Any, str, int, bool]:
    """Resolve session+conversation binding for confirm requests.

    Returns:
        (resolved_session, resolved_session_id, resolved_conversation_id, corrected)
    """
    corrected = False

    if request_conversation_id:
        if not session_from_conversation:
            raise SessionBindingError(
                status_code=409,
                detail="当前对话没有可确认的会话，请先重新发起生成",
            )
        resolved_session = session_from_conversation
        corrected = bool(
            request_session_id and request_session_id != session_from_conversation.id
        )
        resolved_conversation_id = request_conversation_id
    else:
        if not request_session_id:
            raise SessionBindingError(
                status_code=400,
                detail="缺少 session_id，请刷新后重试",
            )
        if not session_from_request:
            raise SessionBindingError(
                status_code=400,
                detail="无法确认历史对话，请创建新对话",
            )
        resolved_session = session_from_request
        resolved_conversation_id = getattr(session_from_request, "conversation_id", None)

    if not resolved_conversation_id:
        raise SessionBindingError(
            status_code=409,
            detail="会话未绑定有效对话，请先重新发起生成",
        )

    session_conversation_id = getattr(resolved_session, "conversation_id", None)
    if session_conversation_id and session_conversation_id != resolved_conversation_id:
        raise SessionBindingError(
            status_code=409,
            detail="会话与对话不匹配，请刷新后重试",
        )

    return resolved_session, resolved_session.id, resolved_conversation_id, corrected
