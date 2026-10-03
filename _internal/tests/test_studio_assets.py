"""Từ điển phát âm và giọng nghe thử là dữ liệu của Studio, không nằm trong bộ cài chỉ-nghe (2026-10-03): Studio tải gói ghim,
đặt đúng chỗ mã khoá chất lượng đọc; máy chưa cài Studio thì "nghe thử giọng" ẩn gọn gàng thay vì báo lỗi."""
from __future__ import annotations

import importlib.util
import json
import re
import shutil
from pathlib import Path

import pytest

from abook import analysis, quality_policy
from abook.webui import studio_setup, voice_picker, word_timing
from abook.webui.actions import FakeRunner
from abook.webui.library import Preferences
from abook.webui.server import App
from abook.webui.studio_setup import ASSET_PATHS, Download, SetupError

from tests.test_studio_setup import ASSET_FILES, _setup, _zip_with, ollama  # noqa: F401 - ollama là fixture

INTERNAL = Path(__file__).resolve().parents[1]
PACKAGE = Path(analysis.__file__).resolve().parent


def _installed(tmp_path: Path, ollama: str, monkeypatch: pytest.MonkeyPatch):  # noqa: F811
    monkeypatch.setattr(studio_setup.shutil, "which", lambda _name: None)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "localappdata"))
    setup = _setup(tmp_path, ollama, [])
    (setup.app_root / "abook" / "assets").mkdir(parents=True)
    (setup.app_root / "abook" / "assets" / "app.ico").write_bytes(b"icon")  # file của bộ cài, không thuộc Studio
    setup.start()
    setup.wait(30)
    assert setup.status()["error"] is None and setup.installed()
    return setup


def test_the_studio_puts_its_data_where_the_locked_code_reads_it(tmp_path: Path, ollama: str,
                                                                  monkeypatch: pytest.MonkeyPatch) -> None:
    setup = _installed(tmp_path, ollama, monkeypatch)
    placed = setup.app_root / "abook" / "assets"
    assert (placed / "cmudict.dict").read_bytes() == ASSET_FILES["cmudict.dict"]
    assert sorted(path.name for path in (placed / "voice_previews").iterdir()) == ["adam.wav", "ly.wav"]
    assert (placed / "app.ico").is_file()
    assert not list((setup.root / "downloads").glob("*")), "gói đã tải không giữ lại"
    # Đường tương đối mà file khoá (analysis.py, quality_policy.py) đọc: Studio phải đặt ĐÚNG chỗ ấy ở mọi thư mục mã.
    assert analysis.CMUDICT_PATH.relative_to(PACKAGE) == Path("assets") / "cmudict.dict"
    assert (PACKAGE / "assets" / "voice_previews").is_dir()
    assert {name for name in ASSET_PATHS} == {"cmudict.dict", "voice_previews"}
    source = Path(quality_policy.__file__).read_text(encoding="utf-8")
    assert 'parent / "assets" / "voice_previews"' in source


def test_the_data_survives_an_app_update_that_replaces_the_code_folder(tmp_path: Path, ollama: str,
                                                                        monkeypatch: pytest.MonkeyPatch) -> None:
    """App cập nhật thay cả thư mục mã (dữ liệu đặt vào đó biến mất); kho `Studio\\assets` còn: cuốn tiếp theo (và mỗi lần mở
    app) đặt lại, bản chép mã dành cho lúc hash khác cũng mang theo."""
    setup = _installed(tmp_path, ollama, monkeypatch)
    placed = setup.app_root / "abook" / "assets"
    shutil.rmtree(placed / "voice_previews")
    (placed / "cmudict.dict").unlink()
    monkeypatch.setattr(quality_policy, "quality_implementation_hash", lambda: "a" * 64)
    book = tmp_path / "cuon"
    book.mkdir()

    assert setup.code_for(book) == setup.app_root
    assert (placed / "cmudict.dict").read_bytes() == ASSET_FILES["cmudict.dict"]
    assert (placed / "voice_previews" / "ly.wav").read_bytes() == b"RIFF-ly"
    copy = setup.root / "code" / ("a" * 16) / "abook" / "assets"
    assert (copy / "cmudict.dict").is_file() and (copy / "voice_previews" / "adam.wav").is_file()

    (placed / "voice_previews" / "ly.wav").write_bytes(b"hong")  # đặt hỏng thì sửa lại, y hệt thì để yên
    setup.ensure_assets()
    assert (placed / "voice_previews" / "ly.wav").read_bytes() == b"RIFF-ly"


