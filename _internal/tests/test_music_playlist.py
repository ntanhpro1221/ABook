"""Nhạc nền cho sách nghe bằng "Nghe ngay" (webui/music_playlist.py, docs/LISTEN_ANYTHING.md mục 4): người nghe chọn một danh sách
phát của danh mục hay "Nhạc của tôi" cho cả cuốn; lựa chọn nằm ở lớp sửa (`music.playlist`), trình phát nhận hàng bài theo đúng
thứ tự trộn sẵn, mỗi bài một độ khuếch đại theo công thức Pha 4. Chưa chọn gì thì máy tự chọn danh sách hợp với cuốn bằng luật từ khoá
(`pick`), trùng khớp với bản Kotlin trên bộ ví dụ dùng chung tests/fixtures/playlist_picker/cases.json."""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote

import numpy as np
import pytest
import soundfile

from abook.webui import book_edits, music_plan, music_playlist
from abook.webui.music_catalog import MusicCatalog
from abook.webui.server import Server
from tests.test_music_catalog_and_select import TRACKS, _catalog_dir
from tests.catalog_signing import TEST_PUBLIC_KEY
from tests.test_text_books import IMPORTS
from tests.test_project_file import _app
from tests.test_webui_listen_and_sync import _request

TOKEN = {"X-Ebook-Token": "t"}
PICKER_CASES = json.loads((Path(__file__).parent / "fixtures" / "playlist_picker" / "cases.json").read_text(encoding="utf-8"))
# Luật chọn của mục lục thử: mặc định "calm", không từ khoá nào - cuốn thử nào cũng được chọn "calm" (hàng bài thật của danh mục thử).
CATALOGUE_PICKER = {"version": 1, "cap": 5, "title_weight": 12.0, "min_score": 4.0, "default": "calm", "order": ["calm", "battle"],
                    "playlists": {"calm": {"title": [], "text": {}}, "battle": {"title": [], "text": {"trận chiến": 1}}}}
CALM = ["https://x/calm2.mp3", "https://x/calm.mp3", "https://x/sad.mp3"]  # thứ tự trộn sẵn, không theo chữ cái
PLAYLISTS = [
    {"id": "calm", "name": "Êm  đềm", "description": "Cho truyện chậm.", "minutes": 10, "tracks": CALM},
    {"id": "battle", "name": "Hành động", "description": "", "minutes": 3, "tracks": ["https://x/battle.mp3"]},
    {"id": "Bad Id", "name": "x", "tracks": CALM},
    {"id": "calm", "name": "trùng mã", "tracks": CALM},
    {"id": "mine", "name": "trùng lựa chọn Nhạc của tôi", "tracks": CALM},
    {"id": "empty", "name": "không bài", "tracks": ["http://x/insecure.mp3", 7]},
    "không phải đối tượng",
]


def _cloud(root: Path, picker: dict | None = None) -> Path:
    return _catalog_dir(root, playlists=PLAYLISTS, **({"playlistPicker": picker} if picker is not None else {}))


# ---- danh mục ----------------------------------------------------------------------------------------------------------


def test_only_well_formed_playlists_of_the_catalogue_are_offered() -> None:
    kept = music_playlist.catalogue_playlists({"playlists": PLAYLISTS})
    assert [item["id"] for item in kept] == ["calm", "battle"]
    assert music_playlist.catalogue_playlists({"playlists": [{"id": "off", "name": "Tắt", "tracks": CALM}]}) == [], '"off" là tắt, không phải mã'
    assert kept[0] == {"id": "calm", "name": "Êm đềm", "description": "Cho truyện chậm.", "minutes": 10, "tracks": CALM}
    assert music_playlist.summaries(kept)[1] == {"id": "battle", "name": "Hành động", "description": "", "minutes": 3, "count": 1}
    assert music_playlist.catalogue_playlists({}) == [], "mục lục cũ chưa có danh sách phát"


def test_the_queue_keeps_the_shuffled_order_and_skips_what_this_machine_cannot_play(tmp_path: Path) -> None:
    catalog = MusicCatalog(tmp_path / "cache", str(_cloud(tmp_path / "cloud")), public_key=TEST_PUBLIC_KEY)
    links = music_playlist.links_of(catalog.playlists(), "calm")
    assert links == CALM and music_playlist.links_of(catalog.playlists(), "gone") == []
    info = catalog.lookup(links)
    queue = music_playlist.queue(links, info, available=lambda link: link != "https://x/calm.mp3")
    assert queue == [{"link": "https://x/calm2.mp3", "duration": 200.0}, {"link": "https://x/sad.mp3", "duration": 240.0}]
    assert music_playlist.queue(["https://x/khong-biet.mp3"], {}) == [{"link": "https://x/khong-biet.mp3", "duration": None}]


