"""Reject new load-sensitive test sites across pytest, JVM, vitest and Qt."""
import json
import socket

import pytest

from scripts.flaky_patterns import BASELINE, Finding, other_patterns, python_patterns, regressions, scan, test_files as source_files


def test_load_sensitive_sites_only_shrink():
    additions = regressions(scan(), json.loads(BASELINE.read_text(encoding="utf-8")))
    assert not additions, "Use a fake clock, a completion signal, an OS-assigned port or isolated temp storage:\n" + "\n".join(
        f"{number} new: {key}" for key, number in sorted(additions.items())
    )


def test_python_aliases_delays_deadlines_ports_and_shared_state_are_detected():
    source = '''
import time as clock
from time import sleep as nap
from datetime import datetime as Date
from socketserver import TCPServer
import tempfile, socket, os, threading
PORT = 4321
nap(.1)
clock.time()
Date.now()
gate.wait(.1)
threading.Event().wait(.1)
socket.socket().bind(('127.0.0.1', PORT))
TCPServer(('localhost', 4322), Handler)
tempfile.gettempdir()
os.chdir('work')
"time.sleep(3)"
# time.sleep(9)
'''
    rules = [rule for _, rule, _ in python_patterns(source)]
    assert rules.count("fixed-delay") == 2
    assert rules.count("wall-clock") == 2
    assert rules.count("short-thread-timeout") == 2
    assert rules.count("fixed-listener-port") == 2
    assert rules.count("shared-temp") == 1
    assert rules.count("process-state") == 1


def test_ephemeral_ports_isolated_temp_and_condition_signals_are_allowed():
    assert list(python_patterns('''
socket.socket().bind(('127.0.0.1', 0))
tempfile.TemporaryDirectory()
tempfile.mkdtemp()
started.wait(5)
''')) == []


@pytest.mark.parametrize(("suffix", "source", "expected"), [
    (".kt", '''Thread.sleep(20)
System.currentTimeMillis()
ServerSocket(4321)
File(System.getProperty("java.io.tmpdir"), "shared")
gate.await(1, TimeUnit.SECONDS)
// Thread.sleep(20)
val text = "Thread.sleep(2)"
''', ["fixed-delay", "wall-clock", "fixed-listener-port", "shared-temp", "short-thread-timeout"]),
    (".ts", '''await new Promise(done => setTimeout(done, 20));
Date.now(); new Date();
// setTimeout(done, 10)
const text = "Date.now()";
''', ["fixed-delay", "wall-clock", "wall-clock"]),
    (".qml", '''wait(10); verify(ok)
wait (duration)
spy.wait(1000)
// wait(20)
''', ["qt-fixed-delay", "qt-fixed-delay"]),
    (".cpp", 'QTest::qWait(5);\nwhile (!thread->wait(10)) {}', ["qt-fixed-delay"]),
])
def test_other_languages_ignore_comments_and_strings(suffix, source, expected):
    assert [rule for _, rule, _ in other_patterns(source, suffix)] == expected


def test_ratchet_does_not_allow_swapping_sites_or_adding_duplicate_calls():
    old = Finding("tests/a.py", 1, "fixed-delay", "time.sleep(1)")
    moved = Finding("tests/a.py", 900, "fixed-delay", "time.sleep(1)")
    new = Finding("tests/b.py", 1, "fixed-delay", "time.sleep(1)")
    baseline = {old.key: 1}
    assert not regressions([moved], baseline)
    assert regressions([new], baseline) == {new.key: 1}
    assert regressions([old, old], baseline) == {old.key: 1}


def test_discovery_covers_all_four_stacks_without_entering_node_modules(tmp_path):
    names = ["tests/test_a.py", "mobile/android/app/src/test/java/ATest.kt", "ui/src/a.test.tsx",
             "ui/scripts/a.test.mjs", "desktop_qt/tests/tst_a.qml", "desktop_qt/tests/test_a.cpp",
             "scripts/audit/test_probe.py", "desktop_qt/tools/test_probe.py"]
    for name in [*names, "ui/node_modules/dependency/test.js", "mobile/android/app/build/ATest.kt"]:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
    assert {p.relative_to(tmp_path).as_posix() for p in source_files(tmp_path)} == set(names)


def test_java_home_is_not_a_shared_temp_directory():
    assert list(other_patterns('val keytool = File(System.getProperty("java.home"), "bin/keytool")', ".kt")) == []


def test_elapsed_measurements_are_inventoried_too():
    assert [rule for _, rule, _ in python_patterns("import time\ntime.monotonic()\ntime.perf_counter()\n")] == ["elapsed-clock", "elapsed-clock"]
    assert [rule for _, rule, _ in other_patterns("System.nanoTime()", ".kt")] == ["elapsed-clock"]


@pytest.mark.parametrize("source", [
    "def free():\n s = socket.socket()\n p = s.getsockname()[1]\n s.close()\n return p\n",
    "def free():\n with socket.socket() as s:\n  p = s.getsockname()[1]\n connect(p)\n",
])
def test_released_ports_are_detected_even_with_context_managers(source):
    assert [rule for _, rule, _ in python_patterns(source)] == ["released-port"]


def test_a_port_kept_reserved_until_consumption_is_allowed():
    assert list(python_patterns("def test():\n with socket.socket() as s:\n  p = s.getsockname()[1]\n  connect(p)\n")) == []
    assert [rule for _, rule, _ in other_patterns("val p = ServerSocket(0).use { it.localPort }", ".kt")] == ["released-port"]


def test_stable_service_ports_must_not_be_shared_between_test_processes():
    assert [rule for _, rule, _ in python_patterns("socket.create_server(('127.0.0.1', bluetooth.stable_port(PHONE)))")] == ["fixed-listener-port"]


def test_kotlin_timeouts_respect_units():
    assert list(other_patterns("gate.await(5, TimeUnit.SECONDS)\nthread.join(2000)", ".kt")) == []
    assert [rule for _, rule, _ in other_patterns("gate.await(500, TimeUnit.MILLISECONDS)\nthread.join(50)", ".kt")] == ["short-thread-timeout", "short-thread-timeout"]


def test_refused_port_is_unlistening_and_stays_reserved(refused_tcp_port):
    with socket.socket() as competitor:
        with pytest.raises(OSError):
            competitor.bind(("127.0.0.1", refused_tcp_port))
    with pytest.raises(ConnectionRefusedError):
        socket.create_connection(("127.0.0.1", refused_tcp_port), timeout=5)
