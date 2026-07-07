# Windows Recorder Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Windows 10/11 recorder that keeps audio on a non-system drive, survives UI restarts, restores unfinished audio after interruption, and uploads through an isolated persistent queue.

**Architecture:** Keep Electron for the desktop shell and move capture, durable audio journaling, SQLite queueing, and upload work into a PyInstaller-packaged Python worker. Electron supervises the worker over newline-delimited JSON on stdio and renders three independent state dimensions: recording, upload, and device health.

**Tech Stack:** Electron 35, React 19, Node.js, Python 3.11+, sounddevice, NumPy, stdlib sqlite3, PyInstaller, Node test runner, pytest.

## Global Constraints

- Support Windows 10/11 x64 only; record Windows 7 as an unsupported risk.
- Install the application and persist configuration, audio, queue, and logs on a non-system drive.
- Keep `contextIsolation: true` and `nodeIntegration: false`.
- Record 16 kHz, mono, 16-bit audio; create one upload segment every 5 minutes.
- Flush raw PCM to disk at least every 10 seconds; maximum unflushed loss is 10 seconds.
- Prefer Ogg Opus; fall back to WAV when encoding fails.
- Do not include test school IDs, class IDs, device IDs, accounts, passwords, or mirror endpoints in production defaults.
- Network failure must not stop recording.
- A failed queue item must not block later items.
- Completed audio is retained for 7 days; pending and failed audio is never automatically deleted.
- Stop implementation after this client-core plan. QR binding and location APIs are a separate plan because the mini-program repository is not present in this workspace.

## File Structure

### Python worker

- `electron-recorder/worker/recorder_worker.py`: stdin/stdout JSON command loop and worker lifecycle.
- `electron-recorder/worker/config.py`: production-safe configuration and non-system-drive validation.
- `electron-recorder/worker/audio_journal.py`: crash-safe raw PCM journal and segment finalization.
- `electron-recorder/worker/queue_store.py`: SQLite schema and queue transitions.
- `electron-recorder/worker/upload_service.py`: existing XXT authentication/upload adapter and isolated retry loop.
- `electron-recorder/worker/retention.py`: completed-file retention and disk threshold checks.
- `electron-recorder/worker/protocol.py`: command/event names and validation.

### Electron shell

- `electron-recorder/src/worker-supervisor.js`: spawn, monitor, restart, and command the packaged worker.
- `electron-recorder/src/runtime-state.js`: combine recording, upload, and health state.
- `electron-recorder/src/main.js`: wire supervisor events to IPC, tray, and power blocking.
- `electron-recorder/src/preload.cjs`: expose the narrow renderer API.
- `electron-recorder/src/renderer.jsx`: remove Web Audio capture and render worker state.
- `electron-recorder/src/state.js`: presentation metadata for the three state dimensions.

### Packaging and documents

- `electron-recorder/scripts/build-worker.py`: build `ClassroomRecorderWorker.exe` with PyInstaller.
- `electron-recorder/scripts/build-windows-release.mjs`: include the worker executable in Electron resources.
- `electron-recorder/docs/TESTING.md`: automated and Windows failure-test commands.
- `electron-recorder/WINDOWS_TEST_README.md`: installation, non-system-drive, and ice-point notes.

---

### Task 1: Production-Safe Configuration and Data Root

**Files:**
- Create: `electron-recorder/worker/__init__.py`
- Create: `electron-recorder/worker/config.py`
- Create: `electron-recorder/worker/test_config.py`
- Modify: `electron-recorder/src/backend.js`

**Interfaces:**
- Produces: `WorkerConfig.load(path: Path) -> WorkerConfig`
- Produces: `validate_data_root(path: Path, system_drive: str) -> None`
- Consumes later: the worker receives `dataRoot`, `segmentSeconds`, `autoRecordEnabled`, and upload endpoint settings from this config.

- [ ] **Step 1: Write failing configuration tests**

