"""Edge phát luồng (uxfix56): `EdgeClient.synthesize(sink=...)` đưa tiếng + mốc ra ngay khi chắc chắn, theo đúng thứ tự, mà nối lại vẫn đúng bằng clip cuối."""
from __future__ import annotations

import itertools
import json
import socket
import struct
import threading
import time
from collections.abc import Callable

import pytest

from abook.readaloud import edge
from abook.readaloud import websocket as ws
from abook.readaloud.mapping import Boundary
from abook.readaloud.model import VoiceError
from tests.test_readaloud import FakeEdge, _server_frame, fake_edge  # noqa: F401 - fixture dùng chung

WORD_FRAMES = 10  # mỗi chữ 10 khung = 240 ms, chữ đọc 200 ms
TAIL_FRAMES = 60  # lặng đuôi 1,44 s: `trim_join_tail` luôn cắt được
SENTENCES = ("Trời đã sẩm tối khi đoàn người tới được cổng làng. Người gác cổng đứng chờ sẵn, tay cầm chiếc đèn dầu cũ. "
             "Họ im lặng bước vào sân, nơi mấy con chó nằm ngủ dưới hiên. Mưa bắt đầu rơi lúc nào không ai hay.")
LONG = f"{SENTENCES} {SENTENCES}"
UNIQUE = SENTENCES + " " + SENTENCES.replace("người", "kẻ")  # như LONG mà mọi mảnh khác chữ nhau (máy chủ giả nhận mảnh theo chữ; LONG có mảnh 4 trùng mảnh 1)


def mp3_frame(seed: int, index: int) -> bytes:
    """Khung MPEG-2 lớp III 24 kHz 48 kbps mono, 144 byte (đúng dạng `trim_join_tail` nhận ra), phần thân khác nhau theo (seed, index)."""
    return b"\xff\xf3\x64\xc0" + bytes((seed * 31 + index * 7 + k) % 251 for k in range(140))


def seed_of(text: str) -> int:
    return sum(map(ord, text)) % 997


class StreamingEdge(FakeEdge):
    """Máy chủ giả gửi tiếng DẦN như Edge thật: tin mốc từng chữ trước, rồi khung tiếng của chữ ấy (cắt ở chỗ lẻ cho khung MP3 trải qua ranh giới khung mạng).
    `pace(spoken)` = giây nghỉ giữa hai chữ; `junk(spoken)` thêm byte rác ở đuôi (khung lạ: không cắt được); `cut(spoken)` = số khung gửi rồi cắt ngang không `turn.end`
    (chỉ lượt đầu của chữ ấy); `vary(spoken)` = lượt thử lại ra tiếng khác; `hold`: chưa bật thì mọi lượt dừng trước khung cuối + `turn.end` (tối đa 10 giây)."""

    threaded = True

    def __init__(self, *, pace: Callable[[str], float] = lambda _: 0.0, junk: Callable[[str], bytes] = lambda _: b"",
                 cut: Callable[[str], int | None] = lambda _: None, vary: Callable[[str], bool] = lambda _: False,
                 dead: Callable[[str], bool] = lambda _: False, hold: threading.Event | None = None, **options) -> None:
        self.pace, self.junk, self.cut, self.vary, self.dead, self.hold = pace, junk, cut, vary, dead, hold
        self.turns: dict[str, int] = {}
        self.lock = threading.Lock()
        super().__init__(**options)

    def _reply(self, conn: socket.socket, spoken: str) -> None:
        with self.lock:
            self.turns[spoken] = turn = self.turns.get(spoken, 0) + 1
        if self.dead(spoken):
            return  # đóng ngay: mọi lượt của mảnh này bị cắt
        seed = seed_of(spoken) + (1 if turn > 1 and self.vary(spoken) else 0)
        stop_after = self.cut(spoken) if turn == 1 else None
        head = b"X-RequestId:1\r\nContent-Type:audio/mpeg\r\nPath:audio"
        conn.sendall(_server_frame(ws.TEXT, b"X-RequestId:1\r\nPath:turn.start\r\n\r\n{}"))
        sent = 0
        pending = b""
        for index, word in enumerate(spoken.split()):
            start = index * WORD_FRAMES * edge.MP3_FRAME_MS
            meta = {"Metadata": [{"Type": "WordBoundary", "Data": {"Offset": start * edge.TICKS_PER_MS, "Duration": 200 * edge.TICKS_PER_MS,
                                                                    "text": {"Text": word, "Length": len(word), "BoundaryType": "WordBoundary"}}}]}
            conn.sendall(_server_frame(ws.TEXT, b"Path:audio.metadata\r\n\r\n" + json.dumps(meta).encode()))
            pending += b"".join(mp3_frame(seed, sent + k) for k in range(WORD_FRAMES))
            sent += WORD_FRAMES
            while len(pending) >= 100:  # khung mạng 100 byte: khung MP3 144 byte trải qua ranh giới
                conn.sendall(_server_frame(ws.BINARY, struct.pack(">H", len(head)) + head + pending[:100]))
                pending = pending[100:]
            time.sleep(self.pace(spoken))
            if stop_after is not None and sent >= stop_after:
                return
        if self.hold is not None:
            self.hold.wait(10)
        pending += b"".join(mp3_frame(seed, sent + k) for k in range(TAIL_FRAMES)) + self.junk(spoken)
        conn.sendall(_server_frame(ws.BINARY, struct.pack(">H", len(head)) + head + pending))
        conn.sendall(_server_frame(ws.TEXT, b"X-RequestId:1\r\nPath:turn.end\r\n\r\n{}"))
        conn.sendall(_server_frame(ws.CLOSE, struct.pack(">H", 1000)))


