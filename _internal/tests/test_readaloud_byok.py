"""Giọng trực tuyến dùng khoá của người dùng (abook/readaloud/byok.py + azure / google / fpt / viettel): mọi bài thử nói chuyện với máy chủ
GIẢ trên máy này - không khoá thật, không gọi dịch vụ trả tiền nào."""
from __future__ import annotations

import base64
import json
import socket
import struct
import threading
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

from abook.readaloud import azure, byok, fpt, google, mp3, spread, viettel
from abook.readaloud import websocket as ws
from abook.readaloud.keys import KeyStore, mask
from abook.readaloud.mapping import map_boundaries
from abook.readaloud.model import VoiceError
from abook.readaloud.service import ReadAloud

SPREAD = Path(__file__).parent / "fixtures" / "readaloud" / "spread"
KEY = "test-key-0123456789abcdef"  # khoá giả của bài thử


def frames(count: int, *, mpeg1: bool = False) -> bytes:
    """`count` khung MP3 lớp III giả: MPEG-2 32 kbps 24 kHz (96 byte, 24 ms) hay MPEG-1 128 kbps 44,1 kHz (417/418 byte, 26,12 ms)."""
    if mpeg1:
        return b"".join(bytes([0xFF, 0xFB, 0x90 | (0x02 if i % 3 == 0 else 0), 0x64]) + b"\0" * (417 + (1 if i % 3 == 0 else 0) - 4)
                        for i in range(count))
    return (bytes([0xFF, 0xF3, 0x44, 0xC4]) + b"\0" * 92) * count


# ---- MP3 và chia theo âm tiết ------------------------------------------------------------------------------------------------


def test_mp3_duration_counts_frames_and_skips_tags_and_junk() -> None:
    assert mp3.duration_ms(frames(50)) == 1200
    id3 = b"ID3\x04\x00\x00" + bytes([0, 0, 0, 20]) + b"\0" * 20
    assert mp3.duration_ms(id3 + frames(25) + b"junk" + id3 + frames(25)) == 1200  # hai dòng nối nhau, mỗi dòng có thẻ riêng
    assert mp3.duration_ms(frames(38, mpeg1=True)) == 38 * 26122 // 1000
    assert mp3.duration_ms(b"") == 0 and mp3.duration_ms(b"\xff\xff\xff\xff" * 10) == 0


CASES = sorted(SPREAD.glob("*.json"))


def test_there_are_shared_spread_fixtures() -> None:
    assert len(CASES) >= 5


@pytest.mark.parametrize("path", CASES, ids=[path.stem for path in CASES])
def test_spread_matches_the_shared_fixtures(path: Path) -> None:
    case = json.loads(path.read_text(encoding="utf-8"))
    found = spread.boundaries(case["text"], case["durationMs"])
    assert map_boundaries(case["text"], found, case["durationMs"]) == case["words"]


def test_spread_marks_each_spoken_word_with_its_position() -> None:
    found = spread.boundaries("Ừ, đi thôi.", 1600)
    assert [(b.text, b.start_ms, b.end_ms, b.char) for b in found] == [("Ừ,", 0, 400, 0), ("đi", 800, 1200, 3), ("thôi.", 1200, 1600, 6)]
    assert spread.boundaries("Xin chào", 0) == []


# ---- kho khoá -----------------------------------------------------------------------------------------------------------------


def test_keys_live_in_their_own_file_and_are_only_shown_masked(tmp_path: Path) -> None:
    keys = KeyStore(tmp_path / "voice-keys.json")
    keys.put("azure", f"  {KEY} ", "SouthEastAsia")
    assert keys.get("azure") == {"key": KEY, "region": "southeastasia", "valid": False, "voices": []}
    shown = keys.public("azure")
    assert shown == {"hasKey": True, "masked": "••••cdef", "region": "southeastasia", "valid": False, "voices": 0}
    assert KEY not in json.dumps(shown) and KEY not in repr(keys)
    assert mask("short") == "••••" and mask("") == ""
    keys.mark("azure", True, [["vi-VN-HoaiMyNeural", "Hoài My"]])
    again = KeyStore(tmp_path / "voice-keys.json")
    assert again.get("azure")["valid"] is True and again.public("azure")["voices"] == 1
    assert (tmp_path / "voice-keys.json").read_bytes().count(b"\r\n") == 0
    again.put("azure", "another-key-9999", "eastus")  # đổi khoá: phải kiểm tra lại
    assert again.get("azure")["valid"] is False and again.get("azure")["voices"] == []
    again.remove("azure")
    assert again.public("azure")["hasKey"] is False


