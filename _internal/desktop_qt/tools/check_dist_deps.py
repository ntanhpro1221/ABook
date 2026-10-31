"""Fail the build when the desktop app drags QtWidgets back in.

Qt.labs.platform (SystemTrayIcon / Menu) is the only thing that ever pulled Qt6Widgets.dll (6.3 MB, ~2.2 MB in the installer) into
dist. The tray is now plain Win32 (src/trayicon.cpp), so:
  - no QML file may `import Qt.labs.platform`;
  - dist must not hold Qt6Widgets.dll, Qt6LabsPlatform.dll or the labs/platform QML plugin.

  check_dist_deps.py <dist dir> <qml dir>     check the real tree
  check_dist_deps.py selftest                 plant every fault in a temp tree; each must be caught, the clean tree must pass
"""
import re
import sys
import tempfile
from pathlib import Path

IMPORT = re.compile(r"^\s*import\s+Qt\.labs\.platform\b", re.MULTILINE)
FORBIDDEN_DIST = ("Qt6Widgets.dll", "Qt6LabsPlatform.dll")


def problems(dist: Path, qml: Path) -> list[str]:
    found = []
    for path in sorted(qml.rglob("*.qml")):
        if IMPORT.search(path.read_text(encoding="utf-8", errors="replace")):
            found.append(f"QML imports Qt.labs.platform: {path}")
    if dist.exists():
        for name in FORBIDDEN_DIST:
            found += [f"dist holds {name}: {p}" for p in sorted(dist.rglob(name))]
        found += [f"dist holds the labs/platform QML plugin: {p}" for p in sorted(dist.rglob("platform")) if p.parent.name == "labs"]
    return found


def selftest() -> int:
    plants = {
        "import line": lambda d, q: (q / "Tray.qml").write_text("import QtQuick\nimport Qt.labs.platform as Native\nItem {}\n"),
        "import with version": lambda d, q: (q / "sub").mkdir() or (q / "sub" / "Tray.qml").write_text("  import Qt.labs.platform 1.1\n"),
        "Qt6Widgets.dll": lambda d, q: (d / "Qt6Widgets.dll").write_bytes(b"MZ"),
        "Qt6LabsPlatform.dll": lambda d, q: (d / "Qt6LabsPlatform.dll").write_bytes(b"MZ"),
        "labs/platform plugin": lambda d, q: (d / "qml" / "Qt" / "labs" / "platform").mkdir(parents=True),
    }
    bad = 0
    with tempfile.TemporaryDirectory(prefix="abook-deps-") as tmp:
        for name in [None, *plants]:
            root = Path(tmp) / (name or "clean").replace("/", "_").replace(" ", "_")
            dist, qml = root / "dist", root / "qml"
            dist.mkdir(parents=True)
            qml.mkdir()
            (qml / "Ok.qml").write_text("import QtQuick\n// Qt.labs.platform is only named in a comment\nItem {}\n")
            (dist / "Qt6Core.dll").write_bytes(b"MZ")
            if name:
                plants[name](dist, qml)
            caught = problems(dist, qml)
            ok = bool(caught) if name else not caught
            print(f"{'ok' if ok else 'WRONG'}: {name or 'clean tree'} -> {len(caught)} problem(s)")
            bad += not ok
    print("DIST_DEPS_SELFTEST " + ("FAILED" if bad else "ok"))
    return 1 if bad else 0


def main() -> int:
    if sys.argv[1:] == ["selftest"]:
        return selftest()
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    found = problems(Path(sys.argv[1]), Path(sys.argv[2]))
    for line in found:
        print(f"DIST_DEPS {line}")
    print(f"DIST_DEPS {len(found)} problem(s)")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
