from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class QueueItem:
    id: int
    local_path: str
    segment_index: int
    status: str
    uploaded_url: str
    last_error: str
    retry_at: int | None
    created_at: str
    completed_at: str | None
    attempts: int
    metadata_attempts: int
    code: str
    device_no: str
    school_id: int | None
    location_id: str
    start_time: str
    end_time: str
    rate: int
    bits: int
    channel: int
    audio_type: int
    audio_format: str
    action: str = ""


class QueueStore:
    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS segments (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  local_path TEXT NOT NULL UNIQUE,
                  segment_index INTEGER NOT NULL,
                  status TEXT NOT NULL DEFAULT 'pending',
                  uploaded_url TEXT NOT NULL DEFAULT '',
                  last_error TEXT NOT NULL DEFAULT '',
                  retry_at INTEGER,
                  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  completed_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_segments_claim
                  ON segments(status, retry_at, id);
                CREATE TABLE IF NOT EXISTS segment_counters (
                  device_id TEXT NOT NULL,
                  day TEXT NOT NULL,
                  current_index INTEGER NOT NULL,
                  PRIMARY KEY (device_id, day)
                );
                """
            )
            columns = {
                row[1] for row in connection.execute("PRAGMA table_info(segments)")
            }
            additions = {
                "attempts": "INTEGER NOT NULL DEFAULT 0",
                "metadata_attempts": "INTEGER NOT NULL DEFAULT 0",
                "code": "TEXT NOT NULL DEFAULT ''",
                "device_no": "TEXT NOT NULL DEFAULT ''",
                "school_id": "INTEGER",
                "location_id": "TEXT NOT NULL DEFAULT ''",
                "start_time": "TEXT NOT NULL DEFAULT ''",
                "end_time": "TEXT NOT NULL DEFAULT ''",
                "rate": "INTEGER NOT NULL DEFAULT 16000",
                "bits": "INTEGER NOT NULL DEFAULT 16",
                "channel": "INTEGER NOT NULL DEFAULT 1",
                "audio_type": "INTEGER NOT NULL DEFAULT 1",
                "audio_format": "TEXT NOT NULL DEFAULT ''",
            }
            for name, declaration in additions.items():
                if name in columns:
                    continue
                connection.execute(
                    f"ALTER TABLE segments ADD COLUMN {name} {declaration}"
                )

    def enqueue(self, segment: dict) -> int:
        values = _segment_values(segment)
        with self._connect() as connection:
            return self._insert(connection, values)

    def claim_next(self, now: str | datetime) -> QueueItem | None:
        now_epoch = _to_epoch_ms(now)
        lease_until = now_epoch + 300_000
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT * FROM segments
                WHERE status IN ('pending', 'uploaded')
                   OR (status IN ('failed', 'metadata_failed', 'uploading', 'registering')
                       AND retry_at <= ?)
                ORDER BY CASE
                    WHEN status IN ('pending', 'failed', 'uploading') THEN 0 ELSE 1
                END, id
                LIMIT 1
                """,
                (now_epoch,),
            ).fetchone()
            if row is None:
                connection.commit()
                return None
            updated = connection.execute(
                """
                UPDATE segments
                SET status = CASE
                    WHEN status IN ('uploaded', 'metadata_failed', 'registering')
                    THEN 'registering' ELSE 'uploading' END,
                    retry_at = ?
                WHERE id = ? AND (
                  status IN ('pending', 'uploaded')
                  OR (status IN ('failed', 'metadata_failed', 'uploading', 'registering')
                      AND retry_at <= ?)
                )
                """,
                (lease_until, row["id"], now_epoch),
            ).rowcount
            if updated != 1:
                connection.rollback()
                return None
            claimed = connection.execute(
                "SELECT * FROM segments WHERE id = ?", (row["id"],)
            ).fetchone()
            connection.commit()
            action = "register" if claimed["status"] == "registering" else "upload"
            return _queue_item(claimed, action)

    def mark_uploaded(self, item_id: int, url: str) -> None:
        self._transition(
            item_id,
            "uploaded",
            ("uploading",),
            """
            UPDATE segments
            SET status = 'uploaded', uploaded_url = ?, last_error = '', retry_at = NULL
            WHERE id = ? AND status IN ('uploading')
            """,
            (url, item_id),
        )

    def mark_completed(self, item_id: int) -> None:
        self._transition(
            item_id,
            "completed",
            ("registering",),
            """
            UPDATE segments
            SET status = 'completed', completed_at = CURRENT_TIMESTAMP,
                last_error = '', retry_at = NULL
            WHERE id = ? AND status = 'registering'
            """,
            (item_id,),
        )

    def mark_failed(
        self, item_id: int, error: str, retry_at: str | datetime
    ) -> None:
        self._transition(
            item_id,
            "failed",
            ("uploading",),
            """
            UPDATE segments
            SET status = 'failed', last_error = ?, retry_at = ?, attempts = attempts + 1
            WHERE id = ? AND status IN ('uploading')
            """,
            (error, _to_epoch_ms(retry_at), item_id),
        )

    def mark_metadata_failed(
        self, item_id: int, error: str, retry_at: str | datetime
    ) -> None:
        self._transition(
            item_id,
            "metadata_failed",
            ("registering",),
            """
            UPDATE segments
            SET status = 'metadata_failed', last_error = ?, retry_at = ?,
                metadata_attempts = metadata_attempts + 1
            WHERE id = ? AND status = 'registering'
            """,
            (error, _to_epoch_ms(retry_at), item_id),
        )

    def next_segment_index(self, device_id: str, day: str) -> int:
        if not device_id or not day:
            raise ValueError("device_id and day are required")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT current_index FROM segment_counters
                WHERE device_id = ? AND day = ?
                """,
                (device_id, day),
            ).fetchone()
            next_index = 1 if row is None else int(row["current_index"]) + 1
            connection.execute(
                """
                INSERT INTO segment_counters(device_id, day, current_index)
                VALUES (?, ?, ?)
                ON CONFLICT(device_id, day)
                DO UPDATE SET current_index = excluded.current_index
                """,
                (device_id, day, next_index),
            )
            connection.commit()
            return next_index

    def counts(self) -> dict[str, int]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT status, COUNT(*) AS count FROM segments GROUP BY status"
            ).fetchall()
        return {row["status"]: row["count"] for row in rows}

    def completed_before(self, before: str | datetime) -> list[QueueItem]:
        cutoff = _to_utc_datetime(before).strftime("%Y-%m-%d %H:%M:%S")
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM segments
                WHERE status = 'completed' AND completed_at < ?
                ORDER BY id
                """,
                (cutoff,),
            ).fetchall()
        return [_queue_item(row) for row in rows]

    def set_completed_at(self, item_id: int, value: str | datetime) -> None:
        """Set a completion timestamp, primarily for migration and maintenance."""
        completed_at = _to_utc_datetime(value).strftime("%Y-%m-%d %H:%M:%S")
        with self._connect() as connection:
            changed = connection.execute(
                """
                UPDATE segments SET completed_at = ?
                WHERE id = ? AND status = 'completed'
                """,
                (completed_at, item_id),
            ).rowcount
        if changed != 1:
            raise ValueError(f"queue item {item_id} is not completed")

    def enqueue_many(self, segments: Iterable[dict]) -> None:
        values = [_segment_values(segment) for segment in segments]
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            for value in values:
                self._insert(connection, value)
            connection.commit()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=30000")
        return connection

    @staticmethod
    def _insert(connection: sqlite3.Connection, values: dict) -> int:
        connection.execute(
            """
            INSERT INTO segments(
              local_path, segment_index, code, device_no, school_id, location_id,
              start_time, end_time, rate, bits, channel, audio_type, audio_format
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(local_path) DO NOTHING
            """,
            tuple(
                values[name]
                for name in (
                    "local_path",
                    "segment_index",
                    "code",
                    "device_no",
                    "school_id",
                    "location_id",
                    "start_time",
                    "end_time",
                    "rate",
                    "bits",
                    "channel",
                    "audio_type",
                    "audio_format",
                )
            ),
        )
        row = connection.execute(
            "SELECT id FROM segments WHERE local_path = ?", (values["local_path"],)
        ).fetchone()
        return int(row["id"])

    def _transition(
        self,
        item_id: int,
        target_status: str,
        source_statuses: tuple[str, ...],
        sql: str,
        parameters: tuple,
    ) -> None:
        with self._connect() as connection:
            changed = connection.execute(sql, parameters).rowcount
            if changed == 1:
                return
            row = connection.execute(
                "SELECT status FROM segments WHERE id = ?", (item_id,)
            ).fetchone()
            if row is None:
                raise KeyError(f"queue item {item_id} does not exist")
            current_status = row["status"]
            if current_status == target_status:
                return
            sources = ", ".join(source_statuses)
            raise ValueError(
                f"cannot transition queue item {item_id} from {current_status} "
                f"to {target_status}; expected {sources}"
            )


