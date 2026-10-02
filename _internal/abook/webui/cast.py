"""Phát sang loa / TV trong mạng nhà bằng DLNA (UPnP AV MediaRenderer) - 01-10. Chủ sách không có loa hay TV để thử
("giả lập hay gì đó đi"), nên mọi phép thử chạy với thiết bị giả `scripts/fake_renderer.py`, trong pytest lẫn trên mạng thật.

Máy tính là bộ não, thiết bị chỉ phát một file: tìm thiết bị bằng SSDP (M-SEARCH ra từng card mạng), đọc mô tả của nó,
điều khiển bằng SOAP AVTransport - đưa ĐƯỜNG DẪN một chương (SetAVTransportURI), Play / Pause / Seek - rồi hỏi nó mỗi
giây đang ở đâu để lưu chỗ nghe và tự sang chương sau khi hết chương. Thiết bị tự tải audio qua một cổng riêng
(`CastMedia`) chỉ phục vụ đúng file đã đưa, dưới một mã ngẫu nhiên 128 bit: loa, TV không ghép mã 6 số như điện thoại.

Mỗi giao thức một "backend" (`Backend`): DLNA ở đây, Google Cast (Chromecast, Google TV, loa Nest) ở `gcast.py`. Phiên phát,
vòng hỏi mỗi giây, lưu chỗ nghe, sang chương, nhận ra bị chiếm máy đều chung - backend chỉ nói chuyện với một thiết bị.

Trong `/api/remote` mỗi thiết bị là một "máy" như điện thoại (`via` cast, `kind` speaker | tv): thanh "Đang phát trên…",
nút "Phát trên…" và "Nghe trên máy này" dùng chung đường với điện thoại và máy đã ghép (server.remote_view/remote_send).

An toàn - trả lời SSDP và mô tả thiết bị là dữ liệu từ mạng LAN: chỉ đọc mô tả ở ĐÚNG địa chỉ IP đã trả lời và chỉ gửi
SOAP tới địa chỉ ấy (một máy lạ không khiến được máy này gọi tới 127.0.0.1 hay máy khác), không theo chuyển hướng, không
đi qua proxy, XML có trần cỡ và không nhận DOCTYPE / ENTITY, mọi chữ đều cắt ngắn.
"""
from __future__ import annotations

import hashlib
import ipaddress
import re
import secrets
import select
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, NamedTuple
from xml.etree import ElementTree
from xml.sax.saxutils import escape

SSDP_GROUP = ("239.255.255.250", 1900)
MEDIA_RENDERER = "urn:schemas-upnp-org:device:MediaRenderer:1"
AV_TRANSPORT = "urn:schemas-upnp-org:service:AVTransport:"
RENDERING_CONTROL = "urn:schemas-upnp-org:service:RenderingControl:"
AGENT = "ABook UPnP/1.0 DLNADOC/1.50"
# Cho tua bằng Range (OP=01) và phát theo luồng. Không ghi DLNA.ORG_PN: chương hiện là MP3 48 kHz 192 kbps (vừa hồ sơ
# "MP3"), nhưng TV khó tính thấy PN sai thì từ chối hẳn còn thiếu PN thì vẫn phát - không đặt cược vào định dạng mãi thế.
DLNA_FEATURES = "DLNA.ORG_OP=01;DLNA.ORG_FLAGS=01700000000000000000000000000000"
MAX_XML = 256 * 1024
TYPES = {".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".wav": "audio/wav", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
         ".png": "image/png"}

SEARCH_SECONDS = 30.0  # có người đang xem: tìm lại thiết bị mỗi chừng ấy giây
FORGET_SECONDS = 95.0  # ba lượt tìm liền không thấy thì thôi hiện (trừ thiết bị đang phát sách)
WANTED_SECONDS = 15.0  # như PeerPlayers: chỉ tìm khi giao diện hỏi /api/remote trong 15 giây qua
PLAYING_POLL = 1.0
IDLE_POLL = 3.0
END_SLACK = 4.0  # thiết bị về STOPPED khi đã tới chừng ấy giây cuối chương = hết chương, sang chương sau
GRACE_SECONDS = 6.0  # vừa đưa chương / bấm phát: thiết bị còn báo STOPPED một lúc trước khi chạy
SAVE_SECONDS = 10.0
LOST_SECONDS = 60.0  # thiết bị im lặng chừng ấy giây giữa lúc phát: coi như đã tắt, bỏ phiên

# Lỗi UPnP AVTransport (UPnP-av-AVTransport-v1 2.4) nói bằng lời người nghe hiểu.
UPNP_ERRORS = {
    401: "thiết bị không có lệnh này",
    402: "thiết bị không nhận lệnh này",
    701: "thiết bị chưa sẵn sàng cho lệnh này",
    702: "thiết bị chưa có gì để phát",
    710: "thiết bị không tua được",
    711: "vị trí tua nằm ngoài chương",
    714: "thiết bị không phát được loại audio này",
    716: "thiết bị không tải được audio từ máy này - kiểm tường lửa Windows (cho ABook dùng mạng riêng)",
    717: "thiết bị không đổi được tốc độ",
}
TV_WORDS = re.compile(r"\b(tv|television|bravia|webos|tizen|roku|fire ?tv|google ?tv|android ?tv|smart ?tv)\b", re.IGNORECASE)
# Máy Windows bật "Cho phép điều khiển Trình phát từ xa" (Windows Media Player) - gặp thật trong mạng nhà chủ sách 01-10.
MEDIA_WORDS = re.compile(r"\b(windows (digital )?media|windows media player|microsoft)\b", re.IGNORECASE)


