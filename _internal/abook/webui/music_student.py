"""Bộ phân tích "trò" cho Nhạc của tôi (music_local.set_analyzer): model CHỈ-NGHE học từ thầy (docs/MUSIC_RESEARCH.md "THẦY ->
TRÒ", docs/MUSIC_IMPORT.md "Phân tích"). Không chặn bài nào - bài nào cũng ra một mục; đầu dò `vox_head.npz` chỉ GẮN CỜ bài có vẻ có lời hát
(`vocals`, `vocalsLikely`) để máy không tự chọn nó làm nền dưới giọng đọc.

Hai đường chạy, cùng một cách cắt cửa sổ và cùng khoá đầu ra:
- torch (máy có Studio: torch + transformers + librosa):
  1. nhúng CLAP: ba cửa sổ 10 giây ở 20 / 50 / 80% bài (bài ngắn: một cửa sổ) mono 48 kHz -> tháp âm thanh của
     laion/clap-htsat-unfused (Apache-2.0, chỉ tháp âm thanh + phép chiếu) -> chuẩn hoá L2 từng cửa sổ -> trung bình -> chuẩn hoá L2;
  2. đầu trò A (`student_head_A.npz`, MỘT đầu cho mọi máy từ 05-10): z-score 512 CLAP -> hồi quy tuyến tính 16 hàng; 13 cường độ cảm xúc =
     sigmoid, valence / energy / tension kẹp -1..1 rồi hiệu chỉnh cho kho trộn (CALIBRATION, kèm `vetVar`; không còn `sd`). `fitsUnderNarration`
     và `family` đọc thẳng từ vector nhúng so với vector chữ đã tính sẵn (app không cần tháp chữ);
  3. âm học 22.050 Hz (music_acoustic.py) chỉ còn dùng cho `loudness.speechBand`, không vào đầu.
- onnx (bản app chỉ-nghe, Python nhúng chỉ có numpy + onnxruntime): mel numpy (music_mel.py) -> tháp CLAP fp16 ONNX trên CPU -> cùng đầu A.
  Bỏ `loudness.speechBand` (cần âm học). Lệch so với torch cùng đầu A < 0,001 trên V/E/T (Corpus/research/music/onnx_student/README.md).
Valence còn có đường chính xác hơn, tuỳ chọn (music_valence.py): V hợp CLAP + MuQ chạy nền sau lúc nhập, ghi đè valence của trò.
Chọn tự động: torch nếu đủ torch + transformers + librosa, không thì onnx nếu đủ numpy + onnxruntime, không thì không có bộ phân tích.
ABOOK_MUSIC_STUDENT_BACKEND=onnx|torch ép một đường (bài thử trên máy có cả hai).

Gói model (~55 MB torch, ~59 MB onnx; thêm 1,27 GB cho đường V hợp, tải riêng khi người dùng bật) nằm trên Hugging Face, ghim theo commit và SHA-256 từng file. Nó là MỘT phần của mô-đun
"Phân tích nhạc" (music_module.py): người dùng bấm thì mới tải (HTTPS thuần, qua studio_setup.download: .part, kiểm băm, rồi mới đổi
tên) vào thư mục dữ liệu của app - không bao giờ tự tải, kể cả lúc nhập nhạc. Chưa có gói / thiếu thư viện -> `analyze` trả None và bài
ở trạng thái "chưa phân tích": KHÔNG BAO GIỜ bịa số. Biến môi trường ABOOK_MUSIC_STUDENT_DIR trỏ tới một thư mục gói có sẵn (bài thử,
máy không mạng).
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
# Đường tải luôn ghim cứng một commit (như studio_setup.py). Trống thì mô-đun KHÔNG tải gói model, chỉ dùng gói đã có sẵn trong thư mục /
# ABOOK_MUSIC_STUDENT_DIR. 03-10: gói đầu c6e1485f (tháp âm thanh CLAP fp16 + đầu trò, 97,4% AUC thầy - docs/MUSIC_RESEARCH.md);
# 60e11bce thêm đường ONNX (tháp .onnx + đầu A); aaa54805 thêm thư viện ONNX Runtime của điện thoại (ort/1.30.0/<abi>/*.so.gz). 05-10: 332e7552 thay đầu A bằng đầu A mới (thang V có phần
# MuQ) cho MỌI máy, bỏ đầu torch cũ, thêm muq/ (tháp MuQ ONNX CC BY-NC 4.0 + vector chữ + hằng số, đường V hợp); 143bea3d: đầu A + vhop_scale dựng lại bằng cửa sổ âm thanh của chính app, hiệu chỉnh mới. Các file còn lại trùng từng byte với ba commit đầu, nên một ghim cho mọi đường.
# 07-10: eed82cec thêm `vox_head.npz` (đầu dò "có lời hát" trên cùng vector nhúng; docs/MUSIC_RESEARCH.md "VOX"), các file khác giữ nguyên băm.
REVISION = "eed82cec48a525de0582dcb5e7c3f436f165a39d"
# Mỗi đường cần những file nào; chung preprocessor_config.json (torch đọc, onnx kiểm music_mel còn đúng cấu hình đã chép).
PACKAGE_FILES = {
    "torch": ("model.safetensors", "config.json", "preprocessor_config.json", "student_head_A.npz", "vox_head.npz"),
    "onnx": ("clap_audio_fp16.onnx", "student_head_A.npz", "preprocessor_config.json", "vox_head.npz"),
    # Tuỳ chọn "đo cảm xúc nhạc chính xác hơn" (music_valence.py): người dùng bật mới tải, không thuộc đường chạy nào ở trên.
    "muq": ("muq/muq_mulan_audio.onnx", "muq/valence_text.npz", "muq/vhop_scale.json"),
}
# SHA-256 + cỡ từng file ở REVISION (đổi REVISION thì đổi cả bảng này).
PACKAGE_HASHES = {
    "model.safetensors": ("9ffea52fdfa83741cc1bbc72abe79a54ca40a207a990d6ccb79ac78f34ea97ee", 56_807_712),
    "config.json": ("3ec6edfeb47a45e9e86810eb5a3ba74a0023bd3b7f8db9c3d9e0aaa5ae7cef98", 1_556),
    "preprocessor_config.json": ("b089fad772ef3242a3ff8b9e4a6449083253d28d83a1ad8aa346cea116bfe514", 524),
    "clap_audio_fp16.onnx": ("484bebfc9f42d3a22fc75e35c9027d543cc6c191031abf510a55392d5c1dbdd9", 58_989_719),
    "student_head_A.npz": ("3fcb54b598dd9b3c42cdacd68bb9938ceb68e65c4895a8133c75066aec7080f7", 53_577),
    "vox_head.npz": ("2def334c729b04ff918072aa0821a3e0146c77d9c1df90a21f1b676f47a48359", 7_374),
    "muq/muq_mulan_audio.onnx": ("5bacc509e048720fe7e45178ce6a4e4d2a15a83d550510818399f4f7e6e9b1c8", 1_273_217_311),
    "muq/valence_text.npz": ("d07deac228b7b561bac016f610340f1f68ec05321abc813d9cb29478dd50847f", 34_394),
    "muq/vhop_scale.json": ("e9516c95ee81bd983eaed7d9e2c21ba1cc46f26eb6df5bbdf13e28b61ff717d7", 1_789),
}
ENV_DIR = "ABOOK_MUSIC_STUDENT_DIR"
ENV_BACKEND = "ABOOK_MUSIC_STUDENT_BACKEND"  # "onnx" | "torch" = ép đường ấy; trống = tự chọn
ENV_DOWNLOAD = "ABOOK_MUSIC_STUDENT_DOWNLOAD"  # "0" = không bao giờ tải (bộ kiểm đặt sẵn, như ABOOK_CAST_DISCOVERY)
VOX_FILE = "vox_head.npz"
# File của gói mà thiếu thì bộ phân tích vẫn chạy (bản gói cũ, trước khi có đầu dò lời hát): bài không có `vocals` / `vocalsLikely`, không đoán.
OPTIONAL_FILES = (VOX_FILE,)
PACKAGE_FOLDER = "student"
RETRY_SECONDS = 600  # nạp hỏng thì chừng ấy giây sau mới thử lại (nhập 40 bài không làm 40 lượt nạp hỏng)
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


def planned_backend() -> str:
    """Đường chạy mô-đun "Phân tích nhạc" sẽ dùng trên máy này, kể cả khi thư viện của nó CHƯA tải: torch nếu máy có đủ torch + transformers
    + librosa (Studio), không thì onnx. ABOOK_MUSIC_STUDENT_BACKEND ép một đường."""
    forced = os.environ.get(ENV_BACKEND, "").strip().lower()
    if forced in _DEPENDENCIES:
        return forced
    return "torch" if all(importlib.util.find_spec(module) is not None for module in _DEPENDENCIES["torch"]) else "onnx"


def backend() -> str | None:
    """Đường chạy của máy này ("torch" / "onnx"), None nếu thiếu thư viện cho cả hai. ABOOK_MUSIC_STUDENT_BACKEND ép một đường
    (thiếu thư viện của đường ép thì None, không rơi sang đường kia)."""
    forced = os.environ.get(ENV_BACKEND, "").strip().lower()
    for name, modules in _DEPENDENCIES.items():
        if forced in ("", name) and all(importlib.util.find_spec(module) is not None for module in modules):
            return name
    return None


def cannot_download() -> str:
    """Rỗng nếu mô-đun được phép tải gói model; không thì lý do (tiếng Việt)."""
    if os.environ.get(ENV_DOWNLOAD, "1") == "0":
        return "tải bộ phân tích nhạc đang bị tắt trên máy này"
    if os.environ.get(ENV_DIR):
        return "thư mục gói model đã được chỉ định sẵn trên máy này"
    if not REVISION:
        return "chưa có bản model để tải"
    return ""


def model_downloads(name: str | None = None) -> list[Any]:
    """Các file của gói model cho đường chạy `name` (mặc định: đường đã định), mỗi file một `studio_setup.Download` ghim cứng."""
    from . import studio_setup

    name = name or planned_backend()
    return [studio_setup.Download(file, f"https://huggingface.co/{REPO_ID}/resolve/{REVISION}/{file}", *PACKAGE_HASHES[file])
            for file in PACKAGE_FILES[name]]


def model_pin(name: str | None = None) -> str:
    """Mã ghim của gói model: đổi khi REVISION hay SHA-256 của bất kỳ file nào của đường chạy đổi. Mô-đun ghi nó lúc tải để biết gói đã tải
    có còn là bản app này ghim không (cùng tên file, cùng cỡ vẫn có thể là model khác)."""
    import hashlib

    name = name or planned_backend()
    return hashlib.sha256("\n".join([REVISION, name, *(f"{file} {PACKAGE_HASHES[file][0]}" for file in PACKAGE_FILES[name])]).encode()).hexdigest()


def model_id() -> str:
    """Mã ngắn của bản model: ghi cạnh mỗi kết quả phân tích để biết bài nào do bản model cũ phân tích (music_local)."""
    return model_pin()[:12]


def _complete(directory: Path | None, name: str | None = None) -> bool:
    name = name or backend()
    return directory is not None and name is not None and all(
        (directory / file).is_file() for file in PACKAGE_FILES[name] if file not in OPTIONAL_FILES)


def available() -> bool:
    """Có thể phân tích được ngay không: đủ thư viện của một đường VÀ gói model đã có sẵn trong thư mục. Chưa có thì bài ở "chưa phân
    tích" cho tới khi người dùng bấm "Phân tích nhạc" (music_module.py) - không bao giờ tự tải."""
    name = backend()
    if name is None:
        return False
    directory = package_dir()
    return _complete(directory, name)


