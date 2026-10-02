"""Bộ phân tích "trò" cho Nhạc của tôi (music_local.set_analyzer): model CHỈ-NGHE học từ thầy (docs/MUSIC_RESEARCH.md "THẦY ->
TRÒ", docs/MUSIC_IMPORT.md "Phân tích"). Không dò "có lời", không chặn bài nào - bài nào cũng ra một mục.

Hai đường chạy, cùng một cách cắt cửa sổ và cùng khoá đầu ra:
- torch (máy có Studio: torch + transformers + librosa), ba bước y như lúc đầu trò được học (LLM_Train/music/build_student.py):
  1. nhúng CLAP: ba cửa sổ 10 giây ở 20 / 50 / 80% bài (bài ngắn: một cửa sổ) mono 48 kHz -> tháp âm thanh của
     laion/clap-htsat-unfused (Apache-2.0, chỉ tháp âm thanh + phép chiếu) -> chuẩn hoá L2 từng cửa sổ -> trung bình -> chuẩn hoá L2;
  2. âm học 22.050 Hz (music_acoustic.py, bản chép đúng số của acoustic_features2);
  3. đầu trò (`student_head.npz`): z-score 512 CLAP + 42 âm học -> hồi quy tuyến tính 16 hàng; 13 cường độ cảm xúc = sigmoid,
     valence / energy / tension kẹp -1..1. `fitsUnderNarration` và `family` đọc thẳng từ vector nhúng so với vector chữ đã tính sẵn
     (app không cần tháp chữ).
- onnx (bản app chỉ-nghe, Python nhúng chỉ có numpy + onnxruntime): mel numpy (music_mel.py) -> tháp CLAP fp16 ONNX trên CPU -> đầu
  trò A (`student_head_A.npz`, chỉ 512 chiều CLAP, không âm học). Cùng phép tính của đầu; bỏ `loudness.speechBand` (cần âm học).
  Lệch so với torch cùng đầu A < 0,001 trên V/E/T (Corpus/research/music/onnx_student/README.md).
Chọn tự động: torch nếu đủ torch + transformers + librosa, không thì onnx nếu đủ numpy + onnxruntime, không thì không có bộ phân tích.
ABOOK_MUSIC_STUDENT_BACKEND=onnx|torch ép một đường (bài thử trên máy có cả hai).

Gói model (~55 MB torch, ~59 MB onnx) nằm trên Hugging Face, ghim theo commit và SHA-256 từng file; tải một lần (HTTPS thuần, qua
studio_setup.download: .part, kiểm băm, rồi mới đổi tên) vào thư mục dữ liệu của app khi bài đầu tiên cần phân tích. Chưa có gói /
không có mạng / thiếu thư viện -> `analyze` trả None và bài ở trạng thái "chưa phân tích": KHÔNG BAO GIỜ bịa số. Biến môi trường
ABOOK_MUSIC_STUDENT_DIR trỏ tới một thư mục gói có sẵn (bài thử, máy không mạng).
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
# ABOOK_MUSIC_STUDENT_DIR. 03-10: gói đầu c6e1485f (tháp âm thanh CLAP fp16 + đầu trò, 97,4% AUC thầy - docs/MUSIC_RESEARCH.md);
# 60e11bce thêm đường ONNX (tháp .onnx + đầu A). Bốn file của đường torch ở hai commit trùng từng byte (oid git bằng nhau), nên
# một ghim cho cả hai đường.
REVISION = "60e11bce3426f52330b744ba74cf1cbc53b1c9a1"
# Mỗi đường cần những file nào; chung preprocessor_config.json (torch đọc, onnx kiểm music_mel còn đúng cấu hình đã chép).
PACKAGE_FILES = {
    "torch": ("model.safetensors", "config.json", "preprocessor_config.json", "student_head.npz"),
    "onnx": ("clap_audio_fp16.onnx", "student_head_A.npz", "preprocessor_config.json"),
}
# SHA-256 + cỡ từng file ở REVISION (đổi REVISION thì đổi cả bảng này).
PACKAGE_HASHES = {
    "model.safetensors": ("9ffea52fdfa83741cc1bbc72abe79a54ca40a207a990d6ccb79ac78f34ea97ee", 56_807_712),
    "config.json": ("3ec6edfeb47a45e9e86810eb5a3ba74a0023bd3b7f8db9c3d9e0aaa5ae7cef98", 1_556),
    "preprocessor_config.json": ("b089fad772ef3242a3ff8b9e4a6449083253d28d83a1ad8aa346cea116bfe514", 524),
    "student_head.npz": ("9a68c59035ec2632760a960da2dfb6cc826f752ab10f1f9645a8ca9e6d1b595e", 57_023),
    "clap_audio_fp16.onnx": ("484bebfc9f42d3a22fc75e35c9027d543cc6c191031abf510a55392d5c1dbdd9", 58_989_719),
    "student_head_A.npz": ("9025d4fceecb3b67a2d5a7b3ddccec49dc86f747120670e94b360a6a7db08850", 53_589),
}
ENV_DIR = "ABOOK_MUSIC_STUDENT_DIR"
ENV_BACKEND = "ABOOK_MUSIC_STUDENT_BACKEND"  # "onnx" | "torch" = ép đường ấy; trống = tự chọn
ENV_DOWNLOAD = "ABOOK_MUSIC_STUDENT_DOWNLOAD"  # "0" = không bao giờ tải (bộ kiểm đặt sẵn, như ABOOK_CAST_DISCOVERY)
PACKAGE_FOLDER = "student"
RETRY_SECONDS = 600  # tải / nạp hỏng thì chừng ấy giây sau mới thử lại (nhập 40 bài không làm 40 lượt gọi mạng)
CLAP_RATE = 48_000
CLAP_WINDOW = 10  # giây
CLAP_MIN = 3  # cửa sổ ngắn hơn 3 giây bị bỏ
CONFIDENCE = 0.5  # chỉ nghe, không có chữ để đối chiếu: cố định
# Thứ tự = ưu tiên: máy có Studio giữ đường torch như trước, bản app chỉ-nghe rơi xuống đường onnx.
_DEPENDENCIES = {"torch": ("numpy", "librosa", "torch", "transformers"), "onnx": ("numpy", "onnxruntime")}

_lock = threading.RLock()  # nạp / tải gói
_run_lock = threading.Lock()  # một lượt suy luận một lúc (CPU của máy người dùng)
_directory: Path | None = None
_student: _Head | None = None
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


def backend() -> str | None:
    """Đường chạy của máy này ("torch" / "onnx"), None nếu thiếu thư viện cho cả hai. ABOOK_MUSIC_STUDENT_BACKEND ép một đường
    (thiếu thư viện của đường ép thì None, không rơi sang đường kia)."""
    forced = os.environ.get(ENV_BACKEND, "").strip().lower()
    for name, modules in _DEPENDENCIES.items():
        if forced in ("", name) and all(importlib.util.find_spec(module) is not None for module in modules):
            return name
    return None


def _may_download() -> bool:
    return bool(REVISION) and not os.environ.get(ENV_DIR) and os.environ.get(ENV_DOWNLOAD, "1") != "0"


def _complete(directory: Path | None, name: str | None = None) -> bool:
    name = name or backend()
    return directory is not None and name is not None and all((directory / file).is_file() for file in PACKAGE_FILES[name])


def available() -> bool:
    """Có thể phân tích được không: đủ thư viện của một đường VÀ (gói đã có sẵn, hay có chỗ để tải - REVISION đã ghim)."""
    name = backend()
    if name is None:
        return False
    directory = package_dir()
    return _complete(directory, name) or (directory is not None and _may_download())


def register() -> bool:
    """Cắm `analyze` vào music_local khi `available()` (server.py gọi lúc dựng kho nhạc). Không cắm thì bài nhập vẫn ở trạng thái
    "chưa phân tích", giao diện nói rõ chưa có bộ phân tích."""
    from . import music_local

    if available():
        music_local.set_analyzer(analyze)
        return True
    return False


def _download(directory: Path) -> bool:
    """Tải các file còn thiếu của đường chạy hiện tại về `directory`: HTTPS thuần (bản app chỉ-nghe không có huggingface_hub),
    qua studio_setup.download (.part, kiểm SHA-256 ghi ở PACKAGE_HASHES, rồi mới đổi tên)."""
    name = backend()
    if not _may_download() or name is None:
        return False
    try:
        from . import studio_setup

        directory.mkdir(parents=True, exist_ok=True)
        for file in PACKAGE_FILES[name]:
            if not (directory / file).is_file():
                sha256, size = PACKAGE_HASHES[file]
                url = f"https://huggingface.co/{REPO_ID}/resolve/{REVISION}/{file}"
                studio_setup.download(studio_setup.Download(file, url, sha256, size), directory / file,
                                      lambda done, total: None, lambda: False)
    except Exception:  # noqa: BLE001 - không mạng, nơi đăng chưa có gói, đĩa đầy, sai băm: bài chưa phân tích, không làm hỏng việc nhập
        return False
    return _complete(directory, name)


class _Head:
    """Đầu trò: z-score + hồi quy tuyến tính + vector chữ đã tính sẵn, dùng chung hai đường. Đầu A không có cột âm học (`names` rỗng)."""

    backend = ""

    def __init__(self, path: Path) -> None:
        import numpy as np

        head = np.load(path)
        self.mu, self.sd = head["mu"].astype(np.float64), head["sd"].astype(np.float64)
        self.coef, self.intercept = head["coef"].astype(np.float64), head["intercept"].astype(np.float64)
        self.names = [str(name) for name in head["names"]] if "names" in head.files else []
        self.emotions = [str(name) for name in head["emos"]]
        self.vet_sd = [float(value) for value in head["vet_sd"]]
        self.background = head["background_text"].astype(np.float64)
        self.family_names = [str(name) for name in head["family_names"]]
        self.family_text = head["family_text"].astype(np.float64)
        if self.mu.shape[0] != 512 + len(self.names) or self.coef.shape != (len(self.emotions) + 3, self.mu.shape[0]):
            raise ValueError("gói model không đúng hình đầu trò")

    def predict(self, embedding: Any, acoustic: dict[str, Any] | None = None) -> dict[str, Any]:
        import numpy as np

        acoustic = acoustic or {}
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


class _Student(_Head):
    """Đường torch: tháp CLAP + bộ trích đặc trưng của transformers + đầu trò đầy đủ (có âm học)."""

    backend = "torch"

    def __init__(self, directory: Path) -> None:
        import torch
        from transformers import ClapAudioModelWithProjection, ClapFeatureExtractor

        super().__init__(directory / "student_head.npz")
        self.torch = torch
        self.extractor = ClapFeatureExtractor.from_pretrained(str(directory))
        self.tower = ClapAudioModelWithProjection.from_pretrained(str(directory), dtype=torch.float32).eval()

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


def _app_dll_directory() -> None:
    """Windows chưa cài VC++ Redistributable thì onnxruntime không nạp được msvcp140.dll; bản đóng gói mang sẵn các DLL ấy ở
    app\\vcruntime (scripts/build_windows_app.ps1) - thêm vào đường tìm DLL trước khi import onnxruntime. Bản dev: không có thư mục."""
    folder = Path(__file__).resolve().parents[2] / "vcruntime"
    if os.name == "nt" and folder.is_dir():
        os.add_dll_directory(str(folder))


class _OnnxStudent(_Head):
    """Đường onnx: mel numpy + tháp CLAP fp16 chạy bằng onnxruntime (CPU) + đầu A (không âm học)."""

    backend = "onnx"

    def __init__(self, directory: Path) -> None:
        _app_dll_directory()
        import onnxruntime

        from . import music_mel

        music_mel.check_config(directory / "preprocessor_config.json")
        super().__init__(directory / "student_head_A.npz")
        if self.names:
            raise ValueError("đầu của đường onnx phải là đầu A (chỉ 512 chiều CLAP)")
        self.session = onnxruntime.InferenceSession(str(directory / "clap_audio_fp16.onnx"), providers=["CPUExecutionProvider"])

    def embed(self, clips: list[Any]) -> Any:
        """Như _Student.embed: tháp -> chuẩn hoá L2 từng cửa sổ -> trung bình -> chuẩn hoá L2 (float64 cả đoạn sau tháp)."""
        import numpy as np

        from . import music_mel

        audio = self.session.run(None, {"input_features": music_mel.input_features(clips)})[0].astype(np.float64)
        audio = audio / np.linalg.norm(audio, axis=1, keepdims=True)
        mean = audio.mean(0)
        return mean / np.linalg.norm(mean)


def _load() -> _Head | None:
    global _student, _failed_at
    with _lock:
        name = backend()
        if name is None:
            return None
        if _student is not None and _student.backend == name:
            return _student
        if _failed_at and time.monotonic() - _failed_at < RETRY_SECONDS:
            return None
        directory = package_dir()
        if directory is None:
            return None
        try:
            if not _complete(directory, name) and not _download(directory):
                raise FileNotFoundError("chưa có gói model")
            _student = (_Student if name == "torch" else _OnnxStudent)(directory)
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
    thư viện, file không giải mã được, hay bài ngắn hơn 3 giây. Đường onnx không có `loudness.speechBand`."""
    student = _load()
    if student is None:
        return None
    from . import music_mel  # numpy: bản app chỉ-nghe cũ chưa có thì available() đã False, tới đây là có

    clips = _clap_windows(music_mel.decode(Path(path), CLAP_RATE))
    if not clips:
        return None
    acoustic = None
    if student.names:  # đầu đầy đủ (đường torch) cần thêm 42 cột âm học
        from . import music_acoustic

        acoustic = music_acoustic.features(music_mel.decode(Path(path), music_acoustic.RATE))
        if acoustic is None:
            return None
    with _run_lock:
        return student.predict(student.embed(clips), acoustic)
