from pathlib import Path

import pytest

from abook.webui import bookfile
from tests.test_webui_listen_and_sync import make_project


@pytest.mark.parametrize("progress", [False, True])
def test_source_replaced_between_hash_and_write_never_publishes_broken_package(tmp_path, monkeypatch, progress):
    project = make_project(tmp_path / "library")
    out = tmp_path / "out.abook"
    real = bookfile.write_entries
    replaced = []

    def replace_source(archive, files, **kwargs):
        source = next(source for name, source in files.items() if name.startswith("chapters/") and isinstance(source, Path))
        replacement = source.with_suffix(".new")
        # Cùng cỡ nhưng byte khác: cả đường tái dùng hash theo cỡ cũng không được công bố gói sai.
        replacement.write_bytes(b"z" * source.stat().st_size)
        replacement.replace(source)
        replaced.append(source)
        return real(archive, files, **kwargs)

    monkeypatch.setattr(bookfile, "write_entries", replace_source)
    try:
        bookfile.pack(project, out, progress=(lambda *args: None) if progress else None)
    except bookfile.BookFileError as error:
        assert "thay đổi" in str(error) and "xuất lại" in str(error)
        assert not out.exists() and not list(tmp_path.glob("*.part"))
    else:
        with bookfile.BookFile(out) as opened:
            opened.verify()
    assert len(replaced) == 1
