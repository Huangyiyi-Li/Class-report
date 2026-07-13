from __future__ import annotations

import json
import os
import shutil
import tempfile
from dataclasses import asdict, dataclass, fields
from pathlib import Path, PureWindowsPath


LOW_SPACE_BYTES = 5 * 1024**3
RUNTIME_SETTING_KEYS = {"autoRecordEnabled", "inputDevice", "dataRoot"}


@dataclass(frozen=True)
class StartupGate:
    allowed: bool
    health: str


@dataclass(frozen=True)
class WorkerConfig:
    data_root: str = ""
    base_url: str = "https://rest.xxt.cn"
    device_no: str = ""
    school_id: int | None = None
    location_id: str = ""
    location_name: str = ""
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
    return changes


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
            config.location_id,
            config.location_name,
        )
    ):
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
