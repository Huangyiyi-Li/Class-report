# Mock Class Binding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add an explicitly enabled mock QR binding flow that binds a Windows recorder to either a classroom or a public studio, while preserving a clean service boundary for the future server API.

**Architecture:** The renderer owns only presentation state and calls a narrow preload API. A main-process `BindingController` talks to a `BindingService` implementation, then sends one validated `apply_binding` command to the worker; the worker remains the sole owner of durable recorder configuration and runtime activation. Mock mode must be explicitly selected with `BINDING_SERVICE_MODE=mock`; the default remote mode fails closed and never falls back to mock data.

**Tech Stack:** Electron 35, React 19, Vite 7, Node.js built-in test runner, Python 3 dataclasses/unittest, `qrcode.react`, existing worker JSON command protocol.

---

## Working rules

- Follow the approved design in `docs/plans/2026-07-15-mock-class-binding-design.md`.
- Work on `feat/windows-recorder-production`; do not tag, publish, or create a release.
- Use TDD for service state, protocol validation, worker lifecycle, and controller behavior.
- Keep mock behavior behind `BINDING_SERVICE_MODE=mock`. With the variable absent, binding is remote/unavailable until the server adapter exists.
- Never let Electron write the worker configuration file directly.
- Do not rewrite metadata already stored in queued or recorded segments during a rebind.
- Commit after each independently passing task using conventional commit messages.

### Task 1: Add the binding service contract and deterministic mock state machine

**Files:**
- Create: `electron-recorder/src/binding-service.js`
- Create: `electron-recorder/src/binding-service.test.js`
- Modify: `electron-recorder/package.json`

**Step 1: Write the failing service tests**

Cover these exact behaviors with injected `now()` and `createId()` functions:

```js
test("mock session moves from waiting to scanned and confirmed", async () => {
  const service = createBindingService({ mode: "mock", now: () => NOW, createId: () => "session-1" });
  const created = await service.createSession({ deviceNo: "AABBCCDDEEFF" });
  assert.equal(created.status, "waiting");
  assert.match(created.qrPayload, /session-1/);
  assert.equal((await service.simulateScan("session-1")).status, "scanned");
  const binding = await service.confirmBinding("session-1", {
    schoolId: 1001,
    locationType: "classroom",
    locationId: "room-101",
  });
  assert.equal(binding.classId, "class-101");
  assert.equal(binding.bindingSource, "mock");
});
```

Also test studio output (`classId` and `className` empty), expiry, unknown sessions, illegal transitions, school/location filtering, and default mode behavior. `createBindingService({})` must return a remote-unavailable adapter whose calls reject with a stable `BINDING_SERVICE_UNAVAILABLE` code; it must not return mock records.

**Step 2: Run the focused test and confirm the red state**

Run: `cd electron-recorder; node --test src/binding-service.test.js`

Expected: FAIL because `binding-service.js` does not exist.

**Step 3: Implement the minimal contract**

Export:

```js
export function createBindingService(options = {}) { /* mode router */ }
export class MockBindingService { /* in-memory sessions and catalog */ }
export class UnavailableRemoteBindingService { /* stable unavailable errors */ }
export const MOCK_BINDING_TTL_MS = 5 * 60 * 1000;
```

Implement `createSession`, `getSession`, `simulateScan`, `listSchools`, `listLocations`, and `confirmBinding`. Return copies of internal records. Produce the canonical payload fields:

```js
{
  deviceNo, schoolId, schoolName, locationType,
  locationId, locationName, classId, className,
  bindingSource: "mock", boundAt
}
```

Add `qrcode.react` as a production dependency with:

Run: `cd electron-recorder; npm install qrcode.react@^4.2.0`

**Step 4: Run the focused tests**

Run: `cd electron-recorder; node --test src/binding-service.test.js`

Expected: PASS, including the no-fallback assertion.

**Step 5: Commit**

```bash
git add electron-recorder/src/binding-service.js electron-recorder/src/binding-service.test.js electron-recorder/package.json electron-recorder/package-lock.json
git commit -m "feat(recorder): add mock binding service"
```

### Task 2: Define the worker binding schema and command protocol

**Files:**
- Modify: `electron-recorder/worker/config.py`
- Modify: `electron-recorder/worker/protocol.py`
- Modify: `electron-recorder/worker/test_config.py`
- Modify: `electron-recorder/worker/test_protocol.py`

