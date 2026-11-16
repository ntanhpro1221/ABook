"""Discard CMake configuration when cached tools or selected SDK paths changed."""
from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

_TOOL = re.compile(r"^(CMAKE_(?:CXX_COMPILER|C_COMPILER|LINKER)):[^=]+=(.*)$")
_SDK = re.compile(r"^(Qt6\w*_DIR|QWindowKit_DIR):[^=]+=(.*)$")


def drop_stale_cmake_cache(build_dir: Path, qt_root: Path | None = None,
                          qwk_install: Path | None = None) -> bool:
    """Keep build products; invalidate configuration left by an uninstalled toolchain."""
    build = build_dir.resolve()
    cache = build / "CMakeCache.txt"
    if not cache.is_file():
        return False
    missing = []
    for line in cache.read_text(encoding="utf-8", errors="replace").splitlines():
        sdk = _SDK.match(line)
        if sdk is not None:
            key, value = sdk.groups()
            expected = qwk_install if key == "QWindowKit_DIR" else qt_root
            if expected is not None and value and not value.endswith("-NOTFOUND"):
                if not Path(value.strip('"')).resolve().is_relative_to(expected.resolve()):
                    missing.append(f"{key}={value} (selected SDK: {expected})")
        match = _TOOL.match(line)
        if match is None:
            continue
        key, value = match.groups()
        value = value.strip().strip('"')
        if not value:  # An unset optional tool is not a stale path.
            continue
        path = Path(value)
        candidate = path if path.is_absolute() else build / path
        if candidate.is_file():
            continue
        if path.name == value and shutil.which(value):
            continue  # Some generators cache a command name rather than an absolute path.
        missing.append(f"{key}={value}")
    if not missing:
        return False

    files = build / "CMakeFiles"
    # Validate both targets before deleting either; never follow a link outside this build.
    for target in (cache, files):
        if target.resolve().parent != build:
            raise ValueError(f"Refusing to clear a CMake cache target outside {build}: {target}")
    cache.unlink()
    if files.is_dir():
        shutil.rmtree(files)
    elif files.exists():
        files.unlink()
    print(f"CMake: cleared CMakeCache.txt and CMakeFiles in {build}; cached tool missing or SDK changed: {', '.join(missing)}")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("build_dir", type=Path)
    parser.add_argument("--qt-root", type=Path)
    parser.add_argument("--qwk-install", type=Path)
    args = parser.parse_args()
    drop_stale_cmake_cache(args.build_dir, args.qt_root, args.qwk_install)


if __name__ == "__main__":
    main()