class CastError(Exception):
    """Lỗi nói được với người dùng (tiếng Việt); `code` là mã lỗi UPnP khi thiết bị trả lỗi."""

    def __init__(self, message: str, code: int = 0) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class Renderer:
    id: str  # 12 hex, ổn định theo UDN - nằm trong đường /api/remote/<id> như mã điện thoại
    name: str
    kind: str  # "tv" | "media" (máy tính bật trình phát nhận lệnh từ xa) | "speaker" - chỉ để chọn biểu tượng
    host: str  # địa chỉ IP đã trả lời SSDP / mDNS; mô tả và lệnh chỉ đi tới đây
    location: str = ""
    av_url: str = ""
    av_type: str = ""  # serviceType đầy đủ (có số phiên bản) - SOAPACTION phải khớp đúng
    rc_url: str = ""
    rc_type: str = ""
    protocol: str = "dlna"  # "dlna" | "gcast" (Google Cast, gcast.py): chọn backend
    port: int = 0  # cổng điều khiển (Cast: cổng SRV, thường 8009); DLNA đi theo av_url


def _clean(value: Any, limit: int = 120) -> str:
    return re.sub(r"[\x00-\x1f\x7f]+", " ", str(value or "")).strip()[:limit]


def _lan(host: str) -> bool:
    """IPv4 trong nhà: mạng riêng, link-local, loopback (bài thử) - thiết bị phát không nằm ở Internet."""
    try:
        address = ipaddress.IPv4Address(host)
    except ValueError:
        return False
    return address.is_private or address.is_link_local or address.is_loopback


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:  # chuyển hướng = lối vòng tới máy khác: không theo
        return None


_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())


def _read(response: Any) -> bytes:
    data = response.read(MAX_XML + 1)
    if len(data) > MAX_XML:
        raise CastError("thiết bị trả lời lạ")
    return data


def _xml(data: bytes) -> ElementTree.Element:
    if len(data) > MAX_XML or re.search(rb"<!\s*(DOCTYPE|ENTITY)", data, re.IGNORECASE):
        raise CastError("thiết bị trả lời lạ")
    try:
        return ElementTree.fromstring(data)
    except ElementTree.ParseError as error:
        raise CastError("thiết bị trả lời lạ") from error


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _children(element: ElementTree.Element, name: str) -> list[ElementTree.Element]:
    return [child for child in element if _local(child.tag) == name]


def _text(element: ElementTree.Element, name: str) -> str:
    found = _children(element, name)
    return (found[0].text or "").strip() if found else ""


def clock(seconds: float) -> str:
    """Giờ kiểu UPnP: H:MM:SS."""
    whole = max(0, round(seconds))
    return f"{whole // 3600}:{whole // 60 % 60:02d}:{whole % 60:02d}"


def seconds_of(value: str) -> float:
    """"H+:MM:SS[.F+]" hay "H+:MM:SS.F0/F1" -> giây; "NOT_IMPLEMENTED", rỗng, lạ -> 0."""
    match = re.fullmatch(r"\s*(\d+):(\d{1,2}):(\d{1,2})(?:\.(\d+)(?:/(\d+))?)?\s*", value or "")
    if not match:
        return 0.0
    hours, minutes, whole, fraction, divisor = match.groups()
    total = int(hours) * 3600 + int(minutes) * 60 + int(whole)
    if fraction:
        total += int(fraction) / int(divisor) if divisor and int(divisor) else float(f"0.{fraction}")
    return float(total)


# ---- tìm thiết bị ----------------------------------------------------------------------------------------------


def _search_message(wait: int) -> bytes:
    return ("M-SEARCH * HTTP/1.1\r\n"
            "HOST: 239.255.255.250:1900\r\n"
            'MAN: "ssdp:discover"\r\n'
            f"MX: {wait}\r\n"
            f"ST: {MEDIA_RENDERER}\r\n"
            f"USER-AGENT: {AGENT}\r\n\r\n").encode("ascii")


def _location(data: bytes) -> str:
    """LOCATION của một trả lời SSDP cho thiết bị phát; "" nếu không phải."""
    lines = data.decode("utf-8", "replace").split("\r\n")
    if not lines or not re.match(r"HTTP/1\.[01] 200", lines[0]):
        return ""
    headers = {}
    for line in lines[1:]:
        name, separator, value = line.partition(":")
        if separator:
            headers[name.strip().lower()] = value.strip()
    if "MediaRenderer" not in headers.get("st", "") and "AVTransport" not in headers.get("st", ""):
        return ""
    return headers.get("location", "")[:500]


def probe(message: bytes, group: tuple[str, int], timeout: float, accept: Callable[[bytes, str], list[tuple[Any, Any]]],
          *, addresses: Iterable[str] | None = None, targets: Iterable[tuple[str, int]] = (),
          ttl: int = 2) -> list[tuple[Any, Any]]:
    """Gửi `message` (UDP) tới nhóm multicast `group` ra từng card mạng (hai lần - UDP trên Wi-Fi hay rơi) và thẳng tới
    `targets` (bài thử, thiết bị giả); gom trả lời trong `timeout` giây. `accept(dữ liệu, địa chỉ đã trả lời)` -> các cặp
    (khoá, giá trị); khoá trùng thì giữ lần đầu. Dùng chung cho SSDP (DLNA) ở đây và mDNS (Google Cast, gcast.py)."""
    if addresses is None:
        from .sync import local_addresses

        addresses = [address for address in local_addresses() if _lan(address)]
    sockets: list[socket.socket] = []
    sends: list[tuple[socket.socket, tuple[str, int]]] = []
    for address in addresses:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, ttl)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(address))
            sock.bind((address, 0))
        except OSError:
            continue
        sockets.append(sock)
        sends.append((sock, group))
    targets = list(targets)
    if targets:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        loopback = all(ipaddress.IPv4Address(host).is_loopback for host, _port in targets)
        sock.bind(("127.0.0.1" if loopback else "0.0.0.0", 0))
        sockets.append(sock)
        sends.extend((sock, target) for target in targets)
    found: dict[Any, Any] = {}
    try:
        start = time.monotonic()
        rounds = [start, start + min(0.6, timeout / 3)]
        deadline = start + timeout
        while sockets:
            now = time.monotonic()
            while rounds and rounds[0] <= now:
                rounds.pop(0)
                for sock, target in sends:
                    try:
                        sock.sendto(message, target)
                    except OSError:
                        pass
            if now >= deadline:
                break
            wait = min(deadline, rounds[0] if rounds else deadline) - now
            readable, _, _ = select.select(sockets, [], [], max(0.0, wait))
            for sock in readable:
                try:
                    data, (source, _port) = sock.recvfrom(8192)
                except OSError:  # Windows: ICMP "cổng đóng" của lần gửi thẳng trước trả về ở đây
                    continue
                for key, value in accept(data, source):
                    found.setdefault(key, value)
    finally:
        for sock in sockets:
            sock.close()
    return list(found.items())


