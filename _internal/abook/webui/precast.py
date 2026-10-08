"""Duyệt trước khi thu (docs/STUDIO_REVIEW.md): lối vào đúng lúc giữa phân tích và thu âm.

Phân vai đã khoá (không còn câu `pending`, `casting_finalized`) mà chưa thu xong chương nào là lúc mọi sửa còn miễn phí:
giọng, giới, gộp bí danh, cách đọc tên, người nói - dây chuyền áp ở ranh giới chương đầu tiên (Pipeline._process_all_chapters),
chưa câu nào phải thu lại.

Hai nơi, mỗi nơi một việc, không bao giờ cùng quyết:
- GIỮ (chỉ khi người dùng bật "Chờ tôi duyệt trước khi thu" cho cuốn ấy): supervisor của lượt chạy
  (background_runner.run_supervisor, `hold_due`) - sống cả khi app đóng. Tới mốc thì nó TẠM DỪNG cuốn đúng một lần, như nút
  "Tạm dừng" (không bao giờ dừng - AGENTS.md), và ghi `HELD_FILE`. Đã giữ một lần thì thôi, kể cả sau khi người dùng bấm "Thu âm".
- BÁO: Studio (`App._precast_tick`) báo mốc MỘT lần - thông báo Windows + lời mời trong giao diện, kể cả Studio từ xa trên
  điện thoại - đọc `heldAt` để nói sách đang chờ hay đang thu tiếp. Mặc định tắt: dây chuyền không chờ ai.

Sổ riêng cạnh dự án, không chạm sổ của dây chuyền: `FILE_NAME` chỉ Studio ghi (công tắc, lúc đã báo, lúc làm tiếp),
`HELD_FILE` chỉ supervisor ghi - hai tiến trình không bao giờ ghi đè dòng của nhau.
"""
from __future__ import annotations

import json
import sqlite3
import time
from contextlib import closing
from pathlib import Path
from typing import Any, Mapping

from ..io_utils import atomic_write_json
from . import store

FILE_NAME = "studio_precast.json"
HELD_FILE = "studio_precast_held.json"
# Bước "Ai nói câu này" xét trước những câu ở ngần này chương sắp thu: chương ấy thu xong là sửa phải thu lại.
UPCOMING = 3


