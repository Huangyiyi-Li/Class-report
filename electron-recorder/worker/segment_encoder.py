from __future__ import annotations

import subprocess
from pathlib import Path


def encode_ogg_opus(wav_path: Path, ffmpeg_path: Path) -> Path:
    target = wav_path.with_suffix(".ogg")
    try:
        subprocess.run(
            [
                str(ffmpeg_path),
                "-y",
                "-i",
                str(wav_path),
                "-ac",
                "1",
                "-ar",
                "16000",
                "-c:a",
                "libopus",
                "-b:a",
                "32k",
                str(target),
            ],
            check=True,
            capture_output=True,
            timeout=120,
        )
        if target.exists() and target.stat().st_size > 0:
            wav_path.unlink(missing_ok=True)
            return target
    except (OSError, subprocess.SubprocessError):
        pass
    target.unlink(missing_ok=True)
    return wav_path
