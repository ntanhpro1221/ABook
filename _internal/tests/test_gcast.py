"""Phát sang Chromecast / Google TV / loa Nest (Google Cast, webui/gcast.py) với thiết bị giả
scripts/fake_cast_receiver.py - 02-10. Thiết bị giả nghe CASTV2 qua TLS thật trên 127.0.0.1, trả lời mDNS ở một cổng UDP
riêng, TẢI file chương qua HTTP (không bao giờ giải mã hay phát audio) và cho vị trí chạy theo đồng hồ (nhanh gấp `speed`
lần). Bài thử đi trọn vòng như test_cast.py (DLNA): tìm -> mở ứng dụng -> LOAD -> thiết bị tải đúng file -> tự sang chương
sau; cộng phần riêng của Cast: khung tin, mDNS, bị chiếm máy, thiết bị tắt, đóng app trả máy."""
from __future__ import annotations

import importlib.util
import json
import socket
import struct
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

from abook.webui import cast, gcast
from abook.webui.actions import FakeRunner
from abook.webui.cast import CastError, CastMedia, CastPlayers
from abook.webui.library import Preferences, book_id
from abook.webui.listening import Listening
from abook.webui.server import App, Server
from tests.test_cast import Book, _now, _until
from tests.test_webui_listen_and_sync import _request, _sync_request, make_project

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("fake_cast_receiver", ROOT / "scripts/fake_cast_receiver.py")
fake_cast_receiver = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fake_cast_receiver)
FakeCastReceiver = fake_cast_receiver.FakeCastReceiver


@contextmanager
def _receiver(name: str = "Loa Nest phòng khách", **options: Any) -> Iterator[Any]:
    options.setdefault("duration", 10.0)  # bằng độ dài chương của Book
    device = FakeCastReceiver(name, **options).start()
    try:
        yield device
    finally:
        device.stop()


@pytest.fixture()
def fast(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cast, "PLAYING_POLL", 0.15)
    monkeypatch.setattr(cast, "IDLE_POLL", 0.2)
    monkeypatch.setattr(cast, "GRACE_SECONDS", 1.0)
    monkeypatch.setattr(gcast, "HEARTBEAT_SECONDS", 0.3)
    monkeypatch.setattr(gcast, "STATUS_SECONDS", 0.3)
    monkeypatch.setattr(gcast, "DEAD_SECONDS", 1.2)
    monkeypatch.setattr(gcast, "RECONNECT_SECONDS", 0.3)


def _google(device: Any) -> Any:
    return lambda: gcast.discover(0.4, addresses=[], targets=[device.mdns_address])


@contextmanager
def _players(book: Book, device: Any) -> Iterator[CastPlayers]:
    players = CastPlayers(book.view, book.audio, book.save, media=CastMedia("127.0.0.1"), find=list,
                          find_google=_google(device))
    try:
        yield players
    finally:
        players.close()


def _found(players: CastPlayers) -> dict[str, Any]:
    players.scan()
    return _until(lambda: next(iter(players.view()), None))


def _names(device: Any) -> list[str]:
    return [action for action, _ in list(device.actions)]


def _play(players: CastPlayers, speaker: dict[str, Any], chapter: int = 1, seconds: float = 0.0) -> None:
    players.send(speaker["device"], {"action": "load", "bookId": "sach", "chapterId": chapter, "seconds": seconds})


# ---- khung tin ------------------------------------------------------------------------------------------------------

PING = ("0800120873656e6465722d301a0a72656365697665722d30222775726e3a782d636173743a636f6d2e676f6f676c652e636173742e7470"
        "2e6865617274626561742800320f7b2274797065223a2250494e47227d")


