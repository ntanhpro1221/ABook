"""Học sinh "hình dạng không khí trong chương" cho nhạc nền (đường q06; docs/MUSIC_RESEARCH.md, Corpus/research/music/SPEC_app_q06.md).

V/E/T của đoạn hôm nay là LLM đọc từng đoạn (music_moods.py) rồi gói lại theo mức chương (music_scenes.apply_chapter_level). Đo cho thấy
một học sinh nhỏ đoán HÌNH dạng không khí TRONG chương tốt hơn hẳn LLM: nhúng chữ đoạn bằng Qwen3-0.6B cắt còn 14 lớp đầu, căn giữa nhúng
trong chương, rồi hồi quy tuyến tính (ridge) ra độ LỆCH V/E/T của từng đoạn quanh mức chương. Mô-đun này chỉ tính độ lệch (`dV`, `dE`, `dT`
trên thang [-1, 1], cùng thang `valence` / `arousal` / `tension` của đoạn) và ghi `music_scene_student.json`; `music_scenes.apply_student`
cộng cả ba vào mức chương khi dựng đoạn (music_plan.build đọc file này như đọc music_moods.json); mức E của chương vẫn là TB nhãn câu,
hình E trong chương lấy từ `dE` (Q06-E 10-10). Ranh giới đoạn vẫn của app.

Gói model (thư mục `scene_q06/` trong repo Hugging Face NGDtuanh/abook-music-student, cùng repo với mô-đun "Phân tích nhạc"; Qwen3 theo
Apache-2.0, (c) Qwen team, cắt 14 lớp): `config.json`, `model.safetensors` (bf16, 0,71 GiB cả gói), `tokenizer.json`, `tokenizer_config.json`,
`LICENSE` và đầu hồi quy `scene_head_q06.npz`: `mu`, `sd` (D,) chuẩn hoá; `coef` (D, 3) cho V/E/T; `intercept` (3,); `layer` (số lớp giữ
lại); `maxTokens` (khúc, 2048). D = 1024. Cộng đầu MỨC CHƯƠNG `chapter_head_q06.npz` (LV-Q06 10-10, Corpus/research/music/PLAN_lv_q06.md; 18 KB, TUỲ CHỌN
trong gói - xem dưới): `mu`, `sd` (D,); `coef` (D, 2) cho V/T; `intercept` (2,); `axes` ("V", "T"); `alpha`. Tải bằng `studio_setup.Download` ghim commit + SHA-256 qua music_module.py (một phần TUỲ CHỌN của
"Phân tích nhạc", người dùng bấm mới tải). ABOOK_MUSIC_SCENE_STUDENT_DIR trỏ tới thư mục gói đã có sẵn (bài thử, máy không mạng). Không có
gói / thiếu torch -> `available()` false và nhạc chạy đường hôm nay, KHÔNG bao giờ bịa số.

Mức chương (LV-Q06): một ridge học trên nhúng TRUNG BÌNH cả chương (trọng số = số chữ của đoạn, KHÔNG căn giữa) của 542 chương bạc:
`V = ((TB(X) - mu) / sd) @ coef[:, 0] + intercept[0]`. Mức V của chương đoán thế này sát hơn mức từ nhãn câu (MAE_V bộ 7 .262 -> .155). Cột T của đầu có
trong file nhưng app KHÔNG dùng (mức T vẫn P0, không có P0 thì nhãn; xem music_scenes.apply_student). `compute` ghi mức V vào mỗi đoạn của chương
(`chapterV`); gói cũ chưa có file này (người dùng chưa cập nhật) thì không ghi `chapterV` và `apply_student` giữ mức V từ nhãn như trước. File này
KHÔNG tính vào "gói đủ file" (`REQUIRED_FILES`) và KHÔNG vào `package_sha` (khoá bộ nhớ đệm nhúng): thêm nó không bắt nhúng lại cả cuốn.

Cách học (khớp LLM_Train/music/stu_embed.py, stu_fit.py, stu_curve.py::fit_predict - làm Y HỆT):
1. Nhúng: chữ đoạn = các câu nối "\\n" (music_moods.scene_text), token hoá có token đặc biệt, cắt khúc `maxTokens` token (mỗi khúc một lần
   forward, không nhìn sang khúc khác), lấy hidden state lớp cuối của model đã cắt (= lớp 14 của bản đủ, TRƯỚC norm cuối nên norm bị
   thay bằng Identity), trung bình theo TOKEN (cộng từng khúc ở float64, chia tổng số token).
2. Căn giữa TRONG chương: X - TB(X) với trọng số = số chữ của đoạn (`max(1, len(text.split()))`), như `stu_fit.eval_feats`.
3. Chuẩn hoá theo gói rồi hồi quy: dev = ((Xc - mu) / sd) @ coef + intercept (`stu_curve.fit_predict`: mu, sd đã tính trên dữ liệu học, sd
   đã cộng 1e-6; ridge có chặn nên `intercept` lấy từ gói, thường ~0 vì đích đã căn giữa). Chương chỉ một đoạn: dev = 0.

Chạy SAU pha phân tích (worker.py gọi sau P0) hay sau "Tính lại" ở tab Nhạc, LUÔN trên CPU 6 luồng (model nhỏ, khỏi tranh VRAM / Ollama với
Studio): kiểu số mặc định bf16 (~18 giây mỗi giờ audio), lần đầu ĐO một khúc ở mỗi kiểu rồi nhớ kiểu nhanh hơn trong `cpu_dtype.json` cạnh gói
(đổi phiên bản torch thì đo lại): CPU không có lệnh bf16 có thể chậm hơn fp32. Nhúng đệm trong `music_scene_student.npz` của dự án, khoá =
SHA-256(chữ đoạn) + SHA gói: đổi gói thì nhúng lại hết, sửa một đoạn chỉ nhúng lại đoạn ấy (độ lệch cả chương tính lại vì căn giữa - rẻ).
Mọi lỗi (thiếu gói / RAM, torch hỏng) -> một dòng log, nhạc chạy đường hôm nay; không bao giờ làm hỏng dây chuyền.
"""
from __future__ import annotations

