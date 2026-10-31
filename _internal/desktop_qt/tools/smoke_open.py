"""Mở file từ dòng lệnh (docs/QT_INSTALLER.md, Q4 + Q5) trên bản đóng gói thật, ở desktop riêng không bao giờ hiện.

1. Bản A chạy với `python_v4.abook` trên dòng lệnh (như bấm đúp file khi app chưa mở): file phải vào Thư viện riêng của lượt
   này, tức host đã sẵn sàng rồi Main.qml mới mở nó.
2. Bản B chạy với một cuốn khác (python_v4 với chương 1 khác, smoke_play.write_package) khi A còn sống (bấm đúp file khi app đang mở): B phải thoát 0 trong vài giây mà không dựng
   host nào, và A phải nhập cuốn ấy.
Cả hai dùng chung một hồ sơ giả (LOCALAPPDATA / USERPROFILE riêng dưới thư mục tạm), nên kênh một bản của chúng không bao giờ
là kênh của app thật của chủ máy.

smoke_open.py <dist có resources/> [--seconds 90]   -> OPEN_OK / OPEN_FAIL <lý do>
smoke_packaged.py gọi `check` trên bản chép của nó (build.bat package).
"""
import argparse
import ctypes
import json
import os
import shutil
import sys
import tempfile
import time
from ctypes import wintypes as wt
from pathlib import Path

import psutil

sys.path.insert(0, str(Path(__file__).resolve().parent))
import smoke_play  # noqa: E402
from windows_process import create_suspended  # noqa: E402

INTERNAL = Path(__file__).resolve().parents[2]
WRITTEN = INTERNAL / "tests/fixtures/book_edits/written"
IMPORTED = "Sách đã nhập"   # abook/webui/packages.py IMPORTED_FOLDER
HANDOFF_S = 10.0            # lần mở thứ hai chỉ nối ống, gửi một dòng rồi thoát


def books(library: Path) -> set[str]:
    """Tên thư mục các cuốn đã nhập vào `library`."""
    folder = library / IMPORTED
    return {p.name for p in folder.iterdir() if p.is_dir()} if folder.is_dir() else set()


def wait_for(predicate, seconds: float, alive=None) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return True
        if alive is not None and alive.poll() is not None:
            return predicate()
        time.sleep(0.25)
    return predicate()


def tree(process) -> list[psutil.Process]:
    try:
        return [psutil.Process(process.pid)] + psutil.Process(process.pid).children(recursive=True)
    except psutil.Error:
        return []


