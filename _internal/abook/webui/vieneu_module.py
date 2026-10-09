"""Mô-đun "Giọng VieNeu" của máy tính (docs/LISTEN_ANYTHING.md mục 3): giọng đọc ngay trên máy cho "Nghe ngay", không cần mạng. Như "Phân tích
nhạc" (music_module.py): bộ cài không mang gì, người dùng bấm mới tải, ghim từng phần, biết phần nào cũ sau khi app lên bản mới và chỉ tải phần ấy.

Người dùng chọn (`CHOICES`, có "Khuyên dùng" theo máy - `recommend`):
- `turbo`: VieNeu-TTS v3 Turbo int8 + bộ giải mã MOSS - 25 giọng, 48 kHz.
- `nano`: VieNeu-TTS v3 Nano - 11 giọng, 24 kHz; đọc tốn ít RAM và hợp máy ít lõi hơn Turbo, nhưng file tải nặng hơn.
- `aligner`: bộ căn chữ wav2vec2 (122 MB, cùng file Studio dùng) - mốc từng chữ chính xác; mặc định có trên máy tính.
Mỗi lựa chọn kéo theo các phần (`NEEDS`); phần dùng chung chỉ tính một lần và phần máy đã có (thư viện của "Phân tích nhạc", bộ căn chữ của
Studio, gói cài sẵn trên máy dev) không tính: dung lượng hiện là cái máy này còn thiếu.
- `libs` numpy + onnxruntime: CHÍNH phần của mô-đun nhạc (music_module.libs_part, cùng chỗ, cùng dấu).
- `g2p` sea-g2p (chữ -> phoneme, Rust + từ điển, Apache-2.0): wheel abi3 ghim, giải vào <dữ liệu app>/vieneu/lib.
- `voices` các giọng có sẵn: hai file JSON trong wheel vieneu 3.8.3 ghim (chỉ lấy hai file ấy, không cài gói vieneu).
- `turbo`, `nano`, `aligner`: file model trên Hugging Face, ghim commit + SHA-256.
- `gguf` ("Bản tăng tốc", lựa chọn `fast`): cùng model Turbo chạy bằng audio.cpp (readaloud/vieneu_gguf.py) - server bản AVX2 ghim + GGUF q8_0, ~200 MB, nhanh
  ~2 lần và ít RAM hơn. Chỉ có cho Windows x64 có AVX2; cần cả `turbo` (đường lui khi server không chạy, và giọng ONNX vẫn là nền). Người dùng có công tắc
  "Dùng bản tăng tốc" (`set_accelerate`); tải xong, lần tự đo của Turbo chạy bằng bản này - hỏng thì ghi "máy này không chạy được" (`broken`) và đọc bằng ONNX.

Thiết bị: luôn CPU. Đo 03-10 trên máy dev (Ryzen 9 8945HX, RTX 5060 Laptop đang bận việc khác ~80%): DirectML chậm hơn CPU nhiều (Turbo RTF 2,83
so với 0,31; Nano 0,77 so với 0,30) - Turbo gọi hàng trăm đồ thị nhỏ mỗi giây, card không gánh được phần chi phí mỗi lần gọi. Torch của Studio là
một tiến trình Python khác, không dùng được trong tiến trình này cho rẻ. Xem docs/LISTEN_ANYTHING.md.

Tải xong thì tự đo vài giây (`benchmark`, VieneuProvider.benchmark): giọng nào không kịp tốc độ nghe (RTF > `SLOW_RTF`) thì `suggestion` đề
nghị đổi - không bao giờ tự đổi. Giao diện hỏi `status()` ~mỗi giây trong lúc tải / đo.
"""
from __future__ import annotations

import importlib
import importlib.util
import os
import shutil
import sys
import zipfile
from pathlib import Path
from typing import Any, Callable

from ..readaloud import vieneu_gguf
from ..readaloud.vieneu import Installed
from . import music_module, studio_setup, voice_module, word_timing
from .music_module import Component
from .studio_setup import Download
from .voice_module import ModuleCore

FOLDER = "vieneu"
LIB_FOLDER = "lib"
LIB_NEXT = "lib.next"  # sea-g2p mới khi bản cũ đã nạp vào tiến trình (.pyd không thay tại chỗ được): đổi chỗ ở lần mở app sau
VOICES_FOLDER = "voices"
ALIGNER_FOLDER = "wordalign"
ENV_DOWNLOAD = "ABOOK_VIENEU_DOWNLOAD"  # "0" = không bao giờ tải (bộ kiểm đặt sẵn)
SLOW_RTF = 0.8  # trên mức này giọng khó theo kịp người nghe ở tốc độ 1x (còn phải đọc trước, nghe nhanh hơn)

