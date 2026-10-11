"""scripts/release.py: nâng số phiên bản đúng 8 file (chạy trên bản sao các file thật) và ghi chú GitHub Release - 2026-10-01."""
from __future__ import annotations

import datetime
import importlib.util
import re
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("release_script", ROOT / "scripts/release.py")
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)

FILES = ["pyproject.toml", "uv.lock", "ui/package.json", "ui/package-lock.json", "mobile/package.json", "mobile/package-lock.json",
         "mobile/android/app/build.gradle", "docs/CHANGELOG.md"]


def _copy(tmp_path: Path) -> Path:
    for relative in FILES:
        (tmp_path / relative).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, tmp_path / relative)
    return tmp_path


def _next(version: str) -> str:
    major, minor, patch = (int(part) for part in version.split("."))
    return f"{major}.{minor}.{patch + 1}"


def test_bump_changes_exactly_the_package_versions_the_build_number_and_the_changelog_heading(tmp_path: Path) -> None:
    root = _copy(tmp_path)
    old = release.current_version(root)
    new = _next(old)
    before = {relative: (root / relative).read_bytes() for relative in FILES}
    code = int(re.search(r"versionCode (\d+)", before["mobile/android/app/build.gradle"].decode()).group(1))

    changed = release.bump(new, root, today=datetime.date(2026, 10, 1))

    assert sorted(path.relative_to(root).as_posix() for path in changed) == sorted(FILES)
    assert release.current_version(root) == new
    for lock in ("ui/package-lock.json", "mobile/package-lock.json", "ui/package.json", "mobile/package.json"):
        text, was = (root / lock).read_text(encoding="utf-8"), before[lock].decode("utf-8")
        # Chỉ "version" của chính gói (1 chỗ ở package.json, 2 chỗ ở lock), không đụng phụ thuộc nào.
        assert text.count(f'"version": "{new}"') - was.count(f'"version": "{new}"') == (2 if "lock" in lock else 1), lock
        assert len(text) == len(was) + (len(new) - len(old)) * (2 if "lock" in lock else 1), lock
    lock, was = (root / "uv.lock").read_text(encoding="utf-8"), before["uv.lock"].decode("utf-8")
    assert re.search(rf'name = "abook"\r?\nversion = "{re.escape(new)}"', lock), "uv.lock: mục của chính gói"
    assert len(lock) == len(was) + len(new) - len(old), "uv.lock: chỉ một chỗ đổi"
    gradle = (root / "mobile/android/app/build.gradle").read_text(encoding="utf-8")
    assert f"versionCode {code + 1}" in gradle and f'versionName "{new}"' in gradle
    changelog = (root / "docs/CHANGELOG.md").read_text(encoding="utf-8")
    assert f"## [Chưa phát hành]\n\n## [{new}] - 2026-10-01\n" in changelog
    for relative in FILES:  # kiểu xuống dòng giữ nguyên
        assert (root / relative).read_bytes().count(b"\r\n") == before[relative].count(b"\r\n"), relative


def test_bump_refuses_the_same_or_a_malformed_version(tmp_path: Path) -> None:
    root = _copy(tmp_path)
    with pytest.raises(AssertionError):
        release.bump(release.current_version(root), root)
    with pytest.raises(AssertionError):
        release.bump("0.4", root)


def test_release_notes_carry_the_changelog_section_and_the_machine_requirements(tmp_path: Path) -> None:
    (tmp_path / "_internal/docs").mkdir(parents=True)
    (tmp_path / "README.md").write_text("# ABook\n\n## Yêu cầu máy\n\n- Windows 11, card 8 GB.\n\n## Cài đặt\n\nx\n",
                                        encoding="utf-8")
    (tmp_path / "_internal/docs/CHANGELOG.md").write_text(
        "# Nhật ký\n\n## [Chưa phát hành]\n\n## [9.9.9] - 2026-10-01\n\n### Studio\n\n- Một điều mới.\n\n## [9.9.8] - x\n\n- cũ\n",
        encoding="utf-8")
    notes = release.release_notes("9.9.9", tmp_path)
    assert "ABook_9.9.9_x64-setup.exe" in notes and "- Windows 11, card 8 GB." in notes
    assert "- Một điều mới." in notes and "- cũ" not in notes
    with pytest.raises(AssertionError):
        release.release_notes("9.9.7", tmp_path)
