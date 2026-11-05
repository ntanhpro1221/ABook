"""Thẻ "Giọng theo máy" của Cài đặt (máy tính): đo mọi máy đọc trên máy đã tải (VieNeu Turbo / Nano, Supertonic, máy đọc cắm thêm sau này) trên
cùng bộ câu, chọn máy đọc mặc định của "Nghe ngay" theo luật viết sẵn (readaloud/engine_pick.py), người dùng chọn tay được.

Đo gì, bằng gì (tất cả trên CPU của máy này, ở luồng nền):
- tốc độ, RAM, thời gian nạp: `ReadAloud.measure_engine` (engine_pick.measure);
- độ rõ (CER): bộ nghe của app nghe lại audio - Whisper của Studio (asr.WhisperVerifier, trên CPU) khi máy có, không thì bộ căn chữ wav2vec2
  (word_timing, giải mã CTC tham lam); phép so chữ là của bộ nghe (asr.transcript_metrics). Máy không có bộ nghe nào: độ rõ "chưa đo";
- tự nhiên: UTMOSv2 của Studio (perceptual_qa) khi máy có; không thì "chưa đo".
Một lượt đo luôn đo LẠI MỌI máy đọc (cùng bộ nghe, cùng bộ chấm trong một lượt - số mới so được với nhau). Tự đo khi một mô-đun giọng vừa tải /
cập nhật xong mà số đo đã cũ (voice_module.on_measured); hay khi người dùng bấm "Đo".
"""
from __future__ import annotations

import os
import platform
import shutil
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from ..readaloud import engine_pick

FILE = "voice-pick.json"
# (tên bộ, hàm (sóng, tần số) -> kết quả, hàm nhả bộ) hay None khi máy không có.
Judge = tuple[str, Callable[[Any, int], Any], Callable[[], None]]

_lock = threading.RLock()
_store: engine_pick.PickStore | None = None
_readaloud: Any = None
_marks: Callable[[str], str] = lambda _voice: ""
_asr: Callable[[], Judge | None] = lambda: None
_natural: Callable[[], Judge | None] = lambda: None
_similarity: Callable[[], Callable[[str, str], float] | None] | None = None
_state: dict[str, Any] = {"measuring": False, "done": 0, "total": 0, "engine": "", "error": ""}
_thread: threading.Thread | None = None
_studio: Callable[[], Any] = lambda: None


def machine() -> dict[str, Any]:
    return {"name": platform.node(), "cores": os.cpu_count() or 1}


def configure(path: Path | str | None, readaloud: Any, *, marks: Callable[[str], str] = lambda _voice: "",
              asr: Callable[[], Judge | None] | None = None, natural: Callable[[], Judge | None] | None = None,
              similarity: Callable[[], Callable[[str, str], float] | None] | None = None,
              studio: Callable[[], Any] = lambda: None) -> None:
    """server.py: file số đo cạnh preferences.json, ReadAloud, `marks(giọng)` = dấu model của giọng (đổi model thì số đo cũ). `asr` / `natural` /
    `similarity`: nạp bộ nghe / bộ chấm tự nhiên / phép so chữ (bỏ trống = của app: `default_asr`, `utmos_judge`, `default_similarity`; bộ kiểm đưa bộ giả).
    Bộ nghe và bộ chấm nạp lần lượt lúc chấm, nhả ngay sau đó - không cùng lúc với nhau hay với máy đọc."""
    global _store, _readaloud, _marks, _asr, _natural, _similarity, _studio
    with _lock:
        _store = engine_pick.PickStore(path, machine()) if path is not None else None
        _readaloud, _marks = readaloud, marks
        _asr, _natural, _similarity = asr or default_asr, natural or utmos_judge, similarity or default_similarity
        _studio = studio
        _state.update(measuring=False, done=0, total=0, engine="", error="")


