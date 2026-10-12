"""Giọng của người kể "tôi" (A+, chủ sách 12-10): sách kể ngôi thứ nhất thì giọng dẫn cùng giới với nhân vật "tôi", và nội tâm của
chính "tôi" đọc bằng giọng dẫn (lời "tôi" nói ra vẫn là giọng nhân vật; nội tâm của mọi người khác và mọi sách ngôi ba giữ nguyên
quyết định 20-09 - `database.thought_reads_as_narrator`).

MỘT chỗ đặt luật. Không sửa file khoá: kết quả ghi bằng đúng những đường người nghe đã dùng để đổi giọng dẫn / gán một câu nội tâm
cho Người kể (`ProjectDB.apply_listener_speaker`, đổi preset của hồ sơ `narrator`), nên tts, kiểm bản thu, ứng viên chấm lại,
`narrator_voiced`... chỉ đọc cột giọng như mọi khi và tự theo.

- `Tellers`: "người kể 'tôi' của đoạn này" (đoạn người dùng đã nhận > chương > cả cuốn; "" = ngôi ba) - dùng chung với tab Kịch bản và
  hộp Việc cần duyệt (`webui/work_items.first_person_lookup`).
- `ensure`: gọi từ worker ngay sau khi phân vai khoá và trước mỗi lần chạy (resume). Chỉ tự áp khi sách CHƯA thu câu nào; có âm thanh
  rồi thì để hai thẻ trong hộp Việc cần duyệt (mặc định không áp).
- Sổ `studio_narrator.json` cạnh dự án (như `studio_precast.json`, chỉ Studio/worker ghi, không theo file .abook): `narratorAuto` = giọng
  dẫn là mặc định máy (người dùng không chọn) nên máy được chọn theo giới; `applied` = những gì máy đã làm (để không làm hai lần và
  không giẫm lên người nghe đã đổi lại).
"""
from __future__ import annotations

import json
import sqlite3
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from . import narrator_sections
from .io_utils import atomic_write_json

FILE_NAME = "studio_narrator.json"
NARRATOR = "NARRATOR"
GENDERS = ("male", "female")


# ---- sổ cạnh dự án ----------------------------------------------------------------------------------------------

