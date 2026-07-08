from datetime import datetime, timezone
from pathlib import Path

from worker.audio_journal import AudioJournal, recover_journals
from worker.config import WorkerConfig
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
    assert journal.finalized == 1
    assert session.finalized_paths.get_nowait() == encoded


def test_writer_rotates_journal_at_segment_boundary(tmp_path: Path):
    first = FakeJournal(tmp_path / "first.wav")
    second = FakeJournal(tmp_path / "second.wav")
    session = CaptureSession(
        WorkerConfig(segment_seconds=300, checkpoint_seconds=1000),
        first,
        ffmpeg_path=Path("ffmpeg.exe"),
        encoder=lambda wav, ffmpeg: wav,
        journal_factory=lambda: second,
        clock=iter([0.0, 100.0, 301.0]).__next__,
    )
    session.pcm_queue.put(b"first")
    session.pcm_queue.put(b"second")
    session.stop_event.set()

    session.writer_loop()

    assert first.appended == [b"first"]
    assert second.appended == [b"second"]
    assert first.finalized == 1
    assert second.finalized == 1


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
