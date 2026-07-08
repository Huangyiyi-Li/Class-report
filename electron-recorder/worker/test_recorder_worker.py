from pathlib import Path
from types import SimpleNamespace
import io
import time
import threading

from worker.config import WorkerConfig
from worker.recorder_worker import RecorderWorker, main


def command(name: str, payload=None):
    return SimpleNamespace(command=name, payload=payload or {})


class FakeSession:
    def __init__(self):
        self.started = 0
        self.stopped = 0

    def start(self):
        self.started += 1

    def stop(self):
        self.stopped += 1


def test_capture_session_uses_configured_input_device(tmp_path: Path):
    captured = {}

    class Journal:
        rate = 16000
        channels = 1
        sample_width = 2

    class Stream:
        def start(self):
            pass

        def stop(self):
            pass

        def close(self):
            pass

    session = __import__("worker.recorder_worker", fromlist=["CaptureSession"]).CaptureSession(
        WorkerConfig(input_device="mic-2"),
        Journal(),
        Path("ffmpeg.exe"),
        stream_factory=lambda **kwargs: captured.update(kwargs) or Stream(),
    )
    session.start()
    session.stop_event.set()
    session.finalize_queue.put(None)
    session.control_queue.put(session._control_sentinel)
    session._close_stream()

    assert captured["device"] == "mic-2"


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

        def __init__(self, config, config_path=None):
            self.session = ActiveSession()

        def snapshot(self):
            return dict(self.state)

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


def test_shutdown_is_bounded_when_upload_service_blocks(tmp_path: Path):
    entered = threading.Event()

    class BlockingService:
        def run_once(self, now):
            entered.set()
            threading.Event().wait()

    events = []
    worker = RecorderWorker(
        WorkerConfig(data_root=str(tmp_path)),
        emit_event=lambda name, payload: events.append((name, payload)),
        recover=lambda root, on_error: [],
        upload_service=BlockingService(),
        upload_poll_seconds=0.01,
        shutdown_join_seconds=0.05,
    )
    worker.startup()
    assert entered.wait(1)

    started = time.monotonic()
    worker.shutdown()

    assert time.monotonic() - started < 0.5
    assert any("did not stop" in payload["message"] for name, payload in events if name == "error")


def test_snapshot_reports_queue_location_disk_and_latest_error(tmp_path: Path):
    events = []
    worker = RecorderWorker(
        WorkerConfig(data_root=str(tmp_path), location_id="room-101", location_name="一班"),
        emit_event=lambda name, payload: events.append((name, payload)),
        recover=lambda root, on_error: [],
    )
    worker.startup()
    worker._capture_error(OSError("microphone gone"))

    snapshot = [payload for name, payload in events if name == "snapshot"][-1]
    assert snapshot["pending"] == 0
    assert snapshot["location"] == {"locationId": "room-101", "locationName": "一班"}
    assert snapshot["freeDiskBytes"] > 0
    assert snapshot["diskHealth"] in {"healthy", "disk_low", "storage_unavailable"}
    assert snapshot["latestError"] == "microphone gone"


def test_flush_queue_runs_until_no_immediately_claimable_item(tmp_path: Path):
    class Service:
        def __init__(self):
            self.results = [SimpleNamespace(status="uploaded"), SimpleNamespace(status="completed"), None]
            self.calls = 0

        def run_once(self, now):
            self.calls += 1
            return self.results.pop(0)

    service = Service()
    events = []
    worker = RecorderWorker(
        WorkerConfig(data_root=str(tmp_path)),
        emit_event=lambda name, payload: events.append((name, payload)),
        recover=lambda root, on_error: [],
        upload_service=service,
    )
    worker.handle(command("flush_queue"))

    assert service.calls == 3
    assert events[-1][0] == "snapshot"


def test_update_settings_whitelists_and_persists_when_idle(tmp_path: Path):
    config_path = tmp_path / "worker-config.json"
    worker = RecorderWorker(
        WorkerConfig(data_root=str(tmp_path)),
        config_path=config_path,
        emit_event=lambda name, payload: None,
        recover=lambda root, on_error: [],
    )

    worker.handle(command("update_settings", {
        "autoRecordEnabled": True,
        "inputDevice": "mic-2",
        "dataRoot": str(tmp_path / "next"),
        "baseUrl": "https://evil.invalid",
    }))

    saved = WorkerConfig.load(config_path)
    assert saved.auto_record_enabled is True
    assert saved.input_device == "mic-2"
    assert saved.data_root == str(tmp_path / "next")
    assert saved.base_url == "https://rest.xxt.cn"


def test_update_settings_is_rejected_while_recording(tmp_path: Path):
    events = []
    worker = RecorderWorker(
        WorkerConfig(data_root=str(tmp_path)),
        config_path=tmp_path / "worker-config.json",
        emit_event=lambda name, payload: events.append((name, payload)),
        recover=lambda root, on_error: [],
    )
    worker.state["recording"] = "recording"

    worker.handle(command("update_settings", {"inputDevice": "mic-2"}))

    assert any(name == "error" and "录音中" in payload["message"] for name, payload in events)
    assert worker.config.input_device == ""
