"""Automatic Japanese names reach VieNeu as ordinary Vietnamese syllables: one phonological word each, nothing joined."""
import json
from pathlib import Path

import pytest

from abook.readaloud import japanese_delivery as delivery, vieneu_engine

CASES = json.loads((Path(__file__).parent / "fixtures/readaloud/japanese_delivery/cases.json").read_text(encoding="utf-8"))["cases"]


@pytest.mark.parametrize("case", CASES)
def test_real_studio_and_readaloud_phonemizers_agree(case, monkeypatch):
    pytest.importorskip("sea_g2p")
    from abook.tts import keep_vieneu_final_mark

    pytest.importorskip("vieneu_utils.phonemize_text")
    import vieneu_utils.phonemize_text as studio

    for name in ("punc_norm", "_phonemize_cached"):
        monkeypatch.setattr(studio, name, getattr(studio, name))
    monkeypatch.setattr(studio, "_abook_keeps_final_mark", False, raising=False)
    keep_vieneu_final_mark()
    normalized = studio._get_normalizer().normalize(case["text"], punc_norm=False)
    assert studio.phonemize_text_with_emotions(normalized) == vieneu_engine.phonemize([case["text"]]) == case["phonemes"]


@pytest.mark.parametrize("case", [case for case in CASES if case["words"]])
def test_every_syllable_of_a_name_is_its_own_word(case):
    """Joined names ("nˈopˌaː2mˌi") lost syllables on both engines; the model gets "nˈo pˈaː mˈi" (level tone: `repair_level_tone`)."""
    words = case["phonemes"].split()
    assert not any(word.count("ˈ") + word.count("ˌ") > 1 for word in words)
    assert "<" not in case["phonemes"] and "‿" not in case["phonemes"]


def test_automatic_groups_do_not_override_another_reading():
    assert delivery.groups(["Nopami", "Nakanori"], "ja") == {"nô-pa-mi", "na-ca-nô-ri"}
    assert delivery.groups(["Nopami"], "ko") == set()
    assert delivery.groups(["Nopami"], "ja", {"Nopami": "Nô pa mi"}) == set()


def test_studio_owns_only_exact_automatic_anchor_spans():
    from abook.readaloud.japanese_policy import NAMESPACE

    text = "Nô-pa-mi và Na-ca-nô-ri."
    automatic = dict(reading_namespace=NAMESPACE, source="rule_romanization", spoken_start=0, spoken_end=8, spoken_form="Nô-pa-mi")
    assert delivery.anchor_spans(text, [automatic]) == [(0, 8)]
    assert delivery.anchor_spans(text, [{**automatic, "source": "listener_choice"}]) == []
    assert delivery.anchor_spans(text, [{**automatic, "spoken_end": 7}]) == []


def test_studio_gives_the_model_the_row_text_itself(monkeypatch):
    """No private envelope: the text Studio stores and checks is the text VieNeu reads."""
    import numpy as np

    from abook import tts
    from abook.readaloud.japanese_policy import NAMESPACE

    heard = []

    class Fake:
        def infer(self, text, **_):
            heard.append(text)
            return np.zeros(8, dtype=np.float32)

    engine = object.__new__(tts.VieNeuEngine)
    engine.tts, engine.settings = Fake(), {}
    monkeypatch.setattr(engine, "load", lambda: None)
    monkeypatch.setattr(engine, "voice_for_profile", lambda profile: "v")
    anchor = dict(reading_namespace=NAMESPACE, source="rule_romanization", spoken_start=0, spoken_end=8, spoken_form="Nô-pa-mi")
    row = {"text": "Nô-pa-mi đã về.", "speaker": "NARRATOR", "_materialized_spoken": ("Nô-pa-mi đã về.", [], [anchor])}
    engine.generate_one(row, None, 1, sampling={})
    assert heard == ["Nô-pa-mi đã về."]


def test_delivery_code_is_in_the_quality_fingerprint():
    from abook.quality_policy import QUALITY_IMPLEMENTATION_FILES

    assert "readaloud/japanese_delivery.py" in QUALITY_IMPLEMENTATION_FILES


def test_a_name_after_a_comma_reaches_the_model_split():
    pytest.importorskip("sea_g2p")
    phones = vieneu_engine.phonemize(["Cậu đã về, Nô-pa-mi-na."])
    name = phones.rsplit(", ", 1)[1]
    assert name == "nˈo pˈaː mˈi nˈaː."  # "pa" keeps its level tone (phoneme_policy.repair_level_tone), not sea-g2p's "pà"
    assert "vˈe2," in phones
