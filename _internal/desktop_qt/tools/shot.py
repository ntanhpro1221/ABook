"""Chụp màn hình của app để tự soát giao diện (không chiếm bàn phím / chuột của người dùng: phím và chuột gửi bằng PostMessage vào đúng cửa sổ,
ảnh lấy bằng PrintWindow nên chụp được cả khi cửa sổ bị che).

  python -X utf8 shot.py <exe> <thư mục ảnh> [--env K=V ...] [--size W,H] step step ...
step:  wait=S | shot=tên | key=esc / enter / down / f5 (PostMessage) | rkey=ctrl+3 / alt+left (phím THẬT, kéo cửa sổ lên trước) | click=X,Y | rclick=X,Y | back | move=X,Y | scroll=X,Y,delta | resize=W,H
Toạ độ là điểm ảnh của vùng client (đúng như ảnh chụp). Ví dụ:
  shot.py dist/ABookDesk.exe out --env ABOOK_PREFERENCES=fx/prefs.json wait=4 shot=library rkey=ctrl+3 wait=1 shot=settings
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import os
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image

ctypes.windll.shcore.SetProcessDpiAwareness(2)
u = ctypes.windll.user32
g = ctypes.windll.gdi32
WM_KEYDOWN, WM_KEYUP, WM_SYSKEYDOWN, WM_SYSKEYUP = 0x100, 0x101, 0x104, 0x105
WM_MOUSEMOVE, WM_LBUTTONDOWN, WM_LBUTTONUP, WM_RBUTTONDOWN, WM_RBUTTONUP, WM_MOUSEWHEEL = 0x200, 0x201, 0x202, 0x204, 0x205, 0x20A
WM_XBUTTONDOWN, WM_XBUTTONUP = 0x20B, 0x20C
VK = {"esc": 0x1B, "enter": 0x0D, "left": 0x25, "up": 0x26, "right": 0x27, "down": 0x28, "tab": 0x09, "f5": 0x74, "home": 0x24, "end": 0x23,
      "pgdn": 0x22, "pgup": 0x21, "space": 0x20, "ctrl": 0x11, "alt": 0x12, "shift": 0x10}
for c in "abcdefghijklmnopqrstuvwxyz0123456789":
    VK[c] = ord(c.upper())


def find_window(pid: int):
    found = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(h, _l):
        q = wt.DWORD()
        u.GetWindowThreadProcessId(h, ctypes.byref(q))
        if q.value == pid and u.IsWindowVisible(h):
            r = wt.RECT()
            u.GetClientRect(h, ctypes.byref(r))
            if r.right > 400:
                found.append(h)
        return True

    u.EnumWindows(cb, 0)
    return found[0] if found else None


def grab(h) -> Image.Image:
    r = wt.RECT()
    u.GetClientRect(h, ctypes.byref(r))
    w, hh = r.right, r.bottom
    hdc = u.GetDC(h)
    mdc = g.CreateCompatibleDC(hdc)
    bmp = g.CreateCompatibleBitmap(hdc, w, hh)
    g.SelectObject(mdc, bmp)
    u.PrintWindow(h, mdc, 3)  # PW_CLIENTONLY | PW_RENDERFULLCONTENT

    class BI(ctypes.Structure):
        _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG), ("biPlanes", wt.WORD), ("biBitCount", wt.WORD),
                    ("biCompression", wt.DWORD), ("biSizeImage", wt.DWORD), ("x", wt.LONG), ("y", wt.LONG), ("c", wt.DWORD), ("i", wt.DWORD)]

    bi = BI(40, w, -hh, 1, 32, 0, 0, 0, 0, 0, 0)
    buf = ctypes.create_string_buffer(w * hh * 4)
    g.GetDIBits(mdc, bmp, 0, hh, buf, ctypes.byref(bi), 0)
    g.DeleteObject(bmp)
    g.DeleteDC(mdc)
    u.ReleaseDC(h, hdc)
    return Image.frombuffer("RGBA", (w, hh), buf, "raw", "BGRA", 0, 1).convert("RGB")


def key(h, combo: str) -> None:
    """Phím đơn (esc, enter, down, f5...) gửi bằng PostMessage. Qt đọc Ctrl/Alt bằng GetKeyState nên tổ hợp có phím bổ trợ phải dùng rkey."""
    if "+" in combo:
        raise SystemExit(f"key={combo}: tổ hợp phím dùng rkey=")
    u.PostMessageW(h, WM_KEYDOWN, VK[combo.lower()], 0)
    time.sleep(0.03)
    u.PostMessageW(h, WM_KEYUP, VK[combo.lower()], 0)


def real_key(h, combo: str) -> None:
    """Phím THẬT (keybd_event) để thử phím tắt có Ctrl/Alt: kéo cửa sổ lên tiêu điểm trong chốc lát. Chỉ dùng khi máy đang không ai gõ."""
    u.keybd_event(0x12, 0, 0, 0)          # một lần Alt cho phép SetForegroundWindow
    u.keybd_event(0x12, 0, 2, 0)
    u.SetForegroundWindow(h)
    time.sleep(0.3)
    parts = combo.lower().split("+")
    for m in parts[:-1]:
        u.keybd_event(VK[m], 0, 0, 0)
    u.keybd_event(VK[parts[-1]], 0, 0, 0)
    time.sleep(0.05)
    u.keybd_event(VK[parts[-1]], 0, 2, 0)
    for m in reversed(parts[:-1]):
        u.keybd_event(VK[m], 0, 2, 0)


def lparam(x: int, y: int) -> int:
    return (y << 16) | (x & 0xFFFF)


def main() -> int:
    a = sys.argv[1:]
    if len(a) < 2:
        print(__doc__)
        return 2
    exe, outdir = Path(a[0]).resolve(), Path(a[1]).resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    steps = []
    i = 2
    while i < len(a):
        if a[i] == "--env":
            k, v = a[i + 1].split("=", 1)
            env[k] = v
            i += 2
        else:
            steps.append(a[i])
            i += 1
    p = subprocess.Popen([str(exe)], env=env, cwd=str(exe.parent))
    h = None
    t0 = time.time()
    while h is None and time.time() - t0 < 15:
        time.sleep(0.1)
        h = find_window(p.pid)
    if h is None:
        print("không thấy cửa sổ")
        p.kill()
        return 1
    # Qt Quick ngừng vẽ khi cửa sổ bị che kín (khung chụp sẽ cũ): đặt trên cùng, không lấy tiêu điểm
    u.SetWindowPos(h, ctypes.c_void_p(-1), 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)   # HWND_TOPMOST phải là c_void_p
    try:
        for s in steps:
            name, _, val = s.partition("=")
            if name == "wait":
                time.sleep(float(val))
            elif name == "shot":
                path = outdir / f"{val}.png"
                grab(h).save(path)
                print("đã chụp", path)
            elif name == "key":
                key(h, val)
            elif name == "rkey":
                real_key(h, val)
            elif name == "back":     # nút Back (nút bên) của chuột
                x, y = 400, 400
                u.PostMessageW(h, WM_MOUSEMOVE, 0, lparam(x, y))
                time.sleep(0.05)
                u.PostMessageW(h, WM_XBUTTONDOWN, (1 << 16) | 0x20, lparam(x, y))   # MK_XBUTTON1
                time.sleep(0.06)
                u.PostMessageW(h, WM_XBUTTONUP, (1 << 16), lparam(x, y))
            elif name in ("click", "rclick", "move"):
                x, y = (int(v) for v in val.split(","))
                u.PostMessageW(h, WM_MOUSEMOVE, 0, lparam(x, y))
                if name != "move":
                    d, up = (WM_LBUTTONDOWN, WM_LBUTTONUP) if name == "click" else (WM_RBUTTONDOWN, WM_RBUTTONUP)
                    time.sleep(0.05)
                    u.PostMessageW(h, d, 1, lparam(x, y))
                    time.sleep(0.06)
                    u.PostMessageW(h, up, 0, lparam(x, y))
            elif name == "scroll":
                x, y, delta = (int(v) for v in val.split(","))
                pt = wt.POINT(x, y)
                u.ClientToScreen(h, ctypes.byref(pt))   # WM_MOUSEWHEEL mang toạ độ màn hình
                u.PostMessageW(h, WM_MOUSEWHEEL, ((delta & 0xFFFF) << 16), lparam(pt.x, pt.y))
            elif name == "resize":
                w, hh = (int(v) for v in val.split(","))
                u.SetWindowPos(h, 0, 0, 0, w, hh, 0x0002 | 0x0004 | 0x0010)  # NOMOVE | NOZORDER | NOACTIVATE
            else:
                print("bước lạ:", s)
    finally:
        u.PostMessageW(h, 0x10, 0, 0)  # WM_CLOSE: thoát êm để app dừng host Python
        try:
            p.wait(8)
        except subprocess.TimeoutExpired:
            p.kill()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
