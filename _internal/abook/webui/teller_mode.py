"""Công tắc B "Người kể xưng “tôi” tự kể chuyện" của một cuốn (abook/teller_voice.py): xem cái giá và bật/tắt.

Bật khi sách chưa phân vai: chỉ ghi ý muốn, worker áp ngay sau khi phân vai. Đã phân vai: áp ngay trong lời gọi này (người dùng đã xác
nhận số câu phải thu lại ở hộp xác nhận) - nên chỉ khi sách KHÔNG chạy (bấm “Dừng” - Tạm dừng chưa đủ), dây chuyền không sửa cùng lúc. Câu đã thu mà đổi giọng được đặt
lại như mọi lần người nghe đổi giọng; chương xong chuyển sang "thu lại" và chạy tiếp (Tiếp tục) là thu.
"""
from __future__ import annotations

from contextlib import closing
from pathlib import Path
from typing import Any

from .. import teller_voice
from ..database import ProjectDB
from ..models import ProjectPaths
from . import store


class Busy(Exception):
    """Sách đang chạy: máy có thể đang sửa chính những câu này."""


def _cast_locked(connection: Any) -> bool:
    row = connection.execute("SELECT * FROM book WHERE id=1").fetchone()
    return bool(row is not None and "casting_finalized" in row.keys() and int(row["casting_finalized"] or 0))  # noqa: SIM118 - sqlite3.Row


def view(project_root: Path) -> dict[str, Any]:
    """{"available": sách có người kể "tôi", "mode", "castLocked", "applied": B đang áp trong sách, "plan": cái giá của việc đổi (None khi
    chưa phân vai: chưa có gì để thu lại)}. `plan.seconds` theo tốc độ thật của chính cuốn (store.seconds_per_line)."""
    settings = store.read_settings(project_root)
    record = teller_voice.read(project_root)
    with closing(store.connect(project_root)) as connection:
        tellers = teller_voice.tellers_of(project_root, settings, connection)
        cast = _cast_locked(connection)
        plan = None
        if tellers.active and cast:
            plan = teller_voice.mode_plan(connection, project_root, tellers)
            each, measured = store.seconds_per_line(connection)
            plan = {**plan, "seconds": round(plan["recorded"] * each, 1), "measured": measured}
    return {"available": tellers.active, "mode": record["mode"], "castLocked": cast, "applied": "teller" in record["applied"], "plan": plan}


def set_mode(project_root: Path, mode: str, *, running: bool) -> dict[str, Any]:
    if mode not in teller_voice.MODES:
        raise ValueError("Chế độ phải là “narrator” hoặc “teller”")
    current = view(project_root)
    if not current["available"]:
        raise ValueError("Sách này không có người kể xưng “tôi”")
    if current["castLocked"] and running and current["mode"] != mode:
        raise Busy("Sách đang chạy - bấm “Dừng” rồi đổi (Tạm dừng chưa đủ).")
    teller_voice.set_mode(project_root, mode)
    if current["castLocked"]:
        db = ProjectDB(ProjectPaths.build(project_root).db)
        teller_voice.ensure(project_root, db, store.read_settings(project_root))
    return view(project_root)