def migrate_json_queue(json_path: str | Path, store: QueueStore) -> None:
    source = Path(json_path)
    if not source.exists():
        return
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("queue JSON must contain a list")
    store.enqueue_many(payload)
    source.replace(source.with_name(f"{source.name}.migrated"))


def _segment_values(segment: dict) -> dict:
    if not isinstance(segment, dict):
        raise TypeError("queue segment must be an object")
    local_path = segment.get("local_path", segment.get("localPath"))
    segment_index = segment.get("segment_index", segment.get("segmentIndex"))
    if not isinstance(local_path, str) or not local_path:
        raise ValueError("local_path is required")
    if isinstance(segment_index, bool) or not isinstance(segment_index, int):
        raise ValueError("segment_index must be an integer")
    return {
        "local_path": local_path,
        "segment_index": segment_index,
        "code": str(segment.get("code") or segment.get("device_no") or ""),
        "device_no": str(
            segment.get("device_no")
            or segment.get("deviceNo")
            or segment.get("code")
            or ""
        ),
        "school_id": segment.get("school_id", segment.get("schoolId")),
        "location_id": str(
            segment.get("location_id") or segment.get("locationId") or ""
        ),
        "start_time": str(
            segment.get("start_time") or segment.get("startTime") or ""
        ),
        "end_time": str(
            segment.get("end_time") or segment.get("endTime") or ""
        ),
        "rate": int(segment.get("rate", 16000)),
        "bits": int(segment.get("bits", 16)),
        "channel": int(segment.get("channel", 1)),
        "audio_type": int(segment.get("audio_type", segment.get("audioType", 1))),
        "audio_format": str(
            segment.get("audio_format")
            or segment.get("format")
            or Path(local_path).suffix.lstrip(".")
        ),
    }


def _queue_item(row: sqlite3.Row, action: str = "") -> QueueItem:
    return QueueItem(**dict(row), action=action)


def _to_epoch_ms(value: str | datetime) -> int:
    utc_value = _to_utc_datetime(value)
    elapsed = utc_value - datetime(1970, 1, 1, tzinfo=timezone.utc)
    return (
        elapsed.days * 86_400_000
        + elapsed.seconds * 1_000
        + elapsed.microseconds // 1_000
    )


def _to_utc_datetime(value: str | datetime) -> datetime:
    if isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    elif isinstance(value, datetime):
        parsed = value
    else:
        raise TypeError("timestamp must be an ISO string or datetime")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must include a UTC offset")
    return parsed.astimezone(timezone.utc)
