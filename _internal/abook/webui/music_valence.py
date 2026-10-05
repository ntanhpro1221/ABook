"""V hợp cho Nhạc của tôi - "Đo cảm xúc nhạc chính xác hơn" (tuỳ chọn, máy tính; docs/MUSIC_RESEARCH.md, đường (a)).

Đầu trò (music_student.py) chỉ nghe bằng CLAP, nên thang V của nó thiếu phần MuQ mà danh mục có. Bật tuỳ chọn này thì mỗi bài nhập được đo thêm
bằng tháp âm thanh MuQ-MuLan (OpenMuQ, Zhu et al. 2025, CC BY-NC 4.0; ONNX fp32 1,27 GB, onnxruntime CPU) và valence của bài là V hợp, tính đúng như
danh mục (hằng số + 101 phân vị trong `muq/vhop_scale.json`, vector chữ trong `muq/valence_text.npz`, cả hai nằm cạnh tháp trên Hugging Face):
  1. CLAP: `100 * (mean(e_c . Tc[0:4]) - mean(e_c . Tc[4:8]))`, e_c = vector nhúng CLAP của bài (music_student.clap_embedding);
  2. MuQ: ba cửa sổ 10 giây mono 24 kHz (cùng cách cắt với CLAP, music_student.audio_windows; cửa sổ ngắn nối vòng từ đầu cho đủ 240.000 mẫu như
     `MuQMuLan._get_all_clips`) -> `latent` 512 chiều, L2 từng cửa sổ -> trung bình -> L2 = e_m; `mean(e_m . Tm[0:4]) - mean(e_m . Tm[4:8])`;
  3. `v_raw = 0,5 * (clap - mean) / sd + 0,5 * (muq - mean) / sd`, rồi đổi sang hạng: `interp(v_raw, 101 phân vị, linspace(-1, 1, 101))`.
Bài mang V hợp KHÔNG áp CALIBRATION["valence"] và không có `vetVar.valence` - nó đã cùng thang với danh mục. E/T và 13 cảm xúc vẫn của đầu trò.

Chạy nền: lúc nhập, music_local ghi ngay số của đầu trò (như khi chưa bật); luồng này (CPU, 2 luồng ORT, ưu tiên thấp, tháp chỉ nạp trong lúc có
việc) ghi đè `valence` rồi đánh dấu `analysis["valenceBy"] = VERSION`. Bài chưa tới lượt vẫn dùng V của đầu trò. Làm tiếp được và làm lại không hại:
chỉ bài chưa mang VERSION hiện tại mới bị đo (phân tích lại bằng đầu trò thay cả mục nên mất dấu và bài được đo lại). Đổi tháp / vector chữ /
hằng số thì đổi VERSION.

Tuỳ chọn, mặc định TẮT: tháp (1,27 GB) chỉ tải khi người dùng bật (`enable`), và chỉ được bật trên máy từ `MIN_RAM_BYTES` RAM (đo 05-10: đỉnh 1,52 GiB
cả tiến trình, 2 luồng ~5 giây mỗi bài). Cần "Phân tích nhạc" (music_module) đã sẵn sàng - V hợp dùng lại vector nhúng CLAP của nó.
"""
from __future__ import annotations

import contextlib
import gc
import json
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from . import music_local, music_module, music_student, voice_module

VERSION = "vhop1"
MIN_RAM_BYTES = int(7.5 * 1024 ** 3)  # máy "8 GB" báo ~7,4-7,9 GiB (một phần RAM dành cho phần cứng)
MUQ_RATE = 24_000
MUQ_SAMPLES = 240_000  # cửa sổ 10 giây
THREADS = 2  # luồng ORT: ~5 giây một bài, không chiếm cả CPU của máy người dùng
_LOWEST = -2  # THREAD_PRIORITY_LOWEST

