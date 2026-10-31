"""Test QML của bản Qt không được chờ một số mili giây cố định rồi mới kiểm.

`wait(100); verify(...)` đậu trên máy rảnh nhưng hỏng khi máy bận (nhiều bản build cùng chạy): điều cần chờ là
một trạng thái, nên phải chờ đúng trạng thái ấy bằng tryVerify / tryCompare. Bộ đếm chỉ được giảm: sửa xong chỗ
nào thì hạ BASELINE xuống, tới 0.
"""
import re
from pathlib import Path

TESTS = Path(__file__).resolve().parent.parent / "desktop_qt" / "tests"
WAIT = re.compile(r"(?<![\w.])wait\s*\(")
CPP_WAIT = re.compile(r"\bQTest::qWait\s*\(")
# Chờ cố định chỉ đúng khi test chứng minh điều gì đó KHÔNG xảy ra trong một khoảng (không gửi lệnh, hàng không đổi);
# dòng ấy ghi dấu này để máy dò bỏ qua.
ABSENCE = "// fixed: proves absence"
# Test đo thời gian (bộ trộn âm, đồng hồ thiết bị) lấy mẫu theo nhịp cố định rồi mới tính số: chờ ấy là phép đo, không phải chờ
# một trạng thái - dòng ấy ghi dấu này, kèm lý do sau gạch ("// fixed: samples timing - ..."). Dòng có dấu mà cũng kiểm
# (verify / compare) là chờ trá hình: máy dò không nhận dấu ấy.
SAMPLES = re.compile(r"// fixed: samples timing - \S")
CHECK = re.compile(r"\b(?:QVERIFY\w*|QCOMPARE\w*|QTRY_\w+|verify|compare|tryVerify|tryCompare|fuzzyCompare)\s*\(")
BASELINE = 0


def fixed_wait_checks(root=TESTS):
    """Catch fixed waits anywhere, including inline calls and wait-only helpers.

    A declaration or an action between a sleep and an assertion does not make
    the sleep safe. Only explicitly documented absence windows are exempt.
    """
    hits = []
    for path in sorted(p for p in root.rglob("*") if p.suffix in {".qml", ".cpp"}):
        text = path.read_text(encoding="utf-8")
        waiting = WAIT if path.suffix == ".qml" else CPP_WAIT
        lines = text.splitlines()
        for i, line in enumerate(lines):
            code = line.split("//", 1)[0]
            sampling = SAMPLES.search(line) and not CHECK.search(code)
            if not waiting.search(code) or ABSENCE in line or sampling:
                continue
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
    assert fixed_wait_checks(tmp_path) == [("tst_probe.qml", 2), ("tst_probe.qml", 8), ("tst_probe.qml", 11)]


def test_detector_sees_inline_and_deferred_checks(tmp_path):
    (tmp_path / "tst_inline.qml").write_text(
        "action(); wait(10); compare(x, 1)\n"
        "wait(30)\nconst row = findChild(page, 'row')\nverify(row)\n"
        "// wait(100) is not executable\n"
        "wait(60) // fixed: proves absence\ncompare(calls.length, 0)\n",
        encoding="utf-8")
    assert fixed_wait_checks(tmp_path) == [("tst_inline.qml", 1), ("tst_inline.qml", 2)]


def test_detector_sees_cpp_waits(tmp_path):
    (tmp_path / "test_probe.cpp").write_text(
        "QTest::qWait(100); QCOMPARE(x, 1);\n"
        "QTest::qWait(50); // fixed: proves absence\nQVERIFY(calls.empty());\n"
        "QTRY_VERIFY(ready);\n// QTest::qWait(300);\n"
        "while (n < 9) { samples.push_back(now()); QTest::qWait(3); } // fixed: samples timing - clock read every 3 ms\n"
        "QTest::qWait(3); // fixed: samples timing\n"
        "QTest::qWait(3); QVERIFY(ok); // fixed: samples timing - a check in disguise\n",
        encoding="utf-8")
    assert fixed_wait_checks(tmp_path) == [("test_probe.cpp", 1), ("test_probe.cpp", 7), ("test_probe.cpp", 8)]


def test_detector_sees_helper_ending_in_wait(tmp_path):
    (tmp_path / "tst_helper.qml").write_text(
        "function open(page) {\n    tryVerify(function() { return page.ready })\n    wait(50)\n}\n"
        "open(page)\nverify(page.visible)\n", encoding="utf-8")
    assert fixed_wait_checks(tmp_path) == [("tst_helper.qml", 3)]


def test_detector_sees_duration_expressions_and_spacing(tmp_path):
    (tmp_path / "tst_expression.qml").write_text(
        "wait(Theme.motionSlow / 3)\nverify(visible)\n"
        "wait (delay)\ncompare(x, 1)\n"
        "spy.wait(1000)\n", encoding="utf-8")
    (tmp_path / "test_expression.cpp").write_text(
        "QTest::qWait (delay);\nQVERIFY(ready);\n", encoding="utf-8")
    assert fixed_wait_checks(tmp_path) == [
        ("test_expression.cpp", 1), ("tst_expression.qml", 1), ("tst_expression.qml", 3)]
