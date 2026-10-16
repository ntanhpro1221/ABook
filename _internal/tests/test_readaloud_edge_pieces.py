"""Giọng Edge đọc SONG SONG các câu của một đoạn (uxfix47): luật cắt mảnh (cùng bộ ví dụ với điện thoại), mốc chữ sau khi nối, trần kết nối, lỗi một mảnh."""
from __future__ import annotations

import json
import socket
import threading
import time
from pathlib import Path

import pytest

from abook.readaloud import edge
from abook.readaloud.mapping import Boundary
from tests.test_readaloud import FakeEdge, fake_edge  # noqa: F401 - fixture dùng chung

CASES = json.loads((Path(__file__).parent / "fixtures" / "readaloud" / "edge" / "pieces.json").read_text(encoding="utf-8"))["cases"]
SENTENCES = ("Trời đã sẩm tối khi đoàn người tới được cổng làng. Người gác cổng đứng chờ sẵn, tay cầm chiếc đèn dầu cũ. "
             "Họ im lặng bước vào sân, nơi mấy con chó nằm ngủ dưới hiên. Mưa bắt đầu rơi lúc nào không ai hay.")


@pytest.mark.parametrize("case", CASES, ids=[case["note"][:40] for case in CASES])
def test_the_shared_cases_cut_the_same_way_on_both_platforms(case) -> None:
    assert edge.speech_pieces(case["text"]) == case["pieces"]


def test_a_short_paragraph_stays_one_request() -> None:
    assert edge.speech_pieces("Một. Hai. Ba.") == ["Một. Hai. Ba."]
    assert edge.speech_pieces("   ") == []
    just_under = ("Câu thứ nhất khá ngắn. " + "Câu thứ hai cũng thế.")[: edge.WHOLE_CHARS - 1]
    assert edge.speech_pieces(just_under) == [just_under.strip()]


def test_pieces_are_few_balanced_and_never_tiny() -> None:
    text = " ".join(f"Câu số {index} nói về chuyện nhỏ." for index in range(1, 25))
    pieces = edge.speech_pieces(text)
    assert 2 <= len(pieces) <= edge.PIECE_PARALLEL
    assert " ".join(pieces).split() == text.split()
    assert all(len(piece) >= edge.MIN_PIECE_CHARS for piece in pieces)
    assert max(map(len, pieces)) < 1.5 * min(map(len, pieces))
    assert all(piece.rstrip()[-1] in ".!?" for piece in pieces)  # mảnh nào cũng kết thúc ở hết câu


def test_the_split_never_lands_inside_a_word_a_number_or_an_initial() -> None:
    text = ("Ông A. Trần ghé qua lúc 3,5 giờ chiều để hỏi giá cái bàn gỗ mít mà nhà tôi định bán, nhưng chúng tôi chưa chốt gì cả, vì còn chờ người anh về quê xem lại một lần nữa. "
            "Giá bao nhiêu thì tuỳ ông ấy trả, miễn là đừng quá thấp so với giá chợ hôm nay.")
    pieces = edge.speech_pieces(text)
    assert len(pieces) >= 2
    assert " ".join(pieces).split() == text.split()
    assert not any(piece.endswith("A.") or piece.endswith("3,") for piece in pieces)
    assert any("3,5" in piece for piece in pieces)


def test_a_long_sentence_without_marks_is_not_cut_below_the_service_limit() -> None:
    sentence = " ".join(["từ"] * 120) + "."
    assert edge.speech_pieces(sentence) == [sentence]


def test_pieces_respect_the_service_byte_limit() -> None:
    text = " ".join(["Câu số một hai ba."] * 600)
    pieces = edge.speech_pieces(text)
    assert len(pieces) > edge.PIECE_PARALLEL  # mỗi mảnh vẫn quá 4000 byte nên cắt tiếp
    assert all(edge.escaped_bytes(piece) <= edge.MAX_CHUNK_BYTES for piece in pieces)
    assert " ".join(pieces).split() == text.split()


# ---- đọc song song -------------------------------------------------------------------------------------------------------------


def test_boundaries_after_joining_follow_the_audio_of_the_earlier_pieces(fake_edge) -> None:
    server, client = fake_edge()
    result = client.synthesize(SENTENCES, edge.DEFAULT_VOICE)
    pieces = edge.speech_pieces(SENTENCES)
    assert len(pieces) >= 2 and len(server.requests) == len(pieces)
    assert len(result.audio) == 12000 * len(pieces)  # mỗi lượt của máy chủ giả là 2 giây
    starts = [b.start_ms for b in result.boundaries]
    assert starts == sorted(starts)
    assert all(b.end_ms <= result.duration_ms for b in result.boundaries)
    first = 0
    for index, piece in enumerate(pieces):  # chữ đầu của mảnh thứ n bắt đầu sau toàn bộ audio các mảnh trước (2 giây mỗi mảnh)
        assert result.boundaries[first].start_ms == 2000 * index
        first += len(piece.split())
    assert [b.text for b in result.boundaries] == SENTENCES.split()


