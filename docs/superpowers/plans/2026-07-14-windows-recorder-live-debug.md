# Windows Recorder Live Debug Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reproduce and fix `WIN-REC-002` on a real Windows 10/11 x64 machine, then prove the exact packaged artifact can complete normal startup and a real microphone recording cycle.

**Architecture:** Keep the current Electron shell and detached Python worker design. Add evidence capture and a packaged normal-start integration gate alongside the existing renderer-only smoke test; make only the minimal runtime fix justified by the Windows evidence.

**Tech Stack:** Windows 10/11 x64, Electron 35, React 19, Node.js 22.12, Python 3.11, PyInstaller, sounddevice/PortAudio, FFmpeg, PowerShell, GitHub Actions.

## Global Constraints

- Reproduce the published `0.1.18-beta.2` Setup artifact before changing code.
- Do not set `ELECTRON_SMOKE_TEST` during reproduction or acceptance.
- Keep all application data off the system drive.
- Do not add Windows 7 support, QR binding, remote policy, a Windows service, or ice-point bypassing.
- Do not publish a release until normal startup and real microphone capture pass on the target machine.
- Redact credentials, binding identity, school data, control tokens, and real audio from committed evidence.

---

### Task 1: Capture the exact Windows failure

**Files:**
- Modify: `docs/windows-recorder/INCIDENTS.md`
- Create only if safe: `docs/windows-recorder/evidence/WIN-REC-002-summary.md`

**Interfaces:**
- Produces: a deterministic reproduction containing artifact SHA-256, Windows build, install mode, error stack, failing process, and exit code.
- Consumes: `0.1.18-beta.2` SHA-256 values already recorded in `INCIDENTS.md`.

- [ ] Verify the downloaded Setup SHA-256 with `Get-FileHash`; stop if it differs from the recorded digest.
- [ ] Reproduce from a clean uninstall/reinstall while preserving a copy of any non-system data directory.
- [ ] Launch the installed exe from PowerShell with Electron logging and save stdout/stderr.
- [ ] Record the exact failing executable, module/path, exit code, Windows build, install path, and whether the worker process appeared.
- [ ] Inspect `app.asar`, packaged worker, and FFmpeg only after the original error is preserved.
- [ ] Update `INCIDENTS.md` with facts and remove all secret or school-specific values.
- [ ] Commit with `docs(recorder): capture 0.1.18 Windows startup failure`.

### Task 2: Add a regression that fails for the observed root cause

**Files:**
- Modify: the smallest relevant `electron-recorder/src/*.test.js` or `electron-recorder/worker/test_*.py`
- Modify if packaging-related: `electron-recorder/src/package-resources.test.js`
- Modify if workflow-related: `.github/workflows/windows-recorder.yml`

**Interfaces:**
- Produces: one focused automated test that fails against commit `4925f9a` for the reproduced reason.
- Consumes: the exact evidence from Task 1; no speculative failure modes.

- [ ] Select the layer from evidence: Electron module packaging, normal bootstrap, worker launch, PyInstaller dependency, control endpoint, or microphone startup.
- [ ] Write a focused regression using the same path and condition as the real failure.
- [ ] Run only that test and confirm it fails for the expected reason.
- [ ] Confirm the test does not rely on a fake WorkerClient if the failure occurs after normal bootstrap.
- [ ] Commit the failing regression with `test(recorder): reproduce Windows startup failure`.

### Task 3: Implement the minimum runtime fix

**Files:**
- Modify: only files identified by Task 2
- Modify: `docs/windows-recorder/INCIDENTS.md`

**Interfaces:**
- Produces: installed normal startup that reaches a real worker connection or an explicit recoverable first-run state.
- Consumes: the Task 2 regression without weakening its assertions.

- [ ] Implement the smallest correction and keep the existing security/storage boundaries.
- [ ] Run the focused regression and confirm it passes.
- [ ] Run `python -m pytest worker ..\windows_client\test_timeouts.py -q`.
- [ ] Run `npm test` and `npm run build`.
- [ ] Update the incident with root cause, fix, and remaining risks.
- [ ] Commit with a root-cause-specific `fix(recorder): ...` message.

### Task 4: Add a packaged normal-start Windows gate

**Files:**
- Create: `electron-recorder/scripts/test-packaged-normal-start.ps1`
- Modify: `.github/workflows/windows-recorder.yml`
- Modify: `electron-recorder/src/package-resources.test.js`
- Modify: `docs/windows-recorder/RELEASE_PROCESS.md`

**Interfaces:**
- Produces: a Windows integration check that launches the packaged exe without `ELECTRON_SMOKE_TEST`, uses a temporary non-system-drive test root where available, starts the real packaged worker, waits for an authenticated ready/snapshot state, and terminates test processes cleanly.
- Consumes: existing packaged worker, FFmpeg, worker control protocol, and the root cause fixed in Task 3.

- [ ] Add a repository assertion requiring the normal-start script and workflow step.
- [ ] Run the assertion and confirm it fails before the script/workflow exist.
- [ ] Implement a bounded PowerShell harness with unique temporary runtime/config paths, log capture, process cleanup, and nonzero failure exit.
- [ ] Keep `ELECTRON_SMOKE_TEST` unset and assert that the real packaged worker process starts and authenticates.
- [ ] Add the step after packaged resource verification and before artifact upload.
- [ ] Run the test on the Windows development machine and then in GitHub Actions.
- [ ] Commit with `ci(recorder): verify packaged normal startup`.

### Task 5: Build and accept a new candidate

**Files:**
- Modify: `electron-recorder/package.json`
- Modify: `electron-recorder/package-lock.json`
- Modify: `docs/windows-recorder/INCIDENTS.md`
- Modify: `docs/windows-recorder/HANDOFF.md`

**Interfaces:**
- Produces: a new prerelease artifact with recorded SHA-256 and Windows acceptance evidence.
- Consumes: all green automation and the normal-start gate from Task 4.

- [ ] Increment the patch version and lockfile version consistently.
- [ ] Build Setup and Portable packages on Windows with the trusted FFmpeg input.
- [ ] Install the Setup package on the failing machine and verify normal startup without test variables.
- [ ] Select a non-system data root, start a real microphone recording, confirm durable output, stop, restart, and reconnect.
- [ ] Push the branch, create a new prerelease tag, and wait for all GitHub workflow steps.
- [ ] Download the GitHub Release Setup artifact and repeat the startup/recording quick regression on the same machine.
- [ ] Record artifact URL, SHA-256, Windows build, results, and any remaining limitations.
- [ ] Close `WIN-REC-002` only after the Release artifact passes; commit with `docs(recorder): close Windows startup incident`.

## Self-review

- The plan covers the latest user report, real Windows reproduction, a root-cause regression, normal packaged startup, real worker launch, microphone capture, and Release-asset retesting.
- It does not claim that renderer smoke, CI resource checks, or a locally built package proves the published installer works.
- It contains no placeholder implementation decisions; the exact code layer is intentionally selected from Task 1 evidence before Task 2 because the new error details are not yet available.
