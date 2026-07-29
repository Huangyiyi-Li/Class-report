import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from datetime import datetime, timezone

from windows_client.xxt_upload import (
    DeviceAuthError,
    XxtDeviceApiClient,
    XxtUploadManager,
    build_device_auth_payload,
    classify_device_auth_error,
)
from worker.queue_store import QueueStore
from worker.recorder_worker import XxtProductionAdapter
from worker.upload_service import UploadService


def test_device_auth_signs_device_number_with_persisted_device_credential():
    payload = build_device_auth_payload("AABBCCDDEEFF", timestamp=1722067200123)

    assert payload == {
        "deviceNo": "AABBCCDDEEFF",
        "sign": "fcd4bc1c48094cd152812f6ac2619f857ab11918",
        "timestamp": 1722067200123,
    }


def test_device_auth_maps_server_binding_fields_for_local_refresh(monkeypatch):
    client = XxtDeviceApiClient(
        "https://unused.test",
        api_routes={
            "deviceAuth": "http://rest-test.xxt.cn/custom/device-auth",
            "ossToken": "http://rest-test.xxt.cn/custom/oss-token",
            "saveAudioFileInfo": "http://rest-test.xxt.cn/custom/save-audio",
        },
    )
    calls = []

    def post(endpoint, payload, *, auth=True):
        calls.append((endpoint, auth))
        return {
            "accessToken": "token",
            "schoolId": 9001,
            "schoolName": "众享中学",
            "groupId": 701,
            "groupName": "七年级一班",
        }

    monkeypatch.setattr(client, "_post_json", post)
    auth = client.device_auth("AABBCCDDEEFF")

    assert calls == [
        ("http://rest-test.xxt.cn/custom/device-auth", False)
    ]
    assert auth.school_id == 9001
    assert auth.school_name == "众享中学"
    assert auth.user_type == 1
    assert auth.class_id == "701"
    assert auth.classroom == "七年级一班"


def test_device_auth_maps_group_zero_to_public_classroom(monkeypatch):
    client = XxtDeviceApiClient("https://example.test")
    monkeypatch.setattr(
        client,
        "_post_json",
        lambda *_args, **_kwargs: {
            "accessToken": "token",
            "schoolId": 9001,
            "schoolName": "众享中学",
            "groupId": 0,
            "groupName": "公共录播室",
        },
    )
    auth = client.device_auth("AABBCCDDEEFF")
    assert auth.user_type == 2
    assert auth.class_id == "0"
    assert auth.classroom == "公共录播室"


def test_device_auth_classifies_server_failures_for_ui_recovery():
    cases = {
        1: ("device_not_found", True),
        2: ("device_unbound", True),
        3: ("signature_invalid", False),
        4: ("clock_invalid", False),
        5: ("school_not_found", True),
        6: ("class_not_found", True),
    }
    for result_code, expected in cases.items():
        error = classify_device_auth_error(
            {"resultCode": result_code, "resultMsg": "设备认证失败"}
        )
        assert isinstance(error, DeviceAuthError)
        assert (error.reason, error.rebind_required) == expected


def test_device_auth_reads_business_code_from_http_error_body():
    error = classify_device_auth_error(
        RuntimeError('HTTP 400: {"resultCode":4,"resultMsg":"设备认证失败"}')
    )

    assert (error.reason, error.rebind_required) == ("clock_invalid", False)


def test_upload_uses_wisdom_oss_contract_and_server_authorized_directory(tmp_path, monkeypatch):
    path = tmp_path / "one.ogg"
    path.write_bytes(b"audio")
    client = XxtDeviceApiClient("https://example.test")
    calls = []
    uploads = []

    def post(endpoint, payload, *, auth=True):
        calls.append((endpoint, payload, client.token, auth))
        if endpoint.endswith("device-auth"):
            return {"accessToken": "device-token"}
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
            "schoolId": 9001,
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
            "/ai-lesson-eval/audio/save-audio-file-info",
            {
                "schoolId": 9001,
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
                "schoolId": 9001,
                "schoolName": "众享中学",
                "groupId": 701,
                "groupName": "七年级一班",
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
        ("/ai-lesson-eval/audio/save-audio-file-info", "fresh-token", True)
    ]


def test_metadata_registration_refreshes_device_auth_without_using_expiry_fields(monkeypatch):
    client = XxtDeviceApiClient("https://example.test")
    issued = iter(["token-1", "token-2"])
    observed = []

    def post(endpoint, payload, *, auth=True):
        if endpoint.endswith("device-auth"):
            return {
                "accessToken": next(issued),
                "schoolId": 9001,
                "schoolName": "众享中学",
                "groupId": 701,
                "groupName": "七年级一班",
            }
        observed.append((endpoint, client.token))
        assert payload["schoolId"] == 9001
        return {"ok": True}

    monkeypatch.setattr(client, "_post_json", post)
    manager = XxtUploadManager(client, "device-1")
    adapter = XxtProductionAdapter(client, manager)
    payload = {
        "deviceNo": "device-1",
        "segmentIndex": 1,
        "fileName": "one.ogg",
        "filePath": "https://files.test/one.ogg",
        "fileSize": 5,
        "format": "ogg",
        "startTime": "2026-07-25T00:00:00+00:00",
        "endTime": "2026-07-25T00:05:00+00:00",
    }

    adapter.save_audio_file_info(payload)
    adapter.save_audio_file_info(payload)

    assert observed == [
        ("/ai-lesson-eval/audio/save-audio-file-info", "token-1"),
        ("/ai-lesson-eval/audio/save-audio-file-info", "token-2"),
    ]
