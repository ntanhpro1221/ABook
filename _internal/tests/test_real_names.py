"""Real names where the name-sound table and the split Japanese-name road meet (fixtures/readaloud/real_names/cases.json).

One roster (a Western "Dan", the Korean "Ji-eun" and "Hyun Woo", the Japanese "Heizaemon" and "Yuki") read in a book of Japanese
origin, of Korean origin and of no settled origin. The same file is read by RealNamesTest.kt: the phone says the same string and
hands the model the same phonemes.
"""
import json
from pathlib import Path

import pytest

from abook.readaloud import japanese_policy, shared_rulings, vieneu
from abook.readaloud.phoneme_policy import book_rulings, sentence_case
from abook.readaloud.studio_tn import studio_tn
from abook.webui.word_timing import tokens

FIXTURE = json.loads((Path(__file__).parent / "fixtures/readaloud/real_names/cases.json").read_text("utf8"))
ROSTER = FIXTURE["roster"]
BOOKS = FIXTURE["books"]
CASES = [(book, case) for book in BOOKS for case in book["cases"]]
STRESS = ("ˈ", "ˌ")


def _id(value):
    if isinstance(value, dict) and "text" in value:
        return value["text"][:28]
    if isinstance(value, dict):
        return f"origin={value['origin']}"
    return None


def _readings(book):
    """What the reader holds for the book before the listener's own readings: proven names under Studio's name readings."""
    return {**book["proven"], **book["sharedWords"]["readings"]}


def _phonemes(text, book, rulings="book"):
    from abook.readaloud import vieneu_engine

    shown, parts = vieneu.units(text, 256, book["origin"], readings=_readings(book), direct_english=True)
    assert len(parts) == 1
    with book_rulings(shared_rulings.rulings_of(book["sharedWords"]) if rulings == "book" else None):
        return vieneu_engine.phonemize(parts[0].pieces, source=parts[0].text(shown))


@pytest.fixture
def studio_frontend(monkeypatch):
    """Studio's VieNeu frontend with ABook's patches, undone after the test (tests/test_readaloud_phoneme_policy.py)."""
    pytest.importorskip("sea_g2p")
    import vieneu_utils.phonemize_text as pt
    from abook.tts import keep_vieneu_final_mark

    for name in ("punc_norm", "_phonemize_cached"):
        monkeypatch.setattr(pt, name, getattr(pt, name))
    monkeypatch.setattr(pt, "_abook_keeps_final_mark", getattr(pt, "_abook_keeps_final_mark", False), raising=False)
    keep_vieneu_final_mark()
    return pt


def test_the_fixture_covers_every_road_in_every_book():
    assert [book["origin"] for book in BOOKS] == ["ja", "ko", None]
    for book in BOOKS:
        shown = " ".join(case["text"] for case in book["cases"])
        for word in ("Ji-eun", "Hyun Woo", "Heizaemon", "Dan", "pin", "veo", "boa", "K", "APP"):
            assert word in shown, (book["origin"], word)
        assert "yuki" in shown.lower()
    ja = " ".join(case["text"] for case in BOOKS[0]["cases"])
    assert "YUKI" in ja and "HYUN WOO" in ja


@pytest.mark.parametrize("book", BOOKS, ids=_id)
def test_the_book_is_what_studio_and_the_book_itself_give(book):
    """`sharedWords` is the roster through shared_rulings' producers, `proven` the names the book's own text proves."""
    shared = book["sharedWords"]
    assert shared_rulings.valid(shared)
    assert shared == {"version": 2, "contexts": {}, "names": shared_rulings.vietnamese_names(ROSTER),
                      "foreign": shared_rulings.foreign_names(ROSTER), "readings": shared_rulings.name_readings(ROSTER, book["origin"])}
    assert shared["foreign"] == ["dan"]  # the Western name spelled like a Vietnamese syllable; no Korean or Japanese name
    texts = [case["text"] for case in book["cases"]]
    assert japanese_policy.book_name_readings(texts, list(ROSTER), book["origin"]) == book["proven"]
    rulings = shared_rulings.rulings_of(shared)
    assert rulings is not None and set(rulings.foreign) == {"dan"}


