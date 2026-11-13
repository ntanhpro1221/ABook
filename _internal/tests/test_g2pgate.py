"""Frozen real-token text gate. Run with -s to print rates; no models or audio."""

import hashlib
import json
import os
from pathlib import Path

import pytest
from g2pgate_policy import canonical_options, canonical_reading, normalized_phones
from g2pgate_runner import compare, table

DATA = Path(__file__).parent / "data/g2pgate"
ROWS = json.loads((DATA / "tokens.json").read_text("utf8"))
EXPECTED = json.loads((DATA / "expected.json").read_text("utf8"))


def test_fixed_set_integrity():
    manifest = json.loads((DATA / "manifest.json").read_text("utf8"))
    assert len({r["token"] for r in ROWS}) >= 600
    assert {r["class"] for r in ROWS} == {
        "japanese",
        "korean",
        "chinese",
        "western",
        "loanword",
        "acronym",
        "mixed",
        "vietnamese",
    }
    assert all(set(r) == {"token", "class", "book_id_hash"} and len(r["book_id_hash"]) == 64 for r in ROWS)
    for name, digest in manifest["sha256"].items():
        assert hashlib.sha256((DATA / name).read_bytes().replace(b"\r\n", b"\n")).hexdigest() == digest
    assert len(json.loads((DATA / "calibration.json").read_text("utf8"))) == len(ROWS)


def test_policy_matches_frozen_oracle():
    for row in ROWS:
        key = row["class"] + ":" + row["token"]
        assert canonical_reading(row["token"], row["class"]) == EXPECTED[key]["reading"], key
        assert canonical_options(row["token"], row["class"]) == EXPECTED[key]["phones"], key


def test_app_g2p_matches_canonical():
    results = compare(ROWS, EXPECTED)
    print("\n" + table(results))
    failures = [r for r in results if r["kind"] != "match" and not r["ambiguity"]]
    assert not failures, "\n".join(
        f"{r['class']}:{r['token']} [{r['kind']}] {r['actual']} != {r['target']}" for r in failures
    )


def test_private_calibration_replay():
    # Context, hashes and sentence phones live only in the private Corpus. Never be
    # copied into the public checkout, including test failure messages.
    path = os.environ.get("G2PGATE_CALIBRATION_SOURCE")
    if not path:
        pytest.skip(
            "442 private-source replay requires G2PGATE_CALIBRATION_SOURCE; see data/g2pgate/README.md"
        )
    from abook.readaloud import shared_rulings, vieneu, vieneu_engine
    from abook.readaloud.phoneme_policy import Rulings, book_rulings

    clips = {c["id"]: c for c in json.loads(Path(path).read_text("utf8"))}
    context = Path(os.environ.get("G2PGATE_CALIBRATION_FIXTURE", "D:/Novels/ABook/Corpus/g2pgate/calibration_context.json"))
    if not context.is_file():
        pytest.skip("Private calibration context is absent; set G2PGATE_CALIBRATION_FIXTURE")
    fixture = json.loads(context.read_text("utf8"))
    assert set(clips) == {r["id"] for r in fixture}
    failures = []
    for row in fixture:
        source = clips[row["id"]]["title"]
        assert hashlib.sha256(source.encode()).hexdigest() == row["source_sha256"], row["id"]
        rulings = Rulings(names=set(row["vietnamese_names"]))
        readings = {**shared_rulings.name_readings(row["roster_origins"], row["origin"]), **row["readings"]}
        with book_rulings(rulings):
            shown, parts = vieneu.units(source, 256, row["origin"], readings=readings, direct_english=True)
            actual = " ".join(
                vieneu_engine.phonemize(p.pieces, source=p.text(shown), rulings=rulings) for p in parts
            )
        if not any(
            normalized_phones(actual) == normalized_phones(p) for p in row["canonical_phonemes"]
        ) and not row.get("ambiguity"):
            failures.append(row["id"])
    assert not failures, failures


@pytest.mark.parametrize(
    "token,lang", [("Jin", "ja"), ("Kappa", "ja"), ("Aoi", "ja"), ("Tengu", "ja"), ("Seol-Ah", "ko")]
)
def test_studio_matches_reader_for_typed_name(token, lang, monkeypatch):
    import vieneu_utils.phonemize_text as pt
    from g2pgate_runner import app_output

    from abook.readaloud import shared_rulings
    from abook.readaloud.phoneme_policy import sentence_case
    from abook.readaloud.studio_tn import studio_tn
    from abook.tts import keep_vieneu_final_mark

    for name in ("punc_norm", "_phonemize_cached"):
        monkeypatch.setattr(pt, name, getattr(pt, name))
    monkeypatch.setattr(
        pt, "_abook_keeps_final_mark", getattr(pt, "_abook_keeps_final_mark", False), raising=False
    )
    keep_vieneu_final_mark()
    readings = shared_rulings.name_readings({token: lang}, lang)
    said, _ = studio_tn(token, lang, True, readings=readings, direct_english=True)
    with sentence_case(said, token):
        chunks = pt.normalize_to_chunks_v3_with_gaps(said)[0]
        actual = " ".join(pt.phonemize_text_with_emotions(chunk) for chunk in chunks)
    assert normalized_phones(actual) == normalized_phones(
        app_output(token, "japanese" if lang == "ja" else "korean")
    )


def test_generated_syllable_does_not_change_another_occurrence():
    from abook.readaloud.phoneme_policy import restore_generated_syllables
    from abook.readaloud.vieneu_engine import _sea

    convert = _sea().g2p.convert
    given = "on lai on time."
    raw = convert(given)
    result = restore_generated_syllables("on-lai on time.", given, raw, convert)
    assert result.split()[0] == "ˈɔn"  # independently attested by dictionary ón, not a production probe
    assert result.split()[2:] == raw.split()[2:]


def test_vietnamese_roster_does_not_override_english_context():
    from abook.readaloud import vieneu
    from abook.readaloud.phoneme_policy import Rulings, book_rulings

    source = ["An", "apple"]
    plain = vieneu.spoken_tokens(source, direct_english=True)
    with book_rulings(Rulings(names={"an"})):
        assert vieneu.spoken_tokens(source, direct_english=True) == plain
