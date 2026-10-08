"""Chọn đường tới một máy đã ghép: Wi-Fi khi thông, Bluetooth khi không - bản máy tính của `Route.kt` (điện thoại).

Ghép một lần, máy kia có thể có hai đường (địa chỉ LAN + cổng; địa chỉ Bluetooth). Mỗi yêu cầu đi Wi-Fi khi địa chỉ LAN đang
thông, Bluetooth khi không; đường nào đang thông được nhớ lại.

KHÔNG BAO GIỜ CHẶN người gọi (giao diện và luồng hỏi trình phát gọi liên tục): chọn theo kết quả thử đã biết; kết quả cũ hơn
FRESH_SECONDS hay chưa có thì thử lại ở luồng nền (nối TCP 1,5 giây) - lần gọi sau thấy kết quả mới. Yêu cầu qua LAN hỏng lúc
nối thì `mark_down` ngay (remote_books._connect): yêu cầu ấy thử lại qua Bluetooth, các yêu cầu sau đi thẳng Bluetooth.
"""
from __future__ import annotations

import socket
import threading
import time
from typing import Callable, NamedTuple

FRESH_SECONDS = 60.0
PROBE_SECONDS = 1.5

_seen: dict[str, tuple[bool, float]] = {}  # "host:cổng" -> (thông không, lúc thử)
_probing: set[str] = set()
_lock = threading.Lock()


class Choice(NamedTuple):
    """`lan` = "host:cổng" đi Wi-Fi, hay `bluetooth` = địa chỉ Bluetooth; cả hai None khi máy kia không có đường nào."""

    lan: str | None
    bluetooth: str | None


def choose(lan: list[str], bluetooth: str | None, known: Callable[[str], bool | None]) -> Choice:
    """Chọn đường, thuần (test được): LAN đã biết là thông -> LAN đầu tiên như thế; không có mà có Bluetooth -> Bluetooth nếu
    mọi LAN đã biết là hỏng hay không có LAN nào; còn lại (chưa biết) -> LAN đầu tiên chưa thử (lạc quan: cùng Wi-Fi là thường
    gặp nhất) - không có thì Bluetooth."""
    for target in lan:
        if known(target) is True:
            return Choice(target, None)
    bt = bluetooth or None
    if bt is not None and (not lan or all(known(target) is False for target in lan)):
        return Choice(None, bt)
    untried = next((target for target in lan if known(target) is None), None)
    if untried is not None:
        return Choice(untried, None)
    if bt is not None:
        return Choice(None, bt)
    return Choice(lan[0], None) if lan else Choice(None, None)


def pick(lan: list[str], bluetooth: str | None, *, now: float | None = None,
         probe: Callable[[str], bool] | None = None) -> Choice:
    """Chọn đường cho các địa chỉ ấy, và thử lại nền những địa chỉ chưa biết hay đã cũ."""
    now = time.time() if now is None else now
    for target in lan:
        with _lock:
            last = _seen.get(target)
            stale = (last is None or now - last[1] > FRESH_SECONDS) and target not in _probing
            if stale:
                _probing.add(target)
        if stale:
            threading.Thread(target=_probe_in_background, args=(target, probe or _reachable),
                             name="route-probe", daemon=True).start()
    with _lock:
        snapshot = dict(_seen)
    return choose(lan, bluetooth, lambda target: snapshot[target][0] if target in snapshot else None)


def mark_down(target: str) -> None:
    with _lock:
        _seen[target] = (False, time.time())


def mark_up(target: str) -> None:
    with _lock:
        _seen[target] = (True, time.time())


def reset() -> None:
    """Quên mọi kết quả thử (bài thử)."""
    with _lock:
        _seen.clear()
        _probing.clear()


def _probe_in_background(target: str, probe: Callable[[str], bool]) -> None:
    try:
        up = probe(target)
        with _lock:
            _seen[target] = (up, time.time())
    finally:
        with _lock:
            _probing.discard(target)


def _reachable(target: str) -> bool:
    host, _, port = target.rpartition(":")
    try:
        with socket.create_connection((host, int(port)), timeout=PROBE_SECONDS):
            return True
    except (OSError, ValueError):
        return False
