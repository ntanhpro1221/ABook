"""Studio từ xa: máy khác điều khiển sản xuất của máy này qua cổng đồng bộ (sync.py).

Chủ sách, 27-09: điện thoại không sản xuất nhưng phải điều khiển được tính năng sản xuất của máy có sản xuất qua các
đường remote. Cổng đồng bộ phục vụ đúng bản giao diện web của cửa sổ app, và chuyển tiếp các lời gọi API của nó sang
máy chủ giao diện cục bộ (server.py, chỉ nghe 127.0.0.1) - cùng mọi kiểm tra đầu vào, không viết lại đường nào. Nhờ thế
trình duyệt điện thoại, máy tính bảng, máy tính thứ hai và app Android (WebView mang sẵn mã thiết bị) cùng dùng một
Studio, và phần Nghe (thư viện, trình phát, đọc theo) đi kèm miễn phí.

NGHE thì mọi thiết bị đã ghép đều được, như app điện thoại qua /sync/v1 (lộ trình đường truyền 27-09 mục 1: iPhone,
iPad, TV, máy khác nghe trong trình duyệt): chế độ CHỈ NGHE chỉ mở `LISTEN_ROUTES`, và giao diện ẩn Studio (`/api/app`
mang `listenOnly`). Điều khiển sản xuất thì ba lớp chặn, lớp nào hỏng cũng về chỉ nghe:
- thiết bị đã ghép: mã thiết bị như điện thoại (`Authorization: Bearer`), hay cookie HttpOnly với trình duyệt - trình
  duyệt ghép bằng mã 6 số như điện thoại (`pairing_page`);
- công tắc riêng "Cho phép điều khiển sản xuất từ thiết bị đã ghép nối" (`remoteStudio`, tắt mặc định, tách khỏi quyền
  nghe) VÀ quyền của chính thiết bị, đọc lại mỗi yêu cầu - tắt là về chỉ nghe ngay;
- DANH SÁCH TRẮNG đường dẫn (`ALLOWED`): những gì chỉ có nghĩa trên chính máy này - hộp thoại chọn file, mở Explorer,
  đổi thư mục thư viện, ghép / gỡ thiết bị, điều khiển điện thoại, mở file sách theo đường dẫn - không bao giờ đi qua.
POST chỉ nhận JSON: trang lạ trong trình duyệt không gửi được JSON sang cổng này mà không qua CORS (cổng không trả lời
CORS), cookie lại SameSite=Strict. Cổng chỉ nói TLS (tls.py): cookie mang `Secure`, và trình duyệt - không ghim được vân tay như
app - báo "không an toàn" một lần vì chứng chỉ tự ký.
"""
from __future__ import annotations

import html
import http.client
import json
import ipaddress
import re
import socket
from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path
from typing import Any, Callable
from urllib.parse import unquote, urlsplit

from .music_plan import TRACK_NAME

COOKIE = "abook_device"
COOKIE_SECONDS = 365 * 24 * 3600
# Trên máy chủ cục bộ, yêu cầu mang header này là yêu cầu TỪ XA (chỉ `forward` gắn nó): `paths` chỉ được nằm trong
# thư mục tải lên, `target` bị bỏ qua (server.py `_remote`). Soát bảo mật 28-09: danh sách trắng lọc ĐƯỜNG, còn tham số
# thì mở cả ổ đĩa và đường UNC (máy khác trong mạng) cho thiết bị ở xa.
REMOTE_HEADER = "X-Abook-Remote"
MAX_FORWARD_BODY = 24 * 1024 * 1024  # ảnh bìa: máy chủ cục bộ nhận tới ~21,3 MB data URL (covers.MAX_UPLOAD_BYTES)
CHUNK = 256 * 1024
# Tuỳ chọn máy tính mà thiết bị ở xa không cần thấy: sách mở gần đây (đường dẫn), chỗ đang nghe theo đường dẫn.
PRIVATE_PREFERENCES = ("recents", "positions")
FORWARD_SECONDS = 120  # tìm bìa trên mạng, tạo sách từ vài trăm chương - không phải lời gọi nào cũng tức thì

