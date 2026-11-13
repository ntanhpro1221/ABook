"""A fake executable cannot reach the native loader; real command dispatch is preserved."""
import os
from pathlib import Path
import struct

import pytest

from tests.process_fakes import guarded_create_process, is_pe_image

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows process boundary")


@pytest.mark.parametrize("payload", [b"fake", b"MZ fake ffmpeg", b"MZ" + b"\0" * 62])
def test_invalid_test_executable_is_rejected_before_native_dispatch(tmp_path, payload):
    file = tmp_path / "tools with spaces" / "ffmpeg.exe"
    file.parent.mkdir()
    file.write_bytes(payload)
    called = []
    dispatch = guarded_create_process(lambda *a, **kw: called.append(a), tmp_path)
    with pytest.raises(OSError) as caught:
        dispatch(None, f'"{file}" -version')
    assert caught.value.winerror == 193
    assert called == []


def test_valid_image_and_nonexistent_file_preserve_original_arguments(tmp_path):
    file = tmp_path / "valid.exe"
    header = bytearray(68)
    header[:2] = b"MZ"
    struct.pack_into("<I", header, 60, 64)
    header[64:68] = b"PE\0\0"
    file.write_bytes(header)
    assert is_pe_image(file)
    called = []
    result = object()

    def original(*args, **kwargs):
        called.append((args, kwargs))
        return result

    dispatch = guarded_create_process(original, tmp_path)
    assert dispatch(str(file), "command text", "attributes", flags=8) is result
    assert called == [((str(file), "command text", "attributes"), {"flags": 8})]
    assert dispatch(str(tmp_path / "missing.exe"), "missing") is result


def test_files_outside_the_test_temporary_root_are_not_opened(tmp_path, monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("Outside executable was probed")

    monkeypatch.setattr(Path, "open", refuse)
    original = lambda *args, **kwargs: "native result"
    dispatch = guarded_create_process(original, tmp_path / "temporary")
    assert dispatch(str(tmp_path / "outside.exe"), "command") == "native result"