def search(timeout: float = 2.0, *, addresses: Iterable[str] | None = None,
           targets: Iterable[tuple[str, int]] = ()) -> list[tuple[str, str]]:
    """M-SEARCH tìm thiết bị phát ra từng card mạng (multicast) và thẳng tới `targets` (bài thử, thiết bị giả); gom trả
    lời trong `timeout` giây -> [(LOCATION, địa chỉ đã trả lời)]."""
    def accept(data: bytes, source: str) -> list[tuple[Any, Any]]:
        location = _location(data)
        return [(location, source)] if location else []

    return probe(_search_message(max(1, int(timeout))), SSDP_GROUP, timeout, accept, addresses=addresses, targets=targets)


def describe(location: str, host: str, *, timeout: float = 3.0) -> Renderer | None:
    """Đọc mô tả thiết bị ở `location` - chỉ khi nó nằm đúng ở `host` (địa chỉ đã trả lời SSDP). None: không phải thiết
    bị phát được (không có AVTransport), hay địa chỉ điều khiển trỏ sang máy khác."""
    parts = urllib.parse.urlsplit(location)
    if parts.scheme != "http" or parts.hostname != host or not _lan(host):
        return None
    try:
        with _OPENER.open(location, timeout=timeout) as response:
            root = _xml(_read(response))
    except (OSError, ValueError) as error:
        raise CastError("không đọc được mô tả thiết bị") from error
    base = _text(root, "URLBase") or location
    queue = _children(root, "device")
    while queue:
        device = queue.pop(0)
        services: dict[str, str] = {}
        for service_list in _children(device, "serviceList"):
            for service in _children(service_list, "service"):
                url = urllib.parse.urljoin(base, _text(service, "controlURL"))
                target = urllib.parse.urlsplit(url)
                if target.scheme == "http" and target.hostname == host:
                    services[_text(service, "serviceType")] = url
        av = next(((kind, url) for kind, url in services.items() if kind.startswith(AV_TRANSPORT)), None)
        if av is None:
            for nested in _children(device, "deviceList"):
                queue.extend(_children(nested, "device"))
            continue
        rc = next(((kind, url) for kind, url in services.items() if kind.startswith(RENDERING_CONTROL)), ("", ""))
        name = _clean(_text(device, "friendlyName"), 80) or host
        model = " ".join(_text(device, field) for field in ("manufacturer", "modelName", "modelDescription"))
        udn = _text(device, "UDN") or location
        kind = ("tv" if TV_WORDS.search(f"{name} {model}") else "media" if MEDIA_WORDS.search(model)
                else "speaker")
        return Renderer(id=hashlib.sha1(udn.encode("utf-8")).hexdigest()[:12], name=name, kind=kind, host=host,
                        location=location, av_url=av[1], av_type=av[0], rc_url=rc[1], rc_type=rc[0])
    return None


# ---- điều khiển ---------------------------------------------------------------------------------------------------


def _fault(data: bytes) -> CastError:
    try:
        root = _xml(data)
    except CastError as error:
        return error
    code = next((element.text or "" for element in root.iter() if _local(element.tag) == "errorCode"), "")
    description = next((element.text or "" for element in root.iter() if _local(element.tag) == "errorDescription"), "")
    number = int(code) if code.strip().isdigit() else 0
    return CastError(UPNP_ERRORS.get(number) or _clean(description) or "thiết bị từ chối lệnh này", number)


def soap(url: str, service: str, action: str, arguments: Iterable[tuple[str, Any]] = (), *,
         timeout: float = 5.0) -> dict[str, str]:
    """Một lệnh UPnP (SOAP 1.1) -> các tham số trả về; lỗi UPnP hay lỗi mạng -> CastError câu tiếng Việt."""
    inner = "".join(f"<{name}>{escape(str(value))}</{name}>" for name, value in arguments)
    body = ('<?xml version="1.0" encoding="utf-8"?>'
            '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" '
            's:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/"><s:Body>'
            f'<u:{action} xmlns:u="{escape(service)}">{inner}</u:{action}></s:Body></s:Envelope>').encode()
    request = urllib.request.Request(url, data=body, method="POST", headers={
        "Content-Type": 'text/xml; charset="utf-8"', "SOAPACTION": f'"{service}#{action}"', "User-Agent": AGENT})
    try:
        with _OPENER.open(request, timeout=timeout) as response:
            root = _xml(_read(response))
    except urllib.error.HTTPError as error:
        raise _fault(error.read(MAX_XML + 1)) from None
    except (OSError, ValueError) as error:
        raise CastError("không trả lời - thiết bị đã tắt hay rời mạng?") from error
    for element in root.iter():
        if _local(element.tag) == f"{action}Response":
            return {_local(child.tag): (child.text or "") for child in element}
    raise CastError("thiết bị trả lời lạ")


def didl(url: str, *, title: str, album: str, duration: float, size: int, mime: str, art: str = "") -> str:
    """Mô tả một chương (DIDL-Lite) cho SetAVTransportURI - TV hiện tên chương, tên sách, bìa."""
    length = f' duration="{clock(duration)}.000"' if duration > 0 else ""
    cover = f"<upnp:albumArtURI>{escape(art)}</upnp:albumArtURI>" if art else ""
    return ('<DIDL-Lite xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/" xmlns:dc="http://purl.org/dc/elements/1.1/" '
            'xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/" xmlns:dlna="urn:schemas-dlna-org:metadata-1-0/">'
            '<item id="abook-chapter" parentID="abook" restricted="1">'
            f"<dc:title>{escape(title)}</dc:title><dc:creator>ABook</dc:creator>"
            f"<upnp:album>{escape(album)}</upnp:album><upnp:artist>{escape(album)}</upnp:artist>{cover}"
            "<upnp:class>object.item.audioItem.musicTrack</upnp:class>"
            f'<res protocolInfo="http-get:*:{mime}:{DLNA_FEATURES}"{length} size="{int(size)}">{escape(url)}</res>'
            "</item></DIDL-Lite>")


