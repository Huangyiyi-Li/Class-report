# Task 3 Report: Detached Worker and Reconnectable Local Control

## Result

The recorder worker now owns its process and capture lifecycle independently of Electron. Electron connects to a loopback-only authenticated control endpoint, starts a detached worker only when no existing endpoint can be reached, and disconnects without issuing `shutdown` when Electron exits.

## RED evidence

- `python3 -m pytest worker/test_control_server.py -q`
  - Failed during collection with `ModuleNotFoundError: worker.control_server`.
- `node --test src/worker-client.test.js`
  - Failed with `ERR_MODULE_NOT_FOUND` for `src/worker-client.js`.

These failures were observed before either production module existed.

## GREEN implementation

- Added `ControlServer`, bound exclusively to `127.0.0.1` on an OS-assigned port.
- Added a cryptographically random token, stored separately from the endpoint metadata.
- Endpoint, token, and lock files use owner-only creation modes and best-effort `chmod(0600)`.
- Added an advisory single-instance lock. A stale lock file does not prevent restart after a crashed process because exclusivity is held by the OS lock, not file existence.
- Authentication is required before commands or snapshots are accepted.
- Client connection teardown removes only the control client. It never invokes `stop`, `pause`, or `shutdown` on the worker.
- Worker main lifetime now waits for process termination signals rather than stdin EOF.
- Added `WorkerClient.connect()`, `.send()`, and `.disconnect()`, preserving `ready`, `snapshot`, and `error` events.
- Electron reads the configured non-system-drive data root, connects first, then detached-spawns with `stdio: "ignore"` and `unref()` only when needed.
- Electron `before-quit` only disconnects the control socket. Explicit `start`, `pause`, `stop`, and `flush_queue` command paths remain unchanged.
- Included `worker-client.js` in packaged application files.

## Verification

- Focused Python lifecycle tests: 5 passed.
- Focused Node lifecycle tests: 4 passed.
- Full Python worker suite: 93 passed.
- Full Node suite: 21 passed.
- Vite production build: passed.
- Electron smoke: passed, including main window, floating ball, and settings modal checks.
- `git diff --check`, `node --check src/main.js`, and `node --check src/worker-client.js`: passed.

## Lifecycle argument

The capture session is owned only by `RecorderWorker`. A control handler calls `worker.handle()` solely for explicit protocol commands. Its `finally` block only unregisters the socket client. Electron's quit path calls `WorkerClient.disconnect()`, which invokes socket `end()` and writes no command. Therefore Electron shutdown, renderer loss, socket errors, and ordinary client disconnects cannot stop an active capture. Worker shutdown occurs only when the worker process receives a termination signal; explicit `pause` and `stop` still finalize the current capture through the existing worker command handler.

## Security self-review

- Listener address is a literal `127.0.0.1`; no wildcard or remote binding was added.
- The token is never included in endpoint JSON, renderer snapshots, IPC responses, events, or logs.
- Token comparison uses `secrets.compare_digest`.
- Detached child stdio is ignored, so secrets cannot leak through Electron's former worker pipes.
- No Windows service, remote-control surface, firewall change, or non-loopback transport was introduced.

## Compatibility and concerns

- Task 2 delayed storage initialization remains intact: `RecorderWorker.__init__` still does not bind or create storage, and the full worker suite passes. The control runtime directory is created only after configuration loading and is rooted below the configured data root (or an explicit `RECORDER_RUNTIME_DIR` override).
- A first-run installation without a configured data root cannot create a compliant non-system-drive endpoint. It exits rather than falling back to the system drive or current working directory. This is intentional for the storage/security requirement, but onboarding must ensure the worker config is established before normal connection.
- Windows advisory locking uses `msvcrt.locking`; behavior is covered structurally but was not executed on this macOS verification host.

## Remediation after review

The initial submission was rejected after deeper lifecycle review. The following corrections were implemented with additional RED/GREEN cycles:

