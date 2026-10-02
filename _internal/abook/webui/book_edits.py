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
     "cover": null | {"color": "#aabbcc", "width": 800, "height": 1200, "version": 1759400000},
                                                                (không có khoá = giữ bìa; null = bỏ bìa, dùng bìa vẽ từ tên;
                                                                 đối tượng = dùng edits/cover.jpg)
     "characters": {"<name trong cast.json>": "<tên hiện>"},
     "chapters": {"<mã chương>": {"title": "Chương 12", "subtitle": "Hồi kết"}},   (mỗi trường tuỳ chọn)
     "music": {"enabled": false, "levelDb": -24.0, "silenced": ["<mã chương>:<mili giây đầu mốc>"]}}

Bộ ví dụ dùng chung với bản Kotlin (BookEdits.kt): tests/fixtures/book_edits/.
"""
from __future__ import annotations

import copy
import json
import re
import threading
import unicodedata
from pathlib import Path
from typing import Any

from .. import names as renames
from ..io_utils import atomic_write_bytes
from . import covers, music_plan, store

EDITS_FILE = "edits.json"
EDITS_COVER = "edits/cover.jpg"
FORMAT = "abook-edits"
VERSION = 1
MAX_EDITS_BYTES = 1024 * 1024
MAX_COVER_BYTES = 8 * 1024 * 1024
TITLE_MAX = store.TITLE_MAX
NAME_MAX = renames.MAX_NAME
MAX_CHARACTERS = 2000
MAX_CHAPTERS = 5000
MAX_SILENCED = 5000
LEVEL_RANGE = (-40.0, -6.0)
_TOP_KEYS = {"format", "version", "title", "cover", "characters", "chapters", "music"}
_COVER_KEYS = {"color", "width", "height", "version"}
_MUSIC_KEYS = {"enabled", "levelDb", "silenced"}
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


def count(edits: dict[str, Any]) -> int:
    """Số thay đổi người nghe đã làm (cho dòng "N thay đổi"): tên sách, bìa, mỗi tên nhân vật, mỗi chương đổi tên, bật/tắt
    nhạc, mức nhạc, mỗi đoạn nhạc im lặng."""
    music = edits.get("music") or {}
    return (("title" in edits) + ("cover" in edits) + len(edits.get("characters") or {}) + len(edits.get("chapters") or {})
            + ("enabled" in music) + ("levelDb" in music) + len(music.get("silenced") or []))


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
    if "music" in raw:
        out["music"] = _validate_music(raw["music"])
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
    if "silenced" in music:
        silenced = music["silenced"]
        if (not isinstance(silenced, list) or len(silenced) > MAX_SILENCED or len(set(silenced)) != len(silenced)
                or any(not isinstance(key, str) or not _CUE_KEY.fullmatch(key) for key in silenced)):
            raise EditsError("Danh sách đoạn nhạc im lặng trong phần sửa không hợp lệ.")
        out["silenced"] = sorted(silenced)
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
    for key in ("title", "cover"):
        if key in edits:
            out[key] = edits[key]
    if edits.get("characters"):
        out["characters"] = dict(sorted(edits["characters"].items()))
    if edits.get("chapters"):
        out["chapters"] = {key: edits["chapters"][key] for key in sorted(edits["chapters"], key=int)}
    if edits.get("music"):
        out["music"] = {key: edits["music"][key] for key in ("enabled", "levelDb", "silenced") if key in edits["music"]}
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
    out = empty()
    conflicts = 0
    for key in ("title", "cover"):
        if key in local:
            out[key] = copy.deepcopy(local[key])
            conflicts += key in incoming and incoming[key] != local[key]
        elif key in incoming:
            out[key] = copy.deepcopy(incoming[key])
    people = {**(incoming.get("characters") or {}), **(local.get("characters") or {})}
    conflicts += sum(1 for name, shown in (local.get("characters") or {}).items()
                     if name in (incoming.get("characters") or {}) and incoming["characters"][name] != shown)
    if people:
        out["characters"] = people
    chapters: dict[str, dict[str, str]] = {}
    for key in {*(incoming.get("chapters") or {}), *(local.get("chapters") or {})}:
        theirs, ours = (incoming.get("chapters") or {}).get(key, {}), (local.get("chapters") or {}).get(key, {})
        conflicts += sum(1 for field in ours if field in theirs and theirs[field] != ours[field])
        chapters[key] = {**theirs, **ours}
    if chapters:
        out["chapters"] = chapters
    music: dict[str, Any] = {}
    local_music, incoming_music = local.get("music") or {}, incoming.get("music") or {}
    for field in ("enabled", "levelDb"):
        if field in local_music:
            music[field] = local_music[field]
            conflicts += field in incoming_music and incoming_music[field] != local_music[field]
        elif field in incoming_music:
            music[field] = incoming_music[field]
    silenced = sorted({*(local_music.get("silenced") or []), *(incoming_music.get("silenced") or [])})
    if silenced:
        music["silenced"] = silenced
    if music:
        out["music"] = music
    cover = None
    if isinstance(out.get("cover"), dict):
        cover = "local" if isinstance(local.get("cover"), dict) else "incoming"
    taken = count(out) - count(local)
    return out, {"adopted": max(0, taken), "kept": count(local), "conflicts": conflicts, "cover": cover}


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
    """`book.json` (lớp sách) -> bản người nghe thấy: tên sách (và tên các phần của cả bộ), tên chương, bìa, nhạc."""
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
    renamed = edits.get("chapters") or {}
    if renamed and isinstance(book.get("chapters"), list):
        out["chapters"] = [apply_chapter(chapter, renamed.get(str(chapter.get("id")))) if isinstance(chapter, dict) else chapter
                           for chapter in book["chapters"]]
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


def apply_cast(cast: dict[str, Any], edits: dict[str, Any], base: dict[str, Any] | None = None) -> dict[str, Any]:
    """`cast.json` -> bản người nghe thấy: tên nhân vật đã đổi (`displayName`, và `originalName` khi khác tên gốc), và
    `firstChapter` theo tên chương mới. `base`: book.json lớp sách (để biết tên chương gốc)."""
    people = edits.get("characters") or {}
    chapter_names = _chapter_renames(base, edits)
    if not people and not chapter_names:
        return cast
    out = copy.deepcopy(cast)
    for kind in ("characters", "extras", "carried"):
        for person in out.get(kind) or []:
            if not isinstance(person, dict):
                continue
            name = person.get("name")
            if name in people:
                original = person.get("originalName") or person.get("displayName") or name
                person["displayName"] = people[name]
                if people[name] != original:
                    person["originalName"] = original
                else:
                    person.pop("originalName", None)
            if person.get("firstChapter") in chapter_names:
                person["firstChapter"] = chapter_names[person["firstChapter"]]
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


def apply_music(music: dict[str, Any] | None, edits: dict[str, Any]) -> dict[str, Any] | None:
    """Mục `music` của book.json sau khi người nghe sửa: tắt hết, mức khác (tính lại `gainDb` từng mốc bằng đúng công thức
    của người làm sách - music_plan.cue_gain_db), bỏ các mốc đã cho im lặng."""
    if music is None:
        return None
    changes = edits.get("music") or {}
    if not changes:
        return music
    out = copy.deepcopy(music)
    tracks = out.get("tracks") if isinstance(out.get("tracks"), dict) else {}
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
    `book`: book.json GỐC. Sách không có nhạc: `hasMusic` false."""
    music = book.get("music") if isinstance(book.get("music"), dict) else None
    changes = edits.get("music") or {}
    base_level = float(music["levelDb"]) if music and _number(music.get("levelDb")) else music_plan.DEFAULT_LEVEL_DB
    silenced = set(changes.get("silenced") or [])
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
            cues.append({"key": key, "chapterId": int(chapter_id), "chapter": shown.get("fullTitle") or shown.get("title") or "",
                         "start": float(cue.get("start", 0)), "end": float(cue.get("end", 0)),
                         "title": str(info.get("title") or ""), "creator": str(info.get("creator") or ""),
                         "silenced": key in silenced})
    return {"package": True, "hasMusic": bool(cues), "enabled": changes.get("enabled", True),
            "levelDb": changes.get("levelDb", base_level), "defaultLevelDb": base_level, "cues": cues}


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


