"""Minimal in-process background tasks for long operations (resume generation, URL fetching).

Local-first and single-user, so a thread pool is enough. Task state lives in memory; results are
persisted by the task itself (e.g. the resume version id), so nothing is lost if a status entry is.
"""

from __future__ import annotations

import logging
import threading
import traceback
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

log = logging.getLogger(__name__)
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="rip-task")
_tasks: dict[str, dict[str, Any]] = {}
_lock = threading.Lock()


def submit(kind: str, fn: Callable[[], dict]) -> str:
    task_id = uuid.uuid4().hex
    with _lock:
        _tasks[task_id] = {"id": task_id, "kind": kind, "status": "queued", "result": None, "error": None,
                           "created_at": datetime.now(timezone.utc).isoformat()}

    def run():
        with _lock:
            _tasks[task_id]["status"] = "running"
        try:
            result = fn()
            with _lock:
                _tasks[task_id].update(status="done", result=result)
        except Exception as exc:
            log.warning("task %s failed: %s", kind, type(exc).__name__)
            log.debug(traceback.format_exc())
            with _lock:
                _tasks[task_id].update(status="failed", error=str(exc)[:500])

    _executor.submit(run)
    return task_id


def get(task_id: str) -> dict | None:
    with _lock:
        t = _tasks.get(task_id)
        return dict(t) if t else None
