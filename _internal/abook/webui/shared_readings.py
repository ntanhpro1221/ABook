"""Cách đọc dùng chung cho mọi sách (01-10, chủ sách: "phần studio ưu tiên hơn").

Sửa cách đọc một tên ("Nasdell" là "Hên-cơ") trước đây chỉ có nghĩa trong MỘT cuốn - chỉ "Làm tiếp cuốn này" mang nó sang phần
sau. Cùng một từ ở cuốn khác (truyện cùng thế giới làm thành dự án riêng, từ nước ngoài hay gặp) thì máy lại đoán và người làm
sách lại sửa. Ở đây người dùng đánh dấu một cách đọc là "dùng cho mọi sách"; sách MỚI tự nhận những mục có trong truyện lúc
tạo, sách có sẵn thì bấm "Dùng cách đọc chung".

Mọi mục đi đúng đường của một lần sửa tay - `listener_overrides.request_pronunciation` (dây chuyền áp ở ranh giới chương,
thu lại câu có từ ấy) - và qua cùng phép kiểm (một từ, âm tiết tiếng Việt thật), nên không có đường thứ hai vào sách.

File cạnh preferences.json: `shared_readings.json` = {"entries": {khoá: {"surface", "spokenForm", "addedAt", "from"}}}.
"""
from __future__ import annotations

import json
import re
import threading
import time
from contextlib import closing
from pathlib import Path
from typing import Any, Iterable

from .. import listener_overrides
from ..io_utils import decode_text_bytes
from . import store

FILE_NAME = "shared_readings.json"


class SharedReadings:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()

    def _read(self) -> dict[str, dict[str, Any]]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        entries = data.get("entries") if isinstance(data, dict) else None
        return {str(key): value for key, value in entries.items() if isinstance(value, dict)} if isinstance(entries, dict) else {}

    def _write(self, entries: dict[str, dict[str, Any]]) -> None:
        from ..io_utils import _replace_with_retry

        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps({"entries": entries}, ensure_ascii=False, indent=1), encoding="utf-8")
        _replace_with_retry(temporary, self.path)

    def entries(self) -> list[dict[str, Any]]:
        """Mọi mục, theo chữ cái của từ gốc."""
        with self._lock:
            entries = self._read()
        return sorted(entries.values(), key=lambda entry: str(entry.get("surface", "")).casefold())

    def put(self, surface: str, spoken_form: str, *, source: str = "", now: float | None = None) -> dict[str, Any]:
        """Thêm hay thay một mục. Cách đọc không qua phép kiểm của dây chuyền thì ValueError(mã lý do) - như sửa trong sách."""
        surface = " ".join(str(surface).split())
        spoken = " ".join(str(spoken_form).split())
        problem = listener_overrides.pronunciation_problem(surface, spoken)
        if problem is not None:
            raise ValueError(problem)
        entry = {"surface": surface, "spokenForm": spoken, "addedAt": time.time() if now is None else now, "from": source}
        with self._lock:
            entries = self._read()
            entries[listener_overrides.surface_key(surface)] = entry
            self._write(entries)
        return entry

    def remove(self, surface: str) -> bool:
        with self._lock:
            entries = self._read()
            removed = entries.pop(listener_overrides.surface_key(surface), None) is not None
            if removed:
                self._write(entries)
        return removed


def present(entries: list[dict[str, Any]], texts: Iterable[str]) -> list[dict[str, Any]]:
    """Các mục có trong truyện: NGUYÊN TỪ, không phân biệt hoa thường - đúng phép khớp của TTS khi đọc tên ("Lucien" có trong
    "lucien," nhưng không có trong "Luciena")."""
    by_key = {listener_overrides.surface_key(str(entry.get("surface", ""))): entry for entry in entries}
    by_key.pop("", None)
    if not by_key:
        return []
    pattern = re.compile(r"(?<!\w)(" + "|".join(re.escape(key) for key in sorted(by_key, key=len, reverse=True)) + r")(?!\w)",
                         re.IGNORECASE)
    found: set[str] = set()
    for text in texts:
        found.update(match.group(1).casefold() for match in pattern.finditer(text))
        if len(found) == len(by_key):
            break
    return [entry for key, entry in by_key.items() if key in found]


def file_texts(paths: Iterable[str | Path]) -> Iterable[str]:
    """Chữ của các file chương (trình tạo sách) - file đọc hỏng thì bỏ qua: dò cách đọc không được làm hỏng việc tạo sách."""
    for path in paths:
        try:
            yield decode_text_bytes(Path(path).read_bytes())
        except OSError:
            continue


def book_texts(project_root: Path) -> Iterable[str]:
    """Chữ của một cuốn có sẵn: các câu đã tách (SQLite, chỉ đọc); sách chưa tách câu thì đọc file chương gốc."""
    with closing(store.connect(project_root)) as connection:
        rows = connection.execute("SELECT text FROM segments").fetchall()
        has_path = "input_path" in {row[1] for row in connection.execute("PRAGMA table_info(chapters)")}
        paths = [str(row[0]) for row in connection.execute("SELECT input_path FROM chapters")] if has_path and not rows else []
    if rows:
        yield "\n".join(str(row[0] or "") for row in rows)
        return
    yield from file_texts(paths)


def _current(project_root: Path) -> dict[str, str]:
    """Cách đọc cuốn sách đang dùng hay đang chờ áp, theo khoá từ: yêu cầu chờ trong overrides.json đè cách đọc trong sổ."""
    current: dict[str, str] = {}
    try:
        with closing(store.connect(project_root)) as connection:
            for row in connection.execute("SELECT normalized_surface, spoken_form FROM pronunciations"):
                current[str(row[0])] = str(row[1] or "")
    except Exception:  # noqa: BLE001 - sách mới chưa có bảng: chưa có cách đọc nào
        pass
    for request in listener_overrides.pronunciation_requests(listener_overrides.read_overrides(project_root)):
        current[listener_overrides.surface_key(request["surface"])] = request["spoken_form"]
    return current


def differing(project_root: Path, entries: list[dict[str, Any]], texts: Iterable[str]) -> list[dict[str, Any]]:
    """Mục có trong truyện mà cuốn sách đang đọc KHÁC (hay chưa có): những gì "Dùng cách đọc chung" sẽ đổi."""
    current = _current(project_root)
    result = []
    for entry in present(entries, texts):
        now = current.get(listener_overrides.surface_key(str(entry["surface"])))
        if now != entry["spokenForm"]:
            result.append({**entry, "current": now or ""})
    return result


def apply(project_root: Path, entries: list[dict[str, Any]], *, now: float | None = None) -> list[str]:
    """Ghi các mục thành yêu cầu cách đọc của cuốn sách (như người dùng sửa từng tên); trả về các từ đã ghi."""
    moment = time.time() if now is None else now
    applied = []
    for entry in entries:
        listener_overrides.request_pronunciation(project_root, str(entry["surface"]), str(entry["spokenForm"]), now=moment)
        applied.append(str(entry["surface"]))
    return applied
