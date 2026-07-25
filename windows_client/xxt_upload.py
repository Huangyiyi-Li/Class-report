# -*- coding: utf-8 -*-
"""XXT Android-compatible upload primitives for the Windows recorder."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .api_client import ClassroomApiClient, REQUEST_TIMEOUT_SECONDS


SERVER_TIMEZONE = timezone(timedelta(hours=8))


def device_sign(device_no: str) -> str:
    return hashlib.sha1(f"{device_no}{device_no}".encode("utf-8")).hexdigest()


def build_device_auth_payload(device_no: str, timestamp: int | None = None) -> dict[str, Any]:
    timestamp = timestamp if timestamp is not None else int(datetime.now().timestamp() * 1000)
    return {"deviceNo": device_no, "sign": device_sign(device_no), "timestamp": timestamp}


def build_oss_object_key(file_name: str, upload_dir: str) -> str:
    authorized_prefix = str(upload_dir or "").strip("/")
    if not authorized_prefix:
        raise ValueError("OSS uploadDir is required")
    return f"{authorized_prefix}/{Path(file_name).name}"


@dataclass
class XxtTokenState:
    expire_at: datetime | None = None
    refresh_margin: timedelta = timedelta(minutes=30)

    def needs_refresh(self, now: datetime | None = None) -> bool:
        if not self.expire_at:
            return True
        now = now or datetime.now()
        return self.expire_at - now < self.refresh_margin


@dataclass
class DeviceAuth:
    access_token: str
    expire_at: datetime
    school_id: int
    school_name: str
    unit_id: int
    unit_name: str
    arc_key: str = ""

    @classmethod
    def from_response(cls, data: dict[str, Any]) -> "DeviceAuth":
        return cls(
            access_token=str(data["accessToken"]),
            expire_at=_millis_to_datetime(int(data["expireDate"])),
            school_id=int(data["schoolId"]),
            school_name=str(data.get("schoolName") or ""),
            unit_id=int(data["groupId"]),
            unit_name=str(data.get("groupName") or ""),
            arc_key=str(data.get("arcKey") or ""),
        )


@dataclass
class OssConfig:
    access_key_id: str
    access_key_secret: str
    security_token: str
    bucket: str
    endpoint: str
    expire_at: datetime
    upload_dir: str = ""

    @classmethod
    def from_response(cls, data: dict[str, Any]) -> "OssConfig":
        return cls(
            access_key_id=str(data["accessKeyId"]),
            access_key_secret=str(data["accessKeySecret"]),
            security_token=str(data["securityToken"]),
            bucket=str(data["bucketName"]),
            endpoint=str(data["endpoint"]),
            expire_at=_millis_to_datetime(int(data["expireDate"])),
            upload_dir=str(data["uploadDir"]),
        )

    def public_url(self, object_key: str) -> str:
        return f"https://{self.bucket}.{self.endpoint}/{object_key}"


class SegmentIndexStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.data = self._load()

    def next_index(self, when: datetime) -> int:
        day = when.strftime("%Y%m%d")
        if self.data.get("date") != day:
            self.data = {"date": day, "last_index": 0}
        self.data["last_index"] = int(self.data.get("last_index", 0)) + 1
        self._save()
        return self.data["last_index"]

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _save(self) -> None:
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")


class AliOssUploader:
    """Aliyun OSS uploader using STS credentials.

    `oss2` is optional so the rest of the client can run in simulation mode.
    Install with `pip install oss2` when using the production upload path.
    """

    def __init__(self, oss_config: OssConfig):
        self.oss_config = oss_config

    def upload(self, local_path: str | Path, object_key: str) -> str:
        try:
            import oss2
        except ImportError as exc:
            raise RuntimeError("缺少 oss2，请执行: pip install oss2") from exc

        auth = oss2.StsAuth(
            self.oss_config.access_key_id,
            self.oss_config.access_key_secret,
            self.oss_config.security_token,
        )
        bucket = oss2.Bucket(
            auth,
            f"https://{self.oss_config.endpoint}",
            self.oss_config.bucket,
            connect_timeout=REQUEST_TIMEOUT_SECONDS,
        )
        bucket.put_object_from_file(object_key, str(local_path))
        return self.oss_config.public_url(object_key)


class XxtUploadManager:
    """Coordinates Android-style device auth, OSS token refresh, and upload."""

    def __init__(self, api_client: "XxtDeviceApiClient", device_no: str, uploader_factory=AliOssUploader):
        self.api_client = api_client
        self.device_no = device_no
        self.uploader_factory = uploader_factory
        self.device_auth_data: DeviceAuth | None = None
        self.oss_config: OssConfig | None = None

    def upload(self, local_path: str | Path) -> str:
        self._ensure_device_auth()
        self._ensure_oss_config()
        object_key = build_oss_object_key(
            Path(local_path).name, self.oss_config.upload_dir
        )
        uploader = self.uploader_factory(self.oss_config)
        return uploader.upload(local_path, object_key)

    def _ensure_device_auth(self) -> None:
        state = XxtTokenState(expire_at=self.device_auth_data.expire_at if self.device_auth_data else None)
        if state.needs_refresh():
            self.device_auth_data = self.api_client.device_auth(self.device_no)

    def ensure_device_auth(self) -> DeviceAuth:
        self._ensure_device_auth()
        return self.device_auth_data

    def _ensure_oss_config(self) -> None:
        state = XxtTokenState(expire_at=self.oss_config.expire_at if self.oss_config else None)
        if state.needs_refresh():
            if not self.device_auth_data:
                self._ensure_device_auth()
            self.oss_config = self.api_client.get_oss_upload_token(self.device_auth_data.access_token)


class XxtDeviceApiClient(ClassroomApiClient):
    """Client for the Android recorder's production API shape."""

    def device_auth(self, device_no: str) -> DeviceAuth:
        response = self._post_json("/wisdom/book-reading/device-auth", build_device_auth_payload(device_no), auth=False)
        if "accessToken" not in response:
            raise RuntimeError(response.get("message") or f"设备认证失败: {response}")
        return DeviceAuth.from_response(response)

    def get_oss_upload_token(self, access_token: str) -> OssConfig:
        original_token = self.token
        self.token = access_token
        try:
            response = self._post_json(
                "/wisdom/ali-oss/get-ali-oss-upload-token", {}
            )
            if "accessKeyId" not in response:
                raise RuntimeError(response.get("message") or f"获取 OSS token 失败: {response}")
            return OssConfig.from_response(response)
        finally:
            self.token = original_token

    def save_audio_file_info(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._post_json(
            "/audio/save-audio-file-info", self._server_audio_metadata(payload)
        )

    @staticmethod
    def _server_audio_metadata(payload: dict[str, Any]) -> dict[str, Any]:
        start_time = _record_time(str(payload["startTime"]))
        end_time = _record_time(str(payload["endTime"]))
        file_path = str(payload["filePath"])
        return {
            "deviceNo": str(payload["deviceNo"]),
            "segmentIndex": int(payload["segmentIndex"]),
            "fileName": str(
                payload.get("fileName") or Path(urlparse(file_path).path).name
            ),
            "filePath": file_path,
            "fileSize": int(payload.get("fileSize") or 0),
            "fileFormat": str(payload["format"]).upper(),
            "duration": max(0, int((end_time - start_time).total_seconds())),
            "recordStartTime": start_time.strftime("%Y-%m-%d %H:%M:%S"),
            "recordEndTime": end_time.strftime("%Y-%m-%d %H:%M:%S"),
            "uploadStatus": 1,
        }

    def _post_json(self, path: str, payload: dict[str, Any], *, auth: bool = True) -> dict[str, Any]:
        # Production XXT APIs expect Device-Access-Token instead of Bearer.
        if not auth or not self.token:
            return super()._post_json(path, payload, auth=False)

        import json
        from urllib import request
        from urllib.error import HTTPError

        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Device-Access-Token": self.token,
        }
        req = request.Request(f"{self.server_url}{path}", data=body, headers=headers, method="POST")
        try:
            with request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc


def _millis_to_datetime(value: int) -> datetime:
    return datetime.fromtimestamp(value / 1000)


def _record_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return parsed.replace(tzinfo=SERVER_TIMEZONE)
    return parsed.astimezone(SERVER_TIMEZONE)
