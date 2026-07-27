from pathlib import Path
from types import SimpleNamespace
import sqlite3
import time
import threading

import pytest

from worker.config import StartupGate, WorkerConfig
from worker.recorder_worker import RecorderWorker, main, run_worker


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

    def wait_until_ready(self, timeout):
        return True


def allow_startup(config, system_drive):
    return StartupGate(True, "healthy")


def require_binding(config, system_drive):
    allowed = bool(
        config.data_root
        and config.device_no
        and config.school_id is not None
        and config.bind_type in {1, 2}
        and config.classroom
    )
    return StartupGate(allowed, "healthy" if allowed else "binding_required")


def classroom_binding(**overrides):
    return {
        "deviceNo": "AABBCCDDEEFF",
        "schoolId": 1001,
        "schoolName": "星河实验学校",
        "bindType": 1,
        "classroom": "一年级一班录音设备",
        "classId": "class-101",
        "className": "一年级一班",
        "bindingSource": "mock",
        "boundAt": "2026-07-15T08:00:00.000Z",
    } | overrides


class FakeUploadService:
    def __init__(self, store, config):
        self.store = store
        self.config = config
        self.calls = 0

    def run_once(self, now):
        self.calls += 1
        return None


def test_apply_binding_activates_initially_blocked_worker_without_restart(tmp_path: Path):
    config_path = tmp_path / "worker-config.json"
    original = WorkerConfig(data_root=str(tmp_path))
    original.save_atomic(config_path)
    services = []

    def upload_factory(config, store):
        service = FakeUploadService(store, config)
        services.append(service)
        return service

    worker = RecorderWorker(
        original,
        config_path=config_path,
        emit_event=lambda *_: None,
        recover=lambda *_args, **_kwargs: [],
        startup_gate=require_binding,
        upload_service_factory=upload_factory,
        upload_poll_seconds=10,
    )
    worker.startup()
    assert worker.state["health"] == "binding_required"
    assert worker.queue_store is None

    worker.execute_command(command("apply_binding", classroom_binding()))

    assert worker.config.bind_type == 1
    assert worker.snapshot()["binding"]["classId"] == "class-101"
    assert worker.snapshot()["health"] == "healthy"
    assert worker.state["recording"] == "idle"
    assert WorkerConfig.load(config_path) == worker.config
    assert worker.queue_store is not None
    assert worker.upload_service is None
    assert worker._upload_thread is None
    assert worker.state["upload"] == "mock_blocked"
    assert services == []
    worker.shutdown()


def test_remote_binding_starts_the_production_upload_boundary(tmp_path: Path):
    config_path = tmp_path / "worker-config.json"
    original = WorkerConfig(data_root=str(tmp_path))
    original.save_atomic(config_path)
    services = []

    def upload_factory(config, store):
        service = FakeUploadService(store, config)
        services.append(service)
        return service

    worker = RecorderWorker(
        original,
        config_path=config_path,
        emit_event=lambda *_: None,
        recover=lambda *_args, **_kwargs: [],
        startup_gate=require_binding,
        upload_service_factory=upload_factory,
        upload_poll_seconds=10,
    )
    worker.startup()

    worker.execute_command(command("apply_binding", classroom_binding(bindingSource="remote")))

    assert worker.upload_service is services[0]
    assert worker._upload_thread is not None
    assert worker.state["upload"] == "clear"
    worker.shutdown()


def test_invalid_binding_preserves_configuration_and_runtime_resources(tmp_path: Path):
    config_path = tmp_path / "worker-config.json"
    original = WorkerConfig(data_root=str(tmp_path))
    original.save_atomic(config_path)
    worker = RecorderWorker(
        original,
        config_path=config_path,
        emit_event=lambda *_: None,
        recover=lambda *_args, **_kwargs: [],
        startup_gate=require_binding,
        upload_service_factory=lambda config, store: FakeUploadService(store, config),
    )
    worker.startup()
    previous_state = dict(worker.state)

    worker.handle(command("apply_binding", classroom_binding(classroom="")))

    assert WorkerConfig.load(config_path) == original
    assert worker.config == original
    assert worker.queue_store is None
    assert worker.upload_service is None
    assert worker.state["health"] == previous_state["health"]
    assert worker.state["recording"] == previous_state["recording"]


