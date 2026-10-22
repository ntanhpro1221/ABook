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
        "voice": "edge:vi-VN-NamMinhNeural", "voiceAt": ...,   # giọng Nghe ngay riêng của cuốn (rỗng = giọng mặc định của máy)
        "finished": false,
        "bookmarks": [{"id": "...", "chapterId": 3, "seconds": 64.0, "note": "", "at": ..., "createdAt": ...,
                       "index": 12, "quote": "Trời đã sáng."}],   # at = lần đổi cuối (gộp hai máy), createdAt = lúc đặt (hiện)
        "night": {"id": "...", "startedAt": ..., "endedAt": ..., "events": [...], "timeline": [...]},
        "updatedAt": ...

Mọi hàm nhận MÃ SÁCH (progress, add_bookmark...) làm việc trên hồ sơ đang dùng của sách ấy - nơi gọi không phải biết
có hồ sơ. Bản lưu cũ ({mã sách: state}) được chuyển sang khi mở: mỗi sách một hồ sơ "Mặc định".

`night` là nhật ký của lần nghe có hẹn giờ ngủ gần nhất (thiết bị nào cũng được): lúc hẹn giờ, những lần chạm, lúc
bắt đầu nhỏ dần, lúc tự dừng - kèm vị trí. Sáng dậy, thẻ "Tối qua" dựng lại từ đó (MorningRecap).
"""
from __future__ import annotations

import contextlib
import copy
import hashlib
import json
import os
import re
import threading
import time
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

from ..io_utils import atomic_write_json, file_lock, file_stamp
from . import notices
from .library import preferences_path

# Nghe tới cách cuối chương dưới 20 giây là coi như nghe xong chương (đoạn cuối thường là khoảng lặng + lời
# chuyển chương, người nghe hay bấm sang chương kế trước khi nó hết).
DONE_TAIL_SECONDS = 20.0
# Hai dấu trang cùng chương cách nhau không quá chừng này là một: bấm hai lần liền (hay Space lặp lại nút vừa
# bấm) không được đẻ ra dấu trùng.
BOOKMARK_MERGE_SECONDS = 5.0
BOOKMARK_QUOTE_CHARS = 60  # ~60 chữ đầu câu của dấu trang đặt ở màn đọc


def _stamp(value: Any) -> bool:
    """Một mốc giờ dùng được (số dương, không phải bool)."""
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0


def bookmark_quote(text: Any) -> str:
    """Đầu câu cho dòng dấu trang: gộp khoảng trắng, cắt ở ranh giới từ quanh `BOOKMARK_QUOTE_CHARS` ký tự, thêm "…" khi có cắt.
    Bản Kotlin: Store.bookmarkQuote."""
    clean = " ".join(str(text or "").split())
    if len(clean) <= BOOKMARK_QUOTE_CHARS:
        return clean
    cut = clean[:BOOKMARK_QUOTE_CHARS]
    space = cut.rfind(" ")
    return (cut[:space] if space > BOOKMARK_QUOTE_CHARS // 2 else cut).rstrip(" ,.;:!?…-—") + "…"
# Thẻ "Tối qua" chỉ nói về đêm vừa rồi: nhật ký cũ hơn chừng này thì thôi.
NIGHT_RECENT_SECONDS = 20 * 3600
NIGHT_MAX_POINTS = 480
MAX_SESSIONS = 200
# Phần dài của state không đi theo thẻ sách / trang sách (thẻ "Tối qua", lịch sử nghe hỏi riêng): danh sách và trang bỏ chúng.
HEAVY_KEYS = ("night", "sessions")
FORMAT_VERSION = 2
DEFAULT_RECORD_NAME = "Mặc định"
MAX_RECORD_NAME = 60
RECORD_ID = re.compile(r"r-[0-9a-f]{16}")
SYNC_KEYS = ("record", "recordName", "nameAt", "activeAt", "movedAt", "book", "records", "active", "activeState",
             "deleted", "deletedRecords")


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


def _well_formed(raw: Any) -> bool:
    """Bản lưu đọc được: dict; dạng hồ sơ (version 2) thì hồ sơ và liên kết đều là dict."""
    if not isinstance(raw, dict):
        return False
    if raw.get("version") != FORMAT_VERSION:
        return True
    return all(isinstance(raw.get(key, {}), dict) and all(isinstance(item, dict) for item in raw.get(key, {}).values())
               for key in ("records", "links"))


def _legacy_format(raw: Any) -> bool:
    return isinstance(raw, dict) and bool(raw) and raw.get("version") != FORMAT_VERSION


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


PLAYBACK_SESSIONS_KEPT = 16  # số phiên phát (lần nạp trang) nhớ mỗi hồ sơ
# Chỗ nghe (`progress`, mỗi ~10 giây) ghi nối vào file nhật ký cạnh hồ sơ chứ không ghi lại cả hồ sơ: hồ sơ của người nghe lâu năm 8-19 MB, mỗi
# lần ghi lại 0,3-0,7 giây CPU + fsync, giữ khoá chung (soát a101 F4). Nhật ký gộp vào hồ sơ ở lần ghi đầy đủ kế tiếp (mọi thay đổi khác) hay khi
# đủ JOURNAL_MAX_LINES dòng; mở lại thì phát lại nhật ký lên hồ sơ nên tắt ngang vẫn thấy chỗ nghe mới nhất.
JOURNAL_SUFFIX = ".journal"
JOURNAL_MAX_LINES = 90


def _append_journal(path: Path, line: dict[str, Any]) -> None:
    """Nối một dòng vào nhật ký và fsync. Mở đầu bằng xuống dòng: lần ghi trước bị cắt giữa chừng (tắt ngang) để lại nửa dòng, dòng này không dính vào nó."""
    payload = ("\n" + json.dumps(line, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    with open(path, "ab") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


class StalePlayback(ValueError):
    """Phiên phát đã bị cửa sổ khác thay thế, hoặc bản ghi đã cũ."""


def _apply_progress(entry: dict[str, Any], chapter_id: Any, seconds: Any, duration: Any, now: float, anchor: dict[str, Any] | None) -> None:
    """Một lần báo chỗ nghe vào state của hồ sơ (`Listening.progress`; phát lại từ nhật ký thì `anchor` đã qua `validated`)."""
    entry["last"] = {"chapterId": int(chapter_id), "seconds": round(float(seconds), 1), "at": now}
    if anchor is not None:
        entry["last"]["anchor"] = anchor
    chapter = entry["chapters"].setdefault(str(int(chapter_id)), {"heard": 0.0, "done": False})
    chapter["heard"] = round(max(float(chapter.get("heard", 0.0)), float(seconds)), 1)
    if float(duration) > 0 and float(duration) - float(seconds) <= DONE_TAIL_SECONDS:
        chapter["done"] = True
    chapter["duration"] = round(float(duration), 1) if float(duration) > 0 else chapter.get("duration", 0)
    chapter["at"] = now
    entry["updatedAt"] = now


class Listening:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or listening_path()
        self._journal = self.path.with_name(self.path.name + JOURNAL_SUFFIX)
        self._journal_lines = 0
        self._lock = threading.Lock()
        # Có file mà không đọc được (chương trình khác giữ): hồ sơ trống trong bộ nhớ, KHÔNG ghi đè file thật; đọc lại ở lần sửa kế.
        self._unread = False
        # Hồ sơ trên đĩa còn dạng cũ ({mã sách: state}): lần ghi kế phải ghi đầy đủ để chuyển nó (nhật ký chỉ áp lên dạng hiện hành).
        self._legacy = False
        try:
            raw = self._read() or {}
            self._data, self._legacy = _upgrade(raw), _legacy_format(raw)
        except notices.Unreadable:
            self._data, self._unread = _upgrade({}), True
        if not self._unread:
            self._replay()
        self._stamp = self._stamps()

    def _stamps(self) -> tuple[Any, Any]:
        """Dấu của hồ sơ và của nhật ký: một trong hai đổi (kể cả do tiến trình khác) thì bản trong bộ nhớ đã cũ."""
        return file_stamp(self.path), file_stamp(self._journal)

    def _replay(self) -> None:
        """Áp nhật ký chỗ nghe lên `self._data` (vừa đọc từ hồ sơ). Dòng cụt do tắt ngang, hay trỏ tới hồ sơ không còn: bỏ qua."""
        self._journal_lines = 0
        try:
            raw = self._journal.read_bytes()
        except OSError:
            return
        for text in raw.splitlines():
            if not text.strip():
                continue
            try:
                item = json.loads(text)
                if not isinstance(item, dict):
                    continue
                self._journal_lines += 1
                self._replay_progress(item)
            except (ValueError, KeyError, TypeError):
                continue

    def _replay_progress(self, item: dict[str, Any]) -> None:
        record = self._data["records"].get(item["record"])
        if not isinstance(record, dict):
            return
        entry = record.setdefault("state", _empty_state())
        entry.setdefault("chapters", {})
        entry.setdefault("bookmarks", [])
        last = entry.get("last")
        if isinstance(last, dict) and float(last.get("at") or 0) > float(item["now"]):
            return  # hồ sơ đã có chỗ nghe mới hơn dòng này (gộp từ máy khác, hay nhật ký chưa kịp xoá sau lần ghi đầy đủ)
        _apply_progress(entry, item["chapter"], item["seconds"], item["duration"], item["now"], item.get("anchor"))
        if item.get("session"):
            playback = record.get("_playback")
            if isinstance(playback, dict) and playback.get("id") == item["session"]:
                playback["revision"] = max(int(playback.get("revision", 0)), int(item["revision"]))
            else:
                record["_playback"] = {"id": item["session"], "revision": int(item["revision"]), "generation": int(item["generation"])}

    def compact(self) -> None:
        """Gộp nhật ký vào hồ sơ ngay (trước khi sao lưu file hồ sơ)."""
        if self._journal_lines or self._journal.exists():
            with self._changing():
                self._save()

    def _read(self) -> Any:
        """Bản lưu trên đĩa; chưa có: None. Hỏng (cắt nửa, rỗng, sai hình dạng - soát a28 lỗi 1): giữ bản hỏng + báo (notices), rồi None -
        trước đây app im lặng coi như chưa nghe gì và lần ghi kế ĐÈ mất hết chỗ nghe, dấu trang."""
        return notices.read_json(self.path, "Hồ sơ nghe (chỗ nghe dở, dấu trang)", _well_formed)

    @contextlib.contextmanager
    def _changing(self, *, require_commit: bool = False, snapshot: bool = True) -> Iterator[None]:
        """Sửa dữ liệu nghe: khoá luồng + khoá file; tiến trình khác cùng hồ sơ đã ghi từ lần mình đọc / ghi cuối thì đọc lại trước khi
        sửa (soát a28 lỗi 14: hai bên giữ cả bảng trong bộ nhớ, bên ghi sau đè mất chỗ nghe của bên kia). File mất / hỏng giữa chừng: giữ
        bản trong bộ nhớ, lần ghi này đưa nó lại ra đĩa. `snapshot=False` (với `require_commit`): không chụp cả hồ sơ để hoàn lại khi lỗi - nơi gọi
        tự hoàn phần nó sửa (`progress`: hồ sơ vài MB, chụp mỗi 10 giây là 0,3 giây)."""
        with self._lock, file_lock(self.path):
            if self._unread or self._stamps() != self._stamp:
                try:
                    raw = self._read()
                except notices.Unreadable:
                    pass
                else:
                    if raw is not None or self._unread:
                        self._data, self._legacy = _upgrade(raw or {}), _legacy_format(raw)
                        self._replay()
                    self._unread = False
                self._stamp = self._stamps()
            if require_commit and self._unread:
                raise OSError("Chưa đọc được hồ sơ nghe. Bạn hãy thử lại.")
            before = json.loads(json.dumps(self._data)) if require_commit and snapshot else None
            try:
                yield
            except BaseException:
                if before is not None:
                    self._data = before
                raise

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
        giữa lúc đang phát thì chỗ nghe vẫn vào hồ sơ cũ. Hồ sơ ấy đã xoá: None (bỏ lần ghi). Không nói hồ sơ nào (điện
        thoại cũ, lời gọi cũ), hay hồ sơ ấy đã sang sách khác (chuyển hồ sơ; hoàn tác cuốn đã xoá về tên khác mang hồ sơ của
        nó đi trong lúc cuốn đang ở đường gốc còn phát): hồ sơ đang dùng của sách này - không bỏ lặng lẽ mọi lần lưu tới khi
        trình phát nạp lại."""
        if record is None:
            return self._book(book)
        owner = self._owner(record)
        if owner is None:
            return None
        if owner != book:
            return self._book(book)
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
        with self._changing():
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
        with self._changing():
            link = self._data["links"].get(book)
            if not link or record_id not in link.get("records", []) or record_id not in self._data["records"]:
                return False
            link["active"] = record_id
            link["activeAt"] = time.time()
            self._save()
            return True

    def rename_record(self, record_id: str, name: str) -> bool:
        with self._changing():
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
        """Gắn hồ sơ sang sách khác (vd. bản sản xuất mới của cùng truyện), thành hồ sơ đang dùng ở đó. `movedAt` của hồ sơ
        là lúc chuyển: đồng bộ với điện thoại theo "lần chuyển sau thắng" (merge_record), như tên theo `nameAt`."""
        with self._changing():
            if record_id not in self._data["records"]:
                return False
            self._unlink(record_id)
            link = self._data["links"].setdefault(to_book, {"records": []})
            link["records"] = [*link.get("records", []), record_id]
            link["active"] = record_id
            link["activeAt"] = self._data["records"][record_id]["movedAt"] = time.time()
            self._save()
            return True

    def delete_record(self, record_id: str) -> bool:
        with self._changing():
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
        with self._changing():
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

    def get(self, book: str, *, omit: tuple[str, ...] = ()) -> dict[str, Any]:
        """Bản chép state của hồ sơ đang dùng. `omit`: khoá không cần (thư viện: HEAVY_KEYS) - không chép rồi bỏ cả trăm phiên nghe
        mỗi cuốn (soát a29: 18% thời gian /api/listen/library ở 300 cuốn)."""
        with self._lock:
            state = self._active(book, create=False) or _empty_state()
            if omit:
                state = {key: value for key, value in state.items() if key not in omit}
            return json.loads(json.dumps(state))

    def all(self) -> dict[str, Any]:
        """{mã sách: state của hồ sơ đang dùng}."""
        with self._lock:
            return json.loads(json.dumps({book: self._active(book, create=False) for book in self._data["links"]}))

    def _playback_owner(self, entry: dict[str, Any]) -> dict[str, Any]:
        # Quyền ghi cục bộ nằm NGOÀI state đồng bộ; điện thoại vẫn gộp theo timestamp.
        return next(row for row in self._data["records"].values() if row.get("state") is entry)

    def begin_progress(self, book: str, session_id: str, record: str | None = None) -> None:
        with self._changing(require_commit=True):
            entry = self._held(book, record)
            if entry is None:
                raise StalePlayback("Hồ sơ nghe đã bị xoá.")
            owner = self._playback_owner(entry)
            sessions = owner.setdefault("_playbackSessions", {})
            playback = owner.get("_playback") or {}
            if session_id in sessions:
                if sessions[session_id] < playback.get("generation", 0):
                    raise StalePlayback("Phiên nghe này đã bị cửa sổ khác thay thế. Bạn hãy nạp lại sách.")
                return
            owner["_playbackSerial"] = int(owner.get("_playbackSerial", 0)) + 1
            sessions[session_id] = owner["_playbackSerial"]
            # Mỗi lần nạp trang là một phiên: chỉ giữ các phiên gần nhất, phiên cũ hơn bị bỏ cũng là phiên đã bị thay thế.
            for stale in sorted(sessions, key=sessions.__getitem__)[:-PLAYBACK_SESSIONS_KEPT]:
                del sessions[stale]
            # Tab vừa mở nhưng còn đứng yên chưa vượt phiên đang phát: chỉ nhận quyền ở lần progress đầu.
            self._save()

    def progress(self, book: str, chapter_id: int, seconds: float, duration: float,
                 record: str | None = None, anchor: dict[str, Any] | None = None,
                 *, session_id: str | None = None, revision: int = 0) -> dict[str, Any]:
        from .reading_anchor import validated

        now = time.time()
        with self._changing(require_commit=True, snapshot=False):
            shape = (len(self._data["records"]), len(self._data["links"]))
            entry = self._held(book, record)
            owner: dict[str, Any] | None = None
            playback: dict[str, Any] = {}
            if session_id is not None:
                owner = self._playback_owner(entry) if entry is not None else {}
                playback = owner.get("_playback") or {}
                generation = (owner.get("_playbackSessions") or {}).get(session_id)
                if generation is None or generation < playback.get("generation", 0):
                    raise StalePlayback("Chỗ nghe đã được cửa sổ khác cập nhật. Bạn hãy nạp lại sách để nghe tiếp.")
                if playback.get("id") != session_id:
                    playback = {"id": session_id, "revision": 0, "generation": generation}
                if revision < playback.get("revision", 0) or revision <= 0:
                    raise StalePlayback("Chỗ nghe đã được cửa sổ khác cập nhật. Bạn hãy nạp lại sách để nghe tiếp.")
                if revision == playback.get("revision"):
                    return json.loads(json.dumps(entry))  # ACK bị mất: thử lại đúng bản, không đổi dấu giờ.
            if entry is None:
                return json.loads(json.dumps(self._active(book, create=False) or _empty_state()))
            saved_anchor = validated(anchor)
            # Phần sẽ sửa, để hoàn lại khi ghi không được (cả hồ sơ không chụp: xem `_changing`).
            key = str(int(chapter_id))
            undo = (copy.deepcopy(entry.get("last")), copy.deepcopy(entry["chapters"].get(key)), entry.get("updatedAt"),
                    copy.deepcopy(owner.get("_playback")) if owner is not None else None)
            try:
                if session_id is not None and owner is not None:
                    owner["_playback"] = playback = {**playback, "revision": revision}
                _apply_progress(entry, chapter_id, seconds, duration, now, saved_anchor)
                if (len(self._data["records"]), len(self._data["links"])) != shape or self._legacy or file_stamp(self.path) is None:
                    self._save()  # hồ sơ / liên kết mới sinh, hay file còn dạng cũ: nhật ký không có chỗ để áp lên
                else:
                    _append_journal(self._journal, {"record": self._record_id(entry), "chapter": int(chapter_id), "seconds": float(seconds),
                                                    "duration": float(duration), "now": now, "anchor": saved_anchor,
                                                    "session": session_id if session_id is not None else "", "revision": revision,
                                                    "generation": playback.get("generation", 0)})
                    self._journal_lines += 1
                    self._stamp = self._stamps()
                    if self._journal_lines >= JOURNAL_MAX_LINES:
                        with contextlib.suppress(OSError):  # dòng đã bền trong nhật ký; gộp không được thì lần sau gộp
                            self._save()
            except BaseException:
                last, chapter_before, updated, playback_before = undo
                for name, value in (("last", last), ("updatedAt", updated)):
                    if value is None:
                        entry.pop(name, None)
                    else:
                        entry[name] = value
                if chapter_before is None:
                    entry["chapters"].pop(key, None)
                else:
                    entry["chapters"][key] = chapter_before
                if owner is not None:
                    if playback_before is None:
                        owner.pop("_playback", None)
                    else:
                        owner["_playback"] = playback_before
                raise
            return json.loads(json.dumps(entry))

    def _record_id(self, entry: dict[str, Any]) -> str:
        return next(key for key, row in self._data["records"].items() if row.get("state") is entry)

    def set_chapter_done(self, book: str, chapter_id: int, done: bool) -> dict[str, Any]:
        with self._changing():
            entry = self._book(book)
            chapter = entry["chapters"].setdefault(str(int(chapter_id)), {"heard": 0.0, "done": False})
            chapter["done"] = bool(done)
            if not done:
                chapter["heard"] = 0.0
            chapter["at"] = entry["updatedAt"] = time.time()
            self._save()
            return json.loads(json.dumps(entry))

    def set_finished(self, book: str, finished: bool) -> dict[str, Any]:
        with self._changing():
            entry = self._book(book)
            entry["finished"] = bool(finished)
            entry["finishedAt"] = entry["updatedAt"] = time.time()
            self._save()
            return json.loads(json.dumps(entry))

    def set_rate(self, book: str, rate: float) -> None:
        with self._changing():
            entry = self._book(book)
            entry["rate"] = float(rate)
            entry["rateAt"] = entry["updatedAt"] = time.time()
            self._save()

    def set_voice(self, book: str, voice: str) -> None:
        """Giọng Nghe ngay người nghe chọn RIÊNG cho cuốn (mã giọng như "edge:..."; rỗng = theo giọng mặc định). Mang mốc giờ như tốc độ: máy nghe
        sau thắng; máy nhận không có giọng ấy (giọng trên máy chưa tải) thì giữ giọng của nó (listen/readAloudVoice.ts `syncedVoice`)."""
        with self._changing():
            entry = self._book(book)
            entry["voice"] = str(voice)[:200]
            entry["voiceAt"] = entry["updatedAt"] = time.time()
            self._save()

    def add_bookmark(self, book: str, chapter_id: int, seconds: float, note: str = "",
                     record: str | None = None, index: int | None = None, quote: str = "") -> dict[str, Any]:
        """Dấu trang mới - hoặc dấu đã có ngay chỗ ấy (±5 giây cùng chương; dấu đặt ở màn đọc: cùng câu), kèm cờ `existing`.
        Đặt từ trình phát thì vào hồ sơ đang phát (`record`, xem `_held`); hồ sơ ấy vừa bị xoá thì vào hồ sơ đang dùng - người
        nghe đã bấm. `index` + `quote`: dấu đặt ở màn đọc trỏ tới CÂU (thứ tự câu trong chương, như `?at=`) và giữ ~60 chữ đầu
        câu, để dòng dấu trang nói câu chữ ấy kể cả chương chưa có audio (`seconds` khi đó là 0)."""
        now = time.time()
        mark = {"id": uuid.uuid4().hex[:12], "chapterId": int(chapter_id), "seconds": round(float(seconds), 1),
                "note": note.strip()[:500], "at": now, "createdAt": now}
        if index is not None and int(index) >= 0:
            mark["index"] = int(index)
            mark["quote"] = bookmark_quote(quote)
        with self._changing():
            entry = self._held(book, record) or self._book(book)
            for current in entry["bookmarks"]:
                if int(current.get("chapterId", -1)) != mark["chapterId"]:
                    continue
                same = (current.get("index") == mark["index"] if "index" in mark
                        else abs(float(current.get("seconds", 0.0)) - mark["seconds"]) <= BOOKMARK_MERGE_SECONDS)
                if same:
                    if mark["note"] and not current.get("note"):
                        current["note"] = mark["note"]
                        current.setdefault("createdAt", current.get("at") or mark["at"])
                        current["at"] = entry["updatedAt"] = mark["at"]
                        self._save()
                    return {**current, "existing": True}
            entry["bookmarks"].append(mark)
            entry["updatedAt"] = mark["at"]
            self._save()
        return mark

    def update_bookmark(self, book: str, mark_id: str, note: str) -> None:
        """Sửa ghi chú: `at` (mốc gộp hai máy) thành lúc sửa để bản vừa sửa thắng bản cũ của máy kia (soát a70); `createdAt` giữ lúc
        đặt dấu - điều dòng dấu trang hiện."""
        with self._changing():
            entry = self._book(book)
            now = time.time()
            for mark in entry["bookmarks"]:
                if mark["id"] == mark_id:
                    mark["note"] = note.strip()[:500]
                    mark.setdefault("createdAt", mark.get("at") or now)
                    mark["at"] = now
            entry["updatedAt"] = now
            self._save()

    def delete_bookmark(self, book: str, mark_id: str) -> None:
        with self._changing():
            entry = self._book(book)
            entry["bookmarks"] = [mark for mark in entry["bookmarks"] if mark["id"] != mark_id]
            entry.setdefault("deleted", {})[mark_id] = time.time()
            entry["updatedAt"] = time.time()
            self._save()

    def restore_bookmark(self, book: str, mark: dict[str, Any]) -> dict[str, Any]:
        """Hoàn tác xoá: đặt lại đúng dấu cũ (cùng id) và gỡ tombstone của nó. `at` mới hơn tombstone - lệnh xoá đã kịp sang máy kia
        cũng không xoá lại nó khi gộp (merge_states); `createdAt` giữ lúc đặt dấu gốc, không thành "vừa xong" (soát a70)."""
        with self._changing():
            entry = self._book(book)
            now = time.time()
            created = mark.get("createdAt") if _stamp(mark.get("createdAt")) else mark.get("at")
            restored = {"id": str(mark["id"])[:40], "chapterId": int(mark["chapterId"]),
                        "seconds": round(float(mark["seconds"]), 1), "note": str(mark.get("note", ""))[:500],
                        "at": now, "createdAt": float(created) if _stamp(created) and float(created) <= now else now}
            if isinstance(mark.get("index"), int) and not isinstance(mark["index"], bool) and mark["index"] >= 0:
                restored["index"] = mark["index"]
                restored["quote"] = bookmark_quote(mark.get("quote"))
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
        with self._changing():
            entry = self._held(book, record)
            if entry is None:
                return
            sessions = [item for item in entry.get("sessions", []) if item.get("id") != played["id"]] + [played]
            entry["sessions"] = sorted(sessions, key=lambda item: item["startedAt"])[-MAX_SESSIONS:]
            self._save()

    def sessions(self, book: str) -> list[dict[str, Any]]:
        with self._lock:
            return json.loads(json.dumps((self._active(book, create=False) or {}).get("sessions", [])))

    def set_reading(self, book: str, chapter_id: int, index: int, *, at: float | None = None,
                    anchor: dict[str, Any] | None = None, record: str | None = None) -> None:
        """Chỗ đọc theo nội dung và hồ sơ; lượt lưu đến muộn không đè bản mới hơn."""
        import math
        from .reading_anchor import validated

        when = time.time() if at is None else float(at)
        if not math.isfinite(when) or when < 0:
            raise ValueError("Thời điểm chỗ đọc không hợp lệ")
        with self._changing():
            if record is not None and self._owner(record) != book:
                return
            entry = self._held(book, record)
            if entry is None or (entry.get("reading") or {}).get("at", 0) >= when:
                return
            place = {"chapterId": int(chapter_id), "index": max(0, int(index)), "at": when}
            if clean := validated(anchor):
                place["anchor"] = clean
            entry["reading"] = place
            entry["updatedAt"] = max(entry.get("updatedAt", 0), when)
            self._save()

    def save_night(self, book: str, night: dict[str, Any]) -> None:
        """Nhật ký đêm của trình phát trên máy này (điện thoại gửi của nó qua `merge`)."""
        with self._changing():
            entry = self._book(book)
            entry["night"] = merge_nights(entry.get("night"), _clean_night(night))
            entry["updatedAt"] = time.time()
            self._save()

    def latest_night(self, now: float | None = None, exists: Callable[[str], bool] | None = None) -> dict[str, Any] | None:
        """Đêm gần nhất chưa bị gạt đi, trong hồ sơ đang dùng của bất kỳ cuốn nào: `{"bookId", "night"}`. `exists`: cuốn còn
        trong thư viện không - cuốn đã xoá thì đêm của nó không còn chỗ để "nghe tiếp", bỏ qua (nhật ký nghe vẫn giữ)."""
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
                    if exists is not None and not exists(book):
                        continue
                    found = (book, night)
            return None if found is None else json.loads(json.dumps({"bookId": found[0], "night": found[1]}))

    def dismiss_night(self, book: str, night_id: str) -> None:
        with self._changing():
            night = (self._active(book, create=False) or {}).get("night")
            if night and night.get("id") == night_id:
                night["dismissed"] = True
                night["dismissedAt"] = time.time()
                self._save()

    def merge(self, book: str, incoming: dict[str, Any]) -> dict[str, Any]:
        """Gộp trạng thái từ thiết bị khác (điện thoại) vào hồ sơ đang dùng của `book`. Mỗi phần mang mốc thời gian
        riêng, bên mới hơn thắng; dấu trang hợp theo id, dấu trang đã xoá ở một bên (tombstone) thì xoá ở cả hai."""
        with self._changing():
            entry = self._book(book)
            merged = merge_states(entry, incoming)
            entry.clear()
            entry.update(merged)
            self._save()
            return json.loads(json.dumps(merged))

    def merge_record(self, book: str, record_id: str, incoming: dict[str, Any], *, name: str = "",
                     name_at: float = 0.0, active_at: float = 0.0, moved_at: float = 0.0,
                     deleted: dict[str, Any] | None = None) -> dict[str, Any]:
        """Gộp MỘT hồ sơ từ thiết bị khác - đúng hồ sơ ấy, không phải hồ sơ đang dùng ở đây (đổi hồ sơ ở máy này đúng
        lúc điện thoại gửi lên thì không trộn hai hồ sơ). Hồ sơ lạ (tạo trên điện thoại) được nhận, cùng mã, gắn vào
        `book`. Hồ sơ đang dùng: bên chọn sau thắng (`active_at` là lúc điện thoại chọn hồ sơ này); tên: bên đổi sau
        thắng (`name_at`). Hồ sơ gắn ở sách nào: lần chuyển sau thắng (`moved_at` là lúc điện thoại chuyển hồ sơ sang
        `book`; chuyển ở đây sau đó thì `book` trong lời đáp nói sách mới cho điện thoại theo). `deleted`: bia mộ của những
        hồ sơ điện thoại đã xoá - ở đây xoá theo; hồ sơ vừa gửi đã bị xoá ở đây thì không sống lại (trả `deleted: true`).

        Trả trạng thái đã gộp, kèm `record`, `book` (sách hồ sơ gắn ở đây - có thể đã được chuyển), `movedAt` của hồ sơ,
        danh sách hồ sơ của sách (tên + lúc đặt tên + lúc chuyển), `active` {record, at}, mọi bia mộ đã biết (`deletedRecords`); hồ sơ đang dùng ở đây
        khác hồ sơ vừa gộp thì kèm luôn `activeState` của nó."""
        with self._changing():
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
            if owner is not None and owner != book and float(moved_at or 0) > float(record.get("movedAt") or 0):
                self._unlink(record_id)  # điện thoại chuyển hồ sơ sang `book` sau lần chuyển ở đây: theo nó
                owner = None
            if owner is None:
                owner = book
                link = self._data["links"].setdefault(book, {"records": []})
                link["records"] = [*link.get("records", []), record_id]
                if not link.get("active") or link["active"] not in self._data["records"]:
                    link["active"] = record_id
            if owner == book:  # hai bên cùng chỗ gắn: giữ lần chuyển muộn nhất mà bên nào biết
                record["movedAt"] = max(float(record.get("movedAt") or 0), float(moved_at or 0))
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
                          "movedAt": float(record.get("movedAt") or 0),
                          "records": [{"id": item,
                                       "name": self._data["records"][item].get("name") or DEFAULT_RECORD_NAME,
                                       "nameAt": float(self._data["records"][item].get("nameAt") or 0),
                                       "movedAt": float(self._data["records"][item].get("movedAt") or 0)}
                                      for item in link.get("records", []) if item in self._data["records"]],
                          "active": {"record": link.get("active"), "at": float(link.get("activeAt") or 0)},
                          "deletedRecords": dict(self._data["deleted"])})
            if link.get("active") and link["active"] != record_id:
                active = self._data["records"].get(link["active"]) or {}
                reply["activeState"] = json.loads(json.dumps(active.get("state") or _empty_state()))
            return reply

    def _save(self) -> None:
        if self._unread:
            return  # chưa đọc được bản trên đĩa: ghi bây giờ là đè mất chỗ nghe, dấu trang thật
        atomic_write_json(self.path, self._data, compact=True)  # nguyên tử + fsync: mất điện không để lại file rỗng
        self._legacy = False
        # Nhật ký đã nằm trong bản vừa ghi. Chưa xoá được (tắt ngang giữa hai việc, file bị giữ): lần mở sau phát lại cũng được - dòng cũ hơn chỗ nghe
        # đã có thì bị bỏ (`_replay_progress`).
        try:
            self._journal.unlink(missing_ok=True)
            self._journal_lines = 0
        except OSError:
            pass
        self._stamp = self._stamps()


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


