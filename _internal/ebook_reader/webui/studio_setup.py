"""Cài Studio (phần làm sách nói) từ trong app Windows đóng gói - docs/PACKAGING.md bước 5.

App đóng gói chỉ mang phần nghe (Python nhúng, ~30 MB). Studio - thư viện của dây chuyền, model, Ollama, ~15-20 GB -
chỉ tải khi người dùng bấm "Cài Studio". Mọi thứ nằm trong MỘT thư mục (`%LOCALAPPDATA%\\ABook\\Studio`): không đụng
PATH, không cài gì toàn máy; mỗi công cụ tải về là một bản ghim cứng (URL + SHA-256), thư viện là đúng danh sách của
runtime đã làm ra sách (`shell/python/studio-requirements.txt`). Từng bước có dấu hoàn tất: mất mạng hay tắt máy giữa
chừng thì bấm lại là làm tiếp từ bước dở (file tải dở giữ ở `.part`, tải tiếp bằng Range).

Chạy ở một luồng nền của host (webui/host.py); giao diện hỏi `status()`. Không hỏi gì giữa chừng (AGENTS.md).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

STUDIO_FOLDER = "Studio"
# Trong thư mục dự án: bản mã nào đã bắt đầu cuốn này (StudioSetup.code_for).
CODE_PIN_FILE = "studio_code.json"
CREATE_NO_WINDOW = 0x08000000
# Thư viện ~6 GB, model ~10 GB, Ollama ~1,5 GB, cộng chỗ cho bản tải dở và cache.
MIN_FREE_BYTES = 30 * 1024**3
PYTHON_VERSION = "3.11"
# Ollama RIÊNG của Studio (chủ sách 28-09: phụ thuộc nằm trọn trong app, gỡ là gỡ hết): bản trong Studio\tools\ollama,
# model trong Studio\models\ollama, "home" (khoá định danh) trong Studio\ollama-home, cổng riêng - không bao giờ dùng
# hay đụng Ollama cài sẵn trên máy (máy có sẵn Ollama ở 11434 vẫn chạy song song được).
OLLAMA_PORT = 11439
OLLAMA_ADDRESS = f"http://127.0.0.1:{OLLAMA_PORT}"


@dataclass(frozen=True)
class Download:
    name: str
    url: str
    sha256: str
    size: int


# Nâng: đổi URL + băm (GitHub cho sẵn `digest` của từng tệp: gh api repos/<repo>/releases/latest), thử cài lại.
UV = Download("uv", "https://github.com/astral-sh/uv/releases/download/0.12.19/uv-x86_64-pc-windows-msvc.zip",
              "6dbb02d79e419522f1c500f0adb1cddcff0cda7d59b0d66ea7f5e3b4a1b2f5f0", 17_955_780)
# runtime_contract đòi UTMOSv2 cài từ git (vcs_info.commit_id) - MinGit là bản Git nhúng chính thức của Git for Windows.
MINGIT = Download("git", "https://github.com/git-for-windows/git/releases/download/v2.55.0.windows.5/"
                  "MinGit-2.55.0.5-64-bit.zip",
                  "56d7b226b7693196cfc71fef26568f536c4a021ab6c37ff2db4287bed908e96e", 38_989_688)
# Ollama: ĐÚNG bản dây chuyền đã được đo và kiểm (máy dev 0.33.2 - mọi lượt đo model, mọi cuốn đã làm), không phải bản
# mới nhất. Thử thật 28-09 với 0.34.4: cùng prompt, qwen3:8b sinh 360 token thay vì 61 (bản mới cho model "suy nghĩ" trước
# khi trả JSON) -> hết ngân sách đầu ra, cuốn thử hỏng ở khâu phân tích. Nâng Ollama là một phiên bản dây chuyền: đo lại
# trên bộ LN rồi mới đổi ghim (Studio đã cài tự biết phải cập nhật - `outdated`).
OLLAMA = Download("ollama", "https://github.com/ollama/ollama/releases/download/v0.33.2/ollama-windows-amd64.zip",
                  "2439cbea65310b1aadf7d8fc41d7faf5d033f920d42e00a476c58bf9bff6950e", 1_460_134_793)


@dataclass(frozen=True)
class PublishedModel:
    """Model phân tích tự huấn luyện, đăng trên Hugging Face (chủ sách 28-09: đăng công khai để Studio tải về;
    scripts/publish_model.py). Đường tải ghim theo commit. `parts`: thường một file; nhiều phần thì ghép theo thứ tự (nơi
    đăng giới hạn cỡ mỗi tệp). `sha256` là băm của CẢ file, cũng là digest lớp model trong Ollama: Ollama kiểm lại khi
    nhận, và model tạo từ đúng file ấy trùng từng byte bản đã đo trên máy dev (thử 28-09: /api/create chỉ với `files` cho
    cùng lớp cấu hình và lớp model như `ollama create` của serve_lora.py).
    """

    name: str
    parts: tuple[Download, ...]
    sha256: str
    size: int


# Tên model trong cài đặt phân tích (config.py) -> nơi tải. Model không có ở đây kéo từ kho Ollama như cũ.
PUBLISHED_MODELS: dict[str, PublishedModel] = {
    # docs/models/abook-analyzer-v3.md - Qwen3-4B-Instruct-2507 + LoRA trên đáp án của dự án, GGUF Q8_0 (lora28v3-4b).
    "abook-analyzer:v3": PublishedModel(
        "abook-analyzer:v3",
        (Download("abook-analyzer-v3.Q8_0.gguf",
                  "https://huggingface.co/NGDtuanh/abook-analyzer/resolve/8b19e96c5e5b2bd8453ebdd2105ea4b44e7d8054/"
                  "abook-analyzer-v3.Q8_0.gguf",
                  "9545ce0bf921f3b771a796272b736d043dc4082cb14d1a51fcc93c55e4c53778", 4_280_403_328),),
        "9545ce0bf921f3b771a796272b736d043dc4082cb14d1a51fcc93c55e4c53778",
        4_280_403_328,
    ),
}

# (mã, nhãn cho người dùng, ước lượng cho người dùng)
STEPS: tuple[tuple[str, str, str], ...] = (
    ("check", "Kiểm tra máy", "card NVIDIA, chỗ trống trên ổ đĩa"),
    ("uv", "Công cụ cài đặt", "18 MB"),
    ("git", "Git nhúng", "39 MB"),
    ("python", "Python 3.11", "30 MB"),
    ("vcruntime", "Thư viện C++ của Microsoft", "2 MB - đi kèm bộ cài"),
    ("packages", "Thư viện làm sách", "~6 GB - bước lâu nhất"),
    ("ollama", "Ollama", "1,5 GB - bản riêng của Studio"),
    ("llm", "Model phân tích truyện", "~5 GB"),
    ("voice", "Model giọng đọc", "~1 GB"),
    ("asr", "Model nghe lại (Whisper)", "~3 GB"),
    ("qa", "Model chấm chất lượng", "~1 GB"),
    ("verify", "Kiểm tra lần cuối", "thử nạp mọi thứ"),
)


class SetupError(Exception):
    """Lỗi đọc được cho người dùng: vì sao dừng, làm gì tiếp."""


class Cancelled(Exception):
    pass


def default_root() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    return Path(base) / "ABook" / STUDIO_FOLDER


def nvidia_gpu() -> dict[str, Any] | None:
    """Card NVIDIA đầu tiên qua NVML (nvml.dll đi cùng driver) - không cần torch hay nvidia-smi trong PATH."""
    try:
        import ctypes

        nvml = ctypes.WinDLL("nvml.dll") if os.name == "nt" else ctypes.CDLL("libnvidia-ml.so.1")
        if nvml.nvmlInit_v2() != 0:
            return None
        try:
            count = ctypes.c_uint()
            if nvml.nvmlDeviceGetCount_v2(ctypes.byref(count)) != 0 or count.value == 0:
                return None
            handle = ctypes.c_void_p()
            if nvml.nvmlDeviceGetHandleByIndex_v2(0, ctypes.byref(handle)) != 0:
                return None
            name = ctypes.create_string_buffer(96)
            nvml.nvmlDeviceGetName(handle, name, 96)

            class Memory(ctypes.Structure):
                _fields_ = [("total", ctypes.c_ulonglong), ("free", ctypes.c_ulonglong), ("used", ctypes.c_ulonglong)]

            memory = Memory()
            nvml.nvmlDeviceGetMemoryInfo(handle, ctypes.byref(memory))
            return {"name": name.value.decode("utf-8", "replace"), "memory": int(memory.total)}
        finally:
            nvml.nvmlShutdown()
    except (OSError, AttributeError):
        return None


def download(item: Download, target: Path, progress: Callable[[int, int], None], cancelled: Callable[[], bool]) -> Path:
    """Tải về `target` (ghi `.part`, tải tiếp bằng Range), kiểm SHA-256 rồi mới đổi tên. Sai băm: xoá, báo lỗi."""
    if target.is_file() and _sha256(target) == item.sha256:
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    part = target.with_name(target.name + ".part")
    for attempt in range(5):
        have = part.stat().st_size if part.is_file() else 0
        request = urllib.request.Request(item.url, headers={"Range": f"bytes={have}-"} if have else {})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                if have and response.status != 206:
                    have = 0  # máy chủ không nhận Range: tải lại từ đầu
                with part.open("ab" if have else "wb") as handle:
                    done = have
                    while chunk := response.read(1 << 20):
                        if cancelled():
                            raise Cancelled()
                        handle.write(chunk)
                        done += len(chunk)
                        progress(done, item.size)
            break
        except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
            if attempt == 4:
                raise SetupError(f"Không tải được {item.name} ({error}). Kiểm tra mạng rồi bấm Cài tiếp.") from error
            time.sleep(3 * (attempt + 1))
    actual = _sha256(part)
    if actual != item.sha256:
        part.unlink(missing_ok=True)
        raise SetupError(f"{item.name} tải về không đúng bản đã ghim (SHA-256 {actual[:12]}…) - đã xoá, bấm Cài tiếp để tải lại.")
    os.replace(part, target)
    return target


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def _unzip(archive: Path, folder: Path) -> None:
    temporary = folder.with_name(folder.name + ".part")
    shutil.rmtree(temporary, ignore_errors=True)
    with zipfile.ZipFile(archive) as bundle:
        bundle.extractall(temporary)
    shutil.rmtree(folder, ignore_errors=True)
    os.replace(temporary, folder)


# ---- đoạn mã chạy trong venv của Studio: hằng số lấy từ runtime_contract (một nguồn sự thật) ----------------------

# Model giọng ghim đúng revision của runtime_contract (bản dev không ghim lúc cài - setup_windows.ps1 nạp VieNeu trực
# tuyến, ai cài sau khi upstream đổi thì hợp đồng hỏng). Bộ mã hoá âm MOSS tải trước, rồi nạp thử OFFLINE đúng như
# worker (_apply_model_network_policy): lần nạp không được tự kéo revision mới và đẩy refs/main khỏi bản ghim.
# Nạp thử cần GPU: VieNeu v3 Turbo gọi torch.cuda.is_bf16_supported() vô điều kiện, không nạp được trên CPU (thử 28-09).
# Lúc cài Studio chưa có cuốn nào chạy (chưa có Studio để chạy) nên không tranh GPU với sách. ABOOK_STUDIO_SKIP_GPU_LOAD=1
# chỉ để thử trình cài trên máy dev khi hàng GPU đang bận - bỏ nạp thử, giữ mọi phép kiểm file.
VOICE_SCRIPT = r"""
import os, sys
from pathlib import Path
from huggingface_hub import snapshot_download
from ebook_reader import runtime_contract as c
hub = Path(os.environ["HF_HUB_CACHE"])
for extra in ("OpenMOSS-Team/MOSS-Audio-Tokenizer-Nano", "OpenMOSS-Team/MOSS-Audio-Tokenizer-Nano-ONNX"):
    snapshot_download(repo_id=extra, cache_dir=str(hub))