import gc
import hashlib
import importlib.util
import io
import json
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable

from ..io_utils import atomic_write_bytes, atomic_write_json
from . import music_bounds, music_moods, music_scenes

REPO_ID = "NGDtuanh/abook-music-student"
SUBFOLDER = "scene_q06"
# Đường tải luôn ghim cứng một commit (như music_student.py); file nào đổi thì SHA-256 + cỡ ở đây đổi theo (khoá = tên file trong thư mục gói,
# không kèm SUBFOLDER - SUBFOLDER chỉ nằm trong URL). REVISION trống thì mô-đun không tải gì, chỉ dùng gói đã có sẵn / ABOOK_MUSIC_SCENE_STUDENT_DIR.
# Đổi REVISION không bắt tải lại file cũ: `studio_setup.download` bỏ qua file đã có đúng SHA-256 và music_module chỉ tính cỡ các file còn thiếu / sai băm.
REVISION = "182d945e4129165f2be9e69b50be919eb1078d63"
CHAPTER_HEAD_FILE = "chapter_head_q06.npz"
PACKAGE_FILES = ("config.json", "model.safetensors", "tokenizer.json", "tokenizer_config.json", "LICENSE", "scene_head_q06.npz", CHAPTER_HEAD_FILE)
# Đủ để chạy học sinh và để tính khoá nhúng; đầu mức chương là phần thêm ở bản sau (thiếu thì chỉ không có `chapterV`).
OPTIONAL_FILES = (CHAPTER_HEAD_FILE,)
REQUIRED_FILES = tuple(file for file in PACKAGE_FILES if file not in OPTIONAL_FILES)
PACKAGE_HASHES: dict[str, tuple[str, int]] = {
    "config.json": ("638669b3924f21702d7938e10dae48890db8be6d4a72836e667932092e712475", 1152),
    "model.safetensors": ("7005be7da7f28271f15f0102ecefe19da6b80b0af6b5ba9477e278ed8430c2d1", 751650088),
    "tokenizer.json": ("be75606093db2094d7cd20f3c2f385c212750648bd6ea4fb2bf507a6a4c55506", 11422650),
    "tokenizer_config.json": ("154e5ff1e7c152d964edf30da854ea62465c767719ac8e97e58babf2d4fa9079", 724),
    "LICENSE": ("832dd9e00a68dd83b3c3fb9f5588dad7dcf337a0db50f7d9483f310cd292e92e", 11343),
    "scene_head_q06.npz": ("84c9b10ac154852341daeabd33659b65333ae77f1eaf24b71c994c46ab9d3ec0", 22234),
    CHAPTER_HEAD_FILE: ("63b5c7d3f2e21796cec7307630bd6ba39b585f684f86e6c2b73e73467833c858", 17874),
}
ENV_DIR = "ABOOK_MUSIC_SCENE_STUDENT_DIR"
ENV_DOWNLOAD = "ABOOK_MUSIC_SCENE_STUDENT_DOWNLOAD"  # "0" = không bao giờ tải
PACKAGE_FOLDER = "scene_student"  # thư mục đặt gói trong <dữ liệu app>/music
HEAD_FILE = "scene_head_q06.npz"
CPU_DTYPE_FILE = "cpu_dtype.json"
FILE = "music_scene_student.json"
CACHE_FILE = "music_scene_student.npz"
VERSION = 1
CPU_THREADS = 6
BENCH_TOKENS = 512  # khúc đo kiểu số trên CPU
_DEPENDENCIES = ("numpy", "torch", "transformers", "safetensors")

_lock = threading.RLock()
_directory: Path | None = None
_sha_memo: dict[tuple[Any, ...], str] = {}


def configure(directory: Path | str | None) -> None:
    """Thư mục đặt gói (server.py: <dữ liệu app>/music/scene_student). ABOOK_MUSIC_SCENE_STUDENT_DIR thắng nếu có."""
    global _directory
    with _lock:
        _directory = Path(directory) if directory is not None else None


def package_dir() -> Path | None:
    override = os.environ.get(ENV_DIR)
    return Path(override) if override else _directory


