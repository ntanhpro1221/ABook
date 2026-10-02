"""Bộ phân tích "trò" cho Nhạc của tôi (music_local.set_analyzer): model CHỈ-NGHE học từ thầy (docs/MUSIC_RESEARCH.md "THẦY ->
TRÒ", docs/MUSIC_IMPORT.md "Phân tích"). Không dò "có lời", không chặn bài nào - bài nào cũng ra một mục.

Một bài đi qua ba bước, y như lúc đầu trò được học (LLM_Train/music/build_student.py):
1. nhúng CLAP: ba cửa sổ 10 giây ở 20 / 50 / 80% bài (bài ngắn: một cửa sổ) mono 48 kHz -> tháp âm thanh của
   laion/clap-htsat-unfused (Apache-2.0, chỉ tháp âm thanh + phép chiếu) -> chuẩn hoá L2 từng cửa sổ -> trung bình -> chuẩn hoá L2;
2. âm học 22.050 Hz (music_acoustic.py, bản chép đúng số của acoustic_features2);
3. đầu trò (`student_head.npz`): z-score 512 CLAP + 42 âm học -> hồi quy tuyến tính 16 hàng; 13 cường độ cảm xúc = sigmoid,
   valence / energy / tension kẹp -1..1. `fitsUnderNarration` và `family` đọc thẳng từ vector nhúng so với vector chữ đã tính sẵn
   (app không cần tháp chữ).

Gói model (~55 MB) nằm trên Hugging Face, ghim theo commit; tải một lần vào thư mục dữ liệu của app khi bài đầu tiên cần phân
tích. Chưa có gói / không có mạng / thiếu torch (app đóng gói chỉ có phần nghe) -> `analyze` trả None và bài ở trạng thái "chưa
phân tích": KHÔNG BAO GIỜ bịa số. Biến môi trường ABOOK_MUSIC_STUDENT_DIR trỏ tới một thư mục gói có sẵn (bài thử, máy không mạng).
"""
from __future__ import annotations

import importlib.util
import os
import threading
import time
from pathlib import Path
from typing import Any

from . import music_plan

REPO_ID = "NGDtuanh/abook-music-student"
# Đường tải luôn ghim cứng một commit (như studio_setup.py). Trống thì app KHÔNG tải gì, chỉ dùng gói đã có sẵn trong thư mục /
# ABOOK_MUSIC_STUDENT_DIR. 03-10: gói đầu (tháp âm thanh CLAP fp16 + đầu trò, 97,4% AUC thầy - docs/MUSIC_RESEARCH.md).
REVISION = "c6e1485f60d3e5433369142b43db562e50386bf1"
PACKAGE_FILES = ("model.safetensors", "config.json", "preprocessor_config.json", "student_head.npz")
ENV_DIR = "ABOOK_MUSIC_STUDENT_DIR"
ENV_DOWNLOAD = "ABOOK_MUSIC_STUDENT_DOWNLOAD"  # "0" = không bao giờ tải (bộ kiểm đặt sẵn, như ABOOK_CAST_DISCOVERY)
PACKAGE_FOLDER = "student"
RETRY_SECONDS = 600  # tải / nạp hỏng thì chừng ấy giây sau mới thử lại (nhập 40 bài không làm 40 lượt gọi mạng)
CLAP_RATE = 48_000
CLAP_WINDOW = 10  # giây
CLAP_MIN = 3  # cửa sổ ngắn hơn 3 giây bị bỏ
CONFIDENCE = 0.5  # chỉ nghe, không có chữ để đối chiếu: cố định
_DEPENDENCIES = ("numpy", "librosa", "torch", "transformers")

_lock = threading.RLock()  # nạp / tải gói
_run_lock = threading.Lock()  # một lượt suy luận một lúc (CPU của máy người dùng)
_directory: Path | None = None
_student: _Student | None = None
_failed_at = 0.0


