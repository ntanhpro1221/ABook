"""Mô-đun "Giọng Supertonic" của máy tính: mười giọng Supertonic 3 (Supertone, 99 triệu tham số, ONNX) đọc ngay trên máy cho "Nghe ngay", không cần
mạng. Cùng khung với "Giọng VieNeu" (voice_module.py): bộ cài không mang gì, người dùng bấm mới tải, ghim từng phần, biết phần nào cũ và chỉ tải
phần ấy, tải xong tự đo vài giây, gỡ được để lấy lại chỗ.

Các phần (`NEEDS`):
- `libs` numpy + onnxruntime: CHÍNH phần của mô-đun nhạc (music_module.libs_part).
- `g2p` sea-g2p: CHÍNH phần của mô-đun VieNeu (vieneu_module.g2p_part) - chỉ để đổi số / ngày / giờ thành chữ trước khi đọc, vì Supertonic đọc số
  kém nhất. Máy không tải được (không phải Windows 64-bit) thì bỏ phần này, giọng vẫn đọc nguyên chữ.
- `supertonic` file model + mười file giọng trên Hugging Face, ghim commit + SHA-256 từng file (`SOURCE`, `FILES`).

Hãng Supertone đã giải thể (repo lưu trữ 09-09-2026) nên trọng số là bản CUỐI: ghim đúng commit; `SOURCE` là MỘT chỗ để đổi sang bản sao của app.
Giấy phép trọng số OpenRAIL-M, mã mẫu MIT - xem THIRD_PARTY.md. Thiết bị luôn CPU (đo: RTF 0,19 ở 8 luồng, RAM ~0,53 GiB).
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from typing import Any, Callable

from ..readaloud.supertonic import PREFIX, TIER, Installed
from . import music_module, vieneu_module, voice_module, word_timing
from .music_module import Component
from .studio_setup import Download
from .voice_module import ModuleCore

FOLDER = "supertonic"
ENV_DOWNLOAD = "ABOOK_SUPERTONIC_DOWNLOAD"  # "0" = không bao giờ tải (bộ kiểm đặt sẵn)
SLOW_RTF = vieneu_module.SLOW_RTF  # trên mức này giọng khó theo kịp người nghe ở tốc độ 1x

# Nơi tải: MỘT hằng (repo Hugging Face + commit). Nâng / đổi sang bản sao của app: đổi hai chuỗi này (file giữ nguyên byte thì SHA-256 dưới đây vẫn đúng).
SOURCE_REPO = "Supertone/supertonic-3"
SOURCE_REVISION = "724fb5abbf5502583fb520898d45929e62f02c0b"
_BASE = f"https://huggingface.co/{SOURCE_REPO}/resolve/{SOURCE_REVISION}/"


def _file(name: str, sha256: str, size: int) -> Download:
    return Download(name, _BASE + name, sha256, size)


# Chỉ những file suy luận cần (cỡ + băm đọc từ Hugging Face đúng commit trên; file LFS có băm sẵn, file nhỏ băm sau khi tải).
FILES = (
    _file("onnx/duration_predictor.onnx", "c3eb91414d5ff8a7a239b7fe9e34e7e2bf8a8140d8375ffb14718b1c639325db", 3_700_147),
    _file("onnx/text_encoder.onnx", "c7befd5ea8c3119769e8a6c1486c4edc6a3bc8365c67621c881bbb774b9902ff", 36_416_150),
    _file("onnx/vector_estimator.onnx", "883ac868ea0275ef0e991524dc64f16b3c0376efd7c320af6b53f5b780d7c61c", 256_534_781),
    _file("onnx/vocoder.onnx", "085de76dd8e8d5836d6ca66826601f615939218f90e519f70ee8a36ed2a4c4ba", 101_424_195),
    _file("onnx/tts.json", "42078d3aef1cd43ab43021f3c54f47d2d75ceb4e75f627f118890128b06a0d09", 8_253),
    _file("onnx/unicode_indexer.json", "9bf7346e43883a81f8645c81224f786d43c5b57f3641f6e7671a7d6c493cb24f", 277_676),
    _file("config.json", "4099082b107a9d4029849ac76b89eca65e03732660969c2babe5bf308c7357f2", 174),
    _file("LICENSE", "0d944a9110fed9a9602d60e0423a272903e7bd21ab060490774efc77c2275e9f", 15_007),
    _file("voice_styles/F1.json", "bbdec6ee00231c2c742ad05483df5334cab3b52fda3ba38e6a07059c4563dbc2", 292_046),
    _file("voice_styles/F2.json", "7c722c6a72707b1a77f035d67f0d1351ba187738e06f7683e8c72b1df3477fc6", 292_423),
    _file("voice_styles/F3.json", "12f6ef2573baa2defa1128069cb59f203e3ab67c92af77b42df8a0e3a2f7c6ab", 290_794),
    _file("voice_styles/F4.json", "c2fa764c1225a76dfc3e2c73e8aa4f70d9ee48793860eb34c295fff01c2e032b", 291_808),
    _file("voice_styles/F5.json", "45966e73316415626cf41a7d1c6f3b4c70dbc1ba2bee5c1978ef0ce33244fc8d", 291_479),
    _file("voice_styles/M1.json", "e35604687f5d23694b8e91593a93eec0e4eca6c0b02bb8ed69139ab2ea6b0a5b", 291_748),
    _file("voice_styles/M2.json", "b76cbf62bac707c710cf0ae5aba5e31eea1a6339a9734bfae33ab98499534a50", 292_055),
    _file("voice_styles/M3.json", "ea1ac35ccb91b0d7ecad533a2fbd0eec10c91513d8951e3b25fbba99954e159b", 290_198),
    _file("voice_styles/M4.json", "ca8eefad4fcd989c9379032ff3e50738adc547eeb5e221b82593a6d7b3bac303", 291_522),
    _file("voice_styles/M5.json", "dd22b92740314321f8ae11c5e87f8dd60d060f15dd3a632b5adf77f471f77af2", 291_469),
)

CHOICE = "supertonic"
CHOICES = (CHOICE,)
NEEDS = {CHOICE: ("libs", "g2p", "supertonic")}
CHOICE_TEXT = {CHOICE: ("Giọng Supertonic", "10 giọng nam nữ, âm thanh 44 kHz - nhẹ máy, đọc nhanh hơn tốc độ nghe; số và ngày giờ được đổi thành chữ trước khi đọc")}
PART_LABEL = {"supertonic": "Giọng Supertonic", "g2p": "Bộ đọc chữ tiếng Việt"}

_core = ModuleCore("giọng Supertonic", "supertonic-module", frozenset({"libs", "g2p"}), lambda: installed() is not None)
_lock = _core.lock
pin = voice_module.pin


def configure(folder: Path | str | None, *, benchmark: Callable[[str], dict[str, Any]] | None = None,
              after_install: Callable[[], None] | None = None) -> None:
    """Thư mục của mô-đun (server.py: <dữ liệu app>/supertonic). `benchmark(tầng)`: tự đo sau khi tải (SupertonicProvider.benchmark);
    `after_install`: nạp lại giọng (SupertonicProvider.forget)."""
    _core.configure(folder, benchmark, after_install)


# ---- các phần ---------------------------------------------------------------------------------------------------------------------
def _model_dir() -> Path | None:
    return None if _core.folder is None else _core.folder / "model"


def _complete(folder: Path | None) -> bool:
    return folder is not None and all((folder / item.name).is_file() for item in FILES)


def _download_off() -> str:
    return "tải giọng Supertonic đang bị tắt trên máy này" if os.environ.get(ENV_DOWNLOAD, "1") == "0" else ""


def _parts() -> list[Component]:
    off = _download_off()
    out = [music_module.libs_part(off or music_module.libs_problem())]
    g2p = vieneu_module.g2p_part()
    if g2p.present or g2p.external or sys.platform == "win32":  # nơi sea-g2p không có sẵn bản tải thì bỏ qua: đọc nguyên chữ
        g2p.blocked = off or g2p.blocked
        out.append(g2p)
    out.append(Component(CHOICE, PART_LABEL[CHOICE], pin(FILES), sum(item.size for item in FILES), _complete(_model_dir()), blocked=off,
                         downloads=list(FILES)))
    return out


def _judged(parts: list[Component]) -> dict[str, str]:
    """Thư viện theo dấu của mô-đun nhạc, bộ đọc chữ theo dấu của mô-đun VieNeu (nơi chúng sống), phần của mô-đun này theo dấu của nó."""
    judged = music_module.judge_parts([part for part in parts if part.id == CHOICE], _core.pins())
    for part in parts:
        if part.id == "libs":
            judged["libs"] = "current" if part.external else music_module.libs_state()
        elif part.id == "g2p":
            judged["g2p"] = "current" if part.external else vieneu_module.g2p_state()
    return judged


def _lacking(parts: list[Component], judged: dict[str, str]) -> list[Component]:
    return [part for part in parts if judged[part.id] != "current"]


def installed() -> Installed | None:
    """Nơi model nằm (cho SupertonicProvider); None khi chưa dùng được (thiếu file hay thiếu thư viện chạy model)."""
    if _core.folder is None:
        return None
    if importlib.util.find_spec("numpy") is None or importlib.util.find_spec("onnxruntime") is None:
        return None
    model = _model_dir()
    return Installed(model, word_timing.model_dir() is not None) if model is not None and _complete(model) else None


def rtf(voice: str) -> float | None:
    """Tốc độ tự đo của giọng Supertonic `voice` ("supertonic:F1") trên máy này - để "Làm trước" ước thời gian; None nếu chưa đo / giọng khác."""
    if not voice.startswith(PREFIX + ":"):
        return None
    value = (_core.benchmarks().get(TIER) or {}).get("rtf")
    return float(value) if isinstance(value, (int, float)) else None


def suggestion(bench: dict[str, Any], tiers: list[str]) -> dict[str, Any] | None:
    """Giọng đã tải mà không kịp tốc độ nghe trên máy này -> đề nghị dùng giọng trực tuyến (người dùng quyết, không bao giờ tự đổi)."""
    slow = float((bench.get(TIER) or {}).get("rtf") or 0)
    if TIER not in tiers or slow < SLOW_RTF:
        return None
    return {"tier": TIER, "rtf": slow, "switchTo": "online", "installed": True}


def status() -> dict[str, Any]:
    with _lock:
        parts = _parts()
        by_id = {part.id: part for part in parts}
        judged = _judged(parts)
        have = judged[CHOICE] != "missing" and all(judged[part.id] != "missing" for part in parts)
        behind = [part for part in _lacking(parts, judged) if judged[part.id] == "outdated"] if have else []
        facts = vieneu_module.device_facts()
        blocked = next((by_id[part].blocked for part in ("libs", "g2p") if part in by_id and judged[part] != "current" and by_id[part].blocked), "")
        if _core.state["downloading"]:
            state = "downloading"
        elif _core.state["error"]:
            state = "error"
        elif have:
            state = "outdated" if behind else "ready"
        else:
            state = "unsupported" if blocked else "missing"
        tiers = [TIER] if have else []
        bench = _core.benchmarks()
        label, detail = CHOICE_TEXT[CHOICE]
        return {
            "state": state, "done": _core.state["done"] if state == "downloading" else 0,
            "total": _core.state["total"] if state == "downloading" else 0, "error": _core.state["error"],
            "supported": not blocked, "reason": blocked,
            "choices": [{"id": CHOICE, "label": label, "detail": detail, "needs": [part.id for part in parts],
                         "bytes": sum(part.size for part in _lacking(parts, judged)), "installed": have, "recommended": False, "default": True,
                         "removable": True}],
            "parts": [{"id": part.id, "label": part.label, "bytes": part.size, "state": judged[part.id], "external": part.external}
                      for part in parts],
            "outdatedParts": [part.label for part in behind], "outdatedBytes": sum(part.size for part in behind),
            "benchmark": {TIER: bench[TIER]} if tiers and isinstance(bench.get(TIER), dict) else {},
            "benchmarking": _core.state["benchmarking"],
            "suggestion": suggestion(bench, tiers) if not _core.state["benchmarking"] else None,
            "device": facts, "recommended": CHOICE, "restart": vieneu_module._restart_pending(), "slowRtf": SLOW_RTF,
        }


# ---- tải, gỡ ----------------------------------------------------------------------------------------------------------------------
def _install(part: Component, progress: Callable[[int], None]) -> None:
    if part.id == "libs":
        music_module.install_libs_part(lambda done, _total: progress(done))
    elif part.id == "g2p":
        vieneu_module.install_g2p_part(progress)
    else:
        target = _model_dir()
        assert target is not None
        voice_module.download_files(part, target, progress)


def start(choices: list[str] | None = None) -> None:
    """Tải các phần còn thiếu hay đã cũ ở luồng nền (`choices` là None: chỉ cập nhật phần đã cũ của cái đã tải)."""
    with _lock:
        if _core.folder is None:
            raise ValueError("Mô-đun giọng Supertonic chưa được cấu hình")
        unknown = [choice for choice in choices or [] if choice not in CHOICES]
        if unknown:
            raise ValueError(f"Không có lựa chọn {unknown[0]!r}")
        if _core.busy():
            return
        parts = _parts()
        judged = _judged(parts)
        update_only = choices is None
        needed = _lacking(parts, judged)
        if update_only and judged[CHOICE] == "missing":
            needed = []  # chưa tải gì thì "cập nhật" không có gì để làm
        elif update_only:
            needed = [part for part in needed if judged[part.id] == "outdated"]
        _core.begin(needed, _install, vieneu_module._activate, lambda _changed: [TIER])


def join(timeout: float | None = None) -> None:
    _core.join(timeout)


def remove(choice: str = CHOICE) -> None:
    """Gỡ giọng Supertonic khỏi máy (file model + giọng). Thư viện chạy model và bộ đọc chữ dùng chung với mô-đun khác nên ở lại."""
    if choice not in CHOICES:
        raise ValueError(f"Không có lựa chọn {choice!r}")
    model = _model_dir()
    if model is not None:
        _core.remove(model, CHOICE, TIER)


def measure_again() -> None:
    """Người dùng bấm "Đo lại": đo lại giọng đã tải ở luồng nền."""
    _core.measure_again([TIER] if installed() is not None else [])
