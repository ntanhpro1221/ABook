"""Mô-đun "Phân tích nhạc" của máy tính: mọi thứ bộ phân tích nhạc cần mà bộ cài KHÔNG mang (docs/MUSIC_IMPORT.md), quản lý như Studio.

Người dùng bấm "Phân tích nhạc" (ở màn Nhạc của tôi, hay ở một bài "chưa phân tích") thì mới tải - không bao giờ tự tải, kể cả lúc
nhập nhạc (nhập chạy không cần mô-đun: thẻ + độ dài đọc bằng tinytag). MỘT nút, MỘT thanh tiến độ, MỘT tổng dung lượng. Gồm tối đa ba phần,
tuỳ máy (`_components`):
- `ffmpeg`  (ffmpeg_setup.py, ~31 MB): giải mã cho model + đo độ to. Máy đã có ffmpeg (Studio, PATH) thì không tải.
- `libs`    (~27 MB): numpy + onnxruntime + ba gói nó đòi - wheel cp314 win_amd64 ghim URL + SHA-256, giải vào <dữ liệu app>/music/lib và thêm
            vào sys.path trước khi import. Máy đã import được (Studio, máy dev) thì không tải.
- `model`   (music_student.py, ~59 MB onnx / ~55 MB torch): gói model trên Hugging Face, ghim commit + SHA-256. Máy Studio (đã có torch + ffmpeg)
            chỉ cần phần này.
Cộng một phần TUỲ CHỌN `scene_q06` (music_scene_student.py, 0,71 GiB, "Học sinh không khí cảnh"): chỉ nằm trong danh sách khi người dùng bấm tải nó
hoặc nó đã nằm trên máy (khi đó cập nhật như mọi phần); thiếu nó mô-đun vẫn "ready".
Mỗi phần có "mã ghim" (`pin`). Lúc tải ghi dấu `module.json` (phần -> ghim đã tải); `status()` so dấu với ghim bản app này mang, KHÔNG băm lại
59 MB mỗi lần mở. App lên bản mới đổi ghim của phần nào thì phần ấy là "cũ" (state `outdated`, kèm danh sách phần và số byte phải tải); một
lần bấm chỉ tải các phần đổi, phần còn lại giữ nguyên - như Studio (`StudioSetup._pins/outdated`). Bản cũ vẫn chạy cho tới lúc cập nhật xong.
Cỡ "cần tải" của phần có thư mục đích riêng (`scene_q06`) chỉ tính các file còn thiếu hay sai SHA-256 (`Component.need`): cập nhật mà gói chỉ thêm một file
18 KB thì báo 18 KB, không phải 0,71 GiB, và thanh tiến độ cũng chạy trên chừng ấy. Kết quả băm nhớ theo (đường dẫn, cỡ, giờ sửa) - không băm lại 0,7 GB mỗi lần
giao diện hỏi `status()`.
Cập nhật KHÔNG tự phân tích lại các bài đã có: `stale` đếm bài phân tích bằng bản cũ, người dùng bấm "Phân tích lại" (`reanalyse`).

Thư viện (numpy/onnxruntime) đã nạp vào tiến trình thì không thay tại chỗ được: bản mới giải vào `lib.next`, đổi chỗ ở lần mở app sau
(`restart` true trong lúc chờ).
Giao diện hỏi `status()` ~mỗi giây trong lúc tải.
"""
from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json
import os
import shutil
import sys
import threading
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .. import io_utils
from . import ffmpeg_setup, music_local, music_student, studio_setup

STAMP_FILE = "module.json"
LIB_FOLDER = "lib"
LIB_NEXT = "lib.next"
DOWNLOADS = "lib.dl"
ENV_DOWNLOAD = "ABOOK_MUSIC_MODULE_DOWNLOAD"  # "0" = không bao giờ tải (bộ kiểm đặt sẵn)

