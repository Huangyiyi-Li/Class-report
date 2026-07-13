from __future__ import annotations

import signal
import sys
import threading
from pathlib import Path

from worker.config import StartupGate, WorkerConfig
from worker.control_server import ControlServer
from worker.recorder_worker import RecorderWorker


class FakeSession:
    def __init__(self, **kwargs):
        self.running = False

    def start(self):
        self.running = True

    def stop(self):
        self.running = False

    def wait_until_ready(self, _timeout):
        return True


def main() -> int:
    runtime_dir = Path(sys.argv[1])
    data_root = runtime_dir / "data"
    config = WorkerConfig(
        data_root=str(data_root), device_no="harness-device", school_id=1,
        location_id="room-1", location_name="Harness Room",
    )
    worker = RecorderWorker(
        config,
        emit_event=lambda _name, _payload: None,
        session_factory=FakeSession,
        recover=lambda _root, _on_error: [],
        startup_gate=lambda _config, _drive: StartupGate(True, "healthy"),
    )
    worker.startup()
    stopped = threading.Event()
    for signal_name in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signal_name, lambda *_args: stopped.set())
    try:
        with ControlServer(worker, runtime_dir):
            stopped.wait()
    finally:
        worker.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