# Nâng: đổi URL + SHA-256 + cỡ (PyPI: https://pypi.org/pypi/<tên>/<số>/json; Hugging Face: /api/models/<repo>/tree/<commit>), chạy lại bài so
# với gói vieneu (tests/test_readaloud_vieneu.py) và đo lại độ to (loudness.py).
G2P = Download("sea-g2p", "https://files.pythonhosted.org/packages/73/57/58916050fe1218c106f89d4fa3b8f18f4ef5d264e6ec5906020f2f1dfcf2/"
               "sea_g2p-0.10.0-cp310-abi3-win_amd64.whl", "118d471796ff4fafe5cdcf1f75431a63e76ec5c0e7786cb7b3ff876d6d5292ea", 27_530_792)
VOICES = Download("vieneu", "https://files.pythonhosted.org/packages/fc/9c/e7b624412b8a734d6b1cd8ca6209f88a309464b05393c40f2e316ec90885/"
                  "vieneu-3.8.3-py3-none-any.whl", "7388d166e65746f5bb075bf8094d324f8131a82393680b712260d6f2f983ef06", 2_643_059)
VOICE_MEMBERS = {"vieneu/assets/voices_v3_turbo.json": "voices_v3_turbo.json", "vieneu/assets/voices_v3_nano.json": "voices_v3_nano.json"}
_TURBO = "https://huggingface.co/pnnbao-ump/VieNeu-TTS-v3-Turbo/resolve/61b85e3d937fbbacb387714180e8182823512523/onnx_int8/"
_CODEC = "https://huggingface.co/OpenMOSS-Team/MOSS-Audio-Tokenizer-Nano-ONNX/resolve/ceff0d0749bfb3fa2d61149794ec6feef0d1e1ae/"
_NANO = "https://huggingface.co/pnnbao-ump/VieNeu-TTS-v3-Nano/resolve/aba295eb96a6fa6003ebe417cc1f2802a7adc1dc/"
TURBO_FILES = (
    Download("config.json", _TURBO + "config.json", "a9f8d9c4b4736448ab355d1a98cfe48f5e39aecf2916c37b0806c228612e9a2d", 2_152),
    Download("tokenizer.json", _TURBO + "tokenizer.json", "6cc6bcbe380b8c37bd9f2514e37c5dfa3e00e122c6e3125dae5c4afe48e39158", 22_320),
    Download("vieneu_prefill.onnx", _TURBO + "vieneu_prefill.onnx",
             "c6a80dabf67c820de798f8deb7d4e0f37d81b5d76e33fbe20ab5a67f2d371f4e", 1_090_823),
    Download("vieneu_decode_step.onnx", _TURBO + "vieneu_decode_step.onnx",
             "2c5b30bd8ccb751c58d651f44c074df10c4113efd08719adaa8e3dec6a6ce2ca", 1_062_040),
    Download("vieneu_acoustic_cached.onnx", _TURBO + "vieneu_acoustic_cached.onnx",
             "f631e3387c788c3d8b9a5ac5df94952af5bc4c4d1049ff8a751e76a246fff2d4", 7_207_223),
    Download("vieneu_backbone_shared.data", _TURBO + "vieneu_backbone_shared.data",
             "bb683925f7c8d826fadca4f8a0252ae4d5fc5b7837c14f6857e18f4c6666588d", 103_891_968),
    Download("vieneu_v3_heads.npz", _TURBO + "vieneu_v3_heads.npz",
             "fb22484baa424bbb775133a6e5f0d00d6299b2b256fbe3312a864b85b9aed01e", 52_219_622),
    Download("moss_audio_tokenizer_decode_full.onnx", _CODEC + "moss_audio_tokenizer_decode_full.onnx",
             "0fbbafe3fd4afa2a019af5c5ced204af6e2d1db044fa40f021525d2aee95b4ac", 681_902),
    Download("moss_audio_tokenizer_decode_shared.data", _CODEC + "moss_audio_tokenizer_decode_shared.data",
             "e69d52e0f4e84ca27850557ee54face46632d3a5a16c89bd246c7c408466dcad", 44_198_912),
)
NANO_FILES = (
    Download("config.json", _NANO + "config.json", "3762f1716fd8d7a1451ddf2e051c03b0a341e8adda4f1dbd0db0ae9777514e56", 2_927),
    Download("constants.npz", _NANO + "constants.npz", "7c011938effe41687a9af85107a31a040dfcf0fb3d0f048ec10f4fb65c1a8829", 53_448),
    Download("text_encoder.onnx", _NANO + "text_encoder.onnx", "204f02cccae1f16ccb2d3840f05721a37fe250b82cbd456337a0ccb49615e4bf", 26_519_943),
    Download("duration_predictor.onnx", _NANO + "duration_predictor.onnx",
             "20fd7fa60006d0a48ee82e0451b3f920d2052588c083c756cce669f3947c0a68", 727_809),
    Download("vector_estimator.onnx", _NANO + "vector_estimator.onnx",
             "c6c1d4398ca35d3ad1bd3f0459413d1b975d09e7f2f3a2b4493a7b92bbf6ce93", 155_132_418),
    Download("codec_decoder.onnx", _NANO + "codec_decoder.onnx", "b0ab15e7828a39d53679e25b1ba4ba415a61311307202a6323130b9e1cc3029d", 99_319_941),
)
# Bản tăng tốc (readaloud/vieneu_gguf.py): server audio.cpp v0.9.1 tự build nhắm AVX2 (MSVC, không AVX-512: trên Zen4 nhanh hơn bản AVX-512 ~1,25 lần và chạy được
# trên mọi máy có AVX2; đổi binary là đổi audio nên ghim cả sha256) + GGUF q8_0 của VieNeu Turbo. Nâng: build lại, đăng lên nơi chứa, đổi URL + băm + cỡ, đo lại.
SERVER_ZIP = Download("audiocpp-server.zip", "https://huggingface.co/NGDtuanh/abook-music-student/resolve/2374dab847a5a1356948a7e6b741997de25ebbbd/"
                      "audiocpp/0.9.1-avx2/audiocpp-server-0.9.1-win-x64-avx2.zip",
                      "533b667e01103617f746b30a31c716fa8e98c3d8a0c7ff53fd1df1795e236c86", 11_582_285)
