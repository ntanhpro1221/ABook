"""The upstream audit compares PyPI against the pins on origin/main, not against whichever checkout runs it.

11-10: the audit ran from an old checkout (0.4.10) and read that checkout's pyproject.toml. It flagged timm, vieneu
and sea-g2p as outdated although main already pinned their newest releases. The pins now come from the ref
(`git show origin/main:./pyproject.toml`), and only fall back to the file on disk when git cannot answer.
"""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import check_dependency_updates as checker

MAIN_CONTRACT = 'VIENEU_CACHE_REVISION = "aaaaaaaaaaaa1111"\n'
OLD_CONTRACT = 'VIENEU_CACHE_REVISION = "bbbbbbbbbbbb2222"\n'


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@t", *args], check=True,
                   capture_output=True)


def _checkout(tmp_path: Path, monkeypatch) -> Path:
    """A repo whose `main` pins timm 1.0.30, and whose working tree is still the old checkout (timm 1.0.29)."""
    inner = tmp_path / "_internal"
    (inner / "abook").mkdir(parents=True)
    _git(tmp_path, "init", "-q", "-b", "main")
    (inner / "pyproject.toml").write_text('dependencies = [\n  "timm==1.0.30",\n]\n', encoding="utf-8")
    (inner / "abook" / "runtime_contract.py").write_text(MAIN_CONTRACT, encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "main")
    (inner / "pyproject.toml").write_text('dependencies = [\n  "timm==1.0.29",\n]\n', encoding="utf-8")
    (inner / "abook" / "runtime_contract.py").write_text(OLD_CONTRACT, encoding="utf-8")
    monkeypatch.setattr(checker, "PYPROJECT", inner / "pyproject.toml")
    return inner


def test_pins_come_from_the_ref_not_from_the_old_checkout(tmp_path, monkeypatch):
    _checkout(tmp_path, monkeypatch)
    assert checker.read_pins("main") == [("timm", "1.0.30")]


def test_without_a_ref_the_file_on_disk_is_read(tmp_path, monkeypatch):
    _checkout(tmp_path, monkeypatch)
    assert checker.read_pins("") == [("timm", "1.0.29")]


def test_a_ref_git_does_not_know_falls_back_to_the_file_on_disk(tmp_path, monkeypatch):
    _checkout(tmp_path, monkeypatch)
    assert checker.read_pins("origin/no-such-branch") == [("timm", "1.0.29")]


def test_model_revisions_also_come_from_the_ref(tmp_path, monkeypatch):
    _checkout(tmp_path, monkeypatch)
    assert checker.pinned_revision("VIENEU_CACHE_REVISION", "main") == "aaaaaaaaaaaa1111"
    assert checker.pinned_revision("VIENEU_CACHE_REVISION", "") == "bbbbbbbbbbbb2222"
    assert checker.pinned_revision("NO_SUCH_REVISION", "main") == ""


def test_the_default_ref_is_origin_main():
    assert checker.PINS_REF == "origin/main"
