"""desktop_qt/tools/check_imports.py: a dist that leans on the build machine's System32 for a VC++ runtime DLL must fail.

Real binaries from the Python that runs the tests stand in for a dist: python3XX.dll imports VCRUNTIME140.dll, which the
build machine has in System32 and a clean PC may not.
"""
import importlib.util
import shutil
import sys
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "check_imports", Path(__file__).resolve().parents[1] / "desktop_qt/tools/check_imports.py")
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)

BASE = Path(sys.base_prefix)
PYTHON_DLL = BASE / f"python{sys.version_info.major}{sys.version_info.minor}.dll"
pytestmark = pytest.mark.skipif(sys.platform != "win32" or not PYTHON_DLL.is_file(), reason="needs a Windows python3XX.dll")


def runtime(folder: Path) -> None:
    for name in ("vcruntime140.dll", "vcruntime140_1.dll"):
        if (BASE / name).is_file():
            shutil.copy(BASE / name, folder / name)


def test_reads_the_import_table():
    names = [name.lower() for name in check.imports(PYTHON_DLL)]
    assert "kernel32.dll" in names and "vcruntime140.dll" in names


def test_runtime_only_in_system32_fails(tmp_path):
    shutil.copy(PYTHON_DLL, tmp_path / PYTHON_DLL.name)
    problems = check.missing(tmp_path)
    assert [name.lower() for name in problems[tmp_path / PYTHON_DLL.name]] == ["vcruntime140.dll"]


def test_runtime_next_to_it_passes(tmp_path):
    shutil.copy(PYTHON_DLL, tmp_path / PYTHON_DLL.name)
    runtime(tmp_path)
    assert check.missing(tmp_path) == {}


def test_python_does_not_borrow_the_qt_app_folder(tmp_path):
    # resources\python\*.pyd load from resources\python, never from dist\ where the Qt app keeps its own runtime.
    runtime(tmp_path)
    python = tmp_path / "resources" / "python"
    python.mkdir(parents=True)
    shutil.copy(PYTHON_DLL, python / PYTHON_DLL.name)
    assert tmp_path / "resources/python" / PYTHON_DLL.name in check.missing(tmp_path)
    runtime(python)
    assert check.missing(tmp_path) == {}


def test_plugin_resolves_from_the_app_folder(tmp_path):
    runtime(tmp_path)
    plugins = tmp_path / "imageformats"
    plugins.mkdir()
    shutil.copy(PYTHON_DLL, plugins / "qfake.dll")
    assert check.missing(tmp_path) == {}