# Thư viện của đường onnx cho Python 3.14 nhúng của bộ cài Windows (shell/python/requirements.txt đã bỏ chúng). Nâng: đổi URL + SHA-256 + cỡ
# từ PyPI (https://pypi.org/pypi/<tên>/<số>/json), thử lại bài thử của music_student. onnxruntime ghim 1.28.0 vì đó là bản đã đo khớp
# (numpy 2.4.6 cũng vậy). Giấy phép: docs/THIRD_PARTY.md.
WHEELS = (
    studio_setup.Download(
        "numpy", "https://files.pythonhosted.org/packages/df/ac/46de6dda46478f7942f839e094970be2d4a861e005c4b3bf07c92e291a09/"
        "numpy-2.4.6-cp314-cp314-win_amd64.whl", "b507f5c4c1d508876d1819b6bf9a49d365b96320b5d4993426b33a23ca4b8261", 12_450_334),
    studio_setup.Download(
        "onnxruntime", "https://files.pythonhosted.org/packages/bb/e2/6feb3a43517aaf2b1bf7e46897ba5eb81a29717f7d7901420614d5ee4653/"
        "onnxruntime-1.28.0-cp314-cp314-win_amd64.whl", "f2a3b9e30ce880d4ca54999cb313569e36da4f62eefe25f87be18f43e9a3a4d5", 14_093_738),
    studio_setup.Download(
        "flatbuffers", "https://files.pythonhosted.org/packages/e8/2d/d2a548598be01649e2d46231d151a6c56d10b964d94043a335ae56ea2d92/"
        "flatbuffers-25.12.19-py2.py3-none-any.whl", "7634f50c427838bb021c2d66a3d1168e9d199b0607e6329399f04846d42e20b4", 26_661),
    studio_setup.Download(
        "packaging", "https://files.pythonhosted.org/packages/df/b2/87e62e8c3e2f4b32e5fe99e0b86d576da1312593b39f47d8ceef365e95ed/"
        "packaging-26.2-py3-none-any.whl", "5fc45236b9446107ff2415ce77c807cee2862cb6fac22b8a73826d0693b0980e", 100_195),
    studio_setup.Download(
        "protobuf", "https://files.pythonhosted.org/packages/0a/19/8d0cb6f20a1ef7b18f1c8986ad5783f22f84cce39c6ce9a6e645ea55192e/"
        "protobuf-7.35.1-cp310-abi3-win_amd64.whl", "230a75ddfc2de4806e56696ce9640c1cdfdb6543b7cfce98d42a4c0a0e7bdb87", 439_996),
)
LIB_MODULES = ("numpy", "onnxruntime")

_lock = threading.RLock()
_folder: Path | None = None  # <dữ liệu app>/music
_thread: threading.Thread | None = None
_after: Callable[[], None] | None = None
_studio_installed: Callable[[], bool] | None = None
_job = ""  # việc nền đang chạy sau khi tải: "" | "analysing"
_state: dict[str, Any] = {"downloading": False, "done": 0, "total": 0, "error": ""}
_verified: dict[tuple[str, int, int, str], bool] = {}  # (đường dẫn, cỡ, giờ sửa, SHA-256 ghim) -> file đúng bản ghim


def file_ok(item: Any, path: Path) -> bool:
    """File `path` đã nằm đúng bản `item` ghim (cỡ + SHA-256). Nhớ theo (đường dẫn, cỡ, giờ sửa) để lần hỏi sau không băm lại; sai cỡ thì khỏi băm."""
    try:
        stat = path.stat()
    except OSError:
        return False
    if stat.st_size != item.size:
        return False
    key = (str(path), stat.st_size, stat.st_mtime_ns, item.sha256)
    with _lock:
        if key not in _verified:
            _verified[key] = studio_setup._sha256(path) == item.sha256
        return _verified[key]


def _remember_ok(item: Any, path: Path) -> None:
    """Vừa tải xong và `studio_setup.download` đã kiểm SHA-256: nhớ luôn để khỏi băm lại."""
    try:
        stat = path.stat()
    except OSError:
        return
    with _lock:
        _verified[(str(path), stat.st_size, stat.st_mtime_ns, item.sha256)] = True


