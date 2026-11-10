"""Missing source spaces change speech boundaries, never book text."""
from __future__ import annotations

import pytest
import json
from pathlib import Path

from abook.readaloud.studio_tn import reading_punctuation, studio_tn, studio_tn_tagged
from abook.readaloud.vieneu import spoken_tokens
from abook.tts import TTSCoordinator, plan_chunks
from abook.config import build_settings


@pytest.mark.parametrize("source, expected", [
    ("lại.Khoảnh", "lại. Khoảnh"),  # reported audit case
    ("Hello?What", "Hello? What"),
    ("Đúng!Được", "Đúng! Được"),
    ("nói,lại:Được;Rồi", "nói, lại: Được; Rồi"),
    ("3.Người", "3. Người"),
    ("xong?!Đúng", "xong?! Đúng"),
    ('xong.”“Đúng', 'xong.” “Đúng'),
    ("rồi...Khoảnh", "rồi...Khoảnh"),
    ("rồi…Senpai", "rồi…Senpai"),
    ('rồi…”Khoảnh', 'rồi…” Khoảnh'),
    ("3.5 1.234.567 3,5 12:30", "3.5 1.234.567 3,5 12:30"),
    ("https://example.com/a?x=yes,b=no", "https://example.com/a?x=yes,b=no"),
    ("www.example.com/a!b", "www.example.com/a!b"),
    ("HTTPS://Example.COM/a?x=Hi!Y", "HTTPS://Example.COM/a?x=Hi!Y"),
    ("Example.COM Example.Com sub.Example.VN", "Example.COM Example.Com sub.Example.VN"),
    ("a.b+tag@example.com", "a.b+tag@example.com"),
    ("example.com sub.example.org hello.world", "example.com sub.example.org hello.world"),
    ("T.P. U.S.A. v.v. v.v V.v.", "T.P. U.S.A. v.v. v.v V.v."),
    ("T.P.HCM", "T.P.HCM"),
    ("TP.HCM PGS.TS. A.B", "TP.HCM PGS.TS. A.B"),
    ("v.v2 build.v3", "v.v2 build.v3"),
    ("Tôi...tôi T...Tôi ừm…ừm", "Tôi...tôi T...Tôi ừm…ừm"),
    ("Đã. Có? Cách!", "Đã. Có? Cách!"),
    ("", ""),
])
def test_reading_spaces_and_lexical_exceptions(source, expected):
    actual, mapping = reading_punctuation(source)
    assert actual == expected
    assert reading_punctuation(actual)[0] == actual
    assert len(mapping) == len(source) + 1
    assert mapping == sorted(mapping)
    assert mapping[-1] == len(actual)
    for i, character in enumerate(source):
        assert actual[mapping[i]] == character


def test_reading_rules_see_both_words_and_mapping_follows_them():
    source = "lại.Khoảnh Chương IV:HP"
    said, mapping = studio_tn(source, None, True)
    assert said == "lại. Khoảnh Chương bốn: hát pê"
    assert said[mapping[source.index("Khoảnh")]:].startswith("Khoảnh")
    assert said[mapping[source.index("HP")]:].startswith("hát pê")
    assert source == "lại.Khoảnh Chương IV:HP"


def test_display_tokens_keep_their_count_and_listener_readings_win():
    source = ["lại.Khoảnh", "Chương", "IV:HP"]
    assert spoken_tokens(source) == ["lại. Khoảnh", "Chương", "bốn: hát pê"]
    assert spoken_tokens(["Hello?What"], readings={"Hello?What": "đọc riêng"}) == ["đọc-riêng"]
    assert source == ["lại.Khoảnh", "Chương", "IV:HP"]


def test_protected_pronunciation_and_its_offsets_survive():
    source = "lại.Khoảnh x.Y"
    start = source.index("x.Y")
    tags = [frozenset({0}) if i >= start else frozenset() for i in range(len(source))]
    said, marks = studio_tn_tagged(source, tags, None, True)
    assert said == "lại. Khoảnh x.Y"
    assert "".join(c for c, mark in zip(said, marks) if mark) == "x.Y"


def test_chunk_planning_uses_sentence_boundaries_in_reading_string():
    reading = studio_tn("Một câu đủ dài rồi.Khoảnh khắc khác đến.", None, True)[0]
    assert plan_chunks(reading, 24) == [
        ("Một câu đủ dài rồi.", "."), ("Khoảnh khắc khác đến.", ".")]


def test_coordinator_preserves_hello_and_source_and_does_not_make_space_alias():
    class Reader:
        def list_pronunciations(self, minimum): return []
    coordinator = TTSCoordinator(build_settings(), Reader(), lambda _: None)
    coordinator._book_origin = (None,)
    source = '“Anh hỏi thế hả? Hello? What a day!”'
    row = {"text": source}
    assert coordinator.spoken_text(row) == source
    assert row["text"] == source
    text, anchors = coordinator.spoken_text_with_anchors({"text": "lại.Khoảnh"})
    assert text == "lại. Khoảnh"
    assert anchors == []


def test_phone_and_desktop_share_reading_boundary_cases():
    fixture = Path(__file__).parent / "fixtures/readaloud/reading_punctuation.json"
    for case in json.loads(fixture.read_text(encoding="utf-8")):
        source = case["source"]
        actual, mapping = reading_punctuation(source)
        assert actual == case["reading"], source
        assert reading_punctuation(actual)[0] == actual, source
        assert len(mapping) == len(source) + 1
        assert all(actual[mapping[i]] == c for i, c in enumerate(source))
        if "spoken" in case:
            assert studio_tn(source, None, True)[0] == case["spoken"], source
            assert " ".join(spoken_tokens(source.split())) == case["spoken"], source


def test_coordinator_does_not_reinterpret_a_url_after_symbols_remove_its_scheme():
    class Reader:
        def list_pronunciations(self, minimum): return []
    coordinator = TTSCoordinator(build_settings(), Reader(), lambda _: None)
    coordinator._book_origin = (None,)
    source = "3.5 12:30 https://example.com/a?x=1 a@example.com"
    assert coordinator.spoken_text({"text": source}) == "3.5 12:30 đường dẫn, a?x bằng 1 a@example.com"
