"""Batch files of the Qt app stay ASCII.

cmd reads a .bat in the OEM code page and re-reads it by offset after every `call`; with LF endings a UTF-8 letter of two or
three bytes shifts that offset, and cmd resumes in the middle of a line. On 31-10 one comment ("Không tìm được") in build.bat
made every later step fail with "'thon' is not recognized" / "'rrorlevel' is not recognized" right after `call vcvars`.
"""
from pathlib import Path

QT = Path(__file__).resolve().parents[1] / "desktop_qt"


def non_ascii_lines(text: str) -> list[int]:
    return [number for number, line in enumerate(text.splitlines(), 1) if any(ord(char) > 127 for char in line)]


def test_checker_finds_a_vietnamese_comment():
    assert non_ascii_lines('rem ok\nrem 31-10 ("Không tìm được")\nset A=1\n') == [2]
    assert non_ascii_lines("rem plain ascii\r\nset A=1\n") == []


def test_every_qt_batch_file_is_ascii():
    batches = sorted(path for path in QT.rglob("*.bat") if "build" not in path.relative_to(QT).parts[:1])
    assert batches, "no .bat found under desktop_qt"
    found = {str(path.relative_to(QT)): lines for path in batches if (lines := non_ascii_lines(path.read_text(encoding="utf-8")))}
    assert not found, f"non-ASCII lines in batch files (cmd misreads them after `call`): {found}"