def register() -> bool:
    """Cắm `analyze` vào music_local khi `available()` (server.py gọi lúc dựng kho nhạc). Không cắm thì bài nhập vẫn ở trạng thái
    "chưa phân tích", giao diện nói rõ chưa có bộ phân tích."""
    from . import music_local

    if available():
        music_local.set_analyzer(analyze)
        music_local.set_analyzer_id(model_id())
        return True
    return False


# Hiệu chỉnh số của trò cho kho TRỘN (nhạc nhập lẫn nhạc danh mục có số của thầy): V/E/T của trò bị nén về giữa nên bài nhập được chọn
# quá thường. Mỗi trục (a, b, var): v' = kẹp(a + b*v, -1, 1) và `vetVar` = phương sai dư, music_select.z_distance cộng
# VET_VAR_WEIGHT * var vào tử số. Khớp F2 trên dự đoán chéo 5 phần của đầu A mới so với danh mục 33e5202f6cda (docs/MUSIC_RESEARCH.md "F2"),
# bằng nhúng torch (lệch onnx < 0,001): một bảng cho mọi đường. Phương sai dư của V (0,073, trước 0,041) lớn hơn vì thang V mới có phần MuQ mà
# CLAP không thấy - bài nhập ít bị chọn quá đà. Bài mang V hợp (music_valence) bỏ bảng này ở trục V: nó đã cùng thang với danh mục.
_HEAD_A_CALIBRATION = {"valence": (-0.057, 1.251, 0.0727), "arousal": (-0.013, 1.098, 0.0322), "tension": (-0.003, 1.283, 0.0412)}
CALIBRATION = {"torch": _HEAD_A_CALIBRATION, "onnx": _HEAD_A_CALIBRATION}


