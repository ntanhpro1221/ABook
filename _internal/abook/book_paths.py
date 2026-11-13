"""Đường dẫn đọc từ sổ dự án là DỮ LIỆU, không phải lệnh: một file `.abookproj` người khác gửi mang sổ do họ viết.

Mọi chỗ đọc hay ghi file theo một cột đường dẫn của sổ (`input_path`, `output_mp3`, `wav_path`, `artifacts.path`...) đi qua
đây trước khi chạm đĩa:

- `inside(root, value)`: file thuộc về cuốn sách (MP3, WAV, mốc mức âm, bìa...) phải nằm trong thư mục sách.
- `chapter_source(root, value)`: the same containment rule for stored chapter sources.

Cả hai từ chối đường UNC (`\\\\máy\\share`, `//máy/share`) và đường thiết bị (`\\\\?\\`, `\\\\.\\`) TRƯỚC mọi I/O: chỉ cần
stat hay mở chúng là Windows đã nối SMB và gửi thông tin đăng nhập của người dùng (soát bảo mật 12-11). Đường tương đối
cũng bị từ chối (sổ luôn ghi đường tuyệt đối). Phép so trước hết theo chữ (không đụng đĩa), rồi so lại sau khi phân giải
liên kết/junction.
"""

from __future__ import annotations

import os
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

class UnsafeBookPath(ValueError):
    """Đường dẫn trong sổ dự án trỏ ra ngoài chỗ được phép. Câu chữ để người dùng đọc."""

    def __init__(self, value: Any = None) -> None:
        super().__init__("Sổ dự án có đường dẫn trỏ ra ngoài thư mục sách — app không đọc hay ghi file ở đó.")
        self.value = value


def network(value: Any) -> bool:
    """Đường mạng hay thiết bị: bắt đầu bằng hai dấu gạch (bất kỳ kiểu `\\` hay `/`)."""
    text = str(value or "").strip()
    return len(text) >= 2 and text[0] in "\\/" and text[1] in "\\/"


def _lexical(value: Any) -> Path | None:
    """Đường tuyệt đối đã gộp `..` theo chữ, hoặc None nếu rỗng / tương đối / mạng / có ký tự NUL. Không chạm đĩa."""
    if value is None or isinstance(value, bool):
        return None
    text = os.fspath(value) if isinstance(value, os.PathLike) else value
    if not isinstance(text, str) or not text.strip() or "\x00" in text or network(text):
        return None
    if os.name == "nt":
        pure = PureWindowsPath(text)
        if not pure.drive or not pure.root:  # "C:x" (theo thư mục hiện thời của ổ) và "\x" (theo ổ hiện thời) là tương đối
            return None
    elif not PurePosixPath(text).is_absolute():
        return None
    normal = os.path.normpath(text)
    if network(normal):
        return None
    return Path(normal)


def _within(path: Path, root: Path) -> bool:
    if os.name == "nt":
        return PureWindowsPath(os.path.normcase(str(path))).is_relative_to(PureWindowsPath(os.path.normcase(str(root))))
    return path.is_relative_to(root)


def _root(root: Any) -> Path:
    base = _lexical(root)
    if base is None:
        raise UnsafeBookPath(root)
    return base


def lexically_inside(root: Any, value: Any) -> bool:
    """`value` nằm trong `root` chỉ xét theo chữ (không chạm đĩa; liên kết chưa được xét - dùng `inside` trước khi mở file)."""
    base, path = _lexical(root), _lexical(value)
    return base is not None and path is not None and _within(path, base)


def inside(root: Any, value: Any) -> Path:
    """Đường thật của `value`, chỉ khi nó nằm trong thư mục sách `root`; không thì `UnsafeBookPath` (kiểm theo chữ trước mọi I/O)."""
    base = _root(root)
    path = _lexical(value)
    if path is None or not _within(path, base):
        raise UnsafeBookPath(value)
    try:
        real, real_base = path.resolve(), base.resolve()
    except (OSError, ValueError) as exc:
        raise UnsafeBookPath(value) from exc
    if network(real) or not _within(real, real_base):  # liên kết / junction trong thư mục sách trỏ ra ngoài
        raise UnsafeBookPath(value)
    return real


def chapter_source(root: Any, value: Any) -> Path:
    """Stored chapter sources must belong to the book, like every other stored file."""
    return inside(root, value)


def safe_inside(root: Any, value: Any) -> Path | None:
    """`inside` nhưng trả None thay vì ném - cho chỗ chỉ hỏi "có file không"."""
    try:
        return inside(root, value)
    except UnsafeBookPath:
        return None


def safe_source(root: Any, value: Any) -> Path | None:
    try:
        return chapter_source(root, value)
    except UnsafeBookPath:
        return None


def connection_root(connection: Any) -> Path:
    """Use the SQLite file location, never the untrusted book.project_root."""
    for _, name, filename in connection.execute("PRAGMA database_list"):
        if name == "main" and filename:
            return _root(Path(filename).parent)
    raise UnsafeBookPath()
