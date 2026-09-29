"""Việc giao diện làm thay người dùng: quét nguồn, tạo sách, chạy, dừng, mở thư mục.

Chạy sách đi đúng đường của CLI và dây chuyền sản xuất: `background_runner.start_background` - supervisor
tách rời, nên đóng cửa sổ (hay cửa sổ sập) không dừng sách, và "Dừng" là `request_stop` (worker dừng ở ranh giới
gần nhất; AGENTS.md: GUI chỉ có MỘT lệnh Dừng).

`FakeRunner` cho lúc phát triển giao diện: bấm "Bắt đầu" không được khởi động worker thật trên máy đang sản xuất
(nó sẽ tranh GPU với lô đang chạy).
"""
from __future__ import annotations

import os
import re
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Callable, Protocol

from ..io_utils import discover_txt_files, natural_key, sha256_file
from . import humanize

# Tiếng Việt đọc ~4,3 âm tiết/giây ở tốc độ kể chuyện; một "từ" tách bằng dấu cách là một âm tiết.
SYLLABLES_PER_SECOND = 4.3
SCAN_WORD_LIMIT_BYTES = 4 * 1024 * 1024
# Studio từ xa: chương TXT gửi từ máy khác nằm ở đây, trong thư viện - dây chuyền còn đọc lại nguồn mỗi lần chạy tiếp.
UPLOAD_FOLDER = "Nguồn tải lên"
MAX_SOURCE_UPLOAD = 8 * 1024 * 1024  # một chương; chương dài nhất của kho truyện ~200 KB
_UNSAFE_NAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
# Tên thiết bị của Windows: làm tên thư mục hay file là ghi vào THIẾT BỊ, không vào đĩa.
_DEVICE_NAME = re.compile(r"^(con|prn|aux|nul|com[0-9¹²³]|lpt[0-9¹²³])(\..*)?$", re.IGNORECASE)


def inside_folder(path: str, root: Path) -> bool:
    """`path` nằm trong `root`? Từ chối TRƯỚC khi chạm đĩa đường UNC (`\\\\máy\\share`, `//máy/share`) và đường thiết bị
    (`\\\\?\\`, `\\\\.\\`): chỉ cần phân giải chúng là Windows đã nối mạng, gửi cả thông tin đăng nhập (soát 28-09)."""
    text = path.strip()
    if not text or text.startswith(("\\\\", "//")) or "\x00" in text:
        return False
    try:
        return Path(text).resolve().is_relative_to(root.resolve())
    except (OSError, ValueError):
        return False


def upload_source(library_root: Path, folder: str, name: str, data: bytes) -> Path:
    """Ghi một chương TXT gửi từ máy khác vào `<thư viện>/Nguồn tải lên/<thư mục>/`, trả thư mục ấy.

    Chỉ lấy TÊN file (không đường dẫn), chỉ `.txt`, tên thư mục và tên file bỏ ký tự Windows không nhận, không nhận tên
    thiết bị (CON, NUL, COM1...) - không có cách nào ghi ra ngoài thư mục tải lên. KHÔNG ghi đè: đè lên nguồn của một
    cuốn đã tạo là cuốn ấy không chạy tiếp được nữa ("Source chapter đã thay đổi nội dung"). Byte giữ nguyên: bảng mã do
    dây chuyền nhận như với file trên máy."""
    if str(library_root) in ("", ".") or not library_root.is_dir():
        raise ValueError("Máy tính chưa có thư mục thư viện")
    if len(data) > MAX_SOURCE_UPLOAD:
        raise ValueError("File quá lớn - tối đa 8 MB một chương")
    folder_name = " ".join(_UNSAFE_NAME.sub(" ", folder).split()).strip(" .")[:80] or "Tải lên"
    file_name = " ".join(_UNSAFE_NAME.sub(" ", name.replace("\\", "/").rsplit("/", 1)[-1]).split()).strip(" .")[:120]
    if not file_name.lower().endswith(".txt"):
        raise ValueError("Chỉ nhận file .txt - mỗi file là một chương")
    if _DEVICE_NAME.match(folder_name) or _DEVICE_NAME.match(file_name):
        raise ValueError("Tên này là tên thiết bị của Windows - đổi tên file rồi gửi lại")
    target_dir = library_root / UPLOAD_FOLDER / folder_name
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / file_name
    if target.exists():
        raise ValueError(f"Đã có chương {file_name} trong lần gửi này - hai file trùng tên")
    temporary = target_dir / f".{file_name}.part"
    temporary.write_bytes(data)
    os.replace(temporary, target)
    return target_dir


