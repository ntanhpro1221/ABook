"""uxfix70 (soát a63, giọng trên máy - VieNeu, Supertonic - trên máy tính):
1. khoá bộ đệm clip mang dấu model (ghim các file model đang dùng + lịch đọc): cập nhật model / đổi lịch thì đoạn đã đọc sẵn được đọc lại; Edge không đổi khoá;
2. nút tải / cập nhật ghi phần CÒN phải tải (file đúng đã có không tính, phần dở sau Huỷ chỉ tính phần còn lại);
3. đổi "Tốc độ giọng trên máy" giữa chừng: nghe ở bậc nhanh dùng được clip bậc chất lượng đã có (chất lượng trước); bậc chất lượng / xuất chỉ nhận chất lượng;
4. lượt đọc trên máy không ai cần nữa dừng giữa các khúc / bước (VoiceError "cancelled", không gì vào bộ đệm): engine Nano / Turbo / Supertonic giả nhẹ,
   ReadAloud, máy chủ giao diện (trình phát đóng kết nối) và Huỷ xuất sách nói."""
from __future__ import annotations

import json
import os
import socket
import threading
import time
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from abook.readaloud import model, supertonic, vieneu_engine
from abook.readaloud.mapping import Boundary
from abook.readaloud.model import Synthesis, Voice, VoiceError, cancellable
from abook.readaloud.service import ReadAloud
from abook.webui import music_module, studio_setup, supertonic_module, vieneu_module, voice_module
from abook.webui.studio_setup import Download


class PlainVoice:
    """Giọng giả đọc đoạn thành `chunks` khúc, mỗi khúc `step` giây, hỏi cờ bỏ giữa các khúc như engine thật. Không có `reading_tag`: như Edge / giọng dùng khoá."""

    speaks_english = True

    def __init__(self, id: str = "local", *, chunks: int = 1, step: float = 0.0) -> None:
        self.id = id
        self.chunks, self.step = chunks, step
        self.calls: list[str] = []
        self.done_chunks = 0
        self.started = threading.Event()
        self.stopped_at: float | None = None

    def voices(self) -> list[Voice]:
        return [Voice(f"{self.id}:a", "A", self.id, False, True)]

    def synthesize(self, text: str, native_voice: str, origin: str | None = None, readings: Any = None) -> Synthesis:
        self.calls.append(text)
        self.started.set()
        try:
            for _ in range(self.chunks):
                model.stop_if_cancelled()
                time.sleep(self.step)
                self.done_chunks += 1
        except VoiceError:
            self.stopped_at = time.monotonic()
            raise
        return Synthesis(b"ID3" + bytes(64), [Boundary(word, index * 100, index * 100 + 90) for index, word in enumerate(text.split())], 500)


class LocalVoice(PlainVoice):
    """Giọng trên máy giả (có `reading_tag` như VieNeu / Supertonic)."""

    def reading_tag(self, text: str, origin: str | None) -> str:
        return ""


# ---- 1. dấu model trong khoá ----------------------------------------------------------------------------------------------------------

def test_a_new_model_mark_reads_the_paragraph_again_once_and_edge_keys_never_change(tmp_path: Path) -> None:
    mark = {"value": "aaaa1111"}
    asked: list[tuple[str, str]] = []

    def model_mark(voice: str, tier: str) -> str:
        asked.append((voice, tier))
        return mark["value"]

    local = LocalVoice()
    service = ReadAloud(tmp_path / "local", [local], model_mark=model_mark)
    service.clip("local:a", "Một hai ba.")
    service.clip("local:a", "Một hai ba.")
    assert local.calls == ["Một hai ba."] and asked[0] == ("local:a", "")
    mark["value"] = "bbbb2222"  # model cập nhật / lịch đọc đổi
    service.clip("local:a", "Một hai ba.")
    service.clip("local:a", "Một hai ba.")
    assert local.calls == ["Một hai ba."] * 2, "đọc lại đúng một lần với model mới"

    plain = PlainVoice("plain")
    asked.clear()
    online = ReadAloud(tmp_path / "plain", [plain], model_mark=model_mark)
    online.clip("plain:a", "Bốn năm.")
    mark["value"] = "cccc3333"
    online.clip("plain:a", "Bốn năm.")
    assert plain.calls == ["Bốn năm."] and asked == [], "giọng không đọc trên máy: không hỏi dấu model, khoá không đổi"


