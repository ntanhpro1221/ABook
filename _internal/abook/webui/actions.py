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
import webbrowser
from urllib.parse import urlsplit
from pathlib import Path
from typing import Any, Callable, Protocol

from .. import importers
from ..io_utils import discover_txt_files, natural_key, sha256_file
from . import humanize

# Tiếng Việt đọc ~4,3 âm tiết/giây ở tốc độ kể chuyện; một "từ" tách bằng dấu cách là một âm tiết.
SYLLABLES_PER_SECOND = 4.3
SCAN_WORD_LIMIT_BYTES = 4 * 1024 * 1024
# Studio từ xa: chương TXT gửi từ máy khác nằm ở đây, trong thư viện - dây chuyền còn đọc lại nguồn mỗi lần chạy tiếp.
UPLOAD_FOLDER = "Nguồn tải lên"
SPLIT_FOLDER = "Nguồn tách chương"
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


def _upload_name(text: str, limit: int) -> str:
    return " ".join(_UNSAFE_NAME.sub(" ", text).split()).strip(" .")[:limit].strip(" .")


def upload_source(library_root: Path, folder: str, name: str, data: bytes) -> Path:
    """Ghi một chương TXT gửi từ máy khác vào `<thư viện>/Nguồn tải lên/<thư mục>/`, trả file đã ghi.

    `folder` có thể có tới ba tầng cách bằng "/" ("<lần gửi>/<thư mục đã chọn>[/<thư mục con>]"): chọn cả thư mục truyện thì
    tên thư mục ấy còn nguyên - nó là tên sách máy gợi ý - mà mỗi lần gửi vẫn nằm riêng một chỗ.
    Chỉ lấy TÊN file (không đường dẫn), chỉ `.txt`, mỗi tầng thư mục và tên file bỏ ký tự Windows không nhận (cả "/" và
    "\\"), tầng rỗng hay ".." bị bỏ, không nhận tên thiết bị (CON, NUL, COM1...) - không có cách nào ghi ra ngoài thư mục
    tải lên. KHÔNG ghi đè: đè lên nguồn của một cuốn đã tạo là cuốn ấy không chạy tiếp được nữa ("Source chapter đã thay
    đổi nội dung"). Byte giữ nguyên: bảng mã do dây chuyền nhận như với file trên máy."""
    if str(library_root) in ("", ".") or not library_root.is_dir():
        raise ValueError("Máy tính chưa có thư mục thư viện")
    if len(data) > MAX_SOURCE_UPLOAD:
        raise ValueError(f"File quá lớn - tối đa {MAX_SOURCE_UPLOAD // 2**20} MB một file")
    parts = [part for part in (_upload_name(piece, 60) for piece in folder.replace("\\", "/").split("/")) if part]
    parts = parts[:3] or ["Tải lên"]
    file_name = _upload_name(name.replace("\\", "/").rsplit("/", 1)[-1], 120)
    if not file_name.lower().endswith((".txt", *importers.IMPORT_SUFFIXES)):
        raise ValueError("Chỉ nhận file .txt (mỗi file là một chương) hay một file .epub / .docx / .pdf")
    if any(_DEVICE_NAME.match(part) for part in parts) or _DEVICE_NAME.match(file_name):
        raise ValueError("Tên này là tên thiết bị của Windows - đổi tên file rồi gửi lại")
    target_dir = library_root / UPLOAD_FOLDER
    for part in parts:
        target_dir /= part
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / file_name
    if target.exists():
        raise ValueError(f"Đã có chương {file_name} trong lần gửi này - hai file trùng tên")
    temporary = target_dir / f".{file_name}.part"
    temporary.write_bytes(data)
    os.replace(temporary, target)
    return target


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
        status = self.setup.status()
        if status["damaged"]:
            raise RuntimeError(f"Studio mất {', '.join(status['damaged'])} (file đã bị xoá hay hỏng) - vào Dự án, bấm "
                               "\"Sửa Studio\" để tải lại đúng phần ấy.")
        outdated = status["outdated"]
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


