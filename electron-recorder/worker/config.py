from __future__ import annotations

import json
import os
import shutil
import tempfile
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime
from pathlib import Path, PureWindowsPath
from urllib.parse import urlparse


LOW_SPACE_BYTES = 5 * 1024**3
API_ROUTE_KEYS = frozenset(
    {
        "deviceAuth",
        "gradeClassList",
        "bindDevice",
        "unbindDevice",
        "ossToken",
        "saveAudioFileInfo",
    }
)
DEFAULT_API_ROUTES = {
    "deviceAuth": "http://rest-test.xxt.cn/wisdom/book-reading/device-auth",
    "gradeClassList": "http://rest-test.xxt.cn/wisdom/group/grade-class-list",
    "bindDevice": "http://rest-test.xxt.cn/ai-lesson-eval/recording-device/bind-device",
    "unbindDevice": "http://rest-test.xxt.cn/ai-lesson-eval/recording-device/unbind-device",
    "ossToken": "http://rest-test.xxt.cn/wisdom/ali-oss/get-ali-oss-upload-token",
    "saveAudioFileInfo": "http://rest-test.xxt.cn/ai-lesson-eval/audio/save-audio-file-info",
}
RUNTIME_SETTING_KEYS = {
    "autoRecordEnabled",
    "inputDevice",
    "dataRoot",
    "apiRoutes",
}
BINDING_FIELD_MAP = {
    "deviceNo": "device_no",
    "schoolId": "school_id",
    "schoolName": "school_name",
    "bindType": "bind_type",
    "classroom": "classroom",
    "classId": "class_id",
    "className": "class_name",
    "bindingSource": "binding_source",
    "boundAt": "bound_at",
}
BINDING_KEYS = frozenset(BINDING_FIELD_MAP)


@dataclass(frozen=True)
class StartupGate:
    allowed: bool
    health: str


