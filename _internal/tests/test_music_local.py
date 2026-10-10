"""Nhạc của tôi (webui/music_local.py): nhập nhạc người dùng tự có, kho theo mã nội dung, ghim cho đoạn, đi theo sách và qua
đồng bộ điện thoại. Chưa có bộ phân tích âm thanh thì bài ở trạng thái "chưa phân tích" - không bịa số."""
from __future__ import annotations

import json
import shutil
import subprocess
import zipfile
from pathlib import Path
from urllib.parse import quote

import numpy as np
import pytest
import soundfile

from abook.io_utils import ffmpeg_executable
from abook.webui import bookfile, music_local, music_plan, packages, projectfile
from abook.webui.library import book_id
from abook.webui.music_catalog import MusicCatalog
from abook.webui.music_local import LocalMusic, MusicImportError
from abook.webui.projectfile import ProjectFile
from tests.test_a_project_can_be_renamed_or_deleted import _call, studio  # noqa: F401 - fixture dùng chung
from tests.test_music_api import _calm_plan, _with_catalog
from tests.test_webui_listen_and_sync import _request, make_project

CALM_ANALYSIS = {"valence": 0.3, "arousal": -0.6, "tension": 0.0, "confidence": 0.9, "sd": {"arousal": 0.1},
                 "emotions": {"peacefulness": 0.9, "sadness": 0.1, "unknown": 1.0}, "fitsUnderNarration": 0.8,
                 "loudness": {"lufs": -22.0, "speechBand": 0.2}}


@pytest.fixture(autouse=True)
def _isolated(monkeypatch):
    """Không luồng tải sẵn nền (chạm mạng); bộ phân tích luôn trả về trạng thái "chưa có" sau mỗi test."""
    from abook.webui.server import App

    monkeypatch.setattr(App, "_warm_music", lambda self, *args, **kwargs: None)
    music_local.set_analyzer(None)
    yield
    music_local.set_analyzer(None)


def _encode(wav: Path, out: Path, **tags: str) -> Path:
    command = [ffmpeg_executable(), "-hide_banner", "-nostdin", "-y", "-i", str(wav)]
    for key, value in tags.items():
        command += ["-metadata", f"{key}={value}"]
    subprocess.run([*command, str(out)], capture_output=True, check=True)
    return out


@pytest.fixture(scope="module")
def songs(tmp_path_factory) -> dict[str, Path]:
    """Vài file nhạc thật (ffmpeg): mp3 có thẻ tiếng Việt, ogg (thẻ ở luồng âm thanh), flac không thẻ, và một file ngắn."""
    folder = tmp_path_factory.mktemp("songs")
    rate = 8000
    wave = (0.3 * np.sin(2 * np.pi * 220 * np.arange(rate * 62) / rate)).astype("float32")
    soundfile.write(folder / "base.wav", wave, rate)
    soundfile.write(folder / "short.wav", wave[: rate * 10], rate)
    return {
        "mp3": _encode(folder / "base.wav", folder / "Đêm trăng.mp3", title="Đêm trăng sáng", artist="Nghệ sĩ Việt",
                       album="Tuyển tập", genre="Ambient"),
        "ogg": _encode(folder / "base.wav", folder / "gio.ogg", title="Gió", artist="Ai đó"),
        "flac": _encode(folder / "base.wav", folder / "khong_the.flac"),
        "short": folder / "short.wav",
        "wav": folder / "base.wav",
    }


# ---- kho -----------------------------------------------------------------------------------------------------------------
def test_an_imported_file_is_copied_by_content_with_its_own_tags_and_measured_loudness(tmp_path: Path, songs) -> None:
    store = LocalMusic(tmp_path / "mine")
    track, existing = store.import_file(songs["mp3"])
    assert existing is False
    digest = music_plan.local_hash(track["link"])
    assert track["link"] == "local:" + digest and (tmp_path / "mine" / "files" / f"{digest}.mp3").is_file()
    assert (track["title"], track["creator"], track["album"], track["genre"]) == (
        "Đêm trăng sáng", "Nghệ sĩ Việt", "Tuyển tập", "Ambient"), "thẻ UTF-8 đọc đúng"
    assert track["duration"] == 62 and track["source"] == "local" and track["name"] == "Đêm trăng.mp3"
    assert isinstance(track["lufs"], float), "độ to đo bằng đúng mã đo của music_plan"
    assert (tmp_path / "mine" / "files" / f"{digest}.lufs2").is_file(), "số đo ghi cạnh file như bài danh mục"
    assert store.file(track["link"]).read_bytes() == songs["mp3"].read_bytes()
    # Mở lại app: sổ còn nguyên.
    assert LocalMusic(tmp_path / "mine").entries()[0]["title"] == "Đêm trăng sáng"