def _decode_head(path: Path) -> str:
    try:
        with path.open("rb") as handle:
            raw = handle.read(SCAN_WORD_LIMIT_BYTES)
    except OSError:
        return ""
    for encoding in ("utf-8-sig", "cp1258"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _first_line(path: Path) -> str:
    try:
        with path.open("r", encoding="utf-8-sig", errors="replace") as handle:
            for line in handle:
                if line.strip():
                    return line.strip()[:120]
    except OSError:
        pass
    return ""


def _title_line(path: Path) -> str:
    """Dòng đầu của file nếu trông là TIÊU ĐỀ truyện (ngắn, không kết bằng dấu câu, không phải "Chương N" hay lời thoại) - tên
    sách gợi ý khi cả truyện nằm trong một file ("whole.txt" mà dòng đầu là "Chuyến phà cuối ngày"); "" nếu không."""
    first = importers.title_from_line(_first_line(path))  # luật chung với "Thêm sách từ file…" và việc tách file cả truyện
    return "" if humanize.is_heading(first) else first


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


def _credits_at_end(path: Path) -> list[str]:
    """Dòng xin ủng hộ / quảng cáo / nguồn ở cuối chương (text_processing.tail_credit_lines, luật chung với sách nhập) - trình
    tạo sách ĐỀ XUẤT bỏ như dòng ghi công đầu chương. Chỉ đọc 8 KB cuối file."""
    from ..io_utils import decode_text_bytes
    from ..text_processing import tail_credit_lines

    try:
        with path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - 8192))
            tail = handle.read()
    except OSError:
        return []
    cut = tail.find(b"\n") if size > 8192 else -1
    return tail_credit_lines(decode_text_bytes(tail[cut + 1:] if cut >= 0 else tail))


# Thư mục cha chung có tên chung chung (hay của chính app) không phải tên truyện.
_GENERIC_FOLDERS = {
    "downloads", "download", "desktop", "documents", "tải xuống", "tai xuong", "tài liệu", "truyen", "truyện", "books",
    "sach", "sách", "temp", "tmp", "users", "home", UPLOAD_FOLDER.casefold(), SPLIT_FOLDER.casefold(), "nguồn epub",
}


def _shared_folder_name(files: list[Path]) -> str:
    """Nhiều thư mục anh em cùng một thư mục cha ("Re Zero/Tập 1", "Re Zero/Tập 2"): tên truyện là tên thư mục cha, không phải
    tên file đầu tiên ("001"). Rỗng khi các file chung một thư mục (đã có `infer_book_title`), không cùng cha, hay cha là gốc ổ
    đĩa / tên chung chung ("Downloads", "Desktop"...)."""
    parents = {path.resolve().parent for path in files}
    if len(parents) < 2:
        return ""
    grandparents = {parent.parent for parent in parents}
    if len(grandparents) != 1:
        return ""
    name = next(iter(grandparents)).name
    return "" if not name or name.casefold() in _GENERIC_FOLDERS else name


