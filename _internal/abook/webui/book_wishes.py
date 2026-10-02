"""Ý MUỐN của người nghe trên một cuốn không có xưởng - docs/EDITING.md, lớp W ("wish") của giai đoạn P2.

Cách đọc một cái tên, ai nói câu này (và gộp hai tên làm một), loại đoạn / cảm xúc / chữ đem đọc của một câu, giọng và giới
của một nhân vật, thu lại một câu: những thứ ấy cần Studio (audio phải thu lại), mà cuốn nhập từ file `.abook` không có
Studio. Người nghe vẫn ghi được ý muốn ở đây - nó nằm trong `edits.json`, mục `wishes`, theo ĐÚNG hình dạng các mục của
`overrides.json` (listener_overrides.py), đi theo file `.abook` (phiên bản 4), hợp lại khi nhập lại file, và chủ máy sản xuất
đọc lại thành yêu cầu thật bằng chính các hàm Studio dùng (`fold`). KHÔNG BAO GIỜ áp vào audio hay chữ người nghe thấy: sách
vẫn như người làm sách đóng gói, chỉ có dấu "đang chờ Studio" (dàn nhân vật: `pendingVoice`, danh sách `pending_details`).

    "wishes": {"pronunciations": {"<khoá từ>": {"surface", "spoken_form", "requested_at", "replaced"?}},
               "speakers":       {"<mã câu>": {"speaker", "text_sha256", "requested_at", "new"?: {"gender"}, "replaced"?}},
               "lines":          {"<mã câu>": {"text_sha256", "kind", "emotion", "intensity", "spoken"?, "requested_at"}},
               "voices":         {"<TÊN CHUẨN>": {"preset", "gender", "avoid", "requested_at", "replaced"?}},
               "retakes":        {"<mã câu>": {"text_sha256", "requested_at"}},
               "aliases":        [{"alias", "person", "at"}]}                 (mỗi mục tuỳ chọn)

Hàm ghi KHÔNG chép lại logic của listener_overrides: nó dựng một thư mục tạm có `overrides.json` mang các ý muốn hiện có, gọi
đúng `listener_overrides.request_*` / `withdraw_requests` / `cancel_retake` lên đó rồi đọc kết quả về - nên hình dạng mục, phép
gộp với mong muốn cũ (`replaced`) và "Hoàn tác" y hệt Studio. Bản Kotlin (BookEdits.kt) viết lại các phép ấy; hai bên đọc chung
bộ ví dụ tests/fixtures/book_edits/.

Dữ liệu của người lạ (file `.abook` đến từ máy khác): `validate` chặt như phần còn lại của `edits.json` - đúng khoá, đúng
kiểu, có trần số mục và độ dài, chữ phải đã sạch (không sửa hộ) - sai một mục là từ chối cả file.
"""
from __future__ import annotations

import copy
import json
import re
import tempfile
from pathlib import Path
from typing import Any, Callable

from .. import aliases as alias_book
from .. import listener_overrides as overrides
from . import book_edits, humanize, store
from .book_edits import EditsError

SECTIONS = ("pronunciations", "speakers", "lines", "voices", "retakes")
ALIASES = "aliases"
BY_CLICK = store.BY_CLICK  # speakers, retakes: một lần bấm ghi nhiều câu cùng một `requested_at` = một thay đổi
MAX_ENTRIES = {"pronunciations": 2000, "speakers": 5000, "lines": 2000, "voices": 2000, "retakes": 5000, ALIASES: 2000}
SURFACE_MAX = 80
SPOKEN_FORM_MAX = 120
SPEAKER_MAX = 200
PRESET_MAX = 120
SPOKEN_TEXT_MAX = overrides.MAX_SPOKEN_CHARS
INTENSITY_MAX = 3
TIME_MAX = 10**11
_LINE_ID = re.compile(r"[A-Za-z0-9_]{1,120}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_ENTRY_KEYS = {
    "pronunciations": {"surface", "spoken_form", "requested_at"},
    "speakers": {"speaker", "text_sha256", "requested_at", "new"},
    "lines": {"text_sha256", "kind", "emotion", "intensity", "spoken", "requested_at"},
    "voices": {"preset", "gender", "avoid", "requested_at"},
    "retakes": {"text_sha256", "requested_at"},
}
_REPLACEABLE = {"pronunciations", "speakers", "voices"}  # các mục `_replacing` của listener_overrides giữ mong muốn cũ

