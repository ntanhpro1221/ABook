"""Nội dung chương, không phải cỡ file, quyết định bản thu."""
import hashlib
import json
from pathlib import Path

from abook.webui import remote_books, sync, store
from abook.webui.listening import Listening
from tests.test_webui_listen_and_sync import make_project


def test_manifest_and_library_detect_equal_size_audio_change(tmp_path):
    project = make_project(tmp_path)
    listening = Listening(tmp_path / "listening.json")
    first = sync.manifest(project, "book", listening)
    audio = store.chapter_audio_paths(project)[1]
    data = audio.read_bytes()
    audio.write_bytes(bytes([data[0] ^ 1]) + data[1:])
    second = sync.manifest(project, "book", listening)
    assert first["version"] != second["version"]
    assert second["chapters"][0]["sha256"] == hashlib.sha256(audio.read_bytes()).hexdigest()


def test_library_carries_the_same_audio_revision_as_manifest(tmp_path):
    from abook.webui.library import Library, Preferences, book_id
    project = make_project(tmp_path / "library")
    preferences = Preferences(tmp_path / "preferences.json")
    preferences.update({"libraryRoot": str(project.parent)})
    listening = Listening(tmp_path / "listening.json")
    app = sync.SyncApp(Library(preferences), listening, sync.Devices(tmp_path / "devices.json"), "Máy thử")
    entry = app.library_view()[0]
    assert entry["audioVersion"] == sync.manifest(project, book_id(project), listening)["audioVersion"]
    audio = store.chapter_audio_paths(project)[1]
    data = audio.read_bytes()
    audio.write_bytes(data[1:] + data[:1])
    assert app.library_view()[0]["audioVersion"] != entry["audioVersion"]


def test_desktop_only_downloads_changed_chapter(tmp_path):
    from abook.webui.audio_revision import describe
    chapters = []
    for number in (1, 2):
        relative = f"chapters/{number}.mp3"
        file = tmp_path / relative
        file.parent.mkdir(exist_ok=True)
        file.write_bytes(b"old")
        chapters.append({"id": number, "file": relative, "available": True, **describe(file)})
    book = {"version": "new", "chapters": chapters}
    chapters[1]["sha256"] = hashlib.sha256(b"new").hexdigest()
    assert remote_books.missing(tmp_path, book) == [("chapters/2.mp3", 3)]


def test_desktop_does_not_play_a_stale_cached_chapter(tmp_path, monkeypatch):
    from abook.webui import packages
    relative = "chapters/1.mp3"
    old = tmp_path / relative
    old.parent.mkdir()
    old.write_bytes(b"old")
    book = {"chapters": [{"id": 1, "available": True, "file": relative,
             "size": 3, "sha256": hashlib.sha256(b"new").hexdigest()}],
             "package": {"remote": {"computer": "other", "book": "book"}, "files": {}}}
    (tmp_path / "book.json").write_text(json.dumps(book), encoding="utf-8")
    fetched = []
    def fetch(folder, name, _book, **_kwargs):
        fetched.append(name)
        (folder / name).write_bytes(b"new")
    monkeypatch.setattr(remote_books, "fetch", fetch)
    assert packages.chapter_file(tmp_path, 1).read_bytes() == b"new"
    assert fetched == [relative]
    assert packages.chapter_file(tmp_path, 1).read_bytes() == b"new"
    assert fetched == [relative], "chương đúng dấu được dùng lại"


def test_windows_extended_prefix_is_canonical_before_containment(tmp_path, monkeypatch):
    import os
    import pytest
    from abook.webui.peer_paths import canonical
    if os.name != "nt":
        pytest.skip("Windows path form")
    file = tmp_path / "scripts/1.json"
    resolved = Path("\\\\?\\" + str(file))
    monkeypatch.setattr(Path, "resolve", lambda self: resolved if self == file else self)
    assert canonical(file).is_relative_to(canonical(tmp_path))


def _aged(file: Path, seconds: float = 3600) -> None:
    """File đã nguội: bộ đệm chỉ tin (cỡ, mtime) khi file không vừa mới ghi."""
    import os, time
    old = time.time() - seconds
    os.utime(file, (old, old))


def test_describe_remembers_the_digest_until_the_file_changes(tmp_path, monkeypatch):
    import os
    from abook.webui import audio_revision
    audio = tmp_path / "1.mp3"
    audio.write_bytes(b"a" * 5000)
    _aged(audio)
    reads = []
    real_open = Path.open
    monkeypatch.setattr(Path, "open", lambda self, mode="r", *a, **k: (reads.append(self) if mode == "rb" else None, real_open(self, mode, *a, **k))[1])
    first = audio_revision.describe(audio)
    assert audio_revision.describe(audio) == first and audio_revision.matches(audio, 5000, first["sha256"])
    assert len(reads) == 1, "lần sau chỉ stat, không đọc lại file"
    audio.write_bytes(b"b" * 5000)  # cùng cỡ, nội dung khác
    stat = audio.stat()
    os.utime(audio, ns=(stat.st_atime_ns, stat.st_mtime_ns - 10_000_000_000))
    changed = audio_revision.describe(audio)
    assert len(reads) == 2 and changed["sha256"] == hashlib.sha256(b"b" * 5000).hexdigest()
    audio.write_bytes(b"c" * 6000)  # cỡ đổi cũng băm lại
    assert audio_revision.describe(audio)["sha256"] == hashlib.sha256(b"c" * 6000).hexdigest()
    assert len(reads) == 3


def test_describe_does_not_trust_a_file_written_a_moment_ago(tmp_path):
    from abook.webui import audio_revision
    audio = tmp_path / "1.mp3"
    audio.write_bytes(b"a" * 100)
    first = audio_revision.describe(audio)
    mtime = audio.stat().st_mtime_ns
    audio.write_bytes(b"b" * 100)
    import os
    os.utime(audio, ns=(mtime, mtime))  # đồng hồ file thô: hai lần ghi trùng mtime, cùng cỡ
    assert audio_revision.describe(audio)["sha256"] != first["sha256"]


def test_digest_cache_is_thread_safe(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from abook.webui import audio_revision
    files = []
    for number in range(8):
        file = tmp_path / f"{number}.mp3"
        file.write_bytes(bytes([number]) * 300)
        _aged(file)
        files.append(file)
    with ThreadPoolExecutor(4) as pool:
        digests = list(pool.map(lambda file: audio_revision.describe(file)["sha256"], files * 5))
    assert digests[:8] == [hashlib.sha256(bytes([n]) * 300).hexdigest() for n in range(8)]


def test_manifest_does_not_hash_unchanged_audio_twice(tmp_path, monkeypatch):
    project = make_project(tmp_path)
    listening = Listening(tmp_path / "listening.json")
    for audio in store.chapter_audio_paths(project).values():
        _aged(audio)
    sync.manifest(project, "book", listening)
    reads = []
    real_open = Path.open
    monkeypatch.setattr(Path, "open", lambda self, mode="r", *a, **k: (reads.append(self) if self.suffix == ".mp3" and mode == "rb" else None, real_open(self, mode, *a, **k))[1])
    sync.manifest(project, "book", listening)
    assert reads == []
