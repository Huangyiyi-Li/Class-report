from __future__ import annotations

import os
import queue
import shutil
import signal
import threading
import time
from datetime import datetime, timezone
from dataclasses import replace
from pathlib import Path
from typing import Callable

from worker.audio_journal import AudioJournal, recover_journals
from worker.config import StartupGate, WorkerConfig, evaluate_startup_gate, validate_settings_patch
from worker.control_server import ControlServer, InstanceLock, ServerAlreadyRunning
from worker.protocol import event
from worker.queue_store import QueueStore, migrate_json_queue
from worker.retention import cleanup_completed, disk_health
from worker.segment_encoder import encode_ogg_opus
from worker.upload_service import UploadService


class CommandRejected(ValueError):
    pass


class CaptureSession:
    FINALIZED_PATH_CAPACITY = 32
    FINALIZED_PATH_PUT_TIMEOUT = 1

    def __init__(
        self,
        config: WorkerConfig,
        journal,
        ffmpeg_path: Path,
        *,
        encoder: Callable[[Path, Path], Path] = encode_ogg_opus,
        stream_factory=None,
        journal_factory=None,
        clock: Callable[[], float] = time.monotonic,
        on_error: Callable[[Exception], None] | None = None,
        on_ready: Callable[[], None] | None = None,
        queue_store: QueueStore | None = None,
    ):
        self.config = config
        self.journal = journal
        self.ffmpeg_path = ffmpeg_path
        self.encoder = encoder
        self.stream_factory = stream_factory
        self.journal_factory = journal_factory
        self.clock = clock
        self.on_error = on_error
        self.on_ready = on_ready
        self._ready = False
        self._ready_event = threading.Event()
        self.queue_store = queue_store
        self.pcm_queue: queue.Queue[bytes] = queue.Queue(maxsize=256)
        self.finalize_queue: queue.Queue = queue.Queue(maxsize=8)
        self.finalized_paths: queue.Queue[Path] = queue.Queue(
            maxsize=self.FINALIZED_PATH_CAPACITY
        )
        self.control_queue = queue.SimpleQueue()
        self._control_sentinel = object()
        self._callback_failure_signaled = False
        self.stop_event = threading.Event()
        self._writer_thread: threading.Thread | None = None
        self._finalizer_thread: threading.Thread | None = None
        self._monitor_thread: threading.Thread | None = None
        self._stream = None
        self._stream_lock = threading.Lock()
        self._failure: Exception | None = None
        self._failure_lock = threading.Lock()

    def audio_callback(self, indata, frames, callback_time, status) -> None:
        if self.stop_event.is_set():
            return
        try:
            self.pcm_queue.put_nowait(indata.copy().tobytes())
        except queue.Full:
            if not self._callback_failure_signaled:
                self._callback_failure_signaled = True
                self.control_queue.put(RuntimeError("PCM queue overrun"))

    def process_control_event(self, timeout: float | None = None) -> bool:
        try:
            item = self.control_queue.get(timeout=timeout)
        except queue.Empty:
            return True
        if item is self._control_sentinel:
            return False
        self._record_failure(item)
        return True

    def monitor_loop(self) -> None:
        while self.process_control_event():
            pass

    def writer_loop(self) -> None:
        try:
            last_checkpoint = self.clock()
            segment_started = last_checkpoint
            while not self.stop_event.is_set() or not self.pcm_queue.empty():
                try:
                    pcm = self.pcm_queue.get(timeout=0.2)
                except queue.Empty:
                    continue
                now = self.clock()
                if now - segment_started >= self.config.segment_seconds:
                    self.finalize_queue.put(self.journal)
                    self.journal = self._new_journal()
                    segment_started = now
                    last_checkpoint = now
                self.journal.append(pcm)
                if not self._ready or now - last_checkpoint >= self.config.checkpoint_seconds:
                    self.journal.checkpoint()
                    last_checkpoint = now
                    if not self._ready:
                        self._ready = True
                        self._ready_event.set()
                        if self.on_ready is not None:
                            self.on_ready()
            self.finalize_queue.put(self.journal)
        except Exception as exc:
            self._record_failure(exc)
        finally:
            self.finalize_queue.put(None)

    def finalizer_loop(self) -> None:
        while True:
            journal = self.finalize_queue.get()
            if journal is None:
                return
            try:
                finalized_at = datetime.now(timezone.utc)
                wav_path = journal.finalize(finalized_at)
                final_path = self.encoder(wav_path, self.ffmpeg_path)
                if self.queue_store is not None:
                    segment_index = self.queue_store.next_segment_index(
                        journal.device_id, finalized_at.date().isoformat()
                    )
                    self.queue_store.enqueue(
                        {
                            "local_path": str(final_path),
                            "segment_index": segment_index,
                            "code": journal.device_id,
                            "device_no": journal.device_id,
                            "school_id": self.config.school_id,
                            "location_id": self.config.location_id,
                            "start_time": journal.started_at.isoformat(),
                            "end_time": finalized_at.isoformat(),
                            "rate": journal.rate,
                            "bits": journal.sample_width * 8,
                            "channel": journal.channels,
                            "audio_type": 1,
                            "audio_format": final_path.suffix.lstrip(".").lower(),
                        }
                    )
                self.finalized_paths.put(
                    final_path, timeout=self.FINALIZED_PATH_PUT_TIMEOUT
                )
            except queue.Full:
                self._record_failure(
                    RuntimeError("finalized path queue backpressure timeout")
                )
            except Exception as exc:
                self._record_failure(exc)

    def _new_journal(self):
        if self.journal_factory is not None:
            return self.journal_factory()
        return AudioJournal(
            self.journal.root,
            self.journal.device_id,
            datetime.now(timezone.utc),
            self.journal.rate,
            self.journal.channels,
            self.journal.sample_width,
            school_id=getattr(self.journal, "school_id", self.config.school_id),
            location_id=getattr(self.journal, "location_id", self.config.location_id),
        )

    def _record_failure(self, exc: Exception) -> None:
        with self._failure_lock:
            if self._failure is not None:
                return
            self._failure = exc
        self.stop_event.set()
        threading.Thread(target=self._close_stream, daemon=True).start()
        if self.on_error is not None:
            self.on_error(exc)

    def raise_if_failed(self) -> None:
        if self._failure is not None:
            raise RuntimeError(str(self._failure)) from self._failure

    def wait_until_ready(self, timeout: float) -> bool:
        return self._ready_event.wait(timeout)

    def start(self) -> None:
        self.stop_event.clear()
        self._monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
        self._monitor_thread.start()
        factory = self.stream_factory or _sounddevice_input_stream
        try:
            self._stream = factory(
                callback=self.audio_callback,
                samplerate=self.journal.rate,
                channels=self.journal.channels,
                device=self.config.input_device or None,
                dtype={1: "int8", 2: "int16", 4: "int32"}[
                    self.journal.sample_width
                ],
            )
            self._stream.start()
        except Exception:
            self.control_queue.put(self._control_sentinel)
            self._monitor_thread.join()
            self._monitor_thread = None
            raise
        self._finalizer_thread = threading.Thread(
            target=self.finalizer_loop, daemon=True
        )
        self._finalizer_thread.start()
        self._writer_thread = threading.Thread(target=self.writer_loop, daemon=True)
        self._writer_thread.start()

    def stop(self) -> None:
        self._close_stream()
        self.stop_event.set()
        if self._writer_thread is not None:
            self._writer_thread.join()
            self._writer_thread = None
        if self._finalizer_thread is not None:
            self._finalizer_thread.join()
            self._finalizer_thread = None
        if self._monitor_thread is not None:
            self.control_queue.put(self._control_sentinel)
            self._monitor_thread.join()
            self._monitor_thread = None
        self.raise_if_failed()

    def _close_stream(self) -> None:
        with self._stream_lock:
            stream = self._stream
            self._stream = None
        if stream is not None:
            stream.stop()
            stream.close()


