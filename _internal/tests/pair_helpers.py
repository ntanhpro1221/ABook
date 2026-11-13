"""Ghép như người dùng nhập mã TAY (soát bảo mật 12-11): lần đầu máy chỉ dò chứng chỉ và trả "mã nhận máy" để so (mã chưa gửi),
người dùng thấy khớp thì bấm "Đúng, ghép" - lần gọi thứ hai mang vân tay ấy. Cho các bài thử chức năng không xét chính bước so."""
from __future__ import annotations

from typing import Any

from abook.webui import remote_books


def pair_confirmed(computers: remote_books.Computers, address: str, code: str, device: str, **options: Any) -> dict[str, Any]:
    try:
        return computers.pair(address, code, device, **options)
    except remote_books.PairConfirm as confirm:
        return computers.pair(address, code, device, fingerprint=confirm.fingerprint, **options)


def pair_app(app: Any, address: str, code: str) -> dict[str, Any]:
    from abook.webui.server import ApiError

    try:
        return app.pair_computer(address, code)
    except ApiError as error:
        if error.status != 409 or "confirm" not in error.extra:
            raise
        return app.pair_computer(address, code, error.extra["confirm"]["fingerprint"])
