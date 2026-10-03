"""Bản chụp CHỈ ĐỌC của vài màn Studio, nằm trong file `.abookproj` (`views/<tên>.json`, docs/EDITING.md phase P3).

Điện thoại (và máy Windows chưa cài Studio) mở file dự án mà không bao giờ mở `project/project.sqlite3`, nhưng người nghe vẫn
muốn thấy máy đang nghi ngờ chỗ nào, mỗi chương có bao nhiêu câu thoại, tên riêng đang đọc ra sao. Người đóng gói chụp sẵn đúng
những thứ ấy bằng CHÍNH các hàm mà Studio dùng cho các màn đó - cùng JSON với các đường `/api/books/<id>/work`, `/casting`,
`/pronunciations` - nên mọi nơi đọc chúng (Python `packages.view`, Kotlin `LocalStudio`) trả y nguyên, giao diện không phải
biết nó đến từ đâu.

| view | hàm Studio | màn |
|---|---|---|
| `work` | `work_items.work_items` | "Việc cần duyệt" |
| `casting` | `casting_review.casting_chapters` | tab "Kịch bản" (mục lục: chương nào bao nhiêu câu thoại, chỗ máy nghi) |
| `names` | `name_readings.name_readings` | "Cách đọc tên" |

Bản chụp là ảnh tại lúc đóng gói: không sửa được, không đồng bộ ngược. Chương chi tiết của tab Kịch bản không chụp (mỗi câu một
dòng, nặng) - phần nghe đã mang `scripts/<chương>.json` của cuốn.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from .casting_review import casting_chapters
from .name_readings import name_readings
from .work_items import work_items

VIEWS: dict[str, Callable[[Path], Any]] = {"work": work_items, "casting": casting_chapters, "names": name_readings}
FOLDER = "views"
MAX_BYTES = 32 * 1024 * 1024


def entry(name: str) -> str:
    return f"{FOLDER}/{name}.json"


def snapshot(project_root: Path) -> dict[str, bytes]:
    """{tên mục trong gói: JSON} của mọi view dựng được. Một view lỗi (sổ dự án thiếu cột của bản app cũ...) thì bỏ riêng nó:
    bản chụp là món quà đi kèm, không được làm hỏng việc sao lưu dự án."""
    out: dict[str, bytes] = {}
    for name, make in VIEWS.items():
        try:
            data = make(Path(project_root))
        except Exception:  # noqa: BLE001 - xem docstring
            continue
        out[entry(name)] = json.dumps(data, ensure_ascii=False, indent=1).encode("utf-8")
    return out


def available(folder: Path) -> list[str]:
    """Tên các view có trong thư mục một cuốn đã nhập, theo thứ tự `VIEWS`."""
    return [name for name in VIEWS if (Path(folder) / entry(name)).is_file()]


def load(folder: Path, name: str) -> Any | None:
    """Một view của cuốn đã nhập, hay None khi không có / hỏng."""
    if name not in VIEWS:
        return None
    try:
        return json.loads((Path(folder) / entry(name)).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
