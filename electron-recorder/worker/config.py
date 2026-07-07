from __future__ import annotations

import json
from dataclasses import dataclass, fields
from pathlib import Path, PureWindowsPath


@dataclass(frozen=True)
class WorkerConfig:
    data_root: str = ""
    base_url: str = "https://rest.xxt.cn"
    device_no: str = ""
    school_id: int | None = None
    location_id: str = ""
    segment_seconds: int = 300
    checkpoint_seconds: int = 10
    auto_record_enabled: bool = False
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


def validate_data_root(path: Path, system_drive: str) -> None:
    drive = PureWindowsPath(str(path)).drive.upper().rstrip("\\/")
    protected = system_drive.upper().rstrip("\\/")
    if not drive or drive == protected:
        raise ValueError("录音数据必须保存到非系统盘")