```python
from pathlib import Path, PureWindowsPath

import pytest

from worker.config import WorkerConfig, validate_data_root


def test_defaults_contain_no_school_or_credentials(tmp_path: Path):
    config = WorkerConfig.load(tmp_path / "missing.json")
    assert config.school_id is None
    assert config.location_id == ""
    assert config.username == ""
    assert config.password == ""
    assert config.mirror_server_url == ""


def test_rejects_system_drive_data_root(tmp_path: Path):
    with pytest.raises(ValueError, match="非系统盘"):
        validate_data_root(Path("C:/ClassroomRecorderData"), "C:")


def test_accepts_non_system_drive_data_root():
    validate_data_root(Path("D:/ClassroomRecorderData"), "C:")
```

- [ ] **Step 2: Run the focused tests and confirm failure**

Run: `cd electron-recorder && python3 -m pytest worker/test_config.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'worker.config'`.

- [ ] **Step 3: Implement production-safe configuration**

```python
# electron-recorder/worker/config.py
from __future__ import annotations

import json
from dataclasses import dataclass, fields
from pathlib import Path, PureWindowsPath


@dataclass(frozen=True)
class WorkerConfig:
    data_root: str = ""
    base_url: str = "https://rest.xxt.cn"
    device_no: str = ""
    school_id: int | None = None
    location_id: str = ""
    segment_seconds: int = 300
    checkpoint_seconds: int = 10
    auto_record_enabled: bool = False
    username: str = ""
    password: str = ""
    mirror_server_url: str = ""

    @classmethod
    def load(cls, path: Path) -> "WorkerConfig":
        if not path.exists():
            return cls()
        payload = json.loads(path.read_text(encoding="utf-8"))
        allowed = {field.name for field in fields(cls)}
        return cls(**{key: value for key, value in payload.items() if key in allowed})


def validate_data_root(path: Path, system_drive: str) -> None:
    drive = PureWindowsPath(str(path)).drive.upper().rstrip("\\/")
    protected = system_drive.upper().rstrip("\\/")
    if not drive or drive == protected:
        raise ValueError("录音数据必须保存到非系统盘")
```

- [ ] **Step 4: Remove unsafe Electron defaults**

In `electron-recorder/src/backend.js`, replace the current test-specific `DEFAULT_CONFIG` with:

```js
const DEFAULT_CONFIG = {
  baseUrl: "https://rest.xxt.cn",
  environmentName: "生产环境",
  deviceNo: "",
  schoolId: null,
  locationId: "",
  locationName: "",
  segmentSeconds: 300,
  checkpointSeconds: 10,
  autoLaunchEnabled: false,
  autoRecordEnabled: false,
  inputDevice: "",
};
```

Delete the mirror account, mirror password, test school, test class, and fixed device number from production defaults.

- [ ] **Step 5: Run tests and secret scan**

Run: `cd electron-recorder && python3 -m pytest worker/test_config.py -q && rg -n "client123|20260529|3041|1083678|192\.168\.6\.152" src worker`

Expected: pytest PASS; `rg` returns no matches.

- [ ] **Step 6: Commit**

```bash
git add electron-recorder/worker electron-recorder/src/backend.js
git commit -m "refactor(recorder): add production-safe worker config"
```

---

### Task 2: Worker Protocol and Electron Supervisor

**Files:**
- Create: `electron-recorder/worker/protocol.py`
- Create: `electron-recorder/worker/recorder_worker.py`
- Create: `electron-recorder/worker/test_protocol.py`
- Create: `electron-recorder/src/worker-supervisor.js`
- Create: `electron-recorder/src/worker-supervisor.test.js`

**Interfaces:**
- Commands: `start`, `pause`, `stop`, `snapshot`, `shutdown`.
- Events: `ready`, `snapshot`, `level`, `segment_completed`, `error`.
- Produces: `WorkerSupervisor.start()`, `.send(command, payload)`, `.stop()` and events `snapshot`, `exit`, `error`.

- [ ] **Step 1: Write failing Python protocol tests**

