"""Offline regression tests: all installation paths and processes are fakes."""
from pathlib import Path
from types import SimpleNamespace
import json
import os
import subprocess
import io
import hashlib
import threading

import pytest

from abook.webui.server import ApiError, App, Handler


@pytest.mark.parametrize("where", ["Books", "Studio/books", "."])
def test_library_cannot_be_saved_in_uninstall_tree(tmp_path, monkeypatch, where):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    target = tmp_path / "local/ABook" / where
    saved = []
    handler = SimpleNamespace(
        _body=lambda: {"libraryRoot": str(target)},
        app=SimpleNamespace(library=SimpleNamespace(root=tmp_path / "books"),
                            preferences=SimpleNamespace(update=saved.append, get=lambda: {}),
                            adopt_moved_library=lambda _: None),
        _send_json=lambda *_: None,
    )
    with pytest.raises(ApiError, match="bạn"):
        Handler.put_preferences(handler, {})
    assert saved == []


# Bộ gỡ Tauri và bộ gỡ Qt (desktop_qt/installer, thêm phép kiểm junction bên trong) cùng luật.
GUARDS = ["shell/src-tauri/windows/uninstall_guard.ps1", "desktop_qt/installer/uninstall_guard.ps1"]


@pytest.mark.parametrize("guard", GUARDS)
@pytest.mark.parametrize("library,code", [("outside", 0), ("ABook/Books", 3), ("ABook/Studio/books", 3)])
@pytest.mark.parametrize("target", ["ABook", "ABook/Studio"])
def test_uninstall_guard_reads_real_preferences(tmp_path, library, code, target, guard):
    prefs = tmp_path / "preferences.json"
    prefs.write_text(json.dumps({"libraryRoot": str(tmp_path / library)}), encoding="utf-8")
    result = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File",
                             str(Path(guard).resolve())],
                            env={**os.environ, "ABOOK_PREFERENCES": str(prefs),
                                 "ABOOK_DELETE_TARGET": str(tmp_path / target)}, capture_output=True)
    expected = 0 if target == "ABook/Studio" and library == "ABook/Books" else code
    assert result.returncode == expected, result.stderr


def test_setup_route_refuses_busy_book_before_shutdown_or_start():
    calls = []
    handler = SimpleNamespace(
        _studio_setup=lambda: SimpleNamespace(start=lambda: calls.append("start")),
        app=SimpleNamespace(_busy_elsewhere=lambda: Path("analysing"), _queue_lock=threading.RLock(),
                            previews=SimpleNamespace(shutdown=lambda: calls.append("shutdown"))),
        _send_json=lambda *_: None,
    )
    with pytest.raises(ApiError, match="[Bb]ạn"):
        Handler.post_studio_setup(handler, {})
    assert calls == []


@pytest.mark.parametrize("phase", ["running", "starting", "paused"])
def test_setup_uses_existing_busy_check_for_every_active_phase(tmp_path, phase):
    book = tmp_path / "book"
    app = SimpleNamespace(library=SimpleNamespace(projects=lambda: [book]), _queue_lock=threading.RLock(),
                          runner=SimpleNamespace(running=lambda _: phase in {"running", "paused"}),
                          jobs=SimpleNamespace(starting=lambda _: phase == "starting"))
    app._busy_elsewhere = lambda: App._busy_elsewhere(app)
    handler = SimpleNamespace(app=app, _studio_setup=lambda: SimpleNamespace())
    with pytest.raises(ApiError):
        Handler.post_studio_setup(handler, {})


def test_book_cannot_start_during_setup(tmp_path):
    app = SimpleNamespace(_mutating=lambda: None, _book=lambda _: tmp_path,
                          _queue_lock=threading.RLock(), studio=SimpleNamespace(running=lambda: True))
    with pytest.raises(ApiError, match="Studio đang cập nhật"):
        App.start(app, "book")


