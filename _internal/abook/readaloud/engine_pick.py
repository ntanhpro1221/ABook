"""Chọn máy đọc trên máy làm mặc định của "Nghe ngay" bằng SỐ ĐO của chính máy này, không theo tên hay bảng quảng cáo của hãng (luật chủ sách
03-10: VieNeu không phải đối tượng tuyệt đối; mỗi máy đọc là một nhà cung cấp cắm vào `Provider` + khung mô-đun tải khi bấm).

Một "máy đọc" = một nhóm giọng cùng model (`engine_of`): "vieneu:turbo", "vieneu:nano", "supertonic". Lượt đo (`measure`) đọc cùng bộ câu
trung tính `SENTENCES` bằng giọng đầu tiên của mỗi máy đọc, ghi:
- `rtf`: giây máy làm / giây nghe được (các khúc báo qua `model.hearing`, không tính lần đọc khởi động - lần chạy đầu của onnxruntime chậm hẳn);
- `ramMb`: RAM tiến trình tăng thêm lúc đỉnh, từ lúc chưa nạp model tới hết bộ câu (đọc RSS mỗi 20 ms);
- `loadMs`: nạp model + lần đọc khởi động;
- `cer`: tỉ lệ sai ký tự khi bộ nghe của app nghe lại audio (người gọi đưa vào, `score_clarity`); None = máy này không có bộ nghe;
- `natural`: điểm tự nhiên (UTMOSv2 của app, `score_naturalness`); None = không có bộ chấm.

Luật chọn (`choose`), viết ra để người dùng đọc được (`verdict`):
1. bỏ máy đọc đo hỏng (`error`);
2. bỏ máy đọc nghe lại sai quá `CER_GATE` (đọc nhoè / nuốt chữ) - chưa đo được độ rõ thì không loại;
3. bỏ máy đọc không kịp đọc trực tiếp (`rtf` >= `LIVE_RTF`): mặc định là cho nghe ngay, máy chậm vẫn chọn tay được ("Làm trước");
4. trong số còn lại: tự nhiên nhất; chênh dưới `NATURAL_TIE` coi như ngang (nhiễu của bộ chấm), khi ấy rõ hơn (CER thấp hơn), rồi nhanh hơn,
   rồi theo mã (để hai lần chọn trên cùng số luôn ra một).
Không còn máy đọc nào thì không có mặc định trên máy (giọng mặc định như khi chưa tải giọng nào).
"""
from __future__ import annotations

import gc
import math
import threading
import time
from typing import Any, Callable, Mapping, Sequence

from .model import hearing

# Bộ câu đo: câu kể chuyện bình thường, không số, không tên riêng, không chữ nước ngoài - đo máy đọc chứ không đo khâu chuẩn hoá chữ.
SENTENCES = (
    "Buổi sáng hôm ấy, trời trong xanh và gió thổi nhẹ qua những hàng cây.",
    "Cô bé mở cửa sổ, lặng lẽ nhìn xuống con đường vắng người bên dưới.",
    "Anh ấy im lặng một lúc lâu rồi mới chậm rãi trả lời câu hỏi.",
    "Chúng tôi đi bộ dọc bờ sông cho tới khi mặt trời lặn hẳn.",
)
WARM_UP = "Xin chào."
CER_GATE = 0.15  # nghe lại sai quá 15 % ký tự: máy đọc đang đọc nhoè / nuốt chữ, không làm mặc định
LIVE_RTF = 0.8  # từ mức này giọng khó theo kịp người nghe ở 1x (còn phải đọc trước, nghe nhanh hơn) - cũng là SLOW_RTF của các mô-đun giọng
NATURAL_TIE = 0.1  # UTMOS chênh dưới mức này: coi như ngang
SAMPLE_EVERY = 0.02