def test_looking_up_a_whole_playlist_fetches_every_shard_it_touches(tmp_path: Path) -> None:
    catalog = MusicCatalog(tmp_path / "cache", str(_cloud(tmp_path / "cloud")), public_key=TEST_PUBLIC_KEY)
    assert set(catalog.lookup(list(TRACKS))) == set(TRACKS)


# ---- máy tự chọn danh sách ---------------------------------------------------------------------------------------------------


def test_the_bundled_picker_is_the_reference_lexicon() -> None:
    assert music_playlist.bundled_picker() == PICKER_CASES["picker"]
    assert music_playlist.valid_picker(PICKER_CASES["picker"])


@pytest.mark.parametrize("case", PICKER_CASES["cases"], ids=lambda case: case["name"])
def test_pick_matches_the_shared_fixture(case: dict) -> None:
    picker = case["picker"] if "picker" in case else PICKER_CASES["picker"]
    assert music_playlist.pick(picker, case["title"], iter(case["chapters"])) == case["expect"]
    scores = music_playlist.pick_scores(picker, case["title"], case["chapters"])
    if case["scores"] is None:
        assert scores is None
    else:
        assert scores is not None and scores.keys() == case["scores"].keys()
        assert all(scores[code] == pytest.approx(value, abs=1e-9) for code, value in case["scores"].items())


@pytest.mark.parametrize("case", PICKER_CASES["selection"], ids=lambda case: case["name"])
def test_the_manifest_picker_is_used_only_when_valid_else_the_bundled_one(case: dict) -> None:
    picker, source = music_playlist.usable_picker(case["manifest"])
    assert source == case["source"]
    assert picker == (case["manifest"]["playlistPicker"] if source == "manifest" else music_playlist.bundled_picker())
    assert music_playlist.pick(picker, case["title"], case["chapters"]) == case["expect"]


def test_the_picker_reads_chapters_lazily_and_stops_once_it_has_enough_text() -> None:
    read: list[int] = []

    def chapters():
        for number in range(10):
            read.append(number)
            yield "Một câu tự đặt, chẳng có từ khoá nào cả. " * 60

    music_playlist.pick(music_playlist.bundled_picker(), "Sách thử", chapters())
    assert len(read) < 10


# ---- lớp sửa -------------------------------------------------------------------------------------------------------------


def test_the_choice_is_a_listener_edit_that_counts_dumps_and_merges() -> None:
    head = {"format": "abook-edits", "version": 1}
    edits = book_edits.validate({**head, "music": {"playlist": "calm"}})
    assert edits["music"] == {"playlist": "calm"} and book_edits.count_applied(edits) == 1
    assert book_edits.validate({**head, "music": {"playlist": music_playlist.MINE}})["music"]["playlist"] == "mine"
    for bad in ("", "Có dấu", "a" * 41, 7, None):
        with pytest.raises(book_edits.EditsError):
            book_edits.validate({**head, "music": {"playlist": bad}})
    dumped = json.loads(book_edits.dump(book_edits.validate({**head, "music": {"silenced": ["1:0"], "playlist": "calm", "levelDb": -24}})))
    assert list(dumped["music"]) == ["levelDb", "playlist", "silenced"]
    merged, report = book_edits.merge(book_edits.validate({**head, "music": {"playlist": "calm"}}),
                                      book_edits.validate({**head, "music": {"playlist": "mine"}}))
    assert merged["music"]["playlist"] == "calm" and report["conflicts"] == 1


# ---- máy chủ -------------------------------------------------------------------------------------------------------------


def _text_book_server(tmp_path: Path, picker: dict | None = CATALOGUE_PICKER):
    app = _app(tmp_path / "studio", tmp_path / "thu_vien")
    app._music_catalog = MusicCatalog(tmp_path / "music_cache", str(_cloud(tmp_path / "cloud", picker)), public_key=TEST_PUBLIC_KEY)
    added = app.add_text_book(str(IMPORTS / "epub3.epub"))
    return app, added["id"], Server(app, port=0).start()


def _call(server, method: str, path: str, body=None):
    status, data, _ = _request(server.port, method, path, headers=TOKEN, body=body)
    return status, json.loads(data) if data else None


