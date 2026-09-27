"""Dòng thoại mở bằng gạch đầu dòng là một lượt nói MỚI; khoá "thoại nối tiếp cùng người nói" chỉ dành cho lời nói kéo
dài qua nhiều đoạn trong một cặp ngoặc chưa đóng.

Tắt đèn (Ngô Tất Tố), chương XX: quan Phủ hỏi, anh Dậu đáp, không lời dẫn nào ở giữa. Trước 28-09 host gán câu đáp cho
chính quan Phủ - phát lại đáp án ba chương thì 11 trên 112 câu thoại bị đè như thế.
"""
from __future__ import annotations

from typing import Any

from ebook_reader.analysis import _repair_continued_dialogue_speakers


def _run(lines: list[tuple[int, str, str]]) -> list[str]:
    group: list[dict[str, Any]] = []
    result: dict[str, dict[str, Any]] = {}
    for number, (paragraph, text, speaker) in enumerate(lines):
        stable_id = f"s{number}"
        group.append({"stable_id": stable_id, "chapter_id": 20, "paragraph_index": paragraph, "text": text})
        result[stable_id] = {"kind": "dialogue", "speaker": speaker, "gender": "male", "age": "adult",
                             "confidence": 0.9}
    _repair_continued_dialogue_speakers(group, result)
    return [result[row["stable_id"]]["speaker"] for row in group]


def test_an_answer_on_its_own_dash_line_keeps_its_speaker() -> None:
    assert _run([
        (27, "- Mày nộp rồi thì biên lai đâu?", "QUAN PHỦ"),
        (28, "- Bẩm lạy quan lớn, con không lấy giấy biên lai...", "DẬU"),
    ]) == ["QUAN PHỦ", "DẬU"]


def test_every_dash_is_a_turn_whatever_the_dash() -> None:
    assert _run([
        (1, "– Bác gái đã chạy được nốt số tiền sưu chưa?", "BÀ LÃO LÁNG GIỀNG"),
        (2, "— Thưa cụ chưa.", "DẬU"),
        (3, "-Hình như nó đã theo quan về phủ thì phải.", "CHỊ DẬU"),
    ]) == ["BÀ LÃO LÁNG GIỀNG", "DẬU", "CHỊ DẬU"]


def test_a_quote_left_open_across_paragraphs_still_chains() -> None:
    # Lời nói dài: ngoặc mở ở đoạn trước, chưa đóng, đoạn sau là phần tiếp theo của cùng người.
    assert _run([
        (5, "“Nghe này, ta chỉ nói một lần thôi.", "LUCIEN"),
        (6, "Ngày mai cả đoàn lên đường trước bình minh.”", "DOUGLAS"),
    ]) == ["LUCIEN", "LUCIEN"]
