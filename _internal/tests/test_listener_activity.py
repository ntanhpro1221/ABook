from types import SimpleNamespace

from abook.webui import listener_activity


def probe(last_input, now, ok=True):
    def read(pointer):
        pointer._obj.dwTime = last_input
        assert pointer._obj.cbSize == 8
        return ok
    return listener_activity.windows_idle_ms(SimpleNamespace(GetLastInputInfo=read), SimpleNamespace(GetTickCount=lambda: now))


def test_global_input_and_uptime_wrap():
    assert probe(90_000, 90_500) == 500
    assert probe(0xFFFFFF00, 0x100) == 512
    # ctypes' default signed DWORD return is handled too.
    assert probe(0x80000000, -2147483148) == 500


def test_failed_probe_is_unknown():
    assert probe(0, 9_000_000, ok=False) is None


def test_unsupported_os_is_unknown(monkeypatch):
    monkeypatch.setattr(listener_activity.sys, "platform", "unsupported")
    assert listener_activity.system_idle_ms() is None


def test_endpoint_never_uses_a_remote_clients_server_idle_time(monkeypatch):
    from abook.webui.server import Handler
    monkeypatch.setattr(listener_activity, "system_idle_ms", lambda: 1234)
    for address, expected in (("127.0.0.1", 1234), ("::1", 1234), ("192.168.1.2", None)):
        replies = []
        handler = SimpleNamespace(client_address=(address, 12345), _send_json=lambda status, body: replies.append(body))
        Handler.get_listener_activity(handler, {})
        assert replies == [{"idleMs": expected}]


def test_auto_sleep_copy_matches_all_three_platforms():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    paths = ["ui/src/listen/sleepActivity.ts", "desktop_qt/src/systemidle.h",
             "mobile/android/app/src/main/java/vn/abook/player/SleepPolicy.kt"]
    for sentence in ("Tự hẹn theo lịch đêm", "Chạm để nghe tiếp"):
        for path in paths:
            assert '"' + sentence + '"' in (root / path).read_text(encoding="utf-8"), path
    for path in paths:
        assert "Tự hẹn vì lâu không dùng máy" not in (root / path).read_text(encoding="utf-8"), path
