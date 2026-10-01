"""Loa giả lập DLNA (UPnP AV MediaRenderer) để thử "Phát trên loa / TV" khi không có thiết bị thật - 01-10.

Chỉ dùng thư viện chuẩn, nên chạy được cả trên máy khác trong mạng (Mac mini): `python3 fake_renderer.py --name "Loa thử"`.
Nó trả lời SSDP (multicast 239.255.255.250:1900, hoặc một cổng UDP riêng cho bài thử), phục vụ mô tả thiết bị và SOAP
AVTransport / RenderingControl, và "phát" bằng cách TẢI audio từ đường dẫn được đưa (kiểm máy tính phục vụ đúng) rồi cho
vị trí chạy theo đồng hồ (`speed` > 1 để bài thử không phải đợi hết chương). Không phát ra loa.

Giống TV thật ở những chỗ hay vấp: không tua được trước khi phát (lỗi 701), hết bài thì về STOPPED với vị trí 0, có thể
không có Pause (`pause=False`) hay không báo vị trí (`report_position=False`). Ghi lại mọi lệnh (`actions`) và mọi lần
tải (`fetches`) cho bài thử.
"""
from __future__ import annotations

import argparse
import re
import socket
import struct
import threading
import time
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from xml.etree import ElementTree
from xml.sax.saxutils import escape

GROUP = "239.255.255.250"
AVT = "urn:schemas-upnp-org:service:AVTransport:1"
RC = "urn:schemas-upnp-org:service:RenderingControl:1"
CM = "urn:schemas-upnp-org:service:ConnectionManager:1"
RENDERER = "urn:schemas-upnp-org:device:MediaRenderer:1"


def _clock(seconds: float) -> str:
    whole = max(0, int(seconds))
    return f"{whole // 3600}:{whole // 60 % 60:02d}:{whole % 60:02d}"


def _seconds(value: str) -> float:
    match = re.fullmatch(r"(\d+):(\d{1,2}):(\d{1,2})(?:\.\d+)?", value.strip())
    return int(match[1]) * 3600 + int(match[2]) * 60 + int(match[3]) if match else 0.0


class UPnPError(Exception):
    def __init__(self, code: int, description: str) -> None:
        super().__init__(description)
        self.code, self.description = code, description


