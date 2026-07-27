# Windows Recorder Stability Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the recorder reproducible from a clean checkout and enforce the production safety and lifecycle guarantees approved in the stability remediation design.

**Architecture:** Preserve Electron as the shell and Python as the recorder, but replace parent-owned stdio lifetime with an authenticated loopback control server owned by a detached single-instance worker. Centralize startup gates and persisted settings in the worker; Electron renders verified state and reconnects without controlling recording lifetime.

**Tech Stack:** Electron 35, React 19, Node.js, Python 3.11+, sounddevice, NumPy, SQLite, PyInstaller, Node test runner, pytest.

## Global Constraints

- Windows 10/11 x64 only; Windows 7 remains an unsupported risk.
- Application data, settings, audio, queue, and logs must remain off the system drive.
- Missing/invalid storage or binding blocks recording; network failure does not.
- Electron keeps `contextIsolation: true` and `nodeIntegration: false`.
- Use TDD: every behavioral change begins with a focused failing test.
- Do not commit `node_modules`, generated renderer bundles, installers, recordings, queues, secrets, or generated worker executables.
- Keep the local control protocol maintainable: an ACK lost after successful execution is reported as an unconfirmed result and manually rechecked; do not add distributed transaction logs, two-phase commit, or durable command-result reconciliation in the first release.

---

### Task 1: Reproducible Repository Baseline

**Files:**
- Modify: `.gitignore`
- Add: `electron-recorder/package.json`
- Add: `electron-recorder/package-lock.json`
- Add: `electron-recorder/vite.config.js`
- Add: `electron-recorder/build/icon.ico`
- Add: `electron-recorder/build/icon.png`
- Add: required source scripts under `electron-recorder/scripts/`
- Test: `electron-recorder/scripts/test-clean-checkout.mjs`

**Interfaces:**
- Produces: a tracked manifest and deterministic `npm ci`, test, and renderer build path.

- [ ] Write a repository test that reads `git ls-files` and fails when any required manifest/config/script/icon is absent or any generated directory is tracked.
- [ ] Run the repository test and confirm it fails because required files are untracked.
- [ ] Track only required build inputs; ignore `node_modules/`, `dist/`, `release/`, generated worker output, archive packages, and legacy demo launchers.
- [ ] Run the repository test, `npm test`, and `npm run build`; confirm all pass.
- [ ] Commit with `build(recorder): make clean checkout reproducible`.

### Task 2: Production Startup Gates and Automatic Recording

**Files:**
- Modify: `electron-recorder/worker/config.py`
- Modify: `electron-recorder/worker/recorder_worker.py`
- Modify: `electron-recorder/worker/test_config.py`
- Modify: `electron-recorder/worker/test_recorder_worker.py`

**Interfaces:**
- Produces: `evaluate_startup_gate(config, system_drive) -> StartupGate` and `RecorderWorker.maybe_auto_start()`.
- Consumes: existing `WorkerConfig`, queue store, capture session and snapshot state.

- [ ] Add failing tests for empty/system-drive/relative data roots, unwritable storage, low disk, missing binding fields, removal of `unconfigured-device`, and successful non-system-drive binding.
- [ ] Add a failing test proving `auto_record_enabled=True` starts exactly once after startup gates pass and never starts when a gate fails.
- [ ] Run focused tests and confirm failures describe the missing gates and automatic behavior.
- [ ] Implement centralized gate evaluation; remove the current-directory fallback and map failures to `storage_unavailable`, `disk_low`, or `binding_required`.
- [ ] Implement automatic start after recovery and queue initialization, using the same guarded start path as manual recording.
- [ ] Run the full worker suite and commit with `fix(recorder): enforce startup safety gates`.

### Task 3: Detached Worker and Reconnectable Local Control

**Files:**
- Create: `electron-recorder/worker/control_server.py`
- Create: `electron-recorder/worker/test_control_server.py`
- Modify: `electron-recorder/worker/recorder_worker.py`
- Create: `electron-recorder/src/worker-client.js`
- Create: `electron-recorder/src/worker-client.test.js`
- Modify: `electron-recorder/src/main.js`

**Interfaces:**
- Worker listens on `127.0.0.1` with an OS-assigned port and requires a random token stored in the non-system-drive runtime directory.
- Electron exposes `WorkerClient.connect()`, `.send(command, payload)`, `.disconnect()` and emits worker events compatible with the current renderer snapshot contract.

- [ ] Add failing Python tests proving an authenticated client can command the worker, a wrong token is rejected, a disconnected client does not stop capture, and a second server instance is rejected.
- [ ] Add failing Node tests proving Electron connects to an existing endpoint, launches a detached worker only when needed, retries connection, and disconnects without sending `shutdown`.
- [ ] Run focused Python and Node tests and confirm the lifecycle failures.
- [ ] Implement the loopback server, endpoint/token file with owner-restricted best-effort permissions, and single-instance lock.
- [ ] Replace stdio supervision in Electron with reconnectable `WorkerClient`; detached worker stdio must not be piped to Electron.
- [ ] Preserve explicit start/pause/stop commands, but remove shutdown-on-Electron-quit behavior.
- [ ] Run full Python/Node suites plus Electron smoke and commit with `refactor(recorder): detach worker lifecycle from Electron`.

