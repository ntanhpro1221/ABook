"""Canonical input must produce the same segments and stable identities."""
import unicodedata

from abook.text_processing import normalize_text, segment_chapter_text


def test_decomposed_chapters_produce_identical_segments_and_stable_ids():
    text = 'Mã bảng kiểm thử mang ba dấu mốc.\n\n“Chọn mẫu số bảy.”'
    decomposed = unicodedata.normalize("NFD", text)
    assert normalize_text(decomposed) == text
    assert segment_chapter_text(1, decomposed) == segment_chapter_text(1, text)


def test_removed_invisible_characters_do_not_leave_decomposed_accents():
    assert normalize_text("a\u200b\u0300") == "à"