class FakeRenderer:
    def __init__(self, name: str = "Loa giả lập", *, host: str = "127.0.0.1", speed: float = 1.0, pause: bool = True,
                 report_position: bool = True, fetch_bytes: int | None = None) -> None:
        self.name, self.host, self.speed = name, host, speed
        self.pause_supported, self.report_position = pause, report_position
        self.fetch_bytes = fetch_bytes  # None: tải hết file; số: chỉ tải chừng ấy byte (bài thử nhanh)
        self.udn = f"uuid:{uuid.uuid4()}"
        self.actions: list[tuple[str, dict[str, str]]] = []
        self.fetches: list[dict[str, Any]] = []
        self.volume = 30
        self._lock = threading.Lock()
        self._state = "NO_MEDIA_PRESENT"
        self._uri = ""
        self._metadata = ""
        self._duration = 0.0
        self._offset = 0.0  # vị trí lúc bắt đầu chạy / lúc dừng
        self._since = 0.0  # lúc bắt đầu chạy (state PLAYING)
        self._http: ThreadingHTTPServer | None = None
        self._udp: socket.socket | None = None
        self._stopping = threading.Event()

    # -- máy chủ ------------------------------------------------------------------------------------------------

    def start(self, *, ssdp_port: int | None = 0, multicast: bool = False, interface: str = "") -> FakeRenderer:
        """`ssdp_port` 0: cổng UDP ngẫu nhiên trên `host` (bài thử gửi M-SEARCH thẳng tới); `multicast`: nghe 1900 như
        thiết bị thật, tham gia nhóm trên card `interface`."""
        self._http = ThreadingHTTPServer((self.host, 0), self._handler())
        self._http.daemon_threads = True
        threading.Thread(target=self._http.serve_forever, daemon=True).start()
        if multicast:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if hasattr(socket, "SO_REUSEPORT"):
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            sock.bind(("", 1900))
            membership = struct.pack("4s4s", socket.inet_aton(GROUP), socket.inet_aton(interface or self.host))
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, membership)
            self._udp = sock
        elif ssdp_port is not None:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock.bind((self.host, ssdp_port))
            self._udp = sock
        if self._udp is not None:
            self._udp.settimeout(0.5)
            threading.Thread(target=self._answer, daemon=True).start()
        threading.Thread(target=self._tick, daemon=True).start()
        return self

    @property
    def ssdp_address(self) -> tuple[str, int]:
        assert self._udp is not None
        return self.host, self._udp.getsockname()[1]

    @property
    def location(self) -> str:
        assert self._http is not None
        return f"http://{self.host}:{self._http.server_address[1]}/description.xml"

    def stop(self) -> None:
        self._stopping.set()
        if self._http is not None:
            self._http.shutdown()
            self._http.server_close()
        if self._udp is not None:
            self._udp.close()

    def _answer(self) -> None:
        while not self._stopping.is_set():
            try:
                data, sender = self._udp.recvfrom(8192)  # type: ignore[union-attr]
            except (TimeoutError, socket.timeout):  # noqa: UP041 - Python 3.9 (Mac): socket.timeout chưa là TimeoutError
                continue
            except OSError:
                return
            text = data.decode("utf-8", "replace")
            if not text.startswith("M-SEARCH") or not re.search(r"ST:\s*(ssdp:all|upnp:rootdevice|" + re.escape(RENDERER) + ")", text, re.IGNORECASE):
                continue
            reply = ("HTTP/1.1 200 OK\r\nCACHE-CONTROL: max-age=1800\r\nEXT:\r\n"
                     f"LOCATION: {self.location}\r\nSERVER: FakeOS/1.0 UPnP/1.0 ABookFake/1.0\r\n"
                     f"ST: {RENDERER}\r\nUSN: {self.udn}::{RENDERER}\r\n\r\n")
            try:
                self._udp.sendto(reply.encode("ascii"), sender)  # type: ignore[union-attr]
            except OSError:
                pass

    # -- trạng thái ---------------------------------------------------------------------------------------------

    def position(self) -> float:
        with self._lock:
            return self._position()

    def _position(self) -> float:
        if self._state != "PLAYING":
            return self._offset
        at = self._offset + (time.monotonic() - self._since) * self.speed
        return min(at, self._duration) if self._duration else at

    @property
    def state(self) -> str:
        with self._lock:
            return self._state

    @property
    def uri(self) -> str:
        with self._lock:
            return self._uri

    def takeover(self, uri: str) -> None:
        """Một bộ điều khiển khác (app khác, điều khiển TV) phát thứ khác trên thiết bị."""
        with self._lock:
            self._uri, self._state, self._offset, self._since = uri, "PLAYING", 0.0, time.monotonic()

    def _tick(self) -> None:
        while not self._stopping.wait(0.05):
            with self._lock:
                if self._state == "PLAYING" and self._duration and self._position() >= self._duration:
                    self._state, self._offset = "STOPPED", 0.0  # hết bài: như phần lớn TV, về đầu

    def _fetch(self, uri: str) -> None:
        record: dict[str, Any] = {"uri": uri, "status": 0, "bytes": 0, "type": ""}
        try:
            request = urllib.request.Request(uri, headers={"Range": "bytes=0-", "getcontentFeatures.dlna.org": "1"})
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(request, timeout=10) as response:
                record["status"], record["type"] = response.status, response.headers.get("Content-Type", "")
                record["features"] = response.headers.get("contentFeatures.dlna.org", "")
                while True:
                    want = 65536 if self.fetch_bytes is None else min(65536, self.fetch_bytes - record["bytes"])
                    chunk = response.read(want) if want > 0 else b""
                    if not chunk:
                        break
                    record["bytes"] += len(chunk)
        except Exception as error:  # noqa: BLE001 - thiết bị thật cũng chỉ báo "không tải được"
            record["error"] = str(error)
        with self._lock:
            self.fetches.append(record)

    def _do(self, service: str, action: str, args: dict[str, str]) -> dict[str, Any]:
        with self._lock:
            self.actions.append((action, args))
            if service == RC:
                if action == "GetVolume":
                    return {"CurrentVolume": self.volume}
                if action == "SetVolume":
                    self.volume = int(args.get("DesiredVolume", self.volume))
                    return {}
                raise UPnPError(401, "Invalid Action")
            if service == CM:
                if action == "GetProtocolInfo":
                    return {"Source": "", "Sink": "http-get:*:audio/mpeg:*,http-get:*:audio/mp4:*"}
                raise UPnPError(401, "Invalid Action")
            if action == "SetAVTransportURI":
                uri = args.get("CurrentURI", "")
                self._uri, self._metadata = uri, args.get("CurrentURIMetaData", "")
                self._duration = 0.0
                match = re.search(r'duration="([^"]+)"', self._metadata)
                if match:
                    self._duration = _seconds(match[1])
                self._state, self._offset = "STOPPED", 0.0
                return {}
            if action == "Play":
                if not self._uri:
                    raise UPnPError(701, "Transition not available")
                if self._state != "PLAYING":
                    resume = self._state == "PAUSED_PLAYBACK"
                    self._state, self._since = "PLAYING", time.monotonic()
                    if not resume:
                        threading.Thread(target=self._fetch, args=(self._uri,), daemon=True).start()
                return {}
            if action == "Pause":
                if not self.pause_supported:
                    raise UPnPError(401, "Invalid Action")
                if self._state == "PLAYING":
                    self._offset, self._state = self._position(), "PAUSED_PLAYBACK"
                return {}
            if action == "Stop":
                self._offset, self._state = 0.0, "STOPPED" if self._uri else "NO_MEDIA_PRESENT"
                return {}
            if action == "Seek":
                if self._state not in ("PLAYING", "PAUSED_PLAYBACK"):
                    raise UPnPError(701, "Transition not available")  # TV thật: chỉ tua khi đã chạy
                if args.get("Unit") != "REL_TIME":
                    raise UPnPError(710, "Seek mode not supported")
                target = _seconds(args.get("Target", ""))
                if self._duration and target > self._duration:
                    raise UPnPError(711, "Illegal seek target")
                self._offset, self._since = target, time.monotonic()
                return {}
            if action == "GetTransportInfo":
                return {"CurrentTransportState": self._state, "CurrentTransportStatus": "OK", "CurrentSpeed": "1"}
            if action == "GetPositionInfo":
                at = _clock(self._position()) if self.report_position else "NOT_IMPLEMENTED"
                return {"Track": 1 if self._uri else 0, "TrackDuration": _clock(self._duration),
                        "TrackMetaData": self._metadata, "TrackURI": self._uri, "RelTime": at, "AbsTime": at,
                        "RelCount": 2147483647, "AbsCount": 2147483647}
            if action == "GetMediaInfo":
                return {"NrTracks": 1 if self._uri else 0, "MediaDuration": _clock(self._duration),
                        "CurrentURI": self._uri, "CurrentURIMetaData": self._metadata, "NextURI": "",
                        "NextURIMetaData": "", "PlayMedium": "NETWORK", "RecordMedium": "NOT_IMPLEMENTED",
                        "WriteStatus": "NOT_IMPLEMENTED"}
            raise UPnPError(401, "Invalid Action")

    # -- HTTP ---------------------------------------------------------------------------------------------------

    def description(self) -> str:
        services = "".join(
            f"<service><serviceType>{kind}</serviceType><serviceId>urn:upnp-org:serviceId:{name}</serviceId>"
            f"<SCPDURL>/{name}.xml</SCPDURL><controlURL>/{name}/control</controlURL>"
            f"<eventSubURL>/{name}/event</eventSubURL></service>"
            for kind, name in ((AVT, "AVTransport"), (RC, "RenderingControl"), (CM, "ConnectionManager")))
        return ('<?xml version="1.0" encoding="utf-8"?><root xmlns="urn:schemas-upnp-org:device-1-0">'
                "<specVersion><major>1</major><minor>0</minor></specVersion><device>"
                f"<deviceType>{RENDERER}</deviceType><friendlyName>{escape(self.name)}</friendlyName>"
                "<manufacturer>ABook</manufacturer><modelName>Fake renderer</modelName>"
                f"<UDN>{self.udn}</UDN><serviceList>{services}</serviceList></device></root>")

    def _handler(self) -> type[BaseHTTPRequestHandler]:
        renderer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: Any) -> None:
                return

            def _reply(self, status: int, body: str) -> None:
                data = body.encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", 'text/xml; charset="utf-8"')
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self) -> None:
                if self.path == "/description.xml":
                    self._reply(200, renderer.description())
                else:
                    self._reply(404, "")

            def do_POST(self) -> None:
                services = {"/AVTransport/control": AVT, "/RenderingControl/control": RC,
                            "/ConnectionManager/control": CM}
                service = services.get(self.path)
                body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
                soap_action = (self.headers.get("SOAPACTION") or "").strip('"')
                if service is None or not soap_action.startswith(service + "#"):
                    self._reply(404, "")
                    return
                action = soap_action.split("#", 1)[1]
                call = next((element for element in ElementTree.fromstring(body).iter()
                             if element.tag.rsplit("}", 1)[-1] == action), None)
                args = {child.tag.rsplit("}", 1)[-1]: child.text or "" for child in call} if call is not None else {}
                try:
                    out = renderer._do(service, action, args)
                except UPnPError as error:
                    self._reply(500, '<?xml version="1.0"?><s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">'
                                "<s:Body><s:Fault><faultcode>s:Client</faultcode><faultstring>UPnPError</faultstring>"
                                '<detail><UPnPError xmlns="urn:schemas-upnp-org:control-1-0">'
                                f"<errorCode>{error.code}</errorCode><errorDescription>{escape(error.description)}"
                                "</errorDescription></UPnPError></detail></s:Fault></s:Body></s:Envelope>")
                    return
                inner = "".join(f"<{key}>{escape(str(value))}</{key}>" for key, value in out.items())
                self._reply(200, '<?xml version="1.0"?><s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" '
                            's:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/"><s:Body>'
                            f'<u:{action}Response xmlns:u="{service}">{inner}</u:{action}Response></s:Body></s:Envelope>')

        return Handler