- Moved `InstanceLock.acquire()` ahead of `RecorderWorker` construction, `startup()`, automatic capture, queue creation, upload-service creation, and upload-thread startup. Two concurrent `run_worker` race tests prove exactly one contender constructs/starts and the loser returns code 2 without entering capture startup.
- Added Electron `app.requestSingleInstanceLock()` handling in a separately tested module. A secondary Electron process quits before startup; the primary receives `second-instance` and focuses its existing window.
- Changed `WorkerClient.connect()` to resolve only after an authenticated `ready` frame. Authentication rejection, timeout, stale/failed endpoint, and close-before-ACK are failed attempts and enter the bounded retry path.
- Added bounded linear backoff capped by `maxRetryDelayMs`. Worker launch is latched for the client lifetime, preventing repeated detached launches across initial retries and later reconnects.
- Added automatic runtime reconnect on both socket `close` and `error`. Explicit `disconnect()` sets a terminal client flag before closing and therefore never reconnects or sends `shutdown`.
- Serialized every authenticated client command through one server command lock. A three-client concurrent `start`/`stop`/`update_settings` test detects and rejects overlapping `worker.handle()` calls.
- Added a two-second authentication deadline and a fixed 64 KiB maximum NDJSON line. Authentication silence and oversized authentication/command lines close the connection.
- Made Electron UI startup independent of worker availability. Windows, tray, floating controls, IPC, and settings are created first; a blocked snapshot is published and connection continues in the background.
- Expanded the real-socket Python loopback integration test: authenticate for a real ACK, start capture, disconnect, reconnect, and verify the same recording snapshot remains active. This is deliberately distinct from the Electron UI smoke, which is retained only as a UI/build smoke and is not claimed as detached-worker verification.

### Remediation RED evidence

- Concurrent client commands overlapped (`stop` and `update_settings` observed while another handler was active).
- `ControlServer` rejected authentication timeout/line-limit constructor options because the defenses did not exist.
- Authentication rejection incorrectly allowed `WorkerClient.connect()` to resolve after one socket attempt.
- Unexpected socket close left `WorkerClient.socket` null instead of reconnecting.
- Runtime `error` without an immediate `close` did not reconnect.
- Electron single-instance tests initially failed with `ERR_MODULE_NOT_FOUND` for the not-yet-created lifecycle module.

### Remediation verification

- Focused lifecycle suites: 27 Python tests and 10 Node tests passed.
- Full Python worker suite: 97 passed.
- Full Node suite: 27 passed.
- Vite production build: passed.
- Electron UI smoke: passed; it is not used as evidence for detached lifecycle behavior.
- `git diff --check` and Node syntax checks: passed.

### Remaining concern

Windows `msvcrt.locking` remains a Task 5 Windows-host gate as directed. No Windows correctness claim is made from the macOS run.

## Second remediation after bootstrap and cancellation review

### RED evidence

- Bootstrap tests initially failed because `worker-bootstrap.js` did not exist; there was no non-system config or restart locator workflow.
- The real Node-to-Python integration test initially failed waiting for `worker-endpoint.json` because no Python control harness existed.
- Disconnecting during authentication left the pending socket open, allowing a late `ready` frame to outlive application shutdown.
- Runtime `error` and late worker recovery tests exposed the need to distinguish a launch cooldown from a permanent launch latch.
- A queued-retry quit test reproduced connection work surviving after terminal disconnect.
- A pending-generation resume test failed with `worker connection cancelled`, proving the old rejected recovery promise could poison a later explicit resume.

### GREEN changes

