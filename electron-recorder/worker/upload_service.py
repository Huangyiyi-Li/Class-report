from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from worker.queue_store import QueueStore


RETRY_SECONDS = (30, 120, 600, 1800)


def retry_delay(attempts: int) -> int:
    return RETRY_SECONDS[min(max(attempts, 0), len(RETRY_SECONDS) - 1)]


@dataclass(frozen=True)
class UploadResult:
    item_id: int
    status: str
    retry_at: int | None = None
    error: str = ""


class UploadService:
    def __init__(self, store: QueueStore, uploader, metadata_client):
        self.store = store
        self.uploader = uploader
        self.metadata_client = metadata_client

    def run_once(self, now: str | datetime) -> UploadResult | None:
        current = _utc_datetime(now)
        item = self.store.claim_next(current)
        if item is None:
            return None
        try:
            path = Path(item.local_path)
            uploaded_url = self.uploader.upload(path)
            self.metadata_client.save_audio_file_info(
                {
                    "segmentIndex": item.segment_index,
                    "filePath": uploaded_url,
                    "fileSize": path.stat().st_size,
                    "format": path.suffix.lstrip(".").lower(),
                }
            )
            self.store.mark_uploaded(item.id, uploaded_url)
            self.store.mark_completed(item.id)
            return UploadResult(item.id, "completed")
        except Exception as exc:
            retry_at = current + timedelta(seconds=retry_delay(item.attempts))
            self.store.mark_failed(item.id, str(exc), retry_at)
            return UploadResult(
                item.id,
                "failed",
                int(retry_at.timestamp() * 1000),
                str(exc),
            )


def _utc_datetime(value: str | datetime) -> datetime:
    parsed = (
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        if isinstance(value, str)
        else value
    )
    if not isinstance(parsed, datetime):
        raise TypeError("now must be an ISO string or datetime")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("now must include a UTC offset")
    return parsed.astimezone(timezone.utc)