@dataclass(frozen=True)
class WorkerConfig:
    data_root: str = ""
    base_url: str = "http://rest-test.xxt.cn"
    api_routes: dict[str, str] = field(
        default_factory=lambda: dict(DEFAULT_API_ROUTES)
    )
    device_no: str = ""
    school_id: int | None = None
    school_name: str = ""
    user_type: int | None = None
    bind_type: int | None = None
    classroom: str = ""
    class_id: str = ""
    class_name: str = ""
    binding_source: str = ""
    bound_at: str = ""
    unbind_pending: bool = False
    segment_seconds: int = 300
    checkpoint_seconds: int = 10
    auto_record_enabled: bool = False
    input_device: str = ""
    username: str = ""
    password: str = ""
    mirror_server_url: str = ""

    @classmethod
    def load(cls, path: Path) -> "WorkerConfig":
        if not path.exists():
            return cls()
        payload = json.loads(path.read_text(encoding="utf-8"))
        if "bind_type" not in payload and payload.get("location_type") in {"classroom", "studio"}:
            classroom_binding = payload["location_type"] == "classroom"
            payload["bind_type"] = 1 if classroom_binding else 2
            payload["classroom"] = (
                f"{payload.get('class_name', '').strip()}录音设备"
                if classroom_binding and str(payload.get("class_name") or "").strip()
                else str(payload.get("location_name") or "").strip()
            )
        allowed = {field.name for field in fields(cls)}
        return cls(**{key: value for key, value in payload.items() if key in allowed})

    def save_atomic(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump(asdict(self), stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)


def validate_settings_patch(patch: object, system_drive: str = "C:") -> dict:
    if not isinstance(patch, dict):
        raise ValueError("settings patch must be an object")
    unknown = set(patch) - RUNTIME_SETTING_KEYS
    if unknown:
        raise ValueError(f"settings patch contains forbidden field: {sorted(unknown)[0]}")
    changes = {}
    if "autoRecordEnabled" in patch:
        value = patch["autoRecordEnabled"]
        if type(value) is not bool:
            raise ValueError("autoRecordEnabled must be boolean")
        changes["auto_record_enabled"] = value
    if "inputDevice" in patch:
        value = patch["inputDevice"]
        if not isinstance(value, str):
            raise ValueError("inputDevice must be a string")
        value = value.strip()
        if not value or len(value) > 256 or "\0" in value or "\n" in value or "\r" in value:
            raise ValueError("inputDevice is invalid")
        changes["input_device"] = value
    if "dataRoot" in patch:
        value = patch["dataRoot"]
        if not isinstance(value, str):
            raise ValueError("dataRoot must be a string")
        value = value.strip()
        if not value or len(value) > 1024 or "\0" in value or "\n" in value or "\r" in value:
            raise ValueError("dataRoot is invalid")
        validate_data_root(value, system_drive)
        changes["data_root"] = value
    if "apiRoutes" in patch:
        changes["api_routes"] = validate_api_routes(patch["apiRoutes"])
    return changes


def validate_api_routes(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ValueError("apiRoutes must be an object")
    supplied = set(value)
    if supplied != API_ROUTE_KEYS:
        missing = sorted(API_ROUTE_KEYS - supplied)
        unknown = sorted(supplied - API_ROUTE_KEYS)
        detail = missing[0] if missing else unknown[0]
        raise ValueError(f"apiRoutes fields are invalid: {detail}")
    routes = {}
    for key in API_ROUTE_KEYS:
        route = value[key]
        if not isinstance(route, str):
            raise ValueError(f"apiRoutes.{key} must be a string")
        route = route.strip()
        parsed = urlparse(route)
        if (
            not route
            or len(route) > 2048
            or any(character in route for character in ("\0", "\r", "\n"))
            or parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.username
            or parsed.password
            or parsed.fragment
        ):
            raise ValueError(f"apiRoutes.{key} must be an http/https URL")
        routes[key] = route.rstrip("/")
    return routes


def validate_binding_payload(payload: object) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("binding payload must be an object")
    supplied = set(payload)
    if supplied != BINDING_KEYS:
        missing = sorted(BINDING_KEYS - supplied)
        unknown = sorted(supplied - BINDING_KEYS)
        detail = missing[0] if missing else unknown[0]
        raise ValueError(f"binding payload fields are invalid: {detail}")

    school_id = payload["schoolId"]
    if type(school_id) is not int or school_id <= 0:
        raise ValueError("schoolId must be a positive integer")

    values = {
        "deviceNo": _validate_binding_string(payload["deviceNo"], "deviceNo", 128),
        "schoolName": _validate_binding_string(payload["schoolName"], "schoolName", 256),
        "classroom": _validate_binding_string(payload["classroom"], "classroom", 256),
        "classId": _validate_binding_string(payload["classId"], "classId", 128, allow_empty=True),
        "className": _validate_binding_string(payload["className"], "className", 256, allow_empty=True),
        "boundAt": _validate_binding_string(payload["boundAt"], "boundAt", 64),
    }
    bind_type = payload["bindType"]
    if type(bind_type) is not int or bind_type not in {1, 2}:
        raise ValueError("bindType must be 1 or 2")
    binding_source = payload["bindingSource"]
    if binding_source not in {"mock", "remote"}:
        raise ValueError("bindingSource must be mock or remote")
    if bind_type == 1 and (not values["classId"] or not values["className"]):
        raise ValueError("classroom binding requires classId and className")
    if bind_type == 2 and (values["classId"] or values["className"]):
        raise ValueError("public classroom binding cannot contain class identity")
    try:
        parsed_bound_at = datetime.fromisoformat(values["boundAt"].replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("boundAt must be an ISO-8601 timestamp") from error
    if parsed_bound_at.tzinfo is None:
        raise ValueError("boundAt must include a timezone")

    normalized = {
        "deviceNo": values["deviceNo"],
        "schoolId": school_id,
        "schoolName": values["schoolName"],
        "bindType": bind_type,
        "classroom": values["classroom"],
        "classId": values["classId"] if bind_type == 1 else "",
        "className": values["className"] if bind_type == 1 else "",
        "bindingSource": binding_source,
        "boundAt": values["boundAt"],
    }
    return {BINDING_FIELD_MAP[key]: value for key, value in normalized.items()}


def _validate_binding_string(value: object, field: str, maximum: int, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    normalized = value.strip()
    if (not normalized and not allow_empty) or len(normalized) > maximum:
        raise ValueError(f"{field} is invalid")
    if any(ord(character) < 32 or ord(character) == 127 for character in normalized):
        raise ValueError(f"{field} contains control characters")
    return normalized


def validate_data_root(path: Path | str, system_drive: str) -> None:
    windows_path = PureWindowsPath(str(path))
    drive = windows_path.drive.upper().rstrip("\\/")
    protected = PureWindowsPath(system_drive).drive.upper().rstrip("\\/")
    if not windows_path.is_absolute() or drive.startswith("\\\\"):
        raise ValueError("录音数据目录必须是 Windows 本地绝对路径")
    if not drive or drive == protected:
        raise ValueError("录音数据必须保存到非系统盘")


def evaluate_startup_gate(config: WorkerConfig, system_drive: str) -> StartupGate:
    if not config.data_root:
        return StartupGate(False, "storage_unavailable")
    root = Path(config.data_root)
    try:
        validate_data_root(root, system_drive)
    except ValueError:
        return StartupGate(False, "storage_unavailable")
    if not _ensure_writable(root):
        return StartupGate(False, "storage_unavailable")
    try:
        if _free_bytes(root) < LOW_SPACE_BYTES:
            return StartupGate(False, "disk_low")
    except OSError:
        return StartupGate(False, "storage_unavailable")
    if not all(
        (
            config.device_no,
            config.school_id is not None,
            config.bind_type in {1, 2},
            config.classroom,
        )
    ):
        return StartupGate(False, "binding_required")
    if config.unbind_pending:
        return StartupGate(False, "binding_required")
    return StartupGate(True, "healthy")


def _ensure_writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=path):
            pass
        return True
    except OSError:
        return False


def _free_bytes(path: Path) -> int:
    return shutil.disk_usage(path).free