class Recorder:
    """Một `StreamSink` ghi lại mọi thứ nhận được, kèm lúc nhận."""

    def __init__(self) -> None:
        self.audio_chunks: list[bytes] = []
        self.bound_chunks: list[list[Boundary]] = []
        self.events: list[tuple[float, str]] = []
        self.calls = 0
        self.on_first_audio: Callable[[], None] | None = None
        self.heard_first_audio_while_the_clip_was_unfinished = False
        self.cuts: list[int] = []

    def cut(self, words: int) -> None:
        self.cuts.append(words)
        self.events.append((time.monotonic(), "cut"))

    def audio(self, data: bytes) -> None:
        if not self.audio_chunks and self.on_first_audio is not None:
            self.heard_first_audio_while_the_clip_was_unfinished = True
            self.on_first_audio()
        self.calls += 1
        self.audio_chunks.append(data)
        self.events.append((time.monotonic(), "audio"))

    def boundaries(self, found: list[Boundary]) -> None:
        self.calls += 1
        self.bound_chunks.append(list(found))
        self.events.append((time.monotonic(), "bounds"))

    @property
    def audio_all(self) -> bytes:
        return b"".join(self.audio_chunks)

    @property
    def bounds_all(self) -> list[Boundary]:
        return [b for chunk in self.bound_chunks for b in chunk]


@pytest.fixture
def streaming():
    servers: list[StreamingEdge] = []

    def make(**options) -> tuple[StreamingEdge, edge.EdgeClient]:
        server = StreamingEdge(**options)
        servers.append(server)
        return server, edge.EdgeClient(host="127.0.0.1", port=server.port, secure=False, connect_timeout=2, read_timeout=3)

    yield make
    for server in servers:
        server.close()


@pytest.mark.parametrize("text,rank", [("Xin chào các bạn.", 0), (SENTENCES, 0), (SENTENCES, edge.RANK_BACKGROUND), (LONG, 0), (LONG, 3)],
                         ids=["một mảnh", "bốn câu rank 0", "bốn câu nền", "tám câu rank 0", "tám câu rank 3"])
def test_what_the_sink_hears_is_exactly_the_clip_that_comes_back(streaming, text: str, rank: int) -> None:
    _, client = streaming(pace=lambda _: 0.002)
    sink = Recorder()
    streamed = client.synthesize(text, edge.DEFAULT_VOICE, rank=rank, sink=sink)
    assert sink.audio_all == streamed.audio
    assert sink.bounds_all == streamed.boundaries
    plain = client.synthesize(text, edge.DEFAULT_VOICE, rank=rank)  # cùng máy chủ giả: phát luồng không đổi một byte, một mốc nào
    assert (streamed.audio, streamed.boundaries, streamed.duration_ms) == (plain.audio, plain.boundaries, plain.duration_ms)
    if len(edge.speech_pieces(text, rank)) > 1:
        assert len(streamed.audio) < len(edge.speech_pieces(text, rank)) * (len(text.split()) * WORD_FRAMES + TAIL_FRAMES) * edge.MP3_FRAME_BYTES, "mảnh đã bị cắt lặng đuôi"