def engine_of(voice_id: str) -> str:
    """Máy đọc của một giọng: phần trước "/" khi mã có tầng ("vieneu:turbo/Đức Trí" -> "vieneu:turbo"), không thì nhà cung cấp ("supertonic:F1" -> "supertonic")."""
    head, slash, _ = voice_id.partition("/")
    return head if slash else voice_id.partition(":")[0]


def verdict(row: Mapping[str, Any]) -> str:
    """Vì sao một máy đọc không được làm mặc định: "error" (đo hỏng), "unclear" (nghe lại sai quá CER_GATE), "slow" (không kịp đọc trực tiếp); "" = đủ điều kiện."""
    if row.get("error") or not _number(row.get("rtf")) or row["rtf"] < 0:
        return "error"
    if any(row.get(key) is not None and (not _number(row[key]) or row[key] < 0) for key in ("cer", "natural")):
        return "error"
    cer = row.get("cer")
    if isinstance(cer, (int, float)) and cer > CER_GATE:
        return "unclear"
    if float(row["rtf"]) >= LIVE_RTF:
        return "slow"
    return ""


def _number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def choose(rows: Mapping[str, Mapping[str, Any]]) -> str | None:
    """Máy đọc mặc định theo luật ở đầu file; None khi không máy đọc nào đủ điều kiện."""
    fit = {engine: row for engine, row in rows.items() if not verdict(row)}
    if not fit:
        return None
    scored = [float(row["natural"]) for row in fit.values() if isinstance(row.get("natural"), (int, float))]
    if scored:
        best = max(scored)
        fit = {engine: row for engine, row in fit.items()
               if isinstance(row.get("natural"), (int, float)) and best - float(row["natural"]) < NATURAL_TIE}

    def rank(item: tuple[str, Mapping[str, Any]]) -> tuple[float, float, str]:
        engine, row = item
        cer = row.get("cer")
        return (float(cer) if isinstance(cer, (int, float)) else math.inf, float(row["rtf"]), engine)

    return min(fit.items(), key=rank)[0]


# ---- đo một máy đọc ---------------------------------------------------------------------------------------------------------------
def _rss() -> int:
    import psutil

    return int(psutil.Process().memory_info().rss)


class _Peak:
    """RSS cao nhất trong khối `with` (đọc mỗi SAMPLE_EVERY giây ở luồng phụ), so với lúc vào khối."""

    def __init__(self, read: Callable[[], int]) -> None:
        self.read = read
        self.base = self.top = read()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="engine-pick-ram", daemon=True)

    def _run(self) -> None:
        while not self._stop.wait(SAMPLE_EVERY):
            self.top = max(self.top, self.read())

    def __enter__(self) -> "_Peak":
        self._thread.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self._stop.set()
        self._thread.join()
        self.top = max(self.top, self.read())


def _settle() -> None:
    """Trả trang nhớ không dùng về cho Windows trước khi đo RAM: model vừa bỏ không bị tính cho máy đọc sau."""
    gc.collect()
    from ..resource_manager import trim_process_working_set

    trim_process_working_set()


Take = tuple[str, Any, int]  # (câu, sóng âm của câu, tần số mẫu)