class _SlowFake(edge.EdgeClient):
    """Mỗi mảnh xong sau một độ trễ riêng (mảnh đầu chậm nhất) để thử thứ tự ghép; ghi lại số kết nối cùng lúc."""

    def __init__(self, delays: dict[int, float] | None = None, fail: dict[int, Exception] | None = None) -> None:
        super().__init__()
        self.delays = delays or {}
        self.fail = fail or {}
        self.live = 0
        self.peak = 0
        self.lock = threading.Lock()

    def _connect(self):  # noqa: ANN202
        raise AssertionError("không nối mạng thật")

    def _speak_one(self, voice, text, compensation_ticks, deadline, *, clip=None):  # noqa: ANN001, ANN202
        order = edge.speech_pieces(SENTENCES).index(text)
        with self.lock:
            self.live += 1
            self.peak = max(self.peak, self.live)
        try:
            time.sleep(self.delays.get(order, 0.0))
            if order in self.fail:
                raise self.fail[order]
            words = text.split()
            return bytes([order + 1]) * 6000, [Boundary(word, 100 * i, 100 * i + 50) for i, word in enumerate(words)]
        finally:
            with self.lock:
                self.live -= 1


def test_pieces_finishing_out_of_order_are_joined_in_reading_order() -> None:
    pieces = edge.speech_pieces(SENTENCES)
    client = _SlowFake(delays={0: 0.3, 1: 0.1, 2: 0.0})
    result = client.synthesize(SENTENCES, edge.DEFAULT_VOICE)
    assert client.peak == min(len(pieces), edge.PIECE_PARALLEL)  # đúng là chạy cùng lúc
    expected = b"".join(bytes([n + 1]) * 6000 for n in range(len(pieces)))
    assert result.audio == expected
    assert [b.text for b in result.boundaries] == SENTENCES.split()
    first = 0
    for n, piece in enumerate(pieces):
        assert result.boundaries[first].start_ms == 1000 * n  # 6000 byte = 1 giây
        first += len(piece.split())
    assert result.duration_ms >= result.boundaries[-1].end_ms


def test_a_failing_piece_fails_the_clip_with_the_same_exception() -> None:
    client = _SlowFake(delays={0: 0.1}, fail={1: edge.EdgeRejected("từ chối")})
    with pytest.raises(edge.EdgeRejected):
        client.synthesize(SENTENCES, edge.DEFAULT_VOICE)
    # Mảnh hỏng TRƯỚC theo thời gian quyết, không đợi mảnh đứng trước nó trong câu chữ đọc xong.
    client = _SlowFake(delays={0: 1.0}, fail={0: edge.EdgeOffline("mất mạng"), 1: edge.EdgeRejected("từ chối")})
    started = time.monotonic()
    with pytest.raises(edge.EdgeRejected):
        client.synthesize(SENTENCES, edge.DEFAULT_VOICE)
    assert time.monotonic() - started < 0.8