repo = c.VIENEU_CACHE_REPOSITORY.removeprefix("models--").replace("--", "/", 1)
snapshot_download(repo_id=repo, revision=c.VIENEU_CACHE_REVISION, cache_dir=str(hub))
ref = hub / c.VIENEU_CACHE_REPOSITORY / "refs" / "main"
ref.parent.mkdir(parents=True, exist_ok=True)
ref.write_text(c.VIENEU_CACHE_REVISION, encoding="utf-8")
result = c.voice_model_check(Path(os.environ["EBOOK_READER_RUNTIME"]))
assert result["ok"], result["detail"]
if os.environ.get("ABOOK_STUDIO_SKIP_GPU_LOAD") != "1":
    for name in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_DATASETS_OFFLINE"):
        os.environ[name] = "1"
    sys.modules["huggingface_hub.constants"].HF_HUB_OFFLINE = True
    from ebook_reader.character_registry import VIENEU_PRESETS
    from ebook_reader.config import build_settings
    from ebook_reader.tts import VieNeuEngine
    engine = VieNeuEngine(build_settings(), print)
    engine.load()
    missing = {preset["name"] for preset in VIENEU_PRESETS} - set(engine.voices)
    assert not missing, f"VieNeu thiếu giọng: {sorted(missing)}"
    engine.unload()
    print("VieNeu nạp được,", len(VIENEU_PRESETS), "giọng")
