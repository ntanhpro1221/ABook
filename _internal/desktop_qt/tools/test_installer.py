"""Bộ cài Qt từ đầu tới cuối trong hồ sơ giả và gốc registry test (docs/QT_INSTALLER.md, Q2).

Không bước nào đụng HKCU hay thư mục cài thật của chủ máy (Lead 31-10):
- bộ cài dựng với /DABOOK_TEST_ROOT=Software\\ABookTest-<uuid>; khoá ấy bị xoá trong finally, kể cả khi hỏng;
- mọi thứ (thư mục cài, LOCALAPPDATA / APPDATA / USERPROFILE / TEMP, lối tắt) nằm trong một thư mục tạm, và bộ cài bản test tự
  từ chối (mã 7) nếu thư mục cài hay lối tắt nằm ngoài %TEMP% của nó;
- khoá thật (.abook, .abookproj, ABook, ABook.Project, khoá gỡ cài, Software\\ABook, giá trị Run "ABook") và file thật (exe, bộ
  gỡ, lối tắt) được chụp trước và sau: khác một byte là đỏ;
- bộ cài và app đã cài chạy trên desktop riêng có bộ canh tiêu điểm (guarded_process / smoke_dist).

Kịch bản: kiểm tĩnh kịch bản test -> hai lần từ chối -> một bản giả cũ hơn (exe, resources thừa, lối tắt, ghim, dữ liệu người
dùng) -> cài im lặng -> file, khoá, lối tắt -> app đã cài tới host Ready bằng Python nhúng của nó -> app đã cài mở file trên
dòng lệnh + file của lần mở thứ hai (smoke_open.py) -> gỡ im lặng -> sạch.

test_installer.py <dist> [--version 0.0.1]
"""
import _winapi
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import uuid
import winreg
from pathlib import Path

import psutil

sys.path.insert(0, str(Path(__file__).resolve().parent))
from guarded_process import run_guarded  # noqa: E402
from private_profile import isolate  # noqa: E402
from smoke_dist import run as run_app  # noqa: E402
import smoke_open  # noqa: E402
from update_site import Site, TestKey  # noqa: E402

HERE = Path(__file__).resolve().parents[1]
INSTALLER = HERE / "installer"
MAKENSIS = Path(os.environ["LOCALAPPDATA"]) / "tauri" / "NSIS" / "makensis.exe"
AUMID = "ABook.Desktop"
REFUSED = 7
REAL_KEYS = [r"Software\Classes\.abook", r"Software\Classes\.abookproj", r"Software\Classes\ABook",
             r"Software\Classes\ABook.Project", r"Software\Microsoft\Windows\CurrentVersion\Uninstall\ABook", r"Software\ABook"]
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
# Dòng nào của kịch bản test (đã tiền xử lý) chứa những chữ này là nó chạm vào trạng thái thật.
REAL_STATE = re.compile(r"Software\\Classes|Software\\ABook[\\\"]|CurrentVersion\\(?:Uninstall|Run)|\$SMPROGRAMS|\$DESKTOP|\$LOCALAPPDATA|\$APPDATA|"
                        r"StartMenuPin|ApplicationDestinations|SHChangeNotify", re.I)
NO_WINDOW = 0x08000000
failures: list[str] = []


def check(ok: bool, what: str):
    print(("ok   " if ok else "FAIL ") + what, flush=True)
    if not ok:
        failures.append(what)


def read_tree(root, path: str) -> dict:
    """Mọi khoá con + giá trị dưới path, để so trước / sau."""
    out = {}
    try:
        key = winreg.OpenKey(root, path)
    except FileNotFoundError:
        return out
    with key:
        values, i = [], 0
        while True:
            try:
                values.append(winreg.EnumValue(key, i))
            except OSError:
                break
            i += 1
        out[path] = sorted(values, key=lambda v: v[0])
        i = 0
        while True:
            try:
                sub = winreg.EnumKey(key, i)
            except OSError:
                break
            out.update(read_tree(root, path + "\\" + sub))
            i += 1
    return out


def delete_tree(root, path: str):
    try:
        key = winreg.OpenKey(root, path, 0, winreg.KEY_ALL_ACCESS)
    except FileNotFoundError:
        return
    with key:
        while True:
            try:
                sub = winreg.EnumKey(key, 0)
            except OSError:
                break
            delete_tree(root, path + "\\" + sub)
    winreg.DeleteKey(root, path)