def test_tags_in_the_audio_stream_and_missing_tags_are_handled(tmp_path: Path, songs) -> None:
    store = LocalMusic(tmp_path / "mine")
    ogg, _ = store.import_file(songs["ogg"])
    assert (ogg["title"], ogg["creator"]) == ("Gió", "Ai đó"), "Ogg / Opus để thẻ ở luồng âm thanh"
    bare, _ = store.import_file(songs["flac"])
    assert bare["title"] == "khong_the" and bare["creator"] == "", "không có thẻ thì dùng tên file"


def test_the_same_content_is_stored_once_whatever_the_file_is_called(tmp_path: Path, songs) -> None:
    store = LocalMusic(tmp_path / "mine")
    first, _ = store.import_file(songs["mp3"])
    copy = tmp_path / "ban sao khac ten.mp3"
    shutil.copyfile(songs["mp3"], copy)
    again, existing = store.import_file(copy)
    assert existing is True and again["link"] == first["link"]
    assert len(store.entries()) == 1 and len(list((tmp_path / "mine" / "files").glob("*.mp3"))) == 1


def test_files_that_are_not_music_are_refused_with_a_reason(tmp_path: Path, songs) -> None:
    store = LocalMusic(tmp_path / "mine")
    notes = tmp_path / "ghi chu.txt"
    notes.write_text("không phải nhạc", encoding="utf-8")
    fake = tmp_path / "gia.mp3"
    fake.write_bytes(b"day khong phai am thanh" * 20)
    for bad, reason in ((notes, "định dạng"), (fake, "không đọc được"), (tmp_path / "mat.mp3", "không thấy")):
        with pytest.raises(MusicImportError, match=reason) as error:
            store.import_file(bad)
        assert bad.name in str(error.value)
    assert store.entries() == [] and not list((tmp_path / "mine").glob("files/*"))


def test_removing_a_track_deletes_its_file_and_loudness(tmp_path: Path, songs) -> None:
    store = LocalMusic(tmp_path / "mine")
    track, _ = store.import_file(songs["mp3"])
    digest = music_plan.local_hash(track["link"])
    assert store.remove(digest) is True and store.remove(digest) is False
    assert store.file(track["link"]) is None and not list((tmp_path / "mine" / "files").glob("*"))
    assert LocalMusic(tmp_path / "mine").entries() == []


def test_a_track_carried_by_a_book_plays_without_being_in_the_store(tmp_path: Path, songs) -> None:
    carried = tmp_path / "files"
    carried.mkdir()
    digest = "a" * 40
    (carried / f"{digest}.flac").write_bytes(b"fLaC")
    store = LocalMusic(tmp_path / "mine", carried)
    assert store.file("local:" + digest) == carried / f"{digest}.flac"
    assert store.file("local:" + "b" * 40) is None and store.file("https://x/a.mp3") is None
    assert store.entries() == [], "bài của người khác không lẫn vào danh sách của tôi"


# ---- phân tích ------------------------------------------------------------------------------------------------------------
def test_without_an_analyzer_a_track_is_not_analysed_and_never_auto_chosen(tmp_path: Path, songs) -> None:
    assert music_local.analyze(songs["mp3"]) is None and not music_local.analyzer_available()
    store = LocalMusic(tmp_path / "mine")
    track, _ = store.import_file(songs["mp3"])
    assert track["analysed"] is False and "valence" not in track and "emotions" not in track, "không bịa số"
    assert store.near(0.3, -0.6) == [], "chưa phân tích thì không vào ứng viên tự động"


def test_an_analysed_track_joins_the_candidate_pool_in_the_shape_of_a_catalog_track(tmp_path: Path, songs) -> None:
    music_local.set_analyzer(lambda _path: dict(CALM_ANALYSIS))
    store = LocalMusic(tmp_path / "mine")
    track, _ = store.import_file(songs["mp3"])
    assert track["analysed"] is True and track["valence"] == 0.3 and track["arousal"] == -0.6
    assert track["background"] == 0.8, "fitsUnderNarration là `background` của danh mục"
    assert track["emotions"] == {"peacefulness": 0.9, "sadness": 0.1}, "chỉ 13 cảm xúc đã biết"
    assert isinstance(track["lufs"], float) and track["lufs"] != -22.0, "số đo từ chính file thắng số của bộ phân tích"
    assert [t["link"] for t in store.near(0.3, -0.6)] == [track["link"]]
    assert store.near(-0.9, 0.9) == [], "cùng cách chia ô như danh mục: bài ở ô xa không phải ứng viên"


