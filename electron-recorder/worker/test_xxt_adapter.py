import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from windows_client.xxt_upload import XxtDeviceApiClient


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