GGUF_MODEL = Download(vieneu_gguf.MODEL_FILE, _TURBO.replace("onnx_int8/", "gguf/") + vieneu_gguf.MODEL_FILE,
                      "a60569e5d7dd6f24cbb7bb2e7c472bb988ad19563a4e78f0cc67cc53fd189bb4", 187_917_664)
GGUF_FILES = (SERVER_ZIP, GGUF_MODEL)
FILES = {"g2p": (G2P,), "voices": (VOICES,), "turbo": TURBO_FILES, "nano": NANO_FILES, "aligner": studio_setup.WORD_ALIGN_FILES, "gguf": GGUF_FILES}

CHOICES = ("turbo", "nano", "aligner")
FAST = "fast"  # "Bản tăng tốc": chỉ hiện trên máy chạy được (`fast_supported`)
NEEDS = {"turbo": ("libs", "g2p", "voices", "turbo"), "nano": ("libs", "g2p", "voices", "nano"), "aligner": ("libs", "aligner"),
         FAST: ("libs", "g2p", "voices", "turbo", "gguf")}
CHOICE_TEXT = {
    "turbo": ("Giọng VieNeu", "25 giọng, âm thanh 48 kHz - hay nhất"),
    "nano": ("Giọng VieNeu Nano", "11 giọng, âm thanh 24 kHz - lúc đọc tốn ít bộ nhớ và hợp máy ít lõi hơn Giọng VieNeu; file tải nặng hơn"),
    "aligner": ("Tô đúng từng chữ đang đọc", "Biết chính xác chữ nào đang được đọc. Không tải thì máy ước theo âm tiết, đôi khi lệch một nhịp"),
    FAST: ("Bản tăng tốc", "Giọng VieNeu đọc nhanh gấp hai lần trở lên và tốn ít bộ nhớ hơn - giọng vẫn như cũ. Dùng kèm Giọng VieNeu"),
}
PART_LABEL = {"g2p": "Bộ đọc chữ tiếng Việt", "voices": "Danh sách giọng", "turbo": "Giọng VieNeu", "nano": "Giọng VieNeu Nano",
              "aligner": "Bộ căn chữ", "gguf": "Bản tăng tốc"}
GGUF_FOLDER = "gguf"
SERVER_FOLDER = "server"  # giải gói server vào đây (đổi cả thư mục một lần, file chạy không bao giờ nằm dở)

_core = ModuleCore("giọng VieNeu", "vieneu-module", frozenset({"libs"}), lambda: installed() is not None)
_lock = _core.lock
_state = _core.state
pin = voice_module.pin


# ---- cấu hình, dấu ----------------------------------------------------------------------------------------------------------------
def configure(folder: Path | str | None, *, benchmark: Callable[[str], dict[str, Any]] | None = None,
              after_install: Callable[[], None] | None = None) -> None:
    """Thư mục của mô-đun (server.py: <dữ liệu app>/vieneu). `benchmark(tầng)`: tự đo sau khi tải (VieneuProvider.benchmark); `after_install`:
    nạp lại giọng (VieneuProvider.forget). Đã tải từ trước thì đưa sea-g2p vào sys.path và chỉ chỗ bộ căn chữ cho word_timing ngay."""
    with _lock:
        _core.configure(folder, _probing(benchmark), _stopping(after_install))
        vieneu_gguf.reset_failure()
        if _core.folder is not None:
            word_timing.add_model_dir(_core.folder / ALIGNER_FOLDER)
            _activate()


