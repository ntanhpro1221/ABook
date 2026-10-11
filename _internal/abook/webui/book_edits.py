"""Lớp SỬA của người nghe trên một cuốn KHÔNG có xưởng - docs/EDITING.md, docs/ABOOK_FILE_FORMAT.md (phiên bản 4).

Một cuốn nhập từ file `.abook` (máy tính hay điện thoại) không có sổ dự án: lớp sách (book.json, cast.json, scripts/, nhạc,
audio, bìa) là của người làm sách và KHÔNG BAO GIỜ bị sửa tại chỗ. Người nghe vẫn đổi được tên sách, bìa, tên nhân vật, tên
chương, nhạc nền (bật/tắt, mức, im lặng một đoạn) - những thứ "áp ngay", không cần thu lại gì. Chúng nằm ở `edits.json` (+
`edits/cover.jpg`) trong thư mục sách; mọi nơi đọc lớp sách (packages.listen/cast/script, nhạc, bìa) đi qua đây để thấy bản đã
sửa. Cuốn CÓ xưởng (dự án) giữ nguyên các file riêng đang dùng (studio_title.json, cover.jpg, names.json,
music_overrides.json, chapter_titles.json) - không bao giờ có edits.json.

`edits.json` là dữ liệu của người lạ (đi theo file `.abook` phiên bản 4): `validate` chặt - đúng khoá, đúng kiểu, có trần cỡ
và độ dài, không ký tự điều khiển - và file sai thì bị từ chối cả file. Không mang tên máy hay tên người nào.

    {"format": "abook-edits", "version": 1,
     "title": "Tên mới",                                        (không có khoá = giữ tên sách)
     "author": "Tên tác giả",                                   (không có khoá = giữ tác giả của sách; "" = sách không rõ tác giả)
     "cover": null | {"color": "#aabbcc", "width": 800, "height": 1200, "version": 1759400000},
                                                                (không có khoá = giữ bìa; null = bỏ bìa, dùng bìa vẽ từ tên;
                                                                 đối tượng = dùng edits/cover.jpg)
     "characters": {"<name trong cast.json>": "<tên hiện>"},
     "chapters": {"<mã chương>": {"title": "Chương 12", "subtitle": "Hồi kết"}},   (mỗi trường tuỳ chọn)
     "skip": {"<mã chương>": ["Dịch: Nhóm Lục Bình"]},          (dòng người nghe chọn bỏ khỏi phần đọc - gợi ý dòng ghi công của bộ
                                                                 nhập sách; màn đọc và đọc to bỏ qua, chữ của sách KHÔNG đổi)
     "readings": {"Haruto": "Ha-ru-tô"},                         (cách đọc riêng của "Nghe ngay": chữ hiện -> chữ đọc, mỗi khoá MỘT từ
                                                                 hay cụm 2..6 từ liền nhau, khớp cả từ, phân biệt hoa thường - readaloud/readings.py;
                                                                 chỉ giọng đọc đổi, chữ của sách KHÔNG đổi)
     "music": {"enabled": false, "levelDb": -24.0, "silenced": ["<mã chương>:<mili giây đầu mốc>"],
               "pins": {"<mã chương>:<mili giây đầu mốc>": "local:<sha1>"},          (đổi bài một mốc sang bài "Nhạc của tôi")
               "tracks": {"<sha1>": {"ext": "mp3", "title": "...", "creator": "...", "duration": 184.0, "lufs": -14.2}},
               "playlist": "fantasy_calm" | "mine" | "off"},            (nhạc nền của sách KHÔNG có nhạc của người làm sách -
                                                                 sách chỉ có chữ nghe bằng "Nghe ngay": một danh sách phát
                                                                 của danh mục, "mine" = "Nhạc của tôi" của máy đang phát,
                                                                 "off" = tắt; không có khoá = máy tự chọn - music_playlist.py)
                                                                (thông tin các bài được ghim, đúng những sha1 mà `pins` nhắc tới;
                                                                 file nằm ở music/<sha1>.<đuôi> như bài của người làm sách)
     "wishes": {...}}                                           (ý muốn chờ Studio - book_wishes.py: cách đọc tên, người nói,
                                                                 cách đọc câu, giọng, thu lại; KHÔNG BAO GIỜ áp vào sách)

Bộ ví dụ dùng chung với bản Kotlin (BookEdits.kt): tests/fixtures/book_edits/.
"""
from __future__ import annotations

import copy
import json
import os
import re
import shutil
import threading
import time
import unicodedata
from pathlib import Path
from typing import Any, Callable, Iterable

from .. import listener_overrides
from .. import names as renames
from ..io_utils import atomic_write_bytes
from ..readaloud import readings as book_readings
from . import covers, music_plan, store

EDITS_FILE = "edits.json"
EDITS_COVER = "edits/cover.jpg"
FORMAT = "abook-edits"
VERSION = 1
MAX_EDITS_BYTES = 1024 * 1024
MAX_COVER_BYTES = 8 * 1024 * 1024
TITLE_MAX = store.TITLE_MAX
AUTHOR_MAX = TITLE_MAX  # tác giả cùng trần với tên sách
NAME_MAX = renames.MAX_NAME
MAX_CHARACTERS = 2000
MAX_CHAPTERS = 5000
MAX_SILENCED = 5000
MAX_PINS = 5000
MAX_SKIP_LINES = 20  # dòng bỏ khỏi phần đọc, mỗi chương
SKIP_LINE_MAX = 300
TRACK_TEXT_MAX = 200  # tên bài / nghệ sĩ trong thẻ file nhạc (music_local._TAG_MAX)
MAX_READINGS = 2000  # cách đọc riêng của một cuốn
READING_WORD_MAX = NAME_MAX  # chữ hiện của một cách đọc (một từ)
READING_SPOKEN_MAX = 200  # chữ đọc
LEVEL_RANGE = (-40.0, -6.0)
_TOP_KEYS = {"format", "version", "title", "author", "cover", "characters", "chapters", "skip", "readings", "music", "wishes"}
_COVER_KEYS = {"color", "width", "height", "version"}
_MUSIC_KEYS = {"enabled", "levelDb", "silenced", "pins", "tracks", "playlist"}
_TRACK_KEYS = {"ext", "title", "creator", "duration", "lufs"}
_LOCAL_LINK = re.compile(r"local:[0-9a-f]{40}")
_PLAYLIST = re.compile(r"[a-z0-9_]{1,40}")  # mã danh sách phát của danh mục (music_playlist.MINE = "Nhạc của tôi")
_SHA1 = re.compile(r"[0-9a-f]{40}")
_CHAPTER_KEYS = {"title", "subtitle"}
_CHAPTER_ID = re.compile(r"\d{1,9}")
_CUE_KEY = re.compile(r"\d{1,9}:\d{1,12}")
_COLOR = re.compile(r"#[0-9a-f]{6}")
_LOCK = threading.RLock()


class EditsError(ValueError):
    """Sửa không hợp lệ, hay `edits.json` không dùng được - câu chữ để người dùng đọc."""


# ---- làm sạch chữ người gõ (cùng luật máy chủ: store.clean_title, names.clean) ----------------------------------


def clean_text(value: Any, limit: int) -> str:
    """Chữ người gõ: NFC, ký tự điều khiển thành dấu cách, gộp khoảng trắng, cắt ở `limit` ký tự (điểm mã)."""
    text = "".join(" " if unicodedata.category(char)[0] == "C" else char for char in unicodedata.normalize("NFC", str(value or "")))
    return " ".join(text.split())[:limit].strip()


def _is_clean(text: str, limit: int) -> bool:
    """Chữ đã ở dạng `clean_text` ghi ra: không ký tự điều khiển, không khoảng trắng nào ngoài dấu cách đơn, không dấu cách
    đầu/cuối/kép, không dài quá `limit`. `validate` KHÔNG sửa chữ của người lạ - gặp chữ chưa sạch là từ chối (hai bản
    cài Python và Kotlin không phải đồng ý về mọi cách Unicode gộp khoảng trắng)."""
    if len(text) > limit or text != text.strip(" ") or "  " in text:
        return False
    return not any(unicodedata.category(char)[0] == "C" or (char.isspace() and char != " ") for char in text)


# ---- đọc / kiểm / ghi -------------------------------------------------------------------------------------------


def empty() -> dict[str, Any]:
    return {"format": FORMAT, "version": VERSION}


def is_empty(edits: dict[str, Any]) -> bool:
    return count(edits) == 0


def count_applied(edits: dict[str, Any]) -> int:
    """Số thay đổi "áp ngay" người nghe đã làm: tên sách, tác giả, bìa, mỗi tên nhân vật, mỗi chương đổi tên, mỗi cách đọc riêng, bật/tắt nhạc, mức
    nhạc, mỗi đoạn nhạc im lặng, mỗi đoạn nhạc đổi sang bài của người nghe, danh sách phát đã chọn. Không kể ý muốn chờ Studio (`wishes`) -
    chúng chưa áp vào đâu cả."""
    music = edits.get("music") or {}
    return (("title" in edits) + ("author" in edits) + ("cover" in edits) + len(edits.get("characters") or {}) + len(edits.get("chapters") or {})
            + len({line for lines in (edits.get("skip") or {}).values() for line in lines})  # một dòng bỏ ở trăm chương: một thay đổi
            + len(edits.get("readings") or {})
            + ("enabled" in music) + ("levelDb" in music) + len(music.get("silenced") or []) + len(music.get("pins") or {})
            + ("playlist" in music))


def count_wishes(edits: dict[str, Any]) -> int:
    """Số ý muốn chờ Studio (book_wishes.count)."""
    from . import book_wishes

    return book_wishes.count(edits.get("wishes"))


def count(edits: dict[str, Any]) -> int:
    """Số thay đổi người nghe đã làm (cho dòng "N thay đổi" và việc mời lưu): thay đổi áp ngay + ý muốn chờ Studio."""
    return count_applied(edits) + count_wishes(edits)


def _number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value == value and abs(value) != float("inf")