def test_pieces_come_out_in_order_whatever_order_they_finish_in(streaming) -> None:
    pieces = edge.speech_pieces(LONG, 0)
    assert len(pieces) >= 4
    # Mảnh đầu chậm nhất, mảnh cuối nhanh nhất: các mảnh sau xong trước mảnh đầu mà không được phát chen lên trước.
    delays = {" ".join(piece.split()): 0.03 * (len(pieces) - index) for index, piece in enumerate(pieces)}
    _, client = streaming(pace=lambda spoken: delays.get(spoken, 0.0) / max(1, len(spoken.split())) * 3)
    sink = Recorder()
    streamed = client.synthesize(LONG, edge.DEFAULT_VOICE, rank=0, sink=sink)
    assert sink.audio_all == streamed.audio and sink.bounds_all == streamed.boundaries
    starts = [b.start_ms for b in sink.bounds_all]
    assert starts == sorted(starts), "mốc đưa ra theo thứ tự thời gian của clip"


def test_the_first_bytes_reach_the_sink_before_any_piece_is_done(streaming) -> None:
    gate = threading.Event()
    _, client = streaming(hold=gate)  # mọi mảnh dừng trước khung cuối: chỉ phát luồng thật mới cho sink nhận tiếng khi clip chưa xong
    sink = Recorder()
    sink.on_first_audio = gate.set
    done = client.synthesize(SENTENCES, edge.DEFAULT_VOICE, rank=0, sink=sink)
    assert sink.heard_first_audio_while_the_clip_was_unfinished
    assert sink.events[0][1] == "bounds", "mốc về trước tiếng của chính chữ ấy"
    assert sink.audio_all == done.audio


def test_a_piece_after_the_head_is_held_until_its_turn(streaming) -> None:
    # Mảnh đầu đọc chậm, các mảnh sau nhanh: trong lúc mảnh đầu đọc, sink chỉ nhận phần của mảnh đầu.
    pieces = edge.speech_pieces(SENTENCES, 0)
    assert len(pieces) >= 2
    first_spoken = " ".join(pieces[0].split())
    first_words = len(first_spoken.split())
    _, client = streaming(pace=lambda spoken: 0.03 if spoken == first_spoken else 0.0)
    sink = Recorder()
    result: dict[str, object] = {}
    thread = threading.Thread(target=lambda: result.update(done=client.synthesize(SENTENCES, edge.DEFAULT_VOICE, rank=0, sink=sink)))
    thread.start()
    time.sleep(0.03 * first_words * 0.5)  # giữa lúc mảnh đầu còn đang đọc
    sink_bytes_now = len(sink.audio_all)
    assert thread.is_alive(), "mảnh đầu còn đọc"
    assert sink_bytes_now <= first_words * WORD_FRAMES * edge.MP3_FRAME_BYTES, "chưa phát quá phần tiếng của chữ mảnh đầu đã đọc"
    assert all(b.start_ms <= first_words * WORD_FRAMES * edge.MP3_FRAME_MS for b in sink.bounds_all), "chưa có mốc của mảnh sau"
    thread.join(10)
    done = result["done"]
    assert sink.audio_all == done.audio and sink.bounds_all == done.boundaries  # type: ignore[attr-defined]


def test_a_piece_with_odd_frames_is_sent_whole(streaming) -> None:
    pieces = edge.speech_pieces(SENTENCES, 0)
    odd = " ".join(pieces[0].split())
    _, client = streaming(junk=lambda spoken: b"\x00" * 7 if spoken == odd else b"", pace=lambda _: 0.001)
    sink = Recorder()
    streamed = client.synthesize(SENTENCES, edge.DEFAULT_VOICE, rank=0, sink=sink)
    assert sink.audio_all == streamed.audio and sink.bounds_all == streamed.boundaries
    words = len(odd.split())
    assert streamed.audio.startswith(b"".join(mp3_frame(seed_of(odd), k) for k in range(words * WORD_FRAMES + TAIL_FRAMES)) + b"\x00" * 7), "mảnh lạ giữ nguyên cả đuôi"


def test_a_cut_turn_is_retried_and_the_sink_hears_the_clip_once(streaming) -> None:
    _, client = streaming(cut=lambda spoken: 30, pace=lambda _: 0.001)  # lượt đầu của mỗi mảnh bị cắt sau 30 khung, lượt thử lại đủ
    for text, rank in (("Một hai ba bốn năm sáu bảy tám chín mười.", 0), (SENTENCES, 0)):
        sink = Recorder()
        streamed = client.synthesize(text, edge.DEFAULT_VOICE, rank=rank, sink=sink)
        assert sink.audio_all == streamed.audio and sink.bounds_all == streamed.boundaries
        plain = streaming(pace=lambda _: 0.0)[1].synthesize(text, edge.DEFAULT_VOICE, rank=rank)
        assert (streamed.audio, streamed.boundaries) == (plain.audio, plain.boundaries)