def main() -> int:
    parser = argparse.ArgumentParser(description="Loa giả lập DLNA - thử 'Phát trên loa / TV' không cần thiết bị thật")
    parser.add_argument("--name", default="Loa giả lập")
    parser.add_argument("--interface", required=True, help="địa chỉ IP của card mạng LAN máy này (vd 192.168.0.77)")
    parser.add_argument("--speed", type=float, default=1.0, help="vị trí chạy nhanh hơn đồng hồ bao nhiêu lần")
    parser.add_argument("--no-pause", action="store_true", help="như TV không có lệnh Pause")
    args = parser.parse_args()
    renderer = FakeRenderer(args.name, host=args.interface, speed=args.speed, pause=not args.no_pause)
    renderer.start(multicast=True, interface=args.interface)
    print(f"{args.name}: {renderer.location}", flush=True)
    seen_actions = seen_fetches = 0
    try:
        while True:
            time.sleep(1)
            with renderer._lock:
                actions, fetches = renderer.actions[seen_actions:], renderer.fetches[seen_fetches:]
                seen_actions, seen_fetches = len(renderer.actions), len(renderer.fetches)
            for action, values in actions:
                if action not in ("GetTransportInfo", "GetPositionInfo"):
                    shown = {key: (value[:60] + "…" if len(value) > 60 else value) for key, value in values.items()
                             if key != "InstanceID"}
                    print(time.strftime("%H:%M:%S"), action, shown, flush=True)
            for fetch in fetches:
                print(time.strftime("%H:%M:%S"), "tải", fetch, flush=True)
    except KeyboardInterrupt:
        renderer.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