class Runner(Protocol):
    def start(self, project_root: Path) -> None: ...
    def stop(self, project_root: Path) -> None: ...
    def running(self, project_root: Path) -> bool: ...
    def pause(self, project_root: Path, paused: bool) -> None: ...
    def pause_reason(self, project_root: Path) -> str | None: ...
    def can_pause(self, project_root: Path) -> bool: ...


class BackgroundRunner:
    """Supervisor thật (`background_runner`)."""

    def start(self, project_root: Path) -> None:
        from ..background_runner import start_background

        start_background(project_root)

    def stop(self, project_root: Path) -> None:
        from ..background_runner import request_stop

        request_stop(project_root, wait=False)

    def running(self, project_root: Path) -> bool:
        from ..background_runner import get_status

        try:
            return bool(get_status(project_root).running)
        except Exception:  # noqa: BLE001 - state hỏng thì coi như không chạy; summary vẫn đọc lease
            return False

    def pause(self, project_root: Path, paused: bool) -> None:
        from ..background_runner import request_pause

        request_pause(project_root, paused)

    def pause_reason(self, project_root: Path) -> str | None:
        """"battery" (máy đang chạy pin), "listener" (người dùng bấm Tạm dừng) hay None - power_source."""
        from ..background_runner import get_status

        try:
            return get_status(project_root).pause_reason
        except Exception:  # noqa: BLE001
            return None

    def can_pause(self, project_root: Path) -> bool:
        from ..background_runner import get_status

        try:
            return get_status(project_root).can_pause
        except Exception:  # noqa: BLE001
            return False


class StudioRunner(BackgroundRunner):
    """App Windows đóng gói (webui/host.py): sách chạy bằng Python của Studio tải thêm (webui/studio_setup.py) và đúng
    bản mã đã bắt đầu cuốn ấy (`code_for` - app tự cập nhật không làm hỏng sách dở). Python nhúng của app chỉ có phần
    nghe. Supervisor là con của host nên thừa hưởng môi trường: runtime của Studio, PYTHONPATH tới bản mã, Ollama."""

    def __init__(self, setup: Any) -> None:
        self.setup = setup

    def start(self, project_root: Path) -> None:
        if not self.setup.installed():
            raise RuntimeError("Máy này chưa cài Studio - vào Dự án, bấm \"Cài Studio\" (một lần, khoảng 20 GB).")
        outdated = self.setup.status()["outdated"]
        if outdated:
            # Bản ghim đổi vì bản cũ làm hỏng sách (vd Ollama 0.34.4 - studio_setup.OLLAMA): không chạy bằng bản cũ.
            raise RuntimeError(f"Studio cần cập nhật ({', '.join(outdated)}) trước khi làm sách - vào Dự án, bấm "
                               "\"Cập nhật Studio\".")
        from ..background_runner import start_background

        code = self.setup.code_for(project_root)
        os.environ.update(self.setup.environment(code))
        # Ollama riêng của Studio chạy trước (home trong Studio); dây chuyền thấy nó đang nghe nên không tự bật bản khác.
        self.setup.ensure_ollama()
        # Supervisor chạy TỪ thư mục mã ghim: `python -m` ưu tiên thư mục làm việc hơn PYTHONPATH.
        start_background(project_root, python_executable=self.setup.pythonw, code_root=code)


