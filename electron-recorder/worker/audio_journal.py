from __future__ import annotations

import json
import os
import wave
from datetime import datetime
from pathlib import Path


class AudioJournal:
    def __init__(
        self,
        root: Path,
        device_id: str,
        started_at: datetime,
        rate: int,
        channels: int,
        sample_width: int,
    ):
        root.mkdir(parents=True, exist_ok=True)
        stem = f"{device_id}_{started_at.strftime('%Y%m%d_%H%M%S_%f')}"
        self.part_path = root / f"{stem}.pcm.part"
        self.meta_path = root / f"{stem}.json"
        self.wav_path = root / f"{stem}.wav"
        self.rate = rate
        self.channels = channels
        self.sample_width = sample_width
        self.file = self.part_path.open("ab", buffering=0)
        self.meta_path.write_text(
            json.dumps(
                {
                    "rate": rate,
                    "channels": channels,
                    "sampleWidth": sample_width,
                }
            ),
            encoding="utf-8",
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
        return self.wav_path


def _pcm_to_wav(
    part: Path, target: Path, rate: int, channels: int, sample_width: int
) -> None:
    with wave.open(str(target), "wb") as output:
        output.setframerate(rate)
        output.setnchannels(channels)
        output.setsampwidth(sample_width)
        output.writeframes(part.read_bytes())


def recover_journals(root: Path) -> list[Path]:
    recovered = []
    for part in root.glob("*.pcm.part"):
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
        part.unlink(missing_ok=True)
        meta_path.unlink(missing_ok=True)
        recovered.append(target)
    return recovered
