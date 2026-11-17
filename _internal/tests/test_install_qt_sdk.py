"""Repository selection and integrity checks must fail before extraction."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
from types import SimpleNamespace
import urllib.error

import pytest

TOOLS = Path(__file__).resolve().parents[1] / 'desktop_qt/tools'
sys.path.insert(0, str(TOOLS))
spec = importlib.util.spec_from_file_location('tested_install_qt_sdk', TOOLS / 'install_qt_sdk.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)
sdk = sys.modules['qt_sdk']


def test_plan_selects_complete_base_and_requested_addons():
    version = installer.qt_version()
    stem = 'qt.qt6.' + version.replace('.', '')
    xml = ('<Updates><PackageUpdate><Name>' + stem + '.win64_msvc2022_64</Name><Version>' + version + '-0-build</Version>'
           '<DownloadableArchives>qtbase.7z, qttools.7z, qtsvg.7z</DownloadableArchives></PackageUpdate>'
           '<PackageUpdate><Name>' + stem + '.addons.qtmultimedia.win64_msvc2022_64</Name><Version>' + version + '-0-build</Version>'
           '<DownloadableArchives>qtmultimedia.7z</DownloadableArchives></PackageUpdate></Updates>')
    plan = installer.archive_plan(xml.encode(), version, installer.package_names(version, ['qtmultimedia']))
    assert [row['archive'] for row in plan] == ['qtbase.7z', 'qttools.7z', 'qtsvg.7z', 'qtmultimedia.7z']
    assert all(row['relative_url'].endswith(version + '-0-build' + row['archive']) for row in plan)
    with pytest.raises(ValueError, match='not in the repository'):
        installer.archive_plan(xml.encode(), version, installer.package_names(version, ['qtimageformats']))


def test_default_install_includes_every_module_the_app_needs():
    names = installer.package_names(installer.qt_version(), installer.REQUIRED_ADDONS)
    assert any(name.endswith('.addons.qtimageformats.win64_msvc2022_64') for name in names)
    assert {'qtmultimedia', 'qttasktree', 'qtimageformats'} <= set(installer.REQUIRED_ADDONS)
    assert set(installer.REQUIRED_ADDONS) == set(sdk.REQUIRED_MODULE_FILES)


def test_repository_pins_cover_the_pinned_version_with_sha256_only():
    pins = installer.load_pins()
    version = installer.qt_version()
    names = installer.package_names(version, installer.REQUIRED_ADDONS)
    assert set(names) <= set(pins['packages'])
    for name in names:
        package = pins['packages'][name]
        assert package['version'].startswith(version + '-')
        assert package['archives'] and all(installer.SHA256.fullmatch(pin['sha256']) and pin['bytes'] > 0
                                           for pin in package['archives'].values())


def pinned_plan(archives=('qtbase.7z',), version='6.0.0-0-build'):
    plan = [dict(package='pkg', version=version, archive=name, relative_url=f'pkg/{version}{name}') for name in archives]
    pins = {'packages': {'pkg': {'version': '6.0.0-0-build',
                                 'archives': {'qtbase.7z': {'sha256': hashlib.sha256(b'correct').hexdigest(), 'bytes': 7}}}}}
    return plan, pins


def test_pins_must_match_the_repository_listing():
    plan, pins = pinned_plan()
    row = installer.apply_pins(plan, pins)[0]
    assert row['algorithm'] == 'sha256' and row['checksum'] == hashlib.sha256(b'correct').hexdigest()
    with pytest.raises(ValueError, match='pins are for'):
        installer.apply_pins(*pinned_plan(version='6.0.0-1-other'))
    with pytest.raises(ValueError, match='differ from the pins'):
        installer.apply_pins(*pinned_plan(archives=('qtbase.7z', 'extra.7z')))
    plan, pins = pinned_plan()
    pins['packages'].clear()
    with pytest.raises(ValueError, match='No SHA-256 pins'):
        installer.apply_pins(plan, pins)


def test_pins_file_rejects_anything_but_sha256(tmp_path):
    path = tmp_path / 'pins.json'
    path.write_text(json.dumps({'packages': {'pkg': {'version': 'v', 'archives': {
        'qtbase.7z': {'sha256': hashlib.sha1(b'x').hexdigest(), 'bytes': 1}}}}}), encoding='utf-8')
    with pytest.raises(ValueError, match='SHA-256'):
        installer.load_pins(path)


def test_checksum_mismatch_never_publishes_archive(tmp_path, monkeypatch):
    def fetch(url, path):
        assert not url.endswith(('.sha256', '.sha1')), 'the server checksum must not be consulted'
        path.write_bytes(b'wrong')
    monkeypatch.setattr(installer, 'fetch', fetch)
    plan, pins = pinned_plan()
    row = installer.apply_pins(plan, pins)[0]
    with pytest.raises(ValueError, match='Checksum mismatch'):
        installer.verified_archive('https://example.invalid/', row, tmp_path)
    assert not (tmp_path / 'qtbase.7z').exists()
    assert not (tmp_path / 'qtbase.7z.part').exists()


def test_unpinned_row_is_refused_before_download(tmp_path, monkeypatch):
    monkeypatch.setattr(installer, 'fetch', lambda url, path: pytest.fail('downloaded without a pin'))
    with pytest.raises(ValueError, match='No pinned SHA-256'):
        installer.verified_archive('https://example.invalid/', dict(archive='qtbase.7z', relative_url='qtbase.7z'), tmp_path)


def test_cached_archive_is_rechecked_against_the_pin(tmp_path, monkeypatch):
    calls = []
    def fetch(url, path):
        calls.append(url)
        path.write_bytes(b'correct')
    monkeypatch.setattr(installer, 'fetch', fetch)
    (tmp_path / 'qtbase.7z').write_bytes(b'corrupt')
    plan, pins = pinned_plan()
    row = installer.apply_pins(plan, pins)[0]
    archive = installer.verified_archive('https://example.invalid/', row, tmp_path)
    assert archive.read_bytes() == b'correct' and calls == ['https://example.invalid/pkg/6.0.0-0-buildqtbase.7z']
    calls.clear()
    installer.verified_archive('https://example.invalid/', row, tmp_path)
    assert calls == []


def test_record_pins_refuses_sha1_only_archives(tmp_path, monkeypatch):
    def fetch(url, path):
        if url.endswith('.sha256'):
            raise urllib.error.HTTPError(url, 404, 'not found', {}, None)
        path.write_bytes(b'correct')
    monkeypatch.setattr(installer, 'fetch', fetch)
    plan, _ = pinned_plan()
    with pytest.raises(ValueError, match='SHA-1 is not accepted'):
        installer.record_pins('https://example.invalid/', plan, tmp_path, tmp_path / 'pins.json')
    assert not (tmp_path / 'pins.json').exists()


def test_record_pins_writes_the_verified_sha256(tmp_path, monkeypatch):
    def fetch(url, path):
        if url.endswith('.sha256'):
            path.write_text(hashlib.sha256(b'correct').hexdigest() + '  qtbase.7z', encoding='ascii')
        else:
            path.write_bytes(b'correct')
    monkeypatch.setattr(installer, 'fetch', fetch)
    plan, _ = pinned_plan()
    pins = installer.record_pins('https://example.invalid/', plan, tmp_path, tmp_path / 'pins.json')
    assert installer.load_pins(tmp_path / 'pins.json') == pins
    assert pins['packages']['pkg']['archives']['qtbase.7z'] == {'sha256': hashlib.sha256(b'correct').hexdigest(), 'bytes': 7}


def test_py7zr_is_pinned_with_hashes_and_checked(monkeypatch):
    text = installer.REQUIREMENTS_FILE.read_text(encoding='utf-8')
    rows = [line for line in text.splitlines() if line and not line.startswith('#')]
    assert rows and all(re.fullmatch(r'[A-Za-z0-9_.-]+==[0-9.]+ --hash=sha256:[0-9a-f]{64}', row) for row in rows)
    wanted = installer.pinned_py7zr_version()
    monkeypatch.setattr(installer.importlib.metadata, 'version', lambda name: wanted)
    installer.check_py7zr()
    monkeypatch.setattr(installer.importlib.metadata, 'version', lambda name: '0.0.1')
    with pytest.raises(ValueError, match='required'):
        installer.check_py7zr()


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


def test_pkgconfig_prefix_is_read_from_the_file_not_assumed(tmp_path):
    root = tmp_path / 'sdk'
    (root / 'lib/pkgconfig').mkdir(parents=True)
    build = 'Z:/build-host/qt-install'
    pc = root / 'lib/pkgconfig/Qt6Core.pc'
    pc.write_text(f'prefix={build}\nlibdir={build}/lib\nincludedir=${{prefix}}/include\n', encoding='utf-8')
    plain = root / 'lib/pkgconfig/Other.pc'
    plain.write_text('Name: other\n', encoding='utf-8')
    installer.relocate_pkgconfig(root)
    assert pc.read_text(encoding='utf-8') == (f'prefix={root.as_posix()}\nlibdir={root.as_posix()}/lib\n'
                                              'includedir=${prefix}/include\n')
    assert plain.read_text(encoding='utf-8') == 'Name: other\n'
