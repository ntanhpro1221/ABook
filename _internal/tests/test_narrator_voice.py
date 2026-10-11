"""Đổi giọng NGƯỜI KỂ không phải tạo lại sách (soát UX a23, B21): như đổi giọng một nhân vật.

Studio ghi mong muốn vào `overrides.json` (mục `voices`, khoá NARRATOR); dây chuyền áp ở ranh giới bằng
`ProjectDB.apply_listener_voice`: hồ sơ giọng người kể (`voice_key` "narrator" - mọi chỗ tra giọng người kể, kể cả nội tâm
không rõ ai nghĩ, đều tra khoá ấy) đổi preset, câu đọc bằng giọng người kể ĐÃ THU được đặt lại để thu bằng giọng mới, câu
chưa thu thì thu bằng giọng mới. Giọng người kể không bao giờ trùng giọng một nhân vật: chọn giọng nhân vật đang dùng bị từ
chối, và nhân vật đổi giọng sau đó không bao giờ nhận giọng người kể mới.
"""

from __future__ import annotations

from pathlib import Path

from abook.listener_overrides import (
    NARRATOR_VOICE_ONLY,
    UNKNOWN_PRESET,
    VOICE_TAKEN,
    request_voice,
    voice_target,
)
from abook.voice_catalog import narrator_presets
from tests.test_listener_overrides import _Pipeline
from tests.test_listener_voices import CAST, NARRATOR_VOICE, SETTINGS, VOICES, _apply, _book, _statuses

HELD = {str(preset["name"]) for _gender, preset, _ratio in CAST.values()}
FREE = [str(preset["name"]) for preset in narrator_presets() if preset["name"] not in HELD | {NARRATOR_VOICE}]


def _narrator_preset(db) -> str:
    return str(db.voice_profile_by_key("narrator")["preset_name"])


def _with_unattributed_thought(db) -> None:
    """Một câu nội tâm không rõ ai nghĩ: đọc bằng giọng người kể (database.thought_reads_as_narrator)."""
    with db.connect() as conn:
        conn.execute("UPDATE segments SET kind='thought', speaker='UNKNOWN' WHERE stable_id='c1s2'")


def test_a_listener_changes_the_narrator_voice_and_only_narrated_recorded_lines_are_redone(tmp_path: Path) -> None:
    _paths, db = _book(tmp_path)
    _with_unattributed_thought(db)
    picked = FREE[0]

    result = _apply(db, "NARRATOR", preset=picked)

    assert result is not None and result["reset_segments"] == 2 and result["chapters"] == [1]
    assert (result["voice_key"], result["previous_voice_key"]) == (picked, NARRATOR_VOICE)
    assert _narrator_preset(db) == picked, "mọi chỗ tra hồ sơ 'narrator' (kể cả nội tâm không rõ ai nghĩ) đọc giọng mới"
    statuses = {str(row["stable_id"]): str(row["status"]) for row in db.list_segments()}
    assert statuses["c1s0"] == "analyzed" and statuses["c1s2"] == "analyzed"
    assert {statuses[key] for key in ("c1s1", "c1s3", "c1s4", "c1s5")} == {"verified"}, "lời nhân vật không đổi"
    with db.connect() as conn:
        assert conn.execute("SELECT status FROM chapters").fetchone()[0] == "warning"
        assert conn.execute("SELECT COUNT(*) FROM voice_profiles WHERE voice_key LIKE 'narrator%'").fetchone()[0] == 1
    assert _apply(db, "NARRATOR", preset=picked) is None, "áp lại yêu cầu đã áp: không đổi gì"
    assert _apply(db, "NARRATOR", preset=NARRATOR_VOICE)["reset_segments"] == 0, "câu vừa đặt lại chưa thu: không tốn gì"
    assert _narrator_preset(db) == NARRATOR_VOICE


def test_the_narrator_cannot_take_a_voice_a_character_speaks_in(tmp_path: Path) -> None:
    _paths, db = _book(tmp_path)
    lucien = str(CAST["LUCIEN"][1]["name"])

    assert _apply(db, "NARRATOR", preset=lucien) == {"problem": VOICE_TAKEN}
    assert _apply(db, "NARRATOR", preset="Không có giọng này") == {"problem": UNKNOWN_PRESET}
    assert _apply(db, "NARRATOR", gender="female") == {"problem": NARRATOR_VOICE_ONLY}, "người kể không có giới để đổi"
    assert _narrator_preset(db) == NARRATOR_VOICE
    assert {str(row["status"]) for row in db.list_segments()} == {"verified"}


def test_after_the_change_no_character_can_be_given_the_new_narrator_voice(tmp_path: Path) -> None:
    from abook.voice_catalog import preset_by_name

    _paths, db = _book(tmp_path)
    picked = next(name for name in FREE if preset_by_name(name)["gender"] == "male")
    _apply(db, "NARRATOR", preset=picked)

    with db.connect() as conn:
        target, problem = voice_target(conn, VOICES, character="NOAH", preset=picked)
    assert target is None and problem == UNKNOWN_PRESET
    assert _apply(db, "NOAH", preset=picked) == {"problem": UNKNOWN_PRESET}
    result = _apply(db, "NATASHA", gender="male")
    assert result is not None
    with db.connect() as conn:
        natasha = conn.execute("SELECT preset_name FROM voice_profiles WHERE voice_key=?", (result["voice_key"],)).fetchone()
    assert natasha[0] not in (picked, NARRATOR_VOICE), "máy chọn giọng cho nhân vật tránh cả giọng người kể mới"


