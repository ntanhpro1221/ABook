"""Release reporting stays non-blocking until the lead enables enforcement."""
import sys
from test_design_lint import dl, canvas, column


def test_release_gate_runs_design_lint_in_report_mode(monkeypatch, tmp_path):
    import importlib.util

    spec = importlib.util.spec_from_file_location("gate_under_test", dl.ROOT / "scripts/release_gate.py")
    gate = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, gate)
    spec.loader.exec_module(gate)
    assert any(c.name == "design-lint" and c.parser == "json" for c in gate.checks())
    assert gate.DESIGN_LINT_BLOCKS is False
    im, draw = canvas()
    column(draw, 60, rows=4)                                       # R10 đỏ
    im.save(tmp_path / "x_light.png")
    monkeypatch.setattr(dl, "ANDROID_SHOTS", tmp_path)
    monkeypatch.setattr(dl, "QT_SHOTS", tmp_path / "none")
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    monkeypatch.setitem(sys.modules, "design_lint", dl)
    report = gate.design_lint_report()
    assert report["status"] == "PASS" and report["mode"] == "report" and report["counts"]["r10"] == 1
    assert report["counts"]["red"] == 1 <= report["counts"]["red_cells"]
    monkeypatch.setattr(gate, "DESIGN_LINT_BLOCKS", True)
    blocked = gate.design_lint_report()
    assert blocked["status"] == "FAIL" and "ảnh đỏ" in blocked["detail"]
