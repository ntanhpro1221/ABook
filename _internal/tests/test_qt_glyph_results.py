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
])
def test_packaging_gate(tmp_path, capsys, log, ok):
    path = tmp_path / "width-test.txt"
    path.write_text(log, encoding="utf-8")
    assert results.check(path) is ok
    output = capsys.readouterr().out
    assert "TEST_TOTALS" in output
    assert f"GLYPH_MISSING {int('GLYPH_MISSING' in log)}" in output
    if "GLYPH_MISSING" in log:
        assert "U+2192" in output and "qml/HistoryList.qml" in output
