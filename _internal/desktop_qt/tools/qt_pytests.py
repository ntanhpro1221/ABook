"""Run the pytest rules that read the Qt sources, as part of build.bat.

They live in _internal/tests next to the web/phone rules, so a Qt-only build never ran them: on 31-10 a parity edit that
reversed four labels ("Không tìm được" instead of the web's "Chưa tìm được") passed every QtTest and only
test_qt_copy_rules.py knew. Every tests/test_qt_*.py is picked up by name, plus the parity checks that compare Qt with
web and phone.
"""
import os
import sys
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parents[2] / "tests"
PARITY = ("test_ui_parity_qt.py", "test_moreinfo_parity.py", "test_host_wait_parity.py")


def files() -> list[str]:
    found = sorted(TESTS.glob("test_qt_*.py")) + [TESTS / name for name in PARITY]
    missing = [path.name for path in found if not path.exists()]
    if missing:
        sys.exit(f"qt_pytests: missing {', '.join(missing)}")
    return [str(path) for path in found]


if __name__ == "__main__":
    os.chdir(TESTS.parent)  # _internal, as `python -m pytest` from there: tests import abook and scripts from it
    sys.path.insert(0, str(TESTS.parent))
    sys.exit(pytest.main(["-q", "-p", "no:cacheprovider", "-rf", *files()]))
