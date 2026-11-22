"""Một lệnh kiểm phát hành, không suy xanh từ mã thoát hay từ kiểm tra bị bỏ sót.

Chạy từ _internal: runtime/.venv/Scripts/python.exe -X utf8 scripts/release_gate.py.
--only chỉ kiểm một phần; MANUAL chặn phát hành cho tới khi có bằng chứng riêng.
"""
from __future__ import annotations

import argparse
import ast
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
import threading
import time
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
RELEASE_BASE: str | None = None
ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
# design-lint chỉ báo cáo cho tới khi dev/design1 gộp (docs/RELEASING.md); Lead đổi thành True để chặn.
DESIGN_LINT_BLOCKS = False
# Từ của chính máy dò không phải mã chuyển đổi; chỉ miễn đúng dòng khai báo này.
FORBIDDEN_TERMS = ("migrat", "legacy", "nâng cấp từ")
# Released 0.4.167 report: 19 skips. Remove two optional audiotsm comparisons;
# pitch and LUFS remain mandatory direct measurements in the same test module.
PYTEST_MAX_SKIPPED = 17
# One Android row (android-unit / android-snapshots) on the owner's laptop, BELOW_NORMAL, nothing else running, compile
# outputs up to date (21-11, loadfix174 --profile): prepareSharedUi 52 s + testDebugUnitTest 332 s + Gradle start ~10 s;
# whole rows measured 389-432 s. Under all-core load at 99.6% (loadfix174 and-load1e/2e) the rows took 710-829 s:
# 1.64-1.92x. The factor 2.5 is that ratio plus about a quarter of headroom.
# The Android rows run at NORMAL priority, not BELOW_NORMAL like every other gate process: under a saturating all-core
# load (cpu_load.py at ~95% of 32 threads) BELOW_NORMAL Gradle got 34 s of CPU in 10 minutes, time-bounded tests failed and
# both rows passed 840 s while still in classes A-D; the same suite at NORMAL under that load passed 3950/0 in 564 s.
# One test JVM fork and one Gradle worker (maxParallelForks = 1) take an equal share of one or two cores, no more.
# The budget is that unloaded time times a stated factor, so it moves with a measurement, never by hand. A row that must also recompile Kotlin under all-core load is not
# covered: BELOW_NORMAL compileDebugKotlin went 52 s -> 1111 s there (the gate yields to the owner's work by design).
ANDROID_ROW_UNLOADED_S = 420
ANDROID_ROW_LOAD_FACTOR = 2.5
ANDROID_ROW_BUDGET_S = round(ANDROID_ROW_UNLOADED_S * ANDROID_ROW_LOAD_FACTOR)
PYTEST_MAX_XFAILED = 0
# Exact generated libmp3lame fixtures: four-second mono test signals, no source audio.
# Pin bytes so the exception cannot silently admit replacement recordings.
IGNORED_TRACKED_APPROVED = {
    "_internal/mobile/android/app/src/test/resources/mp3seek/cbr_info.mp3":
        "bce7766e6933254c2b1ed1edde28283ea146663b504d88cc9dd79d5f2c54f002",
    "_internal/mobile/android/app/src/test/resources/mp3seek/cbr_plain.mp3":
        "ed9f10afe47c000235898d8599f53899999cdd40e79e9b265cd70a86de12b339",
    "_internal/mobile/android/app/src/test/resources/mp3seek/vbr_xing.mp3":
        "1d17de62d2262412376540a3dfc17004a9da87bea17ec2aa9558609482499051",
}
PRIVATE_WORK_LOGS = ("result.md", "PROGRESS.md", "_internal/PROGRESS.md")
# 17-11: laptop rút sạc lúc 17:56, CPU bị hãm, hai bước Gradle chạm deadline 840 s -> hỏng cả lượt gate 5 giờ.
# Mỗi bước chỉ bắt đầu khi cắm sạc; timeout có lúc chạy pin thì chạy lại một lần sau khi có sạc.
POWER_POLL_SECONDS = 30.0
ALLOW_BATTERY_ENV = "ABOOK_GATE_ALLOW_BATTERY"
# Trần một lần chờ sạc liên tục (giây, hay hậu tố s/m/h); quá trần thì các bước còn lại NOT_RUN thay vì treo.
BATTERY_WAIT_MAX_ENV = "ABOOK_GATE_BATTERY_WAIT_MAX"
BATTERY_WAIT_MAX_DEFAULT = 12 * 3600.0
POWER_WAIT_FILE = "power-wait.json"
power_sleep = time.sleep
clock = time.monotonic  # một đồng hồ cho chờ sạc và số giây của bước (bài thử thay bằng đồng hồ giả)


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
    env["ABOOK_REQUIRE_G2P_PARITY"] = "1"
    # Import app luôn từ worktree này, không từ bản editable của runtime dùng chung.
    env["PYTHONPATH"] = str(ROOT)
    env["ABOOK_TEST_PYTHON"] = sys.executable
    env["JAVA_HOME"] = os.environ.get("JAVA_HOME") or "C:/Program Files/Android/Android Studio/jbr"
    env.update(g2p_parity_env())
    return env


def g2p_parity_env() -> dict[str, str]:
    spec = importlib.util.find_spec("sea_g2p")
    dictionary = Path(spec.origin).parent / "sea_g2p.bin" if spec and spec.origin else ROOT / "runtime/missing-sea-g2p.bin"
    library = ROOT / "mobile/sea_g2p_jni/target/release" / ("abook_sea_g2p.dll" if os.name == "nt" else "libabook_sea_g2p.so")
    return {"ABOOK_REQUIRE_G2P_PARITY": "1",
            "ABOOK_SEA_G2P_DICT": str(Path(os.environ.get("ABOOK_SEA_G2P_DICT", str(dictionary))).resolve()),
            "ABOOK_SEA_G2P_LIB": str(Path(os.environ.get("ABOOK_SEA_G2P_LIB", str(library))).resolve())}


