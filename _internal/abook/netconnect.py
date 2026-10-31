"""Nối TCP kiểu "Happy Eyeballs" (RFC 8305, bản gọn) thay cho `socket.create_connection`.

Vì sao: sau khi router mất điện rồi lên lại, nhà mạng thường phát IPv6 nhưng IPv6 không có đường ra. `getaddrinfo` trả địa chỉ
IPv6 trước, `socket.create_connection` thử TUẦN TỰ và mỗi địa chỉ chờ trọn `timeout` -> hai địa chỉ IPv6 chết ăn hết 16-25 giây
trước khi tới IPv4 chạy được ngay (đo 31-10: speech.platform.bing.com, IPv4 nối trong 0,03 giây). Trình duyệt và curl không bị vì
chúng đua các họ địa chỉ. Ở đây cũng vậy: xen kẽ IPv6/IPv4, mở địa chỉ kế sau `STAGGER_SECONDS` (hay ngay khi lần trước hỏng), giữ
các lần trước còn đang chờ, ổ đầu tiên nối xong thắng, còn lại đóng.

Cùng hợp đồng với `socket.create_connection` (kể cả `all_errors`), nên `install()` thay thẳng hàm ấy: `http.client`/`urllib`/`httpx`/
`ssl` đều tra `socket.create_connection` lúc gọi. `abook/__init__.py` gọi `install()` -> mọi lối vào có `import abook` (app, worker,
CLI, máy chủ) đều có, không lối nào quên được. urllib3 (requests) có hàm nối riêng, được bọc lười khi nó được nạp."""

from __future__ import annotations

import importlib.abc
import importlib.machinery
import itertools
import selectors
import socket
import sys
import time
from collections.abc import Callable
from typing import Any

# RFC 8305 mục 5 khuyên 250 ms ("Connection Attempt Delay").
STAGGER_SECONDS = 0.25
# Họ địa chỉ vừa thắng một cuộc đua mà KHÔNG phải họ đứng đầu `getaddrinfo` (IPv6 chết) được xếp đầu trong chừng này giây, để
# các lần nối kế tiếp khỏi trả 250 ms mỗi lần. Hết hạn thì thử lại như thường (IPv6 có thể đã sống lại).
PREFERENCE_SECONDS = 300.0

_DEFAULT = socket._GLOBAL_DEFAULT_TIMEOUT  # cùng dấu hiệu "không đặt hạn" của socket và urllib3

_preferred: tuple[int, float] | None = None  # (họ địa chỉ, hạn dùng theo time.monotonic)


def reset_preference() -> None:
    global _preferred
    _preferred = None


def _preferred_family() -> int | None:
    current = _preferred
    if current is None or time.monotonic() >= current[1]:
        return None
    return current[0]


def interleave(infos: list[tuple]) -> list[tuple]:
    """Xen kẽ các họ địa chỉ: địa chỉ đầu họ thứ nhất, địa chỉ đầu họ thứ hai, địa chỉ kế họ thứ nhất... Thứ tự trong từng họ giữ nguyên
    (getaddrinfo đã xếp theo RFC 6724). Họ thứ nhất = họ của địa chỉ đứng đầu, trừ khi lần đua gần đây cho thấy họ kia mới sống."""
    groups: dict[int, list[tuple]] = {}
    for info in infos:
        groups.setdefault(info[0], []).append(info)
    families = list(groups)
    preferred = _preferred_family()
    if preferred in groups and families[0] != preferred:
        families.remove(preferred)
        families.insert(0, preferred)
    rows = itertools.zip_longest(*(groups[family] for family in families))
    return [info for row in rows for info in row if info is not None]


def _finish(sock: socket.socket, timeout: float | None) -> socket.socket:
    sock.settimeout(timeout)  # trả ổ cho người gọi ở chế độ chặn kèm hạn của họ, như stdlib
    return sock


def _remember(order: list[tuple], winner_family: int) -> None:
    global _preferred
    if winner_family != order[0][0]:
        _preferred = (winner_family, time.monotonic() + PREFERENCE_SECONDS)


def _open(info: tuple, source_address: Any, prepare: Callable[[socket.socket], None] | None, race: bool,
          timeout: float | None) -> tuple[socket.socket, bool]:
    """Tạo ổ cho một địa chỉ và bắt đầu nối. Trả (ổ, đã_nối_xong). `race`: ổ không chặn (nối dở thì trả False); không thì ổ chặn kèm `timeout`."""
    family, kind, proto, _, address = info
    sock = socket.socket(family, kind, proto)
    try:
        if race:
            sock.setblocking(False)
        elif timeout is not None:
            sock.settimeout(timeout)
        if prepare is not None:
            prepare(sock)
        if source_address:
            sock.bind(source_address)
        try:
            sock.connect(address)
        except BlockingIOError:
            return sock, False
        return sock, True
    except BaseException:
        sock.close()
        raise


def _raise(errors: list[BaseException], all_errors: bool):
    try:
        if all_errors:
            raise ExceptionGroup("create_connection failed", list(errors))
        raise errors[-1]
    finally:
        errors.clear()


def _in_turn(order: list[tuple], budget: float | None, timeout: float | None, source_address: Any, all_errors: bool, prepare) -> socket.socket:
    """Lần lượt từng địa chỉ, mỗi địa chỉ trọn `budget` (= `timeout` trừ thời gian tra DNS) - như stdlib. Dùng khi chỉ có một địa chỉ (đua chẳng đua với ai)."""
    errors: list[BaseException] = []
    for info in order:
        try:
            sock, _ = _open(info, source_address, prepare, False, budget)
            return _finish(sock, timeout)
        except OSError as error:
            if not all_errors:
                errors.clear()
            errors.append(error)
    if not errors:
        raise OSError("getaddrinfo returns an empty list")
    _raise(errors, all_errors)