def read(project_root: Path | str) -> dict[str, Any]:
    """{"narratorAuto": bool, "applied": {...}}. File hỏng / chưa có = giọng dẫn là của người dùng, chưa áp gì."""
    try:
        data = json.loads((Path(project_root) / FILE_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    data = data if isinstance(data, dict) else {}
    applied = data.get("applied") if isinstance(data.get("applied"), dict) else {}
    return {"narratorAuto": data.get("narratorAuto") is True, "applied": applied}


def _write(project_root: Path | str, record: dict[str, Any]) -> None:
    atomic_write_json(Path(project_root) / FILE_NAME, {"narratorAuto": record["narratorAuto"], "applied": record["applied"]},
                      fsync=False)


def mark_auto(project_root: Path | str) -> None:
    """Giọng dẫn của sách này là mặc định máy (người dùng không chọn): máy được chọn theo giới "tôi". Ghi lúc tạo sách."""
    record = read(project_root)
    if not record["narratorAuto"]:
        _write(project_root, {**record, "narratorAuto": True})


def auto_for_new_book(first_person: str, chapter_narrators: dict[str, str] | None, narrator: str) -> bool:
    """Sách mới có tự chọn giọng dẫn không: có người kể "tôi" và người dùng không chọn giọng (cùng luật cho trình tạo sách và CLI)."""
    return bool(not narrator.strip() and (first_person.strip() or any(str(name).strip() for name in (chapter_narrators or {}).values())))


# ---- người kể "tôi" của từng đoạn --------------------------------------------------------------------------------

class Tellers:
    """Người kể "tôi" của sách: `identity` (cả cuốn), `chapters` (theo chương), đoạn người dùng đã nhận (`narrator_sections.json`).
    `chapter_index`: {chapters.id: chapters.chapter_index}. Rỗng ở đâu đó = ngôi ba ở đó."""

    def __init__(self, settings: dict[str, Any], project_root: Path | str | None, chapter_index: dict[int, int]) -> None:
        from .analysis import FIRST_PERSON_PRONOUNS, first_person_chapters

        voices = settings.get("voices") if isinstance(settings.get("voices"), dict) else {}
        identity = str(voices.get("first_person_identity") or "").strip()
        self.identity = "" if identity.casefold() in FIRST_PERSON_PRONOUNS else identity
        self.chapters = first_person_chapters(settings)
        self.chapter_index = chapter_index
        self.sections = (narrator_sections.accepted(narrator_sections.load(project_root))
                         if project_root is not None and (self.identity or self.chapters) else {})

    @property
    def active(self) -> bool:
        return bool(self.identity or self.chapters)

    def chapter(self, chapter_id: int) -> str:
        return self.chapters.get(self.chapter_index.get(int(chapter_id), -1), self.identity)

    def of(self, chapter_id: int, seq: int) -> str:
        found = narrator_sections.narrator_at(self.sections, self.chapter_index.get(int(chapter_id), 0), int(seq)) if self.sections else None
        return self.chapter(chapter_id) if found is None else found

    def row_narrator(self, row: Any) -> str:
        return self.of(int(row["chapter_id"]), int(row["seq"]))


def tellers_of(project_root: Path | str, settings: dict[str, Any], connection: sqlite3.Connection) -> Tellers:
    index = {int(row[0]): int(row[1]) if row[1] is not None else int(row[0])
             for row in connection.execute("SELECT id, chapter_index FROM chapters")}
    return Tellers(settings, project_root, index)


def character_ids(connection: sqlite3.Connection, name: str) -> set[int]:
    """Các hàng `characters` là người tên `name`: tên chuẩn, bí danh, hay (nếu duy nhất) một chữ tên riêng của tên đầy đủ trong sổ."""
    from .character_registry import canonical_key, normalize_name

    if not name.strip():
        return set()
    key = canonical_key(name)
    exact = {int(row[0]) for row in connection.execute("SELECT id FROM characters WHERE canonical_name=?", (key,))}
    if exact:
        return exact
    try:
        alias = {int(row[0]) for row in connection.execute(
            "SELECT character_id FROM character_aliases WHERE normalized_alias=?", (normalize_name(name),))}
    except sqlite3.OperationalError:
        alias = set()
    if alias:
        return alias
    near = {int(row[0]) for row in connection.execute("SELECT id, canonical_name, display_name FROM characters")
            if narrator_sections.same_narrator(str(row[1] or ""), name) or narrator_sections.same_narrator(str(row[2] or ""), name)}
    return near if len(near) == 1 else set()


def teller_gender(connection: sqlite3.Connection, name: str) -> str:
    """Giới ("male"/"female") của người kể `name` trong sổ nhân vật; "" khi chưa rõ hay không tìm ra họ."""
    genders = {str(row[0]) for row in connection.execute(
        f"SELECT gender FROM characters WHERE id IN ({','.join(str(i) for i in character_ids(connection, name)) or 'NULL'})")}
    genders &= set(GENDERS)
    return genders.pop() if len(genders) == 1 else ""


def book_teller_gender(connection: sqlite3.Connection, tellers: Tellers) -> str:
    """Giới người kể "tôi" của CẢ cuốn: giới của người kể ở nhiều chương nhất (chương ngôi ba không tính); hoà hay chưa rõ = ""."""
    count: dict[str, int] = {}
    for chapter_id in tellers.chapter_index:
        name = tellers.chapter(chapter_id)
        if name:
            count[name] = count.get(name, 0) + 1
    votes = {gender: 0 for gender in GENDERS}
    for name, chapters in count.items():
        gender = teller_gender(connection, name)
        if gender:
            votes[gender] += chapters
    if votes["male"] == votes["female"]:
        return ""
    return "male" if votes["male"] > votes["female"] else "female"


# ---- giọng dẫn cùng giới ------------------------------------------------------------------------------------------

def preset_gender(preset: str) -> str:
    from .voice_catalog import narrator_presets

    return next((str(item["gender"]) for item in narrator_presets() if item["name"] == preset), "")


def aligned_narrator_preset(connection: sqlite3.Connection, gender: str) -> str | None:
    """Giọng kể chuyện `gender` chưa nhân vật nào giữ: mặc định của giới ấy trước, rồi theo thứ tự danh mục; None khi hết."""
    from .listener_overrides import character_presets
    from .voice_catalog import DEFAULT_NARRATOR_BY_GENDER, narrator_presets

    held = character_presets(connection)
    candidates = [DEFAULT_NARRATOR_BY_GENDER.get(gender, ""), *(str(item["name"]) for item in narrator_presets(gender))]
    return next((name for name in candidates if name and name not in held), None)


def narrator_mismatch(connection: sqlite3.Connection, tellers: Tellers) -> dict[str, Any] | None:
    """Giọng dẫn đang đọc khác giới người kể "tôi" (đã rõ giới) mà còn giọng cùng giới chưa ai giữ: {"gender", "reading", "preset"};
    None nếu không (sách ngôi ba, giới chưa rõ, đã khớp, hồ sơ giọng dẫn chưa có, hết giọng)."""
    from .listener_overrides import narrator_profile

    if not tellers.active:
        return None
    try:
        profile = narrator_profile(connection)
    except sqlite3.OperationalError:
        return None
    if profile is None:
        return None
    gender = book_teller_gender(connection, tellers)
    reading = str(profile["preset_name"] or "")
    if not gender or preset_gender(reading) in ("", gender):
        return None
    preset = aligned_narrator_preset(connection, gender)
    return {"gender": gender, "reading": reading, "preset": preset} if preset else None


# ---- nội tâm của chính "tôi" --------------------------------------------------------------------------------------

def teller_thoughts(connection: sqlite3.Connection, tellers: Tellers, *, skip: set[str] = frozenset()) -> list[sqlite3.Row]:
    """Câu nội tâm do chính người kể "tôi" CỦA ĐOẠN ấy nghĩ (nhân vật của câu == người kể của câu) mà chưa về Người kể. `skip`: mã
    câu đã bỏ qua (máy đã đổi một lần, hay người nghe đã quyết)."""
    if not tellers.active:
        return []
    cache: dict[str, set[int]] = {}
    found = []
    for row in connection.execute(
        "SELECT id, stable_id, chapter_id, seq, text, text_sha256, speaker, kind, voice_profile_id, canonical_character_id"
        + (", wav_path" if "wav_path" in {r[1] for r in connection.execute("PRAGMA table_info(segments)")} else "")
        + " FROM segments WHERE kind='thought' AND canonical_character_id IS NOT NULL AND UPPER(speaker)<>'NARRATOR'"
        " ORDER BY chapter_id, seq"
    ):
        if str(row["stable_id"]) in skip:
            continue
        name = tellers.of(int(row["chapter_id"]), int(row["seq"]))
        if name and int(row["canonical_character_id"]) in cache.setdefault(name, character_ids(connection, name)):
            found.append(row)
    return found


# ---- áp ---------------------------------------------------------------------------------------------------------

def _recorded(connection: sqlite3.Connection) -> bool:
    if "wav_path" not in {row[1] for row in connection.execute("PRAGMA table_info(segments)")}:
        return False
    return connection.execute("SELECT 1 FROM segments WHERE wav_path IS NOT NULL AND wav_path<>'' LIMIT 1").fetchone() is not None


def ensure(project_root: Path | str, db: Any, settings: dict[str, Any], log: Callable[[str], None] = lambda _m: None) -> dict[str, Any]:
    """Áp A+ cho sách vừa phân vai xong. Idempotent; không làm gì trước khi phân vai khoá, khi sách ngôi ba, hay khi đã có câu thu
    âm (khi đó chỉ có thẻ đề xuất). Lỗi từng phần được ghi sự kiện cảnh báo, không bao giờ làm hỏng lượt chạy (người gọi bọc)."""
    result: dict[str, Any] = {}
    if not db.casting_is_finalized():
        return {"skipped": "not_cast"}
    record = read(project_root)
    applied = record["applied"]
    with db.connect() as connection:
        tellers = tellers_of(project_root, settings, connection)
        if not tellers.active:
            return {"skipped": "third_person"}
        if _recorded(connection):
            return {"skipped": "recorded"}
        # (1) giọng dẫn cùng giới: chỉ khi máy chọn giọng dẫn (mặc định), người nghe chưa đổi nó (preset đang đọc còn là giọng của
        #     cài đặt), và máy chưa làm việc này.
        wanted: dict[str, Any] | None = None
        if record["narratorAuto"] and "narrator" not in applied:
            from .listener_overrides import narrator_profile

            profile = narrator_profile(connection)
            configured = str((settings.get("voices") or {}).get("narrator_voice") or "")
            if profile is not None and str(profile["preset_name"] or "") == configured:
                wanted = narrator_mismatch(connection, tellers)
                gender = book_teller_gender(connection, tellers)
                if wanted is None and gender and preset_gender(configured) not in ("", gender):
                    # Khác giới mà hết giọng cùng giới chưa ai giữ: không đổi gì, chỉ báo (mỗi lần chạy lại báo lại).
                    db.event("warning", "NARRATOR_ALIGN_NO_FREE_VOICE",
                             "the first-person narrator's gender differs from the narration voice but every narrator voice of that gender is taken",
                             {"gender": gender})
                    result["narrator"] = "no_free_voice"
        thoughts = teller_thoughts(connection, tellers, skip=set(applied.get("thoughts") or {}))
    if wanted is not None:
        _align_narrator(db, settings, wanted)
        applied["narrator"] = {"from": wanted["reading"], "to": wanted["preset"], "gender": wanted["gender"], "at": time.time()}
        result["narrator"] = applied["narrator"]
        log(f"Người kể xưng “tôi” là {'nữ' if wanted['gender'] == 'female' else 'nam'}: giọng dẫn đổi {wanted['reading']} -> {wanted['preset']}.")
    if thoughts:
        wishes = _wishes(project_root)
        moved: dict[str, str] = dict(applied.get("thoughts") or {})
        for row in thoughts:
            stable_id = str(row["stable_id"])
            if stable_id in wishes:
                continue  # người nghe đã quyết câu này (kể cả "giữ nguyên"): không giẫm lên
            outcome = db.apply_listener_speaker(stable_id=stable_id, text_sha256=str(row["text_sha256"] or ""), speaker=NARRATOR)
            if outcome is None or "problem" not in outcome:
                moved[stable_id] = str(row["speaker"])
        count = len(moved) - len(applied.get("thoughts") or {})
        if count:
            applied["thoughts"] = moved
            result["thoughts"] = count
            db.event("info", "TELLER_THOUGHTS_TO_NARRATOR",
                     f"{count} inner thoughts of the first-person narrator are read in the narration voice",
                     {"lines": count})
            log(f"{count} câu nội tâm của chính người kể “tôi” đọc bằng giọng dẫn.")
    if result:
        _write(project_root, {"narratorAuto": record["narratorAuto"], "applied": applied})
    return result


def _wishes(project_root: Path | str) -> set[str]:
    from .listener_overrides import read_overrides

    entries = read_overrides(Path(project_root)).get("speakers")
    return set(entries) if isinstance(entries, dict) else set()


def _align_narrator(db: Any, settings: dict[str, Any], wanted: dict[str, Any]) -> None:
    """Đổi preset của chính hồ sơ `narrator` (khoá giữ nguyên - như người nghe đổi giọng dẫn) và giới của nhân vật NARRATOR, một
    transaction. Sách chưa thu câu nào nên không có gì phải thu lại."""
    from .config import build_settings

    preset = wanted["preset"]
    description = build_settings(str(settings.get("quality_profile") or "high_quality"),
                                 {"voices": {"narrator_voice": preset}})["voices"]["narrator_description"]
    now = time.time()
    with db.transaction() as conn:
        conn.execute("UPDATE voice_profiles SET preset_name=?, description=?, updated_at=? WHERE voice_key='narrator' COLLATE NOCASE",
                     (preset, description, now))
        conn.execute("UPDATE characters SET gender=?, updated_at=? WHERE canonical_name=?", (wanted["gender"], now, NARRATOR))
    db.event("info", "NARRATOR_ALIGNED_TO_TELLER",
             f"narration voice {wanted['reading']} -> {preset} to match the first-person narrator's gender",
             {"from": wanted["reading"], "to": preset, "gender": wanted["gender"]})
