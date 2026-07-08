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
        if item.action == "register":
            return self._register(item, current)
        return self._upload(item, current)

    def _upload(self, item, current):
        try:
            path = Path(item.local_path)
            uploaded_url = self.uploader.upload(path)
            self.store.mark_uploaded(item.id, uploaded_url)
            return UploadResult(item.id, "uploaded")
        except Exception as exc:
            retry_at = current + timedelta(seconds=retry_delay(item.attempts))
            self.store.mark_failed(item.id, str(exc), retry_at)
            return UploadResult(
                item.id,
                "failed",
                int(retry_at.timestamp() * 1000),
                str(exc),
            )

    def _register(self, item, current):
        try:
            self.metadata_client.save_audio_file_info(_metadata_payload(item))
            self.store.mark_completed(item.id)
            return UploadResult(item.id, "completed")
        except Exception as exc:
            retry_at = current + timedelta(
                seconds=retry_delay(item.metadata_attempts)
            )
            self.store.mark_metadata_failed(item.id, str(exc), retry_at)
            return UploadResult(
                item.id,
                "metadata_failed",
                int(retry_at.timestamp() * 1000),
                str(exc),
            )


def _metadata_payload(item) -> dict:
    return {
        "code": item.code,
        "deviceNo": item.device_no,
        "schoolId": item.school_id,
        "locationId": item.location_id,
        "segmentIndex": item.segment_index,
        "filePath": item.uploaded_url,
        "fileSize": Path(item.local_path).stat().st_size,
        "format": item.audio_format,
        "startTime": item.start_time,
        "endTime": item.end_time,
        "rate": item.rate,
        "bits": item.bits,
        "channel": item.channel,
        "audioType": item.audio_type,
    }


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
