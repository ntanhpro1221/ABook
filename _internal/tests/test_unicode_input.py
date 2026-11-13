"""Canonical input must produce the same segments and stable identities."""
import unicodedata
import hashlib

from abook.readaloud import cache, names
from abook.text_processing import normalize_text, segment_chapter_text


def test_decomposed_chapters_produce_identical_segments_and_stable_ids():
    text = 'Mã bảng kiểm thử mang ba dấu mốc.\n\n“Chọn mẫu số bảy.”'
    decomposed = unicodedata.normalize("NFD", text)
    assert normalize_text(decomposed) == text
    assert segment_chapter_text(1, decomposed) == segment_chapter_text(1, text)


def test_removed_invisible_characters_do_not_leave_decomposed_accents():
    assert normalize_text("a\u200b\u0300") == "à"


def test_reader_does_not_serve_audio_cached_under_the_previous_reading_rules(tmp_path):
    text = "Tôi kiểm GPS."
    previous = hashlib.sha256(f"{names.RULE_VERSION}.18|edge|voice|{text}".encode()).hexdigest()
    store = cache.ClipCache(tmp_path)
    store.put(previous, b"old audio", "mp3", 100, [[0, 100]])
    assert store.get(previous) is not None
    assert store.get(cache.clip_key("edge", "voice", text)) is None
