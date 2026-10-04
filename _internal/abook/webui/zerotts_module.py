"""Mô-đun "Giọng ZeroTTS" của Studio: máy đọc ZeroTTS (ZeroWeight AI, ONNX, chạy CPU) để người nghe chọn tay cho một nhân vật trong
"Đổi giọng" (voice_catalog.ENGINE_VOICES). Như "Giọng Supertonic" (supertonic_module.py): bộ cài không mang gì, người dùng bấm mới tải, ghim
từng phần, biết phần nào cũ và chỉ tải phần ấy, gỡ được để lấy lại chỗ.

Các phần (`PARTS`):
- `code` gói pip `zerotts` (thuần Python, ~67 KB): wheel ghim, giải vào <dữ liệu app>/zerotts/lib. Thư viện nó cần (onnxruntime, tokenizers,
  numpy, scipy, soundfile) Studio đã có sẵn - dây chuyền chạy trong Python của Studio, không phải trong Python của app nghe.
- `zerotts` file model + năm giọng chủ sách chọn trên Hugging Face, ghim commit + SHA-256 từng file (`MODEL_FILES`). Gói `zerotts` tự tải
  bản `main` mới nhất (zerotts/hub.py) - ở đây KHÔNG dùng đường ấy: model đổi là audio đổi, nên ghim đúng commit đã đo.

Giấy phép: gói và trọng số MIT, bộ giải mã âm thanh MOSS (onnx/codec) Apache-2.0 - xem THIRD_PARTY.md.

Studio (tiến trình khác, không ai gọi `configure`) tìm mô-đun qua `locate()`: thư mục cạnh preferences.json, như server đặt.
"""
from __future__ import annotations

import os
import shutil
import sys
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import voice_module
from .music_module import Component
from .studio_setup import Download
from .voice_module import ModuleCore

FOLDER = "zerotts"
LIB_FOLDER = "lib"
MODEL_FOLDER = "model"
ENV_DOWNLOAD = "ABOOK_ZEROTTS_DOWNLOAD"  # "0" = không bao giờ tải (bộ kiểm đặt sẵn)
PACKAGE_VERSION = "0.1.5"  # = engine_versions["zerotts"] của voice_balance.json: khoá cân bằng đo trên đúng bản này

# Nâng: đổi URL + SHA-256 + cỡ (PyPI: https://pypi.org/pypi/zerotts/<số>/json; Hugging Face: /api/models/<repo>?blobs=true ở commit mới),
# đo lại cân bằng giọng (docs/VOICE_BALANCE.md) rồi đổi engine_versions - khoá cũ không áp nhầm cho bản mới.
CODE = Download("zerotts", "https://files.pythonhosted.org/packages/76/30/172226606ccfabfb78080c86c82e58b87fe6f21f2ca8619e8602e2fb5ba6/"
                f"zerotts-{PACKAGE_VERSION}-py3-none-any.whl", "9b4ceade901c224db33f675794c2c2f7c6d9190fd8f97b74c85efe62cef1c04b", 67_306)
SOURCE_REPO = "zeroweight-ai/ZeroTTS"
SOURCE_REVISION = "c2bfbd67dc648cac455077333f7cf5c18a2e3bb4"
_BASE = f"https://huggingface.co/{SOURCE_REPO}/resolve/{SOURCE_REVISION}/"
VOICES = ("baotrang", "giahuy", "huuduc", "kimoanh", "quangminh")  # = giọng ZeroTTS castable của voice_catalog.ENGINE_VOICES


def _file(name: str, sha256: str, size: int) -> Download:
    return Download(name, _BASE + name, sha256, size)


