"""Danh mục nhạc nền trên mây (Cloudflare, file tĩnh - Workers static assets, lượt tải không giới hạn - dựng bằng LLM_Train/music/build_catalog.py).

Không máy chủ, không khoá, không đăng nhập: app tải `manifest.json` (nhỏ), rồi CHỈ những mảnh cần:
- `tracks/<xx>.json`: dữ liệu đã gắn cho các link nhạc - có danh sách link thì tính mảnh (`shard_of`) và tải đúng mảnh ấy;
- `cells/<v>_<a>.json`: bài theo ô cảm xúc - "bài nào hợp với đoạn này".
Mảnh đã tải giữ trong bộ nhớ đệm trên máy theo `revision` của danh mục: danh mục mới thì tải lại, không thì dùng lại, mất
mạng vẫn dùng bản đệm.

    ABOOK_MUSIC_CATALOG=<url hay thư mục>   đổi nguồn (thử nghiệm, bản dựng tại chỗ)
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any, Iterable

# Địa chỉ thật lấy từ cấu hình từ xa (remote_config.RemoteConfig.music_catalogs) - đây chỉ là giá trị dự phòng.
DEFAULT_CATALOG = "https://abook-music.ngdtuanh.workers.dev/"
USER_AGENT = "ABook (+https://github.com/ntanhpro1221/ABook)"
MANIFEST_MAX_AGE = 24 * 3600
FORMAT = "abook-music-catalog"
FORMAT_VERSION = 1


class CatalogError(Exception):
    """Danh mục không đọc được (mất mạng lần đầu, định dạng mới hơn app...). Câu chữ để người dùng đọc."""


def shard_of(link: str) -> str:
    return hashlib.sha1(link.encode("utf-8")).hexdigest()[:2]


def cell_of(valence: float, arousal: float, grid: int = 5) -> tuple[int, int]:
    def index(value: float) -> int:
        return min(grid - 1, max(0, int((value + 1.0) / 2.0 * grid)))
    return index(valence), index(arousal)


class MusicCatalog:
    def __init__(self, cache_dir: Path, source: str | None = None) -> None:
        self.cache_dir = Path(cache_dir)
        self.source = (source or os.environ.get("ABOOK_MUSIC_CATALOG") or DEFAULT_CATALOG).rstrip("/") + "/"
        self._lock = threading.Lock()
        self._manifest: dict[str, Any] | None = None
        self._memory: dict[str, Any] = {}

    # ---- tải ------------------------------------------------------------------------------------------------------
    def _fetch(self, relative: str) -> bytes:
        if self.source.startswith(("http://", "https://")):
            request = urllib.request.Request(self.source + relative, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read()
        return (Path(self.source) / relative).read_bytes()

    def manifest(self, *, refresh: bool = False) -> dict[str, Any]:
        with self._lock:
            path = self.cache_dir / "manifest.json"
            fresh = path.exists() and time.time() - path.stat().st_mtime < MANIFEST_MAX_AGE
            if self._manifest is not None and not refresh and fresh:
                return self._manifest
            data: dict[str, Any] | None = None
            if refresh or not fresh:
                try:
                    # Làm mới chủ động: tham số chống đệm, để CDN không trả bản mục lục cũ (danh mục vừa dựng lại).
                    relative = f"manifest.json?v={int(time.time())}" if refresh and self.source.startswith("http")                         else "manifest.json"
                    data = json.loads(self._fetch(relative).decode("utf-8"))
                    self.cache_dir.mkdir(parents=True, exist_ok=True)
                    tmp = path.with_suffix(".part")
                    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
                    os.replace(tmp, path)
                except (OSError, ValueError):
                    data = None  # mất mạng: dùng bản đệm nếu có
            if data is None:
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, ValueError) as exc:
                    raise CatalogError("Chưa tải được danh mục nhạc nền - cần mạng ở lần đầu.") from exc
            if data.get("format") != FORMAT or not isinstance(data.get("version"), int):
                raise CatalogError("Danh mục nhạc nền không đúng định dạng.")
            if data["version"] > FORMAT_VERSION:
                raise CatalogError("Danh mục nhạc nền mới hơn app - hãy cập nhật app.")
            if self._manifest is None or self._manifest.get("revision") != data.get("revision"):
                self._memory.clear()
            self._manifest = data
            return data

    def _part(self, relative: str) -> Any:
        manifest = self.manifest()
        key = f"{manifest['revision']}/{relative}"
        if key in self._memory:
            return self._memory[key]
        path = self.cache_dir / manifest["revision"] / relative
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            try:
                # Mã phiên bản trong đường dẫn: CDN đệm mảnh 1 giờ - danh mục mới là đường dẫn mới, không lẫn mảnh cũ.
                raw = self._fetch(f"{relative}?v={manifest['revision']}" if self.source.startswith("http") else relative)
            except OSError as exc:
                raise CatalogError("Không tải được danh mục nhạc nền - kiểm tra mạng.") from exc
            value = json.loads(raw.decode("utf-8"))
            # Bộ đệm trên đĩa chỉ để lần sau đỡ tải: hai luồng cùng ghi một mảnh (Windows không cho thay file đang mở)
            # thì bên thua bỏ qua - nội dung như nhau, giá trị đã có trong tay.
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_name(f"{path.stem}.{os.getpid()}.{threading.get_ident()}.part")
            try:
                tmp.write_bytes(raw)
                os.replace(tmp, path)
            except OSError:
                with contextlib.suppress(OSError):
                    tmp.unlink(missing_ok=True)
        self._memory[key] = value
        return value

    # ---- truy vấn -------------------------------------------------------------------------------------------------
    def lookup(self, links: Iterable[str]) -> dict[str, dict[str, Any]]:
        """Dữ liệu đã gắn cho các link (link không có trong danh mục thì không có trong kết quả)."""
        found: dict[str, dict[str, Any]] = {}
        wanted: dict[str, list[str]] = {}
        for link in links:
            wanted.setdefault(shard_of(link), []).append(link)
        existing = set(self.manifest().get("shards") or [])
        for shard, items in wanted.items():
            if shard not in existing:
                continue  # danh mục không có mảnh ấy = không link nào trong đó có dữ liệu (không phải lỗi mạng)
            data = self._part(f"tracks/{shard}.json")
            for link in items:
                if link in data:
                    found[link] = data[link]
        return found

    def cell(self, valence_index: int, arousal_index: int) -> list[dict[str, Any]]:
        manifest = self.manifest()
        name = f"{valence_index}_{arousal_index}"
        if not manifest.get("cells", {}).get(name):
            return []
        return list(self._part(f"cells/{name}.json"))

    def near(self, valence: float, arousal: float, radius: int = 1) -> list[dict[str, Any]]:
        """Bài trong ô của (valence, arousal) và các ô kề trong bán kính `radius`."""
        grid = int(self.manifest().get("grid") or 5)
        vi, ai = cell_of(valence, arousal, grid)
        items: list[dict[str, Any]] = []
        for v in range(max(0, vi - radius), min(grid, vi + radius + 1)):
            for a in range(max(0, ai - radius), min(grid, ai + radius + 1)):
                items.extend(self.cell(v, a))
        return items