def test_a_cast_message_is_encoded_byte_for_byte() -> None:
    message = gcast.encode("sender-0", "receiver-0", gcast.NS_HEARTBEAT, '{"type":"PING"}')
    assert message.hex() == PING
    assert gcast.frame(message) == bytes.fromhex("00000054" + PING) and len(message) == 0x54
    # Chuỗi dài hơn 127 byte: độ dài là varint hai byte.
    long = gcast.encode("a", "b", "c", "x" * 200)
    assert long.endswith(b"\x32\xc8\x01" + b"x" * 200)


def test_a_cast_message_decodes_and_skips_what_it_does_not_know() -> None:
    decoded = gcast.decode(bytes.fromhex(PING))
    assert (decoded.source, decoded.destination, decoded.namespace, decoded.payload) == (
        "sender-0", "receiver-0", gcast.NS_HEARTBEAT, '{"type":"PING"}')
    extra = (b"\x3a\x03abc"  # 7 payload_binary
             b"\x48\x96\x01"  # 9: varint
             b"\x55\x01\x02\x03\x04"  # 10: fixed32
             b"\x59" + bytes(8))  # 11: fixed64
    assert gcast.decode(extra + bytes.fromhex(PING)).payload == '{"type":"PING"}'
    assert gcast.decode(bytes.fromhex(PING) + extra).namespace == gcast.NS_HEARTBEAT
    binary = b"\x08\x00\x12\x01a\x1a\x01b\x22\x01c\x28\x01\x3a\x02xy"  # payload_type BINARY: không có chữ
    assert gcast.decode(binary).payload == ""
    for broken in (b"\x12\x05ab", b"\x12", b"\x0b", b"\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\x01"):
        with pytest.raises(CastError):
            gcast.decode(broken)


def test_frames_are_cut_from_the_stream_and_oversize_ones_are_refused() -> None:
    first, second = gcast.frame(b"hello"), gcast.frame(b"world!")
    framer = gcast.Framer()
    assert framer.feed(first[:2]) == []
    assert framer.feed(first[2:] + second[:5]) == [b"hello"]
    assert framer.feed(second[5:]) == [b"world!"]
    assert framer.feed(first + second) == [b"hello", b"world!"]
    assert gcast.Framer().feed(struct.pack(">I", 64 * 1024) + b"x" * 10) == []  # đúng trần: còn đợi
    with pytest.raises(CastError):
        gcast.Framer().feed(struct.pack(">I", 64 * 1024 + 1))
    with pytest.raises(CastError):
        gcast.Framer().feed(b"\xff\xff\xff\xff")


# ---- tìm thiết bị ---------------------------------------------------------------------------------------------------


def test_the_query_asks_for_the_service_and_wants_the_answer_back_on_its_own_port() -> None:
    packet = gcast.query()
    assert packet[:12] == struct.pack(">HHHHHH", 0, 0, 1, 0, 0, 0)
    assert packet[12:] == b"\x0b_googlecast\x04_tcp\x05local\x00" + struct.pack(">HH", 12, 0x8001)


def test_a_device_answer_is_read_through_name_compression() -> None:
    with _receiver("Loa Nest bếp", video=True, model="Chromecast") as device:
        answer = device.mdns_response()
        assert answer[-4:] == socket.inet_aton("127.0.0.1")
        found = gcast.parse(answer, "127.0.0.1")
        assert len(found) == 1 and found[0].host == "127.0.0.1" and found[0].port == device.port
        assert found[0].instance == f"Loa-Nest-b-p-{device.device_id[:12]}._googlecast._tcp.local"
        assert found[0].field("fn") == "Loa Nest bếp" and found[0].field("md") == "Chromecast"
        assert found[0].field("id") == device.device_id and found[0].field("ca") == "5"