def test_a_text_book_plays_the_chosen_playlist_in_order_under_the_voice(tmp_path: Path) -> None:
    app, book, server = _text_book_server(tmp_path)
    try:
        status, menu = _call(server, "GET", "/api/music/playlists")
        assert status == 200 and menu["error"] == "" and menu["mine"] == 0
        assert [item["id"] for item in menu["playlists"]] == ["calm", "battle"] and "tracks" not in menu["playlists"][0]
        status, view = _call(server, "PUT", f"/api/books/{book}/music", {"playlist": "calm"})
        assert status == 200 and view["playlist"] == "calm" and view["hasMusic"] is False
        assert book_edits.load(app._listenable(book))["music"] == {"playlist": "calm"}
        _status, again = _call(server, "GET", f"/api/books/{book}/music")
        assert again["playlist"] == "calm" and "playlistAuto" not in again
        status, queue = _call(server, "GET", f"/api/books/{book}/music/playlist")
        assert status == 200 and queue["playlist"] == "calm" and queue["error"] == "" and "playlistAuto" not in queue
        assert [track["link"] for track in queue["tracks"]] == CALM
        first = queue["tracks"][0]
        assert first["src"] == "/api/music/track?link=" + quote(first["link"], safe="") and first["duration"] == 200.0
        # Giọng "Nghe ngay" cân về -20 LUFS như giọng Studio: cùng công thức với nhạc theo cảnh (danh mục thử chưa có lufs).
        assert all(track["gainDb"] == music_plan.cue_gain_db(-20.0, None, None) for track in queue["tracks"])
        status, bad = _call(server, "PUT", f"/api/books/{book}/music", {"playlist": "Không có"})
        assert status == 400 and bad["error"]
        _status, view = _call(server, "PUT", f"/api/books/{book}/music", {"playlist": None})
        assert view["playlistAuto"] is True and "playlist" not in (book_edits.load(app._listenable(book)).get("music") or {})
    finally:
        server.stop()


def test_a_text_book_with_no_choice_gets_the_machines_pick_until_the_listener_chooses_or_turns_it_off(tmp_path: Path) -> None:
    app, book, server = _text_book_server(tmp_path)
    try:
        # chưa chọn gì: máy chọn (luật của mục lục thử có mặc định "calm"), hàng bài và màn nhạc nói rõ là máy chọn
        status, queue = _call(server, "GET", f"/api/books/{book}/music/playlist")
        assert status == 200 and queue["playlist"] == "calm" and queue["playlistAuto"] is True
        assert [track["link"] for track in queue["tracks"]] == CALM
        _status, view = _call(server, "GET", f"/api/books/{book}/music")
        assert view["playlist"] == "calm" and view["playlistAuto"] is True
        # kết quả đệm theo (mã sách, nguồn luật, version): lần sau không chọn lại
        calls: list[str] = []
        real = music_playlist.pick
        music_playlist.pick = lambda *args: calls.append("pick") or real(*args)  # type: ignore[assignment]
        try:
            _call(server, "GET", f"/api/books/{book}/music/playlist")
            _call(server, "GET", f"/api/books/{book}/music")
        finally:
            music_playlist.pick = real  # type: ignore[assignment]
        assert calls == []
        # "Tắt" (off) là một lựa chọn, không phải mã danh sách: không nhạc, không máy chọn
        status, view = _call(server, "PUT", f"/api/books/{book}/music", {"playlist": "off"})
        assert status == 200 and view["playlist"] == "off" and "playlistAuto" not in view
        assert book_edits.load(app._listenable(book))["music"] == {"playlist": "off"}
        _status, queue = _call(server, "GET", f"/api/books/{book}/music/playlist")
        assert queue["playlist"] is None and queue["tracks"] == [] and "playlistAuto" not in queue
        _status, view = _call(server, "GET", f"/api/books/{book}/music")
        assert view["playlist"] == "off" and "playlistAuto" not in view
        # null xoá khoá: máy chọn lại
        _status, view = _call(server, "PUT", f"/api/books/{book}/music", {"playlist": None})
        assert "playlist" not in (book_edits.load(app._listenable(book)).get("music") or {})
        assert view["playlist"] == "calm" and view["playlistAuto"] is True, "lời đáp của lần bỏ lựa chọn đã là màn của máy chọn"
        assert _call(server, "GET", f"/api/books/{book}/music/playlist")[1]["playlistAuto"] is True
    finally:
        server.stop()


def test_without_a_downloaded_catalogue_the_machine_picks_with_the_bundled_rules(tmp_path: Path) -> None:
    app = _app(tmp_path / "studio", tmp_path / "thu_vien")
    app._music_catalog = MusicCatalog(tmp_path / "music_cache", str(tmp_path / "chua_co_danh_muc"))  # máy mới, chưa có mạng
    added = app.add_text_book(str(IMPORTS / "epub3.epub"))
    view = app.music_view(added["id"])
    assert view["playlistAuto"] is True and view["playlist"] in music_playlist.bundled_picker()["order"]
    queue = app.music_playlist_queue(added["id"])
    assert queue["playlist"] == view["playlist"] and queue["tracks"] == [] and queue["error"] != "", "tên danh sách có, bài chưa tải được"


