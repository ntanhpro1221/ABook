"""Edge (và giọng nào có `normalises_text`) nhận CÙNG chữ đem đọc với giọng trên máy (`vieneu.spoken_tokens`), mốc từng chữ vẫn một cặp cho mỗi chữ hiện.
Bộ ví dụ dùng chung với Kotlin (`SpokenTextTest`): tests/fixtures/readaloud/spoken/."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from abook.readaloud import azure, cache, fpt, google, readings, spoken, viettel
from abook.readaloud.mapping import Boundary, map_boundaries
from abook.readaloud.service import EdgeProvider, ReadAloud
from abook.webui.word_timing import tokens
from tests.test_readaloud import FakeProvider

FIXTURES = Path(__file__).parent / "fixtures" / "readaloud" / "spoken"
LAYOUT = json.loads((FIXTURES / "layout.json").read_bytes().decode("utf-8"))
WORDS = json.loads((FIXTURES / "words.json").read_bytes().decode("utf-8"))


class NormalisingProvider(FakeProvider):
    id = "fake"
    speaks_english = True
    normalises_text = True


@pytest.mark.parametrize("case", LAYOUT, ids=lambda case: case["id"])
def test_the_spoken_layout_matches_the_shared_cases(case: dict) -> None:
    said, spans = spoken.layout(case["text"], case["origin"], True, case.get("readings"))
    assert said == case["spoken"]
    assert [list(span) if span else None for span in spans] == case["spans"]
    assert len(spans) == len(tokens(case["text"])), "một khoảng cho mỗi chữ hiện"


@pytest.mark.parametrize("case", WORDS, ids=lambda case: case["note"][:40])
def test_the_words_come_back_to_the_shown_tokens(case: dict) -> None:
    said, spans = spoken.layout(case["text"], case["origin"], True, case.get("readings"))
    boundaries = [Boundary(item["text"], item["start"], item["end"]) for item in case["boundaries"]]
    words = spoken.expand_words(map_boundaries(said, boundaries, case["durationMs"]), spans)
    assert words == case["words"]
    assert len(words) == len(tokens(case["text"]))
    assert all(a[0] <= a[1] <= b[0] <= b[1] for a, b in zip(words, words[1:]))


def test_edge_is_the_only_provider_that_asks_for_the_normalised_text() -> None:
    assert EdgeProvider.normalises_text is True and EdgeProvider.speaks_english is True
    for module, name in ((azure, "AzureProvider"), (google, "GoogleProvider"), (fpt, "FptProvider"), (viettel, "ViettelProvider")):
        assert not getattr(getattr(module, name), "normalises_text", False), name


def test_a_normalising_voice_gets_the_text_the_local_voices_get_and_one_highlight_per_shown_word(tmp_path: Path) -> None:
    provider = NormalisingProvider()
    service = ReadAloud(tmp_path, [provider])
    text = "Haaah, HP 1,500 và Tanaka-san."
    clip = service.clip("fake:ngoc", text, origin="ja")
    assert provider.calls[-1] == ("ngoc", "ha… a, hát pê 1500 và Ta-na-ca-xan."), "chữ đã chuẩn hoá, nối bằng một dấu cách"
    words = clip["words"]
    assert len(words) == len(tokens(text))
    assert all(a[0] <= a[1] <= b[0] <= b[1] <= clip["duration_ms"] for a, b in zip(words, words[1:]))
    assert words[0][0] == 0 and words[0][1] > 300, "Haaah, = hai chữ đọc 'ha…' 'a,'"


def test_a_voice_without_the_flag_still_gets_the_raw_text(tmp_path: Path) -> None:
    provider = FakeProvider()
    ReadAloud(tmp_path, [provider]).clip("fake:ngoc", "Haaah, HP 1,500.", origin="ja")
    assert provider.calls[-1] == ("ngoc", "Haaah, HP 1,500.")


def test_the_clip_key_of_a_normalising_voice_is_not_the_raw_one_and_follows_the_origin(tmp_path: Path) -> None:
    text = "Otsuki-san hỏi về Okayama."
    raw, normalised = FakeProvider(), NormalisingProvider()
    service = ReadAloud(tmp_path, [normalised])
    ja, none = service.clip("fake:ngoc", text, origin="ja"), service.clip("fake:ngoc", text)
    assert ja["file"] != none["file"], "tên Nhật đọc khác thì khoá khác"
    assert ja["file"].startswith(cache.clip_key("fake", "ngoc", text, "ja+" + spoken.TAG))
    assert none["file"].startswith(cache.clip_key("fake", "ngoc", text, spoken.TAG))
    assert none["file"] != ReadAloud(tmp_path / "raw", [raw]).clip("fake:ngoc", text)["file"], "clip chữ thô cũ không bao giờ trúng đệm của chữ chuẩn hoá"
    assert len(normalised.calls) == 2


def test_a_book_reading_wins_over_the_names_and_a_shorter_one_leaves_an_empty_highlight(tmp_path: Path) -> None:
    provider = NormalisingProvider()
    service = ReadAloud(tmp_path, [provider])
    table = {"Hạ Vy": "Hạ"}
    clip = service.clip("fake:ngoc", "Hạ Vy cười.", readings=table)
    assert provider.calls[-1] == ("ngoc", "Hạ cười.")
    assert clip["words"][1] == [clip["words"][0][1], clip["words"][0][1]]
    assert clip["file"].startswith(cache.clip_key("fake", "ngoc", "Hạ Vy cười.", spoken.TAG + "+" + readings.tag("Hạ Vy cười.", table)))


def test_a_paragraph_that_normalises_to_nothing_is_read_as_written() -> None:
    said, spans = spoken.layout("*", None, True, None)
    assert said == "*" and spans == [(0, 0)]


def test_prepare_ahead_makes_the_same_clips_as_listening(tmp_path: Path) -> None:
    provider = NormalisingProvider()
    service = ReadAloud(tmp_path, [provider])
    listened = service.clip("fake:ngoc", "Grrr, đi thôi!")
    assert service.clip("fake:ngoc", "Grrr, đi thôi!", background=True)["file"] == listened["file"] and len(provider.calls) == 1
    assert provider.calls[0][1] == "gừ…, đi thôi!"