def text_book_progress(state: dict[str, Any], chapters: list[dict[str, Any]]) -> dict[str, Any]:
    """Như `book_progress` cho sách CHỈ CÓ CHỮ (chưa chương nào có audio): không có độ dài audio để chia nên tính theo chương -
    chương nghe xong là 1, chương đang đọc dở là phần đã đọc trên độ dài ước đã ghi. Trước đây thanh tiến độ của sách chữ luôn 0.
    `chapters` là MỌI chương của sách (phép tính của điện thoại: android/progress.ts `textBookProgress`)."""
    done_chapters = 0
    heard = 0.0
    total = 0.0
    for chapter in chapters:
        record = state.get("chapters", {}).get(str(chapter["id"]))
        if not record:
            continue
        heard += float(record.get("heard") or 0.0)
        if record.get("done"):
            total += 1.0
            done_chapters += 1
        elif float(record.get("duration") or 0.0) > 0:
            total += min(1.0, max(0.0, float(record.get("heard") or 0.0) / float(record["duration"])))
    marked = bool(state.get("finished"))
    all_done = bool(chapters) and done_chapters == len(chapters)
    fraction = min(1.0, total / len(chapters)) if chapters else 0.0
    return {
        "heardSeconds": round(heard, 1),
        "totalSeconds": 0.0,
        "fraction": 1.0 if marked else round(fraction, 4),
        "chaptersDone": done_chapters,
        "finished": marked or all_done,
        "caughtUp": False,
        "rewound": False,
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
    for field, stamp in (("rate", "rateAt"), ("finished", "finishedAt"), ("voice", "voiceAt")):
        if field in theirs and float(theirs.get(stamp) or 0) > float(result.get(stamp) or 0):
            result[field] = theirs[field]
            result[stamp] = theirs[stamp]
    # Dấu trang: hợp theo id, bản sửa sau thắng (bằng nhau thì giữ bản ở đây); bia mộ chỉ xoá dấu không đổi gì sau lúc xoá - dấu được
    # Hoàn tác (mốc mới hơn) sống lại ở cả hai máy (soát a70). Hai bên cùng xoá một dấu: giữ lúc xoá sau.
    deleted = dict(result.get("deleted") or {})
    for key, stamp in (theirs.get("deleted") or {}).items():
        deleted[key] = max(float(stamp or 0), float(deleted.get(key) or 0))
    marks = {mark["id"]: mark for mark in result["bookmarks"]}
    for mark in theirs.get("bookmarks") or []:
        current = marks.get(mark["id"])
        if not current or float(mark.get("at") or 0) > float(current.get("at") or 0):
            marks[mark["id"]] = mark
    alive = [mark for mark in marks.values() if float(mark.get("at") or 0) > float(deleted.get(mark["id"]) or 0)]
    result["bookmarks"] = sorted(alive, key=lambda mark: mark.get("createdAt") or mark.get("at") or 0)
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
