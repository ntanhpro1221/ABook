"""Bản tăng tốc của giọng VieNeu (readaloud/vieneu_gguf.py + phần "gguf" của webui/vieneu_module.py): chọn engine theo máy / theo phần đã tải / theo công tắc,
WAV stereo thành mono, server giả (lên một lần, chết giữa chừng thì khởi lại một lần, chết hẳn thì rơi về ONNX), tắt khi rảnh / khi thoát / khi app chết,
file giọng sinh từ giọng có sẵn, đường tải. Server là một script Python giả tiếng `audiocpp_server` (không cần file thật); bài so byte với file của audio.cpp và bài
chạy server thật chỉ chạy khi máy có sẵn các file ấy (máy dev, thư mục đo của lượt 10-10), như bài so với gói vieneu.
"""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import textwrap
import time
import wave
import zipfile
from pathlib import Path

import numpy as np
import pytest

from abook.readaloud import vieneu, vieneu_gguf
from abook.readaloud.vieneu_gguf import AcceleratedEngine, GgufEngine, GgufError, GgufFiles
from abook.webui import music_module, studio_setup, vieneu_module, word_timing

FAKE_SERVER = '''
import json, struct, sys, time, wave, io, os
from http.server import BaseHTTPRequestHandler, HTTPServer
port, mode, counter = int(sys.argv[1]), sys.argv[2], sys.argv[3]
if mode == "crash-at-start":
    sys.exit(3)
def bump():
    n = int(open(counter).read() or 0) + 1 if os.path.exists(counter) else 1
    open(counter, "w").write(str(n)); return n
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"ok")
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        n = bump()
        if mode == "die-on-second" and n == 2:
            os._exit(7)
        if mode == "always-die":
            os._exit(7)
        if mode == "junk":
            self.send_response(200); self.end_headers(); self.wfile.write(b"not a wav"); return
        left = [8000 * (1 if i % 2 else -1) for i in range(480)]
        right = [int(v * 0.5) for v in left]
        out = io.BytesIO()
        with wave.open(out, "wb") as w:
            w.setnchannels(2); w.setsampwidth(2); w.setframerate(48000)
            w.writeframes(b"".join(struct.pack("<hh", a, b) for a, b in zip(left, right)))
        data = out.getvalue()
        with open(counter + ".seed", "w") as f:  # trước khi trả lời: bài thử đọc file này ngay khi nhận WAV
            f.write(json.dumps({"seed": body["seed"], "input": body["input"], "options": body["options"]}))
        self.send_response(200); self.send_header("Content-Type", "audio/wav"); self.send_header("Content-Length", str(len(data))); self.end_headers()
        self.wfile.write(data)
HTTPServer(("127.0.0.1", port), H).serve_forever()
'''


@pytest.fixture
def fake(tmp_path: Path):
    script = tmp_path / "fake_server.py"
    script.write_bytes(textwrap.dedent(FAKE_SERVER).encode())
    counter = tmp_path / "count.txt"
    files = GgufFiles(tmp_path / "audiocpp_server.exe", tmp_path / "model.gguf", tmp_path / "work")
    modes = {"mode": "normal"}

    def command(_files: GgufFiles, port: int, _threads: int) -> list[str]:
        return [sys.executable, str(script), str(port), modes["mode"], str(counter)]

    def engine(mode: str = "normal", **kwargs) -> GgufEngine:
        modes["mode"] = mode
        return GgufEngine(files, command=command, threads=1, **kwargs)

    vieneu_gguf.reset_failure()
    yield engine, files, counter, tmp_path
    vieneu_gguf.shutdown()
    vieneu_gguf.reset_failure()


def _alive(pid: int) -> bool:
    import psutil

    return psutil.pid_exists(pid) and psutil.Process(pid).status() != psutil.STATUS_ZOMBIE


def _voice(files: GgufFiles) -> Path:
    return vieneu_gguf.voice_dir(files, np.linspace(-1, 1, 192, dtype=np.float32), np.arange(48, dtype=np.int64).reshape(3, 16))