```python
import pytest

from worker.protocol import parse_command


def test_parse_start_command():
    assert parse_command('{"id":"1","command":"start","payload":{}}').command == "start"


def test_reject_unknown_command():
    with pytest.raises(ValueError, match="unsupported command"):
        parse_command('{"id":"1","command":"format_disk","payload":{}}')
```

- [ ] **Step 2: Run and confirm failure**

Run: `cd electron-recorder && python3 -m pytest worker/test_protocol.py -q`

Expected: FAIL because `worker.protocol` does not exist.

- [ ] **Step 3: Implement the protocol**

```python
# electron-recorder/worker/protocol.py
from __future__ import annotations

import json
from dataclasses import dataclass

ALLOWED_COMMANDS = {"start", "pause", "stop", "snapshot", "shutdown"}


@dataclass(frozen=True)
class Command:
    id: str
    command: str
    payload: dict


def parse_command(line: str) -> Command:
    data = json.loads(line)
    command = str(data.get("command", ""))
    if command not in ALLOWED_COMMANDS:
        raise ValueError(f"unsupported command: {command}")
    return Command(id=str(data.get("id", "")), command=command, payload=dict(data.get("payload") or {}))


def event(name: str, payload: dict) -> str:
    return json.dumps({"event": name, "payload": payload}, ensure_ascii=False)
```

- [ ] **Step 4: Implement the minimal worker command loop**

```python
# electron-recorder/worker/recorder_worker.py
from __future__ import annotations

import sys

from worker.protocol import event, parse_command


def emit(name: str, payload: dict) -> None:
    print(event(name, payload), flush=True)


def main() -> int:
    state = {"recording": "idle", "upload": "clear", "health": "healthy"}
    emit("ready", state)
    for line in sys.stdin:
        try:
            command = parse_command(line)
            if command.command == "shutdown":
                emit("snapshot", state)
                return 0
            if command.command == "start":
                state["recording"] = "recording"
            elif command.command == "pause":
                state["recording"] = "paused"
            elif command.command == "stop":
                state["recording"] = "idle"
            emit("snapshot", state)
        except Exception as exc:
            emit("error", {"message": str(exc)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Write the failing Node supervisor test**

```js
// electron-recorder/src/worker-supervisor.test.js
import assert from "node:assert/strict";
import crypto from "node:crypto";
import { EventEmitter } from "node:events";
import test from "node:test";
import { WorkerSupervisor } from "./worker-supervisor.js";

test("parses worker snapshot events", () => {
  const child = new EventEmitter();
  child.stdout = new EventEmitter();
  child.stdin = { write() {} };
  const supervisor = new WorkerSupervisor({ spawnWorker: () => child, restartDelayMs: 1 });
  let snapshot;
  supervisor.on("snapshot", (value) => { snapshot = value; });
  supervisor.start();
  child.stdout.emit("data", Buffer.from('{"event":"snapshot","payload":{"recording":"recording"}}\n'));
  assert.equal(snapshot.recording, "recording");
});
```

- [ ] **Step 6: Implement `WorkerSupervisor`**

```js
// electron-recorder/src/worker-supervisor.js
import { EventEmitter } from "node:events";

export class WorkerSupervisor extends EventEmitter {
  constructor({ spawnWorker, restartDelayMs = 3000 }) {
    super();
    this.spawnWorker = spawnWorker;
    this.restartDelayMs = restartDelayMs;
    this.buffer = "";
    this.stopping = false;
  }

  start() {
    this.child = this.spawnWorker();
    this.child.stdout.on("data", (chunk) => this.consume(chunk.toString("utf8")));
    this.child.on("exit", (code) => {
      this.emit("exit", code);
      if (!this.stopping) setTimeout(() => this.start(), this.restartDelayMs);
    });
  }

  consume(text) {
    this.buffer += text;
    const lines = this.buffer.split("\n");
    this.buffer = lines.pop() || "";
    for (const line of lines.filter(Boolean)) {
      const message = JSON.parse(line);
      this.emit(message.event, message.payload);
    }
  }