BAD_WISHES = "Phần ý muốn chờ Studio trong phần sửa không hợp lệ hay quá dài."
_BAD_ENTRY = {
    "pronunciations": "Một ý muốn về cách đọc tên trong phần sửa không hợp lệ.",
    "speakers": "Một ý muốn về người nói trong phần sửa không hợp lệ.",
    "lines": "Một ý muốn về cách đọc câu trong phần sửa không hợp lệ.",
    "voices": "Một ý muốn về giọng nhân vật trong phần sửa không hợp lệ.",
    "retakes": "Một ý muốn thu lại câu trong phần sửa không hợp lệ.",
    ALIASES: "Một ý muốn gộp tên trong phần sửa không hợp lệ.",
}
TOO_MANY = book_edits.TOO_BIG


# ---- kiểm (dữ liệu của người lạ) -----------------------------------------------------------------------------------


def _time(value: Any) -> float | None:
    return float(value) if book_edits._number(value) and 0 < value <= TIME_MAX else None


def _text(value: Any, limit: int, *, empty: bool = False) -> bool:
    return isinstance(value, str) and (bool(value) or empty) and book_edits._is_clean(value, limit)


def _entry(section: str, key: Any, entry: Any, *, nested: bool = False) -> dict[str, Any]:
    bad = EditsError(_BAD_ENTRY[section])
    if not isinstance(key, str) or not isinstance(entry, dict):
        raise bad
    allowed = _ENTRY_KEYS[section] | ({"replaced"} if section in _REPLACEABLE and not nested else set())
    if set(entry) - allowed:
        raise bad
    if section in ("speakers", "lines", "retakes"):
        if not _LINE_ID.fullmatch(key):
            raise bad
    elif not _text(key, 200):
        raise bad
    out: dict[str, Any] = {}
    requested_at = _time(entry.get("requested_at"))
    if requested_at is None:
        raise bad
    out["requested_at"] = requested_at
    if section == "pronunciations":
        surface, spoken = entry.get("surface"), entry.get("spoken_form")
        if not _text(surface, SURFACE_MAX) or len(surface.split()) != 1 or not _text(spoken, SPOKEN_FORM_MAX):
            raise bad
        out.update(surface=surface, spoken_form=spoken)
    elif section == "speakers":
        speaker, sha = entry.get("speaker"), entry.get("text_sha256")
        if not _text(speaker, SPEAKER_MAX) or not isinstance(sha, str) or not _SHA256.fullmatch(sha):
            raise bad
        out.update(speaker=speaker, text_sha256=sha)
        if "new" in entry:
            new = entry["new"]
            if not isinstance(new, dict) or set(new) != {"gender"} or new["gender"] not in overrides.NEW_CHARACTER_GENDERS:
                raise bad
            out["new"] = {"gender": new["gender"]}
    elif section == "lines":
        out.update(_line_fields(entry, bad))
    elif section == "voices":
        preset, gender, avoid = entry.get("preset"), entry.get("gender"), entry.get("avoid")
        if (not _text(preset, PRESET_MAX, empty=True) or gender not in ("", "male", "female")
                or not _text(avoid, SPEAKER_MAX, empty=True)):
            raise bad
        out.update(preset=preset, gender=gender, avoid=avoid)
    else:
        sha = entry.get("text_sha256")
        if not isinstance(sha, str) or not _SHA256.fullmatch(sha):
            raise bad
        out["text_sha256"] = sha
    if "replaced" in entry:
        out["replaced"] = _entry(section, key, entry["replaced"], nested=True)
    return out


def _line_fields(entry: dict[str, Any], bad: EditsError) -> dict[str, Any]:
    from ..analysis import ALLOWED_EMOTIONS

    sha, kind, emotion, intensity = entry.get("text_sha256"), entry.get("kind"), entry.get("emotion"), entry.get("intensity")
    if (not isinstance(sha, str) or not _SHA256.fullmatch(sha) or kind not in ("", *overrides.LINE_KINDS)
            or not isinstance(emotion, str) or (emotion and emotion not in ALLOWED_EMOTIONS)
            or not (intensity is None or (isinstance(intensity, int) and not isinstance(intensity, bool)
                                          and 0 <= intensity <= INTENSITY_MAX))):
        raise bad
    out: dict[str, Any] = {"text_sha256": sha, "kind": kind, "emotion": emotion, "intensity": intensity}
    if "spoken" in entry:
        if not _text(entry["spoken"], SPOKEN_TEXT_MAX, empty=True):
            raise bad
        out["spoken"] = entry["spoken"]
    return out


def validate(raw: Any) -> dict[str, Any]:
    """Mục `wishes` của `edits.json` -> dạng chuẩn; sai thì `EditsError`. Mỗi mục con không rỗng, dưới trần của nó."""
    if not isinstance(raw, dict) or not raw or set(raw) - {*SECTIONS, ALIASES}:
        raise EditsError(BAD_WISHES)
    out: dict[str, Any] = {}
    for section in SECTIONS:
        if section in raw:
            entries = raw[section]
            if not isinstance(entries, dict) or not entries or len(entries) > MAX_ENTRIES[section]:
                raise EditsError(BAD_WISHES)
            out[section] = {key: _entry(section, key, entry) for key, entry in entries.items()}
    if ALIASES in raw:
        out[ALIASES] = _aliases(raw[ALIASES])
    return out