_lock = threading.RLock()
_store: music_local.LocalMusic | None = None
_get_enabled: Callable[[], bool] = lambda: False
_set_enabled: Callable[[bool], None] = lambda value: None
_state: dict[str, Any] = {"downloading": False, "done": 0, "total": 0, "error": "", "working": False, "left": 0}
_thread: threading.Thread | None = None
_again = False


def configure(store: music_local.LocalMusic | None, get_enabled: Callable[[], bool], set_enabled: Callable[[bool], None]) -> None:
    """server.py: kho nhạc của máy + chỗ nhớ công tắc (preferences `preciseMusicMood`). Quên việc đang chạy của lần trước (bài thử)."""
    global _store, _get_enabled, _set_enabled, _again
    with _lock:
        _store, _get_enabled, _set_enabled, _again = store, get_enabled, set_enabled, False
        _state.update(downloading=False, done=0, total=0, error="", working=False, left=0)


# ---- phép tính --------------------------------------------------------------------------------------------------------------------
@dataclass
class Reference:
    """Hằng số của V hợp (muq/valence_text.npz + muq/vhop_scale.json)."""

    clap_text: Any  # (8, 512): 4 chữ dương rồi 4 chữ âm, đã chuẩn hoá L2
    muq_text: Any
    clap_mean: float
    clap_sd: float
    muq_mean: float
    muq_sd: float
    quantiles: Any  # (101,) v_raw của danh mục theo hạng -1..1


def load_reference(directory: Path) -> Reference:
    import numpy as np

    with np.load(directory / "muq" / "valence_text.npz") as text:
        clap_text, muq_text = text["clap_valence_text"].astype(np.float64), text["muq_valence_text"].astype(np.float64)
    scale = json.loads((directory / "muq" / "vhop_scale.json").read_text(encoding="utf-8"))
    return Reference(clap_text, muq_text,
                     scale["clap_valence_raw"]["mean"], scale["clap_valence_raw"]["sd"],
                     scale["muq_valence_raw"]["mean"], scale["muq_valence_raw"]["sd"], np.array(scale["v_raw_quantiles_101"], dtype=np.float64))


def clap_raw(embedding: Any, ref: Reference) -> float:
    sims = ref.clap_text @ embedding
    return float(100.0 * (sims[:4].mean() - sims[4:8].mean()))


def muq_raw(embedding: Any, ref: Reference) -> float:
    sims = ref.muq_text @ embedding  # KHÔNG nhân 100
    return float(sims[:4].mean() - sims[4:8].mean())


def hybrid_valence(clap: float, muq: float, ref: Reference) -> float:
    """Hai số thô -> hạng -1..1 trong danh mục (ngoài hai đầu thì kẹp, như np.interp)."""
    import numpy as np

    v_raw = 0.5 * (clap - ref.clap_mean) / ref.clap_sd + 0.5 * (muq - ref.muq_mean) / ref.muq_sd
    return float(np.interp(v_raw, ref.quantiles, np.linspace(-1.0, 1.0, len(ref.quantiles))))


def valence_from_embeddings(clap_embedding: Any, muq_embedding: Any, ref: Reference) -> float:
    return hybrid_valence(clap_raw(clap_embedding, ref), muq_raw(muq_embedding, ref), ref)


def muq_clips(y: Any) -> list[Any]:
    """Các cửa sổ MuQ của bài (mono 24 kHz), mỗi cái đủ 240.000 mẫu float32."""
    import numpy as np

    clips = []
    for clip in music_student.audio_windows(y, MUQ_RATE):
        clip = np.asarray(clip, dtype=np.float32)
        if len(clip) < MUQ_SAMPLES:
            clip = np.resize(clip, MUQ_SAMPLES)  # nối vòng từ đầu bao nhiêu lần cũng được (cửa sổ 3-5 giây cần hơn một lần)
        clips.append(clip)
    return clips


