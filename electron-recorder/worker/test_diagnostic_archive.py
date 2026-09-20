import json
from datetime import datetime, timezone

from worker.diagnostic_archive import DiagnosticArchive


def test_archive_redacts_rotates_and_prunes_only_its_own_logs(tmp_path):
    now = datetime(2026, 9, 20, tzinfo=timezone.utc)
    # Exercise filesystem behavior with pytest's temp directory on any host.
    # Windows system-drive rejection is verified separately below.
    archive = DiagnosticArchive(tmp_path, max_bytes=250, now=lambda: now, platform="test")
    assert archive.write({"token": "secret-value", "message": 'accessKeySecret="hidden"', "health": "healthy"})
    folder = tmp_path / "logs" / "diagnostics"
    first = folder / "worker-2026-09-20.jsonl"
    payload = json.loads(first.read_text())
    assert payload["snapshot"]["token"] == "[REDACTED]"
    assert "hidden" not in first.read_text()
    old = folder / "worker-2026-09-01.jsonl"
    old.write_text("old")
    unrelated = folder / "user-note.txt"
    unrelated.write_text("keep")
    archive.write({"health": "healthy", "safe": "x" * 90})
    assert not old.exists()
    assert unrelated.exists()
    assert (folder / "worker-2026-09-20.previous.jsonl").exists()


def test_archive_failure_does_not_break_recording(tmp_path):
    root = tmp_path / "file"
    root.write_text("not a directory")
    archive = DiagnosticArchive(root, platform="test")
    assert archive.write({"health": "healthy"}) is False
    assert archive.status["status"] == "failed"


def test_archive_rejects_system_drive_and_empty_root():
    assert DiagnosticArchive("C:/recordings", platform="win32").write({}) is False
    assert DiagnosticArchive("", platform="win32").write({}) is False
