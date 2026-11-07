from __future__ import annotations

import json
from pathlib import Path

import pytest

from abook.config import build_settings
from abook.database import ProjectDB
from abook.readaloud import english_policy, vieneu
from abook.readaloud.japanese_policy import NAMESPACE, POLICY, contextual_names, metadata, reading, syllables
from abook.romanization import romanized_reading_flags
from abook.studio_names import planned_reading, rule_reading
from abook.tts import TTSCoordinator

FIXTURE = Path(__file__).parent / "fixtures/readaloud/japanese_fallback/cases.json"
DATA = json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", DATA["cases"], ids=lambda c: c["token"])
def test_shared_japanese_fallback(case):
    found = romanized_reading_flags(case["token"], case["origin"])
    assert (found[0] if found else None) == case["reading"]
    assert list(found[1] if found else []) == case["flags"]
    assert " ".join(vieneu.spoken_tokens(case["text"].split(), case["origin"], direct_english=True)) == case["said"]
    assert metadata(case["token"]) == case["metadata"]


@pytest.mark.parametrize("short,full", DATA["conflicts"])
def test_machine_full_and_short_names_share_components(tmp_path, monkeypatch, short, full):
    db = ProjectDB(tmp_path / "project.sqlite3")
    # Deliberately conflicting automatic rows. These are self-written test data.
    for word, spoken in [(full, " ".join("Ki-gi" for _ in full.split())), (short, "Phư-mi")]:
        db.upsert_pronunciation(surface=word, normalized_surface=word.casefold(), spoken_form=spoken,
                                confidence=1, source="english_name_transliteration", locked=True)
    original = [dict(row) for row in db.list_pronunciations()]
    tts = TTSCoordinator(build_settings(), db, lambda _: None)
    monkeypatch.setattr(tts, "_origin_of_book", lambda: "ja")
    spoken, anchors = tts.spoken_text_with_anchors({"text": f"Tôi ghi {full}, rồi {short}."})
    expected = reading(short, "ja", contextual=True)
    assert expected is not None
    assert spoken.casefold().count(expected.casefold()) == 2
    assert all(a["source"] != "english_name_transliteration" for a in anchors)
    assert all(a["provenance"] == "auto" for a in anchors)
    assert all(a["reading_namespace"] == NAMESPACE for a in anchors)
    assert [dict(row) for row in db.list_pronunciations()] == original


def test_listener_component_and_phrase_override_machine_rows(tmp_path, monkeypatch):
    db = ProjectDB(tmp_path / "project.sqlite3")
    db.upsert_pronunciation(surface="Shinji Tanaka", normalized_surface="shinji tanaka", spoken_form="Sin-gi Ta-na-da",
                            confidence=1, source="english_name_transliteration", locked=True)
    db.upsert_pronunciation(surface="Tanaka", normalized_surface="tanaka", spoken_form="Ta-na-da",
                            confidence=1, source="listener_choice", locked=True)
    tts = TTSCoordinator(build_settings(), db, lambda _: None)
    monkeypatch.setattr(tts, "_origin_of_book", lambda: "ja")
    assert tts.spoken_text({"text": "Shinji Tanaka gặp Tanaka."}) == "Sin-gi Ta-na-da gặp Ta-na-da."
    db.set_listener_pronunciation(surface="Shinji Tanaka", normalized_surface="shinji tanaka", spoken_form="Sin-di Ta-na-ca",
                                  source="listener_choice")
    tts.forget_pronunciations()
    assert tts.spoken_text({"text": "Shinji Tanaka gặp Tanaka."}) == "Sin-di Ta-na-ca gặp Ta-na-da."


@pytest.mark.parametrize("origin", ["ja", None])
@pytest.mark.parametrize("surface", ["Shinji Tanaka", "Jin Nakata"])
def test_japanese_names_cannot_be_kept_as_western_names(surface, origin):
    assert planned_reading(surface, origin, direct_english=True)[1] == "rule_romanization"
    assert all(english_policy.reading(w, origin) is None for w in surface.split())