@pytest.mark.parametrize("book", BOOKS, ids=_id)
def test_the_reader_proves_names_without_a_roster_and_says_the_same(book):
    """Read-aloud (desktop and phone) has no roster: it proves names from the text alone, and Studio's readings fill the rest."""
    own = japanese_policy.book_name_readings([case["text"] for case in book["cases"]], origin=book["origin"])
    assert own == {name: said for name, said in book["proven"].items() if name != "WOO"}
    readings = {**own, **book["sharedWords"]["readings"]}
    for case in book["cases"]:
        _, parts = vieneu.units(case["text"], 256, book["origin"], readings=readings, direct_english=True)
        assert [" ".join(part.pieces) for part in parts] == [case["said"]]


@pytest.mark.parametrize("book,case", CASES, ids=_id)
def test_read_aloud_and_studio_say_the_same_string(book, case):
    text, origin, readings = case["text"], book["origin"], _readings(book)
    shown, parts = vieneu.units(text, 256, origin, readings=readings, direct_english=True)
    assert shown == tokens(text)
    assert len(parts) == 1 and (parts[0].first, parts[0].last) == (0, len(shown) - 1)
    assert " ".join(parts[0].pieces) == case["said"]
    assert " ".join(word for word in vieneu.spoken_tokens(shown, origin, readings=readings, direct_english=True) if word) == case["said"]
    said, offsets = studio_tn(text, origin, True, direct_english=True, readings=readings)
    assert said == case["said"]
    assert len(offsets) == len(text) + 1 and offsets == sorted(offsets) and offsets[-1] == len(said)
    assert vieneu.reading_tag(text, origin, direct_english=True) == case["tag"]
    assert case["tag"].endswith("jp-fallback6")


@pytest.mark.parametrize("book,case", CASES, ids=_id)
def test_the_model_gets_one_phonetic_word_per_spoken_syllable(book, case):
    pytest.importorskip("sea_g2p")
    phonemes = _phonemes(case["text"], book)
    assert phonemes == case["phonemes"]
    words = phonemes.split()
    assert len(words) == len(case["said"].replace("-", " ").split())  # no name is joined into one word, none loses a syllable
    assert all(sum(word.count(mark) for mark in STRESS) == 1 for word in words), phonemes


@pytest.mark.parametrize("book,case", CASES, ids=_id)
def test_studio_hands_the_model_the_same_phonemes(book, case, studio_frontend):
    """Studio only sees the normalized string: `sentence_case` carries the shown text and the book's rulings to its frontend."""
    said, _ = studio_tn(case["text"], book["origin"], True, direct_english=True, readings=_readings(book))
    with sentence_case(said, case["text"], shared_rulings.rulings_of(book["sharedWords"])):
        chunks = studio_frontend.normalize_to_chunks_v3_with_gaps(said)[0]
        assert len(chunks) == 1
        assert studio_frontend.phonemize_text_with_emotions(chunks[0]) == case["phonemes"]


