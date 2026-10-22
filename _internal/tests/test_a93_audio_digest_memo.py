"""a93 #1: dấu băm audio nhớ đủ mọi file (không trần LRU) và sống qua lần khởi động lại app."""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

from abook.webui import audio_revision


def _aged(path: Path) -> None:
    old = time.time() - 3600
    os.utime(path, (old, old))


def _files(folder: Path, count: int) -> list[Path]:
    folder.mkdir(parents=True, exist_ok=True)
    out = []
    for number in range(count):
        file = folder / f"{number}.mp3"
        file.write_bytes(bytes([number % 251]) * 300 + number.to_bytes(4, "big"))
        _aged(file)
        out.append(file)
    return out


def _count_reads(monkeypatch) -> list[Path]:
    reads: list[Path] = []
    real_open = Path.open
    monkeypatch.setattr(Path, "open", lambda self, mode="r", *a, **k: (reads.append(self) if mode == "rb" else None, real_open(self, mode, *a, **k))[1])
    return reads


def test_a_library_bigger_than_the_old_limit_is_hashed_once(tmp_path, monkeypatch):
    audio_revision.configure(None)
    files = _files(tmp_path / "audio", 30)
    reads = _count_reads(monkeypatch)
    for _round in range(3):
        for file in files:
            audio_revision.describe(file)
    assert len(reads) == 30, "quét tuần tự cả thư viện nhiều lượt: mỗi file chỉ đọc đúng một lần"
    assert len(audio_revision._MEMO) == 30


def test_digests_survive_an_app_restart_and_a_changed_file_is_hashed_again(tmp_path, monkeypatch):
    store = tmp_path / "prefs" / "audio_digests.json"
    files = _files(tmp_path / "audio", 12)
    audio_revision.configure(store)
    first = {file: audio_revision.describe(file) for file in files}
    audio_revision._flush()
    assert store.is_file()
    audio_revision.configure(store)  # "khởi động lại": bảng trong RAM bị bỏ, nạp lại từ đĩa
    reads = _count_reads(monkeypatch)
    assert {file: audio_revision.describe(file) for file in files} == first
    assert reads == [], "không đọc lại file nào chưa đổi"
    files[3].write_bytes(b"z" * 400)
    _aged(files[3])
    assert audio_revision.describe(files[3])["sha256"] == hashlib.sha256(b"z" * 400).hexdigest()
    assert reads == [files[3]]


def test_a_corrupt_store_is_ignored_and_files_are_hashed_again(tmp_path):
    store = tmp_path / "audio_digests.json"
    store.write_bytes(b'{"files": {"x": [1, 2, "short"]')  # ghi dở
    file = _files(tmp_path / "audio", 1)[0]
    audio_revision.configure(store)
    assert audio_revision._MEMO == {}
    assert audio_revision.describe(file)["sha256"] == hashlib.sha256(file.read_bytes()).hexdigest()
    audio_revision.configure(None)  # bỏ bảng đang giữ, khỏi bị ghi đè lên file thử
    store.write_bytes(json.dumps({"files": {str(file): ["a", "b", "c"], "y": 5}}).encode())  # đúng JSON, sai hình dạng
    audio_revision.configure(store)
    assert audio_revision._MEMO == {}


def test_entries_of_deleted_files_are_dropped_when_saved(tmp_path):
    store = tmp_path / "audio_digests.json"
    files = _files(tmp_path / "audio", 4)
    audio_revision.configure(store)
    for file in files:
        audio_revision.describe(file)
    files[1].unlink()
    audio_revision._flush()
    saved = json.loads(store.read_bytes().decode("utf-8"))["files"]
    assert set(saved) == {os.path.abspath(f) for f in (files[0], files[2], files[3])}
    assert os.path.abspath(files[1]) not in audio_revision._MEMO


def test_a_file_written_a_moment_ago_is_still_not_remembered(tmp_path):
    audio_revision.configure(tmp_path / "audio_digests.json")
    file = tmp_path / "new.mp3"
    file.write_bytes(b"a" * 100)
    audio_revision.describe(file)
    assert audio_revision._MEMO == {}