def _aliases(raw: Any) -> list[dict[str, Any]]:
    bad = EditsError(_BAD_ENTRY[ALIASES])
    if not isinstance(raw, list) or not raw or len(raw) > MAX_ENTRIES[ALIASES]:
        raise EditsError(BAD_WISHES)
    out, seen = [], set()
    for item in raw:
        if not isinstance(item, dict) or set(item) != {"alias", "person", "at"}:
            raise bad
        alias, person, at = item["alias"], item["person"], _time(item["at"])
        if (not _text(alias, alias_book.MAX_NAME) or not _text(person, alias_book.MAX_NAME) or at is None
                or alias in seen):
            raise bad
        seen.add(alias)
        out.append({"alias": alias, "person": person, "at": at})
    return out


# ---- thứ tự ghi, đếm, hợp ----------------------------------------------------------------------------------------


def ordered(wishes: dict[str, Any]) -> dict[str, Any]:
    """Dạng ghi ra `edits.json`: mục xếp theo khoá, khoá của mục xếp theo chữ - cùng nội dung thì cùng byte."""

    def entry(value: dict[str, Any]) -> dict[str, Any]:
        return {key: (entry(item) if isinstance(item, dict) else item) for key, item in sorted(value.items())}

    out: dict[str, Any] = {}
    for section in SECTIONS:
        if wishes.get(section):
            out[section] = {key: entry(wishes[section][key]) for key in sorted(wishes[section])}
    if wishes.get(ALIASES):
        out[ALIASES] = [entry(item) for item in wishes[ALIASES]]
    return out


def _clicks(entries: dict[str, Any] | None) -> int:
    return len({entry.get("requested_at") for entry in (entries or {}).values()})


def count(wishes: dict[str, Any] | None) -> int:
    """Số thay đổi chờ Studio (cho dòng "N thay đổi"): mỗi cách đọc, mỗi câu đổi cách đọc, mỗi giọng; nhiều câu cùng một lần
    bấm (gán người nói cả nhóm, gộp tên, thu lại cả chương) tính là MỘT. Bí danh đi theo lần gộp nên không đếm riêng."""
    wishes = wishes or {}
    return (len(wishes.get("pronunciations") or {}) + len(wishes.get("lines") or {}) + len(wishes.get("voices") or {})
            + _clicks(wishes.get("speakers")) + _clicks(wishes.get("retakes")))


def fits(wishes: dict[str, Any]) -> bool:
    """Số mục từng loại trong trần (`merge` kiểm sau khi hợp: file hợp ra mà `validate` từ chối thì người nghe mất sạch)."""
    return all(len(wishes.get(name) or ()) <= cap for name, cap in MAX_ENTRIES.items())


def merge(local: dict[str, Any] | None, incoming: dict[str, Any] | None) -> tuple[dict[str, Any], int]:
    """Hợp ý muốn trên máy (`local`) với ý muốn trong file vừa mở (`incoming`): hợp theo khoá mục (mã câu, khoá từ, tên chuẩn);
    khoá cả hai cùng có mà khác nhau thì THẮNG BÊN MÁY NÀY, như phần sửa khác. Người nghe rút một ý muốn thì chỉ rút ở máy
    này: không có "bia mộ" nào được ghi (edits.json không mang gì thừa), nên file còn mang nó thì nhập lại sẽ mang nó về -
    rút lần nữa. Trả (ý muốn đã hợp, số khoá hai bên khác nhau)."""
    local, incoming = local or {}, incoming or {}
    out: dict[str, Any] = {}
    conflicts = 0
    for section in SECTIONS:
        ours, theirs = local.get(section) or {}, incoming.get(section) or {}
        conflicts += sum(1 for key in ours if key in theirs and theirs[key] != ours[key])
        merged = {**copy.deepcopy(theirs), **copy.deepcopy(ours)}
        if merged:
            out[section] = merged
    ours_aliases, theirs_aliases = local.get(ALIASES) or [], incoming.get(ALIASES) or []
    mine = {item["alias"] for item in ours_aliases}
    conflicts += sum(1 for item in theirs_aliases if item["alias"] in mine and item not in ours_aliases)
    merged_aliases = copy.deepcopy(ours_aliases) + [copy.deepcopy(item) for item in theirs_aliases if item["alias"] not in mine]
    if merged_aliases:
        out[ALIASES] = merged_aliases
    if not fits(out):
        return copy.deepcopy(local), 0  # quá trần: giữ nguyên của máy này, không nhận thêm
    return out, conflicts


