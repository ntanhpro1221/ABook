"""Khoá của người dùng cho giọng trực tuyến dùng khoá riêng (byok.py): một file JSON cạnh file tuỳ chọn của app (`voice-keys.json`).

Không nằm TRONG preferences.json: file ấy được trả nguyên cho giao diện (`GET /api/preferences`), còn khoá thì không bao giờ rời máy trừ khi
gửi tới đúng nhà cung cấp của nó, trong header. Giao diện chỉ thấy bản che (`public()`: "••••" + 4 ký tự cuối). Không ghi log khoá; lỗi không
bao giờ chép khoá vào câu báo.

Mỗi nhà cung cấp một mục: `key`, `region` (chỉ Azure), `valid` (lần "Kiểm tra" gần nhất thành công và chưa bị từ chối sau đó), `voices`
(danh sách giọng vi-VN lấy lúc kiểm tra: [[mã, tên, giới], ...]) - giọng chỉ hiện trong danh sách chọn khi `valid`.
"""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any

FILE_NAME = "voice-keys.json"
MASK = "••••"


def mask(key: str) -> str:
    """Bản che để hiện: đủ để người dùng nhận ra khoá nào (4 ký tự cuối), không đủ để dùng. Khoá ngắn quá thì che hết."""
    return MASK + key[-4:] if len(key) >= 12 else MASK if key else ""


class KeyStore:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()
        self._data: dict[str, dict[str, Any]] = self._load()

    def __repr__(self) -> str:  # không bao giờ in khoá ra log / traceback
        return f"KeyStore({self.path.name}, {sorted(self._data)})"

    def _load(self) -> dict[str, dict[str, Any]]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return {name: entry for name, entry in data.items() if isinstance(entry, dict)} if isinstance(data, dict) else {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_bytes(json.dumps(self._data, ensure_ascii=False, indent=1).encode("utf-8"))
        if os.name != "nt":
            os.chmod(temporary, 0o600)  # chỉ chủ máy đọc được (Windows: thư mục dữ liệu của người dùng đã riêng)
        from ..io_utils import _replace_with_retry  # Windows: đè lên file đang mở báo PermissionError một lúc

        _replace_with_retry(temporary, self.path)

    def get(self, provider: str) -> dict[str, Any]:
        with self._lock:
            return dict(self._data.get(provider, {}))

    def put(self, provider: str, key: str, region: str = "") -> None:
        """Lưu khoá mới (đổi khoá thì phải kiểm tra lại: `valid` về False, danh sách giọng cũ bỏ)."""
        with self._lock:
            entry: dict[str, Any] = {"key": key.strip(), "valid": False, "voices": []}
            if region:
                entry["region"] = region.strip().lower()
            self._data[provider] = entry
            self._save()

    def mark(self, provider: str, valid: bool, voices: list[list[str]] | None = None) -> None:
        with self._lock:
            entry = self._data.get(provider)
            if entry is None:
                return
            entry["valid"] = valid
            entry["checked"] = int(time.time())
            if voices is not None:
                entry["voices"] = voices
            self._save()

    def remove(self, provider: str) -> None:
        with self._lock:
            if self._data.pop(provider, None) is not None:
                self._save()

    def public(self, provider: str) -> dict[str, Any]:
        """Những gì giao diện được thấy về khoá của một nhà cung cấp."""
        entry = self.get(provider)
        return {"hasKey": bool(entry.get("key")), "masked": mask(str(entry.get("key", ""))), "region": entry.get("region", ""),
                "valid": bool(entry.get("valid")), "voices": len(entry.get("voices") or [])}