def scan_inputs(paths: list[str], epub_root: Path | None = None) -> dict[str, Any]:
    """Những gì người dùng sắp đưa vào sách: file TXT (thư mục chỉ quét một tầng, như app cũ), xếp tự nhiên. File EPUB / DOCX /
    PDF (importers.py) được tách thành thư mục chương TXT trong `epub_root` (thư viện; không có thì cạnh file) rồi quét như một
    thư mục."""
    from . import txt_split, volumes

    files: list[Path] = []
    seen: set[str] = set()
    skipped: list[str] = []
    missing: list[str] = []
    subfolders: list[str] = []
    errors: list[str] = []
    notes: list[str] = []
    book_title = ""
    # Chương tách từ EPUB giữ thứ tự của TỪNG file (hai tập trong một thư mục: hết tập 1 rồi mới tới tập 2) - xếp theo tên
    # file thì "0001 …" của tập 1 và tập 2 xen nhau (soát UX 01-10). TXT là nhóm 0, mỗi file sách một nhóm theo thứ tự gặp.
    group_of: dict[str, int] = {}
    groups = 0

    def unpack(book: Path, root: Path) -> list[Path]:
        nonlocal book_title, groups
        try:
            folder, info = importers.extract(book, root)
            chapter_files = discover_txt_files(folder)
        except (importers.ImportFailed, OSError) as error:
            errors.append(f"{book.name}: {error}")
            return []
        book_title = book_title or str(info.get("title") or "")
        # Dòng ghi công đã có khung gợi ý riêng (credits/tailCredits của từng chương) - không lặp thành ghi chú (soát UX a24, A1).
        notes.extend(f"{book.name}: {note}" for note in info.get("notes") or [] if not importers.is_credit_note(note))
        groups += 1
        for chapter in chapter_files:
            group_of[os.path.normcase(str(chapter.resolve()))] = groups
        return chapter_files

    for item in paths:
        # "Copy as path" của Explorer luôn thêm ngoặc kép; khoảng trắng hai đầu cũng hay dính theo khi dán.
        cleaned = str(item).strip().strip('"').strip("'").strip()
        path = Path(cleaned).expanduser()
        if not path.exists():
            missing.append(cleaned)
            continue
        if path.is_file() and path.suffix.casefold() in importers.IMPORT_SUFFIXES:
            candidates = unpack(path, epub_root or path.parent)
        else:
            candidates = discover_txt_files(path) if path.is_dir() else [path]
        books = sorted((child for child in path.iterdir() if child.suffix.casefold() in importers.IMPORT_SUFFIXES),
                       key=lambda child: natural_key(child.name)) if path.is_dir() else []
        if path.is_dir() and not candidates:
            # Thư mục chỉ có file sách (gửi từ điện thoại, hay chọn thư mục chứa file EPUB): tách từng file như khi chọn nó.
            for book in books:
                candidates += unpack(book, epub_root or path)
        elif books:
            names = ", ".join(book.name for book in books[:2]) + (" …" if len(books) > 2 else "")
            notes.append(f"Thư mục có cả file sách ({names}) - chỉ lấy các file TXT; muốn dùng file sách thì chọn riêng file ấy.")
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
    files.sort(key=lambda path: (group_of.get(os.path.normcase(str(path)), 0), natural_key(path.name)))
    rows = []
    total_words = 0
    for path in files:
        text = _decode_head(path)
        words = len(text.split())
        total_words += words
        rows.append({
            "path": str(path),
            "name": path.name,
            "title": humanize.chapter_title(path.stem),
            "firstLine": _first_line(path),
            # Dòng ghi công ở đầu chương: trình tạo sách ĐỀ XUẤT bỏ chúng khỏi phần đọc (đếm trên đúng các chương còn chọn).
            "credits": _credits_at_top(path),
            "tailCredits": _credits_at_end(path),  # dòng ủng hộ / quảng cáo cuối chương: đề xuất như trên
            "words": words,
            # Số ký tự có chữ (không tính khoảng trắng): hiện cạnh tên chương để thấy chương nào rỗng / quá dài trước khi tạo.
            "chars": sum(not ch.isspace() for ch in text),
            "bytes": path.stat().st_size,
            # Như chapters.input_sha256 của dây chuyền: nhận ra truyện đã có dự án (App.existing_projects).
            "sha256": sha256_file(path),
            # Một file chứa nhiều "Chương N": ĐỀ XUẤT tách (txt_split) - chỉ khi người dùng đưa vào vài file, không đọc lại
            # cả nghìn file chương của một thư mục bình thường.
            "split": txt_split.plan(path) if len(files) <= 3 else None,
        })
    title = book_title
    if files and not title:
        from ..project import infer_book_title

        title = _shared_folder_name(files) or (_title_line(files[0]) if len(files) == 1 else "") or infer_book_title(files)
    return {
        "files": rows,
        "skipped": skipped,
        "missing": missing,
        # EPUB / DOCX / PDF không tách được (hỏng, PDF scan, không có chương nào có chữ...): nói lý do thay vì "không có chương nào".
        "errors": errors,
        # Không phải lỗi nhưng người dùng nên biết (thư mục có cả TXT lẫn EPUB: chỉ lấy TXT; trang chỉ có ảnh bị bỏ; gợi ý bỏ dòng ghi công).
        "notes": notes,
        # Tối đa MAX_VOLUMES: giao diện hiện vài thư mục đầu, và "dùng cả các thư mục này, mỗi thư mục một tập" cần đủ bộ.
        "subfolders": subfolders[:volumes.MAX_VOLUMES],
        # Nhiều tập trong một nguồn (mỗi thư mục / EPUB một tập, hay tiêu đề "Tập 2"): ĐỀ XUẤT chia, None khi chỉ một tập.
        "volumes": volumes.propose(rows),
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
                drop_credit_lines: bool | None = None, drop_tail_credit_lines: bool | None = None) -> Path:
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
    if drop_tail_credit_lines is not None:
        # Dòng ủng hộ / quảng cáo cuối chương: khoá riêng, nên sách tạo trước khi có đề xuất này vẫn tách như cũ.
        overrides["text"] = {**overrides.get("text", {}), "drop_tail_credit_lines": bool(drop_tail_credit_lines)}
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

    def fail(self, project_root: Path, message: str) -> None:
        """Lượt chạy không bắt đầu được vì lý do có trước khi khởi động (hàng đợi: phần nối tiếp chưa gieo được) - hiện ở
        trang sách như một lỗi khởi động."""
        with self._lock:
            self._errors[str(project_root)] = message

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


