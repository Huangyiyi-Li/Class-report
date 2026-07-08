import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from datetime import datetime, timezone

from windows_client.xxt_upload import XxtDeviceApiClient, XxtUploadManager
from worker.queue_store import QueueStore
from worker.recorder_worker import XxtProductionAdapter
from worker.upload_service import UploadService


def test_xxt_legacy_fallback_accepts_worker_metadata_without_key_error(monkeypatch):
    client = XxtDeviceApiClient("https://example.test")
    calls = []

    def post(path, payload, **kwargs):
        calls.append((path, payload))
        if len(calls) == 1:
            raise RuntimeError("primary endpoint rejected payload")
        return {"ok": True}

    monkeypatch.setattr(client, "_post_json", post)
    payload = {
        "code": "device-1",
        "deviceNo": "device-1",
        "schoolId": None,
        "locationId": "room-101",
        "segmentIndex": 3,
        "filePath": "https://files.test/one.ogg",
        "fileSize": 1024,
        "format": "ogg",
        "startTime": "2026-07-07T00:00:00+00:00",
        "endTime": "2026-07-07T00:05:00+00:00",
        "rate": 16000,
        "bits": 16,
        "channel": 1,
        "audioType": 1,
    }

    assert client.save_audio_file_info(payload) == {"ok": True}
    assert calls[1][1]["code"] == "device-1"
    assert calls[1][1]["segmentIndex"] == 3


def test_uploaded_restart_authenticates_then_registers_without_upload(tmp_path, monkeypatch):
    path = tmp_path / "one.ogg"
    path.write_bytes(b"audio")
    store = QueueStore(tmp_path / "queue.db")
    item_id = store.enqueue(
        {
            "local_path": str(path),
            "segment_index": 1,
            "code": "device-1",
            "device_no": "device-1",
            "start_time": "2026-07-07T00:00:00+00:00",
            "end_time": "2026-07-07T00:05:00+00:00",
            "audio_format": "ogg",
        }
    )
    store.claim_next("2026-07-07T00:00:00Z")
    store.mark_uploaded(item_id, "https://files.test/one.ogg")

    client = XxtDeviceApiClient("https://example.test")
    observed = []

    def post(endpoint, payload, *, auth=True):
        observed.append((endpoint, client.token, auth))
        if endpoint.endswith("device-auth"):
            return {
                "accessToken": "fresh-token",
                "expireDate": 4102444800000,
                "schoolId": 1,
                "groupId": 2,
            }
        if len([call for call in observed if "save-audio" in call[0]]) == 1:
            raise RuntimeError("use fallback")
        return {"ok": True}

    monkeypatch.setattr(client, "_post_json", post)
    manager = XxtUploadManager(
        client,
        "device-1",
        uploader_factory=lambda config: (_ for _ in ()).throw(
            AssertionError("uploader must not be created")
        ),
    )
    adapter = XxtProductionAdapter(client, manager)

    result = UploadService(store, adapter, adapter).run_once(
        datetime(2026, 7, 7, 0, 0, 1, tzinfo=timezone.utc)
    )

    assert result.status == "completed"
    assert observed[0][0].endswith("device-auth")
    save_calls = [call for call in observed if "save-audio" in call[0]]
    assert [token for _, token, _ in save_calls] == ["fresh-token", "fresh-token"]