def validate(raw: Any) -> dict[str, Any]:
    """`edits.json` đã đọc -> dạng chuẩn; sai thì `EditsError`. Khoá lạ, kiểu sai, chữ chưa sạch, quá trần: từ chối."""
    if not isinstance(raw, dict) or set(raw) - _TOP_KEYS:
        raise EditsError("Phần sửa của sách có mục lạ.")
    if raw.get("format") != FORMAT or raw.get("version") != VERSION or isinstance(raw.get("version"), bool):
        raise EditsError("Phần sửa của sách không đúng định dạng hay mới hơn app - hãy cập nhật app.")
    out = empty()
    if "title" in raw:
        title = raw["title"]
        if not isinstance(title, str) or not title or not _is_clean(title, TITLE_MAX):
            raise EditsError("Tên sách trong phần sửa không hợp lệ.")
        out["title"] = title
    if "author" in raw:
        author = raw["author"]
        if not isinstance(author, str) or not _is_clean(author, AUTHOR_MAX):  # trống được: sách không rõ tác giả
            raise EditsError("Tác giả trong phần sửa không hợp lệ.")
        out["author"] = author
    if "cover" in raw:
        out["cover"] = _validate_cover(raw["cover"])
    if "characters" in raw:
        people = raw["characters"]
        if not isinstance(people, dict) or len(people) > MAX_CHARACTERS:
            raise EditsError("Phần đổi tên nhân vật không hợp lệ hay quá dài.")
        for name, shown in people.items():
            if not isinstance(name, str) or not name or len(name) > 200 or _has_control(name):
                raise EditsError("Tên nhân vật trong phần sửa không hợp lệ.")
            if not isinstance(shown, str) or not shown or not _is_clean(shown, NAME_MAX):
                raise EditsError("Tên hiện của một nhân vật trong phần sửa không hợp lệ.")
        out["characters"] = dict(people)
    if "chapters" in raw:
        chapters = raw["chapters"]
        if not isinstance(chapters, dict) or len(chapters) > MAX_CHAPTERS:
            raise EditsError("Phần đổi tên chương không hợp lệ hay quá dài.")
        kept: dict[str, dict[str, str]] = {}
        for key, entry in chapters.items():
            if not isinstance(key, str) or not _CHAPTER_ID.fullmatch(key) or not isinstance(entry, dict) or not entry \
                    or set(entry) - _CHAPTER_KEYS:
                raise EditsError("Một mục đổi tên chương không hợp lệ.")
            for field, text in entry.items():
                if not isinstance(text, str) or not _is_clean(text, TITLE_MAX) or (field == "title" and not text):
                    raise EditsError("Tên một chương trong phần sửa không hợp lệ.")
            kept[key] = dict(entry)
        out["chapters"] = kept
    if "skip" in raw:
        out["skip"] = _validate_skip(raw["skip"])
    if "readings" in raw:
        out["readings"] = validate_readings(raw["readings"])
    if "music" in raw:
        out["music"] = _validate_music(raw["music"])
    if "wishes" in raw:
        from . import book_wishes

        out["wishes"] = book_wishes.validate(raw["wishes"])
    return out


def _has_control(text: str) -> bool:
    return any(unicodedata.category(char)[0] == "C" for char in text)


def _validate_cover(cover: Any) -> dict[str, Any] | None:
    if cover is None:
        return None
    if not isinstance(cover, dict) or set(cover) - _COVER_KEYS:
        raise EditsError("Ảnh bìa trong phần sửa không hợp lệ.")
    color, width, height, version = cover.get("color", ""), cover.get("width", 0), cover.get("height", 0), cover.get("version", 0)
    if (not isinstance(color, str) or (color and not _COLOR.fullmatch(color))
            or any(not isinstance(item, int) or isinstance(item, bool) or not 0 <= item <= 10**10 for item in (width, height, version))
            or width > 20_000 or height > 20_000):
        raise EditsError("Ảnh bìa trong phần sửa không hợp lệ.")
    return {"color": color, "width": width, "height": height, "version": version}


def _validate_skip(skip: Any) -> dict[str, list[str]]:
    if not isinstance(skip, dict) or len(skip) > MAX_CHAPTERS:
        raise EditsError("Phần bỏ dòng khỏi phần đọc không hợp lệ hay quá dài.")
    out: dict[str, list[str]] = {}
    for key, lines in skip.items():
        if (not isinstance(key, str) or not _CHAPTER_ID.fullmatch(key) or not isinstance(lines, list) or not lines
                or len(lines) > MAX_SKIP_LINES or len(set(lines)) != len(lines)
                or any(not isinstance(line, str) or not line or not _is_clean(line, SKIP_LINE_MAX) for line in lines)):
            raise EditsError("Một dòng bỏ khỏi phần đọc trong phần sửa không hợp lệ.")
        out[key] = sorted(lines)
    return out


def validate_readings(readings: Any) -> dict[str, str]:
    """`readings` {chữ hiện: chữ đọc}: chữ hiện là MỘT từ hay một cụm 2..6 từ liền nhau đã sạch (không dấu câu hai đầu từng từ, NFC - `readings.is_key`),
    chữ đọc sạch, không rỗng, khác chữ hiện. Dùng cả cho cách đọc gửi kèm lần "Nghe thử" (chưa lưu)."""
    if not isinstance(readings, dict) or not readings or len(readings) > MAX_READINGS:
        raise EditsError("Phần cách đọc riêng không hợp lệ hay quá dài.")
    for shown, spoken in readings.items():
        if (not isinstance(shown, str) or not _is_clean(shown, READING_WORD_MAX) or not book_readings.is_key(shown)
                or not isinstance(spoken, str) or not spoken or not _is_clean(spoken, READING_SPOKEN_MAX) or spoken == shown):
            raise EditsError("Một cách đọc riêng trong phần sửa không hợp lệ.")
    return {shown: readings[shown] for shown in sorted(readings)}


def _validate_music(music: Any) -> dict[str, Any]:
    if not isinstance(music, dict) or not music or set(music) - _MUSIC_KEYS:
        raise EditsError("Phần sửa nhạc nền không hợp lệ.")
    out: dict[str, Any] = {}
    if "enabled" in music:
        if not isinstance(music["enabled"], bool):
            raise EditsError("Phần sửa nhạc nền không hợp lệ.")
        out["enabled"] = music["enabled"]
    if "levelDb" in music:
        level = music["levelDb"]
        if not _number(level) or not LEVEL_RANGE[0] <= level <= LEVEL_RANGE[1]:
            raise EditsError("Mức nhạc nền trong phần sửa nằm ngoài khoảng cho phép.")
        out["levelDb"] = float(level)
    if "playlist" in music:
        playlist = music["playlist"]
        if not isinstance(playlist, str) or not _PLAYLIST.fullmatch(playlist):
            raise EditsError("Danh sách nhạc nền trong phần sửa không hợp lệ.")
        out["playlist"] = playlist
    if "silenced" in music:
        silenced = music["silenced"]
        if (not isinstance(silenced, list) or len(silenced) > MAX_SILENCED or len(set(silenced)) != len(silenced)
                or any(not isinstance(key, str) or not _CUE_KEY.fullmatch(key) for key in silenced)):
            raise EditsError("Danh sách đoạn nhạc im lặng trong phần sửa không hợp lệ.")
        out["silenced"] = sorted(silenced)
    pins: dict[str, str] = {}
    if "pins" in music:
        pins = music["pins"]
        if (not isinstance(pins, dict) or len(pins) > MAX_PINS
                or any(not isinstance(key, str) or not _CUE_KEY.fullmatch(key) or not isinstance(link, str)
                       or not _LOCAL_LINK.fullmatch(link) for key, link in pins.items())):
            raise EditsError("Danh sách đoạn nhạc đã đổi bài trong phần sửa không hợp lệ.")
        out["pins"] = {key: pins[key] for key in sorted(pins)}
    wanted = {link[len(music_plan.LOCAL_PREFIX):] for link in pins.values()}
    if "tracks" in music or wanted:
        tracks = music.get("tracks")
        if not isinstance(tracks, dict) or set(tracks) != wanted:
            raise EditsError("Nhạc đã chọn trong phần sửa không khớp với các đoạn đổi bài.")
        out["tracks"] = {sha: _validate_track(tracks[sha]) for sha in sorted(tracks)}
    return out


def _validate_track(entry: Any) -> dict[str, Any]:
    """Thông tin một bài người nghe đã chọn: đuôi file thật (đúng danh sách của music_plan), tên bài và nghệ sĩ nếu có, độ dài
    và độ to đo từ chính file. Không có giấy phép / ghi công: ABook không nói gì ngoài tên + nghệ sĩ có sẵn trong file."""
    if not isinstance(entry, dict) or set(entry) - _TRACK_KEYS or entry.get("ext") not in music_plan.TRACK_EXTENSIONS:
        raise EditsError("Thông tin một bài nhạc trong phần sửa không hợp lệ.")
    out: dict[str, Any] = {"ext": entry["ext"]}
    for key in ("title", "creator"):
        if key in entry:
            text = entry[key]
            if not isinstance(text, str) or not text or not _is_clean(text, TRACK_TEXT_MAX):
                raise EditsError("Thông tin một bài nhạc trong phần sửa không hợp lệ.")
            out[key] = text
    for key, low, high in (("duration", 0.0, 1e6), ("lufs", -100.0, 20.0)):
        if key in entry:
            value = entry[key]
            if not _number(value) or not low <= value <= high or (key == "duration" and value <= 0):
                raise EditsError("Thông tin một bài nhạc trong phần sửa không hợp lệ.")
            out[key] = float(value)
    return out


def parse(data: bytes) -> dict[str, Any]:
    """Byte của `edits.json` -> dạng chuẩn (`validate`); quá cỡ hay không phải JSON: `EditsError`."""
    if len(data) > MAX_EDITS_BYTES:
        raise EditsError("Phần sửa của sách quá lớn.")
    try:
        raw = json.loads(data.decode("utf-8"), parse_constant=_reject_constant)
    except (UnicodeDecodeError, ValueError) as exc:
        raise EditsError("Phần sửa của sách bị hỏng.") from exc
    return validate(raw)


def _reject_constant(name: str) -> Any:
    raise ValueError(name)


def dump(edits: dict[str, Any]) -> bytes:
    """Byte ghi ra `edits.json`: khoá xếp cố định, UTF-8, xuống dòng LF - cùng nội dung thì cùng byte."""
    return (json.dumps(_ordered(edits), ensure_ascii=False, indent=1) + "\n").encode("utf-8")