def test_verify_does_not_publish_installed_marker(tmp_path, monkeypatch):
    from abook.webui.studio_setup import StudioSetup
    setup = StudioSetup(tmp_path / "studio", tmp_path, gpu=lambda: None)
    setup.pythonw.parent.mkdir(parents=True)
    setup.pythonw.write_bytes(b"fake")
    seen = []
    monkeypatch.setattr(setup, "_run", lambda *_: seen.append(setup.installed()))
    setup._step_verify()
    assert seen == [False]
    assert not setup.installed()


def test_finished_steps_without_marker_repeat_verification(tmp_path, monkeypatch):
    from abook.webui.studio_setup import StudioSetup, STEPS
    setup = StudioSetup(tmp_path / "studio", tmp_path, gpu=lambda: None)
    setup._save(done=[s for s, *_ in STEPS], pins=setup._pins())
    calls = []
    monkeypatch.setattr(setup, "_run", lambda *_: calls.append("verify"))
    setup._run_all()
    assert calls == ["verify"]
    assert "verify" in setup._state()["done"]


def test_crash_after_update_step_cannot_reuse_old_verify(tmp_path, monkeypatch):
    from abook.webui.studio_setup import StudioSetup, STEPS
    setup = StudioSetup(tmp_path / "studio", tmp_path, gpu=lambda: None)
    setup.pythonw.parent.mkdir(parents=True)
    setup.pythonw.write_bytes(b"fake")
    setup.ollama_executable.parent.mkdir(parents=True)
    setup.ollama_executable.write_bytes(b"fake")
    monkeypatch.setattr(setup, "_probe_packages", lambda: [])
    pins = setup._pins()
    setup._save(done=[s for s, *_ in STEPS], pins={**pins, "uv": "old"})
    setup._write_marker()
    original = setup._save

    def save(**changes):
        original(**changes)
        if changes.get("pins", {}).get("uv") == pins["uv"]:
            raise SystemExit("simulated crash after update checkpoint")

    monkeypatch.setattr(setup, "_save", save)
    monkeypatch.setattr(setup, "_step_uv", lambda: None)
    with pytest.raises(SystemExit):
        setup._run_all()
    assert not setup.installed()
    assert "verify" not in setup._state()["done"]
    monkeypatch.setattr(setup, "_save", original)
    calls = []
    monkeypatch.setattr(setup, "_step_verify", lambda: calls.append("verify"))
    setup._run_all()
    assert calls == ["verify"]
    assert setup.installed()


def test_runtime_rechecks_busy_after_download(tmp_path, monkeypatch):
    from abook.webui.studio_setup import StudioSetup, SetupError, OLLAMA
    setup = StudioSetup(tmp_path / "studio", tmp_path, gpu=lambda: None)
    setup.busy = lambda: Path("paused")
    calls = []
    monkeypatch.setattr(setup, "_get", lambda _: tmp_path / "fake.zip")
    monkeypatch.setattr(setup, "stop_processes", lambda *_: calls.append("kill"))
    monkeypatch.setattr("abook.webui.studio_setup._unzip", lambda *_: calls.append("unzip"))
    with pytest.raises(SetupError, match="[Bb]ạn"):
        setup._install_archive(OLLAMA, setup.tools / "ollama")
    assert calls == []


@pytest.mark.parametrize("endless", [False, True])
def test_download_stops_on_first_oversized_chunk(tmp_path, monkeypatch, endless):
    from abook.webui import studio_setup as s

    class Response(io.BytesIO):
        status = 200
        reads = 0

        def read(self, size=-1):
            self.reads += 1
            if self.reads > 4:
                raise AssertionError("downloader kept reading beyond pinned size")
            return b"012345" if endless else super().read(size)

    response = Response(b"0123456789")
    monkeypatch.setattr(s.urllib.request, "urlopen", lambda *_a, **_k: response)
    item = s.Download("fake", "https://invalid.invalid/file", hashlib.sha256(b"123").hexdigest(), 3)
    target = tmp_path / "model"
    with pytest.raises(s.SetupError, match="[Cc]ỡ|[Ll]ớn|[Dd]ung lượng"):
        s.download(item, target, lambda *_: None, lambda: False)
    assert response.reads == 1
    assert not target.exists()
    assert not target.with_name("model.part").exists()