# ---- WAV, file giọng ---------------------------------------------------------------------------------------------------------------
def _wav(channels: int, rate: int = 48_000, width: int = 2) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(channels)
        handle.setsampwidth(width)
        handle.setframerate(rate)
        handle.writeframes(np.tile(np.array([[1000, -3000]], dtype="<i2")[:, :channels], (10, 1)).tobytes() if width == 2 else b"\0" * (10 * channels * width))
    return buffer.getvalue()


def test_a_stereo_wav_becomes_mono_float() -> None:
    mono = vieneu_gguf.mono_samples(_wav(2))
    assert mono.dtype == np.float32 and mono.shape == (10,)
    assert np.allclose(mono, (1000 - 3000) / 2 / 32768)
    assert vieneu_gguf.mono_samples(_wav(1)).shape == (10,)
    for bad in (b"junk", _wav(2, rate=24_000), _wav(2, width=1)):
        with pytest.raises(GgufError):
            vieneu_gguf.mono_samples(bad)


def test_voice_files_are_made_once_from_the_preset(tmp_path: Path) -> None:
    files = GgufFiles(tmp_path / "s.exe", tmp_path / "m.gguf", tmp_path / "work")
    first = _voice(files)
    assert (first / "ref_codes.txt").read_bytes().startswith(b"0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15\n16 17")
    emb = (first / "speaker.emb.txt").read_bytes().decode()
    assert emb.startswith("-1.00000000,") and emb.count(",") == 191 and not emb.endswith("\n")
    stamp = (first / "ref_codes.txt").stat().st_mtime_ns
    assert _voice(files) == first and (first / "ref_codes.txt").stat().st_mtime_ns == stamp, "giọng đã có thì không ghi lại"
    other = vieneu_gguf.voice_dir(files, np.zeros(192, dtype=np.float32), np.zeros((2, 16), dtype=np.int64))
    assert other != first and b"\r" not in (first / "ref_codes.txt").read_bytes()


HERE = Path(r"C:/Users/NGDtuanh/AppData/Local/Temp/claude/D--Novels-ABook/eba3e3d6-08dd-4ad9-8ba0-dc9003c54c4a/scratchpad")
HF_VOICES = HERE / "vieneu_gguf" / "dl" / "model" / "voices"
PRESETS = HERE / "vieneu383" / ".venv" / "Lib" / "site-packages" / "vieneu" / "assets" / "voices_v3_turbo.json"


@pytest.mark.skipif(not (HF_VOICES.is_dir() and PRESETS.is_file()), reason="máy không có file giọng của audio.cpp để so")
def test_voice_files_equal_the_ones_audiocpp_ships(tmp_path: Path) -> None:
    presets = json.loads(PRESETS.read_bytes().decode("utf-8"))["presets"]
    shipped = {"duc_tri": "Đức Trí", "kim_thanh": "Kim Thanh", "my_duyen": "Mỹ Duyên", "truc_ly": "Trúc Ly"}
    files = GgufFiles(tmp_path / "s.exe", tmp_path / "m.gguf", tmp_path / "work")
    for folder, name in shipped.items():
        preset = presets[name]
        mine = vieneu_gguf.voice_dir(files, np.asarray(preset["speaker_emb"], dtype=np.float32), preset["codes"])
        for file in ("ref_codes.txt", "speaker.emb.txt"):
            # bản chép ở máy này ghi bằng Python văn bản nên xuống dòng CRLF; nội dung (số, dấu cách, dấu phẩy) phải trùng từng byte
            assert (mine / file).read_bytes() == (HF_VOICES / folder / file).read_bytes().replace(b"\r\n", b"\n"), (name, file)


# ---- server giả ---------------------------------------------------------------------------------------------------------------------
def test_one_server_serves_many_chunks_and_gets_the_seed_and_voice(fake) -> None:
    engine_for, files, counter, _tmp = fake
    engine = engine_for()
    voice = _voice(files)
    first = engine.speak("a b", voice, 123)
    second = engine.speak("c d", voice, 456)
    assert engine.starts == 1 and engine.running()
    assert first.dtype == np.float32 and first.shape == (480,) and np.isclose(first[1], 8000 * 0.75 / 32768, atol=1e-3), "hai kênh -> trung bình"
    sent = json.loads(Path(str(counter) + ".seed").read_bytes())
    assert sent["seed"] == 456 and sent["input"] == "c d" and sent["options"]["reference_codes_file"] == str(voice / "ref_codes.txt")
    assert second.shape == (480,)


