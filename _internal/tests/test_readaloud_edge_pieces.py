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
    assert edge.speech_pieces(case["text"], case.get("rank", edge.RANK_BACKGROUND)) == case["pieces"]


def test_only_the_paragraph_being_waited_for_is_cut_into_up_to_six_pieces() -> None:
    assert (edge.PIECE_PARALLEL, edge.TARGET_PIECES) == (3, 6)
    assert [edge.piece_limit(rank) for rank in (0, 1, 2, 98, edge.RANK_BACKGROUND)] == [6, 3, 3, 3, 3]
    text = next(case["text"] for case in CASES if case.get("rank") == 0 and len(case["pieces"]) == 6)
    assert len(edge.speech_pieces(text, 0)) == 6
    for rank in (1, 5, 98, edge.RANK_BACKGROUND):
        assert len(edge.speech_pieces(text, rank)) == 3
    assert edge.speech_pieces(text) == edge.speech_pieces(text, edge.RANK_BACKGROUND)
    # Mảnh nào cũng giữ đủ dài và ghép lại đúng chữ gốc ở cả hai cách cắt.
    for rank in (0, 1):
        pieces = edge.speech_pieces(text, rank)
        assert " ".join(pieces).split() == text.split()
        assert all(len(piece) >= edge.MIN_PIECE_CHARS for piece in pieces)


class _PeakFake(edge.EdgeClient):
    """Ghi lại số mảnh chạy cùng lúc (mỗi mảnh giữ chỗ 0,2 giây) và số mảnh đã gửi."""

    def __init__(self) -> None:
        super().__init__()
        self.live = 0
        self.peak = 0
        self.sent = 0
        self.lock = threading.Lock()

    def _speak_one(self, voice, text, compensation_ticks, deadline, *, clip=None, rank=edge.RANK_BACKGROUND):  # noqa: ANN001, ANN202
        with self.lock:
            self.live += 1
            self.sent += 1
            self.peak = max(self.peak, self.live)
        try:
            time.sleep(0.2)
            return b"x" * 6000, [Boundary(word, 100 * i, 100 * i + 50) for i, word in enumerate(text.split())]
        finally:
            with self.lock:
                self.live -= 1


def test_a_rank_zero_clip_runs_six_pieces_at_once_and_other_ranks_three() -> None:
    text = next(case["text"] for case in CASES if case.get("rank") == 0 and len(case["pieces"]) == 6)
    for rank, expected in ((0, 6), (1, 3), (edge.RANK_BACKGROUND, 3)):
        client = _PeakFake()
        client.synthesize(text, edge.DEFAULT_VOICE, rank=rank)
        assert (client.sent, client.peak) == (expected, expected), rank


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

    def _speak_one(self, voice, text, compensation_ticks, deadline, *, clip=None, rank=edge.RANK_BACKGROUND):  # noqa: ANN001, ANN202
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
    monkeypatch.setattr(edge, "_connections", edge.ConnectionSlots(edge.EDGE_CONNECTIONS))
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
        if edge._connections.free == edge.EDGE_CONNECTIONS:  # noqa: SLF001
            break
        time.sleep(0.05)
    assert edge._connections.free == edge.EDGE_CONNECTIONS  # noqa: SLF001 - mọi chỗ đã trả
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
    monkeypatch.setattr(edge, "_connections", edge.ConnectionSlots(2))
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
    taken = edge.ConnectionSlots(1)
    taken.acquire()
    monkeypatch.setattr(edge, "_connections", taken)
    with pytest.raises(edge.EdgeTimeout):
        edge.EdgeClient()._speak_one(edge.DEFAULT_VOICE, "Xin chào", 0, time.monotonic() + 0.05)


# ---- chỗ kết nối: clip người nghe đang chờ đi trước clip đọc trước (uxfix51) ---------------------------------------------------------


def _wait_for(condition, seconds: float = 2.0) -> bool:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if condition():
            return True
        time.sleep(0.005)
    return condition()