def test_a_device_is_described_by_its_txt() -> None:
    with _receiver("Loa Nest phòng ngủ") as speaker, _receiver("TV Google phòng khách", video=True) as television:
        one = gcast.describe(gcast.parse(speaker.mdns_response(), "127.0.0.1")[0])
        two = gcast.describe(gcast.parse(television.mdns_response(), "127.0.0.1")[0])
        assert one.name == "Loa Nest phòng ngủ" and one.kind == "speaker" and one.protocol == "gcast"
        assert one.port == speaker.port and one.host == "127.0.0.1"
        assert len(one.id) == 12 and all(character in "0123456789abcdef" for character in one.id)
        assert one.id == gcast.describe(gcast.parse(speaker.mdns_response(), "127.0.0.1")[0]).id != two.id
        assert two.kind == "tv"
        # Thiếu TXT: lấy tên thể hiện, mã theo đó, cổng mặc định 8009.
        bare = gcast.Found("127.0.0.1", 8009, "Chromecast-abc123._googlecast._tcp.local", ())
        assert gcast.describe(bare).name == "Chromecast-abc123" and gcast.describe(bare).port == 8009
        # Không ở trong nhà thì không nhận.
        assert gcast.describe(gcast.Found("8.8.8.8", 8009, "x._googlecast._tcp.local", ())) is None


def test_an_answer_that_points_to_another_machine_is_ignored() -> None:
    """Trả lời mDNS là dữ liệu từ mạng LAN: máy lạ không được khiến máy này nối tới máy khác."""
    with _receiver() as device:
        device.advertised_host = "10.9.9.9"
        answer = device.mdns_response()
        assert gcast.parse(answer, "127.0.0.1") == [], "A của máy trỏ sang địa chỉ khác địa chỉ đã trả lời"
        assert len(gcast.parse(answer, "10.9.9.9")) == 1, "đúng chủ địa chỉ thì nhận"
    with _receiver() as device:
        answer = device.mdns_response()
        # Chuyển cổng SRV về 0: không nối được.
        broken = bytearray(answer)
        at = answer.index(struct.pack(">HHH", 0, 0, device.port))
        broken[at + 4:at + 6] = b"\x00\x00"
        assert gcast.parse(bytes(broken), "127.0.0.1") == []


def test_broken_or_hostile_packets_find_nothing() -> None:
    with _receiver() as device:
        answer = device.mdns_response()
        assert gcast.parse(gcast.query(), "127.0.0.1") == [], "một câu hỏi không phải trả lời"
        assert gcast.parse(b"", "127.0.0.1") == [] and gcast.parse(b"\x00" * 11, "127.0.0.1") == []
        for end in range(len(answer)):  # cắt cụt ở mọi chỗ không được ném lỗi
            gcast.parse(answer[:end], "127.0.0.1")
        loop = bytearray(answer)
        loop[12] = 0xC0  # tên của câu hỏi trỏ vào chính nó
        loop[13] = 0x0C
        assert gcast.parse(bytes(loop), "127.0.0.1") == []
        crowded = bytearray(answer)
        crowded[6:8] = b"\xff\xff"  # khai báo 65535 câu trả lời
        assert gcast.parse(bytes(crowded), "127.0.0.1") == []


def test_discovery_asks_and_describes_over_udp() -> None:
    with _receiver("Chromecast phòng khách", video=True) as device:
        renderers = gcast.discover(0.4, addresses=[], targets=[device.mdns_address])
        assert len(renderers) == 1
        assert (renderers[0].name, renderers[0].kind, renderers[0].host, renderers[0].port, renderers[0].protocol) == (
            "Chromecast phòng khách", "tv", "127.0.0.1", device.port, "gcast")
        device.sleep()  # tắt nguồn: mDNS im
        assert gcast.discover(0.4, addresses=[], targets=[device.mdns_address]) == []