def test_a_failing_piece_cuts_the_sockets_of_the_pieces_still_reading(monkeypatch) -> None:
    """Mảnh 2 bị từ chối ngay: clip hỏng liền, ổ cắm của mảnh 1 / 3 (đang chờ Edge) bị cắt, chỗ kết nối trả ngay, không mảnh nào thử lại."""
    monkeypatch.setattr(edge, "_connections", threading.BoundedSemaphore(edge.EDGE_CONNECTIONS))
    pieces = edge.speech_pieces(SENTENCES)
    connects: list[str] = []
    aborted: list[str] = []
    lock = threading.Lock()

    class _Connection:
        def __init__(self) -> None:
            self.text = ""
            self.cut = threading.Event()

        def send_text(self, text: str) -> None:
            if "<speak" in text:
                self.text = next(piece for piece in pieces if edge.escape(piece) in text)

        def abort(self) -> None:
            with lock:
                aborted.append(self.text)
            self.cut.set()

        def close(self) -> None:
            pass

    class _Client(edge.EdgeClient):
        def _connect(self):  # noqa: ANN202
            connection = _Connection()
            with lock:
                connects.append("x")
            return connection

    def fake_turn(connection, _compensation, deadline, **_options):  # noqa: ANN001, ANN202
        if connection.text == pieces[1]:
            time.sleep(0.2)  # để mọi mảnh kịp mở kết nối
            raise edge.EdgeRejected("từ chối")
        if not connection.cut.wait(max(0.0, deadline - time.monotonic())):
            return b"x" * 6000, []
        raise edge.EdgeDropped("bị cắt")  # như recv khi ổ cắm bị shutdown

    monkeypatch.setattr(edge, "read_turn", fake_turn)
    started = time.monotonic()
    with pytest.raises(edge.EdgeRejected):
        _Client().synthesize(SENTENCES, edge.DEFAULT_VOICE)
    assert time.monotonic() - started < 2.0
    for _ in range(40):  # luồng mảnh thoát sau khi bị cắt
        if edge._connections._value == edge.EDGE_CONNECTIONS:  # noqa: SLF001
            break
        time.sleep(0.05)
    assert edge._connections._value == edge.EDGE_CONNECTIONS  # noqa: SLF001 - mọi chỗ đã trả
    assert sorted(aborted) == sorted(piece for n, piece in enumerate(pieces) if n != 1)
    assert len(connects) == len(pieces)  # mảnh bị cắt không thử lại


def test_websocket_abort_wakes_a_reader_blocked_in_another_thread() -> None:
    from abook.readaloud import websocket
    left, right = socket.socketpair()
    left.settimeout(5.0)  # như kết nối thật (read_timeout): recv đi qua select
    try:
        connection = websocket.Connection(websocket._Buffered(left, b""))  # noqa: SLF001
        errors: list[BaseException] = []

        def reader() -> None:
            try:
                connection.recv()
            except BaseException as error:  # noqa: BLE001
                errors.append(error)

        thread = threading.Thread(target=reader)
        thread.start()
        time.sleep(0.1)
        connection.abort()
        thread.join(2)
        assert not thread.is_alive() and errors and isinstance(errors[0], websocket.WebSocketError)
        connection.close()
    finally:
        right.close()


def test_a_dropped_piece_is_retried_alone_and_ends_as_dropped_when_it_keeps_failing(fake_edge, monkeypatch) -> None:
    monkeypatch.setattr(edge.time, "sleep", lambda _seconds: None)
    server, client = fake_edge(drop=2)
    result = client.synthesize(SENTENCES, edge.DEFAULT_VOICE)
    pieces = edge.speech_pieces(SENTENCES)
    assert len(result.audio) == 12000 * len(pieces) and len(server.requests) == len(pieces) + 2
    server, client = fake_edge(drop=100)
    with pytest.raises(edge.EdgeDropped):
        client.synthesize(SENTENCES, edge.DEFAULT_VOICE)


def test_the_process_wide_cap_limits_open_connections(monkeypatch) -> None:
    """Hai clip cùng đọc (6 mảnh) mà trần là 2 kết nối: không bao giờ quá 2 kết nối đang mở."""
    monkeypatch.setattr(edge, "_connections", threading.BoundedSemaphore(2))
    live = [0]
    peak = [0]
    lock = threading.Lock()

    class _Connection:
        def send_text(self, _text: str) -> None:
            pass

        def close(self) -> None:
            with lock:
                live[0] -= 1

    class _Client(edge.EdgeClient):
        def _connect(self):  # noqa: ANN202
            with lock:
                live[0] += 1
                peak[0] = max(peak[0], live[0])
            return _Connection()

    def fake_turn(_connection, _compensation, _deadline, **_options):  # noqa: ANN001, ANN202
        time.sleep(0.05)
        return b"x" * 6000, []

    monkeypatch.setattr(edge, "read_turn", fake_turn)
    clients = [_Client(), _Client()]
    threads = [threading.Thread(target=client.synthesize, args=(SENTENCES, edge.DEFAULT_VOICE)) for client in clients]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(10)
    assert live[0] == 0 and 1 <= peak[0] <= 2
    assert peak[0] == 2  # và đúng là có song song, không phải nối tiếp


def test_waiting_for_a_connection_slot_past_the_deadline_is_a_timeout(monkeypatch) -> None:
    taken = threading.BoundedSemaphore(1)
    taken.acquire()
    monkeypatch.setattr(edge, "_connections", taken)
    with pytest.raises(edge.EdgeTimeout):
        edge.EdgeClient()._speak_one(edge.DEFAULT_VOICE, "Xin chào", 0, time.monotonic() + 0.05)
