import subprocess
from pathlib import Path

from worker.segment_encoder import encode_ogg_opus


def fake_successful_ffmpeg(command, **kwargs):
    Path(command[-1]).write_bytes(b"ogg")
    return subprocess.CompletedProcess(command, 0)


def fake_failed_ffmpeg(command, **kwargs):
    raise subprocess.CalledProcessError(1, command)


def test_returns_ogg_when_ffmpeg_succeeds(tmp_path: Path, monkeypatch):
    wav = tmp_path / "segment.wav"
    wav.write_bytes(b"wav")
    monkeypatch.setattr(
        "worker.segment_encoder.subprocess.run", fake_successful_ffmpeg
    )

    result = encode_ogg_opus(wav, Path("ffmpeg.exe"))

    assert result.suffix == ".ogg"


def test_falls_back_to_wav_when_ffmpeg_fails(tmp_path: Path, monkeypatch):
    wav = tmp_path / "segment.wav"
    wav.write_bytes(b"wav")
    monkeypatch.setattr("worker.segment_encoder.subprocess.run", fake_failed_ffmpeg)

    assert encode_ogg_opus(wav, Path("ffmpeg.exe")) == wav


def test_removes_empty_ogg_when_ffmpeg_produces_no_audio(tmp_path: Path, monkeypatch):
    wav = tmp_path / "segment.wav"
    wav.write_bytes(b"wav")
    ogg = tmp_path / "segment.ogg"
    ogg.touch()
    monkeypatch.setattr(
        "worker.segment_encoder.subprocess.run",
        lambda command, **kwargs: subprocess.CompletedProcess(command, 0),
    )

    assert encode_ogg_opus(wav, Path("ffmpeg.exe")) == wav
    assert not ogg.exists()
