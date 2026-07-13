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
