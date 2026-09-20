"""Bounded, best-effort diagnostics independent of the desktop window."""
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from worker.config import validate_data_root


def redact(value):
    if isinstance(value, dict):
        return {key: "[REDACTED]" if re.search(
            r"password|token|secret|authorization|cookie|access.?key|credential",
            key, re.I
        ) else redact(child) for key, child in value.items()}
    if isinstance(value, list):
        return [redact(child) for child in value]
    if isinstance(value, str):
        value = re.sub(
            r'''(?i)((?:[\w-]*(?:token|secret|password|authorization|cookie|access.?key|credential)[\w-]*)["']?\s*[:=]\s*)(?:"[^"]*"|'[^']*'|[^\s,;}]+)''',
            r"\1[REDACTED]", value)
        return re.sub(r"(?i)Bearer\s+\S+", "Bearer [REDACTED]", value)[:2000]
    return value


class DiagnosticArchive:
    def __init__(self, root, *, max_bytes=2 * 1024 * 1024,
                 now=lambda: datetime.now(timezone.utc), platform=sys.platform):
        self.root = str(root)
        self.max_bytes = max_bytes
        self.now = now
        self.platform = platform
        self.status = {"status": "pending"}

    def write(self, snapshot):
        try:
            if not self.root:
                raise ValueError("data root unavailable")
            if self.platform == "win32":
                validate_data_root(self.root, os.environ.get("SystemDrive", "C:"))
            elif not Path(self.root).is_absolute():
                raise ValueError("data root must be absolute")
            now = self.now()
            folder = Path(self.root) / "logs" / "diagnostics"
            folder.mkdir(parents=True, exist_ok=True)
            day = now.strftime("%Y-%m-%d")
            target = folder / f"worker-{day}.jsonl"
            line = json.dumps({"recordedAt": now.isoformat(), "snapshot": redact(snapshot)}, ensure_ascii=False) + "\n"
            if len(line.encode("utf-8")) > self.max_bytes:
                raise ValueError("diagnostic snapshot too large")
            if target.exists() and target.stat().st_size + len(line.encode("utf-8")) > self.max_bytes:
                target.replace(folder / f"worker-{day}.previous.jsonl")
            with target.open("a", encoding="utf-8") as output:
                output.write(line)
            cutoff = (now - timedelta(days=6)).strftime("%Y-%m-%d")
            for entry in folder.iterdir():
                match = re.fullmatch(r"worker-(\d{4}-\d{2}-\d{2})(?:\.previous)?\.jsonl", entry.name)
                if match and match[1] < cutoff and entry.is_file():
                    entry.unlink()
            self.status = {"status": "saved", "savedAt": now.isoformat(), "directory": str(folder)}
            return True
        except Exception as error:
            # Never stop capture because a diagnostic disk write failed.
            self.status = {"status": "failed", "errorType": type(error).__name__}
            return False
