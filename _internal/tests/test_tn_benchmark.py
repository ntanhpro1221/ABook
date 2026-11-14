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
    assert report['schema_version'] == 2
    assert all(set(report['overall'][path]) == set(benchmark.STAGES) for path in benchmark.PATHS)
    assert all(set(row['got_phonemes']) == set(benchmark.PATHS) and
               all(len(row['expected_phonemes'][path]) >= 1 for path in benchmark.PATHS)
               for row in report['results'])
    assert all(set(failure) >= {"id", "category", "text", "expected", "got", "path"} for failure in report["failures"])
    assert "| Category |" in (tmp_path / "report.md").read_text(encoding="utf-8")


@pytest.mark.parametrize('path', benchmark.PATHS)
@pytest.mark.parametrize('stage', benchmark.STAGES)
def test_floor_rejects_a_single_lost_case_and_changed_fixture(path, stage):
    baseline = json.loads(benchmark.BASELINE.read_text(encoding="utf-8"))
    report = copy.deepcopy(baseline)
    report["categories"]["cardinal_small"][path][stage]["correct"] -= 1
    with pytest.raises(ValueError, match="below committed floor"):
        benchmark.check_floor(report, baseline)
    report = copy.deepcopy(baseline)
    report["cases_sha256"] = "changed"
    with pytest.raises(ValueError, match="definition changed"):
        benchmark.check_floor(report, baseline)


def test_comparison_preserves_tones_and_cues_but_ignores_word_separators():
    assert benchmark.normalize('LE-vồ năm.') == benchmark.normalize('le vồ năm!')
    assert benchmark.normalize_phonemes('hˈaːj - nˈam.') == benchmark.normalize_phonemes('hˈaːj nˈam!')
    assert benchmark.normalize_phonemes('hˈa2j') != benchmark.normalize_phonemes('hˈaːj')
    assert benchmark.normalize_phonemes('<|emotion_1|>') != benchmark.normalize_phonemes('<|emotion_2|>')
