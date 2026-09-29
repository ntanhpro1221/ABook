"""Đồng bộ sách sang điện thoại qua Wi-Fi: tìm máy, ghép nối, tải gói sách, đồng bộ chỗ đang nghe.

Tách hẳn khỏi server giao diện (chỉ nghe 127.0.0.1): server này nghe trên mạng LAN nên chỉ mở đúng các đường
đồng bộ, mọi yêu cầu (trừ ghép nối) phải mang mã thiết bị, và chỉ chạy khi người dùng bật "Cho phép điện thoại kết
nối" trong Cài đặt. Không dùng thư viện ngoài (zeroconf...): thêm gói Python là đổi `uv.lock`, tức đổi hash chất
lượng của dây chuyền giữa cuốn sách. Tìm máy bằng UDP broadcast, thư viện chuẩn là đủ.

Gói sách (`book.json`) cùng hình dạng với phía Nghe trên máy tính (listen_view.py), cộng đường dẫn file:

    chapters/<tên>.mp3      audio chương
    scripts/<chapterId>.json  văn bản + mốc thời gian để đọc theo
    cast.json               dàn nhân vật
    samples/<segmentId>.wav   câu mẫu của từng nhân vật
    cover.jpg               ảnh bìa thật, chỉ khi người dùng đã đặt (webui/covers.py)

Điều khiển từ xa (`Remote`): điện thoại đang có sách trên trình phát thì báo "đang phát gì" lên đây, máy tính thấy và
gửi lệnh phát/dừng/tua ngược lại - kể cả chuyển chỗ nghe giữa hai máy. Chiều ngược lại (mạng trạm bước 4): trình phát
trong giao diện CHÍNH máy này báo lên host cùng kiểu (`LOCAL_PLAYER`), và máy đã ghép - điện thoại, máy tính khác - xem
và điều khiển nó qua `GET/POST /sync/v1/player`. Điện thoại chia sẻ thư viện trả lời đúng đường ấy (LibraryServer.kt),
nên bên điều khiển không cần biết đầu kia là gì.

Studio từ xa (remote_studio.py): mọi đường ngoài `/sync/` - giao diện web và API của nó - chỉ mở khi người dùng bật công
tắc riêng, cho thiết bị đã ghép, theo danh sách trắng.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import socket
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import unquote, urlsplit

from . import covers, listen_view, remote_studio, store
from .fingerprints import Fingerprints
from .library import Library, book_id
from .listening import RECORD_ID, SYNC_KEYS, Listening
from .remote_studio import StudioGate

SYNC_PORT = 47630
DISCOVERY_PORT = 47631
DISCOVERY_PROBE = b"EBOOKREADER_DISCOVER"
PAIRING_SECONDS = 300
PAIRING_ATTEMPTS = 5
CHUNK = 256 * 1024
MAX_BODY = 2 * 1024 * 1024
REMOTE_WAIT_SECONDS = 25  # trần của một lần "hỏi dài"; điện thoại đặt thời gian chờ đọc dài hơn thế
PRESENCE_SECONDS = 40  # quá ngần này không nghe tin (hỏi dài chỉ kéo 25 giây) là điện thoại đã đi
COMMAND_SECONDS = 15  # lệnh chưa tới tay điện thoại sau ngần này thì bỏ: "dừng" tới trễ hai phút là một cú giật mình
# Lệnh đã giao mà chưa thấy kết quả (`acks`) sau ngần này thì giao lại: lần trả lời trước có thể đã rơi (mạng / Bluetooth
# đứt giữa lúc hỏi dài - máy chủ không biết, lần hỏi mồ côi vẫn nhận lệnh). Máy nhận bỏ qua lệnh trùng mã.
REDELIVER_SECONDS = 5
REMOTE_ACTIONS = frozenset({"play", "pause", "toggle", "skip", "seek", "next", "previous", "jump", "rate", "load"})
# Mã sách: library.book_id (24 hex), hay mã kiểu cũ của điện thoại chưa đổi khoá (đường dẫn base64, tới ~700 ký tự).
BOOK_ID = re.compile(r"[A-Za-z0-9_-]{1,700}")
LOCAL_PLAYER = "local"  # trình phát trong giao diện của chính máy này, một "thiết bị" của Remote riêng
PLAYER_STATE = ("bookId", "bookTitle", "chapterId", "chapterTitle", "position", "duration", "playing", "buffering", "rate")


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _number(value: Any, low: float, high: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return low
    return min(high, max(low, number)) if number == number else low  # NaN != NaN


def _text(value: Any, limit: int = 200) -> str:
    return value[:limit] if isinstance(value, str) else ""


def _presence(report: dict[str, Any]) -> dict[str, Any]:
    """Trạng thái điện thoại gửi lên, chỉ giữ đúng các trường biết, đúng kiểu, có trần: đây là dữ liệu từ mạng LAN."""
    state = report.get("state") if isinstance(report.get("state"), dict) else {}
    book = _text(state.get("bookId"), 700)
    chapter = state.get("chapterId")
    books = report.get("books") if isinstance(report.get("books"), list) else []
    acks = report.get("acks") if isinstance(report.get("acks"), list) else []
    return {
        "bookId": book if BOOK_ID.fullmatch(book) else "",
        "bookTitle": _text(state.get("bookTitle")),
        "chapterId": chapter if isinstance(chapter, int) and not isinstance(chapter, bool) else None,
        "chapterTitle": _text(state.get("chapterTitle")),
        "position": _number(state.get("position"), 0.0, 86_400.0),
        "duration": _number(state.get("duration"), 0.0, 86_400.0),
        "playing": state.get("playing") is True,
        "buffering": state.get("buffering") is True,
        "rate": _number(state.get("rate"), 0.5, 3.0),
        "books": [item for item in books[:500] if isinstance(item, str) and BOOK_ID.fullmatch(item)],
        # Điện thoại nghe thẳng được mọi cuốn của máy tính (stream play), không chỉ cuốn đã tải.
        "stream": report.get("stream") is True,
        "acks": [{"id": _text(ack.get("id"), 24), "ok": ack.get("ok") is True, "message": _text(ack.get("message"))}
                 for ack in acks[:10] if isinstance(ack, dict)],
    }


def remote_command(body: dict[str, Any]) -> dict[str, Any]:
    """Lệnh máy tính gửi điện thoại, kiểm và rút gọn: chỉ lệnh biết, đúng kiểu, mới đi qua mạng."""
    action = body.get("action")
    if action not in REMOTE_ACTIONS:
        raise ValueError("Lệnh không hỗ trợ")
    command: dict[str, Any] = {"action": action}
    if action in ("skip", "seek", "jump", "load"):
        command["seconds"] = _number(body.get("seconds"), -3600.0 if action == "skip" else 0.0, 86_400.0)
    if action in ("jump", "load"):
        chapter = body.get("chapterId")
        if not isinstance(chapter, int) or isinstance(chapter, bool):
            raise ValueError("Thiếu chương")
        command["chapterId"] = chapter
    if action == "load":
        book = _text(body.get("bookId"), 700)
        if not BOOK_ID.fullmatch(book):
            raise ValueError("Thiếu sách")
        command["bookId"] = book
    if action == "rate":
        command["rate"] = _number(body.get("rate"), 0.5, 3.0)
    return command


class Remote:
    """Điều khiển điện thoại đang phát từ máy tính - kiểu Spotify Connect, gói trong mạng nhà (PLAYER_RESEARCH #12).

    Điện thoại không mở cổng nào (máy chủ vẫn chỉ là máy tính), nên lệnh đi theo lối "hỏi dài": khi có sách trên trình
    phát, điện thoại gửi trạng thái lên `/sync/v1/remote` và để yêu cầu treo tới `wait` giây; có lệnh là máy tính trả
    lời NGAY, nên bấm "dừng" trên máy tính thì điện thoại dừng sau một lượt mạng chứ không đợi tới nhịp hỏi sau. Điện
    thoại đổi trạng thái (phát, dừng, tua, sang chương) thì gửi thêm một lần `wait=0` để máy tính thấy liền.

    Lệnh ở lại tới khi máy nhận báo kết quả (`acks` - nó gửi lại 20 giây) hay quá COMMAND_SECONDS: lần báo nào của nó
    cũng nhận được lệnh chưa giao, còn lệnh đã giao mà REDELIVER_SECONDS chưa thấy kết quả thì giao lại - kết nối đứt giữa
    lúc hỏi dài không làm rơi lệnh. Máy nhận làm mỗi mã lệnh một lần.
    """

    def __init__(self) -> None:
        self._changed = threading.Condition()
        self._presence: dict[str, dict[str, Any]] = {}
        self._commands: dict[str, list[dict[str, Any]]] = {}
        self._generation = 0

    def report(self, device: str, name: str, report: dict[str, Any], wait: Any = 0.0) -> list[dict[str, Any]]:
        """Ghi trạng thái của một điện thoại, trả các lệnh cần giao cho nó (chờ tối đa `wait` giây nếu chưa có)."""
        deadline = time.time() + _number(wait, 0.0, REMOTE_WAIT_SECONDS)
        presence = _presence(report)
        with self._changed:
            generation = self._generation
            self._presence[device] = {**presence, "device": device, "name": name, "at": time.time()}
            done = {ack["id"] for ack in presence["acks"]}
            if done and device in self._commands:
                self._commands[device] = [command for command in self._commands[device] if command["id"] not in done]
            due: list[dict[str, Any]] = []
            while self._generation == generation:
                due, retry_in = self._due(device)
                left = deadline - time.time()
                if due or left <= 0:
                    break
                self._changed.wait(left if retry_in is None else min(left, retry_in))
            now = time.time()
            for command in due:
                command["delivered"] = now
            return [{key: value for key, value in command.items() if key != "delivered"} for command in due]

    def _due(self, device: str) -> tuple[list[dict[str, Any]], float | None]:
        """Lệnh cần giao ngay (chưa giao, hay giao đã lâu mà chưa thấy kết quả), và bao lâu nữa thì có lệnh cần giao lại."""
        now = time.time()
        fresh = [command for command in self._commands.get(device, []) if now - command["at"] <= COMMAND_SECONDS]
        if fresh:
            self._commands[device] = fresh
        else:
            self._commands.pop(device, None)
        due = [command for command in fresh
               if command.get("delivered") is None or now - command["delivered"] >= REDELIVER_SECONDS]
        waits = [REDELIVER_SECONDS - (now - command["delivered"]) for command in fresh
                 if command.get("delivered") is not None and now - command["delivered"] < REDELIVER_SECONDS]
        return due, (max(0.05, min(waits)) if waits else None)

    def send(self, device: str, command: dict[str, Any]) -> dict[str, Any]:
        """Xếp một lệnh cho điện thoại. `LookupError` nếu nó không còn ở đó: lệnh gửi vào khoảng không thì người dùng
        phải được biết, chứ không được tưởng là điện thoại đã dừng."""
        with self._changed:
            seen = self._presence.get(device)
            if seen is None or time.time() - seen["at"] > PRESENCE_SECONDS:
                raise LookupError(device)
            entry = {**command, "id": secrets.token_hex(6), "at": time.time()}
            self._commands.setdefault(device, []).append(entry)
            self._changed.notify_all()
            return entry

    def view(self) -> list[dict[str, Any]]:
        """Các điện thoại đang có mặt, mới nhất trước; `age` = số giây kể từ lần báo cuối (để nội suy vị trí)."""
        now = time.time()
        with self._changed:
            phones = [{**entry, "age": round(now - entry["at"], 2)} for entry in self._presence.values()
                      if now - entry["at"] <= PRESENCE_SECONDS]
        return sorted(phones, key=lambda entry: entry["age"])

    def forget(self, device: str) -> None:
        """Gỡ ghép một điện thoại: nó không còn được thấy, lệnh chờ nó bỏ hết."""
        with self._changed:
            self._presence.pop(device, None)
            self._commands.pop(device, None)
            self._changed.notify_all()

    def reset(self) -> None:
        """Tắt đồng bộ: trả lời ngay mọi lần hỏi đang treo, quên hết."""
        with self._changed:
            self._generation += 1
            self._presence.clear()
            self._commands.clear()
            self._changed.notify_all()


class ExclusiveHTTPServer(ThreadingHTTPServer):
    """Máy chủ HTTP giữ cổng cho riêng mình.

    `HTTPServer` bật SO_REUSEADDR, mà trên Windows cờ ấy nghĩa là "cho phép bind đè lên cổng đang có người nghe":
    một tiến trình khác sẽ lặng lẽ nhận một phần kết nối (của điện thoại, hoặc của chính giao diện - kèm mã phiên),
    và cổng bận thật thì ta cũng không biết. SO_EXCLUSIVEADDRUSE chặn cả hai.
    """

    daemon_threads = True
    allow_reuse_address = os.name != "nt"

    def server_bind(self) -> None:
        if os.name == "nt":
            self.socket.setsockopt(socket.SOL_SOCKET, getattr(socket, "SO_EXCLUSIVEADDRUSE", -5), 1)
        super().server_bind()


class Devices:
    """Điện thoại đã ghép nối: lưu băm của mã (không lưu mã thật), tên, lần thấy cuối.

    Mã ghép nối chỉ có khi người dùng bấm "Ghép điện thoại" trên máy tính: 6 số, dùng một lần, sống 5 phút. Một
    triệu khả năng thì máy khác trong mạng đoán mò được trong vài phút, nên sai `PAIRING_ATTEMPTS` lần là mã bị
    huỷ và KHÔNG tự sinh lại - người dùng thấy lý do và chủ động tạo mã mới.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()
        try:
            self._data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self._data = {"devices": {}}
        self._pairing: tuple[str, float] | None = None
        self._failures = 0
        self.blocked = False

    def start_pairing(self) -> dict[str, Any]:
        with self._lock:
            self._pairing = (f"{secrets.randbelow(10**6):06d}", time.time() + PAIRING_SECONDS)
            self._failures = 0
            self.blocked = False
            return {"code": self._pairing[0], "expiresAt": self._pairing[1]}

    def cancel_pairing(self) -> None:
        with self._lock:
            self._pairing = None
            self._failures = 0
            self.blocked = False

    def pairing(self) -> dict[str, Any] | None:
        with self._lock:
            if self._pairing is None or self._pairing[1] <= time.time():
                return None
            return {"code": self._pairing[0], "expiresAt": self._pairing[1]}

    def pair(self, code: str, name: str, studio: bool = False) -> str | None:
        """`studio`: thiết bị được điều khiển sản xuất (Studio từ xa) - theo TỪNG thiết bị, không theo công tắc chung:
        điện thoại ghép từ trước chỉ để nghe không tự có quyền ấy khi người dùng bật Studio từ xa (soát 28-09)."""
        digits = re.sub(r"[^0-9]", "", code)[:12]  # "482 913" cũng được; compare_digest không nhận chữ ngoài ASCII
        with self._lock:
            if not self._pairing or self._pairing[1] <= time.time():
                return None
            if not secrets.compare_digest(digits, self._pairing[0]):
                self._failures += 1
                if self._failures >= PAIRING_ATTEMPTS:
                    self._pairing = None
                    self.blocked = True
                return None
            self._pairing = None  # mã dùng một lần
            token = secrets.token_urlsafe(32)
            self._data["devices"][_hash(token)] = {"name": name.strip()[:80] or "Điện thoại",
                                                   "pairedAt": time.time(), "lastSeen": time.time(),
                                                   "studio": bool(studio)}
            self._save()
            return token

    def check(self, token: str) -> bool:
        return self.identify(token) is not None

    def identify(self, token: str) -> dict[str, Any] | None:
        """Thiết bị mang mã này: `{"id", "name", "studio"}` (id là 12 ký tự đầu của băm, như trong danh sách)."""
        key = _hash(token)
        with self._lock:
            device = self._data["devices"].get(key)
            if device is None:
                return None
            if time.time() - device.get("lastSeen", 0) > 60:
                device["lastSeen"] = time.time()
                self._save()
            return {"id": key[:12], "name": str(device.get("name") or "Điện thoại"),
                    "studio": bool(device.get("studio"))}

    def set_studio(self, short_id: str, enabled: bool) -> bool:
        """Cho / thôi cho một thiết bị điều khiển sản xuất. False: không có thiết bị này."""
        with self._lock:
            found = [value for key, value in self._data["devices"].items() if key[:12] == short_id]
            for device in found:
                device["studio"] = bool(enabled)
            if found:
                self._save()
            return bool(found)

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            return [{"id": key[:12], **value} for key, value in self._data["devices"].items()]

    def revoke(self, short_id: str) -> None:
        with self._lock:
            self._data["devices"] = {key: value for key, value in self._data["devices"].items() if key[:12] != short_id}
            self._save()

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self._data, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(temporary, self.path)


def manifest(project_root: Path, book: str, listening: Listening) -> dict[str, Any]:
    """`book.json` của một cuốn: chỉ các chương ĐÃ nghe được, kèm tên file để điện thoại tải về."""
    summary = store.summarize(project_root)
    summary["id"] = book
    view = listen_view.book(project_root, book, summary, listening.get(book))
    chapters = []
    for chapter in view.get("chapters", []):
        path = store.chapter_audio_path(project_root, chapter["id"]) if chapter["available"] else None
        chapters.append({
            **chapter,
            "available": path is not None,
            "file": f"chapters/{path.name}" if path else None,
            "size": path.stat().st_size if path else 0,
            "script": f"scripts/{chapter['id']}.json",
        })
    cast = store.cast(project_root)
    samples = sorted({person["sampleId"] for person in cast["characters"] + cast["extras"] if person.get("sampleId")})
    cover = covers.cover_meta(project_root)
    # Đổi ảnh bìa cũng là một phiên bản mới của gói: điện thoại thấy "có cập nhật" và tải lại bìa.
    version = hashlib.sha256(json.dumps([[(c["id"], c["size"]) for c in chapters],
                                         cover["version"] if cover else 0]).encode()).hexdigest()[:16]
    return {
        "format": listen_view.FORMAT,
        "id": book,
        "title": view["title"],
        "narrator": view["narrator"],
        "duration": view["duration"],
        "chaptersTotal": view["chaptersTotal"],
        "chaptersAvailable": sum(1 for chapter in chapters if chapter["available"]),
        "complete": view["complete"],
        "version": version,
        "chapters": chapters,
        "cast": "cast.json",
        "samples": [f"samples/{sample}.wav" for sample in samples],
        "cover": {**cover, "file": covers.COVER_FILE} if cover else None,
    }


class SyncApp:
    def __init__(self, library: Library, listening: Listening, devices: Devices, name: str,
                 remote: Remote | None = None, fingerprints: Fingerprints | None = None,
                 studio: StudioGate | None = None, player: Remote | None = None,
                 routes: Callable[[], dict[str, Any]] | None = None) -> None:
        self.library = library
        self.listening = listening
        self.devices = devices
        self.name = name
        self.remote = remote or Remote()
        self.player = player or Remote()  # trình phát của chính máy này (giao diện báo lên host, webui/server.py)
        self.fingerprints = fingerprints or Fingerprints(listening.path.with_name("fingerprints.json"))
        self.studio = studio  # None: cổng chỉ đồng bộ (test, máy không có giao diện)
        # Các đường tới máy này, gửi kèm lời đáp ghép: điện thoại ghép qua Wi-Fi biết đường Bluetooth dự phòng, ghép qua
        # Bluetooth biết địa chỉ Wi-Fi để dùng khi cùng mạng (tự chọn đường, feat/auto-route).
        self.routes = routes or (lambda: {})
        # Số "việc cần anh" của mỗi dự án, tính lại chỉ khi sách đổi (studio_view): điện thoại hỏi mỗi 15 phút.
        self._work: dict[str, tuple[tuple[float, ...], int]] = {}  # đường dẫn -> (dấu thời gian, số việc)
        self._work_lock = threading.Lock()

    def book(self, value: str) -> Path | None:
        return self.library.resolve(value)

    def player_view(self) -> dict[str, Any]:
        """Trình phát của máy này cho máy đã ghép: cùng hình dạng thân báo của điện thoại (`state`, `books`, `stream`,
        `acks`), nên bên điều khiển đọc bằng đúng `_presence`. `age`: số giây từ lần giao diện báo cuối - bên kia nội suy
        vị trí như máy tính làm với điện thoại. Giao diện không mở (không ai báo trong 40 giây): `state` rỗng."""
        seen = next((entry for entry in self.player.view() if entry["device"] == LOCAL_PLAYER), None)
        return {"name": self.name, "kind": "computer", "stream": True, "books": [],
                "state": {key: seen[key] for key in PLAYER_STATE} if seen else None,
                "acks": seen["acks"] if seen else [], "age": seen["age"] if seen else 0.0}

    def studio_view(self) -> list[dict[str, Any]]:
        """Trạng thái sản xuất gọn cho điện thoại: mỗi dự án Studio một dòng - giai đoạn, còn chạy không, số chương xong,
        số "việc cần anh", lỗi cuối. Điện thoại tự so với lần hỏi trước để báo "sách xong", "có việc mới cần anh", "dừng vì
        lỗi" (StudioAlerts.kt); máy tính không phải nhớ gì cho từng điện thoại.

        Đang chạy hay không đọc từ nhịp tim của worker trong DB (`store.summarize`), không từ bộ chạy của cửa sổ app - cổng
        đồng bộ không có bộ chạy, và sách chạy bằng dòng lệnh cũng phải được báo."""
        from .work_items import work_items

        def stamp_of(path: Path) -> tuple[float, ...]:
            stamps = [store.touched(path)]
            for name in ("overrides.json", "doubt.json"):
                try:
                    stamps.append((path / name).stat().st_mtime)
                except OSError:
                    stamps.append(0.0)
            return tuple(stamps)

        def work_of(path: Path) -> int | None:
            # Không đếm được (sách đời cũ, DB đang khoá) thì None - điện thoại coi là "không biết", không báo gì.
            stamp = stamp_of(path)
            with self._work_lock:
                cached = self._work.get(str(path))
            if cached is not None and cached[0] == stamp:
                return cached[1]
            try:
                count = len(work_items(path)["items"])
            except Exception:  # noqa: BLE001
                return None
            with self._work_lock:
                self._work[str(path)] = (stamp, count)
            return count

        books = []
        for path in self.library.projects():
            try:
                summary = self.library.summary(path, running=False)
            except Exception:  # noqa: BLE001 - một sách hỏng không được làm mất cả danh sách
                continue
            work = work_of(path)
            chapters = summary.get("chapters") or {}
            books.append({
                "id": summary["id"],
                "title": str(summary.get("title") or path.name),
                "phase": str(summary.get("phase") or ""),
                "statusLabel": str(summary.get("statusLabel") or ""),
                "running": bool(summary.get("running")),
                "chapters": {"completed": int(chapters.get("completed") or 0), "total": int(chapters.get("total") or 0)},
                "work": work,
                "lastError": str(summary.get("lastError") or "")[:300],
                "updatedAt": summary.get("updatedAt"),
            })
        return books

    def match(self, books: Any) -> dict[str, str]:
        """Cuốn điện thoại mở từ file là cuốn nào của máy này (mã máy này), so bằng audio từng chương - sách không mang
        mã nào (fingerprints.py). `books`: [{"key": mã phía điện thoại, "chapters": {"chapters/x.mp3": {size, sha256}}}].
        Khoá là mã sách kiểu cũ của chính máy này (cuốn điện thoại tải từ bản cũ, docs/BOOK_IDS.md): trả thẳng mã hiện
        hành để điện thoại đổi khoá cuốn ấy - không cần audio."""
        found: dict[str, str] = {}
        if not isinstance(books, list):
            return found
        projects = list(self.library.projects())
        for item in books[:200]:
            if not isinstance(item, dict) or not isinstance(item.get("key"), str):
                continue
            own = self.library.resolve(item["key"])
            if own is not None:
                found[item["key"]] = book_id(own)
                continue
            if not isinstance(item.get("chapters"), dict):
                continue
            for path in projects:
                if self.fingerprints.shares_a_chapter(path, item["chapters"]):
                    found[item["key"]] = book_id(path)
                    break
        return found

    def library_view(self) -> list[dict[str, Any]]:
        out = []
        for path in self.library.projects():
            try:
                summary = store.summarize(path)
            except Exception:  # noqa: BLE001 - sách hỏng không làm hỏng danh sách
                continue
            if summary["chapters"]["completed"] <= 0:
                continue
            identifier = book_id(path)
            summary["id"] = identifier
            view = listen_view.book(path, identifier, summary, self.listening.get(identifier), with_chapters=False)
            entry = {key: view[key] for key in ("id", "title", "narrator", "duration", "chaptersTotal",
                                                 "chaptersAvailable", "complete", "updatedAt")}
            meta = covers.cover_meta(path)
            entry["cover"] = {"color": meta["color"], "version": meta["version"]} if meta else None
            out.append(entry)
        return out

    def resolve_file(self, project_root: Path, relative: str) -> Path | bytes | None:
        """Đường dẫn file của gói (chỉ các tên trong manifest; không đi ra ngoài thư mục sách)."""
        if relative == "cast.json":
            return json.dumps(store.cast(project_root), ensure_ascii=False).encode("utf-8")
        if relative == covers.COVER_FILE:
            return covers.cover_file(project_root)
        match = re.fullmatch(r"scripts/(\d+)\.json", relative)
        if match:
            script = store.chapter_script(project_root, int(match.group(1)))
            return json.dumps(script, ensure_ascii=False).encode("utf-8") if script else None
        match = re.fullmatch(r"samples/(\d+)\.wav", relative)
        if match:
            cast = store.cast(project_root)
            allowed = {person.get("sampleId") for person in cast["characters"] + cast["extras"]}
            return store.sample_audio_path(project_root, int(match.group(1))) if int(match.group(1)) in allowed else None
        match = re.fullmatch(r"chapters/([^/\\]+\.mp3)", relative)
        if match:
            for chapter in store.chapters(project_root):
                path = store.chapter_audio_path(project_root, chapter["id"]) if chapter["playable"] else None
                if path is not None and path.name == match.group(1):
                    return path
        return None


class SyncHandler(BaseHTTPRequestHandler):
    server_version = "EbookReaderSync"
    protocol_version = "HTTP/1.1"
    # Một kết nối im lặng quá lâu (gửi dở thân, giữ kết nối) bị cắt; "hỏi dài" của điện thoại chờ tối đa 25 giây.
    timeout = 60
    app: SyncApp

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        return

    def _json(self, status: int, payload: Any) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":  # HEAD mà có thân thì lệch luồng keep-alive, yêu cầu kế tiếp đọc nhầm
            self.wfile.write(body)

    def _body(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = -1
        if length < 0 or length > MAX_BODY:
            # Âm thì `rfile.read(-1)` đọc tới hết kết nối - vượt mọi trần, không cần ghép nối (soát 28-09).
            self.close_connection = True
            return {}
        try:
            data = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
        except (ValueError, UnicodeDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def _device(self, *, cookie: bool = False) -> dict[str, Any] | None:
        header = self.headers.get("Authorization") or ""
        if header.startswith("Bearer "):
            return self.app.devices.identify(header[7:].strip())
        if not cookie:
            return None  # các đường /sync/v1 là của app điện thoại: chỉ mã thiết bị tường minh, không cookie tự gửi kèm
        # Trình duyệt (Studio từ xa) mang mã thiết bị trong cookie HttpOnly - cùng mã, cùng danh sách thiết bị.
        token = remote_studio.cookie_token(self.headers.get("Cookie"))
        return self.app.devices.identify(token) if token else None

    def _studio(self, method: str, path: str) -> None:
        """Mọi đường ngoài `/sync/`: giao diện web và API của nó (remote_studio.py). Thiết bị đã ghép luôn NGHE được (như
        app điện thoại qua /sync/v1); điều khiển sản xuất cần cả công tắc chung lẫn quyền của thiết bị."""
        studio = self.app.studio
        if not remote_studio.allowed_host(self.headers.get("Host")):
            self._json(HTTPStatus.FORBIDDEN, {"error": "Host không hợp lệ"})
            return
        if studio is None:
            if path.startswith(("/api/", "/media/")):
                self._json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "Giao diện ABook của máy tính chưa mở"})
            else:
                remote_studio.send_page(self, HTTPStatus.SERVICE_UNAVAILABLE, remote_studio.closed_page(self.app.name))
            return
        device = self._device(cookie=True)
        producing = device is not None and studio.allowed() and bool(device.get("studio"))
        if path.startswith(("/api/", "/media/")):
            if device is None:
                self._json(HTTPStatus.UNAUTHORIZED, {"error": "Thiết bị chưa ghép nối"})
            elif not remote_studio.permitted(method, path):
                self._json(HTTPStatus.FORBIDDEN, {"error": "Việc này chỉ làm được trên chính máy tính"})
            elif not remote_studio.permitted(method, path, producing=producing):
                reason = ("Máy tính chưa cho phép điều khiển sản xuất từ xa" if not studio.allowed()
                          else "Thiết bị này chưa được phép điều khiển sản xuất")
                self._json(HTTPStatus.FORBIDDEN, {"error": f"{reason} - thiết bị này chỉ nghe sách được"})
            elif method not in ("GET", "HEAD") and not remote_studio.same_origin(self.headers):
                self._json(HTTPStatus.FORBIDDEN, {"error": "Yêu cầu không đến từ trang Studio"})
            else:
                remote_studio.forward(self, method, self.path, studio, listen_only=not producing)
            return
        if method not in ("GET", "HEAD"):
            self._json(HTTPStatus.METHOD_NOT_ALLOWED, {"error": "Không hỗ trợ"})
        elif device is None:
            remote_studio.send_page(self, HTTPStatus.OK, remote_studio.pairing_page(self.app.name))
        else:
            remote_studio.serve_static(self, studio.static_dir, path)

    def _file(self, path: Path) -> None:
        size = path.stat().st_size
        start, end, status = 0, size - 1, HTTPStatus.OK
        match = re.match(r"bytes=(\d*)-(\d*)$", self.headers.get("Range") or "")
        if match and size:
            first, last = match.groups()
            if first:
                start = int(first)
                end = min(int(last), size - 1) if last else size - 1
            elif last:
                start = max(0, size - int(last))
            if start > end:
                self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                self.send_header("Content-Range", f"bytes */{size}")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            status = HTTPStatus.PARTIAL_CONTENT
        self.send_response(status)
        self.send_header("Content-Type", "audio/mpeg" if path.suffix == ".mp3" else "audio/wav")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        if status == HTTPStatus.PARTIAL_CONTENT:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        with path.open("rb") as handle:
            handle.seek(start)
            remaining = end - start + 1
            while remaining > 0:
                chunk = handle.read(min(CHUNK, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

    def _route(self, method: str) -> None:
        path = urlsplit(self.path).path
        try:
            if not path.startswith("/sync/"):
                self._studio(method, path)
                return
            if method == "POST" and path == "/sync/v1/pair":
                body = self._body()
                # Ghép lúc người dùng ĐANG bật Studio từ xa: họ ghép thiết bị này để điều khiển - cho luôn quyền ấy.
                studio_on = self.app.studio is not None and self.app.studio.allowed()
                token = self.app.devices.pair(str(body.get("code", "")), str(body.get("device", "")), studio=studio_on)
                if token is None:
                    self._json(HTTPStatus.FORBIDDEN, {"error": "Mã ghép nối sai hoặc đã hết hạn"})
                else:
                    self._json(HTTPStatus.OK, {"token": token, "name": self.app.name, "routes": self.app.routes()})
                return
            if method == "POST" and path == "/sync/v1/pair-browser":
                # Trang ghép của Studio từ xa: cùng mã 6 số, nhưng mã thiết bị về cookie HttpOnly thay vì về tay trang.
                if not remote_studio.allowed_host(self.headers.get("Host")):
                    self._json(HTTPStatus.FORBIDDEN, {"error": "Host không hợp lệ"})
                    return
                if self.app.studio is None:
                    self._json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "Giao diện ABook của máy tính chưa mở"})
                    return
                # Ghép để NGHE luôn được (cùng mã 6 số người dùng vừa bấm trên máy tính); quyền sản xuất chỉ khi công tắc
                # đang bật - như ghép điện thoại.
                body = self._body()
                token = self.app.devices.pair(str(body.get("code", "")), str(body.get("device", "")) or "Trình duyệt",
                                              studio=self.app.studio.allowed())
                if token is None:
                    self._json(HTTPStatus.FORBIDDEN, {"error": "Mã ghép nối sai hoặc đã hết hạn"})
                else:
                    remote_studio.send_bytes(self, HTTPStatus.OK, json.dumps({"name": self.app.name}).encode("utf-8"),
                                             "application/json; charset=utf-8",
                                             extra={"Set-Cookie": remote_studio.device_cookie(token)})
                return
            device = self._device()
            if device is None:
                self._json(HTTPStatus.UNAUTHORIZED, {"error": "Thiết bị chưa ghép nối"})
                return
            if method == "POST" and path == "/sync/v1/remote":
                body = self._body()
                commands = self.app.remote.report(device["id"], device["name"], body, body.get("wait", 0))
                self._json(HTTPStatus.OK, {"commands": [{key: value for key, value in command.items() if key != "at"}
                                                        for command in commands]})
                return
            if path == "/sync/v1/player":
                # Máy đã ghép xem / điều khiển trình phát của máy này (mạng trạm bước 4). Lệnh xếp cho giao diện, giao
                # diện làm rồi báo kết quả trong `acks` của lần xem sau - như điện thoại với máy tính.
                if method == "GET":
                    self._json(HTTPStatus.OK, self.app.player_view())
                elif method == "POST":
                    try:
                        entry = self.app.player.send(LOCAL_PLAYER, remote_command(self._body()))
                    except ValueError as error:
                        self._json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
                    except LookupError:
                        self._json(HTTPStatus.CONFLICT, {"error": f"{self.app.name} chưa mở ABook - không có trình phát"})
                    else:
                        self._json(HTTPStatus.OK, {"id": entry["id"]})
                else:
                    self._json(HTTPStatus.METHOD_NOT_ALLOWED, {"error": "Không hỗ trợ"})
                return
            if method == "GET" and path == "/sync/v1/studio":
                # Thông báo sản xuất trên điện thoại: thông tin của Studio, nên cùng hai điều kiện với Studio từ xa - công
                # tắc trên máy tính bật, và thiết bị này được phép điều khiển sản xuất.
                if self.app.studio is None or not self.app.studio.allowed():
                    self._json(HTTPStatus.FORBIDDEN, {"error": "Máy tính chưa cho phép điều khiển từ xa"})
                elif not device.get("studio"):
                    self._json(HTTPStatus.FORBIDDEN, {"error": "Thiết bị này chưa được phép điều khiển sản xuất"})
                else:
                    self._json(HTTPStatus.OK, {"name": self.app.name, "at": time.time(), "books": self.app.studio_view()})
                return
            if method == "GET" and path == "/sync/v1/library":
                self._json(HTTPStatus.OK, {"name": self.app.name, "books": self.app.library_view()})
                return
            if method == "POST" and path == "/sync/v1/match":
                self._json(HTTPStatus.OK, {"matches": self.app.match(self._body().get("books"))})
                return
            match = re.fullmatch(r"/sync/v1/books/([A-Za-z0-9_-]+)/(manifest|state|files/(.+))", path)
            project = self.app.book(match.group(1)) if match else None
            if not match or project is None:
                self._json(HTTPStatus.NOT_FOUND, {"error": "Không có sách này"})
                return
            book = match.group(1)
            # Điện thoại chưa đổi khoá gọi bằng mã kiểu cũ: dữ liệu nghe lưu theo mã hiện hành (`key`), lời đáp nói lại
            # đúng mã nó dùng - không thì nó tưởng hồ sơ đã chuyển sang cuốn khác và gỡ khỏi cuốn đang nghe.
            key = book_id(project)
            if method == "GET" and match.group(2) == "manifest":
                self._json(HTTPStatus.OK, {**manifest(project, key, self.app.listening), "id": book})
            elif method == "POST" and match.group(2) == "state":
                body = self._body()
                record = body.get("record")
                state = {key: value for key, value in body.items() if key not in SYNC_KEYS}
                if isinstance(record, str) and RECORD_ID.fullmatch(record):
                    # điện thoại biết hồ sơ: gộp đúng hồ sơ ấy (webui/listening.py merge_record)
                    deleted = body.get("deletedRecords")
                    reply = self.app.listening.merge_record(
                        key, record, state, name=str(body.get("recordName") or ""),
                        name_at=float(body.get("nameAt") or 0), active_at=float(body.get("activeAt") or 0),
                        deleted=deleted if isinstance(deleted, dict) else None)
                    if reply.get("book") == key:
                        reply["book"] = book
                    self._json(HTTPStatus.OK, reply)
                else:  # điện thoại đời trước: hồ sơ đang dùng
                    self._json(HTTPStatus.OK, self.app.listening.merge(key, state))
            elif method == "GET" and match.group(3):
                target = self.app.resolve_file(project, unquote(match.group(3)))
                if target is None:
                    self._json(HTTPStatus.NOT_FOUND, {"error": "Không có file này"})
                elif isinstance(target, bytes):
                    self.send_response(HTTPStatus.OK)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(target)))
                    self.end_headers()
                    self.wfile.write(target)
                else:
                    self._file(target)
            else:
                self._json(HTTPStatus.METHOD_NOT_ALLOWED, {"error": "Không hỗ trợ"})
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            return
        except Exception as error:  # noqa: BLE001 - lỗi nào cũng về thành JSON cho điện thoại
            self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": f"{type(error).__name__}: {error}"})

    def do_GET(self) -> None:  # noqa: N802
        self._route("GET")

    def do_POST(self) -> None:  # noqa: N802
        self._route("POST")

    # Chỉ Studio từ xa dùng ba phương thức này (sửa dấu trang, đặt bìa, audio hỏi trước kích thước).
    def do_PUT(self) -> None:  # noqa: N802
        self._route("PUT")

    def do_DELETE(self) -> None:  # noqa: N802
        self._route("DELETE")

    def do_HEAD(self) -> None:  # noqa: N802
        self._route("HEAD")


