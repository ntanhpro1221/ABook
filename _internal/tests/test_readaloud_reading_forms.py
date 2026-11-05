"""Nhịp và các vá số (docs/TEXT_NORMALIZATION.md tầng 5 + tầng 2): Nghe ngay (`vieneu.units`), Studio (`studio_tn`) và Edge (`spoken.layout`) đọc cùng một chuỗi.
Bộ ví dụ dùng chung với Kotlin (`ReadingFormsTest`): tests/fixtures/readaloud/spoken/reading_forms.json."""
from __future__ import annotations

import collections
import json
from pathlib import Path

import pytest

from abook.readaloud import spoken, supertonic, vieneu
from abook.readaloud.studio_tn import studio_tn

CASES = json.loads((Path(__file__).parent / "fixtures" / "readaloud" / "spoken" / "reading_forms.json").read_bytes().decode("utf-8"))["cases"]


def _said(text: str) -> str:
    _toks, units = vieneu.units(text, 256)
    return " ".join(piece for unit in units for piece in unit.pieces if piece)


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_every_voice_reads_the_shared_case_the_same_way(case: dict) -> None:
    assert _said(case["text"]) == case["said"]
    assert studio_tn(case["text"], None, True)[0] == case["said"], "Studio đọc như Nghe ngay"
    assert spoken.layout(case["text"], None)[0] == case["said"], "Edge nhận đúng chuỗi ấy"


def test_the_shared_cases_cover_every_class_with_cases_that_must_stay() -> None:
    classes = collections.Counter(case["id"].rsplit("-", 1)[0] for case in CASES)
    assert len(CASES) >= 80
    assert sum(count for name, count in classes.items() if name.endswith("_keep")) >= 30
    assert {"ellipsis_pause", "ellipsis_lead", "tilde_pause", "roman", "multiplier", "thousands"} <= set(classes)


def test_a_hesitation_inside_a_sentence_does_not_cut_the_sentence() -> None:
    """"Tôi..." trước chữ thường đọc thành dấu phẩy, nên VieNeu / Supertonic đọc cả câu một lượt (sea-g2p bỏ dấu phẩy cuối câu, câu cắt ở đó sẽ dính liền chữ sau)."""
    _toks, units = vieneu.units("Tôi... tôi không biết. Ừm… Vâng.", 256)
    assert [unit.pieces for unit in units] == [["Tôi, tôi không biết.", "Ừm…", "Vâng."]]
    _toks, parts = supertonic.cut("Tôi... tôi không biết gì về chuyện này cả, thật đấy, anh tin tôi đi mà. Ừm… Vâng.")
    assert all(not piece.endswith(",") for part in parts for piece in part.pieces)


def test_roman_numerals_from_forty_need_a_numbered_noun() -> None:
    assert [vieneu.vietnamese_number(n) for n in (40, 41, 44, 45, 99, 100, 101, 105, 110, 115, 121, 200, 305, 399)] == [
        "bốn mươi", "bốn mươi mốt", "bốn mươi bốn", "bốn mươi lăm", "chín mươi chín", "một trăm", "một trăm lẻ một", "một trăm lẻ năm",
        "một trăm mười", "một trăm mười lăm", "một trăm hai mươi mốt", "hai trăm", "ba trăm lẻ năm", "ba trăm chín mươi chín"]
    assert vieneu.numbered_by(["Vua", "Louis", "XL"], 2) is True
    assert vieneu.numbered_by(["Vua", "Louis", "XL"], 2, by_name=False) is False
