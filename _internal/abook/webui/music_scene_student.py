"""Học sinh "hình dạng không khí trong chương" cho nhạc nền (đường q17; docs/MUSIC_RESEARCH.md, Corpus/research/music/SPEC_app_q17_DRAFT.md).

V/E/T của đoạn hôm nay là LLM đọc từng đoạn (music_moods.py) rồi gói lại theo mức chương (music_scenes.apply_chapter_level). Đo cho thấy
một học sinh nhỏ đoán HÌNH dạng không khí TRONG chương tốt hơn hẳn LLM: nhúng chữ đoạn bằng Qwen3-1.7B cắt còn 14 lớp đầu, căn giữa nhúng
trong chương, rồi hồi quy tuyến tính (ridge) ra độ LỆCH V/E/T của từng đoạn quanh mức chương. Mô-đun này chỉ tính độ lệch (`dV`, `dE`, `dT`
trên thang [-1, 1], cùng thang `valence` / `arousal` / `tension` của đoạn) và ghi `music_scene_student.json`; `music_scenes.apply_student`
cộng nó vào mức chương khi dựng đoạn (music_plan.build đọc file này như đọc music_moods.json). Ranh giới đoạn vẫn của app.

Gói model (thư mục `scene_q17/` trong repo Hugging Face NGDtuanh/abook-music-student; Qwen3 theo Apache-2.0):
`config.json` (Qwen3, đã cắt 14 lớp), `model.safetensors` (bf16, ~1,9 GB), `tokenizer.json`, `tokenizer_config.json` và đầu hồi quy
`scene_head_q17.npz`: `mu`, `sd` (D,) chuẩn hoá; `coef` (D, 3) cho V/E/T; `intercept` (3,); `layer` (số lớp giữ lại); `maxTokens` (khúc).
Gói chưa được phát hành: REVISION trống thì mô-đun KHÔNG tải gì (như music_student.py), chỉ dùng gói đã nằm sẵn trong thư mục
(ABOOK_MUSIC_SCENE_STUDENT_DIR trỏ tới nó - bài thử, máy không mạng). Không có gói / thiếu torch -> `available()` false và nhạc chạy
đường hôm nay, KHÔNG bao giờ bịa số.

Cách học (khớp LLM_Train/music/stu_embed.py, stu_fit.py, stu_curve.py::fit_predict - làm Y HỆT):
1. Nhúng: chữ đoạn = các câu nối "\\n" (music_moods.scene_text), token hoá có token đặc biệt, cắt khúc `maxTokens` token (mỗi khúc một lần
   forward, không nhìn sang khúc khác), lấy hidden state lớp cuối của model đã cắt (= lớp 14 của bản đủ, TRƯỚC norm cuối nên norm bị
   thay bằng Identity), trung bình theo TOKEN (cộng từng khúc ở float64, chia tổng số token).
2. Căn giữa TRONG chương: X - TB(X) với trọng số = số chữ của đoạn (`max(1, len(text.split()))`), như `stu_fit.eval_feats`.
3. Chuẩn hoá theo gói rồi hồi quy: dev = ((Xc - mu) / sd) @ coef + intercept (`stu_curve.fit_predict`: mu, sd đã tính trên dữ liệu học, sd
   đã cộng 1e-6; ridge có chặn nên `intercept` lấy từ gói, thường ~0 vì đích đã căn giữa). Chương chỉ một đoạn: dev = 0.

Chạy SAU pha phân tích (worker.py gọi sau khi Ollama dỡ model; VRAM 2,5 GiB không ngồi cạnh model phân tích trong card 8 GB) hay sau
"Tính lại" ở tab Nhạc. GPU nếu có CUDA và còn trống từ 3 GiB (bf16); không thì CPU 6 luồng, kiểu số (bf16 / fp32) chọn bằng ĐO một khúc
lần đầu rồi nhớ trong `cpu_dtype.json` cạnh gói (đổi phiên bản torch thì đo lại): CPU không có lệnh bf16 có thể chậm hơn fp32. Nhúng đệm
trong `music_scene_student.npz` của dự án, khoá = SHA-256(chữ đoạn) + SHA gói: đổi gói thì nhúng lại hết, sửa một đoạn chỉ nhúng lại
đoạn ấy (độ lệch cả chương tính lại vì căn giữa - rẻ). Mọi lỗi (thiếu gói / RAM / VRAM, torch hỏng) -> một dòng log, nhạc chạy đường
hôm nay; không bao giờ làm hỏng dây chuyền.
"""
from __future__ import annotations

