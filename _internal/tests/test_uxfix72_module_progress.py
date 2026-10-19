"""uxfix72 (soát a65): tải tiếp một giọng sau Huỷ - dòng "Đang tải … (N MB) X%" ghi đúng số CÒN phải tải như nút "Tải (N MB)" vừa bấm (trước đây ghi cả
phần, gồm `.part` đã có), và % tính trên số ấy, bắt đầu từ 0. Khung chung của VieNeu / Supertonic / ZeroTTS (voice_module.ModuleCore); điện thoại cùng
luật (VoiceModule.kt, VieneuModuleTest.aResumedDownloadCountsWhatIsLeftLikeTheButtonNotTheWholeFile)."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest

from abook.webui import music_module, studio_setup, voice_module
from abook.webui.studio_setup import Download


def _item(name: str, data: bytes) -> Download:
    return Download(name, f"https://example.invalid/{name}", hashlib.sha256(data).hexdigest(), len(data))


def test_a_resumed_download_counts_what_is_left_like_the_button(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    a, b = b"A" * 40, b"B" * 60
    items = (_item("a.bin", a), _item("b.bin", b))
    folder = tmp_path / "model"
    folder.mkdir()
    (folder / "a.bin").write_bytes(a)  # xong trước lúc Huỷ
    (folder / "b.bin.part").write_bytes(b[:25])  # Huỷ giữa file thứ hai
    part = music_module.Component("model", "Model", "pin", 100, False, downloads=list(items), targets=[folder / "a.bin", folder / "b.bin"])
    assert part.left() == 35, "nút: Tải (35 B)"

    core = voice_module.ModuleCore("giọng thử", "test-module", frozenset(), lambda: False)
    core.configure(tmp_path / "core", None, None)
    seen: list[tuple[int, int]] = []

    def resuming(item: Download, target: Path, progress: Any, cancelled: Any) -> Path:
        # như studio_setup.download: file đúng đã có / phần `.part` dở được báo ngay từ đầu, rồi phần mới về
        have = item.size if studio_setup.matches(target, item) else len(b[:25]) if item.name == "b.bin" else 0
        progress(have, item.size)
        seen.append((core.state["done"], core.state["total"]))
        if have < item.size:
            progress(have + 20, item.size)
            seen.append((core.state["done"], core.state["total"]))
            target.write_bytes(b)
            progress(item.size, item.size)
            seen.append((core.state["done"], core.state["total"]))
        return target

    monkeypatch.setattr(studio_setup, "download", resuming)
    core.begin([part], lambda component, progress: voice_module.download_files(component, folder, progress), lambda: None, lambda _changed: [])
    assert core.state["total"] == 35, "dòng tải ghi số của nút, không phải cả phần 100 B"
    core.join(10)
    assert seen == [(0, 35), (0, 35), (20, 35), (35, 35)], "chỉ tính byte lần tải này thêm: 0 -> 20 -> 35 trên 35"
    assert core.state["done"] == 35 and not core.state["downloading"] and core.state["error"] == ""
