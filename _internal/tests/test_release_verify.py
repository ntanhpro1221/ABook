"""Post-publication verification uses only fake gh/git/HTTP, with real test signatures."""
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import zipfile
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("release_verified", ROOT / "scripts/release.py")
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)
key_spec = importlib.util.spec_from_file_location("update_key", ROOT / "desktop_qt/tools/update_site.py")
keys = importlib.util.module_from_spec(key_spec)
key_spec.loader.exec_module(keys)


@pytest.fixture
def published(tmp_path, monkeypatch):
    from abook.webui import updater
    version = "9.9.9"
    out = tmp_path / "out"
    out.mkdir()
    for name in release.artifacts(version):
        (out / name).write_bytes(b"fixture")
    setup = out / "ABook_9.9.9_x64-setup.exe"
    key = keys.TestKey()
    signature = key.sign(setup.read_bytes(), version)
    setup.with_suffix(".exe.sig").write_text(signature, encoding="utf-8")
    manifest = {"version": version, "platforms": {"windows-x86_64": {
        "signature": signature,
        "url": "https://github.com/ntanhpro1221/ABook/releases/download/v9.9.9/ABook_9.9.9_x64-setup.exe"}}}
    mapping_body = b"Original -> a:\n"
    mapping = tmp_path / "private/9.9.9/mapping.txt"
    mapping.parent.mkdir(parents=True)
    mapping.write_bytes(b"# pg_map_id: abc123\n# pg_map_hash: SHA-256 " +
                        hashlib.sha256(mapping_body).hexdigest().encode() + b"\n" + mapping_body)
    with zipfile.ZipFile(out / "ABook_9.9.9.apk", "w") as package:
        package.writestr("classes.dex", b'~~R8{"pg-map-id":"abc123"}\x00')
    monkeypatch.setattr(release, "ROOT", tmp_path)
    monkeypatch.setattr(release, "MAPPING_ARCHIVE", tmp_path / "private")
    monkeypatch.setattr(updater, "config", lambda _: {"endpoints": ["https://example.test/latest.json"], "pubkey": key.pubkey()})
    state = {"commit": "a" * 40, "remote": "a" * 40, "status": "ahead", "manifest": manifest,
             "notes": "Intro\n\n## Thay đổi\n\n- Released.\n", "mapping": mapping, "out": out}
    calls = []

    def read(command):
        calls.append(command)
        if command[:2] == ["git", "rev-parse"]:
            return state["commit"]
        if command[:2] == ["git", "ls-remote"]:
            return f"tag-object\trefs/tags/v9.9.9\n{state['remote']}\trefs/tags/v9.9.9^{{}}"
        if command[:2] == ["git", "show"]:
            return "## [9.9.9] - today\n\n- Released.\n"
        assert command[:4] == ["gh", "api", "--method", "GET"]
        return json.dumps({"status": state["status"]} if "/compare/" in command[-1] else state["release"])

    monkeypatch.setattr(release, "_read", read)

    def http(url, timeout):
        assert url == "https://example.test/latest.json" and timeout == 30
        if state.get("offline"):
            raise OSError("offline")
        return io.BytesIO(json.dumps(state["manifest"]).encode())

    monkeypatch.setattr(release.urllib.request, "urlopen", http)

    def refresh():
        (out / "latest.json").write_text(json.dumps(manifest), encoding="utf-8")
        state["release"] = {"tag_name": "v9.9.9", "body": state["notes"], "draft": False, "prerelease": False,
                            "assets": [{"name": name, "size": (out / name).stat().st_size,
                                        "digest": "sha256:" + release._sha256(out / name)}
                                       for name in release.artifacts(version)]}

    refresh()
    state.update(refresh=refresh, calls=calls, key=key)
    return state


def test_verify_passes_and_only_reads_git_github_http(published):
    release.verify("9.9.9", published["out"])
    assert all(c[:2] in (["git", "rev-parse"], ["git", "show"], ["git", "ls-remote"], ["gh", "api"])
               for c in published["calls"])