class Discovery(threading.Thread):
    """Trả lời điện thoại đang tìm máy tính trong cùng mạng Wi-Fi (UDP broadcast)."""

    def __init__(self, name: str, port: int, discovery_port: int = DISCOVERY_PORT) -> None:
        super().__init__(name="sync-discovery", daemon=True)
        self.name_text = name
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(("0.0.0.0", discovery_port))
        self.socket.settimeout(1.0)
        self._stop = threading.Event()

    def run(self) -> None:
        reply = json.dumps({"app": "ebook-reader", "name": self.name_text, "port": self.port}).encode("utf-8")
        while not self._stop.is_set():
            try:
                data, address = self.socket.recvfrom(512)
            except (TimeoutError, socket.timeout):
                continue
            except OSError:
                break
            if data.strip() == DISCOVERY_PROBE:
                try:
                    self.socket.sendto(reply, address)
                except OSError:
                    pass

    def stop(self) -> None:
        self._stop.set()
        self.socket.close()


class SyncServer:
    """`host="0.0.0.0"` mở cho cả mạng LAN (kèm trả lời tìm máy). Khi phát triển dùng `127.0.0.1`: máy ảo Android
    gọi được qua 10.0.2.2 mà không mở cổng ra mạng, nên Windows không hỏi tường lửa."""

    def __init__(self, app: SyncApp, *, host: str = "0.0.0.0", port: int = SYNC_PORT,
                 discovery_port: int = DISCOVERY_PORT) -> None:
        handler = type("BoundSyncHandler", (SyncHandler,), {"app": app})
        self.httpd = ExclusiveHTTPServer((host, port), handler)
        self.port = int(self.httpd.server_address[1])
        self.discovery = Discovery(app.name, self.port, discovery_port) if host == "0.0.0.0" else None
        self._thread: threading.Thread | None = None

    def start(self) -> "SyncServer":
        self._thread = threading.Thread(target=self.httpd.serve_forever, name="sync", daemon=True)
        self._thread.start()
        if self.discovery:
            self.discovery.start()
        return self

    def stop(self) -> None:
        if self.discovery:
            self.discovery.stop()
        self.httpd.shutdown()
        self.httpd.server_close()


