# Repository guidance

## Windows recorder scope

The active Windows client lives in `electron-recorder/`. Read these files before changing it:

1. `docs/windows-recorder/HANDOFF.md`
2. `docs/windows-recorder/INCIDENTS.md`
3. `docs/windows-recorder/WINDOWS_DEVELOPMENT.md`
4. `docs/superpowers/specs/2026-07-07-windows-recorder-production-design.md`
5. `docs/superpowers/specs/2026-07-13-windows-recorder-stability-remediation-design.md`

The current branch is `feat/windows-recorder-production`. Do not merge it to `master` or publish another release until the open `WIN-REC-002` startup incident is reproduced and fixed on a real Windows 10/11 x64 machine.

## Required engineering rules

- Treat the installed Windows application as the primary reproduction target. A source-mode or smoke-test pass is insufficient.
- Start every bug fix with a focused failing regression test when the failure can be automated.
- Keep `contextIsolation: true` and `nodeIntegration: false`.
- Never fall back to the system drive for configuration, audio, queue, runtime files, or logs.
- Network failure must not stop recording. Missing storage, binding, or microphone must block recording visibly.
- Do not add Windows 7 support, remote policy, QR binding, a Windows service, or ice-point bypassing while fixing the current startup incident.
- Do not commit secrets, school fixtures, recordings, generated installers, `node_modules`, `dist`, `release`, `build/worker`, or `build/ffmpeg`.
- The untracked legacy files under `windows_client/` are not part of the Electron recorder change unless a task explicitly requires them.

## Verification baseline

Run from `electron-recorder/`:

```powershell
python -m pytest worker ..\windows_client\test_timeouts.py -q
npm test
npm run build
```

For a Windows installer candidate, also follow `docs/windows-recorder/WINDOWS_DEVELOPMENT.md` and complete the normal-start packaged test. `ELECTRON_SMOKE_TEST=1` verifies renderer/package loading only and cannot prove normal startup or recording works.

## Commit and release discipline

- Preserve unrelated user changes and legacy untracked files.
- Use small conventional commits.
- Push work to `feat/windows-recorder-production` and keep PR #1 as draft until all release gates pass.
- Use a new prerelease tag for every candidate; never move or reuse an existing tag.
- A release is acceptable only after Windows normal startup, first-run configuration, worker launch, microphone capture, and stop/restart behavior have been tested on the exact artifact.
