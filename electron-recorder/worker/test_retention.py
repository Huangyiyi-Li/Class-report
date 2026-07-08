import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from worker.queue_store import QueueStore
from worker.retention import cleanup_completed, disk_health


NOW = datetime(2026, 7, 8, tzinfo=timezone.utc)


def add_segment(store, path, status):
    item_id = store.enqueue({"local_path": str(path), "segment_index": item_id_seed(path)})
    if status != "pending":
        store.claim_next(NOW)
        if status == "failed":
            store.mark_failed(item_id, "offline", NOW + timedelta(days=1))
        else:
            store.mark_uploaded(item_id, "https://files.test/" + path.name)
            if status == "completed":
                store.mark_completed(item_id)
    return item_id


def item_id_seed(path):
    return sum(path.name.encode())


def test_cleanup_deletes_only_completed_files_older_than_seven_days(tmp_path):
    store = QueueStore(tmp_path / "queue.db")
    paths = {name: tmp_path / f"{name}.wav" for name in ("completed", "pending", "failed", "uploading", "uploaded")}
    for path in paths.values():
        path.write_bytes(b"audio")
    completed_id = add_segment(store, paths["completed"], "completed")
    add_segment(store, paths["failed"], "failed")
    add_segment(store, paths["uploading"], "uploading")
    add_segment(store, paths["uploaded"], "uploaded")
    add_segment(store, paths["pending"], "pending")
    store.set_completed_at(completed_id, NOW - timedelta(days=8))

    deleted = cleanup_completed(tmp_path, store, NOW, retention_days=7)

    assert deleted == [paths["completed"]]
    assert all(paths[name].exists() for name in ("pending", "failed", "uploading", "uploaded"))


def test_recent_completed_file_is_retained(tmp_path):
    store = QueueStore(tmp_path / "queue.db")
    path = tmp_path / "recent.wav"
    path.write_bytes(b"audio")
    item_id = add_segment(store, path, "completed")
    store.set_completed_at(item_id, NOW - timedelta(days=6))

    assert cleanup_completed(tmp_path, store, NOW) == []
    assert path.exists()


def test_disk_health_uses_five_gib_threshold(tmp_path, monkeypatch):
    monkeypatch.setattr("worker.retention.shutil.disk_usage", lambda path: os.statvfs_result((0, 0, 0, 0, 0, 0, 0, 0, 0, 0)))
    monkeypatch.setattr("worker.retention._free_bytes", lambda path: 5 * 1024**3 - 1)
    assert disk_health(tmp_path) == "low"
    monkeypatch.setattr("worker.retention._free_bytes", lambda path: 5 * 1024**3)
    assert disk_health(tmp_path) == "healthy"
    monkeypatch.setattr("worker.retention._free_bytes", lambda path: (_ for _ in ()).throw(OSError("gone")))
    assert disk_health(tmp_path) == "unavailable"
