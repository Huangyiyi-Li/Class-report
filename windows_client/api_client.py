# -*- coding: utf-8 -*-
"""HTTP adapters for the Windows classroom recording client."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib import request
from urllib.error import HTTPError


REQUEST_TIMEOUT_SECONDS = 30


class LocalPathUploader:
    """Temporary uploader used until the real file-upload API is provided.

    It returns a stable filePath that the current metadata API can store. Swap
    this class for a real uploader without changing the queue or recorder.
    """

    def __init__(self, prefix: str = "/client-cache"):
        self.prefix = prefix.rstrip("/")

    def upload(self, path: str | Path) -> str:
        file_path = Path(path)
        return f"{self.prefix}/{file_path.name}"


class ClassroomApiClient:
    def __init__(self, server_url: str, token: str = ""):
        self.server_url = server_url.rstrip("/")
        self.token = token

    def login(self, username: str, password: str) -> dict[str, Any]:
        result = self._post_json("/api/login", {"username": username, "password": password}, auth=False)
        self.token = result["token"]
        return result

    def save_audio_file_info(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._post_json("/book-reading/audio/save-audio-file-info", payload)

    def build_audio_metadata_payload(self, item: dict[str, Any], file_path: str, file_size_bytes: int) -> dict[str, Any]:
        return {
            "code": item["code"],
            "schoolId": int(item["school_id"]),
            "unitId": int(item["unit_id"]),
            "segmentIndex": int(item["segment_index"]),
            "filePath": file_path,
            "fileSize": max(1, round(file_size_bytes / 1024)),
            "format": item["audio_format"],
            "startTime": item["start_time"],
            "endTime": item["end_time"],
            "uploadStatus": 1,
            "failReason": "",
            "audioType": 1,
        }

    def _post_json(self, path: str, payload: dict[str, Any], *, auth: bool = True) -> dict[str, Any]:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if auth and self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        req = request.Request(f"{self.server_url}{path}", data=body, headers=headers, method="POST")
        try:
            with request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
