"""Tab "Kịch bản" của Studio (webui/casting_review.py): đọc cả chương như kịch bản - câu nào của ai - và sửa người nói của
bất kỳ câu nào bằng đúng đường ghi đè của thẻ "Ai nói câu này".

Project SQLite tối thiểu trong thư mục tạm - chỉ các bảng/cột mà tab và `speaker_target` đọc.
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from abook.webui.casting_review import casting_chapter, casting_chapters


def make_book(root: Path, *, cast: bool = True) -> Path:
    project = root / "sach"
    project.mkdir()
    (project / "book_settings.json").write_text(json.dumps({"voices": {"first_person_identity": "LUCIEN"}}),
                                                encoding="utf-8")
    db = sqlite3.connect(project / "project.sqlite3")
    db.executescript(
        """
        CREATE TABLE chapters (id INTEGER PRIMARY KEY, chapter_index INTEGER, title TEXT);
        CREATE TABLE segments (id INTEGER PRIMARY KEY, stable_id TEXT, chapter_id INTEGER, seq INTEGER,
                               paragraph_index INTEGER, text TEXT, kind TEXT, speaker TEXT, voice_profile_id INTEGER,
                               canonical_character_id INTEGER, status TEXT, wav_path TEXT, text_sha256 TEXT, gender TEXT);
        CREATE TABLE characters (id INTEGER PRIMARY KEY, canonical_name TEXT, display_name TEXT, gender TEXT,
                                 locked INTEGER, age TEXT);
        """
    )
    db.executemany("INSERT INTO chapters VALUES (?, ?, ?)", [(1, 1, "001"), (2, 2, "002"), (3, 3, "003")])
    db.executemany("INSERT INTO characters (id, canonical_name, display_name, gender) VALUES (?,?,?,?)", [
        (1, "LUCIEN", "Lucien", "male"),
        (2, "HEIDI", "Heidi", "female"),
        (3, "RHINE", "Rhine", "male"),
        (4, "NARRATOR", "Người kể", "male"),
        (5, "NPC_LOCAL::C00001::R1::NGƯỜI GÁC", "NPC người gác", "male"),
        (6, "NPC_LOCAL::C00002::R2::BÀ BÁN HÀNG", "NPC bà bán hàng", "female"),
        (7, "ANONYMOUS_MALE", "Vô danh nam", "male"),
    ])
    rows = [
        # id, stable, chapter, seq, paragraph, text, kind, speaker, voice, character, wav
        (1, "a", 1, 0, 0, "Chương 1 - Mở đầu", "narration", "NARRATOR", 1, 4, "chunks/1.wav"),
        (2, "b", 1, 1, 1, "“Đi thôi.”", "dialogue", "LUCIEN", 2, 1, "chunks/2.wav"),
        (3, "c", 1, 2, 2, "“Heidi, đợi đã!”", "dialogue", "HEIDI", 3, 2, None),
        (4, "d", 1, 3, 3, "“Tớ đợi mà.”", "dialogue", "HEIDI", 3, 2, None),
        (5, "e", 1, 4, 4, "“Ai đó?”", "dialogue", "NPC_LOCAL::c00001::r1::người gác", 5, 5, None),
        (6, "f", 1, 5, 5, "Lucien nhìn quanh.", "narration", "NARRATOR", 1, 4, None),
        (7, "g", 1, 6, 5, "Mình lạc rồi sao?", "thought", "LUCIEN", 2, 1, None),
        (8, "h", 1, 7, 6, "“Là tôi.”", "dialogue", "LUCIEN", 2, 1, None),
        (9, "i", 2, 0, 0, "Chương 2", "narration", "NARRATOR", 1, 4, None),
        (10, "j", 2, 1, 1, "“Chào.”", "dialogue", "RHINE", 6, 3, None),
        (11, "k", 2, 2, 2, "“Mua gì?”", "dialogue", "NPC_LOCAL::c00002::r2::bà bán hàng", 7, 6, None),
        (12, "l", 2, 3, 3, "“Hỏi đường.”", "dialogue", "UNKNOWN", 8, 7, None),
    ]
    db.executemany(
        "INSERT INTO segments (id, stable_id, chapter_id, seq, paragraph_index, text, kind, speaker, voice_profile_id,"
        " canonical_character_id, wav_path, status) VALUES (?,?,?,?,?,?,?,?,?,?,?, 'verified')",
        rows,
    )
    db.execute("UPDATE segments SET text_sha256='sha-' || stable_id")
    if not cast:
        db.execute("UPDATE segments SET voice_profile_id = NULL")
    db.commit()
    db.close()
    return project


def test_a_chapter_reads_as_a_script_with_who_says_each_line(tmp_path: Path) -> None:
    """Mọi câu theo thứ tự, người nói đọc được; chỉ lời thoại và nội tâm đổi được người nói. Chọn nhanh là người nói TRONG
    chương (kể cả vai phụ của cảnh này, nhiều câu trước); ô tìm là người có tên khác của cuốn, không có vai phụ cảnh khác."""
    started = time.time()
    project = make_book(tmp_path)
    view = casting_chapter(project, 1)
    assert view is not None
    lines = view["lines"]
    assert [line["stableId"] for line in lines] == list("abcdefgh")
    assert [line["editable"] for line in lines] == [False, True, True, True, True, False, True, True]
    assert lines[0]["label"] == "Người kể" and lines[4]["label"] == "người gác" and lines[6]["kind"] == "thought"
    assert lines[1]["hasAudio"] and not lines[2]["hasAudio"]
    assert lines[5]["paragraph"] == lines[6]["paragraph"] == 5, "câu kể và câu nghĩ cùng một đoạn văn"
    assert [person["label"] for person in view["cast"]] == ["Lucien", "Heidi", "người gác"]
    assert view["cast"][0]["lines"] == 3, "câu nghĩ cũng là lời của Lucien"
    assert [person["label"] for person in view["others"]] == ["Rhine"], "bà bán hàng là vai phụ của chương 2"
    assert view["firstPerson"] == {"value": "LUCIEN", "label": "Lucien", "chip": "LUCIEN"}
    assert view["previous"] is None and view["next"] == 2 and view["castReady"] is True
    assert casting_chapter(project, 99) is None
    assert time.time() - started < 5


def test_the_script_marks_where_the_machine_doubts_and_suggests_someone(tmp_path: Path) -> None:
    """Cùng tín hiệu với hộp Việc cần duyệt, gắn thẳng lên câu: hai câu liền nhau cùng người (gợi ý: người khác vừa nói trước
    cặp ấy), lời gọi chính người nói."""
    project = make_book(tmp_path)
    hints = {line["stableId"]: line["hint"] for line in casting_chapter(project, 1)["lines"] if line["hint"]}
    assert hints["d"]["kind"] == "turn" and hints["d"]["suggest"] == "LUCIEN", "Lucien vừa nói trước cặp Heidi-Heidi"
    assert hints["c"]["kind"] == "vocative" and "Heidi" in hints["c"]["note"]
    assert set(hints) == {"c", "d"}

    listing = {chapter["chapterId"]: chapter for chapter in casting_chapters(project)["chapters"]}
    assert listing[1]["hints"] == 2 and listing[2]["hints"] == 0
    assert (listing[1]["speech"], listing[1]["lines"], listing[1]["index"]) == (6, 8, 1)


def test_a_decision_shows_waiting_then_applied_and_a_refused_one_says_so(tmp_path: Path) -> None:
    """Yêu cầu của người nghe hiện ngay trên câu: "đang chờ" tới ranh giới chương, "đã áp" khi dây chuyền gán xong, "không
    áp được" khi dây chuyền sẽ từ chối (hỏi bằng đúng `speaker_target`). Câu đổi chữ thì yêu cầu tự rơi."""
    from abook.listener_overrides import UNNAMED, request_speakers

    project = make_book(tmp_path)
    request_speakers(project, [("d", "sha-d")], "LUCIEN", now=time.time())
    request_speakers(project, [("h", "sha-h")], "LUCIEN", now=time.time())  # giữ nguyên = người nghe xác nhận
    request_speakers(project, [("e", "sha-e")], "BÀ CHỦ", now=time.time())  # chưa từng nói: chưa có giọng
    request_speakers(project, [("c", "sha-cũ")], "LUCIEN", now=time.time())  # yêu cầu cho chữ cũ
    request_speakers(project, [("b", "sha-b")], UNNAMED, now=time.time())
    wishes = {line["stableId"]: line["wish"] for line in casting_chapter(project, 1)["lines"]}
    assert wishes["d"] == {"value": "LUCIEN", "label": "Lucien", "state": "pending"}
    assert wishes["h"]["state"] == "applied"
    assert wishes["e"]["state"] == "refused" and "chưa có giọng" in wishes["e"]["reason"]
    assert wishes["c"] is None
    assert wishes["b"] == {"value": UNNAMED, "label": "Vai phụ không tên", "state": "pending"}

    db = sqlite3.connect(project / "project.sqlite3")
    db.execute("UPDATE segments SET speaker='LUCIEN', canonical_character_id=1, voice_profile_id=2 WHERE stable_id='d'")
    db.commit()
    db.close()
    view = casting_chapter(project, 1)
    assert next(line for line in view["lines"] if line["stableId"] == "d")["wish"]["state"] == "applied"
    assert casting_chapters(project)["chapters"][0]["decided"] == 5


