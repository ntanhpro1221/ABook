"""a101 F4: chỗ nghe (progress, mỗi ~10 giây) ghi nối vào nhật ký, không ghi lại cả hồ sơ; tắt ngang vẫn đọc lại thấy chỗ nghe mới nhất."""
from __future__ import annotations

import json
from pathlib import Path

from abook.webui import listening as module
from abook.webui.listening import JOURNAL_MAX_LINES, Listening


def _journal(path: Path) -> Path:
    return path.with_name(path.name + module.JOURNAL_SUFFIX)


def _started(tmp_path: Path) -> tuple[Listening, Path]:
    path = tmp_path / "listening.json"
    listening = Listening(path)
    listening.begin_progress("sach", "tab-1")
    return listening, path


def test_progress_appends_to_the_journal_and_does_not_rewrite_the_profile(tmp_path: Path) -> None:
    listening, path = _started(tmp_path)
    base = path.read_bytes()
    for number in range(1, 6):
        listening.progress("sach", 3, 100.0 + number, 1300.0, session_id="tab-1", revision=number)
    assert path.read_bytes() == base, "hồ sơ không bị ghi lại mỗi lần báo chỗ nghe"
    assert len(_journal(path).read_text(encoding="utf-8").split()) == 5
    assert listening.get("sach")["last"]["seconds"] == 105.0


def test_a_crash_before_any_full_save_still_reads_the_latest_place(tmp_path: Path) -> None:
    listening, path = _started(tmp_path)
    listening.progress("sach", 3, 812.4, 1300.0, session_id="tab-1", revision=1)
    listening.progress("sach", 4, 12.0, 900.0, anchor=None, session_id="tab-1", revision=2)
    reopened = Listening(path)  # tiến trình cũ chết: không ai gộp nhật ký
    state = reopened.get("sach")
    assert state["last"]["chapterId"] == 4 and state["last"]["seconds"] == 12.0
    assert state["chapters"]["3"]["heard"] == 812.4 and state["chapters"]["4"]["duration"] == 900.0
    assert reopened.progress("sach", 4, 30.0, 900.0)["last"]["seconds"] == 30.0


def test_a_half_written_last_line_is_ignored_and_the_next_one_is_not_lost(tmp_path: Path) -> None:
    listening, path = _started(tmp_path)
    listening.progress("sach", 3, 50.0, 1300.0, session_id="tab-1", revision=1)
    with open(_journal(path), "ab") as handle:
        handle.write(b'{"record":"r-0","chapter":3,"seco')  # tắt máy giữa lúc ghi
    reopened = Listening(path)
    assert reopened.get("sach")["last"]["seconds"] == 50.0
    reopened.progress("sach", 3, 70.0, 1300.0)
    assert Listening(path).get("sach")["last"]["seconds"] == 70.0


def test_every_other_save_folds_the_journal_into_the_profile(tmp_path: Path) -> None:
    listening, path = _started(tmp_path)
    listening.progress("sach", 3, 50.0, 1300.0, session_id="tab-1", revision=1)
    assert _journal(path).exists()
    listening.set_rate("sach", 1.25)
    assert not _journal(path).exists()
    saved = json.loads(path.read_text(encoding="utf-8"))
    (record,) = saved["records"].values()
    assert record["state"]["last"]["seconds"] == 50.0 and record["state"]["rate"] == 1.25


def test_the_journal_is_folded_after_enough_lines(tmp_path: Path) -> None:
    listening, path = _started(tmp_path)
    for number in range(1, JOURNAL_MAX_LINES + 1):
        listening.progress("sach", 3, float(number), 1300.0, session_id="tab-1", revision=number)
    assert not _journal(path).exists()
    (record,) = json.loads(path.read_text(encoding="utf-8"))["records"].values()
    assert record["state"]["last"]["seconds"] == float(JOURNAL_MAX_LINES)


def test_another_process_changing_the_profile_does_not_lose_the_place(tmp_path: Path) -> None:
    mine, path = _started(tmp_path)
    mine.progress("sach", 3, 50.0, 1300.0, session_id="tab-1", revision=1)
    other = Listening(path)  # tiến trình khác (CLI, bản app thứ hai) cùng hồ sơ
    other.set_rate("sach", 1.5)
    mine.progress("sach", 3, 90.0, 1300.0, session_id="tab-1", revision=2)
    merged = Listening(path).get("sach")
    assert merged["last"]["seconds"] == 90.0 and merged["rate"] == 1.5
    other.progress("sach", 3, 120.0, 1300.0)
    assert Listening(path).get("sach")["last"]["seconds"] == 120.0


def test_an_old_journal_line_does_not_roll_back_a_newer_place(tmp_path: Path) -> None:
    """Tắt ngang giữa lúc gộp (hồ sơ mới ghi xong, nhật ký chưa xoá) hay nhật ký của lần trước: dòng cũ hơn chỗ nghe đã có thì bỏ."""
    listening, path = _started(tmp_path)
    listening.progress("sach", 3, 50.0, 1300.0, session_id="tab-1", revision=1)
    stale = _journal(path).read_text(encoding="utf-8")
    listening.progress("sach", 3, 400.0, 1300.0, session_id="tab-1", revision=2)
    listening.set_rate("sach", 1.5)  # gộp: hồ sơ mang chỗ nghe 400
    _journal(path).write_text(stale, encoding="utf-8")
    assert Listening(path).get("sach")["last"]["seconds"] == 400.0


def test_the_first_report_of_a_new_book_is_written_in_full(tmp_path: Path) -> None:
    """Chưa có hồ sơ nghe của cuốn này trên đĩa: nhật ký không có hồ sơ để áp lên, nên lần đầu ghi đầy đủ."""
    path = tmp_path / "listening.json"
    listening = Listening(path)
    listening.progress("sach", 3, 10.0, 100.0)
    assert not _journal(path).exists()
    listening.progress("khac", 1, 5.0, 100.0)  # hồ sơ mới sinh của cuốn thứ hai
    assert not _journal(path).exists()
    listening.progress("sach", 3, 20.0, 100.0)
    assert _journal(path).exists()
    reopened = Listening(path)
    assert reopened.get("sach")["last"]["seconds"] == 20.0 and reopened.get("khac")["last"]["seconds"] == 5.0