# ---- dấu "đang chờ Studio" trên dàn nhân vật ----------------------------------------------------------------------


def pending_voices(wishes: dict[str, Any] | None) -> dict[str, dict[str, str]]:
    """{khoá tên chuẩn: giọng/giới đang chờ} - như `store.pending_voices` của dự án: dòng nhân vật hiện "chờ áp dụng"."""
    out: dict[str, dict[str, str]] = {}
    for key, entry in ((wishes or {}).get("voices") or {}).items():
        if entry.get("preset") or entry.get("gender"):
            out[key] = {"preset": humanize.voice_label(entry.get("preset", "")),
                        "gender": humanize.GENDER_LABELS.get(entry.get("gender", ""), "")}
    return out


# ---- đọc sách để kiểm một ý muốn trước khi ghi ---------------------------------------------------------------------


class Lines:
    """Tra một câu theo mã ổn định trong chữ đọc theo của cuốn đã nhập (chữ qua lớp sửa: tên người nói là tên đang hiện).
    Tìm chương mang số đó trước (mã `c<chương>_s...`), không thấy mới duyệt hết; đã đọc chương nào thì nhớ lại."""

    def __init__(self, folder: Path) -> None:
        from . import packages

        self.folder = Path(folder)
        self._packages = packages
        self.chapters = [chapter for chapter in packages.edited_manifest(self.folder).get("chapters") or []
                         if isinstance(chapter, dict) and isinstance(chapter.get("id"), int)]
        self._read: dict[int, list[dict[str, Any]]] = {}
        self._by_id: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}

    def _load(self, chapter: dict[str, Any]) -> list[dict[str, Any]]:
        number = chapter["id"]
        if number not in self._read:
            script = self._packages.script(self.folder, number)
            found: list[dict[str, Any]] = []
            for segment in (script.get("segments") if isinstance(script, dict) else None) or []:
                if isinstance(segment, dict) and isinstance(segment.get("stableId"), str):
                    found.append(segment)
                    self._by_id[segment["stableId"]] = (chapter, segment)
            self._read[number] = found
        return self._read[number]

    def segments(self, chapter: dict[str, Any]) -> list[dict[str, Any]]:
        """Mọi câu có mã ổn định của một chương, theo thứ tự trong chữ đọc theo."""
        return self._load(chapter)

    def get(self, stable_id: str) -> tuple[dict[str, Any], dict[str, Any]] | None:
        if stable_id in self._by_id:
            return self._by_id[stable_id]
        match = store.STABLE_ID.match(stable_id)
        hint = int(match.group(1)) if match else -1
        for chapter in sorted(self.chapters, key=lambda item: item["id"] % book_edits.PART_SPAN != hint):
            if chapter["id"] not in self._read:
                self._load(chapter)
                if stable_id in self._by_id:
                    return self._by_id[stable_id]
        return self._by_id.get(stable_id)

    def chapter(self, number: int) -> dict[str, Any] | None:
        return next((chapter for chapter in self.chapters if chapter["id"] == number), None)


def people(folder: Path) -> list[dict[str, Any]]:
    """Nhân vật của cuốn như người nghe thấy (tên đã đổi): characters + extras + carried."""
    from . import packages

    cast = packages.cast(folder)
    return [person for kind in ("characters", "extras", "carried") for person in (cast.get(kind) or [])
            if isinstance(person, dict) and isinstance(person.get("name"), str)]


def _person(cast: list[dict[str, Any]], raw: str) -> dict[str, Any] | None:
    key = overrides.character_key(raw)
    return next((person for person in cast if overrides.character_key(person["name"]) == key), None)


def speaker_problem(lines: Lines, cast: list[dict[str, Any]], stable_id: str, text_sha256: str, speaker: str,
                    new_gender: str = "", as_kind: str = "") -> str | None:
    """Mã lý do Studio sẽ từ chối "ai nói câu này", hoặc None - cùng các phép kiểm của `listener_overrides.speaker_target`
    (câu còn đó, chữ chưa đổi, là lời nói, người ấy có giọng - hay người nghe TẠO người mới), trên chữ đọc theo của cuốn."""
    found = lines.get(stable_id)
    if found is None:
        return overrides.UNKNOWN_LINE
    segment = found[1]
    if str(segment.get("textSha256") or "") != text_sha256:
        return overrides.SOURCE_CHANGED
    if (as_kind or str(segment.get("kind") or "")) not in overrides.SPEECH_KINDS:
        return overrides.NOT_SPEECH
    if speaker == overrides.UNNAMED or overrides.character_key(speaker) == overrides.NARRATOR:
        return None
    person = _person(cast, speaker)
    if person is not None and person.get("voice"):
        return None
    if new_gender in overrides.NEW_CHARACTER_GENDERS:
        display = " ".join(speaker.split()).upper()
        if not display or display in ("NARRATOR", "UNKNOWN") or display.startswith("ANONYMOUS_"):
            return overrides.NO_VOICE
        return None
    return overrides.NO_VOICE