def _queue_waiters(slots: edge.ConnectionSlots, specs: list[tuple[str, int]]) -> list[str]:
    """Hết chỗ; mỗi (tên, rank) xin một chỗ theo thứ tự đã cho; trả thứ tự được trao chỗ khi nhả lần lượt từng chỗ."""
    for _ in range(slots.size):
        assert slots.acquire(0.1)
    granted: list[str] = []
    lock = threading.Lock()

    def wait(name: str, rank: int) -> None:
        if slots.acquire(5.0, rank):
            with lock:
                granted.append(name)

    threads = []
    for index, (name, rank) in enumerate(specs):
        thread = threading.Thread(target=wait, args=(name, rank))
        thread.start()
        threads.append(thread)
        assert _wait_for(lambda: len(slots._queue) == index + 1)  # noqa: SLF001 - đúng thứ tự đến
    for expected in range(len(specs)):
        slots.release()
        assert _wait_for(lambda: len(granted) == expected + 1)
        time.sleep(0.02)
    for thread in threads:
        thread.join(2)
    return granted


def test_connection_slots_grant_the_nearest_to_the_listener_first() -> None:
    granted = _queue_waiters(edge.ConnectionSlots(2), [("bg", edge.RANK_BACKGROUND), ("ahead3", 3), ("ahead1", 1), ("target", 0), ("ahead2", 2), ("ahead1b", 1)])
    assert granted == ["target", "ahead1", "ahead1b", "ahead2", "ahead3", "bg"]  # gần người nghe trước; cùng rank thì ai đến trước được trước


def test_connection_slots_keep_arrival_order_among_equals() -> None:
    assert _queue_waiters(edge.ConnectionSlots(1), [("a", 1), ("b", 1), ("c", 1)]) == ["a", "b", "c"]


def test_connection_slots_timeout_and_abandon_leave_the_queue_and_free_the_way() -> None:
    slots = edge.ConnectionSlots(1)
    assert slots.acquire(0.1)
    assert not slots.acquire(0.05)  # quá hạn: False, không để lại vé trong hàng
    gone = threading.Event()
    result: list[bool] = []
    first = threading.Thread(target=lambda: result.append(slots.acquire(5.0, False, gone.is_set)))
    first.start()
    assert _wait_for(lambda: len(slots._queue) == 1)  # noqa: SLF001
    second_got = threading.Event()
    second = threading.Thread(target=lambda: (slots.acquire(5.0) and second_got.set()))
    second.start()
    assert _wait_for(lambda: len(slots._queue) == 2)  # noqa: SLF001
    gone.set()  # clip của người đứng đầu hàng đã bỏ: người sau không bị chặn lại bởi vé của nó
    first.join(2)
    assert result == [False] and slots._queue and len(slots._queue) == 1  # noqa: SLF001
    slots.release()
    assert second_got.wait(2)
    second.join(2)
    assert slots.free == 0
    slots.release()
    with pytest.raises(ValueError):
        slots.release()


def test_the_production_slots_let_only_rank_zero_past_the_eight_connection_cap() -> None:
    assert edge._connections.size == edge.EDGE_CONNECTIONS and edge._connections.extra == edge.TARGET_PIECES  # noqa: SLF001


def test_rank_zero_takes_a_slot_at_once_when_eight_are_held_by_rank_three_and_the_ceiling_holds() -> None:
    """a55: 8 chỗ đều do clip rank 3 giữ, đoạn người nghe chờ (rank 0) đến sau vài ms - không đợi; tới size + extra thì cũng chờ; rank >= 1 vẫn dừng ở size."""
    slots = edge.ConnectionSlots(edge.EDGE_CONNECTIONS, edge.TARGET_PIECES)
    for _ in range(edge.EDGE_CONNECTIONS):
        assert slots.acquire(0.1, 3)
    assert not slots.acquire(0.05, 1)  # rank >= 1 không được vượt trần
    assert not slots.acquire(0.05)  # nền cũng không
    for _ in range(edge.TARGET_PIECES):
        began = time.monotonic()
        assert slots.acquire(5.0, 0)
        assert time.monotonic() - began < 0.2
    assert slots.free == -edge.TARGET_PIECES
    began = time.monotonic()
    assert not slots.acquire(0.1, 0)  # trần cứng size + TARGET_PIECES: rank 0 cũng phải chờ
    assert time.monotonic() - began >= 0.09
    assert not slots._queue  # noqa: SLF001