_BOOK = r"/api/books/[A-Za-z0-9_-]+"
_LISTEN = r"/api/listen/books/[A-Za-z0-9_-]+"
_RECORD = _LISTEN + r"/records/r-[0-9a-f]{16}"
_MEDIA = r"/media/books/[A-Za-z0-9_-]+"
# Phần Nghe: thư viện nghe, trình phát, chỗ nghe, dấu trang, hồ sơ nghe, đọc theo (chữ chương), dàn nhân vật và câu
# mẫu, audio, bìa - đúng những gì app điện thoại đã có qua /sync/v1, nên mọi thiết bị đã ghép đều được (chế độ chỉ
# nghe). Không có gì của Studio.
LISTEN_ROUTES: tuple[tuple[str, re.Pattern[str]], ...] = tuple((method, re.compile(pattern)) for method, pattern in (
    ("GET", r"/api/app"),
    ("GET", r"/api/preferences"),
    ("GET", r"/api/listen/library"),
    ("GET", _LISTEN),
    ("POST", _LISTEN + r"/progress"),
    ("POST", _LISTEN + r"/chapters/\d+/done"),
    ("POST", _LISTEN + r"/finished"),
    ("POST", _LISTEN + r"/rate"),
    ("POST", _LISTEN + r"/bookmarks"),
    ("PUT", _LISTEN + r"/bookmarks/[0-9a-f]+"),
    ("DELETE", _LISTEN + r"/bookmarks/[0-9a-f]+"),
    ("POST", _LISTEN + r"/bookmarks/restore"),
    ("GET", _LISTEN + r"/records"),
    ("POST", _LISTEN + r"/records"),
    ("POST", _RECORD + r"/activate"),
    ("PUT", _RECORD),
    ("POST", _RECORD + r"/move"),
    ("DELETE", _RECORD),
    ("POST", _LISTEN + r"/night"),
    ("POST", _LISTEN + r"/reading"),
    ("GET", _LISTEN + r"/sessions"),
    ("POST", _LISTEN + r"/sessions"),
    ("GET", r"/api/listen/night"),
    ("POST", r"/api/listen/night/dismiss"),
    ("GET", _MEDIA + r"/chapters/\d+"),
    ("GET", _MEDIA + r"/cover"),
    ("GET", _BOOK + r"/cast"),
    ("GET", _BOOK + r"/chapters/\d+/script"),
    ("GET", _LISTEN + r"/chapters/\d+/text"),  # chữ của chương trong sách chỉ-chữ (textbook.py)
    ("GET", r"/media/voices/[^/]+"),
    ("GET", _MEDIA + r"/samples/\d+"),
    # Nhạc nền của trình phát (httpSource.ts, musicBed.ts): mốc nhạc từng chương, bài đóng trong sách (và bài "Nhạc của tôi"
    # mà đoạn của cuốn này dùng - chỉ qua đường theo sách), bài trong danh mục (máy chủ chỉ tải bài CÓ trong danh mục -
    # server.music_track_file - nên không thành chỗ tải hộ link tuỳ ý).
    ("GET", _BOOK + r"/music/chapters/\d+"),
    ("GET", _BOOK + r"/music/files/" + TRACK_NAME),
    ("GET", r"/api/music/track"),
    # Danh sách phát của sách chỉ có chữ (music_playlist.py): hàng bài của cuốn + các danh sách để chọn. Bài "Nhạc của tôi" vẫn
    # không ra khỏi máy này (đường /api/music/local/... không có ở đây).
    ("GET", _BOOK + r"/music/playlist"),
    ("GET", r"/api/music/playlists"),
))
# Thêm cho thiết bị được điều khiển sản xuất: dự án, bắt đầu/dừng, tạo sách, duyệt phân vai, giọng, bìa.
ALLOWED: tuple[tuple[str, re.Pattern[str]], ...] = LISTEN_ROUTES + tuple((method, re.compile(pattern)) for method, pattern in (
    ("GET", r"/api/library"),
    ("GET", r"/api/voices"),
    ("POST", r"/api/scan"),
    ("POST", r"/api/sources/upload"),
    ("POST", r"/api/sources/split"),
    ("POST", r"/api/first-person"),
    ("POST", r"/api/books"),
    ("GET", _BOOK),
    ("GET", _BOOK + r"/activity"),
    ("GET", _BOOK + r"/pending-changes"),
    ("POST", _BOOK + r"/pending-changes/withdraw"),
    ("POST", _BOOK + r"/chapters/\d+/retake"),
    ("POST", _BOOK + r"/characters/merge"),
    ("POST", _BOOK + r"/characters/rename"),
    ("PUT", _BOOK + r"/chapters/\d+/title"),
    ("POST", _BOOK + r"/start"),
    ("POST", _BOOK + r"/stop"),
    ("POST", _BOOK + r"/pause"),
    ("POST", _BOOK + r"/export"),
    ("POST", _BOOK + r"/bookfile"),
    ("GET", _BOOK + r"/export-size"),
    ("GET", _BOOK + r"/review"),
    ("POST", _BOOK + r"/review"),
    ("GET", _BOOK + r"/work"),
    ("GET", _BOOK + r"/casting"),
    ("GET", _BOOK + r"/casting/\d+"),
    ("GET", _BOOK + r"/continuation"),
    ("GET", _BOOK + r"/parts"),
    ("GET", _BOOK + r"/pronunciations"),
    ("POST", _BOOK + r"/pronunciation"),
    # "Nghe thử" cách đọc tên (reading_preview.py): dùng card đồ hoạ của máy tính - chỉ thiết bị được điều khiển sản xuất, không
    # nằm trong LISTEN_ROUTES. Cả lượt (chờ hàng + nạp + đọc) nằm trong FORWARD_SECONDS (reading_preview.REQUEST_BUDGET).
    ("POST", _BOOK + r"/pronunciation/preview"),
    ("GET", _MEDIA + r"/reading-previews/[0-9a-f]{32}\.wav"),
    ("GET", _BOOK + r"/shared-readings"),
    ("POST", _BOOK + r"/shared-readings"),
    ("GET", r"/api/readings"),
    ("GET", r"/api/analysis-models"),
    ("POST", r"/api/readings"),
    ("POST", _BOOK + r"/speaker"),
    ("POST", _BOOK + r"/voice"),
    ("POST", _BOOK + r"/line"),
    ("GET", _BOOK + r"/voices"),
    ("GET", _BOOK + r"/cover/search"),
    ("PUT", _BOOK + r"/cover"),
    ("DELETE", _BOOK + r"/cover"),
    # Tab Nhạc nền (MusicTab.tsx): xem, chỉnh, dựng lại, "Đổi bài".
    ("GET", _BOOK + r"/music"),
    ("PUT", _BOOK + r"/music"),
    ("POST", _BOOK + r"/music/rebuild"),
    # "Đọc không khí cả đoạn bằng AI": xem model đã tải chưa và tính lại; TẢI model (3,2 GB về máy chủ sách) chỉ làm trên chính máy ấy.
    ("POST", _BOOK + r"/music/moods"),
    ("GET", r"/api/music/moods-model"),
    ("GET", _BOOK + r"/music/scenes/[^/]+/alternatives"),
))
TYPES = {
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".woff2": "font/woff2",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".webmanifest": "application/manifest+json",
}


