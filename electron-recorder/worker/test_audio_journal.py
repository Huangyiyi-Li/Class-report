import json
import wave
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import time

from worker.audio_journal import AudioJournal, recover_journals
from worker.config import WorkerConfig
from worker.queue_store import QueueStore
from worker.recorder_worker import CaptureSession


def test_checkpoint_persists_pcm_before_finalize(tmp_path: Path):
    journal = AudioJournal(
        tmp_path, "device-1", datetime.now(timezone.utc), 16000, 1, 2
    )
    journal.append(b"\x00\x01" * 16000)

    journal.checkpoint()

    assert journal.part_path.stat().st_size == 32000


def test_recovers_unfinished_part_as_wav(tmp_path: Path):
    journal = AudioJournal(
        tmp_path, "device-1", datetime.now(timezone.utc), 16000, 1, 2
    )
    journal.append(b"\x00\x01" * 1600)
    journal.checkpoint()

    recovered = recover_journals(tmp_path)

    assert len(recovered) == 1
    assert recovered[0].suffix == ".wav"
    assert recovered[0].exists()


def test_recovery_enqueues_once_with_journal_time_binding_metadata(tmp_path: Path):
    started = datetime(2026, 7, 12, 23, 59, tzinfo=timezone.utc)
    journal = AudioJournal(
        tmp_path, "old-device", started, 16000, 1, 2,
        school_id=17, location_id="old-room",
    )
    journal.append(b"\x00\x01" * 10)
    journal.checkpoint()
    store = QueueStore(tmp_path / "queue.db")

    first = recover_journals(tmp_path, queue_store=store)
    second = recover_journals(tmp_path, queue_store=store)

    assert len(first) == 1
    assert second == []
    item = store.claim_next(datetime.now(timezone.utc))
    assert item is not None
    assert item.device_no == "old-device"
    assert item.school_id == 17
    assert item.location_id == "old-room"
    assert item.start_time == started.isoformat()
    store.mark_failed(item.id, "offline", datetime.now(timezone.utc))
    assert store.claim_next(datetime.now(timezone.utc)).id == item.id


def test_first_durable_write_notifies_capture_ready_once(tmp_path: Path):
    ready = []
    journal = FakeJournal(tmp_path / "segment.wav")
    session = CaptureSession(
        WorkerConfig(checkpoint_seconds=1000), journal, Path("ffmpeg.exe"),
        on_ready=lambda: ready.append(True), clock=iter([0.0, 1.0, 2.0]).__next__,
    )
    session.pcm_queue.put(b"one")
    session.pcm_queue.put(b"two")
    session.stop_event.set()

    session.writer_loop()

    assert journal.checkpoints == 1
    assert ready == [True]
    assert session.wait_until_ready(0) is True


def test_recovery_end_time_uses_durable_pcm_frames_not_file_mtime(tmp_path: Path):
    started = datetime(2026, 7, 12, 23, 59, tzinfo=timezone.utc)
    journal = AudioJournal(tmp_path, "device", started, 10, 2, 2)
    journal.append(b"\x00" * 80)  # 20 frames = 2 seconds at 10 Hz
    journal.checkpoint()
    journal.part_path.touch()
    store = QueueStore(tmp_path / "queue.db")
    recover_journals(tmp_path, queue_store=store)
    item = store.claim_next(datetime.now(timezone.utc))
    assert item.end_time == (started + timedelta(seconds=2)).isoformat()


def test_recovery_discards_pcm_beyond_durable_frames(tmp_path: Path):
    started = datetime(2026, 7, 12, 23, 59, tzinfo=timezone.utc)
    journal = AudioJournal(tmp_path, "device", started, 10, 2, 2)
    durable_pcm = b"abcdefgh"
    journal.append(durable_pcm)  # 2 complete frames
    journal.checkpoint()
    journal.append(b"unconfirmed-tail")
    journal.file.close()
    store = QueueStore(tmp_path / "queue.db")

    recovered = recover_journals(tmp_path, queue_store=store)

    with wave.open(str(recovered[0]), "rb") as audio:
        assert audio.getnframes() == 2
        assert audio.readframes(10) == durable_pcm
    item = store.claim_next(datetime.now(timezone.utc))
    assert item.end_time == (started + timedelta(seconds=0.2)).isoformat()


