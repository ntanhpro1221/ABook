"""Resolve the desktop SDK from the shared Qt version file."""
from __future__ import annotations

import os
from pathlib import Path
import re

VERSION_FILE = Path(__file__).resolve().parents[1] / "QT_VERSION"


def qt_version() -> str:
    version = VERSION_FILE.read_text(encoding="ascii").strip()
    if not re.fullmatch(r"6\.\d+\.\d+", version):
        raise ValueError(f"Invalid Qt version in {VERSION_FILE}")
    return version


def qt_root() -> Path:
    return Path(os.environ.get("QT_ROOT", f"D:/Novels/native_desk_proto/qt611/{qt_version()}/msvc2022_64"))


def qwk_root() -> Path:
    return Path(os.environ.get("QWK_ROOT", "D:/Novels/native_desk_proto/qwk"))


def qwk_install_root() -> Path:
    return qwk_root() / f"inst-{qt_version()}"


# One file per addon the app needs on top of the base package (tools/install_qt_sdk.py REQUIRED_ADDONS). A missing module
# would build but fail at run time: without qtimageformats every WebP voice portrait / avatar silently shows the fallback.
REQUIRED_MODULE_FILES = {
    "qtmultimedia": "bin/Qt6Multimedia.dll",
    "qttasktree": "bin/Qt6TaskTree.dll",
    "qtimageformats": "plugins/imageformats/qwebp.dll",
}


def validate_qt_root(root: Path | None = None, require_modules: bool = True) -> Path:
    selected = root if root is not None else qt_root()
    header = selected / "include/QtCore/qtcoreversion.h"
    match = re.search(r'^#define QTCORE_VERSION_STR "([^"]+)"', header.read_text(encoding="ascii"), re.M)
    if match is None or match[1] != qt_version():
        raise ValueError(f"Qt SDK at {selected} must match {VERSION_FILE}")
    if require_modules:
        missing = [f"{module} ({path})" for module, path in REQUIRED_MODULE_FILES.items() if not (selected / path).is_file()]
        if missing:
            raise ValueError(f"Qt SDK at {selected} lacks {', '.join(missing)}: "
                             f"install it with tools/install_qt_sdk.py --only-addon <module>")
    return selected


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        validate_qt_root(args.check_root)
    except (OSError, ValueError) as error:
        raise SystemExit(f"ERROR: {error}")