def test_a_retry_that_says_something_else_after_bytes_went_out_fails_the_clip(streaming) -> None:
    _, client = streaming(cut=lambda spoken: 30, vary=lambda spoken: True, pace=lambda _: 0.001)
    sink = Recorder()
    with pytest.raises(edge.EdgeError):
        client.synthesize("Một hai ba bốn năm sáu bảy tám chín mười.", edge.DEFAULT_VOICE, rank=0, sink=sink)
    calls = sink.calls
    time.sleep(0.2)
    assert sink.calls == calls, "lỗi rồi thì sink không nhận gì thêm"
    first_turn = b"".join(mp3_frame(seed_of("Một hai ba bốn năm sáu bảy tám chín mười."), k) for k in range(100))
    assert sink.audio_all and first_turn.startswith(sink.audio_all), "phần đã phát là phần đầu đúng của lượt đầu"


def test_a_failed_piece_fails_the_clip_and_the_sink_gets_nothing_after(streaming) -> None:
    pieces = edge.speech_pieces(LONG, 0)
    dead = " ".join(pieces[2].split())
    _, client = streaming(dead=lambda spoken: spoken == dead, pace=lambda _: 0.002)
    sink = Recorder()
    with pytest.raises(edge.EdgeError):
        client.synthesize(LONG, edge.DEFAULT_VOICE, rank=0, sink=sink)
    calls = sink.calls
    time.sleep(0.3)
    assert sink.calls == calls
    # Phần đã phát là phần đầu đúng của clip (không rác, không chen).
    reference = streaming(pace=lambda _: 0.0)[1].synthesize(LONG, edge.DEFAULT_VOICE, rank=0)
    assert reference.audio.startswith(sink.audio_all) and reference.boundaries[:len(sink.bounds_all)] == sink.bounds_all


def test_a_failed_later_piece_is_told_at_once_and_the_pieces_before_it_still_play_to_the_end(streaming, monkeypatch) -> None:
    # uxfix63 (a59d e1): mảnh 3 hỏng khi mảnh 1-2 còn đang về. Trước: cả clip hỏng ngay, mảnh 1-2 bị cắt, người nghe chỉ còn phần đã phát. Giờ: sink biết NGAY tiếng dừng ở chữ đầu mảnh 3,
    # mảnh 1-2 vẫn về và phát hết, phần dở của mảnh 3 không bao giờ ra sink, rồi mới ném lỗi.
    monkeypatch.setattr(edge, "RETRIES", 0)
    pieces = edge.speech_pieces(UNIQUE, 0)
    spoken = [" ".join(piece.split()) for piece in pieces]
    before = len(spoken[0].split()) + len(spoken[1].split())
    _, client = streaming(cut=lambda text: 30 if text == spoken[2] else None, pace=lambda text: 0.08 if text in spoken[:2] else 0.002)
    sink = Recorder()
    with pytest.raises(edge.EdgeError):
        client.synthesize(UNIQUE, edge.DEFAULT_VOICE, rank=0, sink=sink)
    assert sink.cuts == [before], "báo một lần, đúng số chữ đứng trước mảnh hỏng"
    told = next(at for at, kind in sink.events if kind == "cut")
    assert any(kind == "audio" and at > told for at, kind in sink.events), "báo lúc các mảnh trước còn đang về"
    reference = streaming(pace=lambda _: 0.0)[1].synthesize(UNIQUE, edge.DEFAULT_VOICE, rank=0)
    assert sink.bounds_all == reference.boundaries[:before], "mảnh 1-2 phát đủ, không chữ nào của mảnh hỏng"
    assert reference.audio.startswith(sink.audio_all) and len(sink.audio_all) * 8000 // edge.BITRATE_BPS >= sink.bounds_all[-1].end_ms
    calls = sink.calls
    time.sleep(0.2)
    assert sink.calls == calls


def test_a_failed_first_piece_still_fails_at_once(streaming) -> None:
    text = UNIQUE
    pieces = edge.speech_pieces(text, 0)
    dead = " ".join(pieces[0].split())
    _, client = streaming(dead=lambda spoken: spoken == dead, pace=lambda _: 0.05)
    sink = Recorder()
    with pytest.raises(edge.EdgeError):
        client.synthesize(text, edge.DEFAULT_VOICE, rank=0, sink=sink)
    assert sink.cuts == [] and sink.calls == 0, "mảnh đầu hỏng: không có gì để phát nốt, hỏng ngay như cũ"


def test_an_error_before_any_byte_leaves_the_sink_empty(streaming) -> None:
    _, client = streaming(dead=lambda spoken: True)
    sink = Recorder()
    with pytest.raises(edge.EdgeError):
        client.synthesize("Xin chào các bạn.", edge.DEFAULT_VOICE, rank=0, sink=sink)
    assert sink.calls == 0