class Scorer:
    """Một phiên onnxruntime của tháp MuQ + hằng số. Nặng ~1,5 GiB RAM: tạo khi có việc, bỏ khi hết (`close`)."""

    def __init__(self, directory: Path) -> None:
        music_student._app_dll_directory()
        import onnxruntime

        self.ref = load_reference(directory)
        options = onnxruntime.SessionOptions()
        options.intra_op_num_threads = THREADS
        options.inter_op_num_threads = 1
        options.add_session_config_entry("session.intra_op.allow_spinning", "0")  # luồng rảnh ngủ thật, không quay vòng ăn CPU
        before = _thread_ids()
        self.session = onnxruntime.InferenceSession(str(directory / "muq" / "muq_mulan_audio.onnx"), options, providers=["CPUExecutionProvider"])
        self._warm = False
        self._before = before

    def embedding(self, y: Any) -> Any | None:
        """e_m của bài từ mẫu mono 24 kHz, None nếu không có cửa sổ nào (bài ngắn hơn 3 giây)."""
        import numpy as np

        clips = muq_clips(y)
        if not clips:
            return None
        latents = []
        for clip in clips:
            latent = self.session.run(None, {"wav": clip[None]})[0][0].astype(np.float64)
            latents.append(latent / np.linalg.norm(latent))
            if not self._warm:  # ORT dựng luồng của nó ở lượt chạy đầu: hạ ưu tiên mấy luồng mới ấy
                self._warm = True
                _lower_threads(self._before)
        mean = np.mean(latents, axis=0)
        return mean / np.linalg.norm(mean)

    def score(self, path: Path) -> float | None:
        """V hợp của file nhạc, hay None nếu không giải mã được / quá ngắn / chưa có đầu trò để nhúng CLAP."""
        clap = music_student.clap_embedding(path)
        if clap is None:
            return None
        from . import music_mel  # numpy: Python nhúng của bản cài không có, chỉ nạp khi đo thật (như music_student)

        muq = self.embedding(music_mel.decode(Path(path), MUQ_RATE))
        return None if muq is None else valence_from_embeddings(clap, muq, self.ref)

    def close(self) -> None:
        self.session = None  # type: ignore[assignment]


# ---- ưu tiên thấp -----------------------------------------------------------------------------------------------------------------
def _thread_ids() -> set[int]:
    try:
        import psutil

        return {thread.id for thread in psutil.Process().threads()}
    except Exception:  # noqa: BLE001 - chỉ là phần tử tế với máy người dùng
        return set()


def _lower_threads(before: set[int]) -> None:
    """Windows: hạ ưu tiên các luồng mà onnxruntime vừa dựng (nó không có tuỳ chọn ưu tiên, và luồng không thừa hưởng ưu tiên của luồng cha)."""
    if os.name != "nt":
        return
    try:
        import ctypes

        kernel = ctypes.windll.kernel32
        kernel.OpenThread.restype = ctypes.c_void_p
        for tid in _thread_ids() - before:
            handle = kernel.OpenThread(0x0020, False, tid)  # THREAD_SET_INFORMATION
            if handle:
                kernel.SetThreadPriority(ctypes.c_void_p(handle), _LOWEST)
                kernel.CloseHandle(ctypes.c_void_p(handle))
    except Exception:  # noqa: BLE001
        pass


def _lower_this_thread() -> None:
    """Luồng làm việc nền (giải mã ffmpeg, nhúng CLAP, mel) chạy ưu tiên thấp nhất."""
    try:
        if os.name == "nt":
            import ctypes

            kernel = ctypes.windll.kernel32
            kernel.GetCurrentThread.restype = ctypes.c_void_p
            kernel.SetThreadPriority(ctypes.c_void_p(kernel.GetCurrentThread()), _LOWEST)
        elif hasattr(os, "setpriority"):  # Linux: ưu tiên theo từng luồng
            os.setpriority(os.PRIO_PROCESS, threading.get_native_id(), 10)
    except Exception:  # noqa: BLE001
        pass


# ---- máy này, công tắc, trạng thái ------------------------------------------------------------------------------------------------
def ram_bytes() -> int:
    try:
        import psutil

        return int(psutil.virtual_memory().total)
    except Exception:  # noqa: BLE001
        return 0


