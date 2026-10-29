"""Test QML của bản Qt không được chờ một số mili giây cố định rồi mới kiểm.

`wait(100); verify(...)` đậu trên máy rảnh nhưng hỏng khi máy bận (nhiều bản build cùng chạy): điều cần chờ là
một trạng thái, nên phải chờ đúng trạng thái ấy bằng tryVerify / tryCompare. Bộ đếm chỉ được giảm: sửa xong chỗ
nào thì hạ BASELINE xuống, tới 0.
"""
import re
from pathlib import Path

TESTS = Path(__file__).resolve().parent.parent / "desktop_qt" / "tests"
WAIT = r"wait\(\s*\d+\s*\)"
# Hàm trợ giúp chỉ gói một lần chờ cố định (`function settle() { wait(350) }`) cũng là chờ cố định.
HELPER = re.compile(r"function\s+(\w+)\s*\(\s*\)\s*\{\s*" + WAIT + r"\s*;?\s*\}")
CHECK = re.compile(r"^\s*(verify|compare|fuzzyCompare)\s*\(")
# Chờ cố định chỉ đúng khi test chứng minh điều gì đó KHÔNG xảy ra trong một khoảng (không gửi lệnh, hàng không đổi);
# dòng ấy ghi dấu này để máy dò bỏ qua.
ABSENCE = "// fixed: proves absence"
BASELINE = 67


def fixed_wait_checks(root=TESTS):
    """(file, line) của mỗi `wait(N)` (hay hàm chỉ gói nó) mà dòng có mã kế tiếp là một phép kiểm."""
    hits = []
    for path in sorted(root.rglob("*.qml")):
        text = path.read_text(encoding="utf-8")
        calls = [WAIT] + [re.escape(name) + r"\(\s*\)" for name in HELPER.findall(text)]
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
        "    }\n"
        "}\n", encoding="utf-8")
    assert fixed_wait_checks(tmp_path) == [("tst_probe.qml", 4), ("tst_probe.qml", 8)]  # settle() rồi compare; wait(100) rồi verify
