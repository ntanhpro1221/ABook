"""A+ narration presentation keeps accepted identity and protects recordings."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from abook import narrator_sections, teller_voice
from abook.character_registry import voice_profile_spec
from abook.config import build_settings, settings_hash
from abook.database import ProjectDB
from abook.io_utils import sha256_file
from abook.listener_overrides import request_speaker
from abook.models import ProjectPaths
from abook.voice_catalog import casting_presets, preset_by_name

NARRATOR_VOICE = str(build_settings()["voices"]["narrator_voice"])
FEMALE_NARRATOR = "Kim Thanh"
# Chương 1: kể, lời của Mai, nội tâm của Mai, nội tâm của Bảo, kể. Chương 2: nội tâm của Mai, nội tâm của Bảo, kể.
LINES = [
    (1, "c1s0", "narration", "NARRATOR", "Một câu kể."),
    (1, "c1s1", "dialogue", "MAI", "Một lời nói."),
    (1, "c1s2", "thought", "MAI", "Một ý nghĩ thứ nhất."),
    (1, "c1s3", "thought", "BAO", "Một ý nghĩ thứ hai."),
    (1, "c1s4", "narration", "NARRATOR", "Một câu kể nữa."),
    (2, "c2s0", "thought", "MAI", "Một ý nghĩ thứ ba."),
    (2, "c2s1", "thought", "BAO", "Một ý nghĩ thứ tư."),
    (2, "c2s2", "narration", "NARRATOR", "Một câu kể ở chương hai."),
]


def _settings(identity: str = "Mai", chapters: dict[str, str] | None = None) -> dict[str, Any]:
    settings = build_settings()
    if identity:
        settings["voices"]["first_person_identity"] = identity
    if chapters is not None:
        settings["voices"]["first_person_chapters"] = chapters
    return settings


def _book(tmp_path: Path, *, mai_gender: str = "female", settings: dict[str, Any] | None = None, recorded: bool = False,
          narrator_auto: bool = True) -> tuple[ProjectPaths, ProjectDB, dict[str, Any]]:
    settings = settings or _settings()
    paths = ProjectPaths.build(tmp_path / "project")
    db = ProjectDB(paths.db)
    db.initialize_book(title="T", project_root=paths.root, settings=settings, settings_hash=settings_hash(settings),
                       input_manifest_hash="manifest")
    chapter_ids: dict[int, int] = {}
    for index in (1, 2):
        source = tmp_path / f"00{index}.txt"
        source.write_text("\n".join(text for chapter, *_r, text in LINES if chapter == index), encoding="utf-8")
        chapter_ids[index] = db.ensure_chapters([{
            "chapter_index": index, "title": f"00{index}", "input_path": source, "input_sha256": sha256_file(source),
            "input_size": source.stat().st_size, "output_mp3": paths.chapters / f"00{index}.mp3",
        }])[0]
    for index, chapter_id in chapter_ids.items():
        db.replace_chapter_segments(chapter_id, [
            {"stable_id": stable_id, "seq": seq, "text": text, "text_sha256": f"sha-{stable_id}", "kind_hint": kind}
            for seq, (chapter, stable_id, kind, _speaker, text) in enumerate(line for line in LINES if line[0] == index)
        ])
    narrator = db.upsert_voice_profile({"voice_key": "narrator", "engine": "vieneu", "preset_name": NARRATOR_VOICE,
                                        "description": "kể", "seed": 1, "status": "ready"})
    cast = {"MAI": ("female", preset_by_name("Ngọc Linh")),
            "BAO": ("male", next(p for p in casting_presets("male") if p["name"] != NARRATOR_VOICE))}
    profiles = {"NARRATOR": narrator, **{key: db.upsert_voice_profile(voice_profile_spec(preset)) for key, (_g, preset) in cast.items()}}
    with db.connect() as conn:
        for key, gender in [("NARRATOR", "male"), ("MAI", mai_gender), ("BAO", "male")]:
            conn.execute("INSERT INTO characters(canonical_name,display_name,gender,age,personality,importance,"
                         "mention_count,confidence,locked,created_at,updated_at) VALUES(?,?,?,'adult','','main',1,1,0,0,0)",
                         (key, key.title(), gender))
        for _chapter, stable_id, kind, speaker, _text in LINES:
            conn.execute("UPDATE segments SET kind=?, speaker=?, gender='unknown', status='analyzed',"
                         " canonical_character_id=(SELECT id FROM characters WHERE canonical_name=?), voice_profile_id=? WHERE stable_id=?",
                         (kind, speaker, speaker, profiles[speaker], stable_id))
        if recorded:
            conn.execute("UPDATE segments SET wav_path='take.wav' WHERE stable_id='c1s1'")
    db.finalize_casting()
    if narrator_auto:
        teller_voice.mark_auto(paths.root)
    return paths, db, settings


def _narrator_preset(db: ProjectDB) -> str:
    with db.connect() as conn:
        return str(conn.execute("SELECT preset_name FROM voice_profiles WHERE voice_key='narrator'").fetchone()[0])


def _speakers(db: ProjectDB) -> dict[str, str]:
    with db.connect() as conn:
        return {str(row[0]): str(row[1]) for row in conn.execute("SELECT stable_id, speaker FROM segments")}


def _events(db: ProjectDB, code: str) -> int:
    with db.connect() as conn:
        return int(conn.execute("SELECT COUNT(*) FROM runtime_events WHERE code=?", (code,)).fetchone()[0])


def test_default_a_plus_aligns_narration_and_own_thought_profiles(tmp_path):
    paths, db, settings = _book(tmp_path)
    before = _profiles(db)
    identity = _identities(db)
    messages = []
    result = teller_voice.ensure(paths.root, db, settings, messages.append)
    assert _narrator_preset(db) == FEMALE_NARRATOR
    assert result['narrator']['from'] == NARRATOR_VOICE
    after = _profiles(db)
    assert after['c1s2'] == after['c2s0'] == before['c1s0']
    assert after['c1s1'] == before['c1s1']
    assert after['c1s3'] == before['c1s3'] and after['c2s1'] == before['c2s1']
    assert _identities(db) == identity
    assert _events(db, 'NARRATOR_ALIGNED_TO_TELLER') == 1
    assert _events(db, 'TELLER_THOUGHTS_TO_NARRATOR') == 1
    assert messages and teller_voice.read(paths.root)['applied']['narrator']['to'] == FEMALE_NARRATOR



def test_applying_twice_changes_nothing_more(tmp_path: Path) -> None:
    paths, db, settings = _book(tmp_path)
    teller_voice.ensure(paths.root, db, settings)
    before = (_narrator_preset(db), _speakers(db), _events(db, "NARRATOR_ALIGNED_TO_TELLER"))

    assert teller_voice.ensure(paths.root, db, settings) == {}

    assert (_narrator_preset(db), _speakers(db), _events(db, "NARRATOR_ALIGNED_TO_TELLER")) == before


def test_narrator_auto_false_keeps_base_and_still_applies_own_thought_presentation(tmp_path):
    paths, db, settings = _book(tmp_path, narrator_auto=False)
    before = _profiles(db)
    identity = _identities(db)
    teller_voice.ensure(paths.root, db, settings)
    assert _narrator_preset(db) == NARRATOR_VOICE
    assert _profiles(db)['c1s2'] == before['c1s0']
    assert _identities(db) == identity



def test_a_listener_who_already_changed_the_narration_voice_is_left_alone(tmp_path: Path) -> None:
    paths, db, settings = _book(tmp_path)
    other = next(p["name"] for p in casting_presets("male") if p["name"] not in (NARRATOR_VOICE, FEMALE_NARRATOR))
    with db.transaction() as conn:
        conn.execute("UPDATE voice_profiles SET preset_name=? WHERE voice_key='narrator'", (other,))

    result = teller_voice.ensure(paths.root, db, settings)

    assert _narrator_preset(db) == other and "narrator" not in result


def test_recorded_book_keeps_shared_preset_and_every_recorded_row(tmp_path):
    paths, db, settings = _book(tmp_path, recorded=True)
    with db.transaction() as conn:
        conn.execute("UPDATE segments SET wav_path='thought.wav',wav_sha256='thought-sha',status='verified' WHERE stable_id='c1s2'")
        before = dict(conn.execute("SELECT * FROM segments WHERE stable_id='c1s2'").fetchone())
    profiles = _profiles(db)
    teller_voice.ensure(paths.root, db, settings)
    assert _narrator_preset(db) == NARRATOR_VOICE
    with db.connect() as conn:
        assert dict(conn.execute("SELECT * FROM segments WHERE stable_id='c1s2'").fetchone()) == before
    assert _profiles(db)['c2s0'] == profiles['c1s0']



def test_nothing_happens_before_casting_or_in_a_third_person_book(tmp_path: Path) -> None:
    paths, db, settings = _book(tmp_path, settings=_settings(identity=""))
    assert teller_voice.ensure(paths.root, db, settings) == {"skipped": "third_person"}
    assert _narrator_preset(db) == NARRATOR_VOICE and _speakers(db)["c1s2"] == "MAI"
    paths2, db2, settings2 = _book(tmp_path / "other")
    with db2.transaction() as conn:
        conn.execute("UPDATE book SET casting_finalized=0")
    assert teller_voice.ensure(paths2.root, db2, settings2) == {"skipped": "not_cast"}


def test_unknown_gender_keeps_base_but_known_first_person_identity_selects_thoughts(tmp_path):
    paths, db, settings = _book(tmp_path, mai_gender='unknown')
    before = _profiles(db)
    identity = _identities(db)
    teller_voice.ensure(paths.root, db, settings)
    assert _narrator_preset(db) == NARRATOR_VOICE
    assert _profiles(db)['c1s2'] == before['c1s0']
    assert _profiles(db)['c1s3'] == before['c1s3']
    assert _identities(db) == identity



def test_tied_book_gender_keeps_base_and_local_female_chapter_uses_own_voice(tmp_path):
    paths, db, settings = _book(tmp_path, settings=_settings('Bao', {'2': 'Mai'}))
    before = _profiles(db)
    teller_voice.ensure(paths.root, db, settings)
    after = _profiles(db)
    assert _narrator_preset(db) == NARRATOR_VOICE
    assert after['c1s3'] == before['c1s0']
    assert after['c1s2'] == before['c1s2']
    assert after['c2s0'] == after['c2s2'] == before['c1s1']
    assert after['c2s1'] == before['c2s1']



def test_third_person_chapter_keeps_every_thinker_profile(tmp_path):
    paths, db, settings = _book(tmp_path, settings=_settings(chapters={'2': ''}))
    before = _profiles(db)
    teller_voice.ensure(paths.root, db, settings)
    after = _profiles(db)
    assert after['c1s2'] == before['c1s0']
    assert all(after[sid] == before[sid] for sid in ('c2s0', 'c2s1', 'c2s2'))



def test_listener_thought_choice_wins_and_other_own_thought_still_uses_narration(tmp_path):
    paths, db, settings = _book(tmp_path)
    request_speaker(paths.root, 'c1s2', 'sha-c1s2', 'MAI', now=1.0)
    before = _profiles(db)
    teller_voice.ensure(paths.root, db, settings)
    after = _profiles(db)
    assert after['c1s2'] == before['c1s2']
    assert after['c2s0'] == before['c1s0']
    assert _speakers(db)['c1s2'] == 'MAI'



def test_no_free_narrator_voice_keeps_base_and_emits_warning(tmp_path, monkeypatch):
    paths, db, settings = _book(tmp_path)
    monkeypatch.setattr(teller_voice, 'aligned_narrator_preset', lambda *_args: None)
    messages = []
    result = teller_voice.ensure(paths.root, db, settings, messages.append)
    assert result['narrator'] == 'no_free_voice'
    assert _narrator_preset(db) == NARRATOR_VOICE
    assert _events(db, 'NARRATOR_ALIGN_NO_FREE_VOICE') == 1
    assert messages



def test_the_teller_of_a_section_beats_the_chapter_and_the_book(tmp_path: Path) -> None:
    narrator_sections.decide(tmp_path, 1, 2, 3, accepted=True, narrator="Bao", source="owner")
    narrator_sections.decide(tmp_path, 2, 0, 1, accepted=True, narrator="", source="owner")
    tellers = teller_voice.Tellers(_settings(chapters={"2": "Linh"}), tmp_path, {10: 1, 20: 2})

    assert tellers.active and tellers.identity == "Mai"
    assert tellers.of(10, 1) == "Mai" and tellers.of(10, 2) == "Bao", "đoạn người dùng đã nhận thắng chương và cả cuốn"
    assert tellers.of(20, 5) == "Linh" and tellers.of(20, 0) == "", "đoạn ngôi ba trong chương có người kể"
    assert tellers.chapter(20) == "Linh" and tellers.chapter(10) == "Mai"
    assert not teller_voice.Tellers(_settings(identity=""), tmp_path, {10: 1}).active
    assert teller_voice.Tellers(_settings(identity="tôi"), tmp_path, {10: 1}).identity == "", "đại từ không phải một danh tính"


def test_the_sidecar_survives_a_broken_file_and_new_books_decide_auto_by_the_same_rule(tmp_path: Path) -> None:
    assert teller_voice.read(tmp_path) == {"narratorAuto": False, "mode": "narrator", "applied": {}}
    (tmp_path / teller_voice.FILE_NAME).write_bytes(b"{khong phai json")
    assert teller_voice.read(tmp_path)["narratorAuto"] is False
    teller_voice.mark_auto(tmp_path)
    assert json.loads((tmp_path / teller_voice.FILE_NAME).read_bytes())["narratorAuto"] is True
    assert b"\r\n" not in (tmp_path / teller_voice.FILE_NAME).read_bytes()
    assert teller_voice.auto_for_new_book("Mai", None, "") is True
    assert teller_voice.auto_for_new_book("", {"2": "Linh"}, " ") is True
    assert teller_voice.auto_for_new_book("Mai", None, "Phạm Tuyên") is False
    assert teller_voice.auto_for_new_book("", None, "") is False


def test_a_failure_of_the_teller_voice_never_stops_the_run_but_leaves_a_warning(tmp_path: Path, monkeypatch) -> None:
    from abook import worker

    paths, db, settings = _book(tmp_path)
    messages: list[str] = []

    def broken(*_args, **_kwargs):
        raise RuntimeError("hỏng giữa chừng")

    monkeypatch.setattr(teller_voice, "ensure", broken)

    worker.apply_teller_voice(paths.root, db, settings, messages.append)
    worker.apply_teller_voice(paths.root, db, settings, None)  # pipeline giả không có `log`

    assert _events(db, "TELLER_VOICE_SKIPPED") == 2 and "hỏng giữa chừng" in messages[0]


def test_default_worker_changes_only_presentation_and_never_claims_listener_identity(tmp_path):
    from abook.worker import apply_teller_voice
    paths, db, settings = _book(tmp_path)
    before = _identities(db)
    apply_teller_voice(paths.root, db, settings, None)
    apply_teller_voice(paths.root, db, settings, None)
    assert _identities(db) == before
    assert _events(db, 'SPEAKER_SET_BY_LISTENER') == 0
    assert _events(db, 'TELLER_THOUGHTS_TO_NARRATOR') == 1



def _profiles(db):
    with db.connect() as conn:
        return {r['stable_id']: r['voice_profile_id'] for r in conn.execute('SELECT * FROM segments')}


def _identities(db):
    with db.connect() as conn:
        return [tuple(r) for r in conn.execute('SELECT stable_id,speaker,canonical_character_id,kind FROM segments ORDER BY id')]