def test_a_server_that_dies_in_the_middle_is_started_again_once(fake) -> None:
    engine_for, files, _counter, _tmp = fake
    engine = engine_for("die-on-second")
    voice = _voice(files)
    engine.speak("a", voice, 1)
    # yêu cầu thứ hai làm server chết (os._exit trong tiến trình giả); đếm theo file nên server mới sống tiếp ở yêu cầu thứ ba
    audio = engine.speak("b", voice, 2)
    assert audio.shape == (480,) and engine.starts == 2


def test_a_server_that_never_starts_or_keeps_dying_raises(fake) -> None:
    engine_for, files, _counter, _tmp = fake
    voice = _voice(files)
    with pytest.raises(GgufError, match="thoát ngay"):
        engine_for("crash-at-start").speak("a", voice, 1)
    dying = engine_for("always-die")
    with pytest.raises(GgufError):
        dying.speak("a", voice, 1)
    assert dying.starts == 2, "khởi lại đúng một lần rồi bỏ"
    with pytest.raises(GgufError, match="WAV"):
        engine_for("junk").speak("a", voice, 1)


class FakeOnnx:
    SAMPLE_RATE = 48_000

    def __init__(self) -> None:
        self.calls = 0

    def infer(self, phonemes, speaker, codes, *, rng, **_options):
        self.calls += 1
        return np.full(100, 0.25, dtype=np.float32)


def _accelerated(engine_factory, files: GgufFiles, onnx: FakeOnnx, mode: str):
    engine = engine_factory(mode)
    return AcceleratedEngine(lambda: onnx, lambda: files, engine_of=lambda _files: engine), engine


def test_it_reads_with_the_fast_engine_and_falls_back_to_onnx_for_the_session(fake) -> None:
    engine_for, files, _counter, _tmp = fake
    onnx = FakeOnnx()
    speaker, codes = np.zeros(192, dtype=np.float32), np.zeros((2, 16), dtype=np.int64)
    good, _server = _accelerated(engine_for, files, onnx, "normal")
    audio = good.infer("a", speaker, codes, rng=np.random.RandomState(5))
    assert audio.shape == (480,) and onnx.calls == 0 and good.SAMPLE_RATE == 48_000
    assert good._onnx is None, "ONNX không nạp khi bản tăng tốc chạy suôn sẻ"
    vieneu_gguf.shutdown()
    bad, server = _accelerated(engine_for, files, onnx, "always-die")
    audio = bad.infer("a", speaker, codes, rng=np.random.RandomState(5))
    assert np.allclose(audio, 0.25) and onnx.calls == 1 and vieneu_gguf.failure()
    starts = server.starts
    bad.infer("b", speaker, codes, rng=np.random.RandomState(6))
    assert onnx.calls == 2 and server.starts == starts, "đã hỏng thì cả phiên đọc bằng ONNX, không thử lại từng khúc"
    vieneu_gguf.reset_failure()


def test_a_voice_without_reference_codes_goes_to_onnx(fake) -> None:
    engine_for, files, _counter, _tmp = fake
    onnx = FakeOnnx()
    engine, server = _accelerated(engine_for, files, onnx, "normal")
    engine.infer("a", np.zeros(192, dtype=np.float32), None, rng=np.random.RandomState(1))
    assert onnx.calls == 1 and server.starts == 0


def test_the_same_chunk_seed_gives_the_same_server_seed(fake) -> None:
    engine_for, files, counter, _tmp = fake
    onnx = FakeOnnx()
    engine, _server = _accelerated(engine_for, files, onnx, "normal")
    speaker, codes = np.zeros(192, dtype=np.float32), np.zeros((2, 16), dtype=np.int64)
    seeds = []
    for seed in (77, 77, 78):
        engine.infer("a", speaker, codes, rng=np.random.RandomState(seed))
        seeds.append(json.loads(Path(str(counter) + ".seed").read_bytes())["seed"])
    assert seeds[0] == seeds[1] != seeds[2]