def run_process(command: list[str], cwd: Path, timeout: float, extra_env: dict | None = None, *,
                yield_cpu: bool = True) -> Execution:
    # Explicit both ways: a child inherits its parent's class, and the gate worker itself already runs BELOW_NORMAL.
    priority = subprocess.BELOW_NORMAL_PRIORITY_CLASS if yield_cpu else subprocess.NORMAL_PRIORITY_CLASS
    flags = (subprocess.CREATE_NO_WINDOW | priority) if os.name == "nt" else 0
    proc = subprocess.Popen(command, cwd=cwd, env=safe_env() | (extra_env or {}), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
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


def battery_probe() -> bool:
    """True chỉ khi Windows báo đang chạy pin (GetSystemPowerStatus); máy bàn, không biết hay không phải Windows = có sạc."""
    if os.name != "nt":
        return False
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from abook import power_source  # cùng đầu dò ctypes mà supervisor dùng để tạm dừng khi rút sạc

    return power_source.on_battery() is True


def on_battery() -> bool:
    if os.environ.get(ALLOW_BATTERY_ENV) == "1":
        return False
    try:
        return battery_probe()
    except Exception:  # noqa: BLE001 - đầu dò pin hỏng không được chặn gate
        return False


class PowerWaitExpired(Exception):
    """Chờ sạc quá ABOOK_GATE_BATTERY_WAIT_MAX: gate dừng chạy các bước còn lại thay vì treo."""

    def __init__(self, name: str, waited: float, since: str, limit: float):
        super().__init__(f"chờ sạc quá {limit / 3600:g} giờ (máy chạy pin từ {since}, bước {name})")
        self.waited = waited


@dataclass
class PowerRecord:
    """Số giây chờ sạc và các lần chạy của một bước; ghi dần nên còn đúng cả khi runner ném lỗi."""
    attempts: list[dict] = field(default_factory=list)
    waited: float | None = None

    def add_wait(self, seconds: float) -> None:
        self.waited = round((self.waited or 0.0) + seconds, 3)

    def evidence(self) -> list[dict] | None:
        """Ghi vào báo cáo khi có chạy lại hay có lần nào chạy trên pin (kết quả có thể do CPU bị hãm)."""
        if len(self.attempts) > 1 or any(attempt["on_battery"] for attempt in self.attempts):
            return self.attempts
        return None


def battery_wait_max() -> float:
    raw = os.environ.get(BATTERY_WAIT_MAX_ENV, "").strip().lower()
    if not raw:
        return BATTERY_WAIT_MAX_DEFAULT
    scale = {"s": 1, "m": 60, "h": 3600}.get(raw[-1], 1)
    try:
        value = float(raw[:-1] if raw[-1] in "smh" else raw) * scale
        if value >= 0:
            return value
    except ValueError:
        pass
    print(f"{BATTERY_WAIT_MAX_ENV}={raw!r} không hiểu - dùng mặc định {BATTERY_WAIT_MAX_DEFAULT / 3600:g} giờ",
          file=sys.stderr, flush=True)
    return BATTERY_WAIT_MAX_DEFAULT


def write_power_wait(directory: Path, state: dict) -> None:
    """Trạng thái chờ sạc trong thư mục của lượt gate, để người/agent khác thấy gate đang chờ chứ không treo."""
    try:
        directory.mkdir(parents=True, exist_ok=True)
        payload = dict(state, updated_at=datetime.now().astimezone().isoformat(timespec="seconds"))
        (directory / POWER_WAIT_FILE).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                                                encoding="utf-8", newline="\n")
    except OSError as exc:  # không ghi được trạng thái không được làm hỏng gate
        print(f"không ghi được {POWER_WAIT_FILE}: {exc}", file=sys.stderr, flush=True)


def wait_for_mains(name: str, directory: Path) -> float | None:
    """Chờ (không tính vào deadline của bước) tới khi máy cắm sạc; số giây đã chờ, None khi vốn đang có sạc.

    Quá ABOOK_GATE_BATTERY_WAIT_MAX thì ném PowerWaitExpired. Mỗi lần hỏi ghi power-wait.json vào thư mục lượt gate."""
    if not on_battery():
        return None
    limit = battery_wait_max()
    started = clock()
    since = datetime.now().astimezone()
    state = {"state": "waiting", "check": name, "since": since.isoformat(timespec="seconds"),
             "since_local": since.strftime("%H:%M"), "limit_seconds": limit, "waited_seconds": 0.0}
    print(f"[{name}] máy chạy pin - chờ cắm sạc từ {state['since_local']} (hỏi lại mỗi {POWER_POLL_SECONDS:.0f}s,"
          f" bỏ cuộc sau {limit / 3600:g} giờ; trạng thái ở {directory / POWER_WAIT_FILE})", file=sys.stderr, flush=True)
    while True:
        waited = round(clock() - started, 3)
        state["waited_seconds"] = waited
        if waited >= limit:
            write_power_wait(directory, dict(state, state="gave_up"))
            print(f"[{name}] chờ sạc quá {limit / 3600:g} giờ (từ {state['since_local']}) - các bước còn lại không chạy",
                  file=sys.stderr, flush=True)
            raise PowerWaitExpired(name, waited, state["since_local"], limit)
        write_power_wait(directory, state)
        power_sleep(min(POWER_POLL_SECONDS, limit - waited))
        if not on_battery():
            break
    waited = round(clock() - started, 3)
    write_power_wait(directory, dict(state, state="mains", waited_seconds=waited))
    print(f"[{name}] đã có sạc sau {waited:.0f}s - chạy tiếp", file=sys.stderr, flush=True)
    return waited


class BatteryWatch:
    """Ghi lại có lúc nào chạy pin trong khi một bước đang chạy (hỏi lúc đầu, mỗi POWER_POLL_SECONDS và lúc cuối)."""

    def __enter__(self) -> "BatteryWatch":
        self.seen = on_battery()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._poll, daemon=True)
        self._thread.start()
        return self

    def _poll(self) -> None:
        while not self._stop.wait(POWER_POLL_SECONDS):
            self.seen = self.seen or on_battery()

    def __exit__(self, *_) -> None:
        self._stop.set()
        self._thread.join()
        self.seen = self.seen or on_battery()


def execution_timed_out(execution: Execution) -> bool:
    """Timeout của chính bước, hay của tiến trình con mà worker JSON báo (Gradle 840 s trong worker 900 s)."""
    if execution.timed_out:
        return True
    try:
        return worker_json(execution.output).get("timed_out") is True
    except ValueError:
        return False


def worker_json(output: str) -> dict:
    """Đối tượng JSON cuối cùng worker in ra, kể cả khi nó dính vào dòng log cuối không có xuống dòng (Gradle bị giết)."""
    lines = [line for line in output.splitlines() if line.strip()]
    if not lines:
        raise ValueError("worker không in JSON kết quả (output rỗng)")
    last = lines[-1].rstrip()
    decoder = json.JSONDecoder()
    start = last.find("{")
    while start != -1:
        try:
            value, end = decoder.raw_decode(last, start)
        except ValueError:
            value, end = None, -1
        if end == len(last) and isinstance(value, dict):
            return value
        start = last.find("{", start + 1)
    raise ValueError("dòng cuối của worker không kết thúc bằng JSON kết quả: " + last[-200:])


def py(*args: str) -> list[str]:
    return [sys.executable, "-X", "utf8", *args]


def worker_command(name: str) -> list[str]:
    return py(str(Path(__file__).resolve()), "--worker", name, *(["--base", RELEASE_BASE] if RELEASE_BASE else []))


