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
  không giẫm lên người nghe đã đổi lại); `mode` = ý người dùng ("narrator" mặc định, "teller" = B).
- B (tuỳ chọn, mặc định tắt, theo từng sách): người kể "tôi" tự kể chuyện - câu LỜI KỂ của những đoạn do người ấy kể cũng đọc bằng giọng
  của chính họ (nội tâm của "tôi" cũng vậy, nên B thay thế cả hai việc của A+). Đoạn do người khác kể (đoạn đã nhận ở
  `narrator_sections.json`): có tên thì theo cùng luật với người ấy; không tên / ngôi ba thì giữ giọng dẫn. Câu được ghi người nói +
  nhân vật + hồ sơ giọng của người kể (đường mọi nơi khác đã đọc: đổi giọng nhân vật tự theo), và mọi thứ máy đã đổi nằm trong
  `applied["teller"]` nên tắt B trả về đúng như trước (A+ chạy lại như cũ).
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
MODES = ("narrator", "teller")


# ---- sổ cạnh dự án ----------------------------------------------------------------------------------------------

def read(project_root: Path | str) -> dict[str, Any]:
    """{"narratorAuto": bool, "applied": {...}}. File hỏng / chưa có = giọng dẫn là của người dùng, chưa áp gì."""
    try:
        data = json.loads((Path(project_root) / FILE_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    data = data if isinstance(data, dict) else {}
    applied = data.get("applied") if isinstance(data.get("applied"), dict) else {}
    return {"narratorAuto": data.get("narratorAuto") is True, "mode": data.get("mode") if data.get("mode") in MODES else "narrator",
            "applied": applied}


def _save(project_root: Path | str, **changes: Any) -> None:
    """Ghi MỘT phần của sổ trên bản vừa đọc lại: Studio ghi `narratorAuto` / `mode`, worker ghi `applied` - không ai ghi đè phần của người kia."""
    record = {**read(project_root), **changes}
    atomic_write_json(Path(project_root) / FILE_NAME,
                      {"narratorAuto": record["narratorAuto"], "mode": record["mode"], "applied": record["applied"]}, fsync=False)


def mark_auto(project_root: Path | str) -> None:
    """Giọng dẫn của sách này là mặc định máy (người dùng không chọn): máy được chọn theo giới "tôi". Ghi lúc tạo sách."""
    if not read(project_root)["narratorAuto"]:
        _save(project_root, narratorAuto=True)


def set_mode(project_root: Path | str, mode: str) -> None:
    """Ý của người dùng về B ("teller" bật, "narrator" tắt). Chỉ ghi ý muốn; `ensure` (worker, hay Studio khi sách không chạy) áp vào sách."""
    if mode not in MODES:
        raise ValueError("mode must be narrator or teller")
    if read(project_root)["mode"] != mode:
        _save(project_root, mode=mode)


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


def teller_gender(connection: sqlite3.Connection, name: str, *, locked_only: bool = False) -> str:
    """Giới ("male"/"female") của người kể `name` trong sổ nhân vật; "" khi chưa rõ hay không tìm ra họ. `locked_only`: chỉ giới do
    người dùng nói (đã ghim), không tính suy đoán của model."""
    genders = {str(row[0]) for row in connection.execute(
        f"SELECT gender FROM characters WHERE id IN ({','.join(str(i) for i in character_ids(connection, name)) or 'NULL'})"
        + (" AND locked=1" if locked_only else ""))}
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
    """Hoà sổ với sách vừa phân vai xong. Idempotent; không làm gì trước khi phân vai khoá hay khi sách ngôi ba. Lỗi từng phần được
    ghi sự kiện cảnh báo, không bao giờ làm hỏng lượt chạy (người gọi bọc).
    - `mode == "teller"` (B, người dùng đã bật và đã xác nhận cái giá): áp B, kể cả sách đã có bản thu.
    - B đang áp mà người dùng đã tắt: trả về đúng như trước, rồi A+ chạy như thường.
    - A+ (mặc định): chỉ tự áp khi sách CHƯA thu câu nào; có âm thanh rồi thì chỉ có hai thẻ trong hộp Việc cần duyệt."""
    if not db.casting_is_finalized():
        return {"skipped": "not_cast"}
    record = read(project_root)
    with db.connect() as connection:
        tellers = tellers_of(project_root, settings, connection)
    if not tellers.active:
        return {"skipped": "third_person"}
    result: dict[str, Any] = {}
    if "teller" in record["applied"] and record["mode"] != "teller":
        result.update(_disable_teller(project_root, db, log))
        record = read(project_root)
    if record["mode"] == "teller":
        result.update(_enable_teller(project_root, db, tellers, log))
        return result
    result.update(_ensure_narrator_mode(project_root, db, settings, tellers, record, log))
    return result


def _ensure_narrator_mode(project_root: Path | str, db: Any, settings: dict[str, Any], tellers: Tellers, record: dict[str, Any],
                          log: Callable[[str], None]) -> dict[str, Any]:
    """A+ (mục 1 và 2 của đầu file)."""
    result: dict[str, Any] = {}
    applied = record["applied"]
    with db.connect() as connection:
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
        _save(project_root, applied=applied)
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


# ---- B: người kể "tôi" tự kể chuyện ------------------------------------------------------------------------------

CHUNK = 500


def _heard(row: Any) -> bool:
    """Câu đã có bản thu cần bỏ khi đổi giọng (cùng tập trạng thái với `ProjectDB.apply_listener_speaker`)."""
    from .models import SegmentStatus

    return str(row["status"]) in {SegmentStatus.SIGNAL_PASSED.value, SegmentStatus.ASR_PASSED.value, SegmentStatus.VERIFIED.value,
                                  SegmentStatus.WARNING.value, SegmentStatus.FAILED.value}


def _teller_target(connection: sqlite3.Connection, name: str, narrator_profile_id: int) -> tuple[int, int, str] | None:
    """(nhân vật, hồ sơ giọng, nhãn người nói) mà câu kể của người kể `name` sẽ mang: đúng phép `listener_overrides.speaker_target`
    chọn giọng một người (giọng nhiều câu nhất của họ). None: không tìm ra đúng một người, hay người ấy chưa có giọng riêng."""
    ids = character_ids(connection, name)
    if len(ids) != 1:
        return None
    character_id = next(iter(ids))
    voice = connection.execute(
        "SELECT voice_profile_id, speaker, COUNT(*) AS lines FROM segments WHERE canonical_character_id=? AND voice_profile_id IS NOT NULL"
        " AND kind IN ('dialogue','thought') GROUP BY voice_profile_id, speaker ORDER BY lines DESC, speaker LIMIT 1", (character_id,)).fetchone()
    if voice is None or int(voice["voice_profile_id"]) == narrator_profile_id:
        return None
    return character_id, int(voice["voice_profile_id"]), str(voice["speaker"])


def teller_lines(connection: sqlite3.Connection, tellers: Tellers) -> tuple[dict[tuple[int, int, str], list[sqlite3.Row]], int]:
    """({(nhân vật, hồ sơ, nhãn): các câu lời kể sẽ chuyển sang họ}, số câu bỏ vì người kể chưa có giọng). Chỉ câu lời kể còn mang giọng
    dẫn, ở đoạn có người kể "tôi" (đoạn người khác kể có tên: theo người ấy; không tên / ngôi ba: giữ giọng dẫn)."""
    from .listener_overrides import narrator_profile

    narrator = connection.execute("SELECT id FROM characters WHERE canonical_name=?", (NARRATOR,)).fetchone()
    profile = narrator_profile(connection)
    if narrator is None or profile is None or not tellers.active:
        return {}, 0
    wav = ", wav_path" if "wav_path" in {r[1] for r in connection.execute("PRAGMA table_info(segments)")} else ""
    targets: dict[str, tuple[int, int, str] | None] = {}
    groups: dict[tuple[int, int, str], list[sqlite3.Row]] = {}
    skipped = 0
    for row in connection.execute(
        "SELECT id, stable_id, chapter_id, seq, status, speaker, canonical_character_id, voice_profile_id" + wav
        + " FROM segments WHERE kind='narration' AND UPPER(speaker)='NARRATOR' AND voice_profile_id=?"
        " AND (canonical_character_id IS NULL OR canonical_character_id=?) ORDER BY chapter_id, seq", (int(profile["id"]), int(narrator["id"]))):
        name = tellers.of(int(row["chapter_id"]), int(row["seq"]))
        if not name:
            continue
        if name not in targets:
            targets[name] = _teller_target(connection, name, int(profile["id"]))
        target = targets[name]
        if target is None:
            skipped += 1
        else:
            groups.setdefault(target, []).append(row)
    return groups, skipped


def _count_heard(connection: sqlite3.Connection, ids: list[str], extra: str = "", params: tuple[Any, ...] = ()) -> tuple[int, int]:
    """(số câu còn nguyên trong `ids` [theo điều kiện `extra`], số câu trong đó đã thu)."""
    wav = "wav_path" in {r[1] for r in connection.execute("PRAGMA table_info(segments)")}
    total = heard = 0
    for offset in range(0, len(ids), CHUNK):
        part = ids[offset:offset + CHUNK]
        for row in connection.execute("SELECT status" + (", wav_path" if wav else "") + f" FROM segments WHERE stable_id IN ({','.join('?' * len(part))}){extra}",
                                      (*part, *params)):
            total += 1
            heard += 1 if wav and row["wav_path"] and _heard(row) else 0
    return total, heard


def _shown_name(connection: sqlite3.Connection, character_id: Any, label: str) -> str:
    """Tên người kể như tab Nhân vật hiện (display_name), không phải nhãn người nói ("MAI") trong câu."""
    row = connection.execute("SELECT display_name FROM characters WHERE id=?", (character_id,)).fetchone()
    return str(row[0]).strip() if row is not None and row[0] and str(row[0]).strip() else label


def mode_plan(connection: sqlite3.Connection, project_root: Path | str, tellers: Tellers) -> dict[str, Any]:
    """Cái giá của việc đổi chế độ, cho hộp xác nhận: {"direction": "on"/"off", "lines": số câu đổi giọng, "recorded": số câu trong đó đã
    thu (phải thu lại), "tellers": những người kể bị chạm}. Bật: câu lời kể của đoạn do người kể "tôi" kể + nội tâm A+ đã chuyển
    sang giọng dẫn (trả về giọng nhân vật). Tắt: đúng những câu B đã chuyển."""
    applied = read(project_root)["applied"]
    state = applied.get("teller")
    lines = recorded = 0
    names: list[str] = []
    if isinstance(state, dict):
        for group in state.get("groups") or []:
            total, heard = _count_heard(connection, [str(item) for item in group.get("lines") or []],
                                        " AND canonical_character_id=? AND voice_profile_id=?", (group["character_id"], group["profile_id"]))
            lines, recorded = lines + total, recorded + heard
            names.append(_shown_name(connection, group.get("character_id"), str(group.get("speaker") or "")))
        thought_ids, direction = [str(item) for item in state.get("thoughts") or {}], "off"
    else:
        groups, _skipped = teller_lines(connection, tellers)
        lines = sum(len(rows) for rows in groups.values())
        recorded = sum(1 for rows in groups.values() for row in rows if "wav_path" in row.keys() and row["wav_path"] and _heard(row))  # noqa: SIM118 - sqlite3.Row: `in` xét giá trị
        names = [_shown_name(connection, character, label) for character, _profile, label in groups]
        thought_ids, direction = [str(item) for item in applied.get("thoughts") or {}], "on"
    total, heard = _count_heard(connection, thought_ids)
    return {"direction": direction, "lines": lines + total, "recorded": recorded + heard, "tellers": sorted(set(names), key=str.casefold)}


def _move_lines(db: Any, rows: list[Any], speaker: str, character_id: int, profile_id: int, reason: str) -> int:
    """Chuyển các câu sang (người nói, nhân vật, hồ sơ) trong MỘT transaction; câu đã thu mà giọng đổi thì đặt lại (như mọi lần người nghe
    đổi giọng) và chương xong chuyển sang "thu lại" chứ không thành lỗi. Trả số câu đã đặt lại."""
    from .database import LISTENER_REDO
    from .models import ChapterStatus

    now = time.time()
    reset = 0
    chapters: set[int] = set()
    with db.transaction() as conn:
        for row in rows:
            conn.execute("UPDATE segments SET speaker=?, canonical_character_id=?, voice_profile_id=?, updated_at=? WHERE id=?",
                         (speaker, character_id, profile_id, now, int(row["id"])))
            if row["voice_profile_id"] != profile_id and _heard(row):
                db._reset_segment_pending_conn(conn, int(row["id"]), reason, now)
                chapters.add(int(row["chapter_id"]))
                reset += 1
        for chapter_id in sorted(chapters):
            db._refresh_chapter_counts_conn(conn, chapter_id)
            conn.execute("UPDATE chapters SET status='warning', last_error=? WHERE id=? AND status=?",
                         (LISTENER_REDO + reason, chapter_id, ChapterStatus.COMPLETED.value))
    return reset


def _enable_teller(project_root: Path | str, db: Any, tellers: Tellers, log: Callable[[str], None]) -> dict[str, Any]:
    """Bật B. (1) nội tâm của "tôi" mà A+ đã chuyển sang giọng dẫn trở về giọng nhân vật (B thay thế A+: cả lời kể lẫn nội tâm đều là
    giọng của chính họ); (2) câu lời kể của đoạn do người kể "tôi" kể sang họ. Ý định ghi vào sổ TRƯỚC khi sửa sách (chết giữa chừng
    thì lần sau làm tiếp, và tắt B vẫn trả đúng những câu đã chuyển)."""
    applied = read(project_root)["applied"]
    state = applied.get("teller") if isinstance(applied.get("teller"), dict) else {"groups": [], "thoughts": {}, "at": time.time()}
    result: dict[str, Any] = {}
    changed = "teller" not in applied

    thoughts = dict(applied.get("thoughts") or {})
    if thoughts:
        with db.connect() as connection:
            current = {str(row["stable_id"]): row for row in connection.execute("SELECT stable_id, speaker, text_sha256 FROM segments")}
        left: dict[str, str] = {}
        for stable_id, old in thoughts.items():
            row = current.get(stable_id)
            if row is None or str(row["speaker"]).upper() != NARRATOR:
                left[stable_id] = old  # người nghe đã đổi câu này (hay câu không còn): máy không động tới
                continue
            outcome = db.apply_listener_speaker(stable_id=stable_id, text_sha256=str(row["text_sha256"] or ""), speaker=old)
            if outcome is not None and "problem" in outcome:
                left[stable_id] = old
            else:
                state["thoughts"][stable_id] = old
        if len(left) != len(thoughts):
            changed = True
            result["thoughts_back"] = len(thoughts) - len(left)
            if left:
                applied["thoughts"] = left
            else:
                applied.pop("thoughts", None)

    with db.connect() as connection:
        groups, no_voice = teller_lines(connection, tellers)
    for (character_id, profile_id, speaker), rows in groups.items():
        known = next((group for group in state["groups"]
                      if (group["character_id"], group["profile_id"], group["speaker"]) == (character_id, profile_id, speaker)), None)
        if known is None:
            known = {"character_id": character_id, "profile_id": profile_id, "speaker": speaker, "lines": []}
            state["groups"].append(known)
        known["lines"] = sorted(set(known["lines"]) | {str(row["stable_id"]) for row in rows})
        changed = True
    applied["teller"] = state
    if changed:
        _save(project_root, applied=applied)  # ý định trước, sửa sách sau

    moved = redo = 0
    for (character_id, profile_id, speaker), rows in groups.items():
        redo += _move_lines(db, rows, speaker, character_id, profile_id, f"Người kể “tôi” tự kể chuyện: câu kể thu lại bằng giọng của {speaker}")
        moved += len(rows)
    if moved or result:
        result.update({"narration": moved, "redo": redo, "noVoice": no_voice})
        db.event("info", "TELLER_NARRATION_TO_TELLER",
                 f"{moved} narration lines are read in the first-person narrator's own voice ({redo} re-recorded)",
                 {"lines": moved, "redo": redo, "no_voice": no_voice, "thoughts_back": result.get("thoughts_back", 0)})
        log(f"Người kể “tôi” tự kể chuyện: {moved} câu lời kể đọc bằng giọng của chính họ.")
    elif no_voice:
        result["noVoice"] = no_voice
    return {"teller": result} if result else {}


def _disable_teller(project_root: Path | str, db: Any, log: Callable[[str], None]) -> dict[str, Any]:
    """Tắt B: đúng những câu B đã chuyển (và còn nguyên như B để lại) về giọng dẫn, nội tâm A+ đã trả về nhân vật lại về giọng dẫn."""
    from .listener_overrides import narrator_profile

    applied = read(project_root)["applied"]
    state = applied.get("teller") if isinstance(applied.get("teller"), dict) else {}
    with db.connect() as connection:
        narrator = connection.execute("SELECT id FROM characters WHERE canonical_name=?", (NARRATOR,)).fetchone()
        profile = narrator_profile(connection)
    moved = redo = 0
    if narrator is not None and profile is not None:
        for group in state.get("groups") or []:
            ids = [str(item) for item in group.get("lines") or []]
            for offset in range(0, len(ids), CHUNK):
                part = ids[offset:offset + CHUNK]
                with db.connect() as connection:
                    rows = connection.execute(
                        "SELECT id, chapter_id, status, voice_profile_id FROM segments WHERE kind='narration' AND canonical_character_id=?"
                        f" AND voice_profile_id=? AND stable_id IN ({','.join('?' * len(part))})",
                        (group["character_id"], group["profile_id"], *part)).fetchall()
                redo += _move_lines(db, rows, NARRATOR, int(narrator["id"]), int(profile["id"]),
                                    "Người kể “tôi” thôi tự kể chuyện: câu kể trở về giọng dẫn")
                moved += len(rows)
    returned: dict[str, str] = {}
    for stable_id, old in dict(state.get("thoughts") or {}).items():
        with db.connect() as connection:
            row = connection.execute("SELECT speaker, text_sha256 FROM segments WHERE stable_id=?", (stable_id,)).fetchone()
        if row is None or str(row["speaker"]) != old:
            continue  # người nghe đã đổi câu này sau đó
        outcome = db.apply_listener_speaker(stable_id=stable_id, text_sha256=str(row["text_sha256"] or ""), speaker=NARRATOR)
        if outcome is None or "problem" not in outcome:
            returned[stable_id] = old
    applied.pop("teller", None)
    if returned:
        applied["thoughts"] = {**(applied.get("thoughts") or {}), **returned}
    _save(project_root, applied=applied)
    db.event("info", "TELLER_NARRATION_TO_NARRATOR", f"{moved} narration lines are back in the narration voice ({redo} to re-record)",
             {"lines": moved, "redo": redo, "thoughts": len(returned)})
    log(f"Người kể “tôi” thôi tự kể chuyện: {moved} câu kể trở về giọng dẫn.")
    return {"teller_off": {"narration": moved, "redo": redo, "thoughts": len(returned)}}
