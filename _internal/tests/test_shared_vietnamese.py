"""Words in both sea-g2p dictionaries stay Vietnamese beside names and English words; the cases are shared with Kotlin."""
import json
from pathlib import Path

import pytest

from abook.readaloud import phoneme_policy
from abook.readaloud.phoneme_policy import capitalised, restore_vietnamese, sentence_case, vietnamese_shared

CASES = json.loads((Path(__file__).parent / "fixtures/readaloud/shared_vietnamese/cases.json").read_text("utf8"))["cases"]


def listed(text: str) -> list[str]:
    shared = phoneme_policy._shared()
    return [word for word, _, _ in phoneme_policy._shared_tokens(text, frozenset()) if word in shared.listed]


def test_the_kotlin_copy_is_the_same_table():
    import importlib.util

    path = Path(__file__).parents[1] / "scripts" / "build_shared_words.py"
    spec = importlib.util.spec_from_file_location("build_shared_words", path)
    build = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build)
    assert build.KOTLIN.read_text(encoding="utf-8") == build.kotlin(build.table_text())
    assert build.TABLE.stat().st_size <= 1_000_000  # the phone carries it too


def test_the_table_is_whole_and_integer():
    shared = phoneme_policy._shared()
    assert len(shared.classes) == 12 and set(shared.sentinels).isdisjoint(shared.listed) and shared.listed <= shared.shared
    for entry in shared.words.values():
        assert len(entry["l"]) == len(entry["r"]) == 12
        numbers = [entry["p"], entry["f"], *entry["l"], *entry["r"], *entry["L"].values(), *entry["R"].values()]
        assert all(type(number) is int for number in numbers)


@pytest.fixture
def studio(monkeypatch):
    import vieneu_utils.phonemize_text as pt
    from abook.tts import keep_vieneu_final_mark

    for name in ("punc_norm", "_phonemize_cached"):
        monkeypatch.setattr(pt, name, getattr(pt, name))
    monkeypatch.setattr(pt, "_abook_keeps_final_mark", getattr(pt, "_abook_keeps_final_mark", False), raising=False)
    keep_vieneu_final_mark()
    return pt


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["text"])
def test_the_sentence_decides_which_shared_words_are_vietnamese(case):
    words = listed(case["text"].lower())
    assert [words[i] for i in vietnamese_shared(case["text"].lower(), capitalised(case["text"]))] == case["claimed"]


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["text"])
def test_both_desktop_frontends_give_the_shared_phonemes(case, studio):
    from abook.readaloud.vieneu_engine import phonemize

    assert phonemize([case["text"]]) == case["phonemes"]
    with sentence_case(case["text"]):  # as VieNeuEngine.generate_one does around infer
        chunks = studio.normalize_to_chunks_v3_with_gaps(case["text"])[0]
        assert " ".join(studio.phonemize_text_with_emotions(chunk) for chunk in chunks) == case["phonemes"]


@pytest.mark.parametrize("case", [case for case in CASES if "sea" in case], ids=lambda case: case["text"])
def test_only_the_claimed_words_change_and_only_to_their_vietnamese_reading(case):
    from abook.readaloud.vieneu_engine import _sea

    g2p = _sea().g2p.convert
    before, after = case["sea"].split(), case["phonemes"].split()
    assert len(before) == len(after)
    readings = {phoneme_policy._reading(word, g2p) for word in case["claimed"]}
    for old, new in zip(before, after):
        if old != new:
            assert (new.rstrip(".,!?"), old.rstrip(".,!?")) in readings


def test_a_capital_inside_a_sentence_is_a_name_and_the_first_word_is_not():
    assert capitalised("Leo nhìn Do Cheol-ho. “Bay đi, Iron Man!” — Sang nhà Lucy?") == {"do", "cheol", "iron", "man", "lucy"}
    assert capitalised("<en>G M</en> nói Go.") == {"m", "go"}
    assert vietnamese_shared("leo lên xe đi.") == [0]
    assert vietnamese_shared("leo lên xe đi.", frozenset({"leo"})) == []


def test_the_remembered_case_ends_with_the_utterance():
    assert phoneme_policy.remembered_case() == frozenset()
    with sentence_case("Tháp chủ Leo Bright."):
        assert phoneme_policy.remembered_case() == {"leo", "bright"}
    assert phoneme_policy.remembered_case() == frozenset()


def fake(table):
    calls = []

    def g2p(text):
        calls.append(text)
        return table[text]

    return g2p, calls


READINGS = {"ạ to ạ": "A TO_VI A", "<en>to</en>": "TO_EN", "ạ nach ạ": "A N_VI A", "<en>nach</en>": "N_EN",
            "ạ sich ạ": "A S_VI A", "<en>sich</en>": "S_EN", "ạ trac ạ": "A T_VI A", "<en>trac</en>": "T_EN"}


def test_a_sentence_sea_already_reads_vietnamese_costs_no_second_pass(monkeypatch):
    monkeypatch.setattr(phoneme_policy, "_readings", {})
    g2p, calls = fake(READINGS)
    assert restore_vietnamese("con mèo to quá.", "K M TO_VI Q.", lambda: pytest.fail("no source needed"), g2p) == "K M TO_VI Q."
    assert calls == ["ạ to ạ", "<en>to</en>"]


def test_the_swap_is_dropped_when_anything_else_moves(monkeypatch):
    monkeypatch.setattr(phoneme_policy, "_readings", {})
    text = "con boss to quá."
    good, _ = fake({**READINGS, "con boss nach quá.": "K B N_EN Q."})
    assert restore_vietnamese(text, "K B TO_EN Q.", text, good) == "K B TO_VI Q."
    # every stand-in also changes a neighbour: keep sea-g2p's own answer
    moved, _ = fake({**READINGS, "con boss nach quá.": "K X N_EN Q.", "con boss sich quá.": "K X S_EN Q.", "con boss trac quá.": "K B T_VI Q. extra"})
    assert restore_vietnamese(text, "K B TO_EN Q.", text, moved) == "K B TO_EN Q."
    # the stand-in is a word of the sentence: the next one is used
    taken, calls = fake({**READINGS, "nach boss sich quá.": "N_VI B S_VI Q."})
    assert restore_vietnamese("nach boss to quá.", "N_VI B TO_EN Q.", "nach boss to quá.", taken) == "N_VI B TO_VI Q."
    # the second normalization moved a shared word: no guess
    assert restore_vietnamese(text, "K B TO_EN Q.", "con boss to to quá.", good) == "K B TO_EN Q."
