# Task 6 Report: Core Capture Recovery Completion

## Implemented

- Audio journals now durably persist recording-time device, school, location, and start-time metadata alongside the PCM format metadata.
- Journal recovery converts PCM to WAV and idempotently inserts the recovered path into SQLite using only journal-time identity; the queue remains retryable through the existing failed/claim lifecycle.
- Capture sessions force a checkpoint on the first PCM block and notify readiness only after `fsync` returns. The worker publishes `recording` only from that readiness notification.
- Microphone open failures map to `microphone_unavailable`.
- Unexpected capture failures retain desired-recording intent and use one bounded backoff timer. Stop, pause, and shutdown cancel the timer and clear intent.
- Electron preferences default safely before bootstrap and, after bootstrap, live beside the non-system worker config. `userData` contains only the secret-free config locator.
- The controlled integration harness explicitly signals its simulated durable-write readiness.
- Testing documentation identifies controlled pre-provisioned binding fixtures as technical validation only and keeps self-service QR binding as an external integration blocker.

## TDD Evidence

- RED: 5 Python lifecycle/recovery failures and 1 Node settings-path failure were observed before implementation.
- GREEN: targeted Python recovery/lifecycle tests and Node settings tests passed after the minimum implementation.
- Regression: the real Python worker/Node client integration exposed a synchronous readiness ordering race; the failing integration test drove the ordering fix.

## Scope

No QR binding flow, remote policy, Windows service, or new binding mechanism was added.

## External Release Gates

- Production self-service QR binding remains blocked by the absent mini-program and binding-service repositories.
- Windows 10/11 x64 install/upgrade/uninstall, ice-point restore environment, and 72-hour soak tests remain external release gates.
