"""Canh desktop mặc định (màn hình chủ máy) suốt một lượt thử: không tiến trình nào của lượt thử được có cửa sổ ở đó, và không
hộp lỗi hệ thống nào mang tên exe của lượt thử ("ABook.exe - Application Error" do csrss vẽ, PID không phải của mình).

31-10: bộ cài thử mở lại ABook.exe từ desktop riêng vừa đóng -> 0xc0000142, hộp lỗi hiện trên màn hình thật mà test vẫn xanh.
Dùng: `with DefaultDesktopWatch(work) as watch: ...` rồi `watch.seen` (rỗng = sạch). Cửa sổ đã có lúc vào `with` không tính
(hộp lỗi của lượt trước còn mở thì không làm hỏng mọi lượt sau). EnumWindows liệt kê desktop của luồng gọi,
nên phải chạy từ tiến trình đang ở desktop mặc định (test_installer chạy từ đó).
"""
import ctypes
import re
import threading
from ctypes import wintypes as wt
from pathlib import Path

import psutil

# Tên exe mà một lượt thử bộ cài có thể chạy: app, bộ cài thử, gói cập nhật, bộ gỡ (Au_.exe là bản chép tạm của NSIS),
# Python nhúng, PowerShell của stop_processes / uninstall_guard.
ERROR_CAPTION = re.compile(r"^(?:ABook|ABookDesk|abook-test-installer|ABook_[\d.]+_x64-setup|uninstall|Au_|python|pythonw|"
                           r"powershell)\.exe - ", re.I)


class DefaultDesktopWatch:
    def __init__(self, root: Path, every: float = 0.2) -> None:
        self.root = str(Path(root).resolve()).lower()
        self.every = every
        self.seen: list[str] = []
        self._before: set[int] = set()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        user = ctypes.WinDLL("user32", use_last_error=True)
        self._proc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
        user.EnumWindows.argtypes = [self._proc, wt.LPARAM]
        user.IsWindowVisible.argtypes = [wt.HWND]
        user.InternalGetWindowText.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
        user.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
        self._user = user

    def _ours(self, pid: int) -> bool:
        try:
            exe = psutil.Process(pid).exe()
        except (psutil.Error, OSError):
            return False
        return bool(exe) and exe.lower().startswith(self.root)

    def _matches(self) -> dict[int, str]:
        found: dict[int, str] = {}

        def visit(hwnd, _):
            if not self._user.IsWindowVisible(hwnd):
                return True
            title = ctypes.create_unicode_buffer(256)
            self._user.InternalGetWindowText(hwnd, title, 256)  # không gửi WM_GETTEXT: cửa sổ treo không làm treo bộ canh
            pid = wt.DWORD()
            self._user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if self._ours(pid.value) or ERROR_CAPTION.match(title.value):
                found[hwnd] = f"pid {pid.value}: {title.value!r}"
            return True
        self._user.EnumWindows(self._proc(visit), 0)
        return found

    def scan(self) -> None:
        for hwnd, item in self._matches().items():
            if hwnd not in self._before and item not in self.seen:
                self.seen.append(item)

    def _run(self) -> None:
        while not self._stop.wait(self.every):
            self.scan()

    def __enter__(self) -> "DefaultDesktopWatch":
        self._before = set(self._matches())
        self._thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self._stop.set()
        self._thread.join(5)
        self.scan()
