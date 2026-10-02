"""Phát sang loa / TV (DLNA, webui/cast.py) với loa giả lập scripts/fake_renderer.py - 01-10: chủ sách không có loa
hay TV để thử ("giả lập hay gì đó đi"). Loa giả tải audio thật qua HTTP và cho vị trí chạy theo đồng hồ (nhanh gấp
`speed` lần), nên các bài thử đi trọn vòng: tìm -> đưa chương -> thiết bị tải đúng file -> tự sang chương sau."""
from __future__ import annotations

import importlib.util
import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

from abook.webui import cast
from abook.webui.actions import FakeRunner
from abook.webui.cast import CastError, CastMedia, CastPlayers
from abook.webui.library import Preferences, book_id
from abook.webui.listening import Listening
from abook.webui.server import App, Server
from tests.test_webui_listen_and_sync import _request, _sync_request, make_project

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("fake_renderer", ROOT / "scripts/fake_renderer.py")
fake_renderer = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fake_renderer)
FakeRenderer = fake_renderer.FakeRenderer
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _until(check: Callable[[], Any], seconds: float = 8.0) -> Any:
    deadline = time.time() + seconds
    while time.time() < deadline:
        value = check()
        if value:
            return value
        time.sleep(0.05)
    raise AssertionError("hết giờ chờ")


@contextmanager
def _renderer(name: str = "Loa phòng khách", **options: Any) -> Iterator[Any]:
    device = FakeRenderer(name, **options).start()
    try:
        yield device
    finally:
        device.stop()


@pytest.fixture()
def fast(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cast, "PLAYING_POLL", 0.15)
    monkeypatch.setattr(cast, "IDLE_POLL", 0.2)
    monkeypatch.setattr(cast, "GRACE_SECONDS", 1.0)


class Book:
    """Một cuốn ba chương nghe được (chương 4 chưa thu), file audio thật trên đĩa; ghi lại mọi lần lưu chỗ nghe."""

    def __init__(self, folder: Path, seconds: float = 10.0) -> None:
        self.seconds = seconds
        self.files = {}
        for chapter in (1, 2, 3):
            path = folder / f"{chapter:05d}.mp3"
            path.write_bytes(bytes([chapter]) * (50_000 + chapter))
            self.files[chapter] = path
        self.saved: list[tuple[str, int, float, float]] = []

    def view(self, value: str) -> dict[str, Any]:
        if value != "sach":
            raise CastError("không có cuốn này")
        chapters = [{"id": chapter, "title": f"Chương {chapter}", "fullTitle": f"Chương {chapter}: Phần {chapter}",
                     "duration": self.seconds, "available": True} for chapter in (1, 2, 3)]
        return {"title": "Sách thử", "chapters": [*chapters, {"id": 4, "title": "Chương 4", "duration": 0.0,
                                                               "available": False}]}

    def audio(self, _value: str, chapter: int) -> Path | None:
        return self.files.get(chapter)

    def save(self, value: str, chapter: int, seconds: float, duration: float) -> None:
        self.saved.append((value, chapter, round(seconds, 1), duration))


@contextmanager
def _players(book: Book, device: Any) -> Iterator[CastPlayers]:
    players = CastPlayers(book.view, book.audio, book.save, media=CastMedia("127.0.0.1"),
                          find=lambda: cast.search(0.4, addresses=[], targets=[device.ssdp_address]))
    try:
        yield players
    finally:
        players.close()


def _found(players: CastPlayers) -> dict[str, Any]:
    players.scan()
    return _until(lambda: next(iter(players.view()), None))


def _now(players: CastPlayers) -> dict[str, Any]:
    return players.view()[0]


def _calls(device: Any, name: str) -> list[dict[str, str]]:
    return [arguments for action, arguments in list(device.actions) if action == name]


# ---- tìm và đọc thiết bị --------------------------------------------------------------------------------------------


def test_a_renderer_answers_the_search_and_describes_itself() -> None:
    with _renderer() as device:
        assert cast.search(0.4, addresses=[], targets=[device.ssdp_address]) == [(device.location, "127.0.0.1")]
        found = cast.describe(device.location, "127.0.0.1")
        assert found is not None and found.name == "Loa phòng khách" and found.kind == "speaker"
        assert found.av_url.endswith("/AVTransport/control") and found.av_type == fake_renderer.AVT
        assert found.rc_url.endswith("/RenderingControl/control")
        assert len(found.id) == 12 and found.id == cast.describe(device.location, "127.0.0.1").id
    with _renderer("[TV] Samsung Q60 Series (55)") as device:
        assert cast.describe(device.location, "127.0.0.1").kind == "tv"


