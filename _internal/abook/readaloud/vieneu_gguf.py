"""Bản tăng tốc của giọng VieNeu Turbo cho "Nghe ngay" trên máy tính: cùng model, chạy bằng audio.cpp (GGUF q8_0, ggml) thay vì onnxruntime.
Đo 10-10 trên Ryzen 9 8945HX (6 luồng): đọc nhanh gấp ~2 lần (RTF ấm 0,14 so với 0,27), RAM đỉnh 1,0-1,6 GB so với 1,5-3,7 GB; CER và UTMOS
của 6 giọng không khác ONNX có ý nghĩa (khoảng tin cậy chứa 0). Không trùng byte với ONNX: đổi engine là audio khác, đúng với Nghe ngay (không có
bằng chứng QA theo hạt giống như Studio). Studio (tts.py) không dùng bản này.

Cách chạy: một tiến trình `audiocpp_server` (bản AVX2 tự build, ghim ở vieneu_module) ở 127.0.0.1, cổng ngẫu nhiên, ẩn cửa sổ, nạp model một lần
(0,6 giây), mỗi khúc một yêu cầu `POST /v1/audio/speech` (giọng + hạt giống theo yêu cầu). Đầu vào PHẢI là phoneme (chữ thường vào server ra
rác mà không báo lỗi): phoneme do `vieneu_engine.phonemize` đã làm. Server khởi lười ở khúc đầu, tắt khi rảnh (`IDLE_SECONDS`), khi app thoát
(atexit) và khi app chết (Job Object: Windows tự giết tiến trình con).

`AcceleratedEngine` đứng thay `ve.TurboEngine` trong `VieneuProvider` (cùng `SAMPLE_RATE`, cùng `infer`) nên readaloud/vieneu.py không đổi: bản tăng tốc
chạy được thì dùng, không thì chính engine ONNX (nạp lười, lần đầu cần mới nạp) đọc khúc ấy. Server chết giữa chừng -> khởi lại một lần; lại chết ->
ghi log và đọc bằng ONNX cho tới hết phiên, người nghe không thấy lỗi.
"""
from __future__ import annotations

import atexit
import ctypes
import hashlib
import http.client
import io
import json
import logging
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

# KHÔNG nạp vieneu_engine (numpy) ở đầu file: mô-đun này được webui nạp lúc khởi động, mà numpy chỉ có sau khi tải thư viện chung
# (Python nhúng của bộ cài không có - smoke_embedded_python bắt lỗi này).

log = logging.getLogger(__name__)

SERVER_EXE = "audiocpp_server.exe"
MODEL_FILE = "vieneu-v3-turbo-q8_0.gguf"
SAMPLE_RATE = 48_000  # = vieneu_engine.TURBO_RATE (bài thử giữ hai số khớp nhau)
IDLE_SECONDS = 300.0  # server rảnh chừng này thì tắt (lấy lại ~1,1 GB RAM); khúc kế khởi lại trong ~0,6 giây
START_TIMEOUT = 60.0
REQUEST_TIMEOUT = 300.0
THREADS = 6  # đã đo ở 6 luồng; máy ít luồng hơn thì theo máy
AVX2_FEATURE = 40  # IsProcessorFeaturePresent: PF_AVX2_INSTRUCTIONS_AVAILABLE (bản server build nhắm AVX2 + FMA + F16C, không AVX-512)
CREATE_NO_WINDOW = 0x08000000  # không DETACHED_PROCESS: cờ ấy vô hiệu CREATE_NO_WINDOW (cửa sổ nháy)


class GgufError(Exception):
    """Bản tăng tốc không đọc được khúc này (server không lên, chết, trả không phải WAV)."""


@dataclass(frozen=True)
class GgufFiles:
    """Những gì phần "Bản tăng tốc" đã đặt trên máy: file chạy server, model GGUF, thư mục làm việc (cấu hình, nhật ký, file giọng sinh từ giọng có sẵn)."""

    server: Path
    model: Path
    work: Path


def unsupported_reason() -> str:
    """Rỗng khi máy chạy được bản tăng tốc (Windows 64-bit, CPU có AVX2); không thì lý do bằng tiếng Việt cho người dùng."""
    if sys.platform != "win32":
        return "bản tăng tốc chỉ có cho Windows"
    if os.environ.get("PROCESSOR_ARCHITECTURE", "").upper() not in ("AMD64", "X86_64") and os.environ.get("PROCESSOR_ARCHITEW6432", "").upper() != "AMD64":
        return "bản tăng tốc chỉ có cho máy x64"
    try:
        present = bool(ctypes.windll.kernel32.IsProcessorFeaturePresent(AVX2_FEATURE))
    except (OSError, AttributeError):
        present = False
    return "" if present else "CPU của máy này không có lệnh AVX2"


