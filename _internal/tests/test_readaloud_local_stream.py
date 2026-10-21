"""Phát luồng giọng trên máy (local_stream.py, flac_mp4.py): khúc vừa đọc xong đi ngay tới người nghe, clip cuối KHÔNG đổi một byte, tiếng luồng = đúng các mẫu
int16 của clip cuối, mốc chữ tạm theo khúc, chờ đủ tiếng khi máy chậm hơn thời gian thực, bỏ giữa chừng thì dừng, model không bị nhả giữa luồng, bản ghi M / E
`exact` của máy chủ. Engine giả (như test_readaloud_vieneu / _supertonic), không chạm model thật."""
from __future__ import annotations

import io
import json
import struct
import threading
import time
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
import soundfile

from abook.readaloud import flac_mp4, local_stream, vieneu, vieneu_engine
from abook.readaloud import service as service_module
from abook.readaloud.model import VoiceError, hearing, stop_if_cancelled, unit_made
from abook.readaloud.service import ReadAloud
from abook.readaloud.supertonic import Installed as SupertonicInstalled
from abook.readaloud.supertonic import SupertonicProvider
from abook.readaloud.vieneu import Installed
from tests.test_readaloud_supertonic import FakeEngine as SupertonicFakeEngine
from tests.test_readaloud_vieneu import FakeEngine, _voices

LONG = "Câu đầu tiên dài vừa đủ một khúc của giọng nhẹ. " * 6  # nhiều khúc ở Nano (140 ký tự)


class Listener:
    """[service.StreamListener] ghi lại mọi thứ; `local` / `speed` như ClipStream của máy chủ."""

    def __init__(self, *, local: bool = True, speed: float = 1.0, on_audio=None) -> None:
        self.local = local
        self.speed = speed
        self.events: list[str] = []
        self.chunks: list[bytes] = []
        self.marks: list[tuple[list[list[int]], int, int]] = []
        self.mime = ""
        self.exact = True
        self.on_audio = on_audio

    def started(self) -> None:
        self.events.append("started")

    def format(self, mime: str) -> None:
        self.mime = mime
        self.events.append("format")

    def audio(self, data: bytes) -> None:
        self.chunks.append(data)
        self.events.append("audio")
        if self.on_audio is not None:
            self.on_audio()

    def words(self, words, duration_ms, heard_ms=0) -> None:
        self.marks.append((words, duration_ms, heard_ms))

    def replaced(self) -> None:
        self.exact = False

    def cut(self, word: int) -> None:
        raise AssertionError("giọng trên máy không cắt mảnh")



def _mdat(data: bytes) -> bytes:
    """Nội dung mọi hộp mdat của một luồng fMP4."""
    out, at = b"", 0
    while at < len(data):
        size, kind = struct.unpack(">I4s", data[at:at + 8])
        if kind == b"mdat":
            out += data[at + 8:at + size]
        at += size
    return out


def _pcm_of(stream: bytes, rate: int, count: int) -> bytes:
    """Giải luồng fMP4 FLAC bằng libsndfile (libFLAC: kiểm CRC từng khung) -> int16 little-endian. `count`: số mẫu ghi vào STREAMINFO (luồng để 0 = chưa biết,
    libsndfile cần nó để cấp chỗ)."""
    info = bytearray(flac_mp4.streaminfo(rate))
    info[10:18] = (int.from_bytes(info[10:18], "big") | count).to_bytes(8, "big")
    native = b"fLaC" + bytes([0x80, 0, 0, 34]) + bytes(info) + _mdat(stream)
    samples, found_rate = soundfile.read(io.BytesIO(native), dtype="int16")
    assert found_rate == rate
    return samples.astype("<i2").tobytes()


# ---- định dạng ---------------------------------------------------------------------------------------------------------------------
def test_flac_checksums_match_the_reference_check_values() -> None:
    assert flac_mp4.crc8(b"123456789") == 0xF4 and flac_mp4.crc16(b"123456789") == 0xFEE8


