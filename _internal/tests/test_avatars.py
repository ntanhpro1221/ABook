"""Original character briefs only; no published book text."""
import hashlib
import io
import json
import sqlite3
import threading
from pathlib import Path

import pytest
from PIL import Image

from abook import avatars


def raster(color="red"):
    out = io.BytesIO()
    Image.new("RGB", (320, 280), color).save(out, format="PNG")
    return out.getvalue()


def person(name="MINH"):
    return {"canonical_name": name, "display_name": name.title(), "gender": "male", "age": "elderly"}


def test_extract_only_direct_appearance_and_preserve_text():
    text = "Minh có tóc bạc và đeo kính tròn. Lan có tóc đen. Minh gọi Lan có đôi mắt xanh. Minh nói: “tóc đỏ”."
    before = text.encode()
    assert avatars.appearance("Minh", text, ["Minh", "Lan"]) == ["Minh có tóc bạc và đeo kính tròn."]
    assert text.encode() == before
    assert avatars.appearance("Minh", "Minh nhìn Lan. Ông có tóc bạc.", ["Minh", "Lan"]) == []


def test_image_checkpoint_and_resume_do_not_call_model_twice(tmp_path):
    calls = []
    def render(prompt, seed):
        calls.append((prompt, seed)); return raster()
    first = avatars.generate(tmp_path, person(), ["Minh có tóc bạc."], renderer=render)
    second = avatars.generate(tmp_path, person(), [], renderer=render)
    assert first == second
    assert len(calls) == 1
    data = avatars.image_file(tmp_path, first["file"]).read_bytes()
    assert hashlib.sha256(data).hexdigest() == first["sha256"]
    with Image.open(io.BytesIO(data)) as image:
        assert image.size == (256, 256)
        assert not image.info.get("exif")


def test_user_choice_wins_during_inflight_regeneration(tmp_path):
    avatars.generate(tmp_path, person(), [], renderer=lambda *_: raster())
    entered, proceed = threading.Event(), threading.Event()
    def render(*_):
        entered.set(); assert proceed.wait(5); return raster("green")
    thread = threading.Thread(target=lambda: avatars.generate(tmp_path, person(), [], force=True, renderer=render))
    thread.start(); assert entered.wait(5)
    chosen = avatars.choose(tmp_path, "MINH", raster("blue"))
    proceed.set(); thread.join(5)
    assert not thread.is_alive()
    assert avatars.entries(tmp_path)["MINH"] == chosen
    assert avatars.generate(tmp_path, person(), [], renderer=lambda *_: pytest.fail("must preserve user choice")) == chosen


def test_failed_request_is_retryable_and_fallback_is_deterministic(tmp_path):
    def broken(*_): raise RuntimeError("offline")
    with pytest.raises(RuntimeError): avatars.generate(tmp_path, person(), [], renderer=broken)
    assert avatars.entries(tmp_path) == {}
    assert avatars.generate(tmp_path, person(), []) == avatars.fallback("MINH")
    assert avatars.fallback("Ngọc Linh") == avatars.fallback("Ngo\u0323c Linh")


@pytest.mark.parametrize("path", ["../escape.webp", "avatars/../escape.webp", "//server/a", "C:/x.webp", "avatars/" + "a" * 64 + ".svg"])
def test_media_rejects_paths_before_io(tmp_path, path):
    assert avatars.image_file(tmp_path, path) is None


def test_generation_cannot_write_analysis_or_casting_and_stops_after_checkpoint(tmp_path, monkeypatch):
    from abook.webui import store
    from abook.pipeline import PipelineStopped
    database = tmp_path / "test.sqlite"
    connection = sqlite3.connect(database)
    connection.executescript("CREATE TABLE segments(status TEXT); INSERT INTO segments VALUES('analyzed'); "
        "CREATE TABLE characters(id INTEGER,canonical_name TEXT,display_name TEXT,gender TEXT,age TEXT); "
        "INSERT INTO characters VALUES(1,'MINH','Minh','male','elderly'); "
        "INSERT INTO characters VALUES(2,'LAN','Lan','female','young'); CREATE TABLE chapters(id INTEGER);")
    connection.commit(); connection.close()
    before = database.read_bytes()
    def connect(_):
        connection = sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        return connection
    monkeypatch.setattr(store, "connect", connect)
    stopped = [False]
    def render(*_): stopped[0] = True; return raster()
    with pytest.raises(PipelineStopped):
        avatars.run_after_analysis(tmp_path, lambda: stopped[0], lambda _: None, renderer=render)
    assert list(avatars.entries(tmp_path)) == ["MINH"]
    avatars.run_after_analysis(tmp_path, lambda: False, lambda _: None, renderer=lambda *_: raster())
    assert set(avatars.entries(tmp_path)) == {"MINH", "LAN"}
    assert database.read_bytes() == before