def _race(order: list[tuple], deadline: float | None, timeout: float | None, source_address: Any, all_errors: bool, prepare) -> socket.socket:
    started = time.monotonic()
    queue = list(order)
    selector = selectors.DefaultSelector()
    attempts: dict[socket.socket, tuple] = {}
    errors: list[BaseException] = []
    next_start = started
    winner: socket.socket | None = None
    try:
        while winner is None:
            now = time.monotonic()
            if queue and (not attempts or now >= next_start):
                info = queue.pop(0)
                next_start = now + STAGGER_SECONDS
                try:
                    sock, done = _open(info, source_address, prepare, True, None)
                except OSError as error:
                    errors.append(error)
                    next_start = now  # hỏng ngay (vd. không có đường IPv6) -> thử địa chỉ kế liền
                    continue
                if done:
                    winner = sock
                    _remember(order, info[0])
                    break
                attempts[sock] = info
                selector.register(sock, selectors.EVENT_WRITE)
                continue
            if not attempts and not queue:
                break
            if deadline is not None and now >= deadline:
                errors.append(TimeoutError("timed out"))
                break
            limits = [deadline - now] if deadline is not None else []
            if queue:
                limits.append(next_start - now)
            for key, _ in selector.select(max(0.0, min(limits)) if limits else None):
                sock = key.fileobj
                selector.unregister(sock)
                info = attempts.pop(sock)
                code = sock.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
                if code:
                    errors.append(OSError(code, f"Connect call failed {info[4]}"))
                    sock.close()
                    next_start = time.monotonic()
                    continue
                winner = sock
                _remember(order, info[0])
                break
        if winner is not None:
            return _finish(winner, timeout)
        _raise(errors, all_errors)
    finally:
        for sock in attempts:
            sock.close()
        selector.close()
        errors.clear()


def _connect(host: str, port: int, timeout: Any, source_address: Any, all_errors: bool, family: int = 0,
             prepare: Callable[[socket.socket], None] | None = None) -> socket.socket:
    if timeout is _DEFAULT:
        timeout = socket.getdefaulttimeout()
    # Hạn tính từ TRƯỚC khi tra DNS: tra tên chậm ăn vào hạn chung, không cộng thêm sau nó (PinnedHTTPSConnection: DNS + các địa chỉ chung một hạn).
    deadline = None if timeout is None else time.monotonic() + timeout
    infos = socket.getaddrinfo(host, port, family, socket.SOCK_STREAM)
    if not infos:
        raise OSError("getaddrinfo returns an empty list")
    order = interleave(infos)
    if len(order) == 1 or timeout == 0:
        budget = timeout
        if deadline is not None and timeout:
            budget = deadline - time.monotonic()
            if budget <= 0:
                raise TimeoutError("timed out")
        return _in_turn(order, budget, timeout, source_address, all_errors, prepare)
    return _race(order, deadline, timeout, source_address, all_errors, prepare)


def create_connection(address, timeout=_DEFAULT, source_address=None, *, all_errors=False) -> socket.socket:
    """Thay `socket.create_connection`: cùng đối số, cùng kết quả (ổ chặn kèm hạn `timeout`), cùng lỗi (lỗi cuối; `all_errors` -> ExceptionGroup);
    khác ở chỗ đua các họ địa chỉ thay vì thử tuần tự. `timeout` là hạn CHUNG cho cả cuộc đua, không phải mỗi địa chỉ."""
    host, port = address
    return _connect(host, port, timeout, source_address, all_errors)


# ---- urllib3 (requests) có hàm nối riêng; bọc khi nó được nạp, không nạp nó sớm (≈120 ms) chỉ để bọc ----------------------

def _urllib3_create_connection(address, timeout=_DEFAULT, source_address=None, socket_options=None, *, _family: Callable[[], int]):
    host, port = address
    if host.startswith("["):
        host = host.strip("[]")

    def prepare(sock: socket.socket) -> None:
        for option in socket_options or ():
            sock.setsockopt(*option)

    return _connect(host, port, timeout, source_address, False, _family(), prepare)


def _patch_urllib3(module: Any) -> None:
    if getattr(module.create_connection, "__abook_netconnect__", False):
        return
    family = module.allowed_gai_family

    def create(address, timeout=_DEFAULT, source_address=None, socket_options=None):
        return _urllib3_create_connection(address, timeout, source_address, socket_options, _family=family)

    create.__abook_netconnect__ = True  # type: ignore[attr-defined]
    module.create_connection = create


class _Urllib3Hook(importlib.abc.MetaPathFinder):
    NAME = "urllib3.util.connection"
    done = False

    def find_spec(self, fullname, path=None, target=None):
        if self.done or fullname != self.NAME:
            return None
        self.done = True  # không gỡ khỏi sys.meta_path giữa lúc import đang duyệt nó
        spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        if spec is None or spec.loader is None:
            return spec
        loader = spec.loader
        original = loader.exec_module

        def exec_module(module):
            original(module)
            _patch_urllib3(module)

        loader.exec_module = exec_module  # type: ignore[method-assign]
        return spec


def install() -> None:
    """Một lần mỗi tiến trình, an toàn gọi lại. Gọi từ `abook/__init__.py`."""
    socket.create_connection = create_connection
    module = sys.modules.get(_Urllib3Hook.NAME)
    if module is not None:
        _patch_urllib3(module)
    elif not any(isinstance(finder, _Urllib3Hook) for finder in sys.meta_path):
        sys.meta_path.insert(0, _Urllib3Hook())