class FakeRunner:
    """Giả chạy/dừng cho lúc phát triển giao diện - không đụng tiến trình hay file nào của sách."""

    def __init__(self) -> None:
        self._running: set[str] = set()
        self._paused: dict[str, str] = {}

    def start(self, project_root: Path) -> None:
        time.sleep(1.2)
        self._running.add(str(project_root))

    def stop(self, project_root: Path) -> None:
        self._running.discard(str(project_root))
        self._paused.pop(str(project_root), None)

    def running(self, project_root: Path) -> bool:
        return str(project_root) in self._running

    def pause(self, project_root: Path, paused: bool) -> None:
        if str(project_root) not in self._running:
            raise RuntimeError("Sách này không đang chạy")
        if paused:
            self._paused[str(project_root)] = "listener"
        else:
            self._paused.pop(str(project_root), None)

    def pause_reason(self, project_root: Path) -> str | None:
        return self._paused.get(str(project_root))

    def can_pause(self, project_root: Path) -> bool:
        return str(project_root) in self._running


def _count_words(path: Path) -> int:
    try:
        with path.open("rb") as handle:
            raw = handle.read(SCAN_WORD_LIMIT_BYTES)
    except OSError:
        return 0
    for encoding in ("utf-8-sig", "cp1258"):
        try:
            return len(raw.decode(encoding).split())
        except UnicodeDecodeError:
            continue
    return len(raw.decode("utf-8", errors="replace").split())


def _first_line(path: Path) -> str:
    try:
        with path.open("r", encoding="utf-8-sig", errors="replace") as handle:
            for line in handle:
                if line.strip():
                    return line.strip()[:120]
    except OSError:
        pass
    return ""


def _credits_at_top(path: Path) -> list[str]:
    """Dòng ghi công người dịch / biên tập ở đầu chương (text_processing.credit_lines) - để trình tạo sách ĐỀ XUẤT bỏ
    chúng khỏi phần đọc; chỉ áp dụng khi người dùng đồng ý. Chỉ đọc 8 KB đầu file."""
    from ..io_utils import decode_text_bytes
    from ..text_processing import credit_lines

    try:
        with path.open("rb") as handle:
            head = handle.read(8192)
    except OSError:
        return []
    cut = head.rfind(b"\n")
    return credit_lines(decode_text_bytes(head[:cut] if cut > 0 else head))


def scan_inputs(paths: list[str]) -> dict[str, Any]:
    """Những gì người dùng sắp đưa vào sách: file TXT (thư mục chỉ quét một tầng, như app cũ), xếp tự nhiên."""
    files: list[Path] = []
    seen: set[str] = set()
    skipped: list[str] = []
    missing: list[str] = []
    subfolders: list[str] = []
    for item in paths:
        # "Copy as path" của Explorer luôn thêm ngoặc kép; khoảng trắng hai đầu cũng hay dính theo khi dán.
        cleaned = str(item).strip().strip('"').strip("'").strip()
        path = Path(cleaned).expanduser()
        if not path.exists():
            missing.append(cleaned)
            continue
        candidates = discover_txt_files(path) if path.is_dir() else [path]
        if path.is_dir() and not candidates:
            # Chọn nhầm thư mục cha: gợi ý các thư mục con có TXT ngay bên trong.
            try:
                subfolders.extend(
                    str(child) for child in sorted(path.iterdir(), key=lambda entry: natural_key(entry.name))
                    if child.is_dir() and discover_txt_files(child)
                )
            except OSError:
                pass
        for candidate in candidates:
            if not candidate.is_file() or candidate.suffix.casefold() != ".txt":
                skipped.append(str(candidate))
                continue
            key = os.path.normcase(str(candidate.resolve()))
            if key not in seen:
                seen.add(key)
                files.append(candidate.resolve())
    files.sort(key=lambda path: natural_key(path.name))
    rows = []
    total_words = 0
    for path in files:
        words = _count_words(path)
        total_words += words
        rows.append({
            "path": str(path),
            "name": path.name,
            "title": humanize.chapter_title(path.stem),
            "firstLine": _first_line(path),
            # Dòng ghi công ở đầu chương: trình tạo sách ĐỀ XUẤT bỏ chúng khỏi phần đọc (đếm trên đúng các chương còn chọn).
            "credits": _credits_at_top(path),
            "words": words,
            "bytes": path.stat().st_size,
            # Như chapters.input_sha256 của dây chuyền: nhận ra truyện đã có dự án (App.existing_projects).
            "sha256": sha256_file(path),
        })
    title = ""
    if files:
        from ..project import infer_book_title

        title = infer_book_title(files)
    return {
        "files": rows,
        "skipped": skipped,
        "missing": missing,
        "subfolders": subfolders[:8],
        "suggestedTitle": title,
        "totals": {
            "chapters": len(rows),
            "words": total_words,
            "audioSeconds": round(total_words / SYLLABLES_PER_SECOND),
        },
    }