def cannot_use() -> str:
    """Rỗng nếu máy này bật được tuỳ chọn; không thì lý do (tiếng Việt)."""
    if ram_bytes() < MIN_RAM_BYTES:
        return "cần máy có từ 8 GB RAM"
    if music_student.package_dir() is None:
        return "chưa có chỗ đặt model trên máy này"
    return ""


def present(directory: Path | None = None) -> bool:
    """Tháp + vector chữ + hằng số đã nằm đủ trên máy (đúng cỡ đã ghim; file chỉ được đổi tên sau khi khớp SHA-256)."""
    directory = directory or music_student.package_dir()
    return directory is not None and all(
        (directory / file).is_file() and (directory / file).stat().st_size == music_student.PACKAGE_HASHES[file][1]
        for file in music_student.PACKAGE_FILES["muq"])


def _files(directory: Path | None = None) -> list[Path]:
    """Các file của phần muq/ đang nằm trên đĩa (kể cả `.part` dở dang)."""
    directory = directory or music_student.package_dir()
    if directory is None:
        return []
    found = []
    for file in music_student.PACKAGE_FILES["muq"]:
        for path in (directory / file, (directory / file).with_name(Path(file).name + ".part")):
            if path.is_file():
                found.append(path)
    return found


def removable() -> bool:
    """Đã tắt, không đang tải / đo, mà file MuQ còn trên đĩa: có thể xoá để lấy lại chỗ."""
    return not enabled() and not _state["downloading"] and not _state["working"] and bool(_files())


def enabled() -> bool:
    return bool(_get_enabled())


def ready() -> bool:
    """Bật, đủ file và bộ phân tích CLAP đã cắm: bài vừa nhập sẽ được đo V hợp."""
    return enabled() and present() and music_local.analyzer_available()


def total_bytes() -> int:
    return sum(music_student.PACKAGE_HASHES[file][1] for file in music_student.PACKAGE_FILES["muq"])


def status() -> dict[str, Any]:
    """Cho giao diện (hỏi ~mỗi giây khi `downloading` / `working`). `state`: unavailable (máy không bật được, kèm `reason`) | off | missing (bật
    mà chưa đủ file) | downloading | error | ready. `pending`: số bài còn chờ V hợp."""
    with _lock:
        reason = cannot_use()
        have = present()
        if reason and not have:
            state = "unavailable"
        elif _state["downloading"]:
            state = "downloading"
        elif _state["error"]:
            state = "error"
        elif not enabled():
            state = "off"
        else:
            state = "ready" if have else "missing"
        pending = len(_store.valence_pending(VERSION)) if _store is not None and state == "ready" else 0
        return {"state": state, "enabled": enabled(), "present": have, "removable": removable(), "reason": reason, "bytes": total_bytes(),
                "done": _state["done"] if state == "downloading" else 0, "total": _state["total"] if state == "downloading" else 0,
                "error": _state["error"], "working": bool(_state["working"]), "pending": pending}


def enable() -> None:
    """Người dùng bật: nhớ công tắc, tải tháp nếu chưa có (một luồng), rồi đo các bài đã nhập. ValueError (câu cho người dùng) khi máy không bật được."""
    reason = cannot_use() if not present() else ""
    if reason:
        raise ValueError(f"Máy này chưa đo cảm xúc nhạc chính xác hơn được: {reason}.")
    with _lock:
        _set_enabled(True)
        _state["error"] = ""
        if present():
            kick()
        else:
            _download()


def disable() -> None:
    """Người dùng tắt: dừng đo ở bài kế (bài đã đo giữ số của nó), giữ file đã tải để bật lại không phải tải."""
    with _lock:
        _set_enabled(False)