print("VieNeu", c.VIENEU_CACHE_REVISION[:12], "ok")
"""

# Cả hai bộ nhận dạng: asr.engine chọn được một trong hai (setup_windows.ps1 cũng cài cả hai).
ASR_SCRIPT = r"""
import os
from pathlib import Path
import whisper
from faster_whisper import WhisperModel
root = Path(os.environ["EBOOK_READER_RUNTIME"]) / "models" / "whisper"
root.mkdir(parents=True, exist_ok=True)
model = whisper.load_model("turbo", device="cpu", download_root=str(root))
del model
model = WhisperModel("turbo", device="cpu", compute_type="int8")
del model
print("Whisper turbo + faster-whisper turbo ok")
"""

QA_SCRIPT = r"""
import datetime, hashlib, json, os
from pathlib import Path
from huggingface_hub import hf_hub_download, snapshot_download
from ebook_reader import runtime_contract as c
runtime = Path(os.environ["EBOOK_READER_RUNTIME"])
hub = Path(os.environ["HF_HUB_CACHE"])
root = runtime / "models" / "utmosv2"
root.mkdir(parents=True, exist_ok=True)
marker = root / c.PERCEPTUAL_CACHE_MARKER_FILENAME
marker.unlink(missing_ok=True)
checkpoint = Path(hf_hub_download(repo_id="sarulab-speech/UTMOSv2", filename=c.UTMOS_CHECKPOINT_FILENAME,
                                  revision=c.UTMOS_CHECKPOINT_REVISION, local_dir=str(root)))
with checkpoint.open("rb") as handle:
    assert hashlib.file_digest(handle, "sha256").hexdigest() == c.UTMOS_CHECKPOINT_SHA256, "UTMOSv2 checkpoint sha256"
snapshot_download(repo_id="facebook/wav2vec2-base", revision=c.WAV2VEC2_CACHE_REVISION, cache_dir=str(hub),
                  allow_patterns=["config.json", "preprocessor_config.json", "pytorch_model.bin"])
snapshot_download(repo_id="timm/tf_efficientnetv2_s.in21k_ft_in1k", revision=c.TIMM_CACHE_REVISION, cache_dir=str(hub),
                  allow_patterns=["model.safetensors"])
for repository, revision in ((c.WAV2VEC2_CACHE_REPOSITORY, c.WAV2VEC2_CACHE_REVISION),
                             (c.TIMM_CACHE_REPOSITORY, c.TIMM_CACHE_REVISION)):
    ref = hub / repository / "refs" / "main"
    ref.parent.mkdir(parents=True, exist_ok=True)
    ref.write_text(revision, encoding="utf-8")
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
from utmosv2 import create_model
model = create_model(pretrained=True, config=c.UTMOS_MODEL_CONFIG, fold=c.UTMOS_MODEL_FOLD, checkpoint_path=str(checkpoint),
                     seed=c.UTMOS_MODEL_SEED, device="cpu")
