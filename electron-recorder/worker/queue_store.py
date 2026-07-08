from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
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
    retry_at: str | None
    created_at: str
    completed_at: str | None


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
                  retry_at TEXT,
                  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  completed_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_segments_claim
                  ON segments(status, retry_at, id);
                """
            )

    def enqueue(self, segment: dict) -> int:
        local_path, segment_index = _segment_values(segment)
        with self._connect() as connection:
            return self._insert(connection, local_path, segment_index)

    def claim_next(self, now: str) -> QueueItem | None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT * FROM segments
                WHERE status = 'pending'
                   OR (status = 'failed' AND retry_at <= ?)
                ORDER BY id
                LIMIT 1
                """,
                (now,),
            ).fetchone()
            if row is None:
                connection.commit()
                return None
            updated = connection.execute(
                """
                UPDATE segments
                SET status = 'uploading', retry_at = NULL
                WHERE id = ? AND (
                  status = 'pending'
                  OR (status = 'failed' AND retry_at <= ?)
                )
                """,
                (row["id"], now),
            ).rowcount
            if updated != 1:
                connection.rollback()
                return None
            claimed = connection.execute(
                "SELECT * FROM segments WHERE id = ?", (row["id"],)
            ).fetchone()
            connection.commit()
            return _queue_item(claimed)

    def mark_uploaded(self, item_id: int, url: str) -> None:
        self._update(
            """
            UPDATE segments
            SET status = 'uploaded', uploaded_url = ?, last_error = '', retry_at = NULL
            WHERE id = ?
            """,
            (url, item_id),
        )

    def mark_completed(self, item_id: int) -> None:
        self._update(
            """
            UPDATE segments
            SET status = 'completed', completed_at = CURRENT_TIMESTAMP,
                last_error = '', retry_at = NULL
            WHERE id = ?
            """,
            (item_id,),
        )

    def mark_failed(self, item_id: int, error: str, retry_at: str) -> None:
        self._update(
            """
            UPDATE segments
            SET status = 'failed', last_error = ?, retry_at = ?
            WHERE id = ?
            """,
            (error, retry_at, item_id),
        )

    def counts(self) -> dict[str, int]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT status, COUNT(*) AS count FROM segments GROUP BY status"
            ).fetchall()
        return {row["status"]: row["count"] for row in rows}

    def enqueue_many(self, segments: Iterable[dict]) -> None:
        values = [_segment_values(segment) for segment in segments]
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            for local_path, segment_index in values:
                self._insert(connection, local_path, segment_index)
            connection.commit()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=30000")
        return connection

    @staticmethod
    def _insert(
        connection: sqlite3.Connection, local_path: str, segment_index: int
    ) -> int:
        connection.execute(
            """
            INSERT INTO segments(local_path, segment_index)
            VALUES (?, ?)
            ON CONFLICT(local_path) DO NOTHING
            """,
            (local_path, segment_index),
        )
        row = connection.execute(
            "SELECT id FROM segments WHERE local_path = ?", (local_path,)
        ).fetchone()
        return int(row["id"])

    def _update(self, sql: str, parameters: tuple) -> None:
        with self._connect() as connection:
            connection.execute(sql, parameters)


def migrate_json_queue(json_path: str | Path, store: QueueStore) -> None:
    source = Path(json_path)
    if not source.exists():
        return
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("queue JSON must contain a list")
    store.enqueue_many(payload)
    source.replace(source.with_name(f"{source.name}.migrated"))


def _segment_values(segment: dict) -> tuple[str, int]:
    if not isinstance(segment, dict):
        raise TypeError("queue segment must be an object")
    local_path = segment.get("local_path", segment.get("localPath"))
    segment_index = segment.get("segment_index", segment.get("segmentIndex"))
    if not isinstance(local_path, str) or not local_path:
        raise ValueError("local_path is required")
    if isinstance(segment_index, bool) or not isinstance(segment_index, int):
        raise ValueError("segment_index must be an integer")
    return local_path, segment_index


def _queue_item(row: sqlite3.Row) -> QueueItem:
    return QueueItem(**dict(row))