def test_version_six_package_preserves_avatar_bytes(tmp_path):
    from abook.webui import bookfile
    data = avatars.normalize_image(raster())
    digest = hashlib.sha256(data).hexdigest()
    file = f"avatars/{digest}.webp"
    cast = {"narrator": {}, "characters": [{"name": "MINH", "avatar": {"kind": "image", "file": file, "sha256": digest}}], "extras": []}
    book = {"format": "abook", "title": "Original portrait fixture", "narrator": "", "duration": 0,
        "chaptersTotal": 1, "chaptersAvailable": 0, "complete": False, "version": "test",
        "chapters": [{"id": 1, "title": "One", "duration": 0, "size": 0, "sha256": "", "state": "text", "text": "texts/1.txt"}],
        "cast": "cast.json", "samples": [], "cover": None}
    out = bookfile.seal(book, {file: data, "cast.json": bookfile.json_bytes(cast), "texts/1.txt": b"An original example."},
                         tmp_path / "fixture.abook", producer="test", version=6)
    with bookfile.BookFile(out) as opened:
        assert opened.book["package"]["version"] == 6
        assert opened._zip.read(file) == data
        assert json.loads(opened._zip.read("cast.json"))["characters"][0]["avatar"]["file"] == file


def test_script_lines_carry_only_real_pictures_matched_by_shown_name():
    image = {"kind": "image", "file": "avatars/" + "a" * 64 + ".webp", "sha256": "a" * 64}
    people = {"characters": [{"name": "MINH", "displayName": "Minh", "avatar": image},
                             {"name": "LAN", "displayName": "Lan", "avatar": avatars.fallback("LAN")}], "extras": []}
    chapter = {"segments": [{"speaker": "Minh", "text": "a"}, {"speaker": "Lan", "text": "b"}, {"speaker": "", "text": "c"}]}
    out = avatars.script(chapter, people)
    assert out["segments"][0]["avatar"] == image
    assert "avatar" not in out["segments"][1] and "avatar" not in out["segments"][2]
    assert "avatar" not in chapter["segments"][0], "input script is not mutated"
    only_patterns = {"characters": people["characters"][1:], "extras": []}
    assert avatars.script(chapter, only_patterns) is chapter


def test_voice_portraits_cover_the_catalog_and_are_small():
    from abook.voice_catalog import VIENEU_PRESETS
    folder = Path(avatars.__file__).parent / "assets" / "voice_avatars"
    for voice in VIENEU_PRESETS:
        file = folder / avatars.voice_file(voice["name"])
        assert file.is_file(), voice["name"]
        assert file.stat().st_size < 32 * 1024
    assert sum(p.stat().st_size for p in folder.glob("*.webp")) < 1024 * 1024


def test_current_book_layer_supports_the_volume_tree_with_or_without_pictures():
    from abook.webui import bookfile
    files = {"texts/1.txt": b"x"}
    assert bookfile.layer_version({}, files, {}) == 6
    assert bookfile.layer_version({}, {**files, "avatars/" + "b" * 64 + ".webp": b"y"}, {}) == 6


def test_without_an_image_service_nothing_is_stored_so_a_later_service_still_runs(tmp_path):
    assert avatars.generate(tmp_path, person(), []) == avatars.fallback("MINH")
    avatars.run_after_analysis(tmp_path, lambda: False, lambda _: None)
    assert not (tmp_path / avatars.DB).exists()
    picture = avatars.generate(tmp_path, person(), [], renderer=lambda *_: raster())
    assert picture["kind"] == "image"


# ---- one key for every write and read (soát 0.4.173 B3) / any folder name (B4) ---------------------------------------------


def _png_b64(color="red"):
    import base64
    return base64.b64encode(raster(color)).decode()


def _lucien(cast_view):
    return next(p for p in cast_view["characters"] + cast_view["extras"] if p["name"].casefold() == "lucien")


@pytest.mark.parametrize("sent", ["shown", "LUCIEN", "  lucien "])
def test_a_portrait_uploaded_by_any_spelling_of_the_name_is_saved_and_shown(tmp_path, sent):
    from abook.webui import avatars as studio_avatars
    from tests.test_listener_speakers import _book

    paths, _db = _book(tmp_path)
    shown = _lucien(avatars.cast(paths.root))["name"]
    name = shown if sent == "shown" else sent
    result = studio_avatars.update(paths.root, {"character": name, "action": "upload", "data": _png_b64()})
    assert result["avatar"]["kind"] == "image"
    assert _lucien(avatars.cast(paths.root))["avatar"] == result["avatar"], "the cast row shows what was just saved"
    # Back to the pattern: the same one every client draws from the shown name.
    studio_avatars.update(paths.root, {"character": shown, "action": "pattern"})
    assert _lucien(avatars.cast(paths.root))["avatar"] == avatars.fallback(shown)


def test_an_unknown_character_is_still_refused(tmp_path):
    from abook.webui import avatars as studio_avatars
    from tests.test_listener_speakers import _book

    paths, _db = _book(tmp_path)
    with pytest.raises(ValueError):
        studio_avatars.update(paths.root, {"character": "Không Ai", "action": "upload", "data": _png_b64()})


@pytest.mark.parametrize("folder", ["Sach #2", "Sach 100%", "Sach  co  dau cach", "Sách #ổ"])
def test_portraits_read_from_a_book_whose_folder_name_has_url_characters(tmp_path, folder):
    from tests.test_listener_speakers import _book

    paths, _db = _book(tmp_path / folder)
    saved = avatars.choose(paths.root, "LUCIEN", raster("blue"))
    before = sorted(path.name for path in paths.root.parent.iterdir())
    assert _lucien(avatars.cast(paths.root))["avatar"] == saved
    assert sorted(path.name for path in paths.root.parent.iterdir()) == before, "no stray database next to the book"
    assert sorted(path.name for path in (tmp_path / folder).parent.iterdir()) == [folder]