@pytest.mark.parametrize("failure", ["mkdir", "write", "replace"])
def test_setup_state_write_failures_remain_visible_without_disk(tmp_path, monkeypatch, failure):
    from abook.webui import studio_setup as s
    setup = s.StudioSetup(tmp_path / "studio", tmp_path, gpu=lambda: None)
    if failure == "mkdir":
        original = Path.mkdir
        def mkdir(path, *a, **k):
            if path == setup.root:
                raise PermissionError("denied")
            return original(path, *a, **k)
        monkeypatch.setattr(Path, "mkdir", mkdir)
    elif failure == "write":
        original = Path.write_text
        def write(path, *a, **k):
            if path.name == "setup.json.part":
                raise OSError(28, "No space left")
            return original(path, *a, **k)
        monkeypatch.setattr(Path, "write_text", write)
    else:
        monkeypatch.setattr(s.os, "replace", lambda *_: (_ for _ in ()).throw(OSError("replace denied")))
    setup._run_all()
    status = setup.status()
    assert status["error"] and "Bạn" in status["error"]
    assert "Cài tiếp" in status["error"]
    assert not status["installed"]


@pytest.mark.parametrize("name", ["O'Brien", "Tiếng Việt $ ` có khoảng trắng"])
def test_uninstaller_process_root_is_data_not_powershell_code(tmp_path, name):
    root = tmp_path / name
    helper = Path("shell/src-tauri/windows/stop_processes.ps1").resolve()
    if helper.is_file():
        args = ["-File", str(helper), "-ResolveOnly"]
    else:
        # Execute only the original root assignment, never the process enumeration/kill.
        import re
        source = Path("shell/src-tauri/windows/hooks.nsh").read_text(encoding="utf-8")
        assignment = re.search(r"\$\$root = .*?;", source).group()
        args = ["-Command", assignment.replace("$$", "$").replace("${FOLDER}", str(root)) + " Write-Output $root"]
    result = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", *args],
                            env={**os.environ, "ABOOK_STOP_ROOT": str(root)}, capture_output=True)
    assert result.returncode == 0, result.stderr


def test_requirements_change_invalidates_only_packages_and_verify(tmp_path):
    from abook.webui.studio_setup import StudioSetup, STEPS
    requirement = tmp_path / "studio-requirements.txt"
    requirement.write_text("psutil==1\n")
    setup = StudioSetup(tmp_path / "studio", tmp_path, gpu=lambda: None)
    setup.pythonw.parent.mkdir(parents=True)
    setup.pythonw.write_bytes(b"fake")
    setup._save(done=[s for s, *_ in STEPS], pins=setup._pins())
    setup._write_marker()
    requirement.write_text("psutil==2\n")
    assert "packages" in setup.outdated()


def test_missing_lightweight_dependency_is_repairable(tmp_path, monkeypatch):
    from abook.webui.studio_setup import StudioSetup, STEPS
    setup = StudioSetup(tmp_path / "studio", tmp_path, gpu=lambda: None)
    setup.pythonw.parent.mkdir(parents=True)
    setup.pythonw.write_bytes(b"fake")
    setup.ollama_executable.parent.mkdir(parents=True)
    setup.ollama_executable.write_bytes(b"fake")
    (tmp_path / "studio-requirements.txt").write_text("psutil==1\n")
    setup._save(done=[s for s, *_ in STEPS], pins=setup._pins())
    setup._write_marker()
    setup._probe_packages = lambda: ["psutil"]
    assert "packages" in setup.damaged()


