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
- `voices` các giọng có sẵn: hai file JSON trong wheel vieneu 3.8.1 ghim (chỉ lấy hai file ấy, không cài gói vieneu).
- `turbo`, `nano`, `aligner`: file model trên Hugging Face, ghim commit + SHA-256.

Thiết bị: luôn CPU. Đo 03-10 trên máy dev (Ryzen 9 8945HX, RTX 5060 Laptop đang bận việc khác ~80%): DirectML chậm hơn CPU nhiều (Turbo RTF 2,83
so với 0,31; Nano 0,77 so với 0,30) - Turbo gọi hàng trăm đồ thị nhỏ mỗi giây, card không gánh được phần chi phí mỗi lần gọi. Torch của Studio là
một tiến trình Python khác, không dùng được trong tiến trình này cho rẻ. Xem docs/LISTEN_ANYTHING.md.

Tải xong thì tự đo vài giây (`benchmark`, VieneuProvider.benchmark): giọng nào không kịp tốc độ nghe (RTF > `SLOW_RTF`) thì `suggestion` đề
nghị đổi - không bao giờ tự đổi. Giao diện hỏi `status()` ~mỗi giây trong lúc tải / đo.
"""
from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json
import os
import shutil
import sys
import threading
import zipfile
from pathlib import Path
from typing import Any, Callable

from .. import io_utils
from ..readaloud.vieneu import Installed
from . import music_module, studio_setup, word_timing
from .music_module import Component
from .studio_setup import Download

FOLDER = "vieneu"
STAMP_FILE = "module.json"
LIB_FOLDER = "lib"
LIB_NEXT = "lib.next"  # sea-g2p mới khi bản cũ đã nạp vào tiến trình (.pyd không thay tại chỗ được): đổi chỗ ở lần mở app sau
VOICES_FOLDER = "voices"
ALIGNER_FOLDER = "wordalign"
DOWNLOADS = "dl"
ENV_DOWNLOAD = "ABOOK_VIENEU_DOWNLOAD"  # "0" = không bao giờ tải (bộ kiểm đặt sẵn)
SLOW_RTF = 0.8  # trên mức này giọng khó theo kịp người nghe ở tốc độ 1x (còn phải đọc trước, nghe nhanh hơn)

# Nâng: đổi URL + SHA-256 + cỡ (PyPI: https://pypi.org/pypi/<tên>/<số>/json; Hugging Face: /api/models/<repo>/tree/<commit>), chạy lại bài so
# với gói vieneu (tests/test_readaloud_vieneu.py) và đo lại độ to (loudness.py).
G2P = Download("sea-g2p", "https://files.pythonhosted.org/packages/98/2d/4553efd8f340f332eb5976118e441b09ec95cf60d27fd1ad04240d885905/"
               "sea_g2p-0.9.1-cp310-abi3-win_amd64.whl", "b6d7c09afb83750abe61735ad2e60f5c20b4cdfac30b1b9b1904de9f64f10c32", 27_531_798)
VOICES = Download("vieneu", "https://files.pythonhosted.org/packages/35/03/83c6564f834b90b9fe200c4381a8d8fc506c0697233b1a5b2c3d06d9899f/"
                  "vieneu-3.8.1-py3-none-any.whl", "bf24f88ec95f96459756d897b04a118e923536d36bcfcdccd13ba6f8f7d580ba", 2_642_947)
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
FILES = {"g2p": (G2P,), "voices": (VOICES,), "turbo": TURBO_FILES, "nano": NANO_FILES, "aligner": studio_setup.WORD_ALIGN_FILES}

CHOICES = ("turbo", "nano", "aligner")
NEEDS = {"turbo": ("libs", "g2p", "voices", "turbo"), "nano": ("libs", "g2p", "voices", "nano"), "aligner": ("libs", "aligner")}
CHOICE_TEXT = {
    "turbo": ("Giọng VieNeu", "25 giọng, âm thanh 48 kHz - hay nhất"),
    "nano": ("Giọng VieNeu Nano", "11 giọng, âm thanh 24 kHz - lúc đọc tốn ít bộ nhớ và hợp máy ít lõi hơn Giọng VieNeu; file tải nặng hơn"),
    "aligner": ("Tô đúng từng chữ đang đọc", "Biết chính xác chữ nào đang được đọc. Không tải thì máy ước theo âm tiết, đôi khi lệch một nhịp"),
}
PART_LABEL = {"g2p": "Bộ đọc chữ tiếng Việt", "voices": "Danh sách giọng", "turbo": "Giọng VieNeu", "nano": "Giọng VieNeu Nano",
              "aligner": "Bộ căn chữ"}

_lock = threading.RLock()
_folder: Path | None = None
_thread: threading.Thread | None = None
_bench: Callable[[str], dict[str, Any]] | None = None
_after: Callable[[], None] | None = None
_state: dict[str, Any] = {"downloading": False, "benchmarking": False, "done": 0, "total": 0, "error": ""}


# ---- cấu hình, dấu ----------------------------------------------------------------------------------------------------------------
def configure(folder: Path | str | None, *, benchmark: Callable[[str], dict[str, Any]] | None = None,
              after_install: Callable[[], None] | None = None) -> None:
    """Thư mục của mô-đun (server.py: <dữ liệu app>/vieneu). `benchmark(tầng)`: tự đo sau khi tải (VieneuProvider.benchmark); `after_install`:
    nạp lại giọng (VieneuProvider.forget). Đã tải từ trước thì đưa sea-g2p vào sys.path và chỉ chỗ bộ căn chữ cho word_timing ngay."""
    global _folder, _bench, _after
    with _lock:
        _folder = Path(folder) if folder is not None else None
        _bench, _after = benchmark, after_install
        _state.update(downloading=False, benchmarking=False, done=0, total=0, error="")
        if _folder is not None:
            word_timing.add_model_dir(_folder / ALIGNER_FOLDER)
            _activate()


def _read_stamp() -> dict[str, Any]:
    if _folder is None:
        return {}
    try:
        data = json.loads((_folder / STAMP_FILE).read_bytes().decode("utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_stamp(data: dict[str, Any]) -> None:
    if _folder is not None:
        io_utils.atomic_write_json(_folder / STAMP_FILE, {"version": 1, **{k: v for k, v in data.items() if k != "version"}})


def _pins(stamp: dict[str, Any]) -> dict[str, str]:
    pins = stamp.get("pins")
    return {str(k): str(v) for k, v in pins.items()} if isinstance(pins, dict) else {}


def _activate() -> None:
    if _folder is None:
        return
    lib, pending = _folder / LIB_FOLDER, _folder / LIB_NEXT
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
    return _folder is not None and (_folder / LIB_NEXT).is_dir() and "sea_g2p" in sys.modules


def pin(files: tuple[Download, ...]) -> str:
    return hashlib.sha256("\n".join(f"{item.name} {item.sha256}" for item in files).encode()).hexdigest()


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
    if _folder is None:
        return None
    return _folder / {"g2p": LIB_FOLDER, "voices": VOICES_FOLDER, "aligner": ALIGNER_FOLDER}.get(part, part)


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
    return _folder is not None and any((_folder / name / "sea_g2p").is_dir() for name in (LIB_FOLDER, LIB_NEXT))


def _aligner_external() -> bool:
    found = word_timing.model_dir()
    mine = _dir("aligner")
    return found is not None and (mine is None or found != mine)


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
    return out


def _judged(parts: list[Component]) -> dict[str, str]:
    """Phần thư viện theo dấu của mô-đun nhạc (nơi nó sống), các phần khác theo dấu của mô-đun này."""
    judged = music_module.judge_parts([part for part in parts if part.id != "libs"], _pins(_read_stamp()))
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
    if _folder is None:
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


def rtf(voice: str) -> float | None:
    """Tốc độ tự đo của giọng VieNeu `voice` ("vieneu:turbo/...") trên máy này - để "Làm trước" ước thời gian; None nếu chưa đo / giọng khác."""
    tier = voice.removeprefix("vieneu:").partition("/")[0] if voice.startswith("vieneu:") else ""
    bench = _read_stamp().get("benchmark")
    value = bench.get(tier, {}).get("rtf") if isinstance(bench, dict) and isinstance(bench.get(tier), dict) else None
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
        stamp = _read_stamp()
        tiers = [tier for tier in ("turbo", "nano") if all(judged[part] != "missing" for part in NEEDS[tier])]
        have = [choice for choice in CHOICES if all(judged[part] != "missing" for part in NEEDS[choice])]
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
        bench = stamp.get("benchmark") if isinstance(stamp.get("benchmark"), dict) else {}
        choices = []
        for choice in CHOICES:
            label, detail = CHOICE_TEXT[choice]
            choices.append({"id": choice, "label": label, "detail": detail, "needs": list(NEEDS[choice]),
                            "bytes": sum(part.size for part in _lacking([choice], by_id, judged)), "installed": choice in have,
                            "recommended": choice in (best, "aligner"), "default": choice in (best, "aligner")})
        return {
            "state": state, "done": _state["done"] if state == "downloading" else 0,
            "total": _state["total"] if state == "downloading" else 0, "error": _state["error"],
            "supported": not blocked, "reason": blocked, "choices": choices,
            "parts": [{"id": part.id, "label": part.label, "bytes": part.size, "state": judged[part.id], "external": part.external}
                      for part in parts],
            "outdatedParts": [part.label for part in behind], "outdatedBytes": sum(part.size for part in behind),
            "benchmark": {tier: bench[tier] for tier in tiers if isinstance(bench.get(tier), dict)},
            "benchmarking": _state["benchmarking"], "suggestion": suggestion(bench, tiers) if not _state["benchmarking"] else None,
            "device": facts, "recommended": best, "restart": _restart_pending(), "slowRtf": SLOW_RTF,
        }


# ---- tải --------------------------------------------------------------------------------------------------------------------------
def start(choices: list[str] | None = None) -> None:
    """Tải các phần mà `choices` còn thiếu (hay cập nhật những phần đã cũ của những gì đã tải khi `choices` là None) ở luồng nền."""
    global _thread
    with _lock:
        if _folder is None:
            raise ValueError("Mô-đun giọng VieNeu chưa được cấu hình")
        if (_state["downloading"] or _state["benchmarking"]) and _thread is not None and _thread.is_alive():
            return
        parts = _parts()
        by_id = {part.id: part for part in parts}
        judged = _judged(parts)
        if choices is None:
            choices = [choice for choice in CHOICES if all(judged[part] != "missing" for part in NEEDS[choice])]
        unknown = [choice for choice in choices if choice not in CHOICES]
        if unknown:
            raise ValueError(f"Không có lựa chọn {unknown[0]!r}")
        needed = _lacking(choices, by_id, judged)
        _state.update(error="", done=0)
        if not needed:
            return
        reason = next((part.blocked for part in needed if part.blocked and not part.external), "")
        if reason:
            _state["error"] = reason[0].upper() + reason[1:] + "."
            return
        _state.update(downloading=True, total=sum(part.size for part in needed))
        _thread = threading.Thread(target=_run, args=(needed,), name="vieneu-module", daemon=True)
        _thread.start()


def join(timeout: float | None = None) -> None:
    thread = _thread
    if thread is not None:
        thread.join(timeout)


def _install(part: Component, progress: Callable[[int], None]) -> None:
    assert _folder is not None
    if part.id == "libs":
        music_module.install_libs_part(lambda done, _total: progress(done))
        return
    target = _dir(part.id)
    assert target is not None
    if part.id == "g2p" and "sea_g2p" in sys.modules and target.is_dir():
        target = _folder / LIB_NEXT
    if part.id in ("g2p", "voices"):
        item = part.downloads[0]
        wheel = _folder / DOWNLOADS / f"{item.name}.whl"
        studio_setup.download(item, wheel, lambda have, _total: progress(have), lambda: False)
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
    done = 0  # file model tải thẳng vào chỗ (download ghi .part rồi đổi tên sau khi khớp băm): engine đang chạy chỉ thấy file đủ
    for item in part.downloads:
        studio_setup.download(item, target / item.name, lambda have, _total, offset=done: progress(offset + have), lambda: False)
        done += item.size


def _run(needed: list[Component]) -> None:
    try:
        finished = 0
        stamp = _read_stamp()
        pins = _pins(stamp)
        if _after is not None:
            _after()  # bỏ engine đang nạp: file model sắp được thay
        for part in needed:
            def progress(done: int, base: int = finished) -> None:
                with _lock:
                    _state["done"] = base + done

            _install(part, progress)
            finished += part.size
            if part.id != "libs":
                pins[part.id] = part.pin
                stamp["pins"] = pins
                _write_stamp(stamp)
            with _lock:
                _state["done"] = finished
        _activate()
        shutil.rmtree(_folder / DOWNLOADS, ignore_errors=True)  # type: ignore[operator]
        if _after is not None:
            _after()
        with _lock:
            _state.update(downloading=False, error="")
        changed = {part.id for part in needed}
        _measure([tier for tier in ("turbo", "nano") if changed & set(NEEDS[tier])])
    except Exception as error:  # noqa: BLE001 - mọi lỗi thành một câu cho người dùng
        with _lock:
            _state.update(downloading=False, error=f"Không tải được giọng VieNeu: {music_module._reason(error)}.")
    finally:
        with _lock:
            _state["downloading"] = False


def _measure(tiers: list[str]) -> None:
    """Tự đo các giọng vừa tải (vài giây mỗi giọng); lỗi đo không làm hỏng lần tải."""
    if _bench is None or installed() is None:
        return
    with _lock:
        _state["benchmarking"] = True
    try:
        stamp = _read_stamp()
        results = stamp.get("benchmark") if isinstance(stamp.get("benchmark"), dict) else {}
        for tier in tiers:
            try:
                results[tier] = _bench(tier)
            except Exception:  # noqa: BLE001
                results.pop(tier, None)
        stamp = _read_stamp()
        stamp["benchmark"] = results
        _write_stamp(stamp)
    finally:
        with _lock:
            _state["benchmarking"] = False


def measure_again() -> None:
    """Người dùng bấm "Đo lại" (máy vừa rảnh hơn, vừa cắm sạc): đo lại mọi giọng đã tải ở luồng nền."""
    global _thread
    with _lock:
        if _state["downloading"] or _state["benchmarking"]:
            return
        found = installed()
        tiers = [tier for tier in ("turbo", "nano") if found is not None and getattr(found, tier) is not None]
        if not tiers:
            return
        _state["benchmarking"] = True
        _thread = threading.Thread(target=_measure, args=(tiers,), name="vieneu-bench", daemon=True)
        _thread.start()
