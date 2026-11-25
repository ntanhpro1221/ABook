"""Cổng phát hành phải đỏ khi thiếu bằng chứng, kể cả process tự báo exit 0."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
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
REAL_BATTERY_PROBE = gate.battery_probe


@pytest.fixture(autouse=True)
def mains_power(monkeypatch):
    """Không bài thử nào được phụ thuộc pin thật của máy chạy test hay ngủ thật."""
    monkeypatch.delenv(gate.ALLOW_BATTERY_ENV, raising=False)
    monkeypatch.setattr(gate, "battery_probe", lambda: False)
    monkeypatch.setattr(gate, "power_sleep", lambda seconds: pytest.fail("không được chờ khi có sạc"))


def power_sequence(monkeypatch, states):
    """Đầu dò giả trả lần lượt các trạng thái, phần tử cuối lặp mãi; ghi lại các lần chờ."""
    states, sleeps = list(states), []
    monkeypatch.setattr(gate, "battery_probe", lambda: states.pop(0) if len(states) > 1 else states[0])
    monkeypatch.setattr(gate, "power_sleep", sleeps.append)
    return sleeps


def test_check_waits_for_mains_before_starting_and_waiting_is_not_its_runtime(tmp_path, monkeypatch, capsys):
    # trước bước: pin, pin, có sạc; trong bước (đầu + cuối): có sạc
    sleeps = power_sequence(monkeypatch, [True, True, False])
    calls = []
    def runner(command, cwd, timeout):
        calls.append(timeout)
        return gate.Execution(0, "3 passed in 1s")
    rows = gate.run_gate([fake_check()], tmp_path, runner)
    assert rows[0]["result"] == "PASS" and calls == [1]
    assert sleeps == [gate.POWER_POLL_SECONDS, gate.POWER_POLL_SECONDS]
    assert "power_wait_seconds" in rows[0] and "evidence" not in rows[0]
    err = capsys.readouterr().err
    assert err.count("chờ cắm sạc") == 1 and err.count("đã có sạc") == 1


def test_manual_rows_never_wait_for_mains(tmp_path, monkeypatch):
    sleeps = power_sequence(monkeypatch, [True])
    rows = gate.run_gate([gate.Check("eyes", manual="người duyệt")], tmp_path)
    assert rows[0]["result"] == "MANUAL" and sleeps == []


def test_allow_battery_env_disables_wait_and_rerun(tmp_path, monkeypatch):
    sleeps = power_sequence(monkeypatch, [True])
    monkeypatch.setenv(gate.ALLOW_BATTERY_ENV, "1")
    calls = []
    def runner(*_):
        calls.append(1)
        return gate.Execution(-1, "", True)
    rows = gate.run_gate([fake_check()], tmp_path, runner)
    assert rows[0]["result"] == "FAIL" and "timeout" in rows[0]["detail"]
    assert sleeps == [] and len(calls) == 1


def test_timeout_on_battery_reruns_once_after_mains_returns(tmp_path, monkeypatch):
    # lần 1: đầu có sạc, cuối chạy pin; chờ: pin, có sạc; lần 2: có sạc suốt
    sleeps = power_sequence(monkeypatch, [False, False, True, True, False, False, False])
    outputs = [gate.Execution(-1, "half", True), gate.Execution(0, "5 passed in 1s")]
    rows = gate.run_gate([fake_check()], tmp_path, lambda *_: outputs.pop(0))
    row = rows[0]
    assert row["result"] == "PASS" and row["counts"]["passed"] == 5 and not outputs
    first, second = row["evidence"]["power_attempts"]
    assert first["timed_out"] and first["on_battery"]
    assert Path(first["log"]).read_text(encoding="utf-8") == "half"
    assert not second["timed_out"] and not second["on_battery"]
    assert sleeps == [gate.POWER_POLL_SECONDS]


def test_worker_reported_timeout_on_battery_also_reruns(tmp_path, monkeypatch):
    # Gradle 840 s trong worker 900 s: worker báo timed_out trong JSON, bước ngoài không timeout.
    power_sequence(monkeypatch, [False, True, False])
    timed = json.dumps({"status": "FAIL", "timed_out": True, "counts": {}, "detail": "Gradle: timeout sau 840s"})
    passed = json.dumps({"status": "PASS", "timed_out": False, "counts": {"passed": 4}})
    outputs = [gate.Execution(1, "gradle log\n" + timed), gate.Execution(0, passed)]
    rows = gate.run_gate([fake_check("json")], tmp_path, lambda *_: outputs.pop(0))
    assert rows[0]["result"] == "PASS" and rows[0]["counts"] == {"passed": 4}
    assert [a["timed_out"] for a in rows[0]["evidence"]["power_attempts"]] == [True, False]


def test_second_timeout_fails_and_reruns_only_once(tmp_path, monkeypatch):
    power_sequence(monkeypatch, [False, True, False, True, False])
    calls = []
    def runner(*_):
        calls.append(1)
        return gate.Execution(-1, "", True)
    rows = gate.run_gate([fake_check()], tmp_path, runner)
    assert rows[0]["result"] == "FAIL" and "timeout" in rows[0]["detail"] and len(calls) == 2
    assert len(rows[0]["evidence"]["power_attempts"]) == 2


@pytest.mark.parametrize("execution", [gate.Execution(-1, "", True), gate.Execution(1, "1 failed, 2 passed in 1s")])
def test_no_rerun_without_battery_or_without_timeout(tmp_path, monkeypatch, execution):
    # chạy pin suốt lần chạy nhưng không timeout, hay timeout mà luôn có sạc: không chạy lại
    timed = execution.timed_out
    power_sequence(monkeypatch, [False] if timed else [False, True])
    calls = []
    def runner(*_):
        calls.append(1)
        return execution
    rows = gate.run_gate([fake_check()], tmp_path, runner)
    assert rows[0]["result"] == "FAIL" and len(calls) == 1
    if timed:  # luôn có sạc: không có gì về pin để ghi
        assert "evidence" not in rows[0]
    else:  # có lúc chạy pin: báo cáo phải ghi lại dù không chạy lại
        assert rows[0]["evidence"]["power_attempts"] == [
            {"attempt": 1, "returncode": 1, "timed_out": False, "on_battery": True,
             "seconds": rows[0]["evidence"]["power_attempts"][0]["seconds"]}]


def fake_clock(monkeypatch, states):
    """Như power_sequence nhưng mỗi lần chờ đẩy đồng hồ giả của gate lên đúng số giây chờ (không ngủ thật)."""
    now = [1000.0]
    sleeps = power_sequence(monkeypatch, states)
    def sleep(seconds):
        sleeps.append(seconds)
        now[0] += seconds
    monkeypatch.setattr(gate, "power_sleep", sleep)
    monkeypatch.setattr(gate, "clock", lambda: now[0])
    return sleeps, now


def test_battery_wait_is_bounded_and_remaining_checks_are_not_run(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv(gate.BATTERY_WAIT_MAX_ENV, "90")
    sleeps, _ = fake_clock(monkeypatch, [True])
    def runner(*_):
        pytest.fail("không được chạy bước nào khi chưa từng có sạc")
    checks = [fake_check(), gate.Check("eyes", manual="người duyệt"), gate.Check("later", ["fake"], timeout=1)]
    rows = gate.run_gate(checks, tmp_path, runner)
    assert [r["result"] for r in rows] == ["NOT_RUN", "MANUAL", "NOT_RUN"]
    assert "chờ sạc quá" in rows[0]["detail"] and "chờ sạc quá" in rows[2]["detail"]
    assert rows[0]["power_wait_seconds"] == 90 and rows[0]["seconds"] == 0
    assert sum(sleeps) == 90 and gate.exit_code(rows) == 1
    state = json.loads((tmp_path / gate.POWER_WAIT_FILE).read_text(encoding="utf-8"))
    assert state["state"] == "gave_up" and state["check"] == "suite" and state["waited_seconds"] == 90
    assert len(state["since_local"]) == 5 and state["limit_seconds"] == 90
    err = capsys.readouterr().err
    assert "chờ cắm sạc từ " + state["since_local"] in err and "các bước còn lại không chạy" in err


def test_waiting_state_is_on_disk_while_waiting_and_cleared_to_mains(tmp_path, monkeypatch):
    sleeps, now = fake_clock(monkeypatch, [True, True, False])
    seen = []
    def sleep(seconds):
        seen.append(json.loads((tmp_path / gate.POWER_WAIT_FILE).read_text(encoding="utf-8")))
        sleeps.append(seconds)
        now[0] += seconds
    monkeypatch.setattr(gate, "power_sleep", sleep)
    rows = gate.run_gate([fake_check()], tmp_path, lambda *_: gate.Execution(0, "3 passed in 1s"))
    assert rows[0]["result"] == "PASS" and rows[0]["power_wait_seconds"] == 60 and rows[0]["seconds"] == 0
    assert [s["state"] for s in seen] == ["waiting", "waiting"] and [s["waited_seconds"] for s in seen] == [0, 30]
    assert seen[0]["limit_seconds"] == gate.BATTERY_WAIT_MAX_DEFAULT == 12 * 3600
    final = json.loads((tmp_path / gate.POWER_WAIT_FILE).read_text(encoding="utf-8"))
    assert final["state"] == "mains" and final["waited_seconds"] == 60


def test_rerun_wait_over_limit_fails_the_timed_out_check_and_skips_the_rest(tmp_path, monkeypatch):
    # lần 1: đầu có sạc, cuối chạy pin, timeout; chờ để chạy lại: pin mãi
    monkeypatch.setenv(gate.BATTERY_WAIT_MAX_ENV, "1m")
    fake_clock(monkeypatch, [False, False, True])
    calls = []
    def runner(*_):
        calls.append(1)
        return gate.Execution(-1, "half", True)
    rows = gate.run_gate([fake_check(), gate.Check("later", ["fake"], timeout=1)], tmp_path, runner)
    assert [r["result"] for r in rows] == ["FAIL", "NOT_RUN"] and len(calls) == 1
    assert "không chạy lại" in rows[0]["detail"] and rows[0]["power_wait_seconds"] == 60
    (first,) = rows[0]["evidence"]["power_attempts"]
    assert first["timed_out"] and first["on_battery"] and Path(first["log"]).is_file()


@pytest.mark.parametrize("raw,seconds", [(None, 12 * 3600), ("", 12 * 3600), ("90", 90), ("2h", 7200),
                                         ("30m", 1800), ("45s", 45), ("0", 0), ("nope", 12 * 3600), ("-5", 12 * 3600)])
def test_battery_wait_max_env(monkeypatch, raw, seconds):
    if raw is None:
        monkeypatch.delenv(gate.BATTERY_WAIT_MAX_ENV, raising=False)
    else:
        monkeypatch.setenv(gate.BATTERY_WAIT_MAX_ENV, raw)
    assert gate.battery_wait_max() == seconds


def test_worker_reported_timeout_sets_row_timed_out_without_rerun(tmp_path):
    timed = json.dumps({"status": "FAIL", "timed_out": True, "counts": {}, "detail": "Gradle: timeout sau 840s"})
    rows = gate.run_gate([fake_check("json")], tmp_path, lambda *_: gate.Execution(1, "gradle log\n" + timed))
    assert rows[0]["result"] == "FAIL" and rows[0]["timed_out"] is True and "evidence" in rows[0]
    assert "power_attempts" not in rows[0]["evidence"]  # luôn có sạc: không chạy lại


def test_check_that_passed_partly_on_battery_records_it(tmp_path, monkeypatch):
    power_sequence(monkeypatch, [False, False, True, False])
    rows = gate.run_gate([fake_check()], tmp_path, lambda *_: gate.Execution(0, "3 passed in 1s"))
    assert rows[0]["result"] == "PASS"
    (attempt,) = rows[0]["evidence"]["power_attempts"]
    assert attempt["on_battery"] and not attempt["timed_out"]


def test_waiting_never_counts_as_check_seconds_when_the_runner_raises(tmp_path, monkeypatch):
    fake_clock(monkeypatch, [True, True, False])
    def runner(*_):
        raise FileNotFoundError("java")
    rows = gate.run_gate([fake_check()], tmp_path, runner)
    assert rows[0]["result"] == "FAIL" and "java" in rows[0]["detail"]
    assert rows[0]["power_wait_seconds"] == 60 and rows[0]["seconds"] == 0


def test_ui_dependency_install_waits_for_mains_and_reruns_once(tmp_path, monkeypatch):
    # npm ci lần 1: đầu có sạc, cuối chạy pin, timeout; chờ: pin, có sạc; lần 2 + typecheck: có sạc
    sleeps, _ = fake_clock(monkeypatch, [False, False, True, True, False, False, False])
    npm = [gate.Execution(-1, "npm half", True), gate.Execution(0, "added 1 package")]
    def prepare(directory, runner):
        execution = runner(["npm", "ci"], directory, 900)
        gate.require(execution.returncode == 0 and not execution.timed_out, "npm ci failed")
        return tmp_path, {"install": "x"}
    def runner(command, cwd, timeout):
        return npm.pop(0) if command == ["npm", "ci"] else gate.Execution(0, "")
    rows = gate.run_gate([gate.Check("typecheck", ["tsc"], timeout=1)], tmp_path, runner, prepare=prepare)
    assert rows[0]["result"] == "PASS" and not npm and sleeps == [gate.POWER_POLL_SECONDS]
    first, second = rows[0]["evidence"]["ui_dependencies_power_attempts"]
    assert first["timed_out"] and first["on_battery"] and not second["timed_out"]
    assert (tmp_path / "ui-dependencies.attempt1.log").read_text(encoding="utf-8") == "npm half"
    assert rows[0]["power_wait_seconds"] == 30 and rows[0]["seconds"] == 0


def test_ui_dependency_wait_over_limit_is_not_a_ui_error(tmp_path, monkeypatch):
    monkeypatch.setenv(gate.BATTERY_WAIT_MAX_ENV, "30")
    fake_clock(monkeypatch, [True])
    def prepare(directory, runner):
        runner(["npm", "ci"], directory, 900)
        pytest.fail("npm ci không được chạy trên pin quá trần")
    rows = gate.run_gate([gate.Check("typecheck", ["tsc"], timeout=1), gate.Check("vitest", ["v"], timeout=1)],
                         tmp_path, lambda *_: pytest.fail("không chạy"), prepare=prepare)
    assert [r["result"] for r in rows] == ["NOT_RUN", "NOT_RUN"]


@pytest.mark.parametrize("output", [
    'BUILD FAILED in 14m{"status": "FAIL", "timed_out": true}',
    'task {compileKotlin} killed {x{"status": "FAIL", "timed_out": true}\n\n',
    'line\n{"status": "FAIL", "timed_out": true}',
])
def test_worker_json_glued_to_the_last_log_line(output):
    assert gate.worker_json(output) == {"status": "FAIL", "timed_out": True}
    assert gate.execution_timed_out(gate.Execution(1, output))


def test_worker_json_glued_reaches_validate_report(tmp_path):
    output = 'Daemon stopped{"status": "PASS", "counts": {"passed": 2}}'
    counts, evidence = gate.validate_report(fake_check("json"), gate.Execution(0, output), tmp_path / "x.json")
    assert counts == {"passed": 2} and evidence["status"] == "PASS"
    with pytest.raises(ValueError, match="không kết thúc bằng JSON"):
        gate.validate_report(fake_check("json"), gate.Execution(1, "Gradle killed {"), tmp_path / "x.json")


@pytest.mark.parametrize("fails", [False, True])
def test_worker_prints_its_json_on_its_own_line(monkeypatch, capsys, fails):
    def worker(name, confirm_hash=None):
        print("gradle killed mid-line", end="")
        if fails:
            raise ValueError("Gradle: lỗi")
        return {"status": "PASS", "counts": {"passed": 1}}
    monkeypatch.setattr(gate, "worker", worker)
    assert gate.main(["--worker", "android-unit"]) == int(fails)
    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == "gradle killed mid-line"
    assert json.loads(lines[-1])["status"] == ("FAIL" if fails else "PASS")


def test_power_probe_failure_or_non_windows_counts_as_mains(monkeypatch):
    def broken():
        raise OSError("không đọc được pin")
    monkeypatch.setattr(gate, "battery_probe", broken)
    assert gate.on_battery() is False
    monkeypatch.setattr(gate.os, "name", "posix")
    assert REAL_BATTERY_PROBE() is False


def test_android_worker_reports_gradle_timeout_explicitly(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    monkeypatch.setattr(gate, "android_host_inputs", lambda: {})
    monkeypatch.setattr(gate, "run_process", lambda *args, **kwargs: gate.Execution(-1, "gradle", True))
    result = gate.worker("android-unit")
    assert result["status"] == "FAIL" and result["timed_out"] is True
    assert gate.execution_timed_out(gate.Execution(1, json.dumps(result)))


def test_execution_timed_out_reads_worker_json():
    assert gate.execution_timed_out(gate.Execution(-1, "", True))
    assert gate.execution_timed_out(gate.Execution(1, 'x\n{"status": "FAIL", "timed_out": true}'))
    assert not gate.execution_timed_out(gate.Execution(1, '{"status": "FAIL"}'))
    assert not gate.execution_timed_out(gate.Execution(1, "not json"))
    assert not gate.execution_timed_out(gate.Execution(0, ""))


@pytest.mark.parametrize("name", ["ui-parity", "ui-parity-qt"])
@pytest.mark.parametrize("code,timed_out", [(0, False), (1, False), (0, True)])
def test_parity_worker_requires_the_real_scanner_to_finish_successfully(monkeypatch, name, code, timed_out):
    calls = []
    def scanner(command, cwd, timeout):
        calls.append(command)
        assert cwd == gate.ROOT
        assert timeout == 180
        return gate.Execution(code, "scanner evidence", timed_out)
    monkeypatch.setattr(gate, "run_process", scanner)
    if code or timed_out:
        with pytest.raises(Exception, match="source parity failed"):
            gate.worker(name)
    else:
        result = gate.worker(name)
        assert result["counts"] == {"checks": 1}
        assert result["status"] == "PASS"
        assert result["detail"] == "scanner evidence"
        assert result["timed_out"] is False
    assert calls and calls[0][-1] == "--check"
    expected = "scripts/ui_parity.py" if name == "ui-parity" else "scripts/ui_parity_qt.py"
    assert calls[0] == gate.py(expected, "--check")


@pytest.fixture
def ignored_repo(tmp_path, monkeypatch):
    def run(*args):
        return subprocess.run(["git", "-C", str(tmp_path), *args], check=True,
                              capture_output=True, text=True,
                              creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0).stdout.strip()
    run("init")
    run("config", "user.name", "Gate test")
    run("config", "user.email", "gate@example.invalid")
    (tmp_path / ".gitignore").write_text(
        "/result.md\n/PROGRESS.md\n/_internal/PROGRESS.md\n*.mp3\n", encoding="utf-8")
    run("add", ".gitignore")
    run("commit", "-m", "baseline")
    monkeypatch.setattr(gate, "REPO", tmp_path)
    monkeypatch.setattr(gate, "RELEASE_BASE", run("rev-parse", "HEAD"))
    run("commit", "--allow-empty", "-m", "release work")
    return tmp_path, run


def test_ignored_tracked_is_in_full_gate_and_clean_repo_passes(ignored_repo):
    assert "ignored-tracked" in {check.name for check in gate.checks()}
    assert gate.worker("ignored-tracked")["counts"] == {
        "ignored": 0, "approved": 0, "commits": 1, "findings": 0}


def test_ignored_tracked_blocks_forced_audio_and_staged_removal(ignored_repo):
    root, run = ignored_repo
    (root / "unexpected.mp3").write_bytes(b"test signal")
    run("add", "-f", "unexpected.mp3")
    run("commit", "-m", "forced audio")
    with pytest.raises(ValueError, match="unapproved paths.*unexpected.mp3"):
        gate.worker("ignored-tracked")
    run("update-index", "--force-remove", "unexpected.mp3")
    with pytest.raises(ValueError, match="index differs from HEAD"):
        gate.worker("ignored-tracked")


@pytest.mark.parametrize("relative", list(gate.IGNORED_TRACKED_APPROVED))
def test_ignored_tracked_allows_only_exact_generated_fixture_bytes(ignored_repo, relative):
    root, run = ignored_repo
    path = root / relative
    path.parent.mkdir(parents=True)
    path.write_bytes((ROOT.parent / relative).read_bytes())
    run("add", "-f", relative)
    run("commit", "-m", "generated fixture")
    assert gate.worker("ignored-tracked")["counts"]["approved"] == 1
    path.write_bytes(b"replacement recording")
    run("add", "-f", relative)
    run("commit", "-m", "replaced fixture")
    with pytest.raises(ValueError, match="fixture bytes changed"):
        gate.worker("ignored-tracked")


@pytest.mark.parametrize("relative", gate.PRIVATE_WORK_LOGS)
@pytest.mark.parametrize("rename", [False, True])
def test_ignored_tracked_blocks_work_logs_even_after_deletion(ignored_repo, relative, rename):
    root, run = ignored_repo
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    if rename:
        (root / "notes.txt").write_text("private work notes\n", encoding="utf-8")
        run("add", "notes.txt")
        run("commit", "-m", "notes")
        (root / "notes.txt").rename(path)
        run("add", "-u")
    else:
        path.write_text("private work notes\n", encoding="utf-8")
    run("add", "-f", relative)
    run("commit", "-m", "work log")
    path.unlink()
    run("add", "-u")
    run("commit", "-m", "remove work log")
    assert run("ls-files", "-ci", "--exclude-standard") == ""
    with pytest.raises(ValueError, match="private work logs added in history") as caught:
        gate.worker("ignored-tracked")
    assert relative in str(caught.value)


def test_ignored_tracked_paths_are_anchored_to_repo_root(ignored_repo):
    root, run = ignored_repo
    (root / "docs").mkdir()
    (root / "docs/result.md").write_text("public documentation\n", encoding="utf-8")
    run("add", "docs/result.md")
    run("commit", "-m", "documentation")
    assert gate.worker("ignored-tracked")["counts"]["findings"] == 0


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


def test_private_ui_workspace_preserves_shared_catalogs(tmp_path, monkeypatch):
    root = tmp_path / "source/_internal"
    ui = root / "ui"
    ui.mkdir(parents=True)
    (ui / "package.json").write_text("{}", encoding="utf-8")
    (ui / "package-lock.json").write_text('{"packages":{}}', encoding="utf-8")
    shared = ui / "node_modules"
    shared.mkdir()
    (shared / "sentinel").write_text("shared dependencies must stay untouched", encoding="utf-8")
    for name in ("abook", "docs", "tests", "mobile", "desktop_qt", "ui_strings", "ui_design", "scripts"):
        (root / name).mkdir()
    (root / "scripts/tap_audit").mkdir()
    (root / "scripts/tap_audit/ui_tap_audit.py").write_text("# harness source read by ui/scripts tests", encoding="utf-8")
    catalog = {"strings": {"broken_pdf": "PDF không đọc được"}}
    (root / "ui_strings/vi.json").write_text(json.dumps(catalog), encoding="utf-8")
    (root / "ui_design/tokens.json").write_text('{"space":{"base":4}}', encoding="utf-8")
    digest = hashlib.sha256((ui / "package.json").read_bytes() + (ui / "package-lock.json").read_bytes()).hexdigest()
    install = root / "runtime/release_gate/dependencies" / digest
    (install / "node_modules").mkdir(parents=True)
    (install / "complete.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(gate, "ROOT", root)

    def no_install(*_):
        pytest.fail("Cached dependencies require no installation")

    mirror, _ = gate.prepare_ui(tmp_path / "run", no_install)
    # Vitest reads outside ui/ through the same relative paths as application consumers.
    assert json.loads((mirror.parent / "ui_strings/vi.json").read_text(encoding="utf-8")) == catalog
    assert json.loads((mirror.parent / "ui_design/tokens.json").read_text(encoding="utf-8"))["space"]["base"] == 4
    assert (mirror.parent / "scripts/tap_audit/ui_tap_audit.py").is_file()
    assert (mirror / "node_modules").resolve() == (install / "node_modules").resolve()
    assert (shared / "sentinel").read_text(encoding="utf-8") == "shared dependencies must stay untouched"
    assert not (mirror / "node_modules/sentinel").exists()


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
    monkeypatch.setattr(gate, "release_range", lambda: {"base": "v0.0.1", "commits": 1})
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
    monkeypatch.setattr(gate, "release_range", lambda: {"base": "v0.0.1", "commits": 1})
    source = tmp_path / "source.py"
    source.write_text("# " + gate.FORBIDDEN_TERMS[0], encoding="utf-8")
    monkeypatch.setattr(gate, "REPO", tmp_path)
    monkeypatch.setattr(gate, "changed_files", lambda: [source])
    monkeypatch.setattr(gate, "source_lines", lambda path, base=None: path.read_text(encoding="utf-8").splitlines())
    with pytest.raises(ValueError, match="cần duyệt"):
        gate.worker("forbidden-terms")


@pytest.mark.parametrize("relative,allowed", [
    ("_internal/scripts/corpus/manifest.py", True),
    ("_internal/scripts/corpus/manifest.json", False),
    ("_internal/scripts/corpus/Corpus/chapter.py", False),
    ("_internal/Corpus/chapter.py", False),
])
def test_corpus_tool_namespace_is_distinct_from_private_corpus_data(tmp_path, monkeypatch, relative, allowed):
    monkeypatch.setattr(gate, "REPO", tmp_path)
    monkeypatch.setattr(gate, "release_range", lambda: {"base": "v0.0.1", "commits": 1})
    path = tmp_path / relative
    path.parent.mkdir(parents=True)
    path.write_text("safe = 1\n", encoding="utf-8")
    monkeypatch.setattr(gate, "changed_files", lambda: [path])
    monkeypatch.setattr(gate, "source_lines", lambda path, base=None: path.read_text().splitlines())
    if allowed:
        assert gate.worker("diff-safety")["counts"]["findings"] == 0
    else:
        with pytest.raises(ValueError, match="file riêng tư"):
            gate.worker("diff-safety")


@pytest.mark.parametrize("prefix", ["_internal/abook/assets/voice_avatars/",
                                     "_internal/mobile/android/app/src/main/assets/voice_avatars/"])
def test_voice_artwork_requires_exact_reviewed_clean_bytes(tmp_path, monkeypatch, prefix):
    from PIL import Image

    monkeypatch.setattr(gate, "REPO", tmp_path)
    relative = prefix + "voice-1234abcd.webp"
    path = tmp_path / relative
    path.parent.mkdir(parents=True)
    registry = tmp_path / "_internal/scripts/voice_artwork_reviewed.json"
    registry.parent.mkdir(parents=True)
    def review():
        registry.write_text(json.dumps({relative: {
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "reason": "Reviewed generated illustration with no source text or private metadata.",
        }}), encoding="utf-8")
    Image.new("RGB", (256, 256), "white").save(path, format="WEBP")
    with pytest.raises(ValueError, match="review missing"):
        gate.require_reviewed_voice_artwork(path)
    review()
    gate.require_reviewed_voice_artwork(path)
    Image.new("RGB", (256, 256), "black").save(path, format="WEBP")
    with pytest.raises(ValueError, match="stale"):
        gate.require_reviewed_voice_artwork(path)
    review()
    with path.open("ab") as stream:
        stream.write(b"private trailing data")
    review()
    with pytest.raises(ValueError, match="container invalid"):
        gate.require_reviewed_voice_artwork(path)
    for size, metadata in [((128, 256), {}), ((256, 256), {"xmp": b"private metadata"})]:
        Image.new("RGB", size).save(path, format="WEBP", **metadata)
        review()
        with pytest.raises(ValueError, match="format/metadata invalid"):
            gate.require_reviewed_voice_artwork(path)
    with pytest.raises(ValueError, match="path not permitted"):
        gate.require_reviewed_voice_artwork(tmp_path / "private/voice-1234abcd.webp")


def test_tall_scroll_snapshot_requires_exact_bounded_dimensions(tmp_path, monkeypatch):
    from PIL import Image

    monkeypatch.setattr(gate, "REPO", tmp_path)
    relative = "_internal/mobile/android/app/src/test/snapshots/scroll.png"
    path = tmp_path / relative
    path.parent.mkdir(parents=True)
    registry = tmp_path / "_internal/scripts/snapshot_reviewed.json"
    registry.parent.mkdir(parents=True)
    Image.new("RGB", (32, 9000), "white").save(path)
    def review(dimensions=None):
        row = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
               "reason": "Visually reviewed complete scroll content and all controls at its exact dimensions."}
        if dimensions is not None:
            row["scroll_dimensions"] = dimensions
        registry.write_text(json.dumps({relative: row}), encoding="utf-8")
    for dimensions in (None, [32, 9001]):
        review(dimensions)
        with pytest.raises(ValueError, match="format/metadata invalid"):
            gate.require_reviewed_snapshot(path)
    review([32, 9000])
    gate.require_reviewed_snapshot(path)
    Image.new("RGB", (32, 16385), "white").save(path)
    review([32, 16385])
    with pytest.raises(ValueError, match="format/metadata invalid"):
        gate.require_reviewed_snapshot(path)


def test_binary_diff_requires_exact_reviewed_snapshot_without_metadata(tmp_path, monkeypatch):
    from PIL import Image, PngImagePlugin

    monkeypatch.setattr(gate, "REPO", tmp_path)
    relative = "_internal/mobile/android/app/src/test/snapshots/example.png"
    path = tmp_path / relative
    path.parent.mkdir(parents=True)
    Image.new("RGB", (2, 2), "white").save(path)
    registry = tmp_path / "_internal/scripts/snapshot_reviewed.json"
    registry.parent.mkdir(parents=True)
    with pytest.raises(ValueError, match="review missing"):
        gate.require_reviewed_snapshot(path)

    def review():
        registry.write_text(json.dumps({relative: {
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "reason": "Visually reviewed the complete example and confirmed readable, separated controls.",
        }}), encoding="utf-8")

    review()
    gate.require_reviewed_snapshot(path)
    Image.new("RGB", (2, 2), "black").save(path)
    with pytest.raises(ValueError, match="stale"):
        gate.require_reviewed_snapshot(path)
    metadata = PngImagePlugin.PngInfo()
    metadata.add_text("private", "example metadata")
    Image.new("RGB", (2, 2)).save(path, pnginfo=metadata)
    review()
    with pytest.raises(ValueError, match="metadata invalid"):
        gate.require_reviewed_snapshot(path)
    other = tmp_path / "unreviewed.png"
    Image.new("RGB", (2, 2)).save(other)
    with pytest.raises(ValueError, match="binary"):
        gate.require_reviewed_snapshot(other)


@pytest.mark.parametrize("name", ["diff-safety", "forbidden-terms"])
def test_commits_with_no_checked_files_fail(name, monkeypatch):
    monkeypatch.setattr(gate, "release_range", lambda: {"base": "v0.0.1", "commits": 1})
    monkeypatch.setattr(gate, "changed_files", lambda: [])
    with pytest.raises(ValueError, match="files=0.*range"):
        gate.worker(name)
    monkeypatch.setattr(gate, "release_range", lambda: {"base": "v0.0.1", "commits": 0})
    assert gate.worker(name)["explicitly_empty_range"]


def test_clean_committed_diff_is_checked_from_the_previous_release(tmp_path, monkeypatch):
    def run(*args):
        return subprocess.run(["git", "-C", str(tmp_path), *args], check=True, capture_output=True, text=True).stdout
    run("init")
    run("config", "user.name", "Gate test")
    run("config", "user.email", "gate@example.invalid")
    path = tmp_path / "source.py"
    path.write_text("safe = 1\n", encoding="utf-8")
    run("add", "source.py")
    run("commit", "-m", "baseline")
    run("tag", "v0.0.1")
    path.write_text("# " + gate.FORBIDDEN_TERMS[0] + "\n", encoding="utf-8")
    run("commit", "-am", "new source")
    monkeypatch.setattr(gate, "REPO", tmp_path)
    assert run("status", "--porcelain") == ""
    assert gate.changed_files() == [path]
    assert gate.worker("diff-safety")["range"] == {"base": "v0.0.1", "commits": 1}
    with pytest.raises(ValueError, match="cần duyệt"):
        gate.worker("forbidden-terms")
    run("tag", "v0.0.2")
    assert gate.release_range()["base"] == "v0.0.1"


def test_explicit_release_base_is_an_ancestor_and_reaches_every_worker(tmp_path, monkeypatch):
    def run(*args):
        return subprocess.run(["git", "-C", str(tmp_path), *args], check=True, capture_output=True, text=True).stdout.strip()

    run("init")
    run("config", "user.name", "Gate test")
    run("config", "user.email", "gate@example.invalid")
    path = tmp_path / "source.py"
    path.write_text("safe = 1\n", encoding="utf-8")
    run("add", "source.py")
    run("commit", "-m", "scrubbed baseline")
    base = run("rev-parse", "HEAD")
    run("tag", "v0.3.0-example")
    path.write_text("safe = 2\n", encoding="utf-8")
    run("commit", "-am", "new release")
    monkeypatch.setattr(gate, "REPO", tmp_path)
    monkeypatch.setattr(gate, "RELEASE_BASE", base)
    assert gate.release_range() == {"base": base, "commits": 1}
    assert gate.changed_files() == [path]
    assert gate.worker_command("diff-safety")[-2:] == ["--base", base]
    monkeypatch.setattr(gate, "RELEASE_BASE", "HEAD")
    with pytest.raises(ValueError, match="must precede HEAD"):
        gate.release_range()
    unrelated = run("commit-tree", "HEAD^{tree}", "-m", "unrelated root")
    monkeypatch.setattr(gate, "RELEASE_BASE", unrelated)
    with pytest.raises(subprocess.CalledProcessError):
        gate.release_range()


def test_quality_hash_requires_exact_current_hash_when_changed(monkeypatch):
    from abook import quality_policy
    current = "b" * 64
    monkeypatch.setattr(quality_policy, "quality_implementation_hash", lambda: current)
    monkeypatch.setattr(gate, "release_quality_hash", lambda _: "a" * 64)
    monkeypatch.setattr(gate, "release_range", lambda: {"base": "v0.0.1", "commits": 1})
    monkeypatch.setattr(gate, "changed_files", lambda: [])
    for confirmation in (None, "a" * 64):
        with pytest.raises(ValueError, match="requires --confirm-hash"):
            gate.worker("quality-hash", confirmation)
    assert gate.worker("quality-hash", current)["hash"] == current
    check = next(c for c in gate.checks(current) if c.name == "quality-hash")
    assert check.command[-2:] == ["--confirm-hash", current]


@pytest.mark.parametrize("summary", ["2 passed, 900 skipped in 1s", "2 passed, 1 xfailed in 1s"])
def test_skipped_or_expected_failure_growth_blocks_the_gate(tmp_path, summary):
    rows = gate.run_gate([fake_check()], tmp_path, lambda *_: gate.Execution(0, summary))
    assert rows[0]["result"] == "FAIL"


def test_gate_reports_skip_reasons_and_runs_external_test_tools():
    definitions = {c.name: c for c in gate.checks()}
    assert "-rfs" in definitions["pytest"].command
    assert definitions["qt-installer"].requires == ("qt-tests",)
    assert "desktop_qt/tools/test_installer.py" in definitions["qt-installer"].command
    assert "sheet-geometry" in definitions and "sheet-geometry" in gate.UI_CHECKS
    assert definitions["pytest"].command[definitions["pytest"].command.index("-m", 5) + 1] == "not browser"


def test_missing_host_g2p_fails_before_any_gradle_invocation(tmp_path, monkeypatch):
    monkeypatch.setenv("ABOOK_SEA_G2P_LIB", str(tmp_path / "absent.dll"))
    monkeypatch.setattr(gate, "run_process", lambda *_: pytest.fail("Gradle must not run"))
    assert gate.safe_env()["ABOOK_REQUIRE_G2P_PARITY"] == "1"
    for name in ("android-unit", "android-snapshots"):
        with pytest.raises(ValueError, match="host sea_g2p"):
            gate.worker(name)


def test_snapshot_checks_require_all_goldens_and_unmodified_verified_images(tmp_path, monkeypatch):
    baseline = {"a.png": "a" * 64, "b.png": "b" * 64}
    monkeypatch.setattr(gate, "snapshot_baseline", lambda: baseline.copy())
    with pytest.raises(ValueError, match="missing or extra"):
        gate.validate_snapshot_proofs(tmp_path, baseline)
    for name, digest in baseline.items():
        (tmp_path / (name + ".json")).write_text(json.dumps({"snapshot": name, "status": "verified", "golden_sha256": digest}), encoding="utf-8")
    assert gate.validate_snapshot_proofs(tmp_path, baseline) == {"goldens": 2, "compared": 2, "different": 0}
    monkeypatch.setattr(gate, "snapshot_baseline", lambda: {"a.png": "changed", "b.png": "b" * 64})
    with pytest.raises(ValueError, match="modified"):
        gate.validate_snapshot_proofs(tmp_path, baseline)


def test_phoneme_suite_skip_and_absence_cannot_be_hidden_by_other_android_passes(tmp_path):
    names = ("SeaG2pParityTest", "PhonemePolicyTest", "RealNamesTest", "EnglishDirectFrontendTest", "NormalizedOccurrenceTest")
    for name in names:
        (tmp_path / ("TEST-" + name + ".xml")).write_text(
            f'<testsuite name="vn.abook.player.vieneu.{name}"><testcase name="real"/></testsuite>', encoding="utf-8")
    gate.require_phoneme_suites_ran(tmp_path)
    path = tmp_path / ("TEST-" + names[0] + ".xml")
    path.write_text(f'<testsuite name="{names[0]}"><testcase name="real"><skipped/></testcase></testsuite>', encoding="utf-8")
    with pytest.raises(ValueError, match="skipped"):
        gate.require_phoneme_suites_ran(tmp_path)
    path.rename(path.with_suffix(".absent"))
    with pytest.raises(ValueError, match="missing phoneme"):
        gate.require_phoneme_suites_ran(tmp_path)


def test_android_gate_generates_occurrence_parity_for_its_native_run(tmp_path, monkeypatch):
    from scripts.generate_g2p_parity import load

    monkeypatch.setattr(gate, "ROOT", tmp_path)
    monkeypatch.setattr(gate, "android_host_inputs", lambda: {})
    results = tmp_path / "mobile/android/app/build/test-results/testDebugUnitTest"
    inputs = []

    def run(command, cwd, timeout, extra_env, **options):
        fixture = Path(extra_env["ABOOK_G2P_OCCURRENCE_FIXTURE"])
        assert fixture.is_file() and not fixture.is_relative_to(gate.REPO)
        cases = load(fixture)["cases"]
        assert len(cases) == 12
        assert {case["id"] for case in cases} >= {"before-unit", "tag-middle", "bare-number"}
        assert all(case["units"] and case["phonemes"] for case in cases)
        inputs.append(fixture)
        results.mkdir(parents=True)
        for name in ("SeaG2pParityTest", "PhonemePolicyTest", "RealNamesTest", "EnglishDirectFrontendTest", "NormalizedOccurrenceTest"):
            (results / f"TEST-{name}.xml").write_text(
                f'<testsuite name="{name}" tests="1" failures="0" errors="0"><testcase name="real"/></testsuite>', encoding="utf8")
        return gate.Execution(0, "")

    monkeypatch.setattr(gate, "run_process", run)
    assert gate.worker("android-unit")["status"] == "PASS"
    assert len(inputs) == 1 and not inputs[0].exists()


def test_android_rows_force_only_the_test_task_within_a_measured_budget(tmp_path, monkeypatch):
    # Every row reruns the test task (fresh XML), but unchanged Kotlin is not recompiled: under all-core load the forced
    # BELOW_NORMAL compile alone went 52 s -> 1111 s. The budget is a measured unloaded row times a stated factor.
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    monkeypatch.setattr(gate, "android_host_inputs", lambda: {})
    monkeypatch.setattr(gate, "require_phoneme_suites_ran", lambda results: None)
    monkeypatch.setattr(gate, "parse_gradle", lambda results: {"passed": 1, "failed": 0, "error": 0, "skipped": 0})
    seen = []

    def run(command, cwd, timeout, extra_env, *, yield_cpu=True):
        seen.append((command, timeout, yield_cpu))
        return gate.Execution(0, "")

    monkeypatch.setattr(gate, "run_process", run)
    assert gate.worker("android-unit")["status"] == "PASS"
    command, timeout, yield_cpu = seen[0]
    assert yield_cpu is False  # measured: BELOW_NORMAL Gradle starves under all-core load
    assert "--rerun-tasks" not in command
    at = command.index(":app:testDebugUnitTest")
    assert command[at + 1] == "--rerun"
    assert timeout == gate.ANDROID_ROW_BUDGET_S == round(gate.ANDROID_ROW_UNLOADED_S * gate.ANDROID_ROW_LOAD_FACTOR)
    rows = {check.name: check for check in gate.checks()}
    assert all(rows[name].timeout > timeout for name in ("android-unit", "android-snapshots"))


@pytest.mark.skipif(os.name != "nt", reason="Windows priority classes")
def test_run_process_sets_the_priority_class_explicitly(monkeypatch):
    # The gate worker itself runs BELOW_NORMAL; NORMAL must be asked for, not inherited.
    seen = []

    class Done(Exception):
        pass

    def popen(command, **options):
        seen.append(options["creationflags"])
        raise Done

    monkeypatch.setattr(gate.subprocess, "Popen", popen)
    for yield_cpu in (True, False):
        with pytest.raises(Done):
            gate.run_process(["x"], Path("."), 1, yield_cpu=yield_cpu)
    assert seen[0] & subprocess.BELOW_NORMAL_PRIORITY_CLASS and not seen[0] & subprocess.NORMAL_PRIORITY_CLASS
    assert seen[1] & subprocess.NORMAL_PRIORITY_CLASS and not seen[1] & subprocess.BELOW_NORMAL_PRIORITY_CLASS


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


def negative_tap_scenario():
    healthy = dict(label="choice", tag="BUTTON", disabled=False, hit=True,
                   pointerEvents="auto", blockedInLayer=[], noneAncestors=["BODY"])
    broken = dict(healthy, hit=False, pointerEvents="none", blockedInLayer=["BUTTON"],
                  noneAncestors=["BUTTON", "DIV[role=menu]", "BODY"])
    names = ["negative baseline healthy before injection", "fault injection applied",
             "negative original pointer state restored healthy",
             "visible layer controls receive pointer events throughout opening"]
    return dict(status="FAIL", injected=True, checks=[dict(name=n, pass_=True) for n in names]
                + [dict(name=m+" probe center reaches control", pass_=False) for m in ("mouse", "touch")],
                negativeControl=dict(baseline=dict(healthy=True, elements=[dict(healthy)],
                                                  probes={m: dict(healthy) for m in ("mouse", "touch")}),
                                     detected={m: dict(broken) for m in ("mouse", "touch")},
                                     restored=dict(healthy=True, elements=[dict(healthy)])))


def test_negative_control_accepts_only_scoped_pointer_failure_with_recovery():
    gate.validate_tap_negative(negative_tap_scenario())


@pytest.mark.parametrize("mutation", ["old_report", "setup_error", "baseline", "baseline_flag", "restored",
                                         "missing_touch", "disabled", "target_changed", "no_pointer_fault",
                                         "unrelated_failure", "missing_opening_check", "non_boolean"])
def test_negative_control_rejects_setup_cascades_and_unproven_faults(mutation):
    row = negative_tap_scenario()
    control = row["negativeControl"]
    if mutation == "old_report": del row["negativeControl"]
    elif mutation == "setup_error": row["error"] = "layer did not open after coordinate input"
    elif mutation == "baseline": control["baseline"]["elements"][0]["hit"] = False
    elif mutation == "baseline_flag": control["baseline"]["healthy"] = False
    elif mutation == "restored": control["restored"]["elements"][0]["pointerEvents"] = "none"
    elif mutation == "missing_touch": del control["detected"]["touch"]
    elif mutation == "disabled": control["detected"]["mouse"]["disabled"] = True
    elif mutation == "target_changed": control["detected"]["mouse"]["label"] = "another control"
    elif mutation == "no_pointer_fault": control["detected"]["mouse"]["pointerEvents"] = "auto"
    elif mutation == "unrelated_failure": row["checks"].append(dict(name="close failed", pass_=False))
    elif mutation == "missing_opening_check": row["checks"].pop(3)
    elif mutation == "non_boolean": row["checks"][0]["pass_"] = "true"
    with pytest.raises(ValueError, match="tap-negative"):
        gate.validate_tap_negative(row)


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


def test_preview_bar_runs_in_the_gate_and_needs_every_width_and_theme(tmp_path):
    """Soát 18-11: check_preview_bar.mjs (Chromium bấm thật vào phần đệm thanh "Đang nghe thử") phải là một bước của cổng, không chỉ chạy tay."""
    check = {c.name: c for c in gate.checks()}["preview-bar"]
    assert check.requires == ("gallery-build",) and "preview-bar" in gate.UI_CHECKS
    assert "scripts/check_preview_bar.mjs" in check.command and check.command[check.command.index("--dist") + 1] == "dist/gallery"
    points = {name: {"x": 1, "y": 1} for name in ("padLeft", "padTop", "padBottom", "gap", "padRight")}
    full = [{"width": w, "height": 900, "theme": t, "points": points} for w in (1280, 420) for t in ("light", "dark")]
    artifact = tmp_path / "preview-bar-checks.json"
    artifact.write_text(json.dumps(full), encoding="utf-8")
    counts, _ = gate.validate_report(check, gate.Execution(0), artifact)
    assert counts == {"cases": 4, "points": 20}
    artifact.write_text(json.dumps(full[:3]), encoding="utf-8")
    with pytest.raises(ValueError, match="preview-bar"):
        gate.validate_report(check, gate.Execution(0), artifact)
    artifact.write_text(json.dumps(full), encoding="utf-8")
    with pytest.raises(ValueError, match="exit 1"):
        gate.validate_report(check, gate.Execution(1), artifact)


def test_outside_taps_runs_in_the_gate_and_needs_every_layer_and_press(tmp_path):
    """Soát 18-11 tapfix5: check_outside_taps.mjs (Chromium thật bấm / chạm / bấm phải ra ngoài mọi lớp nổi) là một bước của cổng."""
    check = {c.name: c for c in gate.checks()}["outside-taps"]
    assert check.requires == ("gallery-build",) and "outside-taps" in gate.UI_CHECKS
    assert "scripts/check_outside_taps.mjs" in check.command and check.command[check.command.index("--dist") + 1] == "dist/gallery"
    ids = sorted(gate.OUTSIDE_TAPS_REQUIRED) + ["library-sort-menu-wheel"]
    press = lambda name: next((p for p in ("touch", "right", "wheel") if name.endswith("-" + p)), None)
    rows = [{"id": name, "outside": {"pass": True, **({"press": press(name)} if press(name) else {})}} for name in ids]
    artifact = tmp_path / "outside-taps.json"
    write = lambda results, scenarios=None: artifact.write_text(json.dumps({"scenarios": scenarios or [r["id"] for r in results], "results": results}), encoding="utf-8")
    write(rows)
    counts, _ = gate.validate_report(check, gate.Execution(0), artifact)
    assert counts == {"passed": len(ids), "failed": 0, "scenarios": len(ids)}
    leaked = [dict(r, outside={**r["outside"], "pass": r["id"] != "remote-sleep-in-dialog"}) for r in rows]
    write(leaked)
    with pytest.raises(ValueError, match="lọt ở remote-sleep-in-dialog"):
        gate.validate_report(check, gate.Execution(1), artifact)
    write([r for r in rows if r["id"] != "remote-sleep-in-dialog-touch"])
    with pytest.raises(ValueError, match="bắt buộc"):
        gate.validate_report(check, gate.Execution(0), artifact)
    write(rows, [r["id"] for r in rows] + ["extra"])
    with pytest.raises(ValueError, match="thiếu / trùng"):
        gate.validate_report(check, gate.Execution(0), artifact)
    write([r for r in rows if not r["id"].endswith("-wheel")])
    with pytest.raises(ValueError, match="lăn"):
        gate.validate_report(check, gate.Execution(0), artifact)
    write(rows)
    with pytest.raises(ValueError, match="exit 1"):
        gate.validate_report(check, gate.Execution(1), artifact)


def test_qt_suite_calls_keep_each_build_bat_run_with_its_log_and_input(tmp_path):
    """fix174b runs WidthTests twice; the second run reads tests\\bookmeta and writes its own log (gate 1 of 0.4.174)."""
    text = (
        'call :test "%HERE%build\\width_tests\\WidthTests.exe" "%HERE%build\\width-test.txt"\r\n'
        'call :test "%HERE%build\\width_tests\\WidthTests.exe" "%HERE%build\\bookmeta-test.txt" -input "%HERE%tests\\bookmeta"\r\n'
        'call :test "%HERE%build\\VoiceTests.exe" "%HERE%build\\voice-test.txt"\r\n')
    qt = tmp_path / "desktop_qt"
    calls = gate.qt_suite_calls(text, qt)
    assert [(exe, log) for exe, log, _ in calls] == [
        ("width_tests\\WidthTests.exe", "width-test.txt"), ("width_tests\\WidthTests.exe", "bookmeta-test.txt"),
        ("VoiceTests.exe", "voice-test.txt")]
    assert calls[0][2] == [] and calls[2][2] == []
    assert calls[1][2] == ["-input", str(qt) + os.sep + "tests\\bookmeta"]
    real = (gate.ROOT / "desktop_qt/build.bat").read_text(encoding="ascii")
    found = gate.qt_suite_calls(real, gate.ROOT / "desktop_qt")
    assert len(found) == sum(line.startswith("call :test ") for line in real.splitlines())
    assert len({log for _, log, _ in found}) == len(found), "every build.bat run writes its own log"


def test_qt_suite_passes_its_extra_arguments(tmp_path):
    seen = []

    def runner(command, cwd, timeout):
        seen.append(command)
        Path(command[2].rsplit(",", 1)[0]).write_text("Totals: 3 passed, 0 failed, 0 skipped\n", encoding="utf-8")
        return gate.Execution(0, "")

    gate.run_qt_suite(tmp_path / "WidthTests.exe", tmp_path, tmp_path / "bookmeta-test.txt", runner, arguments=["-input", "x"])
    assert seen[0][-2:] == ["-input", "x"]

def test_vendored_upstream_files_skip_the_term_rule_but_their_readme_does_not(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "release_range", lambda: {"base": "v0.0.1", "commits": 1})
    monkeypatch.setattr(gate, "REPO", tmp_path)
    vendor = tmp_path / "_internal/abook/vendor/pkg"
    vendor.mkdir(parents=True)
    (vendor / "README.md").write_text("pkg 1.0 copied unchanged from the wheel\n", encoding="utf-8")
    upstream = vendor / "_config.py"
    upstream.write_text("# " + gate.FORBIDDEN_TERMS[1] + " handling of upstream\n", encoding="utf-8")
    monkeypatch.setattr(gate, "source_lines", lambda path, base=None: path.read_text(encoding="utf-8").splitlines())
    monkeypatch.setattr(gate, "changed_files", lambda: [upstream])
    assert gate.worker("forbidden-terms")["counts"]["findings"] == 0
    loose = tmp_path / "_internal/abook/vendor/helper.py"  # the project's own file next to the packages
    loose.write_text("# " + gate.FORBIDDEN_TERMS[1] + "\n", encoding="utf-8")
    unvendored = tmp_path / "_internal/abook/vendor/nodoc/mod.py"  # no README naming the upstream source
    unvendored.parent.mkdir()
    unvendored.write_text("# " + gate.FORBIDDEN_TERMS[1] + "\n", encoding="utf-8")
    for path in (loose, unvendored):
        monkeypatch.setattr(gate, "changed_files", lambda path=path: [path])
        with pytest.raises(ValueError, match="cần duyệt"):
            gate.worker("forbidden-terms")
    (vendor / "README.md").write_text("pkg 1.0 - " + gate.FORBIDDEN_TERMS[1] + " note\n", encoding="utf-8")
    monkeypatch.setattr(gate, "changed_files", lambda: [vendor / "README.md"])
    assert gate.worker("forbidden-terms")["prose_mentions_for_manual_review"] == ["_internal/abook/vendor/pkg/README.md"]


def test_binary_fixture_needs_an_exact_reviewed_entry(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "release_range", lambda: {"base": "v0.0.1", "commits": 1})
    monkeypatch.setattr(gate, "REPO", tmp_path)
    fixture = tmp_path / "_internal/tests/fixtures/books/sample.abook"
    fixture.parent.mkdir(parents=True)
    fixture.write_bytes(b"PK\x03\x04\0\0binary")
    monkeypatch.setattr(gate, "changed_files", lambda: [fixture])
    with pytest.raises(ValueError, match="binary review missing"):
        gate.worker("diff-safety")
    registry = tmp_path / "_internal/scripts/binary_reviewed.json"
    registry.parent.mkdir(parents=True)
    entry = {"sha256": hashlib.sha256(fixture.read_bytes()).hexdigest(), "reason": "synthetic package written by the contract test, no story text"}
    registry.write_text(json.dumps({"_internal/tests/fixtures/books/sample.abook": entry}), encoding="utf-8")
    assert gate.worker("diff-safety")["counts"]["findings"] == 0
    fixture.write_bytes(b"PK\x03\x04\0\0changed")
    with pytest.raises(ValueError, match="binary review missing or stale"):
        gate.worker("diff-safety")
    elsewhere = tmp_path / "_internal/abook/blob.bin"
    elsewhere.parent.mkdir(parents=True)
    elsewhere.write_bytes(b"\0\1")
    monkeypatch.setattr(gate, "changed_files", lambda: [elsewhere])
    with pytest.raises(ValueError, match="binary trong diff cần duyệt"):
        gate.worker("diff-safety")
    audio = tmp_path / "_internal/tests/fixtures/books/clip.mp3"
    audio.write_bytes(b"ID3\0")
    monkeypatch.setattr(gate, "changed_files", lambda: [audio])
    with pytest.raises(ValueError, match="audio"):
        gate.worker("diff-safety")


def captured_screen(directory: Path, name: str, nodes: list[dict], *, tree: bool = True, mtime: float | None = None) -> Path:
    from PIL import Image

    directory.mkdir(parents=True, exist_ok=True)
    png = directory / f"{name}.png"
    image = Image.new("RGB", (200, 96), (24, 24, 24))
    for node in nodes:  # the audit only judges text whose ink really reached the screenshot
        if node.get("color"):
            image.paste(tuple(int(node["color"][i:i + 2], 16) for i in (1, 3, 5)), (10, 10, 14, 14))
    image.save(png)
    if tree:
        nodes = [dict(id=i, parent=-1 if i == 0 else 0, bounds=[0, 0, 100, 48], **node) for i, node in enumerate(nodes)]
        (directory / f"{name}.tree.json").write_text(json.dumps({
            "image": png.name, "image_sha256": hashlib.sha256(png.read_bytes()).hexdigest(),
            "width": 200, "height": 96, "nodes": nodes}), encoding="utf-8")
    if mtime is not None:
        for path in directory.glob(name + ".*"):
            os.utime(path, (mtime, mtime))
    return png


def affordance_roots(tmp_path: Path) -> tuple[Path, Path]:
    return tuple(tmp_path / relative for relative in gate.AFFORDANCE_TREES)


def test_affordance_gate_passes_screens_whose_actions_look_tappable(tmp_path):
    for directory in affordance_roots(tmp_path):
        captured_screen(directory, "ok", [{"clickable": True}, {"text": "Thêm giọng"}, {"icon": True}])
    report = gate.affordance_report(tmp_path)
    assert report["status"] == "PASS", report
    assert report["counts"]["screens"] == 2 and report["counts"]["findings"] == 0


def test_affordance_gate_fails_a_plain_action_and_static_accent_text(tmp_path):
    android, qt = affordance_roots(tmp_path)
    captured_screen(android, "plain", [{"clickable": True}, {"text": "Thêm giọng", "color": "#ece8e1"}])
    captured_screen(qt, "accent", [{}, {"text": "Thông tin", "color": "#8a5309"}])
    report = gate.affordance_report(tmp_path)
    assert report["status"] == "FAIL"
    assert sorted(finding["rule"] for finding in report["findings"]) == ["AFFORDANCE_ACCENT", "AFFORDANCE_CLICK"]


def test_affordance_gate_ignores_text_spacing_which_design_lint_owns(tmp_path):
    for directory in affordance_roots(tmp_path):
        captured_screen(directory, "ok", [{"clickable": True}, {"icon": True}])
    report = gate.affordance_report(tmp_path)
    assert all(finding["rule"].startswith("AFFORDANCE_") for finding in report["findings"])


def test_affordance_gate_fails_a_screenshot_without_its_tree_or_a_platform_without_screens(tmp_path):
    android, qt = affordance_roots(tmp_path)
    captured_screen(android, "ok", [{"clickable": True}, {"icon": True}])
    captured_screen(android, "lost", [], tree=False)
    report = gate.affordance_report(tmp_path)
    assert report["status"] == "FAIL"
    assert any("Missing captured tree" in error for error in report["errors"])
    assert any("No captured trees" in error and qt.name in error for error in report["errors"])


def test_affordance_gate_never_passes_empty(tmp_path):
    assert gate.affordance_report(tmp_path)["status"] == "FAIL"


def test_affordance_gate_skips_leftovers_of_removed_tests(tmp_path):
    android, qt = affordance_roots(tmp_path)
    old = 1000.0  # epoch seconds, long before any file this test writes now
    for directory in (android, qt):
        captured_screen(directory, "ok", [{"clickable": True}, {"icon": True}])
    captured_screen(android, "removed_test", [{"clickable": True}, {"text": "Cũ", "color": "#ece8e1"}], mtime=old)
    captured_screen(qt, "removed_untreed", [], tree=False, mtime=old)
    report = gate.affordance_report(tmp_path, since=old + 1)
    assert report["status"] == "PASS", report
    assert report["counts"]["screens"] == 2


def test_release_gate_runs_both_ux_detectors():
    names = {check.name: check for check in gate.checks()}
    assert {"affordance", "affordance-web", "pending-states"} <= set(names)
    assert set(names["affordance"].requires) >= {"android-snapshots", "qt-tests"}
    assert "pending_audit.py" in " ".join(names["pending-states"].command)
    assert "--probe" in names["affordance-web"].command
