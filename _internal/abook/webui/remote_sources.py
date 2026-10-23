"""Tham chiếu chương nguồn cho Studio từ xa: thiết bị ở xa không bao giờ biết đường dẫn nào trên máy tính (có tên người dùng Windows).

Hai loại tham chiếu, cùng một bộ phân tích (`parse`), máy tính đổi lại ra file thật ở server.Handler._ref_sources:

- `ref:<kiểu>:<mã cuốn>:<số thứ tự>:<tên file>` - "Sửa thiết lập" / "Làm lại phân tích" và "Làm tiếp cuốn này" cần đọc lại file nguồn của
  một cuốn có sẵn. Máy tính tìm file ở vị trí đó, kiểm tên file vẫn khớp rồi mới đọc. Kiểu: "redo" - chương lúc tạo cuốn ấy; "next" - chương
  kế tiếp của cuốn ấy (continuation.next_chapters).
- `up:<đường dẫn trong "Nguồn tải lên", cách bằng "/">` - file / thư mục chính thiết bị đã gửi lên (POST /api/sources/upload) hay vừa tách
  chương (POST /api/sources/split). Đổi ra file thật bằng cách nối vào `<thư viện>/Nguồn tải lên`; tầng nào là "..", rỗng, có ổ đĩa / UNC / ký
  tự lạ / tên thiết bị Windows thì không phải tham chiếu (và yêu cầu bị từ chối) - không bao giờ chạm đĩa hay mạng để quyết định điều đó.
"""
from __future__ import annotations

import re
from pathlib import Path, PureWindowsPath
from urllib.parse import quote, unquote

from . import actions

KINDS = ("redo", "next")
UPLOAD = "up"
_REF = re.compile(r"ref:(redo|next):([A-Za-z0-9_-]+):(\d+):(.*)|up:(.+)", re.S)


def make(kind: str, book: str, number: int, path: object) -> str:
    """Tham chiếu tới file thứ `number` (từ 0) của danh sách `kind` của cuốn `book`; chỉ mang TÊN file, không mang đường dẫn."""
    return f"ref:{kind}:{book}:{number}:{quote(PureWindowsPath(str(path)).name, safe='')}"


def make_upload(path: object, uploads: Path) -> str | None:
    """Tham chiếu tới `path` nằm trong thư mục tải lên `uploads`, hay None khi nó nằm ngoài đó (hay có tầng tên không hợp lệ)."""
    where = Path(str(path))
    try:
        relative = where.relative_to(uploads)
    except ValueError:
        try:
            relative = where.resolve().relative_to(uploads.resolve())
        except (OSError, ValueError):
            return None
    if not relative.parts or not all(actions.is_upload_part(part) for part in relative.parts):
        return None
    return f"{UPLOAD}:" + "/".join(relative.parts)


def parse(text: str) -> tuple[str, str, int, str] | None:
    """(kiểu, mã cuốn, số thứ tự, tên file) của một tham chiếu `ref:...`; với `up:...` là ("up", "", 0, đường dẫn tương đối bằng "/").
    None khi chuỗi không phải tham chiếu (kể cả `up:` có tầng không hợp lệ)."""
    found = _REF.fullmatch(text)
    if found is None:
        return None
    kind, book, number, name, relative = found.groups()
    if relative is not None:
        parts = relative.split("/")
        return (UPLOAD, "", 0, relative) if all(actions.is_upload_part(part) for part in parts) else None
    return kind, book, int(number), unquote(name)


def upload_path(relative: str, uploads: Path) -> Path:
    """File thật của `up:<relative>` (đã qua `parse`): nối từng tầng vào `uploads` rồi phân giải, và từ chối (`actions.UploadEscape`) khi một liên kết /
    junction đưa nó ra ngoài `uploads` (hay `uploads` ra ngoài thư viện). Trả đường đã phân giải: không còn liên kết để đổi sau lúc kiểm."""
    return actions.contained_upload(uploads, uploads.joinpath(*relative.split("/")))