@dataclass
class Component:
    id: str
    label: str
    pin: str
    size: int
    present: bool  # đã nằm trên máy (đủ file)
    external: bool = False  # máy đã có sẵn không do mô-đun (Studio, máy dev): không tải, không "cũ"
    blocked: str = ""  # lý do không tải được trên máy này (tiếng Việt), rỗng nếu tải được
    downloads: list[Any] = field(default_factory=list)
    target: Path | None = None  # thư mục đặt file khi không phải thư mục gói model nhạc

    def need(self) -> int:
        """Byte còn phải tải: chỉ các file chưa nằm đúng bản ghim ở `target`. Phần không có thư mục đích riêng thì nguyên `size`."""
        if self.target is None or not self.downloads:
            return self.size
        return sum(item.size for item in self.downloads if not file_ok(item, self.target / item.name))


# ---- cấu hình -----------------------------------------------------------------------------------------------------------------
def configure(folder: Path | str | None, after_install: Callable[[], None] | None = None,
              studio_installed: Callable[[], bool] | None = None) -> None:
    """Thư mục nhạc của app (server.py: <dữ liệu app>/music). `after_install`: việc làm sau khi tải/cập nhật xong (phân tích nốt bài chưa
    phân tích, đo độ to bù); chạy ở luồng tải, không bao giờ tự phân tích lại bài đã có kết quả. Đã có thư viện tải trước đó thì đăng ký ngay.
    `studio_installed`: máy đã cài Studio chưa (phần tuỳ chọn "Học sinh không khí cảnh" chạy trong Studio, xem `scene_student_status`)."""
    global _folder, _after, _studio_installed
    with _lock:
        _folder = Path(folder) if folder is not None else None
        _after = after_install
        _studio_installed = studio_installed
        _state.update(downloading=False, done=0, total=0, error="")
        activate_libs()


def _stamp_path() -> Path | None:
    return _folder / STAMP_FILE if _folder is not None else None


def _read_stamp() -> dict[str, str]:
    path = _stamp_path()
    try:
        pins = json.loads(path.read_text(encoding="utf-8")).get("pins") if path is not None else None
    except (OSError, ValueError, AttributeError):
        return {}
    return {str(key): str(value) for key, value in pins.items()} if isinstance(pins, dict) else {}


def _write_stamp(pins: dict[str, str]) -> None:
    path = _stamp_path()
    if path is not None:
        io_utils.atomic_write_json(path, {"version": 1, "pins": pins})


# ---- thư viện Python ----------------------------------------------------------------------------------------------------------
def _lib() -> Path | None:
    return _folder / LIB_FOLDER if _folder is not None else None


def _lib_next() -> Path | None:
    return _folder / LIB_NEXT if _folder is not None else None


def _libs_loaded() -> bool:
    return any(name in sys.modules for name in LIB_MODULES)


def activate_libs() -> bool:
    """Đưa thư viện đã tải vào sys.path (trước khi import). Có bản `lib.next` chờ mà thư viện chưa được nạp thì đổi chỗ trước. Trả true khi
    đã có thư viện của mô-đun trong sys.path."""
    lib, pending = _lib(), _lib_next()
    if lib is None or pending is None:
        return False
    if pending.is_dir() and (not lib.is_dir() or not _libs_loaded()):  # lần đầu: chưa có gì của mô-đun được nạp nên đổi chỗ ngay
        shutil.rmtree(lib, ignore_errors=True)
        try:
            os.replace(pending, lib)
        except OSError:
            return lib.is_dir() and _register_path(lib)
    return lib.is_dir() and _register_path(lib)


def _register_path(lib: Path) -> bool:
    text = str(lib)
    if text not in sys.path:
        sys.path.insert(0, text)
        importlib.invalidate_caches()
    return True


def _libs_present() -> bool:
    return any(folder is not None and folder.is_dir() for folder in (_lib(), _lib_next()))


def _libs_external() -> bool:
    """Máy tự import được numpy + onnxruntime (không phải của mô-đun): Studio, máy dev."""
    lib = _lib()
    for name in LIB_MODULES:
        try:
            spec = importlib.util.find_spec(name)
        except (ImportError, ValueError):
            spec = None
        if spec is None or spec.origin is None:
            return False
        if lib is not None and Path(spec.origin).is_relative_to(lib):
            return False
    return True


def libs_problem() -> str:
    """Vì sao máy này không tải được thư viện (rỗng = tải được). Dùng chung với mô-đun "Giọng VieNeu" (vieneu_module.py)."""
    if sys.platform != "win32" or sys.version_info[:2] != (3, 14):
        return "thư viện tải sẵn chỉ có cho bản ABook Windows 64-bit - hãy cài numpy và onnxruntime cho Python của máy này"
    return ""