def test_over_cap_releases_never_let_free_exceed_size_and_the_waiters_keep_their_order() -> None:
    slots = edge.ConnectionSlots(2, 2)
    assert slots.acquire(0.1, 3) and slots.acquire(0.1, 3)
    assert slots.acquire(0.1, 0) and slots.acquire(0.1, 0)  # hai chỗ vượt trần
    granted: list[str] = []
    lock = threading.Lock()

    def wait(name: str, rank: int) -> None:
        if slots.acquire(5.0, rank):
            with lock:
                granted.append(name)

    threads = []
    for index, (name, rank) in enumerate([("bg", edge.RANK_BACKGROUND), ("ahead2", 2), ("ahead1", 1)]):
        thread = threading.Thread(target=wait, args=(name, rank))
        thread.start()
        threads.append(thread)
        assert _wait_for(lambda: len(slots._queue) == index + 1)  # noqa: SLF001
    slots.release()  # đang giữ 3 / size 2: chưa dưới trần -> chưa ai trong hàng được chỗ
    slots.release()  # đang giữ 2 -> vẫn chưa (free == 0)
    time.sleep(0.1)
    assert granted == [] and slots.free == 0
    for expected in range(3):
        slots.release()  # xuống dưới trần -> chỗ trao cho người đứng đầu hàng (ahead1, ahead2, bg)
        assert _wait_for(lambda: len(granted) == expected + 1)
        assert slots.free <= slots.size
    for thread in threads:
        thread.join(2)
    assert granted == ["ahead1", "ahead2", "bg"]
    # còn 2 chỗ đang giữ -> nhả hết, free về đúng size
    while slots.free < slots.size:
        slots.release()
    assert slots.free == slots.size
    with pytest.raises(ValueError):
        slots.release()


def test_the_clip_the_listener_waits_for_asked_after_eight_read_ahead_pieces_wait_gets_the_next_free_slot(monkeypatch) -> None:
    """8 chỗ đều bận, 8 mảnh đọc trước đang chờ; clip người nghe chờ (rank 0) xin SAU cùng - chỗ nhả ra đầu tiên là của nó, các mảnh đọc trước theo sau."""
    monkeypatch.setattr(edge, "_connections", edge.ConnectionSlots(edge.EDGE_CONNECTIONS))
    opened: list[str] = []
    lock = threading.Lock()
    gate = threading.Event()

    class _Connection:
        def __init__(self) -> None:
            self.text = ""

        def send_text(self, text: str) -> None:
            if "<speak" in text:
                self.text = text

        def close(self) -> None:
            pass

    class _Client(edge.EdgeClient):
        def _connect(self):  # noqa: ANN202
            return _Connection()

    def fake_turn(connection, _compensation, _deadline, **_options):  # noqa: ANN001, ANN202
        with lock:
            opened.append("target" if "TARGET" in connection.text else "ahead" if "AHEAD" in connection.text else "holder")
        gate.wait(5)
        return b"x" * 6000, []

    monkeypatch.setattr(edge, "read_turn", fake_turn)
    client = _Client()
    holders = [threading.Thread(target=client.synthesize, args=("HOLDER %d." % n, edge.DEFAULT_VOICE)) for n in range(edge.EDGE_CONNECTIONS)]
    for thread in holders:
        thread.start()
    assert _wait_for(lambda: len(opened) == edge.EDGE_CONNECTIONS)  # mọi chỗ đã có người giữ
    ahead = [threading.Thread(target=client.synthesize, args=("AHEAD %d." % n, edge.DEFAULT_VOICE), kwargs={"rank": 1 + n % 3}) for n in range(edge.EDGE_CONNECTIONS)]
    for thread in ahead:
        thread.start()
    assert _wait_for(lambda: len(edge._connections._queue) == edge.EDGE_CONNECTIONS)  # noqa: SLF001 - 8 mảnh đọc trước đã chờ
    target = threading.Thread(target=client.synthesize, args=("TARGET.", edge.DEFAULT_VOICE), kwargs={"rank": 0})
    target.start()
    assert _wait_for(lambda: len(edge._connections._queue) == edge.EDGE_CONNECTIONS + 1)  # noqa: SLF001
    gate.set()
    for thread in [*holders, *ahead, target]:
        thread.join(10)
    assert opened[edge.EDGE_CONNECTIONS] == "target"  # chỗ trống đầu tiên sau 8 chỗ giữ
    assert sorted(opened[edge.EDGE_CONNECTIONS + 1:]) == ["ahead"] * edge.EDGE_CONNECTIONS