def check(exe: Path, seconds: float, logs: dict) -> str | None:
    """None khi qua; không thì lý do. `exe`: ABookDesk.exe của bản đóng gói, hay ABook.exe của bản đã cài (test_installer.py).
    `logs`: nhật ký từng lần mở (a.log, b.log), điền khi xong."""
    user = ctypes.WinDLL("user32", use_last_error=True)
    user.CreateDesktopW.restype = wt.HANDLE
    user.CreateDesktopW.argtypes = [wt.LPCWSTR, wt.LPCWSTR, ctypes.c_void_p, wt.DWORD, wt.DWORD, ctypes.c_void_p]
    user.CloseDesktop.argtypes = [wt.HANDLE]
    nt = ctypes.WinDLL("ntdll")
    nt.NtResumeProcess.argtypes = [wt.HANDLE]
    nt.NtResumeProcess.restype = wt.LONG
    with tempfile.TemporaryDirectory(prefix="abook-open-", ignore_cleanup_errors=True) as tmp:
        root = Path(tmp)
        # Thư mục + tên file có dấu: Explorer truyền đường Unicode, dòng lệnh phải giữ nguyên chữ.
        incoming = root / "Sách tải về"
        for folder in (root / "local", root / "roaming", root / "temp", root / "library", incoming):
            folder.mkdir()
        first = incoming / "python_v4.abook"
        shutil.copyfile(WRITTEN / first.name, first)
        # Cuốn thứ hai phải là cuốn KHÁC (chương 1 khác): mở lại đúng cuốn đã có chỉ mở trang của nó, Thư viện không đổi.
        second = smoke_play.write_package(incoming / "Truyện khác.abook", os.urandom(4096))
        library = root / "library"
        (root / "prefs.json").write_text(json.dumps({"libraryRoot": str(library)}), encoding="utf-8")
        env = {k: v for k, v in os.environ.items() if not k.upper().startswith(("QT_", "QML", "ABOOK_"))}
        env.update(LOCALAPPDATA=str(root / "local"), APPDATA=str(root / "roaming"), TEMP=str(root / "temp"),
                   TMP=str(root / "temp"), ABOOK_PREFERENCES=str(root / "prefs.json"), ABOOK_MUTE="1",
                   QT_FORCE_STDERR_LOGGING="1")
        name = f"ABookOpen-{os.getpid()}"
        desk = user.CreateDesktopW(name, None, None, 0, 0x10000000, None)
        if not desk:
            raise ctypes.WinError(ctypes.get_last_error())
        started = []

        def launch(args, log_name):
            with (root / log_name).open("wb") as log:
                process = create_suspended([str(exe), *map(str, args)], env=env, cwd=str(exe.parent), log=log, desktop=name, show=4)
            started.append(process)
            if nt.NtResumeProcess(wt.HANDLE(int(process._handle))) != 0:
                raise RuntimeError("cannot resume the app")
            return process

        try:
            a = launch([first], "a.log")
            if not wait_for(lambda: len(books(library)) == 1, seconds, alive=a):
                return f"file trên dòng lệnh không vào Thư viện trong {seconds:g} s (A {'còn' if a.poll() is None else 'đã thoát'})"
            have = books(library)
            b = launch([second], "b.log")
            try:
                code = b.wait(HANDOFF_S)
            except Exception:
                return f"lần mở thứ hai không thoát trong {HANDOFF_S:g} s"
            if code != 0:
                return f"lần mở thứ hai thoát mã {code}"
            if not wait_for(lambda: len(books(library)) == 2, seconds, alive=a):
                return f"bản đang chạy không nhập file của lần mở thứ hai (Thư viện: {sorted(books(library))})"
            if a.poll() is not None:
                return f"bản đang chạy đã thoát (mã {a.poll()})"
            if not have <= books(library):
                return "cuốn đầu biến mất sau lần mở thứ hai"
            return None
        finally:
            # Chỉ cây tiến trình lượt này tự dựng (ABookDesk + host của nó), không gì khác.
            for process in started:
                for member in reversed(tree(process)):
                    try:
                        member.kill()
                    except psutil.Error:
                        pass
                try:
                    process.wait(10)
                except Exception:
                    pass
            user.CloseDesktop(desk)
            for log_name in ("a.log", "b.log"):
                if (root / log_name).is_file():
                    logs[log_name] = (root / log_name).read_text(encoding="utf-8", errors="replace")
            time.sleep(1)   # host vừa bị giết còn giữ file trong thư mục tạm một lúc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dist", type=Path)
    ap.add_argument("--seconds", type=float, default=90)
    args = ap.parse_args()
    dist = args.dist.resolve()
    for need in ("ABookDesk.exe", "resources/python/pythonw.exe", "resources/app/abook/webui/host.py"):
        if not (dist / need).is_file():
            print(f"OPEN_FAIL thiếu {need} (build.bat package trước)")
            return 1
    # Bản chép ngoài cây nguồn, như smoke_packaged.py: dist nằm trong cây thì Backend đi tìm host của bản dev (runtime/.venv).
    copy = Path(tempfile.mkdtemp(prefix="abook-open-app-"))
    logs = {}
    try:
        if any((parent / "abook/webui/host.py").is_file() for parent in copy.parents):
            print(f"OPEN_FAIL {copy} nằm dưới một cây nguồn; host sẽ không chạy từ resources/")
            return 1
        shutil.copytree(dist, copy / "ABook")
        why = check(copy / "ABook" / "ABookDesk.exe", args.seconds, logs)
    finally:
        shutil.rmtree(copy, ignore_errors=True)
    if why is not None:
        for log_name, text in logs.items():
            print(f"--- {log_name}")
            print("\n".join(text.splitlines()[-40:]))
    print("OPEN_OK hai lần mở file vào đúng một bản" if why is None else f"OPEN_FAIL {why}")
    return 0 if why is None else 1


if __name__ == "__main__":
    sys.exit(main())
