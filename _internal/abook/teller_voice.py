"""Listener-selected narration presentation, independent of speaker identity.

First-person inner speech shares the narration profile in default A+ mode while
retaining the thinking character's identity. Other inner speech keeps its voice. A named
chapter or accepted section teller of a different gender uses their own voice.
Explicit teller mode also applies same-gender voices. Per-line provenance restores
or retargets presentation after reopen without changing speaker identity.
"""
from __future__ import annotations

import json
import sqlite3
import time
from collections.abc import Callable
from contextlib import nullcontext
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

    def local_choice(self, row: Any) -> bool:
        """A chapter setting or accepted section explicitly supplies this teller."""
        index = self.chapter_index.get(int(row["chapter_id"]), -1)
        return (index in self.chapters or narrator_sections.narrator_at(
            self.sections, index, int(row["seq"])) is not None)


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


def profile_gender(profile: Any) -> str:
    from .voice_catalog import engine_voice

    voice = engine_voice(str(profile["preset_name"]), str(profile["engine"]))
    return str(voice["gender"]) if voice is not None else preset_gender(str(profile["preset_name"]))


def chapter_voice_selected(tellers: Tellers, row: Any, mode: str, base_gender: str, gender: str) -> bool:
    """Share the presentation rule between the writer and the export check."""
    return mode == "teller" or (tellers.local_choice(row) and base_gender in GENDERS
                               and gender in GENDERS and gender != base_gender)


def aligned_narrator_preset(connection: sqlite3.Connection, gender: str) -> str | None:
    """Giọng kể chuyện `gender` chưa nhân vật nào giữ: mặc định của giới ấy trước, rồi theo thứ tự danh mục; None khi hết."""
    from .listener_overrides import character_presets
    from .voice_catalog import DEFAULT_NARRATOR_BY_GENDER, narrator_presets

    held = character_presets(connection)
    candidates = [DEFAULT_NARRATOR_BY_GENDER.get(gender, ""), *(str(item["name"]) for item in narrator_presets(gender, automatic=True))]
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
    return any(has_recording(row) for row in connection.execute("SELECT * FROM segments"))


def ensure(project_root: Path | str, db: Any, settings: dict[str, Any], log: Callable[[str], None] = lambda _m: None) -> dict[str, Any]:
    """Apply A+ by default, or the listener's explicit B, preserving identity."""
    if not db.casting_is_finalized():
        return {"skipped": "not_cast"}
    record = read(project_root)
    with db.connect() as connection:
        tellers = tellers_of(project_root, settings, connection)
    result: dict[str, Any] = {}
    if record["mode"] == "teller" and tellers.active:
        result.update(_enable_teller(project_root, db, tellers, log))
        return result
    if tellers.active:
        result.update(_ensure_narrator_mode(project_root, db, settings, tellers, record, log))
    if "teller" in record["applied"]:
        result.update(_disable_teller(project_root, db, log, tellers=tellers))
    else:
        result.update(_ensure_chapter_tellers(project_root, db, tellers, log))
    if not tellers.active:
        return result or {"skipped": "third_person"}
    return result


def _ensure_narrator_mode(project_root: Path | str, db: Any, settings: dict[str, Any], tellers: Tellers,
                          record: dict[str, Any], log: Callable[[str], None]) -> dict[str, Any]:
    """Align an automatic book profile only before any recording exists."""
    from .listener_overrides import narrator_profile

    if not record["narratorAuto"]:
        return {}
    wanted = None
    with db.transaction() as conn:
        if _recorded(conn) or _narrator_chosen(conn, project_root):
            return {}
        profile = narrator_profile(conn)
        configured = str((settings.get("voices") or {}).get("narrator_voice") or "")
        # A changed preset without a recorded wish is still not ours to replace.
        if profile is None or str(profile["preset_name"] or "") != configured:
            return {}
        gender = book_teller_gender(conn, tellers)
        if not gender or profile_gender(profile) in ("", gender):
            return {}
        preset = aligned_narrator_preset(conn, gender)
        if preset:
            wanted = {"reading": configured, "preset": preset, "gender": gender}
            _align_narrator(db, settings, wanted, connection=conn)
    if wanted is None:
        db.event("warning", "NARRATOR_ALIGN_NO_FREE_VOICE",
                 "the first-person narrator's gender differs from the narration voice but every narrator voice of that gender is taken",
                 {"gender": gender})
        log("Không còn giọng dẫn cùng giới người kể “tôi” chưa nhân vật nào giữ; giữ giọng dẫn hiện tại.")
        return {"narrator": "no_free_voice"}
    applied = read(project_root)["applied"]
    applied["narrator"] = {"from": wanted["reading"], "to": wanted["preset"], "gender": gender, "at": time.time()}
    _save(project_root, applied=applied)
    log(f"Người kể xưng “tôi” là {'nữ' if gender == 'female' else 'nam'}: giọng dẫn đổi {wanted['reading']} -> {wanted['preset']}.")
    return {"narrator": applied["narrator"]}


