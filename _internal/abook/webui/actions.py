"""Việc giao diện làm thay người dùng: quét nguồn, tạo sách, chạy, dừng, mở thư mục.

Chạy sách đi đúng đường của CLI và dây chuyền sản xuất: `background_runner.start_background` - supervisor
tách rời, nên đóng cửa sổ (hay cửa sổ sập) không dừng sách, và "Dừng" là `request_stop` (worker dừng ở ranh giới
gần nhất; AGENTS.md: GUI chỉ có MỘT lệnh Dừng).

`FakeRunner` cho lúc phát triển giao diện: bấm "Bắt đầu" không được khởi động worker thật trên máy đang sản xuất
(nó sẽ tranh GPU với lô đang chạy).
"""
from __future__ import annotations

import hashlib
import io
import os
import re
import stat
import subprocess
import threading
import time
import webbrowser
from urllib.parse import urlsplit
from pathlib import Path
from typing import Any, Callable, Iterable, Protocol

from .. import importers
from ..readaloud import paragraphs as px
from ..readaloud.prepare import listening_seconds
from ..io_utils import discover_txt_files, natural_key
from . import humanize

SCAN_WORD_LIMIT_BYTES = 4 * 1024 * 1024  # đếm chữ / ký tự / thời lượng nghe trên chừng này byte đầu; file dài hơn thì ngoại suy (`estimated`)
MAX_SCAN_NOTES = 6  # ghi chú tối đa liệt kê, như bước xem trước của Nghe ngay (phần còn lại gộp thành một dòng)
# Studio từ xa: chương TXT gửi từ máy khác nằm ở đây, trong thư viện - dây chuyền còn đọc lại nguồn mỗi lần chạy tiếp.
UPLOAD_FOLDER = "Nguồn tải lên"
SPLIT_FOLDER = "Nguồn tách chương"
UPLOAD_EPUB_FOLDER = "Sách đã tách"  # trong UPLOAD_FOLDER: chương tách từ EPUB / DOCX / PDF mà thiết bị ở xa gửi lên
MAX_SOURCE_UPLOAD = 40 * 1024 * 1024  # một file: chương dài nhất của kho truyện ~200 KB, nhưng cả cuốn trong một file TXT / EPUB (hàng chục MB) cũng gửi được
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


OUTSIDE_UPLOADS = ("Nguồn nằm ngoài thư viện — bạn chép file vào thư viện rồi gửi lại.")


class UploadEscape(ValueError):
    """Đường trong "Nguồn tải lên" sau khi phân giải liên kết/junction nằm ngoài thư mục ấy (hay ngoài thư viện)."""

    def __init__(self) -> None:
        super().__init__(OUTSIDE_UPLOADS)


def contained_upload(uploads: Path, path: Path) -> Path:
    """Đường THẬT của `path` (đã phân giải mọi liên kết, junction), chỉ khi nó nằm trong `uploads` và chính `uploads` nằm trong thư viện;
    không thì `UploadEscape`. So theo từng thành phần (`Nguồn tải lên 2` không nằm trong `Nguồn tải lên`), kiểm TRƯỚC mọi I/O; nơi gọi
    nên dùng đường trả về (không còn liên kết để đổi giữa lúc kiểm và lúc mở)."""
    try:
        root = uploads.resolve(strict=False)
        real = path.resolve(strict=False)
        if not root.is_relative_to(uploads.parent.resolve(strict=False)) or not real.is_relative_to(root):
            raise UploadEscape
    except (OSError, ValueError, RuntimeError) as error:
        raise UploadEscape from error
    return real