def remove_files() -> int:
    """Người dùng bấm "Xoá file": gỡ đúng các file muq/ của gói (giữ nguyên tháp CLAP, đầu A, cấu hình), trả số byte lấy lại. Bật lại thì tải lại.
    ValueError (câu cho người dùng) khi còn đang bật hay đang tải / đo."""
    with _lock:
        if enabled():
            raise ValueError("Hãy tắt đo cảm xúc chính xác hơn trước, rồi mới xoá file được.")
        if _state["downloading"] or _state["working"]:
            raise ValueError("Đang tải hay đang đo - chờ xong rồi hãy xoá file.")
        gc.collect()  # phiên onnxruntime cuối cùng buông file thì Windows mới cho xoá
        freed = 0
        for path in _files():
            with contextlib.suppress(OSError):
                size = path.stat().st_size
                path.unlink()
                freed += size
        directory = music_student.package_dir()
        if directory is not None:
            with contextlib.suppress(OSError):
                (directory / "muq").rmdir()  # chỉ khi đã trống
        _state.update(done=0, total=0, error="")
        return freed


def _download() -> None:
    """Caller giữ `_lock`."""
    global _thread
    if _state["downloading"] and _thread is not None and _thread.is_alive():
        return
    _state.update(downloading=True, done=0, total=total_bytes(), error="")
    _thread = threading.Thread(target=_download_run, name="music-valence-download", daemon=True)
    _thread.start()


def _download_run() -> None:
    try:
        directory = music_student.package_dir()
        assert directory is not None
        part = music_module.Component("muq", "Đo cảm xúc nhạc chính xác hơn", "", total_bytes(), False, downloads=music_student.model_downloads("muq"))

        def progress(done: int) -> None:
            with _lock:
                _state["done"] = done

        voice_module.download_files(part, directory, progress)
        with _lock:
            _state.update(downloading=False, error="")
    except Exception as error:  # noqa: BLE001 - mọi lỗi thành một câu cho người dùng
        with _lock:
            _state.update(downloading=False, error=f"Không tải được bộ đo cảm xúc chính xác hơn: {music_module._reason(error)}.")
        return
    kick()


# ---- việc nền: đo các bài chưa mang V hợp ---------------------------------------------------------------------------------------------
def kick() -> None:
    """Có bài mới (nhập, phân tích xong) hay vừa bật: bảo luồng nền đo các bài chưa mang V hợp. Không bật / chưa đủ file / chưa có bộ phân tích CLAP
    thì không làm gì; đang chạy thì nó tự lấy thêm bài mới ở vòng sau."""
    global _thread, _again
    with _lock:
        if not ready() or _store is None:
            return
        if _state["working"]:
            _again = True
            return
        _state["working"] = True
        _thread = threading.Thread(target=_work, name="music-valence", daemon=True)
        _thread.start()


def join(timeout: float | None = None) -> None:
    """Đợi luồng nền xong (bài thử)."""
    thread = _thread
    if thread is not None:
        thread.join(timeout)


def _work() -> None:
    global _again
    _lower_this_thread()
    while True:
        try:
            _process()
        except Exception:  # noqa: BLE001 - việc nền không bao giờ làm hỏng app; bài chưa đo vẫn dùng V của đầu trò
            pass
        with _lock:
            if not _again:
                _state.update(working=False, left=0)
                return
            _again = False


def _process() -> None:
    store = _store
    assert store is not None
    failed: set[str] = set()
    scorer: Scorer | None = None
    try:
        while True:
            todo = [item for item in store.valence_pending(VERSION) if item[0] not in failed]
            if not todo or not ready():
                return
            if scorer is None:
                directory = music_student.package_dir()
                assert directory is not None
                scorer = Scorer(directory)
            for index, (digest, path) in enumerate(todo):
                if not enabled():  # người dùng vừa tắt
                    return
                with _lock:
                    _state["left"] = len(todo) - index
                value = scorer.score(path)
                if value is None or not store.set_valence(digest, value, VERSION):
                    failed.add(digest)  # không giải mã được / quá ngắn / bị xoá giữa chừng: bài giữ V của đầu trò, vòng sau không thử lại
    finally:
        if scorer is not None:
            scorer.close()
