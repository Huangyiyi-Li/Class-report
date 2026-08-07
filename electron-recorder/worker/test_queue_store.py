import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

import pytest

from worker.config import WorkerConfig
from worker.queue_store import QueueStore, migrate_json_queue
from worker.recorder_worker import CaptureSession


def test_failed_item_does_not_block_next_item(tmp_path: Path):
    store = QueueStore(tmp_path / "queue.db")
    first = store.enqueue({"local_path": "one.wav", "segment_index": 1})
    second = store.enqueue({"local_path": "two.wav", "segment_index": 2})

    assert store.claim_next("2026-07-07T00:00:00Z").id == first
    store.mark_failed(first, "offline", "2099-01-01T00:00:00Z")

    assert store.claim_next("2026-07-07T00:00:00Z").id == second


def test_manual_retry_makes_backoff_items_immediately_claimable(tmp_path: Path):
    store = QueueStore(tmp_path / "queue.db")
    item_id = store.enqueue({"local_path": "one.ogg", "segment_index": 1})
    store.claim_next("2026-08-07T01:30:00Z")
    store.mark_failed(item_id, "offline", "2099-01-01T00:00:00Z")

    assert store.claim_next("2026-08-07T01:30:01Z") is None
    assert store.make_retryable_now() == 1

    claimed = store.claim_next("2026-08-07T01:30:01Z")
    assert claimed.id == item_id
    assert claimed.action == "upload"


def test_completed_item_is_not_claimed_again(tmp_path: Path):
    store = QueueStore(tmp_path / "queue.db")
    item_id = store.enqueue({"local_path": "one.wav", "segment_index": 1})
    store.claim_next("2026-07-07T00:00:00Z")
    store.mark_uploaded(item_id, "https://example.test/one.wav")
    store.claim_next("2026-07-07T00:00:00Z")
    store.mark_completed(item_id)

    assert store.claim_next("2026-07-07T00:00:00Z") is None


def test_uploaded_item_is_claimed_for_registration_without_upload(tmp_path: Path):
    store = QueueStore(tmp_path / "queue.db")
    item_id = store.enqueue({"local_path": "one.wav", "segment_index": 1})
    store.claim_next("2026-07-07T00:00:00Z")
    store.mark_uploaded(item_id, "https://example.test/one.wav")

    claimed = store.claim_next("2026-07-07T00:00:00Z")
    assert claimed.id == item_id
    assert claimed.action == "register"


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
    store.claim_next("2026-07-07T00:00:00Z")
    store.mark_failed(first, "offline", "2099-01-01T00:00:00Z")

    assert store.counts() == {"failed": 1, "pending": 1}


def test_diagnostics_exposes_safe_queue_counts_and_recent_failures(tmp_path: Path):
    store = QueueStore(tmp_path / "queue.db")
    path = tmp_path / "AABBCCDDEEFF_20260807_093000_000001.ogg"
    path.write_bytes(b"audio")
    item_id = store.enqueue({"local_path": str(path), "segment_index": 7})
    store.claim_next("2026-08-07T01:30:00Z")
    store.mark_failed(item_id, "获取 OSS 上传凭证失败", "2026-08-07T01:32:00Z")

    diagnostics = store.diagnostics(limit=10)

    assert diagnostics["counts"] == {"failed": 1}
    assert diagnostics["recent"] == [
        {
            "segmentIndex": 7,
            "fileName": path.name,
            "status": "failed",
            "lastError": "获取 OSS 上传凭证失败",
            "retryAt": 1786066320000,
            "attempts": 1,
            "metadataAttempts": 0,
            "startTime": "",
            "endTime": "",
            "fileExists": True,
        }
    ]