def checks(confirm_hash: str | None = None) -> list[Check]:
    node = shutil.which("node") or "node"
    ui = ROOT / "ui"
    definitions = [
        Check("compile", py("-m", "compileall", "-q", "abook", "tests", "scripts")),
        Check("pytest", py("-m", "pytest", "-o", "addopts=", "-q", "-rfs", "-m", "not browser", "--durations=30"), timeout=7200, parser="pytest"),
        Check("sheet-geometry", py("-m", "pytest", str(ROOT / "scripts/tap_audit/test_sheetgeo.py"),
              "-o", "addopts=", "-q", "-rfs"), timeout=1800, parser="pytest"),
        Check("typecheck", [node, "node_modules/typescript/bin/tsc", "-p", "tsconfig.json"], ui, 180),
        Check("vitest", [node, "node_modules/vitest/vitest.mjs", "run", "--no-cache", "--configLoader", "runner", "--reporter", "verbose",
                         "--maxWorkers", os.environ.get("ABOOK_GATE_VITEST_WORKERS", "2")],
              ui, 1800, "vitest"),
        Check("android-unit", worker_command("android-unit"), timeout=ANDROID_ROW_BUDGET_S + 60, parser="json"),
        Check("android-snapshots", worker_command("android-snapshots"), timeout=ANDROID_ROW_BUDGET_S + 60, parser="json"),
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
              ui, 3600, "gallery", ("gallery-build",)),
        # Chromium thật bấm vào phần đệm / khe của thanh "Đang nghe thử" đè lên danh sách nhạc (soát 18-11): cú bấm phải ở lại trong thanh.
        Check("preview-bar", [node, "scripts/check_preview_bar.mjs", "--dist", "dist/gallery", "--out", "<run>/preview-bar"],
              ui, 600, "preview-bar", ("gallery-build",)),
        # Chromium thật bấm / chạm / bấm phải / lăn ra ngoài mọi lớp nổi (soát 18-11 tapfix5): chỉ lớp trên cùng đóng, phần tử dưới không nhận gì.
        Check("outside-taps", [node, "scripts/check_outside_taps.mjs", "--dist", "dist/gallery", "--out", "<run>/outside-taps.json"],
              ui, 900, "outside-taps", ("gallery-build",)),
        Check("contrast", [node, "scripts/check_contrast.mjs", "--compact"], ui),
        Check("qt-tests", worker_command("qt-tests"), timeout=3000, parser="json"),
        Check("qt-installer", py("desktop_qt/tools/test_installer.py", str(ROOT / "desktop_qt/dist")),
              timeout=1200, requires=("qt-tests",)),
        # Sau android-unit / qt-tests: hai bước ấy vừa ghi lại ảnh và cây UI mà máy đo thiết kế đọc.
        Check("design-lint", worker_command("design-lint"), timeout=600, parser="json"),
    ]
    definitions += [Check(name, worker_command(name), parser="json", timeout=1200 if name == "public-fixtures" else 120) for name in
                    ("quality-hash", "changelog", "versions", "licenses", "diff-safety", "forbidden-terms", "public-fixtures", "public-paths", "ignored-tracked", "batch-crlf",
                     "studio-pins", "android-sdk")]
    definitions += [Check(name, manual=detail) for name, detail in (
        ("manual-ui", "Android thật/máy ảo; duyệt ảnh gallery, README, nguồn truyện trong diff và giấy phép thành phần đóng gói"),
        ("manual-quality", "Lead duyệt hash và tác động tới sách đang chạy; không dừng/resume pha phân tích"),
        ("manual-artifacts", "Bộ cài/APK ký, packaged smoke, audio sink hai lượt + đối chứng, cài/cập nhật/gỡ hồ sơ giả"),
        ("manual-dependencies", "Duyệt dependency audit mỗi phiên bản; cần máy Studio/GPU/Ollama, không chạy ở gate CPU"),
    )]
    if confirm_hash:
        next(check for check in definitions if check.name == "quality-hash").command += ["--confirm-hash", confirm_hash]
    return definitions


def git(*args: str) -> str:
    run = subprocess.run(["git", *args], cwd=REPO, capture_output=True, encoding="utf-8", errors="strict",
                         timeout=30, check=True, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    return run.stdout


def tracked_and_new() -> list[Path]:
    names = git("ls-files", "-z", "--cached", "--others", "--exclude-standard").split("\0")
    return [REPO / name for name in dict.fromkeys(names) if name and (REPO / name).is_file()]


def ignored_tracked() -> dict:
    # A staged removal must not hide a file still published by HEAD.
    require(not git("diff", "--cached", "--name-only", "HEAD"),
            "ignored-tracked: index differs from HEAD; commit before checking")
    ignored = [name for name in git("ls-files", "-ci", "--exclude-standard", "-z").split("\0") if name]
    unexpected = [name for name in ignored if name not in IGNORED_TRACKED_APPROVED]
    require(not unexpected, "ignored-tracked: unapproved paths: " + ", ".join(unexpected))
    for name in ignored:
        blob = subprocess.run(["git", "show", "HEAD:" + name], cwd=REPO, capture_output=True,
                              check=True, timeout=30,
                              creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0).stdout
        require(hashlib.sha256(blob).hexdigest() == IGNORED_TRACKED_APPROVED[name],
                "ignored-tracked: approved fixture bytes changed: " + name)
    comparison = release_range()
    commits = git("rev-list", comparison["base"] + "..HEAD").splitlines()
    additions = []
    for commit in commits:
        # Compare every parent, including merges; disable rename detection so a move
        # into a private path counts as an addition. Inspect deleted files too.
        names = git("diff-tree", "--root", "-m", "-r", "--no-commit-id", "--name-only",
                    "--diff-filter=A", "--no-renames", "-z", commit, "--",
                    *(":(top,literal)" + name for name in PRIVATE_WORK_LOGS)).split("\0")
        additions.extend(commit + ":" + name for name in names if name)
    require(not additions, "ignored-tracked: private work logs added in history: " + ", ".join(additions))
    return {"counts": {"ignored": len(ignored), "approved": len(ignored),
                       "commits": len(commits), "findings": 0}, "range": comparison}


def changed_files() -> list[Path]:
    names = git("diff", release_range()["base"], "--name-only", "-z").split("\0")
    names += git("ls-files", "--others", "--exclude-standard", "-z").split("\0")
    return [REPO / name for name in dict.fromkeys(names) if name and (REPO / name).is_file()]


def release_range() -> dict:
    """At a release tag, compare with its predecessor; otherwise use the latest reachable release."""
    if RELEASE_BASE:
        base = git("rev-parse", "--verify", "--end-of-options", RELEASE_BASE + "^{commit}").strip()
        git("merge-base", "--is-ancestor", base, "HEAD")
        commits = int(git("rev-list", "--count", base + "..HEAD").strip())
        require(commits > 0, "explicit release base must precede HEAD")
        return {"base": base, "commits": commits}
    base = git("describe", "--tags", "--abbrev=0", "--match", "v[0-9]*", "HEAD").strip()
    if git("rev-parse", base + "^{}").strip() == git("rev-parse", "HEAD").strip():
        base = git("describe", "--tags", "--abbrev=0", "--match", "v[0-9]*", "HEAD^").strip()
    require(bool(re.fullmatch(r"v\d+\.\d+\.\d+", base)), "invalid release tag: " + base)
    return {"base": base, "commits": int(git("rev-list", "--count", base + "..HEAD").strip())}


def release_quality_hash(base: str) -> str:
    """Read the protected list and exact blobs from the tag, without checking out or executing old code."""
    from abook.quality_policy import _hashed_bytes

    policy = ast.parse(git("show", base + ":_internal/abook/quality_policy.py"))
    filenames = next(ast.literal_eval(node.value) for node in policy.body if isinstance(node, ast.Assign)
                     and any(isinstance(t, ast.Name) and t.id == "QUALITY_IMPLEMENTATION_FILES" for t in node.targets))
    import posixpath

    digest = hashlib.sha256()
    for filename in filenames:
        relative = posixpath.normpath("_internal/abook/" + filename)
        data = subprocess.run(["git", "show", f"{base}:{relative}"], cwd=REPO, capture_output=True,
                              check=True, timeout=30).stdout
        digest.update(filename.encode("utf-8") + b"\0" + _hashed_bytes(filename, data) + b"\0")
    return digest.hexdigest()


def added_lines(path: Path, base: str | None = None) -> list[str]:
    relative = path.relative_to(REPO).as_posix()
    diff = git("diff", base or release_range()["base"], "--no-ext-diff", "--unified=0", "--", relative)
    return [line[1:] for line in diff.splitlines() if line.startswith("+") and not line.startswith("+++")]


def source_lines(path: Path, base: str | None = None) -> list[str]:
    relative = path.relative_to(REPO).as_posix()
    tracked = git("ls-files", "--", relative).strip()
    return added_lines(path, base) if tracked else path.read_text(encoding="utf-8").splitlines()


def version() -> str:
    import tomllib

    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]


def require(ok: bool, detail: str) -> None:
    if not ok:
        raise ValueError(detail)


def android_host_inputs() -> dict[str, str]:
    inputs = g2p_parity_env()
    for key in ("ABOOK_SEA_G2P_LIB", "ABOOK_SEA_G2P_DICT"):
        path = Path(inputs[key])
        require(path.is_file() and path.stat().st_size > 0, f"Required G2P parity input absent: {key}={path} (host sea_g2p)")
    return inputs


