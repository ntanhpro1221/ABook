"""Authored number/unit contexts: occurrence rulings survive both real frontends."""
import json
from pathlib import Path

import pytest

from abook.readaloud import phoneme_policy as pp, vieneu, vieneu_engine
from abook.readaloud.studio_tn import studio_tn
from abook.tts import keep_vieneu_final_mark

CASES = json.loads((Path(__file__).parent / "fixtures/readaloud/normalized_occurrences/cases.json").read_text("utf8"))
VI = {"ben": "bˈɛn", "can": "kˈaːn", "an": "ˈaːn", "ten": "t̪ˈɛn"}


@pytest.fixture
def frontend(monkeypatch):
    import vieneu_utils.phonemize_text as pt
    for name in ("punc_norm", "_phonemize_cached", "_abook_keeps_final_mark"):
        monkeypatch.setattr(pt, name, getattr(pt, name, False), raising=False)
    keep_vieneu_final_mark()
    return pt


def check_phones(phones, case):
    words = [w.rstrip(".,!?") for w in phones.split()]
    assert words.count(VI[case["word"]]) == case["count"], phones
    if "english" in case:
        english = vieneu_engine._sea().g2p.convert(f'<en>{case["english"]}</en>').strip()
        assert words.count(english) == 1, phones


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
@pytest.mark.parametrize("route", ["studio", "reader"])
def test_normalized_occurrences(case, route, frontend):
    rulings = pp.Rulings(names=set(case["names"]))
    with pp.book_rulings(rulings):
        if route == "studio":
            spoken, _ = studio_tn(case["text"], case.get("origin"), True, direct_english=True)
            with pp.sentence_case(spoken, case["text"], rulings):
                if case["id"].startswith("tag-"):
                    assert "<en>C P U</en>" in spoken
                chunks = frontend.normalize_to_chunks_v3_with_gaps(spoken)[0]
                phones = " ".join(frontend.phonemize_text_with_emotions(c) for c in chunks)
            shown, units = vieneu.units(case["text"], 256, case.get("origin"), direct_english=True)
            reader = " ".join(vieneu_engine.phonemize(u.pieces, source=u.text(shown), rulings=rulings) for u in units)
            assert phones == reader
        else:
            shown, units = vieneu.units(case["text"], 256, case.get("origin"), direct_english=True)
            if case["id"].startswith("tag-"):
                assert any("<en>C P U</en>" in piece for u in units for piece in u.pieces)
            phones = " ".join(vieneu_engine.phonemize(u.pieces, source=u.text(shown), rulings=rulings) for u in units)
    check_phones(phones, case)


@pytest.mark.parametrize("cue", [False, True])
def test_repeated_occurrences_across_chunks_and_cues(frontend, cue):
    # Same fragment on either side of an English occurrence; a cursor must
    # consume each occurrence once even after numbers expand into several words.
    source = "Can đi 12 km. " + "Mẹ cất 3 kg gạo, " * 24 + "I can not do it. Can đi 12 km."
    rulings = pp.Rulings(names={"can"})
    with pp.book_rulings(rulings):
        spoken, _ = studio_tn(source, None, True, direct_english=True)
    if cue:
        spoken = spoken.replace("Mẹ", "<|emotion_1|> Mẹ", 1)
    with pp.sentence_case(spoken, source, rulings):
        chunks = frontend.normalize_to_chunks_v3_with_gaps(spoken)[0]
        assert len(chunks) >= 2
        phones = " ".join(frontend.phonemize_text_with_emotions(c) for c in chunks)
    check_phones(phones, {"word": "can", "count": 2, "english": "can"})
    if cue:
        assert "<|emotion_1|>" in phones


def test_changed_normalization_context_is_rejected():
    def normalize(text):
        return "ben đi xa" if text == "Ben đi 12 km." else text.lower()

    raw = "bˈen rest rest rest."
    g2p = lambda word: "bˈɛnɜ" if word == "bén" else "bˈen"
    assert pp.restore_generated_syllables("Ben đi 12 km.", "ben đi 12 km.", raw, g2p,
                                         rulings=pp.Rulings(names={"ben"}), normalize=normalize) == raw


@pytest.mark.parametrize("cue", ["", "[chuckle]", "<|emotion_1|>"])
def test_boundary_preserves_multiword_english_with_the_same_roster_word(frontend, cue):
    spoken = f"Can đi 12 km. {cue} <en>I can do it</en>, Can đi 12 km."
    rulings = pp.Rulings(names={"can"})
    with pp.sentence_case(spoken, rulings=rulings):
        phones = frontend.phonemize_text_with_emotions(spoken)
    check_phones(phones, {"word": "can", "count": 2, "english": "can"})


def test_multitoken_english_span_does_not_shift_roster_positions():
    text = "<en>I can do it</en>, Can đi 12 km."
    assert pp.ruled_vietnamese_words(text, rulings=pp.Rulings(names={"can"})) == {4}
