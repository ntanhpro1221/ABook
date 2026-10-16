"""Bộ đệm nhạc nền của máy (music_dir/files) có trần: nhạc theo cảnh bật sẵn và mỗi bài tải được tới 40 MB, nên không trần thì thư mục phình mãi.
Quá trần thì xoá bài lâu không nghe nhất; không bao giờ xoá bài sách mang theo, bài người dùng nhập, bài ghim, bài đang nghe / vừa tải."""
from __future__ import annotations

import hashlib
import io
import os
import time
import urllib.request
from pathlib import Path

from abook.webui import music_cache, music_plan
from abook.webui.music_cache import MusicCache
from tests.test_a_project_can_be_renamed_or_deleted import studio  # noqa: F401 - fixture dùng chung
from tests.test_music_api import CALM, CALM2, _with_catalog

DAY = 24 * 3600


def _name(seed: str, extension: str = "mp3") -> str:
    return hashlib.sha1(seed.encode("utf-8")).hexdigest() + "." + extension


def _track(folder: Path, name: str, size: int, age_days: float, now: float, body: bytes | None = None) -> Path:
    path = folder / name
    path.write_bytes(body if body is not None else b"ID3" + b"\x01" * (size - 3))
    stamp = now - age_days * DAY
    os.utime(path, (stamp, stamp))
    return path


def _cache(tmp_path: Path, cap: int, now: float) -> MusicCache:
    folder = tmp_path / "files"
    folder.mkdir(exist_ok=True)
    return MusicCache(folder, tmp_path / "files_owned.json", cap_bytes=cap, clock=lambda: now)


def test_under_the_cap_nothing_is_removed(tmp_path: Path) -> None:
    now = time.time()
    cache = _cache(tmp_path, 5000, now)
    for index in range(4):
        _track(cache.folder, _name(f"t{index}"), 1000, 10 + index, now)
    assert cache.prune() == [] and len(list(cache.folder.iterdir())) == 4


def test_over_the_cap_the_least_recently_heard_go_first_down_to_the_low_water_mark(tmp_path: Path) -> None:
    now = time.time()
    cache = _cache(tmp_path, 4000, now)
    oldest = [_track(cache.folder, _name(f"t{index}"), 1000, 30 - index, now) for index in range(6)]  # t0 cũ nhất ... t5
    removed = cache.prune()
    # 6000 B > 4000 B: dọn xuống <= 3600 B (90% trần) -> 3 bài cũ nhất
    assert removed == oldest[:3]
    assert [path.exists() for path in oldest] == [False, False, False, True, True, True]
    assert cache.total_bytes() == 3000


def test_sidecar_files_of_a_removed_track_go_with_it(tmp_path: Path) -> None:
    now = time.time()
    cache = _cache(tmp_path, 1500, now)
    old = _track(cache.folder, _name("old"), 1000, 30, now)
    _track(cache.folder, _name("new"), 1000, 20, now)
    lufs, measure = old.with_suffix(music_plan.LUFS_SIDECAR), old.with_suffix(music_plan.MEASURE_SIDECAR)
    lufs.write_text("-16", encoding="utf-8")
    measure.write_text("{}", encoding="utf-8")
    unrelated = cache.folder / "readme.txt"
    unrelated.write_text("khong phai bai", encoding="utf-8")
    assert cache.prune() == [old]
    assert not lufs.exists() and not measure.exists()
    assert unrelated.exists(), "chỉ động tới file bài nhạc"


def test_never_removed_books_own_tracks_pinned_tracks_recent_ones_and_the_one_just_downloaded(tmp_path: Path) -> None:
    now = time.time()
    cache = _cache(tmp_path, 1000, now)
    carried = _track(cache.folder, _name("sach-mang-theo"), 1000, 90, now)
    pinned = _track(cache.folder, _name("ghim"), 1000, 80, now)
    heard_today = _track(cache.folder, _name("moi-nghe"), 1000, 0.2, now)
    fresh = _track(cache.folder, _name("vua-tai"), 1000, 70, now)
    disposable = _track(cache.folder, _name("bo-duoc"), 1000, 60, now)
    cache.own([carried.name])
    removed = cache.prune(lambda: {pinned.name}, [fresh])
    assert removed == [disposable]
    assert all(path.exists() for path in (carried, pinned, heard_today, fresh))
    # trần chỉ là trần mềm: còn lại toàn bài được bảo vệ thì để nguyên, không xoá bừa
    assert cache.prune(lambda: {pinned.name}, [fresh]) == []


def test_a_file_named_after_its_own_content_is_a_users_track_and_is_never_removed(tmp_path: Path) -> None:
    """Bài người dùng nhập / ghim có tên = sha1 NỘI DUNG (`local:<sha1>`); bài tải theo link có tên = sha1 của link. Dù sổ bài sách mang theo mất, bài nhập không bị xoá."""
    now = time.time()
    cache = _cache(tmp_path, 1000, now)
    body = b"ID3" + b"\x07" * 997
    local = _track(cache.folder, hashlib.sha1(body).hexdigest() + ".mp3", 1000, 90, now, body)
    other = _track(cache.folder, _name("tai-theo-link"), 1000, 80, now)
    assert cache.prune() == [other]
    assert local.exists()


