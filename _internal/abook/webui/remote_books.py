"""Sách trên máy tính KHÁC - mạng trạm, bước 3: máy tính nghe thẳng thư viện của máy tính khác (chủ sách 27-09).

Máy này ghép với cổng đồng bộ của máy kia bằng đúng mã 6 số điện thoại dùng (`sync.Devices.pair`), rồi thấy thư viện của
máy kia như những cuốn "đã nhập" ảo: `<thư viện>/Trên máy khác/<máy>/<sách>/book.json` là manifest máy kia phục vụ cho
điện thoại (`sync.manifest`) kèm mục `package.remote`. File - chương, văn bản đọc theo, nhân vật, câu mẫu - được tải từ máy
kia LẦN ĐẦU có người mở tới rồi giữ lại (`fetch`). Nhờ vậy mọi thứ phía Nghe đã làm cho sách nhập từ file (chương, đọc
theo, dấu trang, hồ sơ nghe, hẹn giờ) dùng nguyên được, và phần đã tải vẫn nghe được khi máy kia đã tắt.

Máy này không bao giờ ghi gì lên máy kia ngoài việc ghép; mã thiết bị máy kia cấp nằm trong `computers.json` cạnh tuỳ chọn
của app (dữ liệu cá nhân - không đồng bộ, không đưa lên đâu), cùng vân tay chứng chỉ TLS của máy kia (tls.py): lúc ghép máy này
nhận chứng chỉ của máy kia và ghi vân tay lại; từ đó mọi yêu cầu chỉ nhận ĐÚNG chứng chỉ ấy. Vân tay đổi là lỗi bảo ghép lại.
"""
from __future__ import annotations

import hashlib
import http.client
import json
import re
import secrets
import shutil
import threading
import time
from pathlib import Path
from typing import Any, NamedTuple
from urllib.parse import quote

from . import tls

REMOTE_FOLDER = "Trên máy khác"
MANIFEST = "book.json"
TIMEOUT = 4
FILE_TIMEOUT = 60
_COMPUTERS: "Computers | None" = None


class RemoteError(Exception):
    """Máy kia không trả lời hay từ chối - thông điệp đọc được cho người dùng."""


def configure(computers: "Computers | None") -> None:
    """App gọi lúc dựng: `packages` hỏi module này khi cần tải một file của sách trên máy khác."""
    global _COMPUTERS
    _COMPUTERS = computers


def _folder(name: str, key: str) -> str:
    clean = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', " ", name or "").strip(" .")
    clean = " ".join(clean.split())[:50].rstrip(" .") or "Máy tính"
    return f"{clean} ({key[:8]})"


