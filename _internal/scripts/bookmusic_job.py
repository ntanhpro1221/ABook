"""Windowless local verification jobs; invoke through the owner's run_detached wrapper."""
from __future__ import annotations

import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "desktop_qt/tools"))
from qt_sdk import qt_root

OUT = ROOT / "runtime" / "bookmusic"
SDK = Path(os.environ.get("LOCALAPPDATA", "")) / "Android/Sdk"
JAVA = Path("C:/Program Files/Android/Android Studio/jbr/bin/java.exe")
PYTHON = Path(os.environ["ABOOK_RUNTIME"]) / ".venv/Scripts/python.exe"
NO_WINDOW = 0x08000000
# Qt width-test binary of this checkout's own build; another build is chosen with ABOOK_WIDTH_TESTS, never a machine-specific default.
WIDTH_TESTS = Path(os.environ.get("ABOOK_WIDTH_TESTS") or ROOT / "desktop_qt/build/width_tests/WidthTests.exe")
# The emulator this script starts (job "emulator") listens on this console port; adb names it emulator-<port>.
EMULATOR_PORT = os.environ.get("ABOOK_EMULATOR_PORT", "5620")
EMULATOR = f"emulator-{EMULATOR_PORT}"


def run(command, cwd, name, env=None):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.status.json").unlink(missing_ok=True)
    with (OUT / f"{name}.log").open("w", encoding="utf-8") as log:
        result = subprocess.run([str(x) for x in command], cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT, creationflags=NO_WINDOW)
    (OUT / f"{name}.status.json").write_text(json.dumps({"exit": result.returncode, "command": [str(x) for x in command]}), encoding="utf-8")
    return result.returncode


def memory_gate():
    class Memory(ctypes.Structure):
        _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [(key, ctypes.c_ulonglong) for key in ("total", "free", "page", "freepage", "virtual", "freevirtual", "extended")]
    for _ in range(2160):
        memory = Memory(); memory.length = ctypes.sizeof(memory)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory))
        if memory.free >= 6 * 1024**3:
            return
        time.sleep(10)
    raise RuntimeError("Less than 6 GiB available RAM")


