"""Cách đọc người nghe sửa trong Studio (hộp "Việc cần anh", docs/STUDIO_REVIEW.md), áp ở ranh giới an toàn.

Giao diện không ghi SQLite của sách: dây chuyền là người ghi duy nhất. Giao diện ghi ý muốn của người nghe vào
`overrides.json` cạnh `project.sqlite3`, dây chuyền đọc file ấy ở ranh giới an toàn và áp từng yêu cầu bằng
`ProjectDB.apply_listener_pronunciation` (ghim cách đọc và đặt lại câu đã thu, một transaction).

File là TRẠNG THÁI MONG MUỐN, không phải hàng đợi: áp lại một yêu cầu đã áp là không làm gì. Nhờ vậy dây chuyền không
bao giờ phải ghi ngược vào file, và không bao giờ có hai tiến trình cùng ghi một file.

Vì sao chỉ ở ranh giới: `cli pronounce` gõ giữa lúc chạy đã giết alpha.47 - câu đang thu mang checksum chuỗi nói lấy
TRƯỚC khi đổi, rồi khâu kiểm báo lệch. Giữa hai chương thì không câu nào đang bay.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

OVERRIDES_FILE = "overrides.json"
OVERRIDES_VERSION = 1

# Lý do từ chối: mã ổn định cho máy, câu chữ cho người nằm ở giao diện (đổi câu chữ không được đổi hash chất lượng).
MULTI_WORD = "multi_word"
NOT_VIETNAMESE = "not_vietnamese"


def overrides_path(project_root: Path) -> Path:
    return Path(project_root) / OVERRIDES_FILE


def read_overrides(project_root: Path) -> dict[str, Any]:
    """Không có file, hay file không đọc được, đều là "chưa có yêu cầu nào".

    Giao diện ghi file bằng thay nguyên tử, nên file hỏng chỉ có thể do sửa tay; khi ấy làm tiếp với cái máy đã
    quyết tốt hơn là dừng cả lần chạy vì một mong muốn không đọc được."""
    try:
        data = json.loads(overrides_path(project_root).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def surface_key(surface: str) -> str:
    """Khoá một từ như `character_registry.normalize_name` - cùng khoá `pronunciations.normalized_surface`."""
    return " ".join(str(surface).strip().casefold().split())


def pronunciation_requests(overrides: dict[str, Any]) -> list[dict[str, str]]:
    """Các yêu cầu cách đọc, theo thứ tự khoá (tất định: cùng file thì cùng thứ tự áp)."""
    entries = overrides.get("pronunciations")
    if not isinstance(entries, dict):
        return []
    requests: list[dict[str, str]] = []
    for key in sorted(entries):
        entry = entries[key]
        if not isinstance(entry, dict):
            continue
        surface, spoken = entry.get("surface"), entry.get("spoken_form")
        if isinstance(surface, str) and isinstance(spoken, str) and surface.strip() and spoken.strip():
            requests.append({"surface": surface.strip(), "spoken_form": " ".join(spoken.split())})
    return requests


def pronunciation_problem(surface: str, spoken_form: str) -> str | None:
    """Mã lý do không áp được một yêu cầu, hoặc None.

    Cùng một hợp đồng với cách đọc máy tự đề xuất: MỘT từ (AGENTS.md - cách đọc lưu theo từng từ, entry nhiều từ từng
    khoá cùng một nhân vật thành hai tên), và cách đọc là các âm tiết tiếng Việt thật (`_valid_vietnamese_spoken_form`,
    đúng phép kiểm chặn "Xă-mon", "Xờ-taiu")."""
    if len(str(surface).split()) != 1:
        return MULTI_WORD
    if surface_key(spoken_form) == surface_key(surface):
        # Đọc đúng như viết: phép kiểm tự động từ chối (máy không được lười phiên âm), người nghe thì được chọn - "Deck"
        # đọc là "Deck" (tests/test_pronounce_command.py).
        return None
    from .analysis import _valid_vietnamese_spoken_form

    if not _valid_vietnamese_spoken_form(surface, spoken_form):
        return NOT_VIETNAMESE
    return None


def request_pronunciation(project_root: Path, surface: str, spoken_form: str, *, now: float) -> None:
    """Giao diện gọi: ghi (hoặc thay) mong muốn cho một từ. Ghi file tạm rồi thay nguyên tử."""
    data = read_overrides(project_root)
    entries = data.get("pronunciations")
    entries = dict(entries) if isinstance(entries, dict) else {}
    entries[surface_key(surface)] = {
        "surface": str(surface).strip(),
        "spoken_form": " ".join(str(spoken_form).split()),
        "requested_at": float(now),
    }
    data["version"] = OVERRIDES_VERSION
    data["pronunciations"] = entries
    target = overrides_path(project_root)
    handle, temporary = tempfile.mkstemp(prefix=".overrides.", suffix=".json", dir=target.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as writer:
            json.dump(data, writer, ensure_ascii=False, indent=1, sort_keys=True)
            writer.flush()
            os.fsync(writer.fileno())
        os.replace(temporary, target)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