def test_an_idle_server_stops_by_itself_and_the_next_chunk_starts_it_again(fake) -> None:
    engine_for, files, _counter, _tmp = fake
    engine = engine_for(idle_seconds=0.4)
    voice = _voice(files)
    engine.speak("a", voice, 1)
    pid = engine._process.pid
    deadline = time.monotonic() + 10
    while engine.running() and time.monotonic() < deadline:
        time.sleep(0.1)
    assert not engine.running() and not _alive(pid)
    engine.speak("b", voice, 2)
    assert engine.starts == 2


def test_shutdown_stops_every_server(fake) -> None:
    engine_for, files, _counter, _tmp = fake
    engine = engine_for()
    engine.speak("a", _voice(files), 1)
    pid = engine._process.pid
    with vieneu_gguf._engines_lock:
        vieneu_gguf._engines[str(files.server)] = engine
    vieneu_gguf.shutdown()
    assert not engine.running() and not _alive(pid)


CHILD = '''
import os, sys
sys.path.insert(0, {root!r})
from pathlib import Path
from abook.readaloud import vieneu_gguf
from abook.readaloud.vieneu_gguf import GgufEngine, GgufFiles
tmp = Path({tmp!r})
files = GgufFiles(tmp / "x.exe", tmp / "m.gguf", tmp / "work")
engine = GgufEngine(files, threads=1, command=lambda f, port, t: [sys.executable, {script!r}, str(port), "normal", {counter!r}])
voice = vieneu_gguf.voice_dir(files, [0.0] * 192, [[0] * 16])
engine.speak("a", voice, 1)
vieneu_gguf._engines[str(files.server)] = engine
print(engine._process.pid, flush=True)
if sys.argv[1] == "hard":
    os._exit(0)  # atexit không chạy: chỉ Job Object cứu được
'''


@pytest.mark.parametrize("how", ["normal", pytest.param("hard", marks=pytest.mark.skipif(sys.platform != "win32", reason="Job Object chỉ có trên Windows"))])
def test_the_server_dies_with_the_app(fake, how: str) -> None:
    _engine_for, _files, counter, tmp = fake
    root = str(Path(vieneu_gguf.__file__).resolve().parents[2])
    (tmp / "child.py").write_bytes(CHILD.format(root=root, tmp=str(tmp), script=str(tmp / "fake_server.py"), counter=str(counter)).encode())
    done = subprocess.run([sys.executable, str(tmp / "child.py"), how], capture_output=True, timeout=60, text=True)
    assert done.returncode == 0, done.stderr
    pid = int(done.stdout.split()[0])
    deadline = time.monotonic() + 10
    while _alive(pid) and time.monotonic() < deadline:
        time.sleep(0.1)
    assert not _alive(pid), "server vẫn sống sau khi app thoát"