class Computers:
    """Máy tính khác đã ghép: địa chỉ, tên, mã thiết bị máy kia cấp, lần thấy cuối."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()

    def _read(self) -> dict[str, Any]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"computers": {}}
        return data if isinstance(data, dict) and isinstance(data.get("computers"), dict) else {"computers": {}}

    def _write(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        temporary.replace(self.path)

    def get(self, computer: str) -> dict[str, Any] | None:
        with self._lock:
            entry = self._read()["computers"].get(computer)
        return {"id": computer, **entry} if isinstance(entry, dict) else None

    def list(self) -> list[dict[str, Any]]:
        """Cho giao diện: không bao giờ kèm mã thiết bị."""
        with self._lock:
            entries = self._read()["computers"]
        return [{"id": key, **{field: value for field, value in entry.items() if field != "token"}}
                for key, entry in sorted(entries.items(), key=lambda item: str(item[1].get("name", "")).casefold())]

    def note(self, computer: str, **fields: Any) -> None:
        with self._lock:
            data = self._read()
            if computer in data["computers"]:
                data["computers"][computer].update(fields)
                self._write(data)

    def pair(self, address: str, code: str, device_name: str) -> dict[str, Any]:
        """Ghép với máy ở `address` ("192.168.1.20" hay "192.168.1.20:47630") bằng mã 6 số đang hiện trên máy ấy."""
        match = re.fullmatch(r"\s*\[?([A-Za-z0-9.\-:]+?)\]?(?::(\d{2,5}))?\s*", address or "")
        digits = re.sub(r"\D", "", code or "")
        if not match or len(digits) != 6:
            raise RemoteError("Nhập địa chỉ máy kia (vd 192.168.1.20) và mã 6 số đang hiện trên máy ấy")
        host, port = match.group(1), int(match.group(2) or 47630)
        # Lần ghép đầu: chưa có vân tay để đối chiếu (None) - ghi lại chứng chỉ máy kia đưa ra, sau khi nó tự xưng cùng vân tay.
        reply, seen = _exchange(Endpoint(host, port, None), "POST", "/sync/v1/pair", "",
                                {"code": digits, "device": device_name or "Máy tính"})
        try:
            data = json.loads(reply.decode("utf-8"))
            token, name = str(data["token"]), str(data.get("name") or host)
            claimed = str(data["fingerprint"]).lower()
        except (ValueError, KeyError) as error:
            raise RemoteError("Máy kia trả lời lạ - có phải ABook không?") from error
        if not seen or claimed != seen:
            raise RemoteError("Chứng chỉ máy kia không khớp với vân tay nó báo - dừng ghép, thử lại")
        with self._lock:
            data = self._read()
            # Ghép lại cùng một máy (cùng địa chỉ) thì thay chỗ cũ: sách đã tải và chỗ nghe giữ nguyên.
            key = next((existing for existing, entry in data["computers"].items()
                        if entry.get("host") == host and int(entry.get("port") or 0) == port), secrets.token_hex(6))
            data["computers"][key] = {"name": name, "host": host, "port": port, "token": token, "fingerprint": seen,
                                      "pairedAt": time.time(), "lastSeen": time.time(), "error": ""}
            self._write(data)
        return {"id": key, "name": name, "host": host, "port": port}

    def forget(self, computer: str, library_root: Path) -> None:
        """Thôi ghép: bỏ mã thiết bị và thư mục đệm của máy ấy (tải lại được khi ghép lại)."""
        with self._lock:
            data = self._read()
            data["computers"].pop(computer, None)
            self._write(data)
        root = Path(library_root).expanduser() / REMOTE_FOLDER
        for child in (root.iterdir() if root.is_dir() else []):
            if child.is_dir() and child.name.endswith(f"({computer[:8]})"):
                shutil.rmtree(child, ignore_errors=True)


def discover(*, timeout: float = 1.5, exclude_port: int | None = None, targets: list[str] | None = None,
             port: int | None = None) -> list[dict[str, Any]]:
    """Máy tính ABook khác trong cùng mạng: gửi đúng lời tìm điện thoại gửi (UDP broadcast - `sync.Discovery` của máy kia
    trả tên + cổng đồng bộ), gom trả lời trong `timeout` giây. Phát tới 255.255.255.255 và địa chỉ broadcast /24 của
    từng card mạng (Windows chỉ đẩy 255.255.255.255 ra một card). Bỏ chính máy này (địa chỉ của máy + cổng đồng bộ
    của máy). Máy kia phải đang bật kết nối - như điện thoại tìm nó."""
    import socket

    from .sync import DISCOVERY_PORT, DISCOVERY_PROBE, local_addresses

    own = set(local_addresses()) | {"127.0.0.1"}
    if targets is None:
        targets = ["255.255.255.255"] + sorted({address.rsplit(".", 1)[0] + ".255" for address in own
                                                if address.count(".") == 3 and not address.startswith("127.")})
    found: dict[tuple[str, int], dict[str, Any]] = {}
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        probe.settimeout(0.2)
        for target in targets:
            try:
                probe.sendto(DISCOVERY_PROBE, (target, port or DISCOVERY_PORT))
            except OSError:
                continue  # card mạng không có đường tới địa chỉ này
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                data, (host, _source_port) = probe.recvfrom(1024)
            except (TimeoutError, OSError):
                continue
            try:
                reply = json.loads(data.decode("utf-8"))
                sync_port = int(reply["port"])
            except (ValueError, KeyError, TypeError):
                continue
            if not isinstance(reply, dict) or reply.get("app") != "abook":
                continue
            if host in own and exclude_port is not None and sync_port == exclude_port:
                continue  # chính máy này trả lời
            # Điện thoại cũng trả lời khi bật "Cho máy khác nghe thư viện này" (LibraryServer.kt, cùng giao thức).
            found[(host, sync_port)] = {"name": str(reply.get("name") or host), "host": host, "port": sync_port,
                                        "kind": "phone" if reply.get("kind") == "phone" else "computer"}
    finally:
        probe.close()
    return sorted(found.values(), key=lambda item: (item["name"].casefold(), item["host"]))


class Endpoint(NamedTuple):
    """Một máy đã ghép: địa chỉ + vân tay chứng chỉ phải gặp. `fingerprint` None: chưa có (lần ghép đầu)."""

    host: str
    port: int
    fingerprint: str | None


def _exchange(endpoint: Endpoint, method: str, path: str, token: str, body: dict[str, Any] | None = None,
              timeout: float = TIMEOUT) -> tuple[bytes, str]:
    """Một yêu cầu qua TLS ghim vân tay: (thân trả lời, vân tay chứng chỉ máy kia đã đưa ra)."""
    if endpoint.fingerprint == "":
        raise RemoteError("Máy này chưa ghi vân tay của máy kia - ghép lại với máy kia")
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    if data is not None:
        headers["Content-Type"] = "application/json"
    connection = tls.PinnedHTTPSConnection(endpoint.host, endpoint.port, expected=endpoint.fingerprint, timeout=timeout)
    try:
        connection.request(method, path, body=data, headers=headers)
        response = connection.getresponse()
        payload = response.read()
        status, seen = response.status, connection.peer_fingerprint
    except tls.PinError as error:
        raise RemoteError("Chứng chỉ của máy kia đã khác lúc ghép - máy kia cài lại ABook, hoặc có ai chen vào mạng. "
                          "Nếu chắc đó vẫn là máy của anh, gỡ rồi ghép lại") from error
    except (OSError, http.client.HTTPException, TimeoutError) as error:
        raise RemoteError("Không kết nối được máy kia - máy tắt, khác mạng hay chưa bật “Cho phép điện thoại kết nối qua Wi-Fi”") from error
    finally:
        connection.close()
    if status >= 400:
        try:
            message = json.loads(payload.decode("utf-8")).get("error")
        except (ValueError, AttributeError):
            message = ""
        raise RemoteError(message or f"Máy kia trả lỗi {status}")
    return payload, seen


def _request(endpoint: Endpoint, method: str, path: str, token: str, body: dict[str, Any] | None = None,
             timeout: float = TIMEOUT) -> bytes:
    return _exchange(endpoint, method, path, token, body, timeout)[0]


def _base(entry: dict[str, Any]) -> Endpoint:
    return Endpoint(str(entry["host"]), int(entry["port"]), str(entry.get("fingerprint") or ""))


def refresh(library_root: Path, computers: Computers) -> dict[str, Any]:
    """Hỏi mọi máy đã ghép thư viện của nó, dựng / cập nhật các cuốn ảo. Máy không trả lời: giữ nguyên những gì đã có."""
    root = Path(library_root).expanduser() / REMOTE_FOLDER
    report: dict[str, Any] = {}
    for public in computers.list():
        entry = computers.get(public["id"])
        if entry is None:
            continue
        try:
            library = json.loads(_request(_base(entry), "GET", "/sync/v1/library", entry["token"]).decode("utf-8"))
            folder = root / _folder(str(library.get("name") or entry["name"]), public["id"])
            listed = [str(book["id"]) for book in library.get("books") or [] if isinstance(book, dict) and book.get("id")]
            _follow_renamed(entry, public["id"], folder, set(listed))
            built = {remote["book"]: child for child, manifest in _manifests(folder)
                     if (remote := remote_of(manifest)) and remote["computer"] == public["id"]}
            books = 0
            for book in listed:
                _refresh_book(entry, public["id"], folder, book, built.get(book))
                books += 1
            computers.note(public["id"], lastSeen=time.time(), error="", name=str(library.get("name") or entry["name"]))
            report[public["id"]] = {"books": books}
        except RemoteError as error:
            computers.note(public["id"], error=str(error))
            report[public["id"]] = {"error": str(error)}
    return report


def _manifests(folder: Path, suffix: str = "") -> list[tuple[Path, dict[str, Any]]]:
    """(thư mục, book.json) các cuốn ảo trong `folder` - chỉ những thư mục có tên kết thúc bằng `suffix` nếu có."""
    found = []
    for child in folder.iterdir() if folder.is_dir() else []:
        if suffix and not child.name.endswith(suffix):
            continue
        try:
            manifest = json.loads((child / MANIFEST).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(manifest, dict):
            found.append((child, manifest))
    return found


def _write_manifest(target: Path, manifest: dict[str, Any]) -> None:
    temporary = target / (MANIFEST + ".tmp")
    temporary.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    temporary.replace(target / MANIFEST)


def _follow_renamed(entry: dict[str, Any], computer: str, folder: Path, listed: set[str]) -> None:
    """Máy kia đổi mã sách (mã kiểu cũ -> mã mới, docs/BOOK_IDS.md): cuốn ảo dựng theo mã cũ hỏi máy kia mã
    mới (`/sync/v1/match` nhận ra mã cũ của chính nó) rồi đổi trong book.json. Thư mục giữ nguyên - mã sách ở máy này,
    chỗ nghe, file đã tải đều giữ; không thì máy này hiện hai bản của một cuốn. Máy kia chưa nâng cấp: không cuốn nào lệch
    mã, không hỏi gì."""
    stale = {}
    for child, manifest in _manifests(folder):
        remote = remote_of(manifest)
        if remote and remote["computer"] == computer and remote["book"] not in listed:
            stale[remote["book"]] = (child, manifest)
    if not stale:
        return
    try:
        reply = json.loads(_request(_base(entry), "POST", "/sync/v1/match", entry["token"],
                                    {"books": [{"key": key} for key in stale]}).decode("utf-8"))
    except (RemoteError, ValueError):
        return
    matches = reply.get("matches") if isinstance(reply, dict) else None
    taken = {remote_of(manifest)["book"] for _child, manifest in _manifests(folder) if remote_of(manifest)}
    for old, new in (matches.items() if isinstance(matches, dict) else []):
        # mã mới phải là cuốn máy kia đang liệt kê, và chưa có cuốn ảo nào mang nó (có rồi thì để nguyên cả hai)
        if old not in stale or not isinstance(new, str) or new not in listed or new in taken:
            continue
        child, manifest = stale[old]
        manifest["package"]["remote"]["book"] = new
        _write_manifest(child, manifest)
        taken.add(new)


def _refresh_book(entry: dict[str, Any], computer: str, folder: Path, book: str, built: Path | None = None) -> None:
    """`built`: thư mục cuốn ảo đã dựng cho sách này - kể cả dựng theo mã cũ rồi đổi mã (`_follow_renamed`: tên thư mục
    còn mang dấu của mã cũ)."""
    manifest = json.loads(_request(_base(entry), "GET", f"/sync/v1/books/{book}/manifest", entry["token"]).decode("utf-8"))
    title = str(manifest.get("title") or "Sách")
    target = built or folder / _folder(title, hashlib.sha256(book.encode()).hexdigest())
    target.mkdir(parents=True, exist_ok=True)
    previous: dict[str, Any] = {}
    try:
        previous = json.loads((target / MANIFEST).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    manifest["package"] = {"remote": {"computer": computer, "book": book}, "files": {}}
    new_cover = manifest.get("cover") if isinstance(manifest.get("cover"), dict) else None
    old_cover = previous.get("cover") if isinstance(previous.get("cover"), dict) else None
    if manifest != previous:
        _write_manifest(target, manifest)
    # Bìa: nhỏ, cần ngay cho thư viện - tải luôn (khi đổi phiên bản), không đợi người mở.
    if new_cover and (new_cover != old_cover or not (target / "cover.jpg").is_file()):
        try:
            data = _request(_base(entry), "GET", f"/sync/v1/books/{book}/files/cover.jpg", entry["token"],
                            timeout=FILE_TIMEOUT)
            (target / "cover.jpg").write_bytes(data)
            meta = {key: new_cover[key] for key in ("color", "width", "height") if new_cover.get(key)}
            (target / "cover.json").write_text(json.dumps(meta), encoding="utf-8")
        except RemoteError:
            pass


def player(entry: dict[str, Any], *, timeout: float = 2.0) -> dict[str, Any]:
    """Trình phát của máy đã ghép lúc này (`GET /sync/v1/player`, mạng trạm bước 4): máy tính hay điện thoại chia sẻ thư
    viện đều trả cùng hình dạng thân báo điện thoại gửi máy tính - đọc bằng `sync._presence`."""
    reply = json.loads(_request(_base(entry), "GET", "/sync/v1/player", entry["token"], timeout=timeout).decode("utf-8"))
    if not isinstance(reply, dict):
        raise RemoteError("Máy kia trả lời lạ - có phải ABook không?")
    return reply


def player_command(entry: dict[str, Any], command: dict[str, Any], *, timeout: float = 5.0) -> dict[str, Any]:
    """Gửi một lệnh (đã qua `sync.remote_command`) cho trình phát của máy đã ghép. Máy tính trả `id` rồi làm sau (kết
    quả về trong `acks`); điện thoại làm ngay và trả luôn `ok`/`message`."""
    reply = json.loads(_request(_base(entry), "POST", "/sync/v1/player", entry["token"], command,
                                timeout=timeout).decode("utf-8"))
    return reply if isinstance(reply, dict) else {}


def local_book(library_root: Path, computer: str, book: str) -> Path | None:
    """Cuốn ảo của máy này cho sách `book` của máy `computer` (đã dựng bởi `refresh`), None nếu chưa có."""
    root = Path(library_root).expanduser() / REMOTE_FOLDER
    mark = f"({hashlib.sha256(book.encode()).hexdigest()[:8]})"
    for folder in root.glob(f"*({computer[:8]})") if root.is_dir() else []:
        # thư mục mang dấu của mã trước (nhanh: giao diện hỏi mỗi 1,5 giây); cuốn đổi mã (`_follow_renamed`) giữ tên cũ
        for suffix in (mark, ""):
            for child, manifest in _manifests(folder, suffix):
                if remote_of(manifest) == {"computer": computer, "book": book}:
                    return child
    return None


def remote_of(manifest: dict[str, Any]) -> dict[str, str] | None:
    package = manifest.get("package") if isinstance(manifest.get("package"), dict) else {}
    remote = package.get("remote") if isinstance(package, dict) else None
    return remote if isinstance(remote, dict) and remote.get("computer") and remote.get("book") else None


def computer_name(manifest: dict[str, Any]) -> str:
    remote = remote_of(manifest)
    entry = _COMPUTERS.get(remote["computer"]) if remote and _COMPUTERS is not None else None
    return str(entry.get("name") or "") if entry else ""


def exchange_state(manifest: dict[str, Any], state: dict[str, Any], *, timeout: float = TIMEOUT) -> dict[str, Any] | None:
    """Gửi chỗ nghe của máy này cho máy kia và nhận bản đã gộp - đúng đường điện thoại dùng (POST .../state; máy kia gộp
    vào hồ sơ đang dùng theo mốc thời gian từng phần, `listening.merge`). Máy kia không trả lời: None, lần sau gửi lại."""
    remote = remote_of(manifest)
    entry = _COMPUTERS.get(remote["computer"]) if remote and _COMPUTERS is not None else None
    if entry is None:
        return None
    body = {key: value for key, value in state.items() if key not in ("night", "sessions")}
    try:
        reply = json.loads(_request(_base(entry), "POST", f"/sync/v1/books/{remote['book']}/state", entry["token"], body,
                                    timeout=timeout).decode("utf-8"))
    except (RemoteError, ValueError):
        return None
    return reply if isinstance(reply, dict) else None


def fetch(package: Path, relative: str, manifest: dict[str, Any]) -> Path | None:
    """Tải một file của sách trên máy khác vào thư mục đệm của nó, trả đường dẫn; máy kia không trả lời thì None."""
    remote = remote_of(manifest)
    if remote is None or _COMPUTERS is None or not re.fullmatch(r"[A-Za-z0-9_./ \-]+", relative) or ".." in relative:
        return None
    entry = _COMPUTERS.get(remote["computer"])
    if entry is None:
        return None
    try:
        data = _request(_base(entry), "GET", f"/sync/v1/books/{remote['book']}/files/{quote(relative)}", entry["token"],
                        timeout=FILE_TIMEOUT)
    except RemoteError:
        return None
    target = (Path(package) / relative).resolve()
    if not target.is_relative_to(Path(package).resolve()):
        return None
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".part")
    temporary.write_bytes(data)
    temporary.replace(target)
    return target