@dataclass
class StudioGate:
    """Những gì cổng đồng bộ cần biết về máy chủ giao diện cục bộ để chuyển tiếp."""

    allowed: Callable[[], bool]  # công tắc của người dùng, đọc mỗi yêu cầu
    port: Callable[[], int]  # cổng của máy chủ giao diện cục bộ (0: chưa chạy)
    token: str | None  # mã phiên của máy chủ ấy
    static_dir: Path  # bản dựng giao diện web (npm run build)


def permitted(method: str, path: str, *, producing: bool = True) -> bool:
    """Đường này có mở cho thiết bị ở xa không: `producing` = được điều khiển sản xuất (cả danh sách), không thì chỉ phần
    Nghe."""
    verb = "GET" if method == "HEAD" else method
    return any(verb == allowed and pattern.fullmatch(path) for allowed, pattern in (ALLOWED if producing else LISTEN_ROUTES))


def cookie_token(header: str | None) -> str:
    """Mã thiết bị trong cookie. Tự tách theo `;`: `SimpleCookie` dừng ở cookie hỏng đầu tiên (của trang khác cùng máy),
    và trình duyệt đã ghép lại thấy trang nhập mã."""
    for part in (header or "").split(";"):
        name, _, value = part.strip().partition("=")
        if name == COOKIE and value:
            return value.strip().strip('"')
    return ""


def allowed_host(header: str | None) -> bool:
    """Chặn DNS rebinding: trang của một tên miền lạ trỏ về IP LAN của máy này gửi `Host: ten-mien-la`. Chỉ nhận IP,
    tên máy (`<máy>`, `<máy>.local`, `<máy>.lan`) và localhost."""
    host = (header or "").strip().lower()
    if host.startswith("["):  # IPv6 dạng [::1]:47630
        host = host[1 : host.find("]")] if "]" in host else host
    else:
        host = host.rsplit(":", 1)[0] if host.count(":") == 1 else host
    if not host:
        return False
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        pass
    machine = socket.gethostname().lower()
    return host in {"localhost", machine, f"{machine}.local", f"{machine}.lan", f"{machine}.home"}