# ---- file giọng -------------------------------------------------------------------------------------------------------------------
def voice_texts(speaker_emb: Any, ref_codes: Any) -> tuple[str, str]:
    """(nội dung `ref_codes.txt`, nội dung `speaker.emb.txt`) của một giọng có sẵn - đúng byte của file audio.cpp tự đóng gói (kiểm với HF
    pnnbao-ump/VieNeu-TTS-v3-Turbo @61b85e3d gguf/voices): mỗi hàng một frame 16 mã; vector người nói 192 số %.8f (qua float32) cách nhau dấu phẩy."""
    import numpy as np

    codes = np.asarray(ref_codes, dtype=np.int64)
    rows = "".join(" ".join(str(int(code)) for code in row) + "\n" for row in codes.reshape(-1, codes.shape[-1]))
    emb = ",".join("%.8f" % float(value) for value in np.asarray(speaker_emb, dtype=np.float32).reshape(-1))
    return rows, emb


def voice_dir(files: GgufFiles, speaker_emb: Any, ref_codes: Any) -> Path:
    """Thư mục chứa file giọng của giọng này, tạo nếu chưa có. Tên thư mục là băm của nội dung (giọng có sẵn đổi thì ra thư mục mới), nên không cần tên
    giọng - tên có dấu tiếng Việt cũng không phải qua đường dẫn."""
    codes, emb = voice_texts(speaker_emb, ref_codes)
    folder = files.work / "voices" / hashlib.sha1((codes + "|" + emb).encode("ascii")).hexdigest()[:16]
    if not ((folder / "ref_codes.txt").is_file() and (folder / "speaker.emb.txt").is_file()):
        folder.mkdir(parents=True, exist_ok=True)
        for name, text in (("ref_codes.txt", codes), ("speaker.emb.txt", emb)):
            part = folder / (name + ".part")
            part.write_bytes(text.encode("ascii"))  # LF, không phụ thuộc hệ điều hành
            os.replace(part, folder / name)
    return folder


# ---- tiến trình con chết theo cha -------------------------------------------------------------------------------------------------
_job: Any = None
_job_lock = threading.Lock()


def _kill_on_close_job() -> Any:
    """Job Object của app (tạo một lần): tiến trình con gán vào nó chết khi app chết, kể cả chết đột ngột (atexit không chạy). None khi không dùng được."""
    global _job
    with _job_lock:
        if _job is not None:
            return _job or None
        _job = False
        if sys.platform != "win32":
            return None
        try:
            from ctypes import wintypes

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

            class Basic(ctypes.Structure):
                _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64), ("LimitFlags", wintypes.DWORD),
                            ("MinimumWorkingSetSize", ctypes.c_size_t), ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                            ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD), ("SchedulingClass", wintypes.DWORD)]

            class Counters(ctypes.Structure):
                _fields_ = [(name, ctypes.c_uint64) for name in ("ReadOps", "WriteOps", "OtherOps", "ReadBytes", "WriteBytes", "OtherBytes")]

            class Extended(ctypes.Structure):
                _fields_ = [("Basic", Basic), ("Io", Counters), ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                            ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]

            kernel32.CreateJobObjectW.restype = wintypes.HANDLE
            kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
            kernel32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
            handle = kernel32.CreateJobObjectW(None, None)
            info = Extended()
            info.Basic.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            if not handle or not kernel32.SetInformationJobObject(handle, 9, ctypes.byref(info), ctypes.sizeof(info)):  # 9 = JobObjectExtendedLimitInformation
                return None
            _job = (kernel32, handle)
        except (OSError, AttributeError, ValueError) as error:
            log.warning("Job Object không dùng được (%s): server bản tăng tốc chỉ tắt theo atexit", error)
        return _job or None


def _bind_to_app(process: subprocess.Popen) -> None:
    job = _kill_on_close_job()
    if job is None:
        return
    kernel32, handle = job
    try:
        from ctypes import wintypes

        kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        if not kernel32.AssignProcessToJobObject(handle, int(process._handle)):  # noqa: SLF001 - Popen không có cách công khai lấy handle
            log.warning("không gán được server bản tăng tốc vào Job Object (lỗi %s)", ctypes.get_last_error())
    except (OSError, AttributeError, ValueError, TypeError) as error:
        log.warning("không gán được server bản tăng tốc vào Job Object (%s)", error)