def snapshot_baseline() -> dict[str, str]:
    prefix = "_internal/mobile/android/app/src/test/snapshots/"
    names = [p for p in git("ls-files", "-z", "--", prefix).split("\0") if p.endswith(".png")]
    require(bool(names), "Roborazzi: no tracked golden images")
    return {p.removeprefix(prefix): hashlib.sha256((REPO / p).read_bytes()).hexdigest() for p in names}


def require_reviewed_snapshot(path: Path) -> None:
    """Permit only the exact PNG bytes covered by an explicit visual review."""
    from PIL import Image

    relative = path.relative_to(REPO).as_posix()
    prefix = "_internal/mobile/android/app/src/test/snapshots/"
    require(relative.startswith(prefix) and path.suffix == ".png",
            f"binary trong diff cần duyệt: {relative}")
    registry = REPO / "_internal/scripts/snapshot_reviewed.json"
    require(registry.is_file(), f"snapshot review missing: {relative}")
    entry = json.loads(registry.read_text(encoding="utf-8")).get(relative)
    require(isinstance(entry, dict) and len(entry.get("reason", "")) >= 40
            and entry.get("sha256") == hashlib.sha256(path.read_bytes()).hexdigest(),
            f"snapshot review missing or stale: {relative}")
    with Image.open(path) as image:
        standard_size = 0 < image.width <= 8192 and 0 < image.height <= 8192
        reviewed_scroll = (entry.get("scroll_dimensions") == [image.width, image.height]
                           and 0 < image.width <= 8192 and 8192 < image.height <= 16384
                           and image.width * image.height <= 8192 * 8192)
        require(image.format == "PNG" and not image.info and (standard_size or reviewed_scroll),
                f"snapshot PNG format/metadata invalid: {relative}")
        image.verify()


def require_reviewed_voice_artwork(path: Path) -> None:
    """Accept only the exact reviewed, generated portraits bundled in both clients."""
    from PIL import Image

    relative = path.relative_to(REPO).as_posix()
    roots = ("_internal/abook/assets/voice_avatars/",
             "_internal/mobile/android/app/src/main/assets/voice_avatars/")
    require(any(relative.startswith(root) and re.fullmatch(r"voice-[0-9a-f]{8}\.webp", relative[len(root):])
                for root in roots), f"binary artwork path not permitted: {relative}")
    registry = REPO / "_internal/scripts/voice_artwork_reviewed.json"
    require(registry.is_file(), f"artwork review missing: {relative}")
    entry = json.loads(registry.read_text(encoding="utf-8")).get(relative)
    data = path.read_bytes()
    require(isinstance(entry, dict) and len(entry.get("reason", "")) >= 40
            and entry.get("sha256") == hashlib.sha256(data).hexdigest(),
            f"artwork review missing or stale: {relative}")
    require(12 <= len(data) < 32 * 1024 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"
            and int.from_bytes(data[4:8], "little") + 8 == len(data),
            f"artwork container invalid: {relative}")
    with Image.open(path) as image:
        require(image.format == "WEBP" and image.size == (256, 256) and image.n_frames == 1
                and not (set(image.info) - {"loop", "background"}),
                f"artwork format/metadata invalid: {relative}")
        image.load()


def validate_snapshot_proofs(directory: Path, baseline: dict[str, str]) -> dict:
    rows = [json.loads(p.read_text(encoding="utf-8")) for p in directory.glob("*.json")]
    names = [row["snapshot"] for row in rows]
    require(len(names) == len(set(names)) and set(names) == set(baseline),
            f"Roborazzi: compared={len(names)}, goldens={len(baseline)}; missing or extra image proofs")
    require(all(row.get("status") == "verified" and row.get("golden_sha256") == baseline[row["snapshot"]] for row in rows),
            "Roborazzi: changed images or invalid verification proofs")
    require(snapshot_baseline() == baseline, "Roborazzi modified the tracked goldens")
    return {"goldens": len(baseline), "compared": len(rows), "different": 0}


def require_phoneme_suites_ran(results: Path) -> None:
    required = {"SeaG2pParityTest", "PhonemePolicyTest", "RealNamesTest", "EnglishDirectFrontendTest", "NormalizedOccurrenceTest"}
    seen = set()
    for path in results.glob("**/TEST-*.xml"):
        suite = ET.parse(path).getroot()
        name = suite.attrib.get("name", "").rsplit(".", 1)[-1]
        if name in required:
            cases = suite.findall("testcase")
            require(bool(cases) and not any(c.find("skipped") is not None for c in cases), name + ": missing/skipped phoneme parity")
            seen.add(name)
    require(seen == required, "missing phoneme parity suites: " + ", ".join(sorted(required - seen)))