def test_repair_reuses_venv_and_models_and_only_runs_packages_and_verify(tmp_path, monkeypatch):
    from abook.webui import studio_setup
    from abook.webui.studio_setup import StudioSetup, STEPS
    setup = StudioSetup(tmp_path / "studio", tmp_path, gpu=lambda: None)
    setup.pythonw.parent.mkdir(parents=True)
    setup.pythonw.write_bytes(b"fake")
    setup.ollama_executable.parent.mkdir(parents=True)
    setup.ollama_executable.write_bytes(b"fake")
    # Model còn nguyên (a96 V1: `damaged` đối chiếu file thật) - chỉ thư viện thiếu.
    (setup.runtime / "models" / "whisper").mkdir(parents=True)
    (setup.runtime / "models" / "whisper" / "large-v3-turbo.pt").write_bytes(b"fake")
    setup.word_align.mkdir(parents=True)
    for item in studio_setup.WORD_ALIGN_FILES:
        (setup.word_align / item.name).write_bytes(b"fake")
    (tmp_path / "studio-requirements.txt").write_text("psutil==1\n")
    (tmp_path / "uv.lock").write_text('[[package]]\nname="psutil"\nversion="1"\nwheels=[{hash="sha256:' + "0" * 64 + '"}]\n')
    setup._save(done=[s for s, *_ in STEPS], pins=setup._pins())
    setup._write_marker()
    missing = ["psutil"]
    monkeypatch.setattr(setup, "_probe_packages", lambda: missing)
    calls = []
    def run(command, label):
        calls.append((command, label))
        missing.clear()
        return ""
    monkeypatch.setattr(setup, "_run", run)
    setup._run_all()
    assert [label for _, label in calls] == ["Cài thư viện", "Kiểm thư viện (chỉ ghi nhật ký)", "Kiểm tra lần cuối"]
    assert all("venv" not in command and "--reinstall" not in command and "--force-reinstall" not in command for command, _ in calls)
    assert setup.installed()


def test_shipped_requirements_have_locked_hashes_and_exact_git_commit():
    from abook.webui.studio_dependencies import locked_requirements
    hashed, vcs = locked_requirements(Path("shell/python/studio-requirements.txt"), Path("uv.lock"))
    assert all("--hash=sha256:" in line for line in hashed.splitlines() if not line.startswith("--"))
    assert len(vcs) == 1 and vcs[0].endswith("@cc2700db57bb83ee13dc31ebe1b868c254e15d09")


def test_same_version_wheel_with_wrong_bytes_is_rejected_offline(tmp_path, monkeypatch):
    from abook.webui import studio_setup as s
    import shutil
    wheel = tmp_path / "a85fake-1.0-py3-none-any.whl"
    import zipfile
    with zipfile.ZipFile(wheel, "w") as bundle:
        bundle.writestr("a85fake.py", "VALUE = 1\n")
        bundle.writestr("a85fake-1.0.dist-info/METADATA", "Metadata-Version: 2.1\nName: a85fake\nVersion: 1.0\n")
        bundle.writestr("a85fake-1.0.dist-info/WHEEL", "Wheel-Version: 1.0\nGenerator: test\nRoot-Is-Purelib: true\nTag: py3-none-any\n")
        bundle.writestr("a85fake-1.0.dist-info/RECORD", "")
    trusted = hashlib.sha256(wheel.read_bytes()).hexdigest()
    with zipfile.ZipFile(wheel, "a") as bundle:
        bundle.comment = b"changed by index"
    (tmp_path / "studio-requirements.txt").write_text("a85fake==1.0\n")
    (tmp_path / "uv.lock").write_text(f'''version = 1
[[package]]
name = "a85fake"
version = "1.0"
wheels = [{{url = "https://invalid.invalid/a85fake.whl", hash = "sha256:{trusted}"}}]
''')
    setup = s.StudioSetup(tmp_path / "studio", tmp_path, gpu=lambda: None)
    monkeypatch.setattr(setup, "_uv", lambda: shutil.which("uv"))
    def run(command, _what):
        command[command.index("--python") + 1] = "D:/Novels/ABook/_internal/runtime/.venv/Scripts/python.exe"
        command += ["--target", str(tmp_path / "isolated"), "--offline", "--no-index", "--find-links", str(tmp_path)]
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
        if result.returncode:
            raise s.SetupError(result.stderr)
        return result.stdout
    monkeypatch.setattr(setup, "_run", run)
    with pytest.raises(s.SetupError, match="[Hh]ash|[Cc]hecksum"):
        setup._step_packages()
    assert not (tmp_path / "isolated/a85fake.py").exists()