def line_problem(lines: Lines, cast: list[dict[str, Any]], stable_id: str, text_sha256: str, *, kind: str = "",
                 emotion: str = "", speaker: str = "", spoken: str | None = None) -> str | None:
    """Mã lý do Studio sẽ từ chối sửa cách đọc một câu (và người nói đi kèm khi câu thành lời thoại), hoặc None - như
    `listener_overrides.line_target` + `speaker_target` trên chữ đọc theo của cuốn."""
    from ..analysis import ALLOWED_EMOTIONS

    found = lines.get(stable_id)
    if found is None:
        return overrides.UNKNOWN_LINE
    segment = found[1]
    if str(segment.get("textSha256") or "") != text_sha256:
        return overrides.SOURCE_CHANGED
    if kind and kind not in overrides.LINE_KINDS:
        return overrides.BAD_KIND
    if emotion and emotion not in ALLOWED_EMOTIONS:
        return overrides.BAD_EMOTION
    if spoken is not None and overrides.spoken_problem(str(segment.get("text") or ""), spoken) is not None:
        return overrides.BAD_TEXT
    if speaker:
        return speaker_problem(lines, cast, stable_id, text_sha256, speaker, as_kind=kind or str(segment.get("kind") or ""))
    return None


def voice_problem(cast: list[dict[str, Any]], character: str, *, gender: str = "") -> str | None:
    """Mã lý do Studio sẽ từ chối giọng/giới của một nhân vật, hoặc None. Tên giọng (`preset`) không kiểm ở đây - bảng giọng
    dùng được nằm ở máy có Studio, nơi bước áp kiểm lại (UNKNOWN_PRESET)."""
    if gender not in ("", "male", "female"):
        return overrides.BAD_GENDER
    if overrides.character_key(character) == overrides.NARRATOR:
        return overrides.NOT_A_CHARACTER
    person = _person(cast, character)
    if person is None:
        return overrides.UNKNOWN_CHARACTER
    return None if person.get("voice") else overrides.NO_VOICE


def speaker_lines(lines: Lines, cast: list[dict[str, Any]], source: str) -> list[tuple[str, str]]:
    """Mọi câu nói (lời thoại, nội tâm) của người `source` - [(mã câu, băm chữ)] - để gộp họ vào người khác. Người nói trong
    chữ đọc theo là tên hiện lúc đóng gói; nhận cả tên chuẩn lẫn tên hiện."""
    person = _person(cast, source)
    labels = {alias_book.key(source)}
    if person is not None:
        labels |= {alias_book.key(str(person.get(field))) for field in ("name", "displayName", "originalName") if person.get(field)}
    found: list[tuple[str, str]] = []
    for chapter in lines.chapters:
        for segment in lines.segments(chapter):
            if (segment.get("kind") in overrides.SPEECH_KINDS and segment.get("textSha256")
                    and alias_book.key(str(segment.get("speaker") or "")) in labels):
                found.append((str(segment["stableId"]), str(segment["textSha256"])))
    return found


def chapter_lines(lines: Lines, chapter_id: int) -> list[tuple[str, str]]:
    """Mọi câu có mã ổn định của một chương - [(mã câu, băm chữ)] - cho "Thu lại cả chương"."""
    chapter = lines.chapter(chapter_id)
    if chapter is None:
        return []
    return [(str(segment["stableId"]), str(segment["textSha256"])) for segment in lines.segments(chapter)
            if segment.get("textSha256")]


# ---- ghi ----------------------------------------------------------------------------------------------------------


def _run(wishes: dict[str, Any], action: Callable[[Path], Any]) -> tuple[dict[str, Any], Any]:
    """Chạy `action(thư mục)` lên một `overrides.json` tạm mang các ý muốn hiện có; trả (ý muốn mới, kết quả của action)."""
    with tempfile.TemporaryDirectory(prefix="abook-wishes-") as raw:
        scratch = Path(raw)
        (scratch / overrides.OVERRIDES_FILE).write_bytes(
            json.dumps({section: wishes[section] for section in SECTIONS if wishes.get(section)}, ensure_ascii=False).encode("utf-8"))
        result = action(scratch)
        data = overrides.read_overrides(scratch)
    return {section: data[section] for section in SECTIONS if isinstance(data.get(section), dict) and data[section]}, result


