"""Nhãn người nói về dạng tên CÓ THẬT trong chương (name_snap.py): model viết một người bằng hai dạng tên ("Toko" cho Tooko)
thì hai giọng; luật chặt đo 11-10 trên 9 model, 0 câu xấu đi / ~11.000 câu."""
from __future__ import annotations

import json
from pathlib import Path

from abook.character_registry import build_registry_and_cast
from abook.config import build_settings
from abook.database import ProjectDB
from abook.name_snap import name_key, snap_map


def test_a_label_the_chapter_never_writes_takes_the_spelling_it_does() -> None:
    lines = [("Toko", '"Chào em."'), ("NARRATOR", "Tooko mỉm cười."), ("NARRATOR", "Tooko quay đi.")]

    assert snap_map(lines) == {"Toko": "Tooko"}


def test_the_first_person_narrator_is_a_known_name_though_the_text_never_names_him() -> None:
    lines = [("Gu Yangchen", '"Đi thôi."'), ("NARRATOR", "Tôi bước vào sân."), ("NARRATOR", "Tôi nhìn quanh.")]

    assert snap_map(lines, {"GU YANGCHEON"}) == {"Gu Yangchen": "GU YANGCHEON"}


def test_a_split_given_name_joins_the_written_one() -> None:
    lines = [("Kim Jae Hun", '"Được."'), ("NARRATOR", "Kim Jaehun gật đầu. Kim Jaehun đứng dậy.")]

    assert snap_map(lines) == {"Kim Jae Hun": "Kim Jaehun"}


def test_two_close_names_in_the_chapter_leave_the_label_alone() -> None:
    lines = [("Mina", '"Ừ."'), ("NARRATOR", "Mira cười. Mira nói. Mia nhìn. Mia gật đầu.")]

    assert snap_map(lines) == {}


def test_a_label_the_chapter_writes_stays() -> None:
    lines = [("Toko", '"Chào."'), ("NARRATOR", "Toko và Tooko. Tooko cười.")]

    assert snap_map(lines) == {}


def test_narrator_and_npc_labels_are_not_names() -> None:
    lines = [("NARRATOR", "Narator mở cửa. Narator đóng cửa."), ("NPC", "Npa đến. Npa đi."),
             ("NPC_LOCAL::abc::Lính", "Lính gác.")]

    assert snap_map(lines) == {}


def test_a_short_name_two_edits_away_stays() -> None:
    """Khoá dưới 9 ký tự chỉ cho lệch một: "Haru" và "Hiro" là hai người."""
    lines = [("Haru", '"Ừ."'), ("NARRATOR", "Hiro cười. Hiro nói.")]

    assert snap_map(lines) == {}


def test_a_long_name_two_edits_away_joins() -> None:
    lines = [("Alexandrina", '"Ừ."'), ("NARRATOR", "Aleksandrina cười. Aleksandrina nói.")]

    assert snap_map(lines) == {"Alexandrina": "Aleksandrina"}


def test_the_key_folds_marks_case_spaces_and_long_vowels() -> None:
    assert name_key("Kim Jae-Hun") == name_key("KIM JAEHUN")
    assert name_key("Tooko") == name_key("toko")
    assert name_key("Gu Yangcheon") == name_key("GU YANGCHEN")
    assert name_key("Đường") == "duong"


def test_the_same_chapter_gives_the_same_answer_in_any_order() -> None:
    lines = [("Toko", '"A."'), ("Kim Jae Hun", '"B."'), ("NARRATOR", "Tooko và Kim Jaehun. Tooko, Kim Jaehun.")]

    assert snap_map(lines) == snap_map(list(reversed(lines))) == {"Toko": "Tooko", "Kim Jae Hun": "Kim Jaehun"}


def _chapter_db(tmp_path: Path, chapters: list[list[tuple[str, str]]], file_name: str = "snap.sqlite3") -> ProjectDB:
    db = ProjectDB(tmp_path / file_name)
    db.initialize_book(title="Book", project_root=tmp_path, settings={}, settings_hash="settings",
                       input_manifest_hash="manifest")
    ids = db.ensure_chapters([
        {"chapter_index": index, "title": f"C{index}", "input_path": tmp_path / f"{index}.txt",
         "input_sha256": f"source-{index}", "input_size": 1, "output_mp3": tmp_path / f"{index}.mp3"}
        for index in range(1, len(chapters) + 1)
    ])
    for chapter_id, (index, lines) in zip(ids, enumerate(chapters, 1)):
        db.replace_chapter_segments(chapter_id, [
            {"stable_id": f"c{index}s{seq}", "seq": seq, "text": text, "text_sha256": f"t-{index}-{seq}",
             "kind_hint": "narration" if speaker == "NARRATOR" else "dialogue",
             "kind": "narration" if speaker == "NARRATOR" else "dialogue",
             "speaker": speaker, "gender": "unknown" if speaker == "NARRATOR" else "female", "confidence": 0.95,
             "status": "analyzed"}
            for seq, (speaker, text) in enumerate(lines, 1)
        ])
    return db