def worker(name: str, confirm_hash: str | None = None) -> dict:
    """Kiểm thuần nguồn cũng chạy trong subprocess để có deadline như bộ test."""
    if name in {"ui-parity", "ui-parity-qt"}:
        script = "scripts/ui_parity.py" if name == "ui-parity" else "scripts/ui_parity_qt.py"
        execution = run_process(py(script, "--check"), ROOT, 180)
        print(execution.output, end="")
        require(execution.returncode == 0 and not execution.timed_out, name + ": source parity failed")
        return {"status": "PASS", "counts": {"checks": 1},
                "detail": execution.output.strip() or "Shared labels, icons and generated parity report", "timed_out": False}
    if name in {"android-unit", "android-snapshots"}:
        inputs = android_host_inputs()  # Fail before Gradle if the mandatory host frontend is unavailable.
        android = ROOT / "mobile/android"
        baseline = None
        if name == "android-snapshots":
            properties = (android / "gradle.properties").read_text(encoding="utf-8")
            require(not re.search(r"(?m)^\s*roborazzi\.test\.record\s*=\s*true\b", properties, re.I),
                    "Roborazzi recording is forbidden in gradle.properties")
            baseline = snapshot_baseline()
            proof_parent = android / "app/build/release_gate"
            proof_parent.mkdir(parents=True, exist_ok=True)
            proofs = Path(tempfile.mkdtemp(prefix="verified-", dir=proof_parent))
            inputs["ABOOK_SNAPSHOT_PROOFS"] = str(proofs.resolve())
        results = ROOT / "mobile/android/app/build/test-results/testDebugUnitTest"
        # Xoá riêng XML cũ trong worktree, không bao giờ dùng kết quả của lần trước.
        for path in results.glob("**/TEST-*.xml"):
            require(path.resolve().is_relative_to(REPO.resolve()), "XML ra ngoài worktree")
            path.unlink()
        # --rerun forces only the test task: fresh XML every row, while unchanged compile outputs stay up to date
        # (--rerun-tasks recompiled Kotlin in both rows; under load that alone outgrew the budget).
        tasks = [":app:verifyRoborazziDebug"] if baseline is not None else []
        tasks += [":app:testDebugUnitTest", "--rerun"]
        java = Path(inputs.get("JAVA_HOME", os.environ.get("JAVA_HOME", "C:/Program Files/Android/Android Studio/jbr"))) / "bin/java.exe"
        command = [str(java), "-classpath", "gradle/wrapper/gradle-wrapper.jar", "org.gradle.wrapper.GradleWrapperMain",
                   "--no-daemon", "-Dorg.gradle.jvmargs=-Xmx6g -XX:MaxMetaspaceSize=768m", *tasks,
                   "-Proborazzi.test.record=false"]
        # Generate sentence phones from this desktop build outside the checkout;
        # the native contract consumes them in this same verification run.
        from scripts.generate_g2p_parity import occurrence_cases, write

        with tempfile.TemporaryDirectory(prefix="abook-g2p-occurrences-") as scratch:
            fixture = Path(scratch) / "occurrences.json"
            require(not fixture.resolve().is_relative_to(REPO.resolve()), "Sentence phonemes must stay outside the checkout")
            write(fixture, occurrence_cases())
            inputs["ABOOK_G2P_OCCURRENCE_FIXTURE"] = str(fixture)
            execution = run_process(command, android, ANDROID_ROW_BUDGET_S, inputs, yield_cpu=False)
        print(execution.output, end="")
        if execution.timed_out:
            # Báo rõ timeout để gate biết đây là deadline (có thể do chạy pin), không phải test đỏ.
            return {"counts": {}, "status": "FAIL", "timed_out": True, "detail": "Gradle: timeout sau 840s"}
        counts = parse_gradle(results)
        require_phoneme_suites_ran(results)
        if baseline is not None:
            counts.update(validate_snapshot_proofs(proofs, baseline))
        ok = (execution.returncode == 0 and not execution.timed_out and counts["passed"] > 0
              and not counts["failed"] and not counts["error"])
        return {"counts": counts, "status": "PASS" if ok else "FAIL", "timed_out": False,
                "detail": "Gradle: đối chiếu exit và XML"}
    if name == "qt-tests":
        return qt_tests()
    if name == "design-lint":
        return design_lint_report()
    if name == "quality-hash":
        sys.path.insert(0, str(ROOT))
        from abook.quality_policy import QUALITY_IMPLEMENTATION_FILES, quality_implementation_hash

        digest = quality_implementation_hash()
        require(bool(re.fullmatch(r"[0-9a-f]{64}", digest)), "hash không hợp lệ")
        comparison = release_range()
        previous = release_quality_hash(comparison["base"])
        require(digest == previous or confirm_hash == digest,
                f"quality hash changed since {comparison['base']}: {previous} -> {digest}; requires --confirm-hash {digest}")
        locked = {(ROOT / "abook" / item).resolve() for item in QUALITY_IMPLEMENTATION_FILES}
        touched = [path.relative_to(REPO).as_posix() for path in changed_files() if path.resolve() in locked]
        return {"counts": {"files": len(locked), "changed": len(touched)}, "hash": digest, "previous_hash": previous,
                "range": comparison, "confirmed_hash": confirm_hash, "locked_changes": touched,
                "implementation_files": list(QUALITY_IMPLEMENTATION_FILES)}
    if name == "changelog":
        # Trước bump: [Chưa phát hành] phải có gạch đầu dòng. Sau bump (commit phát hành): [<version>] phải có - khi ấy
        # [Chưa phát hành] rỗng là đúng, vì release.py publish lấy ghi chú từ [<version>]. Luật cũ chỉ nhìn [Chưa phát hành]
        # nên đá nhau với publish (07-11: 0.4.163 hỏng đăng hai lần).
        text = (ROOT / "docs/CHANGELOG.md").read_text(encoding="utf-8")

        def entries(heading: str) -> list[str]:
            section = re.search(rf"^## \[{re.escape(heading)}\][^\n]*\n(.*?)(?=^## |\Z)", text, re.S | re.M)
            return re.findall(r"^[-*] \S.+", section.group(1), re.M) if section else []

        unreleased, current = entries("Chưa phát hành"), entries(version())
        require(bool(unreleased or current), f"CHANGELOG [Chưa phát hành] và [{version()}] đều rỗng/thiếu")
        return {"counts": {"entries": len(unreleased or current), "released": int(bool(current) and not unreleased)}}
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
    if name == "public-fixtures":
        from scripts import public_leak_scan as scanner
        result = scanner.audit(REPO)
        return {"status": "FAIL" if result["findings"] or result["stale_reviewed"] else "PASS",
                "counts": {"files": result["files"], "text_files": result["text_files"],
                           "findings": len(result["findings"]), "waived": result["waived"]},
                "detail": result["corpus"], "evidence": result}
    if name == "public-paths":
        from scripts import public_leak_scan as scanner
        files = tracked_and_new()
        require(bool(files), "public-paths: no files checked")
        findings = [p.relative_to(REPO).as_posix() for p in files if scanner.private_file(p)]
        require(not findings, "public-paths: private machine/session paths in " + ", ".join(findings))
        return {"counts": {"files": len(files), "findings": 0}}
    if name == "ignored-tracked":
        return ignored_tracked()
    if name in {"diff-safety", "forbidden-terms"}:
        comparison = release_range()
        files = changed_files()
        require(bool(files) or comparison["commits"] == 0,
                f"{name}: files=0 but range {comparison['base']}..HEAD has {comparison['commits']} commits")
        problems = []
        prose_mentions = []
        terms = re.compile("|".join(FORBIDDEN_TERMS), re.I)
        secret = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{20,})|(?:password|secret|api[_-]?key|token)\s*[:=]\s*[\"'][A-Za-z0-9/+_=.-]{24,}[\"']", re.I)
        for path in files:
            relative = path.relative_to(REPO).as_posix()
            if name == "diff-safety":
                parts = path.relative_to(REPO).parts
                corpus_tool = (len(parts) == 4 and parts[:3] == ("_internal", "scripts", "corpus")
                               and path.suffix == ".py")
                prohibited = (path.suffix.lower() in {".wav", ".mp3", ".m4a", ".m4b", ".flac", ".ogg", ".aac", ".opus", ".wma", ".aiff", ".pcm", ".keystore", ".jks", ".p12", ".pfx", ".key"}
                              or path.name.lower() in {"listening.json", "devices.json", "computers.json", "reviews.json", "preferences.json", "local.properties"}
                              or (not corpus_tool and any(p.lower() in {"corpus", "text", "text_tmp"} for p in parts)))
                require(not prohibited, f"file riêng tư/audio/khoá trong diff: {relative}")
                data = path.read_bytes()
                if b"\0" in data:
                    if path.suffix == ".webp":
                        require_reviewed_voice_artwork(path)
                    else:
                        require_reviewed_snapshot(path)
                    continue
                lines = source_lines(path, comparison["base"])
                if any(secret.search(line) for line in lines):
                    problems.append(relative)  # Chỉ ghi đường dẫn, tuyệt đối không in giá trị khoá.
            elif path.suffix.lower() in {".py", ".ts", ".tsx", ".kt", ".cpp", ".h", ".qml", ".js", ".mjs", ".ps1", ".bat", ".cmd"}:
                lines = source_lines(path, comparison["base"])
                if path.resolve() == Path(__file__).resolve():
                    declaration = "FORBIDDEN_TERMS = " + repr(FORBIDDEN_TERMS).replace("'", '"')
                    lines = [line for line in lines if line != declaration]
                if any(terms.search(line) for line in lines):
                    problems.append(relative)
            elif name == "forbidden-terms" and path.suffix.lower() in {".md", ".txt", ".json", ".toml"}:
                if any(terms.search(line) for line in source_lines(path, comparison["base"])):
                    prose_mentions.append(relative)
        require(not problems, f"{name}: cần duyệt " + ", ".join(problems))
        return {"counts": {"files": len(files), "findings": 0, "prose_mentions": len(prose_mentions)},
                "range": comparison, "explicitly_empty_range": not files and comparison["commits"] == 0,
                "prose_mentions_for_manual_review": prose_mentions}
    if name in {"studio-pins", "android-sdk"}:
        module = load_module(ROOT / "scripts/release.py", "gate_release")
        functions = [module.check_android_sdk] if name == "android-sdk" else [
            module.check_studio_assets_pinned, module.check_word_align_pinned, module.check_speaker_model_pinned]
        for function in functions:
            function()
        return {"counts": {"checks": len(functions)}}
    raise ValueError(f"không có worker {name}")


