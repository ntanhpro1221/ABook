"""Một lệnh kiểm phát hành, không suy xanh từ mã thoát hay từ kiểm tra bị bỏ sót.

Chạy từ _internal: runtime/.venv/Scripts/python.exe -X utf8 scripts/release_gate.py.
--only chỉ kiểm một phần; MANUAL chặn phát hành cho tới khi có bằng chứng riêng.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from datetime import datetime, timezone
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
# Từ của chính máy dò không phải mã chuyển đổi; chỉ miễn đúng dòng khai báo này.
FORBIDDEN_TERMS = ("migrat", "legacy", "nâng cấp từ")


@dataclass
class Check:
    name: str
    command: list[str] = field(default_factory=list)
    cwd: Path = ROOT
    timeout: float = 120
    parser: str = "exit"
    requires: tuple[str, ...] = ()
    manual: str = ""


@dataclass
class Execution:
    returncode: int
    output: str = ""
    timed_out: bool = False


def parse_pytest(output: str) -> dict[str, int]:
    """Chỉ tin dòng tổng kết cuối, không lấy số trong tên test hoặc short summary."""
    lines = ANSI.sub("", output).splitlines()
    summaries = [line.strip("= ") for line in lines
                 if re.fullmatch(r"[= ]*\d+ (?:passed|failed|errors?|skipped|deselected|xfailed|xpassed|warnings?)\b.* in .+[= ]*", line)]
    if not summaries or re.search(r"\b(?:no tests ran|collected 0 items)\b", output):
        raise ValueError("pytest: không có summary hoặc không thu được test")
    counts = {"passed": 0, "failed": 0, "error": 0, "skipped": 0, "xfailed": 0, "xpassed": 0}
    for number, kind in re.findall(r"(\d+) (passed|failed|errors?|skipped|xfailed|xpassed)\b", summaries[-1]):
        counts["error" if kind.startswith("error") else kind] = int(number)
    return counts


def parse_vitest(output: str) -> dict[str, int]:
    lines = re.findall(r"^\s*Tests\s+(.+)$", ANSI.sub("", output), re.M)
    if len(lines) != 1:
        raise ValueError("vitest: thiếu hoặc trùng dòng Tests")
    counts = {"passed": 0, "failed": 0, "skipped": 0}
    for number, kind in re.findall(r"(\d+)\s+(passed|failed|skipped|todo)\b", lines[0]):
        counts["skipped" if kind == "todo" else kind] += int(number)
    total = re.search(r"\((\d+)\)\s*$", lines[0])
    if not total or sum(counts.values()) != int(total.group(1)):
        raise ValueError("vitest: tổng Tests không khớp số đã đọc")
    errors = re.findall(r"(?:Unhandled Errors|Errors)\s+(\d+)", ANSI.sub("", output))
    counts["error"] = sum(map(int, errors))
    return counts


def parse_gradle(directory: Path) -> dict[str, int]:
    files = sorted(directory.glob("**/TEST-*.xml"))
    if not files:
        raise ValueError("Gradle: không có XML mới trong build/test-results")
    counts = {"passed": 0, "failed": 0, "error": 0, "skipped": 0, "suites": 0}
    for path in files:
        root = ET.parse(path).getroot()
        suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
        for suite in suites:
            # Đối chiếu cả thuộc tính lẫn testcase: XML rỗng/cắt cụt không phải lượt xanh.
            cases = suite.findall("testcase")
            total = int(suite.attrib["tests"])
            failed = int(suite.attrib["failures"])
            errors = int(suite.attrib["errors"])
            skipped = int(suite.attrib.get("skipped", "0"))
            actual = [sum(case.find(tag) is not None for case in cases) for tag in ("failure", "error", "skipped")]
            if total != len(cases) or actual != [failed, errors, skipped] or min(total, failed, errors, skipped) < 0:
                raise ValueError(f"Gradle: XML không khớp testcase: {path.name}")
            counts["passed"] += total - failed - errors - skipped
            counts["failed"] += failed
            counts["error"] += errors
            counts["skipped"] += skipped
            counts["suites"] += 1
    return counts


def safe_env() -> dict[str, str]:
    env = dict(os.environ, CUDA_VISIBLE_DEVICES="-1", QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software",
               QSG_RHI_BACKEND="software", PYTHONIOENCODING="utf-8", PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1",
               PYTHON=sys.executable, ABOOK_PYTHON=sys.executable, NO_COLOR="1", CI="1")
    # Import app luôn từ worktree này, không từ bản editable của runtime dùng chung.
    env["PYTHONPATH"] = str(ROOT)
    env["ABOOK_TEST_PYTHON"] = sys.executable
    env["JAVA_HOME"] = os.environ.get("JAVA_HOME") or "C:/Program Files/Android/Android Studio/jbr"
    return env


def run_process(command: list[str], cwd: Path, timeout: float) -> Execution:
    flags = (subprocess.CREATE_NO_WINDOW | subprocess.BELOW_NORMAL_PRIORITY_CLASS) if os.name == "nt" else 0
    proc = subprocess.Popen(command, cwd=cwd, env=safe_env(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            encoding="utf-8", errors="replace", creationflags=flags)
    try:
        output, _ = proc.communicate(timeout=timeout)
        return Execution(proc.returncode, output)
    except subprocess.TimeoutExpired:
        # Chỉ thu hồi cây của check này; không để browser/Gradle mồ côi sau timeout.
        import psutil

        try:
            parent = psutil.Process(proc.pid)
            children = parent.children(recursive=True)
            for process in [*reversed(children), parent]:
                try:
                    process.kill()
                except psutil.NoSuchProcess:
                    pass
        except psutil.NoSuchProcess:
            pass
        try:
            output, _ = proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.stdout.close()
            output = ""
        return Execution(-1, output, True)


def py(*args: str) -> list[str]:
    return [sys.executable, "-X", "utf8", *args]


def worker_command(name: str) -> list[str]:
    return py(str(Path(__file__).resolve()), "--worker", name)


def checks() -> list[Check]:
    node = shutil.which("node") or "node"
    ui = ROOT / "ui"
    definitions = [
        Check("compile", py("-m", "compileall", "-q", "abook", "tests", "scripts")),
        Check("pytest", py("-m", "pytest", "-o", "addopts=", "-q", "-rf", "--durations=30"), timeout=7200, parser="pytest"),
        Check("typecheck", [node, "node_modules/typescript/bin/tsc", "-p", "tsconfig.json"], ui, 180),
        Check("vitest", [node, "node_modules/vitest/vitest.mjs", "run", "--no-cache", "--configLoader", "runner", "--reporter", "verbose"],
              ui, 900, "vitest"),
        Check("android-unit", worker_command("android-unit"), timeout=900, parser="json"),
        Check("ui-parity", py("scripts/ui_parity.py", "--check")),
        Check("ui-parity-qt", py("scripts/ui_parity_qt.py", "--check")),
        Check("dom-count", worker_command("dom-count"), parser="json", requires=("vitest",)),
        Check("ui-build", [node, "node_modules/vite/bin/vite.js", "build", "--configLoader", "runner"], ui, 180),
        Check("tap-audit", py("scripts/tap_audit/run.py", "--output", "<run>/tap-audit.json"), timeout=600,
              parser="tap", requires=("ui-build",)),
        Check("tap-negative", py("scripts/tap_audit/run.py", "--inject-fault", "--output", "<run>/tap-negative.json"),
              timeout=600, parser="tap-negative", requires=("ui-build",)),
        Check("gallery-build", [node, "node_modules/vite/bin/vite.js", "build", "-c", "vite.gallery.config.ts",
                                "--configLoader", "runner"], ui, 180),
        Check("gallery-inspect", [node, "scripts/gallery_inspect.mjs", "--theme", "both", "--out", "<run>/gallery"],
              ui, 1800, "gallery", ("gallery-build",)),
        Check("contrast", [node, "scripts/check_contrast.mjs", "--compact"], ui),
        Check("qt-tests", worker_command("qt-tests"), timeout=3000, parser="json"),
    ]
    definitions += [Check(name, worker_command(name), parser="json") for name in
                    ("quality-hash", "changelog", "versions", "licenses", "diff-safety", "forbidden-terms", "batch-crlf",
                     "studio-pins", "android-sdk")]
    definitions += [Check(name, manual=detail) for name, detail in (
        ("manual-ui", "Android thật/máy ảo; duyệt ảnh gallery, README, nguồn truyện trong diff và giấy phép thành phần đóng gói"),
        ("manual-quality", "Lead duyệt hash và tác động tới sách đang chạy; không dừng/resume pha phân tích"),
        ("manual-artifacts", "Bộ cài/APK ký, packaged smoke, audio sink hai lượt + đối chứng, cài/cập nhật/gỡ hồ sơ giả"),
        ("manual-publish", "Commit/tag đúng, notes + 6 assets + latest endpoint, cất mapping R8 vào kho riêng"),
        ("manual-dependencies", "Duyệt dependency audit mỗi phiên bản; cần máy Studio/GPU/Ollama, không chạy ở gate CPU"),
    )]
    return definitions


def git(*args: str) -> str:
    run = subprocess.run(["git", *args], cwd=REPO, capture_output=True, encoding="utf-8", errors="strict",
                         timeout=30, check=True, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    return run.stdout


def tracked_and_new() -> list[Path]:
    names = git("ls-files", "-z", "--cached", "--others", "--exclude-standard").split("\0")
    return [REPO / name for name in dict.fromkeys(names) if name and (REPO / name).is_file()]


def changed_files() -> list[Path]:
    names = git("diff", "HEAD", "--name-only", "-z").split("\0")
    names += git("ls-files", "--others", "--exclude-standard", "-z").split("\0")
    return [REPO / name for name in dict.fromkeys(names) if name and (REPO / name).is_file()]


def added_lines(path: Path) -> list[str]:
    relative = path.relative_to(REPO).as_posix()
    if git("ls-files", "--error-unmatch", "--", relative).strip():
        diff = git("diff", "HEAD", "--no-ext-diff", "--unified=0", "--", relative)
        return [line[1:] for line in diff.splitlines() if line.startswith("+") and not line.startswith("+++")]
    return []


def source_lines(path: Path) -> list[str]:
    relative = path.relative_to(REPO).as_posix()
    tracked = git("ls-files", "--", relative).strip()
    return added_lines(path) if tracked else path.read_text(encoding="utf-8").splitlines()


def version() -> str:
    import tomllib

    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]


def require(ok: bool, detail: str) -> None:
    if not ok:
        raise ValueError(detail)


def worker(name: str) -> dict:
    """Kiểm thuần nguồn cũng chạy trong subprocess để có deadline như bộ test."""
    if name == "android-unit":
        results = ROOT / "mobile/android/app/build/test-results/testDebugUnitTest"
        # Xoá riêng XML cũ trong worktree, không bao giờ dùng kết quả của lần trước.
        for path in results.glob("**/TEST-*.xml"):
            require(path.resolve().is_relative_to(REPO.resolve()), "XML ra ngoài worktree")
            path.unlink()
        android = ROOT / "mobile/android"
        command = [str(android / "gradlew.bat"), "--no-daemon", ":app:testDebugUnitTest", "--rerun-tasks"]
        execution = run_process(command, android, 840)
        print(execution.output, end="")
        counts = parse_gradle(results)
        ok = (execution.returncode == 0 and not execution.timed_out and counts["passed"] > 0
              and not counts["failed"] and not counts["error"])
        return {"counts": counts, "status": "PASS" if ok else "FAIL", "detail": "Gradle: đối chiếu exit và XML"}
    if name == "qt-tests":
        return qt_tests()
    if name == "quality-hash":
        sys.path.insert(0, str(ROOT))
        from abook.quality_policy import QUALITY_IMPLEMENTATION_FILES, quality_implementation_hash

        digest = quality_implementation_hash()
        require(bool(re.fullmatch(r"[0-9a-f]{64}", digest)), "hash không hợp lệ")
        locked = {(ROOT / "abook" / item).resolve() for item in QUALITY_IMPLEMENTATION_FILES}
        touched = [path.relative_to(REPO).as_posix() for path in changed_files() if path.resolve() in locked]
        return {"counts": {"files": len(locked), "changed": len(touched)}, "hash": digest, "locked_changes": touched,
                "implementation_files": list(QUALITY_IMPLEMENTATION_FILES)}
    if name == "changelog":
        text = (ROOT / "docs/CHANGELOG.md").read_text(encoding="utf-8")
        section = re.search(r"^## \[Chưa phát hành\]\s*\n(.*?)(?=^## |\Z)", text, re.S | re.M)
        bullets = re.findall(r"^[-*] \S.+", section.group(1), re.M) if section else []
        require(bool(bullets), "CHANGELOG [Chưa phát hành] rỗng/thiếu")
        return {"counts": {"entries": len(bullets)}}
    if name == "licenses":
        files = [ROOT / "LICENSE", ROOT / "docs/THIRD_PARTY.md"]
        require(all(path.is_file() and path.stat().st_size > 0 for path in files), "thiếu LICENSE/THIRD_PARTY")
        return {"counts": {"files": len(files)}}
    if name == "versions":
        import tomllib

        expected = version()
        require(bool(re.fullmatch(r"\d+\.\d+\.\d+", expected)), "version không phải x.y.z")
        package = json.loads((ROOT / "ui/package.json").read_text(encoding="utf-8"))
        lock = json.loads((ROOT / "ui/package-lock.json").read_text(encoding="utf-8"))
        uv = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
        versions = [package["version"], lock["version"], lock["packages"][""]["version"]]
        versions += [p["version"] for p in uv["package"] if p["name"] == "abook"]
        gradle = (ROOT / "mobile/android/app/build.gradle").read_text(encoding="utf-8")
        versions += [re.search(r'versionName "([^"]+)"', gradle).group(1)]
        require(len(versions) == 5 and all(v == expected for v in versions), "version giữa pyproject/UI/lock/Android bị lệch")
        code = int(re.search(r"versionCode (\d+)", gradle).group(1))
        old = git("show", "HEAD:_internal/mobile/android/app/build.gradle")
        old_code = int(re.search(r"versionCode (\d+)", old).group(1))
        old_version = re.search(r'versionName "([^"]+)"', old).group(1)
        require(code > 0 and code == old_code + int(old_version != expected), "versionCode không tăng đúng 1 khi bump")
        cmake = (ROOT / "desktop_qt/CMakeLists.txt").read_text(encoding="utf-8")
        require('file(READ "${CMAKE_CURRENT_SOURCE_DIR}/../ui/package.json" ABOOK_PACKAGE_JSON)' in cmake
                and 'string(JSON ABOOK_VERSION GET "${ABOOK_PACKAGE_JSON}" version)' in cmake
                and "project(ABookDesk VERSION ${ABOOK_VERSION}" in cmake, "Qt không dùng version từ UI package")
        return {"counts": {"sources": 8, "versionCode": code}, "version": expected}
    if name == "dom-count":
        files = sorted(path.relative_to(REPO).as_posix() for path in (ROOT / "ui/src").rglob("*.dom.test.*"))
        baseline = [p for p in git("ls-tree", "-r", "--name-only", "HEAD", "--", "_internal/ui/src").splitlines()
                    if ".dom.test." in p]
        require(bool(files) and not set(baseline) - set(files), "thiếu file test DOM so với HEAD")
        return {"counts": {"files": len(files), "baseline": len(baseline)}, "files": files}
    if name == "batch-crlf":
        files = [p for p in tracked_and_new() if p.suffix.lower() in {".bat", ".cmd"}]
        bad = []
        for path in files:
            data = path.read_bytes()
            if b"\n" in data.replace(b"\r\n", b"") or b"\r" in data.replace(b"\r\n", b""):
                bad.append(path.relative_to(REPO).as_posix())
        require(bool(files) and not bad, "batch không CRLF: " + ", ".join(bad))
        return {"counts": {"files": len(files)}}
    if name in {"diff-safety", "forbidden-terms"}:
        files = changed_files()
        problems = []
        prose_mentions = []
        terms = re.compile("|".join(FORBIDDEN_TERMS), re.I)
        secret = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{20,})|(?:password|secret|api[_-]?key|token)\s*[:=]\s*[\"'][A-Za-z0-9/+_=.-]{24,}[\"']", re.I)
        for path in files:
            relative = path.relative_to(REPO).as_posix()
            if name == "diff-safety":
                prohibited = (path.suffix.lower() in {".wav", ".mp3", ".m4a", ".m4b", ".flac", ".ogg", ".aac", ".opus", ".wma", ".aiff", ".pcm", ".keystore", ".jks", ".p12", ".pfx", ".key"}
                              or path.name.lower() in {"listening.json", "devices.json", "computers.json", "reviews.json", "preferences.json", "local.properties"}
                              or any(p.lower() in {"corpus", "text", "text_tmp"} for p in path.relative_to(REPO).parts))
                require(not prohibited, f"file riêng tư/audio/khoá trong diff: {relative}")
                data = path.read_bytes()
                require(b"\0" not in data, f"binary trong diff cần duyệt: {relative}")
                lines = source_lines(path)
                if any(secret.search(line) for line in lines):
                    problems.append(relative)  # Chỉ ghi đường dẫn, tuyệt đối không in giá trị khoá.
            elif path.suffix.lower() in {".py", ".ts", ".tsx", ".kt", ".cpp", ".h", ".qml", ".js", ".mjs", ".ps1", ".bat", ".cmd"}:
                lines = source_lines(path)
                if path.resolve() == Path(__file__).resolve():
                    declaration = "FORBIDDEN_TERMS = " + repr(FORBIDDEN_TERMS).replace("'", '"')
                    lines = [line for line in lines if line != declaration]
                if any(terms.search(line) for line in lines):
                    problems.append(relative)
            elif name == "forbidden-terms" and path.suffix.lower() in {".md", ".txt", ".json", ".toml"}:
                if any(terms.search(line) for line in source_lines(path)):
                    prose_mentions.append(relative)
        require(not problems, f"{name}: cần duyệt " + ", ".join(problems))
        return {"counts": {"files": len(files), "findings": 0, "prose_mentions": len(prose_mentions)},
                "prose_mentions_for_manual_review": prose_mentions}
    if name in {"studio-pins", "android-sdk"}:
        module = load_module(ROOT / "scripts/release.py", "gate_release")
        functions = [module.check_android_sdk] if name == "android-sdk" else [
            module.check_studio_assets_pinned, module.check_word_align_pinned, module.check_speaker_model_pinned]
        for function in functions:
            function()
        return {"counts": {"checks": len(functions)}}
    raise ValueError(f"không có worker {name}")


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def run_qt_suite(executable: Path, cwd: Path, log: Path, runner=run_process) -> Execution:
    """Qt GUI không có stdout: yêu cầu file mới như build.bat, rồi đọc byte thực đã ghi."""
    require(not log.exists(), "Qt: từ chối dùng log cũ " + log.name)
    timeout = 1800 if executable.stem == "WidthTests" else 360
    result = runner([str(executable), "-o", str(log) + ",txt"], cwd, timeout)
    require(log.is_file(), "Qt: không tạo log " + log.name)
    output = log.read_text(encoding="utf-8", errors="replace")
    if result.output:
        output += "\n" + result.output
        log.write_text(output, encoding="utf-8")
    return Execution(result.returncode, output, result.timed_out)


def qt_tests() -> dict:
    qt = ROOT / "desktop_qt"
    build_text = (qt / "build.bat").read_text(encoding="ascii")
    targets = re.findall(r'^call :test "%HERE%build\\([^"\n]+\.exe)"', build_text, re.M)
    require(bool(targets), "Qt: không tìm được suite trong build.bat")
    qt_root = Path(os.environ.get("QT_ROOT", "D:/Novels/native_desk_proto/qt611/6.10.3/msvc2022_64"))
    qwk_root = Path(os.environ.get("QWK_ROOT", "D:/Novels/native_desk_proto/qwk"))
    cmake_bin = Path(os.environ.get("CMAKE_BIN", "D:/Novels/native_desk_proto/qt/Tools/CMake_64/bin"))
    ninja_bin = Path(os.environ.get("NINJA_BIN", "D:/Novels/native_desk_proto/qt/Tools/Ninja"))
    vcvars = Path(os.environ.get("VCVARS", "C:/Program Files/Microsoft Visual Studio/18/Community/VC/Auxiliary/Build/vcvars64.bat"))
    require((qwk_root / "inst/lib/cmake/QWindowKit/QWindowKitConfig.cmake").is_file(), "Qt: cần QWindowKit đã dựng (không tự ghi worktree khác)")
    for path in (qt_root / "bin", cmake_bin / "cmake.exe", ninja_bin / "ninja.exe", vcvars):
        require(path.exists(), f"Qt: thiếu {path}")
    # build.bat truyền SDK cho cả qmllint; biến trong file cmd không quay về process Python.
    os.environ["QT_ROOT"] = str(qt_root)
    os.environ["PATH"] = str(qt_root / "bin") + os.pathsep + os.environ.get("PATH", "")
    # Chỉ dựng target test trong worktree; không chạy package, thiết bị hay sách thật.
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    command_file = ROOT / "runtime/release_gate" / ("qt-" + stamp) / "qt-tests.cmd"
    command_file.parent.mkdir(parents=True, exist_ok=True)
    build = qt / "build"
    commands = ["@echo off", f'call "{vcvars}" >nul', "if errorlevel 1 exit /b 1",
                f'set "PATH={qt_root / "bin"};{cmake_bin};{ninja_bin};%PATH%"',
                f'cmake -S "{qt}" -B "{build}" -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH="{qt_root};{qwk_root / "inst"}" -DCMAKE_MAKE_PROGRAM="{ninja_bin / "ninja.exe"}"',
                "if errorlevel 1 exit /b 1", 'cmake --build "' + str(build) + '" --parallel 4 --target ABookDesk_qmltyperegistration ' + " ".join(Path(t.replace("\\", "/")).stem for t in targets),
                "exit /b %errorlevel%"]
    command_file.write_bytes(("\r\n".join(commands) + "\r\n").encode("utf-8"))
    built = run_process(["cmd", "/d", "/c", str(command_file)], qt, 800)
    print(built.output)
    require(built.returncode == 0 and not built.timed_out, "Qt: configure/build lỗi hoặc timeout")
    validator = load_module(qt / "tools/check_test_results.py", "gate_qt_results")
    counts = {"passed": 0, "failed": 0, "skipped": 0, "suites": 0, "timeouts": 0, "missing_summaries": 0, "lint_failed": 0}
    failures = []
    for arguments in (("selftest", str(build)), (str(build),)):
        lint = run_process(py(str(qt / "tools/check_qml_members.py"), *arguments), qt, 120)
        print(lint.output)
        if lint.returncode != 0 or lint.timed_out:
            failures.append("qml_members " + arguments[0])
            counts["lint_failed"] += 1
    for target in targets:
        executable = build / target.replace("\\", "/")
        log = command_file.parent / (executable.stem + ".txt")
        # DLL Qt lấy từ bộ SDK chỉ đọc, không chép gì vào SDK.
        previous = os.environ.get("PATH", "")
        os.environ["PATH"] = str(qt_root / "bin") + os.pathsep + previous
        try:
            result = run_qt_suite(executable, qt, log)
        except Exception as exc:
            failures.append(executable.stem + ": " + str(exc))
            counts["suites"] += 1
            continue
        finally:
            os.environ["PATH"] = previous
        totals = re.findall(r"Totals: (\d+) passed, (\d+) failed, (\d+) skipped", result.output)
        counts["timeouts"] += int(result.timed_out)
        counts["missing_summaries"] += int(not totals)
        # Qt tính cả initTestCase/cleanupTestCase là passed; hai mục ấy chưa chứng minh có bài thử.
        if not (result.returncode == 0 and not result.timed_out and validator.check(log) and totals
                and all(int(t[0]) > 2 for t in totals)):
            failures.append(executable.stem + (": timeout (see per-suite deadline)" if result.timed_out else ": log/Totals/validation lỗi"))
        for row in totals:
            for key, number in zip(("passed", "failed", "skipped"), row):
                counts[key] += int(number)
        counts["suites"] += 1
    require(counts["suites"] == len(targets), "Qt: thiếu suite")
    return {"counts": counts, "status": "FAIL" if failures else "PASS", "failed_suites": failures, "logs": str(command_file.parent),
            "detail": "Qt: " + (", ".join(failures) if failures else "đủ suite, totals và QML lint")}


def validate_report(check: Check, execution: Execution, artifact: Path, row: dict | None = None) -> tuple[dict, dict]:
    kind = check.parser
    counts, evidence = {}, {}
    if execution.timed_out:
        raise ValueError(f"timeout sau {check.timeout}s")
    if kind == "pytest":
        counts = parse_pytest(execution.output)
    elif kind == "vitest":
        counts = parse_vitest(execution.output)
    elif kind == "json":
        evidence = json.loads(execution.output.splitlines()[-1])
        if row is not None:
            row.update(counts=evidence.get("counts", {}), evidence=evidence)
        require(evidence.get("status") == "PASS", evidence.get("detail", "worker FAIL"))
        counts = evidence.get("counts", {})
    elif kind.startswith("tap"):
        evidence = json.loads(artifact.read_text(encoding="utf-8"))
        scenarios = json.loads((ROOT / "scripts/tap_audit/scenarios.json").read_text(encoding="utf-8"))
        rows = evidence["results"]
        require([r["name"] for r in rows] == [s["name"] for s in scenarios], "tap: thiếu/trùng/sai scenarios")
        require(all(evidence.get("cleanup", {}).get(k) is True for k in ("edgeExited", "profileRemoved", "serverExited", "stateRemoved")), "tap: cleanup không đủ")
        passed = sum(row["status"] == "PASS" for row in rows)
        counts = {"passed": passed, "failed": len(rows) - passed, "scenarios": len(rows)}
        if row is not None:
            row.update(counts=counts, evidence=evidence)
        if kind == "tap-negative":
            require(execution.returncode == 1 and evidence.get("status") == "FAIL" and evidence.get("injected") is True,
                    "đối chứng âm không FAIL đúng cách")
            require(all(row.get("injected") is True and any(not c["pass_"] and "center reaches control" in c["name"]
                        for c in row["checks"]) for row in rows), "đối chứng âm thiếu lỗi pointer được cấy")
            return counts, evidence
        require(evidence.get("status") == "PASS" and counts["passed"] > 0 and not counts["failed"], "tap có scenario lỗi")
    elif kind == "gallery":
        evidence = json.loads(artifact.read_text(encoding="utf-8"))
        stories = evidence["stories"]
        require(bool(stories) and evidence["settings"]["themes"] == "both", "gallery rỗng hoặc thiếu chủ đề")
        require(all({s["theme"] for s in stories if s["id"] == story["id"]} == {"light", "dark"} for story in stories), "gallery thiếu chủ đề của story")
        blocked = evidence["settings"]["failOn"]
        require(bool(blocked) and "TAP REACH" in blocked and "SHEET GEOMETRY" in blocked, "gallery không có luật chặn pointer/sheet")
        failed = sum(evidence["counts"][rule] for rule in blocked)
        counts = {"stories": len(stories), "findings": failed, "error": len(evidence["errors"])}
        if row is not None:
            row.update(counts=counts, evidence=evidence)
        require(not failed and not evidence["errors"] and not any(s.get("error") for s in stories), "gallery có lỗi/vi phạm luật chặn")
        geometry = evidence["sheetGeometry"]
        require(geometry["trials"] > 0 and geometry["trials"] == geometry["completed"], "gallery thiếu lượt sheet hoàn tất")
    if kind in {"pytest", "vitest"}:
        require(counts.get("passed", 0) > 0 and not any(counts.get(k, 0) for k in ("failed", "error", "xpassed")),
                "summary có test lỗi hoặc không có test passed: " + json.dumps(counts))
    require(execution.returncode == 0, f"exit {execution.returncode}")
    return counts, evidence


def select_checks(definitions: list[Check], only: list[str] | None) -> list[Check]:
    by_name = {check.name: check for check in definitions}
    requested = set(only or by_name)
    require(not requested - by_name.keys(), "tên check lạ: " + ", ".join(sorted(requested - by_name.keys())))
    def add(name):
        for dependency in by_name[name].requires:
            if dependency not in requested:
                requested.add(dependency)
                add(dependency)
    for name in list(requested):
        add(name)
    return [check for check in definitions if check.name in requested]


UI_CHECKS = {"typecheck", "vitest", "ui-build", "gallery-build", "gallery-inspect", "contrast"}


def directory_link(link: Path, target: Path) -> None:
    """Only create new links inside the private gate workspace."""
    require(not link.exists(), "private link already exists: " + str(link))
    if os.name == "nt":
        result = run_process(["cmd", "/d", "/c", "mklink", "/J", str(link), str(target)], link.parent, 30)
        require(result.returncode == 0, "cannot create private junction: " + result.output)
    else:
        link.symlink_to(target, target_is_directory=True)


def dependency_problems(ui: Path, install: Path) -> list[str]:
    lock = json.loads((ui / "package-lock.json").read_text(encoding="utf-8"))["packages"]
    package = json.loads((ui / "package.json").read_text(encoding="utf-8"))
    problems = []
    for name in sorted(package.get("dependencies", {}) | package.get("devDependencies", {})):
        path = install / "node_modules" / name / "package.json"
        try:
            actual = json.loads(path.read_text(encoding="utf-8"))["version"]
            expected = lock["node_modules/" + name]["version"]
            if actual != expected:
                problems.append(f"{name}: installed {actual}, lock requires {expected}")
        except (OSError, ValueError, KeyError) as exc:
            problems.append(f"{name}: missing/unreadable dependency ({exc})")
    return problems


def prepare_ui(directory: Path, runner=run_process) -> tuple[Path, dict]:
    """One lock-keyed install, a fresh source copy, no writes to shared node_modules."""
    ui = ROOT / "ui"
    digest = hashlib.sha256((ui / "package.json").read_bytes() + (ui / "package-lock.json").read_bytes()).hexdigest()
    install = ROOT / "runtime/release_gate/dependencies" / digest
    install.mkdir(parents=True, exist_ok=True)
    marker = install / "complete.json"
    if not marker.is_file() or dependency_problems(ui, install):
        for name in ("package.json", "package-lock.json"):
            shutil.copyfile(ui / name, install / name)
        npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
        require(bool(npm), "UI dependencies: npm is missing; shared node_modules was not modified")
        execution = runner([npm, "ci", "--include=dev", "--no-audit", "--no-fund"], install, 900)
        log = directory / "ui-dependencies.log"
        log.write_text(execution.output, encoding="utf-8", newline="\n")
        require(execution.returncode == 0 and not execution.timed_out,
                f"UI dependencies: private npm ci failed (exit {execution.returncode}, timeout={execution.timed_out}); see {log}")
        problems = dependency_problems(ui, install)
        require(not problems, "UI dependencies: " + "; ".join(problems))
        marker.write_text(json.dumps({"lock_sha256": digest}) + "\n", encoding="utf-8", newline="\n")
    private_root = directory / "workspace/_internal"
    private_root.mkdir(parents=True)
    mirror = private_root / "ui"
    shutil.copytree(ui, mirror, ignore=shutil.ignore_patterns("node_modules", "dist", ".vite", ".cache"))
    directory_link(mirror / "node_modules", install / "node_modules")
    # Relative source/test fixture imports and the UI build destination keep their real layout.
    for name in ("abook", "docs", "tests", "mobile", "desktop_qt"):
        directory_link(private_root / name, ROOT / name)
    return mirror, {"install": str(install), "lock_sha256": digest, "source": str(ui), "mirror": str(mirror)}


def parse_confirmations(values: list[str], selected: list[Check], head: str, tree: str) -> dict[str, dict]:
    manuals = {check.name for check in selected if check.manual}
    confirmations = {}
    for value in values:
        name, separator, note = value.partition("=")
        require(bool(separator) and bool(note.strip()), "--confirm requires manual-name=nonempty-note")
        require(name in manuals, "--confirm is not a selected MANUAL row: " + name)
        require(name not in confirmations, "duplicate --confirm: " + name)
        confirmations[name] = {"note": note.strip(), "head": head, "tree_sha256": tree,
                               "confirmed_at": datetime.now(timezone.utc).isoformat()}
    return confirmations


def tree_fingerprint() -> str:
    """Bind human evidence to the source bytes too, including uncommitted changes."""
    digest = hashlib.sha256()
    for path in sorted(tracked_and_new()):
        digest.update(path.relative_to(REPO).as_posix().encode("utf-8") + b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def run_gate(selected: list[Check], directory: Path, runner=run_process, inject: str | None = None,
             confirmations: dict | None = None, prepare=prepare_ui) -> list[dict]:
    directory.mkdir(parents=True, exist_ok=True)
    rows = []
    ui_context = None
    ui_error = None
    for check in selected:
        start = time.monotonic()
        row = dict(check=check.name, result="FAIL", counts={}, seconds=0.0, command=check.command,
                   cwd=str(check.cwd), timeout=check.timeout)
        artifact = directory / (check.name + ".json")
        command = check.command
        if check.parser.startswith("tap"):
            command = py("scripts/tap_audit/run.py", "--output", str(artifact))
            if check.parser == "tap-negative":
                command += ["--inject-fault"]
        elif check.parser == "gallery":
            command = [shutil.which("node") or "node", "scripts/gallery_inspect.mjs", "--theme", "both", "--out", str(directory / "gallery")]
            artifact = directory / "gallery/findings.json"
        # Build frontend artifacts outside the protected audio source tree.
        if check.name == "ui-build":
            command = [*command, "--outDir", str(directory / "ui-static")]
        if check.parser.startswith("tap"):
            command += ["--static-dir", str(directory / "ui-static")]
        row["command"] = command
        try:
            if inject == check.name:
                raise ValueError("lỗi cấy chủ động (--inject-failure)")
            if check.manual:
                confirmation = (confirmations or {}).get(check.name)
                row.update(result="CONFIRMED" if confirmation else "MANUAL", detail=check.manual)
                if confirmation:
                    row["confirmation"] = confirmation
            else:
                missing = [name for name in check.requires if not any(r["check"] == name and r["result"] == "PASS" for r in rows)]
                require(not missing, "điều kiện trước chưa PASS: " + ", ".join(missing))
                cwd = check.cwd
                if check.name in UI_CHECKS:
                    if ui_context is None and ui_error is None:
                        try:
                            ui_context = prepare(directory, runner)
                        except Exception as exc:
                            ui_error = str(exc)
                    require(ui_error is None, ui_error or "UI dependency preparation failed")
                    cwd, dependency_evidence = ui_context
                    row.update(cwd=str(cwd), dependencies=dependency_evidence)
                execution = runner(command, cwd, check.timeout)
                row["returncode"] = execution.returncode
                row["timed_out"] = execution.timed_out
                log = directory / (check.name + ".log")
                log.write_text(execution.output, encoding="utf-8")
                row["log"] = str(log)
                # Giữ counts cả khi test đỏ, để không che số lỗi bằng ngoại lệ.
                if not execution.timed_out and check.parser in {"pytest", "vitest"}:
                    row["counts"] = (parse_pytest if check.parser == "pytest" else parse_vitest)(execution.output)
                counts, evidence = validate_report(check, execution, artifact, row)
                row.update(result="PASS", counts=counts)
                if evidence:
                    row["evidence"] = evidence
                if check.name == "dom-count":
                    vitest = next(r for r in rows if r["check"] == "vitest")
                    output = Path(vitest["log"]).read_text(encoding="utf-8")
                    absent = [p for p in evidence["files"] if p.removeprefix("_internal/ui/") not in ANSI.sub("", output).replace("\\", "/")]
                    require(not absent, "Vitest không chứng minh đã chạy DOM: " + ", ".join(absent))
        except Exception as exc:
            row.update(result="FAIL", detail=str(exc))
        row["seconds"] = round(time.monotonic() - start, 3)
        rows.append(row)
        print(f"[{check.name}] {row['result']} ({row['seconds']:.1f}s)", file=sys.stderr, flush=True)
    return rows


def exit_code(rows: list[dict]) -> int:
    return 0 if rows and all(row["result"] in {"PASS", "CONFIRMED"} for row in rows) else 1


def table(rows: list[dict]) -> str:
    lines = ["| check | result | counts | seconds |", "|---|---|---|---:|"]
    for row in rows:
        counts = ", ".join(f"{key}={value}" for key, value in row["counts"].items()) or "—"
        lines.append(f"| {row['check']} | {row['result']} | {counts} | {row['seconds']:.3f} |")
    return "\n".join(lines)


def main(argv: list[str] | None = None, *, runner=run_process, definitions=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", action="append", metavar="NAME", help="lặp cờ hoặc dùng dấu phẩy; gồm cả điều kiện trước")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--inject-failure", metavar="NAME", help="cấy một hàng FAIL để kiểm cổng phát hành")
    parser.add_argument("--worker", help=argparse.SUPPRESS)
    parser.add_argument("--confirm", action="append", default=[], metavar="MANUAL-NAME=NOTE",
                        help="human sign-off for this invocation's exact commit and source bytes; never loaded from earlier reports")
    args = parser.parse_args(argv)
    if args.worker:
        try:
            result = worker(args.worker)
            result.setdefault("status", "PASS")
            print(json.dumps(result, ensure_ascii=False))
            return 0 if result["status"] == "PASS" else 1
        except Exception as exc:
            print(json.dumps({"status": "FAIL", "detail": str(exc)}, ensure_ascii=False))
            return 1
    definitions = checks() if definitions is None else definitions
    if args.list:
        for check in definitions:
            print(f"{check.name:22} {'MANUAL' if check.manual else str(check.timeout) + 's':8} "
                  + (check.manual or subprocess.list2cmdline(check.command) or check.parser)
                  + (f" [requires: {', '.join(check.requires)}]" if check.requires else ""))
        return 0
    only = [name for value in args.only for name in value.split(",")] if args.only else None
    try:
        selected = select_checks(definitions, only)
        require(not args.inject_failure or args.inject_failure in {c.name for c in selected}, "check cấy lỗi không được chọn")
        head = git("rev-parse", "HEAD").strip()
        tree = tree_fingerprint()
        confirmations = parse_confirmations(args.confirm, selected, head, tree)
    except ValueError as exc:
        parser.error(str(exc))
    started = datetime.now(timezone.utc)
    current = version()
    stem = f"{current}-{started.strftime('%Y%m%dT%H%M%S%fZ')}"
    output = ROOT / "runtime/release_gate"
    rows = run_gate(selected, output / stem, runner, args.inject_failure, confirmations)
    final_head = git("rev-parse", "HEAD").strip()
    final_tree = tree_fingerprint()
    if final_head != head or final_tree != tree:
        for row in rows:
            if row["result"] == "CONFIRMED":
                row.update(result="MANUAL", detail="source changed during gate; confirmation invalidated")
    report = dict(version=current, started_at=started.isoformat(), scope="partial" if only else "full", only=only,
                  injected_failure=args.inject_failure, head=head, final_head=final_head,
                  tree_sha256=tree, final_tree_sha256=final_tree, confirmations=confirmations,
                  dirty=bool(git("status", "--porcelain")), rows=rows, exit_code=exit_code(rows))
    report_path = output / (stem + ".json")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(table(rows))
    print(f"Report: {report_path}")
    if only:
        print("PARTIAL: chỉ chứng nhận các check đã chọn, không phải giấy thông hành phát hành.")
    return report["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
