# Task 6 Report: Core Capture Recovery Completion

## Implemented

- Audio journals now durably persist recording-time device, school, location, and start-time metadata alongside the PCM format metadata.
- Journal metadata checkpoints include `durableFrames`; recovery derives `end_time` from recording-time start/rate/frame data and never from recovery-time file timestamps.
- `QueueStore.enqueue_recovered` performs duplicate detection, segment-index allocation, and insertion in one SQLite transaction, so crash retries neither duplicate rows nor consume another index.
- Capture sessions expose a first-durable-write event through `wait_until_ready(timeout)`. The worker waits up to the injected/default three-second deadline before publishing `recording`; a silent opened stream is stopped and mapped to `microphone_unavailable`.
- Microphone open failures map to `microphone_unavailable` regardless of the backend exception type, dispose the failed candidate session, and remain retryable.
- Unexpected capture failures retain desired-recording intent and use one bounded backoff timer. Capture transitions share a lock and generation; stop, pause, and shutdown invalidate callbacks, cancel timers, and cannot return ahead of an in-flight retry start.
- Electron preferences default safely before bootstrap and, after bootstrap, live beside the non-system worker config. Before bootstrap auto-launch IPC and startup registration return a Chinese failed result without changing state or touching OS registration; `userData` contains only the secret-free config locator.
- The controlled integration harness explicitly signals its simulated durable-write readiness.
- Testing documentation identifies controlled pre-provisioned binding fixtures as technical validation only and keeps self-service QR binding as an external integration blocker.

## TDD Evidence

- RED: 5 Python lifecycle/recovery failures and 1 Node settings-path failure were observed before implementation.
- GREEN: targeted Python recovery/lifecycle tests and Node settings tests passed after the minimum implementation.
- Regression: the real Python worker/Node client integration exposed a synchronous readiness ordering race; the failing integration test drove the ordering fix.
- Remediation RED covered an in-flight retry/stop barrier, silent-stream readiness timeout, deterministic frame-derived recovery time, transactional recovery replay, and pre-bootstrap auto-launch rejection.
- Final review RED replaced the synthetic `OSError` with a generic backend startup exception; the fix now cleans up the failed candidate and preserves `microphone_unavailable` plus retry behavior for real PortAudio-style failures.

## Scope

No QR binding flow, remote policy, Windows service, or new binding mechanism was added.

## External Release Gates

- Production self-service QR binding remains blocked by the absent mini-program and binding-service repositories.
- Windows 10/11 x64 install/upgrade/uninstall, ice-point restore environment, and 72-hour soak tests remain external release gates.
