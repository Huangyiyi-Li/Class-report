from __future__ import annotations

import queue
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

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
    ):
        self.config = config
        self.journal = journal
        self.ffmpeg_path = ffmpeg_path
        self.encoder = encoder
        self.stream_factory = stream_factory
        self.journal_factory = journal_factory
        self.clock = clock
        self.pcm_queue: queue.Queue[bytes] = queue.Queue()
        self.finalized_paths: queue.Queue[Path] = queue.Queue()
        self.stop_event = threading.Event()
        self._writer_thread: threading.Thread | None = None
        self._stream = None

    def audio_callback(self, indata, frames, callback_time, status) -> None:
        self.pcm_queue.put_nowait(indata.copy().tobytes())

    def writer_loop(self) -> None:
        last_checkpoint = self.clock()
        segment_started = last_checkpoint
        while not self.stop_event.is_set() or not self.pcm_queue.empty():
            try:
                pcm = self.pcm_queue.get(timeout=0.2)
            except queue.Empty:
                continue
            now = self.clock()
            if (
                self.journal_factory is not None
                and now - segment_started >= self.config.segment_seconds
            ):
                self._finalize_current()
                self.journal = self.journal_factory()
                segment_started = now
                last_checkpoint = now
            self.journal.append(pcm)
            if now - last_checkpoint >= self.config.checkpoint_seconds:
                self.journal.checkpoint()
                last_checkpoint = now
        self._finalize_current()

    def _finalize_current(self) -> None:
        wav_path = self.journal.finalize(datetime.now(timezone.utc))
        self.finalized_paths.put(self.encoder(wav_path, self.ffmpeg_path))

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
        self._writer_thread = threading.Thread(target=self.writer_loop, daemon=True)
        self._writer_thread.start()

    def stop(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        self.stop_event.set()
        if self._writer_thread is not None:
            self._writer_thread.join()
            self._writer_thread = None


def _sounddevice_input_stream(**kwargs):
    import sounddevice

    return sounddevice.InputStream(**kwargs)


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
