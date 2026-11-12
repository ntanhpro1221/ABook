"""The second tier for words that are both Vietnamese and English, and for the origin of each roster name: what is asked,
how the answers are kept and resumed, and how a book carries them. No model: Ollama is a fake that answers by rule."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from abook.pipeline import PipelineStopped
from abook.readaloud import shared_rulings as sr
from abook.readaloud.phoneme_policy import Rulings
from abook.readaloud.vieneu_engine import phonemize

DO_TRANS = "^|do|trans sắp"


class Reply:
    def __init__(self, content: str) -> None:
        self.content = content

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return {"message": {"content": self.content}}


class Ollama:
    """Answers "a Vietnamese word" for every marked "Do" and "Say", "English" otherwise; a name by a fixed list."""

    ORIGINS = {"An An": "vi", "Long": "vi", "Chiaki": "ja", "Jieun": "ko", "Ben": "en", "An Jaehyun": "ko"}

    def __init__(self, broken: bool = False) -> None:
        self.bodies: list[dict] = []
        self.broken = broken

    def post(self, url: str, json: dict, timeout: float) -> Reply:  # noqa: A002 - the requests signature
        assert url == "http://ollama/api/chat"
        self.bodies.append(json)
        if self.broken:
            return Reply("not json")
        items = [re.sub(r"^\d+\. ", "", line) for line in json["messages"][-1]["content"].split("\n")]
        if json["messages"][0]["content"] == sr.NAME_SYSTEM:
            answer = {str(number): self.ORIGINS.get(item.split(" (cùng truyện")[0], "en") for number, item in enumerate(items, 1)}
        else:
            answer = {str(number): {"cum": "x", "loai": "tu_viet" if re.search(r"\[\[(Do|Say)\]\]", item) else "tieng_anh"}
                      for number, item in enumerate(items, 1)}
        return Reply(__import__("json").dumps(answer))


@pytest.fixture
def digest(monkeypatch):
    held = {"value": "digest-one"}
    monkeypatch.setattr(sr, "model_digest", lambda base_url, model=sr.MODEL: held["value"])
    return held


def stretches(*texts: str) -> list[tuple[str, str]]:
    return [(text, text) for text in texts]


def test_only_what_tier_one_doubts_and_sea_reads_english_is_asked():
    assert sr.doubts("Tôi no rồi, con boss to quá.", "Tôi no rồi, con boss to quá.") == []  # the table is sure
    assert sr.doubts("An An.", "An An.") == []  # a name far below zero: the roster's question, not this one
    (doubt,) = sr.doubts("Do trans sắp thi.", "Do trans sắp thi.")
    assert (doubt.key, doubt.word, doubt.shown, doubt.name) == (DO_TRANS, "do", "[[Do]] trans sắp thi.", False)
    # the model reads the sentence as the reader sees it; the key is what the phonemizer sees
    (shout,) = sr.doubts("Hắn bị admin BAN nick rồi.", "Hắn bị admin ban nick rồi.")
    assert (shout.key, shout.shown, shout.name) == ("bị admin|ban|nick rồi", "Hắn bị admin [[BAN]] nick rồi.", True)
    # the text layer moved a table word: no guess
    assert sr.doubts("Do trans sắp thi.", "Vì trans sắp thi do.") == []


def test_a_request_is_the_same_bytes_every_time_and_never_thinks():
    batch = sr.doubts("Do trans sắp thi.", "Do trans sắp thi.")
    first, again = sr.payload(sr.MODEL, "d1", batch), sr.payload(sr.MODEL, "d1", batch)
    assert first == again and first["think"] is False and first["stream"] is False
    assert first["options"]["temperature"] == 0 and first["options"]["seed"] != sr.payload(sr.MODEL, "d2", batch)["options"]["seed"]
    assert first["format"]["required"] == ["1"] and first["messages"][-1]["content"] == "1. [[Do]] trans sắp thi."
    assert [message["role"] for message in first["messages"]] == ["system", "user", "assistant", "user"]
    worked = json.loads(first["messages"][2]["content"])
    assert len(worked) == len(sr.SHOTS) and all(answer["loai"] in sr.KINDS for answer in worked.values())
    names = sr.name_payload(sr.MODEL, "d1", ["An", "Chiaki"], ["An", "Lâm Phong", "Chiaki"])
    assert names["messages"][-1]["content"] == "1. An (cùng truyện: Lâm Phong, Chiaki)\n2. Chiaki"
    assert names["format"]["properties"]["1"]["enum"] == list(sr.ORIGINS)


def test_only_a_vietnamese_word_counts_as_vietnamese():
    content = json.dumps({"1": {"cum": "a", "loai": "tu_viet"}, "2": {"cum": "b", "loai": "ten_viet"}, "3": {"cum": "c", "loai": "ten_ngoai"},
                          "4": {"cum": "d", "loai": "khac"}, "5": "tu_viet"})
    assert sr.parse(content, 6) == [True, False, False, None, None, None]
    assert sr.parse("{", 2) == [None, None] and sr.parse("[]", 1) == [None]
    assert sr.parse_names('{"1": "ja", "2": "zh", "3": "vi"}', 4) == ["ja", None, "vi", None]


def test_the_pass_writes_the_answers_and_a_second_run_asks_nothing(tmp_path: Path, digest):
    ollama = Ollama()
    text = stretches("Do trans sắp thi.", "Do exercise đi.", "Tôi no rồi.", "Hội quán của guild Say xỉn.")
    counts = sr.compute(tmp_path, text, ["AN AN", "Lâm phu nhân", "BEN", "người gọi Lucy"], "http://ollama", session=ollama, log=lambda _: None)
    assert (counts["doubts"], counts["names"], counts["asked"], counts["failed"]) == (3, 2, 5, 0)
    stored = json.loads((tmp_path / sr.FILE).read_text("utf8"))
    assert stored["complete"] is True and stored["digest"] == "digest-one" and stored["prompt"] == sr.PROMPT_VERSION
    assert stored["contexts"] == {DO_TRANS: "v", "^|do|exercise đi": "v", "của guild|say|xỉn ^": "v"}
    assert stored["origins"] == {"An An": "vi", "Ben": "en"} and stored["names"] == ["an"] and stored["foreign"] == ["ben"]
    assert sr.valid(stored) and sr.shared(stored).keys() == {"version", "contexts", "names", "foreign", "readings"}
    asked = len(ollama.bodies)
    assert sr.compute(tmp_path, text, ["AN AN", "Lâm phu nhân", "BEN"], "http://ollama", session=ollama, log=lambda _: None)["asked"] == 0
    assert len(ollama.bodies) == asked
    # the book gained a sentence: only the new doubt is asked; a sentence that left takes its answer along
    more = sr.compute(tmp_path, stretches("Do trans sắp thi.", "Yuna no đâu rồi?"), ["AN AN"], "http://ollama", session=ollama, log=lambda _: None)
    assert more["asked"] == 1 and set(json.loads((tmp_path / sr.FILE).read_text("utf8"))["contexts"]) == {DO_TRANS, "^ yuna|no|đâu rồi"}
    # another model answers for itself
    digest["value"] = "digest-two"
    assert sr.compute(tmp_path, text, ["AN AN"], "http://ollama", session=ollama, log=lambda _: None)["asked"] == 4


def test_an_answer_that_is_not_json_leaves_tier_one_alone_and_a_stop_keeps_what_is_done(tmp_path: Path, digest):
    counts = sr.compute(tmp_path, stretches("Do trans sắp thi."), ["Ben"], "http://ollama", session=Ollama(broken=True), log=lambda _: None)
    assert (counts["asked"], counts["failed"]) == (2, 2)
    stored = sr.read(tmp_path / sr.FILE)
    assert stored["contexts"] == {} and stored["origins"] == {} and sr.rulings_of(stored) is None and sr.load(tmp_path) is None
    (tmp_path / sr.FILE).unlink()
    with pytest.raises(PipelineStopped):  # a stop is a stop: the pipeline must not go on to record with what is there
        sr.compute(tmp_path, stretches("Do trans sắp thi."), ["Ben"], "http://ollama", session=Ollama(), stop_requested=lambda: True,
                   log=lambda _: None)
    assert sr.read(tmp_path / sr.FILE)["complete"] is False
    digest["value"] = None
    with pytest.raises(RuntimeError):
        sr.compute(tmp_path, [], [], "http://ollama", session=Ollama())


def test_the_stored_answers_change_the_phonemes_and_nothing_else(tmp_path: Path, digest):
    sr.compute(tmp_path, stretches("Do trans sắp thi.", "An An."), ["An An"], "http://ollama", session=Ollama(), log=lambda _: None)
    rulings = sr.load(tmp_path)
    assert isinstance(rulings, Rulings) and rulings.contexts == {DO_TRANS: True} and rulings.names == {"an"}
    assert phonemize(["Do trans sắp thi."]) == "dˈuː tɹˈænz sˈaɜp tˈi."
    assert phonemize(["Do trans sắp thi."], rulings=rulings) == "zˈɔ tɹˈænz sˈaɜp tˈi."
    assert phonemize(["An An."]) == "æn æn." and phonemize(["An An."], rulings=rulings) == "ˈaːn ˈaːn."
    assert phonemize(["Tôi no rồi."], rulings=rulings) == phonemize(["Tôi no rồi."])


def test_the_clip_key_only_moves_where_a_ruling_applies(tmp_path: Path):
    rulings = Rulings({DO_TRANS: True}, {"an"})
    assert sr.tag("Tôi no rồi.", rulings) == "" and sr.tag("Do trans sắp thi.", None) == "" and sr.tag("Do trans sắp thi.", Rulings()) == ""
    mark = sr.tag("Do trans sắp thi.", rulings)
    assert re.fullmatch(r"w[0-9a-f]{16}", mark) and mark == sr.tag("Do trans sắp thi.", Rulings({DO_TRANS: True}))
    assert mark != sr.tag("Do trans sắp thi.", Rulings({DO_TRANS: False}))
    assert sr.tag("An An.", rulings) not in ("", mark)


def test_the_roster_is_asked_name_by_name():
    roster = sr.roster_names(["KUCHINASHI", "AN AN", "Lâm phu nhân", "SEO-YEON", "An An", "???", "người gọi Lucy"])
    assert roster == ["Kuchinashi", "An An", "Lâm phu nhân", "Seo-Yeon", "người gọi Lucy"]
    assert sr.asked_names(roster) == ["Kuchinashi", "An An", "Seo-Yeon"]  # diacritics: Vietnamese already; a label is not a name
    origins = {"An An": "vi", "An Jaehyun": "ko", "Long": "vi", "Tan": "vi", "Chiaki": "ja", "Ben": "en"}
    assert sr.word_origins(origins) == {"Jaehyun": "ko", "Long": "vi", "Tan": "vi", "Chiaki": "ja", "Ben": "en"}  # "An" of two origins: undecided
    assert sr.vietnamese_names(origins) == ["tan"]  # "long" sounds the same in both languages: not a table word
    assert sr.vietnamese_names({"An An": "vi"}) == ["an"]


def test_a_name_is_read_by_its_own_origin_where_the_book_would_read_it_otherwise():
    from abook.readaloud import names

    origins = {"Chiaki": "ja", "Jieun": "ko", "Alice": "en", "Tanaka": "ja"}
    assert sr.name_readings(origins, None) == {"Chiaki": "Chi-a-ki", "Jieun": names.name_reading("Jieun", "ko").replace("_", ""),
                                               "Tanaka": "Ta-na-ca"}
    japanese = sr.name_readings(origins, "ja")
    assert "Tanaka" not in japanese and "Chiaki" not in japanese  # the book's origin reads them already
    assert japanese["Jieun"] == names.name_reading("Jieun", "ko").replace("_", "")
    assert set(japanese) == {"Jieun"}  # "other" never undoes the book's own reading
    assert sr.name_readings({"Lan": "vi"}, "ja") == ({"Lan": "Lan"} if names.name_reading("Lan", "ja") else {})
    assert sr.name_item("Chiaki", ["Alice", "Edward"]) == "Chiaki"  # a clear name is judged alone
    assert sr.name_item("An An", ["Alice", "An An", "Edward"]) == "An An (cùng truyện: Alice, Edward)"


def test_a_foreign_name_spelled_like_a_vietnamese_syllable_is_kept_for_the_reader():
    origins = {"Dan": "en", "Tom Riddle": "en", "Alice": "en", "Ben": "en", "Lan": "vi", "Kim Dokja": "ko", "Mai": "ja", "An An": "vi"}
    assert sr.foreign_names(origins) == ["ben", "dan", "tom"]  # "Alice", "Riddle" are no Vietnamese syllable: sea-g2p reads them in English already
    assert sr.foreign_names({"Dan": "vi"}) == [] and sr.foreign_names({"Dan Brown": "en", "Dan": "vi"}) == []  # a Vietnamese Dan; two characters disagree
    rulings = Rulings(foreign={"dan"})
    assert sr.tag("Dan cười.", rulings).startswith("w") and sr.tag("Lan cười.", rulings) == ""


def test_only_a_file_of_this_shape_is_read(tmp_path: Path):
    good = {"version": sr.VERSION, "contexts": {DO_TRANS: "v"}, "names": ["an"], "foreign": ["dan"], "readings": {"Chiaki": "Chi-a-ki"}}
    assert sr.valid(good) and sr.rulings_of(good).contexts == {DO_TRANS: True} and sr.rulings_of(good).foreign == {"dan"}
    assert sr.rulings_of({**good, "contexts": {}, "names": []}).foreign == {"dan"}  # a book with nothing but a foreign name still has rulings
    for bad in ({**good, "version": 0}, {**good, "contexts": {DO_TRANS: "x"}}, {**good, "names": "an"}, {**good, "foreign": "dan"},
                {key: value for key, value in good.items() if key != "foreign"}, {**good, "readings": {"a": 1}}, [], None):
        assert not sr.valid(bad)
    (tmp_path / sr.FILE).write_text("{", encoding="utf8")
    assert sr.read(tmp_path / sr.FILE) is None and sr.load(tmp_path) is None and sr.load(tmp_path / "missing") is None


def test_the_book_file_carries_the_answers(tmp_path: Path):
    from abook.io_utils import atomic_write_json
    from abook.webui import bookfile
    from tests.test_a_package_names_the_recorded_voices import _recorded

    paths, _ = _recorded(tmp_path)
    assert "sharedWords" not in bookfile.listening_layer(paths.root)[0]
    stored = {"version": sr.VERSION, "prompt": sr.PROMPT_VERSION, "model": sr.MODEL, "digest": "d", "complete": True, "bookOrigin": None,
              "origins": {"An An": "vi", "Dan": "en"}, "names": ["an"], "foreign": ["dan"], "readings": {}, "contexts": {DO_TRANS: "v"}}
    atomic_write_json(paths.root / sr.FILE, stored)
    book, _ = bookfile.listening_layer(paths.root)
    assert book["sharedWords"] == {"version": sr.VERSION, "contexts": {DO_TRANS: "v"}, "names": ["an"], "foreign": ["dan"], "readings": {}}
    assert isinstance(book["sharedWords"], bookfile._BOOK_FIELDS["sharedWords"])


# ---- a pass stopped, crashed or failed midway (review 0.4.167 #1) ------------------------------------------------------------

def _book(*texts: str) -> tuple[object, object]:
    from types import SimpleNamespace

    rows = [{"status": "analyzed", "listener_text": text, "text": text} for text in texts]
    db = SimpleNamespace(list_segments=lambda: rows, list_characters=lambda: [{"display_name": "Ben"}, {"display_name": "An An"}])
    tts = SimpleNamespace(spoken_text=lambda row: row["text"], _shared_rulings=("stale",))
    return db, tts


BOOK = ("Do trans sắp thi.", "Do exercise đi.", "Hội quán của guild Say xỉn.")
KEPT = ("contexts", "origins", "names", "foreign")


@pytest.fixture
def quiet(monkeypatch):
    from abook import studio_names

    monkeypatch.setattr(sr, "BATCH", 1)
    monkeypatch.setattr(studio_names, "book_origin_for_project", lambda _db: None)
    monkeypatch.setattr(sr, "release", lambda *_a, **_k: None)


def _settle(root: Path, db, tts, *, stop=lambda: False, emit=lambda *_a: None, **kw):
    from abook import worker

    worker.settle_shared_rulings(root, db, tts, "http://ollama", stop, lambda _: None, emit, pause_requested=lambda: False, **kw)


def test_a_pass_stopped_midway_is_finished_before_the_next_run_records(tmp_path: Path, digest, quiet, monkeypatch):
    db, tts = _book(*BOOK)
    ollama = Ollama()
    monkeypatch.setattr("requests.post", ollama.post)
    whole = tmp_path / "whole"  # an unbroken pass, for the answers the book must end up with
    whole.mkdir()
    _settle(whole, db, tts, analysed=True)
    expected = json.loads((whole / sr.FILE).read_text("utf8"))
    assert expected["complete"] is True
    unbroken = [body["messages"][-1]["content"] for body in ollama.bodies]
    ollama.bodies.clear()
    book = tmp_path / "book"
    book.mkdir()
    # stopped after two requests: the run stops, and nothing reads the half as the book's rulings
    with pytest.raises(PipelineStopped):
        _settle(book, db, tts, stop=lambda: len(ollama.bodies) >= 2, analysed=True)
    half = sr.read(book / sr.FILE)
    assert half["complete"] is False and (half["origins"] or half["contexts"])
    assert sr.finished(half) is None and sr.load(book) is None and tts._shared_rulings is None
    # the next run resumes the pass without a fresh analysis (a resume into an analysed book) and finishes it
    _settle(book, db, tts)
    done = json.loads((book / sr.FILE).read_text("utf8"))
    assert done["complete"] is True and sr.load(book) is not None
    assert {k: done[k] for k in KEPT} == {k: expected[k] for k in KEPT}
    assert [body["messages"][-1]["content"] for body in ollama.bodies] == unbroken, "the resumed pass asks what the unbroken one asked"
    _settle(book, db, tts)  # finished: nothing asked again
    assert len(ollama.bodies) == len(unbroken)


def test_ollama_failing_midway_leaves_the_pass_unfinished_and_raises(tmp_path: Path, digest, quiet):
    db, tts = _book(*BOOK)

    class Dying(Ollama):
        def post(self, url: str, json: dict, timeout: float) -> Reply:  # noqa: A002
            if len(self.bodies) >= 2:
                raise ConnectionError("Ollama chết")
            return super().post(url, json, timeout)

    with pytest.raises(ConnectionError):
        sr.compute(tmp_path, stretches(*BOOK), ["Ben", "An An"], "http://ollama", session=Dying(), log=lambda _: None)
    assert sr.read(tmp_path / sr.FILE)["complete"] is False and sr.load(tmp_path) is None
    # the model gone on the next run: a half-asked book waits for it rather than recording the rest on tier one
    digest["value"] = None
    with pytest.raises(RuntimeError, match="model"):
        _settle(tmp_path, db, tts, model=sr.MODEL)
    assert sr.read(tmp_path / sr.FILE)["complete"] is False


def test_a_book_with_no_model_from_the_start_is_settled_on_tier_one_for_good(tmp_path: Path, digest):
    digest["value"] = None
    db, tts = _book(*BOOK)
    events: list[str] = []
    emit = lambda kind, _payload: events.append(kind)  # noqa: E731
    _settle(tmp_path, db, tts, emit=emit)
    stored = sr.read(tmp_path / sr.FILE)
    assert stored["complete"] is True and stored["skipped"] and sr.load(tmp_path) is None and events == ["shared_rulings_skipped"]
    digest["value"] = "digest-one"  # the model turns up later: a book already recorded on tier one stays on it
    _settle(tmp_path, db, tts, emit=emit)
    _settle(tmp_path, db, tts, emit=emit, analysed=True)
    assert sr.read(tmp_path / sr.FILE) == stored and events == ["shared_rulings_skipped"]


def test_an_occurrence_without_a_usable_answer_is_not_asked_again_on_resume(tmp_path: Path, digest, monkeypatch):
    monkeypatch.setattr(sr, "BATCH", 1)
    broken = Ollama(broken=True)
    with pytest.raises(PipelineStopped):
        sr.compute(tmp_path, stretches(*BOOK), [], "http://ollama", session=broken, stop_requested=lambda: len(broken.bodies) >= 1,
                   log=lambda _: None)
    assert len(sr.read(tmp_path / sr.FILE)["unanswered"]) == 1
    again = Ollama()
    counts = sr.compute(tmp_path, stretches(*BOOK), [], "http://ollama", session=again, log=lambda _: None)
    assert counts["asked"] == 2 and len(again.bodies) == 2, "an unbroken pass asks each occurrence once; so does a resumed one"


def test_an_unfinished_pass_does_not_travel_in_the_book_file(tmp_path: Path):
    from abook.io_utils import atomic_write_json
    from abook.webui import bookfile
    from tests.test_a_package_names_the_recorded_voices import _recorded

    paths, _ = _recorded(tmp_path)
    stored = {"version": sr.VERSION, "prompt": sr.PROMPT_VERSION, "model": sr.MODEL, "digest": "d", "complete": False, "bookOrigin": None,
              "origins": {"An An": "vi"}, "names": ["an"], "foreign": [], "readings": {}, "contexts": {DO_TRANS: "v"}}
    atomic_write_json(paths.root / sr.FILE, stored)
    assert sr.load(paths.root) is None and "sharedWords" not in bookfile.listening_layer(paths.root)[0]