**Step 1: Write failing schema tests**

Add tests proving that `WorkerConfig` round-trips these fields:

```python
school_name: str = ""
location_type: str = ""
class_id: str = ""
class_name: str = ""
binding_source: str = ""
bound_at: str = ""
```

Add `validate_binding_payload` tests for valid classroom and studio payloads. Reject missing identifiers, unsupported `locationType`, a classroom without class fields, a studio with class fields, malformed timestamps, unexpected keys, non-string names, and forbidden control characters. Preserve the existing startup gate requirements.

Add a protocol test:

```python
command = parse_command('{"id":"1","command":"apply_binding","payload":{}}')
self.assertEqual(command.command, "apply_binding")
```

**Step 2: Verify the tests fail**

Run: `cd electron-recorder; python -m unittest worker.test_config worker.test_protocol -v`

Expected: FAIL because the new fields, validator, and command are absent.

**Step 3: Implement validation and protocol support**

- Add the six optional binding metadata fields to `WorkerConfig`.
- Add `BINDING_KEYS` and `validate_binding_payload(payload)` that maps camelCase IPC fields to dataclass field names.
- Normalize studio class values to empty strings only after validating the submitted values.
- Add `apply_binding` to `ALLOWED_COMMANDS`.

The validator must return a dataclass-compatible patch and must not mutate its input.

**Step 4: Verify the focused suite passes**

Run: `cd electron-recorder; python -m unittest worker.test_config worker.test_protocol -v`

Expected: PASS.

**Step 5: Commit**

```bash
git add electron-recorder/worker/config.py electron-recorder/worker/protocol.py electron-recorder/worker/test_config.py electron-recorder/worker/test_protocol.py
git commit -m "feat(recorder): validate worker bindings"
```

### Task 3: Apply binding atomically and activate an initially blocked worker

**Files:**
- Modify: `electron-recorder/worker/recorder_worker.py`
- Modify: `electron-recorder/worker/test_recorder_worker.py`

**Step 1: Write failing worker lifecycle tests**

Use a temporary non-system data root and a fake upload-service factory. Test:

1. An unbound worker starts with `health == "binding_required"`.
2. `apply_binding` atomically persists the complete payload, binds storage, creates the queue store, creates/starts the upload service, sets health to `healthy`, and returns recording state to `idle`.
3. An invalid payload leaves the original config file, in-memory config, health, queue store, and upload service unchanged.
4. Applying or replacing a binding while recording is rejected.
5. Rebinding while idle replaces current upload credentials/configuration but leaves existing queued item metadata unchanged.
6. `snapshot()` exposes the full current binding without credentials.

The success assertion should include:

```python
self.assertEqual(worker.config.location_type, "classroom")
self.assertEqual(worker.snapshot()["binding"]["classId"], "class-101")
self.assertEqual(worker.snapshot()["health"], "healthy")
self.assertTrue(config_path.exists())
```

**Step 2: Verify the tests fail**

Run: `cd electron-recorder; python -m unittest worker.test_recorder_worker -v`

Expected: FAIL because `apply_binding` is unsupported and an initially blocked worker cannot activate.

**Step 3: Implement the lifecycle transition**

- Inject an `upload_service_factory` into `RecorderWorker` for deterministic tests.
- Add `_apply_binding(payload)` and dispatch it from `execute_command`.
- Build a candidate with `dataclasses.replace(self.config, **validated_patch)`.
- Evaluate the candidate startup gate before persistence.
- Prepare the candidate queue store/upload service, save the candidate atomically, then swap live references under the existing worker/upload locks.
- Stop the prior upload service only after the replacement is ready.
- Start the new upload loop once, clear the binding error, and set the recording state to `idle`.
- On any failure, clean up only newly prepared resources and keep the previous live state.
- Update `run_worker()` so startup and `apply_binding` share one activation path and cannot double-start uploads.
- Add a `binding` object to snapshots while retaining the existing `location` fields for compatibility.

**Step 4: Verify the focused suite passes**

Run: `cd electron-recorder; python -m unittest worker.test_recorder_worker -v`

Expected: PASS with no network access.

**Step 5: Run all worker tests**

Run: `cd electron-recorder; python -m unittest discover -s worker -p "test_*.py" -v`