def test_removing_the_studio_returns_the_install_to_the_listening_only_one(tmp_path: Path, ollama: str,
                                                                            monkeypatch: pytest.MonkeyPatch) -> None:
    setup = _installed(tmp_path, ollama, monkeypatch)
    placed = setup.app_root / "abook" / "assets"
    (placed / "cmudict.dict").write_bytes(b"cua-nguoi-dung")  # khác byte với kho: không phải do Studio đặt, giữ
    setup.remove()
    assert not setup.root.exists()
    assert not (placed / "voice_previews").exists() and (placed / "cmudict.dict").read_bytes() == b"cua-nguoi-dung"
    assert (placed / "app.ico").is_file()


def test_a_studio_installed_before_the_data_moved_asks_for_it_and_fetches_only_that(tmp_path: Path, ollama: str,
                                                                                    monkeypatch: pytest.MonkeyPatch) -> None:
    setup = _installed(tmp_path, ollama, monkeypatch)
    state = json.loads(setup.state_path.read_text(encoding="utf-8"))
    state["done"] = [step for step in state["done"] if step != "assets"]
    state["pins"].pop("assets", None)
    setup.state_path.write_text(json.dumps(state), encoding="utf-8")
    shutil.rmtree(setup.assets)

    assert setup.outdated() == ["assets"] and setup.status()["outdated"] == ["Từ điển phát âm và giọng nghe thử"]
    setup.fetched.clear()  # type: ignore[attr-defined]
    setup.start()
    setup.wait(30)
    assert setup.fetched == ["studio-assets"] and setup.outdated() == []  # type: ignore[attr-defined]
    assert (setup.app_root / "abook" / "assets" / "cmudict.dict").is_file()


def test_a_data_pack_missing_a_file_is_refused_and_removed(tmp_path: Path, ollama: str,
                                                          monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(studio_setup.shutil, "which", lambda _name: None)
    setup = _setup(tmp_path, ollama, [])
    original = setup.fetch

    def fetch(item: Download, target: Path, progress, cancelled) -> Path:
        if item.name == "studio-assets":
            return _zip_with(target, {"voice_previews/adam.wav": b"RIFF"})
        return original(item, target, progress, cancelled)

    setup.fetch = fetch  # type: ignore[assignment]
    setup.start()
    setup.wait(30)
    status = setup.status()
    assert "thiếu cmudict.dict" in status["error"] and not setup.assets.exists() and not setup.installed()
    assert [step["id"] for step in status["steps"] if step["done"]] == ["check"]


def test_the_pack_script_makes_the_same_zip_every_time_from_exactly_the_asset_paths(tmp_path: Path) -> None:
    spec = importlib.util.spec_from_file_location("pack_studio_assets", INTERNAL / "scripts" / "pack_studio_assets.py")
    pack = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pack)
    assets = tmp_path / "assets"
    for name, data in ASSET_FILES.items():
        (assets / name).parent.mkdir(parents=True, exist_ok=True)
        (assets / name).write_bytes(data)
    (assets / "app.ico").write_bytes(b"icon")  # file khác của assets không vào gói
    first = pack.pack(assets, tmp_path / "one" / "pack.zip").read_bytes()
    second = pack.pack(assets, tmp_path / "two" / "pack.zip").read_bytes()
    assert first == second
    import zipfile

    with zipfile.ZipFile(tmp_path / "one" / "pack.zip") as bundle:
        assert sorted(bundle.namelist()) == sorted(ASSET_FILES)
        assert {name: bundle.read(name) for name in bundle.namelist()} == ASSET_FILES


def test_the_installer_build_leaves_out_exactly_the_studio_assets() -> None:
    script = (INTERNAL / "scripts" / "build_windows_app.ps1").read_text(encoding="utf-8-sig")
    declared = re.search(r"\$StudioOnlyAssets = @\(([^)]*)\)", script)
    assert declared and re.findall(r'"([^"]+)"', declared.group(1)) == list(ASSET_PATHS)
    assert "/XD @excludeDirs" in script and "$StudioOnlyAssets" in script.split("/XF", 1)[1].splitlines()[0]
    assert (INTERNAL / "abook" / "assets" / "CMUDICT_LICENSE.txt").is_file(), "giấy phép đi cùng bộ cài"