def test_owned_tracks_survive_a_restart_and_a_damaged_ledger_is_ignored(tmp_path: Path) -> None:
    now = time.time()
    cache = _cache(tmp_path, 10, now)
    names = [_name("a"), _name("b")]
    cache.own(names + ["../ngoai.mp3", "khong-phai-bai.txt"])
    assert MusicCache(cache.folder, cache.owned_file).owned() == set(names)
    cache.owned_file.write_text("{không phải json", encoding="utf-8")
    assert MusicCache(cache.folder, cache.owned_file).owned() == set()


def test_touch_marks_the_last_time_heard_but_only_for_files_in_the_cache_and_not_too_often(tmp_path: Path) -> None:
    now = time.time()
    cache = _cache(tmp_path, 1000, now)
    heard = _track(cache.folder, _name("nghe-lai"), 600, 30, now)
    other = _track(cache.folder, _name("khac"), 600, 20, now)
    cache.touch(heard)  # nghe lại: giờ nghe mới nhất
    assert abs(heard.stat().st_mtime - now) < 2
    assert cache.prune() == [other], "bài nghe lại được giữ, bài khác cũ hơn bị dọn"
    outside = tmp_path / "ngoai.mp3"
    outside.write_bytes(b"x")
    os.utime(outside, (1, 1))
    cache.touch(outside)
    cache.touch(None)
    cache.touch(cache.folder / "khong-co.mp3")
    assert outside.stat().st_mtime == 1
    # vừa ghi xong thì không ghi lại
    stamp = heard.stat().st_mtime
    cache.clock = lambda: now + 60
    cache.touch(heard)
    assert heard.stat().st_mtime == stamp


class _Response(io.BytesIO):
    def __init__(self, body: bytes) -> None:
        super().__init__(body)
        self.headers = {"Content-Length": str(len(body))}


def test_a_new_download_prunes_the_cache_but_keeps_the_new_track_the_pinned_and_the_carried(studio, tmp_path: Path, monkeypatch) -> None:  # noqa: F811
    paths, app, _server, _runner = studio
    _with_catalog(app, tmp_path)
    files = app.music_dir / "files"
    files.mkdir(parents=True, exist_ok=True)
    now = time.time()
    carried = _track(files, _name("sach-mang-theo"), 1000, 90, now)
    app.music_cache.own([carried.name])
    pinned_link = "https://x/ghim.mp3"
    pinned = _track(files, app._music_file(pinned_link).name, 1000, 80, now)
    (paths.root / "music_overrides.json").write_text('{"pins": {"1:3": "%s"}}' % pinned_link, encoding="utf-8")
    stale = [_track(files, _name(f"cu{index}"), 1000, 40 - index, now) for index in range(3)]
    body = b"ID3" + b"\x01" * 997
    monkeypatch.setattr(urllib.request, "urlopen", lambda request, timeout=0: _Response(body))
    app.music_cache.cap_bytes = 3000
    got = app.music_track_for_export(CALM)
    assert got is not None and got.read_bytes() == body and got == app._music_file(CALM)
    assert carried.exists() and pinned.exists() and got.exists()
    assert [path.exists() for path in stale] == [False, False, False]
    # tải thêm một bài nữa: vẫn không động tới bài sách mang theo / bài ghim
    got2 = app.music_track_for_export(CALM2)
    assert got2 is not None and got2.exists() and carried.exists() and pinned.exists()
    assert app.music_cache.total_bytes() <= 4 * 1000  # trần mềm: bài được bảo vệ + bài vừa tải ở lại


def test_listening_marks_the_track_as_recently_heard(studio, tmp_path: Path) -> None:  # noqa: F811
    _paths, app, _server, _runner = studio
    _with_catalog(app, tmp_path)
    files = app.music_dir / "files"
    files.mkdir(parents=True, exist_ok=True)
    played = _track(files, app._music_file(CALM).name, 500, 5, time.time())
    app.music_track_file(CALM)  # trình phát lấy file bài (đã có trong bộ đệm)
    assert time.time() - played.stat().st_mtime < 5
    old = _track(files, app._music_file(CALM2).name, 500, 5, time.time())
    app._music_src("sach", CALM2)  # mốc nhạc của chương đang nghe trỏ tới bài này
    assert time.time() - old.stat().st_mtime < 5


def test_opening_a_project_file_records_its_music_as_the_books_own(tmp_path: Path) -> None:
    from tests.test_bookfile_music import CALM as BOOK_CALM, _plan, _tracks
    from tests.test_project_file import _app, _project

    project = _project(tmp_path)
    _plan(project)
    from abook.webui import projectfile

    packed = projectfile.pack(project, tmp_path / "du_an.abookproj", music_track=_tracks(tmp_path))
    other = _app(tmp_path / "may_khac", tmp_path / "thu_vien_moi")
    other.open_book_file(str(packed))
    name = music_plan.track_name(BOOK_CALM).split("/")[1]
    assert name in other.music_cache.owned()
    assert (other.music_dir / "files" / name).is_file()
    with projectfile.ProjectFile(packed) as opened:
        assert name in opened.music_names()
    kept = other.music_dir / "files" / name
    os.utime(kept, (1, 1))  # cũ nhất có thể: chỉ sổ "sách mang theo" còn giữ nó
    tight = music_cache.MusicCache(other.music_dir / "files", other.music_dir / "files_owned.json", cap_bytes=1)
    assert tight.prune() == [] and kept.is_file(), "bài sách mang theo không bao giờ bị dọn, dù trần là 1 byte"