def first_person_hint(paths: list[str]) -> dict[str, Any]:
    """Truyện kể ngôi thứ nhất? + gợi ý "tôi" là ai, cho câu hỏi của bước chọn giọng (first_person.py)."""
    from ..first_person import first_person_hint as hint

    files = [Path(row["path"]) for row in scan_inputs(paths)["files"]]
    if not files:
        return {"rate": 0.0, "firstPerson": False, "suggestions": [], "chapters": []}
    return hint(files)


def create_book(library_root: Path, paths: list[str], title: str, profile: str, narrator: str,
                first_person: str = "", settings_overrides: dict[str, Any] | None = None,
                first_person_chapters: dict[str, str] | None = None,
                drop_credit_lines: bool | None = None) -> Path:
    from ..character_registry import PRONOUNS, normalize_name
    from ..config import build_settings
    from ..project import create_or_open_project

    files = [Path(row["path"]) for row in scan_inputs(paths)["files"]]
    if not files:
        raise ValueError("Chưa có file TXT nào để làm sách")
    first_person = first_person.strip()
    if first_person and normalize_name(first_person) in PRONOUNS:
        raise ValueError(f'"{first_person}" là một đại từ, không phải một nhân vật - điền tên của người xưng "tôi"')
    voices: dict[str, Any] = {}
    if narrator:
        voices["narrator_voice"] = narrator
    if first_person:
        # Cùng cài đặt với `cli create --first-person`: prompt phân tích nói cho model biết "tôi" là ai, và sau phân
        # tích các nhãn đại từ được gộp về người ấy.
        voices["first_person_identity"] = first_person
    chapters: dict[str, str] = {}
    for key, name in (first_person_chapters or {}).items():
        name = str(name or "").strip()
        if not str(key).strip().isdigit():
            raise ValueError(f"Chương {key!r} không phải một số chương")
        if name and normalize_name(name) in PRONOUNS:
            raise ValueError(f'"{name}" là một đại từ, không phải một nhân vật - điền tên người xưng "tôi" của chương ấy')
        chapters[str(int(key))] = name
    if chapters:
        # Người kể theo chương (`cli create --first-person-chapter`): chương đổi góc kể dùng "tôi" của người khác.
        voices["first_person_chapters"] = chapters
    overrides: dict[str, Any] = dict(settings_overrides or {})  # app đóng gói: Ollama riêng của Studio
    if voices:
        overrides["voices"] = voices
    if drop_credit_lines is not None:
        # Lựa chọn của người dùng ở trình tạo sách; không nói gì thì theo mặc định (config: bỏ).
        overrides["text"] = {**overrides.get("text", {}), "drop_credit_lines": bool(drop_credit_lines)}
    settings = build_settings(profile, overrides or None)
    library_root.mkdir(parents=True, exist_ok=True)
    paths_created, _db, _settings = create_or_open_project(files, library_root, settings, title.strip() or None)
    return paths_created.root