def test_the_module_mark_follows_the_pins_and_the_schedule_and_is_computed_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    core = voice_module.ModuleCore("giọng thử", "thu", frozenset(), lambda: True)
    core.configure(tmp_path, None, None)
    core.write_stamp({"pins": {"voices": "v1", "nano": "n1", "turbo": "t1"}})
    first = core.mark(("voices", "nano"), "nano:6:3.0:False")
    assert len(first) == 8 and int(first, 16) >= 0
    reads: list[int] = []
    real = core.read_stamp
    monkeypatch.setattr(core, "read_stamp", lambda: (reads.append(1), real())[1])
    assert core.mark(("voices", "nano"), "nano:6:3.0:False") == first and reads == [], "tính một lần, không đọc module.json mỗi clip"
    assert core.mark(("voices", "nano"), "nano:8:3.0:True") != first, "lịch đọc đổi -> dấu đổi"
    core.write_stamp({"pins": {"voices": "v1", "nano": "n2", "turbo": "t1"}})  # cập nhật phần Nano
    assert core.mark(("voices", "nano"), "nano:6:3.0:False") != first
    core.write_stamp({"pins": {"voices": "v1", "nano": "n1", "turbo": "t9"}})
    assert core.mark(("voices", "nano"), "nano:6:3.0:False") == first, "phần của tầng khác đổi: dấu Nano giữ nguyên"


def test_the_voice_modules_mark_their_own_voices_by_tier(tmp_path: Path) -> None:
    supertonic_module.configure(tmp_path / "supertonic")
    vieneu_module.configure(tmp_path / "vieneu")
    try:
        supertonic_module._core.write_stamp({"pins": {"supertonic": "s1", "supertonic_fast": "f1"}})
        vieneu_module._core.write_stamp({"pins": {"voices": "v1", "nano": "n1", "turbo": "t1"}})
        quality, fast = supertonic_module.model_mark("supertonic:F1", ""), supertonic_module.model_mark("supertonic:F1", "fast5")
        nano, turbo = vieneu_module.model_mark("vieneu:nano/Ái Hân"), vieneu_module.model_mark("vieneu:turbo/Đức Trí")
        assert len({quality, fast, nano, turbo}) == 4
        assert supertonic_module.model_mark("edge:vi-VN-HoaiMyNeural", "") == "" and vieneu_module.model_mark("supertonic:F1") == ""
        supertonic_module._core.write_stamp({"pins": {"supertonic": "s1", "supertonic_fast": "f2"}})
        assert supertonic_module.model_mark("supertonic:F1", "") == quality and supertonic_module.model_mark("supertonic:F1", "fast5") != fast
        supertonic_module._core.write_stamp({"pins": {"supertonic": "s2", "supertonic_fast": "f2"}})
        assert supertonic_module.model_mark("supertonic:F1", "") != quality, "file model chung đổi: cả hai bậc đọc lại"
        vieneu_module._core.write_stamp({"pins": {"voices": "v1", "nano": "n2", "turbo": "t1"}})
        assert vieneu_module.model_mark("vieneu:nano/Ái Hân") != nano and vieneu_module.model_mark("vieneu:turbo/Đức Trí") == turbo
    finally:
        supertonic_module.configure(None)
        vieneu_module.configure(None)