def test_a_windows_computer_that_renders_shows_as_a_media_player(monkeypatch: pytest.MonkeyPatch) -> None:
    """Gặp thật trong mạng nhà chủ sách 01-10: một máy Windows bật điều khiển Windows Media Player từ xa."""
    with _renderer("QuangNgocThuy") as device:
        described = device.description()
        monkeypatch.setattr(device, "description", lambda: described.replace(
            "<manufacturer>ABook</manufacturer><modelName>Fake renderer</modelName>",
            "<manufacturer>Microsoft Corporation</manufacturer><modelName>Windows Digital Media Renderer</modelName>"))
        assert cast.describe(device.location, "127.0.0.1").kind == "media", "không lẫn với máy tính có ABook"


def test_a_description_counts_only_at_the_address_that_answered(monkeypatch: pytest.MonkeyPatch) -> None:
    """Trả lời SSDP là dữ liệu từ mạng LAN: một máy lạ không được khiến máy này gọi tới máy khác hay 127.0.0.1."""
    with _renderer() as device:
        assert cast.describe(device.location, "127.0.0.2") is None
        assert cast.describe(device.location.replace("http:", "https:"), "127.0.0.1") is None
        described = device.description()
        monkeypatch.setattr(device, "description", lambda: described.replace(
            "<specVersion>", "<URLBase>http://10.9.9.9:80/</URLBase><specVersion>"))
        assert cast.describe(device.location, "127.0.0.1") is None, "địa chỉ điều khiển trỏ sang máy khác"
        monkeypatch.setattr(device, "description", lambda: (
            '<?xml version="1.0"?><!DOCTYPE r [<!ENTITY a "aaaaaaaaaa">]><root>&a;&a;</root>'))
        with pytest.raises(CastError):
            cast.describe(device.location, "127.0.0.1")


def test_only_answers_from_renderers_count() -> None:
    renderer = (b"HTTP/1.1 200 OK\r\nST: urn:schemas-upnp-org:device:MediaRenderer:1\r\n"
                b"LOCATION: http://192.168.0.9:49152/d.xml\r\n\r\n")
    assert cast._location(renderer) == "http://192.168.0.9:49152/d.xml"
    assert cast._location(renderer.replace(b"MediaRenderer", b"InternetGatewayDevice")) == ""
    assert cast._location(b"NOTIFY * HTTP/1.1\r\nNT: urn:schemas-upnp-org:device:MediaRenderer:1\r\n\r\n") == ""
    assert cast._location(b"\xff\xfe garbage") == ""


def test_upnp_times_read_both_ways() -> None:
    assert cast.clock(3725.4) == "1:02:05" and cast.clock(-3) == "0:00:00"
    assert cast.seconds_of("1:02:05") == 3725 and cast.seconds_of("0:00:07.500") == 7.5
    assert cast.seconds_of("0:00:07.1/4") == 7.25
    assert cast.seconds_of("NOT_IMPLEMENTED") == 0 and cast.seconds_of("") == 0


# ---- cổng audio ---------------------------------------------------------------------------------------------------


def test_the_media_port_serves_only_what_was_shared(tmp_path: Path) -> None:
    media = CastMedia("127.0.0.1")
    try:
        file = tmp_path / "chuong.mp3"
        file.write_bytes(bytes(range(256)) * 4)
        url = media.share(file, "127.0.0.1")
        assert url.startswith("http://127.0.0.1:") and url.endswith(".mp3")
        with OPENER.open(urllib.request.Request(url, headers={"Range": "bytes=10-19"})) as response:
            assert response.status == 206 and response.read() == bytes(range(10, 20))
            assert response.headers["Content-Range"] == "bytes 10-19/1024"
            assert response.headers["Content-Type"] == "audio/mpeg"
            assert "DLNA.ORG_OP=01" in response.headers["contentFeatures.dlna.org"]
            assert response.headers["transferMode.dlna.org"] == "Streaming"
        with OPENER.open(url) as response:
            assert response.read() == file.read_bytes()
        with OPENER.open(urllib.request.Request(url, method="HEAD")) as response:
            assert response.headers["Content-Length"] == "1024" and response.read() == b""
        base = url.rsplit("/", 1)[0]
        for wrong in (f"{base}/{'A' * 22}.mp3", f"{base}/../chuong.mp3", url.replace("/c/", "/x/")):
            with pytest.raises(urllib.error.HTTPError) as error:
                OPENER.open(wrong)
            assert error.value.code == 404
        assert media.share(file, "127.0.0.1") != url, "mỗi lần đưa một mã mới"
    finally:
        media.close()