# ---- trạng thái ---------------------------------------------------------------------------------------------------------------------
def _snapshot() -> dict[str, Any]:
    installed: dict[str, list[str]] = _readaloud.local_engines() if _readaloud is not None else {}
    saved = _store.load() if _store is not None else {"engines": {}, "override": "", "at": "", "asr": "", "natural": ""}
    rows, measured = [], {}
    for engine, voices in installed.items():
        row = saved["engines"].get(engine)
        fresh = isinstance(row, dict) and row.get("voice") in voices and row.get("mark", "") == _marks(str(row.get("voice")))
        if fresh:
            measured[engine] = row
        shown = row if fresh else {}
        rows.append({"engine": engine, "voice": voices[0], "measured": fresh, "verdict": engine_pick.verdict(shown) if fresh else "",
                     **{key: shown.get(key) for key in ("rtf", "ramMb", "peakRamMb", "loadMs", "cer", "natural")}, "error": str(shown.get("error") or "")})
    auto = engine_pick.choose(measured) if measured else None
    override = saved["override"] if saved["override"] in installed else ""
    # None = chưa đo gì (giọng mặc định như trước khi có số), "" = đã đo mà không máy đọc nào đủ điều kiện.
    chosen = override or (auto if auto is not None else ("" if measured else None))
    return {"rows": rows, "auto": auto, "override": override, "chosen": chosen, "stale": len(measured) < len(installed), "saved": saved}


def chosen() -> str | None:
    """Máy đọc mặc định trên máy này cho ReadAloud(machine_pick=...): mã máy đọc, "" = đã đo mà không máy đọc nào đủ điều kiện, None = chưa đo."""
    with _lock:
        return _snapshot()["chosen"] if _readaloud is not None else None


def status() -> dict[str, Any]:
    with _lock:
        if _readaloud is None or _store is None:
            return {"state": "unsupported", "engines": [], "auto": None, "override": "", "chosen": None}
        snap = _snapshot()
        saved = snap["saved"]
        state = "measuring" if _state["measuring"] else "empty" if not snap["rows"] else "stale" if snap["stale"] else "ready"
        return {"state": state, "engines": snap["rows"], "auto": snap["auto"], "override": snap["override"], "chosen": snap["chosen"],
                "asr": saved["asr"], "natural": saved["natural"], "at": saved["at"], "done": _state["done"], "total": _state["total"],
                "measuring": _state["engine"] if _state["measuring"] else "", "error": _state["error"],
                "liveRtf": engine_pick.LIVE_RTF, "cerGate": engine_pick.CER_GATE}


def set_override(engine: str) -> None:
    """Người dùng chọn tay máy đọc mặc định ("" = theo số đo)."""
    with _lock:
        if _store is None or _readaloud is None:
            raise ValueError("Chưa đo được giọng trên máy này")
        if engine and engine not in _readaloud.local_engines():
            raise ValueError("Giọng này chưa tải trên máy")
        _store.set_override(engine)


# ---- đo -----------------------------------------------------------------------------------------------------------------------------
def start(only_if_stale: bool = False) -> None:
    """Đo lại mọi máy đọc ở luồng nền. `only_if_stale`: chỉ khi có máy đọc chưa có số đo hợp lệ (vừa tải / cập nhật model). Đang đo thì thôi."""
    global _thread
    with _lock:
        if _readaloud is None or _store is None or _state["measuring"]:
            return
        snap = _snapshot()
        if not snap["rows"] or (only_if_stale and not snap["stale"]):
            return
        _state.update(measuring=True, done=0, total=len(snap["rows"]), engine="", error="")
        _thread = threading.Thread(target=_run, name="voice-pick", daemon=True)
        _thread.start()


def module_measured() -> None:
    """voice_module.on_measured: một mô-đun giọng vừa tự đo xong (vừa tải / cập nhật) - đo lại các máy đọc nếu số đo đã cũ."""
    start(only_if_stale=True)


def join(timeout: float | None = None) -> None:
    thread = _thread
    if thread is not None:
        thread.join(timeout)