def test_analysis_that_is_not_usable_leaves_the_track_unanalysed(tmp_path: Path, songs) -> None:
    for result in (None, {"arousal": 0.1}, {"valence": "buồn", "arousal": 0.1}, "xin chào",
                   {"valence": float("nan"), "arousal": 0.0}):
        assert music_local.clean_analysis(result) is None
    music_local.set_analyzer(lambda _path: (_ for _ in ()).throw(RuntimeError("model hỏng")))
    track, _ = LocalMusic(tmp_path / "mine").import_file(songs["mp3"])
    assert track["analysed"] is False, "bộ phân tích lỗi không làm hỏng việc nhập"
    clipped = music_local.clean_analysis({"valence": 4, "arousal": -9, "loudness": -18.5})
    assert clipped == {"valence": 1.0, "arousal": -1.0, "lufs": -18.5}


def test_clean_analysis_keeps_the_residual_variance_and_drops_bad_numbers() -> None:
    cleaned = music_local.clean_analysis({"valence": 0.1, "arousal": 0.2, "tension": 0.3,
                                          "vetVar": {"valence": 0.04, "arousal": float("nan"), "tension": -1.0, "x": "no"}})
    assert cleaned["vetVar"] == {"valence": 0.04, "tension": 0.0}, "số hữu hạn, >= 0; NaN và chữ bị bỏ"
    assert "vetVar" not in music_local.clean_analysis({"valence": 0.1, "arousal": 0.2, "vetVar": "xin chào"})
    assert "vetVar" not in music_local.clean_analysis({"valence": 0.1, "arousal": 0.2, "vetVar": {"valence": float("inf")}})


def test_tracks_imported_before_the_analyzer_existed_are_analysed_later(tmp_path: Path, songs) -> None:
    store = LocalMusic(tmp_path / "mine")
    track, _ = store.import_file(songs["mp3"])
    assert store.analyze_pending() == 0
    music_local.set_analyzer(lambda _path: dict(CALM_ANALYSIS))
    assert store.analyze_pending() == 1 and store.near(0.3, -0.6)[0]["link"] == track["link"]
    assert LocalMusic(tmp_path / "mine").entries()[0]["analysed"] is True


# ---- máy chủ: nhập, ghim, phát -----------------------------------------------------------------------------------------
def _import(server, *paths: Path) -> dict:
    status, data = _call(server, "POST", "/api/music/local/import", {"paths": [str(path) for path in paths]})
    assert status == 200, data
    return data


def _pin(server, book: str, key: str, link: str) -> dict:
    status, view = _call(server, "PUT", f"/api/books/{book}/music", {"pins": {key: link}})
    assert status == 200, view
    return view


def test_the_user_imports_lists_and_removes_music_through_the_api(studio, tmp_path: Path, songs) -> None:  # noqa: F811
    _paths, _app, server, _runner = studio
    status, empty = _call(server, "GET", "/api/music/local")
    assert status == 200 and (empty["tracks"], empty["analyzer"]) == ([], False)
    assert empty["module"]["state"] in ("missing", "ready", "unsupported") and empty["module"]["stale"] == 0, "mô-đun Phân tích nhạc: một thẻ trạng thái duy nhất"
    assert "reader" not in empty, "không còn luồng tải bộ đọc riêng"
    notes = tmp_path / "x.txt"
    notes.write_text("không", encoding="utf-8")
    first = _import(server, songs["mp3"], songs["ogg"], notes)
    assert [t["title"] for t in first["added"]] == ["Đêm trăng sáng", "Gió"] and first["existing"] == []
    assert len(first["failed"]) == 1 and "x.txt" in first["failed"][0], "file hỏng không làm hỏng cả lượt"
    again = _import(server, songs["mp3"])
    assert again["added"] == [] and [t["title"] for t in again["existing"]] == ["Đêm trăng sáng"]
    assert len(again["tracks"]) == 2 and all(not t["analysed"] for t in again["tracks"])
    status, _data = _call(server, "POST", "/api/music/local/import", {"paths": ["tuong_doi/a.mp3"]})
    assert status == 200 and _data["failed"] and not _data["added"], "đường dẫn tương đối bị từ chối"
    status, data = _call(server, "POST", "/api/music/local/analyze")
    assert status == 409 and "bộ phân tích" in data["error"], "chưa có bộ phân tích thì nói rõ"
    digest = music_plan.local_hash(first["added"][0]["link"])
    status, left = _call(server, "DELETE", f"/api/music/local/{digest}")
    assert status == 200 and [t["title"] for t in left["tracks"]] == ["Gió"]
    assert _call(server, "DELETE", f"/api/music/local/{digest}")[0] == 404