- Added a minimal bootstrap module. The first valid settings patch atomically writes a complete worker config to `<dataRoot>/.classroom-recorder/worker-config.json`; `userData` contains only `worker-config-locator.json` with the config path and no credentials.
- Startup resolves config and runtime paths through that locator. Electron no longer reads or writes a formal worker config under `app.getPath("userData")`.
- Settings bootstrap is independent of worker connectivity. It persists first and launches the detached worker for the initially selected data root. Later non-root settings persist even when the worker socket is unavailable.
- Windows bootstrap performs the current minimal absolute/non-system-drive validation. Binding fields remain Task 4 scope; a config lacking binding still starts the worker control plane and reports the existing `binding_required` gate.
- Replaced connection flags with a generation-based cancellation model. `disconnect()` advances the generation, cancels retry sleeps, destroys pending-auth sockets, closes the active socket, and cannot be undone by late awaits or frames.
- `connect()` never clears terminal state. `start()`/`resume()` are the explicit transitions into a new active generation.
- Recovery now loops indefinitely in bounded attempt cycles and capped backoff until explicit disconnect. There is no Electron outer reconnect timer.
- Launching uses cooldown state, not a permanent latch. A successful authenticated connection resets launch eligibility, so a later real worker crash can launch again; one shared recovery promise prevents concurrent duplicate launches.
- Authentication listeners and parser are removed after ACK. Runtime event parsing is attached separately only after generation validation.
- Added a real cross-language test in which Node `WorkerClient` reads Python-generated endpoint/token files and authenticates `ControlServer`. This test was superseded and corrected in the third remediation below to prove Electron disconnect continuity without pretending worker-process restart preserves recording state.

### Verification

- Full Python worker suite: 97 passed.
- Full Node suite: 35 passed, including bootstrap/locator, queued quit cancellation, pending-auth disconnect, resume generation, late relaunch, and cross-language recovery.
- Vite production build: passed.
- Electron UI smoke: passed; still treated only as UI/build evidence.
- Syntax and diff checks: passed.

### Remaining scope note

Bootstrap intentionally performs only the minimum path validation requested here. Binding completeness and stronger configuration validation remain Task 4; Windows lock behavior remains Task 5.

## Third remediation: immutable root and corrected continuity proof

### RED evidence

- Idle and recording-state migration tests showed bootstrap accepted a second data root and created a second formal config.
- Locator tests showed UNC roots and config/data-root mismatches were accepted; the old locator lacked enough trusted structure to reject an escaped config path before reading it.
- An asynchronous child `error` with `ENOENT` was unhandled after `spawn()`, producing a Node uncaught exception after the test ended.
- The earlier cross-language test killed Python and reconstructed a string-backed state harness. Review correctly identified that this did not prove detached Electron continuity and overstated worker-crash behavior.
- Main settings orchestration initially had no isolated proof that a rejected root patch leaves the existing client attached in both idle and recording states.

### GREEN changes

- Data root is now immutable after the first valid locator/config bootstrap. Any differing root patch throws an explicit “首次部署后不可修改，需重新部署” error before settings mutation, client disconnect, config creation, or worker attachment.
- Added orchestration tests for idle and recording states proving a rejected root change never calls the client attachment path. The original worker/client remains the only instance.
- Same-root settings updates preserve the complete existing config, including binding and credential fields; runtime-root migration code is absent.
- Locator now contains only canonical `dataRoot` and `configPath`, still no secrets. Loading revalidates absolute/local/non-system root policy, rejects UNC and relative roots, requires configPath to equal canonical `<data_root>/.classroom-recorder/worker-config.json`, resolves filesystem canonical paths before reading config, and requires config `data_root` to match.
- Malformed, escaped, mismatched, system-drive, and UNC locators return no location; Electron therefore publishes its blocked bootstrap snapshot and does not read or overwrite an arbitrary target.
- Atomic JSON writes use a cryptographically random temporary name opened with `wx`/exclusive creation, remove the temporary on every failure, and best-effort fsync the parent directory on POSIX after rename.
- Detached spawn returns the child to `WorkerClient`, which installs an `error` listener immediately. Asynchronous `ENOENT` is emitted through the existing client/main error path while the bounded long-term recovery loop continues.
- Replaced the persistence harness with a real `RecorderWorker` configured with an injected microphone-free `FakeSession`. One Python process and one `ControlServer` stay alive: Node client A authenticates and starts recording, explicitly disconnects, Python remains running and recording, and Node client B reconnects to the same endpoint and receives `recording` in the live worker snapshot.
- Worker-process crash is no longer claimed to preserve an active recording state. That path only retains the existing journal-recovery guarantees.

