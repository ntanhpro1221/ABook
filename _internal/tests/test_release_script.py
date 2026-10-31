"""scripts/release.py: nâng số phiên bản đúng 6 file (chạy trên bản sao các file thật) và ghi chú GitHub Release - 2026-10-01."""
from __future__ import annotations

import datetime
import importlib.util
import json
import re
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("release_script", ROOT / "scripts/release.py")
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)

FILES = ["pyproject.toml", "uv.lock", "ui/package.json", "ui/package-lock.json",
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
    for lock in ("ui/package-lock.json", "ui/package.json"):
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
    unreleased = changelog.index("## [Chưa phát hành]\n")
    assert changelog.index(f"\n## [{new}] - 2026-10-01\n") > unreleased
    assert changelog.count("## [Chưa phát hành]") == 1
    for relative in FILES:  # kiểu xuống dòng giữ nguyên
        assert (root / relative).read_bytes().count(b"\r\n") == before[relative].count(b"\r\n"), relative


def test_bump_leaves_what_the_installer_does_not_have_under_unreleased() -> None:
    text = ("# x\n\n## [Chưa phát hành]\n\n### Máy tính\n\n- Sửa bộ gỡ.\n\n### Máy tính (bản Qt, chưa có trong bộ cài)\n\n- Khay.\n\n"
            "### Điện thoại\n\n- Giải thích.\n\n## [1.0.0] - x\n\n- cũ\n")
    cut = release.changelog_cut(text, "1.0.1", "2026-10-31")
    assert cut == ("# x\n\n## [Chưa phát hành]\n\n### Máy tính (bản Qt, chưa có trong bộ cài)\n\n- Khay.\n\n"
                   "## [1.0.1] - 2026-10-31\n\n### Máy tính\n\n- Sửa bộ gỡ.\n\n### Điện thoại\n\n- Giải thích.\n\n## [1.0.0] - x\n\n- cũ\n")
    # Không gì giữ lại: như trước.
    assert release.changelog_cut("## [Chưa phát hành]\n\n- Mới.\n\n## [1.0.0] - x\n", "1.0.1", "d") == \
        "## [Chưa phát hành]\n\n## [1.0.1] - d\n\n- Mới.\n\n## [1.0.0] - x\n"


def test_release_notes_refuse_a_section_the_installer_does_not_have(tmp_path: Path) -> None:
    (tmp_path / "_internal/docs").mkdir(parents=True)
    (tmp_path / "README.md").write_text("# ABook\n\n## Yêu cầu máy\n\n- Windows.\n\n## Cài đặt\n", encoding="utf-8")
    (tmp_path / "_internal/docs/CHANGELOG.md").write_text(
        "# x\n\n## [9.9.9] - d\n\n### Máy tính (bản Qt, chưa có trong bộ cài)\n\n- Khay.\n\n## [9.9.8] - x\n", encoding="utf-8")
    with pytest.raises(AssertionError):
        release.release_notes("9.9.9", tmp_path)


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


def test_release_notes_measure_the_installer_instead_of_a_fixed_size(tmp_path: Path) -> None:
    (tmp_path / "_internal/docs").mkdir(parents=True)
    (tmp_path / "README.md").write_text("# ABook\n\n## Yêu cầu máy\n\n- Windows.\n\n## Cài đặt\n", encoding="utf-8")
    (tmp_path / "_internal/docs/CHANGELOG.md").write_text("# x\n\n## [9.9.9] - d\n\n- Mới.\n\n## [9.9.8] - x\n", encoding="utf-8")
    out = tmp_path / "out"
    out.mkdir()
    assert "MB" not in release.release_notes("9.9.9", tmp_path, out)
    (out / "ABook_9.9.9_x64-setup.exe").write_bytes(b"0" * 19_600_000)
    assert "khoảng 20 MB, không cần quyền quản trị" in release.release_notes("9.9.9", tmp_path, out)


class _InstallerBuilt(Exception):
    """Fake _run reached the APK step: the installer half of build() passed."""


def _fake_build(monkeypatch, tmp_path: Path, files: dict[str, str]) -> list[list[str]]:
    # build() up to the APK with a fake _run: the Qt installer step writes `files` where build.bat installer puts its output.
    calls: list[list[str]] = []
    monkeypatch.setattr(release, "ROOT", tmp_path)
    monkeypatch.setattr(release, "current_version", lambda *_: "9.9.9")
    for name in ("check_studio_assets_pinned", "check_word_align_pinned", "check_speaker_model_pinned"):
        monkeypatch.setattr(release, name, lambda: None)

    def run(command, cwd, env=None, low=False):
        calls.append([str(part) for part in command])
        if command[0].endswith("gradlew.bat"):
            raise _InstallerBuilt
        assert env["ABOOK_PYTHON"]
        built = tmp_path / "desktop_qt/build/installer"
        built.mkdir(parents=True, exist_ok=True)
        for name, text in files.items():
            (built / name).write_text(text, encoding="utf-8")
    monkeypatch.setattr(release, "_run", run)
    return calls


def _installer_files(version="9.9.9", signature="sig-of-9.9.9", manifest_signature=None) -> dict[str, str]:
    manifest = {"version": version, "platforms": {"windows-x86_64": {"signature": manifest_signature or signature}}}
    return {"ABook_9.9.9_x64-setup.exe": "MZ", "ABook_9.9.9_x64-setup.exe.sig": signature + "\n", "latest.json": json.dumps(manifest)}


def test_build_makes_the_windows_installer_with_the_qt_build_only(monkeypatch, tmp_path: Path) -> None:
    calls = _fake_build(monkeypatch, tmp_path, _installer_files())
    with pytest.raises(_InstallerBuilt):
        release.build("9.9.9", tmp_path / "out")
    assert calls[0] == ["cmd", "/c", str(tmp_path / "desktop_qt/build.bat"), "installer"]
    assert not any("build_windows_app" in part or "tauri" in part.lower() for call in calls for part in call)
    assert sorted(path.name for path in (tmp_path / "out").iterdir()) == sorted(_installer_files())


@pytest.mark.parametrize("files, why", [
    ({name: text for name, text in _installer_files().items() if not name.endswith(".sig")}, "bộ cài thiếu"),
    (_installer_files(version="9.9.8"), "latest.json ghi 9.9.8"),
    (_installer_files(manifest_signature="sig-of-another-build"), "chữ ký khác file .sig"),
])
def test_build_refuses_an_incomplete_or_mismatched_installer(monkeypatch, tmp_path: Path, files, why) -> None:
    _fake_build(monkeypatch, tmp_path, files)
    with pytest.raises(AssertionError, match=why):
        release.build("9.9.9", tmp_path / "out")