def test_errors_from_the_renderer_read_as_sentences() -> None:
    with _renderer() as device:
        found = cast.describe(device.location, "127.0.0.1")
        with pytest.raises(CastError) as error:
            cast.soap(found.av_url, found.av_type, "Seek", [("InstanceID", 0), ("Unit", "REL_TIME"), ("Target", "0:00:05")])
        assert error.value.code == 701 and "chưa sẵn sàng" in str(error.value)
        device.stop()
        with pytest.raises(CastError) as error:
            cast.soap(found.av_url, found.av_type, "Play", [("InstanceID", 0), ("Speed", "1")], timeout=2)
        assert "không trả lời" in str(error.value)


# ---- phát ---------------------------------------------------------------------------------------------------------


def test_casting_plays_the_chapter_and_moves_on_by_itself(tmp_path: Path, fast: None) -> None:
    book = Book(tmp_path)
    with _renderer(speed=5.0) as device, _players(book, device) as players:
        speaker = _found(players)
        assert speaker["via"] == "cast" and speaker["bookId"] == "" and speaker["stream"] and speaker["kind"] == "speaker"
        players.send(speaker["device"], {"action": "load", "bookId": "sach", "chapterId": 1, "seconds": 0.0})
        assert [action for action, _ in device.actions][:2] == ["SetAVTransportURI", "Play"]
        first = _calls(device, "SetAVTransportURI")[0]
        assert first["CurrentURI"].startswith("http://127.0.0.1:") and "/c/" in first["CurrentURI"]
        metadata = first["CurrentURIMetaData"]
        assert "Chương 1: Phần 1" in metadata and "Sách thử" in metadata and 'duration="0:00:10.000"' in metadata
        fetched = _until(lambda: device.fetches and device.fetches[0])
        assert fetched["status"] in (200, 206) and fetched["type"] == "audio/mpeg"
        assert fetched["bytes"] == book.files[1].stat().st_size, "thiết bị tải đúng file chương từ máy này"
        playing = _until(lambda: (now := _now(players))["playing"] and not now["buffering"] and now)
        assert playing["bookId"] == "sach" and playing["chapterId"] == 1 and playing["chapterTitle"] == "Chương 1: Phần 1"

        # Hết chương 1 (10 giây, loa chạy nhanh gấp 5): tự sang chương 2, chương 1 ghi là đã nghe hết.
        _until(lambda: _now(players)["chapterId"] == 2, 10)
        assert ("sach", 1, 10.0, 10.0) in book.saved
        assert device.uri != first["CurrentURI"] and device.state in ("PLAYING", "STOPPED")
        # Chương cuối hết thì thôi: thiết bị rảnh, chỗ nghe ở cuối chương 3.
        players.send(speaker["device"], {"action": "jump", "chapterId": 3, "seconds": 0.0})
        _until(lambda: _now(players)["bookId"] == "", 10)
        assert ("sach", 3, 10.0, 10.0) in book.saved


def test_resuming_mid_chapter_seeks_once_the_renderer_plays(tmp_path: Path, fast: None) -> None:
    """Phần lớn TV chỉ tua được khi đã chạy (loa giả trả lỗi 701 nếu tua sớm): phát trước, đợi PLAYING, rồi mới tua."""
    book = Book(tmp_path)
    with _renderer() as device, _players(book, device) as players:
        speaker = _found(players)
        players.send(speaker["device"], {"action": "load", "bookId": "sach", "chapterId": 2, "seconds": 6.0})
        names = [action for action, _ in device.actions]
        assert names.index("Seek") > names.index("Play")
        assert _calls(device, "Seek")[0] == {"InstanceID": "0", "Unit": "REL_TIME", "Target": "0:00:06"}
        assert device.position() >= 6 and _now(players)["position"] >= 6
        # App đóng: thiết bị dừng hẳn (cổng audio sắp đóng), chỗ nghe lưu ở chỗ dừng.
        players.close()
        assert device.state == "STOPPED" and book.saved[-1][:2] == ("sach", 2) and book.saved[-1][2] >= 6


