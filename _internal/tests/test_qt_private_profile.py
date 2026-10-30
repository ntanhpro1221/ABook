"""Mọi lượt chạy ABookDesk của công cụ đo / chụp / smoke phải có USERPROFILE riêng, không chỉ LOCALAPPDATA riêng.

QStandardPaths (cache nhạc music_pcm, qtpipelinecache, ...) hỏi SHGetKnownFolderPath, hàm ấy theo USERPROFILE của tiến trình chứ không theo
biến LOCALAPPDATA. 30-10 các lượt đo chỉ đổi LOCALAPPDATA đã để 40 bài nhạc thử (300 MB) trong %LOCALAPPDATA%\\ABook của chủ máy.
"""
import ast
import ctypes
import os
import re
import shutil
import subprocess
import sys
import tempfile
from ctypes import wintypes as wt
from pathlib import Path

import psutil
import pytest

TOOLS = Path(__file__).resolve().parent.parent / "desktop_qt" / "tools"
DIST_EXE = TOOLS.parent / "dist" / "ABookDesk.exe"
LLM_MUSIC = Path(__file__).resolve().parents[3] / "LLM_Train" / "music"  # script đo của luồng nhạc, cạnh các worktree
sys.path.insert(0, str(TOOLS))
from private_profile import isolate  # noqa: E402

KNOWN_LOCAL = """
import ctypes, uuid
g = uuid.UUID('{F1B32785-6FBA-4FCF-9D55-7B8E7F157091}').bytes_le
guid = (ctypes.c_byte * 16).from_buffer_copy(g)
p = ctypes.c_wchar_p()
hr = ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(guid), 0, None, ctypes.byref(p))
print(p.value if hr == 0 else 'FAIL %x' % (hr & 0xffffffff))
"""


def known_local(env):
    return subprocess.run([sys.executable, "-I", "-c", KNOWN_LOCAL], env=env, capture_output=True, text=True, check=True).stdout.strip()


@pytest.mark.skipif(sys.platform != "win32", reason="SHGetKnownFolderPath chỉ có trên Windows")
def test_known_folder_follows_the_private_profile(tmp_path):
    local = tmp_path / "local"
    local.mkdir()
    env = dict(os.environ, LOCALAPPDATA=str(local))
    # Đối chứng: chỉ đổi LOCALAPPDATA thì thư mục mà Qt dùng cho cache vẫn là của chủ máy.
    assert Path(known_local(env)) == Path(known_local(dict(os.environ)))
    isolate(env)
    got = Path(known_local(env))
    assert got == local / "profile" / "AppData" / "Local"
    assert got.is_dir() and (local / "profile" / "AppData" / "Roaming").is_dir()


def test_isolate_refuses_the_real_local_appdata():
    with pytest.raises(RuntimeError):
        isolate(dict(os.environ))
    with pytest.raises(RuntimeError):
        isolate({k: v for k, v in os.environ.items() if k != "LOCALAPPDATA"})


# ---------- máy dò: chỗ mở app không qua isolate() ----------

SUBPROCESS = {"Popen", "run", "call", "check_call", "check_output"}
OS_START = {"startfile", "system", "spawnv", "spawnve", "spawnl", "spawnle", "execv", "execve"}
SAFE = {"create_suspended", "launch"}  # windows_process.create_suspended tự tách hồ sơ cho ABookDesk.exe; measure.launch đi qua nó
SKIP_DIRS = ("site-packages", "__pycache__")


def _scripts(root: Path):
    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(root).parts
        if any(part.startswith((".venv", "_dup")) or part in SKIP_DIRS for part in rel):
            continue
        yield path


def _launch_kind(call: ast.Call) -> str | None:
    func = call.func
    name = func.attr if isinstance(func, ast.Attribute) else func.id if isinstance(func, ast.Name) else ""
    owner = func.value.id if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) else ""
    if name in SAFE:
        return None
    if name in SUBPROCESS and owner in ("subprocess", ""):
        return name
    if name in OS_START and owner == "os":
        return name
    return None


