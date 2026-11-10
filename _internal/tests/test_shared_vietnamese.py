"""Words in both sea-g2p dictionaries stay Vietnamese beside names and English words; the cases are shared with Kotlin."""
import json
from pathlib import Path

import pytest

from abook.readaloud import phoneme_policy
from abook.readaloud.phoneme_policy import (Rulings, capitalised, restore_vietnamese, sentence_case, shared_word_scores, shared_word_verdicts,
                                             vietnamese_shared)

CASES = json.loads((Path(__file__).parent / "fixtures/readaloud/shared_vietnamese/cases.json").read_text("utf8"))["cases"]


def rulings_of(case: dict) -> Rulings | None:
    """The book's second-tier answers a case comes with (`rulings`: contexts {key: "v" / "e"}, names), as shared_rulings.rulings_of reads them."""
    given = case.get("rulings")
    return Rulings({key: answer == "v" for key, answer in given.get("contexts", {}).items()}, set(given.get("names", ()))) if given else None


def case_id(case: dict) -> str:
    return case["text"] + (" +rulings" if case.get("rulings") else "")


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


@pytest.mark.parametrize("case", CASES, ids=case_id)
def test_the_sentence_decides_which_shared_words_are_vietnamese(case):
    words = listed(case["text"].lower())
    capitals = capitalised(case["text"], case.get("source"))
    assert [words[i] for i in vietnamese_shared(case["text"].lower(), capitals, rulings_of(case))] == case["claimed"]
    if "doubtful" in case:  # what tier 1 leaves to the second tier
        assert [word for word, _, sure, _ in shared_word_verdicts(case["text"].lower(), capitals, rulings_of(case)) if not sure] == case["doubtful"]


@pytest.mark.parametrize("case", CASES, ids=case_id)
def test_both_desktop_frontends_give_the_shared_phonemes(case, studio):
    from abook.readaloud.vieneu_engine import phonemize

    assert phonemize([case["text"]], case.get("source"), rulings_of(case)) == case["phonemes"]
    with sentence_case(case["text"], case.get("source"), rulings_of(case)):  # as VieNeuEngine.generate_one does around infer
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


def test_a_shouted_word_is_a_name_unless_its_whole_sentence_is_shouted():
    assert capitalised("Hắn bị admin BAN nick rồi.") == {"ban"}
    assert capitalised("Cửa hàng ở Lalaport TOKYO BAY.") == {"lalaport", "tokyo", "bay"}
    assert capitalised("LUNG LAY! LUNG LAY!") == capitalised("“BAY ĐI!” Cô hét.") == capitalised("Hắn hét: BAY ĐI!") == frozenset()
    # the text layer lower-cases a shouted English word before it is spoken: only the written text can tell
    assert capitalised("Hắn bị admin ban nick rồi.", "Hắn bị admin BAN nick rồi.") == {"ban"}
    assert capitalised("LUNG lay! LUNG lay!", "LUNG LAY! LUNG LAY!") == frozenset()
    assert capitalised("LUNG lay! LUNG lay!") == {"lung"}


def test_tier_one_is_sure_outside_the_band_and_the_book_answers_inside():
    shared = phoneme_policy._shared()
    assert shared.threshold == 0 and shared.doubt == (-100, 0) and shared.name_doubt == 0 and shared.name_threshold > 100_000
    text, key = "do trans sắp thi.", "^|do|trans sắp"
    assert phoneme_policy.shared_word_contexts(text) == [key]
    assert shared_word_scores(text)[0][1] < shared.doubt[0]  # a short sentence: below the band, in doubt by its shape
    assert shared_word_verdicts(text) == [("do", False, False, "table")]
    assert shared_word_verdicts("do you know?") == [("do", False, True, "table")]  # English follows English: sure
    assert shared_word_verdicts("yuna no đâu.") == [("no", False, True, "table")]  # below the band, no such shape: sure
    assert shared_word_verdicts(text, rulings=Rulings({key: True})) == [("do", True, True, "ruling")]
    assert shared_word_verdicts(text, rulings=Rulings({key: False})) == [("do", False, True, "ruling")]
    assert shared_word_verdicts(text, rulings=Rulings({"another|do|sentence": True})) == [("do", False, False, "table")]
    # a capital is never Vietnamese at tier 1; it is in doubt only where the same words in prose would be Vietnamese
    assert shared_word_verdicts("danh hiệu kỵ sĩ tự do.", frozenset({"do"})) == [("do", False, False, "table")]
    assert shared_word_verdicts("iron man đã đến.", frozenset({"man"})) == [("man", False, True, "table")]


def test_a_name_of_the_roster_is_vietnamese_where_it_is_written_as_a_name():
    names = Rulings(names={"an", "can"})
    assert shared_word_verdicts("an an.", frozenset({"an"}), names) == [("an", True, True, "roster")] * 2
    assert shared_word_verdicts("an nói.", rulings=names) == [("an", True, True, "roster")]  # opens the sentence
    assert shared_word_verdicts("cô hỏi: can đâu rồi?", rulings=names) == [("can", True, True, "roster")]
    assert shared_word_verdicts("can you help me?", rulings=names)[0] == ("can", False, True, "table")  # an English word follows
    assert shared_word_verdicts("i can do it.", rulings=names)[0] == ("can", False, True, "table")  # sure English prose stays
    assert shared_word_verdicts("an an.", frozenset({"an"})) == [("an", False, True, "table")] * 2  # no roster: tier 1 alone
    assert not Rulings() and Rulings(names={"an"}) and Rulings({"a|an|b": True})


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
