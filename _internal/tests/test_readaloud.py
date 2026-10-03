"""Đọc to cho "Nghe ngay" (abook/readaloud): nối mảnh từ -> mốc từng chữ (bộ ví dụ chung với Kotlin), khung WebSocket, máy khách Edge (máy chủ giả
trên máy này), bộ đệm, và các đường dẫn của máy chủ giao diện với một giọng giả. Gọi dịch vụ Edge thật: ABOOK_NET_TESTS=1."""
from __future__ import annotations

import json
import os
import random
import socket
import struct
import sys
import threading
import time
from http import HTTPStatus
from pathlib import Path

import pytest

from abook.readaloud import cache as clip_cache
from abook.readaloud import edge, loudness, mapping, windows
from abook.readaloud import websocket as ws
from abook.readaloud.mapping import Boundary, fold, map_boundaries
from abook.readaloud.model import Synthesis, Voice, VoiceError
from abook.readaloud.service import ReadAloud

FIXTURES = Path(__file__).parent / "fixtures" / "readaloud"
CASES = sorted(FIXTURES.glob("*.json"))
NET = pytest.mark.skipif(os.environ.get("ABOOK_NET_TESTS") != "1", reason="gọi dịch vụ thật: ABOOK_NET_TESTS=1")


# ---- mốc từng chữ ---------------------------------------------------------------------------------------------------------


def _boundaries(case: dict) -> list[Boundary]:
    return [Boundary(item["text"], item["start"], item["end"], item.get("char")) for item in case["boundaries"]]


def _check_shape(text: str, words: list[list[int]], duration: int) -> None:
    assert len(words) == len(text.split())
    last_start = 0
    for index, (start, end) in enumerate(words):
        assert 0 <= start <= end <= duration
        assert start >= last_start
        last_start = start
        if index + 1 < len(words):
            assert end <= words[index + 1][0]


def test_there_are_shared_fixtures() -> None:
    assert len(CASES) >= 10


@pytest.mark.parametrize("path", CASES, ids=lambda path: path.stem)
def test_boundaries_map_to_the_expected_words(path: Path) -> None:
    case = json.loads(path.read_bytes().decode("utf-8"))
    words = map_boundaries(case["text"], _boundaries(case), case["durationMs"])
    assert words == case["words"]
    _check_shape(case["text"], words, case["durationMs"])


def test_fold_keeps_letters_and_digits_only() -> None:
    assert fold("“Ừ,” Hà-Nội 2!") == "ừhànội2"
    assert fold("Việt") == fold("Việt")  # NFC: dấu rời ghép lại
    assert fold("— … ,") == ""


def test_random_noise_never_breaks_the_invariants() -> None:
    rng = random.Random(7)
    vocabulary = ["xin", "chào", "—", "1945", "các", "bạn.", "“Ừ,”", "Hà-Nội", "và", "!"]
    for _ in range(300):
        text = " ".join(rng.choice(vocabulary) for _ in range(rng.randint(1, 14)))
        duration = rng.randint(100, 9000)
        pieces = []
        for _ in range(rng.randint(0, 20)):
            start = rng.randint(0, duration + 500)
            pieces.append(Boundary(rng.choice(vocabulary + ["xyz", "một nghìn"]), start, start + rng.randint(0, 800),
                                   rng.choice([None, rng.randint(0, len(text) + 3)])))
        _check_shape(text, map_boundaries(text, pieces, duration), duration)


def test_empty_text_has_no_words() -> None:
    assert map_boundaries("   ", [Boundary("x", 0, 10)], 100) == []


# ---- WebSocket ------------------------------------------------------------------------------------------------------------


def test_a_masked_text_frame_matches_the_rfc_example() -> None:
    # RFC 6455 mục 5.7: "Hello" che bằng khoá 0x37fa213d.
    assert ws.encode_frame(ws.TEXT, b"Hello", bytes.fromhex("37fa213d")) == bytes.fromhex("818537fa213d7f9f4d5158")