def _ordered(edits: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {"format": FORMAT, "version": VERSION}
    for key in ("title", "author", "cover"):
        if key in edits:
            out[key] = edits[key]
    if edits.get("characters"):
        out["characters"] = dict(sorted(edits["characters"].items()))
    if edits.get("chapters"):
        out["chapters"] = {key: edits["chapters"][key] for key in sorted(edits["chapters"], key=int)}
    if edits.get("skip"):
        out["skip"] = {key: sorted(edits["skip"][key]) for key in sorted(edits["skip"], key=int)}
    if edits.get("readings"):
        out["readings"] = dict(sorted(edits["readings"].items()))
    if edits.get("music"):
        music = edits["music"]
        out["music"] = {key: music[key] for key in ("enabled", "levelDb", "playlist", "silenced") if key in music}
        if music.get("pins"):
            out["music"]["pins"] = {key: music["pins"][key] for key in sorted(music["pins"])}
            out["music"]["tracks"] = {sha: {key: music["tracks"][sha][key] for key in ("ext", "title", "creator", "duration", "lufs")
                                            if key in music["tracks"][sha]} for sha in sorted(music["tracks"])}
    if edits.get("wishes"):
        from . import book_wishes

        out["wishes"] = book_wishes.ordered(edits["wishes"])
    return out


def load(folder: Path) -> dict[str, Any]:
    """Phần sửa của một cuốn đã nhập; không có file hay file hỏng thì rỗng (thư viện không được hỏng vì nó)."""
    try:
        return parse((Path(folder) / EDITS_FILE).read_bytes())
    except (OSError, EditsError):
        return empty()


def stamp(folder: Path) -> tuple[int, int, int, int]:
    """Dấu thay đổi của lớp sửa (cho bộ đệm): mốc + cỡ của edits.json và của bìa sửa."""
    out = []
    for name in (EDITS_FILE, EDITS_COVER):
        try:
            info = (Path(folder) / name).stat()
            out += [info.st_mtime_ns, info.st_size]
        except OSError:
            out += [0, 0]
    return (out[0], out[1], out[2], out[3])


def save(folder: Path, edits: dict[str, Any]) -> None:
    """Ghi `edits.json` nguyên tử; không còn thay đổi nào thì xoá cả file lẫn bìa sửa."""
    folder = Path(folder)
    with _LOCK:
        if is_empty(edits):
            (folder / EDITS_FILE).unlink(missing_ok=True)
            (folder / EDITS_COVER).unlink(missing_ok=True)
            return
        atomic_write_bytes(folder / EDITS_FILE, dump(edits))
        if not isinstance(edits.get("cover"), dict):
            (folder / EDITS_COVER).unlink(missing_ok=True)


# ---- hợp hai lớp sửa (nhập lại cùng một cuốn) ----------------------------------------------------------------------


def merge(local: dict[str, Any], incoming: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Hợp phần sửa đã có trên máy (`local`) với phần sửa trong file vừa mở (`incoming`): khoá nào cả hai cùng có thì
    THẮNG BÊN MÁY NÀY (người nghe đã làm nó ở đây), còn lại lấy cả hai. Nhạc im lặng: hợp (không có "bỏ im lặng" để thắng).
    Trả (kết quả, báo cáo): {"adopted": số thay đổi lấy từ file, "kept": số thay đổi của máy này, "conflicts": số khoá hai
    bên khác nhau (đã theo máy này), "cover": "local" | "incoming" | None - bìa sửa lấy từ đâu}."""
    out, report, _clashes = merge_clashes(local, incoming)
    return out, report


def merge_clashes(local: dict[str, Any], incoming: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    """`merge` kèm danh sách từng khoá hai bên khác nhau: [{kind, key, kept, lost}] (giá trị bên máy này được giữ / giá trị bên kia thua;
    bìa và nhạc không mang giá trị). Số phần tử bằng `conflicts` của báo cáo."""
    out = empty()
    conflicts = 0
    clashes: list[dict[str, Any]] = []

    def clash(kind: str, key: str, kept: Any = None, lost: Any = None) -> None:
        clashes.append({"kind": kind, "key": key, "kept": kept, "lost": lost})

    for key in ("title", "author", "cover"):
        if key in local:
            out[key] = copy.deepcopy(local[key])
            conflicts += key in incoming and incoming[key] != local[key]
            if key in incoming and incoming[key] != local[key]:
                clash(key, "", *((local[key], incoming[key]) if key != "cover" else ()))
        elif key in incoming:
            out[key] = copy.deepcopy(incoming[key])
    people = {**(incoming.get("characters") or {}), **(local.get("characters") or {})}
    for name, shown in (local.get("characters") or {}).items():
        if name in (incoming.get("characters") or {}) and incoming["characters"][name] != shown:
            conflicts += 1
            clash("character", name, shown, incoming["characters"][name])
    if people:
        out["characters"] = people
    chapters: dict[str, dict[str, str]] = {}
    for key in {*(incoming.get("chapters") or {}), *(local.get("chapters") or {})}:
        theirs, ours = (incoming.get("chapters") or {}).get(key, {}), (local.get("chapters") or {}).get(key, {})
        for field in ours:
            if field in theirs and theirs[field] != ours[field]:
                conflicts += 1
                clash("chapter", key, ours[field], theirs[field])
        chapters[key] = {**theirs, **ours}
    if chapters:
        out["chapters"] = chapters
    # Dòng bỏ khỏi phần đọc: hợp (không có "đọc lại dòng này" để thắng), như nhạc im lặng.
    local_skip, incoming_skip = local.get("skip") or {}, incoming.get("skip") or {}
    skip = {key: sorted({*incoming_skip.get(key, []), *local_skip.get(key, [])}) for key in {*incoming_skip, *local_skip}}
    if skip:
        out["skip"] = skip
    # Cách đọc riêng: như tên nhân vật - từ nào cả hai cùng đặt thì cách của máy này thắng.
    readings = {**(incoming.get("readings") or {}), **(local.get("readings") or {})}
    for shown, spoken in (local.get("readings") or {}).items():
        if shown in (incoming.get("readings") or {}) and incoming["readings"][shown] != spoken:
            conflicts += 1
            clash("reading", shown, spoken, incoming["readings"][shown])
    if readings:
        out["readings"] = dict(sorted(readings.items()))
    music: dict[str, Any] = {}
    local_music, incoming_music = local.get("music") or {}, incoming.get("music") or {}
    for field in ("enabled", "levelDb", "playlist"):
        if field in local_music:
            music[field] = local_music[field]
            if field in incoming_music and incoming_music[field] != local_music[field]:
                conflicts += 1
                clash("music", field)
        elif field in incoming_music:
            music[field] = incoming_music[field]
    silenced = sorted({*(local_music.get("silenced") or []), *(incoming_music.get("silenced") or [])})
    if silenced:
        music["silenced"] = silenced
    # Đổi bài: mốc nào cả hai cùng đổi thì bài của máy này thắng; thông tin bài chỉ giữ cho các bài còn được ghim.
    pins = {**(incoming_music.get("pins") or {}), **(local_music.get("pins") or {})}
    for key, link in (local_music.get("pins") or {}).items():
        if key in (incoming_music.get("pins") or {}) and incoming_music["pins"][key] != link:
            conflicts += 1
            clash("music", "pins")
    if pins:
        wanted = {link[len(music_plan.LOCAL_PREFIX):] for link in pins.values()}
        known = {**(incoming_music.get("tracks") or {}), **(local_music.get("tracks") or {})}
        music["pins"] = {key: pins[key] for key in sorted(pins)}
        music["tracks"] = {sha: copy.deepcopy(known[sha]) for sha in sorted(wanted)}
    if music:
        out["music"] = music
    from . import book_wishes

    wishes, wish_conflicts = book_wishes.merge(local.get("wishes"), incoming.get("wishes"))
    conflicts += wish_conflicts
    clashes.extend({"kind": "wish", "key": "", "kept": None, "lost": None} for _ in range(wish_conflicts))
    if wishes:
        out["wishes"] = wishes
    cover = None
    if isinstance(out.get("cover"), dict):
        cover = "local" if isinstance(local.get("cover"), dict) else "incoming"
    taken = count(out) - count(local)
    return out, {"adopted": max(0, taken), "kept": count(local), "conflicts": conflicts, "cover": cover}, clashes


# ---- lớp phủ lên lớp sách ---------------------------------------------------------------------------------------


def cue_key(chapter_id: Any, start: float) -> str:
    """Khoá một mốc nhạc của sách đã đóng gói: "<mã chương>:<mili giây đầu mốc>"."""
    return f"{int(chapter_id)}:{int(round(float(start) * 1000))}"


def apply_chapter(chapter: dict[str, Any], edit: dict[str, str] | None) -> dict[str, Any]:
    """Một mục `chapters` của book.json sau khi đổi tên: `title`, `subtitle`, `fullTitle`."""
    if not edit:
        return chapter
    name, subtitle = store.apply_chapter_title(str(chapter.get("title") or ""), str(chapter.get("subtitle") or ""), edit)
    return {**chapter, "title": name, "subtitle": subtitle, "fullTitle": store.chapter_full_title(name, subtitle)}


def apply_manifest(book: dict[str, Any], edits: dict[str, Any]) -> dict[str, Any]:
    """`book.json` (lớp sách) -> bản người nghe thấy: tên sách (và tên các phần của cả bộ), tác giả, tên chương, bìa, nhạc."""
    if is_empty(edits):
        return book
    out = copy.copy(book)
    if "title" in edits:
        out["title"] = edits["title"]
        if isinstance(book.get("parts"), list):
            from .. import continuation

            out["parts"] = [{**part, "title": continuation.continued_title(edits["title"], part["part"])}
                            if isinstance(part, dict) and isinstance(part.get("part"), int) else part
                            for part in book["parts"]]
    if "author" in edits:
        if edits["author"]:
            out["author"] = edits["author"]
        else:
            out.pop("author", None)  # đã bỏ tên tác giả: sách không rõ tác giả
    renamed, skip = edits.get("chapters") or {}, edits.get("skip") or {}
    if (renamed or skip) and isinstance(book.get("chapters"), list):
        # `skip` của chương: dòng người nghe bỏ khỏi phần đọc (màn đọc và đọc to - listen/textScript.ts `withoutLines`).
        out["chapters"] = [{**apply_chapter(chapter, renamed.get(str(chapter.get("id")))),
                            **({"skip": skip[str(chapter.get("id"))]} if str(chapter.get("id")) in skip else {})}
                           if isinstance(chapter, dict) else chapter for chapter in book["chapters"]]
    if "cover" in edits:
        cover = edits["cover"]
        out["cover"] = None if cover is None else {"file": EDITS_COVER, **cover}
    if "music" in edits or book.get("music") is not None:
        music = apply_music(book.get("music"), edits)
        if music is None:
            out.pop("music", None)
        else:
            out["music"] = music
    return out


def shared_cast(cast: dict[str, Any]) -> dict[str, Any]:
    """`cast.json` khi rời máy này (file `.abook` / `.abookproj`, đồng bộ sang máy đã ghép): không dấu "đang chờ đổi giọng"
    (`pendingVoice`) hay "chờ gộp vào X" (`mergedInto`) - đó là ý muốn chưa áp của máy này, chưa thành giọng hay người nói nào;
    máy nhận tự dựng dấu của nó từ lớp sửa nó có (`apply_cast`). Cũng không số câu kể "chờ thu lại" (`redo`) - việc của Studio, người
    nghe chỉ có bản đã thu (soát a26 L5). Mọi đường xuất / đồng bộ dàn nhân vật đi qua đây."""
    out = copy.deepcopy(cast)
    if isinstance(out.get("narrator"), dict):
        out["narrator"].pop("redo", None)
    for kind in ("characters", "extras", "carried"):
        for person in out.get(kind) or []:
            if isinstance(person, dict):
                if "pendingVoice" in person:
                    person["pendingVoice"] = None  # như cast.json của dự án: khoá có, không đang chờ gì
                person.pop("mergedInto", None)
    return out


def apply_cast(cast: dict[str, Any], edits: dict[str, Any], base: dict[str, Any] | None = None) -> dict[str, Any]:
    """`cast.json` -> bản người nghe thấy: tên nhân vật đã đổi (`displayName`, và `originalName` khi khác tên gốc), và
    `firstChapter` theo tên chương mới; dấu ý muốn chờ Studio: đổi giọng (`pendingVoice`), "Gộp vào…" (`mergedInto`).
    `base`: book.json lớp sách (để biết tên chương gốc)."""
    from . import book_wishes

    people = edits.get("characters") or {}
    chapter_names = _chapter_renames(base, edits)
    waiting = book_wishes.pending_voices(edits.get("wishes"))
    merging = (edits.get("wishes") or {}).get(book_wishes.ALIASES)
    if not people and not chapter_names and not waiting and not merging:
        return cast
    out = copy.deepcopy(cast)
    for kind in ("characters", "extras", "carried"):
        for person in out.get(kind) or []:
            if not isinstance(person, dict):
                continue
            name = person.get("name")
            if isinstance(name, str) and listener_overrides.character_key(name) in waiting:
                # Ý muốn đổi giọng/giới chờ Studio: chỉ một dấu "đang chờ" - giọng và audio của người ấy giữ nguyên.
                person["pendingVoice"] = waiting[listener_overrides.character_key(name)]
            if name in people:
                original = person.get("originalName") or person.get("displayName") or name
                person["displayName"] = people[name]
                if people[name] != original:
                    person["originalName"] = original
                else:
                    person.pop("originalName", None)
            if person.get("firstChapter") in chapter_names:
                person["firstChapter"] = chapter_names[person["firstChapter"]]
    book_wishes.mark_merges([person for kind in ("characters", "extras", "carried") for person in out.get(kind) or []
                             if isinstance(person, dict) and isinstance(person.get("name"), str)], edits.get("wishes"))
    return out


def _chapter_renames(base: dict[str, Any] | None, edits: dict[str, Any]) -> dict[str, str]:
    """{tên chương cũ (`title`): tên mới} - `cast.json` ghi chương đầu tiên người ấy nói bằng `title` của chương."""
    renamed = edits.get("chapters") or {}
    if not renamed or not base:
        return {}
    out: dict[str, str] = {}
    for chapter in base.get("chapters") or []:
        edit = renamed.get(str(chapter.get("id"))) if isinstance(chapter, dict) else None
        if edit and "title" in edit and chapter.get("title"):
            out[str(chapter["title"])] = edit["title"]
    return out


def apply_script(script: dict[str, Any], cast: dict[str, Any], edits: dict[str, Any], chapter: dict[str, Any] | None) -> dict[str, Any]:
    """`scripts/<n>.json` -> bản người nghe thấy: tên người nói theo tên nhân vật mới, tên chương. `cast`: cast.json GỐC
    (câu ghi người nói bằng `displayName` lúc đóng gói)."""
    people = edits.get("characters") or {}
    swap = {str(person["displayName"]): people[person["name"]]
            for kind in ("characters", "extras", "carried") for person in cast.get(kind) or []
            if isinstance(person, dict) and person.get("name") in people and person.get("displayName")}
    edit = (edits.get("chapters") or {}).get(str(script.get("chapterId")))
    if not any(shown != old for old, shown in swap.items()) and not edit:
        return script
    out = copy.copy(script)
    if swap and isinstance(script.get("segments"), list):
        out["segments"] = [{**segment, "speaker": swap.get(segment.get("speaker"), segment.get("speaker"))}
                           if isinstance(segment, dict) and segment.get("speaker") in swap else segment
                           for segment in script["segments"]]
    if edit and chapter is not None:
        out["title"] = apply_chapter(chapter, edit)["fullTitle"]
    return out


def _track_number(info: Any, key: str) -> float | None:
    value = info.get(key) if isinstance(info, dict) else None
    return float(value) if _number(value) else None


def pinned_name(sha: str, entry: dict[str, Any]) -> str:
    """Tên file trong sách của một bài người nghe đã ghim: `music/<sha1>.<đuôi>`, đúng chỗ bài của người làm sách nằm."""
    return f"music/{sha}.{entry['ext']}"


def pinned_files(edits: dict[str, Any]) -> list[str]:
    """Tên file (`music/<sha1>.<đuôi>`) của mọi bài người nghe đã ghim trong phần sửa."""
    return [pinned_name(sha, entry) for sha, entry in sorted(((edits.get("music") or {}).get("tracks") or {}).items())]


def _pinned_track(link: str, name: str, entry: dict[str, Any]) -> dict[str, Any]:
    """Mục `music.tracks[tên]` của một bài đã ghim, như bài người làm sách tự nhập (music_plan.package): file, link, tên, nghệ
    sĩ, độ to - không giấy phép."""
    info: dict[str, Any] = {"file": name, "link": link}
    for key in ("title", "creator", "lufs"):
        if key in entry:
            info[key] = entry[key]
    return info


def apply_music(music: dict[str, Any] | None, edits: dict[str, Any]) -> dict[str, Any] | None:
    """Mục `music` của book.json sau khi người nghe sửa: mốc đổi sang bài của họ (`pins`: bài nằm ở music/<sha1>.<đuôi>, gắn
    vào `tracks`), tắt hết, mức khác (tính lại `gainDb` từng mốc bằng đúng công thức của người làm sách -
    music_plan.cue_gain_db), bỏ các mốc đã cho im lặng."""
    if music is None:
        return None
    changes = edits.get("music") or {}
    if not changes:
        return music
    out = copy.deepcopy(music)
    if not isinstance(out.get("tracks"), dict):
        out["tracks"] = {}
    tracks = out["tracks"]
    pins, shown = changes.get("pins") or {}, changes.get("tracks") or {}
    base_level = out["levelDb"] if _number(out.get("levelDb")) else music_plan.DEFAULT_LEVEL_DB
    level = changes.get("levelDb", base_level)
    for chapter_id, cues in (out.get("chapters") or {}).items():
        for cue in cues:
            link = pins.get(cue_key(chapter_id, cue.get("start", 0)))
            if link is None:
                continue
            sha = link[len(music_plan.LOCAL_PREFIX):]
            name = pinned_name(sha, shown[sha])
            tracks.setdefault(name, _pinned_track(link, name, shown[sha]))
            cue["track"] = name
            info = tracks[name]
            cue["gainDb"] = music_plan.cue_gain_db(level, _track_number(info, "lufs"), _track_number(info, "speechBand"))
    if "levelDb" in changes:
        out["levelDb"] = changes["levelDb"]
        for cues in (out.get("chapters") or {}).values():
            for cue in cues:
                info = tracks.get(cue.get("track"))
                cue["gainDb"] = music_plan.cue_gain_db(changes["levelDb"], _track_number(info, "lufs"),
                                                       _track_number(info, "speechBand"))
    if changes.get("enabled") is False:
        out["chapters"] = {}
        return out
    silenced = set(changes.get("silenced") or [])
    if silenced:
        kept: dict[str, list[dict[str, Any]]] = {}
        for chapter_id, cues in (out.get("chapters") or {}).items():
            rest = [cue for cue in cues if cue_key(chapter_id, cue.get("start", 0)) not in silenced]
            if rest:
                kept[chapter_id] = rest
        out["chapters"] = kept
    return out


def music_view(book: dict[str, Any], edits: dict[str, Any]) -> dict[str, Any]:
    """Màn "Nhạc nền" của sách đóng gói: bật/tắt, mức, và từng mốc (đã im lặng hay chưa) - kể cả mốc đã im lặng, để bật lại.
    `book`: book.json GỐC. Sách không có nhạc: `hasMusic` false. `playlist`: danh sách phát người nghe đã chọn (khi có)."""
    music = book.get("music") if isinstance(book.get("music"), dict) else None
    changes = edits.get("music") or {}
    base_level = float(music["levelDb"]) if music and _number(music.get("levelDb")) else music_plan.DEFAULT_LEVEL_DB
    silenced = set(changes.get("silenced") or [])
    pins = changes.get("pins") or {}
    cues: list[dict[str, Any]] = []
    tracks = music.get("tracks") if music and isinstance(music.get("tracks"), dict) else {}
    for chapter in book.get("chapters") or []:
        if not isinstance(chapter, dict):
            continue
        chapter_id = str(chapter.get("id"))
        shown = apply_chapter(chapter, (edits.get("chapters") or {}).get(chapter_id))
        for cue in ((music or {}).get("chapters") or {}).get(chapter_id) or []:
            info = tracks.get(cue.get("track")) or {}
            key = cue_key(chapter_id, cue.get("start", 0))
            pinned = pins.get(key)
            if pinned is not None:  # bài người nghe đã chọn thay bài của người làm sách
                info = (changes.get("tracks") or {}).get(pinned[len(music_plan.LOCAL_PREFIX):]) or {}
            cues.append({"key": key, "chapterId": int(chapter_id), "chapter": shown.get("fullTitle") or shown.get("title") or "",
                         "start": float(cue.get("start", 0)), "end": float(cue.get("end", 0)),
                         "title": str(info.get("title") or ""), "creator": str(info.get("creator") or ""),
                         "silenced": key in silenced, **({"pinned": True} if pinned is not None else {})})
    return {"package": True, "hasMusic": bool(cues), "enabled": changes.get("enabled", True),
            "levelDb": changes.get("levelDb", base_level), "defaultLevelDb": base_level, "cues": cues,
            **({"playlist": changes["playlist"]} if "playlist" in changes else {})}


# ---- bìa --------------------------------------------------------------------------------------------------------


def cover_file(folder: Path) -> Path | None:
    """File ảnh bìa người nghe thấy: bìa sửa, hay bìa của sách; None khi đã bỏ bìa hoặc sách không có."""
    folder = Path(folder)
    edits = load(folder)
    if "cover" in edits:
        path = folder / EDITS_COVER
        return path if isinstance(edits["cover"], dict) and path.is_file() else None
    return covers.cover_file(folder)


def cover_view(folder: Path, book_id: str) -> dict[str, Any] | None:
    """Phần `cover` trong JSON sách của giao diện máy tính, theo bìa người nghe thấy."""
    folder = Path(folder)
    edits = load(folder)
    if "cover" in edits:
        cover = edits["cover"]
        if not isinstance(cover, dict) or not (folder / EDITS_COVER).is_file():
            return None
        return {**cover, "url": f"/media/books/{book_id}/cover?v={cover['version']}"}
    return covers.cover_view(folder, book_id)


# ---- sửa (ghi) ---------------------------------------------------------------------------------------------------


def _base(folder: Path) -> dict[str, Any]:
    from . import packages

    return packages.manifest(folder)


def _base_cast(folder: Path) -> dict[str, Any]:
    from . import packages

    return packages.raw_cast(folder)


TOO_BIG = "Quá nhiều thay đổi đang chờ trong cuốn này - hãy lưu, áp bớt vào dự án rồi làm tiếp."


def _write(folder: Path, edits: dict[str, Any]) -> dict[str, Any]:
    if len(dump(edits)) > MAX_EDITS_BYTES:
        raise EditsError(TOO_BIG)  # file quá cỡ thì lần đọc sau từ chối cả file: không ghi ra thứ chính mình không đọc lại được
    save(folder, edits)
    return edits


def set_title(folder: Path, title: str) -> str:
    """Đặt lại tên sách (người nghe). Tên rỗng: `EditsError`. Trả tên đã làm sạch."""
    cleaned = clean_text(title, TITLE_MAX)
    if not cleaned:
        raise EditsError("Tên sách không được để trống")
    with _LOCK:
        edits = load(folder)
        base = str(_base(folder).get("title") or "")
        if cleaned == base:
            edits.pop("title", None)
        else:
            edits["title"] = cleaned
        _write(folder, edits)
    return cleaned


def set_author(folder: Path, author: str) -> str:
    """Đặt lại tác giả (người nghe). Tên trống là "không rõ tác giả" (sách vốn có tác giả thì ghi `""`; vốn không có thì không có gì để sửa).
    Trả tên đã làm sạch."""
    cleaned = clean_text(author, AUTHOR_MAX)
    with _LOCK:
        edits = load(folder)
        base = clean_text(_base(folder).get("author"), AUTHOR_MAX)
        if cleaned == base:
            edits.pop("author", None)
        else:
            edits["author"] = cleaned
        _write(folder, edits)
    return cleaned


def set_cover(folder: Path, raw: bytes, *, now: int) -> dict[str, Any]:
    """Đặt ảnh bìa từ byte ảnh thô: chuẩn hoá như bìa dự án (`covers.render_cover`), cất ở edits/cover.jpg. `now`: số làm
    phiên bản (giây) để trình duyệt không giữ ảnh cũ. Trả mô tả bìa {color, width, height, version}."""
    try:
        jpeg, meta = covers.render_cover(raw)
    except covers.CoverError as exc:
        raise EditsError(str(exc)) from exc
    with _LOCK:
        edits = load(folder)
        edits["cover"] = {"color": meta["color"], "width": meta["width"], "height": meta["height"], "version": int(now)}
        atomic_write_bytes(Path(folder) / EDITS_COVER, jpeg)
        _write(folder, edits)
    return edits["cover"]


def remove_cover(folder: Path) -> None:
    """Bỏ bìa: sách dùng bìa vẽ từ tên (kể cả khi lớp sách có ảnh bìa). Sách vốn không có bìa thì không có gì để bỏ:
    không ghi thay đổi nào (và bìa đã sửa trước đó, nếu có, được bỏ đi)."""
    with _LOCK:
        edits = load(folder)
        if covers.cover_file(Path(folder)) is None:
            edits.pop("cover", None)
        else:
            edits["cover"] = None
        (Path(folder) / EDITS_COVER).unlink(missing_ok=True)
        _write(folder, edits)


def set_character_name(folder: Path, character: str, name: str) -> dict[str, Any]:
    """Đổi tên hiện của một nhân vật (như tab Nhân vật của Studio): tên rỗng hay đúng tên gốc là trở về tên gốc.
    Trả đúng hình dạng của `POST /characters/rename`: {character, name, original, renamed}."""
    character = str(character).strip()[:200]
    cast = _base_cast(folder)
    person = next((item for kind in ("characters", "extras", "carried") for item in cast.get(kind) or []
                   if isinstance(item, dict) and item.get("name") == character), None)
    if not character or character.upper() == "NARRATOR" or person is None:
        raise EditsError("Không có nhân vật này trong sách")
    base_shown = str(person.get("displayName") or character)
    original = str(person.get("originalName") or base_shown)
    wanted = clean_text(name, NAME_MAX) or original
    with _LOCK:
        edits = load(folder)
        people = dict(edits.get("characters") or {})
        if wanted == base_shown:
            people.pop(character, None)
        else:
            people[character] = wanted
        if people:
            edits["characters"] = people
        else:
            edits.pop("characters", None)
        _write(folder, edits)
    shown = people.get(character, base_shown)
    return {"character": character, "name": shown, "original": original, "renamed": shown != original}


def set_skip_line(folder: Path, chapter_ids: Iterable[int], line: str, skip: bool) -> dict[str, list[str]]:
    """Bỏ (`skip`) hay đọc lại dòng `line` trong phần đọc của các chương `chapter_ids` - gợi ý dòng ghi công mà người nghe chấp nhận
    (một dòng hay lặp ở đầu cả trăm chương: một lần bấm). Chỉ là biến đổi để đọc: chữ của sách không đổi, bỏ chọn là đọc lại như
    cũ. Trả {mã chương: các dòng đang bỏ} của các chương ấy."""
    known = {item.get("id") for item in _base(folder).get("chapters") or [] if isinstance(item, dict)}
    wanted = sorted({int(chapter_id) for chapter_id in chapter_ids})
    if not wanted or any(chapter_id not in known for chapter_id in wanted):
        raise EditsError("Không có chương này trong sách")
    clean = clean_text(line, SKIP_LINE_MAX)
    if not clean:
        raise EditsError("Dòng cần bỏ trống.")
    out: dict[str, list[str]] = {}
    with _LOCK:
        edits = load(folder)
        skipped = dict(edits.get("skip") or {})
        for chapter_id in wanted:
            key = str(chapter_id)
            lines = set(skipped.get(key) or [])
            if skip:
                if clean not in lines and len(lines) >= MAX_SKIP_LINES:
                    raise EditsError(f"Mỗi chương bỏ được tối đa {MAX_SKIP_LINES} dòng.")
                lines.add(clean)
            else:
                lines.discard(clean)
            if lines:
                skipped[key] = sorted(lines)
            else:
                skipped.pop(key, None)
            out[key] = sorted(lines)
        if skipped:
            edits["skip"] = skipped
        else:
            edits.pop("skip", None)
        _write(folder, edits)
    return out


def readings_view(edits: dict[str, Any]) -> dict[str, Any]:
    """Danh sách "Cách đọc tên" của hộp sửa sách: [{surface, spoken}] theo thứ tự chữ hiện."""
    return {"readings": [{"surface": shown, "spoken": spoken} for shown, spoken in sorted((edits.get("readings") or {}).items())]}


def clean_reading(shown: Any, spoken: Any) -> tuple[str, str]:
    """Chữ người gõ ở "Đọc từ này là…" -> (chữ hiện, chữ đọc) đã làm sạch; chữ hiện không phải một từ hay cụm 2..6 từ liền nhau: `EditsError`. Chữ đọc rỗng là bỏ."""
    word = clean_text(shown, READING_WORD_MAX)
    if not book_readings.is_key(word):
        start, end = book_readings.core_span(word)
        word = word[start:end]  # người chạm vào "Haruto," hay “Hạ Vy,” - cách đọc đặt cho chính chữ ấy, không dính dấu câu hai đầu
    if not word or not book_readings.is_key(word):
        raise EditsError("Chỉ đặt được cách đọc cho một từ hay tối đa 6 từ liền nhau, không có dấu câu ở giữa.")
    return word, clean_text(spoken, READING_SPOKEN_MAX)


def set_reading(folder: Path, shown: Any, spoken: Any) -> dict[str, Any]:
    """Đặt (hay bỏ - chữ đọc rỗng / đúng chữ hiện) cách đọc riêng của một từ cho cả cuốn: chỉ giọng đọc của "Nghe ngay" đổi, chữ của
    sách không đổi. Trả `readings_view`."""
    word, said = clean_reading(shown, spoken)
    with _LOCK:
        edits = load(folder)
        readings = dict(edits.get("readings") or {})
        if not said or said == word:
            readings.pop(word, None)
        else:
            if word not in readings and len(readings) >= MAX_READINGS:
                raise EditsError(f"Mỗi cuốn đặt được tối đa {MAX_READINGS} cách đọc.")
            readings[word] = said
        if readings:
            edits["readings"] = dict(sorted(readings.items()))
        else:
            edits.pop("readings", None)
        _write(folder, edits)
    return readings_view(edits)


def set_chapter_title(folder: Path, chapter_id: int, title: str | None, subtitle: str | None = None) -> dict[str, Any]:
    """Đặt lại tên chương `chapter_id`: `title` (nhãn như "Chương 12") và/hoặc `subtitle` (tên phụ, "" là bỏ tên phụ).
    Cả hai trống (`title` rỗng/None và `subtitle` None) là trở về tên của người làm sách. Trả {chapterId, title, subtitle,
    fullTitle} đang hiện."""
    book = _base(folder)
    chapter = next((item for item in book.get("chapters") or [] if isinstance(item, dict) and item.get("id") == int(chapter_id)), None)
    if chapter is None:
        raise EditsError("Không có chương này trong sách")
    new_title = clean_text(title, TITLE_MAX) if title is not None else ""
    new_subtitle = clean_text(subtitle, TITLE_MAX) if subtitle is not None else None
    entry: dict[str, str] = {}
    if new_title and new_title != str(chapter.get("title") or ""):
        entry["title"] = new_title
    if new_subtitle is not None and new_subtitle != str(chapter.get("subtitle") or ""):
        entry["subtitle"] = new_subtitle
    with _LOCK:
        edits = load(folder)
        chapters = dict(edits.get("chapters") or {})
        if entry:
            chapters[str(int(chapter_id))] = entry
        else:
            chapters.pop(str(int(chapter_id)), None)
        if chapters:
            edits["chapters"] = chapters
        else:
            edits.pop("chapters", None)
        _write(folder, edits)
    shown = apply_chapter(chapter, entry)
    return {"chapterId": int(chapter_id), "title": shown.get("title", ""), "subtitle": shown.get("subtitle", ""),
            "fullTitle": shown.get("fullTitle") or shown.get("title", "")}


def base_links(book: dict[str, Any]) -> dict[str, str]:
    """{khoá mốc: link bài người làm sách đã gắn} của book.json GỐC."""
    music = book.get("music") if isinstance(book.get("music"), dict) else {}
    tracks = music.get("tracks") if isinstance(music.get("tracks"), dict) else {}
    out: dict[str, str] = {}
    for chapter_id, cues in (music.get("chapters") or {}).items():
        for cue in cues:
            link = (tracks.get(cue.get("track")) or {}).get("link")
            if isinstance(link, str):
                out[cue_key(chapter_id, cue.get("start", 0))] = link
    return out


def _track_entry(info: dict[str, Any], path: Path) -> dict[str, Any]:
    """Mục `music.tracks[<sha1>]` của phần sửa cho một bài trong kho "Nhạc của tôi" (`info`: music_local.LocalMusic.info; `path`:
    file của nó). Tên bài / nghệ sĩ làm sạch như mọi chữ người gõ; số đo ngoài khoảng cho phép thì bỏ."""
    extension = path.suffix.lower().lstrip(".")
    if extension not in music_plan.TRACK_EXTENSIONS:
        raise EditsError("Định dạng bài nhạc này chưa dùng được")
    entry: dict[str, Any] = {"ext": extension}
    for key in ("title", "creator"):
        text = clean_text(info.get(key), TRACK_TEXT_MAX)
        if text:
            entry[key] = text
    duration, lufs = info.get("duration"), info.get("lufs")
    if _number(duration) and 0 < duration <= 1e6:
        entry["duration"] = float(duration)
    if _number(lufs) and -100.0 <= lufs <= 20.0:
        entry["lufs"] = round(float(lufs), 2)
    return entry


def place(folder: Path, name: str, source: Path) -> None:
    """Chép file bài đã ghim vào thư mục sách (music/<sha1>.<đuôi>) - nguyên tử, không ghi đè file cùng cỡ đã có."""
    target = Path(folder).joinpath(*name.split("/"))
    if target.is_file() and target.stat().st_size == Path(source).stat().st_size:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    part = target.with_name(f".{target.name}.{os.getpid()}.part")
    try:
        shutil.copyfile(source, part)
        os.replace(part, target)
    except OSError as exc:
        raise EditsError(f"Không chép được bài nhạc vào sách ({exc.strerror or exc}).") from exc
    finally:
        part.unlink(missing_ok=True)


def _drop_unused(folder: Path, book: dict[str, Any], names: Iterable[str]) -> None:
    """Xoá file các bài đã bỏ ghim - trừ file nằm trong danh sách của lớp sách (không bao giờ đụng lớp sách)."""
    listed = (book.get("package") or {}).get("files") or {}
    for name in names:
        if name not in listed:
            Path(folder).joinpath(*name.split("/")).unlink(missing_ok=True)


def set_music(folder: Path, body: dict[str, Any],
              track: Callable[[str], tuple[dict[str, Any], Path] | None] | None = None) -> dict[str, Any]:
    """Sửa nhạc nền của sách đóng gói: `enabled`, `levelDb` (kẹp -40..-6 như `music_plan.write_overrides`), `silence`
    {khoá mốc: True/False}, `pins` {khoá mốc: "local:<sha1>" | null} (đổi bài một mốc sang bài trong "Nhạc của tôi", null = về
    bài người làm sách gắn), `playlist` (mã danh sách phát, "mine", "off" = tắt, hay null = bỏ lựa chọn để máy tự chọn - sách không
    có nhạc của người làm sách).
    `track(link)` -> (thông tin, file) của bài trong kho của máy này; file được chép vào thư mục sách
    (music/<sha1>.<đuôi>) để `repack` mang đi. Khoá lạ: `EditsError`. Trả `music_view`."""
    book = _base(folder)
    with _LOCK:
        edits = load(folder)
        music = dict(edits.get("music") or {})
        before = dict(music.get("tracks") or {})
        base_level = music_view(book, empty())["levelDb"]
        if "enabled" in body:
            if body["enabled"]:
                music.pop("enabled", None)
            else:
                music["enabled"] = False
        if "levelDb" in body:
            if not _number(body["levelDb"]):
                raise EditsError("Mức nhạc nền không hợp lệ")
            level = max(LEVEL_RANGE[0], min(LEVEL_RANGE[1], float(body["levelDb"])))
            if level == base_level:
                music.pop("levelDb", None)
            else:
                music["levelDb"] = level
        if "playlist" in body:
            playlist = body["playlist"]
            if not playlist:
                music.pop("playlist", None)
            elif isinstance(playlist, str) and _PLAYLIST.fullmatch(playlist):
                music["playlist"] = playlist
            else:
                raise EditsError("Không có danh sách nhạc nền này")
        if body.get("silence"):
            if not isinstance(body["silence"], dict):
                raise EditsError("Danh sách đoạn im lặng không hợp lệ")
            known = {cue["key"] for cue in music_view(book, empty())["cues"]}
            silenced = set(music.get("silenced") or [])
            for key, on in body["silence"].items():
                if str(key) not in known:
                    raise EditsError("Không có đoạn nhạc này trong sách")
                (silenced.add if on else silenced.discard)(str(key))
            if silenced:
                music["silenced"] = sorted(silenced)
            else:
                music.pop("silenced", None)
        placing: list[tuple[str, Path]] = []
        if body.get("pins"):
            if not isinstance(body["pins"], dict):
                raise EditsError("Phần sửa nhạc nền không hợp lệ.")
            known = {cue["key"] for cue in music_view(book, empty())["cues"]}
            original = base_links(book)
            pins, shown = dict(music.get("pins") or {}), dict(before)
            for key, link in body["pins"].items():
                key = str(key)
                if key not in known:
                    raise EditsError("Không có đoạn nhạc này trong sách")
                if not link:
                    pins.pop(key, None)
                    continue
                sha = music_plan.local_hash(link) if isinstance(link, str) else None
                if sha is None:
                    raise EditsError("Chỉ đổi được sang bài trong Nhạc của tôi")
                if link == original.get(key):
                    pins.pop(key, None)
                    continue
                if sha not in shown:
                    found = track(link) if track is not None else None
                    if found is None:
                        raise EditsError("Bài này không còn trong Nhạc của tôi")
                    info, path = found
                    shown[sha] = _track_entry(info, path)
                    placing.append((pinned_name(sha, shown[sha]), path))
                pins[key] = link
            used = {link[len(music_plan.LOCAL_PREFIX):] for link in pins.values()}
            if pins:
                music["pins"], music["tracks"] = pins, {sha: shown[sha] for sha in sorted(used)}
            else:
                music.pop("pins", None)
                music.pop("tracks", None)
        if music:
            edits["music"] = music
        else:
            edits.pop("music", None)
        for name, path in placing:
            place(folder, name, path)
        try:
            _write(folder, edits)
        except EditsError:
            _drop_unused(folder, book, [name for name, _ in placing])
            raise
        after = (edits.get("music") or {}).get("tracks") or {}
        _drop_unused(folder, book, [pinned_name(sha, before[sha]) for sha in before if sha not in after])
        return music_view(book, edits)


def subtract(folder: Path, sent: dict[str, Any], sent_cover: bytes | None) -> int:
    """Gỡ khỏi lớp sửa của `folder` đúng những gì đã gửi đi (`sent`, chụp lúc đóng gói; `sent_cover`: byte bìa đã gửi) - máy nhận
    đã giữ chúng. Khoá người dùng đổi tiếp SAU lúc chụp (giá trị khác) thì ở lại, lần sau gửi tiếp. Cùng luật với BookEdits.subtract
    (Kotlin). `skip` (dòng bỏ khỏi phần đọc), cách đọc riêng và danh sách phát nhạc ở lại: sách máy kia trả về không mang chúng (sở thích của
    người nghe ở máy này), gỡ đi là dòng đã bỏ lại hiện ra - `sent_marks` ghi nhớ chúng đã gửi. Trả số thay đổi còn lại."""
    folder = Path(folder)
    with _LOCK:
        edits = load(folder)
        before = pinned_files(edits)
        for key in ("title", "author", "cover"):
            if key not in sent or key not in edits or edits[key] != sent[key]:
                continue
            if key == "cover" and isinstance(sent[key], dict):
                mine = folder / EDITS_COVER
                if sent_cover is None or not mine.is_file() or mine.read_bytes() != sent_cover:
                    continue
            edits.pop(key)

        def remove_equal(mine: dict[str, Any] | None, theirs: dict[str, Any] | None) -> None:
            for key in list(mine or {}):
                if key in (theirs or {}) and mine[key] == theirs[key]:
                    del mine[key]

        remove_equal(edits.get("characters"), sent.get("characters"))
        for key in list(edits.get("chapters") or {}):
            remove_equal(edits["chapters"][key], (sent.get("chapters") or {}).get(key))
            if not edits["chapters"][key]:
                del edits["chapters"][key]
        music, sent_music = edits.get("music"), sent.get("music")
        if music and sent_music:
            for field in ("enabled", "levelDb"):  # `playlist` ở lại: máy kia không phản ánh nó trong sách, đây là nơi duy nhất nhạc được chọn
                if field in sent_music and field in music and music[field] == sent_music[field]:
                    del music[field]
            kept = [key for key in music.get("silenced") or [] if key not in set(sent_music.get("silenced") or [])]
            if kept:
                music["silenced"] = kept
            else:
                music.pop("silenced", None)
            remove_equal(music.get("pins"), sent_music.get("pins"))
            if music.get("pins"):
                used = {link[len(music_plan.LOCAL_PREFIX):] for link in music["pins"].values()}
                music["tracks"] = {sha: info for sha, info in (music.get("tracks") or {}).items() if sha in used}
            else:
                music.pop("pins", None)
                music.pop("tracks", None)
            if not music:
                edits.pop("music")
        wishes = edits.get("wishes")
        if wishes:
            from . import book_wishes

            sent_wishes = sent.get("wishes") or {}
            for section in book_wishes.SECTIONS:
                remove_equal(wishes.get(section), sent_wishes.get(section))
                if section in wishes and not wishes[section]:
                    del wishes[section]
            if book_wishes.ALIASES in wishes:
                gone_aliases = sent_wishes.get(book_wishes.ALIASES) or []
                wishes[book_wishes.ALIASES] = [item for item in wishes[book_wishes.ALIASES] if item not in gone_aliases]
                if not wishes[book_wishes.ALIASES]:
                    del wishes[book_wishes.ALIASES]
            if not wishes:
                edits.pop("wishes")
        for key in ("characters", "chapters", "skip"):
            if key in edits and not edits[key]:
                del edits[key]
        save(folder, edits)
        after = set(pinned_files(edits))
        dropped = [name for name in before if name not in after]
        if dropped:
            _drop_unused(folder, _base(folder), dropped)
        return count(edits)


def sent_marks(edits: dict[str, Any], previous: dict[str, Any] | None = None) -> dict[str, Any]:
    """Phần của lớp sửa vừa gửi đi mà `subtract` cố ý GIỮ lại: dòng bỏ khỏi phần đọc, cách đọc riêng và danh sách phát nhạc đã chọn. Máy kia
    nhận và giữ chúng, nhưng sách nó trả về không mang chúng, nên bỏ khỏi lớp sửa ở đây là người nghe mất dòng đã bỏ / cách đọc / nhạc vừa
    đặt. Ghi lại (cộng `previous`: các lần gửi trước) để `unmarked` không đếm chúng là chưa gửi."""
    previous = previous or {}
    out: dict[str, Any] = {}
    skip = {key: sorted({*(previous.get("skip") or {}).get(key, []), *(edits.get("skip") or {}).get(key, [])})
            for key in {*(previous.get("skip") or {}), *(edits.get("skip") or {})}}
    if skip:
        out["skip"] = {key: skip[key] for key in sorted(skip, key=int)}
    readings = {**(previous.get("readings") or {}), **(edits.get("readings") or {})}
    if readings:
        out["readings"] = readings
    music = dict(previous.get("music") or {})
    if "playlist" in (edits.get("music") or {}):
        music["playlist"] = edits["music"]["playlist"]
    if music:
        out["music"] = music
    return out


def unmarked(edits: dict[str, Any], marks: dict[str, Any]) -> dict[str, Any]:
    """`edits` trừ những gì `marks` (`sent_marks` các lần gửi trước) đã nói là máy kia có rồi - để đếm phần CHƯA gửi. Không sửa `edits`."""
    out = copy.deepcopy(edits)
    skip = out.get("skip") or {}
    for key in list(skip):
        skip[key] = [line for line in skip[key] if line not in (marks.get("skip") or {}).get(key, [])]
        if not skip[key]:
            del skip[key]
    if not skip:
        out.pop("skip", None)
    readings = out.get("readings") or {}
    for shown in list(readings):
        if shown in (marks.get("readings") or {}) and marks["readings"][shown] == readings[shown]:
            del readings[shown]
    if not readings:
        out.pop("readings", None)
    music = out.get("music") or {}
    if "playlist" in music and "playlist" in (marks.get("music") or {}) and marks["music"]["playlist"] == music["playlist"]:
        del music["playlist"]
    if not music:
        out.pop("music", None)
    return out


# ---- gỡ cái đã gửi: người nghe bỏ cách đọc / dòng bỏ / danh sách phát SAU khi đã gửi --------------------------------------
#
# Cách đọc, dòng bỏ khỏi phần đọc và danh sách phát ở lại lớp sửa sau khi gửi (`subtract`) nên `sent_marks` biết máy kia đã có chúng. Người
# nghe bỏ một trong số đó đi thì lớp sửa không còn nó - chỉ thiếu thôi thì máy kia vẫn giữ mãi. Hiệu giữa sổ `sent_marks` và lớp sửa hiện
# có là phần phải GỠ ở máy kia: gói gửi đi mang thêm mục `edits_removed.json` ({skip, readings, playlist} - kèm GIÁ TRỊ đã gửi), máy kia chỉ
# gỡ khi giá trị của nó còn đúng bằng giá trị ấy (`apply_removed`: không đè lên bản chính máy kia đã đổi khác). Cùng luật với BookEdits.kt.

REMOVED_FILE = "edits_removed.json"
_REMOVED_KEYS = {"skip", "readings", "playlist"}


def removed_marks(edits: dict[str, Any], marks: dict[str, Any]) -> dict[str, Any]:
    """Cái `marks` (`sent_marks`) nói máy kia đã có mà `edits` hiện không còn: {"skip": {mã chương: [dòng]}, "readings": {chữ hiện: chữ đọc},
    "playlist": mã}. Cách đọc còn đó nhưng đổi chữ đọc thì không phải gỡ (là thay đổi chưa gửi, `unmarked`)."""
    out: dict[str, Any] = {}
    skip = {key: lines for key, lines in
            ((key, [line for line in lines if line not in (edits.get("skip") or {}).get(key, [])])
             for key, lines in (marks.get("skip") or {}).items()) if lines}
    if skip:
        out["skip"] = {key: sorted(skip[key]) for key in sorted(skip, key=int)}
    readings = {shown: spoken for shown, spoken in (marks.get("readings") or {}).items() if shown not in (edits.get("readings") or {})}
    if readings:
        out["readings"] = dict(sorted(readings.items()))
    playlist = (marks.get("music") or {}).get("playlist")
    if playlist is not None and "playlist" not in (edits.get("music") or {}):
        out["playlist"] = playlist
    return out


def count_removed(removed: dict[str, Any]) -> int:
    """Số thay đổi trong `removed` (một dòng bỏ ở trăm chương là một)."""
    return (len({line for lines in (removed.get("skip") or {}).values() for line in lines}) + len(removed.get("readings") or {})
            + ("playlist" in removed))


def forget_marks(marks: dict[str, Any], removed: dict[str, Any]) -> dict[str, Any]:
    """`marks` trừ phần đã gỡ ở máy kia (`removed_marks`): sổ mới không còn nhắc tới chúng."""
    out = copy.deepcopy(marks)
    skip = out.get("skip") or {}
    for key in list(skip):
        skip[key] = [line for line in skip[key] if line not in (removed.get("skip") or {}).get(key, [])]
        if not skip[key]:
            del skip[key]
    if not skip:
        out.pop("skip", None)
    readings = out.get("readings") or {}
    for shown in (removed.get("readings") or {}):
        readings.pop(shown, None)
    if not readings:
        out.pop("readings", None)
    music = out.get("music") or {}
    if "playlist" in removed:
        music.pop("playlist", None)
    if not music:
        out.pop("music", None)
    return out


def validate_removed(raw: Any) -> dict[str, Any]:
    """`edits_removed.json` của người lạ: chỉ ba khoá, mỗi khoá cùng luật với lớp sửa (`skip`, `readings`, `playlist`)."""
    if not isinstance(raw, dict) or not raw or set(raw) - _REMOVED_KEYS:
        raise EditsError("Phần gỡ trong gói sửa không hợp lệ.")
    out: dict[str, Any] = {}
    if "skip" in raw:
        out["skip"] = _validate_skip(raw["skip"])
    if "readings" in raw:
        out["readings"] = validate_readings(raw["readings"])
    if "playlist" in raw:
        if not isinstance(raw["playlist"], str) or not _PLAYLIST.fullmatch(raw["playlist"]):
            raise EditsError("Phần gỡ trong gói sửa không hợp lệ.")
        out["playlist"] = raw["playlist"]
    return out


def dump_removed(removed: dict[str, Any]) -> bytes:
    """Byte ghi ra `edits_removed.json` (khoá xếp cố định, UTF-8, LF)."""
    ordered: dict[str, Any] = {}
    if removed.get("skip"):
        ordered["skip"] = {key: sorted(removed["skip"][key]) for key in sorted(removed["skip"], key=int)}
    if removed.get("readings"):
        ordered["readings"] = dict(sorted(removed["readings"].items()))
    if "playlist" in removed:
        ordered["playlist"] = removed["playlist"]
    return (json.dumps(ordered, ensure_ascii=False, indent=1) + "\n").encode("utf-8")


def parse_removed(data: bytes) -> dict[str, Any]:
    if len(data) > MAX_EDITS_BYTES:
        raise EditsError("Phần gỡ trong gói sửa quá lớn.")
    try:
        raw = json.loads(data.decode("utf-8"), parse_constant=_reject_constant)
    except (UnicodeDecodeError, ValueError) as exc:
        raise EditsError("Phần gỡ trong gói sửa bị hỏng.") from exc
    return validate_removed(raw)


def apply_removed(folder: Path, removed: dict[str, Any]) -> int:
    """Máy giữ sách gỡ khỏi lớp sửa của `folder` những gì người gửi đã bỏ (`removed_marks`), CHỈ khi giá trị ở đây còn đúng bằng giá trị
    người gửi nói (dòng bỏ: còn dòng ấy; cách đọc: còn đúng chữ đọc ấy; danh sách phát: còn đúng mã ấy) - đã đổi khác ở đây thì là bản của
    chính máy này, giữ nguyên. Trả số thay đổi đã gỡ."""
    folder = Path(folder)
    done: dict[str, Any] = {"skip": {}, "readings": {}}
    with _LOCK:
        edits = load(folder)
        skip = edits.get("skip") or {}
        for key, lines in (removed.get("skip") or {}).items():
            drop = [line for line in lines if line in skip.get(key, [])]
            if drop:
                done["skip"][key] = drop
                skip[key] = [line for line in skip[key] if line not in drop]
                if not skip[key]:
                    del skip[key]
        if not skip:
            edits.pop("skip", None)
        readings = edits.get("readings") or {}
        for shown, spoken in (removed.get("readings") or {}).items():
            if readings.get(shown) == spoken:
                done["readings"][shown] = spoken
                del readings[shown]
        if not readings:
            edits.pop("readings", None)
        music = edits.get("music") or {}
        if "playlist" in removed and music.get("playlist") == removed["playlist"]:
            done["playlist"] = removed["playlist"]
            del music["playlist"]
        if not music:
            edits.pop("music", None)
        gone = count_removed(done)
        if gone:
            save(folder, edits)
    return gone


def layer_files(folder: Path, edits: dict[str, Any]) -> dict[str, Path | bytes]:
    """Các mục của lớp sửa khi đóng vào một file zip (file `.abook` v4, hay gói gửi về máy giữ sách): `edits.json` (byte), bìa sửa
    và file các bài nhạc người nghe đã ghim (đường dẫn trong thư mục sách). Lớp sửa rỗng: không mục nào. Thiếu file: `EditsError`."""
    folder = Path(folder)
    if is_empty(edits):
        return {}
    files: dict[str, Path | bytes] = {EDITS_FILE: dump(edits)}
    if isinstance(edits.get("cover"), dict):
        files[EDITS_COVER] = folder / EDITS_COVER
        if not files[EDITS_COVER].is_file():
            raise EditsError("Thiếu ảnh bìa trong phần sửa của sách.")
    for name in pinned_files(edits):
        files[name] = folder.joinpath(*name.split("/"))
        if not files[name].is_file():
            raise EditsError("Thiếu file bài nhạc người nghe đã chọn trong thư mục sách.")
    return files


def clear(folder: Path) -> None:
    """Bỏ mọi thay đổi của người nghe: sách trở về đúng như người làm sách đã đóng gói (kể cả file các bài đã ghim)."""
    with _LOCK:
        pinned = pinned_files(load(folder))
        save(folder, empty())
        if pinned:
            _drop_unused(folder, _base(folder), pinned)


# ---- lớp sửa đóng trong một file zip (file `.abook` v4, hay gói điện thoại gửi về - edits_inbox.py) ----------------------

JPEG_MAGIC = bytes([0xFF, 0xD8, 0xFF])  # ảnh bìa trong lớp sửa phải là JPEG (render_cover luôn ghi JPEG)


def read_layer(archive: Any, names: set[str]) -> tuple[dict[str, Any], bytes | None]:
    """Đọc và KIỂM lớp sửa trong một file zip đã mở (`archive`: zipfile.ZipFile; `names`: tên các mục của nó): `edits.json` đúng
    giao ước (`parse` - sai thì từ chối cả file), mọi bài nhạc đã ghim có đủ file, và bìa sửa đi đôi với `cover` (có `cover` là
    đối tượng thì phải có edits/cover.jpg, và ngược lại), là JPEG, không quá cỡ. Trả (phần sửa, byte bìa hay None); sai: `EditsError`.
    Dùng chung cho file sách của người lạ (bookfile.py) và gói điện thoại gửi về - cùng một cổng kiểm."""
    edits = empty()
    if EDITS_FILE in names:
        if archive.getinfo(EDITS_FILE).file_size > MAX_EDITS_BYTES:
            raise EditsError("Phần sửa của sách quá lớn.")
        edits = parse(archive.read(EDITS_FILE))
    if any(name not in names for name in pinned_files(edits)):
        raise EditsError("File sách thiếu bài nhạc mà người nghe đã chọn.")
    has_cover = EDITS_COVER in names
    if has_cover != isinstance(edits.get("cover"), dict):
        raise EditsError("Ảnh bìa trong phần sửa của sách không khớp.")
    cover = None
    if has_cover:
        info = archive.getinfo(EDITS_COVER)
        if info.file_size > MAX_COVER_BYTES:
            raise EditsError("Ảnh bìa trong phần sửa của sách không dùng được.")
        with archive.open(info) as handle:
            cover = handle.read(MAX_COVER_BYTES + 1)
        if len(cover) > MAX_COVER_BYTES or cover[:3] != JPEG_MAGIC:
            raise EditsError("Ảnh bìa trong phần sửa của sách không dùng được.")
    return edits, cover


# ---- file `.abook` mang phần sửa theo ----------------------------------------------------------------------------


def adopt(folder: Path, incoming: dict[str, Any], cover: bytes | None,
          member: Callable[[str, Path], None] | None = None, *, incoming_wins: bool = False) -> dict[str, Any]:
    """Nhập lại một file sách ĐÃ có trên máy mà file mang phần sửa: hợp vào phần sửa của máy (`merge`: máy này thắng) -
    không giải nén lại audio. `cover`: byte edits/cover.jpg của file (nếu có). `member(tên, đích)`: chép một mục của file ra
    thư mục sách - cho file các bài nhạc người nghe đã ghim mà máy này chưa có. Trả báo cáo của `merge` (kèm "clashes" của `merge_clashes` khi `incoming_wins`).

    `incoming_wins`: phần sửa đến SAU thắng (máy khác gửi phần sửa của người nghe về cuốn này - sync.py): khoá cả hai cùng đặt
    thì lấy bản gửi tới, `conflicts` vẫn là số khoá hai bên khác nhau; `adopted` / `kept` / `cover` của báo cáo khi ấy tính từ phía bản gửi tới."""
    folder = Path(folder)
    with _LOCK:
        merged, report, clashes = merge_clashes(incoming, load(folder)) if incoming_wins else (*merge(load(folder), incoming), [])
        if report["cover"] == ("local" if incoming_wins else "incoming") and cover is not None:
            atomic_write_bytes(folder / EDITS_COVER, cover)
        if member is not None:
            for name in pinned_files(merged):
                target = folder.joinpath(*name.split("/"))
                if not target.is_file():
                    member(name, target)
        save(folder, merged)
    return {**report, "clashes": clashes} if incoming_wins else report


# ---- chủ máy sản xuất mở file đã sửa: áp vào dự án của mình --------------------------------------------------------

INCOMING_FILE = "edits_incoming.json"
INCOMING_COVER = "edits_incoming_cover.jpg"
INCOMING_MUSIC = "edits_incoming_music"  # bài nhạc người nghe ghim (<sha1>.<đuôi>) lấy từ file, chờ nhập vào kho của máy
PART_SPAN = 100_000  # bookfile.PART_SPAN (bookfile nhập module này, nên không nhập ngược ở đây)


def stash_incoming(project: Path, edits: dict[str, Any], cover: bytes | None,
                   member: Callable[[str, Path], None] | None = None) -> None:
    """File `.abook` mang lớp sửa vừa mở ra đúng dự án của máy này (nhận ra bằng audio): cất phần sửa cạnh dự án để người
    dùng quyết ("N thay đổi - áp vào dự án?") - không bao giờ tự áp. `member(tên, đích)`: chép một mục của file ra đĩa - cho
    các bài nhạc người nghe đã ghim (cất ở edits_incoming_music/, `fold` nhập chúng vào kho nhạc của máy)."""
    project = Path(project)
    with _LOCK:
        shutil.rmtree(project / INCOMING_MUSIC, ignore_errors=True)
        if member is not None:
            for name in pinned_files(edits):
                try:
                    member(name, project / INCOMING_MUSIC / name.rpartition("/")[2])
                except (KeyError, OSError):
                    pass  # thiếu trong file: `fold` bỏ qua ghim ấy và nói lý do
        atomic_write_bytes(project / INCOMING_FILE, dump(edits))
        if cover is not None:
            atomic_write_bytes(project / INCOMING_COVER, cover)
        else:
            (project / INCOMING_COVER).unlink(missing_ok=True)


def incoming(project: Path) -> dict[str, Any]:
    """Phần sửa đang chờ người dùng quyết ở một dự án (`stash_incoming`); không có thì rỗng."""
    try:
        return parse((Path(project) / INCOMING_FILE).read_bytes())
    except (OSError, EditsError):
        return empty()


def dismiss_incoming(project: Path) -> None:
    for name in (INCOMING_FILE, INCOMING_COVER):
        (Path(project) / name).unlink(missing_ok=True)
    shutil.rmtree(Path(project) / INCOMING_MUSIC, ignore_errors=True)


def _cue_scenes(plan: dict[str, Any] | None, chapter: int | None, millis: str) -> list[str]:
    """Khoá các đoạn (scene) của rãnh nhạc nằm trong mốc nhạc `<chương>:<mili giây đầu>` - chỗ "im lặng" và "ghim" của dự án
    được ghi (overrides theo đoạn, không theo mốc). Không có mốc ấy: rỗng."""
    if plan is None or chapter is None:
        return []
    cue = next((cue for cue in music_plan.chapter_cues(plan, chapter) if int(round(cue["start"] * 1000)) == int(millis)), None)
    return [scene["key"] for scene in plan.get("scenes") or []
            if cue is not None and scene.get("chapterId") == chapter and scene.get("link") == cue["link"]
            and float(scene["start"]) >= cue["start"] - 0.001 and float(scene["end"]) <= cue["end"] + 0.001]


def chapter_resolver(project: Path) -> Callable[[str], int | None]:
    """Mã chương trong phần sửa (số của sách đã đóng gói: `phần * PART_SPAN + chương`, phần 0 hay phần của dự án này) -> mã chương
    trong dự án; chương không còn trong dự án (hay thuộc phần khác): None."""
    from .. import continuation

    part = continuation.part_number(project)
    have = {chapter["id"] for chapter in store.chapters(project)}

    def local(key: str) -> int | None:
        number = int(key)
        return number % PART_SPAN if number // PART_SPAN in (0, part) and number % PART_SPAN in have else None

    return local


def fold(project: Path, my_music: Any = None) -> dict[str, Any]:
    """Áp phần sửa đang chờ (`incoming`, cất bởi `stash_incoming`) vào dự án rồi xoá phần chờ - `fold_edits` làm việc áp."""
    project = Path(project)
    cover_file = project / INCOMING_COVER
    try:
        cover = cover_file.read_bytes() if cover_file.is_file() else None
    except OSError:
        cover = None
    report = fold_edits(project, incoming(project), cover=cover, music_dir=project / INCOMING_MUSIC, my_music=my_music)
    dismiss_incoming(project)
    return report


def fold_edits(project: Path, edits: dict[str, Any], *, cover: bytes | None = None, music_dir: Path | None = None,
               my_music: Any = None) -> dict[str, Any]:
    """Áp phần sửa `edits` (đã `validate`) vào dự án bằng ĐÚNG những hàm Studio dùng: tên sách (store.set_display_title), bìa
    (covers), tên nhân vật (names.set_name), tên chương (store.set_chapter_title), nhạc nền (music_plan.write_overrides).
    Thay đổi nào không còn chỗ (nhân vật / chương không có trong dự án, nhạc chưa dựng; cách đọc riêng của "Nghe ngay" - dự án đọc tên ở
    Studio) thì bỏ qua và đếm. Ý muốn chờ Studio
    (`wishes`) thành yêu cầu của dự án qua `book_wishes.fold`, không áp. Trả {"applied", "skipped",
    "music": có đổi lựa chọn nhạc không (người gọi dựng lại rãnh nhạc), "requests": số ý muốn đã thành yêu cầu, "reasons":
    lý do từng bài ghim bị bỏ qua (chỉ có khi có)}. `cover`: byte ảnh bìa mới (khi `edits["cover"]` là đối tượng). Bài nhạc
    người nghe ghim (`music.pins`) nằm ở `music_dir/<sha1>.<đuôi>`, được nhập vào kho "Nhạc của tôi" của máy này (`my_music`:
    music_local.LocalMusic) rồi ghim vào đoạn tương ứng; thiếu file / không có kho / file hỏng thì bỏ qua. Hai nơi gọi: người
    dùng đồng ý áp phần sửa trong file `.abook` (`fold`) và điện thoại gửi phần sửa về (edits_inbox.py)."""
    from .music_local import MusicImportError

    project = Path(project)
    applied = skipped = 0
    if "title" in edits:
        store.set_display_title(project, edits["title"])
        applied += 1
    skipped += "author" in edits  # dự án Studio không có tác giả (chỉ sách nhập từ file mới có)
    if "cover" in edits:
        try:
            if edits["cover"] is None:
                covers.remove_cover(project)
                applied += 1
            elif cover is None:
                skipped += 1  # bìa mới không đi kèm
            else:
                covers.save_cover_bytes(project, cover)
                applied += 1
        except (OSError, covers.CoverError):
            skipped += 1
    for name, shown in (edits.get("characters") or {}).items():
        original = store.original_name(project, name)
        if original is None:
            skipped += 1
            continue
        renames.set_name(project, name, shown, original)
        applied += 1
    skipped += len(edits.get("readings") or {})
    local = chapter_resolver(project)
    for key, entry in (edits.get("chapters") or {}).items():
        target = local(key)
        if target is None:
            skipped += 1
            continue
        store.set_chapter_title(project, target, entry.get("title"), entry.get("subtitle"))
        applied += 1
    music_changes: dict[str, Any] = {}
    music = edits.get("music") or {}
    if "enabled" in music:
        music_changes["enabled"] = music["enabled"]
    if "levelDb" in music:
        music_changes["levelDb"] = music["levelDb"]
    silence: dict[str, bool] = {}
    pins: dict[str, str] = {}
    reasons: list[str] = []
    plan = music_plan.read_plan(project)
    for key, link in (music.get("pins") or {}).items():
        chapter, _, millis = key.partition(":")
        scenes = _cue_scenes(plan, local(chapter), millis)
        sha = music_plan.local_hash(link)
        source = (music_dir or project / INCOMING_MUSIC) / f"{sha}.{music['tracks'][sha]['ext']}"
        if not scenes:
            reason = "mốc nhạc này không còn trong dự án"
        elif my_music is None:
            reason = "máy này chưa có kho nhạc"
        elif not source.is_file():
            reason = "file nhạc không có trong sách"
        else:
            reason = ""
            info = music["tracks"][sha]
            try:
                mine, _ = my_music.import_file(source, {"title": info.get("title", ""), "artist": info.get("creator", "")})
                reason = "" if mine["link"] == link else "file nhạc không đúng bài đã ghim"
            except MusicImportError as exc:
                reason = str(exc)
        if reason:
            skipped += 1
            reasons.append(f"{key}: {reason}")
            continue
        pins.update({scene: link for scene in scenes})
        applied += 1
    if pins:
        music_changes["pins"] = pins
    for key in music.get("silenced") or []:
        chapter, _, millis = key.partition(":")
        scenes = _cue_scenes(plan, local(chapter), millis)
        if not scenes:
            skipped += 1
            continue
        silence.update({scene: True for scene in scenes})
        applied += 1
    if silence:
        music_changes["silence"] = silence
    if music_changes:
        music_plan.write_overrides(project, music_changes)
        applied += ("enabled" in music_changes) + ("levelDb" in music_changes)
    requests = 0
    if edits.get("wishes"):
        from . import book_wishes

        # Ý muốn chờ Studio KHÔNG được áp: chúng thành yêu cầu trong overrides.json (đóng dấu lại giờ), vào danh sách "Áp dụng
        # N thay đổi" như mọi yêu cầu - dây chuyền áp ở ranh giới chương kế tiếp hay lần chạy tới.
        folded = book_wishes.fold(project, edits["wishes"], now=time.time())
        requests, skipped = folded["requests"], skipped + folded["skipped"]
    return {"applied": applied, "skipped": skipped, "music": bool(music_changes), "requests": requests,
            **({"reasons": reasons} if reasons else {})}