def _load(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _stamp(data: Mapping[str, Any], name: str) -> float | None:
    value = data.get(name)
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def read(project_root: Path) -> dict[str, Any]:
    """{"wait": bật "Chờ tôi duyệt", "announcedAt": lúc Studio đã báo mốc, "releasedAt": lúc người dùng cho thu tiếp,
    "heldAt": lúc supervisor tạm dừng cuốn để chờ duyệt}. File hỏng hay chưa có = mặc định: không chờ, chưa báo, chưa giữ."""
    root = Path(project_root)
    data = _load(root / FILE_NAME)
    return {"wait": data.get("wait") is True, "announcedAt": _stamp(data, "announcedAt"),
            "releasedAt": _stamp(data, "releasedAt"), "heldAt": _stamp(_load(root / HELD_FILE), "heldAt")}


def _write(project_root: Path, record: Mapping[str, Any]) -> dict[str, Any]:
    """Phần của Studio (không có `heldAt` - dòng ấy của supervisor)."""
    mine = {key: record.get(key) for key in ("wait", "announcedAt", "releasedAt")}
    atomic_write_json(Path(project_root) / FILE_NAME, mine, fsync=False)
    return read(project_root)


def set_wait(project_root: Path, wait: bool) -> dict[str, Any]:
    return _write(project_root, {**read(project_root), "wait": bool(wait)})


def release(project_root: Path, now: float | None = None) -> None:
    """Cuốn làm tiếp (nút "Thu âm" hay "Tiếp tục") sau khi supervisor giữ: không còn là cuốn đang chờ duyệt."""
    record = read(project_root)
    if record["heldAt"] is not None and record["releasedAt"] is None:
        _write(project_root, {**record, "releasedAt": time.time() if now is None else now})


def hold_due(project_root: Path) -> bool:
    """Supervisor hỏi mỗi nhịp kiểm nguồn điện: có phải giữ cuốn này lại chờ duyệt ngay bây giờ không - bật "Chờ tôi duyệt",
    chưa giữ lần nào, và sổ dây chuyền nói phân vai đã khoá, không còn câu chờ phân tích, chưa chương nào thu xong. Nhẹ:
    sổ JSON trước, chỉ mở DB (chỉ đọc) khi tuỳ chọn bật. Mọi lỗi đọc = "chưa" (lượt sau hỏi lại)."""
    try:
        record = read(project_root)
        if not record["wait"] or record["heldAt"] is not None:
            return False
        database = Path(project_root) / store.DB_NAME
        if not database.is_file():
            return False
        with closing(sqlite3.connect(f"{database.as_uri()}?mode=ro", uri=True, timeout=1.0)) as connection:
            finalized = connection.execute("SELECT casting_finalized FROM book WHERE id=1").fetchone()
            total, pending = connection.execute(
                "SELECT COUNT(*), COALESCE(SUM(status = 'pending'), 0) FROM segments").fetchone()
            completed = connection.execute("SELECT COUNT(*) FROM chapters WHERE status = 'completed'").fetchone()[0]
        return bool(finalized and finalized[0]) and total > 0 and not pending and not completed
    except Exception:  # noqa: BLE001 - sổ đang ghi dở, cột lạ, file khoá: không bao giờ làm chết supervisor
        return False


def mark_held(project_root: Path, now: float | None = None) -> None:
    """Chỉ supervisor gọi, ngay khi nó tạm dừng cuốn để chờ duyệt."""
    atomic_write_json(Path(project_root) / HELD_FILE, {"heldAt": time.time() if now is None else now}, fsync=True)


def ready(summary: Mapping[str, Any]) -> bool:
    """Phân tích xong VÀ phân vai đã khoá: dàn nhân vật, giọng, cách đọc tên đã có để duyệt."""
    segments = summary.get("segments") or {}
    total = int(segments.get("total") or 0)
    return bool(summary.get("castLocked")) and total > 0 and int(segments.get("analyzed") or 0) == total


def due(project_root: Path, summary: Mapping[str, Any]) -> bool:
    """Vừa qua mốc: sẵn sàng duyệt, chưa chương nào thu xong, chưa báo lần nào. Mở app khi sách đã thu được vài chương thì
    không báo - lúc ấy màn duyệt vẫn mở được, chỉ không còn "đúng lúc"."""
    chapters = summary.get("chapters") or {}
    return (summary.get("phase") != "done" and ready(summary) and not int(chapters.get("completed") or 0)
            and read(project_root)["announcedAt"] is None)


def announce(project_root: Path, now: float | None = None) -> dict[str, Any]:
    return _write(project_root, {**read(project_root), "announcedAt": time.time() if now is None else now})


def flags(project_root: Path, summary: Mapping[str, Any]) -> dict[str, Any]:
    """Phần nhỏ đi kèm tóm tắt sách (mỗi lần hỏi thư viện): giao diện mời duyệt, hiện công tắc và nút "Thu âm"."""
    record = read(project_root)
    return {
        "ready": ready(summary),
        "wait": record["wait"],
        "announcedAt": record["announcedAt"],
        # Còn đang giữ thật: supervisor tạm dừng để chờ duyệt, chưa ai cho thu tiếp, và sách vẫn đứng vì người dùng
        # (không phải vì pin). Tiến trình chết lúc đang giữ (máy chủ khởi động lại, tắt máy) thì lời hứa "chờ bạn duyệt" vẫn
        # còn: sổ giữ chỉ khép lại khi người dùng cho thu (`release`), nên sách không tự trở thành "tạm ngưng lúc phân vai" cạnh
        # một nút "Tiếp tục tạo" bỏ qua việc duyệt (soát UX a8).
        "held": record["heldAt"] is not None and record["releasedAt"] is None
        and (summary.get("paused") == "listener" or not (summary.get("running") or summary.get("starting"))),
    }


def view(project_root: Path, summary: Mapping[str, Any]) -> dict[str, Any]:
    """Màn "Duyệt trước khi thu": cờ ở trên + đã thu tới chương nào và những chương sắp thu (theo thứ tự đọc)."""
    with closing(store.connect(project_root)) as connection:
        names = store.chapter_names(connection, project_root)
        rows = connection.execute("SELECT id, chapter_index, status FROM chapters ORDER BY chapter_index, id").fetchall()

    def chapter(row: Any) -> dict[str, Any]:
        name = names.get(int(row["id"]), {})
        return {"id": int(row["id"]), "title": name.get("full") or name.get("name") or f"Chương {row['chapter_index']}"}

    done = [row for row in rows if str(row["status"]) == "completed"]
    ahead = [row for row in rows if str(row["status"]) != "completed"]
    return {
        **flags(project_root, summary),
        "chapters": len(rows),
        "recordedChapters": len(done),
        # Chương xa nhất đã thu: sửa ở chương SAU nó không phải thu lại gì.
        "recordedThrough": chapter(done[-1]) if done else None,
        "upcoming": [chapter(row) for row in ahead[:UPCOMING]],
    }