def test_a_track_of_mine_is_offered_in_change_track_even_unanalysed_and_pinning_it_plays_it(  # noqa: F811
        studio, tmp_path: Path, songs) -> None:
    paths, app, server, _runner = studio
    _with_catalog(app, tmp_path)
    book = book_id(paths.root)
    _call(server, "GET", f"/api/books/{book}/music")
    imported = _import(server, songs["mp3"], songs["short"])["added"]
    mine, short = imported[0]["link"], imported[1]["link"]
    scene = json.loads((paths.root / music_plan.PLAN_FILE).read_text(encoding="utf-8"))["scenes"][0]
    status, offered = _call(server, "GET", f"/api/books/{book}/music/scenes/{quote(scene['key'], safe='')}/alternatives")
    assert status == 200 and not any(item["link"] in (mine, short) for item in offered["alternatives"]), "nhóm riêng"
    group = {item["link"]: item for item in offered["mine"]}
    assert set(group) == {mine, short} and not group[mine]["analysed"] and not group[mine]["fits"]
    assert group[mine]["title"] == "Đêm trăng sáng" and group[mine]["creator"] == "Nghệ sĩ Việt" and group[mine]["duration"] == 62
    view = _pin(server, book, scene["key"], mine)
    first = view["plan"]["scenes"][0]
    assert first["link"] == mine and first["pinned"] is True and "pinUnavailable" not in first
    assert view["plan"]["tracks"][mine]["title"] == "Đêm trăng sáng" and view["plan"]["tracks"][mine]["source"] == "local"
    assert not view["plan"]["tracks"][mine].get("license") and not view["plan"]["tracks"][mine].get("attribution"), \
        "không tuyên bố giấy phép cho nhạc của người dùng"
    others = [s["link"] for s in view["plan"]["scenes"][1:] if s["link"]]
    assert mine not in others and short not in others, "bài chưa phân tích chỉ được ghim tay, máy không tự chọn"
    # Trình phát lấy file qua đường THEO SÁCH, không qua /api/music/track (chỉ danh mục).
    chapter = first["chapterId"]
    status, cues = _call(server, "GET", f"/api/books/{book}/music/chapters/{chapter}")
    cue = next(cue for cue in cues["cues"] if cue["link"] == mine)
    digest = music_plan.local_hash(mine)
    assert cue["src"] == f"/api/books/{book}/music/files/{digest}.mp3"
    assert cues["credits"][mine] == {"title": "Đêm trăng sáng", "creator": "Nghệ sĩ Việt"}, "ghi công = thẻ của chính file"
    status, body, _headers = _request(server.port, "GET", cue["src"], headers={"X-Ebook-Token": "t"})
    assert status == 200 and body == songs["mp3"].read_bytes()
    status, _data = _call(server, "GET", "/api/music/track?link=" + quote(mine, safe=""))
    assert status == 400, "đường chung chỉ phục vụ danh mục"
    # Bài trong kho nhưng cuốn này không dùng thì không lấy được qua cuốn này.
    status, _body, _h = _request(server.port, "GET", f"/api/books/{book}/music/files/{music_plan.local_hash(short)}.wav",
                                 headers={"X-Ebook-Token": "t"})
    assert status == 404
    # Nghe thử trên máy này.
    status, body, _h = _request(server.port, "GET", f"/api/music/local/{digest}/file", headers={"X-Ebook-Token": "t"})
    assert status == 200 and body == songs["mp3"].read_bytes()


def test_an_analysed_track_competes_like_a_catalog_track_and_wins_when_it_fits_best(studio, tmp_path: Path, songs) -> None:  # noqa: F811
    paths, app, server, _runner = studio
    _with_catalog(app, tmp_path)
    book = book_id(paths.root)
    _call(server, "GET", f"/api/books/{book}/music")
    music_local.set_analyzer(lambda _path: dict(CALM_ANALYSIS, fitsUnderNarration=1.0,
                                                sd={"valence": 0.01, "arousal": 0.01, "tension": 0.01}))
    mine = _import(server, songs["mp3"])["added"][0]["link"]
    assert [t["link"] for t in app._music_candidates(0.3, -0.6) if t["link"] == mine] == [mine]
    _calm_plan(paths, {})
    _status, view = _call(server, "PUT", f"/api/books/{book}/music", {"family": ""})  # chọn lại trên các đoạn đang có
    chosen = [scene["link"] for scene in view["plan"]["scenes"]]
    assert mine in chosen, "đúng không khí và độ chắc chắn cao thì thắng bài danh mục (cùng cách chấm điểm)"
    assert view["plan"]["scenes"][chosen.index(mine)]["pinned"] is False
    # Ở "Đổi bài", bài này vẫn có mặt trong nhóm của tôi kèm điểm.
    first_other = next(s for s in view["plan"]["scenes"] if s["link"] != mine)
    _status, offered = _call(server, "GET", f"/api/books/{book}/music/scenes/{quote(first_other['key'], safe='')}/alternatives")
    item = next(item for item in offered["mine"] if item["link"] == mine)
    assert item["analysed"] is True and item["fits"] is True and isinstance(item["score"], float)