def _stopping(after_install: Callable[[], None] | None) -> Callable[[], None]:
    """Việc sau khi cập nhật / trước khi thay file model: tắt server bản tăng tốc (nó giữ file model và file chạy mở, Windows không cho thay) rồi nạp lại giọng."""
    def run() -> None:
        vieneu_gguf.shutdown()
        if after_install is not None:
            after_install()
    return run


def _probing(benchmark: Callable[[str], dict[str, Any]] | None) -> Callable[[str], dict[str, Any]] | None:
    """Lần tự đo của Turbo chạy bằng bản tăng tốc khi có (đó là câu thử đầu tiên sau khi tải). Bản tăng tốc hỏng giữa chừng (server không lên, chết, không ra WAV) thì
    khúc ấy đọc bằng ONNX, và ở đây ghi lại "máy này không chạy được" (`accelerated()["broken"]`) để lần sau khỏi thử; "Thử lại tốc độ" thử lại từ đầu."""
    if benchmark is None:
        return None

    def run(tier: str) -> dict[str, Any]:
        if tier != "turbo":
            return benchmark(tier)
        vieneu_gguf.reset_failure()
        _set_broken("")
        try:
            return benchmark(tier)
        finally:
            _set_broken(vieneu_gguf.failure())
    return run

def _activate() -> None:
    folder = _core.folder
    if folder is None:
        return
    lib, pending = folder / LIB_FOLDER, folder / LIB_NEXT
    if pending.is_dir() and "sea_g2p" not in sys.modules:
        shutil.rmtree(lib, ignore_errors=True)
        try:
            os.replace(pending, lib)
        except OSError:
            pass
    if lib.is_dir() and str(lib) not in sys.path:
        sys.path.insert(0, str(lib))
        importlib.invalidate_caches()


def _restart_pending() -> bool:
    return _core.folder is not None and (_core.folder / LIB_NEXT).is_dir() and "sea_g2p" in sys.modules


# ---- máy này ----------------------------------------------------------------------------------------------------------------------
def _ram_gb() -> float:
    try:
        if os.name == "nt":
            import ctypes

            class Status(ctypes.Structure):
                _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong), ("total", ctypes.c_ulonglong), ("free", ctypes.c_ulonglong),
                            ("page_total", ctypes.c_ulonglong), ("page_free", ctypes.c_ulonglong), ("virtual_total", ctypes.c_ulonglong),
                            ("virtual_free", ctypes.c_ulonglong), ("extended", ctypes.c_ulonglong)]

            status = Status()
            status.length = ctypes.sizeof(Status)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return round(status.total / 1024 ** 3, 1)
            return 0.0
        return round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1024 ** 3, 1)
    except (OSError, ValueError, AttributeError):
        return 0.0


_facts: dict[str, Any] | None = None


def device_facts() -> dict[str, Any]:
    """Số luồng CPU, RAM, card NVIDIA (chỉ để hiện - giọng luôn chạy CPU). Hỏi một lần cho cả phiên."""
    global _facts
    if _facts is None:
        gpu = studio_setup.nvidia_gpu()
        _facts = {"cores": os.cpu_count() or 1, "ramGb": _ram_gb(), "gpu": (gpu or {}).get("name", ""), "runs": "cpu"}
    return dict(_facts)


def recommend(facts: dict[str, Any]) -> str:
    """Turbo hay Nano trước khi tải, theo máy. Turbo gần như chỉ chạy một lõi (đo 03-10: RTF 0,64 một luồng, 0,31 tám luồng) nên cần máy đời mới;
    Nano tăng tốc theo số lõi (0,71 -> 0,30). Máy từ 8 luồng và 8 GB RAM (hay không đọc được RAM) là máy xách tay đời mới: Turbo; còn lại Nano.
    Đoán sai thì lần tự đo sau khi tải sẽ đề nghị đổi."""
    ram = float(facts.get("ramGb") or 0)
    return "turbo" if int(facts.get("cores") or 1) >= 8 and (ram == 0 or ram >= 8) else "nano"


# ---- các phần ---------------------------------------------------------------------------------------------------------------------
def _complete(folder: Path | None, files: tuple[Download, ...]) -> bool:
    return folder is not None and all((folder / item.name).is_file() for item in files)


