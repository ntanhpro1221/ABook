"""Bộ cài Qt từ đầu tới cuối trong hồ sơ giả và gốc registry test (docs/QT_INSTALLER.md, Q2).

Không bước nào đụng HKCU hay thư mục cài thật của chủ máy (Lead 31-10):
- bộ cài dựng với /DABOOK_TEST_ROOT=Software\\ABookTest-<uuid>; khoá ấy bị xoá trong finally, kể cả khi hỏng;
- mọi thứ (thư mục cài, LOCALAPPDATA / APPDATA / USERPROFILE / TEMP, lối tắt) nằm trong một thư mục tạm, và bộ cài bản test tự
  từ chối (mã 7) nếu thư mục cài hay lối tắt nằm ngoài %TEMP% của nó;
- khoá thật (.abook, .abookproj, ABook, ABook.Project, khoá gỡ cài, Software\\ABook, giá trị Run "ABook") và file thật (exe, bộ
  gỡ, lối tắt) được chụp trước và sau: khác một byte là đỏ;
- bộ cài và app đã cài chạy trên desktop riêng có bộ canh tiêu điểm (guarded_process / smoke_dist).

Kịch bản: kiểm tĩnh kịch bản test -> hai lần từ chối -> một bản giả cũ hơn (exe, resources thừa, lối tắt, ghim, dữ liệu người
dùng) -> cài im lặng -> file, khoá, lối tắt -> app đã cài tới host Ready bằng Python nhúng của nó -> gỡ im lặng -> sạch.

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
import uuid
import winreg
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from guarded_process import run_guarded  # noqa: E402
from private_profile import isolate  # noqa: E402
from smoke_dist import run as run_app  # noqa: E402

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
        user_files = {"uninstall.exe", "Studio/work.txt", "preferences.json", "ABook/cache/qtpipelinecache.bin"}
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

        # _?= : bộ gỡ chạy tại chỗ để chờ được nó; vì thế chính uninstall.exe không tự xoá được.
        check(run_setup([str(install / "uninstall.exe"), "/S", f"_?={install}"], env, log) == 0, "gỡ im lặng thoát 0")
        worker.wait(15) if worker.poll() is None else None
        check(worker.poll() is not None, "gỡ dừng worker Studio chạy từ thư mục Studio")
        check(other.poll() is None, "pythonw của người dùng ở chỗ khác không bị đụng")
        left = sorted(path.relative_to(install).as_posix() for path in install.rglob("*"))
        check(left == ["preferences.json", "uninstall.exe"], f"gỡ xong: Studio + cache Qt đi, dữ liệu người dùng ở lại ({left[:6]})")
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
