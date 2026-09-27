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
gửi lệnh phát/dừng/tua ngược lại - kể cả chuyển chỗ nghe giữa hai máy.
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
from typing import Any
from urllib.parse import unquote, urlsplit

from . import covers, listen_view, store
from .library import Library, book_id
from .listening import Listening

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
REMOTE_ACTIONS = frozenset({"play", "pause", "toggle", "skip", "seek", "next", "previous", "jump", "rate", "load"})
BOOK_ID = re.compile(r"[A-Za-z0-9_-]{1,700}")  # base64 của đường dẫn thư mục sách (library.book_id)


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
    """

    def __init__(self) -> None:
        self._changed = threading.Condition()
        self._presence: dict[str, dict[str, Any]] = {}
        self._commands: dict[str, list[dict[str, Any]]] = {}
        self._generation = 0

    def report(self, device: str, name: str, report: dict[str, Any], wait: Any = 0.0) -> list[dict[str, Any]]:
        """Ghi trạng thái của một điện thoại, trả các lệnh đang chờ nó (chờ tối đa `wait` giây nếu chưa có)."""
        deadline = time.time() + _number(wait, 0.0, REMOTE_WAIT_SECONDS)
        with self._changed:
            generation = self._generation
            self._presence[device] = {**_presence(report), "device": device, "name": name, "at": time.time()}
            while self._generation == generation and not self._pending(device):
                left = deadline - time.time()
                if left <= 0:
                    break
                self._changed.wait(left)
            commands = self._pending(device)
            self._commands.pop(device, None)
            return commands

    def _pending(self, device: str) -> list[dict[str, Any]]:
        fresh = [command for command in self._commands.get(device, []) if time.time() - command["at"] <= COMMAND_SECONDS]
        if fresh:
            self._commands[device] = fresh
        else:
            self._commands.pop(device, None)
        return fresh

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

    def pair(self, code: str, name: str) -> str | None:
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
                                                   "pairedAt": time.time(), "lastSeen": time.time()}
            self._save()
            return token

    def check(self, token: str) -> bool:
        return self.identify(token) is not None

    def identify(self, token: str) -> dict[str, str] | None:
        """Thiết bị mang mã này: `{"id", "name"}` (id là 12 ký tự đầu của băm, như trong danh sách), hoặc None."""
        key = _hash(token)
        with self._lock:
            device = self._data["devices"].get(key)
            if device is None:
                return None
            if time.time() - device.get("lastSeen", 0) > 60:
                device["lastSeen"] = time.time()
                self._save()
            return {"id": key[:12], "name": str(device.get("name") or "Điện thoại")}

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
                 remote: Remote | None = None) -> None:
        self.library = library
        self.listening = listening
        self.devices = devices
        self.name = name
        self.remote = remote or Remote()

    def book(self, value: str) -> Path | None:
        return self.library.resolve(value)

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
        self.wfile.write(body)

    def _body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            return {}
        try:
            data = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
        except (ValueError, UnicodeDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def _device(self) -> dict[str, str] | None:
        header = self.headers.get("Authorization") or ""
        return self.app.devices.identify(header[7:].strip()) if header.startswith("Bearer ") else None

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
            if method == "POST" and path == "/sync/v1/pair":
                body = self._body()
                token = self.app.devices.pair(str(body.get("code", "")), str(body.get("device", "")))
                if token is None:
                    self._json(HTTPStatus.FORBIDDEN, {"error": "Mã ghép nối sai hoặc đã hết hạn"})
                else:
                    self._json(HTTPStatus.OK, {"token": token, "name": self.app.name})
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
            if method == "GET" and path == "/sync/v1/library":
                self._json(HTTPStatus.OK, {"name": self.app.name, "books": self.app.library_view()})
                return
            match = re.fullmatch(r"/sync/v1/books/([A-Za-z0-9_-]+)/(manifest|state|files/(.+))", path)
            project = self.app.book(match.group(1)) if match else None
            if not match or project is None:
                self._json(HTTPStatus.NOT_FOUND, {"error": "Không có sách này"})
                return
            book = match.group(1)
            if method == "GET" and match.group(2) == "manifest":
                self._json(HTTPStatus.OK, manifest(project, book, self.app.listening))
            elif method == "POST" and match.group(2) == "state":
                self._json(HTTPStatus.OK, self.app.listening.merge(book, self._body()))
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


def local_addresses() -> list[str]:
    """Địa chỉ LAN của máy (để hiện cho người dùng khi điện thoại không tự tìm thấy)."""
    addresses: set[str] = set()
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe.connect(("10.255.255.255", 1))
        addresses.add(probe.getsockname()[0])
        probe.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            address = info[4][0]
            if not address.startswith("127."):
                addresses.add(address)
    except OSError:
        pass
    return sorted(addresses)