def test_a_new_person_the_listener_creates_waits_and_is_not_called_refused(tmp_path: Path) -> None:
    """Soát UX a25 T3: người nghe TẠO người nói mới - một câu ("Ai nói câu này" -> "Người khác…" có giới) hay cả nhóm câu
    (thẻ "hai cách viết một tên" -> "Không, là người khác", giới "unknown") - dây chuyền áp được (`speaker_target` với
    `new_gender`), nên Kịch bản phải hiện "đang chờ", không phải "không áp được... dây chuyền sẽ bỏ qua"."""
    from abook.listener_overrides import request_speakers

    project = make_book(tmp_path)
    request_speakers(project, [("e", "sha-e")], "BÀ CHỦ", now=time.time(), new_gender="female")
    request_speakers(project, [("c", "sha-c"), ("d", "sha-d")], "Glas", now=time.time(), new_gender="unknown")
    wishes = {line["stableId"]: line["wish"] for line in casting_chapter(project, 1)["lines"]}
    assert wishes["e"]["state"] == "pending" and "reason" not in wishes["e"]
    assert wishes["c"]["state"] == wishes["d"]["state"] == "pending"


def test_before_casting_nobody_can_be_chosen_yet(tmp_path: Path) -> None:
    """Chỉ người đã có giọng mới gán được; trước bước phân vai thì chưa ai có - tab nói rõ thay vì để nút bấm rồi hỏng."""
    project = make_book(tmp_path, cast=False)
    view = casting_chapter(project, 2)
    assert view["castReady"] is False and view["cast"] == [] and view["others"] == []
    assert view["previous"] == 1 and view["next"] is None
    assert casting_chapters(project)["castReady"] is False