### Task 4: Persisted Settings, Verified Auto-Launch, and Safe IPC

**Files:**
- Create: `electron-recorder/src/settings.js`
- Create: `electron-recorder/src/settings.test.js`
- Modify: `electron-recorder/src/main.js`
- Modify: `electron-recorder/src/preload.cjs`
- Modify: `electron-recorder/src/renderer.jsx`
- Modify: `electron-recorder/worker/config.py`
- Modify: relevant Node/Python tests.

**Interfaces:**
- Produces: `validateSettingsPatch(patch)` and an auto-launch status `{ desired, actual, status, error }`.
- Consumes: non-system-drive config location established by Task R2.

- [ ] Add failing tests for false-by-default auto-launch, persistence across restart, three-state verification, rejected non-boolean/oversized/object/path inputs, and worker-side validation.
- [ ] Run focused tests and confirm failures.
- [ ] Implement validated settings persistence without overwriting the worker config from stale Electron defaults.
- [ ] Query actual Windows login-item state after every change and startup; render verified/unverified/failed status.
- [ ] Ensure binding identifiers cannot be changed through the general renderer settings IPC.
- [ ] Run full test/build/smoke verification and commit with `fix(recorder): persist and validate runtime settings`.

### Task 5: Diagnostics, Packaging Inputs, and Delivery Gate

**Files:**
- Create: `electron-recorder/scripts/build-worker.py`
- Modify: `electron-recorder/scripts/build-windows-release.mjs`
- Modify: `electron-recorder/package.json`
- Create: `electron-recorder/docs/TESTING.md`
- Modify: `electron-recorder/WINDOWS_TEST_README.md`
- Modify: `electron-recorder/src/main.js`
- Add tests for diagnostic redaction and package resource declarations.

**Interfaces:**
- Produces: `build/worker/ClassroomRecorderWorker.exe`, packaged `resources/worker/ClassroomRecorderWorker.exe`, packaged `resources/ffmpeg/ffmpeg.exe`, and a written diagnostic JSON export.

- [ ] Add failing tests that require worker/FFmpeg package resources and redact password, token, secret, authorization and control-token fields recursively.
- [ ] Run focused tests and confirm failures.
- [ ] Add the PyInstaller build, Windows-only FFmpeg resource validation, and installer resource declarations.
- [ ] Implement Save-dialog diagnostic export with recursive redaction and explicit success/failure feedback.
- [ ] Write exact automated, clean-checkout and Windows failure-test commands; document Win7 non-support, ice-point risk, install/upgrade/uninstall behavior and the 72-hour gate.
- [ ] Run Python, Node, build and Electron smoke tests; on Windows run `npm run dist:win` and inspect packaged resources.
- [ ] Commit with `build(recorder): package worker and document validation`.

### Task 6: Core Capture Recovery Completion

**Files:**
- Modify: `electron-recorder/worker/audio_journal.py`
- Modify: `electron-recorder/worker/recorder_worker.py`
- Modify: worker recovery and lifecycle tests
- Modify: `electron-recorder/src/settings.js`
- Modify: `electron-recorder/src/main.js`
- Modify: relevant Node settings tests
- Modify: `electron-recorder/docs/TESTING.md`

**Interfaces:**
- Produces: recovered journals that enter the durable upload queue exactly once; capture readiness after the first durable write; bounded microphone reopen after an unexpected capture failure; Electron settings persisted beside the non-system worker configuration.

- [ ] Add failing tests proving recovered audio is enqueued once with journal-time device/location metadata and remains retryable.
- [ ] Add failing tests proving `recording` is published only after the first durable audio write and a missing microphone maps to `microphone_unavailable`.
- [ ] Add failing tests proving an unexpected microphone/capture failure retries while recording is desired, and an explicit user stop cancels retry.
- [ ] Add failing Node tests proving Electron preferences default safely before bootstrap and persist beside the located non-system worker config after bootstrap, not under `userData`.
- [ ] Implement the minimum behavior without adding remote policy, Windows services, or a new binding mechanism.
- [ ] Run all Python/Node/build/smoke checks and commit with `fix(recorder): complete capture recovery lifecycle`.

**Scope boundary:** Self-service QR binding remains a separate external integration because the mini-program and binding-service repositories are absent. Windows technical validation may use a controlled pre-provisioned binding fixture; this is not a production user binding flow and must not be presented as one.

## Exit Criteria

1. A clean checkout contains every source/build input and excludes generated dependencies and artifacts.
2. No recording starts without valid non-system storage and a complete device/location binding.
3. Automatic recording begins only after all safety gates pass.
4. Electron main-process termination does not stop an active recorder worker; restarting Electron reconnects to it.
5. Auto-launch is false by default, persisted, and reports actual registration status.
6. Renderer IPC rejects malformed settings and cannot mutate binding identity.
7. The installer definition includes the worker and Windows FFmpeg.
8. All automated checks pass; true Windows/ice-point/72-hour checks remain explicit release gates until executed.
9. Recovered journals re-enter the upload queue, capture state follows a durable first write, and transient microphone failures retry without overriding an explicit stop.