def _dir(part: str) -> Path | None:
    if _core.folder is None:
        return None
    return _core.folder / {"g2p": LIB_FOLDER, "voices": VOICES_FOLDER, "aligner": ALIGNER_FOLDER}.get(part, part)


def _download_off() -> str:
    return "tải giọng VieNeu đang bị tắt trên máy này" if os.environ.get(ENV_DOWNLOAD, "1") == "0" else ""


def _g2p_external() -> bool:
    """Máy tự import được sea_g2p (máy dev có gói vieneu): không tải."""
    lib = _dir("g2p")
    try:
        spec = importlib.util.find_spec("sea_g2p")
    except (ImportError, ValueError):
        return False
    return spec is not None and spec.origin is not None and not (lib is not None and Path(spec.origin).is_relative_to(lib))


def _g2p_present() -> bool:
    return _core.folder is not None and any((_core.folder / name / "sea_g2p").is_dir() for name in (LIB_FOLDER, LIB_NEXT))


def _aligner_external() -> bool:
    found = word_timing.model_dir()
    mine = _dir("aligner")
    return found is not None and (mine is None or found != mine)


def fast_supported() -> bool:
    """Máy chạy được bản tăng tốc (Windows x64, CPU có AVX2): không thì lựa chọn "Bản tăng tốc" không hiện, ONNX như cũ."""
    return not vieneu_gguf.unsupported_reason()


def _choices() -> tuple[str, ...]:
    return CHOICES + (FAST,) if fast_supported() else CHOICES


def _gguf_present() -> bool:
    folder = _dir("gguf")
    return folder is not None and (folder / SERVER_FOLDER / vieneu_gguf.SERVER_EXE).is_file() and (folder / vieneu_gguf.MODEL_FILE).is_file()


def _parts() -> list[Component]:
    off = _download_off()
    libs = music_module.libs_part(off or music_module.libs_problem())
    g2p_problem = off or ("bộ đọc chữ tiếng Việt tải sẵn chỉ có cho Windows 64-bit" if sys.platform != "win32" else "")
    voices_dir = _dir("voices")
    out = [libs, Component("g2p", PART_LABEL["g2p"], pin(FILES["g2p"]), G2P.size, _g2p_present(), external=_g2p_external(),
                           blocked=g2p_problem, downloads=[G2P]),
           Component("voices", PART_LABEL["voices"], pin(FILES["voices"]), VOICES.size,
                     voices_dir is not None and all((voices_dir / name).is_file() for name in VOICE_MEMBERS.values()),
                     blocked=off, downloads=[VOICES])]
    for part in ("turbo", "nano", "aligner"):
        files = FILES[part]
        out.append(Component(part, PART_LABEL[part], pin(files), sum(item.size for item in files), _complete(_dir(part), files),
                             external=part == "aligner" and _aligner_external(), blocked=off, downloads=list(files)))
    out.append(Component("gguf", PART_LABEL["gguf"], pin(GGUF_FILES), sum(item.size for item in GGUF_FILES), _gguf_present(),
                         blocked=off or vieneu_gguf.unsupported_reason(), downloads=list(GGUF_FILES)))
    return out


def _judged(parts: list[Component]) -> dict[str, str]:
    """Phần thư viện theo dấu của mô-đun nhạc (nơi nó sống), các phần khác theo dấu của mô-đun này."""
    judged = music_module.judge_parts([part for part in parts if part.id != "libs"], _core.pins())
    libs = next(part for part in parts if part.id == "libs")
    judged["libs"] = "current" if libs.external else music_module.libs_state()
    return judged


def _lacking(choices: list[str] | tuple[str, ...], parts: dict[str, Component], judged: dict[str, str]) -> list[Component]:
    """Các phần (không trùng) mà những lựa chọn này còn thiếu hay đã cũ trên máy này."""
    wanted: list[str] = []
    for choice in choices:
        wanted += [part for part in NEEDS[choice] if part not in wanted]
    return [parts[part] for part in wanted if judged[part] != "current"]


def installed() -> Installed | None:
    """Nơi các phần đang nằm (cho VieneuProvider); None khi chưa có giọng nào dùng được (bản cũ vẫn dùng được cho tới lúc cập nhật xong)."""
    if _core.folder is None:
        return None
    if importlib.util.find_spec("numpy") is None or importlib.util.find_spec("onnxruntime") is None:
        return None
    voices = _dir("voices")
    if voices is None or not (_g2p_external() or _g2p_present()):
        return None
    turbo_dir, nano_dir = _dir("turbo"), _dir("nano")
    turbo = (turbo_dir, turbo_dir) if _complete(turbo_dir, TURBO_FILES) else None
    nano = nano_dir if _complete(nano_dir, NANO_FILES) else None
    if turbo is None and nano is None:
        return None
    return Installed(voices, turbo, nano, word_timing.model_dir() is not None)