def test_removing_a_track_makes_its_pin_unavailable_and_the_scene_chooses_another(studio, tmp_path: Path, songs) -> None:  # noqa: F811
    paths, app, server, _runner = studio
    _with_catalog(app, tmp_path)
    book = book_id(paths.root)
    view = _call(server, "GET", f"/api/books/{book}/music")[1]
    mine = _import(server, songs["mp3"])["added"][0]["link"]
    key = view["plan"]["scenes"][0]["key"]
    assert _pin(server, book, key, mine)["plan"]["scenes"][0]["link"] == mine
    _call(server, "DELETE", f"/api/music/local/{music_plan.local_hash(mine)}")
    after = _call(server, "PUT", f"/api/books/{book}/music", {"levelDb": -22})[1]
    scene = after["plan"]["scenes"][0]
    assert scene["link"] != mine and scene.get("pinUnavailable") is True and after["overrides"]["pins"][key] == mine, \
        "lựa chọn của người dùng được giữ, chỉ lần dựng này đoạn chọn bài khác"


# ---- đi theo sách và đồng bộ ---------------------------------------------------------------------------------------------
def _local_plan(project: Path, *links: str) -> None:
    """Rãnh nhạc của `project` (chương 1) dùng lần lượt các bài `links` - bài của "Nhạc của tôi" với thông tin như plan thật."""
    scenes = [{"chapterId": 1, "start": i * 30.0, "end": i * 30.0 + 30.0, "link": link, "key": f"1:{i + 1}", "pinned": True}
              for i, link in enumerate(links)]
    plan = {"version": music_plan.PLAN_VERSION, "enabled": True, "levelDb": -20.0, "scenes": scenes,
            "tracks": {link: {"title": "khong_the", "creator": "", "source": "local", "duration": 62} for link in links}}
    (project / music_plan.PLAN_FILE).write_text(json.dumps(plan), encoding="utf-8")


def test_a_pinned_local_track_is_embedded_in_the_book_file_and_plays_on_another_machine(studio, tmp_path: Path, songs) -> None:  # noqa: F811
    _paths, app, server, _runner = studio
    project = make_project(tmp_path / "may_cu")
    mine = app.my_music.import_file(songs["flac"])[0]["link"]
    unused = app.my_music.import_file(songs["ogg"])[0]["link"]
    _local_plan(project, mine)
    digest = music_plan.local_hash(mine)
    out = bookfile.pack(project, tmp_path / f"sach{bookfile.EXTENSION}", music_track=app.music_export_source())
    name = f"music/{digest}.flac"
    with zipfile.ZipFile(out) as archive:
        assert archive.getinfo(name).compress_type == zipfile.ZIP_STORED, "nhạc phát thẳng trong gói"
        assert archive.read(name) == songs["flac"].read_bytes()
        assert not any(music_plan.local_hash(unused) in entry for entry in archive.namelist()), "bài không ghim không đi theo"
    with bookfile.BookFile(out) as opened:
        opened.verify()
        music = json.loads(opened.read("book.json"))["music"]
    info = music["tracks"][name]
    assert info["link"] == mine and info["file"] == name and info["title"] == "khong_the" and "license" not in info
    assert isinstance(info["lufs"], float) and music["chapters"]["1"][0]["track"] == name
    # Máy khác (không có kho của người nhập): mở file là phát được; ghi công = tên + nghệ sĩ của file, không giấy phép.
    other = app.open_book_file(str(out))["id"]
    assert packages.is_package(app.library.resolve_listenable(other))
    status, cues = _call(server, "GET", f"/api/books/{other}/music/chapters/1")
    cue = cues["cues"][0]
    assert cue["link"] == mine and cue["src"] == f"/api/books/{other}/music/files/{digest}.flac"
    status, body, _headers = _request(server.port, "GET", cue["src"], headers={"X-Ebook-Token": "t"})
    assert status == 200 and body == songs["flac"].read_bytes()
    assert cues["credits"][mine] == {"title": "khong_the"}


def test_a_local_track_that_is_gone_is_left_out_of_the_book_and_leaves_silence(studio, tmp_path: Path, songs) -> None:  # noqa: F811
    _paths, app, _server, _runner = studio
    app._music_catalog = MusicCatalog(tmp_path / "empty_cache", str(tmp_path / "khong_co"))  # không bài thay thế nào
    project = make_project(tmp_path / "may_cu")
    mine = app.my_music.import_file(songs["flac"])[0]["link"]
    _local_plan(project, mine)
    app.my_music.remove(music_plan.local_hash(mine))
    assert app.music_track_for_export(mine) is None and app.music_track_available(mine) is False
    out = bookfile.pack(project, tmp_path / f"sach{bookfile.EXTENSION}", music_track=app.music_export_source())
    with zipfile.ZipFile(out) as archive:
        assert not any(entry.startswith("music/") for entry in archive.namelist())


