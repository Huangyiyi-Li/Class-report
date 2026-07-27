# Task 5 Report

## Scope delivered

- Added a Windows-only PyInstaller worker build that emits `build/worker/ClassroomRecorderWorker.exe`.
- Made Windows release packaging require a trusted external `FFMPEG_EXE`, copy it to the generated build input, build the worker, and package both files under `resources/worker` and `resources/ffmpeg`.
- Added save-dialog diagnostic JSON export with explicit success/failure dialogs and recursive redaction for keys containing password, token (including control token), secret, or authorization.
- Added package resource regression tests, recursive diagnostic tests, Vite-compatible Node `^20.19.0 || >=22.12.0`, and the clean-checkout repository gate to the default `npm test` command.
- Hardened the worker build with the repository import path, explicit audio/upload hidden imports, OSS dynamic collection and metadata, plus a pinned build-input manifest.
- Aligned Windows output to NSIS and portable targets, and made Git/check-cleanout explicitly ignore only generated worker and FFmpeg directories while retaining icons.
- Documented exact automated checks, Windows failure tests, Windows 7 non-support, install/upgrade/uninstall expectations, ice-point risk, and the 72-hour release gate.
- Generated artifacts and the FFmpeg binary remain untracked.

## TDD evidence

Initial focused run failed 4/4 because `diagnostics.js`, resource declarations, repository test wiring, Node engines, and Windows input preparation were absent. After the minimal implementation, the focused run passed 5/5.

Remediation contract tests then failed on all four approval findings (runtime build dependencies, portable target, Vite engine range, and explicit generated-input ignores). An additional metadata assertion failed before `--copy-metadata oss2` was added. The remediated focused suite passes 5/5.

## Mac verification

- `node --test src/diagnostics.test.js src/package-resources.test.js`: 5 passed.
- `npm test`: 70 Node tests passed; clean-checkout gate passed.
- `python3 -m pytest electron-recorder/worker`: 113 passed.
- `npm run build`: passed.
- `npm run electron:smoke`: passed with `"passed":true`.
- `node --check src/main.js`, `node --check scripts/build-windows-release.mjs`, `python3 -m py_compile scripts/build-worker.py`, and `git diff --check`: passed.
- `npm run dist:win` on macOS: rejected as designed with `Windows release inputs must be built and packaged on Windows.`

`npm install --package-lock-only --ignore-scripts` reported six dependency audit findings (1 low, 1 moderate, 4 high); no forced dependency upgrades were made because they are outside this scoped packaging task.

## Outstanding release gates

- Run `npm run dist:win` on Windows 10/11 x64 with trusted `FFMPEG_EXE` and inspect packaged resources.
- Complete Windows install, upgrade, uninstall, re-install, and failure matrix.
- Complete ice-point/restore-software persistence testing.
- Complete and retain evidence for the 72-hour stability run.

No Windows true-machine, ice-point, or 72-hour result is claimed from this Mac verification.