def make_engine(tier: str, found: Installed) -> Any:
    """Bộ dựng engine cho VieneuProvider (`engines=`): Turbo trên máy chạy được bản tăng tốc được bọc để dùng nó khi có (`vieneu_gguf.AcceleratedEngine`; ONNX nạp lười
    làm đường lui), còn lại là engine ONNX như trước."""
    from ..readaloud import vieneu

    if tier == "turbo" and fast_supported():
        return vieneu_gguf.AcceleratedEngine(lambda: vieneu._real_engine(tier, found), gguf_files)  # noqa: SLF001 - cùng gói, cùng bộ dựng với đường ONNX
    return vieneu._real_engine(tier, found)  # noqa: SLF001


def rtf(voice: str) -> float | None:
    """Tốc độ tự đo của giọng VieNeu `voice` ("vieneu:turbo/...") trên máy này - để "Làm trước" ước thời gian; None nếu chưa đo / giọng khác."""
    tier = voice.removeprefix("vieneu:").partition("/")[0] if voice.startswith("vieneu:") else ""
    bench = _core.benchmarks()
    value = bench.get(tier, {}).get("rtf") if isinstance(bench.get(tier), dict) else None
    return float(value) if isinstance(value, (int, float)) else None


def suggestion(bench: dict[str, Any], tiers: list[str]) -> dict[str, Any] | None:
    """Giọng đã tải mà không kịp tốc độ nghe trên máy này -> đề nghị (người dùng quyết): Turbo chậm thì Nano (nếu Nano không chậm), còn lại thì
    giọng trực tuyến. None khi mọi giọng đều kịp (hay chưa đo)."""
    slow = [tier for tier in tiers if float((bench.get(tier) or {}).get("rtf") or 0) >= SLOW_RTF]
    if not slow:
        return None
    tier = "turbo" if "turbo" in slow else slow[0]
    rtf = float(bench[tier]["rtf"])
    if tier == "turbo" and "nano" not in slow:
        return {"tier": tier, "rtf": rtf, "switchTo": "nano", "installed": "nano" in tiers}
    return {"tier": tier, "rtf": rtf, "switchTo": "online", "installed": True}


def status() -> dict[str, Any]:
    with _lock:
        parts = _parts()
        by_id = {part.id: part for part in parts}
        judged = _judged(parts)
        tiers = [tier for tier in ("turbo", "nano") if all(judged[part] != "missing" for part in NEEDS[tier])]
        have = [choice for choice in _choices() if all(judged[part] != "missing" for part in NEEDS[choice])]
        behind = _lacking(have, by_id, judged)
        behind = [part for part in behind if judged[part.id] == "outdated"]
        facts = device_facts()
        best = recommend(facts)
        blocked = next((by_id[part].blocked for part in ("libs", "g2p") if judged[part] != "current" and by_id[part].blocked), "")
        if _state["downloading"]:
            state = "downloading"
        elif _state["error"]:
            state = "error"
        elif tiers:
            state = "outdated" if behind else "ready"
        else:
            state = "unsupported" if blocked else "missing"
        bench = _core.benchmarks()
        choices = []
        picks = {best, "aligner"} | ({FAST} if best == "turbo" else set())  # bản tăng tốc đi kèm Turbo: máy hợp Turbo thì khuyên cả hai
        for choice in _choices():
            label, detail = CHOICE_TEXT[choice]
            lacking = _lacking([choice], by_id, judged)
            if choice == FAST:
                lacking = [part for part in lacking if part.id == "gguf"]  # cỡ riêng của nó; phần Giọng VieNeu nó cần đã có dòng của mình
            choices.append({"id": choice, "label": label, "detail": detail, "needs": list(NEEDS[choice]),
                            "bytes": sum(part.size for part in lacking), "installed": choice in have,
                            "recommended": choice in picks, "default": choice in picks, **({"requires": ["turbo"]} if choice == FAST else {})})
        return {
            "state": state, "done": _state["done"] if state == "downloading" else 0,
            "total": _state["total"] if state == "downloading" else 0, "error": _state["error"],
            "supported": not blocked, "reason": blocked, "choices": choices,
            "parts": [{"id": part.id, "label": part.label, "bytes": part.size, "state": judged[part.id], "external": part.external}
                      for part in parts],
            "outdatedParts": [part.label for part in behind], "outdatedBytes": sum(part.size for part in behind),
            "benchmark": {tier: bench[tier] for tier in tiers if isinstance(bench.get(tier), dict)},
            "benchmarking": _state["benchmarking"], "suggestion": suggestion(bench, tiers) if not _state["benchmarking"] else None,
            "cancelled": bool(_state["cancelled"]), "device": facts, "recommended": best, "restart": _restart_pending(), "slowRtf": SLOW_RTF,
            "accelerated": accelerated() if FAST in have else None,
        }


