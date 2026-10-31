"""The packaging gate rejects missing glyphs even after green QtTest totals."""
import importlib.util
from pathlib import Path

import pytest


spec = importlib.util.spec_from_file_location(
    "qt_results", Path(__file__).resolve().parents[1] / "desktop_qt/tools/check_test_results.py")
results = importlib.util.module_from_spec(spec)
spec.loader.exec_module(results)


@pytest.mark.parametrize("log,ok", [
    ("Totals: 10 passed, 0 failed, 0 skipped\n", True),
    ('QWARN : GLYPH_MISSING {"codepoint":"U+2192","source":"qml/HistoryList.qml"}\n'
     "Totals: 10 passed, 0 failed, 0 skipped\n", False),
    ("Totals: 9 passed, 1 failed, 0 skipped\n", False),
    ("FAIL! : crashed\nTotals: 10 passed, 0 failed, 0 skipped\n", False),
    ("test aborted before totals\n", False),
    ("QWARN : file:///D:/x/qml/StudioSettings.qml:139: TypeError: Cannot call method 'join' of undefined\n"
     "Totals: 10 passed, 0 failed, 0 skipped\n", False),
    # A delegate's binding carries a column too.
    ("QWARN : file:///D:/x/qml/LookShortcuts.qml:33:17: TypeError: Cannot read property 'width' of null\n"
     "Totals: 10 passed, 0 failed, 0 skipped\n", False),
    # The same missing field in a typed property: no TypeError, the property silently keeps its old value.
    ("QWARN : file:///D:/x/desktop_qt/qml/RecordMenu.qml:37:13: Unable to assign [undefined] to QString\n"
     "Totals: 10 passed, 0 failed, 0 skipped\n", False),
    ("QWARN : file:///D:/x/desktop_qt/qml/StudioSetupCard.qml:198:17: Unable to assign [undefined] to bool\n"
     "Totals: 10 passed, 0 failed, 0 skipped\n", False),
    ("QWARN : file:///D:/x/desktop_qt/qml/Sidebar.qml:12: ReferenceError: progress is not defined\n"
     "Totals: 10 passed, 0 failed, 0 skipped\n", False),
    # The tests' own QML counts too.
    ("QWARN : file:///D:/x/desktop_qt/tests/width/tst_cast.qml:88: TypeError: Cannot read property 'x' of undefined\n"
     "Totals: 10 passed, 0 failed, 0 skipped\n", False),
    # GlyphAudit saw a JS value on screen (tst_studio2 drew "Máy thấy undefined: ... (NaN chương)" and passed).
    ('QWARN : TEXT_LEAK {"text":"Máy thấy undefined: Tập 1 (NaN chương)","path":"NewVolumes/Prose"}\n'
     "Totals: 10 passed, 0 failed, 0 skipped\n", False),
    # Platform notices are not binding errors.
    ("QWARN : This plugin does not support propagateSizeHints()\n"
     "QWARN : DelegateModel::cancel: index out range 0 0\n"
     "Totals: 10 passed, 0 failed, 0 skipped\n", True),
])
def test_packaging_gate(tmp_path, capsys, log, ok):
    path = tmp_path / "width-test.txt"
    path.write_text(log, encoding="utf-8")
    assert results.check(path) is ok
    output = capsys.readouterr().out
    assert "TEST_TOTALS" in output
    assert f"GLYPH_MISSING {int('GLYPH_MISSING' in log)}" in output
    assert f"TEXT_LEAK {int('TEXT_LEAK' in log)}" in output
    binding = any(kind in log for kind in ("TypeError", "ReferenceError", "Unable to assign"))
    assert f"QML_TYPE_ERROR {int(binding)}" in output
    if "desktop_qt/" in log:
        assert "QML_TYPE_ERROR qml/" in output or "QML_TYPE_ERROR tests/" in output     # path from desktop_qt/ on
    if "GLYPH_MISSING" in log:
        assert "U+2192" in output and "qml/HistoryList.qml" in output