def test_the_studio_serves_the_script_tab_locally_and_to_remote_devices(tmp_path: Path) -> None:
    from abook.webui.library import Preferences, book_id
    from abook.webui.listening import Listening
    from abook.webui.remote_studio import permitted
    from abook.webui.server import App, Server
    from tests.test_webui_listen_and_sync import FakeRunner, _request

    project = make_book(tmp_path)
    preferences = Preferences(tmp_path / "prefs" / "preferences.json")
    preferences.update({"libraryRoot": str(tmp_path)})
    app = App(preferences=preferences, runner=FakeRunner(), token="t", listening=Listening(tmp_path / "prefs" / "l.json"))
    server = Server(app, port=0).start()
    headers = {"X-Ebook-Token": "t"}
    base = f"/api/books/{book_id(project)}/casting"
    try:
        status, data, _ = _request(server.port, "GET", base, headers=headers)
        assert status == 200 and [chapter["chapterId"] for chapter in json.loads(data)["chapters"]] == [1, 2]
        status, data, _ = _request(server.port, "GET", base + "/2", headers=headers)
        lines = json.loads(data)["lines"]
        assert status == 200 and lines[1]["label"] == "Rhine" and lines[1]["current"] == "RHINE"
        assert (lines[3]["label"], lines[3]["current"]) == ("Vai phụ không tên", "UNNAMED"), "xác nhận nhóm vô danh"
        status, _, _ = _request(server.port, "GET", base + "/42", headers=headers)
        assert status == 404
    finally:
        server.stop()
    assert permitted("GET", base) and permitted("GET", base + "/2") and not permitted("POST", base + "/2")


