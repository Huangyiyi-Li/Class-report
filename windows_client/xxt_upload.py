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


def device_sign(device_no: str, credential: str | int) -> str:
    return hashlib.sha1(f"{device_no}{credential}".encode("utf-8")).hexdigest()


def build_device_auth_payload(device_no: str, timestamp: int | None = None) -> dict[str, Any]:
    timestamp = timestamp if timestamp is not None else int(datetime.now().timestamp() * 1000)
    return {
        "deviceNo": device_no,
        "sign": device_sign(device_no, timestamp),
        "timestamp": timestamp,
    }


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
    school_id: int | None = None
    school_name: str = ""
    user_type: int | None = None
    class_id: str = ""
    classroom: str = ""

    @classmethod
    def from_response(cls, data: dict[str, Any]) -> "DeviceAuth":
        group_id = data.get("groupId")
        normalized_group_id = int(group_id) if group_id is not None else None
        return cls(
            access_token=str(data["accessToken"]),
            school_id=int(data["schoolId"]) if data.get("schoolId") is not None else None,
            school_name=str(data.get("schoolName") or "").strip(),
            user_type=(
                1 if normalized_group_id != 0 else 2
            ) if normalized_group_id is not None else None,
            class_id=str(normalized_group_id) if normalized_group_id is not None else "",
            classroom=str(data.get("groupName") or "").strip(),
        )


class DeviceAuthError(RuntimeError):
    def __init__(self, reason: str, message: str, *, rebind_required: bool):
        super().__init__(message)
        self.reason = reason
        self.rebind_required = rebind_required


def classify_device_auth_error(value: Any) -> DeviceAuthError:
    if isinstance(value, DeviceAuthError):
        return value
    if isinstance(value, dict):
        code = str(value.get("code") or value.get("errorCode") or "")
        message = str(
            value.get("message")
            or value.get("msg")
            or value.get("error")
            or value
        )
    else:
        code = ""
        message = str(value)
    source = f"{code} {message}".lower()
    cases = (
        (
            "clock_invalid",
            False,
            ("设备时间与服务器时间不一致", "时间不一致", "北京时间", "timestamp"),
        ),
        (
            "signature_invalid",
            False,
            ("签名无效", "签名错误", "invalid signature", "sign_invalid"),
        ),
        (
            "device_unbound",
            True,
            ("未绑定班级", "未绑定教室", "未绑定班级或者教室", "device_unbound"),
        ),
        (
            "device_not_found",
            True,
            ("设备不存在", "device_not_found", "device not found"),
        ),
        (
            "school_not_found",
            True,
            ("学校不存在", "school_not_found", "school not found"),
        ),
        (
            "class_not_found",
            True,
            ("班级不存在", "class_not_found", "class not found"),
        ),
    )
    for reason, rebind_required, keywords in cases:
        if any(keyword in source for keyword in keywords):
            return DeviceAuthError(
                reason, message or "设备认证失败", rebind_required=rebind_required
            )
    return DeviceAuthError(
        "device_auth_failed",
        message or "设备认证失败",
        rebind_required=False,
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

    def __init__(
        self,
        api_client: "XxtDeviceApiClient",
        device_no: str,
        uploader_factory=AliOssUploader,
        on_device_auth=None,
    ):
        self.api_client = api_client
        self.device_no = device_no
        self.uploader_factory = uploader_factory
        self.on_device_auth = on_device_auth
        self.device_auth_data: DeviceAuth | None = None
        self.oss_config: OssConfig | None = None

    def upload(self, local_path: str | Path) -> str:
        self._ensure_oss_config()
        object_key = build_oss_object_key(
            Path(local_path).name, self.oss_config.upload_dir
        )
        uploader = self.uploader_factory(self.oss_config)
        return uploader.upload(local_path, object_key)

    def _ensure_device_auth(self, *, refresh: bool = False) -> None:
        if refresh or self.device_auth_data is None:
            self.device_auth_data = self.api_client.device_auth(self.device_no)
            if self.on_device_auth is not None:
                self.on_device_auth(self.device_auth_data)

    def ensure_device_auth(self) -> DeviceAuth:
        # The confirmed response contract exposes only accessToken, so refresh
        # before each authenticated metadata request instead of inferring TTL.
        self._ensure_device_auth(refresh=True)
        return self.device_auth_data

    def _ensure_oss_config(self) -> None:
        state = XxtTokenState(expire_at=self.oss_config.expire_at if self.oss_config else None)
        if state.needs_refresh():
            self._ensure_device_auth(refresh=True)
            self.oss_config = self.api_client.get_oss_upload_token(self.device_auth_data.access_token)


class XxtDeviceApiClient(ClassroomApiClient):
    """Client for the Android recorder's production API shape."""

    def __init__(
        self,
        server_url: str,
        token: str = "",
        *,
        api_routes: dict[str, str] | None = None,
    ):
        super().__init__(server_url, token)
        self.api_routes = dict(api_routes or {})

    def _route(self, key: str, fallback: str) -> str:
        return str(self.api_routes.get(key) or fallback)

    def device_auth(self, device_no: str) -> DeviceAuth:
        try:
            response = self._post_json(
                self._route(
                    "deviceAuth", "/wisdom/book-reading/device-auth"
                ),
                build_device_auth_payload(device_no),
                auth=False,
            )
        except Exception as exc:
            raise classify_device_auth_error(exc) from exc
        payload = (
            response.get("data")
            if isinstance(response, dict) and isinstance(response.get("data"), dict)
            else response
        )
        if not isinstance(payload, dict) or "accessToken" not in payload:
            raise classify_device_auth_error(response)
        return DeviceAuth.from_response(payload)

    def get_oss_upload_token(self, access_token: str) -> OssConfig:
        original_token = self.token
        self.token = access_token
        try:
            response = self._post_json(
                self._route(
                    "ossToken",
                    "/wisdom/ali-oss/get-ali-oss-upload-token",
                ),
                {},
            )
            if "accessKeyId" not in response:
                raise RuntimeError(response.get("message") or f"获取 OSS token 失败: {response}")
            return OssConfig.from_response(response)
        finally:
            self.token = original_token

    def save_audio_file_info(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._post_json(
            self._route(
                "saveAudioFileInfo",
                "/ai-lesson-eval/audio/save-audio-file-info",
            ),
            self._server_audio_metadata(payload),
        )

    @staticmethod
    def _server_audio_metadata(payload: dict[str, Any]) -> dict[str, Any]:
        start_time = _record_time(str(payload["startTime"]))
        end_time = _record_time(str(payload["endTime"]))
        file_path = str(payload.get("filePath") or "")
        upload_status = int(payload.get("uploadStatus") or 1)
        metadata = {
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
            "uploadStatus": upload_status,
        }
        if upload_status == 3:
            metadata["failReason"] = str(payload.get("failReason") or "").strip()
        return metadata

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
        req = request.Request(
            self._request_url(path), data=body, headers=headers, method="POST"
        )
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