class _Head:
    """Đầu trò: z-score + hồi quy tuyến tính + vector chữ đã tính sẵn, dùng chung hai đường. Đầu A không có cột âm học (`names` rỗng).
    Lớp con đặt `backend`; V/E/T ra theo CALIBRATION của đường ấy (lớp gốc, `backend` trống: số thô, không `vetVar`)."""

    backend = ""
    vox: dict[str, Any] | None = None  # đầu dò lời hát; None = gói không có

    def __init__(self, path: Path) -> None:
        import numpy as np

        head = np.load(path)
        self.mu, self.sd = head["mu"].astype(np.float64), head["sd"].astype(np.float64)
        self.coef, self.intercept = head["coef"].astype(np.float64), head["intercept"].astype(np.float64)
        self.names = [str(name) for name in head["names"]] if "names" in head.files else []
        self.emotions = [str(name) for name in head["emos"]]
        self.background = head["background_text"].astype(np.float64)
        self.family_names = [str(name) for name in head["family_names"]]
        self.family_text = head["family_text"].astype(np.float64)
        if self.mu.shape[0] != 512 + len(self.names) or self.coef.shape != (len(self.emotions) + 3, self.mu.shape[0]):
            raise ValueError("gói model không đúng hình đầu trò")
        # Đầu dò lời hát: logistic trên đúng vector nhúng 512 chiều. Thiếu file (gói cũ) -> không có hai khoá vocals*, không đoán.
        vox_path = path.with_name(VOX_FILE)
        if vox_path.is_file():
            vox = np.load(vox_path)
            parts = {key: vox[key].astype(np.float64) for key in ("mu", "sd", "coef", "intercept", "tau")}
            if any(parts[key].shape != (512,) for key in ("mu", "sd", "coef")) or any(parts[key].shape != (1,) for key in ("intercept", "tau")):
                raise ValueError("gói model không đúng hình đầu dò lời hát")
            self.vox = {**parts, "intercept": float(parts["intercept"][0]), "tau": float(parts["tau"][0])}

    def vocals(self, embedding: Any) -> float | None:
        """Xác suất bài có lời hát (0..1) từ vector nhúng L2, hay None khi gói không có đầu dò."""
        import numpy as np

        if self.vox is None:
            return None
        score = float(((np.asarray(embedding, dtype=np.float64) - self.vox["mu"]) / self.vox["sd"]) @ self.vox["coef"] + self.vox["intercept"])
        return 1.0 / (1.0 + float(np.exp(-score)))

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
        # kẹp trước rồi mới hiệu chỉnh, đúng thứ tự lúc khớp CALIBRATION (dự đoán chéo đã kẹp -1..1)
        raw = dict(zip(("valence", "arousal", "tension"), (float(np.clip(value, -1.0, 1.0)) for value in out[count:])))
        calibration = CALIBRATION.get(self.backend, {})
        # Không còn `sd` của trò (RMSE giữ ngoài): bài nhập dùng độ không chắc mặc định như bài danh mục, phần sai số của bộ đoán
        # nằm ở `vetVar` (xem CALIBRATION).
        vet = {axis: float(np.clip(value if not calibration else calibration[axis][0] + calibration[axis][1] * value, -1.0, 1.0))
               for axis, value in raw.items()}
        pair = 100.0 * (self.background @ embedding)
        pair = np.exp(pair - pair.max())
        family = self.family_names[int(np.argmax(self.family_text @ embedding))]
        result: dict[str, Any] = {
            "valence": vet["valence"], "arousal": vet["arousal"], "tension": vet["tension"],
            **({"vetVar": {axis: calibration[axis][2] for axis in vet}} if calibration else {}),
            "emotions": {name: float(value) for name, value in zip(self.emotions, intensity)},
            "confidence": CONFIDENCE,
            "fitsUnderNarration": float(pair[0] / pair.sum()),
            # Họ phong cách ngoài danh sách của app (vd "rock") là "other" - như danh mục.
            "family": family if family in music_plan.FAMILIES else "other",
        }
        vocals = self.vocals(embedding)
        if vocals is not None:
            result["vocals"] = round(vocals, 3)
            result["vocalsLikely"] = bool(vocals >= self.vox["tau"])
        band = acoustic.get("speech_band_ratio")
        if band is not None:
            result["loudness"] = {"speechBand": float(band)}
        return result