del model
payload = {
    "schema_version": c.PERCEPTUAL_CACHE_SCHEMA_VERSION,
    "completed_at": datetime.datetime.now().astimezone().isoformat(),
    "checkpoint_revision": c.UTMOS_CHECKPOINT_REVISION,
    "checkpoint_sha256": c.UTMOS_CHECKPOINT_SHA256.upper(),
    "wav2vec2_revision": c.WAV2VEC2_CACHE_REVISION,
    "timm_backbone_revision": c.TIMM_CACHE_REVISION,
    "checkpoint_path": str(checkpoint),
    "model_config": c.UTMOS_MODEL_CONFIG,
    "fold": c.UTMOS_MODEL_FOLD,
    "seed": c.UTMOS_MODEL_SEED,
    "hf_home": os.environ["HF_HOME"],
}
temporary = marker.with_name(marker.name + ".part")
temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
os.replace(temporary, marker)
result = c.perceptual_cache_check(runtime)
assert result["ok"], result["detail"]
print("UTMOSv2 ok")
"""

VERIFY_SCRIPT = r"""
import os
from pathlib import Path
import torch
assert torch.cuda.is_available(), "PyTorch không thấy card NVIDIA (CUDA)"
from ebook_reader.runtime_contract import runtime_contract_errors
errors = runtime_contract_errors(Path(os.environ["EBOOK_READER_RUNTIME"]))
assert not errors, "; ".join(errors)
if os.environ.get("ABOOK_STUDIO_SKIP_GPU_LOAD") != "1":
    print("GPU:", torch.cuda.get_device_name(0))