def _cannot_install_libs() -> str:
    if os.environ.get(ENV_DOWNLOAD, "1") == "0":
        return "tải bộ phân tích nhạc đang bị tắt trên máy này"
    return libs_problem()


def _install_libs(progress: Callable[[int, int], None], cancelled: Callable[[], bool]) -> None:
    assert _folder is not None
    cache = _folder / DOWNLOADS
    staging = _lib_next()
    assert staging is not None
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    done = 0
    for wheel in WHEELS:
        target = cache / f"{wheel.name}.whl"
        studio_setup.download(wheel, target, lambda have, total, base=done: progress(base + have, sum(w.size for w in WHEELS)), cancelled)
        done += wheel.size
        with zipfile.ZipFile(target) as bundle:
            bundle.extractall(staging)
    shutil.rmtree(cache, ignore_errors=True)


def libs_pin() -> str:
    return hashlib.sha256("\n".join(f"{wheel.name} {wheel.sha256}" for wheel in WHEELS).encode()).hexdigest()


def libs_part(blocked: str | None = None) -> Component:
    """Phần "thư viện chạy model" (numpy + onnxruntime): MỘT bản cho cả máy - mô-đun nào tải trước thì mô-đun kia thấy đã có."""
    return Component("libs", "Thư viện chạy model", libs_pin(), sum(w.size for w in WHEELS), _libs_present(), external=_libs_external(),
                     blocked=_cannot_install_libs() if blocked is None else blocked, downloads=list(WHEELS))


def libs_state() -> str:
    """`current` / `outdated` / `missing` của phần thư viện, theo dấu của mô-đun nhạc (nơi phần này sống)."""
    part = libs_part("")
    return judge_parts([part], _read_stamp())[part.id]


def install_libs_part(progress: Callable[[int, int], None]) -> None:
    """Tải phần thư viện cho mô-đun khác (Giọng VieNeu): giải vào chỗ chung, ghi dấu của mô-đun nhạc, đưa vào sys.path."""
    with _lock:
        _install_libs(progress, lambda: False)
        stamp = _read_stamp()
        stamp["libs"] = libs_pin()
        _write_stamp(stamp)
    activate_libs()


def scene_student_part() -> Component:
    """Phần TUỲ CHỌN "Học sinh không khí cảnh" (music_scene_student.py, 0,71 GiB): đoán hình không khí trong chương cho nhạc nền. Chỉ vào `_components()`
    khi người dùng bấm tải nó (`start(scene=True)`) hay nó đã nằm trên máy - thiếu nó mô-đun vẫn "ready", người dùng không bị đòi tải. Chưa có
    REVISION hay bị tắt: `blocked` nêu lý do, `downloads` rỗng."""
    from . import music_scene_student as scene

    return Component("scene_q06", "Học sinh không khí cảnh", scene.model_pin(), scene.total_bytes(), scene.present(),
                     external=bool(os.environ.get(scene.ENV_DIR)), blocked=scene.cannot_download(), downloads=scene.model_downloads(),
                     target=scene.package_dir())


def scene_student_offered() -> str:
    """Rỗng nếu máy này dùng được phần tuỳ chọn (tiến trình này có torch, hoặc đã cài Studio để chạy nó); không thì lý do (tiếng Việt)."""
    from . import music_scene_student as scene

    if scene.dependencies_ok() or (_studio_installed is not None and _studio_installed()):
        return ""
    return "cần cài Studio: bộ này chạy trong Studio của máy tính"


def scene_student_status() -> dict[str, Any]:
    """Cho giao diện: phần tuỳ chọn đã có chưa (`state` current / outdated / missing), cỡ tải, `blocked` (rỗng nếu tải được), và `offered` (máy
    dùng được nó; không thì `reason` nói vì sao - giao diện ẩn nút tải)."""
    part = scene_student_part()
    reason = scene_student_offered()
    state = judge_parts([part], _read_stamp())[part.id]
    return {"state": state, "bytes": part.size if state == "current" else part.need(), "blocked": part.blocked,
            "external": part.external, "offered": not reason, "reason": reason}


