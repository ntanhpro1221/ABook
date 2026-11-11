from __future__ import annotations

import json
from pathlib import Path

import pytest

from abook.analysis import _decomposed_name_pronunciation
from abook.asr import normalize_transcript, transcript_metrics
from abook.config import build_settings
from abook.database import ProjectDB
from abook.readaloud import english_policy, names, vieneu
from abook.studio_names import planned_reading
from abook.tts import TTSCoordinator

FIXTURE = Path(__file__).parent / "fixtures/readaloud/english_direct/cases.json"
CASES = json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"]


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["text"])
def test_shared_reading_contract(case):
    toks = case["text"].split()
    said = vieneu.spoken_tokens(toks, case["origin"], readings=case.get("readings"), direct_english=True)
    assert " ".join(said) == case["said"]
    _, units = vieneu.units(case["text"], 256, case["origin"], readings=case.get("readings"), direct_english=True)
    assert " ".join(piece for unit in units for piece in unit.pieces) == case["said"]


@pytest.mark.parametrize("word", ["to", "da", "cha", "in", "me", "an", "man", "ban", "thanh", "sang"])
def test_vietnamese_homographs_never_take_an_automatic_dictionary_reading(tmp_path, word):
    db = ProjectDB(tmp_path / "project.sqlite3")
    db.upsert_pronunciation(surface=word, normalized_surface=word, spoken_form="tu", confidence=1,
                            source="english_name_transliteration", locked=True)
    tts = TTSCoordinator(build_settings(), db, lambda _: None)
    text = f"Tôi ghi {word} lên bảng."
    spoken, anchors = tts.spoken_text_with_anchors({"text": text})
    assert spoken == text
    assert not anchors
    assert english_policy.reading(word, None) is None
    assert not _decomposed_name_pronunciation(f"{word.title()} Michael", "Tu Mai-cồ") or all(
        surface != word.title() for surface, _ in _decomposed_name_pronunciation(f"{word.title()} Michael", "Tu Mai-cồ")
    )


def test_vietnamese_dictionary_intersection_is_protected():
    homographs = [word for word in names.english_words() if english_policy.vietnamese(word)]
    assert len(homographs) > 100
    from abook.readaloud.abbreviations import standard_reading
    assert all(english_policy.reading(word, None) is None for word in homographs
               if standard_reading(word, [word], 0) is None)


def test_full_and_short_names_have_identical_components():
    for surface in ("Michael", "Michael Godswill", "Ferrell", "Ferrell Bartholomew"):
        assert planned_reading(surface, None, direct_english=True) == (surface, "keep_english")
    assert planned_reading("Tanaka", None, direct_english=True) is None
    assert planned_reading("Tanaka", "ja", direct_english=True) == ("Ta-na-ca", "rule_romanization")
    assert planned_reading("Haruto", "ja", direct_english=True) == planned_reading("Haruto", "ja")


def test_only_vieneu_gets_the_new_policy_and_cache_namespace():
    toks = "Tôi kiểm GPS và video.".split()
    assert vieneu.spoken_tokens(toks) == ["Tôi", "kiểm", "giê pê ét", "và", "vi-đê-ô."]
    assert vieneu.reading_tag("Tôi kiểm GPS.", None) == ""
    assert vieneu.reading_tag("Tôi kiểm GPS.", None, direct_english=True) == f"direct-en{english_policy.VERSION}+jp-fallback6"
    assert english_policy.PROVENANCE == "auto"
    assert english_policy.ACRONYMS >= {"UDF", "MIT", "GPS", "DNA", "ID"}


def test_studio_materializes_acronyms_without_consuming_markup(tmp_path):
    db = ProjectDB(tmp_path / "project.sqlite3")
    tts = TTSCoordinator(build_settings(), db, lambda _: None)
    text, anchors = tts.spoken_text_with_anchors({"text": "Tôi kiểm GPS và ID."})
    assert text == "Tôi kiểm <en>G P S</en> và <en>I D</en>."
    assert [text[a["spoken_start"]:a["spoken_end"]] for a in anchors] == ["<en>G P S</en>", "<en>I D</en>."]


def test_asr_excludes_frontend_controls_and_keeps_every_content_word():
    expected = "Tôi kiểm <en>G P S</en> hôm nay."
    assert normalize_transcript(expected) == normalize_transcript("Tôi kiểm G P S hôm nay.")
    assert transcript_metrics(expected, "Tôi kiểm G P S hôm nay.") == (1.0, 0.0)
    similarity, wer = transcript_metrics(expected, "Tôi kiểm G P S ngày mai.")
    assert similarity < 1 and wer > 0


def test_studio_keeps_other_engines_and_explicit_listener_readings(tmp_path, monkeypatch):
    db = ProjectDB(tmp_path / "project.sqlite3")
    tts = TTSCoordinator(build_settings(), db, lambda _: None)
    monkeypatch.setattr(tts, "_voice_profile_for_row", lambda _: {"engine": "zerotts"})
    assert tts.spoken_text({"text": "Tôi kiểm GPS.", "voice_profile_id": 1}) == "Tôi kiểm giê pê ét."
    db.upsert_pronunciation(surface="GPS", normalized_surface="gps", spoken_form="giê pê ét", confidence=1,
                            source="listener_choice", locked=True)
    tts.forget_pronunciations()
    monkeypatch.setattr(tts, "_voice_profile_for_row", lambda _: {"engine": "vieneu"})
    assert tts.spoken_text({"text": "Tôi kiểm GPS.", "voice_profile_id": 1}) == "Tôi kiểm giê pê ét."


def test_detector_uses_self_written_sentences():
    from scripts.audit_english_homographs import findings

    rows = [{"surface": "to", "spoken_form": "tu", "source": "analysis"},
            {"surface": "da", "spoken_form": "Đa", "source": "listener_choice"},
            {"surface": "Rachel", "spoken_form": "Rachel", "source": "keep_english"}]
    got = findings(rows, ["Loa to đặt cạnh hộp da.", "Bàn to có chân sắt."])
    assert [(r["surface"], r["occurrences"]) for r in got] == [("to", 2), ("da", 1)]