def real_state() -> dict:
    state = {path: read_tree(winreg.HKEY_CURRENT_USER, path) for path in REAL_KEYS}
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        try:
            state["run"] = winreg.QueryValueEx(key, "ABook")
        except FileNotFoundError:
            state["run"] = None
    local, roaming = Path(os.environ["LOCALAPPDATA"]), Path(os.environ["APPDATA"])
    files = [local / "ABook" / "ABook.exe", local / "ABook" / "uninstall.exe",
             roaming / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "ABook.lnk",
             Path(os.environ["USERPROFILE"]) / "Desktop" / "ABook.lnk",
             roaming / "Microsoft" / "Internet Explorer" / "Quick Launch" / "User Pinned" / "TaskBar" / "ABook.lnk"]
    for path in files:
        state[str(path)] = (path.stat().st_size, path.stat().st_mtime_ns) if path.exists() else None
    return state


def shortcuts(paths: list[Path], create: dict | None = None) -> dict:
    """Đọc đích + AppUserModelID của lối tắt (Shell.Application), hay tạo lối tắt giả {đường: đích}."""
    script = r"""
$ErrorActionPreference = 'Stop'
$create = $env:ABOOK_LNK_CREATE | ConvertFrom-Json
foreach ($p in $create.PSObject.Properties) { $l = (New-Object -ComObject WScript.Shell).CreateShortcut($p.Name); $l.TargetPath = $p.Value; $l.Save() }
$shell = New-Object -ComObject Shell.Application
$out = @{}
foreach ($p in ($env:ABOOK_LNK_READ | ConvertFrom-Json)) {
  if (Test-Path -LiteralPath $p) {
    $item = $shell.NameSpace((Split-Path $p)).ParseName((Split-Path $p -Leaf))
    $out[$p] = @{ target = (New-Object -ComObject WScript.Shell).CreateShortcut($p).TargetPath; aumid = $item.ExtendedProperty('System.AppUserModel.ID') }
  } else { $out[$p] = $null }
}
[Console]::OutputEncoding = [Text.Encoding]::UTF8
[Console]::Write(($out | ConvertTo-Json -Compress -Depth 3))
"""
    env = dict(os.environ, ABOOK_LNK_READ=json.dumps([str(p) for p in paths]), ABOOK_LNK_CREATE=json.dumps(create or {}))
    text = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], env=env, capture_output=True,
                          text=True, encoding="utf-8", creationflags=NO_WINDOW, check=True).stdout
    return json.loads(text) if text.strip() else {}


def build(dist: Path, work: Path, version: str, root_key: str) -> Path:
    files = work / "files"
    subprocess.run([sys.executable, "-X", "utf8", str(INSTALLER / "files.py"), str(dist), str(files)], check=True)
    setup = work / "abook-test-installer.exe"
    args = [str(MAKENSIS), "/V2", "/WX", f"/DVERSION={version}", f"/DVERSIONWITHBUILD={version}.0", f"/DABOOK_DIST={dist}",
            f"/DABOOK_FILES={files}", f"/DOUTFILE={setup}", f"/DABOOK_TEST_ROOT={root_key}"]
    def real_lines(command: list[str]) -> list[str]:
        pre = subprocess.run(command + ["/PPO", str(INSTALLER / "abook.nsi")], capture_output=True, text=True,
                             encoding="utf-8", errors="replace", creationflags=NO_WINDOW)
        check(pre.returncode == 0, "kịch bản tiền xử lý được")
        return [line.strip() for line in pre.stdout.splitlines()
                if REAL_STATE.search(line.split(";", 1)[0]) and not line.lstrip().startswith(("!", "#"))]
    # Đối chứng: bản phát hành phải bị bắt (khoá gỡ cài, Run, lối tắt, bỏ ghim, jump list), không thì máy dò mù.
    release = real_lines(args[:-1])
    check(len(release) >= 6, f"máy dò bắt được dòng chạm trạng thái thật của bản phát hành ({len(release)})")
    hits = real_lines(args)
    check(not hits, f"kịch bản test không chạm trạng thái thật ({hits[:3]})")
    made = subprocess.run(args + [str(INSTALLER / "abook.nsi")], capture_output=True, text=True, encoding="utf-8",
                          errors="replace", creationflags=NO_WINDOW)
    if made.returncode != 0:
        print(made.stdout[-3000:], made.stderr[-2000:])
        raise SystemExit("INSTALLER_FAIL makensis")
    return setup


def run_setup(command: list[str], env: dict, log: Path) -> int:
    with log.open("ab") as out:
        return run_guarded(command, cwd=str(log.parent), env=env, log=out, timeout=600)["exit_code"]


def values(tree: dict, path: str) -> dict:
    return {name: value for name, value, _ in tree.get(path, [])}


