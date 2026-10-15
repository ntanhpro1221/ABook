"""Tham chiếu chương nguồn cho Studio từ xa: thiết bị ở xa không bao giờ biết đường dẫn nào trên máy tính (có tên người dùng Windows).

"Sửa thiết lập" / "Làm lại phân tích" và "Làm tiếp cuốn này" cần đọc lại file nguồn của một cuốn có sẵn. Máy tính trả cho thiết bị
`ref:<kiểu>:<mã cuốn>:<số thứ tự>:<tên file>` thay cho đường dẫn; thiết bị chỉ gửi lại đúng chuỗi ấy, máy tính tự tìm file
(server.Handler._ref_sources), kiểm tên file ở vị trí đó vẫn khớp, rồi mới đọc. Kiểu: "redo" - chương lúc tạo cuốn ấy; "next" -
chương kế tiếp của cuốn ấy (continuation.next_chapters).
"""
from __future__ import annotations

import re
from pathlib import PureWindowsPath
from urllib.parse import quote, unquote

KINDS = ("redo", "next")
_REF = re.compile(r"ref:(redo|next):([A-Za-z0-9_-]+):(\d+):(.*)", re.S)


def make(kind: str, book: str, number: int, path: object) -> str:
    """Tham chiếu tới file thứ `number` (từ 0) của danh sách `kind` của cuốn `book`; chỉ mang TÊN file, không mang đường dẫn."""
    return f"ref:{kind}:{book}:{number}:{quote(PureWindowsPath(str(path)).name, safe='')}"


def parse(text: str) -> tuple[str, str, int, str] | None:
    """(kiểu, mã cuốn, số thứ tự, tên file) của một tham chiếu, hay None khi chuỗi không phải tham chiếu."""
    found = _REF.fullmatch(text)
    if found is None:
        return None
    kind, book, number, name = found.groups()
    return kind, book, int(number), unquote(name)