def _names(node: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


def _strings(node: ast.AST) -> list[str]:
    return [n.value for n in ast.walk(node) if isinstance(n, ast.Constant) and isinstance(n.value, str)]


def _assignments(tree: ast.AST, source: str) -> dict[str, list[str]]:
    """Tên -> mã nguồn mọi vế phải gán cho nó (cả tham số argparse `--exe` với default)."""
    out: dict[str, list[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                for name in _names(target):
                    out.setdefault(name, []).append(ast.get_source_segment(source, node.value) or "")
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)) and node.value is not None:
            for name in _names(node.target):
                out.setdefault(name, []).append(ast.get_source_segment(source, node.value) or "")
    return out


def _app_like(text: str) -> bool:
    return bool(re.search(r"abookdesk", text, re.I))


SHELLS = {"cmd", "cmd.exe", "powershell", "powershell.exe", "pwsh", "pwsh.exe", "explorer", "explorer.exe"}


def _starts_app(call: ast.Call, source: str, assigned: dict[str, list[str]], params: set[str]) -> bool:
    """Lệnh có chạy ABookDesk không. Chỉ xét CHƯƠNG TRÌNH được chạy (phần tử đầu của argv; với cmd / powershell / explorer - `start`,
    Start-Process, mở file - thì cả argv): chuỗi có ABookDesk, hay một tên mà vế gán của nó (đệ quy) có ABookDesk, hay tên `...exe` là tham
    số hàm (không biết trước được nó là gì: coi là app). Python chạy một script nhận đường app làm tham số thì không phải chỗ mở app."""
    seen: set[str] = set()

    def is_app(expr: ast.AST, whole: bool = False) -> bool:
        if isinstance(expr, (ast.List, ast.Tuple)):
            if not expr.elts:
                return False
            first = expr.elts[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str) and first.value.lower() in SHELLS:
                return any(is_app(e, True) for e in expr.elts[1:])
            return is_app(first, whole)
        if isinstance(expr, ast.BinOp) and isinstance(expr.op, ast.Add):  # argv nối thêm: chương trình ở vế trái
            return is_app(expr.left, whole)
        if isinstance(expr, ast.Starred):
            return is_app(expr.value, whole)
        if isinstance(expr, ast.Call) and expr.args and isinstance(expr.func, ast.Name) and expr.func.id in ("str", "Path", "os.fspath"):
            return is_app(expr.args[0], whole)
        if isinstance(expr, ast.Constant):
            return isinstance(expr.value, str) and _app_like(expr.value)
        if isinstance(expr, ast.JoinedStr):
            return any(_app_like(text) for text in _strings(expr)) or any(name_is_app(n) for n in _names(expr))
        if isinstance(expr, ast.Name):
            return name_is_app(expr.id)
        return any(_app_like(text) for text in _strings(expr)) or any(name_is_app(n) for n in _names(expr))

    def name_is_app(name: str) -> bool:
        if name in seen:
            return False
        seen.add(name)
        if name in params and "exe" in name.lower() and name not in assigned:
            return True
        for value in assigned.get(name, []):
            try:
                expr = ast.parse(value, mode="eval").body
            except SyntaxError:
                if _app_like(value):
                    return True
                continue
            if is_app(expr):
                return True
        return False

    args = list(call.args) + [k.value for k in call.keywords if k.arg in ("args", "executable")]
    return bool(args) and is_app(args[0])


def _isolated(call: ast.Call, source: str, assigned: dict[str, list[str]]) -> bool:
    """Lệnh có `isolate(` ngay trong nó, hay env= là một tên mà vế gán có `isolate(`."""
    if "isolate(" in (ast.get_source_segment(source, call) or ""):
        return True
    env = next((k.value for k in call.keywords if k.arg == "env"), None)
    return isinstance(env, ast.Name) and any("isolate(" in value for value in assigned.get(env.id, []))


def unisolated_launches(*roots: Path) -> list[str]:
    """Chỗ mở ABookDesk (subprocess.Popen/run/call/check_*, os.startfile/system/spawn*, cmd `start`) mà không qua isolate()."""
    hits = []
    for root in roots:
        for path in _scripts(root):
            source = path.read_text(encoding="utf-8", errors="replace")
            if not _app_like(source):
                continue  # file không nhắc tới app thì không mở được app theo tên
            try:
                tree = ast.parse(source)
            except SyntaxError as error:
                hits.append(f"{path.name}:{error.lineno}: không đọc được ({error.msg})")
                continue
            assigned = _assignments(tree, source)
            params = {a.arg for f in ast.walk(tree) if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef))
                      for a in f.args.args + f.args.kwonlyargs}
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and _launch_kind(node) and _starts_app(node, source, assigned, params) \
                        and not _isolated(node, source, assigned):
                    hits.append(f"{path.relative_to(root)}:{node.lineno}")
    return hits


