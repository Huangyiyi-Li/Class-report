from __future__ import annotations

import json
from dataclasses import dataclass

ALLOWED_COMMANDS = {"start", "pause", "stop", "snapshot", "shutdown"}


@dataclass(frozen=True)
class Command:
    id: str
    command: str
    payload: dict


def parse_command(line: str) -> Command:
    data = json.loads(line)
    command = str(data.get("command", ""))
    if command not in ALLOWED_COMMANDS:
        raise ValueError(f"unsupported command: {command}")
    return Command(
        id=str(data.get("id", "")),
        command=command,
        payload=dict(data.get("payload") or {}),
    )


def event(name: str, payload: dict) -> str:
    return json.dumps({"event": name, "payload": payload}, ensure_ascii=False)