@pytest.mark.parametrize("length", [1, 2, 7, 8210, 20_000])
def test_the_table_crc16_equals_the_bit_by_bit_one(length: int) -> None:
    data = np.random.default_rng(length).integers(0, 256, length, dtype=np.uint8).tobytes()
    crc = 0
    for byte in data:  # CRC-16 của FLAC từng bit: đa thức 0x8005, khởi 0, không phản chiếu
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x8005) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    assert flac_mp4.crc16(data) == crc


@pytest.mark.parametrize("rate", [24_000, 44_100, 48_000])
def test_verbatim_flac_fragments_decode_to_the_exact_samples(rate: int) -> None:
    rng = np.random.default_rng(rate)
    pieces = [(rng.standard_normal(n) * 9000).clip(-32768, 32767).astype("<i2").tobytes() for n in (1, 4095, 4096, 10_001, rate)]
    stream, at = flac_mp4.init_segment(rate), 0
    for index, pcm in enumerate(pieces, 1):
        stream += flac_mp4.fragment(pcm, at, rate, index)
        at += len(pcm) // 2
    assert stream.startswith(struct.pack(">I", 28) + b"ftyp")
    assert _pcm_of(stream, rate, at) == b"".join(pieces), "không mất mẫu nào"
    assert flac_mp4.fragment(b"", 0, rate, 9) == b""


# ---- khi nào bắt đầu phát --------------------------------------------------------------------------------------------------------
def test_play_starts_when_every_later_unit_will_be_ready_in_time() -> None:
    assert local_stream.ready_to_play(3.0, 1.0, 30, [30, 60]), "máy nhanh gấp 3: phát ngay"
    assert local_stream.ready_to_play(3.0, 9.0, 30, []), "khúc cuối đã xong: luôn phát"
    assert not local_stream.ready_to_play(3.0, 6.0, 30, [30]), "chậm gấp đôi: khúc sau chưa kịp"
    assert not local_stream.ready_to_play(3.0, 2.8, 30, [30]), "sát thời gian thực: đệm 20 % sai số"
    assert local_stream.ready_to_play(3.0, 2.0, 30, [30]), "r = 0,67, 1,2 x 0,67 x 3 = 2,4 <= 3"
    assert not local_stream.ready_to_play(3.0, 2.0, 30, [30], speed=1.5), "nghe nhanh hơn thì cần đệm nhiều hơn"
    assert not local_stream.ready_to_play(1.0, 0.5, 10, [10, 200]), "khúc ngắn rồi khúc rất dài: khúc dài chưa kịp"
    assert not local_stream.ready_to_play(0.0, 0.5, 10, [10])


def test_a_slow_machine_holds_the_units_until_the_rest_will_keep_up() -> None:
    rate, now = 24_000, [0.0]
    toks, parts = vieneu.units(LONG.strip(), 140)
    assert len(parts) >= 3
    listener = Listener()
    stream = local_stream.LocalStream(listener, toks, parts, None, clock=lambda: now[0])
    engine = FakeEngine(rate)
    for index, part in enumerate(parts):
        wave = engine.infer(" ".join(part.pieces))
        now[0] += 2.5 * len(wave) / rate  # máy chậm hơn thời gian thực 2,5 lần
        stream(wave, rate, " ".join(part.pieces) + ".", 2.5 * len(wave) / rate)
        if index < len(parts) - 1:
            assert not listener.events, "chưa phát: phát bây giờ thì đứt giữa chừng"
    assert listener.events[:3] == ["started", "format", "audio"] and listener.events.count("audio") == len(parts), "xong cả clip: gửi hết"


def _slow_units(stream, parts, rate, now, upto=None):
    """Đưa các khúc (tới `upto`) vào `stream` như máy chậm hơn thời gian thực 2,5 lần."""
    engine = FakeEngine(rate)
    for part in parts[:upto]:
        wave = engine.infer(" ".join(part.pieces))
        now[0] += 2.5 * len(wave) / rate
        stream(wave, rate, " ".join(part.pieces) + ".", 2.5 * len(wave) / rate)