def test_reconcile_missing_files_removes_only_unavailable_audio_from_pending_queue(
    tmp_path: Path,
):
    store = QueueStore(tmp_path / "queue.db")
    existing = tmp_path / "existing.ogg"
    existing.write_bytes(b"audio")
    store.enqueue({"local_path": str(existing), "segment_index": 1})
    missing_id = store.enqueue(
        {"local_path": str(tmp_path / "deleted.ogg"), "segment_index": 2}
    )

    assert store.reconcile_missing_files() == 1
    assert store.reconcile_missing_files() == 0
    assert store.counts() == {"local_missing": 1, "pending": 1}
    assert store.claim_next("2026-07-07T00:00:00Z").local_path == str(existing)

    with sqlite3.connect(store.database_path) as connection:
        status, retry_at, error = connection.execute(
            "SELECT status, retry_at, last_error FROM segments WHERE id = ?",
            (missing_id,),
        ).fetchone()
    assert status == "local_missing"
    assert retry_at is None
    assert error == "本地录音文件已不存在"


def test_reconcile_missing_files_preserves_completed_history(tmp_path: Path):
    store = QueueStore(tmp_path / "queue.db")
    item_id = store.enqueue(
        {"local_path": str(tmp_path / "uploaded.ogg"), "segment_index": 1}
    )
    store.claim_next("2026-07-07T00:00:00Z")
    store.mark_uploaded(item_id, "https://example.test/uploaded.ogg")
    store.claim_next("2026-07-07T00:00:00Z")
    store.mark_completed(item_id)

    assert store.reconcile_missing_files() == 0
    assert store.counts() == {"completed": 1}


def test_completed_item_rejects_transition_to_failed(tmp_path: Path):
    store = QueueStore(tmp_path / "queue.db")
    item_id = _completed_item(store)

    with pytest.raises(ValueError, match="completed.*failed"):
        store.mark_failed(item_id, "offline", "2026-07-08T00:00:00Z")

    assert store.counts() == {"completed": 1}


def test_completed_item_rejects_transition_to_uploaded(tmp_path: Path):
    store = QueueStore(tmp_path / "queue.db")
    item_id = _completed_item(store)

    with pytest.raises(ValueError, match="completed.*uploaded"):
        store.mark_uploaded(item_id, "https://example.test/replacement.wav")

    assert store.counts() == {"completed": 1}


def test_pending_item_rejects_transition_to_completed(tmp_path: Path):
    store = QueueStore(tmp_path / "queue.db")
    item_id = store.enqueue({"local_path": "one.wav", "segment_index": 1})

    with pytest.raises(ValueError, match="pending.*completed"):
        store.mark_completed(item_id)

    assert store.counts() == {"pending": 1}


def test_repeating_completed_transition_is_idempotent(tmp_path: Path):
    store = QueueStore(tmp_path / "queue.db")
    item_id = _completed_item(store)

    store.mark_completed(item_id)

    assert store.counts() == {"completed": 1}


def test_retry_time_with_offset_is_compared_as_same_utc_instant(tmp_path: Path):
    store = QueueStore(tmp_path / "queue.db")
    item_id = store.enqueue({"local_path": "one.wav", "segment_index": 1})
    store.claim_next("2026-07-06T23:00:00Z")
    store.mark_failed(item_id, "offline", "2026-07-07T08:00:00+08:00")

    claimed = store.claim_next(datetime(2026, 7, 7, tzinfo=timezone.utc))

    assert claimed.id == item_id


def test_retry_time_preserves_fractional_second_ordering(tmp_path: Path):
    store = QueueStore(tmp_path / "queue.db")
    item_id = store.enqueue({"local_path": "one.wav", "segment_index": 1})
    store.claim_next("2026-07-07T00:00:00Z")
    store.mark_failed(item_id, "offline", "2026-07-07T00:00:01.500Z")

    assert store.claim_next("2026-07-07T00:00:01.499Z") is None
    assert store.claim_next("2026-07-07T00:00:01.500Z").id == item_id


def test_segment_index_is_persistent_per_device_and_day(tmp_path: Path):
    database = tmp_path / "queue.db"
    first = QueueStore(database)

    assert first.next_segment_index("device-1", "2026-07-07") == 1
    assert first.next_segment_index("device-1", "2026-07-07") == 2
    reopened = QueueStore(database)
    assert reopened.next_segment_index("device-1", "2026-07-07") == 3
    assert reopened.next_segment_index("device-1", "2026-07-08") == 1
    assert reopened.next_segment_index("device-2", "2026-07-07") == 1


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
        columns = {
            row[1]: row[2] for row in connection.execute("PRAGMA table_info(segments)")
        }
        assert columns["retry_at"] == "INTEGER"