def _run() -> None:
    try:
        engines = _readaloud.local_engines()
        results: dict[str, dict[str, Any]] = {}
        takes: dict[str, list[engine_pick.Take]] = {}
        for index, (engine, voices) in enumerate(engines.items()):
            while _readaloud.live:  # người đang nghe: không tranh CPU với họ (và số tốc độ đo lúc ấy sai)
                time.sleep(0.5)
            with _lock:
                _state.update(done=index, engine=engine)
            voice = voices[0]
            row: dict[str, Any] = {"voice": voice, "mark": _marks(voice)}
            try:
                numbers, takes[engine] = _readaloud.measure_engine(voice)
                row.update(numbers)
            except Exception as error:  # noqa: BLE001 - máy đọc đo hỏng: ghi lý do, không làm mặc định, các máy đọc khác vẫn đo
                row["error"] = str(error)[:300] or type(error).__name__
            results[engine] = row
        with _lock:
            _state.update(done=len(engines), engine="")
        studio = _studio()
        if takes and studio is not None and studio.python.is_file():
            try:
                asr_name, natural_name = score_in_studio(studio, takes, results)
            except Exception as error:  # noqa: BLE001 - keep genuine synthesis measurements when the optional scorer fails
                asr_name, natural_name = "", ""
                with _lock:
                    _state["error"] = f"Chưa nghe lại và chấm được: {error}"
        else:
            similarity = _similarity() if takes else None
            asr_name = _score(_asr() if similarity else None, takes, results, "cer",
                              lambda own, take: engine_pick.score_clarity(take, own, similarity))  # type: ignore[arg-type]
            natural_name = _score(_natural() if takes else None, takes, results, "natural", lambda own, take: engine_pick.score_naturalness(take, own))
        assert _store is not None
        _store.save_run(results, asr=asr_name, natural=natural_name, at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    except Exception as error:  # noqa: BLE001 - mọi lỗi thành một câu
        with _lock:
            _state["error"] = f"Không đo được giọng trên máy này: {error}"
    finally:
        with _lock:
            _state.update(measuring=False, engine="")


def _score(judge: Judge | None, takes: dict[str, list[engine_pick.Take]], results: dict[str, dict[str, Any]], key: str,
           score: Callable[[Callable[[Any, int], Any], list[engine_pick.Take]], float]) -> str:
    """Chấm audio đã đo của mọi máy đọc bằng một bộ (nạp một lần, nhả sau đó); trả tên bộ ("" = không có). Bộ hỏng giữa chừng ở một máy đọc thì máy
    đọc ấy "chưa đo" mục này."""
    if judge is None:
        return ""
    name, run, close = judge
    try:
        for engine, take in takes.items():
            try:
                results[engine][key] = score(run, take)
            except Exception:  # noqa: BLE001
                results[engine][key] = None
    finally:
        close()
    return name


def score_in_studio(studio: Any, takes: dict[str, list[engine_pick.Take]], results: dict[str, dict[str, Any]]) -> tuple[str, str]:
    """The packaged UI has no torch/Whisper; reuse the installed optional Studio interpreter, without installing anything."""
    import json
    import subprocess

    from ..readaloud.vieneu import wav_bytes

    with tempfile.TemporaryDirectory(prefix="abook-voice-pick-") as folder:
        root = Path(folder)
        request: dict[str, list[dict[str, str]]] = {}
        for index, (engine, clips) in enumerate(takes.items()):
            request[engine] = []
            for number, (text, wave, rate) in enumerate(clips):
                path = root / f"{index}-{number}.wav"
                path.write_bytes(wav_bytes(wave, rate))
                request[engine].append({"text": text, "file": str(path)})
        source, target = root / "request.json", root / "scores.json"
        source.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")
        environment = {**os.environ, **studio.environment(), "CUDA_VISIBLE_DEVICES": "-1", "QT_QPA_PLATFORM": "offscreen",
                       "OMP_NUM_THREADS": "2", "MKL_NUM_THREADS": "2", "PYTHONDONTWRITEBYTECODE": "1",
                       "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"}
        with (root / "judge.log").open("w", encoding="utf-8") as log:
            subprocess.run([str(studio.python), "-X", "utf8", "-m", "abook.webui.voice_pick_worker", str(source), str(target)],
                           env=environment, stdout=log, stderr=log, timeout=600, check=True,
                           creationflags=(subprocess.CREATE_NO_WINDOW | subprocess.BELOW_NORMAL_PRIORITY_CLASS) if os.name == "nt" else 0)
        scored = json.loads(target.read_text(encoding="utf-8"))
        for engine, row in results.items():
            row.update(scored["engines"].get(engine, {}))
        return scored["asr"], scored["natural"]


# ---- bộ nghe / bộ chấm của app -----------------------------------------------------------------------------------------------------
def default_similarity() -> Callable[[str, str], float] | None:
    """Phép so chữ của bộ nghe (asr.transcript_metrics: chuẩn hoá số, chữ Anh...); None khi Python này không nạp được asr (thiếu soundfile)."""
    try:
        from ..asr import transcript_metrics
    except Exception:  # noqa: BLE001
        return None
    return lambda expected, heard: transcript_metrics(expected, heard)[0]


def _wav_file(wave: Any, rate: int, folder: str) -> Path:
    import soundfile

    path = Path(folder) / f"take-{time.perf_counter_ns()}.wav"
    soundfile.write(str(path), wave, int(rate))
    return path


def _settings() -> dict[str, Any]:
    from ..config import build_settings

    # Bộ nghe / bộ chấm chạy CPU: GPU có thể đang bận việc khác, và số đo là của máy người dùng, không phải của card.
    return build_settings(overrides={"asr": {"device": "cpu"},
                                     "perceptual_qa": {"enabled": True, "device": "cpu"}})


def whisper_judge() -> Judge | None:
    try:
        from ..asr import WhisperVerifier

        verifier = WhisperVerifier(_settings(), lambda _message: None)
        if not verifier.load():
            return None
    except Exception:  # noqa: BLE001 - máy không có Whisper của Studio
        return None
    folder = tempfile.mkdtemp(prefix="abook-voice-pick-")

    def transcribe(wave: Any, rate: int) -> str:
        path = _wav_file(wave, rate, folder)
        try:
            return verifier.transcribe(path)
        finally:
            path.unlink(missing_ok=True)

    return "whisper", transcribe, lambda: (verifier.unload(), shutil.rmtree(folder, ignore_errors=True))


def ctc_judge() -> Judge | None:
    """Bộ căn chữ wav2vec2 (word_timing) làm bộ nghe: giải mã CTC tham lam (khung có xác suất cao nhất, gộp lặp, bỏ ký tự trống, "|" là dấu cách)."""
    from . import word_timing

    aligner = word_timing.get_aligner()
    if aligner is None:
        return None
    from ..readaloud.vieneu import resample

    letters = {index: token for token, index in aligner.vocab.items() if not (token.startswith("<") and token.endswith(">"))}

    def transcribe(wave: Any, rate: int) -> str:
        best = aligner.emissions(resample(wave, rate)).argmax(-1)
        picked = [int(frame) for at, frame in enumerate(best) if frame != aligner.blank and (at == 0 or frame != best[at - 1])]
        return "".join(letters.get(frame, "") for frame in picked).replace("|", " ").strip()

    return "wav2vec2", transcribe, lambda: None


def utmos_judge() -> Judge | None:
    try:
        from ..perceptual_qa import UTMOSNaturalnessVerifier

        verifier = UTMOSNaturalnessVerifier(_settings(), lambda _message: None)
        if not verifier.load():
            return None
    except Exception:  # noqa: BLE001 - máy không có UTMOSv2 của Studio
        return None
    folder = tempfile.mkdtemp(prefix="abook-voice-pick-")

    def score(wave: Any, rate: int) -> float:
        path = _wav_file(wave, rate, folder)
        try:
            return float(verifier._score(path))  # noqa: SLF001 - cùng phép chấm với bộ chấm của Studio (perceptual_qa._score_worker_job)
        finally:
            path.unlink(missing_ok=True)

    return "utmosv2", score, lambda: (verifier.unload(), shutil.rmtree(folder, ignore_errors=True))


def default_asr() -> Judge | None:
    """Bộ nghe tốt nhất máy có: Whisper của Studio, không thì bộ căn chữ wav2vec2."""
    return whisper_judge() or ctc_judge()
