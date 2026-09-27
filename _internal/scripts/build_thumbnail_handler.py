"""Build thumbnail handler của Explorer (bìa sách cho .abook / .abookproj) bằng MinGW-w64.

    runtime/.venv/Scripts/python.exe scripts/build_thumbnail_handler.py

Ra build/windows/abook_thumbnail.dll (Explorer nạp; trình cài đặt đăng ký cho người dùng hiện tại) và
build/windows/thumbnail_probe.exe (thử DLL không cần registry - tests/test_thumbnail_handler.py). Link tĩnh runtime
C++ để DLL không kéo theo libstdc++/libgcc: Explorer nạp nó trong tiến trình của Windows.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "windows" / "thumbnail"
OUT = ROOT / "build" / "windows"
DLL = OUT / "abook_thumbnail.dll"
PROBE = OUT / "thumbnail_probe.exe"
FLAGS = ["-std=c++17", "-O2", "-Wall", "-Wextra", "-static", "-static-libgcc", "-static-libstdc++"]
LIBS = ["-lole32", "-loleaut32", "-luuid", "-lwindowscodecs", "-lshlwapi", "-lgdi32"]


def compiler() -> str | None:
    """g++ của MinGW-w64: trên PATH, hoặc chỗ cài mặc định."""
    found = shutil.which("g++")
    if found:
        return found
    for candidate in (Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "mingw64" / "bin" / "g++.exe",
                      Path(r"C:\msys64\mingw64\bin\g++.exe")):
        if candidate.is_file():
            return str(candidate)
    return None


def build() -> tuple[Path, Path]:
    """Build nếu nguồn mới hơn đầu ra; trả (dll, probe)."""
    gpp = compiler()
    if gpp is None:
        raise RuntimeError("Không thấy g++ (MinGW-w64) - cài MinGW-w64 hoặc dùng bản DLL build sẵn.")
    OUT.mkdir(parents=True, exist_ok=True)
    sources = list(SOURCE.iterdir())
    newest = max(path.stat().st_mtime for path in sources)
    jobs = (
        (DLL, [str(SOURCE / "abook_thumbnail.cpp"), str(SOURCE / "abook_thumbnail.def"), "-shared"]),
        (PROBE, [str(SOURCE / "thumbnail_probe.cpp"), "-municode"]),
    )
    for target, inputs in jobs:
        if target.is_file() and target.stat().st_mtime >= newest:
            continue
        # g++ gọi as/ld cùng thư mục: đưa thư mục ấy lên PATH cho trường hợp g++ không nằm trên PATH
        env = {**os.environ, "PATH": str(Path(gpp).parent) + os.pathsep + os.environ.get("PATH", "")}
        subprocess.run([gpp, *FLAGS, *inputs, "-o", str(target), *LIBS], check=True, env=env)
    return DLL, PROBE


def main() -> int:
    try:
        dll, probe = build()
    except (RuntimeError, subprocess.CalledProcessError) as error:
        print(error, file=sys.stderr)
        return 1
    print(dll)
    print(probe)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
