"""Bí danh người nghe đã xác nhận ("Thiên Biến Vạn Hóa" là Krai) đi theo cuốn sách (abook/aliases.py): thẻ "Một người
hai tên" ghi cấp TÊN, "Làm tiếp cuốn này" chép sang phần sau, và bước gom tên trước khi phân vai trỏ nhãn bí danh về người
ấy - câu của bí danh không có giọng thứ hai ở phần nào của cuốn."""
from __future__ import annotations

import json
from pathlib import Path

from abook import aliases, continuation
from abook.character_registry import _canonicalize_named_speakers
from abook.database import ProjectDB


def test_a_decision_is_kept_by_name_and_the_latest_wins(tmp_path: Path) -> None:
    assert aliases.add(tmp_path, "Thiên Biến Vạn Hóa", "KRAI ANDREY", now=1.0)
    assert not aliases.add(tmp_path, "THIÊN BIẾN VẠN HÓA", "krai andrey"), "cùng quyết định, viết khác hoa/thường"
    assert not aliases.add(tmp_path, "Krai", "KRAI"), "không trỏ một người về chính họ"
    assert aliases.load(tmp_path) == {"thiên biến vạn hóa": "KRAI ANDREY"}
    # Người nghe đổi ý theo chiều ngược: bản cũ bỏ, không thành vòng.
    assert aliases.add(tmp_path, "KRAI ANDREY", "Thiên Biến Vạn Hóa")
    assert aliases.load(tmp_path) == {"krai andrey": "Thiên Biến Vạn Hóa"}


def test_a_chain_resolves_to_the_person(tmp_path: Path) -> None:
    aliases.add(tmp_path, "Chủ nhân", "Thiên Biến Vạn Hóa")
    aliases.add(tmp_path, "Thiên Biến Vạn Hóa", "KRAI ANDREY")
    assert aliases.load(tmp_path) == {"chủ nhân": "KRAI ANDREY", "thiên biến vạn hóa": "KRAI ANDREY"}


def test_decomposed_marks_are_the_same_name(tmp_path: Path) -> None:
    import unicodedata

    aliases.add(tmp_path, unicodedata.normalize("NFD", "Thiên Biến Vạn Hóa"), "KRAI ANDREY")
    assert aliases.load(tmp_path).get(aliases.key("Thiên Biến Vạn Hóa")) == "KRAI ANDREY"


def _project(root: Path, speakers: list[str]) -> ProjectDB:
    root.mkdir(parents=True)
    source = root / "001.txt"
    source.write_text("Thiên Biến Vạn Hóa Krai Andrey bước vào. Tino chạy theo.", encoding="utf-8")
    db = ProjectDB(root / "project.sqlite3")
    db.initialize_book(title="Nageki", project_root=root, settings={}, settings_hash="s", input_manifest_hash="m")
    chapter = db.ensure_chapters([{"chapter_index": 1, "title": "001", "input_path": source, "input_sha256": "x",
                                   "input_size": 1, "output_mp3": root / "001.mp3"}])[0]
    db.replace_chapter_segments(chapter, [
        {"stable_id": f"s{seq}", "seq": seq, "paragraph_index": seq, "text": "…", "text_sha256": f"t{seq}",
         "kind_hint": "dialogue"}
        for seq in range(len(speakers))
    ])
    with db.transaction() as conn:
        for seq, speaker in enumerate(speakers):
            conn.execute("UPDATE segments SET kind='dialogue', speaker=? WHERE stable_id=?", (speaker, f"s{seq}"))
    return db


def test_the_alias_label_joins_the_person_before_casting(tmp_path: Path) -> None:
    db = _project(tmp_path / "phan2", ["KRAI ANDREY", "THIÊN BIẾN VẠN HÓA", "THIÊN BIẾN VẠN HÓA", "TINO"])
    aliases.add(db.path.parent, "Thiên Biến Vạn Hóa", "KRAI ANDREY")
    said: list[str] = []

    _canonicalize_named_speakers(db, said.append)

    assert [str(row["speaker"]) for row in db.list_segments()] == ["KRAI ANDREY"] * 3 + ["TINO"]
    assert any("người nghe đã gộp" in line for line in said)


def test_without_a_decision_nothing_changes(tmp_path: Path) -> None:
    db = _project(tmp_path / "phan1", ["KRAI ANDREY", "THIÊN BIẾN VẠN HÓA"])
    _canonicalize_named_speakers(db, lambda _message: None)
    assert [str(row["speaker"]) for row in db.list_segments()] == ["KRAI ANDREY", "THIÊN BIẾN VẠN HÓA"]


def test_the_next_part_inherits_the_decision(tmp_path: Path) -> None:
    first = _project(tmp_path / "phan1", ["KRAI ANDREY"])
    aliases.add(first.path.parent, "Thiên Biến Vạn Hóa", "KRAI ANDREY")
    second = ProjectDB(tmp_path / "phan2" / "project.sqlite3")
    second.initialize_book(title="Nageki · Phần 2", project_root=tmp_path / "phan2", settings={}, settings_hash="s",
                           input_manifest_hash="m2")

    assert continuation.carried_summary(first.path.parent)["aliases"] == 1
    report = continuation.seed(first.path.parent, second.path.parent)

    assert report["aliases"] == 1
    assert aliases.load(second.path.parent) == {"thiên biến vạn hóa": "KRAI ANDREY"}
    assert json.loads((second.path.parent / aliases.FILE_NAME).read_text(encoding="utf-8"))["version"] == 1


def test_merging_two_names_in_the_inbox_is_remembered_by_name(tmp_path: Path) -> None:
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
                                                     "speaker": "LUCIEN", "alias": "NATASHA"})
        assert status == 200 and data["alias"] is True
        # Sửa một câu bình thường (không từ thẻ "Một người hai tên") thì không ghi gì ở cấp tên.
        status, data = _call(server, "POST", route, {"lines": [{"stableId": "c1s2", "textSha256": "sha-c1s2"}],
                                                     "speaker": "NATASHA"})
        assert status == 200 and data["alias"] is False
    finally:
        server.stop()
    assert aliases.load(paths.root) == {"natasha": "LUCIEN"}