def test_the_registry_never_sees_the_misspelt_name(tmp_path: Path) -> None:
    """Đổi ở ranh giới đầu ra model -> sổ nhân vật: không có nhân vật ma "Toko", một người một giọng, và việc đổi có trong
    sự kiện phân tích để soát."""
    db = _chapter_db(tmp_path, [
        [("NARRATOR", "Tooko bước vào lớp."), ("Toko", '"Chào cả lớp."'), ("NARRATOR", "Tooko ngồi xuống."),
         ("Tooko", '"Hôm nay học gì?"'), ("Toko", '"Thôi được."')],
        [("NARRATOR", "Toko chạy tới."), ("Toko", '"Đợi đã!"')],
    ])
    said: list[str] = []

    build_registry_and_cast(db, build_settings(), said.append)

    rows = db.list_segments()
    chapter_one = [row for row in rows if str(row["stable_id"]).startswith("c1")]
    assert {str(row["speaker"]) for row in chapter_one} - {"NARRATOR"} == {"Tooko"}
    tooko = [row for row in chapter_one if str(row["speaker"]) == "Tooko"]
    assert len({int(row["voice_profile_id"]) for row in tooko}) == 1
    # Chương 2 viết "Toko": luật theo TỪNG chương, nhãn có trong chữ chương thì giữ.
    assert "Toko" in {str(row["speaker"]) for row in rows if str(row["stable_id"]).startswith("c2")}
    events = [row for row in db.list_events() if str(row["code"]) == "SPEAKER_LABEL_SNAPPED_TO_TEXT"]
    assert [json.loads(str(row["details_json"])) for row in events] == [
        {"chapter_index": 1, "label": "Toko", "name": "Tooko", "lines": 2, "stable_ids": ["c1s2", "c1s5"]}
    ]
    assert any("Toko" in line and "Tooko" in line for line in said)


def test_a_listener_alias_keeps_its_label(tmp_path: Path) -> None:
    """Người nghe đã nói "Toko là Mai" (aliases.json): quyết định của người nghe thắng, luật không đụng nhãn ấy."""
    (tmp_path / "aliases.json").write_bytes(
        json.dumps({"version": 1, "aliases": [{"alias": "Toko", "person": "Mai", "at": 1.0}]}).encode("utf-8")
    )
    db = _chapter_db(tmp_path, [
        [("NARRATOR", "Tooko bước vào lớp."), ("Toko", '"Chào cả lớp."'), ("NARRATOR", "Tooko ngồi xuống."),
         ("Mai", '"Chào."')],
    ])

    build_registry_and_cast(db, build_settings(), lambda _message: None)

    assert not [row for row in db.list_events() if str(row["code"]) == "SPEAKER_LABEL_SNAPPED_TO_TEXT"]
    assert {str(row["speaker"]) for row in db.list_segments()} == {"NARRATOR", "Mai"}


def _snapped_book(tmp_path: Path, misspelt: int) -> ProjectDB:
    """Sổ dự án thật (project.sqlite3 - Studio đọc nó) có `misspelt` câu model ghi "Toko" ở chương chỉ viết "Tooko"."""
    lines = [("NARRATOR", "Tooko bước vào lớp."), ("Tooko", '"Hôm nay học gì?"')]
    lines += [("Toko", f'"Câu {number}."') for number in range(misspelt)]
    db = _chapter_db(tmp_path, [lines], "project.sqlite3")
    build_registry_and_cast(db, build_settings(), lambda _message: None)
    return db


def test_the_snap_reads_as_a_line_in_the_story_log(tmp_path: Path) -> None:
    """Soát UX a24 (SNAP): việc đổi nhãn chỉ hiện mã thô ở "Chi tiết kỹ thuật" - "Diễn biến" phải nói bằng lời."""
    from abook.webui import store

    _snapped_book(tmp_path, 6)

    texts = [item["text"] for item in store.activity(tmp_path) if item["kind"] == "event"]
    assert any("máy viết “Toko”, sách chỉ viết “Tooko” - 6 câu về Tooko" in text for text in texts)


def test_a_big_snap_asks_once_whether_it_is_one_person(tmp_path: Path) -> None:
    """Thẻ nhẹ "Việc cần duyệt": đúng (đóng thẻ) hay là người khác (các câu ấy về nhãn cũ, thành người riêng)."""
    from abook.listener_overrides import read_overrides, request_speakers, speaker_requests
    from abook.webui.work_items import open_count, work_items

    _snapped_book(tmp_path, 6)
    view = work_items(tmp_path)
    cards = [item for item in view["items"] if item["kind"] == "snap"]
    assert len(cards) == 1
    card = cards[0]
    assert card["currentValue"] == "Tooko" and card["newPerson"] == "Toko"
    assert card["keepLabel"] == "Đúng, cùng một người" and card["newPersonLabel"] == "Không, là người khác"
    # Chỉ những câu máy đã đổi - câu sách vẫn ghi Tooko (c1s2) không thuộc thẻ.
    assert sorted(line["stableId"] for line in card["lines"]) == [f"c1s{seq}" for seq in range(3, 9)]
    assert card["affected"] == 6
    assert open_count(view) >= 1
    lines = [(line["stableId"], line["textSha256"]) for line in card["lines"]]

    # "Không, là người khác": các câu về "Toko" như người mới - đúng cơ chế "Người khác…" của thẻ ai nói câu này.
    request_speakers(tmp_path, lines, "Toko", now=1.0, new_gender="unknown")
    assert {entry["speaker"] for entry in speaker_requests(read_overrides(tmp_path))} == {"Toko"}
    again = [item for item in work_items(tmp_path)["items"] if item["kind"] == "snap"]
    assert again and again[0]["requested"] == "Toko"

    # "Đúng, cùng một người": giữ Tooko - thẻ đóng.
    request_speakers(tmp_path, lines, "Tooko", now=2.0)
    assert not [item for item in work_items(tmp_path)["items"] if item["kind"] == "snap"]


def test_a_small_snap_does_not_ask(tmp_path: Path) -> None:
    """Dưới SNAP_MIN_LINES câu: chỉ một dòng ở "Diễn biến", không thẻ."""
    from abook.webui.work_items import SNAP_MIN_LINES, work_items

    _snapped_book(tmp_path, SNAP_MIN_LINES - 1)

    assert not [item for item in work_items(tmp_path)["items"] if item["kind"] == "snap"]