def test_without_a_sink_nothing_changes(streaming) -> None:
    _, client = streaming()
    plain = client.synthesize(SENTENCES, edge.DEFAULT_VOICE, rank=0)
    assert plain.audio and plain.boundaries


def test_read_turn_reports_each_frame_and_each_message_as_it_arrives() -> None:
    class Wire:
        def __init__(self, items) -> None:
            self.items = list(items)

        def recv(self):
            return self.items.pop(0)

    head = b"Path:audio"
    meta = b'Path:audio.metadata\r\n\r\n{"Metadata":[{"Type":"WordBoundary","Data":{"Offset":10000,"Duration":20000,"text":{"Text":"a"}}}]}'
    wire = Wire([(ws.TEXT, meta), (ws.BINARY, struct.pack(">H", len(head)) + head + b"xx"), (ws.BINARY, struct.pack(">H", len(head)) + head + b"yy"),
                 (ws.TEXT, b"Path:turn.end\r\n\r\n{}")])
    seen: list[object] = []
    audio, bounds = edge.read_turn(wire, 0, time.monotonic() + 5, on_audio=lambda data: seen.append(data), on_boundaries=lambda found: seen.append(found))
    assert seen == [[Boundary("a", 1, 3)], b"xx", b"yy"] and audio == b"xxyy" and bounds == [Boundary("a", 1, 3)]


# ---- ReadAloud.clip(stream=...) ----------------------------------------------------------------------------------------------------

VOICE = "edge:vi-VN-HoaiMyNeural"


class Listener:
    """Một `StreamListener` ghi lại mọi thứ."""

    def __init__(self, on_started: Callable[[], None] | None = None) -> None:
        self.events: list[str] = []
        self.chunks: list[bytes] = []
        self.words_calls: list[tuple[list[list[int]], int]] = []
        self.heard: list[int] = []
        self.on_started = on_started

    def started(self) -> None:
        self.events.append("started")
        if self.on_started is not None:
            self.on_started()

    def audio(self, data: bytes) -> None:
        self.events.append("audio")
        self.chunks.append(data)

    def words(self, words: list[list[int]], duration_ms: int, heard_ms: int = 0) -> None:
        self.events.append("words")
        self.words_calls.append((words, duration_ms))
        self.heard.append(heard_ms)

    def cut(self, word: int) -> None:
        self.events.append(f"cut {word}")


def make_service(tmp_path, client: edge.EdgeClient):
    from abook.readaloud.service import EdgeProvider, ReadAloud

    return ReadAloud(tmp_path / "cache", [EdgeProvider(client)])


def test_a_streamed_clip_starts_at_the_first_byte_and_ends_in_the_cache_exactly_as_if_it_had_not_streamed(streaming, tmp_path) -> None:
    gate = threading.Event()
    _, client = streaming(hold=gate)
    service = make_service(tmp_path, client)
    listener = Listener(on_started=gate.set)  # mọi mảnh đang chờ khung cuối: chỉ khi `started` gọi lúc clip chưa xong thì clip mới xong được
    clip = service.clip(VOICE, SENTENCES, rank=0, stream=listener)
    assert listener.events[0] == "started" and listener.events.count("started") == 1
    streamed_audio = b"".join(listener.chunks)
    assert streamed_audio == (tmp_path / "cache" / clip["file"]).read_bytes()
    again = service.clip(VOICE, SENTENCES, cached_only=True)
    assert again == clip and len(clip["words"]) == len(SENTENCES.split())
    # Mốc tạm: mỗi lần đủ số chữ hiện, không giảm, không vượt độ dài phần đã phát; lần cuối trước khi xong không dài hơn clip.
    assert listener.words_calls, "có mốc chữ tạm"
    for words, duration in listener.words_calls:
        assert len(words) == len(SENTENCES.split()) and duration <= clip["duration_ms"]
        assert all(a[0] <= b[0] for a, b in itertools.pairwise(words)) and all(end <= duration for _, end in words)
    # `heard_ms` (uxfix58): mốc hết chữ thật cuối cùng - không vượt độ dài phần đã phát, không giảm; chữ bắt đầu từ đó trở đi là chữ chưa tới, chữ trước đó đã kết thúc không sau nó.
    assert len(listener.heard) == len(listener.words_calls) and listener.heard[-1] > 0
    assert all(a <= b for a, b in itertools.pairwise(listener.heard))
    for (words, duration), heard in zip(listener.words_calls, listener.heard):
        assert heard <= duration and all(end <= heard for start, end in words if start < heard)
    # Cùng clip với bản không phát luồng (máy chủ giả khác, cùng nội dung).
    _, client2 = streaming()
    plain = make_service(tmp_path / "plain", client2).clip(VOICE, SENTENCES, rank=0)
    assert (plain["duration_ms"], plain["words"]) == (clip["duration_ms"], clip["words"])