Expected: PASS.

**Step 6: Commit**

```bash
git add electron-recorder/worker/recorder_worker.py electron-recorder/worker/test_recorder_worker.py
git commit -m "feat(recorder): activate worker after binding"
```

### Task 4: Add the main-process binding controller and narrow IPC bridge

**Files:**
- Create: `electron-recorder/src/binding-controller.js`
- Create: `electron-recorder/src/binding-controller.test.js`
- Modify: `electron-recorder/src/backend.js`
- Modify: `electron-recorder/src/backend.test.js`
- Modify: `electron-recorder/src/main.js`
- Modify: `electron-recorder/src/preload.cjs`
- Modify: `electron-recorder/package.json`

**Step 1: Write failing controller and identity tests**

Test that `resolveDeviceNo()` returns a normalized physical MAC identifier with fallback to existing network-interface derivation. Dependency-inject command execution in controller tests.

Cover:

```js
const controller = new BindingController({
  service,
  resolveDeviceNo: () => "AABBCCDDEEFF",
  getSnapshot: () => ({ recordingState: "idle" }),
  sendWorkerCommand: async (command, payload) => {
    assert.equal(command, "apply_binding");
    applied = payload;
  },
});
```

Assert session creation, scan simulation, catalog listing, confirmation followed by exactly one worker command, no confirmation while recording, and propagation of service/worker errors without mock fallback.

**Step 2: Verify focused tests fail**

Run: `cd electron-recorder; node --test src/backend.test.js src/binding-controller.test.js`

Expected: FAIL because the controller and exported resolver do not exist.

**Step 3: Implement the controller and IPC surface**

Export `resolveDeviceNo()` from `backend.js` using the existing Windows physical-MAC and network-interface logic.

Create `BindingController` with methods matching the service contract. Its `confirmBinding` must refuse non-idle snapshots, obtain the canonical record from the service, await `sendWorkerCommand("apply_binding", record)`, and return the applied binding.

In `main.js`:

- Create the service using `process.env.BINDING_SERVICE_MODE` (default `remote`).
- Instantiate the controller only after the supervisor exists, or inject a command callback that reports worker unavailability.
- Register separate IPC handlers for session creation/status, mock scan, schools, locations, and confirmation.
- Include `bindingServiceMode` and current binding in `recorder:get-snapshot`.

Expose only named methods from `preload.cjs`; do not expose raw `ipcRenderer`:

```js
createBindingSession: () => ipcRenderer.invoke("binding:create-session"),
getBindingSession: (id) => ipcRenderer.invoke("binding:get-session", id),
simulateBindingScan: (id) => ipcRenderer.invoke("binding:simulate-scan", id),
listBindingSchools: (id) => ipcRenderer.invoke("binding:list-schools", id),
listBindingLocations: (id, query) => ipcRenderer.invoke("binding:list-locations", id, query),
confirmBinding: (id, selection) => ipcRenderer.invoke("binding:confirm", id, selection),
```

Add new main-process modules to `build.files`. The existing package-resource test must continue proving that every recursive local import is packaged.

**Step 4: Verify the focused tests pass**

Run: `cd electron-recorder; node --test src/backend.test.js src/binding-controller.test.js src/package-resources.test.js`

Expected: PASS.

**Step 5: Commit**

```bash
git add electron-recorder/src/backend.js electron-recorder/src/backend.test.js electron-recorder/src/binding-controller.js electron-recorder/src/binding-controller.test.js electron-recorder/src/main.js electron-recorder/src/preload.cjs electron-recorder/package.json
git commit -m "feat(recorder): bridge binding service to worker"
```

### Task 5: Build the mock QR binding wizard

**Files:**
- Create: `electron-recorder/src/binding-flow.js`
- Create: `electron-recorder/src/binding-flow.test.js`
- Create: `electron-recorder/src/binding-wizard.jsx`
- Modify: `electron-recorder/src/renderer.jsx`
- Modify: `electron-recorder/src/styles.css`

**Step 1: Write failing pure flow tests**

Keep UI decisions testable without a browser. Test a reducer/model for:

- closed -> waiting QR session;
- waiting -> scanned after polling;
- scanned -> school -> location type -> classroom/studio location -> confirmation;
- expired -> restart;
- confirmed -> closed/current binding shown;
- rebind disabled while recording is not idle;
- classroom requires class data; studio clears class data;
- remote-unavailable error is visible and does not offer a mock action.

