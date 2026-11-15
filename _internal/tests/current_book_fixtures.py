"""Build current metadata in temporary archives, preserving every archived media/source byte."""
from __future__ import annotations

import json
import tempfile
import zipfile
from pathlib import Path

from abook.webui.bookfile import describe


def current_fixture(source: Path) -> Path:
    content: dict[str, bytes] = {}
    with zipfile.ZipFile(source) as archive:
        infos = archive.infolist()
        content = {info.filename: archive.read(info) for info in infos}
    book = json.loads(content["book.json"])
    chapters = book.pop("chapters", [])
    for chapter in chapters:
        chapter["volumeId"] = 1
    book["volumes"] = [{"id": 1, "number": 1, "title": "Quyển 1", "cover": None, "chapters": chapters}]
    book["package"]["version"] = 6
    content["book.json"] = json.dumps(book, ensure_ascii=False).encode("utf-8")
    if "project.json" in content:
        project = json.loads(content["project.json"])
        project["files"]["book.json"] = describe(content["book.json"])
        content["project.json"] = json.dumps(project, ensure_ascii=False).encode("utf-8")
    target = Path(tempfile.mkdtemp(prefix="abook-fixture-")) / source.name
    with zipfile.ZipFile(target, "w") as archive:
        for info in infos:
            archive.writestr(info, content[info.filename])
    return target