  send(command, payload = {}) {
    this.child.stdin.write(`${JSON.stringify({ id: crypto.randomUUID(), command, payload })}\n`);
  }

  stop() {
    this.stopping = true;
    this.send("shutdown");
  }
}
```

- [ ] **Step 7: Run both test suites and commit**

Run: `cd electron-recorder && python3 -m pytest worker/test_protocol.py -q && npm test`

Expected: all Python and Node tests PASS.

```bash
git add electron-recorder/worker electron-recorder/src/worker-supervisor.js electron-recorder/src/worker-supervisor.test.js
git commit -m "feat(recorder): add supervised worker protocol"
```

---

### Task 3: Crash-Safe Audio Journal and Recovery

**Files:**
- Create: `electron-recorder/worker/audio_journal.py`
- Create: `electron-recorder/worker/test_audio_journal.py`
- Modify: `electron-recorder/worker/recorder_worker.py`

**Interfaces:**
- Produces: `AudioJournal.append(pcm: bytes)`, `.checkpoint()`, `.finalize(end_time) -> Path`.
- Produces: `recover_journals(recordings_dir: Path) -> list[Path]`.
- Consumes later: queue storage enqueues each finalized WAV or Ogg path.

- [ ] **Step 1: Write failing recovery tests**

```python
from datetime import datetime, timezone
from pathlib import Path

from worker.audio_journal import AudioJournal, recover_journals


def test_checkpoint_persists_pcm_before_finalize(tmp_path: Path):
    journal = AudioJournal(tmp_path, "device-1", datetime.now(timezone.utc), 16000, 1, 2)
    journal.append(b"\x00\x01" * 16000)
    journal.checkpoint()
    assert journal.part_path.stat().st_size == 32000


def test_recovers_unfinished_part_as_wav(tmp_path: Path):
    journal = AudioJournal(tmp_path, "device-1", datetime.now(timezone.utc), 16000, 1, 2)
    journal.append(b"\x00\x01" * 1600)
    journal.checkpoint()
    recovered = recover_journals(tmp_path)
    assert len(recovered) == 1
    assert recovered[0].suffix == ".wav"
    assert recovered[0].exists()
```

- [ ] **Step 2: Run and confirm failure**

Run: `cd electron-recorder && python3 -m pytest worker/test_audio_journal.py -q`

Expected: FAIL because `worker.audio_journal` does not exist.

- [ ] **Step 3: Implement journal checkpointing and WAV finalization**

```python
# electron-recorder/worker/audio_journal.py
from __future__ import annotations

import json
import os
import wave
from datetime import datetime
from pathlib import Path


class AudioJournal:
    def __init__(self, root: Path, device_id: str, started_at: datetime, rate: int, channels: int, sample_width: int):
        root.mkdir(parents=True, exist_ok=True)
        stem = f"{device_id}_{started_at.strftime('%Y%m%d_%H%M%S_%f')}"
        self.part_path = root / f"{stem}.pcm.part"
        self.meta_path = root / f"{stem}.json"
        self.wav_path = root / f"{stem}.wav"
        self.rate = rate
        self.channels = channels
        self.sample_width = sample_width
        self.file = self.part_path.open("ab", buffering=0)
        self.meta_path.write_text(json.dumps({"rate": rate, "channels": channels, "sampleWidth": sample_width}), encoding="utf-8")

    def append(self, pcm: bytes) -> None:
        self.file.write(pcm)

    def checkpoint(self) -> None:
        self.file.flush()
        os.fsync(self.file.fileno())

    def finalize(self, end_time: datetime | None = None) -> Path:
        self.checkpoint()
        self.file.close()
        _pcm_to_wav(self.part_path, self.wav_path, self.rate, self.channels, self.sample_width)
        self.part_path.unlink(missing_ok=True)
        self.meta_path.unlink(missing_ok=True)
        return self.wav_path


def _pcm_to_wav(part: Path, target: Path, rate: int, channels: int, sample_width: int) -> None:
    with wave.open(str(target), "wb") as output:
        output.setframerate(rate)
        output.setnchannels(channels)
        output.setsampwidth(sample_width)
        output.writeframes(part.read_bytes())


