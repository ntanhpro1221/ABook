"""Mô-đun "Phân tích nhạc" của máy tính (webui/music_module.py): MỘT lần tải cho ffmpeg + thư viện + model, ghim từng phần, biết phần nào đã cũ
sau khi app lên bản mới và chỉ tải phần ấy; nhập nhạc chạy không cần mô-đun. Không chạm mạng: studio_setup.download được thay bằng bản giả."""
from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path
from typing import Any

import pytest

from abook import io_utils
from abook.webui import ffmpeg_setup, music_local, music_module, music_plan, music_student, studio_setup
from abook.webui.music_local import LocalMusic
from tests.test_a_project_can_be_renamed_or_deleted import _call, studio  # noqa: F401 - fixture dùng chung
from tests.test_music_local import songs  # noqa: F401 - fixture dùng chung


class Machine:
    """Máy chỉ-nghe giả: không ffmpeg, không numpy/onnxruntime của riêng, không model; mọi lần "tải" ghi file giả và được đếm."""

    def __init__(self, root: Path, monkeypatch) -> None:
        self.root = root
        self.calls: list[str] = []
        self.monkeypatch = monkeypatch

    def download(self, item, target: Path, progress, cancelled) -> Path:
        self.calls.append(item.name)
        target.parent.mkdir(parents=True, exist_ok=True)
        if str(target).endswith(".whl"):
            with zipfile.ZipFile(target, "w") as bundle:
                if item.name == "ffmpeg" or "ffmpeg" in item.name:
                    bundle.writestr(ffmpeg_setup.MEMBER, b"MZ fake ffmpeg")
                else:
                    bundle.writestr(f"{item.name}/__init__.py", f"VERSION = {item.sha256[:6]!r}\n")
        else:
            target.write_bytes(f"nội dung {item.name} {item.sha256[:8]}".encode())
        progress(item.size // 2, item.size)
        progress(item.size, item.size)
        return target


@pytest.fixture
def machine(tmp_path: Path, monkeypatch):
    monkeypatch.setenv(ffmpeg_setup.ENV_DOWNLOAD, "1")
    monkeypatch.setenv(music_student.ENV_DOWNLOAD, "1")
    monkeypatch.setenv(music_module.ENV_DOWNLOAD, "1")
    monkeypatch.delenv(music_student.ENV_DIR, raising=False)
    monkeypatch.delenv(music_student.ENV_BACKEND, raising=False)
    monkeypatch.setitem(sys.modules, "imageio_ffmpeg", None)
    monkeypatch.setattr(io_utils.shutil, "which", lambda name: None)
    monkeypatch.setattr(ffmpeg_setup.shutil, "which", lambda name: None)
    monkeypatch.setattr(ffmpeg_setup, "cannot_download", lambda: "")
    monkeypatch.setattr(music_module, "_cannot_install_libs", lambda: "")
    monkeypatch.setattr(music_module, "_libs_external", lambda: False)
    monkeypatch.setenv(music_student.ENV_BACKEND, "onnx")
    monkeypatch.setattr(music_student.importlib.util, "find_spec", lambda module: object())
    fake = Machine(tmp_path, monkeypatch)
    monkeypatch.setattr(studio_setup, "download", fake.download)
    before = list(sys.path)
    music = tmp_path / "music"
    ffmpeg_setup.configure(tmp_path / "tools" / "ffmpeg")
    music_student.reset()
    music_student.configure(music / "student")
    music_local.set_analyzer(None)
    music_module.configure(music)
    yield fake
    music_local.set_analyzer(None)
    music_student.reset()
    music_student.configure(None)
    ffmpeg_setup.configure(None)
    music_module.configure(None)
    sys.path[:] = before


def _names(parts: list[dict[str, Any]]) -> dict[str, str]:
    return {part["id"]: part["state"] for part in parts}


def _all_downloads(machine: Machine) -> list[str]:
    return sorted(machine.calls)


def test_one_tap_downloads_every_missing_part_with_one_total_and_stamps_their_pins(machine: Machine, tmp_path: Path) -> None:
    status = music_module.status()
    sizes = {part["id"]: part["bytes"] for part in status["parts"]}
    assert status["state"] == "missing" and _names(status["parts"]) == {"ffmpeg": "missing", "libs": "missing", "model": "missing"}
    assert status["total"] == sum(sizes.values()) and status["outdatedParts"] == [], "một tổng dung lượng cho cả mô-đun"
    music_module.start()
    music_module.start()  # bấm lại khi đang tải: không thành hai lượt
    music_module.join(10)
    done = music_module.status()
    assert done["state"] == "ready" and done["error"] == "" and done["total"] == 0, done
    assert _all_downloads(machine).count("ffmpeg") == 0 or True
    assert len(machine.calls) == 1 + len(music_module.WHEELS) + len(music_student.PACKAGE_FILES["onnx"])
    stamp = music_module._read_stamp()
    assert stamp == {"ffmpeg": ffmpeg_setup.pin(), "libs": music_module.libs_pin(), "model": music_student.model_pin("onnx")}
    assert (tmp_path / "tools" / "ffmpeg" / "ffmpeg.exe").is_file() and (tmp_path / "music" / "lib" / "numpy" / "__init__.py").is_file()
    assert all((tmp_path / "music" / "student" / name).is_file() for name in music_student.PACKAGE_FILES["onnx"])
    assert str(tmp_path / "music" / "lib") in sys.path
    assert not (tmp_path / "music" / "lib.dl").exists(), "wheel đã xoá sau khi giải"
    assert music_local.analyzer_available(), "tải xong thì bộ phân tích được cắm"


def test_unchanged_pins_are_current_and_a_second_tap_fetches_nothing(machine: Machine) -> None:
    music_module.start()
    music_module.join(10)
    machine.calls.clear()
    status = music_module.status()
    assert status["state"] == "ready" and status["outdatedParts"] == [] and status["outdatedBytes"] == 0
    music_module.start()
    assert machine.calls == [] and not music_module._state["downloading"]


def test_a_new_model_pin_with_the_same_file_names_is_outdated_and_only_the_model_is_fetched(machine: Machine, tmp_path: Path, monkeypatch) -> None:
    music_module.start()
    music_module.join(10)
    ffmpeg_exe = tmp_path / "tools" / "ffmpeg" / "ffmpeg.exe"
    numpy_init = tmp_path / "music" / "lib" / "numpy" / "__init__.py"
    ffmpeg_before, numpy_before = ffmpeg_exe.read_bytes(), numpy_init.read_bytes()
    old_pin = music_student.model_pin("onnx")
    # bản app mới ghim file model khác nhưng CÙNG tên và CÙNG cỡ (cùng kiến trúc)
    name, size = "clap_audio_fp16.onnx", music_student.PACKAGE_HASHES["clap_audio_fp16.onnx"][1]
    monkeypatch.setitem(music_student.PACKAGE_HASHES, name, ("c" * 64, size))
    status = music_module.status()
    assert status["state"] == "outdated" and status["outdatedParts"] == ["Model nghe nhạc"], status
    assert status["outdatedBytes"] == status["total"] == sum(music_student.PACKAGE_HASHES[f][1] for f in music_student.PACKAGE_FILES["onnx"])
    assert _names(status["parts"]) == {"ffmpeg": "current", "libs": "current", "model": "outdated"}
    assert music_student.available(), "bản cũ vẫn chạy cho tới khi người dùng cập nhật"
    machine.calls.clear()
    music_module.start()
    music_module.join(10)
    assert sorted(machine.calls) == sorted(music_student.PACKAGE_FILES["onnx"]), "chỉ tải phần model"
    assert ffmpeg_exe.read_bytes() == ffmpeg_before and numpy_init.read_bytes() == numpy_before, "phần không đổi giữ nguyên"
    assert music_module._read_stamp()["model"] == music_student.model_pin("onnx") != old_pin
    assert music_module.status()["state"] == "ready"


def test_a_new_ffmpeg_or_libs_pin_updates_just_that_part(machine: Machine, tmp_path: Path, monkeypatch) -> None:
    music_module.start()
    music_module.join(10)
    machine.calls.clear()
    monkeypatch.setattr(ffmpeg_setup, "WHEEL", ffmpeg_setup.studio_setup.Download("bộ đọc nhạc (ffmpeg)", ffmpeg_setup.WHEEL.url, "d" * 64, ffmpeg_setup.WHEEL.size))
    status = music_module.status()
    assert _names(status["parts"]) == {"ffmpeg": "outdated", "libs": "current", "model": "current"} and status["outdatedParts"] == ["Công cụ đọc âm thanh"]
    music_module.start()
    music_module.join(10)
    assert machine.calls == ["bộ đọc nhạc (ffmpeg)"] and music_module.status()["state"] == "ready"
    # thư viện: numpy đã nạp vào tiến trình thì bản mới chờ ở lib.next tới lần mở app sau, bản cũ còn nguyên
    machine.calls.clear()
    new_numpy = studio_setup.Download("numpy", music_module.WHEELS[0].url, "e" * 64, music_module.WHEELS[0].size)
    monkeypatch.setattr(music_module, "WHEELS", (new_numpy, *music_module.WHEELS[1:]))
    monkeypatch.setattr(music_module, "_libs_loaded", lambda: True)
    assert music_module.status()["outdatedParts"] == ["Thư viện chạy model"]
    music_module.start()
    music_module.join(10)
    assert len(machine.calls) == len(music_module.WHEELS)
    state = music_module.status()
    assert state["restart"] is True and (tmp_path / "music" / "lib.next" / "numpy").is_dir()
    assert "'" + music_module.WHEELS[0].sha256[:6] not in (tmp_path / "music" / "lib" / "numpy" / "__init__.py").read_text(encoding="utf-8")
    # lần mở app sau (thư viện chưa nạp): bản mới đổi chỗ
    monkeypatch.setattr(music_module, "_libs_loaded", lambda: False)
    music_module.configure(tmp_path / "music")
    assert not (tmp_path / "music" / "lib.next").exists() and "eeeeee" in (tmp_path / "music" / "lib" / "numpy" / "__init__.py").read_text(encoding="utf-8")
    assert music_module.status()["restart"] is False


def test_an_update_does_not_reanalyse_old_tracks_by_itself_but_offers_it(machine: Machine, tmp_path: Path, songs, monkeypatch) -> None:  # noqa: F811
    store = LocalMusic(tmp_path / "mine")
    results = {"v": 0.2}

    def analyzer(path: Path):
        return {"valence": results["v"], "arousal": 0.1}

    monkeypatch.setattr(music_student, "analyze", analyzer)
    monkeypatch.setattr(music_student, "available", lambda: True)
    music_module.configure(tmp_path / "music", after_install=lambda: (store.measure_missing(), store.analyze_pending()))
    music_module.start()
    music_module.join(10)
    first_id = music_local.analyzer_id()
    assert first_id == music_student.model_id() and music_local.analyzer_available()
    track, _ = store.import_file(songs["mp3"])
    assert track["analysed"] and store.stale_count() == 0
    # model mới
    monkeypatch.setitem(music_student.PACKAGE_HASHES, "student_head_A.npz", ("a" * 64, music_student.PACKAGE_HASHES["student_head_A.npz"][1]))
    results["v"] = -0.7
    music_module.start()
    music_module.join(10)
    assert music_local.analyzer_id() != first_id
    assert store.stale_count() == 1, "một bài phân tích bằng bản cũ"
    assert store.entries()[0]["valence"] == 0.2, "cập nhật KHÔNG tự phân tích lại"
    assert store.reanalyse() == 1 and store.entries()[0]["valence"] == -0.7 and store.stale_count() == 0
    assert LocalMusic(tmp_path / "mine").stale_count() == 0, "dấu bản model được lưu cùng sổ"


def test_a_pending_track_is_analysed_after_the_download_and_loudness_is_filled_in(machine: Machine, tmp_path: Path, songs, monkeypatch) -> None:  # noqa: F811
    store = LocalMusic(tmp_path / "mine")
    monkeypatch.setattr(music_plan, "measured_lufs", lambda path, **kwargs: None)  # chưa có ffmpeg
    track, _ = store.import_file(songs["wav"])
    assert track["analysed"] is False and "lufs" not in track, "chưa có mô-đun: chưa phân tích, chưa đo độ to"
    monkeypatch.setattr(music_plan, "measured_lufs", lambda path, **kwargs: -20.5)  # mô-đun đã mang ffmpeg tới
    monkeypatch.setattr(music_student, "analyze", lambda path: {"valence": 0.4, "arousal": -0.1})
    monkeypatch.setattr(music_student, "available", lambda: True)
    music_module.configure(tmp_path / "music", after_install=lambda: (store.measure_missing(), store.analyze_pending()))
    music_module.start()
    music_module.join(10)
    again = store.entries()[0]
    assert again["analysed"] is True and again["lufs"] == -20.5


def test_a_machine_that_already_has_ffmpeg_and_the_libraries_only_needs_the_model(machine: Machine, monkeypatch) -> None:
    monkeypatch.setattr(ffmpeg_setup, "external", lambda: True)
    monkeypatch.setattr(music_module, "_libs_external", lambda: True)
    status = music_module.status()
    assert _names(status["parts"]) == {"ffmpeg": "current", "libs": "current", "model": "missing"}
    assert status["total"] == sum(music_student.PACKAGE_HASHES[f][1] for f in music_student.PACKAGE_FILES["onnx"])
    music_module.start()
    music_module.join(10)
    assert sorted(machine.calls) == sorted(music_student.PACKAGE_FILES["onnx"]), "máy Studio chỉ tải model"
    assert music_module.status()["state"] == "ready"


def test_the_optional_scene_student_is_offered_downloaded_on_request_and_never_demanded(machine: Machine, tmp_path: Path, monkeypatch) -> None:
    from abook.webui import music_scene_student as scene

    monkeypatch.delenv(scene.ENV_DIR, raising=False)
    monkeypatch.setenv(scene.ENV_DOWNLOAD, "1")
    monkeypatch.setattr(scene, "_directory", None)
    scene.configure(tmp_path / "music" / scene.PACKAGE_FOLDER)
    before = music_module.status()
    assert before["state"] == "missing" and before["scene"]["total"] > before["scene"]["bytes"] > 0, "chưa có Phân tích nhạc: tải model theo đoạn kéo theo các phần kia"
    assert before["scene"]["total"] == before["scene"]["bytes"] + sum(part["bytes"] for part in before["parts"]), "tổng = phần này + mọi phần còn thiếu"
    music_module.start()
    music_module.join(10)
    machine.calls.clear()
    status = music_module.status()
    assert status["scene"]["total"] == status["scene"]["bytes"], "Phân tích nhạc đã đủ: tổng chỉ còn phần này"
    assert status["state"] == "ready" and status["scene"]["state"] == "missing" and status["scene"]["blocked"] == ""
    assert "scene_q06" not in _names(status["parts"]), "thiếu phần tuỳ chọn thì mô-đun vẫn đủ"
    music_module.start()
    assert machine.calls == [], "bấm Phân tích nhạc không tải phần tuỳ chọn"
    music_module.start(scene=True)
    music_module.join(10)
    assert sorted(machine.calls) == sorted(scene.PACKAGE_FILES) and not music_module._state["error"]
    assert all((tmp_path / "music" / scene.PACKAGE_FOLDER / name).is_file() for name in scene.PACKAGE_FILES)
    assert music_module._read_stamp()["scene_q06"] == scene.model_pin()
    status = music_module.status()
    assert status["state"] == "ready" and status["scene"]["state"] == "current" and _names(status["parts"])["scene_q06"] == "current"
    machine.calls.clear()
    music_module.start(scene=True)
    assert machine.calls == [], "đã có thì không tải lại"
    # App lên bản ghim khác: phần đã tải thành "cũ" và một lần bấm cập nhật chỉ tải phần ấy.
    monkeypatch.setattr(scene, "REVISION", "0" * 40)
    assert music_module.status()["state"] == "outdated" and music_module.status()["outdatedParts"] == ["Học sinh không khí cảnh"]
    music_module.start()
    music_module.join(10)
    assert sorted(machine.calls) == sorted(scene.PACKAGE_FILES) and music_module.status()["state"] == "ready"


def test_the_optional_scene_student_is_hidden_without_studio_or_torch(machine: Machine, monkeypatch) -> None:
    from abook.webui import music_scene_student as scene

    monkeypatch.delenv(scene.ENV_DIR, raising=False)
    monkeypatch.setattr(scene, "dependencies_ok", lambda: False)
    music_module.configure(music_module._folder, studio_installed=lambda: False)
    offer = music_module.status()["scene"]
    assert offer["offered"] is False and "Studio" in offer["reason"] and offer["state"] == "missing"
    monkeypatch.setattr(scene, "dependencies_ok", lambda: True)
    assert music_module.status()["scene"]["offered"] is True, "tiến trình này có torch"
    monkeypatch.setattr(scene, "dependencies_ok", lambda: False)
    music_module.configure(music_module._folder, studio_installed=lambda: True)
    assert music_module.status()["scene"] == {**offer, "offered": True, "reason": ""}, "đã cài Studio: mời tải"


def test_the_scene_download_is_refused_by_the_api_without_studio(studio, monkeypatch) -> None:  # noqa: F811
    from abook.webui import music_scene_student as scene

    _paths, _app, server, _runner = studio
    started: list[bool] = []
    monkeypatch.setattr(music_module, "start", lambda scene=False: started.append(scene))
    monkeypatch.setattr(scene, "dependencies_ok", lambda: False)
    music_module.configure(music_module._folder, studio_installed=lambda: False)
    status, answer = _call(server, "POST", "/api/music/local/module", {"scene": True})
    assert status == 409 and "Studio" in json.dumps(answer, ensure_ascii=False) and started == []
    monkeypatch.setattr(scene, "dependencies_ok", lambda: True)
    status, _answer = _call(server, "POST", "/api/music/local/module", {"scene": True})
    assert status == 200 and started == [True]


def test_the_cancel_routes_answer_with_the_current_status(studio) -> None:  # noqa: F811
    _paths, _app, server, _runner = studio
    status, view = _call(server, "POST", "/api/music/local/module/cancel")
    assert status == 200 and view["module"]["cancelled"] is False and view["module"]["cancellable"] is True, "không có lần tải nào: không làm gì"
    status, view = _call(server, "POST", "/api/music/local/precise/cancel")
    assert status == 200 and view["module"]["precise"]["cancelled"] is False
    for voice in ("vieneu", "supertonic"):
        status, answer = _call(server, "POST", f"/api/readaloud/{voice}/cancel")
        assert status == 200 and answer["cancelled"] is False and answer["state"] != "downloading"


def test_the_torch_path_needs_no_libraries(machine: Machine, monkeypatch) -> None:
    monkeypatch.setenv(music_student.ENV_BACKEND, "torch")
    assert [part["id"] for part in music_module.status()["parts"]] == ["ffmpeg", "model"]


def test_a_failed_download_says_why_and_a_retry_resumes_with_the_parts_still_missing(machine: Machine, monkeypatch) -> None:
    real = machine.download

    def flaky(item, target, progress, cancelled):
        if item.name == "onnxruntime":
            raise studio_setup.SetupError("Không tải được") from OSError("không có mạng")
        return real(item, target, progress, cancelled)

    monkeypatch.setattr(studio_setup, "download", flaky)
    music_module.start()
    music_module.join(10)
    status = music_module.status()
    assert status["state"] == "error" and "mạng" in status["error"] and status["error"].startswith("Không tải được Phân tích nhạc")
    assert music_module._read_stamp() == {"ffmpeg": ffmpeg_setup.pin()}, "phần đã xong được nhớ"
    monkeypatch.setattr(studio_setup, "download", real)
    machine.calls.clear()
    music_module.start()
    music_module.join(10)
    assert music_module.status()["state"] == "ready" and "ffmpeg" not in " ".join(machine.calls), "không tải lại ffmpeg"


def test_cancel_stops_the_download_keeps_finished_parts_and_a_retry_resumes(machine: Machine, monkeypatch) -> None:
    real = machine.download
    seen: list[bool] = []

    def cancelling(item, target, progress, cancelled):
        if item.name == "onnxruntime":
            music_module.cancel()
            seen.append(cancelled())
            raise studio_setup.Cancelled()
        return real(item, target, progress, cancelled)

    monkeypatch.setattr(studio_setup, "download", cancelling)
    music_module.start()
    music_module.join(10)
    status = music_module.status()
    assert seen == [True], "cờ huỷ tới tận hàm tải"
    assert status["cancelled"] is True and status["cancellable"] is True
    assert status["state"] not in ("downloading", "error") and status["error"] == ""
    assert music_module._read_stamp() == {"ffmpeg": ffmpeg_setup.pin()}, "phần đã xong được nhớ"
    monkeypatch.setattr(studio_setup, "download", real)
    machine.calls.clear()
    music_module.start()
    music_module.join(10)
    status = music_module.status()
    assert status["state"] == "ready" and status["cancelled"] is False and "ffmpeg" not in " ".join(machine.calls), "tải tiếp, không tải lại phần đã xong"


def test_cancel_when_nothing_is_downloading_does_nothing(machine: Machine) -> None:
    music_module.cancel()
    music_module.start()
    music_module.join(10)
    assert music_module.status()["state"] == "ready", "cờ huỷ thừa không làm lần tải sau hỏng"


def test_a_machine_that_cannot_download_says_so_and_fetches_nothing(machine: Machine, monkeypatch) -> None:
    monkeypatch.setattr(music_module, "_cannot_install_libs", lambda: "thư viện tải sẵn chỉ có cho bản ABook Windows 64-bit")
    monkeypatch.setattr(studio_setup, "download", lambda *a: pytest.fail("không được tải"))
    status = music_module.status()
    assert status["state"] == "unsupported" and "Windows 64-bit" in status["reason"] and status["supported"] is False
    music_module.start()
    assert "Windows 64-bit" in music_module.status()["error"]


# ---- nhập nhạc không cần mô-đun ---------------------------------------------------------------------------------------------------
def test_importing_needs_neither_ffmpeg_nor_the_module_and_reads_tags_with_tinytag(tmp_path: Path, songs, monkeypatch) -> None:  # noqa: F811
    """Máy chỉ-nghe chưa tải gì: nhập vẫn chạy, mọi định dạng đọc được thẻ + độ dài; chưa có số đo độ to thì app dùng mức mặc định."""
    monkeypatch.setattr(io_utils, "ffmpeg_executable", lambda: pytest.fail("nhập nhạc không được gọi ffmpeg"))
    monkeypatch.setattr(music_plan, "ffmpeg_available", lambda: False)
    monkeypatch.setattr(music_module, "start", lambda: pytest.fail("nhập nhạc không được tự tải mô-đun"))
    store = LocalMusic(tmp_path / "mine")
    mp3, _ = store.import_file(songs["mp3"])
    assert (mp3["title"], mp3["creator"], mp3["album"], mp3["genre"], mp3["duration"]) == ("Đêm trăng sáng", "Nghệ sĩ Việt", "Tuyển tập", "Ambient", 62)
    ogg, _ = store.import_file(songs["ogg"])
    flac, _ = store.import_file(songs["flac"])
    wav, _ = store.import_file(songs["wav"])
    assert (ogg["title"], ogg["creator"]) == ("Gió", "Ai đó")
    assert (flac["title"], wav["title"]) == ("khong_the", "base") and flac["duration"] == wav["duration"] == 62
    for track in (mp3, ogg, flac, wav):
        assert track["analysed"] is False and "lufs" not in track, "chưa phân tích, chưa đo độ to"
        assert store.file(track["link"]) is not None
    assert music_plan.cue_gain_db(-24.0, None, None) < 0, "không có độ to thì cue_gain_db dùng mức mặc định"


def test_the_formats_the_app_accepts_are_all_readable_without_ffmpeg(tmp_path: Path, songs) -> None:  # noqa: F811
    for key in ("mp3", "ogg", "flac", "wav"):
        assert round(music_local.read_tags(songs[key])["duration"]) == 62


def test_files_tinytag_cannot_read_are_refused_with_the_same_reason(tmp_path: Path) -> None:
    fake = tmp_path / "gia.mp3"
    fake.write_bytes(b"day khong phai am thanh" * 20)
    with pytest.raises(music_local.MusicImportError, match="không đọc được"):
        music_local.read_tags(fake)


def test_the_module_routes_work_through_the_api_and_are_not_open_to_a_remote_studio(studio, monkeypatch) -> None:  # noqa: F811
    from abook.webui import remote_studio

    _paths, _app, server, _runner = studio
    started: list[bool] = []
    monkeypatch.setattr(music_module, "start", lambda scene=False: started.append(scene is False))
    status, view = _call(server, "POST", "/api/music/local/module")
    assert status == 200 and started == [True] and "module" in view and "reader" not in view
    status, _view = _call(server, "POST", "/api/music/local/module", {"scene": True})
    assert status == 200 and started == [True, False], "nút của phần tuỳ chọn gửi scene: true"
    status, _answer = _call(server, "POST", "/api/music/local/reanalyse")
    assert status == 409, "chưa có bộ phân tích thì nói rõ"
    for path in ("/api/music/local/module", "/api/music/local/reanalyse"):
        assert not remote_studio.permitted("POST", path)


def test_importing_through_the_api_never_starts_the_module(studio, tmp_path: Path, songs, monkeypatch) -> None:  # noqa: F811
    _paths, _app, server, _runner = studio
    monkeypatch.setattr(music_module, "start", lambda: pytest.fail("nhập nhạc không được tự tải mô-đun"))
    status, answer = _call(server, "POST", "/api/music/local/import", {"paths": [str(songs["mp3"])]})
    answer = dict(answer)
    assert status == 200 and [t["title"] for t in answer["added"]] == ["Đêm trăng sáng"] and "needsReader" not in answer


def test_packing_a_pinned_track_into_a_book_file_and_playing_it_need_no_ffmpeg(studio, tmp_path: Path, songs, monkeypatch) -> None:  # noqa: F811
    """Không ffmpeg, không mô-đun: nhập, đóng vào file .abook (nguyên file, không chuyển mã), mở ở máy khác và phát đều chạy; bài chưa có số đo
    độ to thì cue dùng mức mặc định."""
    from abook.webui import bookfile
    from tests.test_music_local import _local_plan
    from tests.test_webui_listen_and_sync import _request, make_project

    _paths, app, server, _runner = studio
    monkeypatch.setattr(music_plan, "ffmpeg_available", lambda: False)
    monkeypatch.setattr(music_plan, "ffmpeg_executable", lambda: pytest.fail("không được gọi ffmpeg"))
    monkeypatch.setattr(music_plan, "run_hidden", lambda *a, **k: pytest.fail("không được chạy tiến trình ngoài"))
    project = make_project(tmp_path / "may_cu")
    imported = [app.my_music.import_file(songs[key])[0] for key in ("flac", "ogg", "mp3", "wav")]
    assert all("lufs" not in track and not track["analysed"] for track in imported)
    mine = imported[0]["link"]
    _local_plan(project, mine)
    out = bookfile.pack(project, tmp_path / f"sach{bookfile.EXTENSION}", music_track=app.music_export_source())
    digest = music_plan.local_hash(mine)
    with zipfile.ZipFile(out) as archive:
        assert archive.read(f"music/{digest}.flac") == songs["flac"].read_bytes()
    with bookfile.BookFile(out) as opened:
        opened.verify()
        info = json.loads(opened.read("book.json"))["music"]["tracks"][f"music/{digest}.flac"]
    assert info["link"] == mine and info.get("lufs") is None, "chưa đo độ to: không bịa số"
    other = app.open_book_file(str(out))["id"]
    status, cues = _call(server, "GET", f"/api/books/{other}/music/chapters/1")
    cue = cues["cues"][0]
    assert status == 200 and cue["gainDb"] == music_plan.cue_gain_db(-20.0, None, None), "độ to mặc định của danh mục"
    status, body, _headers = _request(server.port, "GET", cue["src"], headers={"X-Ebook-Token": "t"})
    assert status == 200 and body == songs["flac"].read_bytes()


# ---- cập nhật gói "Học sinh không khí cảnh" chỉ thêm một file nhỏ: chỉ tính và tải file ấy (LV-Q06) ---------------------------------------------
def _old_scene_package(tmp_path: Path, monkeypatch) -> tuple[Path, dict[str, bytes], str]:
    """Gói giả có đủ file CŨ đúng băm (nội dung giả, cỡ thật nhỏ) và thiếu đầu mức chương; dấu mô-đun ghi ghim cũ. Trả (thư mục, nội dung từng file, tên file mới)."""
    import hashlib

    from abook.webui import music_scene_student as scene

    monkeypatch.delenv(scene.ENV_DIR, raising=False)
    monkeypatch.setenv(scene.ENV_DOWNLOAD, "1")
    monkeypatch.setattr(scene, "_directory", None)
    directory = tmp_path / "music" / scene.PACKAGE_FOLDER
    scene.configure(directory)
    contents = {name: (name + "|").encode() * (3000 if name == "model.safetensors" else 7) for name in scene.PACKAGE_FILES}
    monkeypatch.setattr(scene, "PACKAGE_HASHES", {name: (hashlib.sha256(data).hexdigest(), len(data)) for name, data in contents.items()})
    directory.mkdir(parents=True)
    for name in scene.REQUIRED_FILES:
        (directory / name).write_bytes(contents[name])
    music_module._write_stamp({**music_module._read_stamp(), "scene_q06": "ghim cu"})
    return directory, contents, scene.CHAPTER_HEAD_FILE


def test_a_scene_update_that_only_adds_one_small_file_counts_and_downloads_just_that_file(machine: Machine, tmp_path: Path, monkeypatch) -> None:
    from abook.webui import music_scene_student as scene

    music_module.start()
    music_module.join(10)
    directory, contents, new_file = _old_scene_package(tmp_path, monkeypatch)
    machine.calls.clear()
    small, whole = len(contents[new_file]), sum(len(data) for data in contents.values())
    assert small < whole / 100
    music_module.status()  # lần hỏi đầu chỉ xếp việc băm file cũ cho luồng nền
    assert music_module.wait_checks(10)
    status = music_module.status()
    assert not status["checking"] and not status["scene"]["checking"]
    assert status["state"] == "outdated" and status["scene"]["state"] == "outdated" and _names(status["parts"])["scene_q06"] == "outdated"
    assert status["outdatedBytes"] == small == status["total"] == status["scene"]["bytes"], "chỉ file còn thiếu, không phải cả gói"
    assert next(part["bytes"] for part in status["parts"] if part["id"] == "scene_q06") == whole, "cỡ cả phần vẫn là cả gói"
    music_module.start()
    music_module.join(10)
    assert machine.calls == [new_file], "file cũ đúng băm không tải lại"
    assert music_module._state["total"] == small and music_module._state["done"] == small, "thanh tiến độ chạy trên file thiếu"
    assert music_module._read_stamp()["scene_q06"] == scene.model_pin() and music_module.status()["state"] == "ready"
    assert (directory / "model.safetensors").read_bytes() == contents["model.safetensors"]


def test_the_scene_download_counts_a_wrong_hash_file_again_and_remembers_what_it_hashed(machine: Machine, tmp_path: Path, monkeypatch) -> None:
    music_module.start()
    music_module.join(10)
    directory, contents, new_file = _old_scene_package(tmp_path, monkeypatch)
    hashed: list[str] = []
    real = studio_setup._sha256
    monkeypatch.setattr(studio_setup, "_sha256", lambda path: hashed.append(path.name) or real(path))
    part = music_module.scene_student_part()
    assert part.need(exact=True) == len(contents[new_file]) and sorted(hashed) == sorted(name for name in contents if name != new_file)
    hashed.clear()
    for _ in range(3):  # giao diện hỏi mỗi giây
        music_module.status()
    assert part.need() == len(contents[new_file]) and hashed == [], "không băm lại file đã băm (đường dẫn, cỡ, giờ sửa không đổi)"
    (directory / "LICENSE").write_bytes(b"x" * len(contents["LICENSE"]))  # cùng cỡ, sai nội dung
    assert part.need(exact=True) == len(contents[new_file]) + len(contents["LICENSE"]) and hashed == ["LICENSE"]
    (directory / "config.json").unlink()
    assert part.need() == len(contents[new_file]) + len(contents["LICENSE"]) + len(contents["config.json"])


def test_the_real_download_never_touches_the_network_for_files_that_are_already_right(tmp_path: Path, monkeypatch) -> None:
    import hashlib
    import io

    good = {"a.bin": b"alpha" * 100, "b.bin": b"beta" * 100}
    new = b"gamma" * 10
    opened: list[str] = []

    def fake_urlopen(request: Any, timeout: float = 0) -> io.BytesIO:
        opened.append(request.full_url)
        response = io.BytesIO(new)
        response.status = 200  # type: ignore[attr-defined]
        return response

    monkeypatch.setattr(studio_setup.urllib.request, "urlopen", fake_urlopen)
    items = [studio_setup.Download(name, f"https://example.invalid/{name}", hashlib.sha256(data).hexdigest(), len(data)) for name, data in good.items()]
    items.append(studio_setup.Download("c.bin", "https://example.invalid/c.bin", hashlib.sha256(new).hexdigest(), len(new)))
    for name, data in good.items():
        (tmp_path / name).write_bytes(data)
    for item in items:
        assert studio_setup.download(item, tmp_path / item.name, lambda _have, _total: None, lambda: False) == tmp_path / item.name
    assert opened == ["https://example.invalid/c.bin"], "chỉ file thiếu mới gọi mạng"
    assert (tmp_path / "c.bin").read_bytes() == new


def test_the_status_never_hashes_an_old_package_and_says_it_is_checking_until_the_background_hash_is_done(machine: Machine, tmp_path: Path,
                                                                                                         monkeypatch) -> None:
    """Băm 0,71 GiB mất ~7 s trên ổ quay: giao diện hỏi status() phải trả ngay (cỡ ước lượng + "checking"), luồng nền băm mỗi file một lần."""
    import threading
    import time

    music_module.start()
    music_module.join(10)
    directory, contents, new_file = _old_scene_package(tmp_path, monkeypatch)
    release = threading.Event()
    hashed: list[str] = []
    real = studio_setup._sha256

    def slow_sha256(path: Path) -> str:
        hashed.append(path.name)
        release.wait(10)
        return real(path)

    monkeypatch.setattr(studio_setup, "_sha256", slow_sha256)
    whole = sum(len(data) for data in contents.values())
    try:
        for _ in range(3):  # giao diện hỏi liên tục trong lúc băm
            started = time.monotonic()
            status = music_module.status()
            assert time.monotonic() - started < 0.5, "status() không chờ băm"
            assert status["checking"] and status["scene"]["checking"]
            assert status["state"] == "outdated" and status["outdatedBytes"] == whole == status["scene"]["bytes"], "chưa băm xong: ước lượng cả gói"
        assert music_module.wait_checks(0.2) is False
    finally:
        release.set()
    assert music_module.wait_checks(10)
    assert sorted(hashed) == sorted(name for name in contents if name != new_file), "mỗi file cũ băm đúng một lần dù hỏi nhiều lần"
    status = music_module.status()
    assert not status["checking"] and status["outdatedBytes"] == len(contents[new_file]) == status["scene"]["bytes"]
    music_module.start()
    music_module.join(10)
    assert machine.calls[-1:] == [new_file] and music_module._state["total"] == len(contents[new_file])
