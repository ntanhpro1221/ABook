"""Reject invalid synthetic executables before Windows opens a loader error dialog."""
from __future__ import annotations

import ctypes
import os
from pathlib import Path
import struct


def is_pe_image(path: Path) -> bool:
    with path.open("rb") as stream:
        header = stream.read(64)
        if len(header) != 64 or header[:2] != b"MZ":
            return False
        offset = struct.unpack_from("<I", header, 60)[0]
        if offset < 64:
            return False
        stream.seek(offset)
        return stream.read(4) == b"PE\0\0"


def executable_from_command(command: str) -> str:
    shell = ctypes.WinDLL("shell32", use_last_error=True)
    parse = shell.CommandLineToArgvW
    parse.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_int)]
    parse.restype = ctypes.POINTER(ctypes.c_wchar_p)
    count = ctypes.c_int()
    values = parse(command, ctypes.byref(count))
    if not values:
        return ""
    try:
        return values[0] if count.value else ""
    finally:
        release = ctypes.WinDLL("kernel32", use_last_error=True).LocalFree
        release.argtypes = [ctypes.c_void_p]
        release.restype = ctypes.c_void_p
        release(ctypes.cast(values, ctypes.c_void_p))


def guarded_create_process(original, temporary_root: Path):
    root = Path(os.path.abspath(temporary_root))

    def create(application, command, *args, **kwargs):
        executable = application or executable_from_command(command)
        path = Path(os.path.abspath(executable)) if executable else None
        if path is not None and path.suffix.casefold() == ".exe" and path.is_relative_to(root):
            try:
                valid = is_pe_image(path)
            except OSError:
                pass  # Preserve the native error for absent or inaccessible files.
            else:
                if not valid:
                    raise OSError(None, "Invalid synthetic executable in test fixture", str(path), 193)
        return original(application, command, *args, **kwargs)

    return create
