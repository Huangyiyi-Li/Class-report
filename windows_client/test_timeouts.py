import sys
from types import SimpleNamespace

from windows_client.api_client import ClassroomApiClient
from windows_client.xxt_upload import AliOssUploader, OssConfig


def test_http_requests_use_thirty_second_timeout(monkeypatch):
    observed = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self):
            return b'{"ok": true}'

    monkeypatch.setattr(
        "windows_client.api_client.request.urlopen",
        lambda request, timeout: observed.append(timeout) or Response(),
    )

    ClassroomApiClient("https://example.test").save_audio_file_info({})
    assert observed == [30]


def test_oss_put_uses_thirty_second_connect_timeout(tmp_path, monkeypatch):
    observed = []

    class Bucket:
        def __init__(self, auth, endpoint, bucket, connect_timeout):
            observed.append(connect_timeout)

        def put_object_from_file(self, object_key, local_path):
            observed.append((object_key, local_path))

    fake_oss2 = SimpleNamespace(StsAuth=lambda *args: object(), Bucket=Bucket)
    monkeypatch.setitem(sys.modules, "oss2", fake_oss2)
    path = tmp_path / "one.ogg"
    path.write_bytes(b"audio")
    config = OssConfig("id", "secret", "token", "bucket", "endpoint", None)

    AliOssUploader(config).upload(path, "one.ogg")

    assert observed == [30, ("one.ogg", str(path))]