def test_pause_play_skip_and_chapters_on_the_renderer(tmp_path: Path, fast: None) -> None:
    with _renderer() as device, _players(Book(tmp_path, seconds=30.0), device) as players:
        speaker = _found(players)["device"]
        players.send(speaker, {"action": "load", "bookId": "sach", "chapterId": 1, "seconds": 0.0})
        _until(lambda: _now(players)["playing"] and not _now(players)["buffering"])
        players.send(speaker, {"action": "pause"})
        assert device.state == "PAUSED_PLAYBACK" and not _now(players)["playing"]
        players.send(speaker, {"action": "toggle"})
        assert device.state == "PLAYING" and _now(players)["playing"]
        before = device.position()
        players.send(speaker, {"action": "skip", "seconds": 15})
        assert 14 <= device.position() - before <= 17
        players.send(speaker, {"action": "skip", "seconds": 60})  # quá cuối chương: sang chương sau
        assert len(_calls(device, "SetAVTransportURI")) == 2 and _now(players)["chapterId"] == 2
        players.send(speaker, {"action": "previous"})
        assert _now(players)["chapterId"] == 1
        players.send(speaker, {"action": "rate", "rate": 1.0})
        with pytest.raises(CastError) as error:
            players.send(speaker, {"action": "rate", "rate": 1.5})
        assert str(error.value) == "Loa phòng khách: loa, TV chỉ phát ở tốc độ 1x"
        with pytest.raises(CastError):
            players.send(speaker, {"action": "jump", "chapterId": 4, "seconds": 0.0})  # chương chưa thu


def test_a_renderer_without_pause_stops_and_comes_back_to_the_same_place(tmp_path: Path, fast: None) -> None:
    with _renderer("TV phòng ngủ", pause=False) as device, _players(Book(tmp_path, seconds=30.0), device) as players:
        speaker = _found(players)
        assert speaker["kind"] == "tv"
        players.send(speaker["device"], {"action": "load", "bookId": "sach", "chapterId": 1, "seconds": 0.0})
        _until(lambda: _now(players)["position"] >= 1.5)
        players.send(speaker["device"], {"action": "pause"})
        assert _calls(device, "Stop") and device.state == "STOPPED"
        time.sleep(0.6)  # vài lượt hỏi thấy STOPPED: là người dùng dừng, không phải hết chương
        now = _now(players)
        assert now["chapterId"] == 1 and not now["playing"] and now["position"] >= 1.5
        players.send(speaker["device"], {"action": "play"})
        assert len(_calls(device, "SetAVTransportURI")) == 2
        assert cast.seconds_of(_calls(device, "Seek")[-1]["Target"]) >= 1
        _until(lambda: _now(players)["playing"])


def test_another_app_taking_the_renderer_ends_the_session(tmp_path: Path, fast: None) -> None:
    with _renderer() as device, _players(Book(tmp_path, seconds=30.0), device) as players:
        speaker = _found(players)
        players.send(speaker["device"], {"action": "load", "bookId": "sach", "chapterId": 1, "seconds": 0.0})
        _until(lambda: _now(players)["playing"])
        device.takeover("http://192.168.0.5:8200/MediaItems/22.mp3")
        _until(lambda: _now(players)["bookId"] == "")
        with pytest.raises(CastError):
            players.send(speaker["device"], {"action": "pause"})


def test_a_renderer_that_keeps_its_position_to_itself_is_followed_by_the_clock(tmp_path: Path, fast: None) -> None:
    with _renderer(report_position=False) as device, _players(Book(tmp_path, seconds=6.0), device) as players:
        speaker = _found(players)
        players.send(speaker["device"], {"action": "load", "bookId": "sach", "chapterId": 1, "seconds": 0.0})
        _until(lambda: _now(players)["position"] >= 2)
        _until(lambda: _now(players)["chapterId"] == 2, 10)


# ---- qua app ------------------------------------------------------------------------------------------------------