def configure(directory: Path | str | None) -> None:
    """Thư mục đặt gói (server.py: <dữ liệu app>/music/student). ABOOK_MUSIC_STUDENT_DIR thắng nếu có."""
    global _directory
    with _lock:
        _directory = Path(directory) if directory is not None else None


def reset() -> None:
    """Quên gói đã nạp và dấu "đã hỏng" (bài thử)."""
    global _student, _failed_at
    with _lock:
        _student, _failed_at = None, 0.0


def package_dir() -> Path | None:
    override = os.environ.get(ENV_DIR)
    return Path(override) if override else _directory


def _may_download() -> bool:
    return bool(REVISION) and not os.environ.get(ENV_DIR) and os.environ.get(ENV_DOWNLOAD, "1") != "0"


def _complete(directory: Path | None) -> bool:
    return directory is not None and all((directory / name).is_file() for name in PACKAGE_FILES)


def available() -> bool:
    """Có thể phân tích được không: đủ thư viện VÀ (gói đã có sẵn, hay có chỗ để tải - REVISION đã ghim)."""
    if any(importlib.util.find_spec(name) is None for name in _DEPENDENCIES):
        return False
    directory = package_dir()
    return _complete(directory) or (directory is not None and _may_download())


def register() -> bool:
    """Cắm `analyze` vào music_local khi `available()` (server.py gọi lúc dựng kho nhạc). Không cắm thì bài nhập vẫn ở trạng thái
    "chưa phân tích", giao diện nói rõ chưa có bộ phân tích."""
    from . import music_local

    if available():
        music_local.set_analyzer(analyze)
        return True
    return False


def _download(directory: Path) -> bool:
    if not _may_download():
        return False
    try:
        from huggingface_hub import hf_hub_download

        directory.mkdir(parents=True, exist_ok=True)
        for name in PACKAGE_FILES:
            if not (directory / name).is_file():
                hf_hub_download(repo_id=REPO_ID, filename=name, revision=REVISION, local_dir=str(directory))
    except Exception:  # noqa: BLE001 - không mạng, nơi đăng chưa có gói, đĩa đầy: bài chưa phân tích, không làm hỏng việc nhập
        return False
    return _complete(directory)