def recover_journals(root: Path) -> list[Path]:
    recovered = []
    for part in root.glob("*.pcm.part"):
        meta = json.loads(part.with_suffix("").with_suffix(".json").read_text(encoding="utf-8"))
        target = part.with_suffix("").with_suffix(".wav")
        _pcm_to_wav(part, target, meta["rate"], meta["channels"], meta["sampleWidth"])
        part.unlink(missing_ok=True)
        part.with_suffix("").with_suffix(".json").unlink(missing_ok=True)
        recovered.append(target)
    return recovered
```

- [ ] **Step 4: Connect `sounddevice.InputStream` to the journal**

In `recorder_worker.py`, add a `CaptureSession` whose callback puts PCM bytes on a queue. A writer thread must call `journal.append()` continuously and `journal.checkpoint()` whenever 10 seconds have elapsed; the sounddevice callback must never perform disk or network work.

```python
def audio_callback(indata, frames, callback_time, status):
    pcm_queue.put_nowait(indata.copy().tobytes())


def writer_loop():
    last_checkpoint = time.monotonic()
    while not stop_event.is_set() or not pcm_queue.empty():
        journal.append(pcm_queue.get(timeout=0.2))
        if time.monotonic() - last_checkpoint >= config.checkpoint_seconds:
            journal.checkpoint()
            last_checkpoint = time.monotonic()
```

- [ ] **Step 5: Run recovery tests and commit**

Run: `cd electron-recorder && python3 -m pytest worker/test_audio_journal.py -q`

Expected: PASS.

```bash
git add electron-recorder/worker/audio_journal.py electron-recorder/worker/test_audio_journal.py electron-recorder/worker/recorder_worker.py
git commit -m "feat(recorder): persist crash-safe audio journals"
```

---

### Task 4: SQLite Queue, Failure Isolation, and Migration

**Files:**
- Create: `electron-recorder/worker/queue_store.py`
- Create: `electron-recorder/worker/test_queue_store.py`
- Modify: `electron-recorder/worker/recorder_worker.py`

**Interfaces:**
- Produces: `QueueStore.enqueue(segment) -> int`, `.claim_next(now) -> QueueItem | None`, `.mark_uploaded(id, url)`, `.mark_completed(id)`, `.mark_failed(id, error, retry_at)`.
- Produces: `QueueStore.counts() -> dict[str, int]`.

- [ ] **Step 1: Write failing queue tests**

```python
from pathlib import Path

from worker.queue_store import QueueStore


def test_failed_item_does_not_block_next_item(tmp_path: Path):
    store = QueueStore(tmp_path / "queue.db")
    first = store.enqueue({"local_path": "one.wav", "segment_index": 1})
    second = store.enqueue({"local_path": "two.wav", "segment_index": 2})
    store.mark_failed(first, "offline", "2099-01-01T00:00:00Z")
    assert store.claim_next("2026-07-07T00:00:00Z").id == second


def test_completed_item_is_not_claimed_again(tmp_path: Path):
    store = QueueStore(tmp_path / "queue.db")
    item_id = store.enqueue({"local_path": "one.wav", "segment_index": 1})
    store.mark_uploaded(item_id, "https://example.test/one.wav")
    store.mark_completed(item_id)
    assert store.claim_next("2026-07-07T00:00:00Z") is None
```

- [ ] **Step 2: Run and confirm failure**

Run: `cd electron-recorder && python3 -m pytest worker/test_queue_store.py -q`

Expected: FAIL because `worker.queue_store` does not exist.

- [ ] **Step 3: Implement the queue schema and transitions**

Use stdlib `sqlite3`, enable `PRAGMA journal_mode=WAL`, and create this schema:

```sql
CREATE TABLE IF NOT EXISTS segments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  local_path TEXT NOT NULL UNIQUE,
  segment_index INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  uploaded_url TEXT NOT NULL DEFAULT '',
  last_error TEXT NOT NULL DEFAULT '',
  retry_at TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  completed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_segments_claim ON segments(status, retry_at, id);
