import logging

import pytest

from abook.webui import cast


@pytest.mark.parametrize("error,kind", [(TimeoutError("private URL/IP/token"), "idle-timeout"),
                                        (BrokenPipeError("private URL/IP/token"), "write-error")])
def test_authenticated_writer_logs_bytes_without_private_error_and_rate_limits(monkeypatch, caplog, error, kind):
    monkeypatch.setattr(cast, "_stream_log_times", {})
    now = [100.0]
    monkeypatch.setattr(cast.time, "monotonic", lambda: now[0])
    class Socket:
        calls = 0
        def settimeout(self, _):
            pass
        def send(self, data):
            self.calls += 1
            if self.calls == 1:
                return 4
            raise error
    caplog.set_level(logging.WARNING, logger=cast.__name__)
    writer = cast._ProgressWriter(Socket(), 300)
    with pytest.raises(type(error)):
        writer.write(b"abcdefgh")
    assert writer.bytes_sent == 4
    assert caplog.messages == [f"Cast transfer {kind} bytes_sent=4"]
    cast._stream_failure(error, 8)
    assert len(caplog.messages) == 1
    now[0] += 30
    cast._stream_failure(error, 8)
    assert caplog.messages[-1] == f"Cast transfer {kind} bytes_sent=8"
    assert "private" not in caplog.text


def test_failure_categories_have_independent_rate_limits(monkeypatch, caplog):
    monkeypatch.setattr(cast, "_stream_log_times", {})
    caplog.set_level(logging.WARNING, logger=cast.__name__)
    cast._stream_failure(TimeoutError(), 2)
    cast._stream_failure(OSError(), 3)
    assert len(caplog.messages) == 2
