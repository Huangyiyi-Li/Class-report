import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from datetime import datetime, timezone

from windows_client.xxt_upload import XxtDeviceApiClient, XxtUploadManager
from worker.queue_store import QueueStore
from worker.recorder_worker import XxtProductionAdapter
from worker.upload_service import UploadService


def test_upload_uses_wisdom_oss_contract_and_server_authorized_directory(tmp_path, monkeypatch):
    path = tmp_path / "one.ogg"
    path.write_bytes(b"audio")
    client = XxtDeviceApiClient("https://example.test")
    calls = []
    uploads = []

    def post(endpoint, payload, *, auth=True):
        calls.append((endpoint, payload, client.token, auth))
        if endpoint.endswith("device-auth"):
            return {
                "accessToken": "device-token",
                "expireDate": 4102444800000,
                "schoolId": 1,
                "schoolName": "测试学校",
                "groupId": 2,
                "groupName": "测试班级",
            }
        return {
            "accessKeyId": "key-id",
            "accessKeySecret": "key-secret",
            "securityToken": "security-token",
            "expireDate": 4102444800000,
            "endpoint": "oss-cn-example.aliyuncs.com",
            "bucketName": "recording-bucket",
            "uploadDir": "recordings/device-1/20260725/",
        }

    class Uploader:
        def __init__(self, config):
            uploads.append(("config", config.bucket, config.endpoint))

        def upload(self, local_path, object_key):
            uploads.append(("upload", Path(local_path).name, object_key))
            return f"https://files.test/{object_key}"

    monkeypatch.setattr(client, "_post_json", post)
    manager = XxtUploadManager(client, "device-1", uploader_factory=Uploader)

    result = manager.upload(path)

    assert [call[0] for call in calls] == [
        "/wisdom/book-reading/device-auth",
        "/wisdom/ali-oss/get-ali-oss-upload-token",
    ]
    assert calls[1][2:] == ("device-token", True)
    assert uploads == [
        ("config", "recording-bucket", "oss-cn-example.aliyuncs.com"),
        ("upload", "one.ogg", "recordings/device-1/20260725/one.ogg"),
    ]
    assert result.endswith("/recordings/device-1/20260725/one.ogg")


def test_audio_metadata_uses_confirmed_server_contract(monkeypatch):
    client = XxtDeviceApiClient("https://example.test")
    client.token = "device-token"
    calls = []

    def post(endpoint, payload, *, auth=True):
        calls.append((endpoint, payload, client.token, auth))
        return {"success": True}

    monkeypatch.setattr(client, "_post_json", post)

    result = client.save_audio_file_info(
        {
            "deviceNo": "device-1",
            "segmentIndex": 3,
            "fileName": "device-1_20260725_003.ogg",
            "filePath": "https://files.test/device-1_20260725_003.ogg",
            "fileSize": 1024,
            "format": "ogg",
            "startTime": "2026-07-25T00:00:00+00:00",
            "endTime": "2026-07-25T00:05:00+00:00",
        }
    )

    assert result == {"success": True}
    assert calls == [
        (
            "/audio/save-audio-file-info",
            {
                "deviceNo": "device-1",
                "segmentIndex": 3,
                "fileName": "device-1_20260725_003.ogg",
                "filePath": "https://files.test/device-1_20260725_003.ogg",
                "fileSize": 1024,
                "fileFormat": "OGG",
                "duration": 300,
                "recordStartTime": "2026-07-25 08:00:00",
                "recordEndTime": "2026-07-25 08:05:00",
                "uploadStatus": 1,
            },
            "device-token",
            True,
        )
    ]


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
    assert save_calls == [
        ("/audio/save-audio-file-info", "fresh-token", True)
    ]