_URL_UNSAFE = '"<>\\'


def open_url(url: str) -> None:
    """Mở liên kết ngoài bằng trình duyệt mặc định của máy (cửa sổ app Tauri không tự mở `target=_blank`). Chỉ http/https
    có tên máy: file:, javascript:, ms-settings:... bị từ chối - đây là cửa vào từ trang web, không được thành lối chạy lệnh.
    Cũng từ chối URL có khoảng trắng, `"`, `<`, `>`, dấu gạch ngược, ký tự điều khiển, hay mà `urlsplit` phải viết lại: chuỗi đưa cho
    trình duyệt đúng là chuỗi người gọi gửi, không có gì lọt vào dòng lệnh (`ShellExecute`)."""
    url = url.strip()
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname or len(url) > 2000:
        raise ValueError("Chỉ mở được liên kết http/https")
    target = parts.geturl()
    if target != url or any(char.isspace() or char in _URL_UNSAFE or ord(char) < 32 or ord(char) == 127 for char in target):
        raise ValueError("Liên kết có ký tự không an toàn")
    webbrowser.open(target)


def recycle_bin_available(path: Path) -> None:
    """Ổ của `path` có Thùng rác không? Không thì OSError (nơi khác Windows cũng vậy). Hỏi riêng để chỗ chờ "Hoàn tác"
    (trash_pending) báo lỗi ngay lúc xoá, không đợi tới lúc hết hạn mới biết không chuyển vào Thùng rác được."""
    if os.name != "nt":
        raise OSError("Chỉ chuyển được vào Thùng rác trên Windows")
    import ctypes
    from ctypes import wintypes

    class RecycleBinInfo(ctypes.Structure):  # SHQUERYRBINFO
        _fields_ = [("cbSize", wintypes.DWORD), ("i64Size", ctypes.c_longlong), ("i64NumItems", ctypes.c_longlong)]

    anchor = path.resolve().anchor
    # Ổ không có Thùng rác (USB, ổ mạng) thì "xoá" là XOÁ HẲN - app không bao giờ tự làm vậy; người dùng tự xoá nếu chắc.
    info = RecycleBinInfo(ctypes.sizeof(RecycleBinInfo), 0, 0)
    if ctypes.windll.shell32.SHQueryRecycleBinW(anchor, ctypes.byref(info)) != 0:
        raise OSError(f"ổ {anchor} không có Thùng rác")


class RecycleCancelled(OSError):
    """Người dùng bấm "Không" ở hộp "xoá hẳn" của Windows: không có gì bị xoá, thư mục còn nguyên chỗ cũ."""


BACKSLASH = chr(92)


def bin_takes(*, size: int, capacity: int | None, nuke: bool, drive_total: int | None = None) -> bool:
    """Thư mục `size` byte vào Thùng rác của ổ được không, không bị Windows hỏi "xoá hẳn"? `capacity`: hạn mức Thùng rác của ổ
    (None: không đọc được - chỉ chắc chắn khi thư mục không quá 1% ổ); `nuke`: ổ đặt "xoá hẳn, không vào Thùng rác"."""
    if nuke:
        return False
    if capacity is None:
        capacity = drive_total // 100 if drive_total else 0
    return size <= capacity * 9 // 10


