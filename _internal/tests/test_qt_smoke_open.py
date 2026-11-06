"""The file-open gate must observe published books across atomic import swaps."""
import importlib.util
from pathlib import Path

from abook.webui import bookfile, packages
from abook.webui.fingerprints import Fingerprints


def smoke_module(monkeypatch):
    tools = Path(__file__).resolve().parents[1] / "desktop_qt/tools"
    monkeypatch.syspath_prepend(str(tools))
    spec = importlib.util.spec_from_file_location("smoke_open_under_test", tools / "smoke_open.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_open_gate_keeps_the_first_book_during_real_import_swaps(tmp_path, monkeypatch):
    smoke = smoke_module(monkeypatch)
    library = tmp_path / "library"
    first_file = smoke.WRITTEN / "python_v4.abook"
    second_file = smoke.smoke_play.write_package(tmp_path / "second.abook", b"a different chapter")
    snapshots = []
    swap = bookfile.swap_in

    def observe(staging, target):
        # This is the exact race: book.json already exists, but the directory
        # still has its temporary name. No timers or scheduling assumptions.
        assert (staging / "book.json").is_file()
        snapshots.append(smoke.books(library))
        swap(staging, target)
        snapshots.append(smoke.books(library))

    monkeypatch.setattr(bookfile, "swap_in", observe)
    fingerprints = Fingerprints(tmp_path / "fingerprints.json")
    first, first_how = packages.import_file(first_file, library, [], fingerprints)
    second, second_how = packages.import_file(second_file, library, [], fingerprints)
    assert first_how == second_how == "new"
    assert first != second
    assert snapshots == [set(), {first.name}, {first.name}, {first.name, second.name}]
    # A stronger check than a directory count: both published packages retain
    # every declared file with its original size and checksum.
    assert packages.damaged_files(first) == []
    assert packages.damaged_files(second) == []
    # Losing a published first book must still be visible to the retention
    # check, even while its retired directory remains on disk.
    first.rename(first.with_name(f".{first.name}.old"))
    assert smoke.books(library) == {second.name}
    assert not {first.name} <= smoke.books(library)


def test_open_gate_ignores_retired_and_unpublished_directories(tmp_path, monkeypatch):
    smoke = smoke_module(monkeypatch)
    imported = tmp_path / smoke.IMPORTED
    for name in (".book.123.part", ".book.123.old", "unfinished"):
        folder = imported / name
        folder.mkdir(parents=True)
        if name.startswith("."):
            (folder / "book.json").write_text("{}", encoding="utf-8")
    assert smoke.books(tmp_path) == set()