import gc
import hashlib
import importlib.util
import io
import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Callable

from ..io_utils import atomic_write_bytes, atomic_write_json
from . import music_moods, music_scenes

REPO_ID = "NGDtuanh/abook-music-student"
SUBFOLDER = "scene_q17"
# Đường tải luôn ghim cứng một commit (như music_student.py). TRỐNG vì gói chưa được phát hành: mô-đun không tải gì, chỉ dùng gói đã có
# sẵn trong thư mục / ABOOK_MUSIC_SCENE_STUDENT_DIR. Phát hành thì điền REVISION + PACKAGE_HASHES (SHA-256 và cỡ từng file).
REVISION = ""
PACKAGE_FILES = ("config.json", "model.safetensors", "tokenizer.json", "tokenizer_config.json", "scene_head_q17.npz")
PACKAGE_HASHES: dict[str, tuple[str, int]] = {}
ENV_DIR = "ABOOK_MUSIC_SCENE_STUDENT_DIR"
ENV_DOWNLOAD = "ABOOK_MUSIC_SCENE_STUDENT_DOWNLOAD"  # "0" = không bao giờ tải
PACKAGE_FOLDER = "scene_student"  # thư mục đặt gói trong <dữ liệu app>/music
HEAD_FILE = "scene_head_q17.npz"
CPU_DTYPE_FILE = "cpu_dtype.json"
FILE = "music_scene_student.json"
CACHE_FILE = "music_scene_student.npz"
VERSION = 1
MIN_FREE_VRAM = 3 * 2 ** 30  # GPU chỉ khi còn trống chừng này (model 1,9 GB + kích hoạt)
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
    return directory is not None and all((directory / file).is_file() for file in PACKAGE_FILES)


def present() -> bool:
    """Gói đã nằm đủ file trên máy."""
    return _complete(package_dir())


def available() -> bool:
    """Chạy được ngay không: đủ torch + transformers + safetensors VÀ đủ file gói. Chưa thì nhạc chạy đường hôm nay (không tự tải)."""
    return all(importlib.util.find_spec(module) is not None for module in _DEPENDENCIES) and present()


def package_sha(directory: Path | None = None) -> str:
    """SHA-256 gộp (tên + nội dung) mọi file gói - một phần khoá bộ nhớ đệm nhúng; "" nếu gói chưa đủ file. Nhớ theo (đường dẫn, cỡ,
    giờ sửa) để một tiến trình không băm lại 1,9 GB mỗi lần hỏi."""
    directory = directory or package_dir()
    if not _complete(directory):
        return ""
    stats = [(directory / file).stat() for file in PACKAGE_FILES]
    signature = (str(directory), *((file, stat.st_size, stat.st_mtime_ns) for file, stat in zip(PACKAGE_FILES, stats)))
    with _lock:
        if signature in _sha_memo:
            return _sha_memo[signature]
    digest = hashlib.sha256()
    for file in PACKAGE_FILES:
        digest.update(file.encode() + b"\0")
        with (directory / file).open("rb") as handle:
            for block in iter(lambda: handle.read(1 << 20), b""):
                digest.update(block)
    with _lock:
        _sha_memo[signature] = digest.hexdigest()
        return _sha_memo[signature]


# ---- đầu hồi quy ----------------------------------------------------------------------------------------------------------------
class Head:
    """`scene_head_q17.npz`: mu, sd (D,), coef (D, 3) cho V/E/T, intercept (3,), layer, maxTokens."""

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


def _gpu_ready(torch: Any) -> bool:
    try:
        return bool(torch.cuda.is_available()) and int(torch.cuda.mem_get_info()[0]) >= MIN_FREE_VRAM
    except Exception:  # noqa: BLE001 - driver hỏng: dùng CPU
        return False