def check_associations(tree: dict, classes: str, install: Path, backup: str, when: str):
    exe = install / "ABook.exe"
    for ext, progid, icon, original in ((".abook", "ABook", "book_file.ico", backup), (".abookproj", "ABook.Project", "project_file.ico", "")):
        own = values(tree, classes + "\\" + ext)
        check(own.get("") == progid and own.get("ABook_backup") == original and own.get("Content Type", "").startswith("application/vnd."),
              f"{when}: {ext} -> {progid}, bản sao lưu gốc {original!r} ({own})")
        command = values(tree, classes + "\\" + progid + r"\shell\open\command").get("")
        check(command == f'"{exe}" "%1"', f"{when}: lệnh mở {ext} có ngoặc quanh exe ({command})")
        icon_path = Path(values(tree, classes + "\\" + progid + r"\DefaultIcon").get("", ""))
        check(icon_path.name == icon and icon_path.is_file(), f"{when}: biểu tượng {ext} có thật ({icon_path})")


def sleeper(python_dir: Path, into: Path) -> subprocess.Popen:
    """Chép Python nhúng của bản dựng vào `into` và chạy nó ngủ: một tiến trình có ExecutablePath dưới `into` (worker Studio
    giả, hay pythonw của người dùng ở chỗ khác)."""
    shutil.copytree(python_dir, into)
    return subprocess.Popen([str(into / "pythonw.exe"), "-c", "import time; time.sleep(900)"], creationflags=NO_WINDOW)


def snapshot(root: Path) -> dict:
    """{đường tương đối: sha256 | "-> đích" của liên kết}; không bao giờ đi theo junction / symlink."""
    out = {}
    for entry in os.scandir(root):
        path = Path(entry.path)
        rel = path.relative_to(root).as_posix()
        if entry.stat(follow_symlinks=False).st_file_attributes & 0x400:  # FILE_ATTRIBUTE_REPARSE_POINT
            out[rel] = "-> " + os.readlink(path)
        elif entry.is_dir(follow_symlinks=False):
            out.update({rel + "/" + k: v for k, v in snapshot(path).items()} or {rel + "/": "dir"})
        else:
            out[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def processes_from(path: Path) -> list[psutil.Process]:
    found = []
    for process in psutil.process_iter(["exe"]):
        try:
            if process.info["exe"] and Path(process.info["exe"]).resolve() == path.resolve():
                found.append(process)
        except (psutil.Error, OSError, ValueError):
            pass
    return found


def wait_for(predicate, seconds: float) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.5)
    return predicate()


