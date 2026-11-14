"""Infrastructure checks and zero-tolerance floors for the committed TN corpus."""
import copy
import json

import pytest

from scripts import tn_benchmark as benchmark


def test_fixture_is_original_case_schema_with_balanced_coverage():
    cases = benchmark.load_cases()
    assert len(cases) >= 400
    assert set(case["category"] for case in cases) == set(benchmark.CATEGORIES)


def test_cli_writes_reports_and_meets_each_committed_floor(tmp_path, capsys):
    assert benchmark.main(["--output-dir", str(tmp_path), "--check-baseline", str(benchmark.BASELINE)]) == 0
    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert json.loads(capsys.readouterr().out)["case_count"] == report["case_count"]
    assert set(report["overall"]) == set(benchmark.PATHS)
    assert len(report["results"]) == report["case_count"]
    assert all(set(failure) >= {"id", "category", "text", "expected", "got", "path"} for failure in report["failures"])
    assert "| Category |" in (tmp_path / "report.md").read_text(encoding="utf-8")


def test_floor_rejects_a_single_lost_case_and_changed_fixture():
    baseline = json.loads(benchmark.BASELINE.read_text(encoding="utf-8"))
    report = copy.deepcopy(baseline)
    report["categories"]["cardinal_small"]["studio"]["correct"] -= 1
    with pytest.raises(ValueError, match="below committed floor"):
        benchmark.check_floor(report, baseline)
    report = copy.deepcopy(baseline)
    report["cases_sha256"] = "changed"
    with pytest.raises(ValueError, match="definition changed"):
        benchmark.check_floor(report, baseline)
