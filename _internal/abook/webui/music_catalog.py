"""Danh mục nhạc nền trên mây (Cloudflare, file tĩnh - Workers static assets, lượt tải không giới hạn - dựng bằng LLM_Train/music/build_catalog.py).

Không máy chủ, không khoá, không đăng nhập: app tải `manifest.json` (nhỏ), rồi CHỈ những mảnh cần:
- `tracks/<xx>.json`: dữ liệu đã gắn cho các link nhạc - có danh sách link thì tính mảnh (`shard_of`) và tải đúng mảnh ấy;
- `cells/<v>_<a>.json`: bài theo ô cảm xúc - "bài nào hợp với đoạn này".
Mục lục còn mang `playlists` - các danh sách phát cố định cho sách nghe bằng "Nghe ngay" (music_playlist.py).
Danh mục có chữ ký (Lead duyệt 04-10): link bài nằm trong các mảnh, nên chỉ ký mục lục là chưa đủ - mục lục đã ký (`manifest.json.sig`,
Ed25519 trên đúng các byte của manifest.json) mang `files` (đường dẫn mảnh -> sha256) và app kiểm từng mảnh tải về. Chữ ký sai,
mục lục cũ hơn bản đang giữ (`issued`) hay mảnh lệch sha256: giữ danh mục đã tải trước, không bao giờ dùng link của bản lạ.
Khoá là khoá cấu hình từ xa (`remote_config.PUBLIC_KEY`).
Mảnh đã tải giữ trong bộ nhớ đệm trên máy theo `revision` của danh mục: danh mục mới thì tải lại, không thì dùng lại, mất
mạng vẫn dùng bản đệm.

    ABOOK_MUSIC_CATALOG=<url hay thư mục>   đổi nguồn (thử nghiệm, bản dựng tại chỗ)
"""
from __future__ import annotations

import contextlib
import concurrent.futures
import hashlib
import json
import logging
import os
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any, Iterable

from .ed25519_verify import verify_base64
from .remote_config import PUBLIC_KEY

log = logging.getLogger(__name__)

# Địa chỉ thật lấy từ cấu hình từ xa (remote_config.RemoteConfig.music_catalogs) - đây chỉ là giá trị dự phòng.
DEFAULT_CATALOG = "https://abook-music.ngdtuanh.workers.dev/"
USER_AGENT = "ABook (+https://github.com/ntanhpro1221/ABook)"
MANIFEST_MAX_AGE = 24 * 3600
FORMAT = "abook-music-catalog"
FORMAT_VERSION = 1
SHARD_WORKERS = 8  # một danh sách phát chạm ~100 mảnh: tải song song, lần đầu không phải chờ từng mảnh một


class CatalogError(Exception):
    """Danh mục không đọc được (mất mạng lần đầu, định dạng mới hơn app...). Câu chữ để người dùng đọc."""


def shard_of(link: str) -> str:
    return hashlib.sha1(link.encode("utf-8")).hexdigest()[:2]


def cell_of(valence: float, arousal: float, grid: int = 5) -> tuple[int, int]:
    def index(value: float) -> int:
        return min(grid - 1, max(0, int((value + 1.0) / 2.0 * grid)))
    return index(valence), index(arousal)