class _Student:
    """Gói đã nạp: tháp CLAP + bộ trích đặc trưng + đầu trò."""

    def __init__(self, directory: Path) -> None:
        import numpy as np
        import torch
        from transformers import ClapAudioModelWithProjection, ClapFeatureExtractor

        self.torch = torch
        self.extractor = ClapFeatureExtractor.from_pretrained(str(directory))
        self.tower = ClapAudioModelWithProjection.from_pretrained(str(directory), dtype=torch.float32).eval()
        head = np.load(directory / "student_head.npz")
        self.mu, self.sd = head["mu"].astype(np.float64), head["sd"].astype(np.float64)
        self.coef, self.intercept = head["coef"].astype(np.float64), head["intercept"].astype(np.float64)
        self.names = [str(name) for name in head["names"]]
        self.emotions = [str(name) for name in head["emos"]]
        self.vet_sd = [float(value) for value in head["vet_sd"]]
        self.background = head["background_text"].astype(np.float64)
        self.family_names = [str(name) for name in head["family_names"]]
        self.family_text = head["family_text"].astype(np.float64)
        if self.mu.shape[0] != 512 + len(self.names) or self.coef.shape != (len(self.emotions) + 3, self.mu.shape[0]):
            raise ValueError("gói model không đúng hình đầu trò")

    def embed(self, clips: list[Any]) -> Any:
        """Vector nhúng 512 chiều của bài từ các cửa sổ 48 kHz: chuẩn hoá L2 từng cửa sổ, trung bình, chuẩn hoá L2."""
        import numpy as np

        torch = self.torch
        inputs = self.extractor(clips, sampling_rate=CLAP_RATE, return_tensors="pt")
        with torch.inference_mode():
            audio = self.tower(input_features=inputs["input_features"]).audio_embeds
            audio = torch.nn.functional.normalize(audio, dim=-1)
            mean = torch.nn.functional.normalize(audio.mean(0, keepdim=True), dim=-1)
        return mean[0].numpy().astype(np.float64)

    def predict(self, embedding: Any, acoustic: dict[str, Any]) -> dict[str, Any]:
        import numpy as np

        # Âm học thiếu một khoá (hay NaN) thì thay bằng trung bình lúc học = z 0, như acoustic_matrix của build_student.
        values = [acoustic.get(name) for name in self.names]
        tail = np.array([self.mu[512 + i] if value is None or not np.isfinite(float(value)) else float(value)
                         for i, value in enumerate(values)])
        z = (np.concatenate([embedding, tail]) - self.mu) / self.sd
        out = z @ self.coef.T + self.intercept
        count = len(self.emotions)
        intensity = 1.0 / (1.0 + np.exp(-out[:count]))
        valence, energy, tension = (float(np.clip(value, -1.0, 1.0)) for value in out[count:])
        pair = 100.0 * (self.background @ embedding)
        pair = np.exp(pair - pair.max())
        family = self.family_names[int(np.argmax(self.family_text @ embedding))]
        result: dict[str, Any] = {
            "valence": valence, "arousal": energy, "tension": tension,
            "sd": dict(zip(("valence", "arousal", "tension"), self.vet_sd)),
            "emotions": {name: float(value) for name, value in zip(self.emotions, intensity)},
            "confidence": CONFIDENCE,
            "fitsUnderNarration": float(pair[0] / pair.sum()),
            # Họ phong cách ngoài danh sách của app (vd "rock") là "other" - như danh mục.
            "family": family if family in music_plan.FAMILIES else "other",
        }
        band = acoustic.get("speech_band_ratio")
        if band is not None:
            result["loudness"] = {"speechBand": float(band)}
        return result


def _load() -> _Student | None:
    global _student, _failed_at
    with _lock:
        if _student is not None:
            return _student
        if _failed_at and time.monotonic() - _failed_at < RETRY_SECONDS:
            return None
        directory = package_dir()
        if directory is None:
            return None
        try:
            if not _complete(directory) and not _download(directory):
                raise FileNotFoundError("chưa có gói model")
            _student = _Student(directory)
        except Exception:  # noqa: BLE001 - thiếu thư viện / gói hỏng / không mạng: chưa phân tích
            _failed_at = time.monotonic()
            return None
        return _student


def _clap_windows(y: Any) -> list[Any]:
    """Tối đa ba cửa sổ 10 giây ở 20 / 50 / 80% bài (bài không dài hơn 10 giây: cả bài), bỏ cửa sổ ngắn hơn 3 giây."""
    n, size = len(y), CLAP_RATE * CLAP_WINDOW
    starts = [0] if n <= size else sorted({min(max(int(n * f) - size // 2, 0), n - size) for f in (0.2, 0.5, 0.8)})
    return [y[s:s + size] for s in starts if len(y[s:s + size]) >= CLAP_RATE * CLAP_MIN]


def analyze(path: Path) -> dict[str, Any] | None:
    """Mục theo hình danh mục cho file nhạc ở `path` (music_local.clean_analysis làm sạch tiếp), hay None khi chưa có gói model /
    thư viện, file không giải mã được, hay bài ngắn hơn 3 giây."""
    student = _load()
    if student is None:
        return None
    from . import music_acoustic

    clips = _clap_windows(music_acoustic.decode(Path(path), CLAP_RATE))
    if not clips:
        return None
    acoustic = music_acoustic.features(music_acoustic.decode(Path(path), music_acoustic.RATE))
    if acoustic is None:
        return None
    with _run_lock:
        return student.predict(student.embed(clips), acoustic)