```

`claim_next(now)` must select the oldest row whose status is `pending`, or `failed` with `retry_at <= now`. It must not select `uploading`, `uploaded`, or `completed` rows.

- [ ] **Step 4: Add one-time JSON queue migration**

Implement `migrate_json_queue(json_path, store)` so existing `queue.json` items are inserted once using `local_path` uniqueness, then rename the source to `queue.json.migrated`. Add a test that runs migration twice and asserts one database row.

- [ ] **Step 5: Run tests and commit**

Run: `cd electron-recorder && python3 -m pytest worker/test_queue_store.py -q`

Expected: PASS.

```bash
git add electron-recorder/worker/queue_store.py electron-recorder/worker/test_queue_store.py electron-recorder/worker/recorder_worker.py
git commit -m "feat(recorder): replace JSON queue with SQLite"
```

---

### Task 5: Isolated Upload Retry and Retention

**Files:**
- Create: `electron-recorder/worker/upload_service.py`
- Create: `electron-recorder/worker/retention.py`
- Create: `electron-recorder/worker/test_upload_service.py`
- Create: `electron-recorder/worker/test_retention.py`
- Modify: `electron-recorder/worker/recorder_worker.py`

**Interfaces:**
- Consumes: `QueueStore`, existing `windows_client.xxt_upload.XxtUploadManager` and `XxtDeviceApiClient`.
- Produces: `UploadService.run_once(now) -> UploadResult | None`.
- Produces: `cleanup_completed(recordings_dir, store, now, retention_days=7) -> list[Path]`.

- [ ] **Step 1: Write upload isolation tests**

```python
def test_upload_failure_marks_one_item_and_continues(tmp_path):
    store = seeded_store(tmp_path, ["one.wav", "two.wav"])
    uploader = FakeUploader(fail_paths={"one.wav"})
    service = UploadService(store, uploader, FakeMetadataClient())
    service.run_once("2026-07-07T00:00:00Z")
    service.run_once("2026-07-07T00:00:01Z")
    assert store.counts()["failed"] == 1
    assert store.counts()["completed"] == 1
```

- [ ] **Step 2: Write retention tests**

```python
def test_cleanup_deletes_only_completed_files_older_than_seven_days(tmp_path):
    completed = create_segment(tmp_path, "completed.wav", age_days=8, status="completed")
    pending = create_segment(tmp_path, "pending.wav", age_days=30, status="pending")
    deleted = cleanup_completed(tmp_path, completed.store, NOW, retention_days=7)
    assert completed.path in deleted
    assert pending.path.exists()
```

- [ ] **Step 3: Run tests and confirm failure**

Run: `cd electron-recorder && python3 -m pytest worker/test_upload_service.py worker/test_retention.py -q`

Expected: FAIL because upload and retention modules do not exist.

- [ ] **Step 4: Implement bounded retry**

Use retry delays `[30, 120, 600, 1800]` seconds, capped at 1800 seconds. `run_once()` handles one row only, catches its exception, records `last_error` and `retry_at`, then returns. The background loop calls it again so another eligible row can proceed.

```python
RETRY_SECONDS = (30, 120, 600, 1800)

def retry_delay(attempts: int) -> int:
    return RETRY_SECONDS[min(max(attempts, 0), len(RETRY_SECONDS) - 1)]
