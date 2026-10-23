"""Soát a106r mục D: giọng VieNeu trên máy tính có "Gỡ" như Supertonic (lấy lại chỗ của Turbo / Nano / bản tăng tốc). Bộ căn chữ dùng chung với
phần tô chữ của sách (word_timing), bộ đọc chữ với Supertonic, thư viện chạy model với mô-đun nhạc: những phần ấy ở lại. Studio không dùng file
của mô-đun này (giọng VieNeu của Studio là gói `vieneu` có model riêng)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from abook.webui import vieneu_module
from tests.test_a_project_can_be_renamed_or_deleted import _call, studio  # noqa: F401 - fixture dùng chung
from tests.test_readaloud_vieneu import Network, module  # noqa: F401 - fixture dùng chung

pytestmark = pytest.mark.usefixtures("names_only_models")


def _install(*choices: str) -> None:
    vieneu_module.start(list(choices))
    vieneu_module.join(10)


def test_removing_nano_gives_its_space_back_and_leaves_turbo(module) -> None:  # noqa: F811
    _network, measured, folder = module
    _install("turbo", "nano")
    assert vieneu_module.status()["benchmark"].keys() == {"turbo", "nano"}
    vieneu_module.remove("nano")
    status = vieneu_module.status()
    assert not (folder / "nano").exists() and (folder / "turbo").is_dir()
    assert status["state"] == "ready" and status["benchmark"].keys() == {"turbo"}
    assert "nano" not in json.loads((folder / "module.json").read_bytes())["pins"] and "turbo" in json.loads((folder / "module.json").read_bytes())["pins"]
    found = vieneu_module.installed()
    assert found is not None and found.nano is None and found.turbo is not None
    assert (folder / "voices").is_dir() and (folder / "lib" / "sea_g2p").is_dir(), "bộ đọc chữ và danh sách giọng dùng chung: ở lại"


def test_removing_the_last_voice_goes_back_to_missing_and_it_can_be_downloaded_again(module) -> None:  # noqa: F811
    network, _measured, folder = module
    _install("turbo")
    vieneu_module.remove("turbo")
    assert not (folder / "turbo").exists() and vieneu_module.installed() is None
    assert vieneu_module.status()["state"] == "missing"
    network.calls.clear()
    _install("turbo")
    assert vieneu_module.status()["state"] == "ready" and "config.json" in network.calls


def test_the_aligner_is_shared_so_it_is_not_removable_and_unknown_choices_are_refused(module) -> None:  # noqa: F811
    _install("turbo", "aligner")
    for choice in ("aligner", "khác", ""):
        with pytest.raises(ValueError):
            vieneu_module.remove(choice)
    assert {choice["id"]: choice.get("removable", False) for choice in vieneu_module.status()["choices"]} == {"turbo": True, "nano": False, "aligner": False}


def test_removing_the_accelerated_build_keeps_the_voice(module) -> None:  # noqa: F811
    _network, _measured, folder = module
    _install("turbo")
    (folder / "gguf" / "server").mkdir(parents=True)
    (folder / "gguf" / "model.gguf").write_bytes(b"x")
    vieneu_module.remove(vieneu_module.FAST)
    assert not (folder / "gguf").exists() and (folder / "turbo").is_dir()


def test_the_server_removes_a_voice(studio, module) -> None:  # noqa: F811
    _network, _measured, folder = module
    _paths, _app, server, _runner = studio
    _install("nano")
    status, view = _call(server, "POST", "/api/readaloud/vieneu/remove", {"choice": "nano"})
    assert status == 200 and view["state"] == "missing" and not (folder / "nano").exists()
    for body in ({}, {"choice": "khác"}, {"choice": "aligner"}):
        status, _ = _call(server, "POST", "/api/readaloud/vieneu/remove", body)
        assert status == 400