def _write(folder: Path, edits: dict[str, Any]) -> dict[str, Any]:
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


def set_music(folder: Path, body: dict[str, Any]) -> dict[str, Any]:
    """Sửa nhạc nền của sách đóng gói: `enabled`, `levelDb` (kẹp -40..-6 như `music_plan.write_overrides`), `silence`
    {khoá mốc: True/False}. Khoá lạ: `EditsError`. Trả `music_view`."""
    book = _base(folder)
    with _LOCK:
        edits = load(folder)
        music = dict(edits.get("music") or {})
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
        if music:
            edits["music"] = music
        else:
            edits.pop("music", None)
        _write(folder, edits)
        return music_view(book, edits)


def clear(folder: Path) -> None:
    """Bỏ mọi thay đổi của người nghe: sách trở về đúng như người làm sách đã đóng gói."""
    with _LOCK:
        save(folder, empty())


# ---- file `.abook` mang phần sửa theo ----------------------------------------------------------------------------


def adopt(folder: Path, incoming: dict[str, Any], cover: bytes | None) -> dict[str, Any]:
    """Nhập lại một file sách ĐÃ có trên máy mà file mang phần sửa: hợp vào phần sửa của máy (`merge`: máy này thắng) -
    không giải nén lại audio. `cover`: byte edits/cover.jpg của file (nếu có). Trả báo cáo của `merge`."""
    folder = Path(folder)
    with _LOCK:
        merged, report = merge(load(folder), incoming)
        if report["cover"] == "incoming" and cover is not None:
            atomic_write_bytes(folder / EDITS_COVER, cover)
        save(folder, merged)
    return report