def test_the_rank_reaches_every_piece_of_a_long_clip() -> None:
    seen: list[int] = []

    class _Client(edge.EdgeClient):
        def _speak_one(self, voice, text, compensation_ticks, deadline, *, clip=None, rank=edge.RANK_BACKGROUND):  # noqa: ANN001, ANN202
            seen.append(rank)
            return b"x" * 6000, []

    _Client().synthesize(SENTENCES, edge.DEFAULT_VOICE, rank=2)
    _Client().synthesize(SENTENCES, edge.DEFAULT_VOICE)
    half = len(seen) // 2
    assert half >= 2 and set(seen[:half]) == {2} and set(seen[half:]) == {edge.RANK_BACKGROUND}


# ---- chỗ nối giữa các mảnh (uxfix50) ---------------------------------------------------------------------------------------------

JOIN_CASES = json.loads((Path(__file__).parent / "fixtures" / "readaloud" / "edge" / "join_tail.json").read_text(encoding="utf-8"))["cases"]
_HEADER = bytes([0xFF, 0xF3, 0x64, 0xC0])  # MPEG-2 lớp III, 48 kbps, 24 kHz, đơn kênh, không đệm: khung 144 byte


def _mp3_frames(count: int) -> bytes:
    """`count` khung hợp lệ, mỗi khung ghi số thứ tự của nó vào byte 4 và 5 để biết khung nào còn lại."""
    return b"".join(_HEADER + (index >> 8).to_bytes(1, "big") + (index & 0xFF).to_bytes(1, "big") + b"\0" * (edge.MP3_FRAME_BYTES - 6) for index in range(count))


@pytest.mark.parametrize("case", JOIN_CASES, ids=[case["note"][:40] for case in JOIN_CASES])
def test_the_join_tail_cut_follows_the_shared_cases(case) -> None:
    audio = _mp3_frames(case["frames"])
    trimmed = edge.trim_join_tail(audio, case["piece"], [Boundary("x", 0, case["last_end_ms"])])
    assert len(trimmed) == case["kept_frames"] * edge.MP3_FRAME_BYTES
    assert trimmed == audio[: len(trimmed)]  # chỉ cắt đuôi, giữ nguyên từng byte phía trước


def test_the_join_tail_is_left_alone_when_the_frames_are_not_what_edge_sends() -> None:
    audio = _mp3_frames(300)
    boundaries = [Boundary("x", 0, 2000)]
    assert len(edge.trim_join_tail(audio, "Xong rồi.", boundaries)) < len(audio)  # đối chứng: dữ liệu tốt thì cắt
    assert edge.trim_join_tail(audio, "Xong rồi.", []) == audio  # không có mốc
    assert edge.trim_join_tail(b"", "Xong rồi.", boundaries) == b""
    assert edge.trim_join_tail(audio + b"\0", "Xong rồi.", boundaries) == audio + b"\0"  # độ dài không chia hết cho khung
    padded = bytearray(audio)
    padded[144 * 200 + 2] |= 0x02  # một khung có bit đệm (145 byte): không còn là CBR 144 byte
    assert edge.trim_join_tail(bytes(padded), "Xong rồi.", boundaries) == bytes(padded)
    other_rate = bytearray(audio)
    other_rate[144 * 10 + 2] = 0x68  # 24 kHz -> 22,05 kHz ... một tần số khác
    assert edge.trim_join_tail(bytes(other_rate), "Xong rồi.", boundaries) == bytes(other_rate)
    noise = bytes(range(256)) * 36 + bytes(144 * 3)  # không phải MP3
    assert edge.trim_join_tail(noise, "Xong rồi.", boundaries) == noise