# ---- server -----------------------------------------------------------------------------------------------------------------------
def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def server_command(files: GgufFiles, port: int, threads: int) -> list[str]:
    """Dòng lệnh khởi server: chỉ nghe 127.0.0.1, tắt giao diện web của nó, model nạp ngay (không lười) để khúc đầu không trả thêm thời gian nạp."""
    config = files.work / "server.json"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_bytes(json.dumps({
        "host": "127.0.0.1", "port": port, "backend": "cpu", "threads": threads, "lazy_load": False,
        "models": [{"id": "vieneu", "family": "vieneu_v3_turbo", "path": str(files.model).replace("\\", "/"), "task": "tts", "mode": "offline"}],
    }, ensure_ascii=False, indent=1).encode("utf-8"))
    return [str(files.server), "--config", str(config), "--no-ui"]


def mono_samples(wav_bytes: bytes) -> Any:
    """WAV PCM 16-bit của server (stereo 48 kHz, hai kênh gần y hệt) -> mono float32 [-1, 1], tần số mẫu `SAMPLE_RATE`."""
    import numpy as np

    try:
        with wave.open(io.BytesIO(wav_bytes)) as reader:
            channels, width, rate, frames = reader.getnchannels(), reader.getsampwidth(), reader.getframerate(), reader.readframes(reader.getnframes())
    except (wave.Error, EOFError) as error:
        raise GgufError(f"server trả về không phải WAV ({error})") from error
    if width != 2 or rate != SAMPLE_RATE:
        raise GgufError(f"WAV của server không phải 16-bit {SAMPLE_RATE} Hz ({width * 8}-bit {rate} Hz)")
    data = np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0
    return data.reshape(-1, channels).mean(axis=1).astype(np.float32) if channels > 1 else data


