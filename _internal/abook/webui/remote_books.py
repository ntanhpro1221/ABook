"""Sách trên máy tính KHÁC - mạng trạm, bước 3: máy tính nghe thẳng thư viện của máy tính khác (chủ sách 27-09).

Máy này ghép với cổng đồng bộ của máy kia bằng đúng mã 6 số điện thoại dùng (`sync.Devices.pair`), rồi thấy thư viện của
máy kia như những cuốn "đã nhập" ảo: `<thư viện>/Trên máy khác/<máy>/<sách>/book.json` là manifest máy kia phục vụ cho
điện thoại (`sync.manifest`) kèm mục `package.remote`. File - chương, văn bản đọc theo, nhân vật, câu mẫu - được tải từ máy
kia LẦN ĐẦU có người mở tới rồi giữ lại (`fetch`), hay cả cuốn một lượt khi người dùng bấm "Tải về máy" (`Downloads`). Nhờ
vậy mọi thứ phía Nghe đã làm cho sách nhập từ file (chương, đọc theo, dấu trang, hồ sơ nghe, hẹn giờ) dùng nguyên được, và phần
đã tải vẫn nghe được khi máy kia đã tắt.

Cuốn của một MÁY TÍNH đã ghép sửa được ở máy này như cuốn điện thoại tải từ máy tính: lớp sửa (book_edits.py) nằm trong thư mục
cuốn ảo, rồi gửi về máy kia đúng đường điện thoại gửi (`send_edits` -> sync.py `receive_edits` -> edits_inbox.py). Ngoài việc ghép,
chỗ nghe và phần sửa ấy, máy này không ghi gì lên máy kia; mã thiết bị máy kia cấp nằm trong `computers.json` cạnh tuỳ chọn
của app (dữ liệu cá nhân - không đồng bộ, không đưa lên đâu), cùng vân tay chứng chỉ TLS của máy kia (tls.py): lúc ghép máy này
nhận chứng chỉ của máy kia và ghi vân tay lại; từ đó mọi yêu cầu chỉ nhận ĐÚNG chứng chỉ ấy. Vân tay đổi là lỗi bảo ghép lại.

Không chung Wi-Fi thì đi Bluetooth (webui/bluetooth.py `Gateway`): máy ghép bằng địa chỉ Bluetooth ("bt:AA:BB:...") hay có trường `bt`
(máy kia báo lúc ghép Wi-Fi) thì gốc https là cổng cục bộ của đường hầm; Wi-Fi trước, hỏng thì Bluetooth (route.py, như Route.kt
của điện thoại). Đổi host sang 127.0.0.1 không làm lỏng gì: TLS đi nguyên vẹn qua đường hầm và vân tay ghim vẫn kiểm.
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
import zipfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator, NamedTuple
from urllib.parse import quote

from . import bluetooth, book_edits, route, tls

REMOTE_FOLDER = "Trên máy khác"
MANIFEST = "book.json"
TIMEOUT = 4
FILE_TIMEOUT = 60
PAIR_BLUETOOTH_TIMEOUT = 45  # ghép qua Bluetooth: tra SDP + nối RFCOMM + bắt tay TLS, người dùng đang chờ ở một yêu cầu riêng
LIBRARY_PORT = 47630  # cổng đồng bộ mặc định (điện thoại: LibraryServer.PORT); máy ghép bằng Bluetooth không dùng nhưng entry có cổng
_COMPUTERS: "Computers | None" = None


class RemoteError(Exception):
    """Máy kia không trả lời hay từ chối - thông điệp đọc được cho người dùng. `status`: mã HTTP khi máy kia trả lỗi (404: máy
    kia không có file ấy), None khi không tới được máy kia."""

    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


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
        return [{"id": key, **{field: value for field, value in entry.items() if field != "token"},
                 **({"waking": now} if (now := waking(key)) else {})}
                for key, entry in sorted(entries.items(), key=lambda item: str(item[1].get("name", "")).casefold())]

    def note(self, computer: str, **fields: Any) -> None:
        with self._lock:
            data = self._read()
            if computer in data["computers"]:
                data["computers"][computer].update(fields)
                self._write(data)

    def pair(self, address: str, code: str, device_name: str) -> dict[str, Any]:
        """Ghép với máy ở `address` ("192.168.1.20" hay "192.168.1.20:47630"; "AA:BB:CC:DD:EE:FF" hay "bt:AA:BB:..." là địa chỉ
        Bluetooth của máy đã ghép trong Cài đặt Windows - không cần chung Wi-Fi) bằng mã 6 số đang hiện trên máy ấy."""
        digits = re.sub(r"\D", "", code or "")
        by_bluetooth = bluetooth.normalize_address(re.sub(r"(?i)^\s*bt:", "", address or ""))
        match = None if by_bluetooth or re.match(r"(?i)\s*bt:", address or "") else re.fullmatch(
            r"\s*\[?([A-Za-z0-9.\-:]+?)\]?(?::(\d{2,5}))?\s*", address or "")  # "bt:..." hỏng không phải tên máy
        if (not match and not by_bluetooth) or len(digits) != 6:
            raise RemoteError("Nhập địa chỉ máy kia (vd 192.168.1.20, hay địa chỉ Bluetooth AA:BB:CC:DD:EE:FF) và mã 6 số "
                              "đang hiện trên máy ấy")
        host, port = (f"bt:{by_bluetooth}", LIBRARY_PORT) if by_bluetooth else (match.group(1), int(match.group(2) or LIBRARY_PORT))
        # Lần ghép đầu: chưa có vân tay để đối chiếu (None) - ghi lại chứng chỉ máy kia đưa ra, sau khi nó tự xưng cùng vân tay.
        first = _tunnel(by_bluetooth, None) if by_bluetooth else Endpoint(host, port, None)
        reply, seen = _exchange(first, "POST", "/sync/v1/pair", "", {"code": digits, "device": device_name or "Máy tính"},
                                PAIR_BLUETOOTH_TIMEOUT if by_bluetooth else TIMEOUT)
        try:
            reply_data = json.loads(reply.decode("utf-8"))
            token, name = str(reply_data["token"]), str(reply_data.get("name") or host)
            claimed = str(reply_data["fingerprint"]).lower()
        except (ValueError, KeyError) as error:
            raise RemoteError("Máy kia trả lời lạ - có phải ABook không?") from error
        if not seen or claimed != seen:
            raise RemoteError("Chứng chỉ máy kia không khớp với vân tay nó báo - dừng ghép, thử lại")
        with self._lock:
            data = self._read()
            # Ghép lại cùng một máy (cùng địa chỉ) thì thay chỗ cũ: sách đã tải và chỗ nghe giữ nguyên.
            # Máy đã từng thôi ghép (cùng vân tay chứng chỉ, dù đổi địa chỉ) lấy lại mã cũ: mã sách ở máy này theo mã ấy, nên chỗ
            # nghe và dấu trang của các cuốn ấy hiện lại, không mất khi ghép lại.
            former = data.get("former", {}).pop(seen, None)
            key = next((existing for existing, entry in data["computers"].items()
                        if entry.get("host") == host and int(entry.get("port") or 0) == port), None) or former or secrets.token_hex(6)
            entry = {"name": name, "host": host, "port": port, "token": token, "fingerprint": seen,
                     "pairedAt": time.time(), "lastSeen": time.time(), "error": ""}
            # Đường Bluetooth dự phòng: máy kia báo trong lời đáp ghép (sync.py `routes`); không báo thì giữ cái đã biết.
            if known := (_routes_bluetooth(reply_data) or data["computers"].get(key, {}).get("bt") or ""):
                entry["bt"] = known
            # Tên Bluetooth điện thoại báo (khác tên máy ở Wi-Fi): để tự khớp với thiết bị đã ghép ở Windows.
            if known_name := (_bluetooth_name(reply_data) or data["computers"].get(key, {}).get("btName") or ""):
                entry["btName"] = known_name
            data["computers"][key] = entry
            self._write(data)
        return {"id": key, "name": name, "host": host, "port": port}

    def set_bluetooth(self, computer: str, address: str) -> None:
        """Người dùng chọn thiết bị Bluetooth của máy đã ghép qua Wi-Fi (`bluetooth.paired_devices`); "" bỏ chọn. Máy ghép bằng
        địa chỉ Bluetooth thì địa chỉ nằm sẵn ở host."""
        clean = bluetooth.normalize_address(address) if address else ""
        if address and not clean:
            raise RemoteError("Địa chỉ Bluetooth phải có dạng AA:BB:CC:DD:EE:FF")
        with self._lock:
            data = self._read()
            entry = data["computers"].get(computer)
            if not isinstance(entry, dict):
                raise RemoteError("Máy này không còn ghép")
            if str(entry.get("host") or "").startswith("bt:"):
                raise RemoteError("Máy này đã ghép qua Bluetooth rồi")
            old = bluetooth.normalize_address(str(entry.get("bt") or ""))
            if clean:
                entry["bt"] = clean
            else:
                entry.pop("bt", None)
            self._write(data)
        if old and old != clean:
            _release_bluetooth({"bt": old}, data["computers"].values())

    def forget(self, computer: str, library_root: Path, *, discard: bool = False) -> None:
        """Thôi ghép: bỏ mã thiết bị và thư mục đệm của máy ấy (tải lại được khi ghép lại). Thư mục đệm mang cả phần sửa chưa gửi của
        người nghe: còn sửa mà `discard` = False thì từ chối (`UnsentEdits`), không đổi gì - gửi trước (`send_unsent`) hay chọn bỏ."""
        if not discard:
            refuse_if_unsent(library_root, computer)
        with self._lock:
            data = self._read()
            gone = data["computers"].pop(computer, None) or {}
            if gone.get("fingerprint"):
                data.setdefault("former", {})[str(gone["fingerprint"])] = computer
            self._write(data)
        _release_bluetooth(gone, data["computers"].values())
        root = Path(library_root).expanduser() / REMOTE_FOLDER
        for child in (root.iterdir() if root.is_dir() else []):
            if child.is_dir() and child.name.endswith(f"({computer[:8]})"):
                shutil.rmtree(child, ignore_errors=True)


class UnsentEdits(RemoteError):
    """Thôi ghép sẽ làm mất phần sửa chưa gửi về máy kia (nói số cuốn và số thay đổi)."""


def unsent_edits(library_root: Path, computer: str) -> list[dict[str, Any]]:
    """Phần sửa chưa gửi của các cuốn của máy `computer` trong thư mục đệm - thứ `Computers.forget` xoá cùng thư mục:
    [{package, title, changes}], ổn định theo tên thư mục. Cuốn không sửa gì thì không có mặt."""
    root = Path(library_root).expanduser() / REMOTE_FOLDER
    found = []
    for folder in sorted(root.iterdir()) if root.is_dir() else []:
        if not (folder.is_dir() and folder.name.endswith(f"({computer[:8]})")):
            continue
        for package, manifest in sorted(_manifests(folder), key=lambda item: item[0].name):
            edits = book_edits.load(package)
            changes = pending_changes(package, edits)
            if changes:
                # Tên người nghe THẤY (đã sửa), không phải tên gốc trong gói: hộp gỡ ghép nói cuốn nào sẽ mất phần sửa.
                title = book_edits.apply_manifest(manifest, edits).get("title")
                found.append({"package": package, "title": str(title or package.name), "changes": changes})
    return found


def cached_books(library_root: Path, computer: str) -> list[dict[str, Any]]:
    """Các cuốn ảo của máy `computer` trong thư mục đệm - thứ `Computers.forget` xoá: [{package, bytes}], `bytes` là phần đã tải về
    máy này (chương, chữ đọc theo, nhạc... - không tính book.json và bìa). Hộp thôi ghép nói số cuốn và dung lượng sẽ mất."""
    root = Path(library_root).expanduser() / REMOTE_FOLDER
    found = []
    for folder in sorted(root.iterdir()) if root.is_dir() else []:
        if not (folder.is_dir() and folder.name.endswith(f"({computer[:8]})")):
            continue
        for package, _manifest in sorted(_manifests(folder), key=lambda item: item[0].name):
            size = 0
            for file in package.rglob("*"):
                if file.is_file() and file.relative_to(package).as_posix() not in (MANIFEST, "cover.jpg", "cover.json"):
                    try:
                        size += file.stat().st_size
                    except OSError:
                        continue
            found.append({"package": package, "bytes": size})
    return found


def refuse_if_unsent(library_root: Path, computer: str) -> None:
    left = unsent_edits(library_root, computer)
    if left:
        raise UnsentEdits(f"{len(left)} cuốn còn {sum(item['changes'] for item in left)} thay đổi chưa gửi - gửi trước hay chọn bỏ rồi thôi ghép")


def send_unsent(library_root: Path, computer: str) -> None:
    """Gửi hết phần sửa chưa gửi của máy `computer` về máy ấy trước khi thôi ghép (`send_edits` từng cuốn; lỗi dừng ngay, cuốn ấy và
    các cuốn sau giữ nguyên). Gửi xong mà vẫn còn sửa (vd sửa thêm giữa chừng) cũng là lỗi - không coi là xong khi còn thứ sẽ mất."""
    for item in unsent_edits(library_root, computer):
        send_edits(item["package"])
    refuse_if_unsent(library_root, computer)


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
                                        "kind": "phone" if reply.get("kind") == "phone" else "computer",
                                        **({"btName": name} if (name := _bluetooth_name(reply)) else {})}
    finally:
        probe.close()
    return sorted(found.values(), key=lambda item: (item["name"].casefold(), item["host"]))


class Endpoint(NamedTuple):
    """Một máy đã ghép: địa chỉ + vân tay chứng chỉ phải gặp. `fingerprint` None: chưa có (lần ghép đầu). Còn lại là đường đi
    (`_base`): `target` "host:cổng" của đường Wi-Fi (để route.py nhớ thông/hỏng), `fallback` địa chỉ Bluetooth thử khi nối Wi-Fi
    hỏng, `bluetooth` địa chỉ Bluetooth của máy mà endpoint này (127.0.0.1:<cổng đường hầm>) dẫn tới."""

    host: str
    port: int
    fingerprint: str | None
    target: str = ""
    fallback: str = ""
    bluetooth: str = ""
    computer: str = ""  # mã máy trong computers.json: Wi-Fi hỏng mà chưa biết địa chỉ Bluetooth thì tìm theo tên (`_look_for_bluetooth`)


# Tên công tắc ở Cài đặt của máy kia - đúng chuỗi của ui/src/shared/syncSwitch.ts (tests/test_sync_switch_label.py giữ hai bên không lệch).
SYNC_SWITCH = "Cho phép thiết bị khác kết nối qua Wi-Fi"
UNREACHABLE = f"Không kết nối được máy kia - máy tắt, khác mạng hay chưa bật “{SYNC_SWITCH}”"
UNREACHABLE_BLUETOOTH = ("Không kết nối được máy kia qua Bluetooth - máy kia đã bật ABook và Bluetooth chưa, và có trong tầm "
                         "sóng không?")


def _unreachable(endpoint: Endpoint) -> str:
    """Lời báo không tới được máy kia: đi Bluetooth (hay lùi về Bluetooth) thì nói lý do đường hầm đã ghi."""
    address = endpoint.bluetooth or endpoint.fallback
    if not address:
        name = _peer_name(endpoint)
        return UNREACHABLE.replace("máy kia", _called(name), 1) if name else UNREACHABLE
    return bluetooth.last_error(address) or UNREACHABLE_BLUETOOTH


def _peer_name(endpoint: Endpoint) -> str:
    """Tên máy đã ghép mà `endpoint` dẫn tới ("" khi chưa biết - lúc đang ghép): lời báo nói tên máy, không nói "máy kia"."""
    entry = _COMPUTERS.get(endpoint.computer) if _COMPUTERS is not None and endpoint.computer else None
    return str(entry.get("name") or "") if entry else ""


def _called(name: str) -> str:
    """"máy <tên>" - tên đã mở đầu bằng "Máy" (vd "Máy kia") thì không thêm chữ máy nữa."""
    return name[:1].lower() + name[1:] if name.casefold().startswith("máy ") else f"máy {name}"


def _cut(endpoint: Endpoint) -> str:
    """Lời báo khi máy kia đang trả lời thì ngừng giữa chừng (tắt máy, rớt mạng): nói đúng điều người dùng thấy."""
    phrase = _called(_peer_name(endpoint) or "kia")
    return f"{phrase[:1].upper()}{phrase[1:]} không trả lời (tắt hay mất mạng)"


def _tunnel(address: str, fingerprint: str | None, computer: str = "") -> Endpoint:
    """Gốc https của máy ở địa chỉ Bluetooth `address`: cổng cục bộ của đường hầm (mở RFCOMM ở nền nếu chưa mở). Vân tay giữ
    nguyên - TLS đi hết đường hầm tới máy kia, nên chứng chỉ vẫn phải khớp."""
    link = bluetooth.gateway(address)
    link.warm()
    return Endpoint("127.0.0.1", link.port, fingerprint, bluetooth=bluetooth.normalize_address(address), computer=computer)


# ---- điện thoại đang ngủ ---------------------------------------------------------------------------------------------------
# Đo 08-10 (docs/BLUETOOTH.md): ColorOS đóng băng ABook ~30 giây sau khi rời màn hình. Hệ điều hành vẫn nhận kết nối (TCP, RFCOMM)
# nhưng app không bắt tay TLS cho tới khi tự dậy: Wi-Fi ~19 giây (gói TCP tới làm nó dậy), Bluetooth có khi 224 giây (không gì
# đánh thức được). Nối lại không giúp gì - kết nối đang chờ xong ngay khi app dậy - nên tầng dưới đã nối thì cứ chờ, nói cho
# người dùng biết, và cho họ thôi chờ. Chỉ coi là xong khi bắt tay TLS + vân tay đã ghim xong.

WAKE_BLUETOOTH_SECONDS = 300
WAKE_WIFI_SECONDS = 60
SLEEPY_SECONDS = 3  # tầng dưới đã nối mà ngần này chưa bắt tay xong: báo "đang ngủ"
QUIET_SECONDS = 600  # thôi chờ / chờ hết hạn: ngần này không tự chờ lại ở nền (người dùng bấm hỏi lại thì vẫn chờ)
STILL_ASLEEP = "Điện thoại vẫn chưa trả lời - mở ABook trên điện thoại rồi bấm “Hỏi lại thư viện”"
STOPPED_WAITING = "Đã thôi chờ - mở ABook trên điện thoại rồi bấm “Hỏi lại thư viện”"
_WAKE_LOCK = threading.Lock()
_waits: dict[str, list["_Wait"]] = {}  # máy -> các lần nối đang chờ nó dậy
_quiet: dict[str, float] = {}  # máy -> lúc thôi chờ / chờ hết hạn


class _Wait:
    """Một lần nối được phép chờ máy kia dậy: tầng dưới (TCP, hay cổng đường hầm) nối với hạn thường như mọi lần, bắt tay TLS
    thì chờ tới `limit`, từng nhịp ngắn để thôi chờ là thôi ngay. Kiểm vân tay vẫn là của PinnedHTTPSConnection."""

    STEP = 0.5

    def __init__(self, endpoint: Endpoint) -> None:
        self.computer = endpoint.computer
        self.bluetooth = endpoint.bluetooth
        self.limit = WAKE_BLUETOOTH_SECONDS if endpoint.bluetooth else WAKE_WIFI_SECONDS
        self.started = time.time()
        self.asleep = False
        self.cancelled = False
        self.finished = threading.Event()

    def handshake(self, sock: Any) -> None:
        """Bắt tay TLS trên `sock` (SSLSocket chưa bắt tay); hết hạn hay bị thôi chờ: TimeoutError."""
        with _WAKE_LOCK:
            _waits.setdefault(self.computer, []).append(self)
        threading.Thread(target=self._watch, name="remote-wake", daemon=True).start()
        deadline = time.monotonic() + self.limit
        usual = sock.gettimeout()
        sock.settimeout(self.STEP)
        try:
            while True:
                try:
                    sock.do_handshake()
                    return
                except TimeoutError:  # OpenSSL giữ trạng thái bắt tay: gọi lại là làm tiếp
                    if self.cancelled or time.monotonic() > deadline:
                        raise
        finally:
            sock.settimeout(usual)
            self.done()

    def _lower_layer_up(self) -> bool:
        """Wi-Fi: TCP đã nối là xong tầng dưới. Bluetooth: cổng cục bộ luôn nối được, phải chờ RFCOMM của đường hầm lên."""
        return not self.bluetooth or bluetooth.gateway(self.bluetooth).up

    def _watch(self) -> None:
        if self.finished.wait(SLEEPY_SECONDS):
            return
        while not self.finished.is_set():
            if self._lower_layer_up():
                self.asleep = True
                return
            self.finished.wait(0.5)

    def cancel(self) -> None:
        self.cancelled = True

    def done(self) -> None:
        self.finished.set()
        with _WAKE_LOCK:
            mine = _waits.get(self.computer, [])
            if self in mine:
                mine.remove(self)
            if not mine:
                _waits.pop(self.computer, None)

    def reason(self, error: BaseException) -> str:
        """Câu cho người dùng khi lần chờ này hỏng; "" nếu không phải chuyện điện thoại ngủ (lỗi thường xử như cũ)."""
        if self.cancelled:
            return STOPPED_WAITING
        if self.asleep and isinstance(error, TimeoutError):
            with _WAKE_LOCK:
                _quiet[self.computer] = time.monotonic()
            return STILL_ASLEEP
        return ""


class _WakingContext:
    """SSLContext của PinnedHTTPSConnection, chỉ khác ở chỗ bắt tay do `_Wait` làm (http.client gọi `wrap_socket` ngay sau khi
    nối TCP xong)."""

    def __init__(self, context: Any, wait: _Wait) -> None:
        self.context, self.wait = context, wait

    def wrap_socket(self, sock: Any, server_hostname: str | None = None) -> Any:
        wrapped = self.context.wrap_socket(sock, server_hostname=server_hostname, do_handshake_on_connect=False)
        self.wait.handshake(wrapped)
        return wrapped


def waking(computer: str) -> dict[str, Any] | None:
    """Máy đang được chờ dậy (cho giao diện): lúc bắt đầu chờ, hạn chờ, đi đường nào."""
    with _WAKE_LOCK:
        asleep = [wait for wait in _waits.get(computer, []) if wait.asleep]
    if not asleep:
        return None
    first = min(asleep, key=lambda wait: wait.started)
    return {"since": first.started, "until": first.started + first.limit, "via": "bluetooth" if first.bluetooth else "wifi"}


def stop_waiting(computer: str) -> None:
    """Người dùng thôi chờ máy này dậy: bỏ các lần nối đang chờ, và một lúc không tự chờ lại ở nền."""
    with _WAKE_LOCK:
        _quiet[computer] = time.monotonic()
        pending = list(_waits.get(computer, []))
    for wait in pending:
        wait.cancel()


def _quiet_now(computer: str) -> bool:
    with _WAKE_LOCK:
        return time.monotonic() - _quiet.get(computer, -QUIET_SECONDS) < QUIET_SECONDS


def _dial(endpoint: Endpoint, timeout: float, *, wake: bool = False) -> tls.PinnedHTTPSConnection:
    """Nối + bắt tay + kiểm vân tay, CHƯA gửi byte nào. `wake`: máy kia có thể đang ngủ - xem `_Wait`."""
    connection = tls.PinnedHTTPSConnection(endpoint.host, endpoint.port, expected=endpoint.fingerprint, timeout=timeout)
    wait = _Wait(endpoint) if wake and endpoint.computer else None
    if wait is not None:
        connection._context = _WakingContext(connection._context, wait)  # type: ignore[attr-defined] - SSLContext của http.client
    try:
        connection.connect()
    except BaseException as error:
        connection.close()
        if wait is not None and (reason := wait.reason(error)):
            raise RemoteError(reason) from error
        raise
    if endpoint.target:
        route.mark_up(endpoint.target)
    return connection


def _connect(endpoint: Endpoint, timeout: float, *, wake: bool = False) -> tls.PinnedHTTPSConnection:
    """Nối tới máy kia. Đường Wi-Fi hỏng lúc nối (không phải lệch vân tay - lệch vân tay là lỗi, không lùi) mà máy kia có đường
    Bluetooth thì đánh dấu Wi-Fi hỏng (các yêu cầu sau đi thẳng Bluetooth) và nối lại qua đường hầm. Chỉ lùi khi CHƯA gửi byte
    nào: yêu cầu ghi không bao giờ chạy hai lần. Máy đang ngủ (`_Wait`) không phải Wi-Fi hỏng: không lùi."""
    try:
        return _dial(endpoint, timeout, wake=wake)
    except tls.PinError:
        raise
    except OSError:
        if endpoint.target:
            route.mark_down(endpoint.target)
        if not endpoint.fallback:
            if endpoint.computer and endpoint.target:
                _look_for_bluetooth(endpoint.computer)  # lần sau (nếu tìm ra) đi Bluetooth
            raise
        return _dial(_tunnel(endpoint.fallback, endpoint.fingerprint, endpoint.computer), timeout, wake=wake)


LOOK_SECONDS = 120  # tìm địa chỉ Bluetooth theo tên: mỗi máy không quá hai phút một lần
_looked: dict[str, float] = {}


def _look_for_bluetooth(computer: str) -> None:
    """Máy đã ghép qua Wi-Fi mà Wi-Fi vừa hỏng, chưa biết địa chỉ Bluetooth của nó (điện thoại Android 8+ không tự báo được):
    ở nền, tìm trong thiết bị đã ghép ở Windows cái trùng tên máy ấy rồi ghi `bt` vào computers.json - từ lần sau Wi-Fi hỏng
    thì đi Bluetooth. Không bao giờ chặn người gọi."""
    if _COMPUTERS is None:
        return
    with _RECORD_LOCK:
        now = time.monotonic()
        if now - _looked.get(computer, -LOOK_SECONDS) < LOOK_SECONDS:
            return
        _looked[computer] = now
    threading.Thread(target=_match_paired, args=(computer,), name="bt-paired-lookup", daemon=True).start()


def _match_paired(computer: str) -> None:
    entry = _COMPUTERS.get(computer) if _COMPUTERS is not None else None
    if entry is None or _bluetooth_of(entry):
        return
    try:
        devices = bluetooth.paired_devices()
        # Windows lưu tên Bluetooth người dùng đặt cho điện thoại, thường khác tên máy ở Wi-Fi: khớp tên Bluetooth điện thoại báo
        # trước, tên máy sau.
        address = ""
        for name in (str(entry.get("btName") or ""), str(entry.get("name") or "")):
            if address := bluetooth.match_by_name(name, devices):
                break
    except Exception:  # noqa: BLE001 - danh sách của Windows hỏng kiểu gì cũng chỉ là "chưa tìm ra"
        return
    if address:
        _COMPUTERS.note(computer, bt=address)


def _read(response: http.client.HTTPResponse, size: int | None = None) -> bytes:
    """Đọc thân trả lời; đứt giữa chừng (máy kia tắt, rớt mạng) là `RemoteError` như lúc không kết nối được."""
    try:
        return response.read() if size is None else response.read(size)
    except (OSError, http.client.HTTPException) as error:
        raise RemoteError(UNREACHABLE) from error


@contextmanager
def _open(endpoint: Endpoint, method: str, path: str, token: str, body: dict[str, Any] | None = None,
          timeout: float = TIMEOUT, upload: tuple[Path, str] | None = None,
          wake: bool = False, extra: dict[str, str] | None = None) -> Iterator[tuple[http.client.HTTPResponse, str]]:
    """Một yêu cầu qua TLS ghim vân tay, thân trả lời CHƯA đọc: (trả lời, vân tay chứng chỉ máy kia đã đưa ra). Máy kia trả lỗi
    thì `RemoteError` mang câu của nó và mã trạng thái. `upload`: (file, kiểu nội dung) gửi làm thân thay cho JSON. `wake`:
    máy kia đang ngủ thì chờ nó dậy (`_Wait`)."""
    if endpoint.fingerprint == "":
        raise RemoteError("Máy này chưa ghi vân tay của máy kia - ghép lại với máy kia")
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    headers.update(extra or {})
    if data is not None:
        headers["Content-Type"] = "application/json"
    connection: tls.PinnedHTTPSConnection | None = None
    try:
        try:
            connection = _connect(endpoint, timeout, wake=wake)
            if upload is not None:
                headers.update({"Content-Type": upload[1], "Content-Length": str(upload[0].stat().st_size)})
                with upload[0].open("rb") as handle:
                    connection.request(method, path, body=handle, headers=headers)
            else:
                connection.request(method, path, body=data, headers=headers)
            response = connection.getresponse()
        except tls.PinError as error:
            raise RemoteError("Chứng chỉ của máy kia đã khác lúc ghép - máy kia cài lại ABook, hoặc có ai chen vào mạng. "
                              "Nếu chắc đó vẫn là máy của anh, gỡ rồi ghép lại") from error
        except (OSError, http.client.HTTPException) as error:
            raise RemoteError(_unreachable(endpoint)) from error
        if response.status >= 400:
            try:
                message = json.loads(_read(response).decode("utf-8")).get("error")
            except (ValueError, AttributeError):
                message = ""
            raise RemoteError(message or f"Máy kia trả lỗi {response.status}", status=response.status)
        yield response, connection.peer_fingerprint
    finally:
        if connection is not None:
            connection.close()


def _exchange(endpoint: Endpoint, method: str, path: str, token: str, body: dict[str, Any] | None = None,
              timeout: float = TIMEOUT, wake: bool = False) -> tuple[bytes, str]:
    """Một yêu cầu qua TLS ghim vân tay: (thân trả lời, vân tay chứng chỉ máy kia đã đưa ra)."""
    with _open(endpoint, method, path, token, body, timeout, wake=wake) as (response, seen):
        return _read(response), seen


def _request(endpoint: Endpoint, method: str, path: str, token: str, body: dict[str, Any] | None = None,
             timeout: float = TIMEOUT, wake: bool = False) -> bytes:
    return _exchange(endpoint, method, path, token, body, timeout, wake=wake)[0]


def _bluetooth_of(entry: dict[str, Any]) -> str:
    """Địa chỉ Bluetooth của máy đã ghép: host "bt:<địa chỉ>" (ghép qua Bluetooth) hay trường `bt` (máy kia báo lúc ghép Wi-Fi)."""
    host = str(entry.get("host") or "")
    return bluetooth.normalize_address(host.removeprefix("bt:") if host.startswith("bt:") else str(entry.get("bt") or ""))


def _bluetooth_name(reply: Any) -> str:
    """Tên Bluetooth máy kia báo (`bluetoothName`: BluetoothAdapter.name của điện thoại, cần quyền "Thiết bị ở gần"); "" nếu không có."""
    value = reply.get("bluetoothName") if isinstance(reply, dict) else None
    return " ".join(value.split())[:80] if isinstance(value, str) else ""


def _routes_bluetooth(reply: Any) -> str:
    """Địa chỉ Bluetooth máy kia báo trong lời đáp ghép / thư viện (`routes.bluetooth`, hay `bt`); "" nếu không có."""
    if not isinstance(reply, dict):
        return ""
    routes = reply.get("routes")
    value = (routes.get("bluetooth") if isinstance(routes, dict) else None) or reply.get("bt")
    return bluetooth.normalize_address(value) if isinstance(value, str) else ""


def _release_bluetooth(gone: dict[str, Any], rest: Any) -> None:
    """Thôi ghép một máy: đóng đường hầm của nó, trừ khi máy khác đã ghép còn dùng đúng địa chỉ ấy."""
    address = _bluetooth_of(gone)
    if address and not any(_bluetooth_of(other) == address for other in rest):
        bluetooth.forget(address)


def _base(entry: dict[str, Any]) -> Endpoint:
    """Gốc để hỏi máy đã ghép, chọn đường như điện thoại (route.py): chỉ có Wi-Fi -> Wi-Fi; chỉ có Bluetooth (ghép bằng địa chỉ
    Bluetooth) -> đường hầm; cả hai -> Wi-Fi khi thông, hỏng thì Bluetooth (và nhớ, thử lại Wi-Fi mỗi phút ở nền). Không bao giờ
    chờ mạng."""
    host, port, fingerprint = str(entry["host"]), int(entry["port"]), str(entry.get("fingerprint") or "")
    computer = str(entry.get("id") or "")
    address = _bluetooth_of(entry)
    if not address:
        return Endpoint(host, port, fingerprint, target=f"{host}:{port}", computer=computer)
    lan = [] if host.startswith("bt:") else [f"{host}:{port}"]
    choice = route.pick(lan, address)
    if choice.lan is None:
        return _tunnel(address, fingerprint, computer)
    return Endpoint(host, port, fingerprint, target=choice.lan, fallback=address, computer=computer)


def refresh(library_root: Path, computers: Computers, *, asked: bool = False) -> dict[str, Any]:
    """Hỏi mọi máy đã ghép thư viện của nó (cùng lúc - một điện thoại đang ngủ không giữ chân máy khác), dựng / cập nhật các
    cuốn ảo. Máy không trả lời: giữ nguyên những gì đã có. Máy đang ngủ thì chờ nó dậy (`_Wait`); vừa thôi chờ / chờ hết hạn
    thì lần hỏi nền bỏ qua máy ấy một lúc, `asked` (người dùng bấm hỏi lại, vừa ghép) thì chờ lại."""
    report: dict[str, Any] = {}
    workers = []
    for public in computers.list():
        if asked:
            with _WAKE_LOCK:
                _quiet.pop(public["id"], None)
        elif _quiet_now(public["id"]):
            continue
        worker = threading.Thread(target=_refresh_computer, args=(library_root, computers, public["id"], report),
                                  name="remote-library", daemon=True)
        worker.start()
        workers.append(worker)
    for worker in workers:
        worker.join()
    return report


def _refresh_computer(library_root: Path, computers: Computers, computer: str, report: dict[str, Any]) -> None:
    entry = computers.get(computer)
    if entry is None:
        return
    try:
        library = json.loads(_request(_base(entry), "GET", "/sync/v1/library", entry["token"], wake=True).decode("utf-8"))
        folder = Path(library_root).expanduser() / REMOTE_FOLDER / _folder(str(library.get("name") or entry["name"]), computer)
        listed = [str(book["id"]) for book in library.get("books") or [] if isinstance(book, dict) and book.get("id")]
        _follow_renamed(entry, computer, folder, set(listed))
        built = {remote["book"]: child for child, manifest in _manifests(folder)
                 if (remote := remote_of(manifest)) and remote["computer"] == computer}
        books = 0
        for book in listed:
            _refresh_book(entry, computer, folder, book, built.get(book))
            books += 1
        # `kind`: máy tính nhận phần sửa của cuốn (POST .../edits, như từ điện thoại); điện thoại chia sẻ thư viện thì không.
        reported = {} if str(entry["host"]).startswith("bt:") else {"bt": _routes_bluetooth(library)}  # máy báo đường Bluetooth của nó
        reported["btName"] = _bluetooth_name(library)
        computers.note(computer, lastSeen=time.time(), error="", name=str(library.get("name") or entry["name"]),
                       kind="computer" if library.get("kind") == "computer" else "phone",
                       **{key: value for key, value in reported.items() if value})
        report[computer] = {"books": books}
    except RemoteError as error:
        computers.note(computer, error=str(error))
        report[computer] = {"error": str(error)}


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


def reachable(entry: dict[str, Any], *, timeout: float = 2.0) -> bool:
    """Máy đã ghép có trả lời ngay lúc này không (cùng lời hỏi nhẹ của `player`; không chờ máy ngủ dậy)."""
    try:
        player(entry, timeout=timeout)
    except (RemoteError, OSError, ValueError):
        return False
    return True


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
    try:
        return _save(Path(package), relative, manifest)
    except RemoteError:
        return None


# ---- tải trọn cuốn về máy này ("Tải về máy", như điện thoại) ---------------------------------------------------------------

DOWNLOAD_FILE = "download.json"  # file nào đã tải theo phiên bản nào của sách (file không có cỡ trong book.json), file máy kia không có
CHUNK = 256 * 1024
_SAFE_NAME = re.compile(r"[A-Za-z0-9_./ \-]+")
_RECORD_LOCK = threading.Lock()
_FILE_LOCKS: dict[str, threading.Lock] = {}


class Cancelled(Exception):
    """Người dùng bấm dừng giữa lúc đang tải một file."""


def _entry_of(book: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """(máy đã ghép giữ cuốn này, mã cuốn ở máy ấy); thôi ghép rồi thì `RemoteError`."""
    remote = remote_of(book)
    entry = _COMPUTERS.get(remote["computer"]) if remote and _COMPUTERS is not None else None
    if entry is None:
        raise RemoteError("Máy này không còn ghép với máy giữ cuốn này - ghép lại rồi thử lại")
    return entry, remote["book"]


def _record(package: Path) -> dict[str, Any]:
    try:
        data = json.loads((package / DOWNLOAD_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    data = data if isinstance(data, dict) else {}
    return {key: data[key] if isinstance(data.get(key), dict) else {} for key in ("files", "absent")}


def _note(package: Path, relative: str, version: Any, *, absent: bool = False) -> None:
    """Ghi file `relative` đã tải (hay máy kia không có) ở phiên bản `version` của sách."""
    with _RECORD_LOCK:
        data = _record(package)
        data["absent" if absent else "files"][relative] = version
        data["files" if absent else "absent"].pop(relative, None)
        temporary = package / (DOWNLOAD_FILE + ".tmp")
        temporary.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        temporary.replace(package / DOWNLOAD_FILE)


def _save(package: Path, relative: str, book: dict[str, Any], *, size: int | None = None,
          progress: Callable[[int], None] | None = None, cancelled: Callable[[], bool] | None = None) -> Path:
    """Tải một file của sách trên máy khác vào thư mục của cuốn: ghi ra `<tên>.part` từng khúc rồi mới đổi tên - đứt giữa chừng thì
    file cũ (nếu có) vẫn nguyên, không bao giờ có file dở mang tên thật. `size`: cỡ book.json ghi (khác thì không nhận). Biết `size` thì
    phần `.part` dở (máy kia tắt giữa chừng, người dùng bấm dừng) được GIỮ và lần sau tải tiếp bằng `Range` - chương lớn trên Wi-Fi yếu
    không phải tải lại từ đầu; máy kia không hiểu `Range` thì tải lại từ đầu. `progress(số byte vừa nhận)`, `cancelled()`: cho việc tải cả
    cuốn. Lỗi: `RemoteError` (hay `Cancelled`); máy kia ngừng trả lời giữa chừng thì nói tên máy ấy (`_cut`)."""
    if not _SAFE_NAME.fullmatch(relative) or ".." in relative:
        raise RemoteError("Tên file lạ trong sách")
    entry, book_key = _entry_of(book)
    target = (package / relative).resolve()
    if not target.is_relative_to(package.resolve()):
        raise RemoteError("Tên file lạ trong sách")
    with _RECORD_LOCK:
        lock = _FILE_LOCKS.setdefault(str(target), threading.Lock())
    with lock:  # bấm nghe đúng chương đang tải nền: một người ghi file `.part`
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + ".part")
        endpoint = _base(entry)
        keep = False
        try:
            have = temporary.stat().st_size if size is not None and temporary.is_file() else 0
            if size is not None and not 0 < have < size:
                have = 0
            with _open(endpoint, "GET", f"/sync/v1/books/{book_key}/files/{quote(relative)}", entry["token"], timeout=FILE_TIMEOUT,
                       extra={"Range": f"bytes={have}-"} if have else None) as (response, _seen):
                if have and not (response.status == 206 and re.match(rf"bytes {have}-", response.getheader("Content-Range") or "")):
                    have = 0  # máy kia gửi cả file (không hiểu Range): bỏ phần dở, tải từ đầu
                expected = response.length
                received = 0
                try:
                    with temporary.open("ab" if have else "wb") as sink:
                        while chunk := _read(response, CHUNK):
                            if cancelled is not None and cancelled():
                                keep = size is not None
                                raise Cancelled
                            sink.write(chunk)
                            received += len(chunk)
                            if progress is not None:
                                progress(len(chunk))
                except RemoteError as problem:
                    if problem.status is None:
                        keep = size is not None
                        raise RemoteError(_cut(endpoint)) from problem
                    raise
                if received < expected if expected is not None else size is not None and have + received < size:
                    keep = size is not None  # đứt giữa chừng mà máy kia đóng êm (tắt máy): phần đã nhận giữ lại cho lần tải tiếp
                    raise RemoteError(_cut(endpoint))
            if size is not None and temporary.stat().st_size != size:
                raise RemoteError("File tải về không đủ - thử lại")
            temporary.replace(target)
        finally:
            if not keep:
                temporary.unlink(missing_ok=True)
    _note(package, relative, book.get("version"))
    return target


def wanted(book: dict[str, Any]) -> list[tuple[str, int | None]]:
    """Mọi file cuốn này cần để nghe trọn khi máy kia đã tắt, kèm cỡ book.json ghi (None khi không ghi): audio + chữ đọc theo của các
    chương đã có, chữ các chương chỉ-có-chữ, dàn nhân vật, câu mẫu giọng, bài nhạc nền. Bìa đã tải lúc dựng cuốn (`_refresh_book`)."""
    files: dict[str, int | None] = {}

    def add(name: Any, size: Any = None) -> None:
        if isinstance(name, str) and name and name not in files:
            files[name] = int(size) if isinstance(size, (int, float)) and not isinstance(size, bool) and size > 0 else None

    for chapter in book.get("chapters") or []:
        if not isinstance(chapter, dict):
            continue
        if chapter.get("available") and chapter.get("file"):
            add(chapter["file"], chapter.get("size"))
            add(chapter.get("script"))
        add(chapter.get("text"))
    add(book.get("cast"))
    for sample in book.get("samples") or []:
        add(sample)
    music = book.get("music") if isinstance(book.get("music"), dict) else {}
    for name, info in (music.get("tracks") or {}).items() if isinstance(music.get("tracks"), dict) else ():
        add(name, info.get("size") if isinstance(info, dict) else None)
    return list(files.items())


def missing(package: Path, book: dict[str, Any]) -> list[tuple[str, int | None]]:
    """Các file trong `wanted` máy này còn thiếu: chưa có, khác cỡ book.json ghi (chương thu lại), hay - file không ghi cỡ - tải
    từ phiên bản trước của sách. File máy kia báo không có (ở đúng phiên bản này) thì thôi."""
    record, version = _record(package), book.get("version")
    out = []
    for relative, size in wanted(book):
        if record["absent"].get(relative, ...) == version:
            continue
        try:
            found = (package / relative).stat().st_size
        except OSError:
            out.append((relative, size))
            continue
        if (found != size) if size is not None else record["files"].get(relative, ...) != version:
            out.append((relative, size))
    return out


def _part_size(package: Path, relative: str, size: int | None) -> int:
    """Phần `.part` dở của một file (lần tải trước đứt giữa chừng, `_save` giữ lại để tải tiếp bằng Range): số byte đã có, 0 khi không dùng được."""
    try:
        have = (package / (relative + ".part")).stat().st_size
    except OSError:
        return 0
    return have if size is not None and 0 < have < size else 0


def _bytes_done(package: Path, files: list[tuple[str, int | None]], left: list[tuple[str, int | None]]) -> int:
    """Byte đã có thật: các file đủ + phần dở của các file còn thiếu."""
    total = sum(size or 0 for _name, size in files)
    return total - sum(size or 0 for _name, size in left) + sum(_part_size(package, name, size) for name, size in left)


class Downloads:
    """Tải trọn những cuốn "Trên máy khác" về máy này ở nền ("Tải về máy" - như điện thoại tải sách của máy tính): từng file một,
    file đã có (đúng cỡ, đúng phiên bản) thì bỏ qua, nên dừng giữa chừng - người dùng bấm dừng, máy kia tắt, app đóng - rồi bấm tải
    tiếp chỉ lấy phần còn thiếu. Xong thì cuốn nghe được trọn khi máy kia đã tắt (`packages._file` thấy file trên đĩa)."""

    def __init__(self) -> None:
        self._jobs: dict[str, dict[str, Any]] = {}
        self._auto: dict[str, int] = {}  # số lần tự tải tiếp của mỗi cuốn (từ lần người dùng bấm gần nhất)
        self._lock = threading.Lock()

    def status(self, package: Path) -> dict[str, Any]:
        """{"state": "none" | "running" | "done" | "failed" | "cancelled", "files", "filesDone", "bytes", "bytesDone", "error"}.
        Không đang tải: tính theo đĩa - đủ file là "done" kể cả sau khi mở lại app."""
        from .packages import manifest

        package = Path(package).resolve()
        with self._lock:
            job = self._jobs.get(str(package))
            if job is not None and job["state"] == "running":
                return {key: value for key, value in job.items() if key not in ("stop", "computer")}
        book = manifest(package)
        files, left = wanted(book), missing(package, book)
        total = sum(size or 0 for _name, size in files)
        state = "done" if not left else job["state"] if job is not None and job["state"] in ("failed", "cancelled") else "none"
        return {"state": state, "files": len(files), "filesDone": len(files) - len(left), "bytes": total,
                "bytesDone": _bytes_done(package, files, left), "error": job["error"] if state == "failed" else "",
                # đứt vì mất kết nối với máy kia (không phải lỗi ổ đĩa): máy kia lên lại thì tự tải tiếp (`resume_interrupted`)
                "retry": state == "failed" and bool(job.get("retry"))}

    def start(self, package: Path, *, wait: bool = False, auto: bool = False) -> dict[str, Any]:
        """Bắt đầu (hay tải tiếp) cả cuốn; đang tải thì thôi. `wait`: tải ngay trong luồng này (bài thử). `auto`: máy tự tải tiếp
        (`resume_interrupted`), không phải người dùng bấm."""
        from .packages import manifest

        package = Path(package).resolve()
        if not auto:
            self._auto.pop(str(package), None)
        book = manifest(package)
        _entry_of(book)  # thôi ghép rồi: nói ngay, không mở việc nền
        with self._lock:
            running = self._jobs.get(str(package))
            if running is not None and running["state"] == "running":
                return {key: value for key, value in running.items() if key not in ("stop", "computer")}
            files, left = wanted(book), missing(package, book)
            total = sum(size or 0 for _name, size in files)
            job = {"state": "running", "files": len(files), "filesDone": len(files) - len(left), "bytes": total,
                   "bytesDone": _bytes_done(package, files, left), "error": "", "stop": threading.Event(),
                   "computer": (remote_of(book) or {}).get("computer", "")}
            self._jobs[str(package)] = job
        if wait:
            self._run(package, book, left, job)
        else:
            threading.Thread(target=self._run, args=(package, book, left, job), name="remote-download", daemon=True).start()
        return self.status(package)

    def resume_interrupted(self, package: Path, reachable: Callable[[str], bool], *, every: float = 10.0, limit: int = 5) -> bool:
        """Lần tải đứt vì mất kết nối với máy kia (`retry`): máy kia trả lời lại (`reachable(mã máy)`) thì tải tiếp luôn, không đợi người dùng
        bấm - như phần sửa tự gửi lại khi tới được máy ấy. Hỏi nhiều nhất mỗi `every` giây, và tối đa `limit` lần tự tải tiếp cho tới khi người
        dùng bấm. Trả True nếu vừa bắt đầu tải tiếp."""
        key = str(Path(package).resolve())
        with self._lock:
            job = self._jobs.get(key)
            if job is None or job["state"] != "failed" or not job.get("retry") or self._auto.get(key, 0) >= limit:
                return False
            if time.monotonic() - job.get("probed", float("-inf")) < every:
                return False
            job["probed"] = time.monotonic()
            computer = job["computer"]
        if not reachable(computer):
            return False
        self._auto[key] = self._auto.get(key, 0) + 1
        try:
            self.start(Path(key), auto=True)
        except RemoteError:
            return False
        return True

    def cancel(self, package: Path) -> dict[str, Any]:
        """Dừng tải: các file đã xong giữ lại, file đang tải dở giữ phần đã nhận để tải tiếp."""
        with self._lock:
            job = self._jobs.get(str(Path(package).resolve()))
            if job is not None:
                job["stop"].set()
        return self.status(package)

    def cancel_computer(self, computer: str) -> None:
        """Thôi ghép một máy: dừng mọi cuốn của máy ấy đang tải (thư mục của chúng sắp bị xoá)."""
        with self._lock:
            for job in self._jobs.values():
                if job["computer"] == computer:
                    job["stop"].set()

    def _run(self, package: Path, book: dict[str, Any], left: list[tuple[str, int | None]], job: dict[str, Any]) -> None:
        def received(count: int) -> None:
            job["bytesDone"] += count

        state, error = "done", ""
        try:
            for relative, size in left:
                if job["stop"].is_set():
                    raise Cancelled
                before = job["bytesDone"] - _part_size(package, relative, size)  # `bytesDone` đã tính phần dở của file này
                try:
                    _save(package, relative, book, size=size, progress=received, cancelled=job["stop"].is_set)
                except RemoteError as problem:
                    if problem.status != 404:
                        raise
                    _note(package, relative, book.get("version"), absent=True)  # máy kia không có file này: thiếu nó vẫn nghe được
                job["bytesDone"] = before + (size or 0)
                job["filesDone"] += 1
        except Cancelled:
            state = "cancelled"
        except RemoteError as problem:
            state, error = "failed", str(problem)
            job["retry"] = problem.status is None  # không tới được / đứt giữa chừng: thử lại được khi máy kia lên
        except OSError as problem:
            state, error = "failed", f"Không ghi được vào ổ đĩa của máy này ({problem.strerror or problem})"
        with self._lock:
            job["state"], job["error"] = state, error


# ---- gửi phần sửa về máy giữ sách (như điện thoại gửi về máy tính - EditsSync.kt, edits_inbox.py) -----------------------

EDITS_STATE = "sync_edits.json"  # = EditsSync.STATE_FILE: kết quả lần gửi gần nhất
_SEND_LOCK = threading.Lock()


def sends_edits(book: dict[str, Any]) -> bool:
    """Cuốn này của một MÁY TÍNH đã ghép: sửa được ở máy này, phần sửa gửi về máy ấy (máy ấy nhận như từ điện thoại - hộp thư,
    xung đột, quyền điều khiển sản xuất). Cuốn của điện thoại chia sẻ thư viện thì không: sửa ở điện thoại ấy."""
    remote = remote_of(book)
    entry = _COMPUTERS.get(remote["computer"]) if remote and _COMPUTERS is not None else None
    return bool(entry) and entry.get("kind") == "computer"


def _last_sent(package: Path) -> dict[str, Any] | None:
    try:
        data = json.loads((package / EDITS_STATE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def edits_state(package: Path) -> dict[str, Any]:
    """`editsSync` của cuốn (cùng hình dạng điện thoại trả - ui/src/shared/editsSync.ts): số thay đổi CHƯA gửi (gửi xong là gỡ khỏi
    lớp sửa, nên số còn lại chính là phần chưa tới máy kia) và kết quả lần gửi gần nhất."""
    last = _last_sent(package)
    return {"pending": pending_changes(package), "last": {key: value for key, value in last.items() if key != "kept"} if last else None}


def _sent_marks(package: Path) -> dict[str, Any]:
    """`book_edits.sent_marks` của các lần gửi trước (nằm trong `sync_edits.json`, khoá `kept`): cách đọc, danh sách phát đã tới máy kia mà vẫn nằm ở đây."""
    kept = (_last_sent(package) or {}).get("kept")
    return kept if isinstance(kept, dict) else {}


def pending_changes(package: Path, edits: dict[str, Any] | None = None) -> int:
    """Số thay đổi CHƯA tới máy kia: lớp sửa trừ phần đã gửi mà vẫn giữ lại ở đây (cách đọc, nhạc đã chọn), cộng phần đã gửi rồi người nghe
    bỏ đi mà máy kia chưa biết (`book_edits.removed_marks`)."""
    edits = book_edits.load(package) if edits is None else edits
    marks = _sent_marks(package)
    return book_edits.count(book_edits.unmarked(edits, marks)) + book_edits.count_removed(book_edits.removed_marks(edits, marks))


def _remember_send(package: Path, state: dict[str, Any]) -> None:
    if "kept" not in state and _sent_marks(package):
        state = {**state, "kept": _sent_marks(package)}  # lần gửi lỗi không làm quên cái đã gửi trước đó
    temporary = package / (EDITS_STATE + ".tmp")
    temporary.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    temporary.replace(package / EDITS_STATE)


def send_edits(package: Path) -> dict[str, Any]:
    """Gửi lớp sửa của cuốn về máy giữ nó - đúng gói điện thoại gửi (edits.json, bìa, bài nhạc ghim; edits_inbox.read_package kiểm)
    qua `POST /sync/v1/books/<mã>/edits`. Máy kia nhận xong: lấy lại bản mới của sách (đã mang các sửa ấy) rồi gỡ đúng những gì đã gửi
    khỏi lớp sửa của máy này (`book_edits.subtract`). Lỗi: ghi lại (lớp sửa giữ nguyên, lần sau gửi lại) rồi `RemoteError`.
    Trả `edits_state` mới."""
    from .edits_inbox import MAX_PACKAGE_BYTES, sender_label
    from .packages import manifest

    package = Path(package).resolve()
    with _SEND_LOCK:
        book = manifest(package)
        edits = book_edits.load(package)
        marks = _sent_marks(package)
        removed = book_edits.removed_marks(edits, marks)  # đã gửi rồi người nghe bỏ đi: báo máy kia gỡ theo
        if book_edits.is_empty(edits) and not removed:
            return edits_state(package)
        outgoing = package / ".edits_out.zip"
        try:
            try:
                entry, book_key = _entry_of(book)
                members = book_edits.layer_files(package, edits)
                if removed:
                    members[book_edits.REMOVED_FILE] = book_edits.dump_removed(removed)
                cover = members[book_edits.EDITS_COVER].read_bytes() if book_edits.EDITS_COVER in members else None
                with zipfile.ZipFile(outgoing, "w", zipfile.ZIP_STORED) as archive:
                    for name, item in members.items():
                        if isinstance(item, bytes):
                            archive.writestr(name, item)
                        else:
                            archive.write(item, name)
                if outgoing.stat().st_size > MAX_PACKAGE_BYTES:
                    raise RemoteError("Phần sửa quá lớn để gửi một lần - bớt bài nhạc đã chọn rồi gửi lại")
                with _open(_base(entry), "POST", f"/sync/v1/books/{book_key}/edits", entry["token"], timeout=120,
                           upload=(outgoing, "application/zip")) as (response, _seen):
                    reply = json.loads(_read(response).decode("utf-8"))
                if not isinstance(reply, dict):
                    raise ValueError
            except book_edits.EditsError as error:
                raise RemoteError(str(error)) from error
            except (ValueError, UnicodeDecodeError) as error:
                raise RemoteError("Máy kia trả lời không hiểu được") from error
            except OSError as error:
                raise RemoteError(f"Không đóng được gói phần sửa ({error.strerror or error})") from error
        except RemoteError as error:
            _remember_send(package, {"state": "error", "at": time.time(), "error": str(error)})
            raise
        finally:
            outgoing.unlink(missing_ok=True)
        _reload(package, entry, book)  # bản mới của máy kia đã mang các sửa: lấy về TRƯỚC khi gỡ lớp sửa để không chớp bản cũ
        book_edits.subtract(package, edits, cover)
        _remember_send(package, {
            "state": "sent", "at": time.time(), "kept": book_edits.sent_marks(edits, book_edits.forget_marks(marks, removed)),
            **{key: int(reply.get(key) or 0) for key in ("applied", "skipped", "requests", "waiting", "skippedWishes")},
            "conflicts": [sender_label(item, entry["name"]) for item in reply.get("conflicts") or [] if isinstance(item, dict) and item.get("label")],
        })
        return edits_state(package)


def _reload(package: Path, entry: dict[str, Any], book: dict[str, Any]) -> None:
    """Lấy lại book.json + bìa của cuốn từ máy kia, và chữ đọc theo / dàn nhân vật đã giữ trên máy này (tên nhân vật, tên chương
    trong đó vừa đổi theo phần sửa). Không tới được máy kia thì thôi - lần làm mới thư viện sau lấy."""
    remote = remote_of(book) or {}
    try:
        _refresh_book(entry, remote["computer"], package.parent, remote["book"], package)
        fresh = json.loads((package / MANIFEST).read_text(encoding="utf-8"))
    except (RemoteError, ValueError, KeyError, OSError):
        return
    for relative, size in wanted(fresh):
        if size is None and (package / relative).is_file():
            try:
                _save(package, relative, fresh)
            except RemoteError:
                return