class MusicCatalog:
    def __init__(self, cache_dir: Path, source: str | None = None, *, public_key: bytes = PUBLIC_KEY) -> None:
        self.cache_dir = Path(cache_dir)
        self.source = (source or os.environ.get("ABOOK_MUSIC_CATALOG") or DEFAULT_CATALOG).rstrip("/") + "/"
        self.public_key = public_key  # khoá công khai kiểm mục lục; test truyền khoá test, app dùng khoá của ABook
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

    def _accept(self, raw: bytes, signature: bytes) -> dict[str, Any] | None:
        """Mục lục đã kiểm: chữ ký đúng khoá, JSON đúng hình dạng, có `issued` và `files`. Không thì None (không ném lỗi)."""
        if not verify_base64(self.public_key, raw, signature):
            return None
        try:
            data = json.loads(raw.decode("utf-8"))
        except ValueError:
            return None
        if not isinstance(data, dict) or data.get("format") != FORMAT or not isinstance(data.get("version"), int):
            return None
        if not isinstance(data.get("issued"), str) or not isinstance(data.get("files"), dict):
            return None
        return data

    def _cached(self) -> dict[str, Any] | None:
        """Mục lục đã cất trên đĩa, kiểm lại chữ ký (file đĩa bị sửa hay ghi dở thì coi như không có)."""
        try:
            return self._accept((self.cache_dir / "manifest.json").read_bytes(), (self.cache_dir / "manifest.json.sig").read_bytes())
        except OSError:
            return None

    def manifest(self, *, refresh: bool = False) -> dict[str, Any]:
        with self._lock:
            path = self.cache_dir / "manifest.json"
            fresh = path.exists() and time.time() - path.stat().st_mtime < MANIFEST_MAX_AGE
            if self._manifest is not None and not refresh and fresh:
                return self._manifest
            current = self._manifest or self._cached()  # bản đang giữ: mốc `issued` để không quay về bản cũ
            rejected = False
            if refresh or not fresh or current is None:
                try:
                    # Làm mới chủ động: tham số chống đệm, để CDN không trả bản mục lục cũ (danh mục vừa dựng lại).
                    suffix = f"?v={int(time.time())}" if refresh and self.source.startswith("http") else ""
                    raw, signature = self._fetch("manifest.json" + suffix), self._fetch("manifest.json.sig" + suffix)
                except OSError:
                    raw = signature = None  # mất mạng: dùng bản đã cất nếu có
                if raw is not None and signature is not None:
                    data = self._accept(raw, signature)
                    if data is None:
                        log.warning("danh mục nhạc: mục lục tải về sai chữ ký hay sai định dạng - giữ bản đã cất")
                    elif current is not None and data["issued"] < current["issued"]:
                        log.warning("danh mục nhạc: mục lục tải về cũ hơn bản đang giữ (%s < %s) - bỏ", data["issued"], current["issued"])
                        data = None
                    if data is None:
                        rejected = True
                    else:
                        self._check_version(data)
                        self.cache_dir.mkdir(parents=True, exist_ok=True)
                        for name, content in (("manifest.json", raw), ("manifest.json.sig", signature)):
                            tmp = self.cache_dir / (name + ".part")
                            tmp.write_bytes(content)
                            os.replace(tmp, self.cache_dir / name)
                        current = data
            if current is None:
                raise CatalogError("Danh mục nhạc nền tải về không có chữ ký hợp lệ - app không dùng." if rejected
                                   else "Chưa tải được danh mục nhạc nền - cần mạng ở lần đầu.")
            self._check_version(current)
            if self._manifest is None or self._manifest.get("revision") != current.get("revision"):
                self._memory.clear()
            self._manifest = current
            return current

    @staticmethod
    def _check_version(data: dict[str, Any]) -> None:
        if data["version"] > FORMAT_VERSION:
            raise CatalogError("Danh mục nhạc nền mới hơn app - hãy cập nhật app.")

    def _part(self, relative: str) -> Any | None:
        """Một mảnh của danh mục (đã giải JSON). Mảnh phải khớp sha256 trong `files` của mục lục đã ký - không có trong `files`
        hay lệch thì không dùng (None: coi như mảnh vắng, các bài trong đó như không có), có ghi nhật ký."""
        manifest = self.manifest()
        key = f"{manifest['revision']}/{relative}"
        if key in self._memory:
            return self._memory[key]
        expected = manifest["files"].get(relative)
        if not isinstance(expected, str):
            log.warning("danh mục nhạc: mảnh %s không có trong mục lục đã ký - bỏ", relative)
            return None
        path = self.cache_dir / manifest["revision"] / relative
        try:
            raw: bytes | None = path.read_bytes()
        except OSError:
            raw = None
        if raw is None or hashlib.sha256(raw).hexdigest() != expected:
            try:
                # Mã phiên bản trong đường dẫn: CDN đệm mảnh 1 giờ - danh mục mới là đường dẫn mới, không lẫn mảnh cũ.
                raw = self._fetch(f"{relative}?v={manifest['revision']}" if self.source.startswith("http") else relative)
            except OSError as exc:
                raise CatalogError("Không tải được danh mục nhạc nền - kiểm tra mạng.") from exc
            if hashlib.sha256(raw).hexdigest() != expected:
                log.warning("danh mục nhạc: mảnh %s lệch sha256 của mục lục đã ký - bỏ", relative)
                return None
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
        try:
            value = json.loads(raw.decode("utf-8"))
        except ValueError:
            log.warning("danh mục nhạc: mảnh %s không phải JSON - bỏ", relative)
            return None
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
        # danh mục không có mảnh ấy = không link nào trong đó có dữ liệu (không phải lỗi mạng)
        shards = [shard for shard in wanted if shard in existing]
        if len(shards) > 1:
            with concurrent.futures.ThreadPoolExecutor(max_workers=SHARD_WORKERS) as pool:
                parts = dict(zip(shards, pool.map(lambda shard: self._part(f"tracks/{shard}.json"), shards)))
        else:
            parts = {shard: self._part(f"tracks/{shard}.json") for shard in shards}
        for shard in shards:
            data = parts[shard]
            if data is None:
                continue  # mảnh không qua kiểm sha256: các bài trong đó coi như không có
            for link in wanted[shard]:
                if link in data:
                    found[link] = data[link]
        return found

    def playlists(self) -> list[dict[str, Any]]:
        """Danh sách phát của danh mục (mục `playlists` của mục lục), đã kiểm hình dạng: [{id, name, description, minutes,
        tracks: [link theo thứ tự trộn sẵn]}]. Mục lục cũ chưa có thì rỗng."""
        from . import music_playlist

        return music_playlist.catalogue_playlists(self.manifest())

    def cell(self, valence_index: int, arousal_index: int) -> list[dict[str, Any]]:
        manifest = self.manifest()
        name = f"{valence_index}_{arousal_index}"
        if not manifest.get("cells", {}).get(name):
            return []
        return list(self._part(f"cells/{name}.json") or [])

    def near(self, valence: float, arousal: float, radius: int = 1) -> list[dict[str, Any]]:
        """Bài trong ô của (valence, arousal) và các ô kề trong bán kính `radius`."""
        grid = int(self.manifest().get("grid") or 5)
        vi, ai = cell_of(valence, arousal, grid)
        items: list[dict[str, Any]] = []
        for v in range(max(0, vi - radius), min(grid, vi + radius + 1)):
            for a in range(max(0, ai - radius), min(grid, ai + radius + 1)):
                items.extend(self.cell(v, a))
        return items