_VOICE_PINS = {
    "baotrang": "abbc5807cc4767e7c62cc59f7b7cd04b4b7e0dba176086447a0c114578cf695a",
    "giahuy": "3979a8369000eaaee1130801c1cacdadddc12e8d9a4a604be7430c4bcc6df32e",
    "huuduc": "d7a6370180263093eb9dd009661ba24b5309f0ba94ec18d8ff2323c80616a7eb",
    "kimoanh": "0aee413f25eae30123f930bd525d31a3b5a20c0803b4899305c2ff4a69466946",
    "quangminh": "4d2acb18f831ade23ed2d02e7b749fa745c95e9ee305795c5ddeb75f93d35fdb",
}
# Chỉ những file `ZeroTTS(model_dir)` cần. Không lấy: silence_frame.npy (chỉ dùng khi đọc liền mạch dài), voice.bin / preview.wav (không
# dùng), và meta.json của giọng - gói đọc nó bằng bảng mã mặc định của máy, tiếng Việt trong đó làm vỡ Python không bật UTF-8 (đo 04-10:
# "charmap codec can't decode" ở giahuy); thiếu file thì gói bỏ qua.
MODEL_FILES = (
    _file("config.json", "3676da6a9f4dba7a8f2d106d5c1fb02c491391dc19c91dae893133a7e219d666", 378),
    _file("tokenizer.json", "4fd646e8a1fd6694cb9c876c914a516ef8dd84b4f84db2605be1a7388885ae91", 191_542),
    _file("null_voice_emb.npy", "ec014c14f79e8fc16f4ca6ea557f33fa2cbd7d448b5de5f467aace9ca0321e9f", 30_848),
    _file("onnx/text_encoder.onnx", "d37557a4abe07953a02686a176664486e73838389a14ff4a3f36b47ac2bccd52", 323_096_725),
    _file("onnx/prefix_step.onnx", "b7544c9fdd3535b21fe8dea855407180ad2084f9da298f8a153893522496565b", 348_303_894),
    _file("onnx/local_frame_decode.onnx", "3c4540ef4e69dcf604dc6f60f6f99f119189694ff5f31113def20406e274f025", 186_743_011),
    _file("onnx/codec/codec_browser_onnx_meta.json", "32009d6ac1cd2663bbbf5c06d6835b3a862c02f7de121663071938f2edac8e92", 14_056),
    _file("onnx/codec/moss_audio_tokenizer_decode_full.onnx", "0fbbafe3fd4afa2a019af5c5ced204af6e2d1db044fa40f021525d2aee95b4ac", 681_902),
    _file("onnx/codec/moss_audio_tokenizer_decode_shared.data", "e69d52e0f4e84ca27850557ee54face46632d3a5a16c89bd246c7c408466dcad", 44_198_912),
    _file("onnx/codec/moss_audio_tokenizer_decode_step.onnx", "9527c86a29e1837edec1f74db57d5eeaadb3a715af3382703566460afed25855", 351_400),
    _file("onnx/codec/LICENSE-Apache-2.0.txt", "38ab08051cc3a06dd39507b77d7e8b928b563c49288eb7263339712652d41c6d", 359),
    *(_file(f"voices/{name}/voice.npz", sha256, 31_262) for name, sha256 in _VOICE_PINS.items()),
)
CHOICE = "zerotts"
PART_LABEL = {"code": "Bộ đọc ZeroTTS", CHOICE: "Giọng ZeroTTS"}

_core = ModuleCore("giọng ZeroTTS", "zerotts-module", frozenset(), lambda: installed() is not None)
_lock = _core.lock
pin = voice_module.pin


@dataclass(frozen=True)
class Installed:
    """Nơi mô-đun đặt mã (`lib`, đưa vào sys.path) và model (`model`, thư mục cho `ZeroTTS(model_dir)`)."""

    lib: Path
    model: Path


def configure(folder: Path | str | None) -> None:
    """Thư mục của mô-đun (server.py: <dữ liệu app>/zerotts)."""
    _core.configure(folder, None, None)


def locate() -> Installed | None:
    """Cho Studio (tiến trình dây chuyền không gọi `configure`): mô-đun ở chỗ server đặt, hay chỗ đã cấu hình."""
    _core.ensure_folder(FOLDER)
    return installed()


# ---- các phần ---------------------------------------------------------------------------------------------------------------------
def _dir(part: str) -> Path | None:
    return None if _core.folder is None else _core.folder / (LIB_FOLDER if part == "code" else MODEL_FOLDER)


def _complete(folder: Path | None) -> bool:
    return folder is not None and all((folder / item.name).is_file() for item in MODEL_FILES)


def _code_present() -> bool:
    lib = _dir("code")
    return lib is not None and (lib / "zerotts" / "synthesizer.py").is_file()


def _download_off() -> str:
    return "tải giọng ZeroTTS đang bị tắt trên máy này" if os.environ.get(ENV_DOWNLOAD, "1") == "0" else ""