# ---- chủ máy sản xuất mở file đã sửa: áp vào dự án của mình --------------------------------------------------------

INCOMING_FILE = "edits_incoming.json"
INCOMING_COVER = "edits_incoming_cover.jpg"
PART_SPAN = 100_000  # bookfile.PART_SPAN (bookfile nhập module này, nên không nhập ngược ở đây)


def stash_incoming(project: Path, edits: dict[str, Any], cover: bytes | None) -> None:
    """File `.abook` mang lớp sửa vừa mở ra đúng dự án của máy này (nhận ra bằng audio): cất phần sửa cạnh dự án để người
    dùng quyết ("N thay đổi - áp vào dự án?") - không bao giờ tự áp."""
    project = Path(project)
    with _LOCK:
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


def fold(project: Path) -> dict[str, Any]:
    """Áp phần sửa đang chờ (`incoming`) vào dự án bằng ĐÚNG những hàm Studio dùng: tên sách (store.set_display_title), bìa
    (covers), tên nhân vật (names.set_name), tên chương (store.set_chapter_title), nhạc nền (music_plan.write_overrides).
    Thay đổi nào không còn chỗ (nhân vật / chương không có trong dự án, nhạc chưa dựng) thì bỏ qua và đếm. Xong thì xoá phần
    chờ. Trả {"applied", "skipped", "music": có đổi lựa chọn nhạc không (người gọi dựng lại rãnh nhạc)}."""
    from .. import continuation

    project = Path(project)
    edits = incoming(project)
    applied = skipped = 0
    if "title" in edits:
        store.set_display_title(project, edits["title"])
        applied += 1
    if "cover" in edits:
        cover = edits["cover"]
        try:
            if cover is None:
                covers.remove_cover(project)
                applied += 1
            else:
                covers.save_cover_bytes(project, (project / INCOMING_COVER).read_bytes())
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
    part = continuation.part_number(project)
    have = {chapter["id"] for chapter in store.chapters(project)}

    def local(key: str) -> int | None:
        number = int(key)
        return number % PART_SPAN if number // PART_SPAN in (0, part) and number % PART_SPAN in have else None

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
    plan = music_plan.read_plan(project)
    for key in music.get("silenced") or []:
        chapter, _, millis = key.partition(":")
        target = local(chapter)
        cue = next((cue for cue in music_plan.chapter_cues(plan, target) if int(round(cue["start"] * 1000)) == int(millis)),
                   None) if plan is not None and target is not None else None
        scenes = [scene["key"] for scene in (plan or {}).get("scenes") or []
                  if cue is not None and scene.get("chapterId") == target and scene.get("link") == cue["link"]
                  and float(scene["start"]) >= cue["start"] - 0.001 and float(scene["end"]) <= cue["end"] + 0.001]
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
    dismiss_incoming(project)
    return {"applied": applied, "skipped": skipped, "music": bool(music_changes)}
