from datetime import datetime, timedelta, timezone
import importlib.util
import sys
from types import SimpleNamespace
import types
from pathlib import Path


def _load_normalize_task_status():
    module_path = Path(__file__).resolve().parent / "routers" / "conversations.py"
    spec = importlib.util.spec_from_file_location("conversations_module_for_test", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None

    fake_database_module = types.ModuleType("database")
    fake_database_module.crud = SimpleNamespace()
    fake_connection_module = types.ModuleType("database.connection")
    fake_connection_module.get_db = lambda: None

    original_database = sys.modules.get("database")
    original_database_connection = sys.modules.get("database.connection")
    try:
        sys.modules["database"] = fake_database_module
        sys.modules["database.connection"] = fake_connection_module
        spec.loader.exec_module(module)
    finally:
        if original_database is not None:
            sys.modules["database"] = original_database
        else:
            sys.modules.pop("database", None)
        if original_database_connection is not None:
            sys.modules["database.connection"] = original_database_connection
        else:
            sys.modules.pop("database.connection", None)

    return module._normalize_task_status


_normalize_task_status = _load_normalize_task_status()


def _session(stage: str, task_status: str, updated_at: datetime):
    return SimpleNamespace(stage=stage, task_status=task_status, updated_at=updated_at)


def test_waiting_supplement_running_is_normalized_to_idle():
    session = _session(
        stage="waiting_supplement",
        task_status="running",
        updated_at=datetime.now(timezone.utc),
    )

    assert _normalize_task_status(session) == "idle"


def test_completed_running_is_normalized_to_completed():
    session = _session(
        stage="completed",
        task_status="running",
        updated_at=datetime.now(timezone.utc),
    )

    assert _normalize_task_status(session) == "completed"


def test_stale_running_session_is_normalized_to_paused():
    session = _session(
        stage="generating",
        task_status="running",
        updated_at=datetime.now(timezone.utc) - timedelta(hours=2),
    )

    assert _normalize_task_status(session) == "paused"


def test_recent_running_session_stays_running():
    session = _session(
        stage="generating",
        task_status="running",
        updated_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )

    assert _normalize_task_status(session) == "running"