def test_the_app_lists_a_speaker_and_casts_a_real_chapter(tmp_path: Path, fast: None) -> None:
    root = tmp_path / "thu_vien"
    root.mkdir()
    project = make_project(root)
    preferences = Preferences(tmp_path / "prefs" / "preferences.json")
    preferences.update({"libraryRoot": str(root)})
    listening = Listening(tmp_path / "prefs" / "listening.json")
    app = App(preferences=preferences, runner=FakeRunner(), token="t", listening=listening)
    headers = {"X-Ebook-Token": "t"}
    with _renderer("Loa bếp") as device:
        app.cast.find = lambda: cast.search(0.4, addresses=[], targets=[device.ssdp_address])
        app.cast.media = CastMedia("127.0.0.1")
        ui = Server(app, port=0).start()
        try:
            def speakers() -> list[dict[str, Any]]:
                _status, data, _ = _request(ui.port, "GET", "/api/remote", headers=headers)
                return [phone for phone in json.loads(data)["phones"] if phone["via"] == "cast"]

            status, _data, _ = _request(ui.port, "POST", "/api/cast/scan", headers=headers)
            assert status == 200
            speaker = _until(speakers)[0]
            assert speaker["name"] == "Loa bếp" and speaker["bookId"] == "" and not speaker["known"]
            identifier = book_id(project)
            status, data, _ = _request(ui.port, "POST", f"/api/remote/{speaker['device']}", headers=headers,
                                       body={"action": "load", "bookId": identifier, "chapterId": 1, "seconds": 0})
            assert status == 200 and json.loads(data)["id"]
            fetched = _until(lambda: device.fetches and device.fetches[0])
            assert fetched["bytes"] == (project / "output" / "chapters" / "00001_645.mp3").stat().st_size
            playing = _until(lambda: [item for item in speakers() if item["playing"] and not item["buffering"]])[0]
            assert playing["bookId"] == identifier and playing["known"] and playing["localBookId"] == identifier
            assert playing["chapterId"] == 1

            status, data, _ = _request(ui.port, "POST", f"/api/remote/{speaker['device']}", headers=headers,
                                       body={"action": "jump", "chapterId": 2, "seconds": 0})
            assert status == 409 and json.loads(data)["error"].startswith("Loa bếp: ")
            status, _data, _ = _request(ui.port, "POST", f"/api/remote/{speaker['device']}", headers=headers,
                                        body={"action": "pause"})
            assert status == 200 and device.state == "PAUSED_PLAYBACK"
            _until(lambda: (listening.get(identifier).get("last") or {}).get("chapterId") == 1)
        finally:
            ui.stop()
            app.close()


def test_a_paired_phone_sees_and_drives_the_speakers_of_this_computer(tmp_path: Path, fast: None) -> None:
    """Điện thoại đã ghép điều khiển loa / TV QUA máy tính (GET/POST /sync/v1/cast): máy tính phục vụ audio, giữ chỗ nghe."""
    root = tmp_path / "thu_vien"
    root.mkdir()
    project = make_project(root)
    preferences = Preferences(tmp_path / "prefs" / "preferences.json")
    preferences.update({"libraryRoot": str(root)})
    app = App(preferences=preferences, runner=FakeRunner(), token="t", listening=Listening(tmp_path / "prefs" / "l.json"))
    app.sync_host, app.sync_port = "127.0.0.1", 0
    with _renderer("TV phòng khách") as device:
        app.cast.find = lambda: cast.search(0.4, addresses=[], targets=[device.ssdp_address])
        app.cast.media = CastMedia("127.0.0.1")
        app.set_sync(True)
        try:
            port = app.sync_server.port
            status, _data, _ = _sync_request(port, "GET", "/sync/v1/cast")
            assert status == 401, "chỉ thiết bị đã ghép mới thấy loa / TV của máy này"
            code = app.devices.start_pairing()["code"]
            _status, data, _ = _sync_request(port, "POST", "/sync/v1/pair", body={"code": code, "device": "Pixel"})
            token = json.loads(data)["token"]

            def renderers() -> list[dict[str, Any]]:
                _status, data, _ = _sync_request(port, "GET", "/sync/v1/cast", token)
                return json.loads(data)["renderers"]

            app.cast.scan()
            tv = _until(renderers)[0]
            assert tv["name"] == "TV phòng khách" and tv["kind"] == "tv" and tv["state"] is None and tv["stream"]
            status, data, _ = _sync_request(port, "POST", f"/sync/v1/cast/{tv['id']}", token,
                                       body={"action": "load", "bookId": book_id(project), "chapterId": 1, "seconds": 0})
            assert status == 200 and json.loads(data)["id"]
            _until(lambda: device.fetches)
            playing = _until(lambda: [item for item in renderers() if item["state"] and item["state"]["playing"]])[0]
            assert playing["state"]["bookId"] == book_id(project) and playing["state"]["chapterId"] == 1
            status, data, _ = _sync_request(port, "POST", f"/sync/v1/cast/{tv['id']}", token, body={"action": "rate", "rate": 2})
            assert status == 409 and "1x" in json.loads(data)["error"]
            status, _data, _ = _sync_request(port, "POST", "/sync/v1/cast/0123456789ab", token, body={"action": "pause"})
            assert status == 404
            status, _data, _ = _sync_request(port, "POST", f"/sync/v1/cast/{tv['id']}", token, body={"action": "format"})
            assert status == 400
        finally:
            app.close()