def tree_hash(dist: Path) -> dict:
    out = {}
    for path in dist.rglob("*"):
        if path.is_file():
            rel = path.relative_to(dist).as_posix()
            out["ABook.exe" if rel == "ABookDesk.exe" else rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dist", type=Path)
    ap.add_argument("--version", default="0.0.1")
    args = ap.parse_args()
    dist = args.dist.resolve()
    root_key = rf"Software\ABookTest-{uuid.uuid4().hex}"
    before = real_state()
    work = Path(tempfile.mkdtemp(prefix="abook-inst-"))
    sleepers: list[subprocess.Popen] = []
    try:
        temp = work / "temp"
        local, roaming, shell = temp / "local", temp / "roaming", temp / "shell"
        install = local / "ABook"
        for folder in (local, roaming, shell / "Programs", shell / "Desktop", shell / "TaskBar"):
            folder.mkdir(parents=True)
        env = {k: v for k, v in os.environ.items() if not k.upper().startswith(("QT_", "QML", "ABOOK_"))}
        env.update(TEMP=str(temp), TMP=str(temp), LOCALAPPDATA=str(local), APPDATA=str(roaming), ABOOK_TEST_SHELL=str(shell),
                   QT_QPA_PLATFORM="offscreen")
        isolate(env)
        setup = build(dist, work, args.version, root_key)
        log = work / "setup.log"
        exe, lnk_programs, lnk_desktop, lnk_pin = (install / "ABook.exe", shell / "Programs" / "ABook.lnk",
                                                   shell / "Desktop" / "ABook.lnk", shell / "TaskBar" / "ABook.lnk")

        # Từ chối: không /D, rồi /D ngoài %TEMP% của bộ cài.
        check(run_setup([str(setup), "/S"], env, log) == REFUSED, "không /D -> từ chối (7)")
        outside = work / "outside" / "ABook"
        check(run_setup([str(setup), "/S", f"/D={outside}"], env, log) == REFUSED and not outside.exists(),
              "/D ngoài %TEMP% -> từ chối, không tạo thư mục")
        check(not read_tree(winreg.HKEY_CURRENT_USER, root_key), "bị từ chối thì không ghi khoá nào")

        # Bản giả cũ hơn: exe, resources thừa, khoá cũ, lối tắt + ghim trỏ vào exe ấy, dữ liệu người dùng, cache Qt, một worker
        # Studio đang chạy, và .abook đang là của app khác.
        (install / "resources" / "app").mkdir(parents=True)
        (install / "resources" / "app" / "stale.py").write_text("old", encoding="utf-8")
        exe.write_bytes(b"old")
        (install / "Studio").mkdir()
        (install / "Studio" / "work.txt").write_text("user", encoding="utf-8")
        (install / "preferences.json").write_text("{}", encoding="utf-8")
        (install / "ABook" / "cache").mkdir(parents=True)
        (install / "ABook" / "cache" / "qtpipelinecache.bin").write_bytes(b"cache")
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, root_key + r"\Uninstall\ABook") as key:
            winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, "0.0.0")
        classes = root_key + r"\Classes"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, classes + r"\.abook") as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "OtherApp")
        shortcuts([], {str(lnk_programs): str(exe), str(lnk_pin): str(exe)})
        python_dir = dist / "resources" / "python"
        worker = sleeper(python_dir, install / "Studio" / "python")
        other = sleeper(python_dir, temp / "other" / "python")
        sleepers.extend([worker, other])

        check(run_setup([str(setup), "/S", f"/D={install}"], env, log) == 0, "cài im lặng thoát 0")
        want = tree_hash(dist)
        got = {path.relative_to(install).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
               for path in install.rglob("*") if path.is_file()}
        missing = [rel for rel, digest in want.items() if got.get(rel) != digest]
        check(not missing, f"{len(want)} file đúng từng byte (thiếu / khác: {missing[:3]})")
        # Mã app chở dạng .py, bộ cài biên dịch tại chỗ (abook.nsi): mỗi .py có đúng một .pyc, trước khi app nào chạy.
        tag = next((dist / "resources" / "python").glob("python3??.dll")).stem.replace("python", "cpython-")
        compiled = {rel.rsplit("/", 1)[0] + "/__pycache__/" + rel.rsplit("/", 1)[1][:-3] + f".{tag}.pyc"
                    for rel in want if rel.startswith("resources/app/abook/") and rel.endswith(".py")}
        check(compiled and compiled <= set(got), f"{len(compiled)} .pyc biên dịch lúc cài (thiếu {sorted(compiled - set(got))[:3]})")
        user_files = {"uninstall.exe", "Studio/work.txt", "preferences.json", "ABook/cache/qtpipelinecache.bin"} | compiled
        extra = sorted(rel for rel in set(got) - set(want) - user_files if not rel.startswith("Studio/python/"))
        check(not extra, f"không file thừa, resources cũ đã xoá ({extra[:3]})")
        check((install / "Studio" / "work.txt").exists() and (install / "preferences.json").exists(), "dữ liệu người dùng còn")
        check(worker.poll() is None and other.poll() is None, "cài đè không dừng worker Studio hay pythonw ở chỗ khác")
        tree = read_tree(winreg.HKEY_CURRENT_USER, root_key)
        uninst = dict((name, value) for name, value, _ in tree.get(root_key + r"\Uninstall\ABook", []))
        check(uninst.get("DisplayName") == "ABook" and uninst.get("DisplayVersion") == args.version
              and uninst.get("Publisher") == "ABook" and uninst.get("MainBinaryName") == "ABook.exe"
              and uninst.get("UninstallString") == f'"{install}\\uninstall.exe"' and uninst.get("NoModify") == 1
              and uninst.get("EstimatedSize", 0) > 100_000, f"khoá gỡ cài đúng ({uninst})")
        manu = dict((name, value) for name, value, _ in tree.get(root_key + r"\ABook\ABook", []))
        check(manu.get("") == str(install), "chỗ cài ghi lại cho lần cập nhật")
        links = shortcuts([lnk_programs, lnk_desktop, lnk_pin])
        for path in (lnk_programs, lnk_desktop, lnk_pin):
            info = links.get(str(path)) or {}
            check(Path(info.get("target", "")) == exe and info.get("aumid") == AUMID,
                  f"lối tắt {path.parent.name}/{path.name} trỏ exe đã cài, AUMID {AUMID} ({info})")
        check_associations(read_tree(winreg.HKEY_CURRENT_USER, root_key), classes, install, "OtherApp", "cài")

        # Cập nhật cài đè (bộ cập nhật: /UPDATE): bản sao lưu vẫn là giá trị gốc, không phải "ABook" (lỗi Tauri 28-09).
        check(run_setup([str(setup), "/S", "/UPDATE", f"/D={install}"], env, log) == 0, "cập nhật im lặng thoát 0")
        check_associations(read_tree(winreg.HKEY_CURRENT_USER, root_key), classes, install, "OtherApp", "cập nhật")
        check(worker.poll() is None and (install / "Studio" / "work.txt").exists(), "cập nhật giữ Studio đang chạy")

        code, text, children = run_app(exe, 120, smoke="host")
        python = install / "resources" / "python"
        hosts = [c for c in children if Path(c).name.lower() in ("python.exe", "pythonw.exe")]
        check(code == 0 and hosts and all(Path(c).is_relative_to(python) for c in hosts),
              f"app đã cài tới host Ready bằng Python nhúng (mã {code}, host {hosts})")
        if code != 0:
            print(text[-3000:])
        # Bấm đúp file: lệnh mở của liên kết là '"<exe>" "%1"' (check_associations) - chạy đúng như thế, rồi lần mở thứ hai.
        open_logs: dict = {}
        why = smoke_open.check(exe, 120, open_logs)
        check(why is None, f"app đã cài mở file trên dòng lệnh và file của lần mở thứ hai ({why or 'ổn'})")
        if why:
            for log_name, text in open_logs.items():
                print(f"--- {log_name}", *text.splitlines()[-20:], sep="\n")

        # Q7: cập nhật thật N -> N+1 qua trang phát hành giả trên 127.0.0.1. Khoá THỬ của lượt này thay khoá thật trong bản N
        # đã cài (updater.json là chỗ duy nhất app đọc khoá); bản N+1 dựng từ một bản sao của dist có updater.json khác (dấu
        # để biết file nào là của N+1) và số 9.9.9 (lớn hơn số của exe). App chạy chế độ smoke "update": bấm "Cập nhật" như
        # người dùng, Backend::runInstaller chạy bộ cài với đúng tham số của bộ cập nhật (/P /UPDATE /R, không /D).
        key, nxt = TestKey(), "9.9.9"
        installed_updater = install / "resources" / "app" / "updater.json"
        endpoints = json.loads(installed_updater.read_text(encoding="utf-8"))["endpoints"]
        installed_updater.write_text(json.dumps({"endpoints": endpoints, "pubkey": key.pubkey()}), encoding="utf-8")
        next_dist = work / "next" / "dist"
        shutil.copytree(dist, next_dist)
        (next_dist / "resources" / "app" / "updater.json").write_text(
            json.dumps({"endpoints": ["https://example.invalid/abook-next/latest.json"], "pubkey": key.pubkey()}), encoding="utf-8")
        next_setup = build(next_dist, work / "next", nxt, root_key)
        site = Site()
        app_env = {name: env[name] for name in ("LOCALAPPDATA", "APPDATA", "TEMP", "TMP", "ABOOK_TEST_SHELL")}
        app_env["ABOOK_UPDATE_URL"] = f"{site.base}/latest.json"
        downloads = temp / "ABook-update"

        def profile(name: str) -> Path:
            # Hồ sơ của lượt chạy do test giữ (không phải thư mục tạm tự xoá của smoke_dist): bộ cài app chạy và app nó mở
            # lại (/R) thừa hưởng handle app.log, nên thư mục ấy chưa xoá được khi lượt chạy trả về.
            folder = work / "runs" / name
            folder.mkdir(parents=True)
            return folder

        def app_files() -> dict:
            return {rel: digest for rel, digest in snapshot(install).items() if rel.startswith("resources/") or "/" not in rel
                    and rel.endswith(".exe")}
        try:
            # Ca âm: đúng khoá, nhưng chữ ký của một gói khác - tải về rồi từ chối, bản N còn nguyên.
            before_files = app_files()
            site.publish(nxt, next_setup, key.sign(b"not this installer", nxt))
            code, text, _children = run_app(exe, 240, smoke="update", root=profile("bad-signature"), extra=app_env)
            reason = next((urllib.parse.unquote(line.split("SMOKE_UPDATE_FAILED ", 1)[1]) for line in text.splitlines()
                           if "SMOKE_UPDATE_FAILED " in line), "")
            check(code == 8 and "chữ ký" in reason and f"/ABook_{nxt}_x64-setup.exe" in site.requests,
                  f"cập nhật: .sig sai -> tải về rồi từ chối, app báo lỗi chữ ký (mã {code}, {reason!r})")
            if code != 8:
                print(text[-3000:])
            uninst = values(read_tree(winreg.HKEY_CURRENT_USER, root_key), root_key + r"\Uninstall\ABook")
            check(uninst.get("DisplayVersion") == args.version and app_files() == before_files
                  and not list(downloads.glob("*.exe")), f"cập nhật: .sig sai -> bản N còn nguyên, gói bị từ chối không nằm lại ({uninst.get('DisplayVersion')})")

            # Ca dương: chữ ký đúng -> app chạy bộ cài rồi thoát 0; bộ cài cài N+1 tại chỗ ghi trong registry rồi mở lại app (/R).
            site.requests.clear()
            site.publish(nxt, next_setup, key.sign(next_setup.read_bytes(), nxt))
            code, text, _children = run_app(exe, 240, smoke="update", root=profile("update"), extra=app_env)
            # App mở lại cũng kiểm bản mới: từ đây trang giả không rao bản nào lớn hơn, để nó không cài lần nữa.
            site.manifest = dict(site.manifest, version="0.0.0")
            check(code == 0 and "SMOKE_UPDATE_FOUND 9.9.9" in text, f"cập nhật: app tìm thấy {nxt}, chạy bộ cài rồi thoát 0 (mã {code})")
            if code != 0:
                print(text[-3000:])
            setup_copy = downloads / f"ABook_{nxt}_x64-setup.exe"
            check(wait_for(lambda: not processes_from(setup_copy), 300), "cập nhật: bộ cài N+1 chạy xong")
            check(wait_for(lambda: bool(processes_from(exe)), 60), "cập nhật: bộ cài mở lại app đã cài (/R)")
            relaunched = processes_from(exe)
            for process in relaunched:
                for child in process.children(recursive=True):
                    child.kill()
                process.kill()
            psutil.wait_procs(relaunched, timeout=15)
            uninst = values(read_tree(winreg.HKEY_CURRENT_USER, root_key), root_key + r"\Uninstall\ABook")
            check(uninst.get("DisplayVersion") == nxt, f"cập nhật: khoá gỡ cài ghi {nxt} ({uninst.get('DisplayVersion')})")
            want_next = tree_hash(next_dist)
            got = snapshot(install)
            wrong = [rel for rel, digest in want_next.items() if got.get(rel) != digest]
            check(not wrong and compiled <= set(got), f"cập nhật: {len(want_next)} file của N+1 đúng từng byte, .pyc biên dịch lại ({wrong[:3]})")
            check((install / "Studio" / "work.txt").read_text(encoding="utf-8") == "user"
                  and (install / "ABook" / "cache" / "qtpipelinecache.bin").read_bytes() == b"cache"
                  and worker.poll() is None, "cập nhật: dữ liệu người dùng + worker Studio đang chạy còn nguyên")
        finally:
            site.close()
            # Ca dương hỏng giữa chừng: app mở lại từ thư mục cài test không được sống tiếp sau lượt thử.
            for process in processes_from(exe):
                try:
                    for child in process.children(recursive=True):
                        child.kill()
                    process.kill()
                except psutil.Error:
                    pass

        # _?= : bộ gỡ chạy tại chỗ để chờ được nó; vì thế chính uninstall.exe không tự xoá được.
        check(run_setup([str(install / "uninstall.exe"), "/S", f"_?={install}"], env, log) == 0, "gỡ im lặng thoát 0")
        worker.wait(15) if worker.poll() is None else None
        check(worker.poll() is not None, "gỡ dừng worker Studio chạy từ thư mục Studio")
        check(other.poll() is None, "pythonw của người dùng ở chỗ khác không bị đụng")
        left = sorted(path.relative_to(install).as_posix() for path in install.rglob("*"))
        # desktop_qt.ini + logs\: app ghi lúc cập nhật ở trên (dữ liệu nằm trong %LOCALAPPDATA%\ABook như máy thật).
        written = [rel for rel in left if rel in ("desktop_qt.ini", "logs") or rel.startswith("logs/")]
        check("desktop_qt.ini" in written and [rel for rel in left if rel not in written] == ["preferences.json", "uninstall.exe"],
              f"gỡ xong: Studio + cache Qt đi, dữ liệu người dùng (cả thứ app ghi) ở lại ({left[:8]})")
        links = shortcuts([lnk_programs, lnk_desktop, lnk_pin])
        check(links.get(str(lnk_programs)) is None and links.get(str(lnk_desktop)) is None, "lối tắt Start + màn hình nền đã gỡ")
        check(links.get(str(lnk_pin)) is not None, "ghim thanh tác vụ của người dùng không bị xoá")
        tree = read_tree(winreg.HKEY_CURRENT_USER, root_key)
        check(values(tree, classes + r"\.abook") == {"": "OtherApp"} and classes + r"\.abookproj" not in tree
              and classes + r"\ABook" not in tree and classes + r"\ABook.Project" not in tree,
              f"gỡ trả .abook về app khác, bỏ .abookproj và ProgId ({ {k: v for k, v in tree.items() if v} })")
        delete_tree(winreg.HKEY_CURRENT_USER, classes)
        tree = read_tree(winreg.HKEY_CURRENT_USER, root_key)
        check(not any(tree.values()) and root_key + r"\Uninstall\ABook" not in tree and root_key + r"\ABook" not in tree,
              f"khoá test sạch ({ {k: v for k, v in tree.items() if v} })")

        # Ô "Xoá dữ liệu" (/DELETEDATA) và uninstall_guard: mỗi vòng cài lại rồi gỡ.
        def cycle(prepare, what: str) -> list[str]:
            check(run_setup([str(setup), "/S", f"/D={install}"], env, log) == 0, f"{what}: cài thoát 0")
            prepare()
            check(run_setup([str(install / "uninstall.exe"), "/S", "/DELETEDATA", f"_?={install}"], env, log) == 0,
                  f"{what}: gỡ /DELETEDATA thoát 0")
            return sorted(path.relative_to(install).as_posix() for path in install.rglob("*"))

        inside = install / "Thư viện"

        def library_inside():
            (inside / "Sách đã nhập").mkdir(parents=True)
            (inside / "Sách đã nhập" / "book.abook").write_bytes(b"book")
            (install / "preferences.json").write_text(json.dumps({"libraryRoot": str(inside)}), encoding="utf-8")
        left = cycle(library_inside, "thư viện nằm trong thư mục dữ liệu")
        check("Thư viện/Sách đã nhập/book.abook" in left and "preferences.json" in left,
              f"thư viện nằm trong thư mục dữ liệu -> giữ cả thư mục ({left[:6]})")
        shutil.rmtree(inside)

        left = cycle(lambda: (install / "preferences.json").write_text("{không phải json", encoding="utf-8"), "tuỳ chọn hỏng")
        check("preferences.json" in left, f"tuỳ chọn không đọc được -> giữ dữ liệu ({left[:6]})")

        outside_library = work / "library"
        (outside_library / "Sách đã nhập").mkdir(parents=True)
        (outside_library / "Sách đã nhập" / "book.abook").write_bytes(b"book")
        junction_target = work / "junction-target"
        junction_target.mkdir()
        (junction_target / "keep.txt").write_text("not ours", encoding="utf-8")

        def studio_junction():
            (install / "preferences.json").write_text(json.dumps({"libraryRoot": str(outside_library)}), encoding="utf-8")
            _winapi.CreateJunction(str(junction_target), str(install / "Studio"))
        # NSIS RMDir /r đi theo junction: một junction bên trong thư mục dữ liệu phải làm guard giữ cả thư mục.
        left = cycle(studio_junction, "Studio là junction")
        check((junction_target / "keep.txt").exists() and "preferences.json" in left,
              f"Studio là junction -> giữ, không đi theo liên kết ra ngoài ({left[:6]})")
        if os.path.lexists(install / "Studio"):
            os.rmdir(install / "Studio")  # gỡ chính liên kết, không đụng đích

        left = cycle(lambda: (install / "preferences.json").write_text(json.dumps({"libraryRoot": str(outside_library)}),
                                                                        encoding="utf-8"), "thư viện ở chỗ khác")
        check(left == ["uninstall.exe"], f"thư viện ở chỗ khác -> /DELETEDATA xoá hết dữ liệu ({left[:6]})")
        check((outside_library / "Sách đã nhập" / "book.abook").exists(), "thư viện sách không bao giờ bị đụng")
        tree = read_tree(winreg.HKEY_CURRENT_USER, root_key)
        check(classes + r"\.abook" not in tree and classes + r"\.abookproj" not in tree,
              "không có liên kết gốc -> gỡ xong không còn khoá .abook / .abookproj")

        # Ca an toàn (Lead 31-10, không phải đường chuyển): latest.json dùng chung, nên bộ cập nhật của một bản Tauri đã cài sẽ
        # chạy bộ cài Qt với đúng tham số của nó - "/P /UPDATE /R /ARGS", không /D (tauri-plugin-updater 2.14, updater.rs
        # updater_parameters; tauri.conf.json installMode passive). Chỗ cài là %LOCALAPPDATA%\ABook mà bộ cài Tauri ghi ở
        # Software\ABook\ABook. Bộ cài Qt được cài hay thoát lỗi, nhưng dữ liệu người dùng phải còn nguyên từng byte.
        tauri_local = temp / "tauri" / "local"
        tauri = tauri_local / "ABook"
        (tauri / "resources").mkdir(parents=True)
        shutil.copytree(dist / "resources", tauri / "resources", dirs_exist_ok=True)
        (tauri / "ABook.exe").write_bytes(b"MZ ABook Tauri 0.4.150")
        (tauri / "uninstall.exe").write_bytes(b"MZ ABook Tauri uninstaller")
        # Dữ liệu: đúng các tên có trong %LOCALAPPDATA%\ABook của một máy dùng thật, + Studio, thư viện bên trong, một file lớn
        # ngẫu nhiên, một junction ra ngoài, và dữ liệu WebView2 của vỏ Tauri (thư mục theo identifier).
        data = {"book_ids.key": os.urandom(32).hex().encode(), "book_ids.key.bak": os.urandom(32).hex().encode(),
                "computers.json": b'[{"name": "Laptop"}]', "desktop_qt.ini": b"[General]\nlibraryRoot=x\n",
                "listening-node.json": b'{"node": 1}', "listening-node.json.lock": b"", "pending-progress.json": b"{}",
                "preferences.json": json.dumps({"libraryRoot": str(tauri / "Thư viện")}).encode(),
                "cache/covers/1.jpg": os.urandom(4096), "logs/host.log": "dòng nhật ký\n".encode(),
                "ABook/cache/qtpipelinecache.bin": b"cache", "Studio/Truyện A/chương 1.txt": "Chương một".encode(),
                "Thư viện/Sách đã nhập/Truyện A.abook": os.urandom(1 << 20)}
        for rel, content in data.items():
            (tauri / rel).parent.mkdir(parents=True, exist_ok=True)
            (tauri / rel).write_bytes(content)
        webview = tauri_local / "com.ngdtuanh.abook" / "EBWebView" / "Default"
        webview.mkdir(parents=True)
        (webview / "Preferences").write_bytes(os.urandom(2048))
        canary = work / "tauri-outside"
        canary.mkdir()
        (canary / "keep.txt").write_text("không phải của ABook", encoding="utf-8")
        _winapi.CreateJunction(str(canary), str(tauri / "Liên kết"))
        for path, items in ((r"\ABook\ABook", {"": str(tauri)}),
                            (r"\Uninstall\ABook", {"DisplayName": "ABook", "DisplayVersion": "0.4.150", "Publisher": "ABook",
                                                   "UninstallString": f'"{tauri}\\uninstall.exe"', "MainBinaryName": "ABook.exe"}),
                            (r"\Classes\.abook", {"": "ABook", "ABook_backup": ""})):
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, root_key + path) as key:
                for name, value in items.items():
                    winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)

        def user_data() -> dict:
            # File của app (cả hai vỏ) không phải dữ liệu: resources\, exe, bộ gỡ, và từng file của dist Qt.
            own = {rel: digest for rel, digest in snapshot(tauri).items()
                   if not rel.startswith("resources/") and rel not in want and rel != "uninstall.exe"}
            return own | {"webview/" + rel: d for rel, d in snapshot(tauri_local / "com.ngdtuanh.abook").items()} \
                | {"outside/" + rel: d for rel, d in snapshot(canary).items()}
        before_data = user_data()
        relaunch = work / "relaunch.txt"
        tauri_env = dict(env, LOCALAPPDATA=str(tauri_local), ABOOK_TEST_RELAUNCH_LOG=str(relaunch))
        code = run_setup([str(setup), "/P", "/UPDATE", "/R", "/ARGS"], tauri_env, log)
        after_data = user_data()
        changed = sorted(rel for rel in before_data.keys() | after_data.keys() if before_data.get(rel) != after_data.get(rel))
        check(not changed and len(before_data) >= len(data) + 2,
              f"tham số của bộ cập nhật Tauri trên bản Tauri đã cài: {len(before_data)} mục dữ liệu còn nguyên từng byte, junction vẫn "
              f"là junction (thoát {code}; đổi: {changed[:4]})")
        if code == 0:
            check((tauri / "ABook.exe").read_bytes() == (dist / "ABookDesk.exe").read_bytes()
                  and relaunch.read_text(encoding="utf-8").strip('"\r\n ') == str(tauri / "ABook.exe"),
                  "tham số Tauri: cài được -> ABook.exe là bản Qt, /R mở lại đúng exe")
        else:
            check((tauri / "ABook.exe").read_bytes() == b"MZ ABook Tauri 0.4.150", f"tham số Tauri: thoát lỗi {code} -> bản Tauri còn nguyên")
        print(f"     tham số Tauri: bộ cài Qt {'cài được' if code == 0 else f'thoát {code}'}")
        os.rmdir(tauri / "Liên kết")  # gỡ chính liên kết, không đụng đích
    finally:
        for process in sleepers:
            if process.poll() is None:
                process.kill()
                process.wait(10)
        delete_tree(winreg.HKEY_CURRENT_USER, root_key)
        shutil.rmtree(work, ignore_errors=True)
    after = real_state()
    check(after == before, "HKCU và file cài thật của chủ máy không đổi một byte")
    check(not read_tree(winreg.HKEY_CURRENT_USER, root_key), "gốc registry test đã xoá")
    print("INSTALLER_OK" if not failures else f"INSTALLER_FAIL {len(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