def test_a_listener_with_no_sound_left_hears_the_first_unit_at_once() -> None:
    """dev/gap (OPPO, Supertonic nhanh): khúc đầu đã xong mà bị giữ 3,4 s / 8,8 s trong lúc người nghe ngồi trong im lặng. Hết tiếng rồi thì giữ chỉ làm lặng dài thêm."""
    rate, now = 24_000, [0.0]
    toks, parts = vieneu.units(LONG.strip(), 140)
    listener = Listener()
    later: list[tuple[float, object]] = []
    stream = local_stream.LocalStream(listener, toks, parts, None, clock=lambda: now[0], reach=0.0, later=lambda delay, task: later.append((delay, task)))
    _slow_units(stream, parts, rate, now, 1)
    assert listener.events == ["started", "format", "audio"] and not later, "khúc đầu đi ngay"
    _slow_units(stream, parts[1:], rate, now)
    assert listener.events.count("audio") == len(parts), "các khúc sau đi khi xong, như luồng đã bắt đầu"


def test_the_held_units_go_out_when_the_listener_runs_out_of_sound_between_two_units() -> None:
    rate, now = 24_000, [0.0]
    toks, parts = vieneu.units(LONG.strip(), 140)
    listener = Listener()
    later: list[tuple[float, object]] = []
    stream = local_stream.LocalStream(listener, toks, parts, None, clock=lambda: now[0], reach=1000.0, later=lambda delay, task: later.append((delay, task)))
    _slow_units(stream, parts, rate, now, 1)
    first = now[0]
    _slow_units(stream, parts[1:], rate, now, 1)
    assert not listener.events, "còn tiếng: giữ như cũ"
    assert len(later) == 1, "hẹn đúng một lần"
    delay, task = later[0]
    assert delay == pytest.approx(1000.0 - first), "hẹn tới lúc người nghe hết tiếng"
    task()
    assert listener.events == ["started", "format", "audio", "audio"], "tới lúc người nghe hết tiếng: hai khúc đã xong đi ngay"
    _slow_units(stream, parts[2:], rate, now)
    assert listener.events.count("audio") == len(parts)


def test_a_late_release_after_the_clip_is_done_or_failed_sends_nothing() -> None:
    rate, now = 24_000, [0.0]
    toks, parts = vieneu.units(LONG.strip(), 140)
    for end in ("close", "drop"):
        listener = Listener()
        later: list[tuple[float, object]] = []
        stream = local_stream.LocalStream(listener, toks, parts, None, clock=lambda: now[0], reach=1e9, later=lambda delay, task: later.append((delay, task)))
        _slow_units(stream, parts, rate, now, 1)
        stream.close(b"") if end == "close" else stream.drop()
        later[0][1]()
        assert not listener.events, end


def test_a_failed_read_cancels_the_pending_release(local_voices, monkeypatch: pytest.MonkeyPatch) -> None:
    make, engines, _ = local_voices
    engines["nano"] = AskingEngine(24_000)
    later: list[object] = []
    monkeypatch.setattr(local_stream, "_schedule", lambda delay, task: later.append(task))
    monkeypatch.setattr(local_stream, "ready_to_play", lambda *args, **kwargs: False)  # máy chậm: không bao giờ tự phát
    calls = [0]

    def gone() -> bool:
        calls[0] += 1
        return calls[0] > 2

    listener = Listener()
    listener.reach = time.perf_counter() + 60
    with pytest.raises(VoiceError):
        make("cache").clip("vieneu:nano/Nhẹ", LONG.strip(), rank=1, stream=listener, cancelled=gone)
    assert later, "đã hẹn"
    later[0]()
    assert not listener.events, "lượt hỏng: không ghi gì vào lời đáp lỗi"


