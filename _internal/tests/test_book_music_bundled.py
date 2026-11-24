""""Nhạc trong sách" liệt kê MỌI bài cuốn dùng (bookmusic2).

Gói "Brunhild the Dragon Slayer.abook" chỉ có nhạc riêng của người làm sách (`local:<sha1>` trong `music.tracks`, có title/creator): trang
sách từng ghi "Chưa có nhạc" trong khi sách vẫn phát nhạc, vì danh sách chỉ giữ bài kho nhạc trực tuyến biết. Bài kho không có là dòng
`bundled` (tên theo book.json, số đoạn, cảm xúc cảnh của đoạn đầu tiên), không lưu / tải được và không vào "Lưu tất cả".
"""
from __future__ import annotations

from pathlib import Path

from abook.webui import bookfile, music_library
from abook.webui.library import book_id
from tests.test_a_project_can_be_renamed_or_deleted import _call, studio  # noqa: F401 - fixture dùng chung
from tests.test_bookfile_music import BATTLE, CALM, _moods, _plan, _tracks
from tests.test_webui_listen_and_sync import make_project

FLOAT, PHANTOM = "local:" + "a" * 40, "local:" + "b" * 40


def _book(app, tmp_path: Path, links: dict[str, str], moods: dict[str, object] | None = None) -> str:
    project = make_project(tmp_path / "nguoi_lam_sach")
    _plan(project)
    _moods(project, moods or {}, links)
    return app.open_book_file(str(bookfile.pack(project, tmp_path / f"sach{bookfile.EXTENSION}", music_track=_tracks(tmp_path), partial=True)))["id"]


def test_a_book_of_packaged_tracks_lists_every_track_in_listening_order(studio, tmp_path: Path) -> None:  # noqa: F811
    _paths, app, server, _runner = studio
    book = _book(app, tmp_path, {CALM: FLOAT, BATTLE: PHANTOM}, {"1:1": {"sadness": 0.8, "nostalgia": 0.6, "joy": 0.2, "fear": 0.1}})
    status, data = _call(server, "GET", f"/api/books/{book}/music/library")
    assert status == 200
    assert [(row["link"], row["scenes"]) for row in data["tracks"]] == [(FLOAT, 1), (PHANTOM, 1)]  # gói gộp hai cảnh liền nhau cùng bài
    first, second = data["tracks"]
    assert (first["title"], first["creator"]) == ("Calm", "A"), "tên + người sáng tác theo music.tracks của book.json"
    assert first["bundled"] is True and first["saved"] is False and first["downloaded"] is False
    assert first["mood"] == [{"id": "sadness", "score": 0.8}, {"id": "nostalgia", "score": 0.6}, {"id": "joy", "score": 0.2}]
    assert second["mood"] == [], "mốc không có cảm xúc: khối \"Vì sao bài này\" ẩn"
    assert data["unsaved"] == [] and data["missingBytes"] == 0, "bài đi kèm sách không có gì để lưu"


def test_a_mixed_book_keeps_catalog_rows_and_saves_only_them(studio, tmp_path: Path) -> None:  # noqa: F811
    from tests.test_music_api import _with_catalog

    _paths, app, server, _runner = studio
    _with_catalog(app, tmp_path)
    sad = "https://x/sad.mp3"
    book = _book(app, tmp_path, {CALM: FLOAT, BATTLE: sad})
    status, data = _call(server, "GET", f"/api/books/{book}/music/library")
    assert status == 200
    assert [row["link"] for row in data["tracks"]] == [FLOAT, sad], "thứ tự nghe"
    bundled, catalog = data["tracks"]
    assert bundled["bundled"] is True and "bundled" not in catalog
    assert catalog["scenes"] == 1 and catalog["duration"] == 240, "dòng danh mục vẫn đọc từ kho"
    assert data["unsaved"] == [sad]
    assert data["missingBytes"] == catalog.get("bytes", 0)


def test_a_catalog_link_the_catalog_does_not_know_still_has_a_row(studio, tmp_path: Path) -> None:  # noqa: F811
    from tests.test_music_api import _with_catalog

    _paths, app, server, _runner = studio
    _with_catalog(app, tmp_path)
    gone, other = "https://x/khong-con.mp3", "https://x/khong-co.mp3"
    book = _book(app, tmp_path, {CALM: gone, BATTLE: other})
    status, data = _call(server, "GET", f"/api/books/{book}/music/library")
    assert status == 200
    assert [(row["link"], row.get("title"), row.get("bundled")) for row in data["tracks"]] == [(gone, "Calm", True), (other, "Battle", True)]
    assert data["unsaved"] == []


def test_a_book_without_music_has_no_rows(studio, tmp_path: Path) -> None:  # noqa: F811
    paths, app, server, _runner = studio
    status, data = _call(server, "GET", f"/api/books/{book_id(paths.root)}/music/library")
    assert status == 200 and data == {"tracks": [], "missingBytes": 0, "unsaved": []}


def test_track_names_and_bundled_rows() -> None:
    music = {"tracks": {"music/a.opus": {"link": FLOAT, "title": "float flower (MONSTER)", "creator": "Kuniaki Haishima", "lufs": -19.5},
                        "music/b.opus": {"link": PHANTOM, "title": "", "creator": None}, "bad": "x"}}
    assert music_library.track_names(music) == {FLOAT: {"title": "float flower (MONSTER)", "creator": "Kuniaki Haishima"}, PHANTOM: {}}
    assert music_library.track_names(None) == {}
    row = music_library.bundled_row({"link": PHANTOM, "scenes": 3, "scene": "2:0"}, {}, None)
    assert row == {"link": PHANTOM, "scenes": 3, "scene": "2:0", "bundled": True, "saved": False, "downloaded": False, "mood": []}