def test_the_phone_gets_the_pinned_local_track_in_its_package_but_only_for_this_books_scenes(studio, tmp_path: Path, songs) -> None:  # noqa: F811
    from abook.webui.library import Library, Preferences
    from abook.webui.listening import Listening
    from abook.webui.sync import Devices, SyncApp, manifest

    _paths, app, _server, _runner = studio
    project = make_project(tmp_path / "may_cu")
    mine = app.my_music.import_file(songs["flac"])[0]["link"]
    unused = app.my_music.import_file(songs["ogg"])[0]["link"]
    _local_plan(project, mine)
    source = app.music_sync_source()
    listening = Listening(tmp_path / "listening2.json")
    package = manifest(project, "b", listening, music_track=source)
    name = f"music/{music_plan.local_hash(mine)}.flac"
    assert list(package["music"]["tracks"]) == [name] and package["music"]["tracks"][name]["link"] == mine
    sync = SyncApp(Library(Preferences(tmp_path / "prefs2.json")), listening, Devices(tmp_path / "devices2.json"), "may",
                   music_track=source)
    found = sync.resolve_file(project, name)
    assert isinstance(found, Path) and found.read_bytes() == songs["flac"].read_bytes()
    assert sync.resolve_file(project, f"music/{music_plan.local_hash(unused)}.ogg") is None, "bài không thuộc cuốn này"
    assert sync.resolve_file(project, f"music/{music_plan.local_hash(mine)}.mp3") is None, "đuôi phải đúng file thật"
    assert sync.resolve_file(project, f"music/{'0' * 40}.flac") is None


def test_a_project_file_carries_the_local_track_and_the_other_machine_keeps_the_pin(tmp_path: Path, songs) -> None:
    from tests.test_project_file import _app, _project

    project = _project(tmp_path)
    app = _app(tmp_path, project.parent)
    mine = app.my_music.import_file(songs["flac"])[0]["link"]
    _local_plan(project, mine)
    packed = projectfile.pack(project, tmp_path / f"p{projectfile.EXTENSION}", music_track=app.music_export_source())
    digest = music_plan.local_hash(mine)
    with ProjectFile(packed) as opened:
        assert f"music/{digest}.flac" in opened.manifest["files"]
    other = _app(tmp_path / "may_khac", tmp_path / "thu_vien_moi")
    book = other.open_book_file(str(packed))["id"]
    folder = other.library.resolve_listenable(book)
    assert other.my_music.entries() == [], "bài của người khác không lẫn vào danh sách của tôi"
    assert other.music_track_available(mine) and other.music_track_cached(mine).read_bytes() == songs["flac"].read_bytes()
    cue = other.music_cues(book, 1)["cues"][0]
    assert cue["link"] == mine and cue["src"].endswith(f"/music/files/{digest}.flac")
    assert other._music_lookup([mine], folder)[mine]["title"] == "khong_the", "tên bài không mất khi dựng lại trên máy khác"


def test_the_file_dialog_is_asked_for_music_only_when_importing_music(studio) -> None:  # noqa: F811
    _paths, app, server, _runner = studio
    asked: list[tuple[str, str]] = []

    class Dialogs:
        def pick_files(self, title: str, start: str, kind: str = "chapters") -> list[str]:
            asked.append((title, kind))
            return ["D:/Nhạc/a.mp3"]

    app.dialogs = Dialogs()
    assert _call(server, "POST", "/api/dialog/files", {"title": "Chọn nhạc", "kind": "music"})[1] == {"paths": ["D:/Nhạc/a.mp3"]}
    _call(server, "POST", "/api/dialog/files", {"title": "Chọn chương"})
    _call(server, "POST", "/api/dialog/files", {"title": "Lạ", "kind": "../../etc"})
    assert asked == [("Chọn nhạc", "music"), ("Chọn chương", "chapters"), ("Lạ", "chapters")]


def test_the_music_of_mine_routes_are_not_open_to_a_remote_studio() -> None:
    from abook.webui import remote_studio

    for method, path in (("GET", "/api/music/local"), ("POST", "/api/music/local/import"), ("DELETE", "/api/music/local/" + "a" * 40),
                         ("GET", "/api/music/local/" + "a" * 40 + "/file"), ("POST", "/api/dialog/files")):
        assert not remote_studio.permitted(method, path), (method, path)
    assert remote_studio.permitted("GET", f"/api/books/abc/music/files/{'a' * 40}.flac"), "đường theo sách thì mở cho trình phát"
    assert not remote_studio.permitted("GET", f"/api/books/abc/music/files/{'a' * 40}.exe")