def test_auxiliary_voice_models_never_follow_main(tmp_path, monkeypatch):
    import sys
    from abook import runtime_contract as contract
    from abook.webui import studio_setup as s
    requests = []
    monkeypatch.setitem(sys.modules, "huggingface_hub", SimpleNamespace(snapshot_download=lambda **kwargs: requests.append(kwargs)))
    monkeypatch.setattr(contract, "voice_model_check", lambda _: {"ok": True, "detail": "fake"})
    monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path / "hub"))
    monkeypatch.setenv("ABOOK_RUNTIME", str(tmp_path))
    monkeypatch.setenv("ABOOK_STUDIO_SKIP_GPU_LOAD", "1")
    exec(s.VOICE_SCRIPT, {})
    assert all(len(request.get("revision", "")) == 40 for request in requests)


def test_faster_whisper_download_never_follows_main(tmp_path, monkeypatch):
    import sys
    from abook.webui import studio_setup as s
    requests = []
    models = []
    monkeypatch.setitem(sys.modules, "huggingface_hub", SimpleNamespace(snapshot_download=lambda **kw: requests.append(kw) or str(tmp_path / "snapshot")))
    monkeypatch.setitem(sys.modules, "whisper", SimpleNamespace(load_model=lambda *_a, **_k: None,
                                                               _MODELS={"turbo": "https://example.invalid/models/" + "0" * 64 + "/large-v3-turbo.pt"}))
    monkeypatch.setitem(sys.modules, "faster_whisper", SimpleNamespace(WhisperModel=lambda name, **_kw: models.append(name)))
    monkeypatch.setenv("ABOOK_RUNTIME", str(tmp_path))
    monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path / "hub"))
    exec(s.ASR_SCRIPT, {})
    assert requests and len(requests[0].get("revision", "")) == 40
    assert models == [str(tmp_path / "snapshot")]


@pytest.mark.xfail(strict=True, reason="a85 #1: immutable worker code needs versioned snapshots and legacy-pin migration; design only per 150-line limit")
def test_live_worker_child_keeps_old_code_after_app_replacement(tmp_path, monkeypatch):
    from abook.webui import studio_setup as s
    setup = s.StudioSetup(tmp_path / "studio", tmp_path / "app", gpu=lambda: None)
    package = setup.app_root / "abook"
    package.mkdir(parents=True)
    marker = setup.app_root / "version_marker.py"
    marker.write_text("VERSION = 'A'\n")
    (package / "__init__.py").write_text("")
    (package / "example.py").write_text("VERSION = 'A'\n")
    book = tmp_path / "book"
    book.mkdir()
    monkeypatch.setattr(setup, "ensure_assets", lambda: None)
    code = setup.code_for(book)
    marker.write_text("VERSION = 'B'\n")
    (package / "example.py").write_text("VERSION = 'B'\n")
    child = subprocess.run(["D:/Novels/ABook/_internal/runtime/.venv/Scripts/python.exe", "-B", "-c",
                            "from abook.example import VERSION; print(VERSION)"], cwd=code,
                           env={**os.environ, "PYTHONPATH": str(code)}, capture_output=True, text=True, encoding="utf-8")
    assert child.returncode == 0, child.stderr
    assert child.stdout.strip() == "A"


@pytest.mark.parametrize("filename", ["ABook_1_x64-setup.exe", "ban-moi.exe"])
def test_upgrade_intent_is_independent_of_installer_filename(filename):
    helper = Path("shell/src-tauri/windows/upgrade_mode.ps1").resolve()
    if helper.is_file():
        args = ["-File", str(helper)]
    else:
        import re
        hooks = Path("shell/src-tauri/windows/hooks.nsh").read_text(encoding="utf-8")
        command = re.search(r'\$\$me = .*?exit 0 }', hooks).group().replace("$$", "$")
        mock = "function Get-CimInstance { param($ClassName,$Filter) if ($Filter -eq ('ProcessId=' + $PID)) { return @{ParentProcessId=100} }; if ($Filter -eq 'ProcessId=100') { return @{ParentProcessId=200} }; return @{Name='" + filename + "'} }; "
        args = ["-Command", mock + command]
    result = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", *args],
                            env={**os.environ, "ABOOK_INSTALLER_UPGRADE": "1"}, capture_output=True)
    assert result.returncode == 3, result.stderr