def test_legacy_recovery_uses_only_complete_frames_from_part(tmp_path: Path):
    started = datetime(2026, 7, 12, 23, 59, tzinfo=timezone.utc)
    journal = AudioJournal(tmp_path, "legacy-device", started, 10, 2, 2)
    journal.append(b"abcdefghij")  # 2 complete frames plus a partial frame
    journal.file.close()
    metadata = json.loads(journal.meta_path.read_text(encoding="utf-8"))
    metadata.pop("durableFrames")
    journal.meta_path.write_text(json.dumps(metadata), encoding="utf-8")
    store = QueueStore(tmp_path / "queue.db")

    recovered = recover_journals(tmp_path, queue_store=store)

    with wave.open(str(recovered[0]), "rb") as audio:
        assert audio.getnframes() == 2
        assert audio.readframes(10) == b"abcdefgh"
    item = store.claim_next(datetime.now(timezone.utc))
    assert item.end_time == (started + timedelta(seconds=0.2)).isoformat()


def test_recovery_isolates_corrupt_metadata_and_keeps_its_pcm(tmp_path: Path):
    corrupt_part = tmp_path / "corrupt.pcm.part"
    corrupt_part.write_bytes(b"pcm")
    (tmp_path / "corrupt.json").write_text("not-json", encoding="utf-8")
    valid = AudioJournal(
        tmp_path, "device-1", datetime.now(timezone.utc), 16000, 1, 2
    )
    valid.append(b"\x00\x01")
    valid.checkpoint()

    errors = []
    recovered = recover_journals(tmp_path, on_error=errors.append)

    assert len(recovered) == 1
    assert corrupt_part.exists()
    assert len(errors) == 1


def test_finalize_keeps_journal_when_atomic_wav_replace_fails(
    tmp_path: Path, monkeypatch
):
    journal = AudioJournal(
        tmp_path, "device-1", datetime.now(timezone.utc), 16000, 1, 2
    )
    journal.append(b"\x00\x01")
    real_replace = __import__("os").replace

    def fail_wav_replace(source, target):
        if str(target).endswith(".wav"):
            raise OSError("replace failed")
        return real_replace(source, target)

    monkeypatch.setattr("worker.audio_journal.os.replace", fail_wav_replace)

    with pytest.raises(OSError, match="replace failed"):
        journal.finalize()
    assert journal.part_path.exists()
    assert journal.meta_path.exists()


class FakeInputData:
    def copy(self):
        return self

    def tobytes(self):
        return b"pcm"


class FakeJournal:
    def __init__(self, wav_path: Path):
        self.wav_path = wav_path
        self.rate = 16000
        self.channels = 1
        self.sample_width = 2
        self.root = wav_path.parent
        self.device_id = "device-1"
        self.appended = []
        self.checkpoints = 0
        self.finalized = 0

    def append(self, pcm: bytes):
        self.appended.append(pcm)

    def checkpoint(self):
        self.checkpoints += 1

    def finalize(self, end_time=None):
        self.finalized += 1
        self.wav_path.write_bytes(b"wav")
        return self.wav_path


class FailingJournal(FakeJournal):
    def append(self, pcm: bytes):
        raise OSError("disk full")


def test_audio_callback_only_queues_pcm(tmp_path: Path):
    journal = FakeJournal(tmp_path / "segment.wav")
    session = CaptureSession(WorkerConfig(), journal, ffmpeg_path=Path("ffmpeg.exe"))

    session.audio_callback(FakeInputData(), 1, None, None)

    assert journal.appended == []
    assert session.pcm_queue.get_nowait() == b"pcm"


def test_writer_checkpoints_and_enqueues_encoded_final_path(tmp_path: Path):
    journal = FakeJournal(tmp_path / "segment.wav")
    encoded = tmp_path / "segment.ogg"
    session = CaptureSession(
        WorkerConfig(checkpoint_seconds=10),
        journal,
        ffmpeg_path=Path("ffmpeg.exe"),
        encoder=lambda wav, ffmpeg: encoded,
        clock=iter([0.0, 11.0]).__next__,
    )
    session.pcm_queue.put(b"pcm")
    session.stop_event.set()

    session.writer_loop()

    assert journal.appended == [b"pcm"]
    assert journal.checkpoints == 1
    assert journal.finalized == 0
    session.finalizer_loop()
    assert journal.finalized == 1
    assert session.finalized_paths.get_nowait() == encoded


def test_writer_rotates_journal_at_segment_boundary(tmp_path: Path):
    first = FakeJournal(tmp_path / "first.wav")
    session = CaptureSession(
        WorkerConfig(segment_seconds=300, checkpoint_seconds=1000),
        first,
        ffmpeg_path=Path("ffmpeg.exe"),
        encoder=lambda wav, ffmpeg: wav,
        clock=iter([0.0, 100.0, 301.0]).__next__,
    )
    session.pcm_queue.put(b"first")
    session.pcm_queue.put(b"second")
    session.stop_event.set()

    session.writer_loop()
    session.finalizer_loop()

    assert first.appended == [b"first"]
    assert first.finalized == 1
    assert session.journal is not first
    assert session.finalized_paths.qsize() == 2


