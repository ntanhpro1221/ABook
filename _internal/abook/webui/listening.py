"""Dữ liệu NGHE của người dùng: HỒ SƠ NGHE độc lập với sách, app giữ liên kết giữa hai bên (chủ sách 27-09).

Sách (thư mục sản xuất, file .abook) không biết gì về việc nghe; hồ sơ nghe không biết mình thuộc sách nào. App giữ
bảng LIÊN KẾT: một sách có nhiều hồ sơ (1-N - hai người nghe chung máy, nghe lại từ đầu mà giữ lần trước...), mỗi hồ
sơ gắn với đúng một sách, mỗi sách có một hồ sơ đang dùng. Mã sách, mã hồ sơ chỉ sống trong bảng này.

    {"version": 2,
     "records": {"<mã hồ sơ>": {"name": "Mặc định", "createdAt": ..., "state": {...}}},
     "links": {"<mã sách của app>": {"records": ["<mã hồ sơ>", ...], "active": "<mã hồ sơ>"}}}

`state` của một hồ sơ - cùng hình dạng với trạng thái trình phát Android giữ, để hai bên đồng bộ được với nhau
(`merge`: mỗi mục mang mốc thời gian, mục mới hơn thắng; dấu trang hợp theo id):

        "last": {"chapterId": 3, "seconds": 812.4, "at": 1790...},
        "chapters": {"3": {"heard": 812.4, "done": false, "at": ...}},
        "rate": 1.25,
        "finished": false,
        "bookmarks": [{"id": "...", "chapterId": 3, "seconds": 64.0, "note": "", "at": ...}],
        "night": {"id": "...", "startedAt": ..., "endedAt": ..., "events": [...], "timeline": [...]},
        "updatedAt": ...

Mọi hàm nhận MÃ SÁCH (progress, add_bookmark...) làm việc trên hồ sơ đang dùng của sách ấy - nơi gọi không phải biết
có hồ sơ. Bản lưu cũ ({mã sách: state}) được chuyển sang khi mở: mỗi sách một hồ sơ "Mặc định".

`night` là nhật ký của lần nghe có hẹn giờ ngủ gần nhất (thiết bị nào cũng được): lúc hẹn giờ, những lần chạm, lúc
bắt đầu nhỏ dần, lúc tự dừng - kèm vị trí. Sáng dậy, thẻ "Tối qua" dựng lại từ đó (MorningRecap).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from .library import preferences_path

# Nghe tới cách cuối chương dưới 20 giây là coi như nghe xong chương (đoạn cuối thường là khoảng lặng + lời
# chuyển chương, người nghe hay bấm sang chương kế trước khi nó hết).
DONE_TAIL_SECONDS = 20.0
# Hai dấu trang cùng chương cách nhau không quá chừng này là một: bấm hai lần liền (hay Space lặp lại nút vừa
# bấm) không được đẻ ra dấu trùng.
BOOKMARK_MERGE_SECONDS = 5.0
# Thẻ "Tối qua" chỉ nói về đêm vừa rồi: nhật ký cũ hơn chừng này thì thôi.
NIGHT_RECENT_SECONDS = 20 * 3600
NIGHT_MAX_POINTS = 480
MAX_SESSIONS = 200
FORMAT_VERSION = 2
DEFAULT_RECORD_NAME = "Mặc định"
MAX_RECORD_NAME = 60
RECORD_ID = re.compile(r"r-[0-9a-f]{16}")
SYNC_KEYS = ("record", "recordName", "nameAt", "activeAt", "book", "records", "active", "activeState", "deleted",
             "deletedRecords")


def listening_path() -> Path:
    return preferences_path().with_name("listening.json")


def _empty_state() -> dict[str, Any]:
    return {"chapters": {}, "bookmarks": []}


def _new_record_id() -> str:
    return "r-" + uuid.uuid4().hex[:16]


def default_record_id(book: str) -> str:
    """Mã hồ sơ "Mặc định" của một cuốn - app tự tạo khi nghe lần đầu hay khi chuyển bản lưu cũ. Suy từ mã sách theo MỘT
    công thức ở mọi máy (Android: Store.defaultRecordId), nên máy tính và điện thoại cùng nghe một cuốn là cùng MỘT hồ
    sơ, gộp được với nhau - không tách đôi chỗ nghe. Hồ sơ người dùng tự tạo thêm thì mã ngẫu nhiên."""
    return "r-" + hashlib.sha256(f"default:{book}".encode()).hexdigest()[:16]


def _upgrade(raw: Any) -> dict[str, Any]:
    """Bản lưu nào cũng thành dạng hồ sơ + liên kết. Bản cũ {mã sách: state}: mỗi sách một hồ sơ "Mặc định"."""
    if isinstance(raw, dict) and raw.get("version") == FORMAT_VERSION:
        records = raw.get("records") if isinstance(raw.get("records"), dict) else {}
        links = raw.get("links") if isinstance(raw.get("links"), dict) else {}
        deleted = raw.get("deleted") if isinstance(raw.get("deleted"), dict) else {}
        return {"version": FORMAT_VERSION, "records": records, "links": links, "deleted": deleted}
    data: dict[str, Any] = {"version": FORMAT_VERSION, "records": {}, "links": {}, "deleted": {}}
    for book, state in (raw.items() if isinstance(raw, dict) else []):
        if not isinstance(state, dict):
            continue
        record = default_record_id(str(book))
        data["records"][record] = {"name": DEFAULT_RECORD_NAME,
                                   "createdAt": float(state.get("updatedAt") or time.time()), "state": state}
        data["links"][str(book)] = {"records": [record], "active": record}
    return data


class Listening:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or listening_path()
        self._lock = threading.Lock()
        try:
            raw: Any = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raw = {}
        self._data = _upgrade(raw)

    # ---- liên kết sách - hồ sơ ---------------------------------------------------------------------------------

    def _active(self, book: str, *, create: bool = True) -> dict[str, Any] | None:
        """State của hồ sơ đang dùng cho `book`; chưa có thì (create) tạo hồ sơ "Mặc định" và gắn vào."""
        link = self._data["links"].get(book)
        record = self._data["records"].get(link.get("active")) if link and link.get("active") else None
        if record is None:
            if not create:
                return None
            record_id = default_record_id(book)
            # hồ sơ mặc định đã bị chuyển sang sách khác, hay đã bị xoá (bia mộ còn đồng bộ): mã mới
            if record_id in self._data["records"] or record_id in self._data["deleted"]:
                record_id = _new_record_id()
            record = self._data["records"][record_id] = {"name": DEFAULT_RECORD_NAME, "createdAt": time.time(),
                                                          "state": _empty_state()}
            link = self._data["links"].setdefault(book, {"records": []})
            link["records"] = [item for item in link.get("records", []) if item in self._data["records"]
                               and item != record_id] + [record_id]
            link["active"] = record_id
        state = record.setdefault("state", _empty_state())
        state.setdefault("chapters", {})
        state.setdefault("bookmarks", [])
        return state

    def _book(self, book: str) -> dict[str, Any]:
        state = self._active(book)
        assert state is not None
        return state

    def _held(self, book: str, record: str | None) -> dict[str, Any] | None:
        """State để trình phát ghi: đúng hồ sơ nó đang phát (`record`), không phải hồ sơ đang dùng - máy khác đổi hồ sơ
        giữa lúc đang phát thì chỗ nghe vẫn vào hồ sơ cũ. Hồ sơ ấy đã xoá hay đã chuyển sang sách khác: None (bỏ lần
        ghi). Không nói hồ sơ nào (điện thoại cũ, lời gọi cũ): hồ sơ đang dùng."""
        if record is None:
            return self._book(book)
        if self._owner(record) != book:
            return None
        state = self._data["records"][record].setdefault("state", _empty_state())
        state.setdefault("chapters", {})
        state.setdefault("bookmarks", [])
        return state

    def records(self, book: str) -> list[dict[str, Any]]:
        """Các hồ sơ gắn với `book`: mã, tên, lúc tạo, lúc nghe gần nhất, chỗ nghe cuối, có đang dùng không."""
        with self._lock:
            link = self._data["links"].get(book) or {}
            found = []
            for record_id in link.get("records", []):
                record = self._data["records"].get(record_id)
                if record is None:
                    continue
                state = record.get("state") or {}
                last = state.get("last") if isinstance(state.get("last"), dict) else None
                found.append({"id": record_id, "name": record.get("name") or DEFAULT_RECORD_NAME,
                              "createdAt": record.get("createdAt"), "updatedAt": state.get("updatedAt"),
                              "active": record_id == link.get("active"),
                              # Chỗ nghe cuối của hồ sơ: menu hiện "Chương 727 · 7:10" - hai hồ sơ cùng "nghe gần nhất hôm
                              # nay" mới phân biệt được (soát UX 29-09).
                              "last": {"chapterId": int(last["chapterId"]), "seconds": float(last.get("seconds") or 0)}
                              if last and str(last.get("chapterId", "")).lstrip("-").isdigit() else None})
            return found

    def create_record(self, book: str, name: str = "") -> dict[str, Any]:
        """Hồ sơ mới cho `book` (nghe từ đầu), thành hồ sơ đang dùng; hồ sơ cũ giữ nguyên."""
        with self._lock:
            link = self._data["links"].setdefault(book, {"records": []})
            record_id = _new_record_id()
            label = name.strip()[:MAX_RECORD_NAME] or f"Hồ sơ {len(link.get('records', [])) + 1}"
            self._data["records"][record_id] = {"name": label, "createdAt": time.time(), "nameAt": time.time(),
                                                "state": _empty_state()}
            link["records"] = [*link.get("records", []), record_id]
            link["active"] = record_id
            link["activeAt"] = time.time()
            self._save()
            return {"id": record_id, "name": label, "active": True}

    def activate(self, book: str, record_id: str) -> bool:
        with self._lock:
            link = self._data["links"].get(book)
            if not link or record_id not in link.get("records", []) or record_id not in self._data["records"]:
                return False
            link["active"] = record_id
            link["activeAt"] = time.time()
            self._save()
            return True

    def rename_record(self, record_id: str, name: str) -> bool:
        with self._lock:
            record = self._data["records"].get(record_id)
            if record is None or not name.strip():
                return False
            record["name"] = name.strip()[:MAX_RECORD_NAME]
            record["nameAt"] = time.time()  # đổi tên sau thắng khi đồng bộ
            self._save()
            return True

    def book_of(self, record_id: str) -> str | None:
        with self._lock:
            return self._owner(record_id)

    def move_record(self, record_id: str, to_book: str) -> bool:
        """Gắn hồ sơ sang sách khác (vd. bản sản xuất mới của cùng truyện), thành hồ sơ đang dùng ở đó."""
        with self._lock:
            if record_id not in self._data["records"]:
                return False
            self._unlink(record_id)
            link = self._data["links"].setdefault(to_book, {"records": []})
            link["records"] = [*link.get("records", []), record_id]
            link["active"] = record_id
            self._save()
            return True

    def delete_record(self, record_id: str) -> bool:
        with self._lock:
            if record_id not in self._data["records"]:
                return False
            self._unlink(record_id)
            del self._data["records"][record_id]
            self._data["deleted"][record_id] = time.time()  # bia mộ: máy kia gửi lại cũng không sống lại
            self._save()
            return True

    def books(self) -> list[str]:
        """Mã các sách có hồ sơ nghe."""
        with self._lock:
            return list(self._data["links"])

    def rename_books(self, renamed: dict[str, str]) -> None:
        """Đổi khoá sách của bảng liên kết ({mã cũ: mã mới}, library.legacy_ids). Hồ sơ giữ nguyên mã - điện thoại gộp
        theo mã hồ sơ nên vẫn khớp. Hai khoá về cùng một cuốn: gộp danh sách hồ sơ; hồ sơ đang dùng là bên chọn sau."""
        with self._lock:
            links = self._data["links"]
            changed = False
            for old, new in renamed.items():
                if old == new or old not in links:
                    continue
                moved = links.pop(old)
                existing = links.get(new)
                if existing is None:
                    links[new] = moved
                else:
                    known = list(existing.get("records", []))
                    existing["records"] = known + [item for item in moved.get("records", []) if item not in known]
                    if moved.get("active") and (not existing.get("active")
                                                or float(moved.get("activeAt") or 0) > float(existing.get("activeAt") or 0)):
                        existing["active"] = moved["active"]
                        existing["activeAt"] = float(moved.get("activeAt") or 0)
                changed = True
            if changed:
                self._save()

    def _owner(self, record_id: str) -> str | None:
        return next((book for book, link in self._data["links"].items() if record_id in link.get("records", [])),
                    None)

    def _unlink(self, record_id: str) -> None:
        book = self._owner(record_id)
        if book is None:
            return
        link = self._data["links"][book]
        link["records"] = [item for item in link["records"] if item != record_id]
        if link.get("active") == record_id:
            def heard_at(item: str) -> float:
                return float((((self._data["records"].get(item) or {}).get("state")) or {}).get("updatedAt") or 0)

            remaining = sorted(link["records"], key=heard_at)
            link["active"] = remaining[-1] if remaining else None
        if not link["records"]:
            del self._data["links"][book]

    # ---- trạng thái nghe của hồ sơ đang dùng ---------------------------------------------------------------------

    def get(self, book: str) -> dict[str, Any]:
        with self._lock:
            return json.loads(json.dumps(self._active(book, create=False) or _empty_state()))

    def all(self) -> dict[str, Any]:
        """{mã sách: state của hồ sơ đang dùng}."""
        with self._lock:
            return json.loads(json.dumps({book: self._active(book, create=False) for book in self._data["links"]}))

    def progress(self, book: str, chapter_id: int, seconds: float, duration: float,
                 record: str | None = None) -> dict[str, Any]:
        now = time.time()
        with self._lock:
            entry = self._held(book, record)
            if entry is None:
                return json.loads(json.dumps(self._active(book, create=False) or _empty_state()))
            entry["last"] = {"chapterId": int(chapter_id), "seconds": round(float(seconds), 1), "at": now}
            chapter = entry["chapters"].setdefault(str(int(chapter_id)), {"heard": 0.0, "done": False})
            chapter["heard"] = round(max(float(chapter.get("heard", 0.0)), float(seconds)), 1)
            if duration > 0 and duration - float(seconds) <= DONE_TAIL_SECONDS:
                chapter["done"] = True
            chapter["duration"] = round(float(duration), 1) if duration > 0 else chapter.get("duration", 0)
            chapter["at"] = now
            entry["updatedAt"] = now
            self._save()
            return json.loads(json.dumps(entry))

    def set_chapter_done(self, book: str, chapter_id: int, done: bool) -> dict[str, Any]:
        with self._lock:
            entry = self._book(book)
            chapter = entry["chapters"].setdefault(str(int(chapter_id)), {"heard": 0.0, "done": False})
            chapter["done"] = bool(done)
            if not done:
                chapter["heard"] = 0.0
            chapter["at"] = entry["updatedAt"] = time.time()
            self._save()
            return json.loads(json.dumps(entry))

    def set_finished(self, book: str, finished: bool) -> dict[str, Any]:
        with self._lock:
            entry = self._book(book)
            entry["finished"] = bool(finished)
            entry["finishedAt"] = entry["updatedAt"] = time.time()
            self._save()
            return json.loads(json.dumps(entry))

    def set_rate(self, book: str, rate: float) -> None:
        with self._lock:
            entry = self._book(book)
            entry["rate"] = float(rate)
            entry["rateAt"] = entry["updatedAt"] = time.time()
            self._save()

    def add_bookmark(self, book: str, chapter_id: int, seconds: float, note: str = "",
                     record: str | None = None) -> dict[str, Any]:
        """Dấu trang mới - hoặc dấu đã có ngay chỗ ấy (±5 giây cùng chương), kèm cờ `existing`. Đặt từ trình phát thì
        vào hồ sơ đang phát (`record`, xem `_held`); hồ sơ ấy vừa bị xoá thì vào hồ sơ đang dùng - người nghe đã bấm."""
        mark = {"id": uuid.uuid4().hex[:12], "chapterId": int(chapter_id), "seconds": round(float(seconds), 1),
                "note": note.strip()[:500], "at": time.time()}
        with self._lock:
            entry = self._held(book, record) or self._book(book)
            for current in entry["bookmarks"]:
                if (int(current.get("chapterId", -1)) == mark["chapterId"]
                        and abs(float(current.get("seconds", 0.0)) - mark["seconds"]) <= BOOKMARK_MERGE_SECONDS):
                    if mark["note"] and not current.get("note"):
                        current["note"] = mark["note"]
                        current["at"] = entry["updatedAt"] = mark["at"]
                        self._save()
                    return {**current, "existing": True}
            entry["bookmarks"].append(mark)
            entry["updatedAt"] = mark["at"]
            self._save()
        return mark

    def update_bookmark(self, book: str, mark_id: str, note: str) -> None:
        with self._lock:
            entry = self._book(book)
            for mark in entry["bookmarks"]:
                if mark["id"] == mark_id:
                    mark["note"] = note.strip()[:500]
            entry["updatedAt"] = time.time()
            self._save()

    def delete_bookmark(self, book: str, mark_id: str) -> None:
        with self._lock:
            entry = self._book(book)
            entry["bookmarks"] = [mark for mark in entry["bookmarks"] if mark["id"] != mark_id]
            entry.setdefault("deleted", {})[mark_id] = time.time()
            entry["updatedAt"] = time.time()
            self._save()

    def restore_bookmark(self, book: str, mark: dict[str, Any]) -> dict[str, Any]:
        """Hoàn tác xoá: đặt lại đúng dấu cũ (cùng id) và gỡ tombstone của nó."""
        with self._lock:
            entry = self._book(book)
            restored = {"id": str(mark["id"])[:40], "chapterId": int(mark["chapterId"]),
                        "seconds": round(float(mark["seconds"]), 1), "note": str(mark.get("note", ""))[:500],
                        "at": time.time()}
            entry["bookmarks"] = [item for item in entry["bookmarks"] if item["id"] != restored["id"]] + [restored]
            (entry.get("deleted") or {}).pop(restored["id"], None)
            entry["updatedAt"] = restored["at"]
            self._save()
            return restored

    def add_session(self, book: str, session: dict[str, Any], record: str | None = None) -> None:
        """Một phiên nghe (bấm phát tới lúc dừng): giờ, thiết bị, từ đâu tới đâu - cho tab "Lịch sử" và thống kê;
        vào đúng hồ sơ đã phát phiên ấy (`record`, xem `_held`)."""
        def place(value: Any) -> dict[str, Any]:
            value = value if isinstance(value, dict) else {}
            return {"chapterId": int(value.get("chapterId") or 0), "seconds": round(float(value.get("seconds") or 0), 1)}

        played = {
            "id": str(session.get("id") or uuid.uuid4().hex[:12])[:40],
            "device": str(session.get("device") or "")[:20],
            "startedAt": float(session.get("startedAt") or time.time()),
            "endedAt": float(session.get("endedAt") or time.time()),
            "listened": round(max(0.0, float(session.get("listened") or 0)), 1),
            "from": place(session.get("from")),
            "to": place(session.get("to")),
        }
        with self._lock:
            entry = self._held(book, record)
            if entry is None:
                return
            sessions = [item for item in entry.get("sessions", []) if item.get("id") != played["id"]] + [played]
            entry["sessions"] = sorted(sessions, key=lambda item: item["startedAt"])[-MAX_SESSIONS:]
            self._save()

    def sessions(self, book: str) -> list[dict[str, Any]]:
        with self._lock:
            return json.loads(json.dumps((self._active(book, create=False) or {}).get("sessions", [])))

    def set_reading(self, book: str, chapter_id: int, index: int) -> None:
        """Chỗ đọc dở ở chế độ đọc: câu thứ `index` của chương."""
        with self._lock:
            entry = self._book(book)
            entry["reading"] = {"chapterId": int(chapter_id), "index": max(0, int(index)), "at": time.time()}
            entry["updatedAt"] = entry["reading"]["at"]
            self._save()

    def save_night(self, book: str, night: dict[str, Any]) -> None:
        """Nhật ký đêm của trình phát trên máy này (điện thoại gửi của nó qua `merge`)."""
        with self._lock:
            entry = self._book(book)
            entry["night"] = merge_nights(entry.get("night"), _clean_night(night))
            entry["updatedAt"] = time.time()
            self._save()

    def latest_night(self, now: float | None = None) -> dict[str, Any] | None:
        """Đêm gần nhất chưa bị gạt đi, trong hồ sơ đang dùng của bất kỳ cuốn nào: `{"bookId", "night"}`."""
        now = time.time() if now is None else now
        with self._lock:
            found: tuple[str, dict[str, Any]] | None = None
            for book in self._data["links"]:
                night = (self._active(book, create=False) or {}).get("night")
                if not night or night.get("dismissed") or not night.get("events"):
                    continue
                if now - float(night.get("endedAt") or night.get("startedAt") or 0) > NIGHT_RECENT_SECONDS:
                    continue
                if found is None or float(night.get("startedAt") or 0) > float(found[1].get("startedAt") or 0):
                    found = (book, night)
            return None if found is None else json.loads(json.dumps({"bookId": found[0], "night": found[1]}))

    def dismiss_night(self, book: str, night_id: str) -> None:
        with self._lock:
            night = (self._active(book, create=False) or {}).get("night")
            if night and night.get("id") == night_id:
                night["dismissed"] = True
                night["dismissedAt"] = time.time()
                self._save()

    def merge(self, book: str, incoming: dict[str, Any]) -> dict[str, Any]:
        """Gộp trạng thái từ thiết bị khác (điện thoại) vào hồ sơ đang dùng của `book`. Mỗi phần mang mốc thời gian
        riêng, bên mới hơn thắng; dấu trang hợp theo id, dấu trang đã xoá ở một bên (tombstone) thì xoá ở cả hai."""
        with self._lock:
            entry = self._book(book)
            merged = merge_states(entry, incoming)
            entry.clear()
            entry.update(merged)
            self._save()
            return json.loads(json.dumps(merged))

    def merge_record(self, book: str, record_id: str, incoming: dict[str, Any], *, name: str = "",
                     name_at: float = 0.0, active_at: float = 0.0,
                     deleted: dict[str, Any] | None = None) -> dict[str, Any]:
        """Gộp MỘT hồ sơ từ thiết bị khác - đúng hồ sơ ấy, không phải hồ sơ đang dùng ở đây (đổi hồ sơ ở máy này đúng
        lúc điện thoại gửi lên thì không trộn hai hồ sơ). Hồ sơ lạ (tạo trên điện thoại) được nhận, cùng mã, gắn vào
        `book`. Hồ sơ đang dùng: bên chọn sau thắng (`active_at` là lúc điện thoại chọn hồ sơ này); tên: bên đổi sau
        thắng (`name_at`). `deleted`: bia mộ của những hồ sơ điện thoại đã xoá - ở đây xoá theo; hồ sơ vừa gửi đã bị xoá
        ở đây thì không sống lại (trả `deleted: true`).

        Trả trạng thái đã gộp, kèm `record`, `book` (sách hồ sơ gắn ở đây - có thể đã được chuyển), danh sách hồ sơ của
        sách (tên + lúc đặt tên), `active` {record, at}, mọi bia mộ đã biết (`deletedRecords`); hồ sơ đang dùng ở đây
        khác hồ sơ vừa gộp thì kèm luôn `activeState` của nó."""
        with self._lock:
            for gone, at in (deleted or {}).items():
                if isinstance(gone, str) and RECORD_ID.fullmatch(gone):
                    if gone in self._data["records"]:
                        self._unlink(gone)
                        del self._data["records"][gone]
                    self._data["deleted"][gone] = max(float(self._data["deleted"].get(gone) or 0), float(at or 0))
            if record_id in self._data["deleted"]:
                self._save()
                return {"record": record_id, "deleted": True, "deletedRecords": dict(self._data["deleted"])}
            record = self._data["records"].get(record_id)
            if record is None:
                record = self._data["records"][record_id] = {"name": name.strip()[:MAX_RECORD_NAME] or DEFAULT_RECORD_NAME,
                                                              "createdAt": time.time(), "nameAt": float(name_at or 0),
                                                              "state": _empty_state()}
            elif name.strip() and float(name_at or 0) > float(record.get("nameAt") or 0):
                record["name"] = name.strip()[:MAX_RECORD_NAME]
                record["nameAt"] = float(name_at)
            owner = self._owner(record_id)
            if owner is None:
                owner = book
                link = self._data["links"].setdefault(book, {"records": []})
                link["records"] = [*link.get("records", []), record_id]
                if not link.get("active") or link["active"] not in self._data["records"]:
                    link["active"] = record_id
            link = self._data["links"][owner]
            if active_at and float(active_at) > float(link.get("activeAt") or 0):
                link["active"] = record_id
                link["activeAt"] = float(active_at)
            state = record.setdefault("state", _empty_state())
            merged = merge_states(state, incoming)
            state.clear()
            state.update(merged)
            self._save()
            reply = json.loads(json.dumps(merged))
            reply.update({"record": record_id, "recordName": record.get("name") or DEFAULT_RECORD_NAME, "book": owner,
                          "records": [{"id": item,
                                       "name": self._data["records"][item].get("name") or DEFAULT_RECORD_NAME,
                                       "nameAt": float(self._data["records"][item].get("nameAt") or 0)}
                                      for item in link.get("records", []) if item in self._data["records"]],
                          "active": {"record": link.get("active"), "at": float(link.get("activeAt") or 0)},
                          "deletedRecords": dict(self._data["deleted"])})
            if link.get("active") and link["active"] != record_id:
                active = self._data["records"].get(link["active"]) or {}
                reply["activeState"] = json.loads(json.dumps(active.get("state") or _empty_state()))
            return reply

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self._data, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(temporary, self.path)


def book_progress(state: dict[str, Any], chapters: list[dict[str, Any]], *, complete: bool = True) -> dict[str, Any]:
    """Đã nghe bao nhiêu phần của cuốn: tính theo thời lượng, chương đánh dấu xong tính trọn.

    `chapters` là các chương NGHE ĐƯỢC. Sách đang sản xuất dở (`complete=False`) nghe hết phần đã có thì chưa phải
    "nghe xong" - nó "đã theo kịp" (`caughtUp`): trước đây nó lọt vào bộ lọc "Đã xong", rơi khỏi thẻ "Đang nghe dở",
    và "Nghe tiếp" phát lại từ đầu.
    """
    total = sum(float(chapter.get("duration") or 0.0) for chapter in chapters)
    heard = 0.0
    done_chapters = 0
    for chapter in chapters:
        record = state.get("chapters", {}).get(str(chapter["id"]))
        length = float(chapter.get("duration") or 0.0)
        if not record:
            continue
        if record.get("done"):
            heard += length
            done_chapters += 1
        else:
            heard += min(length, float(record.get("heard") or 0.0))
    all_heard = bool(chapters) and done_chapters == len(chapters)
    marked = bool(state.get("finished"))
    # Nghe hết rồi quay lại nghe một đoạn (chỗ nghe sau cùng không còn ở đuôi chương cuối, và mới hơn lần tự đánh dấu
    # nghe xong): cờ "done" của các chương vẫn còn, nhưng cuốn đang được NGHE LẠI - tiến độ theo chỗ đang nghe, không
    # còn "nghe xong" (soát UX 05-10: trang sách chỉ còn "Nghe lại từ đầu", thẻ "Đang nghe dở" mất cuốn này).
    rewound = (marked or all_heard) and _rewound(state, chapters)
    if rewound:
        heard = _position_seconds(state["last"], chapters)
    return {
        "heardSeconds": round(heard, 1),
        "totalSeconds": round(total, 1),
        "fraction": round(heard / total, 4) if total else 0.0,
        "chaptersDone": done_chapters,
        "finished": not rewound and (marked or (complete and all_heard)),
        "caughtUp": not rewound and not complete and all_heard and not marked,
        "rewound": rewound,
    }


def _rewound(state: dict[str, Any], chapters: list[dict[str, Any]]) -> bool:
    last = state.get("last") or {}
    if not chapters or "chapterId" not in last:
        return False
    if state.get("finished") and float(state.get("finishedAt") or 0.0) >= float(last.get("at") or 0.0):
        return False
    final = chapters[-1]
    if int(last["chapterId"]) != int(final["id"]):
        return any(int(chapter["id"]) == int(last["chapterId"]) for chapter in chapters)
    length = float(final.get("duration") or 0.0)
    return length > 0 and length - float(last.get("seconds") or 0.0) > DONE_TAIL_SECONDS


def _position_seconds(last: dict[str, Any], chapters: list[dict[str, Any]]) -> float:
    """Chỗ đang nghe tính từ đầu cuốn: các chương trước nó cộng số giây đã tới trong chương ấy."""
    before = 0.0
    for chapter in chapters:
        length = float(chapter.get("duration") or 0.0)
        if int(chapter["id"]) == int(last["chapterId"]):
            return before + min(length, float(last.get("seconds") or 0.0))
        before += length
    return before


def _clean_night(night: dict[str, Any]) -> dict[str, Any]:
    events = [event for event in night.get("events") or [] if isinstance(event, dict)][-200:]
    timeline = [point for point in night.get("timeline") or [] if isinstance(point, dict)][-NIGHT_MAX_POINTS:]
    return {
        "id": str(night.get("id") or uuid.uuid4().hex[:12])[:40],
        "device": str(night.get("device") or "")[:40],
        "bookTitle": str(night.get("bookTitle") or "")[:200],
        "startedAt": float(night.get("startedAt") or time.time()),
        "endedAt": float(night["endedAt"]) if night.get("endedAt") else None,
        "dismissed": bool(night.get("dismissed")),
        "events": events,
        "timeline": timeline,
    }


def merge_nights(ours: dict[str, Any] | None, theirs: dict[str, Any] | None) -> dict[str, Any] | None:
    """Đêm mới hơn thắng; cùng một đêm (cùng id) thì bản ghi dài hơn thắng, còn "đã gạt đi" ở đâu cũng giữ."""
    if not ours or not theirs:
        return ours or theirs
    if ours.get("id") != theirs.get("id"):
        return ours if float(ours.get("startedAt") or 0) >= float(theirs.get("startedAt") or 0) else theirs
    longer = ours if len(ours.get("events") or []) >= len(theirs.get("events") or []) else theirs
    result = json.loads(json.dumps(longer))
    result["dismissed"] = bool(ours.get("dismissed")) or bool(theirs.get("dismissed"))
    result["endedAt"] = ours.get("endedAt") or theirs.get("endedAt")
    return result


def merge_states(ours: dict[str, Any], theirs: dict[str, Any]) -> dict[str, Any]:
    result = json.loads(json.dumps(ours))
    result.setdefault("chapters", {})
    result.setdefault("bookmarks", [])
    if (theirs.get("last") or {}).get("at", 0) > (result.get("last") or {}).get("at", 0):
        result["last"] = theirs["last"]
    if (theirs.get("reading") or {}).get("at", 0) > (result.get("reading") or {}).get("at", 0):
        result["reading"] = theirs["reading"]
    for key, record in (theirs.get("chapters") or {}).items():
        mine = result["chapters"].get(key)
        if not mine or float(record.get("at") or 0) > float(mine.get("at") or 0):
            result["chapters"][key] = record
    for field, stamp in (("rate", "rateAt"), ("finished", "finishedAt")):
        if field in theirs and float(theirs.get(stamp) or 0) > float(result.get(stamp) or 0):
            result[field] = theirs[field]
            result[stamp] = theirs[stamp]
    deleted = dict(result.get("deleted") or {})
    deleted.update(theirs.get("deleted") or {})
    marks = {mark["id"]: mark for mark in result["bookmarks"]}
    for mark in theirs.get("bookmarks") or []:
        current = marks.get(mark["id"])
        if not current or float(mark.get("at") or 0) >= float(current.get("at") or 0):
            marks[mark["id"]] = mark
    result["bookmarks"] = sorted((mark for mark in marks.values() if mark["id"] not in deleted),
                                 key=lambda mark: mark.get("at") or 0)
    result["deleted"] = deleted
    sessions = {item["id"]: item for item in result.get("sessions") or [] if isinstance(item, dict) and item.get("id")}
    for item in theirs.get("sessions") or []:
        if isinstance(item, dict) and item.get("id"):
            sessions[item["id"]] = item
    if sessions:
        result["sessions"] = sorted(sessions.values(), key=lambda item: item.get("startedAt") or 0)[-MAX_SESSIONS:]
    night = merge_nights(result.get("night"), theirs.get("night"))
    if night:
        result["night"] = night
    result["updatedAt"] = max(float(result.get("updatedAt") or 0), float(theirs.get("updatedAt") or 0))
    return result
