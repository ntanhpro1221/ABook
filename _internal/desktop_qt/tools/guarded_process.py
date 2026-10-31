"""Run a process tree on a never-switched desktop, with a pre-resume focus guard."""
import ctypes
from ctypes import wintypes as wt
import os
import subprocess
import threading
import time

import psutil
from windows_process import create_suspended


def run_guarded(command, *, cwd, env, log, timeout=1200):
    if env.get("QT_QPA_PLATFORM") != "offscreen" and not (
        env.get("QT_QPA_PLATFORM") == "windows" and env.get("ABOOK_GUARDED_NATIVE") == "1"):
        raise RuntimeError("Only offscreen Qt or explicitly guarded native tests on the never-switched desktop are permitted")
    user = ctypes.WinDLL("user32", use_last_error=True)
    user.CreateDesktopW.restype = wt.HANDLE
    user.CreateDesktopW.argtypes = [wt.LPCWSTR, wt.LPCWSTR, ctypes.c_void_p, wt.DWORD, wt.DWORD, ctypes.c_void_p]
    user.CloseDesktop.argtypes = [wt.HANDLE]
    user.GetForegroundWindow.restype = wt.HWND
    user.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
    user.GetThreadDesktop.argtypes = [wt.DWORD]
    user.GetThreadDesktop.restype = wt.HANDLE
    user.GetUserObjectInformationW.argtypes = [wt.HANDLE, ctypes.c_int, ctypes.c_void_p, wt.DWORD, ctypes.POINTER(wt.DWORD)]
    def desktop_name(handle):
        value = ctypes.create_unicode_buffer(256)
        needed = wt.DWORD()
        return value.value if user.GetUserObjectInformationW(handle, 2, value, ctypes.sizeof(value), ctypes.byref(needed)) else "unavailable"
    name = f"ABookGuard-{os.getpid()}-{time.monotonic_ns()}"
    desk = user.CreateDesktopW(name, None, None, 0, 0x10000000, None)
    if not desk:
        raise ctypes.WinError()
    kernel = ctypes.WinDLL("kernel32")
    previous = kernel.SetErrorMode(0x8003)
    try:
        process = create_suspended(command, cwd=cwd, env=env, log=log, desktop=name)
    finally:
        kernel.SetErrorMode(previous)
    ready, stopped = threading.Event(), threading.Event()
    violations, errors = [], []
    callback_type = ctypes.WINFUNCTYPE(None, wt.HANDLE, wt.DWORD, wt.HWND, wt.LONG, wt.LONG, wt.DWORD, wt.DWORD)

    def guard():
        def inspect(hwnd):
            pid = wt.DWORD()
            tid = user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            try:
                ours = pid.value == process.pid or any(p.pid == process.pid for p in psutil.Process(pid.value).parents())
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                ours = False
            if ours:
                violations.append({"pid": pid.value, "time": time.time(),
                    "window_desktop": desktop_name(user.GetThreadDesktop(tid))})
                process.kill()
        @callback_type
        def changed(_hook, _event, hwnd, _object, _child, _thread, _time):
            inspect(hwnd)
        user.SetWinEventHook.restype = wt.HANDLE
        user.SetWinEventHook.argtypes = [wt.DWORD, wt.DWORD, wt.HMODULE, callback_type, wt.DWORD, wt.DWORD, wt.DWORD]
        user.UnhookWinEvent.argtypes = [wt.HANDLE]
        hook = user.SetWinEventHook(3, 3, None, changed, 0, 0, 0)
        if not hook:
            errors.append("Foreground guard unavailable")
        ready.set()
        message = wt.MSG()
        while not stopped.is_set():
            while user.PeekMessageW(ctypes.byref(message), None, 0, 0, 1):
                user.TranslateMessage(ctypes.byref(message))
                user.DispatchMessageW(ctypes.byref(message))
            inspect(user.GetForegroundWindow())
            stopped.wait(.01)
        if hook:
            user.UnhookWinEvent(hook)

    thread = threading.Thread(target=guard, daemon=True)
    thread.start()
    try:
        if not ready.wait(5) or errors:
            raise RuntimeError(str(errors))
        nt = ctypes.WinDLL("ntdll")
        nt.NtResumeProcess.argtypes = [wt.HANDLE]
        if nt.NtResumeProcess(wt.HANDLE(int(process._handle))) != 0:
            raise RuntimeError("Could not resume guarded process")
        code = process.wait(timeout)
    finally:
        if process.poll() is None:
            for child in psutil.Process(process.pid).children(recursive=True):
                try:
                    child.kill()
                except psutil.NoSuchProcess:
                    pass
            process.kill()
            process.wait()
        stopped.set()
        thread.join(3)
        user.CloseDesktop(desk)
    result = {"exit_code": code, "foreground_events": len(violations), "errors": errors,
              "platform": env["QT_QPA_PLATFORM"], "isolated_desktop": True, "guard_before_resume": True,
              "isolated_desktop_name": name, "foreground_details": violations}
    result["desktop_verified_before_resume"] = process.desktop
    if violations or errors:
        raise RuntimeError(str(result))
    return result