def route_to(host: str) -> str:
    """Địa chỉ của máy này mà thiết bị ở `host` tới được: card mạng hệ điều hành chọn để đi tới nó."""
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect((host, 9))
        return probe.getsockname()[0]
    finally:
        probe.close()


# ---- backend theo giao thức -------------------------------------------------------------------------------------


class Track(NamedTuple):
    """Một chương đưa cho thiết bị: `url` đã qua CastMedia, `art` là URL bìa (hay "")."""

    url: str
    title: str
    album: str
    duration: float
    size: int
    mime: str
    art: str = ""


class Status(NamedTuple):
    """Thiết bị đang làm gì, nói theo từ vựng UPnP cho mọi giao thức: state PLAYING | PAUSED_PLAYBACK | TRANSITIONING |
    STOPPED | NO_MEDIA_PRESENT. `uri` là thứ nó đang phát ("" = không biết); `reason` khi nó dừng và biết vì sao:
    "finished" (hết chương), "interrupted" (có người khác chiếm máy), "error" (không phát được)."""

    state: str
    position: float
    duration: float
    uri: str
    reason: str = ""


class Backend:
    """Nói chuyện với MỘT thiết bị bằng một giao thức. Mọi lệnh lỗi -> CastError câu tiếng Việt; `status()` phải trả ngay
    (đọc bản chụp hay hỏi một lượt), thiết bị im lặng thì CastError - CastPlayers lo phần còn lại (phiên, sang chương)."""

    def load(self, track: Track, seconds: float) -> float:
        """Đưa chương và phát từ `seconds` -> vị trí thật đã bắt đầu (0 nếu không tua được)."""
        raise NotImplementedError

    def play(self) -> None:
        raise NotImplementedError

    def pause(self) -> bool:
        """True: thiết bị không có Pause nên đã dừng hẳn - "phát" phải đưa lại chương."""
        raise NotImplementedError

    def stop(self, timeout: float = 5.0) -> None:
        raise NotImplementedError

    def seek(self, seconds: float) -> None:
        raise NotImplementedError

    def status(self) -> Status:
        raise NotImplementedError

    def close(self, release: bool = False) -> None:
        """Bỏ kết nối; `release`: trả luôn thiết bị về nguyên trạng (Cast: đóng ứng dụng phát nếu máy này đã mở nó)."""


class DlnaBackend(Backend):
    """DLNA / UPnP AV: SOAP AVTransport tới địa chỉ điều khiển của thiết bị; không giữ kết nối nên `close` không việc gì."""

    def __init__(self, renderer: Renderer) -> None:
        self.renderer = renderer

    def _call(self, action: str, *arguments: tuple[str, Any], timeout: float = 5.0) -> dict[str, str]:
        return soap(self.renderer.av_url, self.renderer.av_type, action, (("InstanceID", 0), *arguments), timeout=timeout)

    def load(self, track: Track, seconds: float) -> float:
        metadata = didl(track.url, title=track.title, album=track.album, duration=track.duration, size=track.size,
                        mime=track.mime, art=track.art)
        arguments = (("CurrentURI", track.url), ("CurrentURIMetaData", metadata))
        try:
            self._call("SetAVTransportURI", *arguments)
        except CastError as error:
            if error.code not in (701, 705):
                raise
            self._call("Stop")  # có TV không nhận bài mới khi đang phát bài cũ
            self._call("SetAVTransportURI", *arguments)
        self._call("Play", ("Speed", "1"))
        return self._seek_when_ready(seconds) if seconds >= 1 else 0.0

    def _seek_when_ready(self, seconds: float) -> float:
        """Phần lớn TV chỉ tua được khi đã chạy: đợi PLAYING (tới 8 giây) rồi tua. Không tua được thì phát từ đầu."""
        deadline = time.time() + 8
        while time.time() < deadline:
            try:
                state = self._call("GetTransportInfo").get("CurrentTransportState", "")
            except CastError:
                state = ""
            if state in ("PLAYING", "PAUSED_PLAYBACK"):
                try:
                    self.seek(seconds)
                    return seconds
                except CastError:
                    return 0.0
            time.sleep(0.3)
        return 0.0

    def play(self) -> None:
        self._call("Play", ("Speed", "1"))

    def pause(self) -> bool:
        try:
            self._call("Pause")
        except CastError as error:
            if error.code not in (401, 701):
                raise
            self._call("Stop")  # thiết bị không có Pause: dừng hẳn, "phát" sẽ đưa lại đúng chỗ
            return True
        return False

    def stop(self, timeout: float = 5.0) -> None:
        self._call("Stop", timeout=timeout)

    def seek(self, seconds: float) -> None:
        self._call("Seek", ("Unit", "REL_TIME"), ("Target", clock(seconds)))

    def status(self) -> Status:
        state = self._call("GetTransportInfo").get("CurrentTransportState", "").strip().upper()
        info = self._call("GetPositionInfo")
        return Status(state, seconds_of(info.get("RelTime", "")), seconds_of(info.get("TrackDuration", "")),
                      info.get("TrackURI") or "")


def backend_for(renderer: Renderer) -> Backend:
    if renderer.protocol == "gcast":
        # gcast.py dùng lại CastError, Backend... ở đây: nhập muộn để khỏi vòng tròn.
        from .gcast import GoogleCast

        return GoogleCast(renderer)
    return DlnaBackend(renderer)


# ---- cổng audio cho thiết bị ------------------------------------------------------------------------------------


