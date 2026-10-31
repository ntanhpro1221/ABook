"""Remove from a windeployqt dist what the app never loads (docs/QT_INSTALLER.md Q1 + cỡ bộ cài).

build.bat runs this after windeployqt, before the VC runtime copy, check_imports.py and smoke_dist.py. dist\ is reused
between builds, so everything goes here (a file from an older build is removed too), each with why it is dead:
- Qt Quick Controls styles: the app imports only QtQuick.Controls.Basic and main.cpp fixes QT_QUICK_CONTROLS_STYLE=Basic.
  windeployqt deploys all of them (16.6 MB, 2.6 MB of the installer).
- QtQuick.Effects: windeployqt deploys it for the styles above; no QML left in the dist imports it.
- styles\ (QStyle plugin): only a QApplication loads one; main.cpp builds a QGuiApplication.
- tls\ and networkinformation\: every request of the C++ side goes to the host on http://127.0.0.1 (https, downloads and
  updates are the host's, in Python with its own OpenSSL); nothing calls QNetworkInformation.
- VC runtime DLLs no binary imports (concrt140, vccorlib140, msvcp140_atomic_wait, msvcp140_codecvt_ids,
  vcruntime140_threads): left from builds that copied the whole redist folder. check_imports.py proves the rest suffices.
Refuses when the app's QML or C++ uses one of these after all.

trim_dist.py <dist> [--qml <desktop_qt/qml>] [--src <desktop_qt/src>]
"""
import argparse
import re
import shutil
import sys
from pathlib import Path

STYLES = ("FluentWinUI3", "Fusion", "Imagine", "Material", "Universal", "Windows")
UNUSED_RUNTIME = ("concrt140.dll", "vccorlib140.dll", "msvcp140_atomic_wait.dll", "msvcp140_codecvt_ids.dll",
                  "vcruntime140_threads.dll")
QML_USES = re.compile(r"^\s*import\s+QtQuick\.(?:Controls\.(?:" + "|".join(STYLES) + r")|NativeStyle|Effects)\b", re.M)
CPP_USES = re.compile(r"\bQ(?:Ssl\w*|NetworkInformation|Application|Style|ProxyStyle|CommonStyle)\b|<QtWidgets")


def targets(dist: Path) -> list[Path]:
    found = []
    for style in STYLES:
        found += [dist / f"Qt6QuickControls2{style}.dll", dist / f"Qt6QuickControls2{style}StyleImpl.dll",
                  dist / "qml/QtQuick/Controls" / style, dist / "qml/QtQuick/Dialogs/quickimpl/qml" / f"+{style}"]
    found.append(dist / "qml/QtQuick/NativeStyle")  # only the Windows style draws through it
    found += [dist / "Qt6QuickEffects.dll", dist / "qml/QtQuick/Effects", dist / "styles", dist / "tls",
              dist / "networkinformation"]
    found += [dist / name for name in UNUSED_RUNTIME]
    return [p for p in found if p.exists()]


def size(path: Path) -> int:
    return path.stat().st_size if path.is_file() else sum(p.stat().st_size for p in path.rglob("*") if p.is_file())


def users(root: Path, suffixes: set[str], pattern: re.Pattern, going: tuple[Path, ...] = ()) -> list[str]:
    """Files under `root` matching `pattern`, except those inside `going` (removed with what they import)."""
    return [f"{p.name}: {m.group(0).strip()}" for p in sorted(root.rglob("*"))
            if p.suffix in suffixes and not any(p.is_relative_to(g) for g in going)
            for m in [pattern.search(p.read_text(encoding="utf-8"))] if m]


def main():
    here = Path(__file__).resolve().parent.parent
    ap = argparse.ArgumentParser()
    ap.add_argument("dist", type=Path)
    ap.add_argument("--qml", type=Path, default=here / "qml")
    ap.add_argument("--src", type=Path, default=here / "src")
    args = ap.parse_args()
    dist = args.dist.resolve()
    if not (dist / "ABookDesk.exe").is_file() or not (dist / "qml/QtQuick/Controls/Basic").is_dir():
        print(f"TRIM_FAIL {dist} is not a windeployqt dist of ABookDesk")
        return 1
    found = users(args.qml, {".qml", ".js"}, QML_USES) + users(args.src, {".cpp", ".h"}, CPP_USES)
    # The dist's own QML that stays must not import what goes either (Dialogs' +<Style> variants go with their style).
    going = tuple(targets(dist))
    found += [f"dist {hit}" for hit in users(dist / "qml/QtQuick/Controls/Basic", {".qml"}, QML_USES, going)]
    found += [f"dist {hit}" for hit in users(dist / "qml/QtQuick/Dialogs", {".qml"}, QML_USES, going)]
    if found:
        print(f"TRIM_FAIL the app uses something this would remove: {'; '.join(found)}")
        return 1
    before = size(dist)
    for path in going:
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
    after = size(dist)
    print(f"TRIM_OK unused styles, effects, plugins and VC runtime DLLs: {before / 1e6:.1f} MB -> {after / 1e6:.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