class Jobs:
    """Theo dõi các lệnh chạy đang khởi động (start_background đợi worker bắt tay, có thể mất vài giây)."""

    def __init__(self, runner: Runner) -> None:
        self.runner = runner
        self._starting: dict[str, float] = {}
        self._errors: dict[str, str] = {}
        self._lock = threading.Lock()

    def starting(self, project_root: Path) -> bool:
        with self._lock:
            return str(project_root) in self._starting

    def error(self, project_root: Path) -> str:
        with self._lock:
            return self._errors.get(str(project_root), "")

    def start(self, project_root: Path, on_done: Callable[[], None] | None = None) -> None:
        key = str(project_root)
        with self._lock:
            if key in self._starting:
                return
            self._starting[key] = time.time()
            self._errors.pop(key, None)

        def work() -> None:
            try:
                self.runner.start(project_root)
            except Exception as exc:  # noqa: BLE001 - lỗi khởi động phải tới được người dùng
                with self._lock:
                    self._errors[key] = str(exc)
            finally:
                with self._lock:
                    self._starting.pop(key, None)
                if on_done:
                    on_done()

        threading.Thread(target=work, name=f"start {project_root.name}", daemon=True).start()

    def stop(self, project_root: Path) -> None:
        self.runner.stop(project_root)


def reveal(path: Path) -> None:
    """Mở thư mục (hoặc chọn sẵn file) trong File Explorer."""
    if os.name != "nt":
        subprocess.Popen(["xdg-open", str(path if path.is_dir() else path.parent)])
        return
    if path.is_file():
        subprocess.Popen(["explorer", "/select,", str(path)])
    else:
        os.startfile(str(path))  # noqa: S606 - mở thư mục của chính người dùng


def move_to_recycle_bin(path: Path) -> None:
    """Chuyển thư mục vào Thùng rác của Windows - khôi phục được từ đó (Shell `SHFileOperationW`, FOF_ALLOWUNDO, không hộp
    thoại nào của Windows). Lỗi (file đang mở, ổ không có Thùng rác...) thành OSError; nơi khác Windows: OSError."""
    if os.name != "nt":
        raise OSError("Chỉ chuyển được vào Thùng rác trên Windows")
    import ctypes
    from ctypes import wintypes

    class FileOperation(ctypes.Structure):  # SHFILEOPSTRUCTW (x64: căn lề mặc định)
        _fields_ = [
            ("hwnd", wintypes.HWND),
            ("wFunc", wintypes.UINT),
            ("pFrom", wintypes.LPCWSTR),
            ("pTo", wintypes.LPCWSTR),
            ("fFlags", ctypes.c_ushort),
            ("fAnyOperationsAborted", wintypes.BOOL),
            ("hNameMappings", ctypes.c_void_p),
            ("lpszProgressTitle", wintypes.LPCWSTR),
        ]

    class RecycleBinInfo(ctypes.Structure):  # SHQUERYRBINFO
        _fields_ = [("cbSize", wintypes.DWORD), ("i64Size", ctypes.c_longlong), ("i64NumItems", ctypes.c_longlong)]

    resolved = path.resolve()
    # Ổ không có Thùng rác (USB, ổ mạng) thì "xoá" là XOÁ HẲN - app không bao giờ tự làm vậy; người dùng tự xoá nếu chắc.
    info = RecycleBinInfo(ctypes.sizeof(RecycleBinInfo), 0, 0)
    if ctypes.windll.shell32.SHQueryRecycleBinW(resolved.anchor, ctypes.byref(info)) != 0:
        raise OSError(f"ổ {resolved.anchor} không có Thùng rác")
    fo_delete = 3
    # ALLOWUNDO | NOCONFIRMATION | SILENT | NOERRORUI | WANTNUKEWARNING: thư mục quá lớn so với Thùng rác thì Windows HỎI
    # trước khi xoá hẳn (không có cờ cuối, NOCONFIRMATION cho nó xoá hẳn im lặng - một cuốn xong nặng hàng chục GB).
    flags = 0x0040 | 0x0010 | 0x0004 | 0x0400 | 0x4000
    # pFrom là danh sách kết thúc bằng HAI ký tự NUL: ctypes thêm một, "\0" ở đây là cái còn lại.
    operation = FileOperation(None, fo_delete, str(resolved) + "\0", None, flags, False, None, None)
    code = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(operation))
    if code != 0 or operation.fAnyOperationsAborted:
        raise OSError(f"SHFileOperationW trả {code:#x}")
    if path.exists():
        raise OSError("Thư mục vẫn còn sau khi chuyển vào Thùng rác")
