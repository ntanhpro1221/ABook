import zipfile
import threading
from pathlib import Path

import pytest

from abook.webui import music_module as music, studio_setup as studio


def test_interrupted_wheels_are_never_activated(tmp_path, monkeypatch):
    monkeypatch.setattr(music, "_folder", tmp_path)
    monkeypatch.setattr(music, "_libs_loaded", lambda: False)
    monkeypatch.setattr(music, "_register_path", lambda _: True)
    old = tmp_path / "lib/old.txt"
    old.parent.mkdir()
    old.write_text("old")
    calls = []

    def download(item, target, *_):
        calls.append(item.name)
        if len(calls) == 2:
            raise studio.Cancelled()
        target.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(target, "w") as bundle:
            bundle.writestr(f"{item.name}/__init__.py", b"new")
        return target

    monkeypatch.setattr(studio, "download", download)
    with pytest.raises(studio.Cancelled):
        music._install_libs(lambda *_: None, lambda: False)
    music.activate_libs()
    assert old.is_file()
    assert not (tmp_path / "lib/numpy").exists()


def test_two_callers_share_one_ffmpeg_download(tmp_path, monkeypatch):
    from abook.webui import ffmpeg_setup as ff
    monkeypatch.setattr(ff, "_folder", tmp_path)
    entered, release, second_started = threading.Event(), threading.Event(), threading.Event()
    calls, errors, results = [], [], []

    def download(_item, target, *_):
        calls.append("download")
        entered.set()
        assert release.wait(5)
        with zipfile.ZipFile(target, "w") as bundle:
            bundle.writestr(ff.MEMBER, b"fake exe")
        return target

    monkeypatch.setattr(studio, "download", download)
    monkeypatch.setattr(ff.io_utils, "use_downloaded_ffmpeg", lambda _: None)

    def run(second=False):
        if second:
            second_started.set()
        try:
            results.append(ff.install(lambda *_: None))
        except Exception as error:
            errors.append(error)

    a = threading.Thread(target=run)
    b = threading.Thread(target=lambda: run(True))
    a.start()
    assert entered.wait(5)
    b.start()
    assert second_started.wait(5)
    # Both jobs have been submitted; release the writer to let a waiting caller finish.
    release.set()
    a.join(5)
    b.join(5)
    assert not a.is_alive() and not b.is_alive()
    assert errors == []
    assert calls == ["download"]
    assert len(results) == 2


def test_unstamped_lib_next_does_not_replace_old_lib(tmp_path, monkeypatch):
    monkeypatch.setattr(music, "_folder", tmp_path)
    monkeypatch.setattr(music, "_libs_loaded", lambda: False)
    monkeypatch.setattr(music, "_register_path", lambda _: True)
    old = tmp_path / "lib/old.txt"
    old.parent.mkdir()
    old.write_text("old")
    (tmp_path / "lib.next").mkdir()
    music.activate_libs()
    assert old.is_file()


def test_n1_observation_interrupted_pair_can_mix_versions(tmp_path, monkeypatch):
    """Evidence of mechanism only; no claim that real model versions are incompatible."""
    from abook.webui import voice_module
    part = music.Component("model", "model", "new", 6, True, downloads=[
        studio.Download("a", "https://invalid.invalid/a", "unused", 3),
        studio.Download("b", "https://invalid.invalid/b", "unused", 3)])
    (tmp_path / "a").write_bytes(b"old")
    (tmp_path / "b").write_bytes(b"old")

    def download(item, target, *_):
        if item.name == "b":
            raise studio.Cancelled()
        target.write_bytes(b"new")
        return target

    monkeypatch.setattr(studio, "download", download)
    with pytest.raises(studio.Cancelled):
        voice_module.download_files(part, tmp_path, lambda *_: None)
    assert [(tmp_path / name).read_bytes() for name in ("a", "b")] == [b"new", b"old"]