def test_discovery_off_sends_nothing_to_the_multicast_groups(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """ABOOK_CAST_DISCOVERY=0 (tests/conftest.py đặt sẵn): không SSDP, không mDNS ra mạng người chạy bài thử."""
    sent: list[tuple[str, int]] = []

    def spy(self: socket.socket, data: bytes, *arguments: Any) -> int:
        sent.append(arguments[-1])
        return len(data)

    monkeypatch.setattr(socket.socket, "sendto", spy)
    preferences = Preferences(tmp_path / "prefs" / "preferences.json")
    app = App(preferences=preferences, runner=FakeRunner(), token="t", listening=Listening(tmp_path / "prefs" / "l.json"))
    try:
        app.cast.scan()
        _until(lambda: app.cast._searched > 0)
        time.sleep(0.5)
        assert [target for target in sent if target[0] in ("224.0.0.251", "239.255.255.250")] == []
        assert app.cast.view() == []
        # Đối chứng: cùng phép gửi mà khi mDNS bật thì đúng là đi tới 224.0.0.251:5353 (gửi giả - socket bị thay).
        gcast.search(0.3, addresses=["127.0.0.1"])
        assert ("224.0.0.251", 5353) in sent
    finally:
        app.close()


# ---- phát -----------------------------------------------------------------------------------------------------------


def test_casting_plays_the_chapter_and_moves_on_by_itself(tmp_path: Path, fast: None) -> None:
    book = Book(tmp_path)
    with _receiver(speed=5.0) as device, _players(book, device) as players:
        speaker = _found(players)
        assert speaker["via"] == "cast" and speaker["protocol"] == "gcast" and speaker["bookId"] == ""
        assert speaker["stream"] and speaker["kind"] == "speaker"
        _play(players, speaker)
        assert _names(device)[:5] == ["connection.CONNECT", "receiver.GET_STATUS", "receiver.LAUNCH",
                                      "connection.CONNECT", "media.LOAD"]
        load = device.calls("media.LOAD")[0]
        assert load["media"]["contentId"].startswith("http://127.0.0.1:") and "/c/" in load["media"]["contentId"]
        assert load["media"]["contentType"] == "audio/mpeg" and load["media"]["streamType"] == "BUFFERED"
        assert load["media"]["metadata"] == {"metadataType": 3, "title": "Chương 1: Phần 1", "albumName": "Sách thử"}
        assert load["autoplay"] is True and load["currentTime"] == 0 and load["sessionId"]
        fetched = _until(lambda: device.fetches and device.fetches[0])
        assert fetched["status"] in (200, 206) and fetched["type"] == "audio/mpeg" and fetched["cors"] == "*"
        assert fetched["bytes"] == book.files[1].stat().st_size, "thiết bị tải đúng file chương từ máy này"
        playing = _until(lambda: (now := _now(players))["playing"] and not now["buffering"] and now)
        assert playing["bookId"] == "sach" and playing["chapterId"] == 1 and playing["chapterTitle"] == "Chương 1: Phần 1"

        # Hết chương 1 (10 giây, chạy nhanh gấp 5): IDLE / FINISHED -> tự sang chương 2, chương 1 ghi là đã nghe hết.
        _until(lambda: _now(players)["chapterId"] == 2, 10)
        assert ("sach", 1, 10.0, 10.0) in book.saved
        assert len(device.calls("media.LOAD")) == 2 and device.content != load["media"]["contentId"]
        assert len(device.calls("receiver.LAUNCH")) == 1, "ứng dụng mở một lần cho cả cuốn"
        # Chương cuối hết thì thôi: phiên đóng, chỗ nghe ở cuối chương 3.
        players.send(speaker["device"], {"action": "jump", "chapterId": 3, "seconds": 0.0})
        _until(lambda: _now(players)["bookId"] == "", 10)
        assert ("sach", 3, 10.0, 10.0) in book.saved
        assert not device.calls("media.STOP"), "hết sách tự nhiên không phải lệnh dừng"


def test_resuming_mid_chapter_starts_there_without_a_seek(tmp_path: Path, fast: None) -> None:
    book = Book(tmp_path)
    with _receiver() as device, _players(book, device) as players:
        _play(players, _found(players), 2, 6.0)
        assert device.calls("media.LOAD")[0]["currentTime"] == 6.0
        assert "media.SEEK" not in _names(device), "Cast bắt đầu từ vị trí ngay trong LOAD: không tua sau"
        assert device.position() >= 6 and _until(lambda: _now(players)["position"] >= 6 and _now(players))["chapterId"] == 2


def test_pause_play_skip_and_chapters_on_the_device(tmp_path: Path, fast: None) -> None:
    with _receiver(duration=30.0) as device, _players(Book(tmp_path, seconds=30.0), device) as players:
        speaker = _found(players)["device"]
        players.send(speaker, {"action": "load", "bookId": "sach", "chapterId": 1, "seconds": 0.0})
        _until(lambda: _now(players)["playing"] and not _now(players)["buffering"])
        players.send(speaker, {"action": "pause"})
        assert device.state == "PAUSED" and not _now(players)["playing"]
        players.send(speaker, {"action": "toggle"})
        assert device.state == "PLAYING" and _now(players)["playing"]
        before = device.position()
        players.send(speaker, {"action": "skip", "seconds": 15})
        assert 14 <= device.position() - before <= 17
        assert device.calls("media.SEEK")[-1]["currentTime"] == pytest.approx(before + 15, abs=2)
        players.send(speaker, {"action": "seek", "seconds": 5})
        assert device.position() < 8
        players.send(speaker, {"action": "skip", "seconds": 60})  # quá cuối chương: sang chương sau
        assert len(device.calls("media.LOAD")) == 2 and _now(players)["chapterId"] == 2
        players.send(speaker, {"action": "previous"})
        assert _now(players)["chapterId"] == 1 and len(device.calls("media.LOAD")) == 3
        players.send(speaker, {"action": "next"})
        assert _now(players)["chapterId"] == 2
        players.send(speaker, {"action": "jump", "chapterId": 3, "seconds": 12.0})
        assert device.calls("media.LOAD")[-1]["currentTime"] == 12.0 and _now(players)["chapterId"] == 3
        players.send(speaker, {"action": "rate", "rate": 1.0})
        with pytest.raises(CastError) as error:
            players.send(speaker, {"action": "rate", "rate": 1.5})
        assert str(error.value) == "Loa Nest phòng khách: loa, TV chỉ phát ở tốc độ 1x"
        with pytest.raises(CastError):
            players.send(speaker, {"action": "jump", "chapterId": 4, "seconds": 0.0})  # chương chưa thu
        assert len(device.calls("receiver.LAUNCH")) == 1 and len(device.calls("media.LOAD")) == 5


def test_play_after_pause_continues_on_the_device_without_loading_again(tmp_path: Path, fast: None) -> None:
    with _receiver(duration=30.0) as device, _players(Book(tmp_path, seconds=30.0), device) as players:
        speaker = _found(players)["device"]
        players.send(speaker, {"action": "load", "bookId": "sach", "chapterId": 1, "seconds": 0.0})
        _until(lambda: _now(players)["position"] >= 1)
        players.send(speaker, {"action": "pause"})
        assert device.state == "PAUSED"
        position = _now(players)["position"]
        players.send(speaker, {"action": "play"})
        assert device.state == "PLAYING" and len(device.calls("media.LOAD")) == 1
        # Tiếp từ chỗ dừng, không về đầu. Vị trí đọc ngay sau "pause" có thể là ước lượng từ trạng thái PLAYING cũ (cộng thời gian trôi),
        # nhỉnh hơn chỗ máy thật dừng vài chục mili giây - lần chạy cả bộ 08-10 hỏng "1.0 >= 1.01". Dung sai 0,1 s, xa mọi lần "về đầu".
        assert _until(lambda: _now(players)["playing"]) and _now(players)["position"] >= position - 0.1


@pytest.mark.parametrize("how", ["takeover", "stop_app", "interrupt"])
def test_another_controller_taking_the_device_ends_the_session(tmp_path: Path, fast: None, how: str) -> None:
    with _receiver(duration=30.0) as device, _players(Book(tmp_path, seconds=30.0), device) as players:
        speaker = _found(players)
        _play(players, speaker)
        _until(lambda: _now(players)["position"] >= 1.2)
        if how == "takeover":
            device.takeover("http://192.168.0.5:8200/MediaItems/22.mp3")  # máy khác LOAD thứ khác
        elif how == "stop_app":
            device.stop_app()  # bấm dừng trên TV
        else:
            device.interrupt()  # IDLE / INTERRUPTED
        _until(lambda: _now(players)["bookId"] == "")
        assert not device.calls("media.STOP") and not device.calls("receiver.STOP"), "không đụng tới thứ người khác đang phát"
        with pytest.raises(CastError):
            players.send(speaker["device"], {"action": "pause"})
        players.send(speaker["device"], {"action": "stop"})  # "Nghe trên máy này" sau đó: không còn gì để dừng, không lỗi
        assert not device.calls("media.STOP")


def test_a_takeover_keeps_the_place_where_the_listener_was(tmp_path: Path, fast: None) -> None:
    book = Book(tmp_path, seconds=30.0)
    with _receiver(duration=30.0) as device, _players(book, device) as players:
        _play(players, _found(players), 1, 4.0)
        _until(lambda: _now(players)["position"] >= 5)
        device.takeover("http://192.168.0.5:8200/MediaItems/22.mp3")
        _until(lambda: _now(players)["bookId"] == "")
        assert book.saved[-1][:2] == ("sach", 1) and book.saved[-1][2] >= 4


@pytest.mark.parametrize("how", ["sleep", "frozen"])
def test_a_device_that_went_to_sleep_is_dropped_after_a_while(tmp_path: Path, fast: None, monkeypatch: pytest.MonkeyPatch,
                                                              how: str) -> None:
    monkeypatch.setattr(cast, "LOST_SECONDS", 1.5)
    book = Book(tmp_path, seconds=30.0)
    with _receiver(duration=30.0) as device, _players(book, device) as players:
        _play(players, _found(players), 1, 3.0)
        _until(lambda: _now(players)["position"] >= 4)
        if how == "sleep":
            device.sleep()  # tắt nguồn: đứt kết nối, nối lại không được
        else:
            device.no_heartbeat_reply = True  # treo: nối vẫn còn nhưng không ai trả lời
        assert _until(lambda: _now(players)["buffering"], 6), "im lặng thì hiện đang tải, chưa bỏ ngay"
        _until(lambda: _now(players)["bookId"] == "", 12)
        assert book.saved[-1][:2] == ("sach", 1) and 4 <= book.saved[-1][2] <= 12


def test_a_device_that_comes_back_quickly_keeps_the_session(tmp_path: Path, fast: None) -> None:
    """Wi-Fi chập chờn: kết nối đứt rồi nối lại được trước LOST_SECONDS, ứng dụng vẫn còn -> phát tiếp, không bỏ phiên."""
    with _receiver(duration=30.0) as device, _players(Book(tmp_path, seconds=30.0), device) as players:
        _play(players, _found(players), 1)
        _until(lambda: _now(players)["position"] >= 1.2)
        device.sleep()
        _until(lambda: _now(players)["buffering"], 6)
        device.wake()
        _until(lambda: _now(players)["playing"] and not _now(players)["buffering"], 10)
        assert _now(players)["bookId"] == "sach" and device.connections >= 2
        assert len(device.calls("media.LOAD")) == 1 and len(device.calls("receiver.LAUNCH")) == 1


def test_closing_the_app_stops_the_device_and_gives_it_back(tmp_path: Path, fast: None) -> None:
    book = Book(tmp_path, seconds=30.0)
    with _receiver(duration=30.0) as device, _players(book, device) as players:
        _play(players, _found(players), 2, 6.0)
        _until(lambda: _now(players)["position"] >= 7)
        assert device.app_running
        players.close()
        names = _names(device)
        assert "media.STOP" in names and "receiver.STOP" in names and names.index("media.STOP") < names.index("receiver.STOP")
        assert device.state == "IDLE" and not device.app_running
        assert book.saved[-1][:2] == ("sach", 2) and book.saved[-1][2] >= 6


def test_an_app_that_was_already_running_is_left_running(tmp_path: Path, fast: None) -> None:
    """Ứng dụng nhận do người khác mở sẵn: máy này dùng nó, dừng phát của mình, nhưng không đóng ứng dụng của người ta."""
    with _receiver(duration=30.0) as device, _players(Book(tmp_path, seconds=30.0), device) as players:
        device.launch()
        _play(players, _found(players))
        assert not device.calls("receiver.LAUNCH") and len(device.calls("media.LOAD")) == 1
        players.close()
        assert "media.STOP" in _names(device) and "receiver.STOP" not in _names(device) and device.app_running


def test_listening_on_this_computer_stops_the_device(tmp_path: Path, fast: None) -> None:
    book = Book(tmp_path, seconds=30.0)
    with _receiver(duration=30.0) as device, _players(book, device) as players:
        speaker = _found(players)
        _play(players, speaker, 1, 3.0)
        _until(lambda: _now(players)["position"] >= 4)
        players.send(speaker["device"], {"action": "stop"})
        assert _now(players)["bookId"] == "" and not device.app_running
        names = _names(device)
        assert names.index("media.STOP") < names.index("receiver.STOP")
        assert book.saved[-1][:2] == ("sach", 1) and book.saved[-1][2] >= 3
        _play(players, speaker, 1, 3.0)  # nghe lại trên loa: nối lại từ đầu, mở lại ứng dụng
        assert len(device.calls("receiver.LAUNCH")) == 2 and _now(players)["playing"]


def test_a_device_that_cannot_fetch_the_audio_says_so_in_the_listeners_words(tmp_path: Path, fast: None) -> None:
    with _receiver() as device, _players(Book(tmp_path), device) as players:
        speaker = _found(players)
        device.refuse_load = True
        with pytest.raises(CastError) as error:
            _play(players, speaker)
        assert "tường lửa" in str(error.value) and error.value.code == 0
        assert _now(players)["bookId"] == "", "không có phiên cho một chương chưa tải được"
        assert not device.app_running, "đừng bỏ lại ứng dụng đã mở cho một phiên không có"


def test_a_device_that_fails_after_the_load_ends_the_session(tmp_path: Path, fast: None) -> None:
    """LOAD nhận rồi mà thiết bị không tải được file (tường lửa chặn cổng audio): IDLE / ERROR."""
    book = Book(tmp_path)
    with _receiver() as device, _players(book, device) as players:
        device.fail_fetch = True
        speaker = _found(players)
        try:
            _play(players, speaker)
        except CastError as error:  # thiết bị báo ngay trong lúc chờ trả lời LOAD
            assert "tường lửa" in str(error)
        _until(lambda: _now(players)["bookId"] == "")


# ---- qua app --------------------------------------------------------------------------------------------------------


def _app(tmp_path: Path, device: Any) -> tuple[App, Path]:
    root = tmp_path / "thu_vien"
    root.mkdir()
    project = make_project(root)
    preferences = Preferences(tmp_path / "prefs" / "preferences.json")
    preferences.update({"libraryRoot": str(root)})
    app = App(preferences=preferences, runner=FakeRunner(), token="t", listening=Listening(tmp_path / "prefs" / "l.json"))
    app.cast.find_google = _google(device)
    app.cast.media = CastMedia("127.0.0.1")
    return app, project


def test_the_app_lists_a_google_device_casts_a_real_chapter_and_hands_it_back(tmp_path: Path, fast: None) -> None:
    headers = {"X-Ebook-Token": "t"}
    with _receiver("Nest Mini bếp", duration=600.0) as device:
        app, project = _app(tmp_path, device)
        ui = Server(app, port=0).start()
        try:
            def speakers() -> list[dict[str, Any]]:
                _status, data, _ = _request(ui.port, "GET", "/api/remote", headers=headers)
                return [phone for phone in json.loads(data)["phones"] if phone["via"] == "cast"]

            assert _request(ui.port, "POST", "/api/cast/scan", headers=headers)[0] == 200
            speaker = _until(speakers)[0]
            assert speaker["name"] == "Nest Mini bếp" and speaker["protocol"] == "gcast" and not speaker["known"]
            identifier = book_id(project)
            status, data, _ = _request(ui.port, "POST", f"/api/remote/{speaker['device']}", headers=headers,
                                       body={"action": "load", "bookId": identifier, "chapterId": 1, "seconds": 0})
            assert status == 200 and json.loads(data)["id"]
            fetched = _until(lambda: device.fetches and device.fetches[0])
            assert fetched["bytes"] == (project / "output" / "chapters" / "00001_645.mp3").stat().st_size
            playing = _until(lambda: [item for item in speakers() if item["playing"] and not item["buffering"]])[0]
            assert playing["bookId"] == identifier and playing["known"] and playing["protocol"] == "gcast"
            status, data, _ = _request(ui.port, "POST", f"/api/remote/{speaker['device']}", headers=headers,
                                       body={"action": "rate", "rate": 2})
            assert status == 409 and "1x" in json.loads(data)["error"]
            # "Nghe trên máy này": lệnh stop trả thiết bị.
            status, _data, _ = _request(ui.port, "POST", f"/api/remote/{speaker['device']}", headers=headers,
                                        body={"action": "stop"})
            assert status == 200 and not device.app_running
            assert _until(lambda: [item for item in speakers() if not item["bookId"]])
        finally:
            ui.stop()
            app.close()


def test_a_paired_phone_sees_and_drives_the_google_devices_of_this_computer(tmp_path: Path, fast: None) -> None:
    with _receiver("TV Google phòng khách", video=True, duration=600.0) as device:
        app, project = _app(tmp_path, device)
        app.sync_host, app.sync_port = "127.0.0.1", 0
        app.set_sync(True)
        try:
            port = app.sync_server.port
            code = app.devices.start_pairing()["code"]
            _status, data, _ = _sync_request(port, "POST", "/sync/v1/pair", body={"code": code, "device": "Pixel"})
            token = json.loads(data)["token"]

            def renderers() -> list[dict[str, Any]]:
                _status, data, _ = _sync_request(port, "GET", "/sync/v1/cast", token)
                return json.loads(data)["renderers"]

            app.cast.scan()
            tv = _until(renderers)[0]
            assert tv["name"] == "TV Google phòng khách" and tv["kind"] == "tv" and tv["protocol"] == "gcast"
            assert tv["state"] is None and tv["stream"]
            status, data, _ = _sync_request(port, "POST", f"/sync/v1/cast/{tv['id']}", token,
                                            body={"action": "load", "bookId": book_id(project), "chapterId": 1, "seconds": 0})
            assert status == 200 and json.loads(data)["id"]
            _until(lambda: device.fetches)
            playing = _until(lambda: [item for item in renderers() if item["state"] and item["state"]["playing"]])[0]
            assert playing["state"]["bookId"] == book_id(project) and playing["state"]["chapterId"] == 1
            status, data, _ = _sync_request(port, "POST", f"/sync/v1/cast/{tv['id']}", token, body={"action": "rate", "rate": 2})
            assert status == 409 and "1x" in json.loads(data)["error"]
            status, _data, _ = _sync_request(port, "POST", f"/sync/v1/cast/{tv['id']}", token, body={"action": "pause"})
            assert status == 200 and device.state == "PAUSED"
        finally:
            app.close()
