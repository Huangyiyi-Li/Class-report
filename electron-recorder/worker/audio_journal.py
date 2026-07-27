from __future__ import annotations

import json
import os
import wave
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable


class AudioJournal:
    def __init__(
        self,
        root: Path,
        device_id: str,
        started_at: datetime,
        rate: int,
        channels: int,
        sample_width: int,
        *,
        school_id: int | None = None,
        location_id: str = "",
    ):
        root.mkdir(parents=True, exist_ok=True)
        self.root = root
        self.device_id = device_id
        self.started_at = started_at
        stem = f"{device_id}_{started_at.strftime('%Y%m%d_%H%M%S_%f')}"
        self.part_path = root / f"{stem}.pcm.part"
        self.meta_path = root / f"{stem}.json"
        self.wav_path = root / f"{stem}.wav"
        self.rate = rate
        self.channels = channels
        self.sample_width = sample_width
        self.school_id = school_id
        self.location_id = location_id
        self.file = self.part_path.open("ab", buffering=0)
        self._metadata = {
                "rate": rate, "channels": channels, "sampleWidth": sample_width,
                "deviceId": device_id, "schoolId": school_id,
                "locationId": location_id, "startedAt": started_at.isoformat(),
                "durableFrames": 0,
            }
        _write_metadata(self.meta_path, self._metadata)

    def append(self, pcm: bytes) -> None:
        self.file.write(pcm)

    def checkpoint(self) -> None:
        self.file.flush()
        os.fsync(self.file.fileno())
        self._metadata["durableFrames"] = (
            self.file.tell() // (self.sample_width * self.channels)
        )
        _write_metadata(self.meta_path, self._metadata)

    def finalize(self, end_time: datetime | None = None) -> Path:
        self.checkpoint()
        self.file.close()
        _pcm_to_wav(
            self.part_path,
            self.wav_path,
            self.rate,
            self.channels,
            self.sample_width,
        )
        self.part_path.unlink(missing_ok=True)
        self.meta_path.unlink(missing_ok=True)
        _fsync_directory(self.wav_path.parent)
        return self.wav_path


def _pcm_to_wav(
    part: Path,
    target: Path,
    rate: int,
    channels: int,
    sample_width: int,
    *,
    frame_count: int | None = None,
) -> None:
    if frame_count is None:
        pcm = part.read_bytes()
    else:
        byte_count = frame_count * channels * sample_width
        with part.open("rb") as source:
            pcm = source.read(byte_count)
        if len(pcm) != byte_count:
            raise ValueError("journal PCM is shorter than its durable frame count")
    temporary = target.with_suffix(target.suffix + ".tmp")
    with wave.open(str(temporary), "wb") as output:
        output.setframerate(rate)
        output.setnchannels(channels)
        output.setsampwidth(sample_width)
        output.writeframes(pcm)
    # Windows cannot flush a handle opened read-only. Reopen the completed WAV
    # for update so fsync/FlushFileBuffers receives a writable handle.
    with temporary.open("r+b") as output_file:
        os.fsync(output_file.fileno())
    os.replace(temporary, target)
    _fsync_directory(target.parent)


def recover_journals(
    root: Path, on_error: Callable[[Exception], None] | None = None, *, queue_store=None
) -> list[Path]:
    recovered = []
    for part in root.glob("*.pcm.part"):
        try:
            meta_path = part.with_suffix("").with_suffix(".json")
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            target = part.with_suffix("").with_suffix(".wav")
            frame_size = meta["channels"] * meta["sampleWidth"]
            durable_frames = meta.get("durableFrames")
            if durable_frames is None:
                durable_frames = part.stat().st_size // frame_size
            if (
                isinstance(durable_frames, bool)
                or not isinstance(durable_frames, int)
                or durable_frames < 0
            ):
                raise ValueError("journal durableFrames must be a non-negative integer")
            _pcm_to_wav(
                part,
                target,
                meta["rate"],
                meta["channels"],
                meta["sampleWidth"],
                frame_count=durable_frames,
            )
            if queue_store is not None:
                started_at = datetime.fromisoformat(meta["startedAt"])
                ended_at = started_at + timedelta(
                    seconds=durable_frames / meta["rate"]
                )
                device_id = meta["deviceId"]
                segment = {
                    "local_path": str(target),
                    "code": device_id, "device_no": device_id,
                    "school_id": meta.get("schoolId"),
                    "location_id": meta.get("locationId", ""),
                    "start_time": meta["startedAt"], "end_time": ended_at.isoformat(),
                    "rate": meta["rate"], "bits": meta["sampleWidth"] * 8,
                    "channel": meta["channels"], "audio_type": 1,
                    "audio_format": "wav",
                }
                queue_store.enqueue_recovered(
                    segment, device_id, started_at.date().isoformat()
                )
            part.unlink(missing_ok=True)
            meta_path.unlink(missing_ok=True)
            _fsync_directory(root)
            recovered.append(target)
        except Exception as exc:
            if on_error is not None:
                on_error(exc)
    return recovered


def _write_metadata(target: Path, payload: dict) -> None:
    temporary = target.with_suffix(target.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as output:
        json.dump(payload, output)
        output.flush()
        os.fsync(output.fileno())
    os.replace(temporary, target)
    _fsync_directory(target.parent)


def _fsync_directory(directory: Path) -> None:
    # Windows does not support fsync on directory handles. The file itself is
    # flushed before the atomic replace above.
    if os.name == "nt":
        return
    try:
        descriptor = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