def test_clear_binding_preserves_queue_and_device_identity_but_blocks_recording(tmp_path: Path):
    config_path = tmp_path / "worker-config.json"
    config = WorkerConfig(
        data_root=str(tmp_path),
        device_no="AABBCCDDEEFF",
        school_id=1001,
        school_name="星河实验学校",
        bind_type=1,
        classroom="1.1班录音设备",
        class_id="101",
        class_name="1.1班",
        binding_source="remote",
        bound_at="2026-07-15T08:00:00.000Z",
    )
    config.save_atomic(config_path)
    worker = RecorderWorker(
        config,
        config_path=config_path,
        emit_event=lambda *_: None,
        recover=lambda *_args, **_kwargs: [],
        startup_gate=require_binding,
        upload_service_factory=lambda candidate, store: FakeUploadService(store, candidate),
    )
    worker.startup()
    queue_store = worker.queue_store

    worker.execute_command(command("prepare_unbind"))

    assert worker.config.unbind_pending is True
    assert worker.snapshot()["binding"]["deviceNo"] == "AABBCCDDEEFF"
    assert worker.state["health"] == "binding_required"
    assert worker.upload_service is None
    assert WorkerConfig.load(config_path).unbind_pending is True

    worker.execute_command(command("clear_binding"))

    assert worker.config.device_no == "AABBCCDDEEFF"
    assert worker.config.school_id is None
    assert worker.config.bind_type is None
    assert worker.config.unbind_pending is False
    assert worker.snapshot()["binding"] is None
    assert worker.state["health"] == "binding_required"
    assert worker.queue_store is queue_store
    assert worker.upload_service is None
    assert WorkerConfig.load(config_path) == worker.config
    worker.shutdown()


def test_binding_activation_failure_does_not_persist_or_swap_runtime(tmp_path: Path):
    config_path = tmp_path / "worker-config.json"
    original = WorkerConfig(data_root=str(tmp_path))
    original.save_atomic(config_path)
    worker = RecorderWorker(
        original,
        config_path=config_path,
        emit_event=lambda *_: None,
        recover=lambda *_args, **_kwargs: [],
        startup_gate=require_binding,
        upload_service_factory=lambda _config, _store: (_ for _ in ()).throw(RuntimeError("auth setup failed")),
    )
    worker.startup()

    worker.handle(command("apply_binding", classroom_binding(bindingSource="remote")))

    assert WorkerConfig.load(config_path) == original
    assert worker.config == original
    assert worker.queue_store is None
    assert worker.upload_service is None
    assert worker.state["health"] == "binding_required"


@pytest.mark.parametrize("recording_state", ["starting", "recording"])
def test_apply_binding_is_rejected_during_active_recording(tmp_path: Path, recording_state):
    config_path = tmp_path / "worker-config.json"
    original = WorkerConfig(data_root=str(tmp_path))
    original.save_atomic(config_path)
    worker = RecorderWorker(
        original,
        config_path=config_path,
        emit_event=lambda *_: None,
        startup_gate=require_binding,
        upload_service_factory=lambda config, store: FakeUploadService(store, config),
    )
    worker.state["recording"] = recording_state

    worker.handle(command("apply_binding", classroom_binding()))

    assert worker.config == original
    assert WorkerConfig.load(config_path) == original
    assert worker.queue_store is None


