"""Trích dẫn lồng trong lời thoại là lời của người nói câu ngoài (chủ sách 17-11).

"Hôm qua cậu còn nói rằng "hôm nay trời đẹp nhỉ" cơ mà." - cả câu, kể cả phần lồng, là MỘT lượt của MỘT người. Bộ tách
từng ghép dấu " theo thứ tự xen kẽ / dừng ở dấu đóng đầu tiên, nên phần lồng thành một đoạn lời kể riêng và được đọc bằng
giọng người kể (sách "Những gì em để lại cho tôi" có 28 câu như thế đã thu).

Bộ ca `tests/fixtures/nestquote/cases.json` (chữ tự viết) cũng đi vào `segmenter_cases.json` của nhạc theo cảnh, nơi bản
Kotlin `SceneSegmenter` được so với đúng các câu Python tách ra.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from abook.text_processing import segment_chapter_text

CASES = json.loads((Path(__file__).parent / "fixtures" / "nestquote" / "cases.json").read_text(encoding="utf-8"))["cases"]


@pytest.mark.parametrize("case", CASES, ids=[case["name"] for case in CASES])
def test_the_splitter_keeps_every_shared_case(case):
    rows = segment_chapter_text(1, case["text"])
    assert [[row["kind_hint"], row["text"]] for row in rows] == case["segments"]


def test_the_quoted_words_stay_inside_the_outer_line_in_every_form():
    markers = ("trời đẹp", "Tớ muốn đi biển", "Hội Thợ Săn")
    nested = [case for case in CASES if not case["name"].startswith("giu_") and any(marker in case["text"] for marker in markers)]
    assert len(nested) >= 20
    for case in nested:
        spoken = [text for kind, text in case["segments"] if any(marker in text for marker in markers)]
        assert spoken, case["name"]
        kinds = {kind for kind, text in case["segments"] if text in spoken}
        assert kinds <= {"dialogue", "thought"}, (case["name"], case["segments"])
        # Phần lồng không bị tách khỏi câu ngoài: mảnh chứa nó còn chữ của câu ngoài.
        assert all(len(text) > len("“hôm nay trời đẹp nhỉ”") for text in spoken), (case["name"], spoken)


def test_straight_quotes_pair_by_position_not_by_alternation():
    rows = segment_chapter_text(1, '"Cậu bảo "đi", rồi lại "ở"," Lan nói. "Thật là."')
    assert [(row["kind_hint"], row["text"]) for row in rows] == [
        ("dialogue", '"Cậu bảo "đi", rồi lại "ở","'),
        ("narration", "Lan nói."),
        ("dialogue", '"Thật là."'),
    ]


def test_a_missing_closer_still_recovers_when_a_quote_follows_in_narration():
    # “ giữa dòng chỉ là lồng khi phía sau có dấu đóng ngoặc ngoài; không có thì vẫn hồi phục như cũ.
    rows = segment_chapter_text(1, "“Nghe này.\n\nTôi nhìn cô ấy, cô ấy bảo “đi thôi” rồi quay đi.\n\nHết.")
    assert [row["kind_hint"] for row in rows] == ["dialogue", "narration", "dialogue", "narration", "narration"]


def test_a_pair_that_only_wraps_another_pair_is_not_a_quotation():
    rows = segment_chapter_text(1, '" "(Đừng có đùn việc cho tôi!!)" "')
    assert [row["kind_hint"] for row in rows] == ["narration"]
