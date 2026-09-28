"""Lô phân tích thấy người nói ĐÃ gán của vài đoạn ngay trước nó - để nối lượt đối đáp qua ranh giới lô (dev/prev-speakers).

Lô chỉ 5 đoạn, đoạn đầu lô không có previous_text; đo 29-09 trên bộ LN (v3): chuỗi đối đáp vắt qua ranh giới lô sai 40% câu,
gọn trong một lô 27%. Không có đoạn thoại nào ngay trước thì prompt như cũ.
"""
from __future__ import annotations

from typing import Any

from ebook_reader.analysis import PREVIOUS_TURNS, OllamaBookAnalyzer
from ebook_reader.config import build_settings
from test_analysis_required import FakeDB


class ChapterDB(FakeDB):
    def __init__(self, rows: list[dict[str, Any]]):
        super().__init__()
        self.rows = rows

    def list_segments(self, chapter_id=None, statuses=None):  # noqa: ARG002 - cùng chữ ký ProjectDB
        return [row for row in self.rows if chapter_id is None or row["chapter_id"] == chapter_id]


def _row(seq: int, kind: str, speaker: str, text: str, status: str = "analyzed", chapter: int = 1) -> dict[str, Any]:
    return {"chapter_id": chapter, "seq": seq, "kind": kind, "speaker": speaker, "text": text, "status": status,
            "gender": "unknown"}


def _analyzer(rows: list[dict[str, Any]]) -> OllamaBookAnalyzer:
    return OllamaBookAnalyzer(build_settings(), ChapterDB(rows), lambda _message: None)


def test_the_last_turns_before_a_batch_name_their_speakers() -> None:
    rows = [
        _row(1, "narration", "NARRATOR", "Điện thoại reo."),
        _row(2, "dialogue", "KAKERU SORANO", "“A lô?”"),
        _row(3, "dialogue", "NPC_LOCAL::c00001::r9::mẹ Kakeru", "“Con không về thăm nhà à?”"),
        _row(4, "dialogue", "KAKERU SORANO", "“Con bận lắm.”"),
        _row(5, "narration", "NARRATOR", "Mẹ thở dài."),
        _row(6, "dialogue", "", "“Vậy là có bạn gái rồi sao.”", status="pending"),
    ]
    text = _analyzer(rows)._previous_turns([rows[5]])
    assert text.startswith("Các đoạn ngay trước")
    lines = text.strip().splitlines()[1:]
    assert len(lines) == PREVIOUS_TURNS == 4, "chỉ bốn đoạn gần nhất"
    assert lines[0] == "- [thoại · KAKERU SORANO] “A lô?”"
    assert lines[1] == "- [thoại · NPC_LOCAL:mẹ Kakeru] “Con không về thăm nhà à?”", "nhãn cục bộ ở dạng model viết"
    assert lines[3] == "- [kể] Mẹ thở dài."


def test_nothing_is_added_without_analysed_dialogue_just_before() -> None:
    first = [_row(1, "dialogue", "", "“Chào.”", status="pending")]
    assert _analyzer(first)._previous_turns(first) == "", "lô đầu chương"
    narration = [_row(1, "narration", "NARRATOR", "Trời mưa."), _row(2, "narration", "NARRATOR", "Gió thổi."),
                 _row(3, "dialogue", "", "“Ồ.”", status="pending")]
    assert _analyzer(narration)._previous_turns([narration[2]]) == "", "chỉ lời kể: prompt như cũ"
    pending = [_row(1, "dialogue", "LUCIEN", "“Đi.”", status="pending"), _row(2, "dialogue", "", "“Ừ.”", status="pending")]
    assert _analyzer(pending)._previous_turns([pending[1]]) == "", "đoạn trước chưa phân tích xong"
    other_chapter = [_row(1, "dialogue", "LUCIEN", "“Đi.”", chapter=1), _row(1, "dialogue", "", "“Ừ.”", status="pending", chapter=2)]
    assert _analyzer(other_chapter)._previous_turns([other_chapter[1]]) == "", "không nối qua chương"


def test_long_turns_are_shortened() -> None:
    rows = [_row(1, "dialogue", "LUCIEN", "“" + "a" * 300 + "”"), _row(2, "dialogue", "", "“Ừ.”", status="pending")]
    line = _analyzer(rows)._previous_turns([rows[1]]).strip().splitlines()[1]
    assert line.endswith("...") and len(line) < 200