class CastMedia:
    """Cổng riêng để thiết bị phát tải audio (và bìa): chỉ phục vụ file đã đưa qua `share`, mỗi file một mã ngẫu nhiên
    128 bit, hết hạn sau 12 giờ; GET/HEAD có Range (thiết bị tua bằng Range). Mở lần đầu cần, nghe mọi card mạng."""

    TTL = 12 * 3600.0

    def __init__(self, host: str = "0.0.0.0") -> None:
        self.host = host
        self._files: dict[str, tuple[Path, str, float]] = {}
        self._lock = threading.Lock()
        self._server: ThreadingHTTPServer | None = None

    def share(self, path: Path, reach: str) -> str:
        """URL để thiết bị ở địa chỉ `reach` tải `path`."""
        server = self._start()
        token = secrets.token_urlsafe(16)
        now = time.time()
        with self._lock:
            for key in [key for key, (_path, _type, until) in self._files.items() if until < now]:
                del self._files[key]
            self._files[token] = (path, TYPES.get(path.suffix.lower(), "application/octet-stream"), now + self.TTL)
        address = "127.0.0.1" if self.host == "127.0.0.1" else route_to(reach)
        return f"http://{address}:{server.server_address[1]}/c/{token}{path.suffix.lower()}"

    def lookup(self, token: str) -> tuple[Path, str] | None:
        with self._lock:
            entry = self._files.get(token)
        if entry is None or entry[2] < time.time():
            return None
        return entry[0], entry[1]

    def _start(self) -> ThreadingHTTPServer:
        with self._lock:
            if self._server is None:
                server = ThreadingHTTPServer((self.host, 0), _media_handler(self))
                server.daemon_threads = True
                threading.Thread(target=server.serve_forever, name="cast-media", daemon=True).start()
                self._server = server
            return self._server

    def close(self) -> None:
        with self._lock:
            server, self._server = self._server, None
        if server is not None:
            server.shutdown()
            server.server_close()


def _media_handler(media: CastMedia) -> type[BaseHTTPRequestHandler]:
    class MediaHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        server_version = "ABook"
        sys_version = ""

        def log_message(self, format: str, *args: Any) -> None:
            return

        def do_HEAD(self) -> None:
            self._serve(body=False)

        def do_GET(self) -> None:
            self._serve(body=True)

        def _serve(self, *, body: bool) -> None:
            match = re.fullmatch(r"/c/([A-Za-z0-9_-]{16,64})(?:\.[a-z0-9]{1,5})?", urllib.parse.urlsplit(self.path).path)
            found = media.lookup(match.group(1)) if match else None
            if found is None or not found[0].is_file():
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            path, mime = found
            size = path.stat().st_size
            start, end, status = 0, size - 1, HTTPStatus.OK
            ranged = re.fullmatch(r"bytes=(\d*)-(\d*)", (self.headers.get("Range") or "").strip())
            if ranged and size:
                first, last = ranged.groups()
                if first:
                    start, end = int(first), min(int(last), size - 1) if last else size - 1
                elif last:
                    start = max(0, size - int(last))
                if start > end or start >= size:
                    self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                    self.send_header("Content-Range", f"bytes */{size}")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                status = HTTPStatus.PARTIAL_CONTENT
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(end - start + 1))
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Access-Control-Allow-Origin", "*")  # ứng dụng nhận của Cast là trang web: tải audio, bìa bằng CORS
            if status == HTTPStatus.PARTIAL_CONTENT:
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.send_header("transferMode.dlna.org", "Interactive" if mime.startswith("image/") else "Streaming")
            self.send_header("contentFeatures.dlna.org", DLNA_FEATURES)
            self.end_headers()
            if not body:
                return
            try:
                with path.open("rb") as handle:
                    handle.seek(start)
                    remaining = end - start + 1
                    while remaining > 0:
                        chunk = handle.read(min(64 * 1024, remaining))
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        remaining -= len(chunk)
            except OSError:  # thiết bị bỏ ngang (tua, dừng, đổi chương)
                self.close_connection = True

    return MediaHandler


# ---- trình phát trên thiết bị -----------------------------------------------------------------------------------


@dataclass
class _Session:
    """Một cuốn đang phát trên một thiết bị - máy tính giữ cuốn nào, chương nào; thiết bị chỉ biết một file."""

    book_id: str
    book_title: str
    chapters: list[dict[str, Any]]  # chương nghe được theo thứ tự: id, title, duration
    chapter_id: int
    chapter_title: str
    duration: float
    url: str
    position: float = 0.0
    playing: bool = True  # người dùng muốn phát; thiết bị báo thì theo thiết bị
    buffering: bool = True
    state: str = ""  # trạng thái thiết bị báo lần cuối
    peak: float = 0.0  # vị trí xa nhất trong chương này - về STOPPED khi đã tới cuối là hết chương
    polled: float = 0.0
    heard: float = 0.0  # lần cuối thiết bị trả lời
    saved: float = 0.0
    grace: float = 0.0  # trước lúc này STOPPED chỉ là thiết bị chưa kịp chạy
    held: bool = False  # người dùng dừng hẳn (thiết bị không có Pause): STOPPED không phải hết chương
    ended: bool = False

    @property
    def token(self) -> str:
        return self.url.rsplit("/", 1)[-1].split(".", 1)[0]

    def estimate(self, now: float) -> float:
        if not self.playing or self.buffering or not self.polled:
            return self.position
        at = self.position + max(0.0, now - self.polled)
        return min(at, self.duration) if self.duration > 0 else at