```

- [ ] **Step 5: Implement safe retention and 5 GB health check**

`cleanup_completed()` must query only `completed` rows older than seven days. `disk_health(path)` returns `healthy`, `low`, or `unavailable`; `low` means free space below `5 * 1024**3` bytes. Never delete pending, failed, uploading, or uploaded rows.

- [ ] **Step 6: Run tests and commit**

Run: `cd electron-recorder && python3 -m pytest worker -q`

Expected: all worker tests PASS.

```bash
git add electron-recorder/worker
git commit -m "feat(recorder): isolate uploads and enforce safe retention"
```

---

### Task 6: Three-Dimension Runtime State and Settings

**Files:**
- Create: `electron-recorder/src/runtime-state.js`
- Create: `electron-recorder/src/runtime-state.test.js`
- Modify: `electron-recorder/src/main.js`
- Modify: `electron-recorder/src/preload.cjs`
- Modify: `electron-recorder/src/state.js`
- Modify: `electron-recorder/src/renderer.jsx`
- Modify: `electron-recorder/src/styles.css`

**Interfaces:**
- Produces: `createRuntimeState(snapshot) -> { recording, upload, health, pending, location, safe }`.
- Renderer commands become `startRecording`, `pauseRecording`, `stopRecording`, `flushQueue`, and `updateSettings` over supervisor IPC.

- [ ] **Step 1: Write failing runtime-state tests**

```js
import assert from "node:assert/strict";
import test from "node:test";
import { createRuntimeState } from "./runtime-state.js";

test("offline upload does not replace recording state", () => {
  const state = createRuntimeState({ recording: "recording", upload: "waiting_network", health: "healthy", pending: 12 });
  assert.equal(state.recording, "recording");
  assert.equal(state.upload, "waiting_network");
  assert.equal(state.pending, 12);
});

test("unsafe storage prevents recording label", () => {
  const state = createRuntimeState({ recording: "recording", upload: "clear", health: "storage_unavailable" });
  assert.equal(state.recording, "recording_error");
  assert.equal(state.safe, false);
});
```

- [ ] **Step 2: Run and confirm failure**

Run: `cd electron-recorder && npm test`

Expected: FAIL because `runtime-state.js` does not exist.

- [ ] **Step 3: Implement state normalization**

```js
// electron-recorder/src/runtime-state.js
const UNSAFE_HEALTH = new Set(["storage_unavailable", "disk_low", "microphone_unavailable", "binding_required"]);

export function createRuntimeState(snapshot = {}) {
  const health = snapshot.health || "healthy";
  const safe = !UNSAFE_HEALTH.has(health);
  return {
    recording: safe ? (snapshot.recording || "idle") : "recording_error",
    upload: snapshot.upload || "clear",
    health,
    pending: Number(snapshot.pending || 0),
    location: snapshot.location || null,
    safe,
  };
}
```

- [ ] **Step 4: Replace renderer-side recording**

Delete `getUserMedia`, `AudioContext`, `ScriptProcessor`, chunk buffering, and Opus encoding from `renderer.jsx`. The renderer calls `shell.startRecording()` and renders supervisor snapshots only. Keep microphone selection in settings; send the selected device ID to `updateSettings`.

- [ ] **Step 5: Wire supervisor into the Electron main process**

In `main.js`, spawn the development worker with `python -m worker.recorder_worker` and the packaged worker from `process.resourcesPath/worker/ClassroomRecorderWorker.exe`. Forward supervisor `snapshot` events to both windows. Start `powerSaveBlocker` only when `snapshot.recording === "recording"`.

- [ ] **Step 6: Update the four required UI surfaces**

Render:

- main status: recording, upload with pending count, and device health;
- settings: auto launch, auto record, microphone, data root, location, version;
- diagnostics: queue counts, free disk, latest error, open folder, export diagnostics;
- first-run gate: show `binding_required` as an explicitly unavailable action until the separate binding plan supplies an activation session.

The blocked state must say `设备尚未绑定，扫码绑定功能将在设备绑定服务接入后启用` and must not render a fake QR code.

- [ ] **Step 7: Run UI tests, build, and smoke test**

Run: `cd electron-recorder && npm test && npm run build && npm run electron:smoke`

Expected: all tests PASS; Vite builds; Electron smoke reports `passed: true`.

- [ ] **Step 8: Commit**

```bash
git add electron-recorder/src
git commit -m "feat(recorder): render worker-backed runtime state"
```

---

### Task 7: Package the Worker and Write the Minimum Delivery Docs

**Files:**
- Create: `electron-recorder/scripts/build-worker.py`
- Modify: `electron-recorder/package.json`
- Modify: `electron-recorder/scripts/build-windows-release.mjs`
- Create: `electron-recorder/docs/TESTING.md`
- Modify: `electron-recorder/WINDOWS_TEST_README.md`

**Interfaces:**
- Produces: `electron-recorder/build/worker/ClassroomRecorderWorker.exe`.
- Electron builder copies the worker to `resources/worker/ClassroomRecorderWorker.exe`.

- [ ] **Step 1: Add the PyInstaller build script**

```python
# electron-recorder/scripts/build-worker.py
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "build" / "worker"

