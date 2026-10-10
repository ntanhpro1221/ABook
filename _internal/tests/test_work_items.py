"""Hộp "Việc cần duyệt" (webui/work_items.py, docs/STUDIO_REVIEW.md): chỗ máy nghi ngờ, xếp theo lợi trên mỗi lần bấm.

Project SQLite tối thiểu trong thư mục tạm - chỉ các bảng/cột mà bộ dựng việc đọc.
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from abook.webui.work_items import work_items


def make_book(root: Path) -> Path:
    project = root / "sach"
    project.mkdir()
    (project / "book_settings.json").write_text("{}", encoding="utf-8")
    db = sqlite3.connect(project / "project.sqlite3")
    db.executescript(
        """
        CREATE TABLE chapters (id INTEGER PRIMARY KEY, chapter_index INTEGER, title TEXT);
        CREATE TABLE segments (id INTEGER PRIMARY KEY, stable_id TEXT, chapter_id INTEGER, seq INTEGER, text TEXT,
                               kind TEXT, speaker TEXT, voice_profile_id INTEGER, canonical_character_id INTEGER,
                               status TEXT, asr_text TEXT, asr_similarity REAL, warning_code TEXT, wav_path TEXT,
                               text_sha256 TEXT, gender TEXT);
        CREATE TABLE characters (id INTEGER PRIMARY KEY, canonical_name TEXT, display_name TEXT, gender TEXT,
                                 locked INTEGER, age TEXT);
        CREATE TABLE pronunciations (surface TEXT, spoken_form TEXT, confidence REAL, locked INTEGER);
        """
    )
    db.execute("INSERT INTO chapters VALUES (1, 1, '001')")
    db.executemany("INSERT INTO characters (id, canonical_name, display_name, gender, locked) VALUES (?,?,?,?,?)", [
        (1, "LUCIEN", "Lucien", "male", 0),
        (2, "HEIDI", "Heidi", "female", 0),
        (3, "ÁO CHOÀNG ĐEN", "Áo choàng đen", "unknown", 0),
        (4, "RHINE", "Rhine", "male", 0),
    ])
    rows = [
        (1, "a", 1, 0, "Chương 1 - Mở đầu", "narration", "NARRATOR", 1, None),
        (2, "b", 1, 1, "“Heidi, các cậu đi đâu vậy?”", "dialogue", "HEIDI", 3, 2),
        (3, "c", 1, 2, "“Đi thôi.”", "dialogue", "LUCIEN", 2, 1),
        (4, "d", 1, 3, "“Ta đến rồi.”", "dialogue", "ÁO CHOÀNG ĐEN", 4, 3),
        (5, "e", 1, 4, "“Ta nữa.”", "dialogue", "ÁO CHOÀNG ĐEN", 4, 3),
        (6, "f", 1, 5, "“Được.”", "dialogue", "RHINE", 2, 4),
        (7, "g", 1, 6, "“Ai đó?”", "dialogue", "NPC_LOCAL::c00001::r1::người gác", 5, None),
        (8, "h", 1, 7, "Hailkes bước tới, Hailkes cười.", "narration", "NARRATOR", 1, None),
    ]
    db.executemany(
        "INSERT INTO segments (id, stable_id, chapter_id, seq, text, kind, speaker, voice_profile_id,"
        " canonical_character_id, status) VALUES (?,?,?,?,?,?,?,?,?, 'verified')",
        rows,
    )
    db.execute("UPDATE segments SET text_sha256='sha-' || stable_id")
    db.execute("INSERT INTO pronunciations VALUES ('Hailkes', 'Hain', 0.72, 1)")
    db.execute("INSERT INTO pronunciations VALUES ('Lucien', 'Lu-xi-ên', 0.99, 1)")
    db.commit()
    db.close()
    return project


def test_the_inbox_finds_each_kind_of_doubt_and_ranks_by_benefit(tmp_path: Path) -> None:
    started = time.time()
    view = work_items(make_book(tmp_path))
    kinds = {item["kind"]: item for item in view["items"]}
    assert kinds["vocative"]["examples"][0]["text"].startswith("“Heidi,"), "người được gọi không phải người nói"
    assert kinds["gender"]["title"].casefold().startswith("áo choàng đen") and kinds["gender"]["affected"] == 2
    assert "LUCIEN" not in str(kinds["gender"]), "đã biết giới thì không hỏi"
    shared = kinds["shared-voice"]
    assert "Lucien" in shared["title"] and "Rhine" in shared["title"], "hai người có tên, một giọng, cùng chương"
    assert kinds["unnamed"]["title"].casefold() == "“người gác” là ai?"
    pronunciation = kinds["pronunciation"]
    assert pronunciation["affected"] == 1 and "Hain" in pronunciation["title"], "đếm câu chứa tên, không đếm lần nhắc"
    assert not any("Lucien" in item["title"] and item["kind"] == "pronunciation" for item in view["items"]), "0,99 là chắc"
    scores = [item["score"] for item in view["items"]]
    assert scores == sorted(scores, reverse=True), "xếp theo lợi trên mỗi lần bấm"
    assert time.time() - started < 5


def test_a_pronunciation_card_has_lines_to_hear_and_shows_a_waiting_request(tmp_path: Path) -> None:
    """Bước 2: người nghe nghe máy đang đọc tên thế nào (câu đã thu trước), sửa ngay trên thẻ; mong muốn chưa áp thì thẻ
    nói "đang chờ" thay vì im lặng như chưa sửa."""
    from abook.listener_overrides import request_pronunciation

    project = make_book(tmp_path)
    db = sqlite3.connect(project / "project.sqlite3")
    db.execute("UPDATE segments SET wav_path='chunks/8.wav' WHERE id=8")
    db.commit()
    db.close()
    (project / "chunks").mkdir()
    (project / "chunks" / "8.wav").write_bytes(b"RIFF")
    card = next(item for item in work_items(project)["items"] if item["kind"] == "pronunciation")
    assert card["surface"] == "Hailkes" and card["requested"] is None
    assert card["examples"][0]["text"].startswith("Hailkes") and card["examples"][0]["hasAudio"] is True

    request_pronunciation(project, "Hailkes", "Hên-khơ", now=time.time())
    card = next(item for item in work_items(project)["items"] if item["kind"] == "pronunciation")
    assert card["requested"] == "Hên-khơ", "dây chuyền chưa áp: thẻ vẫn đó, kèm cách đọc đang chờ"


def test_the_studio_writes_the_request_and_refuses_a_reading_the_voice_cannot_say(tmp_path: Path) -> None:
    """Giao diện không ghi SQLite của sách: chỉ ghi overrides.json. Cách đọc không phải âm tiết tiếng Việt bị từ chối NGAY,
    kèm lý do đọc được - không để tới ranh giới chương mới lặng lẽ bỏ qua."""
    from abook.listener_overrides import pronunciation_requests, read_overrides
    from abook.webui.library import Preferences, book_id
    from abook.webui.listening import Listening
    from abook.webui.server import App, Server
    from tests.test_webui_listen_and_sync import FakeRunner, _request

    project = make_book(tmp_path)
    preferences = Preferences(tmp_path / "prefs" / "preferences.json")
    preferences.update({"libraryRoot": str(tmp_path)})
    app = App(preferences=preferences, runner=FakeRunner(), token="t", listening=Listening(tmp_path / "prefs" / "l.json"))
    server = Server(app, port=0).start()
    headers = {"X-Ebook-Token": "t"}
    path = f"/api/books/{book_id(project)}/pronunciation"
    before = (project / "project.sqlite3").read_bytes()
    try:
        status, data, _ = _request(server.port, "POST", path, headers=headers,
                                   body={"surface": "Hailkes", "spokenForm": " Hên-khơ "})
        assert status == 200 and json.loads(data)["spokenForm"] == "Hên-khơ"
        assert pronunciation_requests(read_overrides(project)) == [{"surface": "Hailkes", "spoken_form": "Hên-khơ"}]
        status, data, _ = _request(server.port, "POST", path, headers=headers,
                                   body={"surface": "Hailkes", "spokenForm": "Hlkx"})
        assert status == 400 and "âm tiết tiếng Việt" in json.loads(data)["error"]
        assert "suggestion" not in json.loads(data), "không có bản viết lại qua được phép kiểm thì không mời"
        # Gõ theo tai sai chính tả: lời báo chỉ đúng âm tiết sai và mời dùng bản sửa - chưa ghi gì tới khi người nghe chọn.
        status, data, _ = _request(server.port, "POST", path, headers=headers,
                                   body={"surface": "Hailkes", "spokenForm": "Hên-kơ"})
        answer = json.loads(data)
        assert status == 400 and answer["suggestion"] == "Hên-cơ" and "“kơ”" in answer["error"]
        assert pronunciation_requests(read_overrides(project)) == [{"surface": "Hailkes", "spoken_form": "Hên-khơ"}]
        status, data, _ = _request(server.port, "POST", path, headers=headers,
                                   body={"surface": "Lucien Evans", "spokenForm": "Lu-si-en"})
        assert status == 400 and "MỘT từ" in json.loads(data)["error"]
    finally:
        server.stop()
    assert (project / "project.sqlite3").read_bytes() == before, "chỉ dây chuyền được ghi SQLite của sách"


def test_a_speaker_card_offers_clickable_choices_and_hides_once_the_listener_keeps_it(tmp_path: Path) -> None:
    """"Ai nói câu này" bấm được: mỗi lựa chọn mang giá trị máy hiểu (khoá tên, NARRATOR, UNNAMED) và thẻ mang mã câu + băm
    chữ. Chọn một người thì thẻ nói "đang chờ"; chọn giữ nguyên thì thẻ biến mất - đã có người quyết."""
    from abook.listener_overrides import NARRATOR, UNNAMED, request_speaker

    project = make_book(tmp_path)
    unsure_line(project, "c")

    card = next(item for item in work_items(project)["items"] if item["kind"] == "speaker")
    assert (card["lines"], card["currentValue"]) == ([{"stableId": "c", "textSha256": "sha-c"}], "LUCIEN")
    values = [choice["value"] for choice in card["choices"]]
    assert values[-2:] == [NARRATOR, UNNAMED] and "RHINE" in values, "người trong chương là lựa chọn, kèm người kể và vô danh"

    request_speaker(project, "c", "sha-c", "RHINE", now=time.time())
    card = next(item for item in work_items(project)["items"] if item["kind"] == "speaker")
    assert card["requested"] == "Rhine"

    request_speaker(project, "c", "sha-c", "LUCIEN", now=time.time())
    assert not [item for item in work_items(project)["items"] if item["kind"] == "speaker"]


def test_a_speaker_card_shows_the_neighbouring_lines_and_offers_only_people_with_a_voice(tmp_path: Path) -> None:
    """Một câu không đủ để quyết ai nói: thẻ mang câu liền trước và liền sau; người chưa nói câu nào (chưa có giọng) không phải chip vì
    bấm vào chỉ ra lỗi - cùng phép thử `speaker_target` với lúc ghi yêu cầu."""
    project = make_book(tmp_path)
    unsure_line(project, "c")

    card = next(item for item in work_items(project)["items"] if item["kind"] == "speaker")
    (example,) = card["examples"]
    assert example["before"] == "“Heidi, các cậu đi đâu vậy?”" and example["after"] == "“Ta đến rồi.”"
    assert all(choice["value"] != "KHONG CO AI" for choice in card["choices"])


def test_the_studio_refuses_on_the_spot_a_speaker_the_pipeline_would_refuse(tmp_path: Path) -> None:
    """Giao diện hỏi bằng ĐÚNG phép dây chuyền dùng (`listener_overrides.speaker_target`), nên không có yêu cầu nào được
    ghi rồi lặng lẽ bị bỏ ở ranh giới chương. Và vẫn không ghi SQLite của sách."""
    from abook.listener_overrides import read_overrides, speaker_requests
    from abook.webui.library import Preferences, book_id
    from abook.webui.listening import Listening
    from abook.webui.server import App, Server
    from tests.test_webui_listen_and_sync import FakeRunner, _request

    project = make_book(tmp_path)
    before = (project / "project.sqlite3").read_bytes()
    preferences = Preferences(tmp_path / "prefs" / "preferences.json")
    preferences.update({"libraryRoot": str(tmp_path)})
    app = App(preferences=preferences, runner=FakeRunner(), token="t", listening=Listening(tmp_path / "prefs" / "l.json"))
    server = Server(app, port=0).start()
    headers = {"X-Ebook-Token": "t"}
    path = f"/api/books/{book_id(project)}/speaker"
    try:
        refused = {
            ("c", "sha-khac", "RHINE"): "đã đổi",
            ("a", "sha-a", "RHINE"): "lời kể",
            ("c", "sha-c", "KHONG CO AI"): "chưa có giọng",
        }
        for (stable_id, text_sha256, speaker), reason in refused.items():
            status, data, _ = _request(server.port, "POST", path, headers=headers,
                                       body={"stableId": stable_id, "textSha256": text_sha256, "speaker": speaker})
            assert status == 400 and reason in json.loads(data)["error"], (speaker, data)
        status, _data, _ = _request(server.port, "POST", path, headers=headers,
                                    body={"stableId": "c", "textSha256": "sha-c", "speaker": "RHINE"})
        assert status == 200
    finally:
        server.stop()
    assert speaker_requests(read_overrides(project)) == [{"stable_id": "c", "speaker": "RHINE", "text_sha256": "sha-c"}]
    assert (project / "project.sqlite3").read_bytes() == before


def test_the_called_person_and_the_unnamed_extra_get_the_chapters_speakers_as_choices(tmp_path: Path) -> None:
    """Người gọi hay người nói, vai phụ không tên: sửa bằng cùng cơ chế gán người nói. Ứng viên là người có tên nói quanh
    câu (6 đoạn, gần nhất trước), rồi người nói nhiều nhất chương (không phải người bị gọi); vai phụ thì chọn một lần cho MỌI câu của vai ấy."""
    from abook.listener_overrides import NARRATOR, UNNAMED, request_speakers

    project = make_book(tmp_path)
    items = {item["kind"]: item for item in work_items(project)["items"]}
    vocative, unnamed = items["vocative"], items["unnamed"]
    assert [choice["value"] for choice in vocative["choices"]] == ["LUCIEN", "ÁO CHOÀNG ĐEN", "RHINE", NARRATOR, UNNAMED]
    assert vocative["lines"] == [{"stableId": "b", "textSha256": "sha-b"}] and vocative["currentValue"] == "HEIDI"
    assert [choice["value"] for choice in unnamed["choices"]] == ["ÁO CHOÀNG ĐEN", "HEIDI", "LUCIEN", "RHINE"]

    request_speakers(project, [(line["stableId"], line["textSha256"]) for line in unnamed["lines"]], "RHINE",
                     now=time.time())
    assert next(item for item in work_items(project)["items"] if item["kind"] == "unnamed")["requested"] == "Rhine"
    request_speakers(project, [(line["stableId"], line["textSha256"]) for line in unnamed["lines"]],
                     unnamed["currentValue"], now=time.time())
    assert not [item for item in work_items(project)["items"] if item["kind"] == "unnamed"], "giữ nguyên thì đóng việc"


def test_a_group_request_is_taken_whole_or_refused_whole(tmp_path: Path) -> None:
    from abook.listener_overrides import read_overrides, speaker_requests
    from abook.webui.library import Preferences, book_id
    from abook.webui.listening import Listening
    from abook.webui.server import App, Server
    from tests.test_webui_listen_and_sync import FakeRunner, _request

    project = make_book(tmp_path)
    preferences = Preferences(tmp_path / "prefs" / "preferences.json")
    preferences.update({"libraryRoot": str(tmp_path)})
    app = App(preferences=preferences, runner=FakeRunner(), token="t", listening=Listening(tmp_path / "prefs" / "l.json"))
    server = Server(app, port=0).start()
    path = f"/api/books/{book_id(project)}/speaker"
    try:
        status, data, _ = _request(server.port, "POST", path, headers={"X-Ebook-Token": "t"}, body={
            "speaker": "RHINE",
            "lines": [{"stableId": "g", "textSha256": "sha-g"}, {"stableId": "e", "textSha256": "sha-khac"}],
        })
        assert status == 400 and "đã đổi" in json.loads(data)["error"]
        assert speaker_requests(read_overrides(project)) == [], "một câu hỏng thì cả nhóm không được ghi"
        status, data, _ = _request(server.port, "POST", path, headers={"X-Ebook-Token": "t"}, body={
            "speaker": "RHINE",
            "lines": [{"stableId": "g", "textSha256": "sha-g"}, {"stableId": "e", "textSha256": "sha-e"}],
        })
        assert status == 200 and json.loads(data)["lines"] == 2
    finally:
        server.stop()
    assert [entry["stable_id"] for entry in speaker_requests(read_overrides(project))] == ["e", "g"]


def make_dialogue_book(root: Path, first_person: str = "") -> Path:
    """Một cảnh đối đáp như Hướng dẫn sinh tồn 062 (28-09): máy gán cả ba câu liền nhau cho GLAST."""
    project = root / "doi_dap"
    project.mkdir(parents=True)
    voices = {"first_person_identity": first_person} if first_person else {}
    (project / "book_settings.json").write_text(json.dumps({"voices": voices}), encoding="utf-8")
    db = sqlite3.connect(project / "project.sqlite3")
    db.executescript(
        """
        CREATE TABLE chapters (id INTEGER PRIMARY KEY, chapter_index INTEGER, title TEXT);
        CREATE TABLE segments (id INTEGER PRIMARY KEY, stable_id TEXT, chapter_id INTEGER, seq INTEGER,
                               paragraph_index INTEGER, text TEXT, kind TEXT, speaker TEXT, voice_profile_id INTEGER,
                               canonical_character_id INTEGER, status TEXT, asr_text TEXT, asr_similarity REAL,
                               warning_code TEXT, wav_path TEXT, text_sha256 TEXT, gender TEXT);
        CREATE TABLE characters (id INTEGER PRIMARY KEY, canonical_name TEXT, display_name TEXT, gender TEXT,
                                 locked INTEGER, age TEXT);
        """
    )
    db.execute("INSERT INTO chapters VALUES (1, 1, '062')")
    db.executemany("INSERT INTO characters (id, canonical_name, display_name, gender, locked) VALUES (?,?,?,?,?)", [
        (1, "GLAST", "Glast", "male", 0), (2, "ED ROSTAILER", "Ed Rostailer", "male", 0),
    ])
    rows = [
        # seq, đoạn, chữ, loại, người nói (máy)
        (0, 0, "Giáo sư Glast lại ngước nhìn trời đêm.", "narration", "NARRATOR"),
        (1, 1, "“Cuối cùng, kế hoạch nào rồi cũng thất bại.”", "dialogue", "GLAST"),
        (2, 2, "“Ai biết ạ?”", "dialogue", "GLAST"),
        (3, 3, "“Ai biết được.”", "dialogue", "GLAST"),
        # Đoạn có lời dẫn riêng: máy có căn cứ, không nghi.
        (4, 4, "“Chỉ điểm chính xác đấy.”", "dialogue", "GLAST"),
        (5, 4, "Glast gật đầu.", "narration", "NARRATOR"),
        (6, 5, "“Ta vẫn nhớ ngày đầu làm giáo sư,", "dialogue", "ED ROSTAILER"),
        # Ngoặc để ngỏ ở đoạn trước: lời nói tiếp của cùng người, không phải lượt mới.
        (7, 6, "khi Obel còn là học trò.”", "dialogue", "ED ROSTAILER"),
        (8, 7, "“Hả?”", "dialogue", "NPC_LOCAL::c00001::r1::lính gác"),
        (9, 8, "“Hả?”", "dialogue", "NPC_LOCAL::c00001::r1::lính gác"),
        (10, 9, "“Đi thôi.”", "dialogue", "ED ROSTAILER"),
        (11, 10, "“Vâng.”", "dialogue", "GLAST"),
    ]
    db.executemany(
        "INSERT INTO segments (id, stable_id, chapter_id, seq, paragraph_index, text, kind, speaker, status)"
        " VALUES (?,?,1,?,?,?,?,?, 'verified')",
        [(seq + 1, f"s{seq}", seq, paragraph, text, kind, speaker) for seq, paragraph, text, kind, speaker in rows],
    )
    db.execute("UPDATE segments SET text_sha256='sha-' || stable_id")
    db.commit()
    db.close()
    return project


def test_quoted_paragraphs_in_a_row_given_to_one_person_are_one_card_that_alternates(tmp_path: Path) -> None:
    """Câu 1-2 và 2-3 là MỘT chuỗi: một thẻ đổi các câu xen kẽ. Trước đây mỗi cặp một thẻ - sửa thẻ đầu (câu 2 là người
    kia) thì thẻ sau vẫn hỏi "câu 3 cũng là của Glast?" như thể câu 2 vẫn là Glast (soát UX 29-09)."""
    view = work_items(make_dialogue_book(tmp_path, first_person="ED ROSTAILER"))
    turns = [item for item in view["items"] if item["kind"] == "turn"]
    assert [item["key"] for item in turns] == ["turns:s1"], "chỉ cặp đóng ngoặc -> mở ngoặc, đoạn sau không lời dẫn"
    card = turns[0]
    assert card["title"] == "3 câu liền nhau đều là của Glast?"
    assert card["suggested"] is False, "chip đầu của thẻ lượt đối đáp không phải đề xuất của máy (soát UX a13 #15)"
    assert [(example["text"], example["changes"]) for example in card["examples"]] == [
        ("“Cuối cùng, kế hoạch nào rồi cũng thất bại.”", False), ("“Ai biết ạ?”", True), ("“Ai biết được.”", False),
    ]
    assert card["choices"][0] == {"label": "Ed Rostailer", "value": "ED ROSTAILER"}, "truyện ngôi thứ nhất: 'tôi' đứng đầu"
    assert [line["stableId"] for line in card["lines"]] == ["s2"], "xen kẽ: câu 2 đổi, câu 1 và 3 giữ người của chúng"
    assert [line["stableId"] for line in card["allLines"]] == ["s1", "s2", "s3"], "phạm vi 'Cả chuỗi': độc thoại vắt nhiều đoạn"
    assert card["score"] > 0.8, "đo 28-09: 38/42 cặp như thế máy sai - xếp trên lời gọi đầu câu"


def test_a_lone_pair_keeps_its_two_line_card(tmp_path: Path) -> None:
    project = make_dialogue_book(tmp_path, first_person="ED ROSTAILER")
    db = sqlite3.connect(project / "project.sqlite3")
    db.execute("DELETE FROM segments WHERE stable_id = 's3'")
    db.commit()
    db.close()
    card = next(item for item in work_items(project)["items"] if item["kind"] == "turn")
    assert (card["key"], card["title"]) == ("turn:s2", "Hai câu liền nhau đều là của Glast?")
    assert [example["changes"] for example in card["examples"]] == [False, True], "sửa câu SAU, câu trước giữ người của nó"
    assert [line["stableId"] for line in card["lines"]] == ["s2"] and "allLines" not in card


def test_a_long_run_is_cut_into_cards_that_keep_the_alternation(tmp_path: Path) -> None:
    """Mười đoạn thoại liền nhau cùng gán Glast: khúc đầu 8 câu đổi câu 2, 4, 6, 8; khúc sau (câu 9-10) đổi câu 10 - câu
    9 giữ Glast như câu 1, 3... vì khúc dài số chẵn."""
    project = make_dialogue_book(tmp_path, first_person="ED ROSTAILER")
    db = sqlite3.connect(project / "project.sqlite3")
    db.execute("DELETE FROM segments")
    db.executemany(
        "INSERT INTO segments (id, stable_id, chapter_id, seq, paragraph_index, text, kind, speaker, status, text_sha256)"
        " VALUES (?,?,1,?,?,?,'dialogue','GLAST','verified',?)",
        [(number, f"t{number}", number, number, f"“Câu {number}.”", f"sha-t{number}") for number in range(1, 11)],
    )
    db.commit()
    db.close()
    turns = [item for item in work_items(project)["items"] if item["kind"] == "turn"]
    assert [item["key"] for item in turns] == ["turns:t1", "turn:t10"]
    assert [line["stableId"] for line in turns[0]["lines"]] == ["t2", "t4", "t6", "t8"]
    assert turns[0]["affected"] == 4 and turns[0]["title"] == "8 câu liền nhau đều là của Glast?"
    assert [line["stableId"] for line in turns[1]["lines"]] == ["t10"]
    assert [example["text"] for example in turns[1]["examples"]] == ["“Câu 9.”", "“Câu 10.”"]


def test_a_book_without_paragraph_numbers_or_a_narrator_still_builds_its_inbox(tmp_path: Path) -> None:
    assert not [item for item in work_items(make_book(tmp_path))["items"] if item["kind"] == "turn"]
    third_person = work_items(make_dialogue_book(tmp_path / "ba", first_person=""))
    card = next(item for item in third_person["items"] if item["kind"] == "turn")
    assert card["choices"][0]["value"] == "ED ROSTAILER", "không có 'tôi' thì là người có tên nói nhiều nhất chương"


def make_alias_book(root: Path) -> Path:
    """Hai cặp một-người-hai-tên theo hai chiều: tên NGẮN nói nhiều (Lucien 3 câu, Lucien Evans 1 câu) và tên DÀI nói nhiều
    (Heidi Schmidt 2 câu, Heidi 1 câu); Anna / Anna Rhine khác giới thì không phải một người."""
    project = make_book(root)
    db = sqlite3.connect(project / "project.sqlite3")
    db.execute("DELETE FROM segments")
    db.executemany("INSERT INTO characters (id, canonical_name, display_name, gender, locked) VALUES (?,?,?,?,?)", [
        (11, "LUCIEN EVANS", "Lucien Evans", "male", 0),
        (12, "HEIDI SCHMIDT", "Heidi Schmidt", "female", 0),
        (13, "ANNA", "Anna", "female", 0),
        (14, "ANNA RHINE", "Anna Rhine", "male", 0),
    ])
    rows = [
        ("a1", "“Đi thôi.”", "LUCIEN", 2, 1),
        ("a2", "“Nhanh lên.”", "LUCIEN", 2, 1),
        ("a3", "“Tới rồi.”", "LUCIEN", 2, 1),
        ("a4", "“Ta là Lucien Evans.”", "LUCIEN EVANS", 9, 11),
        ("b1", "“Chào.”", "HEIDI SCHMIDT", 3, 12),
        ("b2", "“Tạm biệt.”", "HEIDI SCHMIDT", 3, 12),
        ("b3", "“Ừ.”", "HEIDI", 8, 2),
        ("c1", "“Ồ.”", "ANNA", 6, 13),
        ("c2", "“À.”", "ANNA RHINE", 7, 14),
    ]
    db.executemany(
        "INSERT INTO segments (stable_id, chapter_id, seq, text, kind, speaker, voice_profile_id, canonical_character_id,"
        " status, text_sha256) VALUES (?, 1, ?, ?, 'dialogue', ?, ?, ?, 'verified', 'sha-' || ?)",
        [(stable, seq, text, speaker, voice, character, stable) for seq, (stable, text, speaker, voice, character) in enumerate(rows)],
    )
    db.commit()
    db.close()
    return project


def test_one_person_under_two_names_merges_the_fewer_lines_into_the_voice_heard_most(tmp_path: Path) -> None:
    """Thẻ bí danh bấm được: câu của tên ÍT câu về tên NHIỀU câu (người nghe đã quen giọng ấy, ít câu phải thu lại) - kể
    cả khi tên ngắn mới là tên nói nhiều, trường hợp trước đây thẻ bỏ sót. "Hai người khác nhau" giữ cả nhóm, thẻ biến."""
    from abook.listener_overrides import request_speakers

    project = make_alias_book(tmp_path)
    cards = {item["key"]: item for item in work_items(project)["items"] if item["kind"] == "alias"}
    assert set(cards) == {"alias:LUCIEN EVANS|LUCIEN", "alias:HEIDI SCHMIDT|HEIDI"}, "Anna / Anna Rhine khác giới"
    lucien = cards["alias:LUCIEN EVANS|LUCIEN"]
    assert lucien["title"] == "“Lucien” và “Lucien Evans” là một người?"
    assert [line["stableId"] for line in lucien["lines"]] == ["a4"] and lucien["affected"] == 1
    assert lucien["choices"] == [{"label": "Gộp vào Lucien", "value": "LUCIEN", "name": "Lucien"}]
    assert lucien["currentValue"] == "LUCIEN EVANS" and lucien["keepLabel"] == "Hai người khác nhau"
    # Tên được hỏi để hiển thị ("“Lucien Evans” là Lucien") - `current` là nhãn lựa chọn, không phải tên.
    assert lucien["subject"] == "Lucien Evans"
    heidi = cards["alias:HEIDI SCHMIDT|HEIDI"]
    assert [line["stableId"] for line in heidi["lines"]] == ["b3"]
    assert heidi["choices"][0]["value"] == "HEIDI SCHMIDT" and heidi["choices"][0]["name"] == "Heidi Schmidt"

    request_speakers(project, [("a4", "sha-a4")], "LUCIEN", now=time.time())
    request_speakers(project, [("b3", "sha-b3")], "HEIDI", now=time.time())
    cards = {item["key"]: item for item in work_items(project)["items"] if item["kind"] == "alias"}
    assert cards["alias:LUCIEN EVANS|LUCIEN"]["requested"] == "Lucien", "gộp đang chờ ranh giới chương"
    assert "alias:HEIDI SCHMIDT|HEIDI" not in cards, "người nghe nói hai người khác nhau: không hỏi lại"


def make_bracket_book(root: Path) -> Path:
    """Linh thể nói trong 『』 cả chương mà máy chia cho ba người (như Yamiyo, bộ LN 28-09); chương 2 thì 『』 nhất quán."""
    project = make_book(root)
    db = sqlite3.connect(project / "project.sqlite3")
    db.execute("DELETE FROM segments")
    db.execute("INSERT INTO chapters VALUES (2, 2, '002')")
    db.executemany("INSERT INTO characters (id, canonical_name, display_name, gender, locked) VALUES (?,?,?,?,?)", [
        (21, "TỌA PHU ĐỒNG TỬ", "Tọa Phu Đồng Tử", "female", 0),
        (22, "HINA", "Hina", "female", 0),
        (23, "TOMOBE", "Tomobe", "male", 0),
    ])
    rows = [
        ("s1", 1, "『Tạm biệt nhé.』", "TOMOBE"),
        ("s2", 1, "“Vâng.”", "HINA"),
        ("s3", 1, "『Tối nay chúng ta lại ngủ cùng nhau nhé?』", "HINA"),
        ("s4", 1, "『Thiếp hiểu cảm giác đó mà.』", "TỌA PHU ĐỒNG TỬ"),
        ("s5", 1, "『Hử? Khí tức này...』", "TỌA PHU ĐỒNG TỬ"),
        ("t1", 2, "『Chàng về rồi.』", "TỌA PHU ĐỒNG TỬ"),
        ("t2", 2, "『Thiếp đợi mãi.』", "TỌA PHU ĐỒNG TỬ"),
        ("t3", 2, "『Vào đi.』", "TỌA PHU ĐỒNG TỬ"),
    ]
    db.executemany(
        "INSERT INTO segments (stable_id, chapter_id, seq, text, kind, speaker, status, text_sha256)"
        " VALUES (?, ?, ?, ?, 'dialogue', ?, 'verified', 'sha-' || ?)",
        [(stable, chapter, seq, text, speaker, stable) for seq, (stable, chapter, text, speaker) in enumerate(rows)],
    )
    db.commit()
    db.close()
    return project


def test_telepathy_in_corner_brackets_split_across_people_is_fixed_for_the_whole_chapter(tmp_path: Path) -> None:
    """Máy yếu nhất ở lời 『』 (bộ LN 28-09: sai 56-67%): chương chia 『』 cho nhiều người -> một thẻ, một cú bấm gán cả
    nhóm; lời thường (“…”) không nằm trong nhóm; chương đã nhất quán thì không hỏi."""
    from abook.listener_overrides import request_speakers

    project = make_bracket_book(tmp_path)
    cards = [item for item in work_items(project)["items"] if item["kind"] == "bracket"]
    assert [card["key"] for card in cards] == ["bracket:1"], "chương 2 đã nhất quán"
    card = cards[0]
    assert [line["stableId"] for line in card["lines"]] == ["s1", "s3", "s4", "s5"] and card["affected"] == 4
    assert card["choices"][0] == {"label": "Tất cả là Tọa Phu Đồng Tử", "value": "TỌA PHU ĐỒNG TỬ",
                                  "name": "Tọa Phu Đồng Tử"}, "người nói nhiều nhất trong 『』 đứng đầu"
    assert card["choices"][-1]["value"] == "NARRATOR"
    assert not card["currentValue"], "nhóm mang nhiều nhãn: không có nút giữ nguyên"

    request_speakers(project, [(line["stableId"], line["textSha256"]) for line in card["lines"]], "TỌA PHU ĐỒNG TỬ",
                     now=time.time())
    cards = [item for item in work_items(project)["items"] if item["kind"] == "bracket"]
    assert cards and cards[0]["requested"] == "Tọa Phu Đồng Tử", "đang chờ ranh giới chương"


def make_epithet_book(root: Path) -> Path:
    """Người kể Krai bị gán câu dưới danh hiệu "Thiên Biến Vạn Hóa" - sách viết danh hiệu sát tên ba lần. Tino đứng cạnh Krai
    chỉ qua dấu phẩy (danh sách), "Giáo sư" đứng sát HAI người: không phải biệt danh của ai."""
    project = make_book(root)
    source = root / "nguon"
    source.mkdir()
    (source / "001.txt").write_text(
        "Thiên Biến Vạn Hóa Krai bước vào. Ai cũng sợ Thiên Biến Vạn Hóa Krai Andrey. Người ta gọi Krai được mệnh danh"
        " Thiên Biến Vạn Hóa. Tino, Krai và Lucia đi chợ. Tino, Krai ngồi xuống. Tino, Krai lại đi.\n"
        "Giáo sư Glast gật đầu. Giáo sư Krayd lắc đầu. Rồi Giáo sư Glast nói. Giáo sư Krayd im.\n",
        encoding="utf-8")
    db = sqlite3.connect(project / "project.sqlite3")
    db.execute("ALTER TABLE chapters ADD COLUMN input_path TEXT")
    db.execute("UPDATE chapters SET input_path = ?", (str(source / "001.txt"),))
    db.execute("DELETE FROM segments")
    rows = [
        ("k1", "“Đi thôi.”", "KRAI ANDREY"), ("k2", "“Ừ.”", "KRAI ANDREY"), ("k3", "“Được.”", "KRAI ANDREY"),
        ("e1", "“Tôi không làm gì cả.”", "THIÊN BIẾN VẠN HÓA"),
        ("t1", "“Anh Krai!”", "TINO"),
        ("g1", "“Học đi.”", "GIÁO SƯ"), ("g2", "“Ta là Glast.”", "GLAST"), ("g3", "“Ta là Krayd.”", "KRAYD"),
    ]
    db.executemany(
        "INSERT INTO segments (stable_id, chapter_id, seq, text, kind, speaker, voice_profile_id, canonical_character_id,"
        " status, text_sha256) VALUES (?, 1, ?, ?, 'dialogue', ?, 1, NULL, 'verified', 'sha-' || ?)",
        [(stable, seq, text, speaker, stable) for seq, (stable, text, speaker) in enumerate(rows)],
    )
    db.commit()
    db.close()
    return project


def test_a_title_the_book_writes_next_to_one_name_asks_to_join_that_voice(tmp_path: Path) -> None:
    """Thẻ biệt danh (3a): "Thiên Biến Vạn Hóa" sát "Krai" ba lần -> hỏi gộp câu của danh hiệu vào Krai. Dấu phẩy không
    tính (danh sách "Tino, Krai"); chức danh sát hai người ("Giáo sư Glast", "Giáo sư Krayd") không phải biệt danh."""
    project = make_epithet_book(tmp_path)
    cards = {item["key"]: item for item in work_items(project)["items"] if item["kind"] == "alias"}
    assert set(cards) == {"alias:KRAI ANDREY|THIÊN BIẾN VẠN HÓA"}, set(cards)
    card = cards["alias:KRAI ANDREY|THIÊN BIẾN VẠN HÓA"]
    assert [line["stableId"] for line in card["lines"]] == ["e1"] and card["affected"] == 1
    assert card["choices"] == [{"label": "Gộp vào Krai Andrey", "value": "KRAI ANDREY", "name": "Krai Andrey"}]
    assert "sát nhau 3 lần" in card["problem"] and card["keepLabel"] == "Hai người khác nhau"


def test_a_sample_line_is_playable_only_when_its_recording_exists(tmp_path: Path) -> None:
    """Soát UX a8: nút ▶ của câu mẫu nào cũng 404 vì ví dụ mặc định "có audio" - nay hasAudio nói đúng thực tế."""
    project = make_book(tmp_path)
    db = sqlite3.connect(project / "project.sqlite3")
    db.execute("UPDATE segments SET wav_path='chunks/4.wav' WHERE id=4")  # có đường dẫn nhưng file không còn
    db.execute("UPDATE segments SET wav_path='chunks/5.wav' WHERE id=5")  # có file thật
    db.commit()
    db.close()
    (project / "chunks").mkdir()
    (project / "chunks" / "5.wav").write_bytes(b"RIFF")
    gender = next(item for item in work_items(project)["items"] if item["kind"] == "gender")
    audio = {example["segmentId"]: example["hasAudio"] for example in gender["examples"]}
    assert audio == {4: False, 5: True}


def test_the_reserved_unknown_speaker_never_shows_as_a_name_or_gets_a_gender_card(tmp_path: Path) -> None:
    """Soát UX a8: "Unknown là nam hay nữ?" / "máy gán: Unknown" - UNKNOWN là nhãn "vai phụ không tên", tab Kịch bản gọi nó thế."""
    project = make_book(tmp_path)
    db = sqlite3.connect(project / "project.sqlite3")
    db.execute("INSERT INTO characters (id, canonical_name, display_name, gender, locked) VALUES (9, 'UNKNOWN', 'Unknown', 'unknown', 0)")
    db.executemany(
        "INSERT INTO segments (id, stable_id, chapter_id, seq, text, kind, speaker, voice_profile_id,"
        " canonical_character_id, status, text_sha256) VALUES (?,?,?,?,?,?,?,?,?, 'verified', ?)",
        [(20, "u1", 1, 20, "“Ai đó?”", "dialogue", "UNKNOWN", 6, 9, "sha-u1"),
         (21, "u2", 1, 21, "“Là tôi.”", "dialogue", "UNKNOWN", 6, 9, "sha-u2")])
    db.commit()
    db.close()
    items = work_items(project)["items"]
    assert not [item for item in items if item["kind"] == "gender" and "nknown" in item["title"]]
    texts = json.dumps(items, ensure_ascii=False)
    assert "Unknown" not in texts and "UNKNOWN" not in texts.replace("stableId", "")
    from abook.webui.reviews import speaker_label

    assert [speaker_label(raw) for raw in ("UNKNOWN", "Unknown", "UNNAMED", "ANONYMOUS_1")] == ["Vai phụ không tên"] * 4


def test_every_decided_card_carries_the_withdrawal_of_its_own_click(tmp_path: Path) -> None:
    """"Đã quyết, chờ áp dụng" có nút Hoàn tác cho TỪNG mục (không chỉ toast vài giây): thẻ mang đúng thân yêu cầu `withdraw`
    mà thông báo hoàn tác gửi - endpoint + `requestedAt` của lần bấm ấy."""
    from abook.listener_overrides import NARRATOR, request_pronunciation, request_speaker

    project = make_book(tmp_path)
    unsure_line(project, "c")
    cards = {item["kind"]: item for item in work_items(project)["items"]}
    assert "undo" not in cards["speaker"] and "undo" not in cards["pronunciation"], "chưa quyết thì chưa có gì để hoàn tác"

    request_speaker(project, "c", "sha-c", NARRATOR, now=1234.5)
    request_pronunciation(project, "Hailkes", "Hên-khơ", now=2345.5)
    cards = {item["kind"]: item for item in work_items(project)["items"]}
    assert cards["speaker"]["undo"] == {"endpoint": "speaker", "decisions": [
        {"lines": [{"stableId": "c", "textSha256": "sha-c"}], "requestedAt": 1234.5}]}
    assert cards["pronunciation"]["undo"] == {"endpoint": "pronunciation", "decisions": [
        {"surface": "Hailkes", "requestedAt": 2345.5, "previous": cards["pronunciation"]["current"], "keep": False}]}

    # Giữ đúng cách máy đang đọc: hoàn tác cũng bỏ được (keep) dù dây chuyền đã áp hay chưa.
    request_pronunciation(project, "Hailkes", cards["pronunciation"]["current"], now=3456.5)
    card = next(item for item in work_items(project)["items"] if item["kind"] == "pronunciation")
    assert card["undo"]["decisions"][0]["keep"] is True and card["undo"]["decisions"][0]["requestedAt"] == 3456.5


def write_logprobs(project: Path, rows: list[dict]) -> None:
    folder = project / "analysis_logprobs"
    folder.mkdir()
    body = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
    (folder / "00001.jsonl").write_bytes(body.encode("utf-8"))


def lp(stable_id: str, speaker: str, p_first: float) -> dict:
    return {"chapter": 1, "seq": 0, "stable_id": stable_id, "kind": "dialogue", "speaker": speaker, "p_first": p_first,
            "p_seq": p_first, "margin": 0.1, "alts": [], "ntok": 1, "p_end": 0.99}


def speaker_cards(project: Path) -> list[dict]:
    return [item for item in work_items(project)["items"] if item["kind"] == "speaker"]


def unsure_line(project: Path, stable_id: str) -> None:
    """Cho đúng câu `stable_id` của make_book là câu model kém chắc nhất (6 câu thoại có số đo -> 1 thẻ): thẻ "Ai nói câu này"."""
    rows = {"b": "HEIDI", "c": "LUCIEN", "d": "ÁO CHOÀNG ĐEN", "e": "ÁO CHOÀNG ĐEN", "f": "RHINE", "g": "NPC_LOCAL::c00001::r1::người gác"}
    write_logprobs(project, [lp(key, who, 0.3 if key == stable_id else 0.99) for key, who in rows.items()])


def test_the_models_own_doubt_asks_only_the_least_sure_fifth_of_the_measured_lines(tmp_path: Path) -> None:
    """Số đo logprob (analysis_logprobs/): 6 câu thoại có số đo -> tối đa 20% = 1 thẻ; thêm vào cho đủ 20 thì tối đa 4 thẻ,
    là các câu p_first thấp nhất, và câu p_first từ ngưỡng trở lên không bao giờ thành thẻ."""
    from abook.listener_overrides import NARRATOR, UNNAMED

    project = make_book(tmp_path)
    rows = [lp("b", "HEIDI", 0.2), lp("c", "LUCIEN", 0.5), lp("d", "ÁO CHOÀNG ĐEN", 0.9), lp("e", "ÁO CHOÀNG ĐEN", 0.95),
            lp("f", "RHINE", 0.99), lp("g", "NPC_LOCAL::c00001::r1::người gác", 0.7)]
    write_logprobs(project, rows)
    assert [card["key"] for card in speaker_cards(project)] == ["speaker:b"], "6 câu x 20% = 1 thẻ: câu p_first thấp nhất"
    rows += [dict(lp(f"x{index}", "LUCIEN", 0.99)) for index in range(14)]
    (project / "analysis_logprobs" / "00001.jsonl").write_bytes(
        "".join(json.dumps(row) + "\n" for row in rows).encode("utf-8"))
    # 14 câu "x" không có trong sổ nên không tính: vẫn 6 câu đo được thì vẫn 1 thẻ.
    assert [card["key"] for card in speaker_cards(project)] == ["speaker:b"]

    db = sqlite3.connect(project / "project.sqlite3")
    db.executemany(
        "INSERT INTO segments (id, stable_id, chapter_id, seq, text, kind, speaker, status, text_sha256)"
        " VALUES (?,?,1,?,?, 'dialogue', 'LUCIEN', 'verified', ?)",
        [(100 + index, f"x{index}", 100 + index, f"“Câu {index}.”", f"sha-x{index}") for index in range(14)],
    )
    db.commit()
    db.close()
    cards = speaker_cards(project)
    assert [card["key"] for card in cards] == ["speaker:b", "speaker:c", "speaker:g"], (
        "20 câu x 20% = 4 chỗ nhưng chỉ 3 câu dưới ngưỡng, p_first thấp nhất trước")
    first = cards[0]
    assert first["title"] == "Ai nói câu này - Heidi?"
    assert first["problem"] == "Máy gán cho Heidi nhưng chỉ chắc khoảng 20%."
    assert first["suggested"] is False, "thẻ logprob không đề xuất ai: chip đầu không tô cam"
    assert first["doubt"] == 0.8 and first["current"] == "Heidi"
    assert first["lines"] == [{"stableId": "b", "textSha256": "sha-b"}]
    values = [choice["value"] for choice in first["choices"]]
    assert "LUCIEN" in values and "HEIDI" not in values and values[-2:] == [NARRATOR, UNNAMED]
    assert [option for option in first["options"] if option in ("Người kể", "Vai phụ không tên")] == ["Người kể", "Vai phụ không tên"]


def test_a_line_whose_label_changed_gets_no_logprob_card(tmp_path: Path) -> None:
    project = make_book(tmp_path)
    db = sqlite3.connect(project / "project.sqlite3")
    db.executemany(
        "INSERT INTO segments (id, stable_id, chapter_id, seq, text, kind, speaker, status, text_sha256)"
        " VALUES (?,?,1,?,?, 'dialogue', 'LUCIEN', 'verified', ?)",
        [(100 + index, f"x{index}", 100 + index, f"“Câu {index}.”", f"sha-x{index}") for index in range(20)],
    )
    db.commit()
    db.close()
    rows = [lp(f"x{index}", "LUCIEN", 0.99) for index in range(20)]
    rows += [lp("b", "LUCIEN", 0.1),   # sổ nay là HEIDI: nhãn đã đổi sau lần đo
             lp("c", "lucien", 0.15)]  # cùng nhãn khác cách viết: vẫn tính
    write_logprobs(project, rows)
    cards = speaker_cards(project)
    assert [card["key"] for card in cards if card["problem"].startswith("Máy gán")] == ["speaker:c"], \
        "22 câu đo x 20% = 4 chỗ nhưng b đã đổi nhãn nên chỉ c thành thẻ"


def test_a_logprob_card_follows_the_listeners_decision_and_survives_bad_files(tmp_path: Path) -> None:
    from abook.listener_overrides import request_speaker

    project = make_book(tmp_path)
    db = sqlite3.connect(project / "project.sqlite3")
    db.executemany(
        "INSERT INTO segments (id, stable_id, chapter_id, seq, text, kind, speaker, status, text_sha256)"
        " VALUES (?,?,1,?,?, 'dialogue', 'LUCIEN', 'verified', ?)",
        [(100 + index, f"x{index}", 100 + index, f"“Câu {index}.”", f"sha-x{index}") for index in range(10)],
    )
    db.commit()
    db.close()
    write_logprobs(project, [lp(f"x{index}", "LUCIEN", 0.99) for index in range(9)] + [lp("x9", "LUCIEN", 0.3)])
    path = project / "analysis_logprobs" / "00001.jsonl"
    path.write_bytes(path.read_bytes() + b"{not json\n\n[1,2]\n" + json.dumps({"stable_id": "c", "speaker": "LUCIEN"}).encode()
                     + b"\n" + json.dumps(lp("c", "LUCIEN", 1.7)).encode() + b"\n")
    (project / "analysis_logprobs" / "00002.jsonl").write_bytes(b"\xff\xfe broken")
    card = next(item for item in speaker_cards(project))
    assert card["key"] == "speaker:x9" and card["problem"].endswith("chỉ chắc khoảng 30%.")
    assert not card["requested"]

    request_speaker(project, "x9", "sha-x9", "RHINE", now=time.time())
    assert next(item for item in speaker_cards(project))["requested"] == "Rhine"
    request_speaker(project, "x9", "sha-x9", "LUCIEN", now=time.time())
    assert speaker_cards(project) == [], "người nghe đã quyết giữ -> hết hỏi"


def test_without_the_logprob_files_nothing_is_asked(tmp_path: Path) -> None:
    assert not any(item["problem"].startswith("Máy gán") for item in speaker_cards(make_book(tmp_path)))


def with_voices(project: Path) -> None:
    """Sổ giọng của make_book: hồ sơ 2 (Lucien + Rhine) có khoá giọng - thẻ trùng giọng mới có nút "Đổi giọng …"."""
    db = sqlite3.connect(project / "project.sqlite3")
    db.execute("CREATE TABLE voice_profiles (id INTEGER PRIMARY KEY, voice_key TEXT, preset_name TEXT)")
    db.executemany("INSERT INTO voice_profiles VALUES (?,?,?)", [(2, "vieneu:pham-tuyen", "Phạm Tuyên"),
                                                                 (4, "vieneu:hai-dang", "Hải Đăng")])
    db.commit()
    db.close()


def test_a_book_not_yet_recorded_says_changing_a_voice_costs_nothing(tmp_path: Path) -> None:
    """Soát UX a23 B1: sách chưa thu chương nào mà thẻ ghi "thu lại 144 câu" - chỉ câu ĐÃ THU phải thu lại (như hộp chọn giọng)."""
    project = make_book(tmp_path)
    with_voices(project)
    cards = {item["kind"]: item for item in work_items(project)["items"]}
    notes = [choice["note"] for choice in cards["shared-voice"]["voiceChoices"]]
    assert notes == ["chưa thu nên không phải thu lại"] * 2
    assert {choice["note"] for choice in cards["gender"]["voiceChoices"]} <= {"giữ giọng đang đọc",
                                                                             "đổi giọng, chưa thu nên không phải thu lại"}

    db = sqlite3.connect(project / "project.sqlite3")
    db.execute("UPDATE segments SET wav_path='chunks/3.wav' WHERE id=3")  # một câu của Lucien đã thu
    db.execute("UPDATE segments SET wav_path='chunks/4.wav' WHERE id=4")  # một trong hai câu của Áo choàng đen
    db.commit()
    db.close()
    cards = {item["kind"]: item for item in work_items(project)["items"]}
    notes = {choice["label"]: choice["note"] for choice in cards["shared-voice"]["voiceChoices"]}
    assert notes == {"Đổi giọng Lucien": "thu lại 1 câu ở các chương chung",
                     "Đổi giọng Rhine": "chưa thu nên không phải thu lại"}
    assert "đổi giọng, thu lại 1 câu" in {choice["note"] for choice in cards["gender"]["voiceChoices"]}


def test_the_bad_recording_card_drops_the_lines_already_judged(tmp_path: Path) -> None:
    """Soát UX a23 B9: chấm hết câu ở "Cần nghe lại" mà thẻ "Bản thu lỗi · Chưa nghe" vẫn đứng, số việc không về 0 - hộp việc
    đếm hàng chờ mà bỏ qua phán quyết (reviews.json). Đi trọn đường API như tab thật."""
    from abook.webui.actions import FakeRunner
    from abook.webui.library import Preferences, book_id
    from abook.webui.server import App, Server
    from tests.test_webui_listen_and_sync import _request, make_project

    root = tmp_path / "thu_vien"
    project = make_project(root)
    db = sqlite3.connect(project / "project.sqlite3")
    for column in ("stable_id TEXT", "text_sha256 TEXT", "canonical_character_id INTEGER", "asr_text TEXT",
                   "asr_similarity REAL", "warning_code TEXT"):
        db.execute(f"ALTER TABLE segments ADD COLUMN {column}")
    db.execute("ALTER TABLE characters ADD COLUMN locked INTEGER")
    db.execute("UPDATE segments SET stable_id = 's' || id, text_sha256 = 'h' || id")
    db.execute("UPDATE segments SET status='warning', asr_text='Đi thối', asr_similarity=0.5 WHERE id IN (2, 3)")
    db.commit()
    db.close()
    preferences = Preferences(tmp_path / "prefs" / "preferences.json")
    preferences.update({"libraryRoot": str(root)})
    app = App(preferences=preferences, runner=FakeRunner(), token="phien")
    server = Server(app, port=0).start()
    headers = {"X-Ebook-Token": "phien"}
    work = f"/api/books/{book_id(project)}/work"

    def audio_cards() -> list[dict]:
        status, data, _ = _request(server.port, "GET", work, headers=headers)
        assert status == 200, data
        return [item for item in json.loads(data)["items"] if item["kind"] == "audio"]

    try:
        assert [card["affected"] for card in audio_cards()] == [2]
        for stable_id, verdict in (("s2", "ok"), ("s3", "redo")):
            status, data, _ = _request(server.port, "POST", f"/api/books/{book_id(project)}/review", headers=headers,
                                       body={"stableId": stable_id, "verdict": verdict, "chapterId": 1})
            assert status == 200, data
            if stable_id == "s2":
                assert [card["affected"] for card in audio_cards()] == [1], "câu đã chấm rơi khỏi thẻ"
        assert audio_cards() == [], "chấm hết thì thẻ biến mất"
        status, data, _ = _request(server.port, "GET", work + "?count=1", headers=headers)
        assert json.loads(data)["count"] == 0
    finally:
        server.stop()
        app.close()


def test_choosing_a_new_voice_for_one_of_two_sharing_people_settles_the_shared_voice_card(tmp_path: Path) -> None:
    """Soát UX a23 B3: đổi giọng Lucien ở tab Nhân vật (chọn hẳn một giọng) mà thẻ "Lucien, Rhine dùng chung một giọng" vẫn mở."""
    from abook.listener_overrides import request_voice

    project = make_book(tmp_path)
    with_voices(project)
    request_voice(project, "LUCIEN", preset="Hải Đăng", now=time.time())
    card = next(item for item in work_items(project)["items"] if item["kind"] == "shared-voice")
    assert card["requested"] == "đổi giọng Lucien"


def test_the_tab_count_leaves_out_cards_only_a_redo_can_apply(tmp_path: Path, monkeypatch) -> None:
    """Soát UX a23 B2: lúc chờ duyệt, "Việc cần duyệt 6" toàn là thẻ người kể chỉ áp khi làm lại phân tích - không có gì quyết
    được ngay mà số vẫn mời vào. Số trên nhãn chỉ đếm việc chưa quyết mà quyết thì có tác dụng."""
    from abook.webui import server as server_module
    from abook.webui.actions import FakeRunner
    from abook.webui.library import Preferences, book_id
    from abook.webui.server import App, Server
    from tests.test_webui_listen_and_sync import _request, make_project

    view = {"items": [{"key": "narrator:1", "requested": None, "redoOnly": True},
                      {"key": "gender:A", "requested": None},
                      {"key": "gender:B", "requested": "Nam"}], "counts": {}}
    monkeypatch.setattr(server_module, "work_items", lambda *_args, **_kwargs: view)
    root = tmp_path / "thu_vien"
    project = make_project(root)
    preferences = Preferences(tmp_path / "prefs" / "preferences.json")
    preferences.update({"libraryRoot": str(root)})
    app = App(preferences=preferences, runner=FakeRunner(), token="phien")
    server = Server(app, port=0).start()
    try:
        status, data, _ = _request(server.port, "GET", f"/api/books/{book_id(project)}/work?count=1",
                                   headers={"X-Ebook-Token": "phien"})
        assert status == 200 and json.loads(data)["count"] == 1
    finally:
        server.stop()
        app.close()


def test_corner_brackets_that_really_are_several_people_can_be_kept_on_the_card(tmp_path: Path) -> None:
    """Soát UX a23 B7: thẻ 『』 không có "giữ nguyên" - sách thật nhiều người nói 『』 thì thẻ nằm mãi, lối thoát duy nhất là
    "Xác nhận cả chương" ở Kịch bản. "Đúng rồi, giữ nguyên" ghi như xác nhận chương, nhưng chỉ cho các câu của thẻ."""
    from abook.listener_overrides import request_speakers

    project = make_bracket_book(tmp_path)
    card = next(item for item in work_items(project)["items"] if item["kind"] == "bracket")
    assert card["keepLabel"] == "Đúng rồi, giữ nguyên"
    groups = {group["speaker"]: [line["stableId"] for line in group["lines"]] for group in card["keepGroups"]}
    assert groups == {"TOMOBE": ["s1"], "HINA": ["s3"], "TỌA PHU ĐỒNG TỬ": ["s4", "s5"]}, "lời thường “…” không nằm trong nhóm"
    for group in card["keepGroups"]:
        request_speakers(project, [(line["stableId"], line["textSha256"]) for line in group["lines"]], group["speaker"],
                         now=time.time())
    assert not [item for item in work_items(project)["items"] if item["kind"] == "bracket"], "giữ cả nhóm -> hết hỏi"
