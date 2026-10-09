"""Dấu trang theo CÂU (đặt ở màn đọc): vị trí câu + ~60 chữ đầu câu, gộp theo câu, hoàn tác giữ nguyên, dấu cũ không có trường mới vẫn ổn."""
from __future__ import annotations

from pathlib import Path

from abook.webui.listening import BOOKMARK_QUOTE_CHARS, Listening, bookmark_quote, merge_states


def test_a_reader_bookmark_remembers_the_sentence_and_its_first_words(tmp_path: Path) -> None:
    listening = Listening(tmp_path / "listening.json")
    long_sentence = "Trời   đã sáng,\n" + "và sương còn phủ kín cánh đồng làng " * 5
    mark = listening.add_bookmark("b", 2, 0.0, "", index=7, quote=long_sentence)
    assert mark["index"] == 7 and len(mark["quote"]) <= BOOKMARK_QUOTE_CHARS + 1
    assert mark["quote"] == "Trời đã sáng, và sương còn phủ kín cánh đồng làng và sương…", "gộp khoảng trắng, cắt ở ranh giới từ"
    assert bookmark_quote("Câu ngắn.") == "Câu ngắn." and bookmark_quote(None) == ""
    assert listening.get("b")["bookmarks"][0]["index"] == 7


def test_the_same_sentence_is_one_bookmark_and_another_sentence_is_another(tmp_path: Path) -> None:
    listening = Listening(tmp_path / "listening.json")
    first = listening.add_bookmark("b", 2, 0.0, "", index=7, quote="Câu bảy.")
    again = listening.add_bookmark("b", 2, 0.0, "hay", index=7, quote="Câu bảy.")
    assert again["id"] == first["id"] and again["existing"] and again["note"] == "hay"
    near = listening.add_bookmark("b", 2, 0.0, "", index=8, quote="Câu tám.")
    assert near["id"] != first["id"], "không có audio thì mọi dấu đều ở giây 0 - không được gộp theo giờ"
    elsewhere = listening.add_bookmark("b", 3, 0.0, "", index=7, quote="Chương khác.")
    assert elsewhere["id"] not in (first["id"], near["id"])


def test_a_bookmark_from_the_player_has_no_sentence_and_still_merges_by_time(tmp_path: Path) -> None:
    listening = Listening(tmp_path / "listening.json")
    first = listening.add_bookmark("b", 3, 64.0)
    assert "index" not in first and "quote" not in first
    assert listening.add_bookmark("b", 3, 67.0)["id"] == first["id"]


def test_undo_of_a_delete_keeps_the_sentence_and_junk_is_dropped(tmp_path: Path) -> None:
    listening = Listening(tmp_path / "listening.json")
    mark = listening.add_bookmark("b", 2, 0.0, "", index=7, quote="Câu bảy.")
    listening.delete_bookmark("b", mark["id"])
    restored = listening.restore_bookmark("b", mark)
    assert (restored["index"], restored["quote"]) == (7, "Câu bảy.")
    plain = listening.restore_bookmark("b", {"id": "abcdef012345", "chapterId": 1, "seconds": 3, "index": True, "quote": 5})
    assert "index" not in plain and "quote" not in plain


def test_old_bookmarks_without_the_new_fields_survive_a_merge(tmp_path: Path) -> None:
    ours = {"chapters": {}, "bookmarks": [{"id": "a1", "chapterId": 1, "seconds": 5.0, "note": "", "at": 10}]}
    theirs = {"chapters": {}, "bookmarks": [{"id": "b2", "chapterId": 2, "seconds": 0.0, "note": "", "at": 20, "index": 4, "quote": "Câu bốn."}]}
    merged = merge_states(ours, theirs)
    assert [(mark["id"], mark.get("index")) for mark in merged["bookmarks"]] == [("a1", None), ("b2", 4)]
