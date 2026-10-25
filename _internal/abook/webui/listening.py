"""Dữ liệu NGHE của người dùng: HỒ SƠ NGHE độc lập với sách, app giữ liên kết giữa hai bên (chủ sách 27-09).

Sách (thư mục sản xuất, file .abook) không biết gì về việc nghe; hồ sơ nghe không biết mình thuộc sách nào. App giữ
bảng LIÊN KẾT: một sách có nhiều hồ sơ (1-N - hai người nghe chung máy, nghe lại từ đầu mà giữ lần trước...), mỗi hồ
sơ gắn với đúng một sách, mỗi sách có một hồ sơ đang dùng. Mã sách, mã hồ sơ chỉ sống trong bảng này.

    {"version": 2,
     "records": {"<mã hồ sơ>": {"name": "Mặc định", "createdAt": ..., "state": {...}}},
     "links": {"<mã sách của app>": {"records": ["<mã hồ sơ>", ...], "active": "<mã hồ sơ>"}}}

`state` của một hồ sơ - cùng hình dạng với trạng thái trình phát Android giữ, để hai bên đồng bộ được với nhau
(`merge`: mỗi mục mang mốc thời gian, mục mới hơn thắng):

        "last": {"chapterId": 3, "seconds": 812.4, "at": 1790...},
        "chapters": {"3": {"heard": 812.4, "done": false, "at": ...}},
        "rate": 1.25,
        "voice": "edge:vi-VN-NamMinhNeural", "voiceAt": ...,   # giọng Nghe ngay riêng của cuốn (rỗng = giọng mặc định của máy)
        "finished": false,
        "night": {"id": "...", "startedAt": ..., "endedAt": ..., "events": [...], "timeline": [...]},
        "updatedAt": ...

Mọi hàm nhận MÃ SÁCH (progress, set_rate...) làm việc trên hồ sơ đang dùng của sách ấy - nơi gọi không phải biết
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
from .listening_revision import (advance, adopt_meta, clock, epoch, observe, checked_peer, meta_items, meta_newer, require_peer_revisions,
                                 newer, revision as place_revision)

# Nghe tới cách cuối chương dưới 20 giây là coi như nghe xong chương (đoạn cuối thường là khoảng lặng + lời
# chuyển chương, người nghe hay bấm sang chương kế trước khi nó hết).
DONE_TAIL_SECONDS = 20.0


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
             "deleted", "deletedRecords", "nameRev", "activeRev", "movedRev")
# Siêu dữ liệu hồ sơ gộp theo phiên bản Lamport của bảng liên kết (`nameRev`, `activeRev`, `movedRev`, listening_revision.meta_newer);
# `nameAt`/`activeAt`/`movedAt` (đồng hồ tường) vẫn gửi cho máy 0.4.133 và chỉ quyết khi một bên chưa có phiên bản.


def _revs(row: dict[str, Any], *keys: str) -> dict[str, Any]:
    """Các phiên bản siêu dữ liệu `row` đang có, để gửi kèm mốc giờ (thiếu thì không gửi khoá ấy)."""
    return {key: row[key] for key in keys if key in row}


def listening_path() -> Path:
    return preferences_path().with_name("listening.json")


def _empty_state() -> dict[str, Any]:
    return {"chapters": {}}


def _new_record_id() -> str:
    return "r-" + uuid.uuid4().hex[:16]


def default_record_id(book: str) -> str:
    """Mã hồ sơ "Mặc định" của một cuốn - app tự tạo khi nghe lần đầu. Suy từ mã sách theo MỘT
    công thức ở mọi máy (Android: Store.defaultRecordId), nên máy tính và điện thoại cùng nghe một cuốn là cùng MỘT hồ
    sơ, gộp được với nhau - không tách đôi chỗ nghe. Hồ sơ người dùng tự tạo thêm thì mã ngẫu nhiên."""
    return "r-" + hashlib.sha256(f"default:{book}".encode()).hexdigest()[:16]


def _well_formed(raw: Any) -> bool:
    from .listening_schema import clean_profiles
    return isinstance(raw, dict) and clean_profiles(raw) == raw


def _profiles(raw: Any) -> dict[str, Any]:
    """Nội dung file hồ sơ nghe thành dạng hồ sơ + liên kết; không phải dạng hiện hành thì là hồ sơ trống."""
    if isinstance(raw, dict) and raw.get("version") == FORMAT_VERSION:
        records = raw.get("records") if isinstance(raw.get("records"), dict) else {}
        links = raw.get("links") if isinstance(raw.get("links"), dict) else {}
        deleted = raw.get("deleted") if isinstance(raw.get("deleted"), dict) else {}
        # `_clock`/`_epoch`: đồng hồ của tên, lần chuyển, hồ sơ đang chọn (listening_revision.meta_items).
        return {"version": FORMAT_VERSION, "records": records, "links": links, "deleted": deleted,
                **{key: raw[key] for key in ("_clock", "_epoch") if key in raw}}
    return {"version": FORMAT_VERSION, "records": {}, "links": {}, "deleted": {}}


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


class RecordGone(ValueError):
    """Việc ghi nhắm một hồ sơ đã bị xoá hay đã sang sách khác: từ chối rõ ràng, không rơi sang hồ sơ khác."""


class UnpreservedProfile(notices.Unreadable):
    """Readable subset is safe to display, but no writer may replace the original yet."""

    def __init__(self, readable: dict[str, Any]) -> None:
        super().__init__("Chưa giữ được hồ sơ cũ của bạn. Bạn hãy thử lại.")
        self.readable = readable


def _apply_progress(entry: dict[str, Any], chapter_id: Any, seconds: Any, duration: Any, now: float, anchor: dict[str, Any] | None,
                    rev: dict[str, Any] | None = None) -> None:
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
    if rev is not None:
        entry["last"]["rev"] = rev
        chapter["rev"] = rev
        observe(entry, rev)
    entry["updatedAt"] = now


class Listening:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or listening_path()
        self._journal = self.path.with_name(self.path.name + JOURNAL_SUFFIX)
        self._journal_lines = 0
        self._lock = threading.Lock()
        # Có file mà không đọc được (chương trình khác giữ): hồ sơ trống trong bộ nhớ, KHÔNG ghi đè file thật; đọc lại ở lần sửa kế.
        self._unread = False
        self._journal_unread = False
        try:
            with file_lock(self.path):
                raw = self._read() or {}
                self._data = _profiles(raw)
                self._replay()
                self._stamp = self._stamps()
        except notices.Unreadable as error:
            self._data, self._unread = _profiles(error.readable if isinstance(error, UnpreservedProfile) else {}), True
            self._stamp = self._stamps()

    def _stamps(self) -> tuple[Any, Any]:
        """Dấu của hồ sơ và của nhật ký: một trong hai đổi (kể cả do tiến trình khác) thì bản trong bộ nhớ đã cũ."""
        return file_stamp(self.path), file_stamp(self._journal)

    def _replay(self) -> None:
        """Áp nhật ký chỗ nghe lên `self._data` (vừa đọc từ hồ sơ). Dòng cụt do tắt ngang, hay trỏ tới hồ sơ không còn: bỏ qua."""
        self._journal_lines = 0
        try:
            raw = self._journal.read_bytes()
        except FileNotFoundError:
            self._journal_unread = False
            return
        except OSError:
            self._journal_unread = True
            notices.NOTICES.add("Chưa đọc được chỗ nghe; giữ nguyên nhật ký và thử lại trước khi lưu.")
            return
        self._journal_unread = False
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
        last = entry.get("last")
        candidate = {"at": item["now"], "rev": item.get("rev")}
        if isinstance(last, dict) and not newer(candidate, last):
            return  # hồ sơ đã có chỗ nghe mới hơn dòng này (gộp từ máy khác, hay nhật ký chưa kịp xoá sau lần ghi đầy đủ)
        _apply_progress(entry, item["chapter"], item["seconds"], item["duration"], item["now"], item.get("anchor"), item.get("rev"))
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
        trước đây app im lặng coi như chưa nghe gì và lần ghi kế ĐÈ mất hết chỗ nghe."""
        from .listening_schema import clean_profiles
        what = "Hồ sơ nghe (chỗ nghe dở)"
        existed = self.path.exists()
        raw = notices.read_json(self.path, what, lambda value: isinstance(value, dict))
        if raw is None:
            if existed:  # bản hỏng vừa được giữ sang .hong-*: hồ sơ bắt đầu lại từ trống
                self._fresh_node()
            return None
        clean = clean_profiles(raw)
        if clean != raw:
            if notices.keep_broken(self.path, what, then="app giữ phần còn đọc được", copy_only=True) is None:
                raise UnpreservedProfile(clean)
            try:
                atomic_write_json(self.path, clean, compact=True)
            except OSError as error:
                notices.NOTICES.add("Chưa lưu được hồ sơ; bản gốc vẫn còn — bạn thử lại.")
                raise UnpreservedProfile(clean) from error
            self._fresh_node()
        return clean

    def _fresh_node(self) -> None:
        """Hồ sơ dựng lại từ bản hỏng / chỉ đọc được một phần: đồng hồ có thể lùi dưới những phiên bản máy này đã gửi đi. Mã máy mới giữ
        (counter, node) không bao giờ lặp lại cho nội dung khác (soát a118 lỗi 2). Lưu mã không được thì lần chạy này vẫn dùng mã mới."""
        node = uuid.uuid4().hex
        path = preferences_path().with_name("listening-node.json")
        with contextlib.suppress(OSError), file_lock(path):
            atomic_write_json(path, {"node": node})
        self._node_id = node

    @contextlib.contextmanager
    def _changing(self, *, require_commit: bool = False, snapshot: bool = True) -> Iterator[None]:
        """Sửa dữ liệu nghe: khoá luồng + khoá file; tiến trình khác cùng hồ sơ đã ghi từ lần mình đọc / ghi cuối thì đọc lại trước khi
        sửa (soát a28 lỗi 14: hai bên giữ cả bảng trong bộ nhớ, bên ghi sau đè mất chỗ nghe của bên kia). File mất / hỏng giữa chừng: giữ
        bản trong bộ nhớ, lần ghi này đưa nó lại ra đĩa. `snapshot=False` (với `require_commit`): không chụp cả hồ sơ để hoàn lại khi lỗi - nơi gọi
        tự hoàn phần nó sửa (`progress`: hồ sơ vài MB, chụp mỗi 10 giây là 0,3 giây)."""
        with self._lock, file_lock(self.path):
            if self._unread or self._journal_unread or self._stamps() != self._stamp:
                try:
                    raw = self._read()
                except notices.Unreadable:
                    self._unread = True
                else:
                    if raw is not None or self._unread:
                        self._data = _profiles(raw or {})
                    self._replay()
                    self._unread = False
                self._stamp = self._stamps()
            if self._unread or self._journal_unread:
                raise notices.Unreadable("Chưa đọc được hồ sơ nghe. Bạn hãy thử lại.")
            before = json.loads(json.dumps(self._data)) if snapshot else None
            try:
                yield
            except BaseException:
                if before is not None:
                    self._data = before
                raise

    # ---- liên kết sách - hồ sơ ---------------------------------------------------------------------------------

    def _active(self, book: str, *, create: bool = True, default_for: str | None = None) -> dict[str, Any] | None:
        """State của hồ sơ đang dùng cho `book`; chưa có thì (create) tạo hồ sơ "Mặc định" và gắn vào. `default_for`: mã sách bên máy
        giữ sách (cuốn ảo của máy khác có mã cục bộ khác) - hồ sơ Mặc định mang mã suy từ nó, nên hai máy cùng ghép một cuốn
        không đẻ hai hồ sơ Mặc định."""
        link = self._data["links"].get(book)
        record = self._data["records"].get(link.get("active")) if link and link.get("active") else None
        if record is None:
            if not create:
                return None
            record_id = default_record_id(default_for or book)
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
        return state

    def _named(self, book: str, record: str | None) -> dict[str, Any]:
        """State để ghi cho một việc đã chốt hồ sơ lúc bắt đầu (`record`; không nói: hồ sơ đang dùng). Hồ sơ đã xoá / chuyển sách: RecordGone."""
        if record is None:
            return self._book(book)
        if self._owner(record) != book or record not in self._data["records"]:
            raise RecordGone("Hồ sơ nghe này đã bị xoá hoặc chuyển sang cuốn khác. Bạn hãy nạp lại sách.")
        state = self._data["records"][record].setdefault("state", _empty_state())
        state.setdefault("chapters", {})
        return state

    def active_record(self, book: str) -> str | None:
        """Mã hồ sơ đang dùng của sách (None: sách chưa có hồ sơ nào - lần lưu đầu mới tạo)."""
        with self._lock:
            active = (self._data["links"].get(book) or {}).get("active")
            return active if active in self._data["records"] else None

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
            rev = self._meta_rev()
            self._data["records"][record_id] = {"name": label, "createdAt": time.time(), "nameAt": time.time(), "nameRev": rev,
                                                "state": _empty_state()}
            link["records"] = [*link.get("records", []), record_id]
            link["active"] = record_id
            link["activeAt"] = time.time()
            link["activeRev"] = rev
            self._save()
            return {"id": record_id, "name": label, "active": True}

    def activate(self, book: str, record_id: str) -> bool:
        with self._changing():
            link = self._data["links"].get(book)
            if not link or record_id not in link.get("records", []) or record_id not in self._data["records"]:
                return False
            link["active"] = record_id
            link["activeAt"] = time.time()
            link["activeRev"] = self._meta_rev()
            self._save()
            return True

    def rename_record(self, record_id: str, name: str) -> bool:
        with self._changing():
            record = self._data["records"].get(record_id)
            if record is None or not name.strip():
                return False
            record["name"] = name.strip()[:MAX_RECORD_NAME]
            record["nameAt"] = time.time()
            record["nameRev"] = self._meta_rev()  # đổi tên sau (theo nhân quả, không theo đồng hồ tường) thắng khi đồng bộ
            self._save()
            return True

    def _meta_rev(self) -> dict[str, Any]:
        """Phiên bản mới cho tên / lần chuyển / hồ sơ đang chọn: một đồng hồ cho cả bảng liên kết (soát a118 lỗi 5)."""
        return advance(self._data, self._node(), meta_items)

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
            link["activeRev"] = self._data["records"][record_id]["movedRev"] = self._meta_rev()
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
                                                or meta_newer(self._data, moved.get("activeRev"), moved.get("activeAt"),
                                                              existing.get("activeRev"), existing.get("activeAt"), notices.NOTICES.add)):
                        existing["active"] = moved["active"]
                        existing["activeAt"] = float(moved.get("activeAt") or 0)
                        adopt_meta(self._data, existing, "activeRev", moved.get("activeRev"))
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
                    copy.deepcopy(owner.get("_playback")) if owner is not None else None, entry.get("_clock"), entry.get("_epoch"))
            try:
                if session_id is not None and owner is not None:
                    owner["_playback"] = playback = {**playback, "revision": revision}
                rev = advance(entry, self._node())
                _apply_progress(entry, chapter_id, seconds, duration, now, saved_anchor, rev)
                if (len(self._data["records"]), len(self._data["links"])) != shape or file_stamp(self.path) is None:
                    self._save()  # hồ sơ / liên kết mới sinh, hay chưa có file: nhật ký không có chỗ để áp lên
                else:
                    _append_journal(self._journal, {"record": self._record_id(entry), "chapter": int(chapter_id), "seconds": float(seconds),
                                                    "duration": float(duration), "now": now, "anchor": saved_anchor,
                                                    "session": session_id if session_id is not None else "", "revision": revision,
                                                    "generation": playback.get("generation", 0), "rev": rev})
                    self._journal_lines += 1
                    self._stamp = self._stamps()
                    if self._journal_lines >= JOURNAL_MAX_LINES:
                        with contextlib.suppress(OSError):  # dòng đã bền trong nhật ký; gộp không được thì lần sau gộp
                            self._save()
            except BaseException:
                last, chapter_before, updated, playback_before, clock_before, epoch_before = undo
                for name, value in (("last", last), ("updatedAt", updated), ("_clock", clock_before), ("_epoch", epoch_before)):
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

    def _node(self) -> str:
        if cached := getattr(self, "_node_id", None):
            return cached
        # Installation identity lives beside machine preferences, outside every library/profile.
        path = preferences_path().with_name("listening-node.json")
        with file_lock(path):
            node = notices.read_json(path, "Mã phiên bản hồ sơ", lambda v: isinstance(v, dict)
                                     and bool(place_revision({"rev": {"counter": 1, "node": v.get("node")}})[0]))
            if node is None:
                node = {"node": uuid.uuid4().hex}
                atomic_write_json(path, node)
        self._node_id = node["node"]
        return self._node_id

    def set_chapter_done(self, book: str, chapter_id: int, done: bool, record: str | None = None) -> dict[str, Any]:
        """Đánh dấu chương đã nghe / chưa nghe vào hồ sơ màn đang hiện (`record`; không nói: hồ sơ đang dùng). Đã xoá / chuyển sách: RecordGone."""
        with self._changing():
            entry = self._named(book, record)
            chapter = entry["chapters"].setdefault(str(int(chapter_id)), {"heard": 0.0, "done": False})
            chapter["done"] = bool(done)
            if not done:
                chapter["heard"] = 0.0
            chapter["at"] = entry["updatedAt"] = time.time()
            chapter["rev"] = advance(entry, self._node())
            self._save()
            return json.loads(json.dumps(entry))

    def set_finished(self, book: str, finished: bool, record: str | None = None) -> dict[str, Any]:
        with self._changing():
            entry = self._named(book, record)
            entry["finished"] = bool(finished)
            entry["finishedAt"] = entry["updatedAt"] = time.time()
            entry.setdefault("_fieldRevs", {})["finished"] = advance(entry, self._node())
            self._save()
            return json.loads(json.dumps(entry))

    def set_rate(self, book: str, rate: float, record: str | None = None) -> None:
        with self._changing():
            entry = self._named(book, record)
            entry["rate"] = float(rate)
            entry["rateAt"] = entry["updatedAt"] = time.time()
            entry.setdefault("_fieldRevs", {})["rate"] = advance(entry, self._node())
            self._save()

    def set_voice(self, book: str, voice: str, record: str | None = None) -> None:
        """Giọng Nghe ngay người nghe chọn RIÊNG cho cuốn (mã giọng như "edge:..."; rỗng = theo giọng mặc định). Mang mốc giờ như tốc độ: máy nghe
        sau thắng; máy nhận không có giọng ấy (giọng trên máy chưa tải) thì giữ giọng của nó (listen/readAloudVoice.ts `syncedVoice`)."""
        with self._changing():
            entry = self._named(book, record)
            entry["voice"] = str(voice)[:200]
            entry["voiceAt"] = entry["updatedAt"] = time.time()
            entry.setdefault("_fieldRevs", {})["voice"] = advance(entry, self._node())
            self._save()

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
                    anchor: dict[str, Any] | None = None, record: str | None = None, rev: dict[str, Any] | None = None) -> None:
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
            if entry is None:
                return
            place = {"chapterId": int(chapter_id), "index": max(0, int(index)), "at": when}
            if rev is not None:
                if not place_revision({"rev": rev})[0]:
                    raise ValueError("Phiên bản chỗ đọc không hợp lệ")
                place["rev"] = rev
                current = entry.get("reading")
                if current and not newer(place, current):
                    if place.get("rev") == current.get("rev") and all(place[k] == current.get(k) for k in ("chapterId", "index")):
                        return  # same durable edit retried after an ACK was lost
                    raise StalePlayback("Chỗ đọc đã được cập nhật. Bạn hãy nạp lại sách.")
                observe(entry, rev)
            else:
                place["rev"] = advance(entry, self._node())
            if clean := validated(anchor):
                place["anchor"] = clean
            entry["reading"] = place
            entry["updatedAt"] = max(entry.get("updatedAt", 0), when)
            self._save()

    def save_night(self, book: str, night: dict[str, Any], record: str | None = None) -> None:
        """Nhật ký đêm của trình phát trên máy này (điện thoại gửi của nó qua `merge`). `record`: hồ sơ của phiên đêm (chốt lúc hẹn giờ) - lượt lưu
        đến muộn sau khi người nghe đã đổi hồ sơ vẫn về đúng hồ sơ ấy; đã xoá / chuyển sách: RecordGone."""
        with self._changing():
            entry = self._named(book, record)
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
        riêng, bên mới hơn thắng."""
        require_peer_revisions(incoming)
        with self._changing():
            entry = self._book(book)
            merged = merge_states(entry, incoming)
            entry.clear()
            entry.update(merged)
            self._save()
            return json.loads(json.dumps(merged))

    def merge_record(self, book: str, record_id: str, incoming: dict[str, Any], *, name: str = "",
                     name_at: float = 0.0, active_at: float = 0.0, moved_at: float = 0.0,
                     deleted: dict[str, Any] | None = None, name_rev: Any = None, active_rev: Any = None,
                     moved_rev: Any = None) -> dict[str, Any]:
        """Gộp MỘT hồ sơ từ thiết bị khác - đúng hồ sơ ấy, không phải hồ sơ đang dùng ở đây (đổi hồ sơ ở máy này đúng
        lúc điện thoại gửi lên thì không trộn hai hồ sơ). Hồ sơ lạ (tạo trên điện thoại) được nhận, cùng mã, gắn vào
        `book`. Hồ sơ đang dùng: bên chọn sau thắng (`active_at` là lúc điện thoại chọn hồ sơ này); tên: bên đổi sau
        thắng (`name_at`). Hồ sơ gắn ở sách nào: lần chuyển sau thắng (`moved_at` là lúc điện thoại chuyển hồ sơ sang
        `book`; chuyển ở đây sau đó thì `book` trong lời đáp nói sách mới cho điện thoại theo). Ba lần "sau" ấy theo phiên bản
        `name_rev` / `active_rev` / `moved_rev` khi cả hai bên có (meta_newer), không thì theo mốc giờ. `deleted`: bia mộ của những
        hồ sơ điện thoại đã xoá - ở đây xoá theo; hồ sơ vừa gửi đã bị xoá ở đây thì không sống lại (trả `deleted: true`).

        Trả trạng thái đã gộp, kèm `record`, `book` (sách hồ sơ gắn ở đây - có thể đã được chuyển), `movedAt` của hồ sơ,
        danh sách hồ sơ của sách (tên + lúc đặt tên + lúc chuyển), `active` {record, at}, mọi bia mộ đã biết (`deletedRecords`); hồ sơ đang dùng ở đây
        khác hồ sơ vừa gộp thì kèm luôn `activeState` của nó."""
        require_peer_revisions(incoming)
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
            notify = notices.NOTICES.add
            record = self._data["records"].get(record_id)
            fresh = record is None
            if fresh:
                record = self._data["records"][record_id] = {"name": DEFAULT_RECORD_NAME, "createdAt": time.time(),
                                                              "nameAt": float(name_at or 0), "state": _empty_state()}
            if name.strip() and meta_newer(self._data, name_rev, name_at, record.get("nameRev"),
                                           -1.0 if fresh else record.get("nameAt"), notify):
                record["name"] = name.strip()[:MAX_RECORD_NAME]
                record["nameAt"] = float(name_at or 0)
                adopt_meta(self._data, record, "nameRev", name_rev)
            moved_later = meta_newer(self._data, moved_rev, moved_at, record.get("movedRev"), record.get("movedAt"), notify)
            owner = self._owner(record_id)
            if owner is not None and owner != book and moved_later:
                self._unlink(record_id)  # điện thoại chuyển hồ sơ sang `book` sau lần chuyển ở đây: theo nó
                owner = None
            if owner is None:
                owner = book
                link = self._data["links"].setdefault(book, {"records": []})
                link["records"] = [*link.get("records", []), record_id]
                if not link.get("active") or link["active"] not in self._data["records"]:
                    link["active"] = record_id
            if owner == book and moved_later:  # hai bên cùng chỗ gắn: giữ lần chuyển sau cùng mà bên nào biết
                record["movedAt"] = float(moved_at or 0)
                adopt_meta(self._data, record, "movedRev", moved_rev)
            link = self._data["links"][owner]
            if (active_at or active_rev is not None) and meta_newer(self._data, active_rev, active_at, link.get("activeRev"),
                                                                     link.get("activeAt"), notify):
                link["active"] = record_id
                link["activeAt"] = float(active_at or 0)
                adopt_meta(self._data, link, "activeRev", active_rev)
            state = record.setdefault("state", _empty_state())
            merged = merge_states(state, incoming)
            state.clear()
            state.update(merged)
            self._save()
            reply = json.loads(json.dumps(merged))
            reply.update({"record": record_id, "recordName": record.get("name") or DEFAULT_RECORD_NAME, "book": owner,
                          "movedAt": float(record.get("movedAt") or 0), **_revs(record, "movedRev"),
                          "records": [{"id": item,
                                       "name": self._data["records"][item].get("name") or DEFAULT_RECORD_NAME,
                                       "nameAt": float(self._data["records"][item].get("nameAt") or 0),
                                       "movedAt": float(self._data["records"][item].get("movedAt") or 0),
                                       **_revs(self._data["records"][item], "nameRev", "movedRev")}
                                      for item in link.get("records", []) if item in self._data["records"]],
                          "active": {"record": link.get("active"), "at": float(link.get("activeAt") or 0),
                                     **({"rev": link["activeRev"]} if "activeRev" in link else {})},
                          "deletedRecords": dict(self._data["deleted"])})
            if link.get("active") and link["active"] != record_id:
                active = self._data["records"].get(link["active"]) or {}
                reply["activeState"] = json.loads(json.dumps(active.get("state") or _empty_state()))
            return reply

    def sync_request(self, book: str, remote_book: str = "", record: str | None = None) -> dict[str, Any] | None:
        """Thân yêu cầu máy này gửi máy giữ sách (POST .../state; cùng khoá với Store.syncBody của điện thoại): state của MỘT
        hồ sơ kèm mã, tên + lúc đặt tên, lúc chọn (chỉ khi nó đang được chọn), lúc chuyển và bia mộ. `record`: hồ sơ nơi gọi đã
        chốt (trình phát đang phát nó); không nói thì hồ sơ đang dùng NGAY BÂY GIỜ - chốt ở đây, lời đáp về gộp đúng mã ấy
        (`merge_reply`) dù lúc đó người dùng đã đổi hồ sơ. Chưa có hồ sơ nào thì tạo "Mặc định" mang mã suy từ `remote_book`.
        Hồ sơ đã xoá / đã sang sách khác: None (không gửi)."""
        with self._changing():
            if record is None:
                link = self._data["links"].get(book) or {}
                if link.get("active") not in self._data["records"]:
                    self._active(book, default_for=remote_book or None)
                    self._save()
                record = self._data["links"][book]["active"]
            elif self._owner(record) != book or record not in self._data["records"]:
                return None
            link = self._data["links"][book]
            meta = self._data["records"][record]
            body = json.loads(json.dumps(meta.get("state") or _empty_state()))
            body.update({"record": record, "recordName": meta.get("name") or DEFAULT_RECORD_NAME,
                         "nameAt": float(meta.get("nameAt") or 0),
                         "activeAt": float(link.get("activeAt") or 0) if link.get("active") == record else 0.0,
                         "movedAt": float(meta.get("movedAt") or 0), "deletedRecords": dict(self._data["deleted"]),
                         **_revs(meta, "nameRev", "movedRev"), **(_revs(link, "activeRev") if link.get("active") == record else {})})
            return body

    def merge_reply(self, book: str, record: str, reply: dict[str, Any], *, remote_book: str = "",
                    resolve: Callable[[str], str | None] | None = None) -> bool:
        """Gộp lời đáp của máy giữ sách vào ĐÚNG hồ sơ `record` đã gửi (hợp đồng như Store.applySync của điện thoại), không phải hồ
        sơ đang dùng lúc lời đáp về: state, tên (đổi sau thắng), bia mộ (xoá theo), hồ sơ lạ của cuốn (nhận, state trống - lần
        gửi khi chọn nó mới tải về), hồ sơ đang chọn (bên chọn sau thắng, kèm `activeState`) và lần chuyển sách (`resolve` đổi mã sách
        của máy kia ra mã cuốn ảo ở đây; không đổi được thì hồ sơ ở nguyên chỗ). Hồ sơ đã bị xoá (ở đây hay ở máy kia): bỏ lời đáp,
        không rơi sang hồ sơ khác, không tạo hồ sơ mới. True: lời đáp đã được gộp."""
        require_peer_revisions(reply)
        named = reply.get("record")
        if isinstance(named, str) and named != record:
            return False  # lời đáp của hồ sơ khác: không phải của lần gửi này
        with self._changing():
            tombstones = dict(reply["deletedRecords"]) if isinstance(reply.get("deletedRecords"), dict) else {}
            if reply.get("deleted") is True:
                tombstones[record] = max(float(tombstones.get(record) or 0), time.time())
            for gone, at in tombstones.items():
                if isinstance(gone, str) and RECORD_ID.fullmatch(gone):
                    if gone in self._data["records"]:
                        self._unlink(gone)
                        del self._data["records"][gone]
                    self._data["deleted"][gone] = max(float(self._data["deleted"].get(gone) or 0), float(at or 0))
            if record in self._data["deleted"] or record not in self._data["records"]:
                self._save()
                return False
            entry = self._data["records"][record]
            incoming = {key: value for key, value in reply.items() if key not in SYNC_KEYS}
            state = entry.setdefault("state", _empty_state())
            merged = merge_states(state, incoming)
            state.clear()
            state.update(merged)
            # sách hồ sơ gắn ở máy kia: lần chuyển sau thắng
            notify = notices.NOTICES.add
            target = book if self._owner(record) == book else None
            remote_moved = float(reply.get("movedAt") or 0)
            moved_later = meta_newer(self._data, reply.get("movedRev"), remote_moved, entry.get("movedRev"), entry.get("movedAt"), notify)
            there = reply.get("book")
            if target is not None and isinstance(there, str) and there and there != remote_book and moved_later:
                destination = resolve(there) if resolve is not None else None
                if destination and destination != book:
                    self._unlink(record)
                    dest_link = self._data["links"].setdefault(destination, {"records": []})
                    dest_link["records"] = [*dest_link.get("records", []), record]
                    target = destination
                else:
                    target = None  # chuyển sang cuốn ta không có: giữ chỗ gắn ở đây, không trộn danh sách hồ sơ của hai cuốn
            if target is not None and moved_later:
                entry["movedAt"] = remote_moved
                adopt_meta(self._data, entry, "movedRev", reply.get("movedRev"))
            link = self._data["links"].get(target) if target is not None else None
            for item in reply.get("records") or []:
                if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not RECORD_ID.fullmatch(item["id"]):
                    continue
                if item["id"] in self._data["deleted"]:
                    continue
                known = self._data["records"].get(item["id"])
                if known is None:
                    if link is None:
                        continue
                    known = self._data["records"][item["id"]] = {"name": str(item.get("name") or DEFAULT_RECORD_NAME)[:MAX_RECORD_NAME],
                                                                  "createdAt": time.time(), "nameAt": 0.0, "state": _empty_state()}
                    link["records"] = [*link.get("records", []), item["id"]]
                at = float(item.get("nameAt") or 0)
                if str(item.get("name") or "").strip() and meta_newer(self._data, item.get("nameRev"), at, known.get("nameRev"),
                                                                      known.get("nameAt"), notify):
                    known["name"] = str(item["name"]).strip()[:MAX_RECORD_NAME]
                    known["nameAt"] = at
                    adopt_meta(self._data, known, "nameRev", item.get("nameRev"))
                if (link is not None and item["id"] in link.get("records", [])
                        and meta_newer(self._data, item.get("movedRev"), item.get("movedAt"), known.get("movedRev"), known.get("movedAt"), notify)):
                    known["movedAt"] = float(item.get("movedAt") or 0)
                    adopt_meta(self._data, known, "movedRev", item.get("movedRev"))
            active = reply.get("active")
            chosen = active.get("record") if isinstance(active, dict) else None
            if (link is not None and isinstance(chosen, str) and chosen in link.get("records", [])
                    and meta_newer(self._data, active.get("rev"), active.get("at"), link.get("activeRev"), link.get("activeAt"), notify)):
                link["active"] = chosen
                link["activeAt"] = float(active.get("at") or 0)
                adopt_meta(self._data, link, "activeRev", active.get("rev"))
                if chosen != record and isinstance(reply.get("activeState"), dict):
                    other = self._data["records"][chosen].setdefault("state", _empty_state())
                    merged_other = merge_states(other, {key: value for key, value in reply["activeState"].items()
                                                         if key not in SYNC_KEYS})
                    other.clear()
                    other.update(merged_other)
            self._save()
            return True

    def _save(self) -> None:
        if self._unread or self._journal_unread:
            raise notices.Unreadable("Chưa đọc được hồ sơ nghe. Bạn hãy thử lại.")
        atomic_write_json(self.path, self._data, compact=True)  # nguyên tử + fsync: mất điện không để lại file rỗng
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
    finished = {"at": state.get("finishedAt", 0), "rev": state.get("_fieldRevs", {}).get("finished")}
    if state.get("finished") and not newer(last, finished):
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
    from .listening_schema import number
    theirs = checked_peer(ours, theirs, notices.NOTICES.add)
    result = json.loads(json.dumps(ours))
    result.setdefault("chapters", {})
    if theirs.get("last") and newer(theirs["last"], result.get("last")):
        result["last"] = theirs["last"]
    if theirs.get("reading") and newer(theirs["reading"], result.get("reading")):
        result["reading"] = theirs["reading"]
    for key, record in (theirs.get("chapters") or {}).items():
        mine = result["chapters"].get(key)
        if newer(record, mine):
            result["chapters"][key] = record
    for field, stamp in (("rate", "rateAt"), ("finished", "finishedAt"), ("voice", "voiceAt")):
        their_stamp = {"at": theirs.get(stamp, 0), "rev": theirs.get("_fieldRevs", {}).get(field)}
        my_stamp = {"at": result.get(stamp, 0), "rev": result.get("_fieldRevs", {}).get(field)}
        if field in theirs and newer(their_stamp, my_stamp):
            result[field] = theirs[field]
            # Mốc giờ chỉ còn cho máy đời trước; máy kia thiếu / hỏng mốc thì không văng lỗi ở mọi lần đồng bộ (soát a118 lỗi 3).
            if number(theirs.get(stamp)):
                result[stamp] = theirs[stamp]
            else:
                result.pop(stamp, None)
            if their_stamp["rev"]:
                result.setdefault("_fieldRevs", {})[field] = their_stamp["rev"]
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
    result["_clock"] = clock(result)
    if era := epoch(result):
        result["_epoch"] = era
    return result