Example:

```js
assert.equal(canRebind({ recordingState: "recording" }), false);
assert.deepEqual(normalizeSelection({ locationType: "studio", classId: "stale" }), {
  locationType: "studio",
  classId: "",
  className: "",
});
```

**Step 2: Verify the focused test fails**

Run: `cd electron-recorder; node --test src/binding-flow.test.js`

Expected: FAIL because the flow module does not exist.

**Step 3: Implement the pure flow helpers**

Export the reducer, initial state, `canRebind`, and `normalizeSelection`. Keep network/IPC calls out of this file.

**Step 4: Verify the pure test passes**

Run: `cd electron-recorder; node --test src/binding-flow.test.js`

Expected: PASS.

**Step 5: Implement the React wizard**

`BindingWizard` must:

- render `QRCodeSVG` using `session.qrPayload`;
- poll session status while open;
- show a clearly labeled `模拟手机扫码` button only when `bindingServiceMode === "mock"`;
- show a visible `模拟数据` badge in mock mode;
- guide school, classroom/studio, and location selection after scan;
- show the proposed binding before confirmation;
- show expiry/retry and actionable errors;
- close after the worker acknowledges application;
- require confirmation before rebind;
- disable rebind whenever recording is not idle.

Replace the disabled `扫码绑定暂不可用` control in `renderer.jsx` with the current binding summary and active bind/rebind control. Keep existing recording/settings behavior unchanged.

Add responsive styles for a keyboard-accessible modal, QR panel, progress indicator, selection cards, mock badge, and error state. Preserve current design tokens and Windows minimum viewport behavior.

**Step 6: Build the renderer**

Run: `cd electron-recorder; npm run build`

Expected: Vite build succeeds with no unresolved dependency or JSX errors.

**Step 7: Commit**

```bash
git add electron-recorder/src/binding-flow.js electron-recorder/src/binding-flow.test.js electron-recorder/src/binding-wizard.jsx electron-recorder/src/renderer.jsx electron-recorder/src/styles.css
git commit -m "feat(recorder): add mock binding wizard"
```

### Task 6: Exercise the full binding path in automated smoke tests

**Files:**
- Modify: `electron-recorder/src/worker-client.integration.test.js`
- Modify: `electron-recorder/src/worker-bootstrap.test.js` if fixture configuration needs an unbound variant
- Modify: `electron-recorder/src/main.js` smoke path only as needed for deterministic assertions
- Modify: `electron-recorder/scripts/test-clean-checkout.mjs`

**Step 1: Add a failing protocol integration test**

Launch the Python control harness through the existing `WorkerClient`, send `apply_binding`, and assert matching command acknowledgement plus a snapshot containing the binding. Use a temporary config and data directory; never use the developer machine's normal recorder config.

**Step 2: Verify the integration test fails**

Run: `cd electron-recorder; node --test src/worker-client.integration.test.js`

Expected: FAIL until the harness accepts and reports the new command.

**Step 3: Extend the harness/fixture minimally**

If required, modify `electron-recorder/worker/_control_harness.py` so the existing integration path delegates `apply_binding` to the real worker behavior. Do not add a second implementation of binding validation.

**Step 4: Add smoke-mode DOM assertions**

When `ELECTRON_SMOKE_TEST=1` and `BINDING_SERVICE_MODE=mock`, make the deterministic smoke snapshot unbound. Assert that the renderer:

1. shows the bind action;
2. opens the wizard;
3. renders QR content and the mock badge/action;
4. reaches the scanned selection step after simulated scan.

Keep normal smoke mode and production runtime unchanged.

**Step 5: Run integration and repository tests**

Run: `cd electron-recorder; node --test src/worker-client.integration.test.js`

Expected: PASS.

Run: `cd electron-recorder; npm test`

Expected: all Node tests, worker tests invoked by repository verification, and clean-checkout checks PASS.

**Step 6: Commit**

```bash
git add electron-recorder/src/worker-client.integration.test.js electron-recorder/src/worker-bootstrap.test.js electron-recorder/src/main.js electron-recorder/scripts/test-clean-checkout.mjs electron-recorder/worker/_control_harness.py
git commit -m "test(recorder): cover mock binding workflow"
```

