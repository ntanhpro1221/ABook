"""Bài nhạc phải ghi công (giấy phép khác cc0) mà thiếu tên tác giả hay chuỗi ghi công thì không bao giờ vào sách: ghi công không tên vẫn vi phạm CC BY
(FINDINGS_music A2). Bài cc0 và nhạc người dùng nhập không bị đòi."""
from __future__ import annotations

import json
from pathlib import Path

from abook.webui import music_catalog, music_nnscene
from abook.webui.library import book_id
from abook.webui.music_catalog import lacks_credit
from tests.catalog_signing import TEST_PUBLIC_KEY, write_catalog
from tests.test_a_project_can_be_renamed_or_deleted import _call, studio  # noqa: F401 - fixture dùng chung
from tests.test_music_api import _no_background_warming  # noqa: F401 - autouse: không tải sẵn nền
from tests.test_music_catalog_and_select import TRACKS

CREDITED = {"license": "by", "licenseUrl": "https://creativecommons.org/licenses/by/4.0/", "creator": "Tác giả", "attribution": '"Calm" by Tác giả'}
TWINS = ("https://x/calm2.mp3", "https://x/calm3.mp3")  # hai bài giống hệt nhau về không khí: bài kia thay được bài này


def test_only_a_track_that_must_be_credited_and_lacks_the_author_is_refused() -> None:
    assert lacks_credit({**CREDITED, "creator": ""})
    assert lacks_credit({**CREDITED, "creator": "   "})
    assert lacks_credit({**CREDITED, "attribution": None})
    assert lacks_credit({"license": "by-sa"}), "thiếu cả hai"
    assert not lacks_credit(CREDITED)
    assert not lacks_credit({"license": "cc0"}) and not lacks_credit({"license": "CC0", "creator": ""}), "cc0 không bắt buộc ghi công"
    assert not lacks_credit({"source": "local", "license": "by"}), "nhạc người dùng nhập không có giấy phép để đòi"
    assert not lacks_credit({}) and not lacks_credit(None), "danh mục không ghi giấy phép: không có gì để đòi"


def _catalog(root: Path, *, uncredited: str | None = None) -> Path:
    tracks = {link: {**track, **CREDITED} for link, track in TRACKS.items()}
    tracks[TWINS[1]] = dict(tracks[TWINS[0]])
    if uncredited is not None:
        tracks[uncredited] = {**tracks[uncredited], "creator": "", "attribution": '"Calm" by  licensed'}  # như 53 bài thiếu tác giả của OpenGameArt
    return write_catalog(root, tracks)


def _links(view: dict) -> set[str]:
    return {link for scene in view["plan"]["scenes"] for link in music_nnscene.chosen_links([scene])}


def _open(app, tmp_path: Path, name: str, **catalog) -> None:
    app._music_catalog = music_catalog.MusicCatalog(tmp_path / f"cache_{name}", str(_catalog(tmp_path / name, **catalog)), public_key=TEST_PUBLIC_KEY)
    app._music_sized.clear()
    app._music_uncredited.clear()


def test_the_book_never_uses_a_track_that_must_be_credited_but_has_no_author(studio, tmp_path: Path) -> None:  # noqa: F811
    paths, app, server, _runner = studio
    book = book_id(paths.root)
    _open(app, tmp_path, "control")
    status, control = _call(server, "GET", f"/api/books/{book}/music")
    chosen = _links(control)
    assert status == 200 and chosen & set(TWINS), "đối chứng: bộ chọn dùng một trong hai bài"
    bad = sorted(chosen & set(TWINS))[0]
    other = TWINS[1] if bad == TWINS[0] else TWINS[0]
    _open(app, tmp_path, "unnamed", uncredited=bad)
    (paths.root / "music_plan.json").unlink()
    status, view = _call(server, "GET", f"/api/books/{book}/music")
    assert status == 200 and bad not in _links(view), "bài thiếu tác giả vẫn vào rãnh nhạc"
    assert other in _links(view), "bài thay thế đủ ghi công phải được dùng"
    assert app.music_track_available(bad) is False, "bài đã ghi sổ thiếu tác giả thì không dùng được ở mọi chỗ"
    assert bad not in json.loads((paths.root / "music_plan.json").read_text(encoding="utf-8"))["tracks"]


def test_pinning_a_track_without_an_author_does_not_put_it_in_the_book(studio, tmp_path: Path) -> None:  # noqa: F811
    paths, app, server, _runner = studio
    book = book_id(paths.root)
    _open(app, tmp_path, "unnamed", uncredited=TWINS[0])
    _status, first = _call(server, "GET", f"/api/books/{book}/music")
    key = first["plan"]["scenes"][0]["key"]
    status, changed = _call(server, "PUT", f"/api/books/{book}/music", {"pins": {key: TWINS[0]}})
    assert status == 200 and TWINS[0] not in _links(changed), "ghim bài thiếu tác giả vẫn vào sách"
    assert changed["plan"]["scenes"][0].get("pinUnavailable") is True, "người dùng được báo ghim không dùng được ở máy này"
