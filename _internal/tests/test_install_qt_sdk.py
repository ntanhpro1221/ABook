"""Repository selection and integrity checks must fail before extraction."""
from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
import urllib.error

import pytest

TOOLS = Path(__file__).resolve().parents[1] / 'desktop_qt/tools'
sys.path.insert(0, str(TOOLS))
spec = importlib.util.spec_from_file_location('tested_install_qt_sdk', TOOLS / 'install_qt_sdk.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


def test_plan_selects_complete_base_and_requested_addons():
    version = installer.qt_version()
    stem = 'qt.qt6.' + version.replace('.', '')
    xml = ('<Updates><PackageUpdate><Name>' + stem + '.win64_msvc2022_64</Name><Version>' + version + '-0-build</Version>'
           '<DownloadableArchives>qtbase.7z, qttools.7z, qtsvg.7z</DownloadableArchives></PackageUpdate>'
           '<PackageUpdate><Name>' + stem + '.addons.qtmultimedia.win64_msvc2022_64</Name><Version>' + version + '-0-build</Version>'
           '<DownloadableArchives>qtmultimedia.7z</DownloadableArchives></PackageUpdate></Updates>')
    plan = installer.archive_plan(xml.encode(), version, ['qtmultimedia'])
    assert [row['archive'] for row in plan] == ['qtbase.7z', 'qttools.7z', 'qtsvg.7z', 'qtmultimedia.7z']
    assert all(row['relative_url'].endswith(version + '-0-build' + row['archive']) for row in plan)


def test_checksum_mismatch_never_publishes_archive(tmp_path, monkeypatch):
    def fetch(url, path):
        if url.endswith('.sha256'):
            path.write_text(hashlib.sha256(b'correct').hexdigest(), encoding='ascii')
        else:
            path.write_bytes(b'wrong')
    monkeypatch.setattr(installer, 'fetch', fetch)
    with pytest.raises(ValueError, match='Checksum mismatch'):
        installer.verified_archive('https://example.invalid/', dict(archive='qtbase.7z', relative_url='qtbase.7z'), tmp_path)
    assert not (tmp_path / 'qtbase.7z').exists()


def test_sha1_fallback_and_cached_archive_is_rechecked(tmp_path, monkeypatch):
    calls = []
    def fetch(url, path):
        calls.append(url)
        if url.endswith('.sha256'):
            raise urllib.error.HTTPError(url, 404, 'not found', {}, None)
        if url.endswith('.sha1'):
            path.write_text(hashlib.sha1(b'correct').hexdigest(), encoding='ascii')
        else:
            path.write_bytes(b'correct')
    monkeypatch.setattr(installer, 'fetch', fetch)
    (tmp_path / 'qtbase.7z').write_bytes(b'corrupt')
    row = dict(archive='qtbase.7z', relative_url='package/buildqtbase.7z')
    archive = installer.verified_archive('https://example.invalid/', row, tmp_path)
    assert archive.read_bytes() == b'correct'
    assert row['algorithm'] == 'sha1'
    calls.clear()
    installer.verified_archive('https://example.invalid/', row, tmp_path)
    assert all(url.endswith(('.sha256', '.sha1')) for url in calls)


@pytest.mark.parametrize('name', ['../other-sdk/bin/Qt6Core.dll', '/bin/Qt6Core.dll', 'C:/Qt/bin/Qt6Core.dll'])
def test_extraction_rejects_paths_outside_the_selected_sdk(tmp_path, monkeypatch, name):
    class Packed:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def getnames(self): return [name]
        def extractall(self, target): pytest.fail('unsafe archive was extracted')
    monkeypatch.setitem(sys.modules, 'py7zr', SimpleNamespace(SevenZipFile=lambda _: Packed()))
    with pytest.raises(ValueError, match='Unsafe archive entry'):
        installer.extract(tmp_path / 'qtbase.7z', tmp_path / 'sdk', installer.qt_version())


def test_support_dll_is_installed_in_bin(tmp_path, monkeypatch):
    destinations = []
    class Packed:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def getnames(self): return ['d3dcompiler_47.dll']
        def extractall(self, target): destinations.append(target)
    monkeypatch.setitem(sys.modules, 'py7zr', SimpleNamespace(SevenZipFile=lambda _: Packed()))
    installer.extract(tmp_path / 'd3dcompiler_47-x64.7z', tmp_path / 'sdk', installer.qt_version())
    assert destinations == [tmp_path / 'sdk/bin']
