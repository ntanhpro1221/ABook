"""Bài thử không được đổi kết quả theo chỗ trống thật của ổ đĩa máy chạy test (fixture `_roomy_disk` trong conftest)."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import conftest
import psutil
import pytest

from abook.webui import studio_setup

TESTS = Path(__file__).resolve().parent
# Những bài từng đỏ khi ổ thật còn dưới 35 GB (11-11): cài Studio đi qua `StudioSetup._step_check`.
DISK_SENSITIVE = ("test_studio_setup.py", "test_studio_assets.py")


def test_every_test_sees_the_same_roomy_disk_whatever_the_path(tmp_path: Path) -> None:
    for path in (tmp_path, tmp_path / "chua-co", Path(tmp_path.anchor)):
        for usage in (shutil.disk_usage(path), psutil.disk_usage(str(path))):
            assert (usage.total, usage.free) == (conftest.DISK_TOTAL_BYTES, conftest.DISK_FREE_BYTES)
            assert usage.used == usage.total - usage.free
    assert conftest.DISK_FREE_BYTES > studio_setup.MIN_FREE_BYTES


def test_a_test_that_wants_a_full_disk_sets_its_own_number(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "disk_usage", lambda _path: type("U", (), {"total": 10**9, "used": 10**9, "free": 0})())
    assert studio_setup.shutil.disk_usage(tmp_path).free == 0


@pytest.mark.parametrize("real_free_gb", [1, 100])
def test_the_studio_install_tests_pass_whatever_the_real_disk_has_left(tmp_path: Path, real_free_gb: int) -> None:
    env = dict(os.environ)
    env.pop("ABOOK_PREFERENCES", None)  # của phiên test ngoài; phiên con tự đặt chỗ của nó
    env.update(
        ABOOK_TEST_REAL_DISK_GB=str(real_free_gb),
        PYTHONPATH=os.pathsep.join(filter(None, [str(TESTS), env.get("PYTHONPATH", "")])),
        CUDA_VISIBLE_DEVICES="-1",
        PYTHONUTF8="1",
    )
    command = [sys.executable, "-X", "utf8", "-m", "pytest", "-p", "real_disk_plugin", "-p", "no:cacheprovider", "-rf"]
    command += [f"--basetemp={tmp_path / 'con'}", *(str(TESTS / name) for name in DISK_SENSITIVE)]
    run = subprocess.run(command, cwd=TESTS.parent, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600, check=False)
    tail = run.stdout[-3000:] + run.stderr[-1000:]
    assert run.returncode == 0, tail
    summary = run.stdout.strip().splitlines()[-1]
    assert "failed" not in summary and "error" not in summary, tail
    assert int(re.search(r"(\d+) passed", summary).group(1)) >= 40, tail