@pytest.mark.parametrize("guard", GUARDS)
@pytest.mark.parametrize("broken", [False, True])
def test_uninstall_guard_fails_closed_for_unreadable_preferences(tmp_path, broken, guard):
    prefs = tmp_path / "prefs.json"
    if broken:
        prefs.write_text("{broken")
    else:
        prefs.mkdir()
    result = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File",
                             str(Path(guard).resolve())],
                            env={**os.environ, "ABOOK_PREFERENCES": str(prefs), "ABOOK_DELETE_TARGET": str(tmp_path)}, capture_output=True)
    assert result.returncode == 4


@pytest.mark.parametrize("inside", [False, True])
def test_qt_uninstall_guard_refuses_a_junction_inside_the_target(tmp_path, inside):
    """NSIS RMDir /r đi theo junction (test_installer.py 31-10 đã thấy nó làm rỗng thư mục ngoài): bộ gỡ Qt giữ thư mục có
    junction ở bất kỳ đâu bên trong."""
    import _winapi
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep.txt").write_text("not ours", encoding="utf-8")
    target = tmp_path / "local" / "ABook"
    (target / "a" / "b").mkdir(parents=True)
    (target / "a" / "file.txt").write_text("x", encoding="utf-8")
    if inside:
        _winapi.CreateJunction(str(outside), str(target / "a" / "b" / "Studio"))
    result = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File",
                             str(Path("desktop_qt/installer/uninstall_guard.ps1").resolve())],
                            env={**os.environ, "ABOOK_PREFERENCES": str(tmp_path / "none.json"), "ABOOK_DELETE_TARGET": str(target)},
                            capture_output=True)
    if inside:
        os.rmdir(target / "a" / "b" / "Studio")
    assert result.returncode == (4 if inside else 0), result.stderr
    assert (outside / "keep.txt").exists()


@pytest.mark.parametrize("failed,reused,code", [(False, False, 0), (True, False, 4), (False, True, 0)])
def test_process_helper_selects_only_same_root_and_reports_failure(tmp_path, failed, reused, code):
    root = tmp_path / "O'Brien Tiếng Việt $ `"
    script = r'''
function Get-CimInstance {
    param($ClassName, $Filter)
    if ($Filter -eq ('ProcessId=' + $PID)) { return @{ParentProcessId=100} }
    if ($Filter -eq 'ProcessId=200') {
        return @{ProcessId=200; ExecutablePath=($env:ABOOK_STOP_ROOT + '\pythonw.exe'); CreationDate=$env:ABOOK_TEST_DATE}
    }
    return @(
        @{ProcessId=200; ExecutablePath=($env:ABOOK_STOP_ROOT + '\pythonw.exe'); CreationDate='old'},
        @{ProcessId=201; ExecutablePath=($env:ABOOK_STOP_ROOT + '-other\pythonw.exe'); CreationDate='old'},
        @{ProcessId=100; ExecutablePath=($env:ABOOK_STOP_ROOT + '\uninstall.exe'); CreationDate='old'}
    )
}
function Stop-Process {
    param($Id,$Force,$ErrorAction)
    if ($env:ABOOK_TEST_FAIL -eq '1') { throw 'mock access denied' }
    [Console]::Write('stopped:' + $Id)
}
& $env:ABOOK_TEST_HELPER
exit $LASTEXITCODE
'''.replace("param($Id,$Force,$ErrorAction)", "param($Id,[switch]$Force,$ErrorAction)")
    wrapper = tmp_path / "mock.ps1"
    wrapper.write_text(script, encoding="utf-8")
    result = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(wrapper)],
                            env={**os.environ, "ABOOK_STOP_ROOT": str(root), "ABOOK_TEST_DATE": "new" if reused else "old",
                                 "ABOOK_TEST_FAIL": "1" if failed else "0",
                                 "ABOOK_TEST_HELPER": str(Path("shell/src-tauri/windows/stop_processes.ps1").resolve())}, capture_output=True)
    assert result.returncode == code, result.stderr
    assert result.stdout == (b"stopped:200" if not failed and not reused else b"")
