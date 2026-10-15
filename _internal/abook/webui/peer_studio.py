"""Studio của máy tính đã ghép, mở ngay trong app máy này (soát a27 lỗi 14): không ghép lần hai, không cảnh báo chứng chỉ.

Máy chủ giao diện của máy này làm CẦU NỐI: trang của chính máy này gọi `/api/peers/<máy>/studio/<đường của Studio>` và máy
chủ chuyển tiếp sang cổng đồng bộ của máy kia qua TLS ghim vân tay (remote_books._open), mang mã thiết bị máy này nhận lúc
ghép - mã ấy chính là dòng thiết bị của máy này ở máy kia, nên máy kia xét như mọi thiết bị đã ghép (remote_studio.py: công
tắc "Điều khiển sản xuất", quyền của thiết bị, danh sách trắng). Mã chỉ nằm ở máy chủ, không bao giờ xuống trang; mã phiên
của trang (`?t=`) không bao giờ sang máy kia.

Hai lớp chặn ở máy này, trước khi có gì đi ra mạng: cùng luật Origin của Studio từ xa (trang lạ trên máy này có mở được
127.0.0.1 cũng không mượn được cầu nối), và cùng danh sách trắng `remote_studio.ALLOWED` - không mở thêm đường nào. Giao diện
là của máy này (cùng mã, khác gốc API: ui/src/studio/api.ts `peerRoot`).
"""
from __future__ import annotations

import http.client
import json
import re
from http import HTTPStatus
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit

from . import remote_books, remote_studio, tls

PATH = re.compile(r"/api/peers/([0-9a-f]{12})/studio(/.+)")
MISMATCH = "Cập nhật ABook ở hai máy cùng phiên bản"
CHECK_SECONDS = 4  # hỏi máy kia có cho thiết bị này sửa không (sau một lời từ chối)


def listen_only(name: str) -> str:
    """Máy kia chưa cho dòng thiết bị của máy này "Điều khiển sản xuất": nói bật ở đâu, có tên máy."""
    return f"Chỉ nghe - bật quyền sửa ở {name}: Cài đặt > Thiết bị"


def bridge(handler: Any, computer: str, computers: remote_books.Computers, version: str) -> None:
    """Chuyển một yêu cầu của trang máy này sang Studio của máy `computer` và trả nguyên câu trả lời (kể cả audio theo `Range`
    và lỗi kèm trường riêng như `suggestion`). Máy kia tắt / mất mạng: 503 `unreachable` để trang báo và tự nối lại."""
    method = handler.command
    parts = urlsplit(handler.path)
    path = parts.path.removeprefix(f"/api/peers/{computer}/studio")
    query = urlencode([(key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True) if key != "t"])
    if not remote_studio.same_origin(handler.headers):
        remote_studio._json(handler, HTTPStatus.FORBIDDEN, {"error": "Yêu cầu không đến từ trang ABook của máy này"})
        return
    entry = computers.get(computer)
    if entry is None:
        remote_studio._json(handler, HTTPStatus.NOT_FOUND, {"error": "Máy này không ghép với máy ấy"})
        return
    name = str(entry.get("name") or "Máy kia")
    if not remote_studio.permitted(method, path):
        # Nói máy nào (thanh trên cùng của trang đã nói "Studio của <máy>"): việc ấy chỉ làm được ngay trên máy tính đó.
        remote_studio._json(handler, HTTPStatus.FORBIDDEN, {"error": f"Việc này chỉ làm được trên chính máy tính {name}"})
        return
    if entry.get("kind") == "phone":
        remote_studio._json(handler, HTTPStatus.NOT_FOUND, {"error": f"{name} là điện thoại - không có Studio"})
        return
    accepted, body = remote_studio.read_body(handler)
    if not accepted:
        return
    endpoint = remote_books._base(entry)
    extra = {key: value for key in remote_studio.FORWARD_HEADERS if key != "Content-Type" and (value := handler.headers.get(key))}
    try:
        with remote_books._open(endpoint, method, path + (f"?{query}" if query else ""), str(entry["token"]), raw=body,
                                extra=extra, passthrough=True, read_timeout=remote_studio.FORWARD_SECONDS) as (response, _seen):
            if method == "GET" and path == "/api/app" and response.status == HTTPStatus.OK:
                info = json.loads(remote_books._read(response).decode("utf-8"))
                if str(info.get("version") or "") != version:
                    remote_studio._json(handler, HTTPStatus.CONFLICT, {"error": MISMATCH, "mismatch": True})
                    return
                info["peer"] = {"id": computer, "name": name}
                remote_studio._json(handler, HTTPStatus.OK, info)
                return
            if (response.status == HTTPStatus.FORBIDDEN and not remote_studio.permitted(method, path, producing=False)
                    and _listening_only(endpoint, str(entry["token"]))):
                remote_books._read(response)
                remote_studio._json(handler, HTTPStatus.FORBIDDEN, {"error": listen_only(name), "listenOnly": True})
                return
            try:
                remote_studio.relay(handler, method, response)
            except (OSError, http.client.HTTPException):
                handler.close_connection = True  # máy kia ngừng giữa lúc gửi: header đã đi, chỉ còn cắt kết nối
    except remote_books.RemoteError as error:
        if isinstance(error.__cause__, tls.PinError) or endpoint.fingerprint == "":
            remote_studio._json(handler, HTTPStatus.BAD_GATEWAY, {"error": str(error)})
        else:
            remote_studio._json(handler, HTTPStatus.SERVICE_UNAVAILABLE, {"error": remote_books._cut(endpoint), "unreachable": True})


def _listening_only(endpoint: remote_books.Endpoint, token: str) -> bool:
    """Máy kia vừa từ chối một việc của Studio: vì thiết bị này chỉ được nghe (`listenOnly` của nó), hay vì lý do khác của
    chính việc ấy (khi ấy trả nguyên lời của máy kia)."""
    try:
        info = json.loads(remote_books._request(endpoint, "GET", "/api/app", token, timeout=CHECK_SECONDS).decode("utf-8"))
    except (remote_books.RemoteError, ValueError):
        return False
    return isinstance(info, dict) and info.get("listenOnly") is True