Only add files that actually changed.

### Task 7: Document, package, and verify the internal mock build

**Files:**
- Modify: `electron-recorder/docs/TESTING.md`
- Modify: `docs/windows-recorder/HANDOFF.md`
- Modify: `docs/windows-recorder/RELEASE.md`
- Modify: `docs/windows-recorder/verification-matrix.md` if present
- Create: `docs/windows-recorder/evidence/WIN-REC-BINDING-MOCK-2026-07-15.md`

**Step 1: Document operation and safety boundaries**

Document:

- `BINDING_SERVICE_MODE=mock` enables internal mock mode;
- absence of that variable selects remote/unavailable mode;
- production never falls back to mock;
- both classroom and studio payloads;
- idle-only rebind rule;
- how the future HTTP adapter replaces the mock service without changing renderer/worker contracts;
- mock builds are not release candidates and must not be published.

**Step 2: Run the complete verification matrix**

Run:

```powershell
cd electron-recorder
npm test
python -m unittest discover -s worker -p "test_*.py" -v
npm run build
npm run build:worker
$env:BINDING_SERVICE_MODE='mock'
$env:ELECTRON_SMOKE_TEST='1'
npx electron .
Remove-Item Env:BINDING_SERVICE_MODE
Remove-Item Env:ELECTRON_SMOKE_TEST
npm run pack:win
```

Expected:

- all Node and Python tests pass;
- renderer and worker builds succeed;
- Electron smoke exits successfully after verifying the mock binding steps;
- unpacked Windows package is created without publishing.

**Step 3: Verify the packaged app resources and normal launch**

Run the existing package resource and normal-start scripts against the new unpacked build:

```powershell
cd electron-recorder
node --test src/package-resources.test.js
powershell -ExecutionPolicy Bypass -File scripts/test-packaged-normal-start.ps1
```

Expected: packaged startup reaches the binding-required UI without a module error, and the worker process starts.

**Step 4: Manually verify the full mock workflow in the newly packaged app**

Launch the unpacked executable with `BINDING_SERVICE_MODE=mock` and a fresh temporary user-data/config directory. Record evidence for:

1. initial `binding_required` state;
2. QR wizard opens and shows the mock badge;
3. simulated scan reaches school/type/location selection;
4. classroom binding is acknowledged and worker becomes healthy;
5. microphone recording starts, produces a non-empty audio segment, and stops cleanly;
6. queued upload reaches the expected retry/error state without claiming a successful real server upload;
7. idle rebind to a studio succeeds and old queue metadata remains unchanged;
8. rebind is disabled while recording.

Store commands, timestamps, config excerpts with secrets removed, log paths, segment hashes/sizes, and screenshots in the evidence document. Do not claim server upload success: this task verifies mock binding and the existing upload attempt boundary only.

**Step 5: Review the diff and commit documentation**

Run: `git diff --check`

Expected: no whitespace errors.

```bash
git add electron-recorder/docs/TESTING.md docs/windows-recorder/HANDOFF.md docs/windows-recorder/RELEASE.md docs/windows-recorder/verification-matrix.md docs/windows-recorder/evidence/WIN-REC-BINDING-MOCK-2026-07-15.md
git commit -m "docs(recorder): verify mock binding workflow"
```

Only add documentation files that exist or were intentionally created.

**Step 6: Push the feature branch after all checks pass**

Run: `git status --short; git log --oneline --decorate -10`

Expected: clean worktree and the planned commits on `feat/windows-recorder-production`.

Run: `git push origin feat/windows-recorder-production`

Expected: branch push succeeds. Do not create a tag, GitHub release, or published installer.

## Acceptance criteria

- A fresh unbound packaged client can complete the mock QR flow and activate the worker without restarting the app.
- Both classroom and studio binding payloads persist atomically and appear in snapshots.
- The UI always labels mock data and never exposes mock actions in default remote mode.
- Rebinding is idle-only and does not mutate previously queued/recorded metadata.
- A newly built Windows package starts normally, starts its worker, and records a non-empty microphone segment after binding.
- Tests cover service transitions, no-fallback behavior, worker validation/lifecycle, controller IPC, UI flow helpers, and control-protocol integration.
- Documentation clearly distinguishes verified mock flow/upload attempts from unverified real server upload success.
- No version, tag, release, or installer is published as part of this work.