# Card mạng ảo trên máy (WSL/Hyper-V, VirtualBox, VMware, Docker...): điện thoại không bao giờ tới được địa chỉ của chúng.
VIRTUAL_ADAPTERS = ("vethernet", "hyper-v", "wsl", "virtualbox", "vmware", "docker", "loopback")


def _virtual_addresses() -> set[str]:
    try:
        import psutil
    except ImportError:
        return set()
    try:
        return {
            address.address
            for name, addresses in psutil.net_if_addrs().items()
            if any(marker in name.casefold() for marker in VIRTUAL_ADAPTERS)
            for address in addresses
            if address.family == socket.AF_INET
        }
    except OSError:
        return set()


def _tailscale(address: str) -> bool:
    """100.64.0.0/10 - dải của Tailscale (CGNAT): dùng được từ xa, nhưng cùng Wi-Fi thì không phải địa chỉ nên gõ."""
    parts = address.split(".")
    return len(parts) == 4 and parts[0] == "100" and parts[1].isdigit() and 64 <= int(parts[1]) <= 127


def local_addresses() -> list[str]:
    """Địa chỉ LAN của máy (để hiện cho người dùng khi điện thoại không tự tìm thấy): địa chỉ ra mạng chính ĐẦU TIÊN, Tailscale
    cuối, bỏ card ảo và địa chỉ link-local 169.254.x.x. Soát UX 29-09: "gõ 100.73.x.x hoặc 192.168.0.1 hoặc 192.168.0.230" -
    192.168.0.1 là card WSL, 100.73 là Tailscale, người dùng không biết gõ cái nào."""
    addresses: set[str] = set()
    primary = ""
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe.connect(("10.255.255.255", 1))
        primary = probe.getsockname()[0]
        probe.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            address = info[4][0]
            if not address.startswith(("127.", "169.254.")):
                addresses.add(address)
    except OSError:
        pass
    addresses -= _virtual_addresses()
    if primary and not primary.startswith(("0.", "127.", "169.254.")):
        addresses.add(primary)
    else:
        primary = ""
    return sorted(addresses, key=lambda address: (address != primary, _tailscale(address), address))