def test_a_sentence_end_keeps_the_pause_edge_makes_between_sentences_and_other_cuts_keep_less() -> None:
    assert edge.join_tail_ms("Hết câu.") == edge.JOIN_TAIL_SENTENCE_MS
    assert edge.join_tail_ms("Hết câu?”") == edge.JOIN_TAIL_SENTENCE_MS
    assert edge.join_tail_ms("Hết câu…") == edge.JOIN_TAIL_SENTENCE_MS
    assert edge.join_tail_ms("Còn tiếp,") == edge.JOIN_TAIL_OTHER_MS
    assert edge.join_tail_ms("“Còn tiếp,”") == edge.JOIN_TAIL_OTHER_MS
    assert edge.join_tail_ms("một hai ba") == edge.JOIN_TAIL_OTHER_MS
    assert edge.JOIN_TAIL_OTHER_MS < edge.JOIN_TAIL_SENTENCE_MS


class _FrameFake(edge.EdgeClient):
    """Mỗi mảnh trả `frames` khung hợp lệ (2,4 giây... 12 giây) với các chữ trải đều, hết chữ cuối ở `end_ms`."""

    def __init__(self, frames: list[int], ends: list[int]) -> None:
        super().__init__()
        self.frames = frames
        self.ends = ends

    def _connect(self):  # noqa: ANN202
        raise AssertionError("không nối mạng thật")

    def _speak_one(self, voice, text, compensation_ticks, deadline, *, clip=None, rank=edge.RANK_BACKGROUND):  # noqa: ANN001, ANN202
        order = edge.speech_pieces(SENTENCES).index(text)
        words = text.split()
        end = self.ends[order]
        step = (end - 125) // len(words)
        return _mp3_frames(self.frames[order]), [Boundary(word, 125 + i * step, 125 + (i + 1) * step if i < len(words) - 1 else end) for i, word in enumerate(words)]