# ---- máy chủ HTTP giả -----------------------------------------------------------------------------------------------------------


class FakeHttp:
    """Máy chủ HTTP giả: `routes[(phương thức, đường dẫn)] = hàm(yêu cầu) -> (mã, header, thân)`; ghi lại mọi yêu cầu."""

    def __init__(self) -> None:
        self.routes: dict[tuple[str, str], Callable[[dict[str, Any]], tuple[int, dict[str, str], bytes]]] = {}
        self.seen: list[dict[str, Any]] = []
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args: Any) -> None:
                pass

            def _handle(self) -> None:
                length = int(self.headers.get("Content-Length") or 0)
                request = {"method": self.command, "path": self.path, "headers": {k.lower(): v for k, v in self.headers.items()},
                           "body": self.rfile.read(length) if length else b""}
                fake.seen.append(request)
                route = fake.routes.get((self.command, self.path.split("?")[0]))
                status, headers, body = route(request) if route else (404, {}, b"{}")
                self.send_response(status)
                for name, value in headers.items():
                    self.send_header(name, value)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            do_GET = do_POST = _handle

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def http():
    servers: list[FakeHttp] = []

    def make() -> FakeHttp:
        server = FakeHttp()
        servers.append(server)
        return server

    yield make
    for server in servers:
        server.close()


def _store(tmp_path: Path, provider: str, region: str = "", valid: bool = True, voices: list[list[str]] | None = None) -> KeyStore:
    keys = KeyStore(tmp_path / "voice-keys.json")
    keys.put(provider, KEY, region)
    if valid:
        keys.mark(provider, True, voices or [["v", "V"]])
    return keys


def _no_key_in_urls(server: FakeHttp) -> None:
    assert all(KEY not in request["path"] for request in server.seen)


# ---- Google ------------------------------------------------------------------------------------------------------------------


