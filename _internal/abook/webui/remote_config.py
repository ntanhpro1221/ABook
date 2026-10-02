"""Cấu hình từ xa: những gì có thể đổi sau khi app đã phát hành (chỗ đặt danh mục nhạc, bản dự phòng, nguồn tìm thêm...)
KHÔNG ghi cứng trong app - chủ sách 02-10: "link hay các thứ có thể thay đổi thì không nên hardcode vào app".

App chỉ ghi cứng vài ĐỊA CHỈ KHỞI ĐỘNG (repo GitHub công khai, qua hai đường khác nhau) trỏ tới một file nhỏ
`remote-config/remote-config.json` + chữ ký `remote-config.json.sig`. Cấu hình có quyền bảo app lấy dữ liệu ở chỗ khác, nên:
- chỉ nhận file có chữ ký Ed25519 đúng khoá của ABook (khoá bí mật ở repo riêng tư, ký bằng scripts/sign_remote_config.py);
- không nhận bản cũ hơn bản đang giữ (`issued`) - không ai quay app về địa chỉ cũ được bằng file cũ còn chữ ký;
- tải hỏng / chữ ký sai / mất mạng: dùng bản tốt gần nhất đã lưu, chưa có thì DEFAULTS đóng sẵn trong app.

    ABOOK_REMOTE_CONFIG=<url hay file>   đổi nguồn (thử nghiệm) - vẫn phải có chữ ký đúng
"""
from __future__ import annotations

import base64
import json
import os
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any

from .ed25519_verify import verify

FORMAT = "abook-remote-config"
FORMAT_VERSION = 1
PUBLIC_KEY = bytes.fromhex("1486a17adc7729ca8a23dd8bd11f5b7d59eb4424f3948bb8e9ddf2333ee18e22")
BOOTSTRAP = (
    "https://cdn.jsdelivr.net/gh/ntanhpro1221/ABook@main/remote-config/remote-config.json",
    "https://raw.githubusercontent.com/ntanhpro1221/ABook/main/remote-config/remote-config.json",
)
REFRESH_SECONDS = 6 * 3600
USER_AGENT = "ABook (+https://github.com/ntanhpro1221/ABook)"
DEFAULTS: dict[str, Any] = {
    "format": FORMAT,
    "version": FORMAT_VERSION,
    "issued": "",  # mặc định đóng trong app: bản có chữ ký nào cũng mới hơn
    "music": {
        "catalogs": ["https://abook-music.ngdtuanh.workers.dev/"],
        "openverse": "https://api.openverse.org/v1/",
    },
}


class RemoteConfig:
    def __init__(self, cache_dir: Path, *, sources: tuple[str, ...] | None = None,
                 public_key: bytes = PUBLIC_KEY) -> None:
        self.cache_dir = Path(cache_dir)
        override = os.environ.get("ABOOK_REMOTE_CONFIG")
        self.sources = tuple(sources) if sources else ((override,) if override else BOOTSTRAP)
        self.public_key = public_key
        self._lock = threading.Lock()
        self._value: dict[str, Any] | None = None
        self._checked = 0.0

    def _read(self, source: str, suffix: str = "") -> bytes:
        if source.startswith(("http://", "https://")):
            request = urllib.request.Request(source + suffix, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=15) as response:
                return response.read()
        return Path(source + suffix).read_bytes()

    def _accept(self, raw: bytes, signature: bytes) -> dict[str, Any] | None:
        try:
            if not verify(self.public_key, raw, base64.b64decode(signature.strip(), validate=True)):
                return None
            value = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return None
        if not isinstance(value, dict) or value.get("format") != FORMAT:
            return None
        if not isinstance(value.get("version"), int) or value["version"] > FORMAT_VERSION:
            return None  # định dạng mới hơn app: giữ bản cũ, bản app mới sẽ đọc được
        if not isinstance(value.get("issued"), str):
            return None
        return value

    def _cached(self) -> dict[str, Any] | None:
        path = self.cache_dir / "remote-config.json"
        try:
            return self._accept(path.read_bytes(), (self.cache_dir / "remote-config.json.sig").read_bytes())
        except OSError:
            return None

    def get(self, *, refresh: bool = False) -> dict[str, Any]:
        with self._lock:
            if self._value is not None and not refresh and time.time() - self._checked < REFRESH_SECONDS:
                return self._value
            current = self._value or self._cached() or DEFAULTS
            for source in self.sources:
                try:
                    raw, signature = self._read(source), self._read(source, ".sig")
                except OSError:
                    continue
                value = self._accept(raw, signature)
                if value is None:
                    continue
                if value["issued"] < str(current.get("issued", "")):
                    continue  # bản cũ hơn bản đang giữ - có thể là file cũ bị dựng lại
                self.cache_dir.mkdir(parents=True, exist_ok=True)
                for name, data in (("remote-config.json", raw), ("remote-config.json.sig", signature)):
                    tmp = self.cache_dir / (name + ".part")
                    tmp.write_bytes(data)
                    os.replace(tmp, self.cache_dir / name)
                current = value
                break
            self._value, self._checked = current, time.time()
            return current

    def music_catalogs(self) -> list[str]:
        music = self.get().get("music") or {}
        catalogs = [str(item) for item in music.get("catalogs") or [] if str(item).startswith(("http://", "https://"))]
        return catalogs or list(DEFAULTS["music"]["catalogs"])
