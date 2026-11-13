"""Generated name syllables keep their Vietnamese phones after chunk/cue splits."""
import pytest

from abook.readaloud.phoneme_policy import sentence_case
from abook.readaloud.studio_tn import studio_tn
from abook.tts import keep_vieneu_final_mark


@pytest.fixture
def frontend(monkeypatch):
    import vieneu_utils.phonemize_text as pt
    for name in ("punc_norm", "_phonemize_cached", "_abook_keeps_final_mark"):
        monkeypatch.setattr(pt, name, getattr(pt, name, False), raising=False)
    keep_vieneu_final_mark()
    return pt


def test_name_phones_survive_two_chunks_of_a_long_line(frontend):
    source = "Tengu " + "mẹ về nhà, " * 40 + "Tengu."
    spoken, _ = studio_tn(source, "ja", True, direct_english=True)
    assert len(spoken) > 256
    with sentence_case(spoken, source):
        chunks = frontend.normalize_to_chunks_v3_with_gaps(spoken)[0]
        assert len(chunks) >= 2
        phones = " ".join(frontend.phonemize_text_with_emotions(c) for c in chunks)
    assert phones.count("t̪ˈɛn") == 2, phones
    assert "t̪ˈen" not in phones


def test_name_phones_survive_emotion_fragment_splitting(frontend):
    source = "Tengu [chuckle] Tengu."
    spoken, _ = studio_tn(source, "ja", True, direct_english=True)
    # Exercise the upstream cue splitter directly; production can supply already
    # resolved cues as well as text fragments to this boundary.
    spoken = spoken.replace("[chuckle]", "<|emotion_1|>")
    with sentence_case(spoken, source):
        phones = frontend.phonemize_text_with_emotions(spoken)
    assert "<|emotion_1|>" in phones
    assert phones.count("t̪ˈɛn") == 2, phones
