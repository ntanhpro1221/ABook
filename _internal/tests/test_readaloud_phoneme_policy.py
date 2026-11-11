"""The shared phoneme boundary must retain every romaji syllable nucleus."""
import json
from pathlib import Path

import pytest

from abook.readaloud.phoneme_policy import repair_syllabic_gi, restore_unread_words
from abook.readaloud.vieneu_engine import phonemize

CASES = json.loads((Path(__file__).parent / "fixtures/readaloud/phoneme_delivery/cases.json").read_text("utf8"))["cases"]


@pytest.fixture(autouse=True)
def isolate_studio_frontend(monkeypatch):
    import vieneu_utils.phonemize_text as pt

    for name in ("punc_norm", "_phonemize_cached"):
        monkeypatch.setattr(pt, name, getattr(pt, name))
    monkeypatch.setattr(pt, "_abook_keeps_final_mark", getattr(pt, "_abook_keeps_final_mark", False), raising=False)


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["text"])
def test_shared_frontend_contract_including_studio_double_normalization(case):
    import vieneu_utils.phonemize_text as pt
    from abook.tts import keep_vieneu_final_mark

    keep_vieneu_final_mark()
    assert phonemize([case["text"]]) == case["phonemes"]
    chunks = pt.normalize_to_chunks_v3_with_gaps(case["text"])[0]
    assert len(chunks) == 1
    assert pt.phonemize_text_with_emotions(chunks[0]) == case["phonemes"]


@pytest.mark.parametrize("text", ["gi", "Ha-gi-me.", "Cây-gi Ki-ri-a.", "Gi-gi?", "a-gi, gi!"])
def test_syllabic_gi_keeps_its_vowel_in_both_frontends(text):
    import vieneu_utils.phonemize_text as pt
    from abook.tts import keep_vieneu_final_mark

    keep_vieneu_final_mark()
    mine = phonemize([text])
    studio = " ".join(pt.phonemize_text_with_emotions(chunk) for chunk in pt.normalize_to_chunks_v3_with_gaps(text)[0])
    assert mine == studio
    assert "zˈi" in mine
    assert repair_syllabic_gi(text, mine) == mine


@pytest.mark.parametrize("text,phones", [
    ("gì", "zˈi2."), ("giô", "zˈo."), ("gi", "zˈi."),
    ("gi", "z z."), ("gin", "z."), ("gi ghi", "z ɣˈi."),
])
def test_other_words_and_mismatched_spans_are_not_guessed(text, phones):
    assert repair_syllabic_gi(text, phones) == phones.replace("z ɣ", "zˈi ɣ")


@pytest.mark.parametrize("surface", ["Andou", "Haruto", "Hajime", "Tanaka"])
def test_a_locked_honorific_does_not_hide_the_unrendered_name(tmp_path, monkeypatch, surface):
    from abook.config import build_settings
    from abook.database import ProjectDB
    from abook.readaloud.japanese_policy import reading
    from abook.tts import TTSCoordinator

    db = ProjectDB(tmp_path / "project.sqlite3")
    db.upsert_pronunciation(surface="senpai", normalized_surface="senpai", spoken_form="xen-pai",
                            confidence=1, source="rule_romanization", locked=True)
    tts = TTSCoordinator(build_settings(), db, lambda _: None)
    monkeypatch.setattr(tts, "_origin_of_book", lambda: "ja")
    spoken, anchors = tts.spoken_text_with_anchors({"text": f"{surface}-senpai, em chào anh."})
    assert spoken == f"{reading(surface, 'ja')}-xen-pai, em chào anh."
    assert {a["surface"] for a in anchors} == {surface, "senpai"}
    for a in anchors:
        assert spoken[a["spoken_start"]:a["spoken_end"]] == a["spoken_form"]


def test_explicit_whole_name_and_embedded_subword_remain_protected():
    from abook.readaloud.studio_tn import studio_tn_tagged

    text = "Haruto-xen-pai-Miyagi."
    start, end = text.index("xen"), text.index("-Miyagi")
    tags = [frozenset({7}) if start <= i < end else frozenset() for i in range(len(text))]
    said, marked = studio_tn_tagged(text, tags, "ja", True, direct_english=True)
    assert said == "Ha-ru-tô-xen-pai-Mi-a-ghi."
    assert "".join(c for c, ids in zip(said, marked) if 7 in ids) == "xen-pai"
    protected, _ = studio_tn_tagged(text, [frozenset({7}) for _ in text], "ja", True, direct_english=True)
    assert protected == text
    embedded = "Haruto"
    same, _ = studio_tn_tagged(embedded, [frozenset({7}) if i < 2 else frozenset() for i in range(len(embedded))], "ja", True, direct_english=True)
    assert same == embedded


@pytest.mark.parametrize("source,spoken", [
    ("Naoki-kun.", "Na-o_-ki-cun."),
    ("Naoto đến.", "Na-o_-tô đến."),
    ("Kaori.", "Ca-o_-ri."),
])
def test_studio_retains_syllabic_o_through_the_first_normalizer(source, spoken):
    import vieneu_utils.phonemize_text as pt
    from abook.readaloud.studio_tn import studio_tn
    from abook.tts import keep_vieneu_final_mark

    keep_vieneu_final_mark()
    said, _ = studio_tn(source, "ja", True, direct_english=True)
    assert said == spoken
    chunks = pt.normalize_to_chunks_v3_with_gaps(said)[0]
    studio = pt.phonemize_text_with_emotions(chunks[0])
    assert studio == phonemize([spoken])
    assert "ˈɔ" in studio


@pytest.mark.parametrize("text,before,after", [
    ("hết pin rồi", "hˈeɜt̪ pˈɪn ɹˈo2j", "hˈeɜt̪ pˈin ɹˈo2j"),
    ("pin, it is over", "pˈɪn, ɪt ɪz ˈoʊvɚ", "pˈin, ɪt ɪz ˈoʊvɚ"),  # punctuation between: "it" is no neighbour
    ("pin it now", "pˈɪn ɪt nˈaʊ", "pˈɪn ɪt nˈaʊ"),  # an English word right after
    ("<en>the pin</en> rồi", "ðə pˈɪn ɹˈo2j", "ðə pˈɪn ɹˈo2j"),  # inside a span the reader marked English
    ("hết pin rồi", "hˈeɜt̪ pˈɪn", "hˈeɜt̪ pˈɪn"),  # words and phonemes do not line up: nothing is guessed
])
def test_a_vietnamese_word_with_only_an_english_sound_gets_the_sound_of_its_spelling(text, before, after):
    from abook.readaloud.vieneu_engine import _sea

    assert restore_unread_words(text, before, _sea().g2p.convert) == after
