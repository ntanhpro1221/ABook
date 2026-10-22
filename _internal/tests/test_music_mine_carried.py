"""Sách chọn "Nhạc của tôi" mang theo đúng các bài đã chọn (file + thứ tự + thông tin bài) trong file `.abook`, như bài người nghe đã ghim: máy nhận
phát bản của cuốn, không giải lại từ kho riêng của nó (soát a103 F3)."""
from __future__ import annotations

import json
import threading
import wave
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from abook.webui import book_edits, bookfile, music_local, packages
from abook.webui.server import App


def _wav(path: Path, sample: int) -> Path:
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(8000)
        handle.writeframes(bytes([sample, 0]) * 8000)
    return path


def _text_book(folder: Path) -> Path:
    folder.mkdir()
    (folder / "texts").mkdir()
    text = folder / "texts/1.txt"
    text.write_bytes("Chuong mot. Ban dang nghe truyen.".encode("utf-8"))
    book = {"title": "Sach chu", "author": "Tac gia", "chapters": [{"id": 1, "index": 1, "title": "Chuong 1", "text": "texts/1.txt", "state": "text"}]}
    archive = folder.parent / (folder.name + ".abook")
    bookfile.seal(book, {"texts/1.txt": text}, archive, producer="Audit", version=5)
    with bookfile.BookFile(archive) as opened:
        return opened.extract(folder.parent / (folder.name + "-imported"))


def _app(folder: Path, store: music_local.LocalMusic) -> App:
    app = object.__new__(App)
    app._editable = app._book = app._listenable = lambda value: folder
    app._moods_lock = threading.RLock()
    app._music_taxonomy = lambda: {}
    app.music_track_cached = lambda link: None
    app.music_track_available = lambda link, **kw: True
    app.preferences = SimpleNamespace(get=lambda: {"autoMusic": True})
    app.my_music = store
    return app


def _mine(store: music_local.LocalMusic):
    return lambda: [(info, store.file(info["link"])) for info in reversed(store.entries()) if store.file(info["link"]) is not None]


@pytest.fixture(autouse=True)
def _quiet(monkeypatch):
    monkeypatch.setattr(music_local, "_measures", lambda path: {})
    monkeypatch.setattr(music_local, "analyze", lambda path: None)


def _store(tmp_path: Path, name: str, *samples: int) -> tuple[music_local.LocalMusic, list[str]]:
    store = music_local.LocalMusic(tmp_path / name)
    links = [store.import_file(_wav(tmp_path / f"{name}{n}.wav", n))[0]["link"] for n in samples]
    return store, links


def test_a_book_saved_with_my_music_carries_the_chosen_tracks_to_the_receiver(tmp_path: Path) -> None:
    folder = _text_book(tmp_path / "source")
    owner, links = _store(tmp_path, "owner", 1, 2)
    receiver_store, [other] = _store(tmp_path, "receiver", 9)
    book_edits.set_music(folder, {"playlist": "mine"}, mine=_mine(owner))
    saved = tmp_path / "chosen.abook"
    bookfile.repack(folder, saved)
    with zipfile.ZipFile(saved) as archive:
        names = set(archive.namelist())
    assert {f"music/{link.split(':')[1]}.wav" for link in links} <= names, "gói không mang file nhạc của những bài đã chọn"
    with bookfile.BookFile(saved) as opened:
        arrived = opened.extract(tmp_path / "arrived")
    app = _app(arrived, receiver_store)
    queue = app.music_playlist_queue("book")
    assert queue["playlist"] == "mine"
    assert [track["link"] for track in queue["tracks"]] == links, "máy nhận phát bài của kho riêng của nó, không phải bài của cuốn"
    assert other not in [track["link"] for track in queue["tracks"]]
    for track in queue["tracks"]:
        assert track["src"].startswith("/api/books/book/music/files/")
        assert packages.music_file(arrived, "music/" + track["src"].rsplit("/", 1)[1]).is_file()
    empty_receiver = _app(arrived, music_local.LocalMusic(tmp_path / "bare"))
    assert [track["link"] for track in empty_receiver.music_playlist_queue("book")["tracks"]] == links


def test_choosing_another_playlist_drops_the_carried_tracks(tmp_path: Path) -> None:
    folder = _text_book(tmp_path / "source")
    owner, links = _store(tmp_path, "owner", 1, 2)
    book_edits.set_music(folder, {"playlist": "mine"}, mine=_mine(owner))
    files = [folder / f"music/{link.split(':')[1]}.wav" for link in links]
    assert all(path.is_file() for path in files)
    book_edits.set_music(folder, {"playlist": "calm"}, mine=_mine(owner))
    edits = book_edits.load(folder)
    assert "mine" not in edits["music"] and "tracks" not in edits["music"]
    assert not any(path.exists() for path in files)


def test_choosing_my_music_again_takes_the_current_tracks(tmp_path: Path) -> None:
    folder = _text_book(tmp_path / "source")
    owner, links = _store(tmp_path, "owner", 1)
    book_edits.set_music(folder, {"playlist": "mine"}, mine=_mine(owner))
    added = owner.import_file(_wav(tmp_path / "later.wav", 3))[0]["link"]
    book_edits.set_music(folder, {"playlist": "mine"}, mine=_mine(owner))
    assert book_edits.load(folder)["music"]["mine"] == [link.split(":")[1] for link in [*links, added]]


def test_the_carried_list_is_read_back_only_with_its_choice_and_files() -> None:
    sha = "0" * 40
    track = {"ext": "wav"}
    ok = {"format": book_edits.FORMAT, "version": book_edits.VERSION, "music": {"playlist": "mine", "mine": [sha], "tracks": {sha: track}}}
    assert book_edits.validate(json.loads(json.dumps(ok)))["music"]["mine"] == [sha]
    for broken in ({"playlist": "calm", "mine": [sha], "tracks": {sha: track}}, {"playlist": "mine", "mine": [sha, sha], "tracks": {sha: track}},
                   {"playlist": "mine", "mine": [sha]}, {"playlist": "mine", "mine": ["x"], "tracks": {"x": track}}):
        with pytest.raises(book_edits.EditsError):
            book_edits.validate({**ok, "music": broken})


def test_the_carried_list_follows_its_choice_through_merge_and_send(tmp_path: Path) -> None:
    sha = "1" * 40
    mine = {"music": {"playlist": "mine", "mine": [sha], "tracks": {sha: {"ext": "wav"}}}}
    plain = {"music": {"levelDb": -24.0}}
    merged, _report = book_edits.merge(book_edits.validate({**book_edits.empty(), **plain}), book_edits.validate({**book_edits.empty(), **mine}))
    assert merged["music"]["mine"] == [sha] and merged["music"]["tracks"] == {sha: {"ext": "wav"}}
    folder = _text_book(tmp_path / "source")
    owner, _links = _store(tmp_path, "owner", 1)
    book_edits.set_music(folder, {"playlist": "mine"}, mine=_mine(owner))
    sent = book_edits.load(folder)
    book_edits.subtract(folder, sent, None)
    assert book_edits.load(folder)["music"]["mine"] == sent["music"]["mine"], "gửi đi rồi mà bài đã chọn mất khỏi sách"
