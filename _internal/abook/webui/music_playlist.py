"""Nhạc nền cho sách nghe bằng "Nghe ngay" (docs/LISTEN_ANYTHING.md mục 4): sách chỉ có chữ không qua phân tích nên không có không
khí từng cảnh để chọn bài - người nghe chọn một DANH SÁCH PHÁT cho cả cuốn.

Lựa chọn nằm ở lớp sửa của người nghe (`edits.json`, `music.playlist` - book_edits.py) nên đi theo sách và đồng bộ như mọi sửa khác:
- mã một danh sách phát của danh mục (mục `playlists` của mục lục, dựng bằng LLM_Train/music/playlists.py - 12 danh sách cố
  định, mỗi danh sách là các link theo thứ tự đã trộn sẵn);
- `MINE` = "Nhạc của tôi" của máy đang phát (music_local.py), theo thứ tự trong kho;
- `OFF` = "off": người nghe tắt nhạc nền;
- không có khoá = TỰ CHỌN: máy chọn danh sách hợp với cuốn bằng luật từ khoá (`pick`, luật nằm ở `playlistPicker` của mục lục
  danh mục; chưa có mục lục thì dùng bản đóng kèm app assets/playlist_picker.json). Không chọn được thì không phát nhạc.

Trình phát chơi các bài nối nhau theo đúng thứ tự, qua mọi chương (không bắt đầu lại mỗi chương), chuyển mờ và nằm dưới giọng theo
đúng công thức Pha 4 (`music_plan.cue_gain_db`; giọng "Nghe ngay" được cân về -20 LUFS lúc phát như giọng Studio). Bản Kotlin:
Playlists.kt.
"""
from __future__ import annotations

import functools
import json
import math
import re
import unicodedata
from pathlib import Path
from typing import Any, Callable, Iterable

MINE = "mine"
OFF = "off"  # khớp _ID nhưng không phải mã danh sách: `music.playlist` = "off" là tắt
_ID = re.compile(r"[a-z0-9_]{1,40}")
TEXT_MAX = 200
BUNDLED_PICKER = Path(__file__).resolve().parent / "assets" / "playlist_picker.json"  # bản chép nguyên của genre_lexicon.json
PICKER_CHARS = 6000  # đầu vào của bộ chọn: tên sách + chừng ấy ký tự đầu phần truyện
MIN_CHAPTER = 1500
_FRONT = re.compile(r"^\s*(minh ho[aạ]|l[oờ]i b[aạ]t|m[uụ]c l[uụ]c|l[oờ]i t[aá]c gi[aả]|l[oờ]i d[iị]ch gi[aả]|illustration|afterword|"
                    r"table of contents|extra|ngo[aạ]i truy[eệ]n|side story)", re.IGNORECASE)
_WORD = re.compile(r"\w+")


def _text(value: Any) -> str:
    return " ".join(str(value).split())[:TEXT_MAX] if isinstance(value, str) else ""


