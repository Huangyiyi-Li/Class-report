from datetime import datetime, timezone
from pathlib import Path
import threading

from worker.queue_store import QueueStore
from worker.upload_service import RETRY_SECONDS, UploadService, retry_delay


class FakeUploader:
    def __init__(self, fail_paths=()):
        self.fail_paths = set(fail_paths)
        self.calls = []

    def upload(self, path):
        self.calls.append(Path(path).name)
        if Path(path).name in self.fail_paths:
            raise OSError("offline")
        return f"https://files.test/{Path(path).name}"


class FakeMetadataClient:
    def __init__(self, failures=0):
        self.payloads = []
        self.failures = failures

    def save_audio_file_info(self, payload):
        self.payloads.append(payload)
        if self.failures:
            self.failures -= 1
            raise OSError("metadata offline")


def seeded_store(tmp_path, names):
    store = QueueStore(tmp_path / "queue.db")
    for index, name in enumerate(names, 1):
        path = tmp_path / name
        path.write_bytes(b"audio")
        store.enqueue(segment(path, index))
    return store


def segment(path, index=1):
    return {
        "local_path": str(path),
        "segment_index": index,
        "code": "device-1",
        "device_no": "device-1",
        "school_id": None,
        "location_id": "room-101",
        "start_time": "2026-07-07T00:00:00Z",
        "end_time": "2026-07-07T00:05:00Z",
        "rate": 16000,
        "bits": 16,
        "channel": 1,
        "audio_type": 1,
        "audio_format": path.suffix.lstrip("."),
    }


def test_upload_failure_marks_one_item_and_continues(tmp_path):
    store = seeded_store(tmp_path, ["one.wav", "two.wav"])
    service = UploadService(store, FakeUploader({"one.wav"}), FakeMetadataClient())

    service.run_once("2026-07-07T00:00:00Z")
    service.run_once("2026-07-07T00:00:01Z")
    result = service.run_once("2026-07-07T00:00:02Z")

    assert store.counts() == {"failed": 1, "completed": 1}
    assert result.status == "completed"


def test_success_uploads_then_registers_metadata(tmp_path):
    store = seeded_store(tmp_path, ["one.wav"])
    metadata = FakeMetadataClient()

    service = UploadService(store, FakeUploader(), metadata)
    assert service.run_once("2026-07-07T00:00:00Z").status == "uploaded"
    result = service.run_once("2026-07-07T00:00:01Z")

    assert result.status == "completed"
    assert metadata.payloads == [
        {
            "segmentIndex": 1,
            "filePath": "https://files.test/one.wav",
            "fileSize": 5,
            "format": "wav",
            "code": "device-1",
            "deviceNo": "device-1",
            "schoolId": None,
            "locationId": "room-101",
            "startTime": "2026-07-07T00:00:00Z",
            "endTime": "2026-07-07T00:05:00Z",
            "rate": 16000,
            "bits": 16,
            "channel": 1,
            "audioType": 1,
        }
    ]


def test_retry_schedule_is_bounded_and_persisted(tmp_path):
    store = seeded_store(tmp_path, ["one.wav"])
    service = UploadService(store, FakeUploader({"one.wav"}), FakeMetadataClient())
    now = datetime(2026, 7, 7, tzinfo=timezone.utc)

    for attempt, seconds in enumerate(RETRY_SECONDS, 1):
        result = service.run_once(now)
        assert result.status == "failed"
        assert result.retry_at == int(now.timestamp() * 1000) + seconds * 1000
        now = datetime.fromtimestamp(result.retry_at / 1000, timezone.utc)
    result = service.run_once(now)
    assert result.retry_at == int(now.timestamp() * 1000) + 1800 * 1000
    assert [retry_delay(i) for i in range(6)] == [30, 120, 600, 1800, 1800, 1800]


def test_metadata_retries_never_upload_twice(tmp_path):
    store = seeded_store(tmp_path, ["one.wav"])
    uploader = FakeUploader()
    metadata = FakeMetadataClient(failures=2)
    service = UploadService(store, uploader, metadata)

    assert service.run_once("2026-07-07T00:00:00Z").status == "uploaded"
    first = service.run_once("2026-07-07T00:00:01Z")
    second = service.run_once(datetime.fromtimestamp(first.retry_at / 1000, timezone.utc))
    completed = service.run_once(datetime.fromtimestamp(second.retry_at / 1000, timezone.utc))

    assert completed.status == "completed"
    assert uploader.calls == ["one.wav"]


def test_restart_after_mark_uploaded_only_registers(tmp_path):
    store = seeded_store(tmp_path, ["one.wav"])
    claimed = store.claim_next("2026-07-07T00:00:00Z")
    store.mark_uploaded(claimed.id, "https://files.test/one.wav")
    uploader = FakeUploader()

    result = UploadService(QueueStore(store.database_path), uploader, FakeMetadataClient()).run_once(
        "2026-07-07T00:00:01Z"
    )

    assert result.status == "completed"
    assert uploader.calls == []


def test_stale_registering_claim_is_recovered(tmp_path):
    store = seeded_store(tmp_path, ["one.wav"])
    item = store.claim_next("2026-07-07T00:00:00Z")
    store.mark_uploaded(item.id, "https://files.test/one.wav")
    registering = store.claim_next("2026-07-07T00:00:01Z")
    assert registering.action == "register"

    result = UploadService(QueueStore(store.database_path), FakeUploader(), FakeMetadataClient()).run_once(
        "2026-07-07T00:05:02Z"
    )
    assert result.status == "completed"


def test_stale_uploading_claim_is_recovered(tmp_path):
    store = seeded_store(tmp_path, ["one.wav"])
    claimed = store.claim_next("2026-07-07T00:00:00Z")
    assert claimed.action == "upload"

    uploader = FakeUploader()
    result = UploadService(QueueStore(store.database_path), uploader, FakeMetadataClient()).run_once(
        "2026-07-07T00:05:01Z"
    )
    assert result.status == "uploaded"
    assert uploader.calls == ["one.wav"]


def test_bottom_layer_timeout_becomes_retryable(tmp_path):
    store = seeded_store(tmp_path, ["one.wav"])

    class TimedOutUploader:
        def upload(self, path):
            raise TimeoutError("socket timed out after 30s")

    result = UploadService(
        store, TimedOutUploader(), FakeMetadataClient()
    ).run_once("2026-07-07T00:00:00Z")

    assert result.status == "failed"
    assert "timed out" in result.error


def test_upload_service_runs_network_call_synchronously(tmp_path, monkeypatch):
    store = seeded_store(tmp_path, ["one.wav"])
    monkeypatch.setattr(
        threading,
        "Thread",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("UploadService must not create timeout threads")
        ),
    )

    result = UploadService(store, FakeUploader(), FakeMetadataClient()).run_once(
        "2026-07-07T00:00:00Z"
    )
    assert result.status == "uploaded"
