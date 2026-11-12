"""Kho nhạc (màn "Nhạc"): lướt, tìm, lọc cả danh mục nhạc nền ký số; lưu bài về máy để nghe không mạng.

- Chỉ mục: mọi bài của mọi mảnh `tracks/<xx>.json` (MusicCatalog.everything) thu gọn thành dòng (`row`) - một lần mỗi
  `revision` của danh mục, giữ trong bộ nhớ. Lọc / tìm chạy trên máy chủ (`select`) cho web và Qt; điện thoại có bản Kotlin
  (MusicLibrary.kt). Ba nơi chạy CÙNG bộ ca: tests/fixtures/music_library/cases.json.
- Đã lưu (`SavedTracks`): bài người dùng bấm "Tải về" / "Lưu" - sổ saved.json cạnh bộ đệm. Bài đã lưu là bài GHIM: bộ dọn bộ đệm
  (music_cache.prune) không xoá. Bỏ lưu thì xoá bản tải (trừ khi sách nào đó đang ghim / mang theo bài ấy).
- Tải (`Downloads`): một luồng nền, lần lượt, dùng đúng đường tải của trình phát (server.App.music_track_file: kiểm byte + sha1,
  tải tiếp bằng Range, bản sao dự phòng). Huỷ được từng bài; mất mạng thì bài dừng ở "Chưa tải xong" (giữ phần đã có) và tải tiếp
  khi người dùng bấm lại.
"""
from __future__ import annotations

import contextlib
import functools
import json
import threading
import unicodedata
from collections import deque
from pathlib import Path
from typing import Any, Callable, Iterable

from ..io_utils import atomic_write_json

SAVED_VERSION = 1
EMOTION_THRESHOLD = 0.5  # chip cảm xúc: bài có điểm cảm xúc ấy từ 0,5 trở lên, xếp theo điểm
SLOW_BPM = 90  # Chậm < 90, Vừa 90-130, Nhanh > 130
FAST_BPM = 130
SHORT_SECONDS = 120  # < 2 phút, 2-5 phút, > 5 phút
LONG_SECONDS = 300
TEMPOS = ("slow", "mid", "fast")
LENGTHS = ("short", "mid", "long")
ROW_KEYS = ("title", "creator", "duration", "bpm", "style", "bytes", "lufs", "audibleStart", "audibleEnd")
DETAIL_KEYS = ("title", "creator", "duration", "bpm", "style", "bytes", "arousal", "valence", "license", "licenseUrl",
               "licenseVersion", "attribution", "landing", "source", "vocals", "audibleStart", "audibleEnd")


@functools.lru_cache(maxsize=32768)  # tên bài / người sáng tác của cả danh mục: gấp một lần, các lượt lọc sau dùng lại
def fold(text: str) -> str:
    """Chữ để so khi tìm: bỏ dấu tiếng Việt (cả đ/Đ), không phân biệt hoa thường, gộp khoảng trắng."""
    decomposed = unicodedata.normalize("NFD", str(text or "").replace("đ", "d").replace("Đ", "D"))
    plain = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(plain.casefold().split())