def _sounddevice_input_stream(**kwargs):
    import sounddevice

    return sounddevice.InputStream(**kwargs)


class RecorderWorker:
    def __init__(
        self,
        config: WorkerConfig,
        *,
        emit_event: Callable[[str, dict], None] | None = None,
        session_factory=None,
        recover=recover_journals,
        ffmpeg_path: Path = Path("ffmpeg.exe"),
        queue_store: QueueStore | None = None,
        upload_service=None,
        upload_poll_seconds: float = 1.0,
        shutdown_join_seconds: float = 5.0,
        config_path: Path | None = None,
        startup_gate: Callable[[WorkerConfig, str], StartupGate] = evaluate_startup_gate,
        system_drive: str | None = None,
        capture_retry_delays: tuple[float, ...] = (1.0, 2.0, 5.0, 10.0),
        session_ready_timeout: float = 3.0,
    ):
        self.config = config
        self.emit_event = emit_event or emit
        self.session_factory = session_factory or CaptureSession
        self.recover = recover
        self.ffmpeg_path = ffmpeg_path
        self.recordings_dir: Path | None = None
        self.queue_store = queue_store
        self._provided_queue_store = queue_store
        self.upload_service = upload_service
        self.upload_poll_seconds = upload_poll_seconds
        self.shutdown_join_seconds = shutdown_join_seconds
        self.config_path = config_path
        self.startup_gate = startup_gate
        self.system_drive = system_drive or os.environ.get("SystemDrive", "C:")
        self.capture_retry_delays = capture_retry_delays
        self.session_ready_timeout = session_ready_timeout
        self._capture_retry_attempt = 0
        self._capture_retry_timer: threading.Timer | None = None
        self._desired_recording = False
        self._capture_generation = 0
        self._capture_transition_lock = threading.RLock()
        self._upload_lock = threading.Lock()
        self._upload_stop = threading.Event()
        self._upload_thread: threading.Thread | None = None
        self.legacy_queue_path: Path | None = None
        self.state = {
            "recording": "idle",
            "upload": "clear",
            "health": "healthy",
            "recovered": 0,
            "latestError": "",
        }
        self.session: CaptureSession | None = None
        self._state_lock = threading.Lock()

    def startup(self) -> None:
        gate = self._evaluate_startup_gate()
        if not gate.allowed:
            return
        self._bind_storage(self.config)
        assert self.recordings_dir is not None
        assert self.queue_store is not None
        assert self.legacy_queue_path is not None
        self.recordings_dir.mkdir(parents=True, exist_ok=True)
        migrate_json_queue(self.legacy_queue_path, self.queue_store)
        try:
            recovered = self.recover(
                self.recordings_dir, self._recovery_error, queue_store=self.queue_store
            )
        except TypeError as exc:
            if "queue_store" not in str(exc):
                raise
            recovered = self.recover(self.recordings_dir, self._recovery_error)
        self.state["recovered"] = len(recovered)
        for path in recovered:
            self.emit_event("recovered", {"path": str(path)})
        self.start_uploading()
        self.maybe_auto_start()

    def start_uploading(self) -> None:
        if self.upload_service is not None and self._upload_thread is None:
            self._upload_stop.clear()
            self._upload_thread = threading.Thread(
                target=self._upload_loop, daemon=True
            )
            self._upload_thread.start()

    def _upload_loop(self) -> None:
        while not self._upload_stop.is_set():
            try:
                now = datetime.now(timezone.utc)
                with self._upload_lock:
                    result = self.upload_service.run_once(now)
                cleanup_completed(self.recordings_dir, self.queue_store, now)
                health = disk_health(self.recordings_dir)
                if health != "healthy":
                    self.state["health"] = "disk_low" if health == "low" else health
                if result is not None:
                    self.state["upload"] = result.status
            except Exception as exc:
                self.state["health"] = "error"
                self.emit_event("error", {"message": f"upload worker failed: {exc}"})
            self._upload_stop.wait(self.upload_poll_seconds)

    def execute_command(self, command) -> bool:
        if command.command == "shutdown":
            with self._capture_transition_lock:
                self._cancel_capture_retry()
                self._desired_recording = False
                self._capture_generation += 1
                self._stop_session("idle")
            self.emit_event("snapshot", self.snapshot())
            return False
        if command.command == "start":
            with self._capture_transition_lock:
                self._desired_recording = True
                if not self._guarded_start():
                    raise CommandRejected(self.state["latestError"] or "recording start rejected")
        elif command.command == "pause":
            with self._capture_transition_lock:
                self._desired_recording = False
                self._capture_generation += 1
                self._cancel_capture_retry()
                self._stop_session("paused")
        elif command.command == "stop":
            with self._capture_transition_lock:
                self._desired_recording = False
                self._capture_generation += 1
                self._cancel_capture_retry()
                self._stop_session("idle")
        elif command.command == "flush_queue":
            self._flush_queue()
        elif command.command == "update_settings":
            if self.state["recording"] == "recording":
                self._command_error("录音中不允许变更运行设置")
                raise CommandRejected("录音中不允许变更运行设置")
            self._update_settings(command.payload)
        self.emit_event("snapshot", self.snapshot())
        return True

    def handle(self, command) -> bool:
        try:
            return self.execute_command(command)
        except CommandRejected:
            return command.command != "shutdown"
        except Exception as exc:
            self._capture_error(exc)
            return command.command != "shutdown"

    def maybe_auto_start(self) -> None:
        if self.config.auto_record_enabled:
            with self._capture_transition_lock:
                self._desired_recording = True
                self._guarded_start()

    def _guarded_start(self) -> bool:
        gate = self._evaluate_startup_gate()
        if not gate.allowed:
            self._command_error(f"recording blocked: {gate.health}")
            return False
        if self.queue_store is None:
            self._bind_storage(self.config)
        if self.session is None:
            self._capture_generation += 1
            generation = self._capture_generation
            journal = AudioJournal(
                self.recordings_dir,
                self.config.device_no,
                datetime.now(timezone.utc),
                16000,
                1,
                2,
                school_id=self.config.school_id,
                location_id=self.config.location_id,
            )
            self.session = self.session_factory(
                config=self.config,
                journal=journal,
                ffmpeg_path=self.ffmpeg_path,
                on_error=lambda exc: self._capture_error(exc, generation),
                queue_store=self.queue_store,
            )
            candidate = self.session
            self.state["recording"] = "starting"
            try:
                candidate.start()
            except Exception as exc:
                self.session = None
                self._cleanup_failed_session(candidate)
                self.state["recording"] = "microphone_unavailable"
                self.state["health"] = "microphone_unavailable"
                self.state["latestError"] = str(exc)
                self._schedule_capture_retry()
                return False
            ready = candidate.wait_until_ready(self.session_ready_timeout)
            if self.session is not candidate:
                return False
            if not ready:
                failed_session = candidate
                self.session = None
                failed_session.stop()
                message = "microphone produced no durable audio before readiness timeout"
                self.state["recording"] = "microphone_unavailable"
                self.state["health"] = "microphone_unavailable"
                self.state["latestError"] = message
                self._schedule_capture_retry()
                return False
            self._capture_ready()
        return True

    def _capture_ready(self) -> None:
        with self._state_lock:
            if not self._desired_recording or self.session is None:
                return
            self._capture_retry_attempt = 0
            self.state["recording"] = "recording"
            self.state["health"] = "healthy"
        self.emit_event("snapshot", self.snapshot())

    def _evaluate_startup_gate(self) -> StartupGate:
        gate = self.startup_gate(self.config, self.system_drive)
        self.state["health"] = gate.health
        if not gate.allowed:
            self.state["recording"] = "error"
        return gate

    def _bind_storage(self, config: WorkerConfig) -> None:
        root = Path(config.data_root)
        recordings_dir = root / "recordings"
        legacy_queue_path = root / "queue.json"
        queue_store = self._provided_queue_store or QueueStore(root / "queue.db")
        recordings_dir.mkdir(parents=True, exist_ok=True)
        self.recordings_dir = recordings_dir
        self.queue_store = queue_store
        self.legacy_queue_path = legacy_queue_path

    def _stop_session(self, next_state: str) -> None:
        session = self.session
        self.session = None
        if session is not None:
            session.stop()
        self.state["recording"] = next_state

    def _capture_error(self, exc: Exception, generation: int | None = None) -> None:
        with self._state_lock:
            if generation is not None and generation != self._capture_generation:
                return
            self.state["recording"] = "error"
            self.state["health"] = "error"
            self.state["latestError"] = str(exc)
            failed_session = self.session
            self.session = None
        if failed_session is not None:
            threading.Thread(
                target=self._cleanup_failed_session,
                args=(failed_session,),
                daemon=True,
            ).start()
        self.emit_event("error", {"message": str(exc)})
        self.emit_event("snapshot", self.snapshot())
        self._schedule_capture_retry()

    def _schedule_capture_retry(self) -> None:
        with self._state_lock:
            if not self._desired_recording or self._capture_retry_timer is not None:
                return
            index = min(self._capture_retry_attempt, len(self.capture_retry_delays) - 1)
            self._capture_retry_attempt += 1
            timer = threading.Timer(self.capture_retry_delays[index], self._retry_capture)
            timer.daemon = True
            self._capture_retry_timer = timer
            timer.start()

    def _retry_capture(self) -> None:
        with self._capture_transition_lock:
            with self._state_lock:
                self._capture_retry_timer = None
                desired = self._desired_recording
            if desired:
                self._guarded_start()

    def _cancel_capture_retry(self) -> None:
        with self._state_lock:
            timer = self._capture_retry_timer
            self._capture_retry_timer = None
        if timer is not None:
            timer.cancel()

    @staticmethod
    def _cleanup_failed_session(session) -> None:
        try:
            session.stop()
        except Exception:
            pass

    def _recovery_error(self, exc: Exception) -> None:
        self.state["health"] = "error"
        self.state["latestError"] = str(exc)
        self.emit_event("error", {"message": f"journal recovery failed: {exc}"})

    def snapshot(self) -> dict:
        counts = self.queue_store.counts() if self.queue_store is not None else {}
        pending = sum(count for status, count in counts.items() if status != "completed")
        try:
            if self.recordings_dir is None:
                raise OSError("data root is not configured")
            free_bytes = shutil.disk_usage(self.recordings_dir).free
            disk_status = disk_health(self.recordings_dir)
            disk_health_name = "disk_low" if disk_status == "low" else disk_status
        except OSError:
            free_bytes = 0
            disk_health_name = "storage_unavailable"
        location = None
        if self.config.location_id or self.config.location_name:
            location = {
                "locationId": self.config.location_id,
                "locationName": self.config.location_name,
            }
        return {
            **self.state,
            "pending": pending,
            "completed": counts.get("completed", 0),
            "location": location,
            "dataRoot": self.config.data_root,
            "freeDiskBytes": free_bytes,
            "diskHealth": disk_health_name,
        }

    def _flush_queue(self) -> None:
        if self.upload_service is None:
            return
        with self._upload_lock:
            while self.upload_service.run_once(datetime.now(timezone.utc)) is not None:
                pass

    def _update_settings(self, payload: dict) -> None:
        changes = validate_settings_patch(payload, self.system_drive)
        requested_root = changes.pop("data_root", None)
        if requested_root and requested_root != self.config.data_root:
            raise CommandRejected("录音数据目录首次部署后不可修改，需重新部署")
        candidate = replace(self.config, **changes)
        if candidate.data_root != self.config.data_root:
            self._rebind_storage(candidate)
        else:
            if self.config_path is not None:
                candidate.save_atomic(self.config_path)
            self.config = candidate

    def _rebind_storage(self, candidate: WorkerConfig) -> None:
        gate = self.startup_gate(candidate, self.system_drive)
        if not gate.allowed:
            raise ValueError(f"storage switch blocked: {gate.health}")
        if self._provided_queue_store is not None:
            raise ValueError("cannot switch data root with an externally managed queue")
        if self.queue_store is not None:
            counts = self.queue_store.counts()
            pending = sum(count for status, count in counts.items() if status != "completed")
            if pending:
                raise ValueError("待上传队列未清空，不允许切换数据目录")
        root = Path(candidate.data_root)
        new_recordings = root / "recordings"
        new_store = QueueStore(root / "queue.db")
        new_recordings.mkdir(parents=True, exist_ok=True)
        if self.config_path is not None:
            candidate.save_atomic(self.config_path)
        with self._upload_lock:
            self.config = candidate
            self.recordings_dir = new_recordings
            self.queue_store = new_store
            self.legacy_queue_path = root / "queue.json"
            if self.upload_service is not None and hasattr(self.upload_service, "store"):
                self.upload_service.store = new_store

    def _command_error(self, message: str) -> None:
        self.state["latestError"] = message
        self.emit_event("error", {"message": message})
        self.emit_event("snapshot", self.snapshot())

    def shutdown(self) -> None:
        self._upload_stop.set()
        if self._upload_thread is not None:
            thread = self._upload_thread
            thread.join(timeout=self.shutdown_join_seconds)
            if thread.is_alive():
                self.state["health"] = "error"
                self.emit_event(
                    "error", {"message": "upload worker did not stop before timeout"}
                )
            else:
                self._upload_thread = None
        try:
            self._stop_session("idle")
        except Exception as exc:
            self._capture_error(exc)