# ---- chọn engine theo máy / theo phần đã tải ----------------------------------------------------------------------------------------
@pytest.fixture
def module(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    for variable in (vieneu_module.ENV_DOWNLOAD, music_module.ENV_DOWNLOAD):
        monkeypatch.setenv(variable, "1")
    monkeypatch.setattr(sys, "path", sys.path.copy())
    monkeypatch.setattr(vieneu_module, "_g2p_external", lambda: False)
    monkeypatch.setattr(music_module, "_libs_external", lambda: True)
    monkeypatch.setattr(vieneu_module, "_facts", {"cores": 16, "ramGb": 16.0, "gpu": "", "runs": "cpu"})
    monkeypatch.setattr(vieneu_gguf, "unsupported_reason", lambda: "")
    monkeypatch.setattr(word_timing, "_more", [])
    monkeypatch.setattr(word_timing, "_studio", None)
    monkeypatch.setattr(word_timing, "model_dir", lambda: None)
    music_module.configure(tmp_path / "music")
    stopped: list[int] = []
    monkeypatch.setattr(vieneu_gguf, "shutdown", lambda: stopped.append(1))
    vieneu_module.configure(tmp_path / "vieneu")
    yield tmp_path / "vieneu", stopped
    vieneu_module.configure(None)
    music_module.configure(None)


def _place_gguf(folder: Path) -> None:
    (folder / "gguf" / "server").mkdir(parents=True)
    (folder / "gguf" / "server" / vieneu_gguf.SERVER_EXE).write_bytes(b"x")
    (folder / "gguf" / vieneu_gguf.MODEL_FILE).write_bytes(b"y")


def test_the_fast_files_are_used_only_when_loaded_wanted_and_not_broken(module, monkeypatch: pytest.MonkeyPatch) -> None:
    folder, _stopped = module
    assert vieneu_module.gguf_files() is None, "chưa tải"
    _place_gguf(folder)
    files = vieneu_module.gguf_files()
    assert files is not None and files.server == folder / "gguf" / "server" / vieneu_gguf.SERVER_EXE and files.model.name == vieneu_gguf.MODEL_FILE
    monkeypatch.setattr(vieneu_gguf, "unsupported_reason", lambda: "CPU không có AVX2")
    assert vieneu_module.gguf_files() is None and not vieneu_module.fast_supported(), "máy không có AVX2: ONNX"
    monkeypatch.setattr(vieneu_gguf, "unsupported_reason", lambda: "")
    vieneu_module._set_broken("server thoát ngay")
    assert vieneu_module.gguf_files() is None and vieneu_module.accelerated()["problem"] == "server thoát ngay"
    vieneu_module._set_broken("")
    assert vieneu_module.gguf_files() is not None
    vieneu_module.set_accelerate(False)
    assert vieneu_module.gguf_files() is None and vieneu_module.accelerated()["on"] is False
    vieneu_module.set_accelerate(True)
    assert vieneu_module.gguf_files() is not None


def test_a_new_pin_forgets_an_old_broken_mark(module, monkeypatch: pytest.MonkeyPatch) -> None:
    folder, _stopped = module
    _place_gguf(folder)
    vieneu_module._set_broken("hỏng")
    assert vieneu_module.gguf_files() is None
    monkeypatch.setattr(vieneu_module, "GGUF_FILES", tuple(studio_setup.Download(i.name, i.url, "0" * 64, i.size) for i in vieneu_module.GGUF_FILES))
    assert vieneu_module.gguf_files() is not None, "bản server mới thì thử lại"


def test_make_engine_wraps_turbo_only_on_machines_that_can_run_it(module, monkeypatch: pytest.MonkeyPatch) -> None:
    plain = object()
    monkeypatch.setattr(vieneu, "_real_engine", lambda tier, found: plain)
    found = vieneu.Installed(Path("v"), (Path("t"), Path("t")), Path("n"), False)
    wrapped = vieneu_module.make_engine("turbo", found)
    assert isinstance(wrapped, AcceleratedEngine) and wrapped.onnx() is plain
    assert vieneu_module.make_engine("nano", found) is plain, "Nano không có bản tăng tốc"
    monkeypatch.setattr(vieneu_gguf, "unsupported_reason", lambda: "CPU không có AVX2")
    assert vieneu_module.make_engine("turbo", found) is plain


def test_the_unsupported_reason_follows_the_machine(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    assert "Windows" in vieneu_gguf.unsupported_reason()
    if os.name == "nt":
        monkeypatch.setattr(sys, "platform", "win32")
        import ctypes

        class Kernel:
            def __init__(self, avx2: bool) -> None:
                self.avx2 = avx2

            def IsProcessorFeaturePresent(self, feature: int) -> int:  # noqa: N802
                assert feature == vieneu_gguf.AVX2_FEATURE
                return int(self.avx2)

        for avx2, reason in ((True, ""), (False, "AVX2")):
            monkeypatch.setattr(ctypes, "windll", type("W", (), {"kernel32": Kernel(avx2)})(), raising=False)
            monkeypatch.setenv("PROCESSOR_ARCHITECTURE", "AMD64")
            assert reason in vieneu_gguf.unsupported_reason()
        monkeypatch.setenv("PROCESSOR_ARCHITECTURE", "ARM64")
        monkeypatch.delenv("PROCESSOR_ARCHITEW6432", raising=False)
        assert "x64" in vieneu_gguf.unsupported_reason()


# ---- đường tải + trạng thái ----------------------------------------------------------------------------------------------------------
class Network:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def download(self, item, target: Path, progress, cancelled) -> Path:
        self.calls.append(item.name)
        target.parent.mkdir(parents=True, exist_ok=True)
        if item.name == "sea-g2p":
            with zipfile.ZipFile(target, "w") as bundle:
                bundle.writestr("sea_g2p/__init__.py", "")
        elif item.name == "vieneu":
            with zipfile.ZipFile(target, "w") as bundle:
                for member in vieneu_module.VOICE_MEMBERS:
                    bundle.writestr(member, json.dumps({"presets": {"A": {"speaker_emb": [0.1]}}}))
        elif item.name == vieneu_module.SERVER_ZIP.name:
            with zipfile.ZipFile(target, "w") as bundle:
                bundle.writestr(vieneu_gguf.SERVER_EXE, "MZ")
                bundle.writestr("third_party/ggml-LICENSE.txt", "MIT")
        else:
            target.write_bytes(item.sha256.encode())
        progress(item.size, item.size)
        return target


def test_the_pinned_server_and_model_match_what_was_measured() -> None:
    assert vieneu_module.SERVER_ZIP.sha256 == "533b667e01103617f746b30a31c716fa8e98c3d8a0c7ff53fd1df1795e236c86" and vieneu_module.SERVER_ZIP.size == 11_582_285
    assert "2374dab847a5a1356948a7e6b741997de25ebbbd" in vieneu_module.SERVER_ZIP.url
    assert vieneu_module.GGUF_MODEL.sha256 == "a60569e5d7dd6f24cbb7bb2e7c472bb988ad19563a4e78f0cc67cc53fd189bb4" and vieneu_module.GGUF_MODEL.size == 187_917_664
    assert "61b85e3d937fbbacb387714180e8182823512523/gguf/vieneu-v3-turbo-q8_0.gguf" in vieneu_module.GGUF_MODEL.url
    assert 195_000_000 < sum(item.size for item in vieneu_module.GGUF_FILES) < 205_000_000


def test_the_fast_choice_shows_its_own_size_downloads_both_files_and_measures_turbo(module, monkeypatch: pytest.MonkeyPatch) -> None:
    folder, stopped = module
    network = Network()
    monkeypatch.setattr(studio_setup, "download", network.download)
    measured: list[str] = []

    def bench(tier: str) -> dict:
        measured.append(tier)
        return {"rtf": 0.14, "firstAudioMs": 700, "loadMs": 600, "audioSeconds": 5.0}

    vieneu_module.configure(folder, benchmark=bench)
    status = vieneu_module.status()
    by_id = {choice["id"]: choice for choice in status["choices"]}
    gguf = sum(item.size for item in vieneu_module.GGUF_FILES)
    assert by_id["fast"]["bytes"] == gguf, "cỡ riêng của bản tăng tốc; Giọng VieNeu có dòng của nó"
    assert by_id["fast"]["requires"] == ["turbo"] and by_id["fast"]["recommended"] and by_id["fast"]["default"]
    assert status["accelerated"] is None
    vieneu_module.start(["turbo", "fast"])
    vieneu_module.join(10)
    status = vieneu_module.status()
    assert status["state"] == "ready", status
    assert network.calls.count(vieneu_module.SERVER_ZIP.name) == 1 and network.calls.count(vieneu_module.GGUF_MODEL.name) == 1
    assert (folder / "gguf" / "server" / vieneu_gguf.SERVER_EXE).is_file() and (folder / "gguf" / "server" / "third_party" / "ggml-LICENSE.txt").is_file()
    assert (folder / "gguf" / vieneu_gguf.MODEL_FILE).is_file() and not (folder / "gguf" / "server.part").exists()
    assert not (folder / "dl").exists(), "gói zip đã giải thì xoá"
    assert stopped, "server cũ tắt trước khi thay file"
    assert "turbo" in measured, "lần đo của Turbo chạy bằng bản tăng tốc"
    assert status["accelerated"] == {"on": True, "active": True, "problem": ""}
    stamp = json.loads((folder / "module.json").read_bytes())
    assert stamp["pins"]["gguf"] == vieneu_module.pin(vieneu_module.GGUF_FILES)
    assert {choice["id"]: choice["bytes"] for choice in status["choices"]}["fast"] == 0
    # chỉ bản tăng tốc đổi ghim -> chỉ tải lại nó, và đo lại Turbo
    network.calls.clear()
    measured.clear()
    changed = tuple(studio_setup.Download(i.name, i.url, "0" * 64 if i.name == vieneu_module.SERVER_ZIP.name else i.sha256, i.size) for i in vieneu_module.GGUF_FILES)
    monkeypatch.setattr(vieneu_module, "GGUF_FILES", changed)
    monkeypatch.setattr(vieneu_module, "SERVER_ZIP", changed[0])
    monkeypatch.setitem(vieneu_module.FILES, "gguf", changed)
    status = vieneu_module.status()
    assert status["state"] == "outdated" and status["outdatedParts"] == ["Bản tăng tốc"]
    vieneu_module.start(None)
    vieneu_module.join(10)
    assert sorted(set(network.calls)) == sorted(item.name for item in changed) and measured == ["turbo"]


def test_a_failed_trial_marks_the_machine_and_the_next_trial_tries_again(module, monkeypatch: pytest.MonkeyPatch) -> None:
    folder, _stopped = module
    _place_gguf(folder)
    attempts: list[str] = []

    def bench(tier: str) -> dict:
        attempts.append(tier)
        if len(attempts) == 1:
            vieneu_gguf._fail("server thoát ngay khi khởi động (mã 3)")  # như AcceleratedEngine khi server không lên
        return {"rtf": 0.5, "firstAudioMs": 1, "loadMs": 1, "audioSeconds": 5.0}

    vieneu_module.configure(folder, benchmark=bench)
    vieneu_module._core._bench("turbo")
    state = vieneu_module.accelerated()
    assert state["problem"].startswith("server thoát") and not state["active"] and vieneu_module.gguf_files() is None
    assert json.loads((folder / "module.json").read_bytes())["gguf"]["broken"].startswith("server thoát"), "ghi lại: lần sau khỏi thử"
    vieneu_module._core._bench("turbo")  # "Thử lại tốc độ"
    assert vieneu_module.accelerated()["problem"] == "" and vieneu_module.gguf_files() is not None
    vieneu_module._core._bench("nano")
    assert attempts == ["turbo", "turbo", "nano"]
    vieneu_gguf.reset_failure()


def test_the_fast_choice_is_hidden_when_the_machine_cannot_run_it(module, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(vieneu_gguf, "unsupported_reason", lambda: "CPU của máy này không có lệnh AVX2")
    assert "fast" not in {choice["id"] for choice in vieneu_module.status()["choices"]}
    with pytest.raises(ValueError):
        vieneu_module.start(["fast"])


def test_the_accelerated_engine_loads_without_numpy_and_keeps_the_turbo_rate() -> None:
    """webui nạp vieneu_gguf lúc khởi động, trước khi máy có numpy (Python nhúng của bộ cài): không được nạp vieneu_engine ở đầu file."""
    import ast

    from abook.readaloud import vieneu_engine, vieneu_gguf

    tree = ast.parse(Path(vieneu_gguf.__file__).read_text(encoding="utf-8"))
    top = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))]
    names = {alias.name for node in top for alias in node.names} | {node.module or "" for node in top if isinstance(node, ast.ImportFrom)}
    assert not names & {"numpy", "vieneu_engine"}, names
    assert vieneu_gguf.SAMPLE_RATE == vieneu_engine.TURBO_RATE
