"""Cài đặt "Tốc độ giọng trên máy" (một cho cả máy): giọng Supertonic và VieNeu Nano có hai bậc khi nghe trực tiếp - "Chất lượng cao nhất" và "Nhanh
hơn" (bộ khử nhiễu int8 nhỏ hơn, ít bước hơn: readaloud/supertonic.FAST, vieneu_module.NANO_FAST). `auto` (mặc định): máy tự chọn theo lần tự đo sau
khi tải - lần đo ấy đo bậc chất lượng; RTF dưới SLOW_RTF thì giữ chất lượng, không thì "Nhanh hơn". Người dùng chọn hẳn một bậc thì luôn theo đó;
"Tự động" chỉ đổi giữa hai bậc của cùng một giọng, không bao giờ đổi sang giọng khác.

Bậc chỉ áp cho Nghe ngay. Studio và mọi bản xuất (sách nói, MP3 / M4B) luôn đọc bậc chất lượng (`ReadAloud.clip(quality=True)`); clip bậc nhanh có dấu
riêng trong khoá bộ đệm (`live_tag`) nên không bao giờ đứng thay clip chất lượng. File bậc nhanh chỉ tải khi bậc ấy được chọn (thẻ mô-đun hiện lựa
chọn "Bản nhanh hơn" kèm cỡ của nó); chưa tải thì Nghe ngay vẫn đọc bậc chất lượng. Điện thoại: VoiceSpeed.kt, cùng luật, cùng hình trạng thái.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from .. import io_utils

FILE = "voice-speed.json"
AUTO, QUALITY, FAST = "auto", "quality", "fast"
CHOICES = (AUTO, QUALITY, FAST)
FAMILIES = ("supertonic", "nano")  # giọng có hai bậc: mười giọng Supertonic, các giọng VieNeu Nano

_lock = threading.Lock()
_path: Path | None = None


def configure(path: Path | str | None) -> None:
    """File lưu lựa chọn (server.py: cạnh preferences.json). None = chưa cấu hình: luôn "Tự động"."""
    global _path
    with _lock:
        _path = Path(path) if path is not None else None


def choice() -> str:
    with _lock:
        path = _path
    if path is None:
        return AUTO
    try:
        value = json.loads(path.read_bytes().decode("utf-8")).get("choice")
    except (OSError, ValueError, AttributeError):
        return AUTO
    return value if value in CHOICES else AUTO


def set_choice(value: str) -> None:
    if value not in CHOICES:
        raise ValueError(f"Không có lựa chọn {value!r}")
    with _lock:
        if _path is None:
            raise ValueError("Cài đặt tốc độ giọng chưa được cấu hình")
        io_utils.atomic_write_json(_path, {"version": 1, "choice": value})


def decide(chosen: str, rtf: float | None) -> str:
    """Bậc mà lựa chọn `chosen` muốn cho một giọng đo được `rtf` (bậc chất lượng; None = chưa đo -> giữ chất lượng)."""
    from .vieneu_module import SLOW_RTF  # mức chung của mọi giọng trên máy (nhập muộn: mô-đun giọng nhập file này)

    if chosen in (QUALITY, FAST):
        return chosen
    return FAST if rtf is not None and rtf >= SLOW_RTF else QUALITY


def family(voice_id: str) -> str:
    """"supertonic" / "nano" cho giọng có hai bậc, "" cho giọng khác."""
    if voice_id.startswith("supertonic:"):
        return "supertonic"
    return "nano" if voice_id.startswith("vieneu:nano/") else ""


def _module(name: str) -> Any:
    from . import supertonic_module, vieneu_module

    return supertonic_module if name == "supertonic" else vieneu_module


def wants_fast(name: str) -> bool:
    """Lựa chọn hiện tại muốn bậc nhanh cho giọng `name` (để thẻ mô-đun mời tải "Bản nhanh hơn")."""
    return decide(choice(), _module(name).speed_rtf()) == FAST


def live_tag(voice_id: str) -> str:
    """Dấu bậc của clip Nghe ngay bằng `voice_id` trong khoá bộ đệm: "fast<số bước>" khi đang đọc bậc nhanh (lựa chọn muốn và file đã tải), "" khi
    đọc bậc chất lượng hay giọng không có bậc. Cũng là cái `ReadAloud.clip` hỏi để chọn engine."""
    name = family(voice_id)
    if not name:
        return ""
    module = _module(name)
    if decide(choice(), module.speed_rtf()) != FAST or not module.speed_fast_ready():
        return ""
    return f"fast{module.FAST_STEPS}"


def status() -> dict[str, Any]:
    """Cho dòng cài đặt: lựa chọn + mỗi giọng có hai bậc đã tải trên máy: bậc muốn (`tier`), bậc đang đọc (`using`), số đo, cỡ file bậc nhanh còn thiếu."""
    chosen = choice()
    voices = []
    for name in FAMILIES:
        module = _module(name)
        if not module.speed_installed():
            continue
        rtf = module.speed_rtf()
        tier = decide(chosen, rtf)
        ready = module.speed_fast_ready()
        voices.append({"id": name, "name": module.SPEED_NAME, "module": module.SPEED_MODULE, "fastChoice": module.FAST_CHOICE,
                       "rtf": rtf, "tier": tier, "using": FAST if tier == FAST and ready else QUALITY,
                       "fastBytes": 0 if ready else module.speed_fast_bytes()})
    return {"choice": chosen, "voices": voices}