@pytest.mark.parametrize("size", [0, 5, 125, 126, 300, 65535, 65536, 70000])
def test_frames_round_trip_at_every_length_class(size: int) -> None:
    payload = bytes(range(256)) * (size // 256 + 1)
    payload = payload[:size]
    frame = ws.encode_frame(ws.BINARY, payload)
    cursor = iter([frame])
    buffer = bytearray(frame)

    def receive(count: int) -> bytes:
        chunk = bytes(buffer[:count])
        del buffer[:count]
        assert len(chunk) == count
        return chunk

    del cursor
    assert ws.read_frame(receive) == (True, ws.BINARY, payload)
    assert not buffer


def _server_frame(opcode: int, payload: bytes, fin: bool = True) -> bytes:
    """Khung của máy chủ: không che."""
    length = len(payload)
    head = bytes([(0x80 if fin else 0) | opcode])
    if length < 126:
        head += bytes([length])
    elif length < 65536:
        head += bytes([126]) + struct.pack(">H", length)
    else:
        head += bytes([127]) + struct.pack(">Q", length)
    return head + payload


class _Pipe:
    """Socket giả: những gì máy khách gửi gom vào `sent`, những gì nó nhận là `incoming`."""

    def __init__(self, incoming: bytes) -> None:
        self.incoming = bytearray(incoming)
        self.sent = bytearray()

    def recv(self, count: int) -> bytes:
        chunk = bytes(self.incoming[:count])
        del self.incoming[:count]
        return chunk

    def sendall(self, data: bytes) -> None:
        self.sent += data

    def close(self) -> None:
        pass


def test_fragmented_messages_join_and_pings_get_a_pong() -> None:
    wire = (_server_frame(ws.TEXT, b"xin ", fin=False) + _server_frame(ws.PING, b"ping") + _server_frame(ws.CONTINUATION, b"chao", fin=True)
            + _server_frame(ws.BINARY, b"\x01\x02"))
    pipe = _Pipe(wire)
    connection = ws.Connection(pipe)  # type: ignore[arg-type]
    assert connection.recv() == (ws.TEXT, b"xin chao")
    assert bytes(pipe.sent[:1]) == bytes([0x80 | ws.PONG])  # pong có mặt nạ, mang lại đúng "ping"
    assert connection.recv() == (ws.BINARY, b"\x01\x02")


def test_a_close_frame_raises_closed_and_is_answered() -> None:
    pipe = _Pipe(_server_frame(ws.CLOSE, struct.pack(">H", 1008) + "vi phạm".encode()))
    connection = ws.Connection(pipe)  # type: ignore[arg-type]
    with pytest.raises(ws.Closed) as caught:
        connection.recv()
    assert caught.value.code == 1008 and caught.value.reason == "vi phạm"
    assert bytes(pipe.sent[:1]) == bytes([0x80 | ws.CLOSE])


def test_the_accept_key_matches_the_rfc_example() -> None:
    assert ws.accept_key("dGhlIHNhbXBsZSBub25jZQ==") == "s3pPLMBiTxaQ9kYGzzhZRbK+xOo="


# ---- máy khách Edge với máy chủ giả -----------------------------------------------------------------------------------------


class FakeEdge:
    """Máy chủ WebSocket giả nói đúng giao thức Edge, trên cổng tự chọn của máy này (không TLS)."""

    def __init__(self, *, reject_first: bool = False, silent: bool = False, drop: int = 0, busy: int = 0) -> None:
        self.reject_first = reject_first
        self.busy = busy  # số lần bắt tay đầu bị trả 503 (dịch vụ bận)
        self.drop = drop  # số lượt đầu bị cắt giữa chừng (như dịch vụ thật thỉnh thoảng làm)
        self.silent = silent
        self.requests: list[str] = []
        self.messages: list[str] = []
        self.listener = socket.socket()
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen(5)
        self.port = self.listener.getsockname()[1]
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def close(self) -> None:
        self.listener.close()

    def _serve(self) -> None:
        rejected = False
        while True:
            try:
                conn, _ = self.listener.accept()
            except OSError:
                return
            with conn:
                raw = b""
                while b"\r\n\r\n" not in raw:
                    chunk = conn.recv(4096)
                    if not chunk:
                        break
                    raw += chunk
                text = raw.decode("latin-1")
                self.requests.append(text)
                if self.busy > 0:
                    self.busy -= 1
                    conn.sendall(b"HTTP/1.1 503 Service Unavailable\r\nContent-Length: 0\r\n\r\n")
                    continue
                if self.reject_first and not rejected:
                    rejected = True
                    conn.sendall(b"HTTP/1.1 403 Forbidden\r\nDate: Fri, 03 Oct 2026 10:00:00 GMT\r\nContent-Length: 0\r\n\r\n")
                    continue
                key = next(line.split(":", 1)[1].strip() for line in text.split("\r\n") if line.lower().startswith("sec-websocket-key"))
                conn.sendall(("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                              f"Sec-WebSocket-Accept: {ws.accept_key(key)}\r\n\r\n").encode())
                try:
                    self._talk(conn)
                except (OSError, ws.WebSocketError):
                    pass

    def _talk(self, conn: socket.socket) -> None:
        def receive(count: int) -> bytes:
            data = b""
            while len(data) < count:
                chunk = conn.recv(count - len(data))
                if not chunk:
                    raise OSError("đóng")
                data += chunk
            return data

        config = ws.read_frame(receive)[2].decode()
        ssml = ws.read_frame(receive)[2].decode()
        self.messages += [config, ssml]
        if self.drop > 0:
            self.drop -= 1
            return
        if self.silent:
            time.sleep(1.5)
            return
        spoken = ssml.split("<prosody pitch='+0Hz' rate='+0%' volume='+0%'>")[1].split("</prosody>")[0]
        conn.sendall(_server_frame(ws.TEXT, b"X-RequestId:1\r\nPath:turn.start\r\n\r\n{}"))
        offset = 0
        step = 3_000_000 if len(spoken.split()) <= 6 else 20_000_000 // len(spoken.split())  # chữ dài thì dồn vào 2 giây audio
        for word in spoken.split():
            meta = {"Metadata": [{"Type": "WordBoundary", "Data": {"Offset": offset, "Duration": min(2_500_000, step // 2 + 1_000_000),
                                                                    "text": {"Text": word, "Length": len(word), "BoundaryType": "WordBoundary"}}}]}
            conn.sendall(_server_frame(ws.TEXT, b"Path:audio.metadata\r\n\r\n" + json.dumps(meta).encode()))
            offset += step
        head = b"X-RequestId:1\r\nContent-Type:audio/mpeg\r\nPath:audio"
        conn.sendall(_server_frame(ws.BINARY, struct.pack(">H", len(head)) + head + b"A" * 12000))  # 12000 byte @48 kbps = 2,000 s
        conn.sendall(_server_frame(ws.BINARY, struct.pack(">H", 20) + b"X-RequestId:1\r\nPath:audio"[:20] if False else struct.pack(">H", len(b"Path:audio")) + b"Path:audio"))
        conn.sendall(_server_frame(ws.TEXT, b"X-RequestId:1\r\nPath:turn.end\r\n\r\n{}"))
        conn.sendall(_server_frame(ws.CLOSE, struct.pack(">H", 1000)))


@pytest.fixture
def fake_edge():
    servers: list[FakeEdge] = []

    def make(**options) -> tuple[FakeEdge, edge.EdgeClient]:
        server = FakeEdge(**options)
        servers.append(server)
        return server, edge.EdgeClient(host="127.0.0.1", port=server.port, secure=False, connect_timeout=2, read_timeout=2)

    yield make
    for server in servers:
        server.close()


def test_the_edge_client_speaks_the_protocol(fake_edge) -> None:
    server, client = fake_edge()
    result = client.synthesize("Xin chào các bạn & bạn", "vi-VN-HoaiMyNeural")
    assert result.audio == b"A" * 12000 and result.ext == "mp3"
    assert result.duration_ms == 2000
    # 100 ns -> ms (chia 10 000): bắt đầu 0, 300, 600...; mỗi mảnh dài 250 ms; "&" được escape rồi unescape đúng.
    assert [(b.text, b.start_ms, b.end_ms) for b in result.boundaries] == [
        ("Xin", 0, 250), ("chào", 300, 550), ("các", 600, 850), ("bạn", 900, 1150), ("&", 1200, 1450), ("bạn", 1500, 1750)]
    request = server.requests[0]
    assert request.startswith("GET /consumer/speech/synthesize/readaloud/edge/v1?TrustedClientToken=")
    assert "Sec-MS-GEC=" in request and f"Sec-MS-GEC-Version={edge.SEC_MS_GEC_VERSION}" in request and "ConnectionId=" in request
    assert "Origin: chrome-extension://" in request and "Cookie: muid=" in request
    config, ssml = server.messages
    assert "Path:speech.config" in config and '"wordBoundaryEnabled":"true"' in config and edge.OUTPUT_FORMAT in config
    json.loads(config.split("\r\n\r\n", 1)[1])  # JSON hợp lệ
    assert "Path:ssml" in ssml and "<voice name='vi-VN-HoaiMyNeural'>" in ssml and "bạn &amp; bạn" in ssml


def test_long_text_goes_in_chunks_with_offsets_compensated_by_audio_bytes(fake_edge) -> None:
    server, client = fake_edge()
    text = " ".join(["Câu số một hai ba."] * 600)  # > 4000 byte -> nhiều lượt
    chunks = edge.split_text(text)
    assert len(chunks) > 1 and all(len(edge.escape(chunk).encode()) <= edge.MAX_CHUNK_BYTES for chunk in chunks)
    assert " ".join(chunks).split() == text.split()
    result = client.synthesize(text, edge.DEFAULT_VOICE)
    assert len(result.audio) == 12000 * len(chunks)
    starts = [b.start_ms for b in result.boundaries]
    assert starts == sorted(starts)
    # mốc đầu của lượt thứ hai = 2000 ms (audio lượt đầu) + 0
    first_of_second = len(chunks[0].split())
    assert result.boundaries[first_of_second].start_ms == 2000
    assert len(server.requests) == len(chunks)


def test_a_connection_dropped_mid_turn_is_retried(fake_edge, monkeypatch) -> None:
    monkeypatch.setattr(edge.time, "sleep", lambda _seconds: None)
    server, client = fake_edge(drop=2)
    result = client.synthesize("Xin chào", edge.DEFAULT_VOICE)
    assert result.audio == b"A" * 12000 and len(server.requests) == 3
    server, client = fake_edge(drop=3)
    with pytest.raises(edge.EdgeError) as caught:
        client.synthesize("Xin chào", edge.DEFAULT_VOICE)
    assert isinstance(caught.value, edge.EdgeDropped) and len(server.requests) == 3


def test_a_busy_handshake_is_retried_like_a_dropped_turn(fake_edge, monkeypatch) -> None:
    # Soát 03-10: HTTP 429 / 5xx lúc bắt tay là lỗi thoáng qua - thử lại, không coi là dịch vụ đổi giao thức.
    monkeypatch.setattr(edge.time, "sleep", lambda _seconds: None)
    server, client = fake_edge(busy=2)
    result = client.synthesize("Xin chào", edge.DEFAULT_VOICE)
    assert result.audio == b"A" * 12000 and len(server.requests) == 3
    server, client = fake_edge(busy=3)
    with pytest.raises(edge.EdgeError) as caught:
        client.synthesize("Xin chào", edge.DEFAULT_VOICE)
    assert isinstance(caught.value, edge.EdgeDropped) and "503" in str(caught.value)


def test_a_403_teaches_the_clock_skew_and_retries_once(fake_edge) -> None:
    server, client = fake_edge(reject_first=True)
    saved = edge._clock_skew
    try:
        result = client.synthesize("Xin chào", edge.DEFAULT_VOICE)
        assert len(server.requests) == 2 and result.audio
        assert abs(edge._clock_skew - (1_791_021_600 - time.time())) < 5
    finally:
        edge._clock_skew = saved


def test_a_closed_port_is_offline_with_a_clear_reason() -> None:
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    listener.close()
    with pytest.raises(edge.EdgeOffline) as caught:
        edge.EdgeClient(host="127.0.0.1", port=port, secure=False, connect_timeout=2).synthesize("Xin chào", edge.DEFAULT_VOICE)
    assert caught.value.reason == "offline"


def test_an_unresolvable_host_is_offline() -> None:
    with pytest.raises(edge.EdgeOffline):
        edge.EdgeClient(host="khong-co-mang.invalid", connect_timeout=2).synthesize("Xin chào", edge.DEFAULT_VOICE)


def test_a_silent_service_times_out(fake_edge) -> None:
    server, client = fake_edge(silent=True)
    client.read_timeout = 0.3
    with pytest.raises(edge.EdgeError) as caught:
        client.synthesize("Xin chào", edge.DEFAULT_VOICE)
    assert caught.value.reason in ("timeout", "offline")


def test_the_gec_token_follows_the_published_recipe() -> None:
    import hashlib

    now = 1_791_021_607.0  # 2026-10-03 10:00:07 UTC
    ticks = int(((now + 11_644_473_600) - (now + 11_644_473_600) % 300) * 10_000_000)
    assert edge.gec_token(now, 0.0) == hashlib.sha256(f"{ticks}{edge.TRUSTED_CLIENT_TOKEN}".encode()).hexdigest().upper()
    assert edge.gec_token(now, 0.0) == edge.gec_token(now + 200, 0.0)  # cùng khung 5 phút


def test_metadata_parse_ignores_other_types() -> None:
    body = json.dumps({"Metadata": [{"Type": "SessionEnd", "Data": {"Offset": 5}},
                                    {"Type": "WordBoundary", "Data": {"Offset": 1_234_567, "Duration": 1_000_000, "text": {"Text": "a&amp;b"}}}]})
    assert edge.parse_metadata(body, 10_000_000) == [Boundary("a&b", 1123, 1223)]


# ---- bộ đệm ---------------------------------------------------------------------------------------------------------------


def test_the_cache_stores_reads_and_trims_the_least_recently_used(tmp_path: Path) -> None:
    store = clip_cache.ClipCache(tmp_path / "c", limit=2500)
    keys = [clip_cache.clip_key("edge", "v", f"đoạn {n}") for n in range(3)]
    assert len(set(keys)) == 3 and all(len(key) == 64 for key in keys)
    store.put(keys[0], b"a" * 1000, "mp3", 800, [[0, 400], [400, 800]])
    time.sleep(0.02)
    store.put(keys[1], b"b" * 1000, "mp3", 900, [[0, 900]])
    time.sleep(0.02)
    hit = store.get(keys[0])  # dùng lại clip 0: nó không còn là "lâu không dùng nhất"
    assert hit is not None and hit.words == [[0, 400], [400, 800]] and hit.duration_ms == 800
    time.sleep(0.02)
    store.put(keys[2], b"c" * 1000, "wav", 700, [[0, 700]])
    assert store.get(keys[1]) is None, "clip lâu không dùng nhất bị bỏ"
    assert store.get(keys[0]) is not None and store.get(keys[2]) is not None
    assert store.size() <= 2500 + 200
    assert not [entry for entry in (tmp_path / "c").iterdir() if entry.name.endswith(".part")]


def test_the_cache_only_serves_well_formed_names(tmp_path: Path) -> None:
    store = clip_cache.ClipCache(tmp_path)
    key = clip_cache.clip_key("edge", "v", "x")
    store.put(key, b"zz", "mp3", 10, [[0, 10]])
    assert store.path(f"{key}.mp3") == tmp_path / f"{key}.mp3"
    for bad in ("../x.mp3", f"{key}.json", "abc.mp3", f"{key}.mp3/..", f"{key.upper()}.mp3"):
        assert store.path(bad) is None
    assert store.mime(f"{key}.mp3") == "audio/mpeg" and store.mime(f"{key}.wav") == "audio/wav"


def test_the_cache_ignores_a_torn_entry(tmp_path: Path) -> None:
    store = clip_cache.ClipCache(tmp_path)
    key = clip_cache.clip_key("edge", "v", "x")
    (tmp_path / f"{key}.json").write_bytes(b"{oops")
    assert store.get(key) is None


# ---- dịch vụ + máy chủ giao diện ------------------------------------------------------------------------------------------


class FakeProvider:
    id = "fake"

    def __init__(self, *, fail: VoiceError | None = None) -> None:
        self.calls: list[tuple[str, str]] = []
        self.fail = fail

    def voices(self) -> list[Voice]:
        return [Voice("fake:ngoc", "Ngọc", "fake", False, True)]

    def synthesize(self, text: str, native_voice: str) -> Synthesis:
        self.calls.append((native_voice, text))
        if self.fail:
            raise self.fail
        pieces = []
        for index, word in enumerate(text.split()):
            pieces.append(Boundary(word.strip("."), index * 300, index * 300 + 250))
        return Synthesis(b"ID3" + bytes(range(256)) * 4, pieces, len(text.split()) * 300)


def test_the_service_makes_a_clip_once_and_then_serves_the_cache(tmp_path: Path) -> None:
    provider = FakeProvider()
    service = ReadAloud(tmp_path, [provider])
    first = service.clip("fake:ngoc", "Xin chào — các bạn.")
    second = service.clip("fake:ngoc", "Xin chào — các bạn.")
    assert first == second and len(provider.calls) == 1
    assert first["duration_ms"] == 1500 and len(first["words"]) == 5
    assert first["words"][2] == [550, 900]  # gạch ngang: nội suy giữa "chào" (kết thúc 550) và "các" (bắt đầu 900)
    assert service.clip("fake:ngoc", "Câu khác.")["words"] and len(provider.calls) == 2


def test_the_service_refuses_unknown_voices_empty_text_and_uncached_lookups(tmp_path: Path) -> None:
    service = ReadAloud(tmp_path, [FakeProvider()])
    for voice, text, reason in (("fake:khac", "Xin chào", "voice"), ("khong:co", "Xin chào", "voice"), ("fake:ngoc", " — … ", "empty"),
                                ("fake:ngoc", "Chưa đọc bao giờ", "uncached")):
        with pytest.raises(VoiceError) as caught:
            service.clip(voice, text, cached_only=True)
        assert caught.value.reason == reason
    with pytest.raises(ValueError):
        service.clip("fake:ngoc", "x" * 20_001)


def test_warming_lists_the_voices_in_the_background(tmp_path: Path) -> None:
    class Slow(FakeProvider):
        listed = threading.Event()

        def voices(self) -> list[Voice]:
            self.listed.set()
            return super().voices()

    provider = Slow()
    ReadAloud(tmp_path, [provider]).warm()
    assert provider.listed.wait(5)


def test_voice_loudness_table_matches_the_measurements() -> None:
    assert loudness.gain_db("edge:vi-VN-HoaiMyNeural") == -1.7
    assert loudness.gain_db("edge:vi-VN-NamMinhNeural") == -0.3
    assert loudness.gain_db("device:bat-ky") == 0.0


def test_edge_lists_hoai_my_first_and_as_the_default() -> None:
    voices = ReadAloud("unused", [__import__("abook.readaloud.service", fromlist=["x"]).EdgeProvider()]).voices()
    assert [(v["id"], v["name"], v["provider"], v["online"], v["default"]) for v in voices] == [
        ("edge:vi-VN-HoaiMyNeural", "Hoài My", "edge", True, True), ("edge:vi-VN-NamMinhNeural", "Nam Minh", "edge", True, False)]
    assert voices[0]["gain_db"] == -1.7 and voices[1]["gain_db"] == -0.3


def _server(tmp_path: Path, provider: FakeProvider):
    from abook.webui.actions import FakeRunner
    from abook.webui.library import Preferences
    from abook.webui.listening import Listening
    from abook.webui.server import App, Server

    preferences = Preferences(tmp_path / "prefs" / "preferences.json")
    preferences.update({"libraryRoot": str(tmp_path / "lib")})
    app = App(preferences=preferences, runner=FakeRunner(), token="t", listening=Listening(tmp_path / "prefs" / "listening.json"))
    assert app.readaloud.cache.folder == tmp_path / "prefs" / "readaloud-cache"
    app.readaloud = ReadAloud(tmp_path / "prefs" / "readaloud-cache", [provider])
    return Server(app, port=0).start()


def test_the_endpoints_make_a_clip_and_serve_it_with_ranges(tmp_path: Path) -> None:
    from tests.test_webui_listen_and_sync import _request

    provider = FakeProvider()
    server = _server(tmp_path, provider)
    headers = {"X-Ebook-Token": "t"}
    try:
        status, data, _ = _request(server.port, "GET", "/api/readaloud/voices", headers=headers)
        assert status == 200 and json.loads(data) == [
            {"id": "fake:ngoc", "name": "Ngọc", "provider": "fake", "online": False, "default": True, "language": "vi-VN", "gender": "",
             "gain_db": 0.0}]
        body = {"voice": "fake:ngoc", "text": "Xin chào các bạn."}
        status, data, _ = _request(server.port, "POST", "/api/readaloud/clip", headers=headers, body=body)
        clip = json.loads(data)
        assert status == 200 and clip["duration_ms"] == 1200 and len(clip["words"]) == 4
        assert clip["url"].startswith("/media/readaloud/") and clip["url"].endswith(".mp3")
        assert _request(server.port, "POST", "/api/readaloud/clip", headers=headers, body=body)[0] == 200
        assert len(provider.calls) == 1
        status, audio, response = _request(server.port, "GET", clip["url"], headers=headers)
        assert status == 200 and response["Content-Type"] == "audio/mpeg" and response["Accept-Ranges"] == "bytes" and len(audio) == 3 + 1024
        status, part, response = _request(server.port, "GET", clip["url"], headers={**headers, "Range": "bytes=3-9"})
        assert status == 206 and part == audio[3:10] and response["Content-Range"] == f"bytes 3-9/{len(audio)}"
        cached = {**body, "cachedOnly": True}
        assert _request(server.port, "POST", "/api/readaloud/clip", headers=headers, body=cached)[0] == 200
        status, data, _ = _request(server.port, "POST", "/api/readaloud/clip", headers=headers, body={**cached, "text": "Chưa có."})
        assert status == 404 and json.loads(data)["reason"] == "uncached"
        assert _request(server.port, "GET", "/media/readaloud/" + "0" * 64 + ".mp3", headers=headers)[0] == 404
        assert _request(server.port, "GET", clip["url"])[0] == 401
        status, data, _ = _request(server.port, "POST", "/api/readaloud/clip", headers=headers, body={"voice": "fake:ngoc"})
        assert status == 400
    finally:
        server.stop()


@pytest.mark.parametrize("reason,status", [("offline", 503), ("timeout", 504), ("rejected", 502), ("service", 502)])
def test_provider_failures_become_json_errors_with_a_reason(tmp_path: Path, reason: str, status: int) -> None:
    from tests.test_webui_listen_and_sync import _request

    server = _server(tmp_path, FakeProvider(fail=VoiceError("Không có mạng để dùng giọng trực tuyến.", reason)))
    try:
        got, data, _ = _request(server.port, "POST", "/api/readaloud/clip", headers={"X-Ebook-Token": "t"},
                                body={"voice": "fake:ngoc", "text": "Xin chào"})
        assert got == status
        payload = json.loads(data)
        assert payload["reason"] == reason and payload["error"]
        got, data, _ = _request(server.port, "POST", "/api/readaloud/clip", headers={"X-Ebook-Token": "t"},
                                body={"voice": "fake:la", "text": "Xin chào"})
        assert got == HTTPStatus.BAD_REQUEST and json.loads(data)["reason"] == "voice"
    finally:
        server.stop()


# ---- giọng của máy Windows --------------------------------------------------------------------------------------------------


@pytest.mark.skipif(not windows.available(), reason="cần Windows + PowerShell")
def test_the_windows_helper_makes_a_wav_with_word_cues(tmp_path: Path) -> None:
    """Giọng nào cài sẵn cũng được (máy dev có thể chỉ có en-US): thử chính đoạn PowerShell, ghi WAV ra file - không phát ra loa."""
    listed = windows._run(tmp_path, {"mode": "list"}).get("voices") or []
    if not listed:
        pytest.skip("máy không có giọng OneCore nào")
    text = "Hello there, how are you today?"
    made = windows.synthesize(tmp_path, listed[0]["id"], text)
    assert made.ext == "wav" and made.audio[:4] == b"RIFF" and made.duration_ms > 500
    assert [piece.text for piece in made.boundaries][:2] == ["Hello", "there"] and made.boundaries[0].char == 0
    words = map_boundaries(text, made.boundaries, made.duration_ms)
    _check_shape(text, words, made.duration_ms)
    assert windows.voices(tmp_path / "x") == [] or all(v.language.lower().startswith("vi") for v in windows.voices(tmp_path / "x"))


# ---- dịch vụ thật (tắt mặc định) -------------------------------------------------------------------------------------------


@NET
def test_the_real_edge_service_returns_mp3_and_word_boundaries() -> None:
    text = "Xin chào các bạn, hôm nay trời đẹp lắm."
    made = edge.EdgeClient().synthesize(text, edge.DEFAULT_VOICE)
    assert made.audio[:3] in (b"ID3", b"\xff\xfb", b"\xff\xf3") or made.audio[0] == 0xFF
    words = map_boundaries(text, made.boundaries, made.duration_ms)
    assert len(words) == len(text.split()) and made.duration_ms > 1000
    _check_shape(text, words, made.duration_ms)