# ---- clip qua ReadAloud: bất biến byte ---------------------------------------------------------------------------------------------
@pytest.fixture
def local_voices(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(vieneu_engine, "phonemize", lambda pieces: " ".join(pieces).lower().rstrip(".!?,") + ".")
    found = {"": Installed(_voices(tmp_path / "voices"), (tmp_path, tmp_path), tmp_path, False)}  # bài thử đổi được (bộ căn chữ)
    engines = {"turbo": FakeEngine(48_000), "nano": FakeEngine(24_000)}

    def make(folder: str, **kwargs) -> ReadAloud:
        return ReadAloud(tmp_path / folder, [], vieneu_locate=lambda: found[""], vieneu_engines=lambda tier, _found: engines[tier], **kwargs)

    return make, engines, found


@pytest.mark.parametrize("voice, text", [("vieneu:nano/Nhẹ", LONG.strip()), ("vieneu:turbo/Thường", LONG.strip())], ids=["nano", "turbo"])
def test_the_streamed_clip_is_byte_identical_and_the_stream_is_its_samples(local_voices, tmp_path: Path, voice: str, text: str) -> None:
    make, _, _ = local_voices
    plain = make("plain").clip(voice, text)
    listener = Listener()
    streamed_service = make("streamed")
    streamed = streamed_service.clip(voice, text, rank=0, stream=listener)
    assert (tmp_path / "streamed" / streamed["file"]).read_bytes() == (tmp_path / "plain" / plain["file"]).read_bytes(), "clip cuối không đổi một byte"
    assert streamed == plain, "cùng tên file, độ dài, mốc chữ"
    assert listener.events[:3] == ["started", "format", "audio"] and listener.mime == local_stream.MIME and listener.exact
    rate = 24_000 if "nano" in voice else 48_000
    final = (tmp_path / "streamed" / streamed["file"]).read_bytes()
    assert _pcm_of(b"".join(listener.chunks), rate, len(final[44:]) // 2) == final[44:], "tiếng luồng = đúng các mẫu int16 của clip cuối"
    tier = voice.split(":")[1].split("/")[0]
    _, parts = vieneu.units(text, vieneu.MAX_CHARS[tier])
    assert len(listener.chunks) == len(parts), "mỗi khúc một mảnh, đi ngay khi xong"
    words, duration, heard = listener.marks[0]
    assert len(words) == len(text.split()) and heard == duration
    assert all(b <= duration for _, b in words), "chữ chưa tới đứng cuối phần đã có"
    last, total, _ = listener.marks[-1]
    assert total == streamed["duration_ms"] and last == streamed["words"], "khúc cuối xong: mốc tạm = mốc cuối"


def test_without_local_or_in_the_background_nothing_streams(local_voices) -> None:
    make, _, _ = local_voices
    service = make("cache")
    edge_only = Listener(local=False)
    service.clip("vieneu:nano/Nhẹ", LONG.strip(), rank=0, stream=edge_only)
    background = Listener()
    service.clip("vieneu:nano/Nhẹ", LONG.strip() + " Làm trước.", rank=0, stream=background, background=True)
    assert not edge_only.events and not background.events


def test_a_read_ahead_paragraph_streams_too_so_the_player_can_join_it_while_it_is_read(local_voices, tmp_path: Path) -> None:
    """livejoin: giọng trên máy không có hàng chờ kết nối để nhường, nên đoạn đọc trước (rank > 0) cũng phát luồng; clip cuối vẫn y hệt."""
    make, _, _ = local_voices
    plain = make("plain").clip("vieneu:nano/Nhẹ", LONG.strip(), rank=3)
    ahead = Listener()
    streamed = make("ahead").clip("vieneu:nano/Nhẹ", LONG.strip(), rank=3, stream=ahead)
    assert ahead.events[:2] == ["started", "format"] and ahead.chunks
    assert streamed == plain
    assert (tmp_path / "ahead" / streamed["file"]).read_bytes() == (tmp_path / "plain" / plain["file"]).read_bytes()


def test_the_aligner_runs_once_per_unit_when_streaming(local_voices, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from abook.webui import word_timing

    make, _, found = local_voices
    found[""] = replace(found[""], aligner=True)
    calls: list[str] = []

    class CountingAligner:
        def align(self, wave, text, offset):
            calls.append(text)
            count = len(text.split())
            step = len(wave) / 16_000 / count
            return [[offset + i * step, offset + (i + 1) * step] for i in range(count)], 0.99  # giây, như Aligner.align

    shared = CountingAligner()  # như word_timing.get_aligner: một bộ căn nạp một lần
    monkeypatch.setattr(word_timing, "get_aligner", lambda: shared)
    monkeypatch.setattr(local_stream, "_remembered", None)
    plain = make("plain").clip("vieneu:nano/Nhẹ", LONG.strip())
    units_count = len(calls)
    calls.clear()
    listener = Listener()
    streamed = make("streamed").clip("vieneu:nano/Nhẹ", LONG.strip(), rank=0, stream=listener)
    assert len(calls) == units_count > 1, "clip cuối lấy lại phần căn lúc phát luồng, không căn lần hai"
    assert streamed["words"] == plain["words"] and listener.marks[-1][0] == plain["words"]


def test_a_one_unit_paragraph_is_answered_as_before(local_voices, tmp_path: Path) -> None:
    make, _, _ = local_voices
    text = "Xin chào các bạn, hôm nay trời đẹp quá."
    assert len(vieneu.units(text, vieneu.MAX_CHARS["turbo"])[1]) == 1
    listener = Listener()
    streamed = make("streamed").clip("vieneu:turbo/Thường", text, rank=0, stream=listener)
    assert not listener.events, "khúc đầu là cả clip: phát luồng không sớm hơn, chỉ tốn thêm"
    assert streamed == make("plain").clip("vieneu:turbo/Thường", text)


def test_a_lifted_clip_of_many_units_says_the_stream_was_replaced(tmp_path: Path) -> None:
    engine = SupertonicFakeEngine()
    infer = engine.infer
    engine.infer = lambda *a, **k: infer(*a, **k) * np.float32(0.04)
    provider = SupertonicProvider(lambda: SupertonicInstalled(tmp_path, False), engines=lambda _found: engine, aligner=lambda: None,
                                  normalize=lambda pieces: " ".join(pieces).lower())
    provider.speaks_english = False
    text = "Ừ. " + "Câu này dài để đoạn thành nhiều khúc của giọng Supertonic nhé. " * 8
    service = ReadAloud(tmp_path / "cache", [provider])
    listener = Listener()
    clip = service.clip("supertonic:F3", text.strip(), rank=0, stream=listener)
    plain = ReadAloud(tmp_path / "plain", [provider]).clip("supertonic:F3", text.strip())
    assert (tmp_path / "cache" / clip["file"]).read_bytes() == (tmp_path / "plain" / plain["file"]).read_bytes()
    final = (tmp_path / "cache" / clip["file"]).read_bytes()
    streamed = _pcm_of(b"".join(listener.chunks), 44_100, len(final[44:]) // 2)
    assert listener.events.count("audio") > 1
    assert listener.exact == (streamed == final[44:]), "khác clip cuối (bù cả clip) thì báo, giống thì không"


class AskingEngine(FakeEngine):
    """Như engine thật: hỏi cờ bỏ lượt trước mỗi khúc (vieneu_engine)."""

    def infer(self, phonemes: str, *args, **kwargs) -> np.ndarray:
        stop_if_cancelled()
        return super().infer(phonemes, *args, **kwargs)


def test_leaving_the_paragraph_stops_the_voice_and_caches_nothing(local_voices, tmp_path: Path) -> None:
    make, engines, _ = local_voices
    engines["nano"] = AskingEngine(24_000)
    gone = threading.Event()
    listener = Listener(on_audio=gone.set)
    service = make("cache")
    with pytest.raises(VoiceError) as error:
        service.clip("vieneu:nano/Nhẹ", LONG.strip(), rank=0, stream=listener, cancelled=gone.is_set)
    assert error.value.reason == "cancelled"
    assert len(engines["nano"].calls) < len(vieneu.units(LONG.strip(), 140)[1]), "dừng giữa các khúc"
    assert not list((tmp_path / "cache").glob("*.wav"))


def test_the_model_is_not_released_while_a_clip_is_streaming(local_voices) -> None:
    make, _, _ = local_voices
    now = [0.0]
    released: list[list[str]] = []
    service = make("cache", clock=lambda: now[0])

    def idle() -> None:
        now[0] += service_module.IDLE_SECONDS * 2
        released.append(service.release_idle())

    service.clip("vieneu:nano/Nhẹ", LONG.strip(), rank=0, stream=Listener(on_audio=idle))
    assert released and all(item == [] for item in released), "đang phát luồng = đang dùng"
    now[0] += service_module.IDLE_SECONDS * 2
    assert service.release_idle() == ["vieneu"], "xong rồi thì nhả như thường"


def test_units_reach_no_one_outside_hearing() -> None:
    heard: list[int] = []
    unit_made(np.zeros(3), 24_000, "a.", 0.1)
    with hearing(lambda wave, rate, said, seconds: heard.append(rate)):
        unit_made(np.zeros(3), 24_000, "a.", 0.1)
    unit_made(np.zeros(3), 24_000, "a.", 0.1)
    assert heard == [24_000]


# ---- máy chủ: bản ghi M, E exact ---------------------------------------------------------------------------------------------------
def test_the_server_streams_a_local_voice_only_when_the_player_takes_flac(local_voices, tmp_path: Path) -> None:
    from tests.test_readaloud import FakeProvider, _server
    from tests.test_readaloud_edge_stream import post_clip, records

    make, _, _ = local_voices
    server = _server(tmp_path, FakeProvider())
    server.app.readaloud = make("prefs/readaloud-cache")
    try:
        body = {"voice": "vieneu:nano/Nhẹ", "text": LONG.strip(), "rank": 0, "stream": True}
        _, response, data = post_clip(server.port, body)
        assert response.getheader("Content-Type").startswith("application/json"), "trình phát không nói nhận FLAC: JSON như cũ"
        _, response, data = post_clip(server.port, {**body, "text": "Đoạn khác. " + LONG.strip(), "localStream": True, "rate": 1.25})
        assert response.status == 200 and response.getheader("Content-Type") == "application/vnd.abook.clipstream"
        found = records(data)
        kinds = [kind for kind, _ in found]
        assert kinds[:2] == ["M", "A"] and kinds[-1] == "E" and json.loads(found[0][1]) == {"mime": local_stream.MIME}
        final = json.loads(found[-1][1])
        assert "exact" not in final and final["url"].endswith(".wav")
        # livejoin: đoạn đọc trước (rank > 0) của giọng trên máy cũng phát luồng; Edge (không `localStream`) thì vẫn chỉ rank 0
        _, response, data = post_clip(server.port, {**body, "text": "Đoạn đọc trước. " + LONG.strip(), "rank": 2, "localStream": True})
        assert response.getheader("Content-Type") == "application/vnd.abook.clipstream" and records(data)[0][0] == "M"
        _, response, _ = post_clip(server.port, {**body, "text": "Đoạn khác nữa. " + LONG.strip(), "rank": 2})
        assert response.getheader("Content-Type").startswith("application/json")
    finally:
        server.stop()


def test_the_server_passes_the_sound_left_as_the_moment_to_stop_holding(local_voices, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.test_readaloud import FakeProvider, _server
    from tests.test_readaloud_edge_stream import post_clip

    make, _, _ = local_voices
    seen: list[float] = []
    real = local_stream.for_clip
    monkeypatch.setattr(local_stream, "for_clip", lambda *args: seen.append(args[-1]) or real(*args))
    server = _server(tmp_path, FakeProvider())
    server.app.readaloud = make("prefs/readaloud-cache")
    try:
        body = {"voice": "vieneu:nano/Nhẹ", "text": LONG.strip(), "rank": 1, "stream": True, "localStream": True}
        before = time.perf_counter()
        post_clip(server.port, {**body, "soundLeft": 7.5})
        post_clip(server.port, {**body, "text": "Đoạn khác. " + LONG.strip()})
        post_clip(server.port, {**body, "text": "Đoạn nữa. " + LONG.strip(), "soundLeft": "7"})
        assert before + 7.5 <= seen[0] <= time.perf_counter() + 7.5, "giây còn nghe -> lúc hết tiếng"
        assert seen[1:] == [float("inf"), float("inf")], "không nói / sai kiểu: không biết"
    finally:
        server.stop()
