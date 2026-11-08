"""Inference boundaries preserve phones and keep each source component together."""
import json
from pathlib import Path

import pytest

from abook.readaloud import japanese_delivery as delivery, vieneu_engine

CASES = json.loads((Path(__file__).parent / "fixtures/readaloud/japanese_delivery/cases.json").read_text(encoding="utf-8"))["cases"]


@pytest.mark.parametrize("case", CASES)
def test_shared_delivery_contract(case):
    marked = delivery.mark(case["text"], case["words"])
    assert marked == case["marked"]
    assert delivery.phonemes(marked, True, lambda value, final: case["calls"][value + "|" + str(int(final))]) == case["phonemes"]


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
    normalized = studio._get_normalizer().normalize(case["marked"], punc_norm=False)
    assert studio.phonemize_text_with_emotions(normalized) == vieneu_engine.phonemize([case["marked"]]) == case["phonemes"]


def test_automatic_groups_do_not_override_another_reading():
    chosen = delivery.groups(["Nopami", "Nakanori"], "ja")
    assert delivery.mark("Nô-pa-mi Na-ca-nô-ri", chosen) == "<en>Nô‿pa‿mi</en> <en>Na‿ca‿nô‿ri</en>"
    assert delivery.mark("cách-đọc-riêng", chosen) == "cách-đọc-riêng"
    assert delivery.groups(["Nopami"], "ko") == set()
    assert delivery.groups(["Nopami"], "ja", {"Nopami": "Nô pa mi"}) == set()


def test_studio_marks_only_exact_automatic_anchor_spans():
    from abook.readaloud.japanese_policy import NAMESPACE

    text = "Nô-pa-mi và Na-ca-nô-ri."
    automatic = dict(reading_namespace=NAMESPACE, source="rule_romanization", spoken_start=0, spoken_end=8, spoken_form="Nô-pa-mi")
    assert delivery.mark_anchors(text, [automatic]) == "<en>Nô‿pa‿mi</en> và Na-ca-nô-ri."
    assert delivery.mark_anchors(text, [{**automatic, "source": "listener_choice"}]) == text
    assert delivery.mark_anchors(text, [{**automatic, "spoken_end": 7}]) == text


def test_context_sensitive_conversion_keeps_the_original_stream():
    def plain(text, final):
        return "whole sentence." if final else "different fragment"

    assert delivery.phonemes("Tên <en>Nô‿pa‿mi</en>.", True, plain) == "whole sentence."


def test_delivery_code_is_in_the_quality_fingerprint():
    from abook.quality_policy import QUALITY_IMPLEMENTATION_FILES

    assert "readaloud/japanese_delivery.py" in QUALITY_IMPLEMENTATION_FILES


def test_a_name_after_a_comma_reaches_the_model_joined():
    pytest.importorskip("sea_g2p")
    marked = delivery.mark("Cậu đã về, Nô-pa-mi-na.", {"nô-pa-mi-na"})
    phones = vieneu_engine.phonemize([marked])
    name = phones.rsplit(", ", 1)[1]
    assert len(name.split()) == 1 and name.startswith("nˈopˌ") and name.count("ˈ") == 1
    assert "vˈe2," in phones