def same_origin(headers: Any) -> bool:
    """Lệnh GHI mang cookie phải đến từ chính trang Studio: `Sec-Fetch-Site` (trình duyệt đời mới, WebView) hay `Origin`
    trùng `Host`. SameSite=Strict không phân biệt cổng - trang ở cổng khác của cùng IP vẫn là "same-site"."""
    fetch_site = (headers.get("Sec-Fetch-Site") or "").lower()
    if fetch_site:
        return fetch_site in ("same-origin", "none")
    origin = headers.get("Origin")
    if origin:
        return urlsplit(origin).netloc.lower() == (headers.get("Host") or "").lower()
    return True  # không phải trình duyệt: không có cookie tự gửi kèm để lợi dụng


def device_cookie(token: str) -> str:
    return f"{COOKIE}={token}; Path=/; Max-Age={COOKIE_SECONDS}; HttpOnly; Secure; SameSite=Strict"


def send_bytes(handler: Any, status: int, body: bytes, content_type: str, *,
               cache: str = "no-store", extra: dict[str, str] | None = None) -> None:
    handler.send_response(status)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", cache)
    for name, value in (extra or {}).items():
        handler.send_header(name, value)
    handler.end_headers()
    if handler.command != "HEAD":
        handler.wfile.write(body)


def send_page(handler: Any, status: int, page: str) -> None:
    send_bytes(handler, status, page.encode("utf-8"), "text/html; charset=utf-8")


def forward(handler: Any, method: str, target: str, gate: StudioGate, *, listen_only: bool = False) -> None:
    """Chuyển một yêu cầu đã qua danh sách trắng sang máy chủ giao diện cục bộ, trả nguyên câu trả lời (kể cả audio
    theo từng đoạn `Range`). `/api/app` được sửa cho đúng máy đang xem: không có hộp thoại chọn file của máy này, và
    `listenOnly` khi thiết bị chỉ được nghe (giao diện ẩn Studio)."""
    port = gate.port()
    if not port:
        _json(handler, HTTPStatus.SERVICE_UNAVAILABLE, {"error": "Giao diện của máy tính chưa sẵn sàng"})
        return
    try:
        length = int(handler.headers.get("Content-Length") or 0)
    except ValueError:
        length = -1
    if length < 0 or length > MAX_FORWARD_BODY:
        # Âm thì `rfile.read(-1)` đọc tới hết kết nối - vượt mọi trần. Không đọc thân: đóng kết nối sau câu trả lời.
        handler.close_connection = True
        _json(handler, HTTPStatus.REQUEST_ENTITY_TOO_LARGE if length > 0 else HTTPStatus.BAD_REQUEST,
              {"error": "Yêu cầu quá lớn" if length > 0 else "Content-Length không hợp lệ"})
        return
    body = handler.rfile.read(length) if length else None
    if body is not None and not (handler.headers.get("Content-Type") or "").startswith("application/json"):
        _json(handler, HTTPStatus.UNSUPPORTED_MEDIA_TYPE, {"error": "Chỉ nhận JSON"})
        return
    headers = {"Host": f"127.0.0.1:{port}", "X-Ebook-Token": gate.token or "", REMOTE_HEADER: "1"}
    for name in ("Content-Type", "Range", "If-None-Match", "If-Modified-Since"):
        value = handler.headers.get(name)
        if value:
            headers[name] = value
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=FORWARD_SECONDS)
    try:
        connection.request(method, target, body=body, headers=headers)
        response = connection.getresponse()
        path = urlsplit(target).path
        if method == "GET" and path in ("/api/app", "/api/preferences") and response.status == HTTPStatus.OK:
            info = json.loads(response.read().decode("utf-8"))
            if path == "/api/app":
                info.update(dialogs=False, remote=True, listenOnly=listen_only)
            for key in PRIVATE_PREFERENCES:
                info.pop(key, None)
            if listen_only and "libraryRoot" in info:
                info["libraryRoot"] = ""  # thiết bị chỉ nghe không cần biết thư mục (và tên người dùng) trên máy tính
            _json(handler, HTTPStatus.OK, info)
            return
        handler.send_response(response.status)
        for name in ("Content-Type", "Content-Length", "Content-Range", "Accept-Ranges", "Cache-Control", "ETag",
                     "Last-Modified"):
            value = response.getheader(name)
            if value:
                handler.send_header(name, value)
        handler.end_headers()
        if method == "HEAD":
            return
        while True:
            chunk = response.read(CHUNK)
            if not chunk:
                break
            handler.wfile.write(chunk)
    finally:
        connection.close()