def test_every_app_launch_in_tools_isolates_the_profile():
    assert unisolated_launches(TOOLS) == []


@pytest.mark.skipif(not LLM_MUSIC.is_dir(), reason="máy này không có LLM_Train/music")
def test_every_app_launch_in_music_scripts_isolates_the_profile():
    assert unisolated_launches(LLM_MUSIC) == []


def test_create_suspended_isolates_the_app_only():
    source = (TOOLS / "windows_process.py").read_text(encoding="utf-8")
    body = source.split("def create_suspended(", 1)[1]
    assert re.search(r'name\.lower\(\) == "abookdesk\.exe":\s*\n\s*env = isolate\(dict\(env\)\)', body)


BAD = {
    "popen.py": 'EXE = ROOT / "dist/ABookDesk.exe"\np = subprocess.Popen([str(EXE)], env=env, cwd=str(EXE.parent))\n',
    "run_multiline.py": 'def go(exe, env):\n    subprocess.run(\n        [str(exe), "-x"],\n        env=env,\n    )\n# ABookDesk\n',
    "startfile.py": 'app = Path("D:/x/dist/ABookDesk.exe")\nos.startfile(app)\n',
    "cmd_start.py": 'desk = "ABookDesk.exe"\nsubprocess.call(["cmd", "/c", "start", "", desk])\n',
    "system.py": 'os.system("start D:/x/dist/ABookDesk.exe")\n',
    "chained.py": 'base = Path("dist")\nexe = base / "ABookDesk.exe"\nmine = exe\nsubprocess.Popen([str(mine)], env=dict(os.environ))\n',
    "cmd_list.py": 'cmd = [str(Path("dist/ABookDesk.exe")), "-x"]\nsubprocess.run(cmd + ["y"], env=env)\n',
    "shell_start.py": 'subprocess.run(["powershell.exe", "-Command", "Start-Process", str(ROOT / "dist/ABookDesk.exe")])\n',
}
GOOD = {
    "isolated.py": 'exe = Path("dist/ABookDesk.exe")\np = subprocess.Popen([str(exe)], env=isolate(env), cwd=str(exe.parent))\n',
    "env_var.py": 'exe = Path("dist/ABookDesk.exe")\nenv = isolate(dict(os.environ, LOCALAPPDATA=str(local)))\nsubprocess.run([str(exe)], env=env)\n',
    "suspended.py": 'exe = Path("dist/ABookDesk.exe")\ncreate_suspended([str(exe)], env=env, cwd=".", log=log, desktop=d, show=4)\n',
    "script_arg.py": 'cmd = [sys.executable, "shot.py", str(HERE / "dist/ABookDesk.exe")]\nsubprocess.call(cmd + ["wait=3"])\n',
    "taskkill.py": 'subprocess.run(["taskkill", "/IM", "ABookDesk.exe", "/F"])\n',
    "other_tool.py": 'EXE = Path("build/LoopQt.exe")  # cạnh ABookDesk\nsubprocess.run([FFMPEG, "-i", "x"])\nsubprocess.run([str(EXE), "s.json"], env=env)\n',
}


def test_scan_catches_every_kind_of_bare_launch(tmp_path):
    for name, body in {**BAD, **GOOD}.items():
        (tmp_path / name).write_text(body, encoding="utf-8")
    hits = unisolated_launches(tmp_path)
    assert sorted(h.split(":")[0] for h in hits) == sorted(BAD)