def own_teller_thought(connection: sqlite3.Connection, tellers: Tellers, row: Any) -> bool:
    """The accepted thinker is the named first-person teller at this exact line."""
    return (row["kind"] == "thought" and str(row["speaker"]).upper() != NARRATOR
            and row["canonical_character_id"] in character_ids(connection, tellers.row_narrator(row)))


def has_recording(row: Any) -> bool:
    return bool(row["wav_path"] or row["wav_sha256"] or _heard(row))


def has_presentation_table(connection: sqlite3.Connection) -> bool:
    """A read-only source without this table has no presentation evidence."""
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='chapter_teller_lines'").fetchone() is not None


def presentation_applied(connection: sqlite3.Connection) -> bool:
    """SQLite provenance owns completion, including a crash before the sidecar write."""
    return connection.execute(
        "SELECT 1 FROM segments s JOIN chapter_teller_lines t ON t.segment_id=s.id "
        "WHERE s.speaker=t.original_speaker "
        "AND s.canonical_character_id IS t.original_character_id "
        "AND s.voice_profile_id=t.applied_profile_id LIMIT 1").fetchone() is not None


def _narrator_chosen(connection: sqlite3.Connection, project_root: Path | str) -> bool:
    """Only an explicit narrator wish/applied listener choice suppresses chapter voices.

    narratorAuto=False is NOT evidence of a deliberate choice (CLI-created books also have it).
    """
    from .listener_overrides import read_overrides

    entries = read_overrides(Path(project_root)).get("voices")
    entry = entries.get(NARRATOR) if isinstance(entries, dict) else None
    if isinstance(entry, dict) and str(entry.get("preset") or "").strip():
        return True
    return any(json.loads(row[0]).get("character") == NARRATOR for row in connection.execute(
        "SELECT details_json FROM runtime_events WHERE code='VOICE_SET_BY_LISTENER'"))