def cannot_download() -> str:
    """Rỗng nếu được phép tải gói; không thì lý do (tiếng Việt)."""
    if os.environ.get(ENV_DOWNLOAD, "1") == "0":
        return "tải bộ đoán hình không khí cảnh đang bị tắt trên máy này"
    if os.environ.get(ENV_DIR):
        return "thư mục gói model đã được chỉ định sẵn trên máy này"
    if not REVISION:
        return "chưa có bản model để tải"
    return ""


def model_downloads() -> list[Any]:
    """Các file của gói, mỗi file một `studio_setup.Download` ghim cứng; rỗng khi chưa có bản phát hành (REVISION trống)."""
    from . import studio_setup

    if not REVISION:
        return []
    return [studio_setup.Download(file, f"https://huggingface.co/{REPO_ID}/resolve/{REVISION}/{SUBFOLDER}/{file}", *PACKAGE_HASHES[file])
            for file in PACKAGE_FILES]


def model_pin() -> str:
    """Mã ghim của gói (đổi khi REVISION hay SHA-256 của file nào đổi), cho dấu "đã tải" của music_module.py."""
    return hashlib.sha256("\n".join([REVISION, SUBFOLDER, *(f"{file} {PACKAGE_HASHES.get(file, ('',))[0]}" for file in PACKAGE_FILES)]).encode()).hexdigest()


def total_bytes() -> int:
    return sum(size for _sha, size in PACKAGE_HASHES.values())


def _complete(directory: Path | None) -> bool:
    return directory is not None and all((directory / file).is_file() for file in REQUIRED_FILES)


def present() -> bool:
    """Gói đã nằm đủ file trên máy."""
    return _complete(package_dir())


def dependencies_ok() -> bool:
    """Tiến trình NÀY import được torch + transformers + safetensors (+ numpy)."""
    return all(importlib.util.find_spec(module) is not None for module in _DEPENDENCIES)


def available() -> bool:
    """Chạy được ngay trong tiến trình này không: đủ torch + transformers + safetensors VÀ đủ file gói. Chưa thì nhạc chạy đường hôm nay (không tự
    tải). Tiến trình server của bản cài không có torch: ở đó "Tính lại" chạy q06 bằng tiến trình con của Studio (`run_in_studio`)."""
    return dependencies_ok() and present()


def package_sha(directory: Path | None = None) -> str:
    """SHA-256 gộp (tên + nội dung) các file BẮT BUỘC của gói (không có đầu mức chương) - một phần khoá bộ nhớ đệm nhúng; "" nếu gói chưa đủ
    file. Nhớ theo (đường dẫn, cỡ, giờ sửa) để một tiến trình không băm lại 0,71 GiB mỗi lần hỏi."""
    directory = directory or package_dir()
    if not _complete(directory):
        return ""
    stats = [(directory / file).stat() for file in REQUIRED_FILES]
    signature = (str(directory), *((file, stat.st_size, stat.st_mtime_ns) for file, stat in zip(REQUIRED_FILES, stats)))
    with _lock:
        if signature in _sha_memo:
            return _sha_memo[signature]
    digest = hashlib.sha256()
    for file in REQUIRED_FILES:
        digest.update(file.encode() + b"\0")
        with (directory / file).open("rb") as handle:
            for block in iter(lambda: handle.read(1 << 20), b""):
                digest.update(block)
    with _lock:
        _sha_memo[signature] = digest.hexdigest()
        return _sha_memo[signature]


# ---- đầu hồi quy ----------------------------------------------------------------------------------------------------------------
class Head:
    """`scene_head_q06.npz`: mu, sd (D,), coef (D, 3) cho V/E/T, intercept (3,), layer, maxTokens."""

    def __init__(self, path: Path) -> None:
        import numpy as np

        data = np.load(path)
        self.mu, self.sd = data["mu"].astype(np.float64), data["sd"].astype(np.float64)
        self.coef, self.intercept = data["coef"].astype(np.float64), data["intercept"].astype(np.float64)
        self.layer, self.max_tokens = int(data["layer"]), int(data["maxTokens"])
        width = self.mu.shape[0] if self.mu.ndim == 1 else -1
        if (width < 1 or self.sd.shape != (width,) or self.coef.shape != (width, 3) or self.intercept.shape != (3,)
                or self.layer < 1 or self.max_tokens < 1):
            raise ValueError("gói model không đúng hình đầu hồi quy")

    def deviations(self, embeddings: Any, weights: Any) -> Any:
        """Độ lệch (dV, dE, dT) của từng đoạn của MỘT chương, mảng (n, 3). `embeddings` (n, D); `weights`: số chữ của đoạn. Căn giữa
        trong chương (trung bình theo trọng số) -> chuẩn hoá -> hồi quy, đúng stu_curve.fit_predict. Một đoạn: 0."""
        import numpy as np

        x = np.asarray(embeddings, dtype=np.float64)
        if len(x) < 2:
            return np.zeros((len(x), 3))
        centered = x - np.average(x, axis=0, weights=np.asarray(weights, dtype=np.float64))
        return ((centered - self.mu) / self.sd) @ self.coef + self.intercept