def test_the_nano_schedule_is_part_of_the_mark(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    vieneu_module.configure(tmp_path / "vieneu")
    try:
        vieneu_module._core.write_stamp({"pins": {"voices": "v1", "nano": "n1"}})
        before = vieneu_module.model_mark("vieneu:nano/Ái Hân")
        monkeypatch.setattr(vieneu_engine, "NANO_STEPS", vieneu_engine.NANO_STEPS + 2)
        assert vieneu_module.model_mark("vieneu:nano/Ái Hân") != before
    finally:
        vieneu_module.configure(None)


# ---- 2. cỡ phần còn phải tải ---------------------------------------------------------------------------------------------------------

def _item(name: str, data: bytes) -> Download:
    import hashlib

    return Download(name, f"https://example.invalid/{name}", hashlib.sha256(data).hexdigest(), len(data))


def test_left_counts_only_missing_or_changed_files_and_the_rest_of_a_partial_one(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    good, other = b"0123456789", b"abcdefghij"
    item = _item("a.bin", good)
    target = tmp_path / "a.bin"
    assert studio_setup.left(item, target) == 10
    target.with_name("a.bin.part").write_bytes(good[:3])
    assert studio_setup.left(item, target) == 7, "phần dở sau Huỷ: chỉ phần còn lại"
    target.write_bytes(other)  # cùng cỡ, khác nội dung (bản cũ)
    assert studio_setup.left(item, target) == 7
    target.write_bytes(good)
    # Hai lần ghi cùng cỡ trong một nhịp đồng hồ hệ thống có thể cùng giờ sửa (khoá băm của `matches`): đẩy giờ sửa đi như một lần tải thật.
    stamp = target.stat().st_mtime_ns + 1_000_000_000
    os.utime(target, ns=(stamp, stamp))
    assert studio_setup.left(item, target) == 0
    hashed: list[Path] = []
    real = studio_setup._sha256
    monkeypatch.setattr(studio_setup, "_sha256", lambda path: (hashed.append(path), real(path))[1])
    assert studio_setup.left(item, target) == 0 and studio_setup.matches(target, item) and hashed == [], "file đã băm thì không băm lại"


def test_the_supertonic_card_shows_what_is_left_to_download(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    files = (_item("onnx/a.onnx", b"A" * 40), _item("onnx/b.onnx", b"B" * 60))
    fast = (_item("vector_estimator.onnx", b"F" * 50),)
    monkeypatch.setattr(supertonic_module, "FILES", files)
    monkeypatch.setattr(supertonic_module, "FAST_FILES", fast)
    monkeypatch.setattr(music_module, "libs_part", lambda blocked=None: music_module.Component("libs", "Thư viện", "x", 1, True, external=True))
    monkeypatch.setattr(vieneu_module, "g2p_part", lambda: music_module.Component("g2p", "Bộ đọc chữ", "x", 1, True, external=True))
    supertonic_module.configure(tmp_path / "supertonic")
    try:
        model = tmp_path / "supertonic" / "model"
        (model / "onnx").mkdir(parents=True)
        (model / "onnx" / "a.onnx").write_bytes(b"A" * 40)
        (model / "onnx" / "b.onnx.part").write_bytes(b"B" * 25)  # Huỷ giữa file thứ hai
        status = supertonic_module.status()
        choice = next(row for row in status["choices"] if row["id"] == "supertonic")
        part = next(row for row in status["parts"] if row["id"] == "supertonic")
        assert choice["bytes"] == 35 and part["bytes"] == 35, "40 B đã đủ, 25 B của file dở: còn 35 B (không phải 100)"
        (model / "onnx" / "b.onnx").write_bytes(b"B" * 60)
        (model / "onnx" / "b.onnx.part").unlink()
        supertonic_module._core.write_stamp({"pins": {"supertonic": "ghim-cu"}})  # bản cũ đã tải: thẻ mời "Cập nhật"
        (model / "onnx" / "b.onnx").write_bytes(b"b" * 60)  # chỉ file b đổi trong bản mới
        status = supertonic_module.status()
        assert status["state"] == "outdated" and status["outdatedBytes"] == 60, "cập nhật chỉ tải file đổi"
        assert supertonic_module.speed_fast_bytes() == 50
        (tmp_path / "supertonic" / "fast").mkdir()
        (tmp_path / "supertonic" / "fast" / "vector_estimator.onnx.part").write_bytes(b"F" * 20)
        assert supertonic_module.speed_fast_bytes() == 30, "Bản nhanh hơn dở: dòng Tốc độ giọng ghi phần còn lại"
    finally:
        supertonic_module.configure(None)


# ---- 3. tra bậc -----------------------------------------------------------------------------------------------------------------------

def test_listening_fast_takes_a_quality_clip_first_but_never_the_other_way(tmp_path: Path) -> None:
    tier = {"value": ""}
    quality, fast = LocalVoice(), LocalVoice()
    service = ReadAloud(tmp_path, [quality], speed=lambda _voice: tier["value"], model_mark=lambda _voice, tag: f"m{tag}")
    service.fast["local"] = fast
    made = service.clip("local:a", "Đoạn đã chuẩn bị.")  # đọc sẵn ở bậc chất lượng
    tier["value"] = "fast5"  # người nghe đổi sang Nhanh hơn giữa chương
    assert service.clip("local:a", "Đoạn đã chuẩn bị.") == made and fast.calls == [], "ca 1: nghe nhanh dùng clip chất lượng đã có"
    service.clip("local:a", "Đoạn chưa có.")
    assert fast.calls == ["Đoạn chưa có."] and quality.calls == ["Đoạn đã chuẩn bị."], "ca 1b: chưa có gì thì đọc bậc nhanh"
    tier["value"] = ""
    service.clip("local:a", "Đoạn chưa có.")
    assert quality.calls == ["Đoạn đã chuẩn bị.", "Đoạn chưa có."], "ca 2: nghe chất lượng không nhận clip bậc nhanh"
    tier["value"] = "fast5"
    service.clip("local:a", "Một đoạn nhanh.")
    service.clip("local:a", "Một đoạn nhanh.", quality=True)
    assert quality.calls[-1] == "Một đoạn nhanh.", "ca 3: xuất (quality) không nhận clip bậc nhanh"
    with pytest.raises(VoiceError):
        service.clip("local:a", "Lạ hoắc.", cached_only=True)
    assert service.clip("local:a", "Đoạn đã chuẩn bị.", cached_only=True) == made, "tra bộ đệm ở bậc nhanh cũng thấy clip chất lượng"


# ---- 4. dừng lượt đọc không ai cần --------------------------------------------------------------------------------------------------

class _Flag:
    """Cờ bỏ đúng sau `after` lần hỏi."""

    def __init__(self, after: int) -> None:
        self.after, self.asked = after, 0

    def __call__(self) -> bool:
        self.asked += 1
        return self.asked > self.after


class _Session:
    def __init__(self, run: Any) -> None:
        self.run = run


def test_the_nano_engine_stops_between_flow_steps() -> None:
    engine = vieneu_engine.NanoEngine.__new__(vieneu_engine.NanoEngine)
    engine._lock = threading.RLock()
    engine.vocab, engine.emotion_map, engine.bos, engine.eos, engine.pad, engine.fps = {"a": 3}, {}, 1, 2, 0, 10.0
    engine.null_ctx, engine.null_mask = np.zeros((1, 2, 4), np.float32), np.ones((1, 2), bool)
    engine.null_spk, engine.null_style = np.zeros((1, 4), np.float32), np.zeros((1, 2, 4), np.float32)
    steps: list[int] = []
    engine.text = _Session(lambda _o, feed: [np.zeros((1, 3, 4), np.float32)])
    engine.dur = _Session(lambda _o, feed: [np.array([0.0], np.float32)])
    engine.ve = _Session(lambda _o, feed: (steps.append(1), [np.zeros_like(feed["x"])])[1])
    engine.dec = _Session(lambda _o, feed: [np.zeros((1, 1, 2400), np.float32)])
    with cancellable(lambda: False):
        engine.infer("aaa", np.zeros(4, np.float32), np.zeros((1, 2, 4), np.float32), seed=1)
    full = len(steps)
    assert full == 2 * vieneu_engine.NANO_STEPS - (0 if vieneu_engine.NANO_CFG_LAST else 1)
    steps.clear()
    flag = _Flag(2)  # hỏi lần 1 ở đầu khúc, lần 2 trước bước 1, lần 3 (trước bước 2) thì đã bỏ
    with cancellable(flag), pytest.raises(VoiceError) as caught:
        engine.infer("aaa", np.zeros(4, np.float32), np.zeros((1, 2, 4), np.float32), seed=1)
    assert caught.value.reason == "cancelled" and len(steps) <= 2, "dừng trong vòng một bước"


def test_the_turbo_engine_stops_between_frames() -> None:
    engine = vieneu_engine.TurboEngine.__new__(vieneu_engine.TurboEngine)
    engine.layers, engine.n_vq, engine.audio_pad, engine.sgs = 1, 1, 0, 5
    frames: list[int] = []
    engine.pre = _Session(lambda _o, feed: [np.zeros((1, 2, 4), np.float32), np.zeros(1), np.zeros(1)])
    engine.dec = _Session(lambda _o, feed: [np.zeros((1, 1, 4), np.float32), np.zeros(1), np.zeros(1)])
    engine._frame = lambda h, sampling, hist, rng: (frames.append(1), ([7], False))[1]
    engine._embed = lambda rows, anchor: np.zeros((1, 1, 4), np.float32)
    sampling = {**vieneu_engine.DEFAULT_SAMPLING, "repetition_penalty": 1.0}
    with cancellable(_Flag(3)), pytest.raises(VoiceError) as caught:
        engine._generate(np.zeros((1, 2, 4), np.float32), None, 200, sampling, np.random.RandomState(1))
    assert caught.value.reason == "cancelled" and len(frames) == 3, "dừng ở frame kế, không chạy hết 200 frame"


def test_the_supertonic_engine_stops_between_denoising_steps() -> None:
    engine = supertonic.SupertonicEngine.__new__(supertonic.SupertonicEngine)
    engine.SAMPLE_RATE, engine.chunk, engine.latent_dim, engine.steps = 44_100, 512, 4, 8
    engine.indexer = np.arange(0x3000, dtype=np.int64)
    engine._styles = {"F1": (np.zeros((1, 2, 4), np.float32), np.zeros((1, 2, 4), np.float32))}
    engine._lock = threading.Lock()
    steps: list[int] = []
    engine.sessions = {
        "duration_predictor": _Session(lambda _o, feed: [np.array([0.5], np.float32)]),
        "text_encoder": _Session(lambda _o, feed: [np.zeros((1, 4, 3), np.float32)]),
        "vector_estimator": _Session(lambda _o, feed: (steps.append(1), [feed["noisy_latent"]])[1]),
        "vocoder": _Session(lambda _o, feed: [np.zeros((1, 44_100), np.float32)]),
    }
    with cancellable(_Flag(3)), pytest.raises(VoiceError) as caught:
        engine.infer("Xin chào.", "F1", np.random.RandomState(1))
    assert caught.value.reason == "cancelled" and len(steps) == 2, "dừng trước bước khử nhiễu kế (8 bước)"


def test_a_cancelled_local_read_stops_within_one_chunk_and_caches_nothing(tmp_path: Path) -> None:
    local = LocalVoice(chunks=50, step=0.01)
    service = ReadAloud(tmp_path, [local])
    with pytest.raises(VoiceError) as caught:
        service.clip("local:a", "Một đoạn dài.", cancelled=lambda: local.done_chunks >= 3)
    assert caught.value.reason == "cancelled" and local.done_chunks == 3
    assert not list(tmp_path.glob("*.mp3")), "không gì vào bộ đệm"
    with pytest.raises(VoiceError):
        service.clip("local:a", "Một đoạn dài.", cached_only=True)
    model.stop_if_cancelled()  # ngoài lượt ấy: không còn cờ nào


def test_the_player_closing_the_connection_frees_the_cpu_within_a_fraction_of_a_second(tmp_path: Path) -> None:
    from tests.test_readaloud import _server

    local = LocalVoice(chunks=500, step=0.01)  # 5 giây nếu không ai dừng
    server = _server(tmp_path, local)  # type: ignore[arg-type]
    try:
        body = json.dumps({"voice": "local:a", "text": "Đoạn người nghe vừa bỏ."}).encode("utf-8")
        client = socket.create_connection(("127.0.0.1", server.port))
        client.sendall(f"POST /api/readaloud/clip HTTP/1.1\r\nHost: 127.0.0.1:{server.port}\r\nX-Ebook-Token: t\r\nContent-Type: application/json\r\n"
                       f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body)
        assert local.started.wait(10)
        time.sleep(0.1)
        closed = time.monotonic()
        client.close()  # trình phát bỏ đoạn này (nhảy đi nơi khác)
        deadline = time.monotonic() + 3
        while local.stopped_at is None and time.monotonic() < deadline:
            time.sleep(0.01)
        assert local.stopped_at is not None, "lượt đọc phải dừng"
        assert local.stopped_at - closed <= 0.3, local.stopped_at - closed
        assert local.done_chunks < 100
        assert not list((tmp_path / "prefs" / "readaloud-cache").glob("*.mp3"))
    finally:
        server.stop()


def test_cancelling_an_export_stops_a_long_local_read_within_half_a_second(tmp_path: Path) -> None:
    from abook.webui import export_jobs, listen_export
    from tests.test_listen_export import _library, tmp_work

    if not listen_export.ffmpeg_available():
        pytest.skip("cần ffmpeg")
    app, book_id, path, _fake = _library(tmp_path)
    local = LocalVoice(chunks=1000, step=0.01)  # đoạn ~1000 ký tự: chục giây nếu đọc nốt
    app.readaloud = ReadAloud(tmp_path / "cache_local", [local])
    stop = threading.Event()
    outcome: dict[str, Any] = {}

    def export() -> None:
        try:
            listen_export.export_audiobook(app.readaloud, path, tmp_path / "xuat", tmp_work(tmp_path / "xuat"), fmt="m4b", book_id=book_id,
                                           reading=listen_export.Reading("local:a", None, {}), cancelled=stop.is_set)
        except BaseException as error:  # noqa: BLE001 - bài thử ghi lại để kiểm
            outcome["error"] = error
        outcome["at"] = time.monotonic()

    worker = threading.Thread(target=export)
    worker.start()
    assert local.started.wait(20)
    time.sleep(0.2)
    asked = time.monotonic()
    stop.set()
    worker.join(10)
    assert isinstance(outcome.get("error"), export_jobs.Cancelled), outcome
    assert outcome["at"] - asked <= 0.5, outcome["at"] - asked
    assert not list((tmp_path / "cache_local").glob("*.mp3"))