def _change(folder: Path, action: Callable[[Path], Any],
            *, aliases: Callable[[list[dict[str, Any]]], list[dict[str, Any]]] | None = None) -> Any:
    """Đọc ý muốn của cuốn, áp `action` (hàm của listener_overrides) lên bản tạm, kiểm trần, ghi lại. Trả kết quả của action."""
    with book_edits._LOCK:
        edits = book_edits.load(folder)
        current = edits.get("wishes") or {}
        new, result = _run(current, action)
        kept = aliases(copy.deepcopy(current.get(ALIASES) or [])) if aliases is not None else current.get(ALIASES)
        if kept:
            new[ALIASES] = kept
        if not fits(new):
            raise EditsError(TOO_MANY)
        if new:
            edits["wishes"] = new
        else:
            edits.pop("wishes", None)
        book_edits._write(folder, edits)
        return result


def request_pronunciation(folder: Path, surface: str, spoken_form: str, *, now: float) -> None:
    surface = book_edits.clean_text(surface, SURFACE_MAX)
    spoken_form = book_edits.clean_text(spoken_form, SPOKEN_FORM_MAX)
    _change(folder, lambda scratch: overrides.request_pronunciation(scratch, surface, spoken_form, now=now))


def request_speakers(folder: Path, lines: list[tuple[str, str]], speaker: str, *, now: float, new_gender: str = "") -> None:
    speaker = book_edits.clean_text(speaker, SPEAKER_MAX)
    _change(folder, lambda scratch: overrides.request_speakers(scratch, lines, speaker, now=now, new_gender=new_gender))


def request_line(folder: Path, stable_id: str, text_sha256: str, *, kind: str = "", emotion: str = "",
                 intensity: int | None = None, speaker: str = "", spoken: str | None = None, now: float) -> None:
    speaker = book_edits.clean_text(speaker, SPEAKER_MAX)
    spoken = book_edits.clean_text(spoken, SPOKEN_TEXT_MAX) if spoken is not None else None
    _change(folder, lambda scratch: overrides.request_line(scratch, stable_id, text_sha256, kind=kind, emotion=emotion,
                                                           intensity=intensity, speaker=speaker, spoken=spoken, now=now))


def request_voice(folder: Path, character: str, *, preset: str = "", gender: str = "", avoid: str = "", now: float) -> None:
    character = book_edits.clean_text(character, SPEAKER_MAX)
    preset, avoid = book_edits.clean_text(preset, PRESET_MAX), book_edits.clean_text(avoid, SPEAKER_MAX)
    _change(folder, lambda scratch: overrides.request_voice(scratch, character, preset=preset, gender=gender, avoid=avoid, now=now))


def request_retakes(folder: Path, lines: list[tuple[str, str]], *, now: float) -> None:
    """Một lần bấm cho nhiều câu (cả chương) - cùng một `requested_at`, một lần ghi file."""

    def action(scratch: Path) -> None:
        for stable_id, text_sha256 in lines:
            overrides.request_retake(scratch, stable_id, text_sha256, now=now)

    _change(folder, action)


def cancel_retake(folder: Path, stable_id: str) -> None:
    _change(folder, lambda scratch: overrides.cancel_retake(scratch, stable_id))


