import json
import sqlite3
import threading
from pathlib import Path

import pytest

from worker.config import WorkerConfig
from worker.queue_store import QueueStore, migrate_json_queue
from worker.recorder_worker import CaptureSession


def test_failed_item_does_not_block_next_item(tmp_path: Path):
    store = QueueStore(tmp_path / "queue.db")
    first = store.enqueue({"local_path": "one.wav", "segment_index": 1})
    second = store.enqueue({"local_path": "two.wav", "segment_index": 2})

    store.mark_failed(first, "offline", "2099-01-01T00:00:00Z")

    assert store.claim_next("2026-07-07T00:00:00Z").id == second


def test_completed_item_is_not_claimed_again(tmp_path: Path):
    store = QueueStore(tmp_path / "queue.db")
    item_id = store.enqueue({"local_path": "one.wav", "segment_index": 1})
    store.mark_uploaded(item_id, "https://example.test/one.wav")
    store.mark_completed(item_id)

    assert store.claim_next("2026-07-07T00:00:00Z") is None


def test_uploaded_item_is_not_claimed_again(tmp_path: Path):
    store = QueueStore(tmp_path / "queue.db")
    item_id = store.enqueue({"local_path": "one.wav", "segment_index": 1})
    store.mark_uploaded(item_id, "https://example.test/one.wav")

    assert store.claim_next("2026-07-07T00:00:00Z") is None


def test_claim_next_is_atomic_between_workers(tmp_path: Path):
    store = QueueStore(tmp_path / "queue.db")
    item_id = store.enqueue({"local_path": "one.wav", "segment_index": 1})
    barrier = threading.Barrier(2)
    claimed = []

    def claim():
        barrier.wait()
        claimed.append(store.claim_next("2026-07-07T00:00:00Z"))

    threads = [threading.Thread(target=claim) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert [item.id for item in claimed if item is not None] == [item_id]


def test_counts_groups_items_by_status(tmp_path: Path):
    store = QueueStore(tmp_path / "queue.db")
    first = store.enqueue({"local_path": "one.wav", "segment_index": 1})
    store.enqueue({"local_path": "two.wav", "segment_index": 2})
    store.mark_failed(first, "offline", "2099-01-01T00:00:00Z")

    assert store.counts() == {"failed": 1, "pending": 1}


def test_json_queue_migration_is_idempotent(tmp_path: Path):
    store = QueueStore(tmp_path / "queue.db")
    source = tmp_path / "queue.json"
    payload = [{"localPath": "one.wav", "segmentIndex": 1}]
    source.write_text(json.dumps(payload), encoding="utf-8")

    migrate_json_queue(source, store)
    source.write_text(json.dumps(payload), encoding="utf-8")
    migrate_json_queue(source, store)

    assert store.counts() == {"pending": 1}
    assert not source.exists()
    assert source.with_name("queue.json.migrated").exists()


def test_json_queue_is_not_renamed_when_an_item_cannot_be_migrated(tmp_path: Path):
    store = QueueStore(tmp_path / "queue.db")
    source = tmp_path / "queue.json"
    source.write_text(
        json.dumps(
            [
                {"localPath": "valid.wav", "segmentIndex": 1},
                {"localPath": "missing-index.wav"},
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises((KeyError, ValueError, TypeError)):
        migrate_json_queue(source, store)

    assert source.exists()
    assert not source.with_name("queue.json.migrated").exists()
    assert store.counts() == {}


def test_database_uses_wal_journal_mode(tmp_path: Path):
    database = tmp_path / "queue.db"
    QueueStore(database)

    with sqlite3.connect(database) as connection:
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_finalized_encoded_path_is_persisted_in_queue(tmp_path: Path):
    class Journal:
        rate = 16000
        channels = 1
        sample_width = 2
        root = tmp_path
        device_id = "device-1"

        def finalize(self, end_time):
            return tmp_path / "segment.wav"

    encoded = tmp_path / "segment.ogg"
    store = QueueStore(tmp_path / "queue.db")
    session = CaptureSession(
        WorkerConfig(),
        Journal(),
        ffmpeg_path=Path("ffmpeg.exe"),
        encoder=lambda wav, ffmpeg: encoded,
        queue_store=store,
    )
    session.finalize_queue.put(Journal())
    session.finalize_queue.put(None)

    session.finalizer_loop()

    item = store.claim_next("2026-07-07T00:00:00Z")
    assert item.local_path == str(encoded)
    assert item.segment_index == 1