def _folder_size(path: Path) -> int | None:
    total = 0
    try:
        for base, _folders, files in os.walk(path):
            for name in files:
                try:
                    total += os.lstat(os.path.join(base, name)).st_size
                except OSError:
                    pass
    except OSError:
        return None
    return total


def _bin_limits(anchor: str) -> tuple[int | None, bool]:
    """(hạn mức byte, ổ đặt xoá hẳn) của Thùng rác ổ `anchor` theo sổ đăng ký Windows; không đọc được thì (None, False)."""
    import ctypes
    import winreg

    volume = ctypes.create_unicode_buffer(64)
    if not ctypes.windll.kernel32.GetVolumeNameForVolumeMountPointW(anchor, volume, len(volume)):
        return None, False
    guid = volume.value.rstrip(BACKSLASH).rsplit(BACKSLASH, 1)[-1].removeprefix("Volume")  # tên ổ có dạng \\?\Volume{GUID}\
    key = BACKSLASH.join(("Software", "Microsoft", "Windows", "CurrentVersion", "Explorer", "BitBucket", "Volume", guid))
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as handle:
            values = {}
            for name in ("MaxCapacity", "NukeOnDelete"):
                try:
                    values[name] = int(winreg.QueryValueEx(handle, name)[0])
                except OSError:
                    values[name] = None
    except OSError:
        return None, False
    capacity = values["MaxCapacity"]
    return (capacity * 1024 * 1024 if capacity else None), bool(values["NukeOnDelete"])


def recycle_bin_accepts(path: Path) -> bool:
    """Thùng rác của ổ nhận thư mục `path` mà Windows không hỏi "xoá hẳn" không? Không chắc thì False - nơi gọi chuyển thẳng vào
    Thùng rác ngay lúc người dùng bấm xoá (hộp hỏi hiện đúng lúc họ đang nhìn), không để hộp bật bất ngờ ở luồng dọn nền."""
    if os.name != "nt":
        return True
    try:
        recycle_bin_available(path)
        anchor = path.resolve().anchor
        size = _folder_size(path)
        if size is None:
            return False
        import shutil

        capacity, nuke = _bin_limits(anchor)
        return bin_takes(size=size, capacity=capacity, nuke=nuke, drive_total=shutil.disk_usage(anchor).total)
    except Exception:  # noqa: BLE001 - không đọc được gì thì coi như không chắc
        return False


def move_to_recycle_bin(path: Path) -> None:
    """Chuyển thư mục vào Thùng rác của Windows - khôi phục được từ đó (Shell `SHFileOperationW`, FOF_ALLOWUNDO, không hộp
    thoại nào của Windows). Lỗi (file đang mở, ổ không có Thùng rác...) thành OSError; nơi khác Windows: OSError."""
    recycle_bin_available(path)
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

    resolved = path.resolve()
    fo_delete = 3
    # ALLOWUNDO | NOCONFIRMATION | SILENT | NOERRORUI | WANTNUKEWARNING: thư mục quá lớn so với Thùng rác thì Windows HỎI
    # trước khi xoá hẳn (không có cờ cuối, NOCONFIRMATION cho nó xoá hẳn im lặng - một cuốn xong nặng hàng chục GB).
    flags = 0x0040 | 0x0010 | 0x0004 | 0x0400 | 0x4000
    # pFrom là danh sách kết thúc bằng HAI ký tự NUL: ctypes thêm một, "\0" ở đây là cái còn lại.
    operation = FileOperation(None, fo_delete, str(resolved) + "\0", None, flags, False, None, None)
    code = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(operation))
    if operation.fAnyOperationsAborted or code in (0x75, 0x4C7):  # DE_OPCANCELLED / ERROR_CANCELLED: bấm "Không" ở hộp xoá hẳn
        raise RecycleCancelled(f"SHFileOperationW bị huỷ ({code:#x})")
    if code != 0:
        raise OSError(f"SHFileOperationW trả {code:#x}")
    if path.exists():
        raise OSError("Thư mục vẫn còn sau khi chuyển vào Thùng rác")