def _google(server: FakeHttp, *, step: int = 300) -> None:
    def synth(request: dict[str, Any]) -> tuple[int, dict[str, str], bytes]:
        if request["headers"].get("x-goog-api-key") != KEY:
            return 400, {}, json.dumps({"error": {"code": 400, "message": "API key not valid. Please pass a valid API key.",
                                                  "status": "INVALID_ARGUMENT", "details": [{"reason": "API_KEY_INVALID"}]}}).encode()
        payload = json.loads(request["body"])
        marks = [part.split('"')[0] for part in payload["input"]["ssml"].split('<mark name="')[1:]]
        points = [{"markName": name, "timeSeconds": index * step / 1000} for index, name in enumerate(marks)]
        audio = frames(len(marks) * step // 24)
        return 200, {"Content-Type": "application/json"}, json.dumps(
            {"audioContent": base64.b64encode(audio).decode(), "timepoints": points, "audioConfig": {}}).encode()

    server.routes[("POST", "/v1beta1/text:synthesize")] = synth
    server.routes[("GET", "/v1/voices")] = lambda request: (200, {}, json.dumps({"voices": [
        {"languageCodes": ["vi-VN"], "name": "vi-VN-Wavenet-A", "ssmlGender": "FEMALE", "naturalSampleRateHertz": 24000},
        {"languageCodes": ["vi-VN"], "name": "vi-VN-Chirp3-HD-Achernar", "ssmlGender": "FEMALE"},
        {"languageCodes": ["vi-VN"], "name": "vi-VN-Standard-B", "ssmlGender": "MALE"},
        {"languageCodes": ["en-US"], "name": "en-US-Neural2-A"}]}).encode())


def test_google_sends_marks_in_ssml_and_maps_timepoints_to_words(tmp_path: Path, http) -> None:
    server = http()
    _google(server)
    provider = google.GoogleProvider(_store(tmp_path, "google"), base=server.base)
    made = provider.synthesize("Xin chào, các bạn & tôi.", "vi-VN-Wavenet-A")
    request = server.seen[-1]
    payload = json.loads(request["body"])
    assert payload["voice"] == {"languageCode": "vi-VN", "name": "vi-VN-Wavenet-A"}
    assert payload["audioConfig"] == {"audioEncoding": "MP3"} and payload["enableTimePointing"] == ["SSML_MARK"]
    assert payload["input"]["ssml"] == ('<speak><mark name="0"/>Xin <mark name="1"/>chào, <mark name="2"/>các <mark name="3"/>bạn '
                                        '<mark name="4"/>&amp; <mark name="5"/>tôi. <mark name="end"/></speak>')
    assert request["headers"]["x-goog-api-key"] == KEY
    _no_key_in_urls(server)
    assert made.duration_ms == 6 * 300 + 300 - 12  # 7 mốc x 300 ms = 87 khung 24 ms
    words = map_boundaries("Xin chào, các bạn & tôi.", made.boundaries, made.duration_ms)
    assert words[:3] == [[0, 300], [300, 600], [600, 900]] and words[4] == [1200, 1500]


def test_google_long_paragraphs_go_in_several_calls_with_offsets(tmp_path: Path, http) -> None:
    server = http()
    _google(server, step=48)
    provider = google.GoogleProvider(_store(tmp_path, "google"), base=server.base)
    text = " ".join(f"chữ{index}" for index in range(900))
    made = provider.synthesize(text, "vi-VN-Wavenet-A")
    calls = [request for request in server.seen if request["method"] == "POST"]
    assert len(calls) >= 2 and all(len(json.loads(call["body"])["input"]["ssml"].encode()) <= 5000 for call in calls)
    words = map_boundaries(text, made.boundaries, made.duration_ms)
    assert len(words) == 900 and all(b >= a for a, b in zip([w[0] for w in words], [w[0] for w in words[1:]]))
    assert words[-1][1] <= made.duration_ms and words[-1][0] > words[0][0]


def test_google_check_lists_only_marked_vietnamese_voices_and_an_invalid_key_says_auth(tmp_path: Path, http) -> None:
    server = http()
    _google(server)
    keys = _store(tmp_path, "google", valid=False)
    provider = google.GoogleProvider(keys, base=server.base)
    assert provider.voices() == []  # chưa kiểm tra: chưa hiện giọng nào
    assert provider.check() == {"ok": True, "voices": 2}
    assert [v.id for v in provider.voices()] == ["google:vi-VN-Standard-B", "google:vi-VN-Wavenet-A"]
    assert [v.name for v in provider.voices()] == ["Standard B (Google Cloud)", "WaveNet A (Google Cloud)"]
    assert [v.gender for v in provider.voices()] == ["male", "female"]
    keys.put("google", "wrong-key-000000")
    result = provider.check()
    assert result["ok"] is False and result["reason"] == "auth" and "wrong-key" not in result["message"]
    assert provider.voices() == []


# ---- Azure (WebSocket giả + REST giả) --------------------------------------------------------------------------------------------


def _server_frame(opcode: int, payload: bytes) -> bytes:
    head = bytes([0x80 | opcode])
    if len(payload) < 126:
        return head + bytes([len(payload)]) + payload
    return head + bytes([126]) + struct.pack(">H", len(payload)) + payload if len(payload) < 65536 else \
        head + bytes([127]) + struct.pack(">Q", len(payload)) + payload


class FakeAzure:
    """Máy chủ WebSocket giả nói giao thức tổng hợp của Speech SDK; `close_with`: đóng giữa lượt bằng (mã, lý do); `status`: từ chối bắt tay."""

    def __init__(self, *, status: int = 101, close_with: tuple[int, str] | None = None) -> None:
        self.status = status
        self.close_with = close_with
        self.handshakes: list[str] = []
        self.messages: list[str] = []
        self.listener = socket.socket()
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen(5)
        self.port = self.listener.getsockname()[1]
        threading.Thread(target=self._serve, daemon=True).start()

    def close(self) -> None:
        self.listener.close()

    def _serve(self) -> None:
        while True:
            try:
                conn, _ = self.listener.accept()
            except OSError:
                return
            with conn:
                raw = b""
                while b"\r\n\r\n" not in raw:
                    raw += conn.recv(4096)
                text = raw.decode("latin-1")
                self.handshakes.append(text)
                if self.status != 101:
                    conn.sendall(f"HTTP/1.1 {self.status} No\r\nContent-Length: 0\r\n\r\n".encode())
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

        sent = [ws.read_frame(receive)[2].decode() for _ in range(3)]
        self.messages += sent
        if self.close_with:
            code, reason = self.close_with
            conn.sendall(_server_frame(ws.CLOSE, struct.pack(">H", code) + reason.encode()))
            return
        spoken = sent[2].split("'>", 2)[2].split("</voice>")[0]
        conn.sendall(_server_frame(ws.TEXT, b"Path:turn.start\r\nX-RequestId:1\r\n\r\n{}"))
        conn.sendall(_server_frame(ws.TEXT, b"Path:something.new\r\nX-RequestId:1\r\n\r\n{}"))  # tin lạ: Azure bỏ qua
        for index, word in enumerate(spoken.split()):
            meta = {"Metadata": [{"Type": "WordBoundary", "Data": {"Offset": index * 4_000_000, "Duration": 3_000_000,
                                                                    "text": {"Text": word, "Length": len(word), "BoundaryType": "WordBoundary"}}}]}
            conn.sendall(_server_frame(ws.TEXT, b"Path:audio.metadata\r\nX-RequestId:1\r\n\r\n" + json.dumps(meta).encode()))
        head = b"Path:audio\r\nX-RequestId:1\r\nX-StreamId:1"
        conn.sendall(_server_frame(ws.BINARY, struct.pack(">H", len(head)) + head + b"A" * 12000))  # 12000 byte @ 48 kbps = 2 s
        conn.sendall(_server_frame(ws.TEXT, b"Path:turn.end\r\nX-RequestId:1\r\n\r\n{}"))
        conn.sendall(_server_frame(ws.CLOSE, struct.pack(">H", 1000)))


@pytest.fixture
def fake_azure():
    servers: list[FakeAzure] = []

    def make(**options: Any) -> FakeAzure:
        server = FakeAzure(**options)
        servers.append(server)
        return server

    yield make
    for server in servers:
        server.close()


def test_azure_speaks_the_sdk_protocol_with_the_key_in_a_header(tmp_path: Path, fake_azure) -> None:
    server = fake_azure()
    provider = azure.AzureProvider(_store(tmp_path, "azure", "southeastasia"), host="127.0.0.1", port=server.port, secure=False)
    made = provider.synthesize("Xin chào các bạn.", "vi-VN-HoaiMyNeural")
    handshake = server.handshakes[0]
    assert handshake.startswith(f"GET {azure.WS_PATH} HTTP/1.1") and KEY not in handshake.split("\r\n")[0]
    assert f"Ocp-Apim-Subscription-Key: {KEY}" in handshake and "X-ConnectionId: " in handshake
    config, context, ssml = server.messages
    assert "Path:speech.config" in config and "Path:synthesis.context" in context and "Path:ssml" in ssml
    options = json.loads(context.split("\r\n\r\n", 1)[1])["synthesis"]["audio"]
    assert options["metadataOptions"]["wordBoundaryEnabled"] == "true" and options["outputFormat"] == azure.OUTPUT_FORMAT
    assert "<voice name='vi-VN-HoaiMyNeural'>Xin chào các bạn.</voice>" in ssml
    assert len({line for message in server.messages for line in message.split("\r\n") if line.startswith("X-RequestId:")}) == 1
    assert made.duration_ms == 2000 and [(b.text, b.start_ms, b.end_ms) for b in made.boundaries][:2] == [("Xin", 0, 300), ("chào", 400, 700)]


@pytest.mark.parametrize("status,reason", [(401, "auth"), (429, "quota"), (500, "service")])
def test_azure_handshake_refusals_carry_a_reason(tmp_path: Path, fake_azure, status: int, reason: str) -> None:
    server = fake_azure(status=status)
    keys = _store(tmp_path, "azure", "eastus")
    provider = azure.AzureProvider(keys, host="127.0.0.1", port=server.port, secure=False)
    with pytest.raises(VoiceError) as caught:
        provider.synthesize("Xin chào", "vi-VN-HoaiMyNeural")
    assert caught.value.reason == reason and KEY not in str(caught.value)
    assert keys.get("azure")["valid"] is (reason != "auth")  # khoá bị từ chối: giọng thôi hiện


def test_azure_quota_closed_mid_turn_is_a_quota_error(tmp_path: Path, fake_azure) -> None:
    server = fake_azure(close_with=(1007, "Quota exceeded for this subscription"))
    provider = azure.AzureProvider(_store(tmp_path, "azure", "eastus"), host="127.0.0.1", port=server.port, secure=False)
    with pytest.raises(VoiceError) as caught:
        provider.synthesize("Xin chào", "vi-VN-HoaiMyNeural")
    assert caught.value.reason == "quota"


def test_azure_voices_come_from_the_rest_list_filtered_to_vietnamese(tmp_path: Path, http) -> None:
    server = http()
    server.routes[("GET", azure.VOICES_PATH)] = lambda request: (
        (200, {}, json.dumps([{"ShortName": "vi-VN-HoaiMyNeural", "LocalName": "Hoài My", "Locale": "vi-VN", "Gender": "Female"},
                              {"ShortName": "en-US-JennyNeural", "LocalName": "Jenny", "Locale": "en-US"},
                              {"ShortName": "vi-VN-NamMinhNeural", "LocalName": "Nam Minh", "Locale": "vi-VN", "Gender": "Male"}]).encode())
        if request["headers"].get("ocp-apim-subscription-key") == KEY else (401, {}, b""))
    port = int(server.base.rsplit(":", 1)[1])
    provider = azure.AzureProvider(_store(tmp_path, "azure", "eastus", valid=False), host="127.0.0.1", port=port, secure=False)
    assert provider._voices(provider.keys.get("azure")) == [["vi-VN-HoaiMyNeural", "Hoài My", "female"], ["vi-VN-NamMinhNeural", "Nam Minh", "male"]]
    _no_key_in_urls(server)
    bad = azure.AzureProvider(_store(tmp_path, "azure", "not a region!", valid=False), host="127.0.0.1", port=port, secure=False)
    assert bad.check()["reason"] == "auth"


# ---- FPT.AI ------------------------------------------------------------------------------------------------------------------


def test_fpt_posts_plain_text_then_polls_the_async_link(tmp_path: Path, http) -> None:
    server = http()
    polls = {"count": 0}

    def ask(request: dict[str, Any]) -> tuple[int, dict[str, str], bytes]:
        if request["headers"].get("api_key") != KEY:
            return 401, {}, json.dumps({"message": "Invalid authentication credentials"}).encode()
        return 200, {"Content-Type": "application/json"}, json.dumps(
            {"async": f"{server.base}/file/1.mp3", "error": 0, "message": "...", "request_id": "1"}).encode()

    def file(request: dict[str, Any]) -> tuple[int, dict[str, str], bytes]:
        polls["count"] += 1
        return (404, {}, b"") if polls["count"] < 3 else (200, {"Content-Type": "audio/mpeg"}, frames(50))

    server.routes[("POST", "/hmi/tts/v5")] = ask
    server.routes[("GET", "/file/1.mp3")] = file
    provider = fpt.FptProvider(_store(tmp_path, "fpt"), url=f"{server.base}/hmi/tts/v5", poll_seconds=0.01)
    made = provider.synthesize("Xin chào các bạn.", "banmai")
    post = server.seen[0]
    assert post["body"].decode("utf-8") == "Xin chào các bạn." and post["headers"]["voice"] == "banmai"
    assert post["headers"]["api_key"] == KEY and post["headers"]["format"] == "mp3"
    assert all("api_key" not in request["headers"] for request in server.seen[1:])  # link tải file không kèm khoá
    assert polls["count"] == 3 and made.duration_ms == 1200
    assert map_boundaries("Xin chào các bạn.", made.boundaries, made.duration_ms) == [[0, 300], [300, 600], [600, 900], [900, 1200]]


def test_fpt_errors_become_reasons(tmp_path: Path, http) -> None:
    server = http()
    answers = iter([(401, {}, b'{"message":"Invalid authentication credentials"}'),
                    (200, {}, json.dumps({"error": 1, "message": "Quota exceeded"}).encode()),
                    (429, {}, b'{"message":"API rate limit exceeded"}')])
    server.routes[("POST", "/hmi/tts/v5")] = lambda request: next(answers)
    provider = fpt.FptProvider(_store(tmp_path, "fpt"), url=f"{server.base}/hmi/tts/v5", poll_seconds=0.01)
    reasons = []
    for _ in range(3):
        with pytest.raises(VoiceError) as caught:
            provider._synthesize({"key": KEY}, "Xin chào", "banmai")
        reasons.append(caught.value.reason)
    assert reasons == ["auth", "quota", "quota"]


# ---- Viettel AI --------------------------------------------------------------------------------------------------------------


def test_viettel_posts_json_and_spreads_syllables(tmp_path: Path, http) -> None:
    server = http()
    server.routes[("POST", "/tts/speech_synthesis")] = lambda request: (
        (200, {"Content-Type": "audio/mpeg"}, frames(100)) if request["headers"].get("token") == KEY
        else (401, {"Content-Type": "application/json"}, json.dumps({"vi_message": "Token không hợp lệ"}).encode()))
    server.routes[("GET", "/tts/voices")] = lambda request: (200, {}, json.dumps([
        {"name": "Quỳnh Anh chất lượng cao", "description": "Nữ miền Bắc", "code": "hn-quynhanh", "location": "BAC"},
        {"name": "Minh Quân", "description": "Nam miền Nam", "code": "hcm-minhquan", "location": "NAM"}]).encode())
    keys = _store(tmp_path, "viettel", valid=False)
    provider = viettel.ViettelProvider(keys, base=server.base)
    assert provider.check() == {"ok": True, "voices": 2}
    assert [v.name for v in provider.voices()] == ["Quỳnh Anh - miền Bắc (Viettel AI)", "Minh Quân - miền Nam (Viettel AI)"]
    assert [v.gender for v in provider.voices()] == ["female", "male"]
    made = provider.synthesize("Ừ, đi thôi. Nhanh lên!", "hn-quynhanh")
    payload = json.loads(server.seen[-1]["body"])
    assert payload == {"text": "Ừ, đi thôi. Nhanh lên!", "voice": "hn-quynhanh", "speed": 1.0, "tts_return_option": 3, "token": KEY,
                       "without_filter": False}
    _no_key_in_urls(server)
    assert made.duration_ms == 2400
    assert map_boundaries("Ừ, đi thôi. Nhanh lên!", made.boundaries, 2400) == [[0, 300], [600, 900], [900, 1200], [1800, 2100], [2100, 2400]]
    keys.put("viettel", "wrong-key-000000")
    keys.mark("viettel", True, [["hn-quynhanh", "Q"]])
    with pytest.raises(VoiceError) as caught:
        provider.synthesize("Xin chào", "hn-quynhanh")
    assert caught.value.reason == "auth" and "Token không hợp lệ" in str(caught.value) and provider.voices() == []


def test_long_text_for_estimated_voices_goes_in_pieces_with_offsets() -> None:
    sent: list[str] = []

    def speak(piece: str) -> bytes:
        sent.append(piece)
        return frames(len(piece.split()) * 10)  # 240 ms mỗi chữ

    text = " ".join(["chữ"] * 30)
    made = byok.estimated_synthesis(text, 40, speak, "Giả")
    assert len(sent) > 1 and " ".join(sent) == text
    words = map_boundaries(text, made.boundaries, made.duration_ms)
    assert made.duration_ms == 30 * 240 and words[0] == [0, 240] and words[-1] == [29 * 240, 30 * 240]


# ---- không theo chuyển hướng (khoá không đi sang máy khác) ---------------------------------------------------------------------


def test_a_redirect_is_not_followed_so_the_key_never_reaches_another_host(tmp_path: Path, http) -> None:
    elsewhere = http()
    server = http()
    server.routes[("POST", "/v1beta1/text:synthesize")] = lambda request: (302, {"Location": f"{elsewhere.base}/steal"}, b"")
    provider = google.GoogleProvider(_store(tmp_path, "google"), base=server.base)
    with pytest.raises(VoiceError) as caught:
        provider.synthesize("Xin chào", "vi-VN-Wavenet-A")
    assert caught.value.reason == "rejected" and elsewhere.seen == []


def test_a_closed_port_is_offline() -> None:
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    with pytest.raises(VoiceError) as caught:
        byok.request("GET", f"http://127.0.0.1:{port}/", {}, name="Giả", timeout=2)
    assert caught.value.reason == "offline"


# ---- dịch vụ đọc to + máy chủ giao diện ------------------------------------------------------------------------------------------


def test_keyed_voices_join_the_list_only_once_checked_and_a_revoked_key_says_auth(tmp_path: Path) -> None:
    keys = KeyStore(tmp_path / "voice-keys.json")
    service = ReadAloud(tmp_path / "cache", keys=keys)
    assert [p for p in service.providers] == ["edge", "azure", "google", "fpt", "viettel", "device"]
    assert [item["id"] for item in service.online_providers()] == ["azure", "google", "fpt", "viettel"]
    assert all(item["hasKey"] is False and item["limits"]["free"] for item in service.online_providers())
    keys.put("fpt", KEY)
    assert not [v for v in service.providers["fpt"].voices()]
    keys.mark("fpt", True, [["banmai", "Ban Mai - nữ miền Bắc"]])
    assert [v.id for v in service.providers["fpt"].voices()] == ["fpt:banmai"]
    keys.mark("fpt", False)
    with pytest.raises(VoiceError) as caught:
        service.clip("fpt:banmai", "Xin chào")
    assert caught.value.reason == "auth"


def test_the_endpoints_store_mask_check_and_remove_keys(tmp_path: Path, monkeypatch) -> None:
    from abook.webui.actions import FakeRunner
    from abook.webui.library import Preferences
    from abook.webui.listening import Listening
    from abook.webui.server import App, Server
    from tests.test_webui_listen_and_sync import _request

    preferences = Preferences(tmp_path / "prefs" / "preferences.json")
    preferences.update({"libraryRoot": str(tmp_path / "lib")})
    app = App(preferences=preferences, runner=FakeRunner(), token="t", listening=Listening(tmp_path / "prefs" / "listening.json"))
    monkeypatch.setattr(fpt.FptProvider, "_synthesize", lambda self, entry, text, voice: (_ for _ in ()).throw(
        VoiceError("Khoá FPT.AI đã hết hạn mức.", "quota")))
    server = Server(app, port=0).start()
    headers = {"X-Ebook-Token": "t"}
    try:
        status, data, _ = _request(server.port, "PUT", "/api/readaloud/online/fpt", headers=headers, body={"key": KEY})
        shown = json.loads(data)
        assert status == 200 and shown["masked"] == "••••cdef" and shown["hasKey"] and not shown["valid"]
        assert KEY in (tmp_path / "prefs" / "voice-keys.json").read_text(encoding="utf-8")
        assert KEY not in (tmp_path / "prefs" / "preferences.json").read_text(encoding="utf-8")
        status, data, _ = _request(server.port, "GET", "/api/readaloud/online", headers=headers)
        assert status == 200 and KEY not in data.decode("utf-8")
        status, data, _ = _request(server.port, "GET", "/api/preferences", headers=headers)
        assert KEY not in data.decode("utf-8")
        status, data, _ = _request(server.port, "POST", "/api/readaloud/online/fpt/check", headers=headers, body={})
        result = json.loads(data)
        assert status == 200 and result["ok"] is False and result["reason"] == "quota" and result["provider"]["valid"] is False
        assert _request(server.port, "PUT", "/api/readaloud/online/azure", headers=headers, body={"key": KEY, "region": "../x"})[0] == 400
        assert _request(server.port, "PUT", "/api/readaloud/online/other", headers=headers, body={"key": KEY})[0] == 404
        assert _request(server.port, "GET", "/api/readaloud/online")[0] == 401
        status, data, _ = _request(server.port, "DELETE", "/api/readaloud/online/fpt", headers=headers)
        assert status == 200 and json.loads(data)["hasKey"] is False
    finally:
        server.stop()



def test_syllable_counts_are_the_shared_contract_with_the_phone() -> None:
    from abook.webui.word_timing import syllable_count

    counts = json.loads((SPREAD / "syllables" / "counts.json").read_text(encoding="utf-8"))["counts"]
    assert len(counts) >= 20
    assert {token: syllable_count(token) for token in counts} == counts


def test_voices_carry_a_gender_hint(tmp_path: Path) -> None:
    from abook.readaloud import windows

    assert [windows.gender(value) for value in ("Female", "male", 0, "1", None)] == ["female", "male", "male", "female", ""]
    service = ReadAloud(tmp_path / "cache", [__import__("abook.readaloud.service", fromlist=["x"]).EdgeProvider()])
    assert [voice["gender"] for voice in service.voices()] == ["female", "male"]


def test_an_empty_key_keeps_the_stored_one_and_only_moves_the_region(tmp_path: Path) -> None:
    keys = KeyStore(tmp_path / "voice-keys.json")
    service = ReadAloud(tmp_path / "cache", keys=keys)
    with pytest.raises(ValueError):
        service.set_key("azure", "", "eastus")
    service.set_key("azure", KEY, "eastus")
    shown = service.set_key("azure", "  ", "southeastasia")
    assert shown["region"] == "southeastasia" and keys.get("azure")["key"] == KEY and shown["valid"] is False
