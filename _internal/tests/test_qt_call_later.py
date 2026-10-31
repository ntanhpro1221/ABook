"""Bản Qt hẹn việc "để sau" bằng Later.call(owner, fn) (desktop_qt/src/later.h), không bằng Qt.callLater.

Qt.callLater chỉ canh object của hàm chưa bị xoá. Loader / Repeater gỡ một màn thì ngữ cảnh QML của nó mất ngay (id thành null) trong
khi object còn chờ xoá, nên hàm hẹn vẫn chạy và báo TypeError: EditBookActions "Cannot read property 'children' of null" (tst_studio3),
NewChapters "root is not defined", NewProjectScreen. Later.call bỏ qua hàm hẹn khi ngữ cảnh của owner đã mất (tests/width/tst_later.qml).
"""
import re
from pathlib import Path

QML = Path(__file__).resolve().parent.parent / "desktop_qt" / "qml"
CALL_LATER = re.compile(r"\bQt\.callLater\s*\(")


def call_later_sites(root=QML):
    hits = []
    for path in sorted(list(root.glob("*.js")) + list(root.glob("*.qml"))):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if CALL_LATER.search(line):
                hits.append(f"{path.name}:{number}: {line.strip()}")
    return hits


def test_no_qt_call_later():
    hits = call_later_sites()
    assert not hits, "dùng Later.call(owner, fn) thay vì Qt.callLater:\n" + "\n".join(hits)


def test_detector_sees_call_later(tmp_path):
    (tmp_path / "Old.qml").write_text("Item { onWidthChanged: Qt.callLater(relayout) }\n", encoding="utf-8")
    (tmp_path / "Ok.qml").write_text("Item { onWidthChanged: Later.call(root, relayout) }\n", encoding="utf-8")
    assert [hit.split(":")[0] for hit in call_later_sites(tmp_path)] == ["Old.qml"]