def _parts() -> list[Component]:
    off = _download_off()
    return [
        Component("code", PART_LABEL["code"], pin((CODE,)), CODE.size, _code_present(), blocked=off, downloads=[CODE]),
        Component(CHOICE, PART_LABEL[CHOICE], pin(MODEL_FILES), sum(item.size for item in MODEL_FILES), _complete(_dir(CHOICE)),
                  blocked=off, downloads=list(MODEL_FILES)),
    ]


def _judged(parts: list[Component]) -> dict[str, str]:
    from .music_module import judge_parts

    return judge_parts(parts, _core.pins())


def installed() -> Installed | None:
    """Nơi mã + model nằm; None khi chưa đủ (chưa tải, hay mới tải một phần)."""
    if _core.folder is None or not _code_present() or not _complete(_dir(CHOICE)):
        return None
    lib, model = _dir("code"), _dir(CHOICE)
    assert lib is not None and model is not None
    return Installed(lib, model)


def status() -> dict[str, Any]:
    """Trạng thái cho "Đổi giọng": `state` missing / downloading / ready / outdated / error, tiến độ, dung lượng còn thiếu."""
    with _lock:
        if _core.folder is None:
            return {"state": "unsupported", "done": 0, "total": 0, "bytes": 0, "error": ""}
        parts = _parts()
        judged = _judged(parts)
        lacking = [part for part in parts if judged[part.id] != "current"]
        have = all(judged[part.id] != "missing" for part in parts)
        if _core.state["downloading"]:
            state = "downloading"
        elif _core.state["error"]:
            state = "error"
        elif have:
            state = "outdated" if lacking else "ready"
        else:
            state = "missing"
        return {
            "state": state, "done": _core.state["done"] if state == "downloading" else 0,
            "total": _core.state["total"] if state == "downloading" else 0, "error": _core.state["error"],
            "bytes": sum(part.size for part in lacking),
        }


# ---- tải, gỡ ----------------------------------------------------------------------------------------------------------------------
def _install(part: Component, progress: Callable[[int], None]) -> None:
    folder = _core.folder
    target = _dir(part.id)
    assert folder is not None and target is not None
    if part.id != "code":
        voice_module.download_files(part, target, progress)  # file model tải thẳng vào chỗ: chỉ thấy file đủ
        return
    wheel = folder / voice_module.DOWNLOADS / f"{CODE.name}.whl"
    from .studio_setup import download

    download(CODE, wheel, lambda have, _total: progress(have), lambda: False)
    staging = target.with_name(target.name + ".part")
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    with zipfile.ZipFile(wheel) as bundle:
        bundle.extractall(staging, [member for member in bundle.namelist() if member.startswith("zerotts/")])
    shutil.rmtree(target, ignore_errors=True)
    os.replace(staging, target)
    wheel.unlink(missing_ok=True)


def start() -> None:
    """Tải các phần còn thiếu hay đã cũ ở luồng nền."""
    with _lock:
        if _core.folder is None:
            raise ValueError("Mô-đun giọng ZeroTTS chưa được cấu hình")
        if _core.busy():
            return
        parts = _parts()
        judged = _judged(parts)
        _core.begin([part for part in parts if judged[part.id] != "current"], _install, lambda: None, lambda _changed: [])


def join(timeout: float | None = None) -> None:
    _core.join(timeout)


def remove() -> None:
    """Gỡ giọng ZeroTTS khỏi máy (mã + model). Sách đã thu giữ nguyên; câu nào còn phải thu bằng giọng này thì cần tải lại."""
    with _lock:
        if _core.folder is None:
            return
        if _core.busy():
            raise ValueError("Đang tải giọng ZeroTTS - chờ tải xong rồi hãy gỡ")
        for part in ("code", CHOICE):
            directory = _dir(part)
            if directory is not None:
                _core.remove(directory, part, "")


def import_engine(found: Installed) -> Any:
    """Lớp `ZeroTTS` từ mã đã tải. Giọng người dùng tự cài (~/.zerotts/voices) KHÔNG được che giọng đã ghim: gói đọc thư mục ấy lúc
    import, nên trỏ nó vào một chỗ trống của mô-đun trước."""
    os.environ["ZEROTTS_VOICES_HOME"] = str(found.lib.parent / "no_user_voices")
    if str(found.lib) not in sys.path:
        sys.path.insert(0, str(found.lib))
    from zerotts.synthesizer import ZeroTTS

    return ZeroTTS
