from __future__ import annotations

import sys

from worker.protocol import event, parse_command


def emit(name: str, payload: dict) -> None:
    print(event(name, payload), flush=True)


def main() -> int:
    state = {"recording": "idle", "upload": "clear", "health": "healthy"}
    emit("ready", state)
    for line in sys.stdin:
        try:
            command = parse_command(line)
            if command.command == "shutdown":
                emit("snapshot", state)
                return 0
            if command.command == "start":
                state["recording"] = "recording"
            elif command.command == "pause":
                state["recording"] = "paused"
            elif command.command == "stop":
                state["recording"] = "idle"
            emit("snapshot", state)
        except Exception as exc:
            emit("error", {"message": str(exc)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
