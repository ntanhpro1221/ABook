"""Cách đọc riêng của một cuốn chỉ có chữ ("Đọc từ này là…", lớp sửa `readings`): áp theo từng chữ hiện cho mọi giọng, mốc từng chữ vẫn
khớp chữ hiện, khoá clip chỉ đổi ở đoạn có từ ấy. Bộ ví dụ dùng chung với Kotlin: tests/fixtures/book_edits/readings/speech.json."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from abook.readaloud import cache, readings, vieneu
from abook.readaloud.service import ReadAloud
from abook.webui import book_edits, packages
from abook.webui.library import book_id
from abook.webui.word_timing import tokens
from tests import book_edits_fixtures as shared
from tests.test_readaloud import FakeProvider
from tests.test_readaloud_vieneu import fake_voices  # noqa: F401 - fixture dùng chung

SPEECH = shared.FIXTURES / "readings" / "speech.json"


def test_the_shared_speech_cases_match() -> None:
    golden = json.loads(SPEECH.read_text(encoding="utf-8"))
    assert golden == shared.speech_cases(), "Python và bộ ví dụ (Kotlin đọc cùng file) phải khớp"
    for case in golden["cases"]:
        assert len(case["spokenTokens"] or tokens(case["spokenText"])) == len(case["tokens"]), "số chữ đem đọc = số chữ hiện"


def test_only_whole_words_match_and_case_counts() -> None:
    table = {"Haruto": "Ha ru tô"}
    assert readings.spoken_text("“Haruto!” haruto Harutoo Haruto-kun", table) == "“Ha-ru-tô!” haruto Harutoo Haruto-kun"
    assert readings.tag("haruto Harutoo", table) == "" and readings.tag("Haruto", table).startswith("r")
    assert readings.spoken_text("a\n  Haruto\tb", table) == "a\n  Ha-ru-tô\tb", "khoảng trắng giữ nguyên"
    assert readings.is_word("Haruto") and readings.is_word("Haruto-kun") and not readings.is_word("Hai kes")
    assert not readings.is_word("Haruto,") and not readings.is_word("") and not readings.is_word("Tôkyô")


def test_an_online_voice_reads_the_spoken_form_and_each_shown_word_keeps_one_highlight(tmp_path: Path) -> None:
    provider = FakeProvider()
    service = ReadAloud(tmp_path, [provider])
    text = "Hôm nay Haruto đi học."
    clip = service.clip("fake:ngoc", text, readings={"Haruto": "Ha ru tô"})
    assert provider.calls[-1] == ("ngoc", "Hôm nay Ha-ru-tô đi học."), "giọng nhận chữ đem đọc, chữ hiện không đổi"
    assert len(clip["words"]) == len(text.split()) and clip["words"][2] == [600, 850], "cả cụm Ha-ru-tô là MỘT chữ sáng"


def test_changing_a_reading_reads_again_only_the_paragraphs_with_that_word(tmp_path: Path) -> None:
    provider = FakeProvider()
    service = ReadAloud(tmp_path, [provider])
    first = {"Haruto": "Ha ru tô", "Kate": "Kết"}
    named, plain = "Haruto về.", "Trời mưa."
    before = (service.clip("fake:ngoc", named, readings=first), service.clip("fake:ngoc", plain, readings=first))
    assert service.clip("fake:ngoc", plain) == before[1], "đoạn không có từ nào: cùng clip như khi không có cách đọc"
    calls = len(provider.calls)
    changed = {"Haruto": "Ha-ru-to", "Kate": "Kết"}
    assert service.clip("fake:ngoc", plain, readings=changed) == before[1] and len(provider.calls) == calls
    assert service.clip("fake:ngoc", named, readings={**changed, "Kate": "Kê"})["file"] != before[0]["file"]
    assert len(provider.calls) == calls + 1
    assert service.clip("fake:ngoc", named, readings={**first, "Lucien": "Lu-xi-en"}) == before[0], "cách đọc của từ khác không đụng tới"


def test_a_voice_on_this_computer_applies_the_reading_after_the_names(fake_voices, tmp_path: Path) -> None:  # noqa: F811
    provider, engines = fake_voices
    service = ReadAloud(tmp_path / "cache", [provider])
    text = "Haruto đến cùng Kate."
    clip = service.clip("vieneu:turbo/Thường", text, origin="ja", readings={"Haruto": "Ha-ru-to", "Kate": "Kết"})
    said = engines["turbo"].calls[-1]
    assert "ha-ru-to" in said and "ha-ru-tô" not in said and "kết" in said, "cách đọc của người nghe thắng luật phiên âm"
    assert len(clip["words"]) == len(text.split())
    key = cache.clip_key("vieneu", "turbo/Thường", text, "+".join([vieneu.reading_tag(text, "ja"),
                                                                       readings.tag(text, {"Haruto": "Ha-ru-to", "Kate": "Kết"})]))
    assert clip["file"].startswith(key)


def test_prepare_ahead_uses_the_same_readings_as_listening(fake_voices, tmp_path: Path) -> None:  # noqa: F811
    provider, _ = fake_voices
    service = ReadAloud(tmp_path / "cache", [provider])
    table = {"Haruto": "Ha-ru-to"}
    service.prepare.start("vieneu:nano/Nhẹ", ["Haruto về nhà rồi."], "", None, table)
    service.prepare.join(30)
    assert service.clip("vieneu:nano/Nhẹ", "Haruto về nhà rồi.", cached_only=True, readings=table)
    with pytest.raises(Exception):
        service.clip("vieneu:nano/Nhẹ", "Haruto về nhà rồi.", cached_only=True)


def test_the_listener_sets_a_reading_and_the_book_is_read_with_it(tmp_path: Path) -> None:
    from abook.webui.actions import FakeRunner
    from abook.webui.library import Preferences
    from abook.webui.listening import Listening
    from abook.webui.server import App, Server
    from tests.test_webui_listen_and_sync import _request

    library = tmp_path / "lib"
    folder = library / packages.IMPORTED_FOLDER / "base"
    shutil.copytree(shared.BASE, folder)
    preferences = Preferences(tmp_path / "prefs" / "preferences.json")
    preferences.update({"libraryRoot": str(library)})
    app = App(preferences=preferences, runner=FakeRunner(), token="t", listening=Listening(tmp_path / "prefs" / "listening.json"))
    provider = FakeProvider()
    app.readaloud = ReadAloud(tmp_path / "prefs" / "readaloud-cache", [provider])
    server = Server(app, port=0).start()
    identifier = book_id(folder)

    def call(method: str, path: str, body: dict | None = None):
        status, data, _ = _request(server.port, method, path, headers={"X-Ebook-Token": "t"}, body=body)
        return status, json.loads(data)

    try:
        status, view = call("PUT", f"/api/books/{identifier}/readings", {"surface": "Haruto", "spoken": "Ha ru tô"})
        assert status == 200 and view == {"readings": [{"surface": "Haruto", "spoken": "Ha ru tô"}]}
        assert book_edits.load(folder)["readings"] == {"Haruto": "Ha ru tô"}
        assert (folder / "edits.json").read_bytes().count(b"\r") == 0
        status, clip = call("POST", "/api/readaloud/clip", {"voice": "fake:ngoc", "text": "Haruto về.", "bookId": identifier})
        assert status == 200 and provider.calls[-1][1] == "Ha-ru-tô về."
        # "Nghe thử" một cách đọc chưa lưu: cách đọc gửi kèm thắng của cuốn, không ghi gì vào sách.
        status, _ = call("POST", "/api/readaloud/clip", {"voice": "fake:ngoc", "text": "Haruto", "bookId": identifier, "readings": {"Haruto": "Ha-ru-to"}})
        assert status == 200 and provider.calls[-1][1] == "Ha-ru-to"
        assert book_edits.load(folder)["readings"] == {"Haruto": "Ha ru tô"}
        status, _ = call("POST", "/api/readaloud/clip", {"voice": "fake:ngoc", "text": "Haruto", "bookId": identifier, "readings": {}})
        assert status == 200 and provider.calls[-1][1] == "Haruto", "ô cách đọc trống: nghe từ ấy như thường"
        status, answer = call("POST", "/api/readaloud/clip", {"voice": "fake:ngoc", "text": "Haruto", "readings": {"Hai kes": "x"}})
        assert status == 400 and answer["error"]
        assert call("GET", f"/api/books/{identifier}/readings", None) == (200, {"readings": [{"surface": "Haruto", "spoken": "Ha ru tô"}]})
        assert call("PUT", f"/api/books/{identifier}/readings", {"surface": "Haruto", "spoken": ""})[1] == {"readings": []}
        assert not (folder / "edits.json").exists(), "bỏ cách đọc cuối cùng: không còn thay đổi nào"
    finally:
        server.stop()


def test_a_producer_folding_the_edits_skips_the_readings(tmp_path: Path) -> None:
    from tests.test_webui_listen_and_sync import make_project

    project = make_project(tmp_path)
    report = book_edits.fold_edits(project, book_edits.validate({**shared.HEAD, "readings": {"Haruto": "Ha-ru-tô"}}))
    assert report["applied"] == 0 and report["skipped"] == 1
