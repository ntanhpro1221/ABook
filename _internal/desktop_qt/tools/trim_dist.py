"""Remove the Qt Quick Controls styles the app never loads from a windeployqt dist (docs/QT_INSTALLER.md Q1).

windeployqt deploys every style of QtQuick.Controls (16.6 MB, 2.6 MB of it in the LZMA installer). The app imports only
QtQuick.Controls.Basic and main.cpp fixes QT_QUICK_CONTROLS_STYLE=Basic, so the others are dead weight. Refuses when a
QML file of the app imports one of them. build.bat runs this after windeployqt, before smoke_dist.py.

trim_dist.py <dist> [--qml <desktop_qt/qml>]
"""
import argparse
import re
import shutil
import sys
from pathlib import Path

STYLES = ("FluentWinUI3", "Fusion", "Imagine", "Material", "Universal", "Windows")


def targets(dist: Path) -> list[Path]:
    found = []
    for style in STYLES:
        found += [dist / f"Qt6QuickControls2{style}.dll", dist / f"Qt6QuickControls2{style}StyleImpl.dll",
                  dist / "qml/QtQuick/Controls" / style, dist / "qml/QtQuick/Dialogs/quickimpl/qml" / f"+{style}"]
    found.append(dist / "qml/QtQuick/NativeStyle")  # only the Windows style draws through it
    return [p for p in found if p.exists()]


def size(path: Path) -> int:
    return path.stat().st_size if path.is_file() else sum(p.stat().st_size for p in path.rglob("*") if p.is_file())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dist", type=Path)
    ap.add_argument("--qml", type=Path, default=Path(__file__).resolve().parent.parent / "qml")
    args = ap.parse_args()
    dist = args.dist.resolve()
    if not (dist / "ABookDesk.exe").is_file() or not (dist / "qml/QtQuick/Controls/Basic").is_dir():
        print(f"TRIM_FAIL {dist} is not a windeployqt dist of ABookDesk")
        return 1
    used = re.compile(r"^\s*import\s+QtQuick\.(?:Controls\.(?:" + "|".join(STYLES) + r")|NativeStyle)\b", re.M)
    users = [p.name for p in sorted(args.qml.rglob("*")) if p.suffix in {".qml", ".js"} and used.search(p.read_text(encoding="utf-8"))]
    if users:
        print(f"TRIM_FAIL the app imports a style this would remove: {', '.join(users)}")
        return 1
    before = size(dist)
    for path in targets(dist):
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
    after = size(dist)
    print(f"TRIM_OK styles {', '.join(STYLES)} + NativeStyle: {before / 1e6:.1f} MB -> {after / 1e6:.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