def test_synthesize_trims_every_piece_but_the_last_and_shifts_the_later_boundaries_by_the_trimmed_length() -> None:
    pieces = edge.speech_pieces(SENTENCES)
    count = len(pieces)
    assert count >= 3
    frames = [300 + 7 * n for n in range(count)]
    ends = [int(f * 24 - 850) for f in frames]  # đuôi 850 ms như Edge thật
    result = _FrameFake(frames, ends).synthesize(SENTENCES, edge.DEFAULT_VOICE)
    kept = []
    for n in range(count - 1):
        tail = edge.join_tail_ms(pieces[n])
        kept.append(-(-(ends[n] + tail) // 24))
        assert kept[-1] < frames[n]  # có cắt
    kept.append(frames[-1])  # mảnh cuối giữ nguyên
    assert len(result.audio) == sum(kept) * 144
    assert result.duration_ms == sum(kept) * 24
    first = 0
    before = 0
    for n, piece in enumerate(pieces):  # chữ đầu của mảnh n bắt đầu sau toàn bộ audio ĐÃ CẮT của các mảnh trước
        assert result.boundaries[first].start_ms == 125 + before * 24
        before += kept[n]
        first += len(piece.split())
    # Chỗ nối (hết chữ cuối mảnh n -> chữ đầu mảnh n+1) đúng bằng phần giữ + lặng đầu mảnh sau, không còn ~0,85 giây đuôi.
    first = 0
    for n, piece in enumerate(pieces[:-1]):
        last = first + len(piece.split()) - 1
        gap = result.boundaries[last + 1].start_ms - result.boundaries[last].end_ms
        assert gap < edge.join_tail_ms(piece) + 24 + 125 + 1
        first = last + 1
    assert [b.text for b in result.boundaries] == SENTENCES.split()


def test_a_single_piece_clip_is_never_trimmed() -> None:
    audio = _mp3_frames(200)

    class _One(edge.EdgeClient):
        def _speak_one(self, voice, text, compensation_ticks, deadline, *, clip=None, rank=edge.RANK_BACKGROUND):  # noqa: ANN001, ANN202
            return audio, [Boundary("Xin", 125, 600), Boundary("chào.", 600, 1400)]

    result = _One().synthesize("Xin chào.", edge.DEFAULT_VOICE)
    assert result.audio == audio and result.duration_ms == 200 * 24


# ---- bắt tay treo (uxfix50) ------------------------------------------------------------------------------------------------------


def _client(server, connect_timeout: float = 0.3) -> edge.EdgeClient:
    return edge.EdgeClient(host="127.0.0.1", port=server.port, secure=False, connect_timeout=connect_timeout, read_timeout=2)


def test_a_handshake_that_hangs_once_is_retried_and_the_clip_succeeds(fake_edge, monkeypatch) -> None:
    """a51: 8 / 95 mảnh treo ~10 s lúc bắt tay, bị coi là "không có mạng" (EdgeOffline, không thử lại) - cả chương dừng. Giờ: hết giờ rồi thử lại."""
    monkeypatch.setattr(edge.time, "sleep", lambda _seconds: None)  # nghỉ chờ giữa các lần thử không cần thật
    server, _ = fake_edge(hang=1)
    started = time.monotonic()
    result = _client(server).synthesize("Xin chào", edge.DEFAULT_VOICE)
    assert result.audio == b"A" * 12000
    assert len(server.requests) == 1  # kết nối treo không bao giờ gửi yêu cầu tới máy chủ giả
    assert time.monotonic() - started < 3.0  # hết giờ ở 0,3 s, không phải 10 s


def test_a_hanging_handshake_in_one_piece_does_not_fail_the_whole_clip(fake_edge, monkeypatch) -> None:
    monkeypatch.setattr(edge.time, "sleep", lambda _seconds: None)  # nghỉ chờ giữa các lần thử không cần thật
    server, _ = fake_edge(hang=2)
    pieces = edge.speech_pieces(SENTENCES)
    result = _client(server).synthesize(SENTENCES, edge.DEFAULT_VOICE)
    assert len(result.audio) == 12000 * len(pieces)
    assert [b.text for b in result.boundaries] == SENTENCES.split()


def test_a_handshake_that_always_hangs_ends_as_offline_after_the_retries(fake_edge, monkeypatch) -> None:
    monkeypatch.setattr(edge.time, "sleep", lambda _seconds: None)  # nghỉ chờ giữa các lần thử không cần thật
    server, _ = fake_edge(hang=100)
    started = time.monotonic()
    with pytest.raises(edge.EdgeOffline) as caught:
        _client(server).synthesize("Xin chào", edge.DEFAULT_VOICE)
    assert caught.value.reason == "offline"
    assert len(server.hung) == edge.RETRIES + 1  # đã thử đủ lần, mỗi lần một kết nối mới
    assert time.monotonic() - started < 6.0


def test_a_dns_failure_or_a_refused_connection_stays_offline_at_once(monkeypatch) -> None:
    attempts: list[int] = []
    monkeypatch.setattr(edge.time, "sleep", lambda _seconds: attempts.append(1))
    for error in (socket.gaierror(11001, "không tìm thấy máy chủ"), ConnectionRefusedError(10061, "bị từ chối"), OSError(10051, "mạng không tới được")):
        def failing(*_args, _error=error, **_kwargs):  # noqa: ANN002, ANN003, ANN202
            raise _error

        monkeypatch.setattr(socket, "create_connection", failing)
        with pytest.raises(edge.EdgeOffline):
            edge.EdgeClient(connect_timeout=1).synthesize("Xin chào", edge.DEFAULT_VOICE)
    assert attempts == []  # không nghỉ chờ thử lại: mất mạng thật báo ngay như trước


def test_the_connect_timeout_is_a_few_times_the_measured_handshake_not_ten_seconds() -> None:
    assert 3.0 <= edge.CONNECT_TIMEOUT <= 5.0