def _ensure_chapter_tellers(project_root: Path | str, db: Any, tellers: Tellers,
                            log: Callable[[str], None] = lambda _m: None) -> dict[str, Any]:
    """Apply or undo chapter narration profiles in one transaction.

    Identity stays unchanged. Source-bound provenance and audio resets commit with
    the profile change, so an interrupted update can be safely repeated.
    """
    from .listener_overrides import narrator_profile
    from .database import thought_reads_as_narrator
    from .webui.store import keep_heard_scripts

    record = read(project_root)
    mode = record["mode"]
    allow_recorded = mode == "teller" or "teller" in record["applied"]
    wishes = _wishes(project_root)
    kept = False
    changed = redo = thoughts = 0
    with db.transaction() as conn:
        base = narrator_profile(conn)
        if base is None:
            return {}
        chosen = _narrator_chosen(conn, project_root)
        base_gender = profile_gender(base)
        genders: dict[str, str] = {}
        targets = {}
        origins = {int(r["segment_id"]): dict(r) for r in conn.execute("SELECT * FROM chapter_teller_lines")}
        for row in conn.execute("SELECT * FROM segments WHERE kind IN ('narration','dialogue','thought') ORDER BY chapter_id,seq"):
            stable = str(row["stable_id"])
            origin = origins.get(int(row["id"]))
            if stable in wishes:
                conn.execute("DELETE FROM chapter_teller_lines WHERE segment_id=?", (row["id"],))
                continue
            if origin and (row["speaker"] != origin["original_speaker"] or row["canonical_character_id"] != origin["applied_character_id"]
                           or row["voice_profile_id"] != origin["applied_profile_id"]):
                # A subsequent listener change owns this row, even without a pending wish.
                conn.execute("DELETE FROM chapter_teller_lines WHERE segment_id=?", (row["id"],))
                continue
            # Automatic presentation never invalidates an existing take. Explicit B
            # keeps its priced retake path, including an explicit return from B.
            if not allow_recorded and has_recording(row):
                continue
            original = ({**dict(row), "speaker": origin["original_speaker"],
                         "canonical_character_id": origin["original_character_id"], "voice_profile_id": origin["original_profile_id"]}
                        if origin else dict(row))
            name = tellers.row_narrator(row)
            if name not in targets:
                targets[name] = _teller_target(conn, name, int(base["id"])) if name and not chosen else None
                genders[name] = teller_gender(conn, name)
            target = (targets[name] if chapter_voice_selected(tellers, row, mode, base_gender, genders[name]) else None)
            own_thought = own_teller_thought(conn, tellers, original)
            eligible = str(original["speaker"]).upper() == NARRATOR or thought_reads_as_narrator(
                original["kind"], original["speaker"], original["voice_profile_id"])
            desired_profile = target[1] if target is not None and eligible else original["voice_profile_id"]
            if mode == "narrator" and own_thought:
                desired_profile = target[1] if target is not None else int(base["id"])
            desired = (original["speaker"], original["canonical_character_id"],
                       desired_profile)
            current = (row["speaker"], row["canonical_character_id"], row["voice_profile_id"])
            if desired == current:
                continue
            if not kept:
                keep_heard_scripts(Path(project_root))
                kept = True
            if desired_profile != original["voice_profile_id"]:
                conn.execute("INSERT INTO chapter_teller_lines(segment_id,original_speaker,original_character_id,original_profile_id,"
                             "applied_character_id,applied_profile_id) VALUES(?,?,?,?,?,?) ON CONFLICT(segment_id) DO UPDATE SET"
                             " applied_character_id=excluded.applied_character_id,applied_profile_id=excluded.applied_profile_id",
                             (row["id"], original["speaker"], original["canonical_character_id"], original["voice_profile_id"], original["canonical_character_id"], desired_profile))
            else:
                conn.execute("DELETE FROM chapter_teller_lines WHERE segment_id=?", (row["id"],))
            redo += _move_lines(db, [row], desired[2], "Giọng kể theo chương: thu lại bằng giọng người kể", connection=conn)
            changed += 1
            thoughts += int(own_thought and mode == "narrator" and desired_profile == int(base["id"]))
    if thoughts:
        db.event("info", "TELLER_THOUGHTS_TO_NARRATOR",
                 f"{thoughts} inner thoughts of the first-person narrator are read in the narration voice", {"lines": thoughts})
        log(f"{thoughts} câu nội tâm của chính người kể “tôi” đọc bằng giọng dẫn.")
    return {"chapterNarrator": {"lines": changed, "redo": redo}} if changed else {}


def _wishes(project_root: Path | str) -> set[str]:
    from .listener_overrides import read_overrides

    overrides = read_overrides(Path(project_root))
    # Text edits do not select a voice. Choosing NARRATOR selects ownership; its
    # presentation still follows the chapter, unless a narrator preset was chosen.
    return {stable for stable, entry in (overrides.get("speakers") or {}).items()
            if isinstance(entry, dict) and str(entry.get("speaker") or "").upper() not in ("", NARRATOR, "UNKNOWN")}