def test_the_narrator_of_each_chapter_points_at_their_chip(tmp_path: Path) -> None:
    """Người kể "tôi" theo TỪNG chương (first_person_chapters đè cả cuốn; rỗng = chương kể ngôi ba) và chip của người ấy
    trong chương - tab Kịch bản mời soát câu gán cho người kể, loại câu máy nhầm nhiều nhất (ANALYSIS_RESEARCH 30-09)."""
    project = make_book(tmp_path)
    settings = {"voices": {"first_person_identity": "Lucien", "first_person_chapters": {"1": "heidi"}}}
    (project / "book_settings.json").write_text(json.dumps(settings), encoding="utf-8")
    assert casting_chapter(project, 1)["firstPerson"]["chip"] == "HEIDI", "chương 1 người kể là Heidi, gõ thường vẫn khớp"
    settings["voices"]["first_person_chapters"] = {"1": ""}
    (project / "book_settings.json").write_text(json.dumps(settings), encoding="utf-8")
    assert casting_chapter(project, 1)["firstPerson"] is None, "chương kể ngôi ba: không có người kể"



def test_script_names_a_person_the_way_the_cast_tab_does(tmp_path: Path) -> None:
    """Soát UX a8, mục 20: Kịch bản và Nhân vật gọi một người bằng cùng kiểu chữ - tên hiển thị của sổ nhân vật."""
    project = make_book(tmp_path)
    db = sqlite3.connect(project / "project.sqlite3")
    db.execute("UPDATE characters SET display_name = 'Heidi Bé Nhỏ' WHERE canonical_name = 'HEIDI'")
    db.commit()
    db.close()
    view = casting_chapter(project, 1)
    assert view is not None
    assert {line["label"] for line in view["lines"] if line["speaker"] == "HEIDI"} == {"Heidi Bé Nhỏ"}
    assert "Heidi Bé Nhỏ" in [person["label"] for person in view["cast"]]
    # Vai phụ cục bộ vẫn theo tên trong câu, không theo "NPC ..." của sổ.
    assert next(line for line in view["lines"] if line["stableId"] == "e")["label"] == "người gác"


