"""Bộ gỡ giữ thư mục dữ liệu có junction ở bất kỳ đâu bên trong (31-10).

NSIS RMDir /r đi theo junction: một junction dưới %LOCALAPPDATA%\\ABook (vd Studio trỏ ra ổ khác) làm rỗng thư mục đích ngoài app khi
người dùng tích "Xoá dữ liệu". Guard chỉ kiểm junction trên đường TỚI thư mục thì không đủ. Áp cho mọi bộ gỡ có trong cây.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GUARDS = [ROOT / "shell" / "src-tauri" / "windows" / "uninstall_guard.ps1",
          ROOT / "desktop_qt" / "installer" / "uninstall_guard.ps1"]

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="junction + bộ gỡ chỉ có trên Windows")


def _guard(guard: Path, tmp_path: Path, target: Path) -> int:
    return subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(guard)],
                          env={**os.environ, "ABOOK_PREFERENCES": str(tmp_path / "none.json"), "ABOOK_DELETE_TARGET": str(target)},
                          capture_output=True).returncode


@pytest.mark.parametrize("guard", GUARDS, ids=["tauri", "qt"])
@pytest.mark.parametrize("depth", ["top", "deep"])
def test_a_junction_inside_the_target_preserves_it(tmp_path: Path, guard: Path, depth: str):
    if not guard.exists():
        pytest.skip(f"{guard.relative_to(ROOT)} chưa có ở nhánh này")
    import _winapi
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep.txt").write_text("not ours", encoding="utf-8")
    target = tmp_path / "local" / "ABook"
    (target / "a" / "b").mkdir(parents=True)
    (target / "a" / "file.txt").write_text("x", encoding="utf-8")
    assert _guard(guard, tmp_path, target) == 0  # không junction: xoá được
    _winapi.CreateJunction(str(outside), str(target / "Studio" if depth == "top" else target / "a" / "b" / "Studio"))
    assert _guard(guard, tmp_path, target) == 4
    assert (outside / "keep.txt").exists()