def test_an_error_before_the_first_byte_is_a_plain_voice_error(streaming, tmp_path) -> None:
    _, client = streaming(dead=lambda spoken: True)
    service = make_service(tmp_path, client)
    listener = Listener()
    with pytest.raises(edge.EdgeError):
        service.clip(VOICE, "Xin chào các bạn.", rank=0, stream=listener)
    assert listener.events == []
    with pytest.raises(VoiceError):
        service.clip(VOICE, "Xin chào các bạn.", cached_only=True)


def test_an_error_after_the_first_byte_still_raises_the_voice_error(streaming, tmp_path) -> None:
    pieces = edge.speech_pieces(LONG, 0)
    dead = " ".join(pieces[2].split())
    _, client = streaming(dead=lambda spoken: spoken == dead, pace=lambda _: 0.002)
    service = make_service(tmp_path, client)
    listener = Listener()
    with pytest.raises(edge.EdgeError):
        service.clip(VOICE, LONG, rank=0, stream=listener)
    assert listener.events and listener.events[0] == "started"
    calls = len(listener.events)
    time.sleep(0.3)
    assert len(listener.events) == calls


def test_the_second_request_for_the_same_paragraph_waits_and_then_hits_the_cache(streaming, tmp_path) -> None:
    server, client = streaming(pace=lambda _: 0.01)
    service = make_service(tmp_path, client)
    first, second = Listener(), Listener()
    results: dict[str, dict] = {}
    one = threading.Thread(target=lambda: results.update(one=service.clip(VOICE, SENTENCES, rank=0, stream=first)))
    one.start()
    while not first.events:
        time.sleep(0.005)
    two = threading.Thread(target=lambda: results.update(two=service.clip(VOICE, SENTENCES, rank=0, stream=second)))
    two.start()
    one.join(20)
    two.join(20)
    assert results["one"] == results["two"]
    assert second.events == [], "người thứ hai trúng bộ đệm: không có luồng"
    assert sum(server.turns.values()) == len(edge.speech_pieces(SENTENCES, 0)), "đọc đúng một lần"


@pytest.mark.parametrize("options", [{"rank": 1}, {"rank": edge.RANK_BACKGROUND}, {"rank": 0, "background": True}], ids=["rank 1", "rank nền", "việc nền"])
def test_only_the_paragraph_being_waited_for_streams(streaming, tmp_path, options) -> None:
    _, client = streaming()
    service = make_service(tmp_path, client)
    listener = Listener()
    clip = service.clip(VOICE, SENTENCES, stream=listener, **options)
    assert listener.events == [] and clip["words"]


def test_a_cache_hit_and_a_cached_only_lookup_never_stream(streaming, tmp_path) -> None:
    _, client = streaming()
    service = make_service(tmp_path, client)
    service.clip(VOICE, SENTENCES, rank=0)
    listener = Listener()
    service.clip(VOICE, SENTENCES, rank=0, stream=listener)
    service.clip(VOICE, SENTENCES, rank=0, cached_only=True, stream=listener)
    assert listener.events == []


def test_other_voices_ignore_the_stream(tmp_path) -> None:
    from tests.test_readaloud import FakeProvider

    service = __import__("abook.readaloud.service", fromlist=["ReadAloud"]).ReadAloud(tmp_path, [FakeProvider()])
    listener = Listener()
    assert service.clip("fake:ngoc", "Xin chào các bạn.", rank=0, stream=listener)["words"]
    assert listener.events == []


def test_the_words_are_told_at_most_twice_a_second_and_once_more_whenever_a_piece_is_done() -> None:
    from abook.readaloud.service import _Live

    now = [100.0]
    listener = Listener()
    live = _Live(listener, "một hai ba bốn năm", None, None, clock=lambda: now[0])
    live.boundaries([Boundary("một", 0, 200)])
    assert listener.events == [], "chưa có byte tiếng nào: chưa gửi gì"
    live.audio(b"x" * 144)
    assert listener.events == ["started", "audio", "words"], "mốc đã về trước đó thì gửi ngay sau byte đầu"
    for step in range(1, 6):  # mốc dày cứ 0,15 giây
        now[0] += 0.15
        live.boundaries([Boundary("hai", step * 10, step * 10 + 5)])
    assert listener.events.count("words") == 2, "0,5 giây sau lần trước mới gửi lại"
    live.piece_done()
    assert listener.events.count("words") == 3 and listener.events[-1] == "words"
    live.piece_done()
    assert listener.events.count("words") == 3, "không có gì mới thì không gửi lại"