def test_the_pipeline_applies_a_narrator_voice_request_at_a_boundary(tmp_path: Path) -> None:
    paths, db = _book(tmp_path)
    request_voice(paths.root, "NARRATOR", preset=FREE[0], now=1.0)
    pipeline = _Pipeline(paths, db)
    pipeline.settings = SETTINGS

    assert pipeline._apply_listener_overrides() == {1}
    assert pipeline._apply_listener_overrides() == set()
    assert _narrator_preset(db) == FREE[0] and _statuses(db, "NARRATOR") == {"analyzed"}


def test_studio_lists_narrator_voices_counts_the_redo_and_shows_the_wait(tmp_path: Path) -> None:
    """Hộp "Đổi giọng" của hàng "Người kể": giọng kể chuyện dùng được, giọng nhân vật đang giữ thì không chọn được (nói của
    ai), hộp "Áp dụng" và dòng người kể nói đúng số câu đã thu sẽ thu lại."""
    from abook.config import save_settings
    from abook.webui import store
    from abook.webui.voice_picker import voice_choices

    paths, db = _book(tmp_path)
    _with_unattributed_thought(db)
    save_settings(paths.settings, SETTINGS)
    view = voice_choices(paths.root, "NARRATOR")
    assert view is not None and view["character"]["value"] == "NARRATOR" and view["rerecord"]["lines"] == 2
    by_name = {voice["name"]: voice for voice in view["voices"]}
    assert by_name[NARRATOR_VOICE]["current"] and not by_name[NARRATOR_VOICE]["takenBy"]
    lucien = str(CAST["LUCIEN"][1]["name"])
    assert by_name[lucien]["takenBy"] == ["Lucien", "Rhine"], "giọng nhân vật đang dùng: nói của ai"
    assert not by_name[FREE[0]]["takenBy"]

    request_voice(paths.root, "NARRATOR", preset=FREE[0], now=10.0**10)
    details = store.pending_details(paths.root, 0.0)
    (item,) = [entry for entry in details["items"] if entry["kind"] == "voice"]
    assert item["lines"] == 2 and item["label"] == f"Giọng của người kể: {FREE[0]}"
    cast = store.cast(paths.root)
    assert cast["narrator"]["voice"] == NARRATOR_VOICE and cast["narrator"]["pendingVoice"]["preset"] == FREE[0]
    assert voice_choices(paths.root, "NARRATOR")["pending"]["name"] == FREE[0]
    # Đầu trang dự án: giọng SẼ dùng (chờ áp dụng), không phải giọng cũ như chưa có gì (soát UX a24, lặt vặt).
    settings = store.summarize(paths.root)["settings"]
    assert settings["narrator"] == NARRATOR_VOICE and settings["narratorPending"] == FREE[0]

    _apply(db, "NARRATOR", preset=FREE[0])
    assert store.cast(paths.root)["narrator"]["voice"] == FREE[0], "dòng người kể nói giọng đang đọc, không phải giọng lúc tạo"
    assert store.narrator_voice(paths.root) == FREE[0]


def test_a_voice_waiting_for_the_narrator_is_not_offered_to_a_character_and_the_other_way(tmp_path: Path) -> None:
    """Soát UX a24, A2: ý muốn CHƯA ÁP cũng giữ giọng - người kể chờ giọng X thì nhân vật không chọn được X (và hộp nói vì
    sao), nhân vật chờ giọng Y thì người kể không chọn được Y."""
    from abook.config import save_settings
    from abook.webui import store
    from abook.webui.voice_picker import voice_choices

    paths, _db = _book(tmp_path)
    save_settings(paths.settings, SETTINGS)
    waiting, wanted = FREE[0], FREE[1]
    request_voice(paths.root, "NARRATOR", preset=waiting, now=10.0**10)

    assert store.voice_request_problem(paths.root, "NOAH", preset=waiting) == store.NARRATOR_WISHED
    assert store.voice_request_problem(paths.root, "NOAH", preset=wanted) is None
    entry = next(voice for voice in voice_choices(paths.root, "NOAH")["voices"] if voice["name"] == waiting)
    assert entry["takenBy"] == ["Người kể"] and "người kể" in entry["takenNote"]

    request_voice(paths.root, "NOAH", preset=wanted, now=10.0**10)
    assert store.voice_request_problem(paths.root, "NARRATOR", preset=wanted) == VOICE_TAKEN
    by_name = {voice["name"]: voice for voice in voice_choices(paths.root, "NARRATOR")["voices"]}
    assert by_name[wanted]["takenBy"] == ["Noah (chờ áp dụng)"]
    assert store.voice_request_problem(paths.root, "NARRATOR", preset=waiting) is None, "chính ý muốn của người kể"


