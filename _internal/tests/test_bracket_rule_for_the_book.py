"""Quy ước 『』 của cả cuốn (abook/bracket_rule.py): lỗi 『』 phần lớn là quy ước riêng từng cuốn (TCF: lời kể; Yamiyo:
linh thể - đo 29-09) - người nghe chọn một lần ở thẻ 『』 với phạm vi "Cả cuốn", mọi câu 『』 của dự án về người ấy, và các
phần sau của cuốn tự áp trước bước phân vai."""
from __future__ import annotations

from pathlib import Path

from abook import bracket_rule, continuation
from abook.character_registry import _canonicalize_named_speakers
from abook.database import ProjectDB
from abook.webui.work_items import work_items
from tests.test_work_items import make_bracket_book


def test_the_card_offers_this_chapter_or_the_whole_book(tmp_path: Path) -> None:
    card = next(item for item in work_items(make_bracket_book(tmp_path))["items"] if item["kind"] == "bracket")
    assert card["scopeLabels"] == ["Chương này", "Cả cuốn"]
    assert [line["stableId"] for line in card["lines"]] == ["s1", "s3", "s4", "s5"]
    assert [line["stableId"] for line in card["allLines"]] == ["s1", "s3", "s4", "s5", "t1", "t2", "t3"], \
        "cả cuốn: mọi câu 『』, kể cả chương đã nhất quán"


def test_a_rule_is_kept_and_carried_once(tmp_path: Path) -> None:
    first, second = tmp_path / "phan1", tmp_path / "phan2"
    first.mkdir()
    second.mkdir()
    assert bracket_rule.save(first, "TỌA PHU ĐỒNG TỬ")
    assert not bracket_rule.save(first, "TỌA PHU ĐỒNG TỬ"), "cùng quyết định: không ghi lại"
    assert bracket_rule.carry(first, second) and bracket_rule.load(second) == "TỌA PHU ĐỒNG TỬ"
    bracket_rule.save(second, "NARRATOR")
    assert not bracket_rule.carry(first, second), "phần sau đã có quy ước riêng thì giữ"


def _project(root: Path, lines: list[tuple[str, str, str]]) -> ProjectDB:
    root.mkdir(parents=True)
    source = root / "001.txt"
    source.write_text("Tomobe và Hina ngủ. Linh thể nói trong đầu.", encoding="utf-8")
    db = ProjectDB(root / "project.sqlite3")
    db.initialize_book(title="Yamiyo", project_root=root, settings={}, settings_hash="s", input_manifest_hash="m")
    chapter = db.ensure_chapters([{"chapter_index": 1, "title": "001", "input_path": source, "input_sha256": "x",
                                   "input_size": 1, "output_mp3": root / "001.mp3"}])[0]
    db.replace_chapter_segments(chapter, [
        {"stable_id": f"s{seq}", "seq": seq, "paragraph_index": seq, "text": text, "text_sha256": f"t{seq}",
         "kind_hint": kind}
        for seq, (text, kind, _speaker) in enumerate(lines)
    ])
    with db.transaction() as conn:
        for seq, (_text, kind, speaker) in enumerate(lines):
            conn.execute("UPDATE segments SET kind=?, speaker=? WHERE stable_id=?", (kind, speaker, f"s{seq}"))
    return db


def test_the_book_rule_gives_every_bracketed_line_to_its_speaker_before_casting(tmp_path: Path) -> None:
    db = _project(tmp_path / "phan2", [
        ("『Chàng về rồi.』", "dialogue", "HINA"),
        (" 『Thiếp đợi mãi.』", "dialogue", "TOMOBE"),
        ("“Ừ.”", "dialogue", "TOMOBE"),
        ("『Hệ thống: nhiệm vụ mới.』", "narration", "NARRATOR"),
    ])
    bracket_rule.save(db.path.parent, "TỌA PHU ĐỒNG TỬ")
    said: list[str] = []

    _canonicalize_named_speakers(db, said.append)

    assert [str(row["speaker"]) for row in db.list_segments()] == \
        ["TỌA PHU ĐỒNG TỬ", "TỌA PHU ĐỒNG TỬ", "TOMOBE", "NARRATOR"], "lời thường và lời kể không bị đụng"
    assert any("quy ước người nghe chọn" in line for line in said)


def test_the_next_part_inherits_the_rule(tmp_path: Path) -> None:
    first = _project(tmp_path / "phan1", [("『Chàng về rồi.』", "dialogue", "TỌA PHU ĐỒNG TỬ")])
    bracket_rule.save(first.path.parent, "TỌA PHU ĐỒNG TỬ")
    second = ProjectDB(tmp_path / "phan2" / "project.sqlite3")
    second.initialize_book(title="Yamiyo · Phần 2", project_root=tmp_path / "phan2", settings={}, settings_hash="s",
                           input_manifest_hash="m2")

    assert continuation.carried_summary(first.path.parent)["bracket"] == "TỌA PHU ĐỒNG TỬ"
    assert continuation.seed(first.path.parent, second.path.parent)["bracket"] is True
    assert bracket_rule.load(second.path.parent) == "TỌA PHU ĐỒNG TỬ"


def test_choosing_the_whole_book_in_the_inbox_records_the_rule(tmp_path: Path) -> None:
    from abook.config import build_settings, save_settings
    from abook.webui.actions import FakeRunner
    from abook.webui.library import Preferences, book_id
    from abook.webui.listening import Listening
    from abook.webui.server import App, Server
    from tests.test_a_project_can_be_renamed_or_deleted import _call
    from tests.test_listener_speakers import _book

    paths, _db = _book(tmp_path)
    save_settings(paths.settings, build_settings())
    preferences = Preferences(tmp_path / "prefs" / "preferences.json")
    preferences.update({"libraryRoot": str(tmp_path)})
    app = App(preferences=preferences, runner=FakeRunner(), token="t", listening=Listening(tmp_path / "prefs" / "l.json"))
    server = Server(app, port=0).start()
    route = f"/api/books/{book_id(paths.root)}/speaker"
    try:
        status, data = _call(server, "POST", route, {"lines": [{"stableId": "c1s3", "textSha256": "sha-c1s3"}],
                                                     "speaker": "NATASHA"})
        assert status == 200 and data["alias"] is False and bracket_rule.load(paths.root) == "", "chỉ chương này"
        status, data = _call(server, "POST", route, {"lines": [{"stableId": "c1s3", "textSha256": "sha-c1s3"}],
                                                     "speaker": "NATASHA", "bracketRule": True})
        assert status == 200 and data["alias"] is True
    finally:
        server.stop()
    assert bracket_rule.load(paths.root) == "NATASHA"