def test_a_release_cannot_be_built_while_the_studio_data_pack_is_unpublished(monkeypatch: pytest.MonkeyPatch) -> None:
    spec = importlib.util.spec_from_file_location("release_script_assets", INTERNAL / "scripts" / "release.py")
    release = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(release)
    monkeypatch.setattr(studio_setup, "STUDIO_ASSETS", Download("studio-assets", "https://x/resolve/PIN_REVISION/a.zip", "0" * 64, 1))
    with pytest.raises(AssertionError, match="chưa ghim"):
        release.check_studio_assets_pinned()
    monkeypatch.setattr(studio_setup, "STUDIO_ASSETS", Download("studio-assets", "https://x/resolve/" + "c" * 40 + "/a.zip", "a" * 64, 1))
    release.check_studio_assets_pinned()


def test_without_the_studio_data_a_voice_has_no_preview_button_and_no_error(tmp_path: Path,
                                                                             monkeypatch: pytest.MonkeyPatch) -> None:
    from abook.voice_catalog import VOICE_PREVIEW_FILENAMES

    app = App(preferences=Preferences(tmp_path / "prefs.json"), runner=FakeRunner(), token="t")
    assert any(voice["preview"] for voice in app.voices()), "máy dev có giọng nghe thử"
    empty = tmp_path / "chua_cai_studio"
    monkeypatch.setattr(voice_picker, "VOICE_PREVIEW_DIR", empty)
    assert not any(voice["preview"] for voice in app.voices())
    assert all(app.voice_file(name) is None for name in VOICE_PREVIEW_FILENAMES)
    empty.mkdir()
    name, filename = next(iter(VOICE_PREVIEW_FILENAMES.items()))
    (empty / filename).write_bytes(b"RIFF")
    assert app.voice_file(name) == empty / filename and voice_picker.preview_file(name) == empty / filename


def test_a_studio_installed_before_the_word_model_asks_for_it_and_fetches_only_its_three_files(tmp_path: Path, ollama: str,
                                                                                               monkeypatch: pytest.MonkeyPatch) -> None:
    """Model căn từng chữ (webui/word_timing.py) là một bước của Studio: Studio cài từ bản app cũ thấy mình "cũ", cập nhật chỉ tải ba file ấy."""
    setup = _installed(tmp_path, ollama, monkeypatch)
    state = json.loads(setup.state_path.read_text(encoding="utf-8"))
    state["done"] = [step for step in state["done"] if step != "wordalign"]
    state["pins"].pop("wordalign", None)
    setup.state_path.write_text(json.dumps(state), encoding="utf-8")
    shutil.rmtree(setup.word_align)

    assert setup.outdated() == ["wordalign"] and setup.status()["outdated"] == ["Model căn từng chữ khi nghe"]
    setup.fetched.clear()  # type: ignore[attr-defined]
    setup.start()
    setup.wait(30)
    assert setup.fetched == [item.name for item in studio_setup.WORD_ALIGN_FILES] and setup.outdated() == []  # type: ignore[attr-defined]
    assert {path.name for path in setup.word_align.iterdir()} == {item.name for item in studio_setup.WORD_ALIGN_FILES}
    assert setup.word_align == setup.runtime / "models" / studio_setup.WORD_ALIGN_FOLDER, "word_timing.model_dir đọc đúng chỗ này qua ABOOK_RUNTIME"


def test_the_pinned_word_model_matches_the_files_the_pack_script_makes_and_a_release_needs_the_pin(monkeypatch: pytest.MonkeyPatch) -> None:
    spec = importlib.util.spec_from_file_location("release_script_words", INTERNAL / "scripts" / "release.py")
    release = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(release)
    files = studio_setup.WORD_ALIGN_FILES
    assert [item.name for item in files] == list(word_timing.MODEL_FILES)
    assert all(re.fullmatch(r"[0-9a-f]{64}", item.sha256) and item.size > 0 for item in files), "băm + cỡ là của file thật"
    assert all("/resolve/95c5e5f04153618e00213dca6459810bd6dd1c72/word-align/" in item.url for item in files), "ghim theo commit đã đăng"
    release.check_word_align_pinned()
    monkeypatch.setattr(studio_setup, "WORD_ALIGN_FILES", tuple(Download(item.name, item.url.replace("95c5e5f04153618e00213dca6459810bd6dd1c72", "PIN_REVISION"),
                                                                         item.sha256, item.size) for item in files))
    with pytest.raises(AssertionError, match="chưa ghim"):  # chưa đăng: URL còn PIN_REVISION thì không dựng bản phát hành
        release.check_word_align_pinned()
