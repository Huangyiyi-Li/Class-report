from pathlib import Path
from types import SimpleNamespace
import io
import time

from worker.config import WorkerConfig
from worker.recorder_worker import RecorderWorker, main


def command(name: str):
    return SimpleNamespace(command=name, payload={})


class FakeSession:
    def __init__(self):
        self.started = 0
        self.stopped = 0

    def start(self):
        self.started += 1

    def stop(self):
        self.stopped += 1


def test_commands_control_real_capture_sessions(tmp_path: Path):
    sessions = []

    def session_factory(**kwargs):
        session = FakeSession()
        sessions.append(session)
        return session

    worker = RecorderWorker(
        WorkerConfig(data_root=str(tmp_path), device_no="device-1"),
        emit_event=lambda name, payload: None,
        session_factory=session_factory,
        recover=lambda root, on_error: [],
    )
    worker.startup()

    worker.handle(command("start"))
    worker.handle(command("pause"))
    worker.handle(command("start"))
    keep_running = worker.handle(command("shutdown"))

    assert [session.started for session in sessions] == [1, 1]
    assert [session.stopped for session in sessions] == [1, 1]
    assert keep_running is False


def test_startup_reports_recovered_journals(tmp_path: Path):
    recovered = tmp_path / "recordings" / "recovered.wav"
    events = []
    worker = RecorderWorker(
        WorkerConfig(data_root=str(tmp_path), device_no="device-1"),
        emit_event=lambda name, payload: events.append((name, payload)),
        recover=lambda root, on_error: [recovered],
    )

    worker.startup()

    assert ("recovered", {"path": str(recovered)}) in events
    assert worker.state["recovered"] == 1


def test_capture_error_changes_recording_and_health_state(tmp_path: Path):
    events = []
    captured = {}

    def session_factory(**kwargs):
        captured["on_error"] = kwargs["on_error"]
        captured["session"] = FakeSession()
        return captured["session"]

    worker = RecorderWorker(
        WorkerConfig(data_root=str(tmp_path), device_no="device-1"),
        emit_event=lambda name, payload: events.append((name, payload)),
        session_factory=session_factory,
        recover=lambda root, on_error: [],
    )
    worker.startup()
    worker.handle(command("start"))

    captured["on_error"](OSError("disk full"))

    assert worker.state["recording"] == "error"
    assert worker.state["health"] == "error"
    assert ("error", {"message": "disk full"}) in events
    deadline = time.monotonic() + 1
    while captured["session"].stopped == 0 and time.monotonic() < deadline:
        time.sleep(0.01)
    assert captured["session"].stopped == 1


def test_main_shuts_down_worker_when_stdin_reaches_eof(monkeypatch):
    calls = []
    finalized = []

    class ActiveSession:
        def stop(self):
            finalized.append(True)

    class FakeWorker:
        state = {"recording": "recording"}

        def __init__(self, config):
            self.session = ActiveSession()

        def startup(self):
            calls.append("startup")

        def handle(self, command):
            return True

        def shutdown(self):
            calls.append("shutdown")
            self.session.stop()

    monkeypatch.setattr("worker.recorder_worker.RecorderWorker", FakeWorker)
    monkeypatch.setattr("worker.recorder_worker.sys.stdin", io.StringIO(""))

    assert main() == 0
    assert calls == ["startup", "shutdown"]
    assert finalized == [True]


def test_worker_runs_upload_service_in_background_and_stops_it(tmp_path: Path):
    class UploadService:
        def __init__(self):
            self.calls = 0

        def run_once(self, now):
            self.calls += 1

    service = UploadService()
    worker = RecorderWorker(
        WorkerConfig(data_root=str(tmp_path)),
        emit_event=lambda name, payload: None,
        recover=lambda root, on_error: [],
        upload_service=service,
        upload_poll_seconds=0.01,
    )
    worker.startup()
    deadline = time.monotonic() + 1
    while service.calls == 0 and time.monotonic() < deadline:
        time.sleep(0.01)

    worker.shutdown()
    calls = service.calls
    time.sleep(0.03)
    assert calls > 0
    assert service.calls == calls
