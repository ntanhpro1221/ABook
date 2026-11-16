"""The Qt SDK choice must agree across Python, CMake and Windows build entrypoints."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import re

import pytest

ROOT = Path(__file__).resolve().parents[1]
QT = ROOT / "desktop_qt"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sdk = load("tested_qt_sdk", QT / "tools/qt_sdk.py")
cache_helper = load("tested_qt_sdk_cache", QT / "tools/drop_stale_cmake_cache.py")


def version_literals(text):
    return re.findall(r"(?<!\d)6\.\d+\.\d+(?!\d)", text)


def test_guard_finds_a_copied_qt_path():
    assert version_literals('set QT_ROOT=D:/Qt/' + '6.' + '99.1/msvc2022_64')
    assert not version_literals('set QT_ROOT=D:/Qt/%QT_VERSION%/msvc2022_64')


def test_build_code_has_no_qt_version_copies():
    sources = [QT / "build.bat", QT / "CMakeLists.txt",
               ROOT / "scripts/release_gate.py", ROOT / "scripts/bookmusic_job.py"]
    sources += [path for path in (QT / "tools").rglob("*")
                if path.suffix in {".py", ".bat", ".cmake"} or path.name == "CMakeLists.txt"]
    found = {str(path.relative_to(ROOT)): matches for path in sources
             if (matches := version_literals(path.read_text(encoding="utf-8")))}
    assert not found, f"Qt versions belong only in desktop_qt/QT_VERSION: {found}"


def test_sdk_defaults_and_qwk_share_the_version_file(tmp_path, monkeypatch):
    version_file = tmp_path / "QT_VERSION"
    version_file.write_text('6.' + '99.1\n', encoding="ascii")
    monkeypatch.setattr(sdk, "VERSION_FILE", version_file)
    monkeypatch.delenv("QT_ROOT", raising=False)
    monkeypatch.delenv("QWK_ROOT", raising=False)
    assert sdk.qt_root() == Path("D:/Novels/native_desk_proto/qt611") / sdk.qt_version() / "msvc2022_64"
    assert sdk.qwk_install_root() == sdk.qwk_root() / ("inst-" + sdk.qt_version())
    monkeypatch.setenv("QT_ROOT", str(tmp_path / "sdk"))
    monkeypatch.setenv("QWK_ROOT", str(tmp_path / "qwk"))
    assert sdk.qt_root() == tmp_path / "sdk"
    assert sdk.qwk_install_root() == tmp_path / "qwk" / ("inst-" + sdk.qt_version())


@pytest.mark.parametrize("value", ["", "6.11", "6.11.3 trailing", "7.0.0"])
def test_invalid_version_file_is_rejected(tmp_path, monkeypatch, value):
    version_file = tmp_path / "QT_VERSION"
    version_file.write_text(value, encoding="ascii")
    monkeypatch.setattr(sdk, "VERSION_FILE", version_file)
    with pytest.raises(ValueError, match="Invalid Qt version"):
        sdk.qt_version()


@pytest.mark.parametrize("key", ["Qt6_DIR", "Qt6Core_DIR", "Qt6QmlPrivate_DIR", "QWindowKit_DIR"])
def test_changed_sdk_discards_configuration_but_preserves_products(tmp_path, key):
    build = tmp_path / "build"
    build.mkdir()
    cache = build / "CMakeCache.txt"
    cache.write_text(f"{key}:PATH={tmp_path / 'previous/lib/cmake' / key}\n", encoding="utf-8")
    files = build / "CMakeFiles"
    files.mkdir()
    product = build / "kept.obj"
    product.write_bytes(b"compiled product")
    assert cache_helper.drop_stale_cmake_cache(build, tmp_path / "sdk", tmp_path / "qwk")
    assert not cache.exists() and not files.exists()
    assert product.read_bytes() == b"compiled product"


def test_matching_sdk_preserves_configuration(tmp_path):
    cache = tmp_path / "CMakeCache.txt"
    cache.write_text(f"Qt6Core_DIR:PATH={tmp_path / 'sdk/lib/cmake/Qt6Core'}\n"
                     f"QWindowKit_DIR:PATH={tmp_path / 'qwk/lib/cmake/QWindowKit'}\n", encoding="utf-8")
    before = cache.read_bytes()
    assert not cache_helper.drop_stale_cmake_cache(tmp_path, tmp_path / "sdk", tmp_path / "qwk")
    assert cache.read_bytes() == before


def test_sdk_header_must_match_the_version_file(tmp_path):
    header = tmp_path / "include/QtCore/qtcoreversion.h"
    header.parent.mkdir(parents=True)
    header.write_text(f'#define QTCORE_VERSION_STR "{sdk.qt_version()}"\n', encoding="ascii")
    assert sdk.validate_qt_root(tmp_path) == tmp_path
    header.write_text('#define QTCORE_VERSION_STR "' + '6.' + '99.1"\n', encoding="ascii")
    with pytest.raises(ValueError, match="must match"):
        sdk.validate_qt_root(tmp_path)