class _Embedder:
    """Qwen3 đã cắt `layer` lớp + token hoá; `embed` ra vector nhúng float32 của một đoạn chữ."""

    def __init__(self, directory: Path, head: Head, sample_text: str) -> None:
        import torch
        from transformers import AutoModel, AutoTokenizer

        self.torch, self.head = torch, head
        self.threads = torch.get_num_threads()
        self.tokenizer = AutoTokenizer.from_pretrained(str(directory))
        self.device = "cuda" if _gpu_ready(torch) else "cpu"
        remembered = None
        if self.device == "cpu":
            torch.set_num_threads(CPU_THREADS)
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
        self.model = model.eval().to(self.device)
        if self.device == "cpu" and remembered is None:
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
                part = ids[start:start + self.head.max_tokens][None].to(self.device)
                hidden = self.model(input_ids=part, use_cache=False).last_hidden_state
                total += hidden[0].float().sum(0).double().cpu().numpy()
                count += part.shape[1]
        return (total / count).astype(np.float32) if count else np.zeros(total.shape, dtype=np.float32)

    def close(self) -> None:
        """Trả RAM / VRAM và số luồng torch."""
        torch = self.torch
        self.model = None
        gc.collect()
        try:
            if self.device == "cuda":
                torch.cuda.empty_cache()
            else:
                torch.set_num_threads(self.threads)
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
    head = Head(directory / HEAD_FILE)
    package = package_sha(directory)
    cache_path = project_root / CACHE_FILE
    cache = _load_cache(cache_path)
    used: set[str] = set()
    embedder: _Embedder | None = None
    items: list[dict[str, Any]] = []
    embedded = 0
    dirty = finished = False

    try:
        for script in music_plan.book_scripts(project_root):
            segments = [segment for segment in script.get("segments") or [] if isinstance(segment, dict)]
            position = {segment.get("id"): index for index, segment in enumerate(segments)}
            scenes = music_scenes.chapter_scenes(script)
            spans = [(position.get(scene["firstSegment"]), position.get(scene["lastSegment"])) for scene in scenes]
            if not scenes or any(first is None or last is None for first, last in spans):
                continue
            texts = [music_moods.scene_text(segments, first, last) for first, last in spans]
            keys = [hashlib.sha256(text.encode("utf-8")).hexdigest() + package for text in texts]
            used.update(keys)
            for text, key in zip(texts, keys):
                if key in cache:
                    continue
                while pause_requested() and not stop_requested():
                    time.sleep(1.0)
                if stop_requested():
                    return embedded
                if embedder is None:
                    embedder = _Embedder(directory, head, text)
                cache[key] = embedder.embed(text)
                embedded += 1
                dirty = True
            deviations = head.deviations([cache[key] for key in keys], [max(1, len(text.split())) for text in texts])
            items += [{"chapterId": scene["chapterId"], "firstSegment": scene["firstSegment"], "lastSegment": scene["lastSegment"],
                       "dV": round(float(dev[0]), 4), "dE": round(float(dev[1]), 4), "dT": round(float(dev[2]), 4)}
                      for scene, dev in zip(scenes, deviations)]
            atomic_write_json(project_root / FILE, {"version": VERSION, "package": package, "built": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                                                    "scenes": items})
            log(f"Hình không khí trong chương: xong chương {script.get('chapterId')} ({len(items)} đoạn)")
            if dirty:
                _save_cache(cache_path, cache)
                dirty = False
        finished = True
        return embedded
    finally:
        if finished:  # làm trọn cuốn: bỏ nhúng của đoạn / gói không còn dùng
            if dirty or any(key not in used for key in cache):
                _save_cache(cache_path, {key: vector for key, vector in cache.items() if key in used})
        elif dirty:  # dừng giữa chương / lỗi: phần đã nhúng vẫn ghi
            _save_cache(cache_path, cache)
        if embedder is not None:
            embedder.close()


def run_after_analysis(project_root: Path, stop_requested: Callable[[], bool], log: Callable[[str], None],
                       emit: Callable[[str, dict[str, Any]], None], pause_requested: Callable[[], bool] = lambda: False) -> None:
    """Móc của dây chuyền sau pha phân tích (worker.py): đoán hình không khí trong chương nếu máy có gói model và nhạc nền của cuốn không
    tắt. KHÔNG BAO GIỜ ném: mọi lỗi (thiếu gói / RAM / VRAM, torch hỏng) thành MỘT dòng log, nhạc chạy đường hôm nay."""
    from . import music_plan

    try:
        if not available() or not music_plan.read_overrides(project_root)["enabled"]:
            return
        embedded = compute(project_root, stop_requested=stop_requested, log=log, pause_requested=pause_requested)
        emit("music_scene_student_done", {"embedded": embedded})
    except Exception as error:  # noqa: BLE001 - tuỳ chọn: lỗi gì cũng chỉ là không có hình không khí
        log(f"Bỏ qua hình không khí trong chương: {type(error).__name__}: {error}")