@pytest.mark.parametrize("book", BOOKS, ids=_id)
def test_each_name_and_word_has_its_own_sound_in_every_book(book):
    pytest.importorskip("sea_g2p")
    from abook.readaloud.vieneu_engine import phonemize

    by_text = {case["text"]: case for case in book["cases"]}
    # Ji-eun: the romanization writes "Gi-ưn", the name-sound table says it as "Gi-ân" (sea-g2p has no "ưn")
    assert by_text["Ji-eun gật đầu."]["said"] == "Gi-ưn gật đầu."
    assert by_text["Ji-eun gật đầu."]["phonemes"] == phonemize(["Gi-ân gật đầu."]) == "zˈi ˈən ɣˈə6t̪ ɗˈə2w."
    # Hyun Woo: three level syllables, no tone guessed and no English "woo"
    assert by_text["Hyun Woo nhìn Ji-eun rồi cười."]["phonemes"].startswith("hˈi ˈun ˈu ɲˈi2n ")
    # Heizaemon: four phonetic words wherever it stands, the same sounds in every book
    for text in ("Chờ đã, Heizaemon!", "Pa-pa nhìn Heizaemon.", "Dan! Heizaemon và Yuki đang chờ.", "Hạng K! Heizaemon mở APP."):
        assert "Hây-da-e-môn" in by_text[text]["said"]
        assert " hˈəɪ zˈaː ˈɛ mˈon" in " " + by_text[text]["phonemes"].replace("!", " ").replace(".", " ")
    # Yuki is "Giu-ki" beside a Vietnamese word, a Western name and a Japanese name
    assert "zˈu kˈi" in by_text["Dan! Heizaemon và Yuki đang chờ."]["phonemes"]
    # Dan: a name by the book's rulings (đ) after "Rồi" and opening a sentence; without the rulings sea-g2p reads the syllable "dan"
    assert by_text["Rồi Dan cười."]["phonemes"] == "ɹˈo2j ɗˈaːn kˈyə2j."
    assert by_text["Dan! Heizaemon và Yuki đang chờ."]["phonemes"].startswith("ɗˈaːn! ")
    assert _phonemes("Rồi Dan cười.", book, rulings=None) == "ɹˈo2j zˈaːn kˈyə2j."
    # pin / veo / boa: Vietnamese level syllables, not the English words of sea-g2p's dictionary
    words = by_text["Nước trong veo, Yuki thả con boa xuống rồi thay pin."]["phonemes"].replace(",", "").replace(".", "").split()
    assert [words[2], words[7], words[-1]] == ["vˈɛw", "bwˈaː", "pˈin"]
    assert by_text["Rồi Dan hỏi Ji-eun: điện thoại hết pin à?"]["phonemes"].endswith(" pˈin ˈaː2?")
    # K is the letter "ca"; APP is the English word, lower-cased for the reader and said with an English vowel
    app = by_text["Ji-eun tải APP hạng K về máy."]
    assert app["said"] == "Gi-ưn tải app hạng K về máy."
    assert app["phonemes"].endswith(" t̪ˈaː4j ˈæp hˈaː6ŋ kˈaː vˈe2 mˈaɜj.")
    assert phonemize(["hạng K về máy."]) == phonemize(["hạng ca về máy."]) == "hˈaː6ŋ kˈaː vˈe2 mˈaɜj."
    assert by_text["Hạng K! Heizaemon mở APP."]["phonemes"] == "hˈaː6ŋ kˈaː! hˈəɪ zˈaː ˈɛ mˈon mˈəː4 ˈæp."


def test_a_shouted_name_is_the_name_in_a_japanese_book():
    """YUKI / HYUN WOO in capitals are the names, not letters and not English: same string and sounds as the plain spelling."""
    pytest.importorskip("sea_g2p")
    book = BOOKS[0]
    by_text = {case["text"]: case for case in book["cases"]}
    assert book["proven"] == {"HYUN": "Hi-un", "WOO": "Woo", "YUKI": "Giu-ki"}
    assert by_text["YUKI! Heizaemon gọi lớn."]["said"] == "Giu-ki! Hây-da-e-môn gọi lớn."
    assert by_text["“HYUN WOO! Ji-eun đâu rồi?”"]["said"] == "“Hi-un U! Gi-ưn đâu rồi?”"
    assert by_text["“HYUN WOO! Ji-eun đâu rồi?”"]["phonemes"] == "hˈi ˈun ˈu! zˈi ˈən ɗˈə1w ɹˈo2j?"
    mixed = by_text["Rồi Dan, Heizaemon và YUKI mở APP hạng K xem cục pin."]
    assert mixed["said"] == "Rồi Dan, Hây-da-e-môn và Giu-ki mở app hạng K xem cục pin."
    assert mixed["phonemes"] == "ɹˈo2j ɗˈaːn, hˈəɪ zˈaː ˈɛ mˈon vˌaː2 zˈu kˈi mˈəː4 ˈæp hˈaː6ŋ kˈaː sˈɛm kˈu6c pˈin."
    assert _phonemes("Rồi Dan, Heizaemon và Yuki mở APP hạng K xem cục pin.", book) == mixed["phonemes"]