def test_general_evidence_and_short_homographs():
    assert planned_reading("Haruto", None, direct_english=True)[1] == "rule_romanization"
    assert english_policy.reading("Michael", None) == ("Michael", "keep_english")
    assert " ".join(vieneu.spoken_tokens("Jin Nakata đến.".split(), None, direct_english=True)) == "Gin Na-ca-ta đến."
    assert " ".join(vieneu.spoken_tokens("Jin, Nakata đến.".split(), None, direct_english=True)) == "Jin, Na-ca-ta đến."
    assert vieneu.spoken_tokens(["Tanaka"], None) == ["Tanaka"]
    assert " ".join(vieneu.spoken_tokens("Tanaka Abe đến.".split(), None, direct_english=True)) == "Ta-na-ca a-be đến."
    for word in ("Abe", "Jin", "Aya", "Rita", "Tina", "Mary", "Rachel", "Anime"):
        assert reading(word, None) is None
        assert reading(word, "ja") is None
    assert vieneu.spoken_tokens(["T-Tanaka"], "ja", direct_english=True) == ["Ta-ta-na-ca"]


def test_checkpoint_uses_component_rows_and_auto_provenance(monkeypatch):
    from test_studio_names import JAPANESE, _analyzer, _book, _stored

    db = _book(JAPANESE, *["Shinji Tanaka gặp Jin Nakata."] * 3)
    analyzer, sent = _analyzer(db, monkeypatch)
    analyzer.reconcile_name_pronunciations()
    stored = _stored(db)
    assert sent == []
    assert "Shinji Tanaka" not in stored and "Jin Nakata" not in stored
    for word in ["Shinji", "Tanaka", "Jin", "Nakata"]:
        assert stored[word] == (reading(word, "ja", contextual=True), "rule_romanization")


def test_long_vowels_remain_auto_without_name_lists():
    assert metadata("Ryuu") ["long_vowels"] == ["uu"]
    assert metadata("Ryō") ["long_vowels"] == ["ō"]
    assert metadata("Satou") ["long_vowels"] == ["ou"]
    for word in ("Aya", "Haruto", "Tanaka", "Yuuki Satou"):
        assert metadata(word)["provenance"] == "auto"
        assert set(metadata(word)) == {"provenance", "reading_namespace", "source_spelling", "long_vowels"}
    assert set(POLICY["fixed"]) == {"onigiri"}
    assert set(POLICY) <= {"version", "namespace", "provenance", "description", "choices", "long_vowels", "long_o", "vowels", "internal_vowels", "vowel", "simple", "allowed", "onsets", "geminate_coda", "fixed", "suffixes", "honorifics", "common", "emit", "vowel_pairs", "routing"}


@pytest.mark.parametrize("core,count", [("Tanaka", 3), ("Satou", 2), ("Yuuki", 2), ("Shinji", 2), ("Ryu", 1), ("Sappa", 2), ("English", 0), ("Nnka", 0), ("Kkaka", 0)])
def test_complete_phonotactic_parse(core, count):
    assert syllables(core) == count


@pytest.mark.parametrize("case", DATA["routing"])
def test_shared_context_routing(case):
    toks = case["text"].split()
    ctx = contextual_names(toks)
    from abook.readaloud.names import split_token
    import re

    actual = []
    for index, token in enumerate(toks):
        before, core, after = split_token(token)
        if not before[-1:].isdigit() and not re.match(r"^[-–]?\d", after) and reading(core, None, contextual=index in ctx):
            actual.append(index)
    assert actual == case["indices"]


def test_namespace_invalidates_vieneu_clips_even_without_origin():
    assert vieneu.reading_tag("Tôi ghi tên.", None, direct_english=True).endswith(NAMESPACE)
    assert NAMESPACE not in vieneu.reading_tag("Tôi ghi tên.", None)