subprocess.run([
    sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile",
    "--name", "ClassroomRecorderWorker", "--distpath", str(DIST),
    "--paths", str(ROOT.parent), str(ROOT / "worker" / "recorder_worker.py"),
    "--hidden-import", "sounddevice", "--hidden-import", "numpy",
], cwd=ROOT, check=True)
```

- [ ] **Step 2: Add packaging scripts and resources**

Add to `package.json`:

```json
{
  "scripts": {
    "build:worker": "python scripts/build-worker.py",
    "dist:win": "npm run build:worker && node scripts/build-windows-release.mjs"
  },
  "build": {
    "extraResources": [
      { "from": "build", "to": "build", "filter": ["icon.ico", "icon.png"] },
      { "from": "build/worker", "to": "worker", "filter": ["ClassroomRecorderWorker.exe"] }
    ]
  }
}
```

- [ ] **Step 3: Write the automated and Windows test checklist**

`electron-recorder/docs/TESTING.md` must contain exact commands for `pytest`, `npm test`, `npm run build`, and `npm run electron:smoke`, plus a Windows checklist for:

- install to `D:` or another non-system drive;
- verify data stays off `C:`;
- integrated and USB microphone;
- UI crash while recording;
- worker kill and restart;
- network disconnect and recovery;
- forced power-off recovery;
- less than 5 GB disk space;
- 100%, 125%, and 150% scaling;
- 72-hour recording.

- [ ] **Step 4: Rewrite the Windows README to match the real product**

Remove the obsolete claim that Electron is UI-only. State Windows 10/11 x64 support, Windows 7 non-support, non-system-drive requirement, ice-point risk, install/upgrade/uninstall behavior, and the location of data and diagnostics.

- [ ] **Step 5: Build and verify on the development machine**

Run: `cd electron-recorder && python3 -m pytest worker -q && npm test && npm run build && npm run electron:smoke`

Expected: all worker and Node tests PASS; renderer build succeeds; smoke test reports `passed: true`.

Run on Windows: `npm run dist:win`

Expected: signed-test or unsigned controlled-test installer contains `resources/worker/ClassroomRecorderWorker.exe` and launches without requiring Python.

- [ ] **Step 6: Commit**

```bash
git add electron-recorder/scripts electron-recorder/package.json electron-recorder/docs electron-recorder/WINDOWS_TEST_README.md
git commit -m "build(recorder): package worker and document Windows validation"
```

---

## Client-Core Exit Criteria

This plan is complete only when:

1. Electron UI capture code has been removed.
2. The Python worker records and checkpoints audio on a non-system drive.
3. Killing and restarting the Electron UI does not stop the worker.
4. Unfinished PCM journals recover into valid WAV files.
5. SQLite queue migration and failed-item isolation pass automated tests.
6. Network failure does not change the recording state.
7. Production defaults contain no test identifiers or credentials.
8. The packaged Windows installer includes the worker executable.
9. Automated tests, build, and Electron smoke test pass.
10. The Windows test guide is accurate and ready for true Win10/11 and ice-point validation.

## Deferred Second Plan: Self-Service Binding

The next implementation plan will cover activation sessions, QR polling, multi-school selection, classroom/recording-room matching and creation, binding history, migration, and the final first-run UI. It requires the mini-program repository or its owning team to confirm the route, login API, and release process; those artifacts are not present in this workspace, so this plan intentionally does not invent file paths or a fake QR implementation.