class ChapterHead:
    """`chapter_head_q06.npz`: mu, sd (D,), coef (D, 2) cho V/T, intercept (2,), axes ("V", "T"), alpha. Mức V/T của cả chương từ nhúng trung bình."""

    def __init__(self, path: Path) -> None:
        import numpy as np

        data = np.load(path)
        self.mu, self.sd = data["mu"].astype(np.float64), data["sd"].astype(np.float64)
        self.coef, self.intercept = data["coef"].astype(np.float64), data["intercept"].astype(np.float64)
        width = self.mu.shape[0] if self.mu.ndim == 1 else -1
        if (width < 1 or self.sd.shape != (width,) or self.coef.shape != (width, 2) or self.intercept.shape != (2,)
                or [str(axis) for axis in data["axes"]] != ["V", "T"]):
            raise ValueError("gói model không đúng hình đầu mức chương")

    def level(self, embeddings: Any, weights: Any) -> Any:
        """(V, T) thô của MỘT chương (chưa kẹp): TB nhúng các đoạn theo trọng số = số chữ, KHÔNG căn giữa, rồi chuẩn hoá + hồi quy."""
        import numpy as np

        mean = np.average(np.asarray(embeddings, dtype=np.float64), axis=0, weights=np.asarray(weights, dtype=np.float64))
        return ((mean - self.mu) / self.sd) @ self.coef + self.intercept


def load_chapter_head(directory: Path | None, log: Callable[[str], None] = lambda _line: None) -> ChapterHead | None:
    """Đầu mức chương của gói nếu có và đúng hình; gói cũ chưa có file ấy -> None (không phải lỗi). File hỏng -> một dòng log và None: mức V về nhãn."""
    path = None if directory is None else directory / CHAPTER_HEAD_FILE
    if path is None or not path.is_file():
        return None
    try:
        return ChapterHead(path)
    except (OSError, ValueError, KeyError) as error:
        log(f"Bỏ qua mức chương của học sinh: {type(error).__name__}: {error}")
        return None