# ---- bài có vẻ có lời hát (đầu dò lời hát của music_student): máy không tự chọn, ghim tay vẫn được ------------------------------
def _vocal_analyzer(path: Path) -> dict:
    """Hai bài giống hệt nhau về không khí; chỉ bài .ogg bị đầu dò báo có lời."""
    return dict(CALM_ANALYSIS, fitsUnderNarration=1.0, sd={"valence": 0.01, "arousal": 0.01, "tension": 0.01},
                vocals=0.93 if path.suffix == ".ogg" else 0.04, vocalsLikely=path.suffix == ".ogg")


def test_clean_analysis_keeps_the_vocal_flags_and_clamps_the_probability() -> None:
    cleaned = music_local.clean_analysis({"valence": 0.1, "arousal": 0.2, "vocals": 1.7, "vocalsLikely": True})
    assert cleaned["vocals"] == 1.0 and cleaned["vocalsLikely"] is True
    assert music_local.clean_analysis({"valence": 0.1, "arousal": 0.2, "vocals": -3})["vocals"] == 0.0
    plain = music_local.clean_analysis({"valence": 0.1, "arousal": 0.2, "vocals": "nhiều", "vocalsLikely": "có"})
    assert "vocals" not in plain and "vocalsLikely" not in plain, "không phải số / không phải bool thì bỏ, không đoán"
    assert "vocals" not in music_local.clean_analysis({"valence": 0.1, "arousal": 0.2, "vocals": float("nan")})
    assert music_local.clean_analysis({"valence": 0.1, "arousal": 0.2, "vocalsLikely": False})["vocalsLikely"] is False


def test_the_auto_switch_decides_whether_the_machine_may_pick_a_track_by_itself(tmp_path: Path, songs) -> None:
    music_local.set_analyzer(_vocal_analyzer)
    store = LocalMusic(tmp_path / "mine")
    plain, _ = store.import_file(songs["mp3"])
    sung, _ = store.import_file(songs["ogg"])
    assert "auto" not in plain and "auto" not in sung, "vắng = mặc định"
    plain_digest, sung_digest = music_plan.local_hash(plain["link"]), music_plan.local_hash(sung["link"])
    assert music_local.auto_excluded({}) is False
    assert music_local.auto_excluded({"vocalsLikely": True}) is True
    assert music_local.auto_excluded({"vocalsLikely": True, "auto": "on"}) is False
    assert music_local.auto_excluded({"auto": "off"}) is True and music_local.auto_excluded({"vocalsLikely": True, "auto": "off"}) is True
    # "off" loại cả bài không có lời; ghim tay không đi qua near nên vẫn dùng được
    assert store.set_auto(plain_digest, "off") is True
    assert store.near(0.3, -0.6) == [], "bài thường bị tắt và bài có lời đều không vào danh sách tự chọn"
    assert next(t for t in LocalMusic(tmp_path / "mine").entries() if t["link"] == plain["link"])["auto"] == "off", "ghi vào sổ của máy"
    assert store.file(plain["link"]) is not None and plain["link"] in store.lookup([plain["link"]])
    music_local.set_analyzer_id("model-cong-tac")  # phân tích lại không làm mất công tắc
    assert store.reanalyse() == 2 and store.near(0.3, -0.6) == []
    assert store.lookup([plain["link"]])[plain["link"]]["auto"] == "off"
    # "on" cho bài có lời vào lại; None về mặc định
    assert store.set_auto(sung_digest, "on") is True and [t["link"] for t in store.near(0.3, -0.6)] == [sung["link"]]
    assert store.set_auto(plain_digest, None) is True and {t["link"] for t in store.near(0.3, -0.6)} == {plain["link"], sung["link"]}
    assert store.set_auto(sung_digest, None) is True and [t["link"] for t in store.near(0.3, -0.6)] == [plain["link"]]
    assert "auto" not in next(t for t in store.entries() if t["link"] == plain["link"])
    assert store.set_auto("0" * 40, "on") is False
    with pytest.raises(ValueError):
        store.set_auto(plain_digest, "maybe")


def test_a_track_that_probably_has_lyrics_is_not_an_automatic_candidate_until_the_user_allows_it(tmp_path: Path, songs) -> None:
    music_local.set_analyzer(_vocal_analyzer)
    store = LocalMusic(tmp_path / "mine")
    plain, _ = store.import_file(songs["mp3"])
    sung, _ = store.import_file(songs["ogg"])
    assert sung["analysed"] is True and sung["vocalsLikely"] is True and "auto" not in sung
    assert [t["link"] for t in store.near(0.3, -0.6)] == [plain["link"]], "bài có lời không vào danh sách tự chọn, nhưng không bị xoá"
    assert {t["link"] for t in store.entries()} == {plain["link"], sung["link"]}, "vẫn nằm trong kho"
    digest = music_plan.local_hash(sung["link"])
    assert store.set_auto(digest, "on") is True
    assert {t["link"] for t in store.near(0.3, -0.6)} == {plain["link"], sung["link"]}
    assert next(t for t in LocalMusic(tmp_path / "mine").entries() if t["link"] == sung["link"])["auto"] == "on", "ghi vào sổ của máy"
    music_local.set_analyzer_id("model-moi")  # phân tích lại không làm mất lựa chọn của người dùng
    assert store.reanalyse() == 2 and store.near(0.3, -0.6)[0]["vocalsLikely"] is True
    assert {t["link"] for t in store.near(0.3, -0.6)} == {plain["link"], sung["link"]}
    assert store.set_auto(digest, None) is True and [t["link"] for t in store.near(0.3, -0.6)] == [plain["link"]]
    assert store.set_auto("0" * 40, "on") is False