class _Student(_Head):
    """Đường torch: tháp CLAP + bộ trích đặc trưng của transformers + đầu A (như đường onnx; âm học chỉ để đo `loudness.speechBand`)."""

    backend = "torch"

    def __init__(self, directory: Path) -> None:
        import torch
        from transformers import ClapAudioModelWithProjection, ClapFeatureExtractor

        super().__init__(directory / "student_head_A.npz")
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
            if not _complete(directory, name):
                raise FileNotFoundError("chưa có gói model")
            _student = (_Student if name == "torch" else _OnnxStudent)(directory)
        except Exception:  # noqa: BLE001 - thiếu thư viện / gói hỏng / không mạng: chưa phân tích
            _failed_at = time.monotonic()
            return None
        return _student


def audio_windows(y: Any, rate: int) -> list[Any]:
    """Tối đa ba cửa sổ 10 giây ở 20 / 50 / 80% bài (bài không dài hơn 10 giây: cả bài), bỏ cửa sổ ngắn hơn 3 giây. `rate`: tần số lấy mẫu
    của `y` - CLAP 48 kHz ở đây, MuQ 24 kHz ở music_valence (cùng một cách cắt)."""
    n, size = len(y), rate * CLAP_WINDOW
    starts = [0] if n <= size else sorted({min(max(int(n * f) - size // 2, 0), n - size) for f in (0.2, 0.5, 0.8)})
    return [y[s:s + size] for s in starts if len(y[s:s + size]) >= rate * CLAP_MIN]


def _clap_windows(y: Any) -> list[Any]:
    return audio_windows(y, CLAP_RATE)


def _clips(path: Path) -> list[Any]:
    from . import music_mel

    return _clap_windows(music_mel.decode(Path(path), CLAP_RATE))


def analyze(path: Path) -> dict[str, Any] | None:
    """Mục theo hình danh mục cho file nhạc ở `path` (music_local.clean_analysis làm sạch tiếp), hay None khi chưa có gói model /
    thư viện, file không giải mã được, hay bài ngắn hơn 3 giây. Đường onnx không có `loudness.speechBand`."""
    student = _load()
    if student is None:
        return None
    from . import music_mel  # numpy: bản app chỉ-nghe cũ chưa có thì available() đã False, tới đây là có

    clips = _clips(path)
    if not clips:
        return None
    acoustic = None
    if student.backend == "torch":  # âm học (librosa) chỉ còn để đo loudness.speechBand; không đo được thì bài vẫn có số, chỉ thiếu khoá ấy
        from . import music_acoustic

        acoustic = music_acoustic.features(music_mel.decode(Path(path), music_acoustic.RATE))
    with _run_lock:
        return student.predict(student.embed(clips), acoustic)


def clap_embedding(path: Path) -> Any | None:
    """Vector nhúng CLAP 512 chiều (L2) của bài - đúng cái `analyze` đưa cho đầu trò; music_valence cần nó cho nửa CLAP của V hợp. None khi
    chưa có gói / thư viện, file không giải mã được hay bài ngắn hơn 3 giây."""
    student = _load()
    clips = _clips(path) if student is not None else []
    if not clips:
        return None
    with _run_lock:
        return student.embed(clips)