class CastPlayers:
    """Thiết bị phát trong mạng nhà và những gì máy này đang phát trên chúng.

    Một luồng nền tìm thiết bị khi có người đang xem (giao diện hỏi trong 15 giây qua, nhịp 30 giây) và hỏi thiết bị
    đang phát mỗi giây - KỂ CẢ khi không ai xem, để lưu chỗ nghe và sang chương sau. `view()` chỉ đọc bản chụp, không bao
    giờ đợi mạng. Lệnh (`send`) chạy thẳng trong luồng HTTP, mỗi thiết bị một khoá (có TV nghẹn khi hai lệnh chồng nhau).
    """

    def __init__(self, book: Callable[[str], dict[str, Any]], audio: Callable[[str, int], Path | None],
                 save: Callable[[str, int, float, float], None], *,
                 cover: Callable[[str], Path | None] = lambda _book: None, media: CastMedia | None = None,
                 find: Callable[[], list[tuple[str, str]]] = search,
                 read: Callable[[str, str], Renderer | None] = describe,
                 find_google: Callable[[], list[Renderer]] = list,
                 backend: Callable[[Renderer], Backend] = backend_for) -> None:
        """`find` + `read`: DLNA (SSDP rồi đọc mô tả). `find_google`: Google Cast (mDNS, đã đủ thông tin) - mặc định
        không tìm gì, để bài thử không gửi multicast ra mạng người chạy; app đưa `gcast.discover` vào."""
        self.book, self.audio, self.save, self.cover = book, audio, save, cover
        self.media = media or CastMedia()
        self.find, self.read, self.find_google, self.backend = find, read, find_google, backend
        self._lock = threading.Lock()
        self._renderers: dict[str, tuple[Renderer, float]] = {}  # mã -> (thiết bị, lúc thấy cuối)
        self._described: dict[str, tuple[float, Renderer | None]] = {}  # LOCATION -> (lúc đọc, mô tả)
        self._backends: dict[str, Backend] = {}  # thiết bị -> backend đang giữ kết nối (có phiên) hay vừa dùng
        self._sessions: dict[str, _Session] = {}
        self._device_locks: dict[str, threading.Lock] = {}
        self._wanted = 0.0
        self._searched = 0.0
        self._thread: threading.Thread | None = None
        self._wake = threading.Event()

    # -- nhìn ---------------------------------------------------------------------------------------------------

    def view(self) -> list[dict[str, Any]]:
        now = time.time()
        with self._lock:
            self._wanted = now
            self._ensure_thread()
            items = [(renderer, self._sessions.get(renderer.id)) for renderer, _seen in self._renderers.values()]
        return [self._presence(renderer, session, now) for renderer, session in items]

    def scan(self) -> None:
        """Người dùng mở "Phát trên…": tìm lại ngay, không đợi nhịp 30 giây."""
        with self._lock:
            self._wanted = time.time()
            self._searched = 0.0
            self._ensure_thread()
        self._wake.set()

    def owns(self, device: str) -> bool:
        with self._lock:
            return device in self._renderers

    def close(self) -> None:
        """App đóng: thiết bị đang phát sách của máy này dừng hẳn (cổng audio sắp đóng - để nó phát nốt phần đã tải rồi
        báo lỗi thì khó hiểu hơn), chỗ nghe lưu đúng chỗ dừng, rồi đóng cổng audio."""
        with self._lock:
            active = [(self._renderers[device][0], session) for device, session in self._sessions.items()
                      if not session.ended and device in self._renderers]
        for renderer, session in active:
            session.ended = True
            self._store(session, session.estimate(time.time()))
            self._stop(renderer, 2.0)
        with self._lock:
            rest, self._backends = list(self._backends.values()), {}
        for backend in rest:
            backend.close()
        self.media.close()

    def _stop(self, renderer: Renderer, timeout: float) -> None:
        """Dừng thiết bị và trả nó về nguyên trạng; thiết bị không trả lời thì thôi - chỗ nghe đã lưu rồi."""
        with self._lock:
            backend = self._backends.pop(renderer.id, None)
        if backend is None:
            return
        try:
            backend.stop(timeout)
        except CastError:
            pass
        backend.close(release=True)

    def _presence(self, renderer: Renderer, session: _Session | None, now: float) -> dict[str, Any]:
        base = {"device": renderer.id, "name": renderer.name, "kind": renderer.kind, "via": "cast",
                "protocol": renderer.protocol, "rate": 1.0, "books": [], "stream": True, "acks": []}
        if session is None or session.ended:
            return {**base, "bookId": "", "bookTitle": "", "chapterId": None, "chapterTitle": "", "position": 0.0,
                    "duration": 0.0, "playing": False, "buffering": False, "age": 0.0}
        return {**base, "bookId": session.book_id, "bookTitle": session.book_title, "chapterId": session.chapter_id,
                "chapterTitle": session.chapter_title, "position": round(session.position, 2),
                "duration": round(session.duration, 1), "playing": session.playing, "buffering": session.buffering,
                "age": round(max(0.0, now - session.polled), 2) if session.polled else 0.0}

    # -- lệnh ---------------------------------------------------------------------------------------------------

    def send(self, device: str, command: dict[str, Any]) -> dict[str, Any]:
        """Lệnh đã kiểm (sync.remote_command) cho thiết bị `device`; lỗi -> CastError "<tên>: <vì sao>"."""
        with self._lock:
            entry = self._renderers.get(device)
            session = self._sessions.get(device)
        if entry is None:
            raise CastError("Không còn thấy thiết bị này trong mạng")
        renderer = entry[0]
        try:
            with self._device(device):
                self._apply(renderer, session if session is not None and not session.ended else None, command)
        except CastError as error:
            raise CastError(f"{renderer.name}: {error}", error.code) from None
        self._wake.set()
        return {"id": secrets.token_hex(6)}

    def _apply(self, renderer: Renderer, session: _Session | None, command: dict[str, Any]) -> None:
        action = command["action"]
        if action == "load":
            view = self.book(command["bookId"])
            chapters = [{"id": int(item["id"]), "title": str(item.get("fullTitle") or item.get("title") or ""),
                         "duration": float(item.get("duration") or 0)}
                        for item in view.get("chapters") or [] if isinstance(item, dict) and item.get("available")]
            chapter = next((item for item in chapters if item["id"] == command["chapterId"]), None)
            if chapter is None:
                raise CastError("chương này chưa nghe được")
            self._load(renderer, command["bookId"], str(view.get("title") or ""), chapters, chapter, command["seconds"])
            return
        if action == "rate":
            if abs(command["rate"] - 1.0) > 0.01:
                raise CastError("loa, TV chỉ phát ở tốc độ 1x")
            return
        if session is None:
            if action == "stop":
                return  # "Nghe trên máy này" sau khi thiết bị đã bị chiếm hay tự hết: không còn gì để dừng
            raise CastError("chưa phát gì từ máy này - bấm “Phát trên…” ở thanh phát")
        backend = self._backend(renderer)
        now = time.time()
        if action == "stop":
            # Người nghe chuyển về máy này: dừng hẳn, trả thiết bị về nguyên trạng, chỗ nghe lưu đúng chỗ dừng.
            session.ended = True
            self._store(session, session.estimate(now))
            self._stop(renderer, 5.0)
            return
        if action in ("play", "pause", "toggle"):
            want = not session.playing if action == "toggle" else action == "play"
            if want:
                if session.held or session.state in ("STOPPED", "NO_MEDIA_PRESENT"):
                    chapter = self._chapter(session, session.chapter_id)
                    self._load(renderer, session.book_id, session.book_title, session.chapters, chapter,
                               session.position)
                    return
                backend.play()
                session.grace = now + GRACE_SECONDS
            else:
                session.position = session.estimate(now)
                session.held = backend.pause() or session.held
                self._store(session, session.position)
            session.playing, session.buffering, session.polled = want, want, now
            return
        if action in ("seek", "skip"):
            target = command["seconds"] + (session.estimate(now) if action == "skip" else 0.0)
            if action == "skip" and session.duration > 0 and target >= session.duration - 1:
                following = self._neighbour(session, 1)
                if following is not None:
                    self._load(renderer, session.book_id, session.book_title, session.chapters, following, 0.0)
                    return
            target = max(0.0, min(target, session.duration - 1 if session.duration > 1 else target))
            backend.seek(target)
            session.position, session.peak, session.polled = target, target, now
            return
        if action in ("next", "previous", "jump"):
            if action == "jump":
                chapter = self._chapter(session, command["chapterId"])
            else:
                chapter = self._neighbour(session, 1 if action == "next" else -1)
                if chapter is None:
                    raise CastError("đã là chương cuối" if action == "next" else "đã là chương đầu")
            self._load(renderer, session.book_id, session.book_title, session.chapters, chapter,
                       command.get("seconds", 0.0) if action == "jump" else 0.0)
            return
        raise CastError("thiết bị chưa làm được lệnh này")

    def _load(self, renderer: Renderer, book_id: str, book_title: str, chapters: list[dict[str, Any]],
              chapter: dict[str, Any], seconds: float) -> None:
        """Đưa một chương cho thiết bị và phát từ `seconds`. Gọi khi đã giữ khoá thiết bị."""
        path = self.audio(book_id, chapter["id"])
        if path is None:
            raise CastError("chương này chưa nghe được trên máy này")
        url = self.media.share(path, renderer.host)
        cover = self.cover(book_id)
        art = self.media.share(cover, renderer.host) if cover is not None else ""
        track = Track(url, chapter["title"], book_title, chapter["duration"], path.stat().st_size,
                      TYPES.get(path.suffix.lower(), "audio/mpeg"), art)
        resume = seconds >= 1 and (chapter["duration"] <= 0 or seconds < chapter["duration"] - 1)
        backend = self._backend(renderer)
        try:
            started = backend.load(track, seconds if resume else 0.0)
        except CastError:
            with self._lock:
                idle = renderer.id not in self._sessions or self._sessions[renderer.id].ended
            if idle:
                self._release(renderer.id, stop=True)  # lần đưa đầu hỏng: đừng giữ kết nối (Cast: cả ứng dụng đã mở) cho một phiên không có
            raise
        now = time.time()
        session = _Session(book_id=book_id, book_title=book_title, chapters=chapters, chapter_id=chapter["id"],
                           chapter_title=chapter["title"], duration=chapter["duration"], url=url, position=0.0,
                           polled=now, heard=now, saved=now, grace=now + GRACE_SECONDS)
        if resume:
            session.position = session.peak = started
        with self._lock:
            previous = self._sessions.get(renderer.id)
            self._sessions[renderer.id] = session
        if previous is not None and not previous.ended and previous.chapter_id != session.chapter_id:
            self._store(previous, previous.position)
        self._store(session, session.position)  # "Nghe tiếp" trỏ ngay tới chương đang phát trên thiết bị

    def _backend(self, renderer: Renderer) -> Backend:
        with self._lock:
            found = self._backends.get(renderer.id)
            if found is None:
                found = self._backends[renderer.id] = self.backend(renderer)
            return found

    def _release(self, device: str, *, stop: bool = False) -> None:
        """Bỏ backend của thiết bị (phiên đã hết); `stop`: trả thiết bị về nguyên trạng - không dùng khi bị chiếm máy."""
        with self._lock:
            backend = self._backends.pop(device, None)
        if backend is not None:
            backend.close(release=stop)

    def _end(self, device: str, session: _Session) -> None:
        """Phiên hết (bị chiếm máy, thiết bị tắt, hết chương cuối): thôi hỏi, đóng kết nối - không đụng tới thứ đang phát."""
        session.ended = True
        with self._lock:
            current = self._sessions.get(device) is session
        if current:
            self._release(device)

    def _device(self, device: str) -> threading.Lock:
        with self._lock:
            return self._device_locks.setdefault(device, threading.Lock())

    @staticmethod
    def _chapter(session: _Session, chapter_id: int) -> dict[str, Any]:
        chapter = next((item for item in session.chapters if item["id"] == chapter_id), None)
        if chapter is None:
            raise CastError("chương này chưa nghe được")
        return chapter

    @staticmethod
    def _neighbour(session: _Session, step: int) -> dict[str, Any] | None:
        ids = [item["id"] for item in session.chapters]
        if session.chapter_id not in ids:
            return None
        index = ids.index(session.chapter_id) + step
        return session.chapters[index] if 0 <= index < len(ids) else None

    def _store(self, session: _Session, seconds: float) -> None:
        session.saved = time.time()
        try:
            self.save(session.book_id, session.chapter_id, seconds, session.duration)
        except Exception:  # noqa: BLE001, S110 - lưu chỗ nghe hỏng không được làm ngừng việc hỏi thiết bị
            pass

    # -- nền ----------------------------------------------------------------------------------------------------

    def _ensure_thread(self) -> None:
        """Gọi khi giữ self._lock."""
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._loop, name="cast-players", daemon=True)
            self._thread.start()

    def _loop(self) -> None:
        while True:
            now = time.time()
            with self._lock:
                wanted = now - self._wanted < WANTED_SECONDS
                active = [device for device, session in self._sessions.items() if not session.ended]
                if not wanted and not active:
                    self._thread = None
                    return
                due = wanted and now - self._searched >= SEARCH_SECONDS
                if due:
                    self._searched = now
            if due:
                self._search()
            for device in active:
                self._poll(device)
            with self._lock:
                playing = any(session.playing and not session.ended for session in self._sessions.values())
            self._wake.wait(PLAYING_POLL if playing or not active else IDLE_POLL)
            self._wake.clear()

    def _search(self) -> None:
        with ThreadPoolExecutor(max_workers=1, thread_name_prefix="cast-google") as pool:
            google = pool.submit(self._find_google)  # mDNS và SSDP cùng lúc: một lượt tìm vẫn chừng 2 giây
            try:
                found = self.find()
            except OSError:
                found = []
            casts = google.result()
        now = time.time()

        def one(item: tuple[str, str]) -> Renderer | None:
            location, host = item
            with self._lock:
                cached = self._described.get(location)
            # Mô tả giữ 10 phút; đọc hỏng thì thử lại sau 1 phút (thiết bị vừa bật còn đang khởi động).
            if cached is not None and now - cached[0] < (600 if cached[1] is not None else 60):
                return cached[1]
            try:
                renderer = self.read(location, host)
            except (CastError, OSError, ValueError):
                renderer = None
            with self._lock:
                self._described[location] = (now, renderer)
            return renderer

        if found:
            with ThreadPoolExecutor(max_workers=8, thread_name_prefix="cast-describe") as pool:
                renderers = list(pool.map(one, found))
        else:
            renderers = []
        with self._lock:
            for renderer in [*renderers, *casts]:
                if renderer is not None:
                    self._renderers[renderer.id] = (renderer, now)
            for device, (_renderer, seen) in list(self._renderers.items()):
                session = self._sessions.get(device)
                if now - seen > FORGET_SECONDS and (session is None or session.ended):
                    del self._renderers[device]

    def _find_google(self) -> list[Renderer]:
        try:
            return [renderer for renderer in self.find_google() if isinstance(renderer, Renderer)]
        except (CastError, OSError, ValueError):
            return []

    def _poll(self, device: str) -> None:
        with self._lock:
            entry = self._renderers.get(device)
            session = self._sessions.get(device)
            backend = self._backends.get(device)
        if entry is None or session is None or session.ended or backend is None:
            return
        renderer = entry[0]
        lock = self._device(device)
        if not lock.acquire(timeout=0.2):  # đang có lệnh: lượt sau hỏi
            return
        try:
            if self._sessions.get(device) is not session:
                return
            try:
                status = backend.status()
            except CastError:
                now = time.time()
                session.buffering = session.playing
                if now - session.heard > LOST_SECONDS:
                    self._store(session, session.position)
                    self._end(device, session)
                return
            advance = self._observe(session, status)
            if session.ended:  # bị chiếm máy hay thiết bị báo lỗi: lưu chỗ nghe cuối rồi thôi
                self._store(session, session.estimate(time.time()))
                self._end(device, session)
                return
            if advance:
                self._store(session, session.duration)  # chương xong: "đã nghe hết" như trình phát trong app
                following = self._neighbour(session, 1)
                if following is None:
                    self._end(device, session)
                    return
                try:
                    self._load(renderer, session.book_id, session.book_title, session.chapters, following, 0.0)
                except CastError:
                    self._end(device, session)
        finally:
            lock.release()

    def _observe(self, session: _Session, status: Status) -> bool:
        """Cập nhật phiên theo lời thiết bị; True khi vừa hết chương (thiết bị báo hết, hay đã tới cuối rồi về STOPPED)."""
        now = time.time()
        session.heard = now
        state = status.state
        if status.uri and session.token not in status.uri and state in ("PLAYING", "PAUSED_PLAYBACK", "TRANSITIONING"):
            session.ended = True  # có người phát thứ khác trên thiết bị (app khác, điều khiển TV)
            return False
        if status.reason in ("interrupted", "error"):
            session.ended = True  # bị chiếm máy, hay thiết bị không phát được file
            return False
        if status.duration > 1 and abs(status.duration - session.duration) > 1:
            session.duration = status.duration  # độ dài thật của file (độ dài trong sách là tổng câu + khoảng lặng)
        reported = status.position
        before = session.state
        session.state = state
        advance = False
        if state == "PLAYING":
            if reported <= 0 and session.playing and not session.buffering and session.polled:
                reported = session.estimate(now)  # thiết bị không báo vị trí (NOT_IMPLEMENTED): ước theo đồng hồ
            session.playing, session.buffering, session.held = True, False, False
            session.position = reported
            session.peak = max(session.peak, reported)
        elif state == "PAUSED_PLAYBACK":
            session.playing = session.buffering = False
            session.position = reported or session.position
        elif state == "TRANSITIONING":
            session.buffering = True
        elif status.reason == "finished" and session.playing and not session.held:
            advance = True  # thiết bị tự nói đã hết (Cast: IDLE / FINISHED): không đoán theo vị trí
        elif now < session.grace:
            session.buffering = session.playing
        elif session.held or not session.playing:
            session.playing = session.buffering = False
        elif session.duration > 0 and max(session.peak, session.estimate(now)) >= session.duration - END_SLACK:
            advance = True
        else:  # dừng giữa chương: điều khiển TV, hay thiết bị không phát được
            session.playing = session.buffering = False
        session.polled = now
        if not advance and (state != before or session.playing and now - session.saved >= SAVE_SECONDS):
            self._store(session, session.position)
        return advance
