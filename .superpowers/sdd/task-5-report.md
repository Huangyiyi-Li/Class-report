# Task 5 Report: Isolated Upload Retry and Retention

## RED

- Added upload isolation, metadata registration, bounded retry, retention, disk-health, and worker-loop tests first.
- Initial focused run failed during collection because `worker.upload_service` and `worker.retention` did not exist.
- After the first implementation pass, focused tests exposed worker constructor wiring and queue-fixture ordering defects; both were corrected before proceeding.

## GREEN

- `UploadService.run_once(now)` claims and handles exactly one queue row.
- Upload or metadata exceptions are contained to that row, persist `last_error`, and schedule UTC epoch retries at 30/120/600/1800 seconds (capped at 1800).
- Successful rows upload, register metadata, then transition `uploading -> uploaded -> completed`.
- Queue retry attempts are persisted with an additive SQLite migration for existing databases.
- Retention queries only `completed` rows older than the cutoff and additionally confines deletion to the recordings root.
- Disk health reports `healthy`, `low` below 5 GiB free, or `unavailable` on filesystem errors.
- Recorder startup/shutdown owns a stoppable background loop; XXT dependencies are lazy-loaded only for configured devices and remain behind narrow injected interfaces.

## Tests

- Focused GREEN: `python3 -m pytest worker/test_upload_service.py worker/test_retention.py worker/test_recorder_worker.py -q` — 11 passed.
- Full verification: `python3 -m pytest worker -q` — 52 passed.
- Diff hygiene: `git diff --check` — clean.
- Tests use fake upload and metadata clients; no real network requests are made.

## Files

- Created `electron-recorder/worker/upload_service.py`
- Created `electron-recorder/worker/retention.py`
- Created `electron-recorder/worker/test_upload_service.py`
- Created `electron-recorder/worker/test_retention.py`
- Modified `electron-recorder/worker/queue_store.py`
- Modified `electron-recorder/worker/recorder_worker.py`
- Modified `electron-recorder/worker/test_recorder_worker.py`

## Self-review

- Confirmed one failed item cannot block the next pending item.
- Confirmed metadata failure remains retryable because `mark_uploaded` occurs only after metadata registration succeeds.
- Confirmed cleanup cannot delete pending, failed, uploading, or uploaded rows and cannot escape the recordings directory.
- Confirmed retry timing uses timezone-aware UTC instants and persisted epoch milliseconds.
- Confirmed no UI, packaging, QR-code work, or unrelated `windows_client` files are included.

## Attention points

- A metadata-registration failure retries the complete item, including upload. This preserves the strict state machine and avoids stranding an `uploaded` row without registered metadata; the production object key is stable for the same segment.
- Production XXT imports are intentionally lazy so unconfigured workers and tests do not require optional OSS dependencies.
