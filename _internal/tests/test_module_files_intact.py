"""Soát a96 V2: một mô-đun giọng chỉ "sẵn sàng" khi file của nó ĐÚNG bản đã ghim, không chỉ khi có tên file.

File model bị cắt cụt hay hỏng (đĩa lỗi, phần mềm dọn đĩa, tải dở) từng vẫn được tính là đã tải: giọng liệt kê như có, đến lúc nạp mới lỗi,
và nút tải không có việc để sửa. Bài thử dùng file thật rất nhỏ với băm thật của chúng (không chạm model ghim của app).
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from abook.webui import studio_setup, voice_module, zerotts_module as z


def _item(name: str, data: bytes) -> studio_setup.Download:
    return studio_setup.Download(name, "https://example.invalid/" + name, hashlib.sha256(data).hexdigest(), len(data))


def test_intact_means_same_size_and_hash_not_just_the_name(tmp_path: Path) -> None:
    good, other = b"a model " * 100, b"b model " * 100
    item = _item("model.onnx", good)
    assert not studio_setup.intact(tmp_path, [item]), "chưa có file"
    (tmp_path / "model.onnx").write_bytes(good[:50])
    assert not studio_setup.intact(tmp_path, [item]), "cắt cụt"
    (tmp_path / "model.onnx").write_bytes(other)  # cùng cỡ, khác nội dung
    assert len(other) == len(good) and not studio_setup.intact(tmp_path, [item])
    (tmp_path / "model.onnx").write_bytes(good)
    assert studio_setup.intact(tmp_path, [item])
    assert not studio_setup.intact(None, [item])


def test_the_hash_is_not_recomputed_while_the_file_stays_the_same(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data = b"x" * 4096
    item = _item("m.bin", data)
    (tmp_path / "m.bin").write_bytes(data)
    assert studio_setup.intact(tmp_path, [item])
    hashed: list[Path] = []
    real = studio_setup._digest
    monkeypatch.setattr(studio_setup, "_digest", lambda path: hashed.append(path) or real(path))
    for _ in range(5):  # trang hỏi trạng thái liên tục
        assert studio_setup.intact(tmp_path, [item])
    assert hashed == []
    (tmp_path / "m.bin").write_bytes(data[:-1] + b"y")  # đổi nội dung, cùng cỡ: dấu stat đổi -> băm lại
    import os
    os.utime(tmp_path / "m.bin", ns=(1, 2))
    assert not studio_setup.intact(tmp_path, [item]) and len(hashed) == 1


def test_a_corrupt_zerotts_model_is_not_ready_and_the_download_button_repairs_it(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Đảo khẳng định của test nháp a96: trước đây status "ready" và start() không làm gì."""
    files = (_item("config.json", b"{}"), _item("tokenizer.json", b'{"a": 1}'))
    monkeypatch.setattr(z, "MODEL_FILES", files)
    z.configure(tmp_path / "zerotts")
    try:
        code = z._dir("code") / "zerotts" / "synthesizer.py"
        code.parent.mkdir(parents=True)
        code.write_bytes(b"# never imported")
        model = z._dir(z.CHOICE)
        model.mkdir(parents=True)
        (model / "config.json").write_bytes(b"{}")
        (model / "tokenizer.json").write_bytes(b'{"a": 1}')
        z._core.write_stamp({"pins": {part.id: part.pin for part in z._parts()}})
        assert z.installed() is not None and z.status()["state"] == "ready" and not z.status()["damaged"]

        (model / "tokenizer.json").write_bytes(b"broken")
        assert z.installed() is None
        status = z.status()
        assert status["state"] == "missing" and status["damaged"] is True
        assert status["bytes"] == len(b'{"a": 1}'), "chỉ phần hỏng còn phải tải"

        fetched: list[str] = []
        contents = {"config.json": b"{}", "tokenizer.json": b'{"a": 1}'}

        def fake_download(item, target, progress, cancelled):
            if studio_setup.matches(target, item):  # như downloader thật: file đúng thì bỏ qua
                return target
            fetched.append(item.name)
            target.write_bytes(contents[item.name])
            progress(item.size, item.size)
            return target

        monkeypatch.setattr(studio_setup, "download", fake_download)
        z.start()
        z.join(10)
        assert fetched == ["tokenizer.json"], "chỉ tải lại phần hỏng"
        assert z.installed() is not None and z.status()["state"] == "ready"
    finally:
        z.configure(None)


def test_damaged_part_needs_a_pin_from_an_earlier_download() -> None:
    from abook.webui.music_module import Component

    gone = Component("model", "Model", "pin", 10, False)
    assert voice_module.has_damaged_part([gone], {"model": "pin"})
    assert not voice_module.has_damaged_part([gone], {}), "chưa từng tải: là tải lần đầu, không phải sửa"
    assert not voice_module.has_damaged_part([Component("model", "Model", "pin", 10, True)], {"model": "pin"})


def test_reopening_the_app_does_not_rehash_a_model_that_did_not_change(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Lượt hỏi trạng thái đầu tiên sau khi mở lại app từng băm lại cả ~0,9 GB model ZeroTTS ngay trên luồng trả lời."""
    import os
    from abook.webui import audio_revision
    data = b"weights " * 512
    item = _item("model.onnx", data)
    folder = tmp_path / "module"
    folder.mkdir()
    (folder / "model.onnx").write_bytes(data)
    os.utime(folder / "model.onnx", ns=(1_000_000_000, 1_000_000_000))  # file đã nằm yên từ lâu
    store = tmp_path / "audio_digests.json"
    audio_revision.configure(store)
    try:
        assert studio_setup.intact(folder, [item])
        audio_revision._flush()
        assert store.is_file()
        # Mở lại app: bảng trong bộ nhớ của cả hai mô-đun mất, chỉ còn file trên đĩa.
        monkeypatch.setattr(studio_setup, "_hashed", {})
        audio_revision.configure(None)
        audio_revision.configure(store)

        class NoHashing:
            @staticmethod
            def sha256(*_: object) -> None:
                raise AssertionError("băm lại model không đổi")

        monkeypatch.setattr(audio_revision, "hashlib", NoHashing)
        monkeypatch.setattr(studio_setup, "_sha256", NoHashing.sha256)
        assert studio_setup.intact(folder, [item])
    finally:
        audio_revision.configure(None)
