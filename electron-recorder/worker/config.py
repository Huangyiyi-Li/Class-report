from __future__ import annotations

import json
import os
import shutil
import tempfile
from dataclasses import asdict, dataclass, fields
from pathlib import Path, PureWindowsPath


LOW_SPACE_BYTES = 5 * 1024**3


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


def validate_data_root(path: Path, system_drive: str) -> None:
    drive = PureWindowsPath(str(path)).drive.upper().rstrip("\\/")
    protected = system_drive.upper().rstrip("\\/")
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
