"""`abook.netconnect`: nối TCP đua IPv6/IPv4 (RFC 8305 gọn). Ca gốc: IPv6 không có đường ra, IPv4 chạy -> phải nối bằng IPv4 trong chưa tới một giây
thay vì chờ hết hạn từng địa chỉ IPv6 như `socket.create_connection` (đo 31-10: Edge TTS chết 25 giây mỗi lần).

"Địa chỉ chết" ở đây là ổ giả có fd thật (đầu một cặp socketpair đã nhồi đầy bộ đệm gửi nên KHÔNG BAO GIỜ báo ghi được) - chạy giống nhau trên mọi hệ điều hành,
không cần mạng thật. Địa chỉ sống là cổng lắng nghe thật trên 127.0.0.1."""
from __future__ import annotations

import ast
import errno
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

from abook import netconnect

INTERNAL = Path(__file__).resolve().parent.parent
REAL_SOCKET = socket.socket
V6, V4 = socket.AF_INET6, socket.AF_INET


class FakeSocket:
    """Ổ giả theo kịch bản: 'hang' = connect treo mãi; 'refuse' = connect xong sau đó báo ECONNREFUSED; 'unreachable' = connect ném ngay."""

    def __init__(self, behaviour: str, family: int) -> None:
        self.behaviour = behaviour
        self.family = family
        self.closed = False
        self.connected_to = None
        self._near, self._far = socket.socketpair()
        self._near.setblocking(False)
        if behaviour == "hang":
            try:
                while True:
                    self._near.send(b"x" * 65536)
            except (BlockingIOError, InterruptedError):
                pass

    def fileno(self) -> int:
        return self._near.fileno()

    def setblocking(self, flag: bool) -> None:
        pass

    def settimeout(self, value) -> None:
        pass

    def setsockopt(self, *args) -> None:
        pass

    def bind(self, address) -> None:
        pass

    def connect(self, address) -> None:
        self.connected_to = address
        if self.behaviour == "unreachable":
            raise OSError(errno.ENETUNREACH, "network unreachable")
        raise BlockingIOError(errno.EWOULDBLOCK, "in progress")

    def getsockopt(self, level, option) -> int:
        return errno.ECONNREFUSED if self.behaviour == "refuse" else 0

    def close(self) -> None:
        self.closed = True
        self._near.close()
        self._far.close()


def info(family: int, address: str, port: int = 80) -> tuple:
    return (family, socket.SOCK_STREAM, 6, "", (address, port, 0, 0) if family == V6 else (address, port))


@pytest.fixture(autouse=True)
def clean_state():
    netconnect.reset_preference()
    yield
    netconnect.reset_preference()


