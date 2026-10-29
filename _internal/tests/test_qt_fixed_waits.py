"""Test QML của bản Qt không được chờ một số mili giây cố định rồi mới kiểm.

`wait(100); verify(...)` đậu trên máy rảnh nhưng hỏng khi máy bận (nhiều bản build cùng chạy): điều cần chờ là
một trạng thái, nên phải chờ đúng trạng thái ấy bằng tryVerify / tryCompare. Bộ đếm chỉ được giảm: sửa xong chỗ
nào thì hạ BASELINE xuống, tới 0.
"""
import re
from pathlib import Path

TESTS = Path(__file__).resolve().parent.parent / "desktop_qt" / "tests"
WAIT = r"wait\(\s*\d+\s*\)"
FUNCTION = re.compile(r"function\s+(\w+)\s*\([^)]*\)\s*\{")
LAST_WAIT = re.compile(r"^" + WAIT + r"\s*;?\s*(//.*)?$")


def helpers(text):
    """Hàm trợ giúp mà lệnh cuối là một lần chờ cố định (`function settle() { wait(350) }`, hay
    `tryVerify(...); wait(50)` ở cuối) - gọi nó rồi kiểm cũng là chờ cố định."""
    names = []
    for m in FUNCTION.finditer(text):
        depth, j = 1, m.end()
        while depth and j < len(text):
            depth += {"{": 1, "}": -1}.get(text[j], 0)
            j += 1
        lines = [l.strip() for l in text[m.end():j - 1].splitlines() if l.strip() and not l.strip().startswith("//")]
        if lines and LAST_WAIT.match(lines[-1]) and ABSENCE not in lines[-1]:
            names.append(m.group(1))
    return names
CHECK = re.compile(r"^\s*(verify|compare|fuzzyCompare)\s*\(")
# Chờ cố định chỉ đúng khi test chứng minh điều gì đó KHÔNG xảy ra trong một khoảng (không gửi lệnh, hàng không đổi);
# dòng ấy ghi dấu này để máy dò bỏ qua.
ABSENCE = "// fixed: proves absence"
BASELINE = 59


def fixed_wait_checks(root=TESTS):
    """(file, line) của mỗi `wait(N)` (hay hàm chỉ gói nó) mà dòng có mã kế tiếp là một phép kiểm."""
    hits = []
    for path in sorted(root.rglob("*.qml")):
        text = path.read_text(encoding="utf-8")
        calls = [WAIT] + [re.escape(name) + r"\([^)]*\)" for name in helpers(text)]
        waiting = re.compile(r"^\s*(" + "|".join(calls) + r")\s*;?\s*(//.*)?$")
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if not waiting.match(line) or ABSENCE in line:
                continue
            nxt = next((l for l in lines[i + 1:] if l.strip() and not l.strip().startswith("//")), "")
            if CHECK.match(nxt):
                hits.append((path.relative_to(root).as_posix(), i + 1))
    return hits


def test_fixed_waits_before_checks_only_shrink():
    hits = fixed_wait_checks()
    listing = "\n".join(f"  {f}:{n}" for f, n in hits)
    assert len(hits) <= BASELINE, f"{len(hits)} chỗ wait(N) rồi kiểm (trần {BASELINE}) - dùng tryVerify/tryCompare:\n{listing}"


def test_detector_sees_the_pattern(tmp_path):
    (tmp_path / "tst_probe.qml").write_text(
        "TestCase {\n"
        "    function settle() { wait(350) }\n"
        "    function open(page) {\n"
        "        tryVerify(function() { return page.ready })\n"
        "        wait(50)\n"
        "    }\n"
        "    function test_b() {\n"
        "        settle()\n"
        "        compare(y, 1)\n"
        "    }\n"
        "    function test_a() {\n"
        "        wait(100)\n"
        "        // ghi chú\n"
        "        verify(x)\n"
        "        wait(50)\n"
        "        mouseClick(y)\n"
        "        wait(80)   // fixed: proves absence\n"
        "        compare(calls.length, 0)\n"
        "        tryVerify(function() { return z })\n"
        "        open(page)\n"
        "        verify(page.shown)\n"
        "    }\n"
        "}\n", encoding="utf-8")
    # settle() rồi compare; wait(100) rồi verify; open(page) kết thúc bằng wait(50) rồi verify
    assert fixed_wait_checks(tmp_path) == [("tst_probe.qml", 8), ("tst_probe.qml", 12), ("tst_probe.qml", 20)]