class GgufEngine:
    """Một server audio.cpp và các yêu cầu tới nó, tuần tự (máy chỉ có chừng ấy lõi). `command(files, cổng, luồng)` thay được cho bài thử."""

    def __init__(self, files: GgufFiles, *, threads: int | None = None, idle_seconds: float = IDLE_SECONDS,
                 command: Callable[[GgufFiles, int, int], list[str]] = server_command) -> None:
        self.files = files
        from . import vieneu_engine

        self.threads = threads or min(vieneu_engine.default_threads(), THREADS)
        self.idle_seconds = idle_seconds
        self._command = command
        self._lock = threading.RLock()
        self._process: subprocess.Popen | None = None
        self._port = 0
        self._used = 0.0
        self._watch: threading.Thread | None = None
        self._stop_watch = threading.Event()
        self.starts = 0

    # ---- vòng đời ----
    def running(self) -> bool:
        process = self._process
        return process is not None and process.poll() is None

    def _start(self) -> None:
        self._kill()
        port = _free_port()
        log_path = self.files.work / "server.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("ab") as log_file:
            try:
                process = subprocess.Popen(self._command(self.files, port, self.threads), stdin=subprocess.DEVNULL, stdout=log_file, stderr=subprocess.STDOUT,
                                           cwd=str(self.files.server.parent), creationflags=CREATE_NO_WINDOW if sys.platform == "win32" else 0)
            except OSError as error:
                raise GgufError(f"không chạy được server ({error})") from error
        _bind_to_app(process)
        self._process, self._port = process, port
        self.starts += 1
        deadline = time.monotonic() + START_TIMEOUT
        while time.monotonic() < deadline:
            if process.poll() is not None:
                self._process = None
                raise GgufError(f"server thoát ngay khi khởi động (mã {process.returncode})")
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as reply:
                    if reply.status == 200:
                        self._used = time.monotonic()
                        self._watch_idle()
                        return
            except (OSError, urllib.error.URLError, http.client.HTTPException):
                time.sleep(0.1)
        self._kill()
        raise GgufError(f"server không sẵn sàng sau {START_TIMEOUT:.0f} giây")

    def _kill(self) -> None:
        process, self._process = self._process, None
        if process is None:
            return
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(5)

    def stop(self) -> None:
        """Tắt server (lấy lại RAM, thả file model để cập nhật được). Khúc kế sẽ khởi lại."""
        self._stop_watch.set()
        with self._lock:
            self._kill()

    def _watch_idle(self) -> None:
        self._stop_watch.clear()
        if self._watch is not None and self._watch.is_alive():
            return

        def run() -> None:
            while not self._stop_watch.wait(min(30.0, max(self.idle_seconds / 4, 0.05))):
                if self._lock.acquire(blocking=False):  # đang đọc khúc thì lock bận: chưa phải rảnh
                    try:
                        if self._process is None:
                            return
                        if time.monotonic() - self._used >= self.idle_seconds:
                            self._kill()
                            return
                    finally:
                        self._lock.release()

        self._watch = threading.Thread(target=run, name="vieneu-gguf-idle", daemon=True)
        self._watch.start()

    # ---- đọc ----
    def _post(self, body: dict[str, Any]) -> bytes:
        request = urllib.request.Request(f"http://127.0.0.1:{self._port}/v1/audio/speech", data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                                         headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as reply:
            return reply.read()

    def speak(self, phonemes: str, voice: Path, seed: int) -> Any:
        """Một khúc phoneme -> sóng âm mono float32 `SAMPLE_RATE`. `voice`: thư mục file giọng (`voice_dir`). Server không lên / chết hai lần liền -> GgufError."""
        body = {"model": "vieneu", "input": phonemes, "seed": int(seed),
                "options": {"reference_codes_file": str(voice / "ref_codes.txt"), "speaker_embedding_file": str(voice / "speaker.emb.txt")}}
        with self._lock:
            problem: Exception | None = None
            for _attempt in range(2):  # lần hai: server chết giữa chừng thì khởi lại một lần
                try:
                    if not self.running():
                        self._start()
                    audio = mono_samples(self._post(body))
                    self._used = time.monotonic()
                    return audio
                except GgufError as error:
                    problem = error
                except (OSError, urllib.error.URLError, http.client.HTTPException) as error:
                    problem = GgufError(f"server không trả lời ({error})")
                log.warning("bản tăng tốc VieNeu: %s", problem)
                self._kill()
            assert problem is not None
            raise problem


# ---- dùng chung trong app -----------------------------------------------------------------------------------------------------------
_engines: dict[str, GgufEngine] = {}
_engines_lock = threading.Lock()
_failure = ""


def engine_for(files: GgufFiles) -> GgufEngine:
    """Engine dùng chung của app cho các file này (một server cho cả app)."""
    key = str(files.server)
    with _engines_lock:
        engine = _engines.get(key)
        if engine is None or engine.files != files:
            engine = _engines[key] = GgufEngine(files)
        return engine


def shutdown() -> None:
    """Tắt mọi server đang chạy (app thoát, hay trước khi thay file model / file chạy)."""
    with _engines_lock:
        engines = list(_engines.values())
    for engine in engines:
        engine.stop()


atexit.register(shutdown)


def failure() -> str:
    """Lý do bản tăng tốc đã tắt trong phiên này (rỗng = chưa hỏng)."""
    return _failure


def reset_failure() -> None:
    global _failure
    _failure = ""


def _fail(reason: str) -> None:
    global _failure
    _failure = reason
    log.warning("bản tăng tốc VieNeu tắt cho phiên này, đọc bằng ONNX: %s", reason)


class AcceleratedEngine:
    """Đứng thay `ve.TurboEngine`: `infer` cùng chữ ký và cùng `SAMPLE_RATE`. `locate()`: file bản tăng tốc đang dùng được (None = không dùng: chưa tải, người dùng
    tắt, máy không chạy được); `onnx()`: dựng engine ONNX khi cần (nạp lười: máy chạy bản tăng tốc suôn sẻ không tốn 0,5-3,7 GB RAM của nó)."""

    SAMPLE_RATE = SAMPLE_RATE

    def __init__(self, onnx: Callable[[], Any], locate: Callable[[], GgufFiles | None], *,
                 engine_of: Callable[[GgufFiles], GgufEngine] = engine_for) -> None:
        self._onnx_make = onnx
        self._onnx: Any = None
        self._onnx_lock = threading.Lock()
        self._locate = locate
        self._engine_of = engine_of

    def onnx(self) -> Any:
        with self._onnx_lock:
            if self._onnx is None:
                self._onnx = self._onnx_make()
            return self._onnx

    def infer(self, phonemes: str, speaker_emb: Any, ref_codes: Any, *, rng: Any, **options: Any) -> Any:
        files = self._locate() if ref_codes is not None and not _failure else None  # giọng không có mã tham chiếu: audio.cpp không đọc được, ONNX đọc
        if files is not None:
            try:
                voice = voice_dir(files, speaker_emb, ref_codes)
                return self._engine_of(files).speak(phonemes, voice, int(rng.randint(1, 2 ** 31 - 1)))  # hạt của audio.cpp suy từ đúng hạt của khúc
            except (GgufError, OSError) as error:
                _fail(str(error))
        return self.onnx().infer(phonemes, speaker_emb, ref_codes, rng=rng, **options)