# ---------- app thật: không một file nào mới trong %LOCALAPPDATA%\ABook của chủ máy ----------

def _snapshot(root: Path) -> dict[str, tuple[int, int]]:
    out = {}
    if root.is_dir():
        for path in root.rglob("*"):
            try:
                stat = path.stat()
            except OSError:
                continue
            out[str(path.relative_to(root))] = (stat.st_mtime_ns, stat.st_size if path.is_file() else -1)
    return out


def _foreign_apps() -> list[int]:
    mine = {os.getpid(), *(p.pid for p in psutil.Process().parents())}
    found = []
    for process in psutil.process_iter(["pid", "name"]):
        if (process.info["name"] or "").lower() == "abookdesk.exe" and process.pid not in mine:
            found.append(process.pid)
    return found


@pytest.mark.skipif(sys.platform != "win32" or not DIST_EXE.is_file(), reason="cần dist/ABookDesk.exe đã đóng trên Windows")
def test_real_app_through_isolate_leaves_the_owner_app_data_untouched():
    if _foreign_apps():
        pytest.skip("app của người khác đang chạy: nó được quyền ghi %LOCALAPPDATA%\\ABook, so mtime không còn nghĩa")
    from windows_process import create_suspended
    owner = Path(os.environ["LOCALAPPDATA"]) / "ABook"
    before = _snapshot(owner)
    user = ctypes.WinDLL("user32", use_last_error=True)
    user.CreateDesktopW.restype = wt.HANDLE
    user.CreateDesktopW.argtypes = [wt.LPCWSTR, wt.LPCWSTR, ctypes.c_void_p, wt.DWORD, wt.DWORD, ctypes.c_void_p]
    user.CloseDesktop.argtypes = [wt.HANDLE]
    nt = ctypes.WinDLL("ntdll")
    nt.NtResumeProcess.argtypes = [wt.HANDLE]
    nt.NtResumeProcess.restype = wt.LONG
    root = Path(tempfile.mkdtemp(prefix="abook-isolate-"))
    try:
        (root / "local").mkdir()
        (root / "roaming").mkdir()
        env = {k: v for k, v in os.environ.items() if not k.upper().startswith(("QT_", "QML", "ABOOK_"))}
        env.update(LOCALAPPDATA=str(root / "local"), APPDATA=str(root / "roaming"), ABOOK_PREFERENCES=str(root / "prefs.json"),
                   ABOOK_MUTE="1", ABOOK_SMOKE_EXIT="1")
        name = f"ABookSmoke-{os.getpid()}-isolate"  # bàn làm việc ẩn: không cửa sổ nào hiện lên màn chủ máy
        desk = user.CreateDesktopW(name, None, None, 0, 0x10000000, None)
        assert desk, ctypes.WinError(ctypes.get_last_error())
        try:
            with (root / "app.log").open("wb") as log:
                process = create_suspended([str(DIST_EXE), "-qwindowgeometry", "1280x800+0+0"], env=env, cwd=str(DIST_EXE.parent),
                                           log=log, desktop=name, show=4)
            assert nt.NtResumeProcess(wt.HANDLE(int(process._handle))) == 0
            try:
                code = process.wait(60)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(10)
                code = None
        finally:
            user.CloseDesktop(desk)
        assert code == 0, (root / "app.log").read_text(encoding="utf-8", errors="replace")[-2000:]
        after = _snapshot(owner)
        changed = sorted(k for k in after if before.get(k) != after[k])
        assert changed == [], f"app ghi vào %LOCALAPPDATA%\\ABook của chủ máy: {changed[:8]}"
        # Đối chứng dương: app thật đã ghi cache của Qt - vào hồ sơ riêng.
        cache = root / "local" / "profile" / "AppData" / "Local" / "ABook" / "ABook" / "cache"
        assert (cache / "music_pcm").is_dir(), "app không ghi cache nhạc vào hồ sơ riêng"
    finally:
        shutil.rmtree(root, ignore_errors=True)