@pytest.mark.parametrize("fault, message", [
    ("tag", "tag trên origin"), ("ancestry", "origin/main"), ("draft", "draft"),
    ("prerelease", "prerelease"), ("release-tag", "sai tag"),
    ("asset-missing", "6 assets"), ("asset-duplicate", "6 assets"),
    ("size", "kích thước"), ("digest", "SHA-256"), ("digest-missing", "SHA-256"),
    ("local-missing", "thiếu file"), ("notes-empty", "rỗng"), ("notes-changed", "khác CHANGELOG"),
    ("latest-old", "chưa trả"), ("latest-different", "khác latest.json"),
    ("url", "sai gói"), ("sig-file", "khác .sig"), ("signature", "minisign"),
    ("mapping-missing", "thiếu mapping"), ("mapping-corrupt", "hash nội dung"),
    ("mapping-other-build", "khác build APK"), ("mapping-build-file", "khác file build"),
])
def test_verify_rejects_each_wrong_publication(published, fault, message):
    p = published
    r = p["release"]
    if fault == "tag": p["remote"] = "b" * 40
    elif fault == "ancestry": p["status"] = "diverged"
    elif fault in {"draft", "prerelease"}: r[fault] = True
    elif fault == "release-tag": r["tag_name"] = "v9.9.8"
    elif fault == "asset-missing": r["assets"].pop()
    elif fault == "asset-duplicate": r["assets"][-1] = copy.deepcopy(r["assets"][0])
    elif fault == "size": r["assets"][0]["size"] += 1
    elif fault == "digest": r["assets"][0]["digest"] = "sha256:" + "0" * 64
    elif fault == "digest-missing": r["assets"][0].pop("digest")
    elif fault == "local-missing": (p["out"] / "LICENSE").unlink()
    elif fault == "notes-empty": r["body"] = "  "
    elif fault == "notes-changed": r["body"] += "invented change"
    elif fault == "latest-old": p["manifest"]["version"] = "9.9.8"
    elif fault == "latest-different": p["manifest"]["notes"] = "tampered"
    elif fault == "url":
        p["manifest"]["platforms"]["windows-x86_64"]["url"] += "wrong"
        p["refresh"]()
    elif fault in {"signature", "sig-file"}:
        p["manifest"]["platforms"]["windows-x86_64"]["signature"] = "invalid"
        if fault == "signature":
            (p["out"] / "ABook_9.9.9_x64-setup.exe.sig").write_text("invalid", encoding="utf-8")
        p["refresh"]()
    elif fault == "mapping-missing": p["mapping"].unlink()
    elif fault == "mapping-corrupt": p["mapping"].write_bytes(p["mapping"].read_bytes() + b"changed")
    elif fault == "mapping-other-build":
        p["mapping"].write_bytes(p["mapping"].read_bytes().replace(b"abc123", b"abc124"))
    elif fault == "mapping-build-file":
        built = release.ROOT / "mobile/android/app/build/outputs/mapping/release/mapping.txt"
        built.parent.mkdir(parents=True)
        built.write_bytes(b"other build")
    with pytest.raises(AssertionError, match=message):
        release.verify("9.9.9", p["out"])


def test_network_failure_is_not_a_pass(published):
    published["offline"] = True
    with pytest.raises(OSError, match="offline"):
        release.verify("9.9.9", published["out"])


def test_verify_cli_accepts_tag_without_publishing(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(release, "verify", lambda *args: calls.append(args))
    assert release.main(["verify", "v0.4.162", "--out", str(tmp_path), "--commit", "abc"]) == 0
    assert calls == [("0.4.162", tmp_path, "abc")]


@pytest.mark.parametrize("fails", [False, True])
def test_publish_calls_verify_last_and_propagates_failure(published, monkeypatch, fails):
    calls = []
    monkeypatch.setattr(release, "_run", lambda command, *args: calls.append(command))
    monkeypatch.setattr(release, "release_notes", lambda *args, **kwargs: "notes")
    monkeypatch.setattr(release.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="fake"))
    monkeypatch.setattr(release.time, "sleep", lambda _: None)

    def verify(*args):
        assert calls[-1][:3] == ["gh", "release", "create"]
        assert args == ("9.9.9", published["out"], "commit")
        calls.append(["verified"])
        if fails:
            raise AssertionError("post-publication failure")

    monkeypatch.setattr(release, "verify", verify)
    # No real publication: every process and HTTP request is mocked.
    monkeypatch.setattr(release.urllib.request, "urlopen", lambda *args, **kwargs:
                        io.BytesIO(b'{"version":"9.9.9"}'))
    if fails:
        with pytest.raises(AssertionError, match="post-publication failure"):
            release.publish("9.9.9", "commit", published["out"])
    else:
        release.publish("9.9.9", "commit", published["out"])
    assert calls[-1] == ["verified"]


def test_github_get_failure_is_not_a_pass(published, monkeypatch):
    def unavailable(_):
        raise OSError("GitHub unavailable")
    monkeypatch.setattr(release, "_github", unavailable)
    with pytest.raises(OSError, match="GitHub unavailable"):
        release.verify("9.9.9", published["out"])


def test_mapping_without_header_is_rejected(published):
    published["mapping"].write_bytes(b"not a mapping")
    with pytest.raises(AssertionError, match="thiếu build id/hash"):
        release.verify("9.9.9", published["out"])


def test_valid_signature_for_another_version_is_rejected(published):
    p = published
    signature = p["key"].sign((p["out"] / "ABook_9.9.9_x64-setup.exe").read_bytes(), "9.9.8")
    p["manifest"]["platforms"]["windows-x86_64"]["signature"] = signature
    (p["out"] / "ABook_9.9.9_x64-setup.exe.sig").write_text(signature, encoding="utf-8")
    p["refresh"]()
    with pytest.raises(AssertionError, match="minisign"):
        release.verify("9.9.9", p["out"])
