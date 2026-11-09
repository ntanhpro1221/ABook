"""The shared catalog is build input, and the source gate must catch new copy."""
import json
from pathlib import Path

from scripts import gen_ui_strings as gen
from scripts import check_ui_sources as gate
from scripts.ui_copy_source import expand
from scripts import ui_parity as parity
from scripts import ui_parity_qt as qt


def test_generated_strings_match_the_catalog():
    assert not gen.main(['--check'])
    assert len(gen.outputs()) == 5


def test_catalog_uses_numbered_slots_without_gaps():
    data=gen.catalog()
    assert len(data['strings']) > 1000
    for key,value in data['strings'].items():
        assert gen.slots(value) == list(range(len(gen.slots(value)))), key
        assert '\r' not in value, key
    assert set(data['android_resources'].values()) <= data['strings'].keys()


def test_generated_sources_use_lf():
    for path in gen.outputs():
        assert b'\r' not in path.read_bytes(), path


def test_raw_source_build_gate_passes():
    assert not gate.main()


def test_raw_native_detector_catches_new_label(tmp_path):
    path=tmp_path/'Probe.kt'
    path.write_text('fun probe() { BasicText("Chữ cứng mới"); BasicText(text = "Hello world") }',encoding='utf-8')
    old=parity.ROOT
    parity.ROOT=tmp_path
    try:
        scan=parity.Scan()
        parity.kt_scan_file(path,scan,{}, {})
        assert {'Chữ cứng mới','Hello world'} <= {x.text for x in scan.items}
    finally:
        parity.ROOT=old


def test_raw_qt_detector_catches_new_label(tmp_path):
    path=tmp_path/'Probe.qml'
    path.write_text('import QtQuick\nItem { Text { text: "Chữ cứng mới" } }',encoding='utf-8')
    scan=qt.QtScan()
    qt.qml_scan_file(path,scan)
    assert 'Chữ cứng mới' in {x.text for x in scan.items}


def test_resolver_preserves_interpolation_and_key_identity():
    entries=gen.catalog()['strings']
    key=next(k for k,v in entries.items() if v=='Chương {0}')
    assert expand(f'S.{key}(book.chapter)', 'kt') == '"Chương ${book.chapter}"'
    assert expand(f'S.{key}(book.chapter)', 'ts') == '`Chương ${book.chapter}`'


def test_exceptions_are_exact_and_have_review_reasons():
    entries=json.loads(gate.EXCEPTIONS.read_text(encoding='utf-8'))
    assert all(set(x)=={'file','text','reason'} and len(x['reason']) > 20 for x in entries)
    assert len({(x['file'],x['text']) for x in entries}) == len(entries)
