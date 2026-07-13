from __future__ import annotations

import json
import signal
import sys
import threading
from pathlib import Path

from worker.control_server import ControlServer


class PersistentHarnessWorker:
    def __init__(self, runtime_dir: Path):
        self.state_path = runtime_dir / "harness-state.json"
        self.emit_event = lambda _name, _payload: None
        try:
            self.state = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            self.state = {"recording": "idle", "upload": "clear", "health": "healthy"}

    def snapshot(self):
        return dict(self.state)

    def handle(self, command):
        if command.command == "start":
            self.state["recording"] = "recording"
        elif command.command == "pause":
            self.state["recording"] = "paused"
        elif command.command == "stop":
            self.state["recording"] = "idle"
        self.state_path.write_text(json.dumps(self.state), encoding="utf-8")
        self.emit_event("snapshot", self.snapshot())
        return True


def main() -> int:
    runtime_dir = Path(sys.argv[1])
    stopped = threading.Event()
    for signal_name in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signal_name, lambda *_args: stopped.set())
    with ControlServer(PersistentHarnessWorker(runtime_dir), runtime_dir):
        stopped.wait()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
