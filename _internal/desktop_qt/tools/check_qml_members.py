"""Máy dò QML đọc thành viên không có trên kiểu thật (qmllint missing-property).

Loại lỗi 31-10: BenchScenario đọc Player.position / Player.duration - singleton C++ Player không có hai thuộc tính ấy (vị trí ở
Player.clock). QML không báo gì lúc chạy: undefined > 0 là false, kịch bản listen không bao giờ thoát, seek:end thành NaN.

Chạy qmllint với đúng tuỳ chọn module mà CMake sinh (build/.rcc/qmllint/ABookDesk_json.rsp: -I build, các qrc), sau
cmake --build để qmltypes của C++ là bản mới. Chỉ giữ cảnh báo missing-property trên KIỂU CÓ THẬT: singleton / kiểu C++
của module, kiểu QML, kiểu Qt. Bỏ "QObject" / "QQuickItem": qmllint chỉ còn biết lớp gốc (thuộc tính khai var / Item,
parent, contentItem...) chứ không phải kiểu ấy thiếu thành viên. Chỗ qmllint sai có chủ đích nằm ở ALLOWED kèm lý do.

  python -X utf8 tools/check_qml_members.py <build>            thoát 1 nếu có QML đọc thành viên không có
  python -X utf8 tools/check_qml_members.py selftest <build>   máy dò bắt QML giả đọc Player.position, im với Player.clock.position
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# qmllint chỉ biết lớp gốc: không phải kiểu thật thiếu thành viên.
BASE_TYPES = {"QObject", "QQuickItem"}

# (kiểu, thành viên) -> lý do qmllint sai.
ALLOWED = {
    ("QQmlApplication", "screens"): "Qt.application trong QtQuick là QQuickApplication (có screens); qmllint 6.10 gán kiểu QQmlApplication",
    ("QQmlApplication", "state"): "như trên: Qt.application.state là của QGuiApplication qua QQuickApplication",
    ("QQmlApplication", "font"): "như trên: Qt.application.font là của QQuickApplication",
}

MEMBER = re.compile(r'Member "(\w+)" not found on type "(\w+)"')


def qmllint() -> str:
    found = shutil.which("qmllint")
    if found:
        return found
    root = os.environ.get("QT_ROOT")
    path = Path(root) / "bin" / "qmllint.exe" if root else None
    if path and path.is_file():
        return str(path)
    raise SystemExit("không tìm thấy qmllint (PATH hay QT_ROOT)")


def options(build: Path) -> tuple[list[str], list[str]]:
    """Tuỳ chọn của rsp CMake (bỏ --json của nó) và danh sách file của module."""
    rsp = build / ".rcc" / "qmllint" / "ABookDesk_json.rsp"
    lines = [line.strip() for line in rsp.read_text(encoding="utf-8").splitlines() if line.strip()]
    out: list[str] = []
    files: list[str] = []
    i = 0
    while i < len(lines):
        arg = lines[i]
        if arg == "--json":
            i += 2
            continue
        if arg in ("-I", "--resource"):
            out += [arg, lines[i + 1]]
            i += 2
            continue
        if arg.endswith((".qml", ".js")):
            files.append(arg)
        else:
            out.append(arg)
        i += 1
    return out, files


def lint(build: Path, files: list[str]) -> list[dict]:
    opts, _ = options(build)
    with tempfile.TemporaryDirectory() as tmp:
        report = Path(tmp) / "lint.json"
        subprocess.run([qmllint(), *opts, "--json", str(report), *files],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if not report.is_file():
            raise SystemExit("qmllint không ghi báo cáo")
        data = json.loads(report.read_text(encoding="utf-8"))
    found = []
    for entry in data.get("files", []):
        for warning in entry.get("warnings", []):
            if warning.get("id") != "missing-property":
                continue
            m = MEMBER.search(warning.get("message", ""))
            if not m or m.group(2) in BASE_TYPES:
                continue
            member, kind = m.group(1), m.group(2)
            found.append({"file": entry.get("filename", ""), "line": warning.get("line"), "type": kind, "member": member,
                          "allowed": ALLOWED.get((kind, member))})
    return found


def check(build: Path) -> int:
    _, files = options(build)
    found = lint(build, files)
    bad = [f for f in found if not f["allowed"]]
    for f in bad:
        print(f'{f["file"]}:{f["line"]}: {f["type"]} không có "{f["member"]}"', file=sys.stderr)
    used = {(f["type"], f["member"]) for f in found if f["allowed"]}
    stale = sorted(set(ALLOWED) - used)
    for kind, member in stale:
        print(f"ALLOWED thừa (qmllint không còn báo): {kind}.{member}", file=sys.stderr)
    print(json.dumps(dict(check="qml_members", files=len(files), missing=len(bad), allowed=len(used), stale=len(stale)), ensure_ascii=False))
    return 1 if bad or stale else 0


FAKE = """import QtQuick
import ABook

Item {
    property bool heard: Player.playing && Player.%s > 0
}
"""


def selftest(build: Path) -> int:
    failures = []
    with tempfile.TemporaryDirectory() as tmp:
        bad = Path(tmp) / "FakeReadsPosition.qml"
        bad.write_text(FAKE % "position", encoding="utf-8")
        good = Path(tmp) / "FakeReadsClock.qml"
        good.write_text(FAKE % "clock.position", encoding="utf-8")
        hits = [(f["type"], f["member"]) for f in lint(build, [str(bad)])]
        if hits != [("Player", "position")]:
            failures.append(f"Player.position: chờ [('Player', 'position')], được {hits}")
        hits = [(f["type"], f["member"]) for f in lint(build, [str(good)])]
        if hits:
            failures.append(f"Player.clock.position: chờ im, được {hits}")
    print(json.dumps(dict(selftest="qml_members", failures=failures), ensure_ascii=False))
    return 1 if failures else 0


def main(argv: list[str]) -> int:
    if argv[:1] == ["selftest"] and len(argv) == 2:
        return selftest(Path(argv[1]))
    if len(argv) == 1:
        return check(Path(argv[0]))
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