def serve_static(handler: Any, root: Path, path: str) -> None:
    relative = unquote(path).lstrip("/") or "index.html"
    if "\\" in relative or ":" in relative:
        # `\\máy\share` ghép thành đường UNC: Windows tự nối SMB (gửi NTLM) TRƯỚC khi `relative_to` kịp từ chối.
        relative = "index.html"
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        candidate = root / "index.html"
    if not candidate.is_file():
        candidate = root / "index.html"  # trang dùng định tuyến #/..., mọi đường khác về trang chính
    if not candidate.is_file():
        send_page(handler, HTTPStatus.SERVICE_UNAVAILABLE, _page(
            "Chưa có giao diện", "Máy tính này chưa dựng giao diện web (npm run build trong _internal/ui)."))
        return
    cache = "public, max-age=31536000, immutable" if "/assets/" in candidate.as_posix() else "no-cache"
    send_bytes(handler, HTTPStatus.OK, candidate.read_bytes(), TYPES.get(candidate.suffix.lower(),
               "application/octet-stream"), cache=cache)


def closed_page(machine: str) -> str:
    return _page("ABook chưa mở", f"Giao diện ABook trên <b>{html.escape(machine)}</b> chưa chạy. Mở ABook trên máy tính "
                 "rồi tải lại trang này.")


def pairing_page(machine: str) -> str:
    """Trình duyệt chưa ghép: nhập mã 6 số máy tính đưa ra (như điện thoại), cổng đặt cookie rồi mở Studio."""
    return _page("Ghép với ABook", f"""
<p>Ghép trình duyệt này với ABook trên <b>{html.escape(machine)}</b> để nghe sách của máy ấy. Trên máy tính: Cài đặt →
Điện thoại và thiết bị → “Ghép thiết bị mới”, rồi nhập mã 6 số vào đây.</p>
<form id="pair">
  <label>Mã ghép nối<input id="code" inputmode="numeric" autocomplete="one-time-code" maxlength="7" required></label>
  <label>Tên thiết bị này<input id="device" maxlength="80" placeholder="Ví dụ: Điện thoại của Anh"></label>
  <button type="submit">Ghép nối</button>
  <p id="message" role="alert"></p>
</form>
<script>
document.getElementById("pair").addEventListener("submit", async (event) => {{
  event.preventDefault();
  const message = document.getElementById("message");
  message.textContent = "Đang ghép…";
  const device = document.getElementById("device").value.trim() || "Trình duyệt";
  try {{
    const response = await fetch("/sync/v1/pair-browser", {{
      method: "POST",
      headers: {{ "Content-Type": "application/json" }},
      body: JSON.stringify({{ code: document.getElementById("code").value, device }}),
    }});
    const data = await response.json().catch(() => ({{}}));
    if (response.ok) {{
      // Cùng đường "/", chỉ khác phần sau #: phải tự tải lại thì cổng mới trả giao diện thay cho trang này.
      history.replaceState(null, "", "/#/studio");
      location.reload();
    }} else message.textContent = data.error || "Không ghép được";
  }} catch {{
    message.textContent = "Không nói chuyện được với máy tính";
  }}
}});
</script>""")


def _page(title: str, content: str) -> str:
    return f"""<!doctype html><html lang="vi"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)} · ABook</title>
<style>
:root {{ color-scheme: light dark; --bg: #f4f1ec; --fg: #1d1f1c; --muted: #5d625b; --accent: #1f4c3c; --line: #d8d3ca; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg: #0e1115; --fg: #e8e6e1; --muted: #a3a8a0; --accent: #7fc4a4;
  --line: #2b3038; }} }}
body {{ margin: 0; background: var(--bg); color: var(--fg); font: 16px/1.5 system-ui, sans-serif; }}
main {{ max-width: 28rem; margin: 0 auto; padding: 3rem 16px; }}
h1 {{ font-size: 1.4rem; margin: 0 0 1rem; }}
p {{ color: var(--muted); }}
b {{ color: var(--fg); }}
form {{ display: grid; gap: 1rem; margin-top: 1.5rem; }}
label {{ display: grid; gap: .35rem; font-weight: 600; }}
input {{ font: inherit; padding: .7rem .8rem; border: 1px solid var(--line); border-radius: .6rem;
  background: transparent; color: inherit; }}
#code {{ font-size: 1.6rem; letter-spacing: .3em; font-variant-numeric: tabular-nums; }}
button {{ font: inherit; font-weight: 600; padding: .8rem; border: 0; border-radius: .6rem; background: var(--accent);
  color: var(--bg); cursor: pointer; }}
button:focus-visible, input:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 2px; }}
</style>
<main><h1>{html.escape(title)}</h1>{content}</main>
</html>"""


def _json(handler: Any, status: int, payload: Any) -> None:
    send_bytes(handler, status, json.dumps(payload, ensure_ascii=False).encode("utf-8"),
               "application/json; charset=utf-8")