# ---- tải --------------------------------------------------------------------------------------------------------------------------
def start(choices: list[str] | None = None) -> None:
    """Tải các phần mà `choices` còn thiếu (hay cập nhật những phần đã cũ của những gì đã tải khi `choices` là None) ở luồng nền."""
    with _lock:
        if _core.folder is None:
            raise ValueError("Mô-đun giọng VieNeu chưa được cấu hình")
        if _core.busy():
            return
        parts = _parts()
        by_id = {part.id: part for part in parts}
        judged = _judged(parts)
        if choices is None:
            choices = [choice for choice in _choices() if all(judged[part] != "missing" for part in NEEDS[choice])]
        unknown = [choice for choice in choices if choice not in _choices()]
        if unknown:
            raise ValueError(f"Không có lựa chọn {unknown[0]!r}")
        _core.begin(_lacking(choices, by_id, judged), _install, _activate, _tiers_changed)


def _tiers_changed(changed: set[str]) -> list[str]:
    """Giọng cần tự đo lại sau khi tải: tầng có phần vừa đổi; bản tăng tốc đổi thì đo lại Turbo (lần đo ấy chạy bằng nó)."""
    return [tier for tier in ("turbo", "nano") if changed & (set(NEEDS[tier]) | ({"gguf"} if tier == "turbo" else set()))]


def join(timeout: float | None = None) -> None:
    _core.join(timeout)


def cancel() -> None:
    """Người dùng bấm Huỷ khi đang tải: dừng giữa chừng, phần đã tải được giữ để lần sau làm tiếp."""
    _core.cancel()


def _install(part: Component, progress: Callable[[int], None], cancelled: Callable[[], bool] | None = None) -> None:
    """`cancelled`: cờ Huỷ của mô-đun đang tải (mặc định của chính mô-đun này); mô-đun khác dùng chung bộ đọc chữ truyền cờ của nó."""
    folder = _core.folder
    assert folder is not None
    cancelled = cancelled or _core.cancelled
    if part.id == "libs":
        music_module.install_libs_part(lambda done, _total: progress(done), cancelled)
        return
    target = _dir(part.id)
    assert target is not None
    if part.id == "g2p" and "sea_g2p" in sys.modules and target.is_dir():
        target = folder / LIB_NEXT
    if part.id in ("g2p", "voices"):
        item = part.downloads[0]
        wheel = folder / voice_module.DOWNLOADS / f"{item.name}.whl"
        studio_setup.download(item, wheel, lambda have, _total: progress(have), cancelled)
        staging = target.with_name(target.name + ".part")
        shutil.rmtree(staging, ignore_errors=True)
        staging.mkdir(parents=True)
        with zipfile.ZipFile(wheel) as bundle:
            if part.id == "g2p":
                bundle.extractall(staging)
            else:
                for member, name in VOICE_MEMBERS.items():
                    (staging / name).write_bytes(bundle.read(member))
        shutil.rmtree(target, ignore_errors=True)
        os.replace(staging, target)
        wheel.unlink(missing_ok=True)
        return
    if part.id == "gguf":
        _install_gguf(target, folder, progress, cancelled)
        return
    voice_module.download_files(part, target, progress, cancelled)  # file model tải thẳng vào chỗ: engine đang chạy chỉ thấy file đủ


def _install_gguf(target: Path, folder: Path, progress: Callable[[int], None], cancelled: Callable[[], bool]) -> None:
    """Gói server (zip, giải vào `server/` bằng cách đổi cả thư mục) + GGUF (tải thẳng vào chỗ, `.part` rồi đổi tên sau khi khớp băm). Server cũ phải tắt trước
    (nó giữ file chạy và file model mở): `_core._after` đã làm việc ấy ở đầu lần tải."""
    vieneu_gguf.shutdown()
    archive = folder / voice_module.DOWNLOADS / SERVER_ZIP.name
    studio_setup.download(SERVER_ZIP, archive, lambda have, _total: progress(have), cancelled)
    studio_setup.download(GGUF_MODEL, target / GGUF_MODEL.name, lambda have, _total: progress(SERVER_ZIP.size + have), cancelled)
    staging = target / (SERVER_FOLDER + ".part")
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    with zipfile.ZipFile(archive) as bundle:
        bundle.extractall(staging)
    shutil.rmtree(target / SERVER_FOLDER, ignore_errors=True)
    os.replace(staging, target / SERVER_FOLDER)
    archive.unlink(missing_ok=True)
    vieneu_gguf.reset_failure()