def main():
    job = sys.argv[1]
    env = dict(os.environ, JAVA_HOME=str(JAVA.parent.parent), ANDROID_HOME=str(SDK), ANDROID_SDK_ROOT=str(SDK), PYTHONUTF8="1")
    if job in {"emulator", "emulator-host"}:
        gpu = "host" if job == "emulator-host" else "swiftshader_indirect"
        return run([SDK / "emulator/emulator.exe", "-avd", "navanim", "-read-only", "-port", EMULATOR_PORT, "-no-window", "-no-snapshot", "-no-boot-anim", "-noaudio", "-memory", "1536", "-gpu", gpu], ROOT, job, env)
    if job.startswith("gradle"):
        memory_gate()
        return run([JAVA, "-classpath", "gradle/wrapper/gradle-wrapper.jar", "org.gradle.wrapper.GradleWrapperMain", "--no-daemon", "--max-workers=2", "-Dorg.gradle.jvmargs=-Xmx6g -XX:MaxMetaspaceSize=1g", "-Pkotlin.compiler.execution.strategy=in-process", *sys.argv[2:]], ROOT / "mobile/android", job, env)
    if job == "audit":
        adb = SDK / "platform-tools/adb.exe"
        mode = sys.argv[2]
        apks = [ROOT / "mobile/android" / apk for apk in ("app/build/outputs/apk/debug/app-debug.apk", "app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk")]
        if mode.startswith("before") and (OUT / "before-app.apk").is_file():
            apks = [OUT / "before-app.apk", OUT / "before-test.apk"]
        for apk in apks:
            code = run([adb, "-s", EMULATOR, "install", "-r", apk], ROOT, f"install-{mode}-{Path(apk).stem}", env)
            if code: return code
        result = run([adb, "-s", EMULATOR, "shell", "am", "instrument", "-w", "-r", "-e", "bookMusicAudit", "true", "-e", "class", "vn.abook.player.BookMusicScrollAuditTest", "com.ngdtuanh.abook.dev.test/androidx.test.runner.AndroidJUnitRunner"], ROOT, f"audit-{mode}", env)
        if "OK (1 test)" not in (OUT / f"audit-{mode}.log").read_text(encoding="utf-8"):
            return 1
        run([adb, "-s", EMULATOR, "pull", "/sdcard/Android/data/com.ngdtuanh.abook.dev/files/bookmusic-scroll.json", OUT / f"{mode}.json"], ROOT, f"pull-{mode}", env)
        return result
    if job == "paired":
        for mode in ("before-host1", "after-host1", "before-host2", "after-host2"):
            sys.argv = [sys.argv[0], "audit", mode]
            if main(): return 1
        return 0
    if job == "web":
        node = Path("C:/Program Files/nodejs/node.exe")
        return run([node, "node_modules/vitest/vitest.mjs", "run", *sys.argv[2:]], ROOT / "ui", job, env)
    if job == "final-checks":
        node = Path("C:/Program Files/nodejs/node.exe")
        commands = [
            ("web-final", [node, "node_modules/vitest/vitest.mjs", "run", "src/music", "src/listen/bookSplit.dom.test.tsx", "src/listen/bookScreenErrors.dom.test.tsx", "src/listen/motion139Book.dom.test.tsx", "--maxWorkers=2"], ROOT / "ui"),
            ("typecheck", [node, "node_modules/typescript/bin/tsc", "-p", "tsconfig.json"], ROOT / "ui"),
            ("pytest-final", [PYTHON, "-X", "utf8", "-m", "pytest", "-o", "addopts=", "-q", "tests/test_music_library.py", "tests/test_release_gate.py::test_parity_workers_run_the_real_checker_and_propagate_failure"], ROOT),
        ]
        failed = []
        for name, command, cwd in commands:
            if run(command, cwd, name, env): failed.append(name)
        (OUT / "final-checks.status.json").write_text(json.dumps({"failed": failed}), encoding="utf-8")
        return int(bool(failed))
    if job == "rules":
        return run([PYTHON, "-X", "utf8", "scripts/ui_parity_rules.py"], ROOT, job, env)
    if job == "qt":
        qt = qt_root() / "bin"
        env.update(PATH=str(qt) + os.pathsep + env["PATH"], QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software",
                   QML2_IMPORT_PATH=str(ROOT / "desktop_qt/tests/qml/stub"), QML_IMPORT_PATH=str(ROOT / "desktop_qt/tests/qml/stub"),
                   ABOOK_GLYPH_AUDIT=str(OUT / "qt-glyph.json"))
        return run([WIDTH_TESTS, "-input", ROOT / "desktop_qt/tests/width/tst_book_music.qml", "-o", str(OUT / "qt-results.txt") + ",txt", "-o", str(OUT / "qt-results.xml") + ",xml"], ROOT, job, env)
    if job == "python":
        return run([PYTHON, "-X", "utf8", *sys.argv[2:]], ROOT, job, env)
    if job == "prepare":
        for name, arguments in (("strings", ["scripts/gen_ui_strings.py"]), ("parity-generate", ["scripts/ui_parity.py"]),
                                ("qt-parity-generate", ["scripts/ui_parity_qt.py"]), ("prepare-shared", ["scripts/prepare_ui.py"])):
            result = run([PYTHON, "-X", "utf8", *arguments], ROOT, name, env)
            if result: return result
        return 0
    if job == "checks":
        node = Path("C:/Program Files/nodejs/node.exe")
        commands = [
            ("web-final", [node, "node_modules/vitest/vitest.mjs", "run", "src/music", "src/listen/bookSplit.dom.test.tsx", "src/listen/bookScreenErrors.dom.test.tsx", "src/listen/motion139Book.dom.test.tsx", "--maxWorkers=2"], ROOT / "ui"),
            ("typecheck", [node, "node_modules/typescript/bin/tsc", "-p", "tsconfig.json"], ROOT / "ui"),
            ("ui-parity", [PYTHON, "-X", "utf8", "scripts/release_gate.py", "--worker", "ui-parity", "--base", "c7452dc34"], ROOT),
            ("ui-parity-qt", [PYTHON, "-X", "utf8", "scripts/release_gate.py", "--worker", "ui-parity-qt", "--base", "c7452dc34"], ROOT),
            ("pytest", [PYTHON, "-X", "utf8", "-m", "pytest", "-o", "addopts=", "-q", "tests/test_music_library.py", "tests/test_release_gate.py", "tests/test_ui_strings.py", "tests/test_ui_parity.py", "tests/test_ui_parity_qt.py"], ROOT),
        ]
        failed = []
        for name, command, cwd in commands:
            if run(command, cwd, name, env): failed.append(name)
        (OUT / "checks.status.json").write_text(json.dumps({"failed": failed}), encoding="utf-8")
        return int(bool(failed))
    raise ValueError(job)


if __name__ == "__main__":
    raise SystemExit(main())