def test_enqueue_recovered_is_idempotent_without_consuming_another_index(tmp_path: Path):
    store = QueueStore(tmp_path / "queue.db")
    segment = {
        "local_path": str(tmp_path / "recovered.wav"), "code": "device-1",
        "device_no": "device-1", "school_id": 1, "location_id": "room",
        "start_time": "2026-07-12T23:59:00+00:00", "end_time": "2026-07-13T00:00:00+00:00",
        "rate": 16000, "bits": 16, "channel": 1, "audio_type": 1, "audio_format": "wav",
    }
    first = store.enqueue_recovered(segment, "device-1", "2026-07-12")
    second = store.enqueue_recovered(segment, "device-1", "2026-07-12")
    assert first == second
    assert store.next_segment_index("device-1", "2026-07-12") == 2


def test_finalized_encoded_path_is_persisted_in_queue(tmp_path: Path):
    class Journal:
        rate = 16000
        channels = 1
        sample_width = 2
        root = tmp_path
        device_id = "device-1"
        started_at = datetime(2026, 7, 7, tzinfo=timezone.utc)

        def finalize(self, end_time):
            return tmp_path / "segment.wav"

    encoded = tmp_path / "segment.ogg"
    store = QueueStore(tmp_path / "queue.db")
    today = datetime.now(timezone.utc).date().isoformat()
    assert store.next_segment_index("device-1", today) == 1
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
    assert item.segment_index == 2
    assert item.code == "device-1"
    assert item.device_no == "device-1"
    assert item.start_time == "2026-07-07T00:00:00+00:00"
    assert item.rate == 16000
    assert item.bits == 16
    assert item.channel == 1


def test_finalized_segment_notifies_worker_after_queue_persistence(tmp_path: Path):
    class Journal:
        rate = 16000
        channels = 1
        sample_width = 2
        root = tmp_path
        device_id = "device-1"
        started_at = datetime(2026, 8, 7, tzinfo=timezone.utc)

        def finalize(self, end_time):
            return tmp_path / "segment.wav"

    encoded = tmp_path / "segment.ogg"
    observed = []
    session = CaptureSession(
        WorkerConfig(),
        Journal(),
        ffmpeg_path=Path("ffmpeg.exe"),
        encoder=lambda wav, ffmpeg: encoded,
        queue_store=QueueStore(tmp_path / "queue.db"),
        on_segment_finalized=observed.append,
    )
    session.finalize_queue.put(Journal())
    session.finalize_queue.put(None)

    session.finalizer_loop()

    assert observed[0]["segmentIndex"] == 1
    assert observed[0]["fileName"] == "segment.ogg"
    assert observed[0]["fileExists"] is False


def test_uploaded_and_stale_registering_are_claimed_for_registration(tmp_path: Path):
    store = QueueStore(tmp_path / "queue.db")
    item_id = store.enqueue({"local_path": "one.wav", "segment_index": 1})
    upload = store.claim_next("2026-07-07T00:00:00Z")
    assert upload.action == "upload"
    store.mark_uploaded(item_id, "https://files.test/one.wav")

    register = store.claim_next("2026-07-07T00:00:01Z")
    assert register.action == "register"
    assert store.claim_next("2026-07-07T00:00:02Z") is None
    recovered = store.claim_next("2026-07-07T00:05:02Z")
    assert recovered.id == item_id
    assert recovered.action == "register"


def _completed_item(store: QueueStore) -> int:
    item_id = store.enqueue({"local_path": "one.wav", "segment_index": 1})
    store.claim_next("2026-07-07T00:00:00Z")
    store.mark_uploaded(item_id, "https://example.test/one.wav")
    store.claim_next("2026-07-07T00:00:00Z")
    store.mark_completed(item_id)
    return item_id
