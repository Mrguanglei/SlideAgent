import importlib.util
import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest


def _load_session_guard_module():
    module_path = Path(__file__).resolve().parent / "services" / "session_guard.py"
    spec = importlib.util.spec_from_file_location("session_guard", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_resolve_confirm_binding_prefers_conversation_session_on_mismatch():
    session_guard = _load_session_guard_module()
    request_session = SimpleNamespace(id="session_a", conversation_id=1)
    conversation_session = SimpleNamespace(id="session_b", conversation_id=2)

    _, session_id, conversation_id, corrected = session_guard.resolve_confirm_session_binding(
        request_session_id="session_a",
        request_conversation_id=2,
        session_from_request=request_session,
        session_from_conversation=conversation_session,
    )

    assert session_id == "session_b"
    assert conversation_id == 2
    assert corrected is True


def test_resolve_confirm_binding_requires_conversation_session():
    session_guard = _load_session_guard_module()

    with pytest.raises(session_guard.SessionBindingError) as exc_info:
        session_guard.resolve_confirm_session_binding(
            request_session_id="session_a",
            request_conversation_id=2,
            session_from_request=SimpleNamespace(id="session_a", conversation_id=1),
            session_from_conversation=None,
        )

    assert exc_info.value.status_code == 409


def test_resolve_confirm_binding_uses_session_path_without_conversation():
    session_guard = _load_session_guard_module()
    request_session = SimpleNamespace(id="session_a", conversation_id=10)

    _, session_id, conversation_id, corrected = session_guard.resolve_confirm_session_binding(
        request_session_id="session_a",
        request_conversation_id=None,
        session_from_request=request_session,
        session_from_conversation=None,
    )

    assert session_id == "session_a"
    assert conversation_id == 10
    assert corrected is False


def test_resolve_confirm_binding_prefers_conversation_even_without_request_session():
    session_guard = _load_session_guard_module()
    conversation_session = SimpleNamespace(id="session_b", conversation_id=20)

    _, session_id, conversation_id, corrected = session_guard.resolve_confirm_session_binding(
        request_session_id=None,
        request_conversation_id=20,
        session_from_request=None,
        session_from_conversation=conversation_session,
    )

    assert session_id == "session_b"
    assert conversation_id == 20
    assert corrected is False


def test_resolve_confirm_binding_rejects_session_without_conversation_binding():
    session_guard = _load_session_guard_module()
    broken_session = SimpleNamespace(id="session_a", conversation_id=None)

    with pytest.raises(session_guard.SessionBindingError) as exc_info:
        session_guard.resolve_confirm_session_binding(
            request_session_id="session_a",
            request_conversation_id=None,
            session_from_request=broken_session,
            session_from_conversation=None,
        )

    assert exc_info.value.status_code == 409


def test_resolve_confirm_binding_isolation_under_parallel_calls():
    session_guard = _load_session_guard_module()

    async def resolve_for_history_tab():
        req_session = SimpleNamespace(id="history_old", conversation_id=100)
        conv_session = SimpleNamespace(id="history_new", conversation_id=101)
        return session_guard.resolve_confirm_session_binding(
            request_session_id=req_session.id,
            request_conversation_id=101,
            session_from_request=req_session,
            session_from_conversation=conv_session,
        )

    async def resolve_for_new_tab():
        req_session = SimpleNamespace(id="new_old", conversation_id=200)
        conv_session = SimpleNamespace(id="new_new", conversation_id=201)
        return session_guard.resolve_confirm_session_binding(
            request_session_id=req_session.id,
            request_conversation_id=201,
            session_from_request=req_session,
            session_from_conversation=conv_session,
        )

    async def _run_parallel():
        return await asyncio.gather(resolve_for_history_tab(), resolve_for_new_tab())

    history_result, new_result = asyncio.run(_run_parallel())

    assert history_result[1] == "history_new"
    assert history_result[2] == 101
    assert history_result[3] is True

    assert new_result[1] == "new_new"
    assert new_result[2] == 201
    assert new_result[3] is True