def test_idle_rebind_replaces_upload_service_without_rewriting_queue_metadata(tmp_path: Path):
    config_path = tmp_path / "worker-config.json"
    first = WorkerConfig(
        data_root=str(tmp_path),
        device_no="OLDDEVICE",
        school_id=7,
        school_name="旧学校",
        bind_type=1,
        classroom="旧班级录音设备",
        class_id="old-class",
        class_name="旧班级",
        binding_source="remote",
        bound_at="2026-07-14T08:00:00.000Z",
    )
    first.save_atomic(config_path)
    services = []

    def upload_factory(config, store):
        service = FakeUploadService(store, config)
        services.append(service)
        return service

    worker = RecorderWorker(
        first,
        config_path=config_path,
        emit_event=lambda *_: None,
        recover=lambda *_args, **_kwargs: [],
        startup_gate=require_binding,
        upload_service_factory=upload_factory,
        upload_poll_seconds=10,
    )
    worker.startup()
    worker.queue_store.enqueue({
        "local_path": str(tmp_path / "old.ogg"),
        "segment_index": 1,
        "device_no": "OLDDEVICE",
        "code": "OLDDEVICE",
        "school_id": 7,
        "location_id": "old-room",
    })

    worker.execute_command(command("apply_binding", classroom_binding(bindingSource="remote")))

    with sqlite3.connect(worker.queue_store.database_path) as connection:
        metadata = connection.execute(
            "SELECT device_no, school_id, location_id FROM segments WHERE local_path = ?",
            (str(tmp_path / "old.ogg"),),
        ).fetchone()
    assert metadata == ("OLDDEVICE", 7, "old-room")
    assert worker.upload_service is services[-1]
    assert worker.upload_service.config.device_no == "AABBCCDDEEFF"
    assert len(services) == 2
    worker.shutdown()


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
        startup_gate=allow_startup,
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
        startup_gate=allow_startup,
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
        startup_gate=allow_startup,
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


def test_recording_is_published_only_after_session_reports_durable_write(tmp_path: Path):
    captured = {}
    def session_factory(**kwargs):
        captured.update(kwargs)
        return FakeSession()
    worker = RecorderWorker(
        WorkerConfig(data_root=str(tmp_path), device_no="device-1"),
        session_factory=session_factory, recover=lambda *_: [],
        startup_gate=allow_startup, emit_event=lambda *_: None,
    )
    worker.startup()
    worker.handle(command("start"))
    assert worker.state["recording"] == "recording"


def test_open_stream_without_audio_times_out_as_microphone_unavailable(tmp_path: Path):
    class SilentSession(FakeSession):
        def wait_until_ready(self, timeout): return False
    worker = RecorderWorker(
        WorkerConfig(data_root=str(tmp_path), device_no="device-1"),
        session_factory=lambda **_: SilentSession(), recover=lambda *_: [],
        startup_gate=allow_startup, emit_event=lambda *_: None,
        session_ready_timeout=0.01, capture_retry_delays=(1,),
    )
    worker.startup()
    worker.handle(command("start"))
    assert worker.session is None
    assert worker.state["recording"] == "microphone_unavailable"
    assert "durable audio" in worker.state["latestError"]
    worker.handle(command("stop"))


def test_missing_microphone_maps_to_microphone_unavailable(tmp_path: Path):
    class MissingMicrophone(FakeSession):
        def start(self): raise RuntimeError("No input device")
    sessions = []
    def session_factory(**_):
        session = MissingMicrophone()
        sessions.append(session)
        return session
    worker = RecorderWorker(
        WorkerConfig(data_root=str(tmp_path), device_no="device-1"),
        session_factory=session_factory, recover=lambda *_: [],
        startup_gate=allow_startup, emit_event=lambda *_: None,
    )
    worker.startup()
    worker.handle(command("start"))
    assert worker.session is None
    assert worker.state["recording"] == "microphone_unavailable"
    assert "No input device" in worker.state["latestError"]
    assert sessions[0].stopped == 1
    worker.handle(command("stop"))


def test_unexpected_capture_failure_retries_and_stop_cancels_future_retry(tmp_path: Path):
    callbacks, sessions = [], []
    def session_factory(**kwargs):
        callbacks.append(kwargs)
        session = FakeSession()
        sessions.append(session)
        return session
    worker = RecorderWorker(
        WorkerConfig(data_root=str(tmp_path), device_no="device-1"),
        session_factory=session_factory, recover=lambda *_: [],
        startup_gate=allow_startup, emit_event=lambda *_: None,
        capture_retry_delays=(0.01, 0.02),
    )
    worker.startup()
    worker.handle(command("start"))
    callbacks[0]["on_error"](OSError("device disconnected"))
    deadline = time.monotonic() + 1
    while len(sessions) < 2 and time.monotonic() < deadline: time.sleep(0.01)
    assert len(sessions) == 2
    callbacks[1]["on_error"](OSError("device disconnected again"))
    worker.handle(command("stop"))
    time.sleep(0.05)
    assert len(sessions) == 2