def test_a_cut_names_the_first_shown_word_without_sound_and_waits_for_the_first_byte() -> None:
    from abook.readaloud.service import _Live

    # Chữ hiện "1900" đọc thành bốn chữ: "Năm" "1900" "anh" "đi." <- "năm một nghìn chín trăm anh đi."
    said = "năm một nghìn chín trăm anh đi."
    spans = [(0, 0), (1, 4), (5, 5), (6, 6)]
    listener = Listener()
    live = _Live(listener, said, spans, None)
    live.cut(5)
    assert listener.events == [], "chưa có byte tiếng nào: chưa mở lời đáp"
    live.audio(b"x" * 144)
    assert listener.events[:3] == ["started", "audio", "cut 2"], "chữ hiện đầu tiên không có tiếng: 'anh'"
    for words, shown in ((3, 1), (1, 1), (0, 0), (7, 4)):  # cắt giữa chữ hiện thành nhiều chữ đọc: đọc lại cả chữ ấy
        other = Listener()
        cut = _Live(other, said, spans, None)
        cut.audio(b"x" * 144)
        cut.cut(words)
        assert other.events[-1] == f"cut {shown}"
    plain = Listener()
    cut = _Live(plain, "một hai ba bốn", None, None)
    cut.audio(b"x" * 144)
    cut.cut(2)
    assert plain.events[-1] == "cut 2"


# ---- POST /api/readaloud/clip với stream: true ---------------------------------------------------------------------------------------

HEADERS = {"X-Ebook-Token": "t"}


def clip_server(tmp_path, client: edge.EdgeClient):
    from abook.readaloud.service import EdgeProvider
    from tests.test_readaloud import _server

    server = _server(tmp_path, EdgeProvider(client))  # type: ignore[arg-type] - chỉ cần `id` / `voices` / `synthesize`
    return server, server.app.readaloud


def post_clip(port: int, body: dict, *, read: bool = True):
    import http.client
    import json as json_module

    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=20)
    connection.request("POST", "/api/readaloud/clip", body=json_module.dumps(body).encode(), headers={**HEADERS, "Content-Type": "application/json"})
    response = connection.getresponse()
    return connection, response, (response.read() if read else b"")


def records(data: bytes) -> list[tuple[str, bytes]]:
    out, at = [], 0
    while at < len(data):
        size = int.from_bytes(data[at + 1:at + 5], "big")
        out.append((chr(data[at]), data[at + 5:at + 5 + size]))
        at += 5 + size
    assert at == len(data), "bản ghi cuối không đứt dở"
    return out


def test_a_streamed_clip_comes_back_as_records_ending_with_the_normal_json(streaming, tmp_path) -> None:
    import json as json_module

    _, client = streaming(pace=lambda _: 0.002)
    server, _ = clip_server(tmp_path, client)
    try:
        connection, response, data = post_clip(server.port, {"voice": VOICE, "text": SENTENCES, "rank": 0, "stream": True})
        assert response.status == 200 and response.getheader("Content-Type") == "application/vnd.abook.clipstream"
        assert response.getheader("Transfer-Encoding") == "chunked" and response.getheader("Cache-Control") == "no-store"
        found = records(data)
        kinds = [kind for kind, _ in found]
        assert kinds[0] == "A" and kinds[-1] == "E" and kinds.count("E") == 1 and set(kinds) <= {"A", "W", "E"} and "W" in kinds
        final = json_module.loads(found[-1][1])
        assert final["url"].startswith("/media/readaloud/") and final["url"].endswith(".mp3") and len(final["words"]) == len(SENTENCES.split())
        audio = b"".join(body for kind, body in found if kind == "A")
        assert audio == (tmp_path / "prefs" / "readaloud-cache" / final["url"].rsplit("/", 1)[1]).read_bytes(), "luồng == file trong bộ đệm"
        for kind, body in found:
            if kind == "W":
                tentative = json_module.loads(body)
                assert len(tentative["words"]) == len(SENTENCES.split()) and tentative["duration_ms"] <= final["duration_ms"]
                assert 0 < tentative["heard_ms"] <= tentative["duration_ms"]
        # Cùng đoạn hỏi lại: trúng bộ đệm -> JSON y hệt hôm nay (kể cả có `stream`), cùng kết nối giữ sống.
        connection.request("POST", "/api/readaloud/clip", body=json_module.dumps({"voice": VOICE, "text": SENTENCES, "rank": 0, "stream": True}).encode(),
                           headers={**HEADERS, "Content-Type": "application/json"})
        again = connection.getresponse()
        cached = json_module.loads(again.read())
        assert again.status == 200 and again.getheader("Content-Type").startswith("application/json") and cached == final
        connection.close()
    finally:
        server.stop()


