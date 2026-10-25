import io
import json
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from abook.webui import diagnostics, notices, remote_books
from abook.webui.listening import Listening
from abook.webui.cast import CastMedia


@pytest.mark.parametrize("case", json.loads((Path(__file__).parent / "fixtures/diagnostics_states.json").read_text("utf-8")), ids=lambda case: case["name"])
def test_diagnostics_states_survive_python_boundaries(case, monkeypatch):
    """Python relays the same state/error envelope to the shared UI; blank errors are data, not collection failures."""
    report = case["report"]
    monkeypatch.setattr(remote_books, "_COMPUTERS", SimpleNamespace(get=lambda _: {"host": "127.0.0.1", "port": 1, "token": "test",
        "addresses": [{"address": "127.0.0.1:1", "lastSuccess": 0}]}))
    monkeypatch.setattr(remote_books, "_request", lambda *args, **kwargs: json.dumps(report).encode())
    result = remote_books.diagnostics("test")
    result.pop("fetchedAt")
    assert result == report
    with zipfile.ZipFile(io.BytesIO(diagnostics.bundle(report, None))) as archive:
        assert json.loads(archive.read("thong-tin.json")) == report


@pytest.mark.parametrize("case", json.loads((Path(__file__).parent / "fixtures/diagnostics_paths.json").read_text("utf-8")))
def test_shared_private_paths_and_source_frames(case):
    assert diagnostics.redact(case["raw"]) == case["safe"]


def test_bundle_includes_recovery_metadata_without_profile_contents(tmp_path):
    notices.NOTICES.clear()
    path = tmp_path / "listening.json"
    path.write_text('{"book":{"chapters":[],"private":"PROFILE-CONTENT"}}', encoding="utf-8")
    Listening(path)
    notices.NOTICES.add("must not export this notice content", kind="saving-blocked")
    info = diagnostics.machine_info("test", tmp_path)
    with zipfile.ZipFile(io.BytesIO(diagnostics.bundle(info, None))) as archive:
        text = archive.read("thong-tin.json").decode()
    recovery = json.loads(text)["dataRecovery"]
    assert recovery["savingBlocked"]
    assert any(row["kind"] == "recovered" and row["preservedFile"].startswith("listening.json.hong-") for row in recovery["notices"])
    assert all(row["at"] > 0 for row in recovery["notices"])
    assert "PROFILE-CONTENT" not in text
    assert "must not export" not in text
    notices.NOTICES.clear()


def test_desktop_bundle_keeps_300_short_log_lines(tmp_path):
    (tmp_path / "host.log").write_text("\n".join(f"line {i}" for i in range(300)), encoding="utf-8")
    with zipfile.ZipFile(io.BytesIO(diagnostics.bundle({}, tmp_path))) as archive:
        lines = archive.read("nhat-ky/host.log").decode().splitlines()
    assert lines == [f"line {i}" for i in range(300)]


def test_cast_capability_from_real_share_is_hidden_without_opening_server(tmp_path, monkeypatch):
    media = CastMedia("127.0.0.1")
    monkeypatch.setattr(media, "_start", lambda: SimpleNamespace(server_address=("127.0.0.1", 1234)))
    url = media.share(tmp_path / "audio.mp3", "127.0.0.1")
    token = next(iter(media._files))
    assert len(token) == 22
    for path in (url, "/c/" + token, "/c/" + "ab" * 16 + ".mp3"):
        safe = diagnostics.redact(path)
        assert "/c/***" in safe
        assert token not in safe


def test_phone_progress_survives_desktop_diagnostics_boundary(monkeypatch):
    monkeypatch.setattr(remote_books, "_COMPUTERS", SimpleNamespace(get=lambda _: {"host": "127.0.0.1", "port": 1, "token": "test",
        "addresses": [{"address": "127.0.0.1:1", "lastSuccess": 0}]}))
    monkeypatch.setattr(remote_books, "_request", lambda *args, **kwargs: json.dumps({"work": [{"progress": {"done": "3", "total": "10", "phase": "download"}}]}).encode())
    assert remote_books.diagnostics("test")["work"][0]["progress"] == {"done": "3", "total": "10", "phase": "download"}
