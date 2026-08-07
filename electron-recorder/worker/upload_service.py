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
    stage: str = ""


class UploadService:
    def __init__(self, store: QueueStore, uploader, metadata_client):
        self.store = store
        self.uploader = uploader
        self.metadata_client = metadata_client
        self._status_listener = None

    def set_status_listener(self, listener) -> None:
        self._status_listener = listener

    def diagnostics(self) -> dict:
        if hasattr(self.uploader, "diagnostics"):
            return dict(self.uploader.diagnostics())
        return {}

    def set_device_auth_listener(self, on_success, on_failure) -> None:
        if hasattr(self.metadata_client, "set_device_auth_listener"):
            self.metadata_client.set_device_auth_listener(on_success, on_failure)

    def check_device_auth(self):
        if not hasattr(self.metadata_client, "check_device_auth"):
            raise RuntimeError("当前上传服务不支持重新检测设备认证")
        return self.metadata_client.check_device_auth()

    def run_once(self, now: str | datetime) -> UploadResult | None:
        current = _utc_datetime(now)
        item = self.store.claim_next(current)
        if item is None:
            return None
        if item.action == "register":
            return self._register(item, current)
        return self._upload(item, current)

    def _upload(self, item, current):
        self._notify("upload", "started", item, current)
        try:
            path = Path(item.local_path)
            uploaded_url = self.uploader.upload(path)
            self.store.mark_uploaded(item.id, uploaded_url)
            self._notify("upload", "succeeded", item, current)
            return UploadResult(item.id, "uploaded", stage="upload")
        except Exception as exc:
            failure_message = str(exc).strip() or type(exc).__name__
            try:
                self.metadata_client.save_audio_file_info(
                    _metadata_payload(
                        item,
                        upload_status=3,
                        fail_reason=failure_message,
                    )
                )
            except Exception:
                pass
            retry_at = current + timedelta(seconds=retry_delay(item.attempts))
            self.store.mark_failed(item.id, failure_message, retry_at)
            result = UploadResult(
                item.id,
                "failed",
                int(retry_at.timestamp() * 1000),
                failure_message,
                "upload",
            )
            self._notify(
                "upload",
                "waiting_retry",
                item,
                current,
                error=failure_message,
                retry_at=result.retry_at,
            )
            return result

    def _register(self, item, current):
        self._notify("registration", "started", item, current)
        try:
            self.metadata_client.save_audio_file_info(_metadata_payload(item))
            self.store.mark_completed(item.id)
            self._notify("registration", "succeeded", item, current)
            return UploadResult(item.id, "completed", stage="registration")
        except Exception as exc:
            retry_at = current + timedelta(
                seconds=retry_delay(item.metadata_attempts)
            )
            self.store.mark_metadata_failed(item.id, str(exc), retry_at)
            result = UploadResult(
                item.id,
                "metadata_failed",
                int(retry_at.timestamp() * 1000),
                str(exc),
                "registration",
            )
            self._notify(
                "registration",
                "waiting_retry",
                item,
                current,
                error=str(exc),
                retry_at=result.retry_at,
            )
            return result

    def _notify(
        self,
        stage: str,
        status: str,
        item,
        current: datetime,
        *,
        error: str = "",
        retry_at: int | None = None,
    ) -> None:
        if self._status_listener is None:
            return
        payload = {
            "stage": stage,
            "status": status,
            "segmentIndex": item.segment_index,
            "updatedAt": current.isoformat(),
        }
        if error:
            payload["error"] = error
        if retry_at is not None:
            payload["retryAt"] = retry_at
        self._status_listener(payload)


def _metadata_payload(
    item,
    *,
    upload_status: int = 1,
    fail_reason: str = "",
) -> dict:
    try:
        file_size = Path(item.local_path).stat().st_size
    except OSError:
        if upload_status == 1:
            raise
        file_size = 0
    payload = {
        "code": item.code,
        "deviceNo": item.device_no,
        "segmentIndex": item.segment_index,
        "fileName": Path(item.local_path).name,
        "filePath": item.uploaded_url if upload_status == 1 else "",
        "fileSize": file_size,
        "format": item.audio_format,
        "startTime": item.start_time,
        "endTime": item.end_time,
        "rate": item.rate,
        "bits": item.bits,
        "channel": item.channel,
        "audioType": item.audio_type,
        "uploadStatus": upload_status,
    }
    if upload_status == 3:
        payload["failReason"] = fail_reason
    return payload


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