### Verification

- Full Python worker suite: 97 passed.
- Full Node suite: 43 passed.
- Vite production build and Electron UI smoke: passed.
- Node syntax checks and `git diff --check`: passed.

### Remaining scope

Task 4 still owns binding UX/config completeness and disabling the root field with redeployment guidance. Task 5 still owns Windows-host lock validation.

## Fourth remediation: acknowledged worker-owned persistence

### RED evidence

- `WorkerClient` had no `sendCommand` API, so concurrent command IDs could not be correlated and callers could not distinguish worker persistence success from a socket write.
- ControlServer emitted snapshots but no command-specific result ACK; the new authenticated command test timed out waiting for `command_result`.
- Disconnected and timed-out settings commands lacked a deterministic rejection/cleanup contract.
- A synchronous exception from `launchWorker()` escaped the recovery loop instead of being reported and retried.
- Bootstrap called `realpath` before safely creating a missing legal root and did not reapply local/non-system policy to the canonical result.

### GREEN changes

- Added `command_result` frames containing the original command ID plus `success` or `error`. The server serializes `execute_command`, completes worker handling and atomic config save, then ACKs only that authenticated client.
- Added `WorkerClient.sendCommand()`. It tracks independent command IDs, resolves only matching successful ACKs, rejects worker errors, rejects all pending commands on disconnect, and removes timeout state without caching or replaying commands.
- Existing `send()` delegates to the ACK path so start/pause/stop remain compatible while IPC callers can await completion.
- For an established formal config, Electron never writes settings first. It sends `update_settings` to the online worker and mutates Electron memory only after ACK. Recording rejection, disconnection, save failure, and timeout leave Electron and disk unchanged and tell the caller to retry later.
- First bootstrap remains the sole Electron-owned config write. Runtime data-root changes are also rejected inside the worker protocol.
- Idle worker settings tests prove memory and disk converge after save; recording tests prove both remain unchanged on rejection. Node tests prove disconnected commands do not write or silently resend.
- Command ACK tests cover out-of-order concurrent IDs, error rejection, timeout cleanup, and disconnect cleanup.
- Bootstrap now lexically validates, safely creates a missing root, canonicalizes it, then revalidates canonical local/non-system policy before any config or locator write. Injected `D:`→`C:` and `D:`→UNC canonical mappings are rejected with zero file writes.
- Both synchronous launch exceptions and asynchronous child `error` events are emitted through the client/main error path while launch cooldown and long-term recovery continue.

### Verification

- Full Python worker suite: 97 passed.
- Full Node suite: 50 passed.
- Vite production build and Electron UI smoke: passed.
- Syntax and diff checks: passed.

### Remaining scope

Task 4 retains the disabled-root/redeployment UI copy and binding validation. Task 5 retains Windows-host lock validation.

## Scope convergence decision

The first production version intentionally stops short of distributed-transaction semantics for the low-probability case where the worker successfully executes and persists a settings command but its ACK is lost before Electron receives it.

In that case the product message is: **“保存结果未确认，请重新打开设置核对。”** The user can reopen settings and retry after confirming the current state. We do not add command deadlines, persistent result logs, automatic reconciliation, or replay because those mechanisms materially expand the protocol and failure-state surface beyond the core recorder lifecycle.

This is recorded as a known low-probability risk, not as a claim that disk state is unchanged after an ACK timeout. The retained core guarantees are single-instance worker startup, detached Electron/worker lifecycles, authenticated loopback control, reconnectable clients, first-run bootstrap, immutable data root, worker-owned settings persistence with command ACKs, and real disconnect-continuity coverage.