def test_stop_waits_for_inflight_retry_start_and_leaves_no_session_or_timer(tmp_path: Path):
    entered, release = threading.Event(), threading.Event()
    sessions = []
    class BarrierSession(FakeSession):
        def start(self):
            entered.set()
            release.wait(1)
            super().start()
    def factory(**_):
        session = BarrierSession() if sessions else FakeSession()
        sessions.append(session)
        return session
    worker = RecorderWorker(
        WorkerConfig(data_root=str(tmp_path), device_no="device-1"),
        session_factory=factory, recover=lambda *_: [], startup_gate=allow_startup,
        emit_event=lambda *_: None, capture_retry_delays=(0.01,),
    )
    worker.startup(); worker.handle(command("start"))
    worker._capture_error(OSError("disconnect"))
    assert entered.wait(1)
    stopper = threading.Thread(target=lambda: worker.handle(command("stop")))
    stopper.start(); time.sleep(0.02); release.set(); stopper.join(1)
    assert not stopper.is_alive()
    assert worker.session is None
    assert worker._capture_retry_timer is None


def test_shutdown_waits_for_inflight_retry_and_invalidates_capture(tmp_path: Path):
    entered, release = threading.Event(), threading.Event()
    sessions = []

    class BarrierSession(FakeSession):
        def start(self):
            entered.set()
            release.wait(1)
            super().start()

    def factory(**_):
        session = BarrierSession() if sessions else FakeSession()
        sessions.append(session)
        return session

    worker = RecorderWorker(
        WorkerConfig(data_root=str(tmp_path), device_no="device-1"),
        session_factory=factory, recover=lambda *_: [], startup_gate=allow_startup,
        emit_event=lambda *_: None, capture_retry_delays=(0.01,),
    )
    worker.startup()
    worker.handle(command("start"))
    worker._capture_error(OSError("disconnect"))
    assert entered.wait(1)

    shutdown = threading.Thread(target=worker.shutdown)
    shutdown.start()
    time.sleep(0.02)
    assert shutdown.is_alive()
    release.set()
    shutdown.join(1)

    assert not shutdown.is_alive()
    assert worker._desired_recording is False
    assert worker.session is None
    assert worker._capture_retry_timer is None


def test_main_lifetime_is_not_tied_to_stdin_eof(monkeypatch, tmp_path):
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

    class FakeControlServer:
        def __init__(self, worker, runtime_dir, **_kwargs):
            calls.append(("server", runtime_dir))

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    class ReturningEvent:
        def wait(self):
            calls.append("wait")

        def set(self):
            pass

    monkeypatch.setattr("worker.recorder_worker.RecorderWorker", FakeWorker)
    monkeypatch.setattr("worker.recorder_worker.ControlServer", FakeControlServer)
    monkeypatch.setattr("worker.recorder_worker.threading.Event", ReturningEvent)
    monkeypatch.setenv("RECORDER_RUNTIME_DIR", str(tmp_path))

    assert main() == 0
    assert calls == ["startup", ("server", tmp_path), "wait", "shutdown"]
    assert finalized == [True]


