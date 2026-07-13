from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = ROOT / "worker" / "recorder_worker.py"
OUTPUT = ROOT / "build" / "worker"


def main() -> int:
    if sys.platform != "win32":
        print("ClassroomRecorderWorker.exe must be built on Windows.", file=sys.stderr)
        return 1

    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--onefile",
            "--name",
            "ClassroomRecorderWorker",
            "--distpath",
            str(OUTPUT),
            "--workpath",
            str(ROOT / "worker" / "build"),
            "--specpath",
            str(ROOT / "worker"),
            str(ENTRYPOINT),
        ],
        cwd=ROOT,
        check=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