def test_start_configures_input_stream_for_journal_format(tmp_path: Path):
    captured = {}

    class FakeStream:
        def start(self):
            captured["started"] = True

        def stop(self):
            pass

        def close(self):
            pass

    def stream_factory(**kwargs):
        captured.update(kwargs)
        return FakeStream()

    journal = FakeJournal(tmp_path / "segment.wav")
    session = CaptureSession(
        WorkerConfig(),
        journal,
        ffmpeg_path=Path("ffmpeg.exe"),
        encoder=lambda wav, ffmpeg: wav,
        stream_factory=stream_factory,
    )

    session.start()
    session.stop()

    assert captured["samplerate"] == 16000
    assert captured["channels"] == 1
    assert captured["dtype"] == "int16"
    assert captured["started"] is True


def test_writer_failure_is_stored_and_observable_by_owner(tmp_path: Path):
    errors = []
    journal = FailingJournal(tmp_path / "segment.wav")
    session = CaptureSession(
        WorkerConfig(),
        journal,
        ffmpeg_path=Path("ffmpeg.exe"),
        on_error=errors.append,
        clock=iter([0.0, 1.0]).__next__,
    )
    session.pcm_queue.put(b"pcm")
    session.stop_event.set()

    session.writer_loop()

    with pytest.raises(RuntimeError, match="disk full"):
        session.raise_if_failed()
    assert len(errors) == 1


def test_async_writer_failure_stops_stream_and_stop_raises(tmp_path: Path):
    stopped = []

    class FakeStream:
        def start(self):
            pass

        def stop(self):
            stopped.append(True)

        def close(self):
            pass

    session = CaptureSession(
        WorkerConfig(),
        FailingJournal(tmp_path / "segment.wav"),
        ffmpeg_path=Path("ffmpeg.exe"),
        stream_factory=lambda **kwargs: FakeStream(),
    )
    session.pcm_queue.put(b"pcm")
    session.start()
    deadline = time.monotonic() + 1
    while not stopped and time.monotonic() < deadline:
        time.sleep(0.01)

    assert stopped
    with pytest.raises(RuntimeError, match="disk full"):
        session.stop()


def test_encoder_failure_from_finalizer_is_observable(tmp_path: Path):
    journal = FakeJournal(tmp_path / "segment.wav")
    session = CaptureSession(
        WorkerConfig(),
        journal,
        ffmpeg_path=Path("ffmpeg.exe"),
        encoder=lambda wav, ffmpeg: (_ for _ in ()).throw(OSError("ffmpeg failed")),
    )
    session.finalize_queue.put(journal)
    session.finalize_queue.put(None)

    session.finalizer_loop()

    with pytest.raises(RuntimeError, match="ffmpeg failed"):
        session.raise_if_failed()


def test_pcm_queue_overrun_becomes_explicit_failure(tmp_path: Path):
    errors = []
    session = CaptureSession(
        WorkerConfig(),
        FakeJournal(tmp_path / "segment.wav"),
        ffmpeg_path=Path("ffmpeg.exe"),
        on_error=errors.append,
    )
    for _ in range(session.pcm_queue.maxsize):
        session.pcm_queue.put_nowait(b"pcm")

    session.audio_callback(FakeInputData(), 1, None, None)

    assert errors == []
    assert not session.stop_event.is_set()
    session.process_control_event(timeout=0)

    with pytest.raises(RuntimeError, match="PCM queue overrun"):
        session.raise_if_failed()
    assert session.stop_event.is_set()


def test_finalized_path_queue_is_bounded(tmp_path: Path):
    session = CaptureSession(
        WorkerConfig(),
        FakeJournal(tmp_path / "segment.wav"),
        ffmpeg_path=Path("ffmpeg.exe"),
    )

    assert session.finalized_paths.maxsize > 0


def test_finalized_path_backpressure_becomes_explicit_failure(tmp_path: Path):
    journal = FakeJournal(tmp_path / "segment.wav")
    session = CaptureSession(
        WorkerConfig(),
        journal,
        ffmpeg_path=Path("ffmpeg.exe"),
        encoder=lambda wav, ffmpeg: wav,
    )
    session.FINALIZED_PATH_PUT_TIMEOUT = 0
    for _ in range(session.finalized_paths.maxsize):
        session.finalized_paths.put_nowait(tmp_path / "queued.wav")
    session.finalize_queue.put(journal)
    session.finalize_queue.put(None)

    session.finalizer_loop()

    with pytest.raises(RuntimeError, match="backpressure timeout"):
        session.raise_if_failed()
