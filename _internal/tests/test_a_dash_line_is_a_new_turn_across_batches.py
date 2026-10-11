"""Thoại gạch đầu dòng là lượt nói mới cả khi sửa "vắt lô" (`character_registry._repair_cross_batch_dialogue_continuations`).

Bước ấy nối hai câu thoại liền đoạn thành MỘT lời khi đoạn trước chưa đóng ngoặc và đoạn sau chưa mở ngoặc - đúng cho lời
trong ngoặc kép bị cắt đoạn. Nhưng sách thoại bằng "-"/"–"/"—" không bao giờ mở ngoặc, nên cả cuộc thoại bị chép người nói
câu đầu. Đo 12-10 (NAMEFORM, cổng rộng b9lps1234, bản phát hành 0.4.54): một chương thoại gạch mất 70 câu đúng; dùng
`analysis.opens_a_new_turn` (phép thử bước sửa trong lô đã dùng) thì +53 câu, 55 chương còn lại không đổi câu nào.
"""
from __future__ import annotations

from pathlib import Path

from abook.character_registry import _repair_cross_batch_dialogue_continuations
from abook.database import ProjectDB


def _project(root: Path, lines: list[tuple[int, str, str, str, str]]) -> ProjectDB:
    """`lines`: (đoạn văn, loại, chữ, người nói, giới)."""
    root.mkdir(parents=True)
    source = root / "001.txt"
    source.write_bytes("\n".join(text for _p, _k, text, _s, _g in lines).encode("utf-8"))
    db = ProjectDB(root / "project.sqlite3")
    db.initialize_book(title="Thử", project_root=root, settings={}, settings_hash="s", input_manifest_hash="m")
    chapter = db.ensure_chapters([{"chapter_index": 1, "title": "001", "input_path": source, "input_sha256": "x",
                                   "input_size": 1, "output_mp3": root / "001.mp3"}])[0]
    db.replace_chapter_segments(chapter, [
        {"stable_id": f"s{seq}", "seq": seq, "paragraph_index": paragraph, "text": text, "text_sha256": f"t{seq}",
         "kind_hint": kind}
        for seq, (paragraph, kind, text, _speaker, _gender) in enumerate(lines)
    ])
    with db.transaction() as conn:
        for seq, (_paragraph, kind, _text, speaker, gender) in enumerate(lines):
            conn.execute("UPDATE segments SET kind=?, speaker=?, gender=? WHERE stable_id=?",
                         (kind, speaker, gender, f"s{seq}"))
    return db


def _repair(db: ProjectDB) -> list[str]:
    _repair_cross_batch_dialogue_continuations(db, lambda _message: None)
    return [str(row["speaker"]) for row in sorted(db.list_segments(), key=lambda row: int(row["seq"]))]


def test_a_dash_exchange_keeps_each_speaker(tmp_path: Path) -> None:
    db = _project(tmp_path / "b", [
        (1, "dialogue", "- Mai cậu có rảnh không", "AN", "male"),
        (2, "dialogue", "- Chắc là có", "BÌNH", "female"),
        (3, "dialogue", "– Vậy đi chợ với tớ nhé", "AN", "male"),
        (4, "dialogue", "— Ừ thì đi", "BÌNH", "female"),
    ])

    assert _repair(db) == ["AN", "BÌNH", "AN", "BÌNH"]


def test_a_quote_cut_across_paragraphs_is_still_one_speaker(tmp_path: Path) -> None:
    # Lời trong ngoặc kép bị cắt đoạn: đoạn sau là phần tiếp của cùng người, model lệch người ở lô sau.
    db = _project(tmp_path / "b", [
        (1, "dialogue", "“Nghe này, ta chỉ nói một lần thôi.", "AN", "male"),
        (2, "dialogue", "Ngày mai cả đoàn lên đường.”", "BÌNH", "female"),
    ])

    assert _repair(db) == ["AN", "AN"]


def test_an_opened_quote_or_a_closed_line_is_a_new_turn(tmp_path: Path) -> None:
    db = _project(tmp_path / "b", [
        (1, "dialogue", "“Đi thôi.”", "AN", "male"),
        (2, "dialogue", "“Ừ.”", "BÌNH", "female"),
        (3, "dialogue", "(Lại thế nữa rồi)", "AN", "male"),
    ])

    assert _repair(db) == ["AN", "BÌNH", "AN"]


def test_a_dash_line_after_an_unclosed_quote_is_a_new_turn(tmp_path: Path) -> None:
    db = _project(tmp_path / "b", [
        (1, "dialogue", "“Khoan đã, để tôi nói hết", "AN", "male"),
        (2, "dialogue", "- Không cần", "BÌNH", "female"),
    ])

    assert _repair(db) == ["AN", "BÌNH"]
