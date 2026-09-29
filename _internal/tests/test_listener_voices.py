"""Người nghe sửa giọng và giới của một nhân vật trong Studio, và mọi câu của người ấy được đọc lại bằng giọng mới.

Hộp "Việc cần bạn" ghi mong muốn vào `overrides.json` (mục `voices`); dây chuyền áp ở ranh giới an toàn bằng
`ProjectDB.apply_listener_voice`: giọng mới là hồ sơ bước phân vai sẽ tạo cho người ấy với mọi người khác giữ nguyên
giọng (`character_registry.book_allocator`), mọi câu sang cùng lúc - "một người một giọng" vẫn đúng - câu đã thu được đặt
lại, giới và giọng được ghim cho lô sau. Một transaction.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ebook_reader.character_registry import assert_voice_stability, voice_profile_spec
from ebook_reader.config import build_settings, settings_hash
from ebook_reader.database import ProjectDB
from ebook_reader.io_utils import sha256_file
from ebook_reader.listener_overrides import (
    BAD_GENDER,
    NOT_A_CHARACTER,
    UNKNOWN_CHARACTER,
    UNKNOWN_PRESET,
    read_overrides,
    request_voice,
    voice_requests,
)
from ebook_reader.models import ProjectPaths
from ebook_reader.voice_catalog import casting_presets, preset_by_name
from tests.test_listener_overrides import _Pipeline

SETTINGS = build_settings()
VOICES = SETTINGS["voices"]
NARRATOR_VOICE = str(VOICES["narrator_voice"])
MALE = [preset for preset in casting_presets("male") if preset["name"] != NARRATOR_VOICE]
FEMALE = [preset for preset in casting_presets("female") if preset["name"] != NARRATOR_VOICE]
# Ai, giới trong sổ, giọng đang mang (preset, bậc formant). RHINE dùng CHUNG đúng hồ sơ của LUCIEN, cùng chương.
CAST = {
    "LUCIEN": ("male", MALE[0], 1.0),
    "NATASHA": ("female", FEMALE[0], 1.0),
    "NOAH": ("unknown", MALE[1], 1.0),
    "RHINE": ("male", MALE[0], 1.0),
}
LINES = [
    ("c1s0", "narration", "NARRATOR", "Lucien nhìn Natasha."),
    ("c1s1", "dialogue", "LUCIEN", "“Đi thôi.”"),
    ("c1s2", "dialogue", "NOAH", "“Tớ đi với.”"),
    ("c1s3", "dialogue", "NATASHA", "“Chắc.”"),
    ("c1s4", "dialogue", "NOAH", "“Nhanh lên.”"),
    ("c1s5", "dialogue", "RHINE", "“Ừ.”"),
]


def _book(tmp_path: Path) -> tuple[ProjectPaths, ProjectDB]:
    """Một chương đã phân vai và thu xong."""
    paths = ProjectPaths.build(tmp_path / "project")
    db = ProjectDB(paths.db)
    db.initialize_book(title="T", project_root=paths.root, settings=SETTINGS, settings_hash=settings_hash(SETTINGS),
                       input_manifest_hash="manifest")
    source = tmp_path / "001.txt"
    source.write_text("\n".join(text for *_rest, text in LINES), encoding="utf-8")
    chapter_id = db.ensure_chapters([{
        "chapter_index": 1, "title": "001", "input_path": source, "input_sha256": sha256_file(source),
        "input_size": source.stat().st_size, "output_mp3": paths.chapters / "001.mp3",
    }])[0]
    db.replace_chapter_segments(chapter_id, [
        {"stable_id": stable_id, "seq": seq, "text": text, "text_sha256": f"sha-{stable_id}", "kind_hint": kind}
        for seq, (stable_id, kind, _speaker, text) in enumerate(LINES)
    ])
    narrator = db.upsert_voice_profile({"voice_key": "narrator", "engine": "vieneu", "preset_name": NARRATOR_VOICE,
                                        "description": "kể", "seed": 1, "status": "ready"})
    profiles = {"NARRATOR": narrator}
    for key, (_gender, preset, ratio) in CAST.items():
        profiles[key] = db.upsert_voice_profile(voice_profile_spec(preset, ratio))
    with db.connect() as conn:
        for key, gender in [("NARRATOR", "male"), *[(key, spec[0]) for key, spec in CAST.items()]]:
            conn.execute("INSERT INTO characters(canonical_name,display_name,gender,age,personality,importance,"
                         "mention_count,confidence,locked,created_at,updated_at) VALUES(?,?,?,'adult','','main',1,1,0,0,0)",
                         (key, key.title(), gender))
        for stable_id, kind, speaker, _text in LINES:
            conn.execute(
                "UPDATE segments SET kind=?, speaker=?, gender='unknown', status='verified', wav_path='take.wav',"
                " wav_sha256='sha', canonical_character_id=(SELECT id FROM characters WHERE canonical_name=?),"
                " voice_profile_id=? WHERE stable_id=?",
                (kind, speaker, speaker, profiles[speaker], stable_id))
    db.update_chapter_status(chapter_id, "completed")
    db.finalize_casting()
    return paths, db


def _voice(db: ProjectDB, speaker: str) -> set[str]:
    with db.connect() as conn:
        return {str(row[0]) for row in conn.execute(
            "SELECT v.voice_key FROM segments s JOIN voice_profiles v ON v.id=s.voice_profile_id WHERE s.speaker=?",
            (speaker,))}


def _character(db: ProjectDB, key: str) -> dict[str, Any]:
    with db.connect() as conn:
        return dict(conn.execute("SELECT * FROM characters WHERE canonical_name=?", (key,)).fetchone())


def _statuses(db: ProjectDB, speaker: str) -> set[str]:
    return {str(row["status"]) for row in db.list_segments() if str(row["speaker"]) == speaker}


def _apply(db: ProjectDB, character: str, **request: str):
    return db.apply_listener_voice(character=character, voices=VOICES, **request)


def test_a_listener_says_the_character_is_a_girl_and_every_line_moves_to_a_female_voice(tmp_path: Path) -> None:
    _paths, db = _book(tmp_path)
    before = _voice(db, "NOAH")

    result = _apply(db, "Noah", gender="female")

    assert result is not None and result["reset_segments"] == 2 and result["chapters"] == [1]
    (voice,) = _voice(db, "NOAH")
    assert voice != next(iter(before)) and voice == result["voice_key"]
    with db.connect() as conn:
        preset = conn.execute("SELECT preset_name FROM voice_profiles WHERE voice_key=?", (voice,)).fetchone()[0]
        assert conn.execute("SELECT status FROM chapters").fetchone()[0] == "warning"
        event = conn.execute("SELECT details_json FROM runtime_events WHERE code='VOICE_SET_BY_LISTENER'").fetchone()
    assert preset_by_name(preset)["gender"] == "female" and preset != NARRATOR_VOICE
    assert voice not in _voice(db, "NATASHA"), "Natasha cùng chương: không bao giờ nhận đúng giọng của cô"
    assert _statuses(db, "NOAH") == {"analyzed"}, "câu đã thu phải thu lại bằng giọng mới"
    assert _statuses(db, "LUCIEN") == {"verified"}, "người khác không đổi"
    noah = _character(db, "NOAH")
    assert (noah["gender"], noah["locked"], noah["locked_voice_key"]) == ("female", 1, voice), "ghim cho lô sau"
    assert json.loads(event[0])["gender"] == "female"
    assert_voice_stability(db)
    assert _apply(db, "NOAH", gender="female") is None, "áp lại yêu cầu đã áp: không đổi gì"


def test_confirming_the_gender_the_voice_already_has_only_pins_it(tmp_path: Path) -> None:
    """Noah đang đọc bằng giọng nam, người nghe nói "nam": ghim giới cho lô sau, không câu nào phải thu lại."""
    _paths, db = _book(tmp_path)
    before = _voice(db, "NOAH")

    result = _apply(db, "NOAH", gender="male")

    assert result is not None and result["reset_segments"] == 0 and result["chapters"] == []
    assert _voice(db, "NOAH") == before and _statuses(db, "NOAH") == {"verified"}
    noah = _character(db, "NOAH")
    assert (noah["gender"], noah["locked"], noah["locked_voice_key"]) == ("male", 1, "")
    assert _apply(db, "NOAH", gender="male") is None
    assert _apply(db, "NATASHA") is None, "không yêu cầu gì (\"giữ nguyên\"): không đổi gì"


def test_two_people_sharing_a_voice_in_one_chapter_are_pulled_apart(tmp_path: Path) -> None:
    _paths, db = _book(tmp_path)
    (shared,) = _voice(db, "RHINE")
    assert _voice(db, "LUCIEN") == {shared}

    result = _apply(db, "RHINE", avoid=shared)

    (voice,) = _voice(db, "RHINE")
    assert voice != shared and _voice(db, "LUCIEN") == {shared}
    assert result is not None and result["reset_segments"] == 1
    assert _statuses(db, "LUCIEN") == {"verified"}
    assert _apply(db, "RHINE", avoid=shared) is None, "đã khác giọng Lucien: không đổi nữa"


def test_a_picked_voice_takes_a_formant_step_nobody_in_the_chapter_holds(tmp_path: Path) -> None:
    """Người nghe chọn đúng preset Lucien đang dùng cho Noah (cùng chương): cùng preset, KHÁC bậc formant - như bước phân
    vai vẫn làm - chứ không thành hai người một giọng."""
    _paths, db = _book(tmp_path)
    lucien_preset = CAST["LUCIEN"][1]["name"]

    _apply(db, "NOAH", preset=lucien_preset)

    (voice,) = _voice(db, "NOAH")
    with db.connect() as conn:
        preset, ratio = conn.execute(
            "SELECT preset_name, formant_ratio FROM voice_profiles WHERE voice_key=?", (voice,)).fetchone()
    assert preset == lucien_preset and abs(float(ratio) - 1.0) > 1e-6
    assert voice not in _voice(db, "LUCIEN")
    assert _character(db, "NOAH")["gender"] == "male", "giới theo preset đã chọn"
    assert_voice_stability(db)


@pytest.mark.parametrize(("character", "request_", "problem"), [
    ("HEIDI", {}, UNKNOWN_CHARACTER),
    ("NARRATOR", {"gender": "female"}, NOT_A_CHARACTER),
    ("NOAH", {"preset": "Không có giọng này"}, UNKNOWN_PRESET),
    ("NOAH", {"preset": NARRATOR_VOICE}, UNKNOWN_PRESET),
    ("NOAH", {"gender": "robot"}, BAD_GENDER),
])
def test_a_request_that_cannot_apply_changes_nothing(tmp_path: Path, character, request_, problem) -> None:
    _paths, db = _book(tmp_path)

    assert _apply(db, character, **request_) == {"problem": problem}
    assert {str(row["status"]) for row in db.list_segments()} == {"verified"}


def test_a_crash_inside_the_apply_leaves_the_character_as_it_was(tmp_path: Path, monkeypatch) -> None:
    paths, db = _book(tmp_path)
    before = _voice(db, "NOAH")

    def crash(self, conn, chapter_id):
        raise RuntimeError("máy tắt giữa transaction")

    monkeypatch.setattr(ProjectDB, "_refresh_chapter_counts_conn", crash)
    with pytest.raises(RuntimeError):
        _apply(db, "NOAH", gender="female")
    monkeypatch.undo()

    reopened = ProjectDB(paths.db)
    assert _voice(reopened, "NOAH") == before and _statuses(reopened, "NOAH") == {"verified"}
    noah = _character(reopened, "NOAH")
    assert (noah["gender"], noah["locked"], noah["locked_voice_key"]) == ("unknown", 0, "")


def test_the_pipeline_applies_a_voice_request_at_a_boundary(tmp_path: Path) -> None:
    paths, db = _book(tmp_path)
    request_voice(paths.root, "Noah", gender="female", now=1.0)
    request_voice(paths.root, "Heidi", gender="female", now=1.0)  # không có trong sách: báo một lần, không áp
    assert [entry["character"] for entry in voice_requests(read_overrides(paths.root))] == ["HEIDI", "NOAH"]
    pipeline = _Pipeline(paths, db)
    pipeline.settings = SETTINGS

    assert pipeline._apply_listener_overrides() == {1}
    assert pipeline._apply_listener_overrides() == set()
    assert _statuses(db, "NOAH") == {"analyzed"}
    with db.connect() as conn:
        rejected = conn.execute("SELECT COUNT(*) FROM runtime_events WHERE code='LISTENER_OVERRIDE_REJECTED'").fetchone()
    assert rejected[0] == 1
    assert_voice_stability(db)


def test_the_inbox_offers_one_click_gender_and_voice_fixes_and_the_studio_records_them(tmp_path: Path) -> None:
    """Thẻ "Nam hay nữ" nói máy đang đọc bằng giọng gì và cái giá của từng lựa chọn; thẻ "Chung giọng" tách đúng giọng
    đang dùng chung. Studio ghi yêu cầu qua POST /voice (từ chối tại chỗ những gì dây chuyền sẽ từ chối), không bao giờ
    ghi SQLite; dây chuyền áp ở ranh giới và thẻ tự biến mất."""
    from ebook_reader.webui.library import Preferences, book_id
    from ebook_reader.webui.listening import Listening
    from ebook_reader.webui.server import App, Server
    from ebook_reader.webui.work_items import work_items
    from tests.test_webui_listen_and_sync import FakeRunner, _request

    from ebook_reader.config import save_settings

    paths, db = _book(tmp_path)
    save_settings(paths.settings, SETTINGS)  # thư viện nhận ra sách nhờ file này
    cards = {item["kind"]: item for item in work_items(paths.root)["items"]}
    gender = cards["gender"]
    assert gender["title"] == "Noah là nam hay nữ?" and gender["problem"].endswith("giọng nam.")
    assert [(choice["label"], choice["note"]) for choice in gender["voiceChoices"]] == [
        ("Nam", "giữ giọng đang đọc"), ("Nữ", "đổi giọng, thu lại 2 câu")]
    shared = cards["shared-voice"]
    (lucien_voice,) = _voice(db, "LUCIEN")
    assert {choice["character"] for choice in shared["voiceChoices"]} == {"LUCIEN", "RHINE"}
    assert {choice["avoid"] for choice in shared["voiceChoices"]} == {lucien_voice}

    preferences = Preferences(tmp_path / "prefs" / "preferences.json")
    preferences.update({"libraryRoot": str(tmp_path)})
    app = App(preferences=preferences, runner=FakeRunner(), token="t", listening=Listening(tmp_path / "prefs" / "l.json"))
    server = Server(app, port=0).start()
    headers = {"X-Ebook-Token": "t"}
    path = f"/api/books/{book_id(paths.root)}/voice"
    before = paths.db.read_bytes()
    try:
        status, data, _ = _request(server.port, "POST", path, headers=headers, body={"character": "NOAH", "gender": "female"})
        assert status == 200
        status, data, _ = _request(server.port, "POST", path, headers=headers, body={"character": "NOAH", "gender": "robot"})
        assert status == 400 and "nam hoặc nữ" in json.loads(data)["error"]
        status, data, _ = _request(server.port, "POST", path, headers=headers, body={"character": "HEIDI"})
        assert status == 400 and "Không có nhân vật" in json.loads(data)["error"]
        status, _, _ = _request(server.port, "POST", path, headers=headers,
                                body={"character": "RHINE", "avoid": lucien_voice})
        assert status == 200
    finally:
        server.stop()
    assert paths.db.read_bytes() == before, "chỉ dây chuyền được ghi SQLite của sách"
    cards = {item["kind"]: item for item in work_items(paths.root)["items"]}
    assert cards["gender"]["requested"] == "Nữ" and cards["shared-voice"]["requested"] == "đổi giọng Rhine"

    pipeline = _Pipeline(paths, db)
    pipeline.settings = SETTINGS
    assert pipeline._apply_listener_overrides() == {1}
    kinds = {item["kind"] for item in work_items(paths.root)["items"]}
    assert "gender" not in kinds and "shared-voice" not in kinds, "đã áp: giới đã ghim, hai người đã khác giọng"
    assert_voice_stability(db)


def test_the_voice_picker_lists_every_castable_voice_with_what_the_listener_needs_to_choose(tmp_path: Path) -> None:
    """Màn "Đổi giọng": mọi giọng dùng được (không giọng người kể), giọng đang dùng, giọng máy gợi ý cho mỗi giới, và ai
    đang dùng giọng ấy cùng mấy chương - để người nghe không vô tình chọn đúng giọng người cùng cảnh."""
    from ebook_reader.config import save_settings
    from ebook_reader.webui.library import Preferences, book_id
    from ebook_reader.webui.listening import Listening
    from ebook_reader.webui.remote_studio import permitted
    from ebook_reader.webui.server import App, Server
    from ebook_reader.webui.voice_picker import voice_choices
    from tests.test_webui_listen_and_sync import FakeRunner, _request

    paths, _db = _book(tmp_path)
    save_settings(paths.settings, SETTINGS)
    view = voice_choices(paths.root, "Rhine")
    assert view is not None and view["character"] == {"value": "RHINE", "label": "Rhine", "gender": "male",
                                                      "lines": 1, "chapters": 1}
    names = {voice["name"] for voice in view["voices"]}
    assert NARRATOR_VOICE not in names and {MALE[0]["name"], FEMALE[0]["name"]} <= names
    current = [voice for voice in view["voices"] if voice["current"]]
    assert [voice["name"] for voice in current] == [MALE[0]["name"]]
    assert current[0]["sharedWith"] == [{"label": "Lucien", "chapters": 1}], "Lucien cùng giọng, cùng chương"
    assert current[0]["otherUsers"] == 0
    assert {voice["gender"] for voice in view["voices"] if voice["suggested"]} == {"male", "female"}
    assert voice_choices(paths.root, "Heidi") is None and voice_choices(paths.root, "NARRATOR") is None

    preferences = Preferences(tmp_path / "prefs" / "preferences.json")
    preferences.update({"libraryRoot": str(tmp_path)})
    app = App(preferences=preferences, runner=FakeRunner(), token="t", listening=Listening(tmp_path / "prefs" / "l.json"))
    server = Server(app, port=0).start()
    base = f"/api/books/{book_id(paths.root)}/voices"
    try:
        status, data, _ = _request(server.port, "GET", base + "?character=NOAH", headers={"X-Ebook-Token": "t"})
        assert status == 200 and json.loads(data)["character"]["value"] == "NOAH"
        status, _, _ = _request(server.port, "GET", base + "?character=HEIDI", headers={"X-Ebook-Token": "t"})
        assert status == 404
    finally:
        server.stop()
    assert permitted("GET", base)