# ---- model --------------------------------------------------------------------------------------------------------------------
def read_cpu_dtype(directory: Path, torch_version: str) -> str | None:
    """Kiểu số đã đo cho CPU của máy này ("bf16" / "fp32"); None nếu chưa đo hay đo bằng phiên bản torch khác."""
    try:
        saved = json.loads((directory / CPU_DTYPE_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if isinstance(saved, dict) and saved.get("torch") == torch_version and saved.get("dtype") in ("bf16", "fp32"):
        return str(saved["dtype"])
    return None


def remember_cpu_dtype(directory: Path, name: str, torch_version: str) -> None:
    try:
        atomic_write_json(directory / CPU_DTYPE_FILE, {"dtype": name, "torch": torch_version})
    except OSError:
        pass  # thư mục chỉ đọc: lần sau đo lại


class _Embedder:
    """Qwen3-0.6B đã cắt `layer` lớp + token hoá; `embed` ra vector nhúng float32 của một đoạn chữ."""

    def __init__(self, directory: Path, head: Head, sample_text: str, threads: int = CPU_THREADS) -> None:
        import torch
        from transformers import AutoModel, AutoTokenizer

        self.torch, self.head = torch, head
        self.threads = torch.get_num_threads()
        self.tokenizer = AutoTokenizer.from_pretrained(str(directory))
        torch.set_num_threads(threads)
        remembered = read_cpu_dtype(directory, torch.__version__)
        dtype = torch.float32 if remembered == "fp32" else torch.bfloat16
        model = AutoModel.from_pretrained(str(directory), dtype=dtype)
        if model.config.num_hidden_layers < head.layer:
            raise ValueError("gói model không đủ lớp")
        if model.config.num_hidden_layers > head.layer:
            model.layers = model.layers[:head.layer]
            model.config.num_hidden_layers = head.layer
            if getattr(model.config, "layer_types", None):
                model.config.layer_types = model.config.layer_types[:head.layer]
        model.norm = torch.nn.Identity()  # lớp 14 của bản đủ là TRƯỚC norm cuối
        self.model = model.eval()
        if remembered is None:
            remember_cpu_dtype(directory, self._pick_cpu_dtype(sample_text), torch.__version__)

    def _time_forward(self, ids: Any) -> float:
        """Giây cho một lượt forward `ids` (sau một lượt khởi động)."""
        with self.torch.inference_mode():
            self.model(input_ids=ids[:, :16], use_cache=False)
            started = time.perf_counter()
            self.model(input_ids=ids, use_cache=False)
            return time.perf_counter() - started

    def _pick_cpu_dtype(self, text: str) -> str:
        """Đo một khúc ~512 token ở bf16 rồi fp32, giữ model ở kiểu nhanh hơn, trả tên kiểu. Model nạp sẵn ở bf16 (kiểu của gói);
        bf16 -> fp32 -> bf16 không mất gì. Không có chữ để đo thì giữ bf16."""
        torch = self.torch
        ids = self._ids(text)
        if len(ids) == 0:
            return "bf16"
        ids = ids.repeat(-(-BENCH_TOKENS // len(ids)))[:BENCH_TOKENS][None]
        bf16 = self._time_forward(ids)
        self.model.to(torch.float32)
        fp32 = self._time_forward(ids)
        if bf16 <= fp32:
            self.model.to(torch.bfloat16)
            return "bf16"
        return "fp32"

    def _ids(self, text: str) -> Any:
        return self.tokenizer(text, add_special_tokens=True, return_tensors="pt")["input_ids"][0]

    def embed(self, text: str) -> Any:
        """Trung bình theo token của hidden state lớp cuối, chia khúc `maxTokens` token, tổng từng khúc ở float64 (stu_embed.embed)."""
        import numpy as np

        ids = self._ids(text)
        total = np.zeros(self.model.config.hidden_size, dtype=np.float64)
        count = 0
        with self.torch.inference_mode():
            for start in range(0, len(ids), self.head.max_tokens):
                part = ids[start:start + self.head.max_tokens][None]
                hidden = self.model(input_ids=part, use_cache=False).last_hidden_state
                total += hidden[0].float().sum(0).double().cpu().numpy()
                count += part.shape[1]
        return (total / count).astype(np.float32) if count else np.zeros(total.shape, dtype=np.float32)

    def close(self) -> None:
        """Trả RAM và số luồng torch."""
        self.model = None
        gc.collect()
        try:
            self.torch.set_num_threads(self.threads)
        except Exception:  # noqa: BLE001 - chỉ là dọn dẹp
            pass


# ---- kết quả + bộ nhớ đệm -------------------------------------------------------------------------------------------------------
def load(project_root: Path) -> dict[str, Any] | None:
    """`music_scene_student.json` của dự án nếu đúng phiên bản; sai / hỏng / chưa có -> None."""
    try:
        value = json.loads((Path(project_root) / FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(value, dict) or value.get("version") != VERSION or not isinstance(value.get("scenes"), list):
        return None
    return value


def _load_cache(path: Path) -> dict[str, Any]:
    """{khoá: vector nhúng float32}; file thiếu / hỏng -> rỗng (nhúng lại, không mất gì ngoài thời gian)."""
    import numpy as np

    try:
        with np.load(path, allow_pickle=False) as data:
            keys, vectors = [str(key) for key in data["keys"]], data["vectors"]
        return dict(zip(keys, vectors)) if len(keys) == len(vectors) else {}
    except (OSError, ValueError, KeyError):
        return {}


def _save_cache(path: Path, cache: dict[str, Any]) -> None:
    import numpy as np

    buffer = io.BytesIO()
    keys = list(cache)
    np.savez(buffer, keys=np.array(keys, dtype=str), vectors=np.stack([cache[key] for key in keys]) if keys else np.zeros((0, 0), np.float32))
    atomic_write_bytes(path, buffer.getvalue())


class ChapterStudent:
    """Đoán hình không khí trong chương, từng chương một: nhúng chữ đoạn (có bộ nhớ đệm), độ lệch cả chương và mức V chương. Một đối tượng cho cả
    lượt tính (`compute` cho dự án; nhạc theo cảnh của "Nghe ngay", music_nnscene.py, cho sách chữ) - model chỉ nạp khi có đoạn cần nhúng.
    `threads`: số luồng CPU của torch lúc nhúng. `stopped` true sau khi `stop_requested` dừng giữa chừng."""

    def __init__(self, directory: Path, cache_path: Path | None, *, log: Callable[[str], None] = print, threads: int = CPU_THREADS) -> None:
        self.directory, self.cache_path, self.log, self.threads = directory, cache_path, log, threads
        self.head = Head(directory / HEAD_FILE)
        self.chapter_head = load_chapter_head(directory, log)
        self.package = package_sha(directory)
        self.cache = {} if cache_path is None else _load_cache(cache_path)
        self.used: set[str] = set()
        self.embedder: _Embedder | None = None
        self.embedded = 0
        self.dirty = False
        self.stopped = False

    def chapter(self, script: dict[str, Any], scenes: list[dict[str, Any]], *, stop_requested: Callable[[], bool] = lambda: False,
                pause_requested: Callable[[], bool] = lambda: False) -> list[dict[str, Any]] | None:
        """Các mục (`dV`, `dE`, `dT`, `chapterV`) của từng đoạn `scenes` của chương `script`. None: chương không dùng được (đoạn không khớp câu)
        hay bị dừng (`stopped`); phần đã nhúng vẫn nằm trong bộ nhớ đệm."""
        segments = [segment for segment in script.get("segments") or [] if isinstance(segment, dict)]
        position = {segment.get("id"): index for index, segment in enumerate(segments)}
        spans = [(position.get(scene["firstSegment"]), position.get(scene["lastSegment"])) for scene in scenes]
        if not scenes or any(first is None or last is None for first, last in spans):
            return None
        texts = [music_moods.scene_text(segments, first, last) for first, last in spans]
        keys = [hashlib.sha256(text.encode("utf-8")).hexdigest() + self.package for text in texts]
        self.used.update(keys)
        for text, key in zip(texts, keys):
            if key in self.cache:
                continue
            while pause_requested() and not stop_requested():
                time.sleep(1.0)
            if stop_requested():
                self.stopped = True
                return None
            if self.embedder is None:
                self.embedder = _Embedder(self.directory, self.head, text, *(() if self.threads == CPU_THREADS else (self.threads,)))
            self.cache[key] = self.embedder.embed(text)
            self.embedded += 1
            self.dirty = True
        vectors, weights = [self.cache[key] for key in keys], [max(1, len(text.split())) for text in texts]
        deviations = self.head.deviations(vectors, weights)
        # Mức V của cả chương (cùng giá trị ở mọi đoạn của chương; thiếu đầu mức chương thì không ghi): đo từ nhúng đã có, không chạy model thêm.
        level = {} if self.chapter_head is None else {"chapterV": round(float(self.chapter_head.level(vectors, weights)[0]), 4)}
        return [{"chapterId": scene["chapterId"], "firstSegment": scene["firstSegment"], "lastSegment": scene["lastSegment"],
                 "dV": round(float(dev[0]), 4), "dE": round(float(dev[1]), 4), "dT": round(float(dev[2]), 4), **level}
                for scene, dev in zip(scenes, deviations)]

    def save(self, *, prune: bool = False) -> None:
        """Ghi bộ nhớ đệm nhúng nếu có gì mới. `prune`: bỏ nhúng của đoạn / gói không còn dùng (làm trọn cuốn)."""
        if self.cache_path is None:
            return
        if prune and (self.dirty or any(key not in self.used for key in self.cache)):
            _save_cache(self.cache_path, {key: vector for key, vector in self.cache.items() if key in self.used})
        elif self.dirty:
            _save_cache(self.cache_path, self.cache)
        else:
            return
        self.dirty = False

    def close(self) -> None:
        """Trả RAM và số luồng torch."""
        if self.embedder is not None:
            self.embedder.close()
            self.embedder = None


class StudioChapterStudent:
    """`ChapterStudent` cho tiến trình KHÔNG có torch (server của bản cài): cùng bề mặt server dùng (`chapter`, `stopped`, `save`, `close`) nhưng
    việc nhúng chạy ở MỘT tiến trình con bằng Python của Studio (`serve`: `python -m abook.webui.music_scene_student --serve ...`), sinh ở chương đầu
    tiên và giữ model giữa các chương. Giao thức: mỗi dòng stdin một chương `{"script", "scenes"}`, mỗi dòng stdout một câu trả lời `{"items": [...] | null}`
    (thêm `"error"` khi chương lỗi); tiến trình con tự ghi bộ nhớ đệm nhúng sau mỗi chương nên `save` ở đây không làm gì. Mọi sự cố (chết, dòng rác,
    báo lỗi) thành None: chương ấy dựng đường N0 như nhánh `except` của `_scene_job`. Chết giữa chừng thì chương kế sinh lại; tiến trình con báo
    lỗi ngay khi khởi động (thiếu torch / gói: `{"error"}` không kèm `items`) thì `broken` và không sinh lại nữa."""

    POLL_SECONDS = 0.2
    KILL_AFTER_SECONDS = 5.0
    CLOSE_WAIT_SECONDS = 10.0

    def __init__(self, python: Path | str, code_root: Path | str, environment: dict[str, str], directory: Path, cache_path: Path | None, *,
                 threads: int = CPU_THREADS) -> None:
        self.python, self.code_root, self.environment, self.directory, self.cache_path, self.threads = python, code_root, environment, directory, cache_path, threads
        self.stopped = False
        self.broken = False
        self._process: subprocess.Popen[bytes] | None = None
        self._lines: queue.Queue[bytes | None] = queue.Queue()

    def _command(self) -> list[str]:
        command = [str(self.python), "-m", "abook.webui.music_scene_student", "--serve", "--package", str(self.directory), "--threads", str(self.threads)]
        return command + (["--cache", str(self.cache_path)] if self.cache_path is not None else [])

    def _spawn(self) -> None:
        process = subprocess.Popen(
            self._command(), cwd=str(self.code_root), env={**os.environ, **self.environment, "PYTHONIOENCODING": "utf-8"}, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0)
        lines: queue.Queue[bytes | None] = queue.Queue()  # hàng riêng mỗi tiến trình: dòng muộn của tiến trình đã giết không lẫn sang tiến trình sau

        def read() -> None:
            try:
                for line in process.stdout or ():
                    lines.put(line)
            except (OSError, ValueError):
                pass
            lines.put(None)

        threading.Thread(target=read, name="music-scene-student-reader", daemon=True).start()
        self._process, self._lines = process, lines

    def _kill(self) -> None:
        process, self._process = self._process, None
        if process is None:
            return
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(self.KILL_AFTER_SECONDS)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        try:
            if process.stdin is not None:
                process.stdin.close()
        except OSError:
            pass

    def chapter(self, script: dict[str, Any], scenes: list[dict[str, Any]], *, stop_requested: Callable[[], bool] = lambda: False,
                pause_requested: Callable[[], bool] = lambda: False) -> list[dict[str, Any]] | None:
        """Như `ChapterStudent.chapter`: các mục của từng đoạn, hay None (chương không dùng được, sự cố, hay bị dừng - `stopped` true)."""
        if self.broken or not scenes:
            return None
        if stop_requested():
            self.stopped = True
            return None
        try:
            if self._process is None or self._process.poll() is not None:
                self._kill()
                self._spawn()
            process = self._process
            payload = json.dumps({"script": script, "scenes": scenes}).encode("ascii") + b"\n"

            def send() -> None:  # luồng riêng: yêu cầu lớn mà tiến trình con còn đang nạp torch thì pipe đầy, không được treo việc dừng
                try:
                    process.stdin.write(payload)  # type: ignore[union-attr]
                    process.stdin.flush()  # type: ignore[union-attr]
                except (OSError, ValueError):
                    pass  # tiến trình con chết: hàng đọc báo EOF

            threading.Thread(target=send, name="music-scene-student-writer", daemon=True).start()
            while True:
                while pause_requested() and not stop_requested():
                    time.sleep(1.0)
                if stop_requested():
                    self.stopped = True
                    self._kill()
                    return None
                try:
                    line = self._lines.get(timeout=self.POLL_SECONDS)
                except queue.Empty:
                    continue
                if line is None:  # tiến trình con chết (hay đóng stdout)
                    self._kill()
                    return None
                reply = _parse_reply(line)
                if reply is None:
                    self._kill()  # dòng rác: giao thức lệch, không tin tiến trình này nữa
                    return None
                if "items" not in reply:  # lỗi lúc khởi động
                    self.broken = True
                    self._kill()
                    return None
                items = reply["items"]
                if reply.get("error") or not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
                    return None
                return items
        except Exception:  # noqa: BLE001 - không sinh được tiến trình / pipe hỏng: chương này dựng không có học sinh
            self._kill()
            return None

    def save(self, *, prune: bool = False) -> None:
        """Tiến trình con ghi bộ nhớ đệm sau mỗi chương - ở đây không còn gì để ghi."""

    def close(self) -> None:
        """Đóng stdin để tiến trình con ghi đệm rồi thoát (chờ tối đa `CLOSE_WAIT_SECONDS`), quá hạn thì giết."""
        process, self._process = self._process, None
        if process is None:
            return
        try:
            if process.stdin is not None:
                process.stdin.close()
        except OSError:
            pass
        try:
            process.wait(self.CLOSE_WAIT_SECONDS)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def _parse_reply(line: bytes) -> dict[str, Any] | None:
    """Một dòng stdout của `serve` thành dict; không phải JSON object -> None."""
    try:
        value = json.loads(line.decode("utf-8"))
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


def compute(project_root: Path, *, stop_requested: Callable[[], bool] = lambda: False, log: Callable[[str], None] = print,
            pause_requested: Callable[[], bool] = lambda: False, directory: Path | None = None) -> int:
    """Nhúng chữ từng đoạn (ranh giới của app) chưa có trong bộ nhớ đệm, tính độ lệch cả chương và ghi `music_scene_student.json` sau
    mỗi chương. Model chỉ nạp khi có đoạn cần nhúng. Trả số đoạn đã nhúng. `pause_requested`: nút "Tạm dừng" / gác pin - đứng chờ giữa
    hai đoạn (CPU nặng); `stop_requested` thì phần đã nhúng vẫn được giữ."""
    from . import music_plan

    project_root = Path(project_root)
    directory = directory or package_dir()
    if not _complete(directory):
        raise FileNotFoundError("chưa có gói model")
    student = ChapterStudent(directory, project_root / CACHE_FILE, log=log)
    items: list[dict[str, Any]] = []
    finished = False

    bounds = music_bounds.load(project_root) or {}  # ranh LLM chia cảnh: cùng đoạn với music_plan.build
    try:
        for script in music_plan.book_scripts(project_root):
            scenes = music_scenes.chapter_scenes(script, boundaries=bounds.get(script.get("chapterId")))
            chapter = student.chapter(script, scenes, stop_requested=stop_requested, pause_requested=pause_requested)
            if student.stopped:
                return student.embedded
            if chapter is None:
                continue
            items += chapter
            atomic_write_json(project_root / FILE, {"version": VERSION, "package": student.package, "built": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                                                    "scenes": items})
            log(f"Hình không khí trong chương: xong chương {script.get('chapterId')} ({len(items)} đoạn)")
            student.save()
        finished = True
        return student.embedded
    finally:
        student.save(prune=finished)  # làm trọn cuốn: bỏ nhúng của đoạn / gói không còn dùng; dừng giữa chương / lỗi: phần đã nhúng vẫn ghi
        student.close()


def run_in_studio(project_root: Path, python: Path | str, code_root: Path | str, environment: dict[str, str], log: Callable[[str], None],
                  *, package: Path | None = None) -> bool:
    """Chạy `compute` bằng Python của Studio (tiến trình server của bản cài không có torch): `python -m abook.webui.music_scene_student <dự án>
    --package <gói>`, từ thư mục mã `code_root` (cùng mã với worker, xem `StudioSetup.code_for`), không hiện cửa sổ; chờ xong, mỗi dòng stdout của nó
    thành một dòng log. KHÔNG BAO GIỜ ném: lỗi hay mã thoát khác 0 thành MỘT dòng log, trả False (nhạc chạy đường hôm nay)."""
    from . import music_plan

    try:
        directory = package or package_dir()
        if not _complete(directory) or not music_plan.read_overrides(project_root)["enabled"]:
            return False
        command = [str(python), "-m", "abook.webui.music_scene_student", str(project_root), "--package", str(directory)]
        process = subprocess.Popen(
            command, cwd=str(code_root), env={**os.environ, **environment, "PYTHONIOENCODING": "utf-8"}, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0)
        tail = ""
        for line in process.stdout or ():
            tail = line.strip() or tail
            log(line.rstrip())
        code = process.wait()
        if code != 0:
            log(f"Bỏ qua hình không khí trong chương: Studio thoát với mã {code}" + (f" ({tail})" if tail else ""))
            return False
        return True
    except Exception as error:  # noqa: BLE001 - tuỳ chọn: lỗi gì cũng chỉ là không có hình không khí
        log(f"Bỏ qua hình không khí trong chương: {type(error).__name__}: {error}")
        return False


def serve(package: Path, cache: Path | None, threads: int = CPU_THREADS, *, stdin: Any = None, stdout: Any = None) -> int:
    """Chế độ phục vụ của `StudioChapterStudent`: mỗi dòng stdin `{"script", "scenes"}` -> `ChapterStudent.chapter` -> MỘT dòng stdout `{"items": [...]}`
    (hay `{"items": null}`; chương lỗi thêm `"error"`) rồi ghi bộ nhớ đệm, nên bị giết thì mất nhiều nhất một chương. EOF ở stdin: ghi đệm, đóng, thoát 0.
    Thiếu gói / torch: dòng đầu `{"error": ...}` (không có `items`) và thoát 2. stdout CHỈ mang dòng giao thức (mọi `print` lạc đi sang stderr)."""
    out = stdout or sys.stdout
    source = stdin or sys.stdin
    for stream in (out, source):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    sys.stdout = sys.stderr  # thư viện in gì cũng không lẫn vào giao thức

    def reply(value: dict[str, Any]) -> None:
        out.write(json.dumps(value) + "\n")
        out.flush()

    configure(package)
    try:
        if not available():
            reply({"error": "thiếu torch / transformers hoặc thiếu file gói"})
            return 2
        student = ChapterStudent(package, cache, log=lambda line: print(line, file=sys.stderr), threads=threads)
    except Exception as error:  # noqa: BLE001
        reply({"error": f"{type(error).__name__}: {error}"})
        return 2
    try:
        for line in source:
            if not line.strip():
                continue
            try:
                request = json.loads(line)
                items = student.chapter(request["script"], request["scenes"])
                student.save()
                reply({"items": items})
            except Exception as error:  # noqa: BLE001 - một chương lỗi không dừng việc phục vụ
                reply({"items": None, "error": f"{type(error).__name__}: {error}"})
        return 0
    finally:
        student.save()
        student.close()


def main(argv: list[str] | None = None) -> int:
    """`python -m abook.webui.music_scene_student <thư mục dự án> [--package <thư mục gói>]`: tính cả cuốn, in log ra stdout. 0 = xong.
    `--serve --package <gói> [--cache <npz>] [--threads n]`: phục vụ từng chương qua stdin / stdout (`serve`)."""
    import argparse

    parser = argparse.ArgumentParser(prog="music_scene_student")
    parser.add_argument("project", nargs="?")
    parser.add_argument("--package")
    parser.add_argument("--serve", action="store_true", help="phục vụ từng chương qua stdin / stdout (StudioChapterStudent)")
    parser.add_argument("--cache")
    parser.add_argument("--threads", type=int, default=CPU_THREADS)
    arguments = parser.parse_args(argv)
    if arguments.serve:
        if not arguments.package:
            parser.error("--serve cần --package")
        return serve(Path(arguments.package), Path(arguments.cache) if arguments.cache else None, arguments.threads)
    if not arguments.project:
        parser.error("thiếu thư mục dự án")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if arguments.package:
        configure(arguments.package)
    try:
        if not available():
            print("Bỏ qua hình không khí trong chương: thiếu torch / transformers hoặc thiếu file gói", flush=True)
            return 2
        compute(Path(arguments.project), log=lambda line: print(line, flush=True))
        return 0
    except Exception as error:  # noqa: BLE001
        print(f"Bỏ qua hình không khí trong chương: {type(error).__name__}: {error}", flush=True)
        return 1


def run_after_analysis(project_root: Path, stop_requested: Callable[[], bool], log: Callable[[str], None],
                       emit: Callable[[str, dict[str, Any]], None], pause_requested: Callable[[], bool] = lambda: False) -> None:
    """Móc của dây chuyền sau pha phân tích (worker.py): đoán hình không khí trong chương nếu máy có gói model và nhạc nền của cuốn không
    tắt. KHÔNG BAO GIỜ ném: mọi lỗi (thiếu gói / RAM, torch hỏng) thành MỘT dòng log, nhạc chạy đường hôm nay."""
    from . import music_plan

    try:
        if not available() or not music_plan.read_overrides(project_root)["enabled"]:
            return
        embedded = compute(project_root, stop_requested=stop_requested, log=log, pause_requested=pause_requested)
        emit("music_scene_student_done", {"embedded": embedded})
    except Exception as error:  # noqa: BLE001 - tuỳ chọn: lỗi gì cũng chỉ là không có hình không khí
        log(f"Bỏ qua hình không khí trong chương: {type(error).__name__}: {error}")


if __name__ == "__main__":
    raise SystemExit(main())