@pytest.fixture
def listener():
    server = REAL_SOCKET(V4, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(8)
    yield server
    server.close()


def script(monkeypatch, infos: list[tuple], fakes: dict[int, list[str]]):
    """getaddrinfo -> `infos`; ổ của họ có trong `fakes` là ổ giả (lần lượt theo kịch bản), họ còn lại là ổ thật. Trả danh sách ổ giả đã tạo."""
    created: list[FakeSocket] = []
    prepared = {family: [FakeSocket(behaviour, family) for behaviour in behaviours] for family, behaviours in fakes.items()}  # tạo TRƯỚC khi thay socket.socket

    def factory(family, kind, proto=0):
        if prepared.get(family):
            fake = prepared[family].pop(0)
            created.append(fake)
            return fake
        return REAL_SOCKET(family, kind, proto)

    class Namespace:  # chỉ `abook.netconnect` thấy ổ giả; phần còn lại của tiến trình (listener.accept...) vẫn dùng socket thật
        socket = staticmethod(factory)
        getaddrinfo = staticmethod(lambda *args, **kwargs: infos)

        def __getattr__(self, name):
            return getattr(socket, name)

    monkeypatch.setattr(netconnect, "socket", Namespace())
    return created


def test_blackholed_ipv6_does_not_delay_a_working_ipv4(monkeypatch, listener):
    port = listener.getsockname()[1]
    infos = [info(V6, "2001:db8::1", port), info(V6, "2001:db8::2", port), info(V4, "127.0.0.1", port), info(V4, "127.0.0.1", port)]
    created = script(monkeypatch, infos, {V6: ["hang", "hang"]})
    started = time.monotonic()
    sock = netconnect.create_connection(("fake.example", port), timeout=8)
    elapsed = time.monotonic() - started
    try:
        assert elapsed < 1.0
        assert sock.family == V4 and sock.gettimeout() == 8  # ổ chặn kèm hạn của người gọi, như stdlib
        accepted, _ = listener.accept()
        accepted.sendall(b"ok")
        assert sock.recv(2) == b"ok"
        accepted.close()
    finally:
        sock.close()
    assert created and all(fake.closed for fake in created)  # lần đang treo bị đóng khi có người thắng


def test_default_timeout_is_applied_like_stdlib(monkeypatch, listener):
    port = listener.getsockname()[1]
    script(monkeypatch, [info(V4, "127.0.0.1", port)], {})
    monkeypatch.setattr(netconnect.socket, "getdefaulttimeout", lambda: 3.5, raising=False)
    sock = netconnect.create_connection(("fake.example", port))
    try:
        assert sock.gettimeout() == 3.5
    finally:
        sock.close()


def test_families_are_interleaved():
    infos = [info(V6, "::1"), info(V6, "::2"), info(V6, "::3"), info(V4, "1.1.1.1"), info(V4, "2.2.2.2")]
    assert [item[4][0] for item in netconnect.interleave(infos)] == ["::1", "1.1.1.1", "::2", "2.2.2.2", "::3"]
    infos = [info(V4, "1.1.1.1"), info(V6, "::1")]
    assert [item[4][0] for item in netconnect.interleave(infos)] == ["1.1.1.1", "::1"]
    only = [info(V4, "1.1.1.1"), info(V4, "2.2.2.2")]
    assert netconnect.interleave(only) == only


def test_attempts_start_in_interleaved_order_and_failure_starts_the_next_at_once(monkeypatch):
    monkeypatch.setattr(netconnect, "STAGGER_SECONDS", 30.0)  # nếu "hỏng thì thử liền" sai, bài này treo tới hết hạn
    infos = [info(V6, "::1"), info(V6, "::2"), info(V4, "1.1.1.1"), info(V4, "2.2.2.2")]
    created = script(monkeypatch, infos, {V6: ["unreachable", "refuse"], V4: ["refuse", "refuse"]})
    started = time.monotonic()
    with pytest.raises(OSError) as raised:
        netconnect.create_connection(("fake.example", 80), timeout=10)
    assert time.monotonic() - started < 2.0
    assert [fake.connected_to[0] for fake in created] == ["::1", "1.1.1.1", "::2", "2.2.2.2"]
    assert raised.value.errno == errno.ECONNREFUSED  # lỗi cuối, như stdlib
    assert all(fake.closed for fake in created)


def test_all_errors_gives_an_exception_group(monkeypatch):
    infos = [info(V6, "::1"), info(V4, "1.1.1.1")]
    script(monkeypatch, infos, {V6: ["unreachable"], V4: ["refuse"]})
    with pytest.raises(ExceptionGroup) as raised:
        netconnect.create_connection(("fake.example", 80), timeout=5, all_errors=True)
    assert len(raised.value.exceptions) == 2


def test_overall_timeout_covers_all_attempts_together(monkeypatch):
    infos = [info(V6, "::1"), info(V6, "::2"), info(V4, "1.1.1.1"), info(V4, "2.2.2.2")]
    created = script(monkeypatch, infos, {V6: ["hang", "hang"], V4: ["hang", "hang"]})
    started = time.monotonic()
    with pytest.raises(TimeoutError):
        netconnect.create_connection(("fake.example", 80), timeout=1.0)
    elapsed = time.monotonic() - started
    assert 0.9 <= elapsed < 2.0  # không phải 4 x 1,0
    assert len(created) == 4 and all(fake.closed for fake in created)


def test_slow_dns_counts_against_the_overall_timeout(monkeypatch):
    infos = [info(V6, "::1"), info(V4, "1.1.1.1")]
    script(monkeypatch, infos, {V6: ["hang"], V4: ["hang"]})
    real = netconnect.socket.getaddrinfo

    def slow(*args, **kwargs):
        time.sleep(0.6)
        return real(*args, **kwargs)

    monkeypatch.setattr(netconnect.socket, "getaddrinfo", slow)
    started = time.monotonic()
    with pytest.raises(TimeoutError):
        netconnect.create_connection(("fake.example", 80), timeout=1.0)
    assert time.monotonic() - started < 1.35  # 0,6 DNS + 0,4 còn lại, không phải 0,6 + 1,0


def test_literal_address_behaves_like_before(listener):
    port = listener.getsockname()[1]
    sock = netconnect.create_connection(("127.0.0.1", port), timeout=2, source_address=("127.0.0.1", 0))
    try:
        assert sock.getpeername() == ("127.0.0.1", port) and sock.gettimeout() == 2
        assert sock.getsockname()[0] == "127.0.0.1"
    finally:
        sock.close()
    closed = REAL_SOCKET(V4, socket.SOCK_STREAM)
    closed.bind(("127.0.0.1", 0))
    free_port = closed.getsockname()[1]
    closed.close()
    with pytest.raises(ConnectionRefusedError):
        netconnect.create_connection(("127.0.0.1", free_port), timeout=10)  # Windows báo "từ chối" sau ~2 giây (SYN thử lại)


def test_unresolvable_host_raises_gaierror(monkeypatch):
    def fail(*args, **kwargs):
        raise socket.gaierror(socket.EAI_NONAME, "no such host")

    monkeypatch.setattr(socket, "getaddrinfo", fail)
    with pytest.raises(socket.gaierror):
        netconnect.create_connection(("nowhere.invalid", 80), timeout=1)


def test_family_that_just_won_is_tried_first_next_time(monkeypatch, listener):
    port = listener.getsockname()[1]
    infos = [info(V6, "2001:db8::1", port), info(V4, "127.0.0.1", port)]
    script(monkeypatch, infos, {V6: ["hang"]})
    netconnect.create_connection(("fake.example", port), timeout=5).close()
    assert [item[0] for item in netconnect.interleave(infos)] == [V4, V6]
    monkeypatch.setattr(netconnect, "PREFERENCE_SECONDS", 0.0)
    netconnect.reset_preference()
    assert [item[0] for item in netconnect.interleave(infos)] == [V6, V4]


# ---- phủ khắp app: một chỗ cài, không lối vào nào quên được ------------------------------------------------------------

def run_python(code: str) -> str:
    result = subprocess.run([sys.executable, "-X", "utf8", "-c", code], cwd=INTERNAL, capture_output=True, text=True, encoding="utf-8", timeout=120, check=False)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def test_importing_abook_installs_it_for_http_client_and_urllib():
    out = run_python("""
import socket
real = socket.create_connection
import abook, http.client, urllib.request
assert socket.create_connection is not real
import abook.netconnect as n
assert socket.create_connection is n.create_connection
assert http.client.HTTPSConnection('example.com')._create_connection is n.create_connection
print('ok')
""")
    assert out == "ok"


@pytest.mark.parametrize("module", ["abook.webui.server", "abook.cli", "abook.worker", "abook.pipeline", "abook.webui.studio_setup",
                                    "abook.readaloud.edge", "abook.webui.peer_studio", "abook.webui.remote_books"])
def test_every_entry_point_has_it_after_import(module):
    out = run_python(f"""
import importlib, socket
importlib.import_module({module!r})
import abook.netconnect as n
print(socket.create_connection is n.create_connection)
""")
    assert out == "True"


def test_requests_through_urllib3_also_races_and_still_works():
    out = run_python("""
import threading, http.server
import abook
import requests, urllib3.util.connection as c
assert getattr(c.create_connection, '__abook_netconnect__', False)
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.send_header('Content-Length', '2'); self.end_headers(); self.wfile.write(b'ok')
    def log_message(self, *a): pass
server = http.server.HTTPServer(('127.0.0.1', 0), H)
threading.Thread(target=server.serve_forever, daemon=True).start()
print(requests.get(f'http://localhost:{server.server_port}/', timeout=5).text)
""")
    assert out == "ok"


def test_nothing_else_replaces_or_bypasses_the_hook():
    """Một lối nối mới viết tay (gán lại socket.create_connection, hay `from socket import create_connection` chụp bản gốc trước khi cài) sẽ phá phủ này."""
    offenders: list[str] = []
    for path in list((INTERNAL / "abook").rglob("*.py")) + [INTERNAL / "app.py"]:
        if path.name == "netconnect.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "socket" and any(alias.name == "create_connection" for alias in node.names):
                offenders.append(f"{path.relative_to(INTERNAL)}:{node.lineno} from socket import create_connection")
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Attribute) and t.attr == "create_connection" for t in node.targets):
                offenders.append(f"{path.relative_to(INTERNAL)}:{node.lineno} gán create_connection")
    assert not offenders, offenders


def test_package_init_installs_it_before_anything_else_can_connect():
    tree = ast.parse((INTERNAL / "abook" / "__init__.py").read_text(encoding="utf-8"))
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "install"]
    assert calls, "abook/__init__.py phải gọi netconnect.install()"


def test_scripts_that_download_in_the_studio_venv_import_abook_first():
    """Các đoạn mã `python -c` chạy trong venv Studio tải model bằng huggingface_hub (httpx -> socket.create_connection): phải `import abook` trước lần tải đầu."""
    from abook.webui import studio_setup

    for name in ("VOICE_SCRIPT", "ASR_SCRIPT", "QA_SCRIPT"):
        text = getattr(studio_setup, name)
        download = min(text.find(marker) for marker in ("snapshot_download(", "hf_hub_download(") if marker in text)
        assert "import abook" in text or "from abook" in text, name
        first = min(index for index in (text.find("import abook"), text.find("from abook")) if index >= 0)
        assert first < download, f"{name}: tải trước khi nạp abook"