def request_alias(folder: Path, alias: str, person: str, *, now: float) -> bool:
    """"`alias` là `person`" (thẻ "Một người hai tên", "Gộp vào…"): cất để chủ máy sản xuất ghi vào aliases.json của dự án.
    Cùng tên bí danh thì mới thay cũ. Trả True khi có gì mới được ghi."""
    alias, person = book_edits.clean_text(alias, alias_book.MAX_NAME), book_edits.clean_text(person, alias_book.MAX_NAME)
    if not alias or not person or alias_book.key(alias) == alias_book.key(person):
        return False
    wrote: list[bool] = []

    def keep(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if any(item["alias"] == alias and item["person"] == person for item in entries):
            return entries
        wrote.append(True)
        return [item for item in entries if item["alias"] != alias] + [{"alias": alias, "person": person, "at": float(now)}]

    _change(folder, lambda scratch: None, aliases=keep)
    return bool(wrote)


def made_at(folder: Path, section: str, keys: list[str], requested_at: float) -> dict[str, dict[str, Any]]:
    """Những ý muốn trong `section` do CHÍNH một lần bấm ghi (`listener_overrides.requests_made_at`)."""
    return overrides.requests_made_at(book_edits.load(folder).get("wishes") or {}, section, keys, requested_at)


def withdraw(folder: Path, section: str, keys: list[str], requested_at: float) -> list[str]:
    """Rút ý muốn của đúng một lần bấm: ý muốn nó thay (`replaced`) trở lại, hoặc biến mất. "Gộp vào…" ghi cả bí danh cùng
    mốc ấy - rút lần gộp là rút luôn bí danh. Trả các khoá đã rút."""
    removed: list[str] = []

    def action(scratch: Path) -> None:
        if section == "retakes":
            mine = overrides.requests_made_at(overrides.read_overrides(scratch), section, keys, requested_at)
            for stable_id in mine:
                overrides.cancel_retake(scratch, stable_id)
            removed.extend(mine)
        else:
            removed.extend(overrides.withdraw_requests(scratch, section, keys, requested_at))

    def drop_aliases(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [item for item in entries if abs(item["at"] - requested_at) >= 1e-6] if section == "speakers" and removed else entries

    _change(folder, action, aliases=drop_aliases)
    return removed


# ---- danh sách "đang chờ Studio" ---------------------------------------------------------------------------------


def pending_details(folder: Path, wishes: dict[str, Any] | None) -> dict[str, Any]:
    """Cùng hình dạng với `store.pending_details` của dự án ({items, lines, chapters, seconds}) - từng ý muốn nói bằng lời,
    đủ để rút đúng nó (`section`, `key`, `requestedAt`) - nhưng không có câu nào "đã thu" để đếm: cuốn này chưa thu lại gì."""
    wishes = wishes or {}
    if not any(wishes.get(section) for section in SECTIONS):
        return {"items": [], "lines": 0, "chapters": [], "seconds": 0.0}
    lines = Lines(folder)
    cast = people(folder)
    titles = {chapter["id"]: str(chapter.get("fullTitle") or chapter.get("title") or "") for chapter in lines.chapters}

    def who(raw: Any) -> str:
        raw = str(raw or "")
        if overrides.character_key(raw) == overrides.NARRATOR:
            return "người kể"
        person = _person(cast, raw)
        return str(person.get("displayName") or person["name"]) if person is not None else raw

    def handle(section: str, key: str, entry: dict[str, Any]) -> dict[str, Any]:
        return {"section": section, "key": key, "requestedAt": float(entry.get("requested_at") or 0)}

    items: list[dict[str, Any]] = []
    for key in sorted(wishes.get("pronunciations") or {}):
        entry = wishes["pronunciations"][key]
        items.append({"kind": "pronunciation", "label": store.label_pronunciation(entry["surface"], entry["spoken_form"]),
                      "lines": 0, **handle("pronunciations", key, entry)})
    clicks: dict[float, list[str]] = {}
    for stable_id in sorted(wishes.get("speakers") or {}):
        if lines.get(stable_id) is not None:
            clicks.setdefault(wishes["speakers"][stable_id]["requested_at"], []).append(stable_id)
    for at, ids in clicks.items():
        entry = wishes["speakers"][ids[0]]
        chapter, segment = lines.get(ids[0])  # type: ignore[misc]
        if len(ids) == 1:
            items.append({"kind": "speaker", "label": store.label_speaker(segment["text"], who(entry["speaker"]), 1),
                          "chapter": titles.get(chapter["id"], ""), "lines": 0, **handle("speakers", ids[0], entry)})
            continue
        places = sorted({lines.get(stable_id)[0]["id"] for stable_id in ids})  # type: ignore[index]
        items.append({"kind": "speaker", "label": store.label_speaker("", who(entry["speaker"]), len(ids)),
                      "chapter": titles.get(places[0], "") + (f" và {len(places) - 1} chương khác" if len(places) > 1 else ""),
                      "lines": 0, "section": "speakers", "key": ids[0], "keys": ids, "requestedAt": at})
    for stable_id in sorted(wishes.get("lines") or {}):
        found = lines.get(stable_id)
        if found is None:
            continue
        entry = wishes["lines"][stable_id]
        items.append({"kind": "line", "label": store.label_line(found[1]["text"], entry),
                      "chapter": titles.get(found[0]["id"], ""), "lines": 0, **handle("lines", stable_id, entry)})
    for key in sorted(wishes.get("voices") or {}):
        entry = wishes["voices"][key]
        items.append({"kind": "voice", "label": store.label_voice(who(key), entry), "lines": 0, **handle("voices", key, entry)})
    retake_clicks: dict[float, list[str]] = {}
    for stable_id in sorted(wishes.get("retakes") or {}):
        retake_clicks.setdefault(wishes["retakes"][stable_id]["requested_at"], []).append(stable_id)
    for at, ids in retake_clicks.items():
        known = [stable_id for stable_id in ids if lines.get(stable_id) is not None]
        if not known:
            continue
        chapter, segment = lines.get(known[0])  # type: ignore[misc]
        if len(ids) == 1:
            items.append({"kind": "retake", "label": store.label_retake(segment["text"], 1),
                          "chapter": titles.get(chapter["id"], ""), "lines": 0,
                          **handle("retakes", known[0], wishes["retakes"][known[0]])})
        else:
            items.append({"kind": "retake", "label": store.label_retake("", len(ids)), "chapter": titles.get(chapter["id"], ""),
                          "lines": 0, "section": "retakes", "key": ids[0], "keys": ids, "requestedAt": at})
    return {"items": items, "lines": 0, "chapters": [], "seconds": 0.0}


# ---- chủ máy sản xuất: ý muốn thành yêu cầu thật --------------------------------------------------------------------


def fold(project: Path, wishes: dict[str, Any], *, now: float) -> dict[str, int]:
    """Đọc lại ý muốn của một file `.abook` thành YÊU CẦU của dự án bằng chính các hàm Studio dùng
    (`listener_overrides.request_*`, `aliases.add`) - ghi vào overrides.json như thể người dùng vừa bấm trong Studio, KHÔNG áp:
    chúng vào danh sách "Áp dụng N thay đổi" như mọi yêu cầu. `requested_at` được đóng dấu lại (đồng hồ điện thoại có thể lệch;
    yêu cầu phải mới hơn lần ghi sổ cuối thì mới "chờ áp"): mỗi lần bấm cũ một dấu mới riêng, giữ thứ tự và giữ cái gì từng
    là MỘT lần bấm. Ý muốn mà Studio sẽ từ chối ngay (câu đã đổi chữ, người chưa có giọng...) thì bỏ qua và đếm.
    Trả {"requests": số ý muốn đã ghi thành yêu cầu, "skipped": số bị bỏ qua}."""
    stamps = {at: now + index * 1e-3 for index, at in enumerate(sorted(
        {entry["requested_at"] for section in SECTIONS for entry in (wishes.get(section) or {}).values()}
        | {item["at"] for item in wishes.get(ALIASES) or []}))}
    requests = skipped = 0

    for key in sorted(wishes.get("pronunciations") or {}):
        entry = wishes["pronunciations"][key]
        if overrides.pronunciation_problem(entry["surface"], entry["spoken_form"]) is not None:
            skipped += 1
            continue
        overrides.request_pronunciation(project, entry["surface"], entry["spoken_form"], now=stamps[entry["requested_at"]])
        requests += 1
    groups: dict[tuple[float, str, str], list[tuple[str, str]]] = {}
    for stable_id in sorted(wishes.get("speakers") or {}):
        entry = wishes["speakers"][stable_id]
        new_gender = (entry.get("new") or {}).get("gender", "")
        if store.speaker_request_problem(project, stable_id, entry["text_sha256"], entry["speaker"], new_gender) is not None:
            skipped += 1
            continue
        groups.setdefault((entry["requested_at"], entry["speaker"], new_gender), []).append((stable_id, entry["text_sha256"]))
        requests += 1
    for (at, speaker, new_gender), members in groups.items():
        overrides.request_speakers(project, members, speaker, now=stamps[at], new_gender=new_gender)
    for stable_id in sorted(wishes.get("lines") or {}):
        entry = wishes["lines"][stable_id]
        if store.line_request_problem(project, stable_id, entry["text_sha256"], kind=entry["kind"], emotion=entry["emotion"],
                                      intensity=entry["intensity"], spoken=entry.get("spoken")) is not None:
            skipped += 1
            continue
        overrides.request_line(project, stable_id, entry["text_sha256"], kind=entry["kind"], emotion=entry["emotion"],
                               intensity=entry["intensity"], spoken=entry.get("spoken"), now=stamps[entry["requested_at"]])
        requests += 1
    for key in sorted(wishes.get("voices") or {}):
        entry = wishes["voices"][key]
        if store.voice_request_problem(project, key, preset=entry["preset"], gender=entry["gender"], avoid=entry["avoid"]) is not None:
            skipped += 1
            continue
        overrides.request_voice(project, key, preset=entry["preset"], gender=entry["gender"], avoid=entry["avoid"],
                                now=stamps[entry["requested_at"]])
        requests += 1
    for stable_id in sorted(wishes.get("retakes") or {}):
        entry = wishes["retakes"][stable_id]
        if store.segment_text_sha256(project, stable_id) != entry["text_sha256"]:
            skipped += 1
            continue
        overrides.request_retake(project, stable_id, entry["text_sha256"], now=stamps[entry["requested_at"]])
        requests += 1
    for item in sorted(wishes.get(ALIASES) or [], key=lambda item: item["at"]):
        alias_book.add(project, item["alias"], item["person"], now=stamps[item["at"]])
    return {"requests": requests, "skipped": skipped}