def _align_narrator(db: Any, settings: dict[str, Any], wanted: dict[str, Any],
                    *, connection: sqlite3.Connection | None = None) -> None:
    """Đổi preset của chính hồ sơ `narrator` (khoá giữ nguyên - như người nghe đổi giọng dẫn) và giới của nhân vật NARRATOR, một
    transaction. Sách chưa thu câu nào nên không có gì phải thu lại."""
    from .config import build_settings

    preset = wanted["preset"]
    description = build_settings(str(settings.get("quality_profile") or "high_quality"),
                                 {"voices": {"narrator_voice": preset}})["voices"]["narrator_description"]
    now = time.time()
    with (nullcontext(connection) if connection is not None else db.transaction()) as conn:
        db._set_narrator_preset_conn(conn, preset, settings["voices"], now, description=description)
        conn.execute("UPDATE characters SET gender=?, updated_at=? WHERE canonical_name=?", (wanted["gender"], now, NARRATOR))
        conn.execute("INSERT INTO runtime_events(timestamp,level,code,message,details_json) VALUES(?,?,?,?,?)",
                     (now, "info", "NARRATOR_ALIGNED_TO_TELLER",
                      f"narration voice {wanted['reading']} -> {preset} to match the first-person narrator's gender",
                      json.dumps({"from": wanted["reading"], "to": preset, "gender": wanted["gender"]})))

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
    presented = has_presentation_table(connection)
    own_profile = ("CASE WHEN t.segment_id IS NOT NULL AND s.voice_profile_id=t.applied_profile_id"
                   " AND s.speaker=t.original_speaker AND s.canonical_character_id IS t.original_character_id"
                   " THEN t.original_profile_id ELSE s.voice_profile_id END" if presented else "s.voice_profile_id")
    join = " LEFT JOIN chapter_teller_lines t ON t.segment_id=s.id" if presented else ""
    voice = connection.execute(
        f"SELECT {own_profile} AS own_profile, s.speaker, COUNT(*) AS lines FROM segments s{join}"
        " WHERE s.canonical_character_id=? AND s.voice_profile_id IS NOT NULL"
        " AND s.kind IN ('dialogue','thought') GROUP BY own_profile,s.speaker ORDER BY lines DESC,s.speaker LIMIT 1",
        (character_id,)).fetchone()
    if voice is None or voice["own_profile"] is None or int(voice["own_profile"]) == narrator_profile_id:
        return None
    return character_id, int(voice["own_profile"]), str(voice["speaker"])


def teller_lines(connection: sqlite3.Connection, tellers: Tellers) -> tuple[dict[tuple[int, int, str], list[sqlite3.Row]], int]:
    """({(nhân vật, hồ sơ, nhãn): các câu lời kể sẽ chuyển sang họ}, số câu bỏ vì người kể chưa có giọng). Chỉ câu lời kể còn mang giọng
    dẫn, ở đoạn có người kể "tôi" (đoạn người khác kể có tên: theo người ấy; không tên / ngôi ba: giữ giọng dẫn)."""
    from .listener_overrides import narrator_profile
    from .database import thought_reads_as_narrator

    narrator = connection.execute("SELECT id FROM characters WHERE canonical_name=?", (NARRATOR,)).fetchone()
    profile = narrator_profile(connection)
    if narrator is None or profile is None or not tellers.active:
        return {}, 0
    wav = ", wav_path" if "wav_path" in {r[1] for r in connection.execute("PRAGMA table_info(segments)")} else ""
    targets: dict[str, tuple[int, int, str] | None] = {}
    groups: dict[tuple[int, int, str], list[sqlite3.Row]] = {}
    skipped = 0
    for row in connection.execute(
        "SELECT id, stable_id, chapter_id, seq, status, kind, speaker, canonical_character_id, voice_profile_id" + wav
        + " FROM segments WHERE kind IN ('narration','dialogue','thought') ORDER BY chapter_id, seq"):
        narrator_owned = (str(row["speaker"]).upper() == NARRATOR
                          and row["voice_profile_id"] == int(profile["id"])
                          and row["canonical_character_id"] in (None, int(narrator["id"])))
        if not narrator_owned and not thought_reads_as_narrator(row["kind"], row["speaker"], row["voice_profile_id"]):
            continue
        name = tellers.of(int(row["chapter_id"]), int(row["seq"]))
        if not name:
            continue
        if name not in targets:
            targets[name] = _teller_target(connection, name, int(profile["id"]))
        target = targets[name]
        if target is None:
            skipped += 1
        elif row["voice_profile_id"] != target[1]:
            groups.setdefault(target, []).append(row)
    return groups, skipped


def _shown_name(connection: sqlite3.Connection, character_id: Any, label: str) -> str:
    """Tên người kể như tab Nhân vật hiện (display_name), không phải nhãn người nói ("MAI") trong câu."""
    row = connection.execute("SELECT display_name FROM characters WHERE id=?", (character_id,)).fetchone()
    return str(row[0]).strip() if row is not None and row[0] and str(row[0]).strip() else label


