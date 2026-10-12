"""B (tuỳ chọn, mặc định tắt): người kể "tôi" tự kể chuyện - câu lời kể của đoạn do họ kể đọc bằng giọng của chính họ.
Bật khi sách đã có bản thu thì chỉ những câu đổi giọng bị thu lại; tắt trả về đúng như trước (`applied["teller"]`)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from abook import narrator_sections, teller_voice
from abook.character_registry import assert_voice_stability
from abook.config import build_settings
from abook.database import LISTENER_REDO, ProjectDB
from abook.voice_catalog import casting_presets
from tests.test_teller_voice import _book, _events, _settings, _speakers


def _rows(db: ProjectDB) -> list[tuple]:
    with db.connect() as conn:
        return [tuple(row) for row in conn.execute(
            "SELECT stable_id, speaker, canonical_character_id, voice_profile_id, status FROM segments ORDER BY stable_id")]


def _record_everything(db: ProjectDB) -> None:
    with db.transaction() as conn:
        conn.execute("UPDATE segments SET status='verified', wav_path='take.wav', wav_sha256='sha'")
        conn.execute("UPDATE chapters SET status='completed'")


def _profile_of(db: ProjectDB, stable_id: str) -> tuple[int, int, str]:
    with db.connect() as conn:
        row = conn.execute("SELECT canonical_character_id, voice_profile_id, speaker FROM segments WHERE stable_id=?", (stable_id,)).fetchone()
    return int(row[0]), int(row[1]), str(row[2])


def test_the_switch_is_off_by_default_and_a_book_stays_as_it_was(tmp_path: Path) -> None:
    paths, db, settings = _book(tmp_path)
    assert teller_voice.read(paths.root)["mode"] == "narrator"

    teller_voice.ensure(paths.root, db, settings)

    assert _speakers(db)["c1s0"] == "NARRATOR" and _speakers(db)["c2s2"] == "NARRATOR"


def test_on_a_book_without_audio_the_narration_of_the_teller_takes_the_tellers_voice(tmp_path: Path) -> None:
    paths, db, settings = _book(tmp_path)
    teller_voice.set_mode(paths.root, "teller")

    result = teller_voice.ensure(paths.root, db, settings)

    assert result["teller"]["narration"] == 3 and result["teller"]["redo"] == 0
    speakers = _speakers(db)
    assert speakers["c1s0"] == speakers["c1s4"] == speakers["c2s2"] == "MAI"
    assert _profile_of(db, "c1s0")[:2] == _profile_of(db, "c1s1")[:2], "cùng nhân vật và cùng hồ sơ giọng với lời Mai nói"
    assert speakers["c1s2"] == "MAI" and speakers["c1s3"] == "BAO", "nội tâm là giọng chính họ, không qua giọng dẫn"
    assert _events(db, "TELLER_NARRATION_TO_TELLER") == 1
    assert_voice_stability(db)


def test_applying_twice_changes_nothing_more(tmp_path: Path) -> None:
    paths, db, settings = _book(tmp_path)
    teller_voice.set_mode(paths.root, "teller")
    teller_voice.ensure(paths.root, db, settings)
    before = (_rows(db), teller_voice.read(paths.root))

    assert teller_voice.ensure(paths.root, db, settings) == {}

    assert (_rows(db), teller_voice.read(paths.root)) == before


def test_turning_it_off_restores_the_book_exactly_including_what_the_plus_mode_did(tmp_path: Path) -> None:
    paths, db, settings = _book(tmp_path)
    teller_voice.ensure(paths.root, db, settings)  # A+: giọng dẫn nữ, nội tâm của Mai về giọng dẫn
    plus = (_rows(db), teller_voice.read(paths.root)["applied"])
    assert _speakers(db)["c1s2"] == "NARRATOR"

    teller_voice.set_mode(paths.root, "teller")
    on = teller_voice.ensure(paths.root, db, settings)
    speakers = _speakers(db)
    assert on["teller"]["thoughts_back"] == 2 and speakers["c1s2"] == "MAI" and speakers["c2s0"] == "MAI"
    assert speakers["c1s0"] == "MAI" and "thoughts" not in teller_voice.read(paths.root)["applied"]

    teller_voice.set_mode(paths.root, "narrator")
    off = teller_voice.ensure(paths.root, db, settings)

    assert off["teller_off"]["narration"] == 3 and off["teller_off"]["thoughts"] == 2
    after = (_rows(db), teller_voice.read(paths.root)["applied"])
    assert after[0] == plus[0], "đúng như trước khi bật B, từng câu từng cột"
    assert after[1]["thoughts"] == plus[1]["thoughts"] and after[1]["narrator"] == plus[1]["narrator"] and "teller" not in after[1]
    assert teller_voice.ensure(paths.root, db, settings) == {}


def test_turning_it_on_after_recording_resets_only_the_lines_whose_voice_changes_and_says_the_price_first(tmp_path: Path) -> None:
    paths, db, settings = _book(tmp_path)
    _record_everything(db)
    teller_voice.set_mode(paths.root, "teller")
    with db.connect() as conn:
        plan = teller_voice.mode_plan(conn, paths.root, teller_voice.tellers_of(paths.root, settings, conn))
    assert plan == {"direction": "on", "lines": 3, "recorded": 3, "tellers": ["Mai"]}

    result = teller_voice.ensure(paths.root, db, settings)

    assert result["teller"]["redo"] == 3
    statuses = {row[0]: row[4] for row in _rows(db)}
    assert {statuses[i] for i in ("c1s0", "c1s4", "c2s2")} == {"analyzed"}
    assert {statuses[i] for i in ("c1s1", "c1s2", "c1s3", "c2s0", "c2s1")} == {"verified"}, "câu không đổi giọng giữ bản thu"
    with db.connect() as conn:
        chapters = conn.execute("SELECT status, last_error FROM chapters").fetchall()
    assert {row[0] for row in chapters} == {"warning"} and all(str(row[1]).startswith(LISTENER_REDO) for row in chapters)

    teller_voice.set_mode(paths.root, "narrator")
    with db.connect() as conn:
        assert teller_voice.mode_plan(conn, paths.root, teller_voice.tellers_of(paths.root, settings, conn))["direction"] == "off"
    teller_voice.ensure(paths.root, db, settings)
    assert _speakers(db)["c1s0"] == "NARRATOR"


def test_a_section_told_by_someone_else_follows_that_person_or_keeps_the_narration_voice(tmp_path: Path) -> None:
    paths, db, settings = _book(tmp_path, settings=_settings(chapters={"2": "Bao"}))
    teller_voice.set_mode(paths.root, "teller")
    teller_voice.ensure(paths.root, db, settings)
    speakers = _speakers(db)
    assert speakers["c1s0"] == "MAI" and speakers["c2s2"] == "BAO", "chương do Bảo kể: câu kể theo Bảo"

    paths2, db2, settings2 = _book(tmp_path / "third", settings=_settings(chapters={"2": ""}))
    teller_voice.set_mode(paths2.root, "teller")
    teller_voice.ensure(paths2.root, db2, settings2)
    assert _speakers(db2)["c2s2"] == "NARRATOR" and _speakers(db2)["c1s0"] == "MAI", "chương ngôi ba giữ giọng dẫn"

    paths3, db3, settings3 = _book(tmp_path / "section")
    narrator_sections.decide(paths3.root, 1, 0, 0, accepted=True, narrator="", source="owner")  # đoạn ngôi ba trong chương của Mai
    narrator_sections.decide(paths3.root, 1, 4, 4, accepted=True, narrator="Bao", source="owner")
    teller_voice.set_mode(paths3.root, "teller")
    teller_voice.ensure(paths3.root, db3, settings3)
    speakers3 = _speakers(db3)
    assert speakers3["c1s0"] == "NARRATOR" and speakers3["c1s4"] == "BAO" and speakers3["c2s2"] == "MAI"


def test_a_teller_without_a_voice_of_their_own_is_left_alone(tmp_path: Path) -> None:
    paths, db, settings = _book(tmp_path, settings=_settings(identity="Lan"))
    teller_voice.set_mode(paths.root, "teller")

    teller_voice.ensure(paths.root, db, settings)

    assert _speakers(db)["c1s0"] == "NARRATOR" and _speakers(db)["c2s2"] == "NARRATOR"


def test_changing_the_tellers_voice_afterwards_changes_the_narration_too(tmp_path: Path) -> None:
    paths, db, settings = _book(tmp_path)
    teller_voice.set_mode(paths.root, "teller")
    teller_voice.ensure(paths.root, db, settings)
    with db.connect() as conn:
        taken = {row[0] for row in conn.execute("SELECT preset_name FROM voice_profiles")}
    other = next(p["name"] for p in casting_presets("female") if p["name"] not in taken)

    db.apply_listener_voice(character="Mai", voices=build_settings()["voices"], preset=other)

    assert _profile_of(db, "c1s0")[1] == _profile_of(db, "c1s1")[1] == _profile_of(db, "c2s2")[1]
    with db.connect() as conn:
        assert conn.execute("SELECT preset_name FROM voice_profiles WHERE id=?", (_profile_of(db, "c1s0")[1],)).fetchone()[0] == other


def test_a_crash_between_the_note_and_the_change_is_harmless_and_still_undoable(tmp_path: Path, monkeypatch) -> None:
    paths, db, settings = _book(tmp_path)
    teller_voice.set_mode(paths.root, "teller")
    before = _rows(db)

    def broken(*_args: Any, **_kwargs: Any):
        raise RuntimeError("chết giữa chừng")

    monkeypatch.setattr(teller_voice, "_move_lines", broken)
    with pytest.raises(RuntimeError):
        teller_voice.ensure(paths.root, db, settings)
    monkeypatch.undo()
    assert _rows(db) == before and teller_voice.read(paths.root)["applied"]["teller"]["groups"], "ý định đã ghi, sách chưa đổi"

    teller_voice.set_mode(paths.root, "narrator")
    teller_voice.ensure(paths.root, db, settings)
    assert "teller" not in teller_voice.read(paths.root)["applied"]
    kept = lambda rows: [row for row in rows if row[0] not in ("c1s2", "c2s0")]  # nội tâm của “tôi”: A+ chạy lại như thường
    assert kept(_rows(db)) == kept(before)


def test_a_third_person_book_ignores_the_switch(tmp_path: Path) -> None:
    paths, db, settings = _book(tmp_path, settings=_settings(identity=""))
    teller_voice.set_mode(paths.root, "teller")

    assert teller_voice.ensure(paths.root, db, settings) == {"skipped": "third_person"}
    assert _speakers(db)["c1s0"] == "NARRATOR"


def test_the_sidecar_keeps_the_studios_mode_when_the_worker_saves_its_part(tmp_path: Path) -> None:
    teller_voice.set_mode(tmp_path, "teller")
    teller_voice._save(tmp_path, applied={"thoughts": {"s": "MAI"}})

    record = teller_voice.read(tmp_path)

    assert record["mode"] == "teller" and record["applied"] == {"thoughts": {"s": "MAI"}}
    with pytest.raises(ValueError):
        teller_voice.set_mode(tmp_path, "robot")
