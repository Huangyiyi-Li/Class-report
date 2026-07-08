from __future__ import annotations

import os
import queue
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from worker.audio_journal import AudioJournal, recover_journals
from worker.config import WorkerConfig
from worker.protocol import event, parse_command
from worker.segment_encoder import encode_ogg_opus


class CaptureSession:
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
    ):
        self.config = config
        self.journal = journal
        self.ffmpeg_path = ffmpeg_path
        self.encoder = encoder
        self.stream_factory = stream_factory
        self.journal_factory = journal_factory
        self.clock = clock
        self.on_error = on_error
        self.pcm_queue: queue.Queue[bytes] = queue.Queue(maxsize=256)
        self.finalize_queue: queue.Queue = queue.Queue(maxsize=8)
        self.finalized_paths: queue.Queue[Path] = queue.Queue()
        self.stop_event = threading.Event()
        self._writer_thread: threading.Thread | None = None
        self._finalizer_thread: threading.Thread | None = None
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
            self._record_failure(RuntimeError("PCM queue overrun"))

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
                if now - last_checkpoint >= self.config.checkpoint_seconds:
                    self.journal.checkpoint()
                    last_checkpoint = now
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
                wav_path = journal.finalize(datetime.now(timezone.utc))
                self.finalized_paths.put(self.encoder(wav_path, self.ffmpeg_path))
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

    def start(self) -> None:
        self.stop_event.clear()
        factory = self.stream_factory or _sounddevice_input_stream
        self._stream = factory(
            callback=self.audio_callback,
            samplerate=self.journal.rate,
            channels=self.journal.channels,
            dtype={1: "int8", 2: "int16", 4: "int32"}[self.journal.sample_width],
        )
        self._stream.start()
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
    ):
        self.config = config
        self.emit_event = emit_event or emit
        self.session_factory = session_factory or CaptureSession
        self.recover = recover
        self.ffmpeg_path = ffmpeg_path
        root = Path(config.data_root) if config.data_root else Path.cwd()
        self.recordings_dir = root / "recordings"
        self.state = {
            "recording": "idle",
            "upload": "clear",
            "health": "healthy",
            "recovered": 0,
        }
        self.session: CaptureSession | None = None
        self._state_lock = threading.Lock()

    def startup(self) -> None:
        self.recordings_dir.mkdir(parents=True, exist_ok=True)
        recovered = self.recover(self.recordings_dir, self._recovery_error)
        self.state["recovered"] = len(recovered)
        for path in recovered:
            self.emit_event("recovered", {"path": str(path)})

    def handle(self, command) -> bool:
        try:
            if command.command == "shutdown":
                self._stop_session("idle")
                self.emit_event("snapshot", dict(self.state))
                return False
            if command.command == "start":
                if self.session is None:
                    journal = AudioJournal(
                        self.recordings_dir,
                        self.config.device_no or "unconfigured-device",
                        datetime.now(timezone.utc),
                        16000,
                        1,
                        2,
                    )
                    self.session = self.session_factory(
                        config=self.config,
                        journal=journal,
                        ffmpeg_path=self.ffmpeg_path,
                        on_error=self._capture_error,
                    )
                    self.session.start()
                self.state["recording"] = "recording"
            elif command.command == "pause":
                self._stop_session("paused")
            elif command.command == "stop":
                self._stop_session("idle")
            self.emit_event("snapshot", dict(self.state))
            return True
        except Exception as exc:
            self._capture_error(exc)
            return command.command != "shutdown"

    def _stop_session(self, next_state: str) -> None:
        session = self.session
        self.session = None
        if session is not None:
            session.stop()
        self.state["recording"] = next_state

    def _capture_error(self, exc: Exception) -> None:
        with self._state_lock:
            self.state["recording"] = "error"
            self.state["health"] = "error"
            failed_session = self.session
            self.session = None
        if failed_session is not None:
            threading.Thread(
                target=self._cleanup_failed_session,
                args=(failed_session,),
                daemon=True,
            ).start()
        self.emit_event("error", {"message": str(exc)})
        self.emit_event("snapshot", dict(self.state))

    @staticmethod
    def _cleanup_failed_session(session) -> None:
        try:
            session.stop()
        except Exception:
            pass

    def _recovery_error(self, exc: Exception) -> None:
        self.state["health"] = "error"
        self.emit_event("error", {"message": f"journal recovery failed: {exc}"})


def emit(name: str, payload: dict) -> None:
    print(event(name, payload), flush=True)


def main() -> int:
    config_path = Path(os.environ.get("RECORDER_CONFIG_PATH", "worker-config.json"))
    worker = RecorderWorker(WorkerConfig.load(config_path))
    worker.startup()
    emit("ready", dict(worker.state))
    for line in sys.stdin:
        try:
            command = parse_command(line)
            if not worker.handle(command):
                return 0
        except Exception as exc:
            emit("error", {"message": str(exc)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