def emit(name: str, payload: dict) -> None:
    print(event(name, payload), flush=True)


class XxtProductionAdapter:
    def __init__(self, api_client, upload_manager):
        self.api_client = api_client
        self.upload_manager = upload_manager

    def upload(self, path):
        return self.upload_manager.upload(path)

    def save_audio_file_info(self, payload):
        auth = self.upload_manager.ensure_device_auth()
        self.api_client.token = auth.access_token
        return self.api_client.save_audio_file_info(payload)


def create_upload_service(config: WorkerConfig, store: QueueStore):
    if not config.device_no:
        return None
    from windows_client.xxt_upload import XxtDeviceApiClient, XxtUploadManager

    api_client = XxtDeviceApiClient(config.base_url)
    upload_manager = XxtUploadManager(api_client, config.device_no)
    adapter = XxtProductionAdapter(api_client, upload_manager)
    return UploadService(store, adapter, adapter)


def run_worker(config_path: Path, stopped: threading.Event, worker_factory=None) -> int:
    worker_factory = worker_factory or RecorderWorker
    config = WorkerConfig.load(config_path)
    runtime_override = os.environ.get("RECORDER_RUNTIME_DIR")
    if not runtime_override and not config.data_root:
        raise ValueError("data root is required for the worker runtime directory")
    runtime_dir = Path(runtime_override or config.data_root) / (
        "" if runtime_override else "runtime"
    )
    try:
        instance_lock = InstanceLock(runtime_dir).acquire()
    except ServerAlreadyRunning:
        return 2
    with instance_lock:
        worker = worker_factory(config, config_path=config_path)
        try:
            worker.startup()
            if config.device_no and worker.queue_store is not None:
                worker.upload_service = create_upload_service(config, worker.queue_store)
                worker.start_uploading()
            with ControlServer(worker, runtime_dir, instance_lock=instance_lock):
                stopped.wait()
            return 0
        finally:
            worker.shutdown()


def main() -> int:
    config_path = Path(os.environ.get("RECORDER_CONFIG_PATH", "worker-config.json"))
    stopped = threading.Event()
    for signal_name in ("SIGINT", "SIGTERM"):
        if hasattr(signal, signal_name):
            signal.signal(getattr(signal, signal_name), lambda *_args: stopped.set())
    return run_worker(config_path, stopped)


if __name__ == "__main__":
    raise SystemExit(main())