# ---- các phần của máy này -----------------------------------------------------------------------------------------------------
def _components(scene: bool = False) -> list[Component]:
    """`scene`: có cả phần tuỳ chọn "Học sinh không khí cảnh" (người dùng vừa bấm tải nó); phần ấy đã nằm trên máy thì luôn có mặt."""
    backend = music_student.planned_backend()
    out: list[Component] = []
    external_ffmpeg = ffmpeg_setup.external()
    out.append(Component("ffmpeg", "Công cụ đọc âm thanh", ffmpeg_setup.pin(), ffmpeg_setup.WHEEL.size, ffmpeg_setup.downloaded(),
                         external=external_ffmpeg, blocked=ffmpeg_setup.cannot_download(), downloads=[ffmpeg_setup.WHEEL]))
    if backend == "onnx":
        out.append(libs_part())
    files = music_student.model_downloads(backend)
    directory = music_student.package_dir()
    pinned_elsewhere = bool(os.environ.get(music_student.ENV_DIR))
    out.append(Component("model", "Model nghe nhạc", music_student.model_pin(backend), sum(item.size for item in files),
                         music_student._complete(directory, backend), external=pinned_elsewhere,
                         blocked=music_student.cannot_download() if not pinned_elsewhere else "", downloads=files))
    extra = scene_student_part()
    if scene or (extra.present and not extra.external):
        out.append(extra)
    return out


def _judge(components: list[Component]) -> dict[str, str]:
    return judge_parts(components, _read_stamp())


def judge_parts(components: list[Component], stamp: dict[str, str]) -> dict[str, str]:
    """Từng phần: `current` (dùng được, đúng ghim hoặc máy có sẵn), `outdated` (đã tải nhưng ghim khác bản app này mang), `missing`.
    `stamp`: phần -> ghim đã tải (dấu của mô-đun). Dùng chung với vieneu_module."""
    judged = {}
    for part in components:
        if part.external:
            judged[part.id] = "current"
        elif not part.present:
            judged[part.id] = "missing"
        elif part.id in stamp and stamp[part.id] != part.pin:
            judged[part.id] = "outdated"
        else:
            judged[part.id] = "current"  # có file mà chưa có dấu (đặt tay) thì coi là đúng - dấu chỉ ghi lúc mô-đun tự tải
    return judged


def _needed(components: list[Component], judged: dict[str, str]) -> list[Component]:
    return [part for part in components if judged[part.id] != "current"]


def ready() -> bool:
    """Mô-đun đã đủ để phân tích (mọi phần dùng được; bản cũ vẫn tính) VÀ bộ phân tích đã cắm."""
    return music_local.analyzer_available()


def status() -> dict[str, Any]:
    with _lock:
        components = _components()
        judged = _judge(components)
        needed = _needed(components, judged)
        installed_any = any(judged[part.id] != "missing" and not part.external for part in components)
        behind = [part for part in needed if judged[part.id] == "outdated" or (installed_any and judged[part.id] == "missing")]
        blocked = next((part.blocked for part in needed if part.blocked), "")
        if _state["downloading"]:
            state = "downloading"
        elif _state["error"]:
            state = "error"
        elif not needed:
            state = "ready"
        elif blocked:
            state = "unsupported"
        else:
            state = "outdated" if installed_any else "missing"
        total = _state["total"] if state == "downloading" else sum(part.need() for part in needed)
        return {
            "state": state, "done": _state["done"] if state == "downloading" else 0, "total": total,
            "error": _state["error"], "ready": state in ("ready", "outdated") and music_local.analyzer_available(),
            "supported": not blocked, "reason": blocked,
            "parts": [{"id": part.id, "label": part.label, "bytes": part.size, "state": judged[part.id], "external": part.external}
                      for part in components],
            "outdatedParts": [part.label for part in behind] if state in ("outdated", "downloading") else [],
            "outdatedBytes": sum(part.need() for part in behind),
            "restart": bool((pending := _lib_next()) is not None and pending.is_dir() and _lib().is_dir() and _libs_loaded()),
            "analysing": _job == "analysing", "metered": False, "scene": scene_student_status(),
        }