print("hợp đồng runtime ok")
"""


class StudioSetup:
    """Cài / kiểm Studio trong `root`. `app_root` là thư mục chứa `ebook_reader` và `studio-requirements.txt` (thư
    mục `app` của bản cài). Các hàm bên ngoài (tải, chạy lệnh, dò GPU) truyền vào được để thử không cần mạng."""

    def __init__(
        self,
        root: Path,
        app_root: Path,
        *,
        fetch: Callable[..., Path] = download,
        gpu: Callable[[], dict[str, Any] | None] = nvidia_gpu,
        analysis_model: str = "qwen3:8b",
        ollama_address: str = OLLAMA_ADDRESS,
    ) -> None:
        self.root = root
        self.app_root = app_root
        self.fetch = fetch
        self.gpu = gpu
        self.analysis_model = analysis_model
        self.ollama_address = ollama_address
        self.runtime = root / "runtime"
        self.venv = self.runtime / ".venv"
        self.tools = root / "tools"
        self.state_path = root / "setup.json"
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._cancel = threading.Event()
        self._process: subprocess.Popen[str] | None = None
        self._step: str | None = None
        self._progress: tuple[int, int] | None = None
        self._detail = ""

    # ---- trạng thái -------------------------------------------------------------------------------------------

    @property
    def python(self) -> Path:
        return self.venv / "Scripts" / "python.exe"

    @property
    def pythonw(self) -> Path:
        return self.venv / "Scripts" / "pythonw.exe"

    def installed(self) -> bool:
        return (self.runtime / ".setup_complete").is_file() and self.pythonw.is_file()

    def _state(self) -> dict[str, Any]:
        try:
            state = json.loads(self.state_path.read_text(encoding="utf-8"))
            return state if isinstance(state, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save(self, **changes: Any) -> None:
        state = {**self._state(), **changes, "updated": time.time()}
        self.root.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_name(self.state_path.name + ".part")
        temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, self.state_path)

    def _pins(self) -> dict[str, str]:
        """Bản ghim của các bước tải công cụ/model. App lên bản mới đổi ghim (nâng uv, Git, Ollama, đổi model phân tích)
        thì bước ấy phải chạy lại trên Studio đã cài - không thì Studio cứ chạy bản cũ mà app không hề biết."""
        return {"uv": UV.sha256, "git": MINGIT.sha256, "ollama": OLLAMA.sha256, "llm": self.analysis_model}

    def outdated(self) -> list[str]:
        """Bước đã xong nhưng bằng bản ghim khác bản app này mang (Studio cài từ bản app cũ hơn)."""
        state = self._state()
        done = set(state.get("done") or [])
        pins = state.get("pins") or {}
        return [step for step, pin in self._pins().items() if step in done and pins.get(step) != pin]

    def status(self) -> dict[str, Any]:
        state = self._state()
        outdated = set(self.outdated())
        done = set(state.get("done") or []) - outdated
        running = self._thread is not None and self._thread.is_alive()
        progress = self._progress if running else None
        return {
            "installed": self.installed(),
            "outdated": [label for step, label, _hint in STEPS if step in outdated],
            "running": running,
            "step": self._step if running else None,
            "steps": [{"id": step, "label": label, "hint": hint, "done": step in done} for step, label, hint in STEPS],
            "progress": {"done": progress[0], "total": progress[1]} if progress else None,
            "detail": self._detail if running else "",
            "error": None if running else state.get("error"),
            "gpu": state.get("gpu"),
            "root": str(self.root),
        }

    # ---- điều khiển -------------------------------------------------------------------------------------------

    def start(self) -> dict[str, Any]:
        with self._lock:
            if not (self._thread is not None and self._thread.is_alive()) and (not self.installed() or self.outdated()):
                self._cancel.clear()
                self._thread = threading.Thread(target=self._run_all, name="studio-setup", daemon=True)
                self._thread.start()
        return self.status()

    def cancel(self) -> dict[str, Any]:
        self._cancel.set()
        process = self._process
        if process is not None and process.poll() is None:
            process.kill()
        return self.status()

    def remove(self) -> dict[str, Any]:
        """Gỡ Studio: dừng mọi tiến trình chạy từ thư mục Studio (Ollama riêng, worker) rồi xoá cả thư mục - thư viện,
        model (kể cả model Ollama), công cụ, bản mã của sách dở. Sách đã làm, chỗ nghe, dữ liệu app nằm chỗ khác - giữ
        nguyên. Ollama cài sẵn của người dùng (nếu có) không bao giờ bị đụng."""
        self.cancel()
        self.wait(30)
        self.stop_processes()

        def writable(function: Callable[..., Any], path: str, _error: Any) -> None:
            os.chmod(path, 0o700)  # MinGit có file chỉ-đọc
            function(path)

        if self.root.exists():
            if sys.version_info >= (3, 12):
                shutil.rmtree(self.root, onexc=writable)
            else:  # Python dev 3.11 (Python nhúng của app là 3.14)
                shutil.rmtree(self.root, onerror=writable)
        return self.status()

    def stop_processes(self, folder: Path | None = None) -> list[int]:
        """Dừng các tiến trình chạy từ thư mục Studio - hay một thư mục con của nó (`folder`) - theo đường dẫn file chạy,
        không theo tên: pythonw.exe của người dùng không bị đụng. Trả mã các tiến trình đã dừng."""
        import psutil

        root = str((folder or self.root).resolve()).casefold()
        stopped: list[int] = []
        for process in psutil.process_iter(["pid", "exe"]):
            executable = str(process.info.get("exe") or "").casefold()
            if executable.startswith(root + os.sep) and process.info["pid"] != os.getpid():
                try:
                    process.kill()
                    stopped.append(int(process.info["pid"]))
                except psutil.Error:
                    continue
        psutil.wait_procs([psutil.Process(pid) for pid in stopped if psutil.pid_exists(pid)], timeout=10)
        return stopped

    def wait(self, timeout: float | None = None) -> None:
        thread = self._thread
        if thread is not None:
            thread.join(timeout)

    def code_for(self, project_root: Path) -> Path:
        """Thư mục mã chạy cuốn này. Đổi một file khoá chất lượng là cuốn đang làm dở không làm tiếp được (AGENTS.md),
        mà app tự cập nhật - nên cuốn nào cũng chạy bằng đúng bản mã đã bắt đầu nó: lần chạy đầu chép mã của app vào
        `Studio\\code\\<hash chất lượng>` và ghi dấu vào dự án, các lần sau (kể cả sau khi app lên bản mới) dùng lại."""
        pin = project_root / CODE_PIN_FILE
        try:
            code_id = str(json.loads(pin.read_text(encoding="utf-8"))["code"])
        except (OSError, ValueError, KeyError, TypeError):
            code_id = ""
        if code_id:
            folder = self.root / "code" / code_id
            if not (folder / "ebook_reader").is_dir():
                raise SetupError(f"Mất bản mã đã làm cuốn này ({folder}) - cuốn này phải làm lại bằng bản hiện tại.")
            return folder
        from ..quality_policy import quality_implementation_hash

        code_id = quality_implementation_hash()[:16]
        folder = self.root / "code" / code_id
        if not (folder / "ebook_reader").is_dir():
            temporary = folder.with_name(folder.name + ".part")
            shutil.rmtree(temporary, ignore_errors=True)
            shutil.copytree(self.app_root / "ebook_reader", temporary / "ebook_reader",
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            for name in ("pyproject.toml", "uv.lock"):  # nằm trong hash chất lượng
                if (self.app_root / name).is_file():
                    shutil.copy2(self.app_root / name, temporary / name)
            os.replace(temporary, folder)
        payload = {"code": code_id, "since": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
        temporary_pin = pin.with_name(pin.name + ".part")
        temporary_pin.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        os.replace(temporary_pin, pin)
        return folder

    def environment(self, code: Path | None = None) -> dict[str, str]:
        """Biến môi trường cho worker và các lệnh cài: runtime của Studio, mã (của cuốn đang chạy - `code_for`; mặc định
        mã của app), Ollama + Git của Studio trong PATH (dây chuyền tìm `ollama` bằng shutil.which) - Ollama ấy nghe cổng
        riêng và giữ model trong Studio, kể cả khi dây chuyền tự khởi động lại nó."""
        models = self.runtime / "models"
        path = [str(self.tools / "ollama"), str(self.tools / "git" / "cmd")]
        return {
            "OLLAMA_HOST": f"127.0.0.1:{self.ollama_address.rsplit(':', 1)[-1]}",
            "OLLAMA_MODELS": str(models / "ollama"),
            "EBOOK_READER_RUNTIME": str(self.runtime),
            "PYTHONPATH": str(code or self.app_root),
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
            "HF_HOME": str(models / "huggingface"),
            "HF_HUB_CACHE": str(models / "huggingface" / "hub"),
            "HF_HUB_DISABLE_XET": "1",
            # Windows không bật Developer Mode không cho tạo symlink. huggingface_hub 1.29 tự dò và chuyển sang chép
            # file, nhưng dò có tranh chấp: nó ghi tạm "được" trước khi thử, luồng tải song song đọc trúng giá trị tạm
            # và tạo symlink -> WinError 1314 (thử cài thật 28-09). Luôn chép file.
            "HF_HUB_DISABLE_SYMLINKS": "1",
            "HF_HUB_DISABLE_SYMLINKS_WARNING": "1",
            "TORCH_HOME": str(models / "torch"),
            "UV_CACHE_DIR": str(self.root / "cache" / "uv"),
            "UV_PYTHON_INSTALL_DIR": str(self.root / "python"),
            # Python riêng của Studio, không bám vào Python cài sẵn trên máy (gỡ Python ấy là Studio hỏng).
            "UV_PYTHON_PREFERENCE": "only-managed",
            # Bộ nhớ đệm biên dịch JIT của CUDA (mặc định %APPDATA%\NVIDIA\ComputeCache): thử thật 28-09, một cuốn chạy
            # bằng Studio ghi 21 mục vào đó - thứ bộ gỡ không dọn được. Trỏ vào Studio (biến chuẩn của driver CUDA).
            "CUDA_CACHE_PATH": str(self.root / "cache" / "nvidia"),
            "PATH": os.pathsep.join(path + [os.environ.get("PATH", "")]),
        }

    # ---- các bước -----------------------------------------------------------------------------------------------

    def _run_all(self) -> None:
        self._save(error=None)
        try:
            outdated = set(self.outdated())
            ran = False
            for step, _label, _hint in STEPS:
                fresh = step in set(self._state().get("done") or []) and step not in outdated
                if fresh and not (step == "verify" and ran):  # cập nhật bước nào thì kiểm tra lần cuối lại
                    continue
                ran = True
                self._step, self._progress, self._detail = step, None, ""
                getattr(self, f"_step_{step}")()
                state, pins = self._state(), self._pins()
                self._save(done=sorted(set(state.get("done") or []) | {step}),
                           pins={**(state.get("pins") or {}), **({step: pins[step]} if step in pins else {})})
            self._write_marker()
        except Cancelled:
            self._save(error="Đã dừng - bấm Cài tiếp để làm tiếp từ bước dở.")
        except SetupError as error:
            self._save(error=str(error))
        except Exception as error:  # noqa: BLE001 - lỗi lạ không được làm sập host
            self._save(error=f"Lỗi ở bước {self._step}: {type(error).__name__}: {error}")
        finally:
            self._step, self._progress, self._process = None, None, None

    def _cancelled(self) -> bool:
        return self._cancel.is_set()

    def _set_progress(self, done: int, total: int) -> None:
        self._progress = (done, total)

    def _get(self, item: Download) -> Path:
        return self.fetch(item, self.root / "downloads" / item.url.rsplit("/", 1)[-1], self._set_progress, self._cancelled)

    def _install_archive(self, item: Download, folder: Path) -> None:
        archive = self._get(item)
        self.stop_processes(folder)  # cập nhật: bản cũ đang chạy (Ollama riêng) thì không thay file được
        _unzip(archive, folder)
        archive.unlink(missing_ok=True)  # gói nén của Ollama 1,5 GB: không giữ hai bản

    def _run(self, command: list[str], what: str) -> str:
        """Chạy một lệnh không hiện cửa sổ, ghi mọi dòng vào nhật ký, giữ dòng cuối làm chi tiết cho giao diện."""
        log = self.root / "logs" / "setup.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        environment = {**os.environ, **self.environment()}
        lines: list[str] = []
        with log.open("a", encoding="utf-8", buffering=1) as handle:  # theo dòng: đọc được ngay khi đang chạy
            handle.write(f"\n=== {time.strftime('%Y-%m-%d %H:%M:%S')} {what}: {' '.join(command)}\n")
            self._process = subprocess.Popen(
                command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                env=environment, cwd=str(self.root), creationflags=CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            assert self._process.stdout is not None
            for line in self._process.stdout:
                handle.write(line)
                text = line.strip()
                if text:
                    lines.append(text)
                    self._detail = text[-160:]
            code = self._process.wait()
        if self._cancelled():
            raise Cancelled()
        if code != 0:
            tail = " | ".join(lines[-3:])
            raise SetupError(f"{what} không xong (mã {code}): {tail[-400:]} - chi tiết ở {log}")
        return "\n".join(lines)

    def _step_check(self) -> None:
        gpu = self.gpu()
        if gpu is None:
            raise SetupError("Studio cần card đồ hoạ NVIDIA (dây chuyền đọc sách chạy bằng CUDA) - máy này không có, "
                             "hay driver NVIDIA chưa cài. Phần nghe sách vẫn dùng bình thường.")
        self._save(gpu=gpu)
        self.root.mkdir(parents=True, exist_ok=True)
        free = shutil.disk_usage(self.root).free
        if free < MIN_FREE_BYTES:
            raise SetupError(f"Ổ đĩa của {self.root} còn {free / 1024**3:.0f} GB - Studio cần khoảng 30 GB trống.")

    def _step_uv(self) -> None:
        self._install_archive(UV, self.tools / "uv")

    def _step_git(self) -> None:
        self._install_archive(MINGIT, self.tools / "git")

    def _uv(self) -> str:
        return str(self.tools / "uv" / "uv.exe")

    def _step_python(self) -> None:
        if not self.python.is_file():
            # Không --seed: pip/setuptools/wheel đi theo danh sách thư viện, đúng bản của runtime đã làm sách (torch
            # đòi setuptools<82; --seed cài bản mới nhất).
            self._run([self._uv(), "venv", "--python", PYTHON_VERSION, str(self.venv)], "Tạo Python 3.11")

    def _base_python(self) -> Path | None:
        """Thư mục Python gốc của venv (dòng `home` trong pyvenv.cfg) - thư mục ỨNG DỤNG của tiến trình Python thật (file
        python.exe trong venv chỉ là trình chuyển tiếp), nơi Windows tìm DLL trước System32."""
        try:
            for line in (self.venv / "pyvenv.cfg").read_text(encoding="utf-8").splitlines():
                key, _, value = line.partition("=")
                if key.strip().lower() == "home" and value.strip():
                    return Path(value.strip())
        except OSError:
            return None
        return None

    def _step_vcruntime(self) -> None:
        """VC++ runtime app-local: đo 28-09 trên Studio cài thật, torch/onnxruntime... nạp msvcp140.dll, msvcp140_1.dll từ
        System32 - tức cần VC++ Redistributable mà Windows sạch không có. Bộ cài mang sẵn đúng các file Microsoft cho phân
        phối lại (`app\\vcruntime`, scripts/build_windows_app.ps1); chép vào thư mục Python gốc - nơi được tìm TRƯỚC
        System32 - nên mọi thư viện dùng bản của Studio, máy có hay không có gói Redistributable cũng vậy. Không đè file
        Python đã mang sẵn (vcruntime140.dll của chính bản dựng Python). Bản dev (không có thư mục ấy): bỏ qua."""
        source = self.app_root / "vcruntime"
        base = self._base_python()
        if not source.is_dir() or base is None:
            return
        for dll in sorted(source.glob("*.dll")):
            target = base / dll.name
            if not target.exists():
                shutil.copy2(dll, target)

    def _requirements(self) -> Path:
        for candidate in (self.app_root / "studio-requirements.txt",
                          self.app_root / "shell" / "python" / "studio-requirements.txt"):
            if candidate.is_file():
                return candidate
        raise SetupError("Bản cài thiếu danh sách thư viện của Studio (studio-requirements.txt) - cài lại app.")

    def _step_packages(self) -> None:
        self._run([self._uv(), "pip", "install", "--python", str(self.python), "--no-deps",
                   "--index-strategy", "unsafe-best-match", "-r", str(self._requirements())], "Cài thư viện")
        # Chỉ ghi nhật ký, không chặn: runtime làm ra sách cũng có xung đột khai báo vô hại (datasets khai fsspec cũ
        # hơn bản đang dùng). Cửa chặn thật là bước "Kiểm tra lần cuối" - hợp đồng runtime nạp thật từng thư viện.
        try:
            self._run([self._uv(), "pip", "check", "--python", str(self.python)], "Kiểm thư viện (chỉ ghi nhật ký)")
        except SetupError:
            pass

    def settings_overrides(self) -> dict[str, Any]:
        """Cài đặt riêng cho sách tạo trong app đóng gói: khâu phân tích nói chuyện với Ollama riêng của Studio."""
        return {"analysis": {"base_url": self.ollama_address}}

    def _step_ollama(self) -> None:
        self._install_archive(OLLAMA, self.tools / "ollama")

    def _step_llm(self) -> None:
        """Kéo model phân tích qua API của Ollama (không gọi CLI `ollama`: khi máy chủ tắt nó tự mở app khay). Model của
        dự án (PUBLISHED_MODELS) không có trong kho Ollama: tải từ Hugging Face rồi nạp vào Ollama riêng."""
        self.ensure_ollama()
        published = PUBLISHED_MODELS.get(self.analysis_model)
        if published is not None:
            self._install_published(published)
            return
        request = urllib.request.Request(f"{self.ollama_address}/api/pull", method="POST",
                                         data=json.dumps({"model": self.analysis_model, "stream": True}).encode("utf-8"),
                                         headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                for raw in response:
                    if self._cancelled():
                        raise Cancelled()
                    event = json.loads(raw.decode("utf-8"))
                    if event.get("error"):
                        raise SetupError(f"Ollama không tải được {self.analysis_model}: {event['error']}")
                    if event.get("total"):
                        self._set_progress(int(event.get("completed") or 0), int(event["total"]))
                    self._detail = str(event.get("status") or "")
        except urllib.error.URLError as error:
            raise SetupError(f"Không nói chuyện được với Ollama ({error}) - bấm Cài tiếp để thử lại.") from error

    def _install_published(self, model: PublishedModel) -> None:
        """Tải từng phần (kiểm băm từng phần, tải tiếp được), đẩy CẢ file vào Ollama bằng /api/blobs - ghép ngay trên
        đường truyền, không ghi file ghép 4 GB ra đĩa - rồi /api/create. Cài tiếp sau khi hỏng giữa chừng: model đã có
        thì thôi, blob đã có thì chỉ còn tạo."""
        if self._ollama_has(model.name):
            return
        digest = f"sha256:{model.sha256}"
        if not self._ollama_blob(digest):
            parts: list[Path] = []
            before = 0
            for index, part in enumerate(model.parts, start=1):
                self._detail = f"Tải phần {index}/{len(model.parts)}"
                parts.append(self.fetch(part, self.root / "downloads" / part.name,
                                        lambda done, _total, base=before: self._set_progress(base + done, model.size),
                                        self._cancelled))
                before += part.size
            self._detail = "Nạp model vào Ollama"
            sent = 0

            def body():
                nonlocal sent
                for path in parts:
                    with path.open("rb") as handle:
                        while chunk := handle.read(1 << 20):
                            if self._cancelled():
                                raise Cancelled()
                            sent += len(chunk)
                            self._set_progress(sent, model.size)
                            yield chunk

            request = urllib.request.Request(f"{self.ollama_address}/api/blobs/{digest}", data=body(), method="POST",
                                             headers={"Content-Length": str(model.size),
                                                      "Content-Type": "application/octet-stream"})
            try:
                with urllib.request.urlopen(request, timeout=600):
                    pass
            except urllib.error.HTTPError as error:
                raise SetupError(f"Ollama không nhận model {model.name} (HTTP {error.code}) - bấm Cài tiếp để tải lại.") from error
            except urllib.error.URLError as error:
                raise SetupError(f"Không nói chuyện được với Ollama ({error}) - bấm Cài tiếp để thử lại.") from error
            for path in parts:
                path.unlink(missing_ok=True)  # Ollama đã giữ bản của nó: không để hai bản 4 GB trên đĩa
        self._detail = "Tạo model trong Ollama"
        file = re.sub(r"[^A-Za-z0-9._-]+", "-", model.name) + ".gguf"
        request = urllib.request.Request(
            f"{self.ollama_address}/api/create", method="POST", headers={"Content-Type": "application/json"},
            data=json.dumps({"model": model.name, "files": {file: digest}, "stream": False}).encode("utf-8"))
        try:
            with urllib.request.urlopen(request, timeout=600) as response:
                reply = json.loads(response.read().decode("utf-8") or "{}")
        except urllib.error.HTTPError as error:
            raise SetupError(f"Ollama không tạo được model {model.name} (HTTP {error.code}).") from error
        except urllib.error.URLError as error:
            raise SetupError(f"Không nói chuyện được với Ollama ({error}) - bấm Cài tiếp để thử lại.") from error
        if reply.get("status") != "success":
            raise SetupError(f"Ollama không tạo được model {model.name}: {reply.get('error') or reply}")

    def _ollama_has(self, name: str) -> bool:
        try:
            with urllib.request.urlopen(f"{self.ollama_address}/api/tags", timeout=10) as response:
                models = json.loads(response.read().decode("utf-8")).get("models") or []
        except (urllib.error.URLError, ValueError):
            return False
        return any(entry.get("name") == name or entry.get("model") == name for entry in models if isinstance(entry, dict))

    def _ollama_blob(self, digest: str) -> bool:
        try:
            with urllib.request.urlopen(urllib.request.Request(f"{self.ollama_address}/api/blobs/{digest}", method="HEAD"),
                                        timeout=10):
                return True
        except (urllib.error.URLError, ValueError):
            return False

    def ensure_ollama(self) -> None:
        """Ollama riêng của Studio đang nghe cổng riêng; chưa thì khởi động nó ẩn. "Home" của nó (USERPROFILE: khoá định
        danh, thư mục mặc định) đặt trong Studio, để gỡ Studio là không sót gì ở ~/.ollama - nơi có thể là Ollama của
        chính người dùng (không bao giờ đụng)."""
        if self._ollama_alive():
            return
        executable = self.tools / "ollama" / "ollama.exe"
        if not executable.is_file():
            raise SetupError("Không thấy Ollama của Studio - bấm Cài tiếp để tải lại.")
        home = self.root / "ollama-home"
        home.mkdir(parents=True, exist_ok=True)
        log = self.root / "logs" / "ollama.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        environment = {**os.environ, **self.environment(), "USERPROFILE": str(home), "HOME": str(home)}
        with log.open("ab") as handle:
            subprocess.Popen([str(executable), "serve"], stdout=handle, stderr=subprocess.STDOUT, env=environment,
                             cwd=str(home), creationflags=CREATE_NO_WINDOW if os.name == "nt" else 0)
        for _ in range(60):
            if self._ollama_alive():
                return
            time.sleep(0.5)
        raise SetupError(f"Ollama không khởi động được - xem {log}.")

    def _ollama_alive(self) -> bool:
        try:
            with urllib.request.urlopen(f"{self.ollama_address}/api/tags", timeout=3):
                return True
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            return False

    def _step_voice(self) -> None:
        self._run([str(self.python), "-c", VOICE_SCRIPT], "Tải model giọng")

    def _step_asr(self) -> None:
        self._run([str(self.python), "-c", ASR_SCRIPT], "Tải Whisper")

    def _step_qa(self) -> None:
        self._run([str(self.python), "-c", QA_SCRIPT], "Tải model chấm chất lượng")

    def _step_verify(self) -> None:
        # Hợp đồng runtime đòi dấu cài đặt: ghi thử, kiểm, hỏng thì gỡ dấu (lần sau chạy lại bước này).
        self._write_marker()
        try:
            self._run([str(self.python), "-c", VERIFY_SCRIPT], "Kiểm tra lần cuối")
        except Exception:
            (self.runtime / ".setup_complete").unlink(missing_ok=True)
            raise

    def _write_marker(self) -> None:
        from ..runtime_contract import PERCEPTUAL_CACHE_MARKER_FILENAME, SETUP_SCHEMA_VERSION

        marker = self.runtime / ".setup_complete"
        payload = {
            "schema_version": SETUP_SCHEMA_VERSION,
            "completed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "python": str(self.python),
            "internal_root": str(self.app_root),
            "perceptual_ready_marker": str(self.runtime / "models" / "utmosv2" / PERCEPTUAL_CACHE_MARKER_FILENAME),
            "installed_by": "studio_setup",
        }
        self.runtime.mkdir(parents=True, exist_ok=True)
        temporary = marker.with_name(marker.name + ".part")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, marker)
