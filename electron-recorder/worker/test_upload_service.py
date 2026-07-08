from datetime import datetime, timezone
from pathlib import Path

from worker.queue_store import QueueStore
from worker.upload_service import RETRY_SECONDS, UploadService, retry_delay


class FakeUploader:
    def __init__(self, fail_paths=()):
        self.fail_paths = set(fail_paths)

    def upload(self, path):
        if Path(path).name in self.fail_paths:
            raise OSError("offline")
        return f"https://files.test/{Path(path).name}"


class FakeMetadataClient:
    def __init__(self):
        self.payloads = []

    def save_audio_file_info(self, payload):
        self.payloads.append(payload)


def seeded_store(tmp_path, names):
    store = QueueStore(tmp_path / "queue.db")
    for index, name in enumerate(names, 1):
        path = tmp_path / name
        path.write_bytes(b"audio")
        store.enqueue({"local_path": str(path), "segment_index": index})
    return store


def test_upload_failure_marks_one_item_and_continues(tmp_path):
    store = seeded_store(tmp_path, ["one.wav", "two.wav"])
    service = UploadService(store, FakeUploader({"one.wav"}), FakeMetadataClient())

    service.run_once("2026-07-07T00:00:00Z")
    result = service.run_once("2026-07-07T00:00:01Z")

    assert store.counts() == {"failed": 1, "completed": 1}
    assert result.status == "completed"


def test_success_uploads_then_registers_metadata(tmp_path):
    store = seeded_store(tmp_path, ["one.wav"])
    metadata = FakeMetadataClient()

    result = UploadService(store, FakeUploader(), metadata).run_once(
        "2026-07-07T00:00:00Z"
    )

    assert result.status == "completed"
    assert metadata.payloads == [
        {
            "segmentIndex": 1,
            "filePath": "https://files.test/one.wav",
            "fileSize": 5,
            "format": "wav",
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
