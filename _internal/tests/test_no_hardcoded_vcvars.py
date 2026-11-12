"""Build scripts must find MSVC through vswhere, never through one edition's install path.

11-11 the Visual Studio Community IDE was uninstalled; every script that hard-coded
.../18/Community/.../vcvars64.bat broke the release build although Build Tools work the same.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
EDITION_PATH = re.compile(r"Microsoft Visual Studio[\\/]+\d+[\\/]+(Community|Professional|Enterprise|BuildTools)", re.I)
SKIP = {"node_modules", "build", "dist", ".venv", "runtime", "__pycache__"}


def _sources():
    for path in ROOT.rglob("*"):
        if path.suffix.lower() not in {".bat", ".cmd", ".py", ".ps1"} or not path.is_file():
            continue
        if SKIP.intersection(path.relative_to(ROOT).parts) or path.name == Path(__file__).name:
            continue
        yield path


def test_no_script_hard_codes_a_visual_studio_edition():
    offenders = [str(p.relative_to(ROOT)) for p in _sources()
                 if EDITION_PATH.search(p.read_text(encoding="utf-8", errors="replace"))]
    assert offenders == [], f"use desktop_qt/tools/find_vcvars.bat or release_gate.find_vcvars(): {offenders}"


def test_find_vcvars_bat_is_crlf():
    data = (ROOT / "desktop_qt/tools/find_vcvars.bat").read_bytes()
    assert data.count(b"\n") == data.count(b"\r\n")
