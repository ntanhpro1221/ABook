"""Discard CMake's toolchain cache only when a cached build tool has gone away."""
from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

_TOOL = re.compile(r"^(CMAKE_(?:CXX_COMPILER|C_COMPILER|LINKER)):[^=]+=(.*)$")


def drop_stale_cmake_cache(build_dir: Path) -> bool:
    """Keep build products; invalidate configuration left by an uninstalled toolchain."""
    build = build_dir.resolve()
    cache = build / "CMakeCache.txt"
    if not cache.is_file():
        return False
    missing = []
    for line in cache.read_text(encoding="utf-8", errors="replace").splitlines():
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
    print(f"CMake: cleared CMakeCache.txt and CMakeFiles in {build}; cached tool missing: {', '.join(missing)}")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("build_dir", type=Path)
    args = parser.parse_args()
    drop_stale_cmake_cache(args.build_dir)


if __name__ == "__main__":
    main()