def test_the_narrator_gets_the_voice_first_and_the_blocked_wish_becomes_a_card(tmp_path: Path) -> None:
    """Người kể và LUCIEN (xếp trước NARRATOR theo tên) cùng chờ một giọng (ghi từ trước khi có kiểm tra): người kể áp
    trước nên giữ giọng; ý muốn của Lucien bị từ chối và thành một thẻ "Việc cần duyệt" - không mất lặng lẽ."""
    from abook.config import save_settings
    from abook.webui.work_items import work_items

    paths, db = _book(tmp_path)
    save_settings(paths.settings, SETTINGS)
    picked = FREE[0]
    request_voice(paths.root, "LUCIEN", preset=picked, now=1.0)
    request_voice(paths.root, "NARRATOR", preset=picked, now=2.0)
    pipeline = _Pipeline(paths, db)
    pipeline.settings = SETTINGS

    pipeline._apply_listener_overrides()

    assert _narrator_preset(db) == picked
    cards = [item for item in work_items(paths.root)["items"] if item["kind"] == "voice-wish"]
    assert [card["key"] for card in cards] == ["voice-wish:LUCIEN"]
    assert picked in cards[0]["title"] and cards[0]["keepCharacters"] == ["LUCIEN"]

    request_voice(paths.root, "LUCIEN", now=3.0)  # "Giữ giọng đang dùng"
    assert not [item for item in work_items(paths.root)["items"] if item["kind"] == "voice-wish"]


def test_a_narrator_wish_a_character_took_meanwhile_becomes_a_card(tmp_path: Path) -> None:
    from abook.config import save_settings
    from abook.webui.work_items import work_items

    paths, _db = _book(tmp_path)
    save_settings(paths.settings, SETTINGS)
    lucien = str(CAST["LUCIEN"][1]["name"])
    request_voice(paths.root, "NARRATOR", preset=lucien, now=1.0)  # bước phân vai đã cấp giọng ấy cho Lucien

    (card,) = [item for item in work_items(paths.root)["items"] if item["kind"] == "voice-wish"]
    assert card["key"] == "voice-wish:NARRATOR" and "Lucien" in card["problem"] and card["affected"] == 1


def test_a_chapter_waiting_to_redo_a_listener_change_is_not_an_error_and_still_plays(tmp_path: Path) -> None:
    """Soát UX a24, A3: sau "Áp dụng" (đổi giọng người kể), chương đã xong chờ thu lại các câu ấy - không phải "Có lỗi khi làm sách"
    với chữ thô "Người nghe đổi giọng NARRATOR…", và MP3 cũ vẫn nghe được, đầu trang vẫn đếm là chương nghe được."""
    from abook.webui import store

    paths, db = _book(tmp_path)
    mp3 = paths.root / "output" / "chapters" / "001.mp3"
    mp3.parent.mkdir(parents=True, exist_ok=True)
    mp3.write_bytes(b"ID3")
    assert store.chapters(paths.root)[0]["playable"]

    _apply(db, "NARRATOR", preset=FREE[0])

    (chapter,) = store.chapters(paths.root)
    assert chapter["status"] == "warning" and chapter["redo"] and chapter["lastError"] == ""
    assert chapter["statusLabel"] == "Chờ thu lại theo sửa của bạn" and chapter["playable"]
    summary = store.summarize(paths.root)
    assert summary["chapters"]["completed"] == 1 and summary["chapters"]["redo"] == 1
    # Hàng "Người kể chuyện" của tab Nhân vật nói các câu kể đang chờ thu lại bằng giọng mới (soát UX a24, lặt vặt).
    assert store.cast(paths.root)["narrator"]["redo"] > 0
    assert store.chapter_audio_path(paths.root, chapter["id"]) == mp3.resolve()

    db.update_chapter_status(chapter["id"], "synthesizing")  # dây chuyền bắt đầu làm lại: hết "chờ thu lại"
    (chapter,) = store.chapters(paths.root)
    assert not chapter["redo"] and not chapter["playable"]


def test_the_narrator_box_names_people_as_the_cast_tab_does_and_once(tmp_path: Path) -> None:
    """Soát UX a24 (lặt vặt): hộp "Đổi giọng" của người kể ghi khoá chuẩn viết hoa từng chữ ("Lính Gác 1") và ghi lặp khi hai
    người cùng một tên hiện. Ghi như hàng ở tab Nhân vật (tên sổ viết), mỗi tên một lần."""
    import sqlite3

    from abook.webui.voice_picker import voice_choices

    paths, db = _book(tmp_path)
    with sqlite3.connect(db.path) as connection:
        connection.execute("UPDATE characters SET display_name='Lính gác 1' WHERE canonical_name IN ('LUCIEN', 'RHINE')")
    view = voice_choices(paths.root, "NARRATOR")
    assert view is not None
    lucien = str(CAST["LUCIEN"][1]["name"])
    (voice,) = [entry for entry in view["voices"] if entry["name"] == lucien]
    assert voice["takenBy"] == ["Lính gác 1"]