def catalogue_playlists(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    """Mục `playlists` của mục lục danh mục, chỉ giữ mục đúng hình dạng: {id, name, description, minutes, tracks}. Mã lạ, trùng
    mã hay không có bài nào thì bỏ; link chỉ nhận https:// (máy chủ chỉ tải bài có trong danh mục, music_track_file)."""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in manifest.get("playlists") or []:
        if not isinstance(item, dict):
            continue
        playlist_id = item.get("id")
        if not isinstance(playlist_id, str) or not _ID.fullmatch(playlist_id) or playlist_id in (MINE, OFF) or playlist_id in seen:
            continue
        links = [link for link in item.get("tracks") or [] if isinstance(link, str) and link.startswith("https://")]
        if not links:
            continue
        seen.add(playlist_id)
        minutes = item.get("minutes")
        out.append({"id": playlist_id, "name": _text(item.get("name")) or playlist_id, "description": _text(item.get("description")),
                    "minutes": int(minutes) if isinstance(minutes, (int, float)) and not isinstance(minutes, bool) and minutes > 0 else 0,
                    "tracks": list(dict.fromkeys(links))})
    return out


def summaries(playlists: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Danh sách phát cho menu chọn (không kèm link): {id, name, description, minutes, count}."""
    return [{"id": item["id"], "name": item["name"], "description": item["description"], "minutes": item["minutes"],
             "count": len(item["tracks"])} for item in playlists]


def links_of(playlists: Iterable[dict[str, Any]], playlist_id: str) -> list[str]:
    """Các link của danh sách `playlist_id`, đúng thứ tự trộn sẵn; danh mục không (còn) có danh sách ấy thì rỗng."""
    return next((list(item["tracks"]) for item in playlists if item["id"] == playlist_id), [])


def queue(links: Iterable[str], tracks: dict[str, dict[str, Any]],
          available: Callable[[str], bool] | None = None) -> list[dict[str, Any]]:
    """Hàng bài để phát: [{link, duration}] theo đúng thứ tự `links`, bỏ bài máy này không dùng được (`available`) - danh sách
    vẫn chạy với các bài còn lại. `duration` (giây) lấy từ thông tin bài (`tracks[link]`); không biết thì None (trình phát dùng
    độ dài thật của file). Độ khuếch đại từng bài gắn sau bằng `music_plan.apply_gain`, cùng chỗ với nhạc theo cảnh."""
    out: list[dict[str, Any]] = []
    for link in links:
        if available is not None and not available(link):
            continue
        duration = (tracks.get(link) or {}).get("duration")
        ok = isinstance(duration, (int, float)) and not isinstance(duration, bool) and duration > 0
        out.append({"link": link, "duration": float(duration) if ok else None})
    return out


# ---- máy tự chọn danh sách ----------------------------------------------------------------------------------------------
# Bộ chọn từ khoá, không model (docs/MUSIC_RESEARCH.md "Nghe ngay: máy tự chọn danh sách phát"; bản tham chiếu LLM_Train/music/
# listen_genre/picker.py + prepare.py). Bản Kotlin: Playlists.pick - hai bên phải ra cùng mã và cùng điểm trên bộ ví dụ dùng chung
# tests/fixtures/playlist_picker/cases.json.
#
# Luật nằm ở dữ liệu `{version, cap, title_weight, min_score, default, order, playlists: {mã: {title, text, prior?}}}`: mục
# `playlistPicker` của mục lục danh mục khi nó hợp lệ, không thì bản đóng kèm app. Điểm danh sách = Σ trọng số x min(số lần gặp,
# cap) của các cụm trong thân truyện + title_weight x số cụm gặp trong tên + prior; điểm cao nhất thắng, hoà thì theo `order`, dưới
# `min_score` thì `default`. Tên so ở dạng BỎ DẤU (tên file hay mất dấu), thân so ở dạng CÓ DẤU ("ma" / "má" / "mà" khác nhau).


def _number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def valid_picker(picker: Any, ids: Iterable[str] | None = None) -> bool:
    """Luật chọn đúng hình dạng (kiểm chặt, không sửa): version nguyên; cap, title_weight, min_score là số; default, `order` không
    rỗng và `playlists` nói về các mã chữ; mỗi danh sách có `title` (danh sách chữ), `text` ({cụm: số}), `prior` (số) nếu có. `ids`
    cho thì default và mọi mã trong `order` / `playlists` phải nằm trong đó (danh sách của danh mục)."""
    if not isinstance(picker, dict) or not isinstance(picker.get("version"), int) or isinstance(picker.get("version"), bool):
        return False
    if not all(_number(picker.get(key)) for key in ("cap", "title_weight", "min_score")):
        return False
    order, playlists, default = picker.get("order"), picker.get("playlists"), picker.get("default")
    if not isinstance(order, list) or not order or not isinstance(playlists, dict) or not isinstance(default, str):
        return False
    if not all(isinstance(code, str) for code in order) or not all(isinstance(code, str) for code in playlists):
        return False
    for item in playlists.values():
        if not isinstance(item, dict):
            return False
        titles, text = item.get("title", []), item.get("text", {})
        if not isinstance(titles, list) or not all(isinstance(key, str) for key in titles):
            return False
        if not isinstance(text, dict) or not all(isinstance(key, str) and _number(weight) for key, weight in text.items()):
            return False
        if "prior" in item and not _number(item["prior"]):
            return False
    if ids is not None:
        known = set(ids)
        return default in known and set(order) <= known and set(playlists) <= known
    return True


@functools.lru_cache(maxsize=1)
def bundled_picker() -> dict[str, Any] | None:
    """Luật chọn đóng kèm app (assets/playlist_picker.json) - dùng khi chưa có mục lục danh mục (máy mới, chưa có mạng) hay mục lục
    mang luật hỏng. Không đọc được thì None (không tự chọn)."""
    try:
        picker = json.loads(BUNDLED_PICKER.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return picker if valid_picker(picker) else None


def usable_picker(manifest: dict[str, Any] | None) -> tuple[dict[str, Any] | None, str]:
    """(luật, nguồn) dùng cho máy này: `manifest["playlistPicker"]` nếu hợp lệ với các danh sách của chính mục lục ấy ("manifest"),
    không thì bản đóng kèm ("bundled"); không có cả hai thì (None, "none"). `manifest` None = chưa tải được danh mục."""
    if isinstance(manifest, dict):
        picker = manifest.get("playlistPicker")
        if valid_picker(picker, {item["id"] for item in catalogue_playlists(manifest)}):
            return picker, "manifest"
    bundled = bundled_picker()
    return (bundled, "bundled") if bundled is not None else (None, "none")


def words(text: str) -> str:
    """Các từ (`\\w+`, NFC, chữ thường) nối bằng một dấu cách, có dấu cách hai đầu - để tìm cụm nguyên từ bằng ` cụm `."""
    return " " + " ".join(_WORD.findall(unicodedata.normalize("NFC", text).lower())) + " "


def strip_marks(text: str) -> str:
    text = unicodedata.normalize("NFD", text.replace("đ", "d").replace("Đ", "D"))
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn")


def _squash(text: str) -> str:
    return "\n".join(" ".join(line.split()) for line in text.splitlines() if line.strip())


def picker_body(chapters: Iterable[str]) -> str:
    """Thân truyện cho bộ chọn: bỏ chương phụ ngắn (< MIN_CHAPTER ký tự) và chương mở bằng minh hoạ / lời bạt / mục lục, mỗi dòng
    gộp khoảng trắng, lấy PICKER_CHARS ký tự đầu. `chapters` đọc lười - đủ chữ rồi thì không đọc tiếp chương sau."""
    parts: list[str] = []
    total = 0
    for chapter in chapters:
        text = chapter.strip()
        if len(text) < MIN_CHAPTER or _FRONT.match(text.splitlines()[0]):
            continue
        parts.append(_squash(text))
        total += len(parts[-1]) + 1
        if total > PICKER_CHARS:
            break
    return "\n".join(parts)[:PICKER_CHARS]


def pick_scores(picker: dict[str, Any] | None, title: str, chapters: Iterable[str]) -> dict[str, float] | None:
    """Điểm từng danh sách của `picker` cho cuốn tên `title` với các chương `chapters` (theo thứ tự); luật hỏng thì None."""
    if not valid_picker(picker):
        return None
    body_words, title_words = words(picker_body(chapters)), words(strip_marks(title))
    out: dict[str, float] = {}
    for code, item in picker["playlists"].items():
        text = {words(key).strip(): float(weight) for key, weight in item.get("text", {}).items()}
        titles = [words(strip_marks(key)).strip() for key in item.get("title", [])]
        score = sum(weight * min(body_words.count(f" {key} "), picker["cap"]) for key, weight in text.items())
        score += picker["title_weight"] * sum(1 for key in titles if title_words.count(f" {key} "))
        out[code] = score + float(item.get("prior", 0.0))
    return out


def pick(picker: dict[str, Any] | None, title: str, chapters: Iterable[str]) -> str | None:
    """Mã danh sách hợp với cuốn: điểm cao nhất (hoà thì theo `order`), dưới `min_score` thì `default`. Luật hỏng thì None."""
    scores = pick_scores(picker, title, chapters)
    if scores is None:
        return None
    order = picker["order"]
    best = max(order, key=lambda code: (scores.get(code, 0.0), -order.index(code)))
    return best if scores.get(best, 0.0) >= picker["min_score"] else picker["default"]
