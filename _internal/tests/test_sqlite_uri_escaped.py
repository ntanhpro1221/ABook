"""SQLite URIs are built with `as_uri` (escaped), never by hand: a hand-built "file:...?mode=ro" is cut at `#` or `?` in a folder
name, loses `mode=ro` and opens - or creates - another file next to the book (soát 0.4.173 B4)."""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import pytest

from abook.io_utils import sqlite_read_only_uri

ROOT = Path(__file__).resolve().parents[1] / "abook"
# "file:{...}" / 'file:' + ... / "file:%s" - a URI glued from a raw path.
HAND_BUILT = re.compile(r"""["']file:(?:\{|["']\s*\+|%s)""")


def test_no_sqlite_uri_in_the_app_is_built_from_a_raw_path() -> None:
    offenders = []
    for path in sorted(ROOT.rglob("*.py")):
        if "_vendor" in path.parts:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if HAND_BUILT.search(line):
                offenders.append(f"{path.relative_to(ROOT).as_posix()}:{number}: {line.strip()}")
    assert not offenders, "use io_utils.sqlite_read_only_uri (or Path.as_uri()):\n" + "\n".join(offenders)


@pytest.mark.parametrize("folder", ["Sach #2", "Sach 100%", "Sach  hai  dau cach", "Sách #ổ", "a&b;c=d"])
def test_the_read_only_uri_opens_exactly_that_file_read_only(tmp_path: Path, folder: str) -> None:
    database = tmp_path / folder / "x.sqlite3"
    database.parent.mkdir()
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE t (v)")
        connection.execute("INSERT INTO t VALUES (7)")
    connection.close()
    before = sorted(path.name for path in tmp_path.iterdir())
    reader = sqlite3.connect(sqlite_read_only_uri(database), uri=True)
    try:
        assert reader.execute("SELECT v FROM t").fetchall() == [(7,)]
        with pytest.raises(sqlite3.OperationalError):
            reader.execute("INSERT INTO t VALUES (8)")
    finally:
        reader.close()
    assert sorted(path.name for path in tmp_path.iterdir()) == before, "no stray file beside the folder"
