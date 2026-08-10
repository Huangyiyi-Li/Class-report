import os
import subprocess
from pathlib import Path

import pytest

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


@pytest.mark.skipif(os.name != "nt", reason="Windows process creation flag")
def test_windows_ffmpeg_never_opens_a_console_window(tmp_path: Path, monkeypatch):
    wav = tmp_path / "segment.wav"
    wav.write_bytes(b"wav")
    invocation = {}

    def capture_invocation(command, **kwargs):
        invocation.update(kwargs)
        Path(command[-1]).write_bytes(b"ogg")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr("worker.segment_encoder.subprocess.run", capture_invocation)
    encode_ogg_opus(wav, Path("ffmpeg.exe"))

    assert invocation["creationflags"] & subprocess.CREATE_NO_WINDOW


def test_falls_back_to_wav_when_ffmpeg_fails(tmp_path: Path, monkeypatch):
    wav = tmp_path / "segment.wav"
    wav.write_bytes(b"wav")
    monkeypatch.setattr("worker.segment_encoder.subprocess.run", fake_failed_ffmpeg)

    assert encode_ogg_opus(wav, Path("ffmpeg.exe")) == wav


def test_removes_empty_ogg_when_ffmpeg_produces_no_audio(tmp_path: Path, monkeypatch):
    wav = tmp_path / "segment.wav"
    wav.write_bytes(b"wav")
    ogg = tmp_path / "segment.ogg"

    def write_empty_output(command, **kwargs):
        Path(command[-1]).touch()
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(
        "worker.segment_encoder.subprocess.run",
        write_empty_output,
    )

    assert encode_ogg_opus(wav, Path("ffmpeg.exe")) == wav
    assert not ogg.exists()
    assert not list(tmp_path.glob("*.tmp.ogg"))


def test_failed_reencode_never_deletes_an_existing_valid_ogg(tmp_path: Path, monkeypatch):
    wav = tmp_path / "segment.wav"
    wav.write_bytes(b"wav")
    ogg = tmp_path / "segment.ogg"
    ogg.write_bytes(b"previous-valid-ogg")

    def write_partial_then_fail(command, **kwargs):
        Path(command[-1]).write_bytes(b"partial")
        raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(
        "worker.segment_encoder.subprocess.run", write_partial_then_fail
    )

    assert encode_ogg_opus(wav, Path("ffmpeg.exe")) == wav
    assert ogg.read_bytes() == b"previous-valid-ogg"
    assert not list(tmp_path.glob("*.tmp.ogg"))
