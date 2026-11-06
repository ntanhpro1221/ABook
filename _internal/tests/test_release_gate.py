"""Cổng phát hành phải đỏ khi thiếu bằng chứng, kể cả process tự báo exit 0."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("release_gate_tested", ROOT / "scripts/release_gate.py")
gate = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = gate
spec.loader.exec_module(gate)
FIXTURES = Path(__file__).parent / "fixtures/release_gate"


def test_publication_verification_is_not_a_prepublication_manual_row():
    assert "manual-publish" not in {check.name for check in gate.checks()}


def test_parsers_read_captured_outputs():
    assert gate.parse_pytest((FIXTURES / "pytest-passed.txt").read_text(encoding="utf-8"))["passed"] == 11
    assert gate.parse_vitest((FIXTURES / "vitest-a90a.txt").read_text(encoding="utf-8")) == {
        "passed": 1354, "failed": 0, "skipped": 1, "error": 0}


@pytest.mark.parametrize("output,counts", [
    ("1 failed, 12 passed, 2 errors in 1.23s\n", {"failed": 1, "passed": 12, "error": 2}),
    ("== 1 error in 0.1s ==\n", {"error": 1, "passed": 0}),
    ("12 passed in 1s\n1 failed, 12 passed in 2s\n", {"failed": 1, "passed": 12}),
    ("\x1b[32m2 passed, 1 skipped in 0.1s\x1b[0m\n", {"passed": 2, "skipped": 1}),
])
def test_pytest_summary(output, counts):
    found = gate.parse_pytest(output)
    assert all(found[key] == value for key, value in counts.items())


@pytest.mark.parametrize("output", ["", "........ [100%]\n", "no tests ran in 0.01s", "collected 0 items\n1 passed in 1s"])
def test_pytest_requires_summary_and_collection(output):
    with pytest.raises(ValueError):
        gate.parse_pytest(output)


@pytest.mark.parametrize("output", ["", "Test Files 1 passed (1)", "Tests 2 passed (3)", "Tests 1 passed (1)\nTests 1 passed (1)"])
def test_vitest_requires_real_test_summary(output):
    with pytest.raises(ValueError):
        gate.parse_vitest(output)


def fake_check(parser="pytest"):
    return gate.Check("suite", ["fake"], parser=parser, timeout=1)


@pytest.mark.parametrize("execution", [
    gate.Execution(0, "1 failed, 12 passed in 1s"),
    gate.Execution(0, ""),
    gate.Execution(0, "no tests ran in 0.01s"),
    gate.Execution(0, "1 error in 0.1s"),
    gate.Execution(7, "12 passed in 1s"),
    gate.Execution(-1, "", True),
    gate.Execution(0, "12 passed, 1 xpassed in 1s"),
])
def test_fake_runner_never_turns_missing_or_bad_evidence_green(tmp_path, execution):
    rows = gate.run_gate([fake_check()], tmp_path, lambda *_: execution)
    assert rows[0]["result"] == "FAIL"
    assert gate.exit_code(rows) == 1
    if execution.timed_out:
        assert "timeout" in rows[0]["detail"]
    if "1 failed" in execution.output:
        assert rows[0]["counts"]["failed"] == 1


def test_vitest_failure_even_with_zero_exit(tmp_path):
    rows = gate.run_gate([fake_check("vitest")], tmp_path,
                         lambda *_: gate.Execution(0, "Tests 1 failed | 2 passed (3)"))
    assert rows[0]["result"] == "FAIL" and rows[0]["counts"]["failed"] == 1


def test_all_pass_returns_exit_zero_and_persists_counts(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    monkeypatch.setattr(gate, "version", lambda: "9.9.9")
    monkeypatch.setattr(gate, "git", lambda *args: "head" if args[0] == "rev-parse" else "")
    assert gate.main([], runner=lambda *_: gate.Execution(0, "12 passed in 1.0s"), definitions=[fake_check()]) == 0
    reports = list((tmp_path / "runtime/release_gate").glob("*.json"))
    assert len(reports) == 1
    report = json.loads(reports[0].read_text(encoding="utf-8"))
    assert report["scope"] == "full" and report["exit_code"] == 0
    assert report["rows"][0]["counts"]["passed"] == 12


def test_manual_and_unavailable_are_blocking(tmp_path):
    manual = gate.Check("eyes", manual="người duyệt ảnh")
    def missing(*_):
        raise FileNotFoundError("thiếu công cụ")
    rows = gate.run_gate([manual, fake_check()], tmp_path, missing)
    assert [r["result"] for r in rows] == ["MANUAL", "FAIL"]
    assert gate.exit_code(rows) == 1


def test_confirmations_are_explicit_and_bound_to_this_run(tmp_path):
    manual = gate.Check("manual-ui", manual="review images")
    confirmation = gate.parse_confirmations(["manual-ui=Reviewed light and dark images"], [manual], "commit-A", "tree-A")
    rows = gate.run_gate([manual], tmp_path / "signed", confirmations=confirmation)
    assert rows[0]["result"] == "CONFIRMED" and gate.exit_code(rows) == 0
    assert rows[0]["confirmation"]["head"] == "commit-A"
    assert rows[0]["confirmation"]["tree_sha256"] == "tree-A"
    # A later invocation never reads the earlier JSON or sign-off.
    assert gate.run_gate([manual], tmp_path / "next")[0]["result"] == "MANUAL"


@pytest.mark.parametrize("values", [["manual-ui"], ["manual-ui= "], ["suite=ok"],
                                    ["manual-ui=ok", "manual-ui=again"]])
def test_invalid_confirmation_is_rejected(values):
    with pytest.raises(ValueError):
        gate.parse_confirmations(values, [gate.Check("manual-ui", manual="review")], "A", "T")


def test_source_change_during_gate_invalidates_confirmation(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    monkeypatch.setattr(gate, "version", lambda: "9.9.9")
    monkeypatch.setattr(gate, "git", lambda *args: "A" if args[0] == "rev-parse" else "")
    fingerprints = iter(["before", "after"])
    monkeypatch.setattr(gate, "tree_fingerprint", lambda: next(fingerprints))
    manual = gate.Check("manual-ui", manual="review")
    assert gate.main(["--confirm", "manual-ui=reviewed"], definitions=[manual]) == 1
    report = json.loads(next((tmp_path / "runtime/release_gate").glob("*.json")).read_text(encoding="utf-8"))
    assert report["rows"][0]["result"] == "MANUAL"
    assert "invalidated" in report["rows"][0]["detail"]


def test_missing_ui_dependencies_fail_once_and_never_use_shared_junction(tmp_path):
    calls = []
    def missing(directory, runner):
        calls.append(directory)
        raise ValueError("UI dependencies: missing vitest")
    def unexpected(*_):
        pytest.fail("must not run against incomplete shared dependencies")
    checks = [gate.Check("typecheck", ["node"]), gate.Check("vitest", ["node"])]
    rows = gate.run_gate(checks, tmp_path, unexpected, prepare=missing)
    assert len(calls) == 1
    assert all(row["result"] == "FAIL" and "missing vitest" in row["detail"] for row in rows)


def test_private_dependency_check_rejects_missing_and_wrong_locked_versions(tmp_path):
    ui = tmp_path / "ui"
    ui.mkdir()
    (ui / "package.json").write_text(json.dumps({"devDependencies": {"vitest": "^5"}}), encoding="utf-8")
    (ui / "package-lock.json").write_text(json.dumps({"packages": {"node_modules/vitest": {"version": "5.0.5"}}}), encoding="utf-8")
    assert "vitest" in gate.dependency_problems(ui, tmp_path)[0]
    package = tmp_path / "node_modules/vitest/package.json"
    package.parent.mkdir(parents=True)
    package.write_text('{"version":"4.0.0"}', encoding="utf-8")
    assert "lock requires 5.0.5" in gate.dependency_problems(ui, tmp_path)[0]
    package.write_text('{"version":"5.0.5"}', encoding="utf-8")
    assert gate.dependency_problems(ui, tmp_path) == []


def test_failed_dependency_does_not_claim_its_checks_ran(tmp_path):
    definitions = [fake_check(), gate.Check("dependent", ["fake"], requires=("suite",))]
    rows = gate.run_gate(definitions, tmp_path, lambda *_: gate.Execution(0, ""))
    assert rows[1]["result"] == "FAIL" and "điều kiện trước" in rows[1]["detail"]


def test_only_includes_prerequisites_and_unknown_names_fail():
    definitions = [fake_check(), gate.Check("dependent", requires=("suite",))]
    assert [c.name for c in gate.select_checks(definitions, ["dependent"])] == ["suite", "dependent"]
    with pytest.raises(ValueError):
        gate.select_checks(definitions, ["typo"])


def test_injected_failure_is_not_a_green_run(tmp_path):
    rows = gate.run_gate([fake_check()], tmp_path, lambda *_: gate.Execution(0, "12 passed in 1s"), "suite")
    assert gate.exit_code(rows) == 1 and "cấy" in rows[0]["detail"]


def write_xml(directory, body='<testcase name="good"/><testcase name="bad"><failure/></testcase>', tests=2, failures=1):
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "TEST-example.xml"
    path.write_text(f'<testsuite tests="{tests}" failures="{failures}" errors="0" skipped="0">{body}</testsuite>', encoding="utf-8")
    return path


def test_gradle_xml_counts_actual_testcases(tmp_path):
    write_xml(tmp_path)
    assert gate.parse_gradle(tmp_path) == {"passed": 1, "failed": 1, "error": 0, "skipped": 0, "suites": 1}


def test_gradle_parser_reads_captured_junit_xml():
    assert gate.parse_gradle(FIXTURES / "gradle") == {"passed": 1, "failed": 0, "error": 0, "skipped": 0, "suites": 1}


def test_gradle_refuses_missing_empty_malformed_or_inconsistent_xml(tmp_path):
    with pytest.raises(ValueError):
        gate.parse_gradle(tmp_path)
    path = write_xml(tmp_path, "", 2, 0)
    with pytest.raises(ValueError):
        gate.parse_gradle(tmp_path)
    path.write_text("<testsuite", encoding="utf-8")
    with pytest.raises(Exception):
        gate.parse_gradle(tmp_path)


def test_process_timeout_is_real_and_bounded(tmp_path):
    result = gate.run_process(gate.py("-c", "import time; time.sleep(10)"), tmp_path, .1)
    assert result.timed_out and result.returncode != 0


def test_qt_gui_counts_come_from_the_new_file_even_with_empty_stdout(tmp_path):
    log = tmp_path / "suite.txt"
    def runner(command, cwd, timeout):
        assert command[-2] == "-o" and command[-1] == str(log) + ",txt"
        log.write_text("Totals: 3 passed, 0 failed, 0 skipped\n", encoding="utf-8")
        return gate.Execution(0, "")
    result = gate.run_qt_suite(tmp_path / "suite.exe", tmp_path, log, runner)
    assert "3 passed" in result.output


def test_qt_never_reuses_a_stale_log_or_claims_a_missing_log_passed(tmp_path):
    log = tmp_path / "suite.txt"
    with pytest.raises(ValueError, match="không tạo log"):
        gate.run_qt_suite(tmp_path / "suite.exe", tmp_path, log, lambda *_: gate.Execution(0, ""))
    log.write_text("Totals: 3 passed, 0 failed, 0 skipped\n", encoding="utf-8")
    with pytest.raises(ValueError, match="log cũ"):
        gate.run_qt_suite(tmp_path / "suite.exe", tmp_path, log, lambda *_: gate.Execution(0, ""))


def test_source_checks_detect_crlf_and_private_data_failures(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "REPO", tmp_path)
    bad = tmp_path / "broken.cmd"
    bad.write_bytes(b"@echo off\n")
    monkeypatch.setattr(gate, "tracked_and_new", lambda: [bad])
    with pytest.raises(ValueError, match="CRLF"):
        gate.worker("batch-crlf")
    bad.write_bytes(b"@echo off\r\n")
    assert gate.worker("batch-crlf")["counts"]["files"] == 1
    audio = tmp_path / "private.wav"
    audio.write_bytes(b"RIFF")
    monkeypatch.setattr(gate, "changed_files", lambda: [audio])
    with pytest.raises(ValueError, match="file riêng tư"):
        gate.worker("diff-safety")


def test_term_detector_only_exempts_its_own_literal_declaration(tmp_path, monkeypatch):
    source = tmp_path / "source.py"
    source.write_text("# " + gate.FORBIDDEN_TERMS[0], encoding="utf-8")
    monkeypatch.setattr(gate, "REPO", tmp_path)
    monkeypatch.setattr(gate, "changed_files", lambda: [source])
    monkeypatch.setattr(gate, "source_lines", lambda path: path.read_text(encoding="utf-8").splitlines())
    with pytest.raises(ValueError, match="cần duyệt"):
        gate.worker("forbidden-terms")


def test_vitest_unhandled_errors_block_even_when_all_tests_pass(tmp_path):
    rows = gate.run_gate([fake_check("vitest")], tmp_path,
                         lambda *_: gate.Execution(0, "Tests 12 passed (12)\nErrors 1 error"))
    assert rows[0]["result"] == "FAIL" and rows[0]["counts"]["error"] == 1


def test_json_failure_preserves_test_counts(tmp_path):
    report = json.dumps({"status": "FAIL", "counts": {"passed": 9, "failed": 7}, "detail": "test đỏ"})
    rows = gate.run_gate([fake_check("json")], tmp_path, lambda *_: gate.Execution(0, report))
    assert rows[0]["result"] == "FAIL" and rows[0]["counts"]["failed"] == 7


def test_version_mismatch_and_android_code_drift_are_blocking(tmp_path, monkeypatch):
    for relative in ("pyproject.toml", "uv.lock", "ui/package.json", "ui/package-lock.json",
                     "mobile/android/app/build.gradle", "desktop_qt/CMakeLists.txt"):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    assert gate.worker("versions")["version"] == gate.version()
    package = tmp_path / "ui/package.json"
    original = package.read_text(encoding="utf-8")
    package.write_text(original.replace(gate.version(), "99.99.99"), encoding="utf-8")
    with pytest.raises(ValueError, match="bị lệch"):
        gate.worker("versions")
    package.write_text(original, encoding="utf-8")
    gradle = tmp_path / "mobile/android/app/build.gradle"
    gradle.write_text(gate.re.sub(r"versionCode \d+", "versionCode 0", gradle.read_text(encoding="utf-8")), encoding="utf-8")
    with pytest.raises(ValueError, match="versionCode"):
        gate.worker("versions")


def test_negative_control_cannot_pass_on_browser_start_failure(tmp_path, monkeypatch):
    artifact = tmp_path / "tap.json"
    artifact.write_text(json.dumps({"status": "FAIL", "results": [], "error": "missing browser"}), encoding="utf-8")
    check = gate.Check("tap-negative", parser="tap-negative")
    with pytest.raises(ValueError, match="scenarios"):
        gate.validate_report(check, gate.Execution(1, ""), artifact)


def test_publish_stops_before_any_external_mutation_on_gate_failure(tmp_path, monkeypatch):
    release = gate.load_module(ROOT / "scripts/release.py", "release_gate_publish_test")
    calls = []
    def fail(command, *args, **kwargs):
        calls.append(command)
        raise subprocess.CalledProcessError(1, command)
    monkeypatch.setattr(release, "_run", fail)
    monkeypatch.setattr(release, "release_notes", lambda *a, **k: "notes")
    with pytest.raises(subprocess.CalledProcessError):
        release.publish("9.9.9", "HEAD", tmp_path)
    assert len(calls) == 1 and calls[0][-1].endswith("release_gate.py")
    assert not (tmp_path / "notes.md").exists()


def test_publish_without_a_changelog_section_stops_before_the_gate(tmp_path, monkeypatch):
    release = gate.load_module(ROOT / "scripts/release.py", "release_gate_publish_changelog_test")
    calls = []
    monkeypatch.setattr(release, "_run", lambda command, *a, **k: calls.append(command))
    with pytest.raises(AssertionError, match="CHANGELOG"):
        release.publish("9.9.9", "HEAD", tmp_path)
    assert calls == []


def test_changelog_accepts_unreleased_entries_or_the_bumped_version_section(tmp_path, monkeypatch):
    docs = tmp_path / "docs"
    docs.mkdir()
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    monkeypatch.setattr(gate, "version", lambda: "9.9.9")
    log = docs / "CHANGELOG.md"
    log.write_text("# Log\n\n## [Chưa phát hành]\n\n- Mới\n\n## [9.9.8] - 2026-01-01\n\n- Cũ\n", encoding="utf-8")
    assert gate.worker("changelog")["counts"] == {"entries": 1, "released": 0}
    log.write_text("# Log\n\n## [Chưa phát hành]\n\n## [9.9.9] - 2026-01-02\n\n- Mới\n- Hai\n\n## [9.9.8]\n\n- Cũ\n", encoding="utf-8")
    assert gate.worker("changelog")["counts"] == {"entries": 2, "released": 1}
    log.write_text("# Log\n\n## [Chưa phát hành]\n\n## [9.9.8]\n\n- Cũ\n", encoding="utf-8")
    with pytest.raises(ValueError, match="CHANGELOG"):
        gate.worker("changelog")
