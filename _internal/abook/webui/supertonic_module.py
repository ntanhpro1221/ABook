"""Mô-đun "Giọng Supertonic" của máy tính: mười giọng Supertonic 3 (Supertone, 99 triệu tham số, ONNX) đọc ngay trên máy cho "Nghe ngay", không cần
mạng. Cùng khung với "Giọng VieNeu" (voice_module.py): bộ cài không mang gì, người dùng bấm mới tải, ghim từng phần, biết phần nào cũ và chỉ tải
phần ấy, tải xong tự đo vài giây, gỡ được để lấy lại chỗ.

Các phần (`NEEDS`):
- `libs` numpy + onnxruntime: CHÍNH phần của mô-đun nhạc (music_module.libs_part).
- `g2p` sea-g2p: CHÍNH phần của mô-đun VieNeu (vieneu_module.g2p_part) - chỉ để đổi số / ngày / giờ thành chữ trước khi đọc, vì Supertonic đọc số
  kém nhất. Máy không tải được (không phải Windows 64-bit) thì bỏ phần này, giọng vẫn đọc nguyên chữ.
- `supertonic` file model + mười file giọng trên Hugging Face, ghim commit + SHA-256 từng file (`SOURCE`, `FILES`). Bộ khử nhiễu là bản int8 "top30"
  app làm từ bản fp32 của hãng (thay được trên 144 clip thử, 18-10; repo của app, voice_module.APP_MODELS) - bản fp32 không tải nữa. Bộ tạo sóng
  (vocoder) cũng là bản int8 của app (thay được cả hai bậc, 19-10; nhanh gấp đôi, 101 -> 45 MB).
- `supertonic_fast` ("Bản nhanh hơn", `FAST_FILES`): bộ khử nhiễu int8 "fast" cho bậc "Nhanh hơn" của "Tốc độ giọng trên máy" (voice_speed.py). Chỉ tải
  khi bậc ấy được chọn: lựa chọn này chỉ hiện trên thẻ khi đó (hay khi đã tải).

Hãng Supertone đã giải thể (repo lưu trữ 09-09-2026) nên trọng số là bản CUỐI: ghim đúng commit; `SOURCE` là MỘT chỗ để đổi sang bản sao của app.
Giấy phép trọng số OpenRAIL-M, mã mẫu MIT - xem THIRD_PARTY.md. Thiết bị luôn CPU (đo: RTF 0,19 ở 8 luồng, RAM ~0,53 GiB).
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from typing import Any, Callable

from ..readaloud.supertonic import FAST, OPENING_CUT, PREFIX, QUALITY, TIER, Installed
from . import music_module, vieneu_module, voice_module, voice_speed, word_timing
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
    Download("onnx/vector_estimator.onnx", voice_module.APP_MODELS + "supertonic3-int8/top30/vector_estimator.onnx",
             "30ca11e17f99f2ccb33b7d8ec7cc51df9c86c7f2df3ede6a2107b5f505d526f0", 115_904_311),
    Download("onnx/vocoder.onnx", voice_module.APP_MODELS + "supertonic3-int8/vocoder/vocoder.onnx",
             "a81b861b87697404ae897b0824801691ecaac59f6801b70c6b55b9432aa46059", 45_162_003),
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

# Bậc "Nhanh hơn" (readaloud/supertonic.FAST): một file, đặt ở FAST[0] tính từ thư mục mô-đun.
FAST_FILES = (Download(Path(FAST[0]).name, voice_module.APP_MODELS + "supertonic3-int8/fast/vector_estimator.onnx",
                       "e30ab5a4457219a8e402b52ad0ba28fab2fa658ed0027b78c298cfed25c08272", 81_526_521),)
FAST_STEPS = FAST[1]

CHOICE = "supertonic"
FAST_CHOICE = "supertonic_fast"
CHOICES = (CHOICE, FAST_CHOICE)
NEEDS = {CHOICE: ("libs", "g2p", "supertonic"), FAST_CHOICE: ("libs", "g2p", "supertonic", FAST_CHOICE)}
CHOICE_TEXT = {CHOICE: ("Giọng Supertonic", "10 giọng nam nữ, âm thanh 44 kHz - nhẹ máy, đọc nhanh hơn tốc độ nghe; số và ngày giờ được đổi thành chữ trước khi đọc"),
               FAST_CHOICE: ("Bản nhanh hơn", "Giọng Supertonic đọc nhanh hơn khi bạn nghe trực tiếp, tiếng kém hơn một chút. Sách bạn xuất ra vẫn dùng bản chất lượng cao nhất")}
PART_LABEL = {"supertonic": "Giọng Supertonic", "g2p": "Bộ đọc chữ tiếng Việt", FAST_CHOICE: "Bản nhanh hơn"}
# Cho "Tốc độ giọng trên máy" (voice_speed.status).
SPEED_NAME = "Giọng Supertonic"
SPEED_MODULE = "supertonic"

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
    return None if _core.folder is None else _core.folder / Path(QUALITY[0]).parts[0]


def _fast_dir() -> Path | None:
    return None if _core.folder is None else _core.folder / Path(FAST[0]).parent


def _complete(folder: Path | None, files: tuple[Download, ...] | None = None) -> bool:
    return folder is not None and all((folder / item.name).is_file() for item in (FILES if files is None else files))


def _download_off() -> str:
    return "tải giọng Supertonic đang bị tắt trên máy này" if os.environ.get(ENV_DOWNLOAD, "1") == "0" else ""


def _parts() -> list[Component]:
    off = _download_off()
    out = [music_module.libs_part(off or music_module.libs_problem())]
    g2p = vieneu_module.g2p_part()
    if g2p.present or g2p.external or sys.platform == "win32":  # nơi sea-g2p không có sẵn bản tải thì bỏ qua: đọc nguyên chữ
        g2p.blocked = off or g2p.blocked
        out.append(g2p)
    model, fast = _model_dir(), _fast_dir()
    out.append(Component(CHOICE, PART_LABEL[CHOICE], pin(FILES), sum(item.size for item in FILES), _complete(model), blocked=off,
                         downloads=list(FILES), targets=[model / item.name for item in FILES] if model is not None else []))
    out.append(Component(FAST_CHOICE, PART_LABEL[FAST_CHOICE], pin(FAST_FILES), sum(item.size for item in FAST_FILES),
                         _complete(fast, FAST_FILES), blocked=off, downloads=list(FAST_FILES),
                         targets=[fast / item.name for item in FAST_FILES] if fast is not None else []))
    return out


def _judged(parts: list[Component]) -> dict[str, str]:
    """Thư viện theo dấu của mô-đun nhạc, bộ đọc chữ theo dấu của mô-đun VieNeu (nơi chúng sống), phần của mô-đun này theo dấu của nó."""
    judged = music_module.judge_parts([part for part in parts if part.id in CHOICES], _core.pins())
    for part in parts:
        if part.id == "libs":
            judged["libs"] = "current" if part.external else music_module.libs_state()
        elif part.id == "g2p":
            judged["g2p"] = "current" if part.external else vieneu_module.g2p_state()
    return judged


def _lacking(parts: list[Component], judged: dict[str, str], choices: tuple[str, ...] | list[str] = (CHOICE,)) -> list[Component]:
    """Các phần (không trùng) mà những lựa chọn này còn thiếu hay đã cũ."""
    wanted = {part for choice in choices for part in NEEDS[choice]}
    return [part for part in parts if part.id in wanted and judged[part.id] != "current"]


def installed() -> Installed | None:
    """Nơi model nằm (cho SupertonicProvider); None khi chưa dùng được (thiếu file hay thiếu thư viện chạy model)."""
    if _core.folder is None:
        return None
    if importlib.util.find_spec("numpy") is None or importlib.util.find_spec("onnxruntime") is None:
        return None
    model = _model_dir()
    return Installed(model, word_timing.model_dir() is not None) if model is not None and _complete(model) else None


def locate() -> Installed | None:
    """Cho Studio (tiến trình dây chuyền không gọi `configure`): mô-đun ở chỗ mặc định cạnh preferences.json, như server đặt."""
    _core.ensure_folder(FOLDER)
    return installed()


def installed_fast() -> Installed | None:
    """Như `installed` nhưng đọc bằng bậc "Nhanh hơn" (bộ khử nhiễu + số bước của supertonic.FAST); None khi file bậc ấy chưa tải."""
    found = installed()
    fast = _fast_dir()
    if found is None or fast is None or not _complete(fast, FAST_FILES):
        return None
    return Installed(found.folder, found.aligner, estimator=fast / FAST_FILES[0].name, steps=FAST_STEPS)


# ---- cho "Tốc độ giọng trên máy" (voice_speed.py) -------------------------------------------------------------------------------------
def speed_installed() -> bool:
    return installed() is not None


def speed_rtf() -> float | None:
    """Tốc độ tự đo của bậc chất lượng (lần đo sau khi tải luôn đo bậc này)."""
    value = (_core.benchmarks().get(TIER) or {}).get("rtf")
    return float(value) if isinstance(value, (int, float)) else None


def speed_fast_ready() -> bool:
    return installed_fast() is not None


def speed_fast_bytes() -> int:
    """Byte "Bản nhanh hơn" còn phải tải (phần dở sau Huỷ không tính lại)."""
    return next(part for part in _parts() if part.id == FAST_CHOICE).left()


def rtf(voice: str) -> float | None:
    """Tốc độ tự đo của giọng Supertonic `voice` ("supertonic:F1") trên máy này - để "Làm trước" ước thời gian; None nếu chưa đo / giọng khác."""
    if not voice.startswith(PREFIX + ":"):
        return None
    value = (_core.benchmarks().get(TIER) or {}).get("rtf")
    return float(value) if isinstance(value, (int, float)) else None


def model_mark(voice: str, tier: str) -> str:
    """Dấu model của clip giọng Supertonic `voice` ở bậc `tier` (dấu bậc của ReadAloud: "" = chất lượng, "fast<n>" = nhanh) cho khoá bộ đệm: ghim phần model
    (bậc nhanh: cả phần "Bản nhanh hơn" - nó dùng chung các file còn lại) + bậc + số bước. "" cho giọng khác."""
    if not voice.startswith(PREFIX + ":"):
        return ""
    if tier:
        return _core.mark((CHOICE, FAST_CHOICE), f"fast:{FAST[1]}:open{OPENING_CUT}")
    return _core.mark((CHOICE,), f"quality:{QUALITY[1]}:open{OPENING_CUT}")


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
        have = all(judged[part] != "missing" for part in NEEDS[CHOICE] if part in judged)
        fast_here = have and judged[FAST_CHOICE] != "missing"
        behind = [part for part in _lacking(parts, judged, CHOICES if fast_here else (CHOICE,)) if judged[part.id] == "outdated"] if have else []
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
        # cỡ trên nút tải / cập nhật = phần CÒN phải tải (file đúng đã có, phần dở sau Huỷ không tính lại); phần đủ rồi thì cỡ cả phần
        left = {part.id: part.size if judged[part.id] == "current" else part.left() for part in parts}
        shown = [CHOICE]
        if fast_here or (have and voice_speed.wants_fast("supertonic")):
            shown.append(FAST_CHOICE)  # chỉ khi "Tốc độ giọng trên máy" muốn bậc nhanh (hay đã tải): không ai phải tải thứ không dùng
        choices = []
        for choice in shown:
            label, detail = CHOICE_TEXT[choice]
            lacking = _lacking(parts, judged, (choice,))
            if choice == FAST_CHOICE:
                lacking = [part for part in lacking if part.id == FAST_CHOICE]  # cỡ riêng của nó; Giọng Supertonic có dòng của mình
            choices.append({"id": choice, "label": label, "detail": detail, "needs": [part.id for part in parts if part.id in NEEDS[choice]],
                            "bytes": sum(left[part.id] for part in lacking), "installed": fast_here if choice == FAST_CHOICE else have,
                            "recommended": False, "default": True, "removable": True, **({"requires": [CHOICE]} if choice == FAST_CHOICE else {})})
        return {
            "state": state, "done": _core.state["done"] if state == "downloading" else 0, "retrying": _core.retrying(),
            "total": _core.state["total"] if state == "downloading" else 0, "error": _core.state["error"],
            "errorDetail": _core.state.get("error_detail", "") if _core.state["error"] else "",
            "supported": not blocked, "reason": blocked,
            "choices": choices,
            "parts": [{"id": part.id, "label": part.label, "bytes": left[part.id], "state": judged[part.id], "external": part.external}
                      for part in parts],
            "outdatedParts": [part.label for part in behind], "outdatedBytes": sum(left[part.id] for part in behind),
            "benchmark": {TIER: bench[TIER]} if tiers and isinstance(bench.get(TIER), dict) else {},
            "benchmarking": _core.state["benchmarking"],
            "suggestion": suggestion(bench, tiers) if not _core.state["benchmarking"] else None,
            "cancelled": bool(_core.state["cancelled"]), "device": facts, "recommended": CHOICE, "restart": vieneu_module._restart_pending(), "slowRtf": SLOW_RTF,
        }


# ---- tải, gỡ ----------------------------------------------------------------------------------------------------------------------
def _install(part: Component, progress: Callable[[int], None]) -> None:
    if part.id == "libs":
        music_module.install_libs_part(lambda done, _total: progress(done), _core.cancelled)
    elif part.id == "g2p":
        vieneu_module.install_g2p_part(progress, _core.cancelled)
    else:
        target = _fast_dir() if part.id == FAST_CHOICE else _model_dir()
        assert target is not None
        voice_module.download_files(part, target, progress, _core.cancelled)


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
        if choices is None:
            # "Cập nhật": phần đã cũ của những gì đã tải (chưa tải gì thì không có gì để làm)
            have = [choice for choice in CHOICES if judged[CHOICE] != "missing" and judged[choice] != "missing"]
            needed = [part for part in _lacking(parts, judged, have) if judged[part.id] == "outdated"]
        else:
            needed = _lacking(parts, judged, choices)
        # Lần tự đo chỉ đo bậc chất lượng (voice_speed: "Tự động" chọn theo nó): tải riêng bản nhanh hơn thì không đo lại.
        _core.begin(needed, _install, vieneu_module._activate, lambda changed: [TIER] if changed & set(NEEDS[CHOICE]) else [])


def join(timeout: float | None = None) -> None:
    _core.join(timeout)


def cancel() -> None:
    """Người dùng bấm Huỷ khi đang tải: dừng giữa chừng, phần đã tải được giữ để lần sau làm tiếp."""
    _core.cancel()


def remove(choice: str = CHOICE) -> None:
    """Gỡ giọng Supertonic khỏi máy (file model + giọng, và bản nhanh hơn đi theo), hay chỉ bản nhanh hơn (`FAST_CHOICE`). Thư viện chạy model và bộ đọc
    chữ dùng chung với mô-đun khác nên ở lại."""
    if choice not in CHOICES:
        raise ValueError(f"Không có lựa chọn {choice!r}")
    model, fast = _model_dir(), _fast_dir()
    if model is not None and choice == CHOICE:
        _core.remove(model, CHOICE, TIER)
    if fast is not None and (choice == FAST_CHOICE or fast.exists() or FAST_CHOICE in _core.pins()):
        _core.remove(fast, FAST_CHOICE, "")


def measure_again() -> None:
    """Người dùng bấm "Đo lại": đo lại giọng đã tải ở luồng nền."""
    _core.measure_again([TIER] if installed() is not None else [])