def _is_link(entry: os.DirEntry[str]) -> bool:
    """Symlink hay reparse point (junction, mount point) của Windows - `DirEntry.is_symlink` bỏ sót junction."""
    if entry.is_symlink():
        return True
    return bool(getattr(entry.stat(follow_symlinks=False), "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def check_upload_folder(uploads: Path, folder: Path) -> None:
    """Thư mục tải lên đem quét: mục con trực tiếp là liên kết/junction trỏ ra ngoài cũng bị từ chối (quét đọc cả chúng)."""
    try:
        with os.scandir(folder) as entries:
            for entry in entries:
                if _is_link(entry):
                    contained_upload(uploads, Path(entry.path))
    except OSError as error:
        raise UploadEscape from error  # không xác minh được MỘT mục cũng không được cho phép quét phần còn lại


def is_upload_part(part: str) -> bool:
    """`part` là MỘT tầng đường dẫn hợp lệ trong "Nguồn tải lên"? Đúng dạng `upload_source` / `txt_split.split` ghi ra: không rỗng, không "."
    / "..", không ký tự Windows không nhận (cả "/" "\\" ":"), không kết bằng dấu chấm / cách, không phải tên thiết bị (CON, NUL...)."""
    return bool(part) and part not in (".", "..") and not part.endswith((" ", ".")) and not _UNSAFE_NAME.search(part) \
        and not _DEVICE_NAME.match(part)


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
        raise ValueError(f"File vượt {MAX_SOURCE_UPLOAD // 2 ** 20} MB — bạn tách nhỏ để gửi hoặc mở ngay trên máy tính.")
    parts = [part for part in (_upload_name(piece, 60) for piece in folder.replace("\\", "/").split("/")) if part]
    parts = parts[:3] or ["Tải lên"]
    file_name = _upload_name(name.replace("\\", "/").rsplit("/", 1)[-1], 120)
    if not file_name.lower().endswith((".txt", *importers.IMPORT_SUFFIXES)):
        raise ValueError("Bạn gửi TXT (mỗi file một chương) hoặc một file EPUB, DOCX, PDF.")
    if any(_DEVICE_NAME.match(part) for part in parts) or _DEVICE_NAME.match(file_name):
        raise ValueError("Tên này là tên thiết bị của Windows - đổi tên file rồi gửi lại")
    uploads = library_root / UPLOAD_FOLDER
    target_dir = uploads
    for part in parts:
        target_dir /= part
    target_dir = contained_upload(uploads, target_dir)  # junction trong "Nguồn tải lên" không đưa việc ghi ra ngoài thư viện
    target_dir.mkdir(parents=True, exist_ok=True)
    target_dir = contained_upload(uploads, target_dir)  # kiểm lại sau khi tạo: liên kết đổi giữa chừng cũng bị chặn trước khi ghi byte nào
    target = target_dir / file_name
    if os.path.lexists(target):
        raise ValueError(f"Đã có chương {file_name} trong lần gửi này - hai file trùng tên")
    temporary = target_dir / f".{file_name}.part"
    # O_EXCL (xb) từ chối cả symlink có đích chưa tồn tại, không mở rồi ghi theo liên kết .part có sẵn.
    with temporary.open("xb") as output:
        output.write(data)
    os.replace(temporary, target)
    return target


class Runner(Protocol):
    def start(self, project_root: Path) -> None: ...
    def stop(self, project_root: Path) -> None: ...
    def running(self, project_root: Path) -> bool: ...
    def pause(self, project_root: Path, paused: bool) -> None: ...
    def pause_reason(self, project_root: Path) -> str | None: ...
    def can_pause(self, project_root: Path) -> bool: ...
    def stopping(self, project_root: Path) -> bool: ...
    def lease_after(self, project_root: Path) -> float | None: ...
    def last_end(self, project_root: Path) -> dict[str, Any] | None: ...


class RunnerGone(RuntimeError):
    """Sách không còn tiến trình nào để nhận lệnh "Dừng" / "Tạm dừng" (đã xong, đã dừng hay tiến trình đã chết)."""


class BackgroundRunner:
    """Supervisor thật (`background_runner`)."""

    def start(self, project_root: Path) -> None:
        from ..background_runner import start_background

        start_background(project_root)

    def stop(self, project_root: Path) -> None:
        from ..background_runner import BackgroundGone, request_stop

        try:
            request_stop(project_root, wait=False)
        except BackgroundGone as error:
            raise RunnerGone("Sách đã không còn chạy") from error

    def running(self, project_root: Path) -> bool:
        from ..background_runner import get_status

        try:
            return bool(get_status(project_root).running)
        except Exception:  # noqa: BLE001 - state hỏng thì coi như không chạy
            return False

    def pause(self, project_root: Path, paused: bool) -> None:
        from ..background_runner import BackgroundGone, request_pause

        try:
            request_pause(project_root, paused)
        except BackgroundGone as error:
            raise RunnerGone("Sách đã không còn chạy") from error

    def stopping(self, project_root: Path) -> bool:
        """Đã bấm "Dừng", worker còn đang chạy tới checkpoint sạch kế."""
        from ..background_runner import get_status

        try:
            return get_status(project_root).stopping
        except Exception:  # noqa: BLE001
            return False

    def lease_after(self, project_root: Path) -> float | None:
        """Nhịp tim worker trong sổ chỉ tính nếu mới hơn mốc này: supervisor ghi lượt chạy còn dở (kể cả đã chết) -> vô cực (nó là
        nguồn duy nhất); đã kết thúc -> lúc kết thúc; chưa có supervisor nào (chạy bằng dòng lệnh) -> None, sổ là nguồn duy nhất."""
        from ..background_runner import get_status, lease_after_of

        try:
            return lease_after_of(get_status(project_root))
        except Exception:  # noqa: BLE001
            return None

    def last_end(self, project_root: Path) -> dict[str, Any] | None:
        """Lượt chạy gần nhất của supervisor kết thúc vì sự cố (`failed`: worker lỗi / thoát bất thường; `lost`: tiến trình chết
        không kịp ghi gì) - `detail` và mã thoát để trang sách nói nguyên nhân thay vì im lặng. None: chưa chạy, đang chạy, hay
        kết thúc bình thường (xong / bạn bấm Dừng)."""
        from ..background_runner import get_status

        try:
            status = get_status(project_root)
        except Exception:  # noqa: BLE001
            return None
        if status.state not in ("failed", "lost"):
            return None
        return {"state": status.state, "detail": status.detail or "", "exitCode": status.exit_code}

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

    def log_lost(self, project_root: Path) -> dict[str, Any] | None:
        """Nhật ký phụ của lượt chạy không ghi được và đã bỏ dòng (`background_runner.log_loss`): sách vẫn chạy, trang chỉ báo."""
        from ..background_runner import get_status

        try:
            return get_status(project_root).log_lost
        except Exception:  # noqa: BLE001
            return None


class StudioRunner(BackgroundRunner):
    """App Windows đóng gói (webui/host.py): sách chạy bằng Python của Studio tải thêm (webui/studio_setup.py) và đúng
    bản mã đã bắt đầu cuốn ấy (`code_for` - app tự cập nhật không làm hỏng sách dở). Python nhúng của app chỉ có phần
    nghe. Supervisor là con của host nên thừa hưởng môi trường: runtime của Studio, PYTHONPATH tới bản mã, Ollama."""

    def __init__(self, setup: Any) -> None:
        self.setup = setup

    def start(self, project_root: Path) -> None:
        if not self.setup.installed():
            raise RuntimeError("Máy này chưa cài Studio - vào Dự án, bấm \"Cài Studio\" (một lần, khoảng 25 GB).")
        status = self.setup.status()
        if status["damaged"]:
            raise RuntimeError(f"Studio thiếu {', '.join(status['damaged'])} — bạn bấm “Sửa Studio” ở Dự án.")
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

    def stopping(self, project_root: Path) -> bool:
        return False  # giả dừng tức thì

    def lease_after(self, project_root: Path) -> float | None:
        return float("inf") if str(project_root) in self._running else None

    def last_end(self, project_root: Path) -> dict[str, Any] | None:
        return None


_TAIL_BYTES = 8192


def _read_chapter(path: Path) -> tuple[bytes, bytes, int, str]:
    """Mọi thứ trình tạo sách cần của một file chương trong MỘT lần mở: `SCAN_WORD_LIMIT_BYTES` đầu, 8 KB cuối, cỡ và sha256 (như
    io_utils.sha256_file). Thư mục 3000 chương từng mở mỗi file năm lần, mỗi lần mở ~1 ms trên Windows (soát uxfix30)."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        head = handle.read(SCAN_WORD_LIMIT_BYTES)
        digest.update(head)
        size, tail = len(head), head[-_TAIL_BYTES:]
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
            tail = (tail + chunk)[-_TAIL_BYTES:]
    return head, tail, size, digest.hexdigest()


_UNICODE_ENCODINGS = frozenset({"utf-8-sig", "utf-8", "utf-16", "utf-16-le", "utf-16-be"})
_FIRST_LINE_BYTES = 64 * 1024


def _decode_head(raw: bytes, truncated: bool = False) -> tuple[str, str]:
    """(chữ, bảng mã) của đầu một file chương, bằng đúng bộ nhận bảng mã của dây chuyền (`io_utils.decode_text`: UTF-16, UTF-8, CP1258...).
    `truncated`: đầu file bị cắt ở một mốc byte nào đó, có thể rơi giữa một ký tự (UTF-8 nhiều byte, cặp thay thế UTF-16) - lùi tới ranh
    ký tự gần nhất, không thì phần đuôi lỗi làm cả đoạn bị đoán thành CP1258 và ra chữ rác."""
    from ..io_utils import decode_text

    if truncated:
        for cut in range(4):
            try:
                text, encoding = decode_text(raw[: len(raw) - cut] if cut else raw)
            except UnicodeDecodeError:
                continue
            if encoding in _UNICODE_ENCODINGS:
                return text, encoding
    return decode_text(raw)


def _decode_tail(tail: bytes, encoding: str, head: bytes, size: int) -> str:
    """Chữ của 8 KB cuối một file dài hơn phần đầu đã đọc, theo bảng mã đã nhận ra từ phần đầu (`encoding`). Mốc cắt có thể rơi giữa một
    ký tự: UTF-16 lệch chẵn lẻ thì bỏ byte đầu, ký tự dở thì bỏ qua."""
    codec = encoding
    if encoding == "utf-16":  # BOM chỉ nằm ở đầu file: phần cuối cần biết thứ tự byte
        codec = "utf-16-be" if head.startswith(b"\xfe\xff") else "utf-16-le"
    if codec.startswith("utf-16") and (size - len(tail)) % 2:
        tail = tail[1:]
    return tail.decode(codec, errors="ignore")


def _first_line(path: Path) -> str:
    """Dòng đầu có chữ của file (gợi ý tên truyện): đọc phần đầu, cùng bộ nhận bảng mã với cả trình tạo sách."""
    try:
        with path.open("rb") as handle:
            raw = handle.read(_FIRST_LINE_BYTES + 1)
    except OSError:
        return ""
    return _first_text_line(io.StringIO(_decode_head(raw[:_FIRST_LINE_BYTES], len(raw) > _FIRST_LINE_BYTES)[0]))


def _first_text_line(lines: Iterable[str]) -> str:
    for line in lines:
        if line.strip():
            return line.strip()[:120]
    return ""


def _title_line(path: Path) -> str:
    """Dòng đầu của file nếu trông là TIÊU ĐỀ truyện (ngắn, không kết bằng dấu câu, không phải "Chương N" hay lời thoại) - tên
    sách gợi ý khi cả truyện nằm trong một file ("whole.txt" mà dòng đầu là "Chuyến phà cuối ngày"); "" nếu không."""
    first = importers.title_from_line(_first_line(path))  # luật chung với "Thêm sách từ file…" và việc tách file cả truyện
    return "" if humanize.is_heading(first) else first


def _upload_place(path: Path) -> list[str] | None:
    """Các tầng của file gửi từ thiết bị ở xa dưới thư mục tải lên: [lần gửi, (thư mục đã chọn, thư mục con...), tên file]. None khi file
    không nằm trong thư mục tải lên."""
    parts = path.resolve().parts
    for index in range(len(parts) - 1, -1, -1):
        if parts[index] == UPLOAD_FOLDER:
            return list(parts[index + 1:])
    return None


def _common_name(names: list[str]) -> str:
    """Phần chung của vài tên ("Mùa mưa 1", "Mùa mưa 2" -> "Mùa mưa"), bỏ số thứ tự / dấu ở đuôi; không có thì rỗng."""
    return re.sub(r"[\s._\-–—(\[\d]+$", "", os.path.commonprefix(names)).strip()


def _loose_upload_title(files: list[Path]) -> str | None:
    """File gửi từ thiết bị ở xa nằm trong thư mục của lần gửi (`Nguồn tải lên/<lần gửi>/`, tên có mã ngẫu nhiên): tên ấy không phải
    tên truyện. File lẻ: lấy tên file ("Mùa mưa") - nhiều file thì phần chung của tên ("Mùa mưa 1", "Mùa mưa 2" -> "Mùa mưa"); có
    thư mục đã chọn (kể cả lẫn với file lẻ) thì lấy tên thư mục ấy - không bao giờ tên chương đầu ("Chương 1"); nhiều thư mục thì
    phần chung của tên chúng. Không có thì để trống, người dùng tự đặt. None với mọi nguồn khác (infer_book_title lo)."""
    places = [_upload_place(path) for path in files]
    if not files or any(place is None or len(place) < 2 for place in places):
        return None
    folders = sorted({place[1] for place in places if place is not None and len(place) >= 3})
    if len(folders) == 1:
        return folders[0]
    if folders:
        return _common_name(folders)
    stems = [path.stem for path in files]
    if len(stems) == 1:
        return stems[0].strip()
    return _common_name(stems)


def _credits_at_top(text: str) -> list[str]:
    """Dòng ghi công người dịch / biên tập ở đầu chương (text_processing.credit_lines) - để trình tạo sách ĐỀ XUẤT bỏ
    chúng khỏi phần đọc; chỉ áp dụng khi người dùng đồng ý. Chỉ xét 8 KB chữ đầu (`text`: phần đầu file, đã giải mã)."""
    from ..text_processing import credit_lines

    head = text[:_TAIL_BYTES]
    cut = head.rfind("\n")
    return credit_lines(head[:cut] if cut > 0 else head)


def _credits_at_end(text: str, midfile: bool) -> list[str]:
    """Dòng xin ủng hộ / quảng cáo / nguồn ở cuối chương (text_processing.tail_credit_lines, luật chung với sách nhập) - trình
    tạo sách ĐỀ XUẤT bỏ như dòng ghi công đầu chương. Chỉ xét 8 KB chữ cuối (`text`); `midfile`: `text` bắt đầu giữa file nên dòng đầu
    của nó có thể dở - bỏ qua."""
    from ..text_processing import tail_credit_lines

    tail = text if midfile else text[-_TAIL_BYTES:]
    cut = tail.find("\n") if midfile or len(text) > _TAIL_BYTES else -1
    return tail_credit_lines(tail[cut + 1:] if cut >= 0 else tail)


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


def _gather_inputs(paths: list[str], epub_root: Path | None = None) -> tuple[list[Path], dict[str, Any]]:
    """Các file chương của `scan_inputs` theo thứ tự trong sách, cùng những gì phải nói với người dùng về nguồn (bỏ qua, không
    thấy, thư mục con gợi ý, lỗi, ghi chú, tên sách của file EPUB) - chưa đọc chương nào. Tạo sách chỉ cần danh sách này: thư
    mục 3000 chương từng bị đọc lại hết (ghi công, sha256...) chỉ để lấy đường dẫn (soát uxfix30)."""
    files: list[Path] = []
    seen: set[str] = set()
    skipped: list[str] = []
    missing: list[str] = []
    subfolders: list[str] = []
    errors: list[str] = []
    notes: list[str] = []
    matter: dict[str, str] = {}  # chương tách từ EPUB / DOCX không nên tích sẵn (bìa, bản quyền, mục lục...) -> lý do
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
        except importers.ImportFailed as error:
            errors.append(f"{book.name}: {error}")
            return []
        except OSError as error:  # lời báo không mang đường dẫn của máy này (thiết bị ở xa cũng đọc nó)
            errors.append(f"{book.name}: {humanize.write_error(error) if humanize.is_write_problem(error) else 'không đọc được thư mục chương vừa tách'}")
            return []
        book_title = book_title or str(info.get("title") or "")
        # Dòng ghi công đã có khung gợi ý riêng (credits/tailCredits của từng chương) - không lặp thành ghi chú (soát UX a24, A1).
        notes.extend(f"{book.name}: {note}" for note in info.get("notes") or [] if not importers.is_credit_note(note))
        groups += 1
        reasons = info.get("matter") if isinstance(info.get("matter"), dict) else {}
        for chapter in chapter_files:
            key = os.path.normcase(str(chapter.resolve()))
            group_of[key] = groups
            if chapter.name in reasons:
                matter[key] = str(reasons[chapter.name])
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
            notes.append(f"Chỉ lấy TXT trong thư mục; bạn chọn riêng {names} nếu muốn dùng file sách.")
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
    return files, {"skipped": skipped, "missing": missing, "subfolders": subfolders, "errors": errors, "notes": notes,
                   "bookTitle": book_title, "matter": matter}


def capped_notes(notes: list[str]) -> list[str]:
    """Tối đa `MAX_SCAN_NOTES` ghi chú, phần còn lại gộp thành một dòng - như bước xem trước của Nghe ngay (sách 600 trang từng ra 690 dòng)."""
    unique = list(dict.fromkeys(notes))
    if len(unique) <= MAX_SCAN_NOTES:
        return unique
    return [*unique[:MAX_SCAN_NOTES], f"…và {len(unique) - MAX_SCAN_NOTES} ghi chú nữa."]


def input_files(paths: list[str]) -> list[Path]:
    """Đúng các file chương `scan_inputs(paths)` liệt kê, không đọc chương nào."""
    return _gather_inputs(paths)[0]


def scan_inputs(paths: list[str], epub_root: Path | None = None) -> dict[str, Any]:
    """Những gì người dùng sắp đưa vào sách: file TXT (thư mục chỉ quét một tầng, như app cũ), xếp tự nhiên. File EPUB / DOCX /
    PDF (importers.py) được tách thành thư mục chương TXT trong `epub_root` (thư viện; không có thì cạnh file) rồi quét như một
    thư mục."""
    from . import txt_split, volumes

    files, found = _gather_inputs(paths, epub_root)
    rows = []
    errors = list(found["errors"])
    legacy: dict[str, list[str]] = {}
    total_words = 0
    total_seconds = 0.0
    estimated = False
    for path in files:
        try:
            head, tail, size, sha256 = _read_chapter(path)
            truncated = size > len(head)
            text, encoding = _decode_head(head, truncated)
        except UnicodeDecodeError:
            # Một file hỏng không chặn cả lô: nói tên nó và cách sửa, các file khác quét tiếp (dây chuyền cũng không đọc được file này).
            errors.append(f"{path.name} hỏng chữ — bạn tải lại hoặc lưu bản gốc dạng UTF-8.")
            continue
        except OSError as error:
            errors.append(f"{path.name}: {humanize.write_error(error) if humanize.is_write_problem(error) else 'không đọc được file (đang bị chương trình khác khoá?)'}")
            continue
        kind = importers.legacy_encoding(head, encoding)
        if kind:
            legacy.setdefault(kind, []).append(path.name)
        words = len(text.split())
        # Độ dài nghe ước: cùng cách với hộp Xuất sách nói (prepare.listening_seconds trên chữ của các đoạn đọc được) - soát a64: ở đây "4 phút",
        # hộp xuất "7 phút", thật 6:14.
        seconds = listening_seconds(sum(len(paragraph.text) for paragraph in px.split_paragraphs(text) if px.is_speakable(paragraph.text)))
        chars = sum(not ch.isspace() for ch in text)
        # File dài hơn phần đầu đã đọc: chữ, ký tự, thời lượng ngoại suy theo cỡ file (giao diện ghi "~"), không đọc cả file chỉ để đếm.
        if truncated and head:
            scale = size / len(head)
            words, chars, seconds, estimated = round(words * scale), round(chars * scale), seconds * scale, True
        total_words += words
        total_seconds += seconds
        reason = found["matter"].get(os.path.normcase(str(path)), "")
        rows.append({
            "path": str(path),
            "name": path.name,
            "title": humanize.chapter_title(path.stem),
            # Không tích sẵn (bìa, bản quyền, mục lục, mục rất ngắn của EPUB / DOCX): cùng luật với Nghe ngay (importers.default_picks); vẫn tích lại được.
            **({"matter": reason} if reason else {}),
            **({"estimated": True} if truncated else {}),
            # Cả file nằm trong phần đầu đã đọc thì lấy dòng đầu từ đó; file dài hơn (hiếm) đọc lại như trước.
            "firstLine": _first_text_line(io.StringIO(text)),
            # Dòng ghi công ở đầu chương: trình tạo sách ĐỀ XUẤT bỏ chúng khỏi phần đọc (đếm trên đúng các chương còn chọn).
            "credits": _credits_at_top(text),
            # dòng ủng hộ / quảng cáo cuối chương: đề xuất như trên (file dài hơn phần đầu đã đọc thì giải mã 8 KB cuối theo bảng mã của phần đầu)
            "tailCredits": _credits_at_end(_decode_tail(tail, encoding, head, size) if truncated else text, truncated),
            "words": words,
            "audioSeconds": round(seconds),
            # Số ký tự có chữ (không tính khoảng trắng): hiện cạnh tên chương để thấy chương nào rỗng / quá dài trước khi tạo.
            "chars": chars,
            "bytes": size,
            # Như chapters.input_sha256 của dây chuyền: nhận ra truyện đã có dự án (App.existing_projects).
            "sha256": sha256,
            # Một file chứa nhiều "Chương N": ĐỀ XUẤT tách (txt_split) - chỉ khi người dùng đưa vào vài file, không đọc lại
            # cả nghìn file chương của một thư mục bình thường.
            "split": txt_split.plan(path) if len(files) <= 3 else None,
        })
    notes = [*found["notes"], *(importers.legacy_note(kind, names) for kind, names in legacy.items())]
    title = found["bookTitle"]
    if files and not title:
        from ..project import infer_book_title

        loose = _loose_upload_title(files)
        title = (_shared_folder_name(files) if loose is None else "") or (_title_line(files[0]) if len(files) == 1 else "") or (
            loose if loose is not None else infer_book_title(files))
    return {
        "files": rows,
        "skipped": found["skipped"],
        "missing": found["missing"],
        # EPUB / DOCX / PDF không tách được (hỏng, PDF scan, không có chương nào có chữ...): nói lý do thay vì "không có chương nào".
        "errors": errors,
        # Không phải lỗi nhưng người dùng nên biết (thư mục có cả TXT lẫn EPUB: chỉ lấy TXT; trang chỉ có ảnh bị bỏ; gợi ý bỏ dòng ghi công).
        "notes": capped_notes(notes),
        # Tối đa MAX_VOLUMES: giao diện hiện vài thư mục đầu, và "dùng cả các thư mục này, mỗi thư mục một tập" cần đủ bộ.
        "subfolders": found["subfolders"][:volumes.MAX_VOLUMES],
        # Nhiều tập trong một nguồn (mỗi thư mục / EPUB một tập, hay tiêu đề "Tập 2"): ĐỀ XUẤT chia, None khi chỉ một tập.
        "volumes": volumes.propose(rows),
        "suggestedTitle": title,
        "totals": {
            "chapters": len(rows),
            "words": total_words,
            "audioSeconds": round(total_seconds),
            **({"estimated": True} if estimated else {}),
        },
    }


def first_person_hint(paths: list[str]) -> dict[str, Any]:
    """Truyện kể ngôi thứ nhất? + gợi ý "tôi" là ai, cho câu hỏi của bước chọn giọng (first_person.py)."""
    from ..first_person import first_person_hint as hint

    files = input_files(paths)
    if not files:
        return {"rate": 0.0, "firstPerson": False, "suggestions": [], "chapters": []}
    return hint(files)


def create_book(library_root: Path, paths: list[str], title: str, profile: str, narrator: str,
                first_person: str = "", settings_overrides: dict[str, Any] | None = None,
                first_person_chapters: dict[str, str] | None = None,
                drop_credit_lines: bool | None = None, drop_tail_credit_lines: bool | None = None,
                first_person_gender: str = "", teller_mode: bool = False) -> Path:
    """`narrator` rỗng = người dùng không chọn giọng dẫn: sách có người kể "tôi" thì máy chọn giọng dẫn cùng giới người ấy
    (abook/teller_voice.py). `first_person_gender` ("male"/"female"/"" = chưa rõ): người dùng nói giới người kể "tôi" ngay lúc tạo -
    ghim giới ấy cho nhân vật (như một người nghe ghim) và, khi không chọn giọng dẫn, giọng dẫn cùng giới được đặt NGAY, để bước phân vai
    tránh nó. `teller_mode` (B, tuỳ chọn, mặc định tắt): người kể "tôi" tự kể chuyện - câu lời kể của đoạn họ kể cũng đọc bằng giọng
    của chính họ (teller_voice.set_mode)."""
    from .. import teller_voice
    from ..character_registry import PRONOUNS, normalize_name
    from ..config import build_settings
    from ..project import create_or_open_project

    files = input_files(paths)
    if not files:
        raise ValueError("Chưa có file TXT nào để làm sách")
    first_person = first_person.strip()
    if first_person and normalize_name(first_person) in PRONOUNS:
        raise ValueError(f"“{first_person}” là đại từ — bạn điền tên người xưng “tôi”.")
    voices: dict[str, Any] = {}
    if teller_mode and not (first_person or any(str(name).strip() for name in (first_person_chapters or {}).values())):
        raise ValueError("Bạn điền tên người kể “tôi” để bật tự kể chuyện.")
    if first_person_gender and (first_person_gender not in teller_voice.GENDERS or not first_person):
        raise ValueError("Bạn điền tên người kể “tôi” rồi chọn giới nam hoặc nữ.")
    if narrator:
        voices["narrator_voice"] = narrator
    elif first_person_gender:
        voices["narrator_gender"] = first_person_gender  # giọng dẫn mặc định của giới ấy (config.build_settings)
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
            raise ValueError(f"“{name}” là đại từ — bạn điền tên người xưng “tôi” trong chương.")
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
    paths_created, db, _settings = create_or_open_project(files, library_root, settings, title.strip() or None)
    if not db.casting_is_finalized():  # sách đã phân vai (mở lại đúng sách cũ) thì giọng dẫn đã là chuyện đã rồi
        if teller_voice.auto_for_new_book(first_person, chapters, narrator):
            teller_voice.mark_auto(paths_created.root)
        if first_person_gender:
            db.lock_character_gender(first_person, first_person_gender)  # ghim như người nghe: thắng suy đoán của model
        if teller_mode:
            teller_voice.set_mode(paths_created.root, "teller")
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

    def reserve(self, project_root: Path) -> bool:
        """Nhận lượt trước khi chuẩn bị chạy; App giữ khoá hàng khi kiểm máy rảnh và gọi hàm này."""
        key = str(project_root)
        with self._lock:
            if key in self._starting:
                return False
            self._starting[key] = time.time()
            self._errors.pop(key, None)
            return True

    def unreserve(self, project_root: Path) -> None:
        with self._lock:
            self._starting.pop(str(project_root), None)

    def start(self, project_root: Path, on_done: Callable[[], None] | None = None, *, reserved: bool = False) -> None:
        key = str(project_root)
        if not reserved and not self.reserve(project_root):
            return

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

        try:
            threading.Thread(target=work, name=f"start {project_root.name}", daemon=True).start()
        except BaseException:
            self.unreserve(project_root)
            raise

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