def test_a_picker_the_catalogue_ships_broken_falls_back_to_the_bundled_one(tmp_path: Path) -> None:
    app, book, server = _text_book_server(tmp_path, {**CATALOGUE_PICKER, "default": "khong_co_trong_danh_muc"})
    try:
        _status, view = _call(server, "GET", f"/api/books/{book}/music")
        assert view["playlistAuto"] is True and view["playlist"] in music_playlist.bundled_picker()["order"]
    finally:
        server.stop()


def test_a_book_without_a_usable_picker_plays_nothing_until_chosen(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(music_playlist, "bundled_picker", lambda: None)
    app, book, server = _text_book_server(tmp_path, None)
    try:
        _status, queue = _call(server, "GET", f"/api/books/{book}/music/playlist")
        assert queue["playlist"] is None and queue["tracks"] == [] and "playlistAuto" not in queue
        assert "playlist" not in _call(server, "GET", f"/api/books/{book}/music")[1]
    finally:
        server.stop()


def test_a_playlist_the_catalogue_no_longer_has_plays_nothing(tmp_path: Path) -> None:
    app, book, server = _text_book_server(tmp_path)
    try:
        book_edits.set_music(app._listenable(book), {"playlist": "gone"})
        _status, queue = _call(server, "GET", f"/api/books/{book}/music/playlist")
        assert queue["playlist"] == "gone" and queue["tracks"] == [] and queue["error"] == ""
    finally:
        server.stop()


def test_my_music_plays_oldest_first_from_this_machines_store(tmp_path: Path) -> None:
    app, book, server = _text_book_server(tmp_path)
    try:
        rate = 8000
        for index, frequency in enumerate((220, 330)):
            wav = tmp_path / f"bai{index}.wav"
            soundfile.write(wav, (0.3 * np.sin(2 * np.pi * frequency * np.arange(rate * 2) / rate)).astype("float32"), rate)
            app.my_music.import_file(wav)
        _status, menu = _call(server, "GET", "/api/music/playlists")
        assert menu["mine"] == 2
        _call(server, "PUT", f"/api/books/{book}/music", {"playlist": "mine"})
        _status, queue = _call(server, "GET", f"/api/books/{book}/music/playlist")
        expected = [entry["link"] for entry in reversed(app.my_music.entries())]
        assert [track["link"] for track in queue["tracks"]] == expected
        digest = music_plan.local_hash(expected[0])
        assert queue["tracks"][0]["src"] == f"/api/music/local/{digest}/file"
        assert all(isinstance(track["gainDb"], float) and track["gainDb"] <= 0 for track in queue["tracks"])
    finally:
        server.stop()


def test_a_book_with_its_makers_music_keeps_the_scene_music(tmp_path: Path) -> None:
    from tests.book_edits_fixtures import BASE

    app = _app(tmp_path / "studio", tmp_path / "thu_vien")
    app._music_catalog = MusicCatalog(tmp_path / "music_cache", str(_cloud(tmp_path / "cloud")), public_key=TEST_PUBLIC_KEY)
    folder = tmp_path / "sach"
    import shutil

    shutil.copytree(BASE, folder)
    book_edits.set_music(folder, {"playlist": "calm"})
    app._listenable = lambda value: folder  # type: ignore[method-assign]
    assert app.music_playlist_queue("sach")["tracks"] == []


def test_turning_off_the_machines_pick_in_settings_silences_only_the_books_with_no_choice(tmp_path: Path) -> None:
    app, book, server = _text_book_server(tmp_path)
    try:
        app.preferences.update({"autoMusic": False})
        _status, view = _call(server, "GET", f"/api/books/{book}/music")
        assert "playlist" not in view and "playlistAuto" not in view and view["autoOff"] is True
        _status, queue = _call(server, "GET", f"/api/books/{book}/music/playlist")
        assert queue["playlist"] is None and queue["tracks"] == []
        # cuốn người nghe đã chọn nhạc thì vẫn phát
        _status, view = _call(server, "PUT", f"/api/books/{book}/music", {"playlist": "calm"})
        assert view["playlist"] == "calm" and "autoOff" not in view
        assert [track["link"] for track in _call(server, "GET", f"/api/books/{book}/music/playlist")[1]["tracks"]] == CALM
        # bật lại: máy chọn như trước
        app.preferences.update({"autoMusic": True})
        _status, view = _call(server, "PUT", f"/api/books/{book}/music", {"playlist": None})
        assert view["playlistAuto"] is True and "autoOff" not in view
        # đổi qua API cài đặt: chỉ nhận đúng true/false
        assert _call(server, "PUT", "/api/preferences", {"autoMusic": "tắt"})[1]["autoMusic"] is True
        assert _call(server, "PUT", "/api/preferences", {"autoMusic": False})[1]["autoMusic"] is False
    finally:
        server.stop()