def test_competing_worker_main_loser_never_constructs_or_starts_worker(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    WorkerConfig(data_root=str(tmp_path)).save_atomic(config_path)
    monkeypatch.setenv("RECORDER_RUNTIME_DIR", str(tmp_path / "runtime"))
    stop = threading.Event()
    constructed = []
    started = []
    results = []

    class Worker:
        queue_store = None
        def __init__(self, *_args, **_kwargs): constructed.append(self)
        def startup(self): started.append(self)
        def snapshot(self): return {"recording": "idle"}
        def shutdown(self): pass

    threads = [threading.Thread(target=lambda: results.append(run_worker(config_path, stop, Worker))) for _ in range(2)]
    for thread in threads: thread.start()
    deadline = time.monotonic() + 1
    while 2 not in results and time.monotonic() < deadline: time.sleep(0.01)
    stop.set()
    for thread in threads: thread.join()
    assert sorted(results) == [0, 2]
    assert len(constructed) == 1
    assert len(started) == 1


def test_competing_auto_start_loser_never_enters_capture_startup(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    WorkerConfig(data_root=str(tmp_path), auto_record_enabled=True).save_atomic(config_path)
    monkeypatch.setenv("RECORDER_RUNTIME_DIR", str(tmp_path / "runtime"))
    stop = threading.Event()
    captures = []
    results = []

    class Worker:
        queue_store = None
        def __init__(self, *_args, **_kwargs): pass
        def startup(self): captures.append("capture")
        def snapshot(self): return {"recording": "recording"}
        def shutdown(self): pass

    threads = [threading.Thread(target=lambda: results.append(run_worker(config_path, stop, Worker))) for _ in range(2)]
    for thread in threads: thread.start()
    deadline = time.monotonic() + 1
    while 2 not in results and time.monotonic() < deadline: time.sleep(0.01)
    stop.set()
    for thread in threads: thread.join()
    assert sorted(results) == [0, 2]
    assert captures == ["capture"]


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
        startup_gate=allow_startup,
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
        startup_gate=allow_startup,
    )
    worker.startup()
    assert entered.wait(1)

    started = time.monotonic()
    worker.shutdown()

    assert time.monotonic() - started < 0.5
    assert any("did not stop" in payload["message"] for name, payload in events if name == "error")


def test_snapshot_reports_queue_binding_disk_and_latest_error(tmp_path: Path):
    events = []
    worker = RecorderWorker(
        WorkerConfig(
            data_root=str(tmp_path),
            device_no="device-1",
            school_id=7,
            school_name="示例学校",
            bind_type=1,
            classroom="一班录音设备",
            class_id="class-1",
            class_name="一班",
        ),
        emit_event=lambda name, payload: events.append((name, payload)),
        recover=lambda root, on_error: [],
        startup_gate=allow_startup,
    )
    worker.startup()
    worker._capture_error(OSError("microphone gone"))

    snapshot = [payload for name, payload in events if name == "snapshot"][-1]
    assert snapshot["pending"] == 0
    assert snapshot["binding"]["classroom"] == "一班录音设备"
    assert "location" not in snapshot
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


def test_update_settings_rejects_unknown_fields_without_persisting_partial_changes(tmp_path: Path):
    config_path = tmp_path / "worker-config.json"
    events = []
    worker = RecorderWorker(
        WorkerConfig(data_root=str(tmp_path)),
        config_path=config_path,
        emit_event=lambda name, payload: events.append((name, payload)),
        recover=lambda root, on_error: [],
        startup_gate=allow_startup,
    )

    worker.handle(command("update_settings", {
        "autoRecordEnabled": True,
        "inputDevice": "mic-2",
        "dataRoot": str(tmp_path),
        "baseUrl": "https://evil.invalid",
    }))

    saved = WorkerConfig.load(config_path)
    assert saved.auto_record_enabled is False
    assert saved.input_device == ""
    assert saved.base_url == "https://rest.xxt.cn"
    assert any(name == "error" and "forbidden field" in payload["message"] for name, payload in events)


def test_update_settings_is_rejected_while_recording(tmp_path: Path):
    events = []
    config_path = tmp_path / "worker-config.json"
    original = WorkerConfig(data_root=str(tmp_path))
    original.save_atomic(config_path)
    worker = RecorderWorker(
        original,
        config_path=config_path,
        emit_event=lambda name, payload: events.append((name, payload)),
        recover=lambda root, on_error: [],
    )
    worker.state["recording"] = "recording"

    worker.handle(command("update_settings", {"inputDevice": "mic-2"}))

    assert any(name == "error" and "录音中" in payload["message"] for name, payload in events)
    assert worker.config.input_device == ""
    assert WorkerConfig.load(config_path).input_device == ""


def test_auto_record_starts_exactly_once_after_recovery_and_queue_initialization(tmp_path: Path):
    order = []
    sessions = []

    def recover(root, on_error):
        order.append("recovery")
        return []

    def session_factory(**kwargs):
        assert order == ["recovery"]
        assert kwargs["journal"].device_id == "device-1"
        session = FakeSession()
        sessions.append(session)
        return session

    worker = RecorderWorker(
        WorkerConfig(
            data_root=str(tmp_path),
            device_no="device-1",
            school_id=7,
            bind_type=1,
            classroom="一班录音设备",
            auto_record_enabled=True,
        ),
        emit_event=lambda name, payload: None,
        session_factory=session_factory,
        recover=recover,
        startup_gate=allow_startup,
    )

    worker.startup()
    worker.maybe_auto_start()

    assert len(sessions) == 1
    assert sessions[0].started == 1


def test_failed_gate_blocks_both_automatic_and_manual_recording(tmp_path: Path):
    events = []
    sessions = []
    worker = RecorderWorker(
        WorkerConfig(data_root=str(tmp_path), auto_record_enabled=True),
        emit_event=lambda name, payload: events.append((name, payload)),
        session_factory=lambda **kwargs: sessions.append(FakeSession()),
        recover=lambda root, on_error: [],
        startup_gate=lambda config, system_drive: StartupGate(False, "binding_required"),
    )

    worker.startup()
    worker.handle(command("start"))

    assert sessions == []
    assert worker.state["health"] == "binding_required"
    assert worker.state["recording"] != "recording"
    assert any(name == "error" for name, payload in events)


def test_empty_data_root_does_not_initialize_storage_in_current_directory(monkeypatch):
    initialized = []
    monkeypatch.setattr(
        "worker.recorder_worker.QueueStore",
        lambda path: initialized.append(path),
    )

    worker = RecorderWorker(WorkerConfig(data_root=""))

    assert initialized == []
    assert worker.recordings_dir is None


@pytest.mark.parametrize("data_root", ["relative-data", "C:/system-data"])
def test_invalid_data_root_never_creates_storage_before_or_during_startup(
    tmp_path: Path, monkeypatch, data_root
):
    monkeypatch.chdir(tmp_path)
    worker = RecorderWorker(
        WorkerConfig(
            data_root=data_root,
            device_no="device-1",
            school_id=7,
            bind_type=1,
            classroom="一班录音设备",
        ),
        system_drive="C:",
    )

    worker.startup()

    assert not (tmp_path / data_root).exists()
    assert worker.queue_store is None


def test_data_root_update_is_rejected_without_rebinding_storage(tmp_path: Path):
    old_root = tmp_path / "old"
    new_root = tmp_path / "new"
    captured = {}

    def session_factory(**kwargs):
        captured.update(kwargs)
        return FakeSession()

    worker = RecorderWorker(
        WorkerConfig(data_root=str(old_root), device_no="device-1"),
        emit_event=lambda name, payload: None,
        session_factory=session_factory,
        recover=lambda root, on_error: [],
        startup_gate=allow_startup,
    )
    worker.startup()
    old_database = worker.queue_store.database_path
    original = worker.config

    worker.handle(command("update_settings", {"dataRoot": str(new_root)}))
    worker.handle(command("start"))

    assert worker.config == original
    assert worker.recordings_dir == old_root / "recordings"
    assert worker.queue_store.database_path == old_root / "queue.db"
    assert worker.legacy_queue_path == old_root / "queue.json"
    assert captured["journal"].root == old_root / "recordings"
    assert captured["queue_store"] is worker.queue_store
    assert old_database == old_root / "queue.db"
    assert not new_root.exists()


def test_same_unsafe_data_root_is_validated_before_equality_check():
    events = []
    worker = RecorderWorker(
        WorkerConfig(data_root="C:/Recorder"), system_drive="C:",
        emit_event=lambda name, payload: events.append((name, payload)),
    )

    worker.handle(command("update_settings", {"dataRoot": "C:/Recorder", "inputDevice": "mic-2"}))

    assert worker.config.input_device == ""
    assert any(name == "error" and "非系统盘" in payload["message"] for name, payload in events)


def test_failed_data_root_switch_preserves_old_configuration_and_resources(tmp_path: Path):
    old_root = tmp_path / "old"

    def gate(config, system_drive):
        allowed = config.data_root == str(old_root)
        return StartupGate(allowed, "healthy" if allowed else "storage_unavailable")

    worker = RecorderWorker(
        WorkerConfig(data_root=str(old_root), device_no="device-1"),
        emit_event=lambda name, payload: None,
        recover=lambda root, on_error: [],
        startup_gate=gate,
    )
    worker.startup()
    old_store = worker.queue_store
    old_recordings = worker.recordings_dir
    old_legacy = worker.legacy_queue_path

    worker.handle(command("update_settings", {"dataRoot": str(tmp_path / "bad")}))

    assert worker.config.data_root == str(old_root)
    assert worker.queue_store is old_store
    assert worker.recordings_dir == old_recordings
    assert worker.legacy_queue_path == old_legacy