def design_lint_report() -> dict:
    """Máy đo thiết kế trên ảnh đã vẽ (scripts/design_lint.py, docs/DESIGN.md §8).

    Chế độ BÁO CÁO: số ảnh đỏ theo từng luật vào bảng gate, không chặn phát hành. Lead bật DESIGN_LINT_BLOCKS
    sau khi dev/design1 gộp; khi ấy còn ô đỏ hay ngoại lệ thừa là FAIL. Lỗi đo hay không có ảnh luôn FAIL.
    """
    sys.path.insert(0, str(ROOT / "scripts"))
    import design_lint

    fresh_android = ROOT / "mobile/android/app/build/design_lint"
    android = fresh_android if any(fresh_android.glob("*.png")) else design_lint.ANDROID_SHOTS
    web_dir = os.environ.get("ABOOK_DESIGN_LINT_WEB")
    shots = design_lint.collect(android, design_lint.QT_SHOTS, Path(web_dir) if web_dir else None)
    require(bool(shots), "design-lint: không có ảnh Android/Qt để đo")
    report = design_lint.run(shots, design_lint.load_groups(), design_lint.load_exceptions())
    red = len({f["image"] for f in report["findings"]})   # ảnh khác nhau có ít nhất một luật đỏ
    cells = sum(report["red_images"].values())             # cặp ảnh x luật
    problems = list(report["errors"])
    missing = sum(v["images"] - v["sidecars"] for v in report["tree_coverage"].values())
    if DESIGN_LINT_BLOCKS and (missing or not all(report["platforms"][p] for p in ("android", "qt", "web"))):
        problems.append(f"thiếu cây UI {missing} ảnh hoặc thiếu nền tảng Android/Qt/web")
    if DESIGN_LINT_BLOCKS and (red or report["stale_exceptions"]):
        problems.append(f"{red} ảnh đỏ, {len(report['stale_exceptions'])} ngoại lệ thừa")
    counts = {"images": report["images"], "trees": report["trees"], "red": red, "red_cells": cells,
              "waived": report["waived"]}
    counts["unmeasured_trees"] = missing
    counts.update({rule.lower(): number for rule, number in report["red_images"].items()})
    return {"counts": counts, "status": "FAIL" if problems else "PASS", "mode": "block" if DESIGN_LINT_BLOCKS else "report",
            "seconds": report["seconds"], "platforms": report["platforms"], "findings": report["findings"],
            "tree_coverage": report["tree_coverage"],
            "stale_exceptions": report["stale_exceptions"], "errors": report["errors"],
            "detail": "design-lint: " + ("; ".join(problems) if problems else
                                         f"{red} ảnh đỏ, {cells} ô ảnh x luật (chế độ {'chặn' if DESIGN_LINT_BLOCKS else 'báo cáo'})")}


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


QT_TEST_CALL = re.compile(r'^call :test "%HERE%build\\([^"\n]+\.exe)" "%HERE%build\\([^"\n]+\.txt)"([^\n]*)$', re.M)


def qt_suite_calls(build_text: str, qt: Path) -> list[tuple[str, str, list[str]]]:
    """Mỗi dòng `call :test` của build.bat: (exe, tên log, tham số thêm). Một binary có thể chạy nhiều lần với input khác
    (WidthTests trên tests\\bookmeta), mỗi lần một log riêng; %HERE% là thư mục desktop_qt như trong build.bat."""
    calls = []
    for exe, log, rest in QT_TEST_CALL.findall(build_text):
        arguments = [quoted or bare for quoted, bare in re.findall(r'"([^"]*)"|(\S+)', rest)]
        calls.append((exe, log, [argument.replace("%HERE%", str(qt) + os.sep) for argument in arguments]))
    return calls


def run_qt_suite(executable: Path, cwd: Path, log: Path, runner=run_process, *, arguments: list[str] | None = None) -> Execution:
    """Qt GUI không có stdout: yêu cầu file mới như build.bat, rồi đọc byte thực đã ghi."""
    require(not log.exists(), "Qt: từ chối dùng log cũ " + log.name)
    timeout = 1800 if executable.stem == "WidthTests" else 360
    result = runner([str(executable), "-o", str(log) + ",txt", *(arguments or [])], cwd, timeout)
    require(log.is_file(), "Qt: không tạo log " + log.name)
    output = log.read_text(encoding="utf-8", errors="replace")
    if result.output:
        output += "\n" + result.output
        log.write_text(output, encoding="utf-8")
    return Execution(result.returncode, output, result.timed_out)