# ---- tải ---------------------------------------------------------------------------------------------------------------------
def start(scene: bool = False) -> None:
    """Bắt đầu tải (hay cập nhật chỉ những phần có ghim đổi) ở luồng nền. Gọi nhiều lần cũng chỉ một lượt; đang lỗi thì gọi lại là thử lại; đã
    đủ thì không làm gì. `scene`: tải cả phần tuỳ chọn "Học sinh không khí cảnh" (người dùng bấm riêng nút ấy)."""
    global _thread
    with _lock:
        if _state["downloading"] and _thread is not None and _thread.is_alive():
            return
        components = _components(scene)
        needed = _needed(components, _judge(components))
        _state.update(error="", done=0)
        if not needed:
            return
        reason = next((part.blocked for part in needed if part.blocked), "")
        if reason:
            _state["error"] = reason[0].upper() + reason[1:] + "."
            return
        _state.update(downloading=True, total=sum(part.need() for part in needed))
        _thread = threading.Thread(target=_run, args=(needed,), name="music-module", daemon=True)
        _thread.start()


def join(timeout: float | None = None) -> None:
    """Đợi luồng tải xong (bài thử)."""
    thread = _thread
    if thread is not None:
        thread.join(timeout)


def _reason(error: BaseException) -> str:
    if isinstance(error, studio_setup.SetupError):
        if error.__cause__ is not None:  # download() bọc lỗi mạng
            return "không tải được - kiểm tra kết nối mạng rồi thử lại"
        return "file tải về không đúng bản đã ghim (đã xoá) - thử lại"
    if isinstance(error, (zipfile.BadZipFile, KeyError)):
        return "gói tải về hỏng - thử lại"
    if isinstance(error, OSError):
        return f"không ghi được vào ổ đĩa ({error.strerror or error})"
    return f"lỗi không ngờ ({type(error).__name__}: {error})"


def _run(needed: list[Component]) -> None:
    global _job
    try:
        assert _folder is not None
        finished = 0
        stamp = _read_stamp()
        for part in needed:
            need = part.need()  # trước khi tải: file đã đúng bản ghim không tính, không tải lại

            def progress(done: int, _total: int = 0, base: int = finished) -> None:
                """`done` = byte đã tải của riêng phần này; thanh tiến độ chung = các phần đã xong + phần đang tải."""
                with _lock:
                    _state["done"] = base + done

            if part.id == "ffmpeg":
                ffmpeg_setup.install(progress, lambda: False)
            elif part.id == "libs":
                _install_libs(progress, lambda: False)
            else:
                directory = part.target if part.id == "scene_q06" else music_student.package_dir()
                assert directory is not None
                directory.mkdir(parents=True, exist_ok=True)
                done = 0
                for item in part.downloads:
                    if part.target is not None and file_ok(item, directory / item.name):
                        continue
                    studio_setup.download(item, directory / item.name, lambda have, _t, offset=done: progress(offset + have), lambda: False)
                    if part.target is not None:
                        _remember_ok(item, directory / item.name)
                    done += item.size
            finished += need
            stamp[part.id] = part.pin
            _write_stamp(stamp)
            with _lock:
                _state["done"] = finished
        activate_libs()
        music_student.reset()
        music_student.register()
        with _lock:
            _state.update(downloading=False, error="")
        if _after is not None:
            _job = "analysing"
            try:
                _after()
            finally:
                _job = ""
    except Exception as error:  # noqa: BLE001 - mọi lỗi đều thành một câu cho người dùng, không bao giờ im lặng
        with _lock:
            _state.update(downloading=False, error=f"Không tải được Phân tích nhạc: {_reason(error)}.")
    finally:
        with _lock:
            _state["downloading"] = False


def run_job(work: Callable[[], Any]) -> None:
    """Chạy `work` (phân tích lại các bài cũ - người dùng bấm) ở luồng nền, giao diện thấy `analysing` trong lúc đó."""
    global _job, _thread

    def target() -> None:
        global _job
        try:
            work()
        finally:
            _job = ""

    with _lock:
        if _job or _state["downloading"]:
            return
        _job = "analysing"
        _thread = threading.Thread(target=target, name="music-module-job", daemon=True)
        _thread.start()