def mode_plan(connection: sqlite3.Connection, project_root: Path | str, tellers: Tellers) -> dict[str, Any]:
    """Price an explicit narration voice change without altering any line."""
    from .listener_overrides import narrator_profile
    from .database import thought_reads_as_narrator

    record = read(project_root)
    applied = presentation_applied(connection)
    off = "teller" in record["applied"] or (record["mode"] == "teller" and applied)
    mode = "narrator" if off else "teller"
    base = narrator_profile(connection)
    lines, names = [], set()
    if base is not None:
        chosen = _narrator_chosen(connection, project_root)
        origins = {int(r["segment_id"]): dict(r) for r in connection.execute("SELECT * FROM chapter_teller_lines")}
        wishes, targets, genders = _wishes(project_root), {}, {}
        for row in connection.execute("SELECT * FROM segments ORDER BY chapter_id,seq"):
            origin = origins.get(int(row["id"]))
            if str(row["stable_id"]) in wishes:
                continue
            if origin and (row["speaker"] != origin["original_speaker"] or row["canonical_character_id"] != origin["applied_character_id"]
                           or row["voice_profile_id"] != origin["applied_profile_id"]):
                continue
            original_profile = origin["original_profile_id"] if origin else row["voice_profile_id"]
            own_thought = own_teller_thought(connection, tellers, row)
            eligible = row["speaker"].upper() == NARRATOR or thought_reads_as_narrator(row["kind"], row["speaker"], original_profile)
            if not eligible and not own_thought and origin is None:
                continue
            name = tellers.row_narrator(row)
            if name not in targets:
                targets[name] = _teller_target(connection, name, int(base["id"])) if name and not chosen else None
                genders[name] = teller_gender(connection, name)
            target = targets[name]
            selected = chapter_voice_selected(tellers, row, mode, profile_gender(base), genders[name])
            desired = target[1] if target is not None and selected and eligible else original_profile
            if mode == "narrator" and own_thought:
                desired = target[1] if target is not None and selected else int(base["id"])
            if desired != row["voice_profile_id"]:
                lines.append(row)
                if target is not None:
                    names.add(_shown_name(connection, target[0], target[2]))
    return {"direction": "off" if off else "on", "lines": len(lines),
            "recorded": sum(bool(_heard(row)) for row in lines),
            "tellers": [] if off else sorted(names, key=str.casefold)}


def _move_lines(db: Any, rows: list[Any], profile_id: int | None, reason: str,
                *, connection: sqlite3.Connection | None = None) -> int:
    """Change voice profiles and reset affected audio in the same transaction."""
    now = time.time()
    reset = 0
    chapters: set[int] = set()
    with (nullcontext(connection) if connection is not None else db.transaction()) as conn:
        for row in rows:
            conn.execute("UPDATE segments SET voice_profile_id=?, updated_at=? WHERE id=?",
                         (profile_id, now, int(row["id"])))
            if row["voice_profile_id"] != profile_id and _heard(row):
                db._reset_segment_pending_conn(conn, int(row["id"]), reason, now)
                chapters.add(int(row["chapter_id"]))
                reset += 1
        for chapter_id in sorted(chapters):
            db._refresh_chapter_counts_conn(conn, chapter_id)
            db._mark_listener_redo_conn(conn, chapter_id, reason)
    return reset


def _enable_teller(project_root: Path | str, db: Any, tellers: Tellers, log: Callable[[str], None]) -> dict[str, Any]:
    """Apply the selected narration profile; per-line provenance owns undo."""
    result = _ensure_chapter_tellers(project_root, db, tellers, log)
    change = result.get("chapterNarrator")
    applied = read(project_root)["applied"]
    with db.connect() as conn:
        active = presentation_applied(conn)
    if active and "teller" not in applied:
        applied["teller"] = {"at": time.time()}
        _save(project_root, applied=applied)
    if not change:
        return {}
    db.event("info", "TELLER_NARRATION_TO_TELLER", "Listener selected a narration voice", change)
    return {"teller": {"narration": change["lines"], "redo": change["redo"], "noVoice": 0}}


def _disable_teller(project_root: Path | str, db: Any, log: Callable[[str], None], *, tellers: Tellers) -> dict[str, Any]:
    result = _ensure_chapter_tellers(project_root, db, tellers, log)
    change = result.get("chapterNarrator", {"lines": 0, "redo": 0})
    applied = read(project_root)["applied"]
    applied.pop("teller", None)
    _save(project_root, applied=applied)
    db.event("info", "TELLER_NARRATION_TO_NARRATOR", "Listener restored the narration voice", change)
    return {"teller_off": {"narration": change["lines"], "redo": change["redo"], "thoughts": 0}}