def measure(speak: Callable[[str], object], sentences: Sequence[str] = SENTENCES, *, rss: Callable[[], int] = _rss,
            settle: Callable[[], None] = _settle, clock: Callable[[], float] = time.perf_counter) -> tuple[dict[str, Any], list[Take]]:
    """Đo một máy đọc đã bỏ model (người gọi `forget` trước): `speak(chữ)` đọc chữ bằng giọng đo, các khúc tới qua `model.hearing`.
    Trả (số đo: rtf, ramMb, loadMs, audioSeconds; audio từng câu để nghe lại / chấm). Máy đọc không báo khúc nào thì lỗi (ValueError)."""
    import numpy as np

    units: list[tuple[Any, int, float]] = []

    def heard(wave: Any, rate: int, _said: str, seconds: float) -> None:
        units.append((wave, rate, seconds))

    settle()
    takes: list[Take] = []
    with _Peak(rss) as peak:
        began = clock()
        with hearing(heard):
            speak(WARM_UP)
        load_ms = (clock() - began) * 1000
        units.clear()
        for text in sentences:
            start = len(units)
            with hearing(heard):
                speak(text)
            mine = units[start:]
            if not mine:
                raise ValueError("máy đọc không báo khúc nào")
            takes.append((text, np.concatenate([np.asarray(wave, dtype=np.float32).reshape(-1) for wave, _rate, _s in mine]), int(mine[0][1])))
    made = sum(seconds for _w, _r, seconds in units)
    heard_seconds = sum(len(np.asarray(wave).reshape(-1)) / rate for wave, rate, _s in units)
    if heard_seconds <= 0:
        raise ValueError("máy đọc không ra tiếng")
    return ({"rtf": round(made / heard_seconds, 3), "ramMb": round(max(0, peak.top - peak.base) / 2 ** 20), "peakRamMb": round(peak.top / 2 ** 20), "loadMs": round(load_ms),
             "audioSeconds": round(heard_seconds, 2)}, takes)


def score_clarity(takes: Sequence[Take], transcribe: Callable[[Any, int], str], similarity: Callable[[str, str], float]) -> float:
    """CER trung bình của các câu: 1 - độ giống ký tự (`similarity(chữ mong đợi, chữ nghe được)`, phép so của bộ nghe app - asr.transcript_metrics)."""
    errors = [max(0.0, 1.0 - float(similarity(text, transcribe(wave, rate)))) for text, wave, rate in takes]
    return round(sum(errors) / len(errors), 4)


def score_naturalness(takes: Sequence[Take], score: Callable[[Any, int], float]) -> float:
    """Điểm tự nhiên trung bình của các câu."""
    values = [float(score(wave, rate)) for _text, wave, rate in takes]
    return round(sum(values) / len(values), 3)


# ---- lưu theo máy -----------------------------------------------------------------------------------------------------------------
class PickStore:
    """Số đo của lần đo gần nhất trên máy này + lựa chọn tay của người dùng, một file JSON cạnh tuỳ chọn (dữ liệu của máy, không đồng bộ).
    `machine`: vài nét nhận ra máy (tên, số luồng); file nằm trên máy khác (chép cả thư mục dữ liệu) thì số đo coi như chưa có - lựa chọn tay vẫn giữ."""

    def __init__(self, path: Any, machine: Mapping[str, Any]) -> None:
        from pathlib import Path

        self.path = Path(path)
        self.machine = dict(machine)
        self._lock = threading.Lock()

    def _read(self) -> dict[str, Any]:
        import json

        try:
            data = json.loads(self.path.read_bytes().decode("utf-8"))
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def _write(self, data: dict[str, Any]) -> None:
        from .. import io_utils

        io_utils.atomic_write_json(self.path, {"version": 1, **data})

    def load(self) -> dict[str, Any]:
        """{"engines": {máy đọc: số đo}, "at", "asr", "natural", "override"}; số đo của máy khác thì `engines` rỗng."""
        with self._lock:
            data = self._read()
        engines = data.get("engines") if data.get("machine") == self.machine else None
        return {"engines": engines if isinstance(engines, dict) else {}, "at": str(data.get("at") or "") if engines else "",
                "asr": str(data.get("asr") or "") if engines else "", "natural": str(data.get("natural") or "") if engines else "",
                "override": str(data.get("override") or "")}

    def save_run(self, engines: Mapping[str, Mapping[str, Any]], *, asr: str, natural: str, at: str) -> None:
        with self._lock:
            data = self._read()
            data.update(machine=self.machine, engines={key: dict(value) for key, value in engines.items()}, asr=asr, natural=natural, at=at)
            self._write(data)

    def set_override(self, engine: str) -> None:
        """Máy đọc người dùng chọn tay ("" = theo số đo)."""
        with self._lock:
            data = self._read()
            data["override"] = engine
            self._write(data)