def find_vcvars() -> Path:
    """vcvars64.bat of the newest Visual Studio / Build Tools with x64 C++ tools (no hard-coded edition)."""
    if os.environ.get("VCVARS"):
        return Path(os.environ["VCVARS"])
    vswhere = Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")) / "Microsoft Visual Studio/Installer/vswhere.exe"
    if not vswhere.is_file():
        return vswhere  # require() reports it missing
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    found = subprocess.run([str(vswhere), "-latest", "-products", "*", "-requires",
                            "Microsoft.VisualStudio.Component.VC.Tools.x86.x64", "-property", "installationPath"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           creationflags=flags).stdout.strip().splitlines()
    return Path(found[0]) / "VC/Auxiliary/Build/vcvars64.bat" if found else vswhere.parent / "(no x64 C++ tools)/vcvars64.bat"


def qt_tests() -> dict:
    qt = ROOT / "desktop_qt"
    build_text = (qt / "build.bat").read_text(encoding="ascii")
    calls = qt_suite_calls(build_text, qt)
    require(bool(calls) and len(calls) == len(re.findall(r"^call :test ", build_text, re.M)),
            "Qt: không đọc được mọi dòng call :test trong build.bat")
    targets = list(dict.fromkeys(exe for exe, _, _ in calls))
    sdk = load_module(qt / "tools/qt_sdk.py", "gate_qt_sdk")
    qt_root = sdk.validate_qt_root()
    qwk_install = sdk.qwk_install_root()
    cmake_bin = Path(os.environ.get("CMAKE_BIN", "D:/Novels/native_desk_proto/qt/Tools/CMake_64/bin"))
    ninja_bin = Path(os.environ.get("NINJA_BIN", "D:/Novels/native_desk_proto/qt/Tools/Ninja"))
    vcvars = find_vcvars()
    require((qwk_install / "lib/cmake/QWindowKit/QWindowKitConfig.cmake").is_file(), "Qt: cần QWindowKit đã dựng (không tự ghi worktree khác)")
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
    build_jobs = max(1, min(4, int(os.environ.get("CMAKE_BUILD_PARALLEL_LEVEL", "4"))))
    commands = ["@echo off", f'call "{vcvars}" >nul', "if errorlevel 1 exit /b 1",
                f'set "PATH={qt_root / "bin"};{cmake_bin};{ninja_bin};%PATH%"',
                f'"{sys.executable}" -X utf8 "{qt / "tools/drop_stale_cmake_cache.py"}" "{build}" --qt-root "{qt_root}" --qwk-install "{qwk_install}"',
                "if errorlevel 1 exit /b 1",
                f'cmake -S "{qt}" -B "{build}" -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH="{qt_root};{qwk_install}" -DCMAKE_MAKE_PROGRAM="{ninja_bin / "ninja.exe"}"',
                "if errorlevel 1 exit /b 1", 'cmake --build "' + str(build) + '" --parallel ' + str(build_jobs) + ' --target ABookDesk_qmltyperegistration ' + " ".join(Path(t.replace("\\", "/")).stem for t in targets),
                "exit /b %errorlevel%"]
    command_file.write_bytes(("\r\n".join(commands) + "\r\n").encode("utf-8"))
    built = run_process([str(command_file)], qt, 800)
    print(built.output)
    if built.timed_out:
        return {"counts": {}, "status": "FAIL", "timed_out": True, "detail": "Qt: configure/build timeout"}
    require(built.returncode == 0 and not built.timed_out, "Qt: configure/build lỗi hoặc timeout")
    validator = load_module(qt / "tools/check_test_results.py", "gate_qt_results")
    counts = {"passed": 0, "failed": 0, "skipped": 0, "suites": 0, "timeouts": 0, "missing_summaries": 0, "lint_failed": 0,
              "member_data_errors": 0}
    failures = []
    for arguments in (("selftest", str(build)), (str(build),)):
        lint = run_process(py(str(qt / "tools/check_qml_members.py"), *arguments), qt, 120)
        print(lint.output)
        if lint.returncode != 0 or lint.timed_out:
            failures.append("qml_members " + arguments[0])
            counts["lint_failed"] += 1
    for target, log_name, arguments in calls:
        executable = build / target.replace("\\", "/")
        log = command_file.parent / log_name
        # DLL Qt lấy từ bộ SDK chỉ đọc, không chép gì vào SDK.
        previous = os.environ.get("PATH", "")
        os.environ["PATH"] = str(qt_root / "bin") + os.pathsep + previous
        try:
            result = run_qt_suite(executable, qt, log, arguments=arguments)
        except Exception as exc:
            failures.append(executable.stem + ": " + str(exc))
            counts["suites"] += 1
            continue
        finally:
            os.environ["PATH"] = previous
        totals = re.findall(r"Totals: (\d+) passed, (\d+) failed, (\d+) skipped", result.output)
        counts["timeouts"] += int(result.timed_out)
        counts["missing_summaries"] += int(not totals)
        counts["member_data_errors"] += result.output.count("Cannot find member data")
        # Qt tính cả initTestCase/cleanupTestCase là passed; hai mục ấy chưa chứng minh có bài thử.
        if not (result.returncode == 0 and not result.timed_out and validator.check(log) and totals
                and all(int(t[0]) > 2 for t in totals)):
            failures.append(executable.stem + (": timeout (see per-suite deadline)" if result.timed_out else ": log/Totals/validation lỗi"))
        for row in totals:
            for key, number in zip(("passed", "failed", "skipped"), row):
                counts[key] += int(number)
        counts["suites"] += 1
    require(counts["suites"] == len(calls), "Qt: thiếu suite")
    return {"counts": counts, "status": "FAIL" if failures else "PASS", "failed_suites": failures, "logs": str(command_file.parent),
            "timed_out": bool(counts["timeouts"]),
            "detail": "Qt: " + (", ".join(failures) if failures else "đủ suite, totals và QML lint")}


# Lớp nổi mà cổng phải thử thật (check_outside_taps.mjs): menu modal=false, menu modal, Popover, Popover trong hộp thoại - chuột, chạm, chuột phải.
OUTSIDE_TAPS_REQUIRED = {"library-sort-menu", "library-sort-menu-touch", "library-sort-menu-right", "book-action-menu-touch", "player-speed-popover",
                         "player-speed-popover-right", "remote-sleep-in-dialog", "remote-sleep-in-dialog-touch", "remote-sleep-in-dialog-right"}


def validate_tap_negative(scenario: dict) -> None:
    """A negative control must isolate its fault from setup, app and cleanup errors."""
    require(scenario.get("status") == "FAIL" and scenario.get("injected") is True
            and not scenario.get("error"), "tap-negative: injection failed or unrelated scenario error")
    control = scenario.get("negativeControl", {})

    def reachable(element: dict) -> bool:
        return (element.get("hit") is True and element.get("disabled") is False
                and element.get("blockedInLayer") == [] and element.get("pointerEvents") == "auto")

    for phase in ("baseline", "restored"):
        data = control.get(phase, {})
        elements = data.get("elements", [])
        require(data.get("healthy") is True and bool(elements)
                and any(reachable(e) for e in elements)
                and all(e.get("disabled") is True or reachable(e) for e in elements),
                "tap-negative: missing/unhealthy " + phase)
    probes = control.get("baseline", {}).get("probes", {})
    detected = control.get("detected", {})
    require(set(probes) == set(detected) == {"mouse", "touch"}, "tap-negative: missing mouse/touch samples")
    for mode in ("mouse", "touch"):
        before, broken = probes[mode], detected[mode]
        require(reachable(before), "tap-negative: unhealthy baseline probe " + mode)
        require(broken.get("hit") is False and broken.get("disabled") is False
                and broken.get("pointerEvents") == "none" and bool(broken.get("blockedInLayer"))
                and bool(broken.get("noneAncestors")), "tap-negative: fault not detected by " + mode)
        require(broken.get("label") == before.get("label") and broken.get("tag") == before.get("tag"),
                "tap-negative: probe target changed during injection")
    expected = {mode + " probe center reaches control" for mode in ("mouse", "touch")}
    checks = scenario.get("checks", [])
    failures = [c for c in checks if c.get("pass_") is False]
    require(len(failures) == 2 and {c.get("name") for c in failures} == expected
            and all(c.get("pass_") is True or c in failures for c in checks),
            "tap-negative: unexpected failures beyond the injected pointer fault")
    required = {"negative baseline healthy before injection", "fault injection applied",
                "negative original pointer state restored healthy",
                "visible layer controls receive pointer events throughout opening"}
    require(required <= {c.get("name") for c in checks if c.get("pass_") is True},
            "tap-negative: missing baseline, opening or restoration checks")


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
        evidence = worker_json(execution.output)
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
            for scenario in rows:
                validate_tap_negative(scenario)
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
    elif kind == "preview-bar":
        results = json.loads(artifact.read_text(encoding="utf-8"))
        cases = {(r["width"], r["theme"]) for r in results}
        counts = {"cases": len(results), "points": sum(len(r["points"]) for r in results)}
        if row is not None:
            row.update(counts=counts, evidence=results)
        require(cases == {(w, t) for w in (1280, 420) for t in ("light", "dark")} and all(len(r["points"]) >= 4 for r in results),
                "preview-bar: thiếu khổ / chủ đề hay điểm đệm")
    elif kind == "outside-taps":
        evidence = json.loads(artifact.read_text(encoding="utf-8"))
        results = evidence["results"]
        ids = [r["id"] for r in results]
        failed = [r["id"] for r in results if r.get("error") or not (r.get("outside") or {}).get("pass") or (r.get("inside") and not r["inside"].get("pass"))]
        counts = {"passed": len(results) - len(failed), "failed": len(failed), "scenarios": len(results)}
        if row is not None:
            row.update(counts=counts, evidence=evidence)
        require(ids == evidence.get("scenarios") and len(set(ids)) == len(ids), "outside-taps: thiếu / trùng kịch bản")
        require({r.get("outside", {}).get("press") for r in results} >= {"touch", "right", "wheel"}, "outside-taps: thiếu chạm / chuột phải / lăn")
        require(OUTSIDE_TAPS_REQUIRED <= set(ids), "outside-taps: thiếu kịch bản bắt buộc " + ", ".join(sorted(OUTSIDE_TAPS_REQUIRED - set(ids))))
        require(not failed, "outside-taps: lọt ở " + ", ".join(failed))
    if kind in {"pytest", "vitest"}:
        require(counts.get("passed", 0) > 0 and not any(counts.get(k, 0) for k in ("failed", "error", "xpassed")),
                "summary có test lỗi hoặc không có test passed: " + json.dumps(counts))
    if kind == "pytest":
        require(counts["skipped"] <= PYTEST_MAX_SKIPPED,
                f"pytest skipped={counts['skipped']} exceeds ceiling {PYTEST_MAX_SKIPPED}")
        require(counts["xfailed"] <= PYTEST_MAX_XFAILED, "pytest: unexpected xfailed tests")
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


UI_CHECKS = {"typecheck", "vitest", "ui-build", "gallery-build", "gallery-inspect", "preview-bar", "outside-taps", "contrast", "sheet-geometry"}


def directory_link(link: Path, target: Path) -> None:
    """Only create new links inside the private gate workspace."""
    require(not link.exists(), "private link already exists: " + str(link))
    if os.name == "nt":
        quote = lambda value: "'" + str(value).replace("'", "''") + "'"
        command = f"New-Item -ItemType Junction -Path {quote(link)} -Target {quote(target)} -ErrorAction Stop | Out-Null"
        result = run_process(["powershell", "-NoProfile", "-NonInteractive", "-Command", command], link.parent, 30)
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
    # scripts/: ui/scripts/tap_readiness.test.mjs runs the tap harness's own browser predicates.
    for name in ("abook", "docs", "tests", "mobile", "desktop_qt", "ui_strings", "ui_design", "scripts"):
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


def run_on_mains(name: str, run, directory: Path, record: PowerRecord) -> Execution:
    """Chạy một bước khi có sạc; timeout mà có lúc chạy pin thì chạy lại đúng một lần sau khi có sạc lại.

    Số giây chờ và các lần chạy ghi thẳng vào `record` trước khi gọi run(), nên vẫn đúng khi run() ném lỗi
    hay khi chờ sạc quá trần (PowerWaitExpired)."""
    while True:
        try:
            pause = wait_for_mains(name, directory)
        except PowerWaitExpired as exc:
            record.add_wait(exc.waited)
            raise
        if pause is not None:
            record.add_wait(pause)
        started = clock()
        with BatteryWatch() as watch:
            execution = run()
        attempt = {"attempt": len(record.attempts) + 1, "returncode": execution.returncode,
                   "timed_out": execution_timed_out(execution), "on_battery": watch.seen,
                   "seconds": round(clock() - started, 3)}
        record.attempts.append(attempt)
        if len(record.attempts) == 2 or not (attempt["timed_out"] and watch.seen):
            return execution
        log = directory / f"{name}.attempt1.log"
        log.write_text(execution.output, encoding="utf-8")
        attempt["log"] = str(log)
        print(f"[{name}] timeout trong lúc có chạy pin - chạy lại một lần khi có sạc", file=sys.stderr, flush=True)


def mains_runner(runner, name: str, directory: Path, record: PowerRecord):
    """Runner bọc run_on_mains, cho các lệnh chạy ngoài một bước (npm ci của prepare_ui)."""
    def run(command, cwd, timeout, *args):
        return run_on_mains(name, lambda: runner(command, cwd, timeout, *args), directory, record)
    return run


def run_gate(selected: list[Check], directory: Path, runner=run_process, inject: str | None = None,
             confirmations: dict | None = None, prepare=prepare_ui) -> list[dict]:
    directory.mkdir(parents=True, exist_ok=True)
    rows = []
    ui_context = None
    ui_error = None
    gave_up = None  # lý do bỏ các bước còn lại khi chờ sạc quá trần
    for check in selected:
        start = clock()
        power, ui_power = PowerRecord(), PowerRecord()
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
        elif check.parser == "preview-bar":
            command = [*check.command[:-1], str(directory / "preview-bar")]
            artifact = directory / "preview-bar/preview-bar-checks.json"
        elif check.parser == "outside-taps":
            artifact = directory / "outside-taps.json"
            command = [*check.command[:-1], str(artifact)]
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
            elif gave_up is not None:
                row.update(result="NOT_RUN", detail="không chạy: " + gave_up)
            else:
                missing = [name for name in check.requires if not any(r["check"] == name and r["result"] == "PASS" for r in rows)]
                require(not missing, "điều kiện trước chưa PASS: " + ", ".join(missing))
                cwd = check.cwd
                if check.name in UI_CHECKS:
                    if ui_context is None and ui_error is None:
                        try:
                            ui_context = prepare(directory, mains_runner(runner, "ui-dependencies", directory, ui_power))
                        except PowerWaitExpired:
                            raise
                        except Exception as exc:
                            ui_error = str(exc)
                    require(ui_error is None, ui_error or "UI dependency preparation failed")
                    cwd, dependency_evidence = ui_context
                    row.update(cwd=str(cwd), dependencies=dependency_evidence)
                    if check.name == "sheet-geometry":
                        # The wrapper builds its gallery only in the private, lock-matched UI mirror.
                        command = py("-c", "import os,pytest; os.environ['ABOOK_SHEETGEO_ROOT']="
                                     + repr(str(cwd.parent.parent)) + "; raise SystemExit(pytest.main("
                                     + repr(check.command[5:]) + "))")
                        row["command"] = command
                execution = run_on_mains(check.name, lambda: runner(command, cwd, check.timeout), directory, power)
                row["returncode"] = execution.returncode
                row["timed_out"] = execution_timed_out(execution)
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
        except PowerWaitExpired as exc:
            gave_up = str(exc)
            if power.attempts:  # lần 1 đã timeout trên pin; lần chạy lại bị bỏ
                row.update(result="FAIL", detail="timeout trong lúc chạy pin; không chạy lại vì " + gave_up)
            else:
                row.update(result="NOT_RUN", detail="không chạy: " + gave_up)
        except Exception as exc:
            row.update(result="FAIL", detail=str(exc))
        waited = (power.waited or 0.0) + (ui_power.waited or 0.0)
        if power.waited is not None or ui_power.waited is not None:
            row["power_wait_seconds"] = round(waited, 3)
        for key, record in (("power_attempts", power), ("ui_dependencies_power_attempts", ui_power)):
            attempts = record.evidence()
            if attempts:
                if not isinstance(row.get("evidence"), dict):
                    row["evidence"] = {}
                row["evidence"][key] = attempts
        row["seconds"] = round(max(0.0, clock() - start - waited), 3)
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
    global RELEASE_BASE
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", action="append", metavar="NAME", help="lặp cờ hoặc dùng dấu phẩy; gồm cả điều kiện trước")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--inject-failure", metavar="NAME", help="cấy một hàng FAIL để kiểm cổng phát hành")
    parser.add_argument("--worker", help=argparse.SUPPRESS)
    parser.add_argument("--base", help="explicit ancestor commit for source comparison after history rewriting")
    parser.add_argument("--confirm-hash", help="explicit approval of this exact quality implementation hash")
    parser.add_argument("--confirm", action="append", default=[], metavar="MANUAL-NAME=NOTE",
                        help="human sign-off for this invocation's exact commit and source bytes; never loaded from earlier reports")
    args = parser.parse_args(argv)
    RELEASE_BASE = args.base
    if args.worker:
        try:
            result = worker(args.worker, args.confirm_hash)
            result.setdefault("status", "PASS")
            # Xuống dòng trước JSON: log Gradle/Qt bị giết giữa chừng có thể không kết thúc bằng "\n".
            print("\n" + json.dumps(result, ensure_ascii=False))
            return 0 if result["status"] == "PASS" else 1
        except Exception as exc:
            print("\n" + json.dumps({"status": "FAIL", "detail": str(exc)}, ensure_ascii=False))
            return 1
    definitions = checks(args.confirm_hash) if definitions is None else definitions
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
                  injected_failure=args.inject_failure, head=head, final_head=final_head, release_base=RELEASE_BASE,
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
