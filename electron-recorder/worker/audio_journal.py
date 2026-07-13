from __future__ import annotations

import json
import os
import wave
from datetime import datetime
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
        _write_metadata(
            self.meta_path,
            {
                "rate": rate, "channels": channels, "sampleWidth": sample_width,
                "deviceId": device_id, "schoolId": school_id,
                "locationId": location_id, "startedAt": started_at.isoformat(),
            },
        )

    def append(self, pcm: bytes) -> None:
        self.file.write(pcm)

    def checkpoint(self) -> None:
        self.file.flush()
        os.fsync(self.file.fileno())

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
    part: Path, target: Path, rate: int, channels: int, sample_width: int
) -> None:
    temporary = target.with_suffix(target.suffix + ".tmp")
    with wave.open(str(temporary), "wb") as output:
        output.setframerate(rate)
        output.setnchannels(channels)
        output.setsampwidth(sample_width)
        output.writeframes(part.read_bytes())
    with temporary.open("rb") as output_file:
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
            _pcm_to_wav(
                part,
                target,
                meta["rate"],
                meta["channels"],
                meta["sampleWidth"],
            )
            if queue_store is not None:
                ended_at = datetime.fromtimestamp(target.stat().st_mtime).astimezone()
                device_id = meta["deviceId"]
                queue_store.enqueue({
                    "local_path": str(target),
                    "segment_index": queue_store.next_segment_index(
                        device_id, ended_at.date().isoformat()
                    ),
                    "code": device_id, "device_no": device_id,
                    "school_id": meta.get("schoolId"),
                    "location_id": meta.get("locationId", ""),
                    "start_time": meta["startedAt"], "end_time": ended_at.isoformat(),
                    "rate": meta["rate"], "bits": meta["sampleWidth"] * 8,
                    "channel": meta["channels"], "audio_type": 1,
                    "audio_format": "wav",
                })
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
    try:
        descriptor = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