def test_the_planner_never_picks_a_track_with_lyrics_by_itself_but_a_pin_still_plays_it(studio, tmp_path: Path, songs) -> None:  # noqa: F811
    paths, app, server, _runner = studio
    _with_catalog(app, tmp_path)
    book = book_id(paths.root)
    _call(server, "GET", f"/api/books/{book}/music")
    music_local.set_analyzer(_vocal_analyzer)
    plain = _import(server, songs["mp3"])["added"][0]["link"]
    sung = _import(server, songs["ogg"])["added"][0]["link"]
    assert {t["link"] for t in app._music_candidates(0.3, -0.6)} >= {plain} and sung not in {t["link"] for t in app._music_candidates(0.3, -0.6)}
    _calm_plan(paths, {})
    view = _call(server, "PUT", f"/api/books/{book}/music", {"family": ""})[1]
    chosen = [scene["link"] for scene in view["plan"]["scenes"]]
    assert plain in chosen, "bài giống hệt nhưng không có lời thì vẫn được tự chọn"
    assert sung not in chosen, "bài có lời không bao giờ được tự chọn"
    key = view["plan"]["scenes"][0]["key"]
    pinned = _pin(server, book, key, sung)["plan"]["scenes"][0]
    assert pinned["link"] == sung and pinned["pinned"] is True, "ghim thắng"
    # công tắc tự chọn: qua API, khoá nằm trong danh sách của máy và bài vào / ra danh sách tự chọn
    digest = music_plan.local_hash(sung)
    status, body = _call(server, "POST", f"/api/music/local/{digest}/auto", {"auto": "on"})
    assert status == 200 and next(t for t in body["tracks"] if t["link"] == sung)["auto"] == "on"
    assert sung in {t["link"] for t in app._music_candidates(0.3, -0.6)}
    for bad in ({"auto": "co"}, {"auto": True}, {"auto": 1}, {}, {"ok": True}):
        assert _call(server, "POST", f"/api/music/local/{digest}/auto", bad)[0] == 400, bad
    assert _call(server, "POST", f"/api/music/local/{'0' * 40}/auto", {"auto": "on"})[0] == 404
    assert _call(server, "POST", f"/api/music/local/{'0' * 40}/auto", {"auto": None})[0] == 404
    status, body = _call(server, "POST", f"/api/music/local/{digest}/auto", {"auto": None})
    assert status == 200 and "auto" not in next(t for t in body["tracks"] if t["link"] == sung)
    assert sung not in {t["link"] for t in app._music_candidates(0.3, -0.6)}
    plain_digest = music_plan.local_hash(plain)
    status, body = _call(server, "POST", f"/api/music/local/{plain_digest}/auto", {"auto": "off"})
    assert status == 200 and next(t for t in body["tracks"] if t["link"] == plain)["auto"] == "off"
    assert plain not in {t["link"] for t in app._music_candidates(0.3, -0.6)}, "bài thường bị tắt cũng không được tự chọn"
    pinned = _pin(server, book, key, plain)["plan"]["scenes"][0]
    assert pinned["link"] == plain and pinned["pinned"] is True, "ghim tay vẫn thắng công tắc tắt"


def test_the_auto_switch_route_is_not_open_to_a_remote_studio() -> None:
    from abook.webui import remote_studio

    assert not remote_studio.permitted("POST", "/api/music/local/" + "a" * 40 + "/auto")


def test_the_keys_that_explain_why_the_machine_skips_a_track_reach_the_swap_list() -> None:
    """"Đổi bài" của một đoạn nói đúng như Cài đặt: bài có vẻ có lời / bài bạn đã tắt mang nhãn của nó (ui: musicLocal.mineNote)."""
    assert music_local.auto_keys({"title": "x", "vocalsLikely": True, "auto": "off", "valence": 0.1}) == {"vocalsLikely": True, "auto": "off"}
    assert music_local.auto_keys({"title": "x", "vocalsLikely": False}) == {"vocalsLikely": False}
    assert music_local.auto_keys({"title": "x"}) == {}, "bài bình thường: không thêm khoá nào"