def test_the_script_marks_the_lines_the_model_is_unsure_of_with_the_inbox_budget(tmp_path: Path) -> None:
    """Soát UX a13 #2: hộp việc hỏi câu p_first thấp (20% câu có số đo, cùng hàm `unsure_speaker_lines`), tab Kịch bản phải
    đánh dấu cùng câu ấy - mở chương nào cũng ra cùng ngân sách của cả cuốn."""
    project = make_book(tmp_path)
    folder = project / "analysis_logprobs"
    folder.mkdir()
    spoken = {"b": "LUCIEN", "c": "HEIDI", "d": "HEIDI", "e": "NPC_LOCAL::c00001::r1::người gác", "g": "LUCIEN", "h": "LUCIEN",
              "j": "RHINE", "k": "NPC_LOCAL::c00002::r2::bà bán hàng", "l": "UNKNOWN"}
    low = {"h": 0.25, "j": 0.4}
    rows = [{"chapter": 1, "seq": 0, "stable_id": key, "kind": "dialogue", "speaker": who, "p_first": low.get(key, 0.99),
             "p_seq": 0.9, "margin": 0.1, "alts": [], "ntok": 1, "p_end": 0.99} for key, who in spoken.items()]
    (folder / "00001.jsonl").write_bytes("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows).encode("utf-8"))
    one = {line["stableId"]: line["hint"] for line in casting_chapter(project, 1)["lines"] if line["hint"]}
    assert one["h"]["kind"] == "unsure" and "25%" in one["h"]["note"] and "Lucien" in one["h"]["note"]
    assert set(one) == {"c", "d", "h"}, "9 câu có số đo x 20% = 1 chỗ: chỉ câu thấp nhất, dù câu 'j' cũng dưới ngưỡng"
    assert not any(line["hint"] for line in casting_chapter(project, 2)["lines"]), "'j' vượt ngân sách của cả cuốn"
    listing = {chapter["chapterId"]: chapter for chapter in casting_chapters(project)["chapters"]}
    assert listing[1]["hints"] == 3 and listing[2]["hints"] == 0


def test_a_line_waiting_for_a_retake_says_so_until_the_pipeline_has_done_it(tmp_path: Path) -> None:
    """Soát UX a23 B11: Kịch bản có "Thu lại câu này" - câu đã xin thu lại hiện "chờ" tới khi dây chuyền thu (listener_retake_at
    đuổi kịp), câu đổi chữ thì yêu cầu rơi; bản của sách chưa nâng cấp (không có cột) vẫn hiện."""
    from abook.listener_overrides import request_retake

    project = make_book(tmp_path)
    request_retake(project, "b", "sha-b", now=100.0)
    request_retake(project, "c", "sha-cũ", now=100.0)  # câu đã đổi chữ từ lúc xin
    waiting = {line["stableId"]: line["retake"] for line in casting_chapter(project, 1)["lines"]}
    assert waiting["b"] == "pending" and waiting["c"] is None and waiting["d"] is None

    db = sqlite3.connect(project / "project.sqlite3")
    db.execute("ALTER TABLE segments ADD COLUMN listener_retake_at REAL NOT NULL DEFAULT 0")
    db.execute("UPDATE segments SET listener_retake_at = 50 WHERE stable_id = 'b'")
    db.commit()
    assert casting_chapter(project, 1)["lines"][1]["retake"] == "pending", "lần thu lại gần nhất cũ hơn yêu cầu"
    db.execute("UPDATE segments SET listener_retake_at = 100 WHERE stable_id = 'b'")
    db.commit()
    db.close()
    assert casting_chapter(project, 1)["lines"][1]["retake"] is None, "dây chuyền đã thu theo yêu cầu này"


def test_the_script_asks_for_a_retake_of_several_lines_in_one_click(tmp_path: Path) -> None:
    """Shift-chọn nhiều câu rồi "Thu lại": một lần bấm, một mốc (hộp Áp dụng đếm một thay đổi); đổi ý thì bỏ cả nhóm."""
    from abook.listener_overrides import read_overrides
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
    path = f"/api/books/{book_id(project)}/review"
    try:
        refs = [{"stableId": "b"}, {"stableId": "h"}]
        status, data, _ = _request(server.port, "POST", path, headers=headers, body={"verdict": "redo", "chapterId": 1, "lines": refs})
        assert status == 200
        retakes = read_overrides(project)["retakes"]
        assert sorted(retakes) == ["b", "h"] and retakes["b"]["requested_at"] == retakes["h"]["requested_at"]
        assert retakes["b"]["text_sha256"] == "sha-b"
        assert json.loads(data)["lines"] == 2
        status, _data, _ = _request(server.port, "POST", path, headers=headers, body={"verdict": None, "lines": refs})
        assert status == 200 and read_overrides(project)["retakes"] == {}
    finally:
        server.stop()


def test_two_windows_editing_one_line_tell_the_late_one_what_it_replaced(tmp_path: Path) -> None:
    """Soát UX a23 B19: cửa sổ B đã đổi người nói câu 'd' trong khi cửa sổ A còn thấy chưa ai đổi. A ghi đè thì được báo "câu này vừa được
    sửa ở nơi khác" (không chặn: lần ghi vẫn vào), và ô hỏi nhẹ `stamp` đổi để cửa sổ kia tự làm mới."""
    from abook.listener_overrides import read_overrides, request_speakers
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
    base = f"/api/books/{book_id(project)}"
    try:
        before = json.loads(_request(server.port, "GET", base + "/casting/stamp", headers=headers)[1])["stamp"]
        assert before == 0, "chưa ai sửa gì: chưa có overrides.json"
        request_speakers(project, [("d", "sha-d")], "LUCIEN", now=time.time())  # cửa sổ B
        after = json.loads(_request(server.port, "GET", base + "/casting/stamp", headers=headers)[1])["stamp"]
        assert after != before

        body = {"lines": [{"stableId": "d", "textSha256": "sha-d"}], "speaker": "HEIDI", "seen": {"d": ""}}  # cửa sổ A còn thấy cũ
        status, data, _ = _request(server.port, "POST", base + "/speaker", headers=headers, body=body)
        assert status == 200 and json.loads(data)["elsewhere"] == {"d": "LUCIEN"}
        assert read_overrides(project)["speakers"]["d"]["speaker"] == "HEIDI", "không chặn: lần ghi vẫn vào"

        body["seen"] = {"d": "HEIDI"}  # A đã thấy bản mới nhất
        status, data, _ = _request(server.port, "POST", base + "/speaker", headers=headers, body=body)
        assert status == 200 and json.loads(data)["elsewhere"] == {}
        body.pop("seen")  # khách cũ không gửi `seen`: không báo gì
        status, data, _ = _request(server.port, "POST", base + "/speaker", headers=headers, body=body)
        assert status == 200 and json.loads(data)["elsewhere"] == {}
    finally:
        server.stop()