@pytest.mark.parametrize("extra", [{}, {"stream": False}, {"stream": True, "rank": 1}, {"stream": True}, {"stream": "true", "rank": 0}], ids=["không", "false", "rank 1", "không rank", "không phải true"])
def test_without_stream_true_and_rank_zero_the_answer_is_the_old_json(streaming, tmp_path, extra) -> None:
    import json as json_module

    _, client = streaming()
    server, _ = clip_server(tmp_path, client)
    try:
        _, response, data = post_clip(server.port, {"voice": VOICE, "text": "Xin chào các bạn.", **extra})
        assert response.status == 200 and response.getheader("Content-Type").startswith("application/json")
        assert set(json_module.loads(data)) == {"url", "duration_ms", "words"}
    finally:
        server.stop()


def test_cached_only_with_stream_stays_json(streaming, tmp_path) -> None:
    import json as json_module

    _, client = streaming()
    server, _ = clip_server(tmp_path, client)
    try:
        _, response, data = post_clip(server.port, {"voice": VOICE, "text": "Xin chào các bạn.", "rank": 0, "stream": True, "cachedOnly": True})
        assert response.status == 200 and json_module.loads(data) == {"cached": False, "reason": "uncached"}
    finally:
        server.stop()


def test_an_error_before_the_first_byte_is_still_a_json_error(streaming, tmp_path) -> None:
    import json as json_module

    _, client = streaming(dead=lambda spoken: True)
    server, _ = clip_server(tmp_path, client)
    try:
        _, response, data = post_clip(server.port, {"voice": VOICE, "text": "Xin chào các bạn.", "rank": 0, "stream": True})
        assert response.status == 502 and response.getheader("Content-Type").startswith("application/json")
        assert json_module.loads(data)["reason"] == "service" and json_module.loads(data)["error"]
    finally:
        server.stop()


def test_an_error_after_the_first_byte_comes_as_an_x_record(streaming, tmp_path) -> None:
    import json as json_module

    pieces = edge.speech_pieces(UNIQUE, 0)
    dead = " ".join(pieces[2].split())
    _, client = streaming(dead=lambda spoken: spoken == dead, pace=lambda _: 0.002)
    server, _ = clip_server(tmp_path, client)
    try:
        _, response, data = post_clip(server.port, {"voice": VOICE, "text": UNIQUE, "rank": 0, "stream": True})
        assert response.status == 200
        found = records(data)
        assert found[0][0] == "A" and found[-1][0] == "X" and [kind for kind, _ in found].count("X") == 1 and "E" not in [kind for kind, _ in found]
        failure = json_module.loads(found[-1][1])
        assert failure["reason"] == "service" and failure["message"]
        # uxfix63: mảnh 3 hỏng -> một bản ghi C (chữ hiện đầu tiên của mảnh hỏng), rồi X.
        kinds = [kind for kind, _ in found]
        assert kinds.count("C") == 1 and kinds.index("C") < kinds.index("X")
        assert json_module.loads(found[kinds.index("C")][1]) == {"word": len(pieces[0].split()) + len(pieces[1].split())}
    finally:
        server.stop()


def test_a_listener_who_hangs_up_does_not_spoil_the_clip(streaming, tmp_path) -> None:
    import json as json_module

    _, client = streaming(pace=lambda _: 0.01)
    server, service = clip_server(tmp_path, client)
    try:
        payload = json_module.dumps({"voice": VOICE, "text": SENTENCES, "rank": 0, "stream": True}).encode()
        sock = socket.create_connection(("127.0.0.1", server.port), timeout=10)
        sock.sendall(b"POST /api/readaloud/clip HTTP/1.1\r\nHost: 127.0.0.1:%d\r\nX-Ebook-Token: t\r\nContent-Type: application/json\r\nContent-Length: %d\r\n\r\n" % (server.port, len(payload)) + payload)
        got = b""
        while b"\r\n\r\n" not in got:
            got += sock.recv(4096)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))  # đóng bằng RST giữa lúc đang phát
        sock.close()
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            try:
                clip = service.clip(VOICE, SENTENCES, cached_only=True)
                break
            except VoiceError:  # chưa đọc xong
                time.sleep(0.05)
        else:
            pytest.fail("clip không vào bộ đệm sau khi người nghe ngắt")
        assert len(clip["words"]) == len(SENTENCES.split())
        assert (tmp_path / "prefs" / "readaloud-cache" / clip["file"]).is_file()
    finally:
        server.stop()