# ---- bản tăng tốc: dùng được không, công tắc -------------------------------------------------------------------------------------------
def _broken(stamp: dict[str, Any]) -> str:
    """Lý do bản tăng tốc (đúng bản đã ghim) không chạy được trên máy này, ghi lúc tự đo; rỗng nếu chưa hỏng. Bản mới thì thử lại."""
    info = stamp.get("gguf")
    return str(info.get("broken") or "") if isinstance(info, dict) and info.get("pin") == pin(GGUF_FILES) else ""


def _set_broken(reason: str) -> None:
    with _lock:
        stamp = _core.read_stamp()
        if reason == _broken(stamp):
            return
        if reason:
            stamp["gguf"] = {"broken": reason, "pin": pin(GGUF_FILES)}
        else:
            stamp.pop("gguf", None)
        _core.write_stamp(stamp)


def gguf_files() -> vieneu_gguf.GgufFiles | None:
    """File bản tăng tốc nếu đang dùng được: đã tải, máy chạy được, người dùng không tắt, chưa ghi là hỏng. None -> Nghe ngay đọc bằng ONNX."""
    folder = _dir("gguf")
    if folder is None or not _gguf_present() or vieneu_gguf.unsupported_reason():
        return None
    stamp = _core.read_stamp()
    if stamp.get("accelerate") is False or _broken(stamp):
        return None
    return vieneu_gguf.GgufFiles(folder / SERVER_FOLDER / vieneu_gguf.SERVER_EXE, folder / vieneu_gguf.MODEL_FILE, folder / "work")


def accelerated() -> dict[str, Any]:
    """Cho thẻ: `on` công tắc người dùng; `active` đang thật sự đọc bằng bản tăng tốc; `problem` lý do nó không chạy (ghi lúc tự đo, hay hỏng giữa phiên)."""
    stamp = _core.read_stamp()
    problem = _broken(stamp) or vieneu_gguf.failure()
    on = stamp.get("accelerate") is not False
    return {"on": on, "active": gguf_files() is not None and not problem, "problem": problem}


def set_accelerate(on: bool) -> None:
    """Công tắc "Dùng bản tăng tốc". Bật lại thì thử lại từ đầu (xoá dấu hỏng); đổi xong tự đo lại Turbo để con số tốc độ trên thẻ đúng với cách đọc đang dùng."""
    with _lock:
        if _core.folder is None:
            raise ValueError("Mô-đun giọng VieNeu chưa được cấu hình")
        stamp = _core.read_stamp()
        stamp["accelerate"] = bool(on)
        if on:
            stamp.pop("gguf", None)
        _core.write_stamp(stamp)
    vieneu_gguf.reset_failure()
    if not on:
        vieneu_gguf.shutdown()
    found = installed()
    if found is not None and found.turbo is not None:
        _core.measure_again(["turbo"])


# ---- bộ đọc chữ dùng chung ----------------------------------------------------------------------------------------------------------
# Mô-đun "Giọng Supertonic" (supertonic_module.py) cũng cần sea-g2p để đổi số / ngày / giờ thành chữ: MỘT bản cho cả máy, nằm ở đây, dấu ở dấu của
# mô-đun này - như thư viện chạy model của mô-đun nhạc (music_module.libs_part) mà cả hai mô-đun giọng dùng chung.
def g2p_part() -> Component:
    for part in _parts():
        if part.id == "g2p":
            return part
    raise AssertionError("thiếu phần g2p")


def g2p_state() -> str:
    """`current` / `outdated` / `missing` của bộ đọc chữ, theo dấu của mô-đun này."""
    part = g2p_part()
    return music_module.judge_parts([part], _core.pins())[part.id]


def install_g2p_part(progress: Callable[[int], None], cancelled: Callable[[], bool] | None = None) -> None:
    """Tải bộ đọc chữ cho mô-đun khác: giải vào chỗ chung, ghi dấu ở đây, đưa vào sys.path (bản đã nạp thì chờ lần mở app sau, `LIB_NEXT`)."""
    with _lock:
        part = g2p_part()
        _install(part, progress, cancelled)
        stamp = _core.read_stamp()
        stamp["pins"] = {**_core.pins(), "g2p": part.pin}
        _core.write_stamp(stamp)
        _activate()


def measure_again() -> None:
    """Người dùng bấm "Đo lại" (máy vừa rảnh hơn, vừa cắm sạc): đo lại mọi giọng đã tải ở luồng nền."""
    found = installed()
    _core.measure_again([tier for tier in ("turbo", "nano") if found is not None and getattr(found, tier) is not None])
