from __future__ import annotations

import shutil
from datetime import datetime, timedelta
from pathlib import Path

from worker.queue_store import QueueStore


LOW_SPACE_BYTES = 5 * 1024**3


def cleanup_completed(
    recordings_dir: str | Path,
    store: QueueStore,
    now: str | datetime,
    retention_days: int = 7,
) -> list[Path]:
    root = Path(recordings_dir).resolve()
    cutoff = _as_datetime(now) - timedelta(days=retention_days)
    deleted = []
    for item in store.completed_before(cutoff):
        original = Path(item.local_path)
        if original.is_symlink():
            continue
        path = original.resolve()
        if not path.is_relative_to(root):
            continue
        try:
            original.unlink()
        except FileNotFoundError:
            continue
        deleted.append(original)
    return deleted


def disk_health(path: str | Path) -> str:
    try:
        free = _free_bytes(path)
    except OSError:
        return "unavailable"
    return "low" if free < LOW_SPACE_BYTES else "healthy"


def _free_bytes(path: str | Path) -> int:
    return shutil.disk_usage(path).free


def _as_datetime(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    raise TypeError("timestamp must be an ISO string or datetime")