def _number(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def tempo_of(bpm: Any) -> str | None:
    value = _number(bpm)
    if value is None or value <= 0:
        return None
    return "slow" if value < SLOW_BPM else "fast" if value > FAST_BPM else "mid"


def length_of(seconds: Any) -> str | None:
    value = _number(seconds)
    if value is None or value <= 0:
        return None
    return "short" if value < SHORT_SECONDS else "long" if value > LONG_SECONDS else "mid"


def emotion_score(info: dict[str, Any], emotion: str) -> float:
    emotions = info.get("emotions")
    value = _number(emotions.get(emotion)) if isinstance(emotions, dict) else None
    return value if value is not None else 0.0


def _sort_key(link: str, info: dict[str, Any]) -> tuple[str, str, str]:
    return fold(str(info.get("title") or "")), fold(str(info.get("creator") or "")), link


def select(tracks: dict[str, dict[str, Any]], filters: dict[str, Any], playlists: dict[str, list[str]],
           downloaded: Iterable[str] = ()) -> list[str]:
    """Các link qua bộ lọc, theo thứ tự hiện. `filters` (khoá vắng / rỗng = không lọc):
    q (tìm trong tên bài + người sáng tác, mọi từ phải có, bỏ dấu / hoa thường), playlist (mã danh sách phát), style (mã phong cách),
    emotion (mã cảm xúc: điểm >= 0,5, xếp theo điểm giảm dần), tempo (slow / mid / fast), length (short / mid / long), downloaded (true).
    Không lọc cảm xúc thì xếp theo tên bài (bỏ dấu), rồi người sáng tác. Cùng luật: MusicLibrary.kt, tests/fixtures/music_library/cases.json."""
    words = fold(filters.get("q") or "").split()
    playlist = filters.get("playlist") or ""
    members = set(playlists.get(playlist) or []) if playlist else None
    style = filters.get("style") or ""
    emotion = filters.get("emotion") or ""
    tempo = filters.get("tempo") or ""
    length = filters.get("length") or ""
    only_saved = set(downloaded) if filters.get("downloaded") else None
    found: list[tuple[str, dict[str, Any]]] = []
    for link, info in tracks.items():
        if members is not None and link not in members:
            continue
        if only_saved is not None and link not in only_saved:
            continue
        if style and info.get("style") != style:
            continue
        if tempo and tempo_of(info.get("bpm")) != tempo:
            continue
        if length and length_of(info.get("duration")) != length:
            continue
        if emotion and emotion_score(info, emotion) < EMOTION_THRESHOLD:
            continue
        if words:
            haystack = fold(str(info.get("title") or "")) + " " + fold(str(info.get("creator") or ""))
            if not all(word in haystack for word in words):
                continue
        found.append((link, info))
    if emotion:
        found.sort(key=lambda item: (-emotion_score(item[1], emotion), *_sort_key(*item)))
    else:
        found.sort(key=lambda item: _sort_key(*item))
    return [link for link, _info in found]


def row(link: str, info: dict[str, Any]) -> dict[str, Any]:
    """Một dòng của danh sách: đủ để vẽ dòng và nghe thử (không kèm 13 điểm cảm xúc - chi tiết bài mới có)."""
    out: dict[str, Any] = {"link": link}
    for key in ROW_KEYS:
        value = info.get(key)
        if isinstance(value, (str, int, float)) and not isinstance(value, bool) and value != "":
            out[key] = value
    return out


def top_emotions(info: dict[str, Any], count: int = 3) -> list[str]:
    emotions = info.get("emotions") if isinstance(info.get("emotions"), dict) else {}
    ranked = sorted(((name, _number(value) or 0.0) for name, value in emotions.items()), key=lambda item: (-item[1], item[0]))
    return [name for name, _value in ranked[:count]]


def detail(link: str, info: dict[str, Any], playlists: list[dict[str, Any]]) -> dict[str, Any]:
    """Chi tiết bài: mọi trường hiện trên sheet chi tiết + 13 cảm xúc (xếp giảm dần) + các danh sách phát chứa bài."""
    out: dict[str, Any] = {"link": link}
    for key in DETAIL_KEYS:
        value = info.get(key)
        if value is not None and value != "":
            out[key] = value
    emotions = info.get("emotions") if isinstance(info.get("emotions"), dict) else {}
    out["emotions"] = [{"id": name, "score": round(_number(emotions.get(name)) or 0.0, 3)} for name in
                       sorted(emotions, key=lambda name: (-(_number(emotions.get(name)) or 0.0), name))]
    out["playlists"] = [{"id": item["id"], "name": item["name"]} for item in playlists if link in (item.get("tracks") or [])]
    return out


def why(scene_emotions: Any, track_emotions: Any, cosine: Callable[[Any, Any], float | None], count: int = 3) -> dict[str, Any] | None:
    """Khối "Vì sao bài này": cảm xúc máy đọc được ở đoạn (bộ chọn nhạc theo cảnh, plan["scenes"][i]["emotions"]) đặt cạnh cảm xúc của bài,
    `count` cảm xúc khớp nhất (tích điểm đoạn x điểm bài lớn nhất - đúng các số hạng của độ khớp cosine bộ chọn dùng: music_select.emotion_cosine).
    Đoạn không có cảm xúc (sách chọn theo danh sách phát, sách đóng gói) -> None: ẩn khối."""
    if not isinstance(scene_emotions, dict) or not isinstance(track_emotions, dict):
        return None
    fit = cosine(scene_emotions, track_emotions)
    if fit is None:
        return None
    pairs = []
    for name in sorted(set(scene_emotions) | set(track_emotions)):
        scene, track = max(0.0, _number(scene_emotions.get(name)) or 0.0), max(0.0, _number(track_emotions.get(name)) or 0.0)
        pairs.append({"id": name, "scene": round(scene, 3), "track": round(track, 3), "weight": scene * track})
    pairs.sort(key=lambda item: (-item["weight"], item["id"]))
    matches = [{key: item[key] for key in ("id", "scene", "track")} for item in pairs[:count] if item["weight"] > 0]
    return {"fit": round(fit, 3), "matches": matches}


def book_tracks(scenes: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """"Nhạc trong sách": các bài cuốn này dùng (gộp trùng, theo lần xuất hiện đầu), số đoạn mỗi bài, đoạn đầu tiên (để mở "Vì sao bài này")."""
    found: dict[str, dict[str, Any]] = {}
    for scene in scenes:
        link = scene.get("link") if isinstance(scene, dict) else None
        if not isinstance(link, str) or not link:
            continue
        entry = found.setdefault(link, {"link": link, "scenes": 0, "scene": scene.get("key")})
        entry["scenes"] += 1
    return list(found.values())


class SavedTracks:
    """Sổ bài người dùng lưu (saved.json: {"version": 1, "links": [...]}, mới lưu sau cùng)."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()
        self._links: list[str] | None = None

    def links(self) -> list[str]:
        with self._lock:
            return list(self._read_links())

    def _read_links(self) -> list[str]:
        """Read under the instance lock shared by all request threads, including writers."""
        if self._links is None:
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                links = data.get("links") if isinstance(data, dict) and data.get("version") == SAVED_VERSION else None
            except (OSError, ValueError):
                links = None
            self._links = [link for link in links or [] if isinstance(link, str) and link.startswith("https://")]
        return self._links

    def _write(self, links: list[str]) -> None:
        self._links = links
        with contextlib.suppress(OSError):
            atomic_write_json(self.path, {"version": SAVED_VERSION, "links": links})

    def add(self, links: Iterable[str]) -> list[str]:
        with self._lock:
            current = self._read_links()
            added = [link for link in dict.fromkeys(links) if link.startswith("https://") and link not in current]
            if added:
                self._write(current + added)
            return added

    def remove(self, links: Iterable[str]) -> list[str]:
        with self._lock:
            gone = set(links)
            current = self._read_links()
            kept = [link for link in current if link not in gone]
            if len(kept) != len(current):
                self._write(kept)
            return [link for link in current if link in gone]


class Downloads:
    """Hàng tải bài đã lưu: một luồng, lần lượt. `fetch(link, progress, cancel)` = App.music_track_file (ném lỗi khi hỏng,
    export_jobs.Cancelled khi huỷ). Trạng thái: đang chờ / đang tải (byte đã có, tổng) / hỏng (lời báo)."""

    def __init__(self, fetch: Callable[..., Path], cancelled: type[BaseException]) -> None:
        self._fetch = fetch
        self._cancelled = cancelled
        self._lock = threading.Lock()
        self._queue: deque[str] = deque()
        self._active: str | None = None
        self._progress: dict[str, tuple[int, int | None]] = {}
        self._failed: dict[str, str] = {}
        self._cancel: dict[str, threading.Event] = {}
        self._thread: threading.Thread | None = None

    def enqueue(self, links: Iterable[str]) -> None:
        with self._lock:
            for link in links:
                self._failed.pop(link, None)
                if link != self._active and link not in self._queue:
                    self._queue.append(link)
            if self._queue and self._thread is None:
                self._thread = threading.Thread(target=self._run, name="music-library-download", daemon=True)
                self._thread.start()

    def cancel(self, links: Iterable[str]) -> None:
        with self._lock:
            for link in links:
                with contextlib.suppress(ValueError):
                    self._queue.remove(link)
                self._failed.pop(link, None)
                event = self._cancel.get(link)
                if event is not None:
                    event.set()

    def state(self) -> dict[str, Any]:
        with self._lock:
            active = {}
            for link in [*([self._active] if self._active else []), *self._queue]:
                done, total = self._progress.get(link, (0, None))
                active[link] = {"done": done, "total": total}
            return {"active": active, "failed": dict(self._failed)}

    def busy(self) -> bool:
        with self._lock:
            return self._active is not None or bool(self._queue)

    def _run(self) -> None:
        while True:
            with self._lock:
                if not self._queue:
                    self._active = None
                    self._thread = None  # gỡ trong cùng khoá: enqueue sau đó mở luồng mới
                    return
                link = self._active = self._queue.popleft()
                cancel = self._cancel[link] = threading.Event()

            def progress(done: int, total: int | None, link: str = link) -> None:
                with self._lock:
                    self._progress[link] = (done, total)

            try:
                self._fetch(link, progress=progress, cancel=cancel)
            except self._cancelled:
                pass
            except Exception as exc:  # noqa: BLE001 - luồng nền: lời báo về sổ hỏng, bài sau vẫn tải
                message = getattr(exc, "message", None) or str(exc) or type(exc).__name__
                with self._lock:
                    self._failed[link] = str(message)
            finally:
                with self._lock:
                    self._progress.pop(link, None)
                    self._cancel.pop(link, None)
                    self._active = None
