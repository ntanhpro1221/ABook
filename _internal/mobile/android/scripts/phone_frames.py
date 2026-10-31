"""Thời gian khung của app native trên máy thật, theo ngân sách §1 của docs/NATIVE_PHONE_UI.md (chu kỳ hiển thị P suy ra từ tần số quét của máy).

    python phone_frames.py --package com.ngdtuanh.abook.dev2 --serial <adb serial> [--scenarios openclose,push] [--iters N] [--out DIR]
                           [--keep-traces] [--compose-trace] [--display N | --virtual-display [--vd-size 1080x2400/420]]

AN TOÀN (máy của người khác, màn hình đang có người dùng): script chạm vào màn hình bằng toạ độ nên TRƯỚC MỖI thao tác (tap / vuốt / Back) nó đọc
`dumpsys activity activities` + `dumpsys window displays` và đòi: activity của gói đang đo là activity trên cùng đang chạy (resumed) CỦA MÀN HÌNH ĐANG ĐO, trong
cửa sổ toàn màn hình (không freeform / pinned / PiP) và đang giữ tiêu điểm. Sai một điều là dừng ngay, KHÔNG gửi thao tác ấy, force-stop gói đo, thoát mã 3.
Không có lần thử lại nào chạm vào màn hình. Phím đánh thức chỉ gửi khi màn hình đang tắt, vuốt mở khoá chỉ khi khoá màn hình đang hiện (lúc đó không app nào nhận).
`--display N`: mọi thao tác đi tới màn hình N (`input -d N`) và app được mở trên đó (`am start --display N`). `--virtual-display`: tự mở một màn hình ảo bằng
scrcpy (cửa sổ đặt ngoài vùng nhìn thấy), đo trên đó, rồi tắt đúng tiến trình scrcpy đã mở (theo PID) - màn hình thật không bị chạm.

Vì sao không chạy Macrobenchmark: trên ColorOS (OPPO CPH2121) UiAutomator trong tiến trình đo không thấy cửa sổ của app và phiên perfetto của Macrobenchmark
không ghi lát cắt nào của app, nên `FrameTimingMetric` ra rỗng. Ở đây: cùng kịch bản và cùng toạ độ với `:benchmark` (đọc thẳng từ Taps.kt, không chép
lại), một vệt perfetto cho mỗi lần lặp, và số đo cùng định nghĩa với `frameDurationCpuMs` - từ đầu `Choreographer#doFrame N` (luồng giao diện) tới cuối
`DrawFrame N` (RenderThread); frameOverrun = kết thúc thật - kết thúc dự kiến của khung trong frame timeline.

Ngân sách theo chu kỳ P = 1000 / tần số quét (60 Hz -> 16,7 ms; 120 Hz -> 8,3 ms):
    p95 <= 0,75 P, p99 <= P, số khung > P không quá 1 % của kịch bản, và mỗi khung "dựng" một lần (mở một màn lần đầu, mở nguội) <= 2 P.
Mỗi kịch bản khai số khung dựng mỗi lần lặp (BUILDS): chừng ấy khung nặng nhất của mỗi lần lặp được xét riêng với mức 2 P, phần còn lại với ba mức trên.

Cần: adb, `pip install perfetto`, máy đã cài bản benchmarkRelease (cài kèm app.dm để có baseline profile). Không bao giờ bấm HOME giữa kịch bản
(trình phát đang phát sẽ vào PiP, lần mở sau vào thẳng Đang nghe): mỗi lần lặp khởi động lại Activity bằng `am start -f NEW_TASK|CLEAR_TASK`.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time

SCRCPY = os.environ.get("SCRCPY", "scrcpy")

HERE = os.path.dirname(os.path.abspath(__file__))
TAPS = os.path.join(HERE, "..", "benchmark", "src", "main", "java", "vn", "abook", "benchmark", "Taps.kt")
ACTIVITY = "vn.abook.player.ui.NativeActivity"


def load_spots():
    """Toạ độ theo tỉ lệ màn hình, đọc từ `Spot` trong Taps.kt: một nguồn cho cả bài Macrobenchmark lẫn script này."""
    text = open(TAPS, encoding="utf-8").read()
    spots = {m.group(1): (float(m.group(2)), float(m.group(3))) for m in re.finditer(r"val (\w+) = ([\d.]+)f to ([\d.]+)f", text)}
    consts = {m.group(1): float(m.group(2)) for m in re.finditer(r"const val (\w+) = ([\d.]+)f", text)}
    return spots, consts


class Unsafe(Exception):
    """Cửa sổ của app đo không còn là cửa sổ trên cùng, toàn màn hình, có tiêu điểm của màn hình đang đo: không gửi thêm thao tác nào."""


ACTIVITY_DISPLAY = r"^Display #(\d+) "
WINDOW_DISPLAY = r"^\s*Display: mDisplayId=(\d+)"


def section(text, header, display):
    """Đoạn của một màn hình trong bản dumpsys nhiều màn hình: các đoạn mở đầu bằng `header` (nhóm 1 = số hiệu màn hình); None nếu không có."""
    heads = list(re.finditer(header, text, re.M))
    for i, m in enumerate(heads):
        if int(m.group(1)) == display:
            return text[m.end(): heads[i + 1].start() if i + 1 < len(heads) else len(text)]
    return None


def verdict(package, display, activities, windows):
    """None nếu mọi thứ đúng, không thì một câu nói điều sai. Hàm thuần (kiểm thử được bằng ảnh chụp dumpsys)."""
    acts, wins = section(activities, ACTIVITY_DISPLAY, display), section(windows, WINDOW_DISPLAY, display)
    if acts is None or wins is None:
        return f"không thấy màn hình {display}"
    # Android 14+ (máy ảo API 36): `topResumedActivity=`; Android 12 (OPPO ColorOS): `mResumedActivity: ` - cả hai nằm trong đoạn `Display #N` của màn hình đó.
    top = re.search(r"(?:topResumedActivity=|mResumedActivity: )ActivityRecord\{\S+ u\d+ ([\w.$]+)/", acts)
    if not top or top.group(1) != package:
        return f"trên màn hình {display} activity trên cùng đang chạy là {top.group(1) if top else 'không có'}, không phải {package}"
    task = re.search(r"\* Task\{[^\n]*", acts)
    if not task or f":{package} " not in task.group(0):
        return f"tác vụ trên cùng của màn hình {display} không phải của {package}"
    mode = re.search(r"\bmode=([\w-]+)", task.group(0))
    if not mode or mode.group(1) != "fullscreen":
        return f"cửa sổ của {package} không toàn màn hình (mode={mode.group(1) if mode else '?'})"
    if "visible=true" not in task.group(0):
        return f"cửa sổ của {package} không hiện"
    focus = re.search(r"mCurrentFocus=Window\{\S+ u\d+ ([\w.$]+)/", wins)
    if not focus or focus.group(1) != package:
        return f"tiêu điểm của màn hình {display} đang ở {focus.group(1) if focus else 'không ai'}, không phải {package}"
    return None


def display_hz(dump, display):
    """Tần số quét của chính màn hình `display` theo `dumpsys display` (`mBaseDisplayInfo=DisplayInfo{..., displayId N, ..., renderFrameRate 60.0` ở Android 13+;
    `fps=` của chế độ đang dùng ở bản cũ hơn); None nếu không đọc được. Màn hình ảo có tần số riêng, không phải của màn hình thật."""
    for line in dump.splitlines():
        if "mBaseDisplayInfo=DisplayInfo{" in line and re.search(rf"displayId {display}\b", line):
            m = re.search(r"renderFrameRate ([\d.]+)", line) or re.search(r"\bfps=([\d.]+)", line)
            if m:
                return float(m.group(1))
    return None


class Phone:
    def __init__(self, adb, serial, package, display=0, size=None):
        self.adb_path, self.serial, self.package, self.display = adb, serial, package, display
        self.env = dict(os.environ, MSYS_NO_PATHCONV="1")
        self.sent = 0  # số thao tác đã gửi tới màn hình (bằng chứng "không gửi gì thêm" khi dừng)
        if size:
            self.w, self.h = size
        else:
            found = re.search(r"(\d+)x(\d+)", self.shell("wm size" + (f" -d {display}" if display else "")).splitlines()[0])
            self.w, self.h = int(found.group(1)), int(found.group(2))

    def run(self, *args, **kw):
        return subprocess.run([self.adb_path, "-P", os.environ.get("ADB_PORT", "5037"), "-s", self.serial, *args], capture_output=True, text=True, env=self.env, **kw).stdout

    def shell(self, cmd):
        return self.run("shell", cmd)

    def refresh_hz(self):
        """Tần số quét của màn hình đang đo (màn hình khác 0: theo `display_hz`). Màn hình thật: SurfaceFlinger báo `refresh-rate : 60.00fps` (máy ảo: `peak-refresh-rate : 60.00 Hz`); không có thì `renderFrameRate` / `refreshRate=` của dumpsys display."""
        if self.display != 0:
            found = display_hz(self.shell("dumpsys display"), self.display)
            if found is None:
                raise SystemExit(f"không đọc được tần số quét của màn hình {self.display} (dùng --hz)")
            return found
        flinger, display = self.shell("dumpsys SurfaceFlinger"), self.shell("dumpsys display")
        m = (re.search(r"refresh-rate\s*:\s*([\d.]+)\s*fps", flinger) or re.search(r"peak-refresh-rate\s*:\s*([\d.]+)\s*Hz", flinger)
             or re.search(r"renderFrameRate ([\d.]+)", display) or re.search(r"refreshRate=([\d.]+)", display))
        if not m:
            raise SystemExit("không đọc được tần số quét của máy")
        return float(m.group(1))

    def guard(self):
        """Đòi cửa sổ của app đo đang ở trên cùng màn hình đo (xem docstring đầu file); sai thì ném Unsafe, chưa có thao tác nào được gửi."""
        problem = verdict(self.package, self.display, self.shell("dumpsys activity activities"), self.shell("dumpsys window displays"))
        if problem:
            raise Unsafe(problem)

    def _input(self, *args):
        self.guard()
        self.shell(f"input -d {self.display} " + " ".join(str(a) for a in args))
        self.sent += 1

    def tap(self, spot, settle=0.7):
        self._input("tap", int(spot[0] * self.w), int(spot[1] * self.h))
        time.sleep(settle)

    def back(self, settle=0.7):
        self._input("keyevent", "KEYCODE_BACK")
        time.sleep(settle)

    def swipe(self, x0, y0, x1, y1, ms, settle=0.3):
        self._input("swipe", int(x0 * self.w), int(y0 * self.h), int(x1 * self.w), int(y1 * self.h), ms)
        time.sleep(settle)

    def wake_if_asleep(self):
        """Màn hình thật đang tắt thì bật (phím gửi vào màn hình tắt, không app nào nhận); đang sáng thì không gửi gì. Vuốt mở khoá chỉ khi khoá màn hình đang hiện.
        Đo trên màn hình khác (màn hình ảo trên máy có người dùng): KHÔNG gửi gì tới màn hình thật; màn hình thật tắt hay khoá mà app trên màn hình ảo bị
        dừng / che thì `guard()` trước thao tác kế tiếp tự ném Unsafe."""
        if self.display != 0:
            return
        if "mWakefulness=Awake" not in self.shell("dumpsys power"):
            self.shell("input keyevent KEYCODE_WAKEUP")
            time.sleep(0.8)
        if "isKeyguardShowing=true" in self.shell("dumpsys window"):
            self.shell(f"input swipe {self.w // 2} {int(self.h * 0.83)} {self.w // 2} {int(self.h * 0.25)} 200")
            time.sleep(1.0)

    def awake(self):
        """Máy hẹn giờ tắt màn hình ngắn (15 giây) và không có thao tác nào trong lúc chờ: đánh thức màn hình thật nếu nó tắt (không đổi cài đặt nào)."""
        self.wake_if_asleep()

    def nap(self, seconds):
        """Chờ `seconds` giây, cứ ~4 giây xem màn hình thật có tắt không và bật lại nếu tắt (không gửi phím nào khi màn hình đang sáng)."""
        end = time.time() + seconds
        while time.time() < end:
            time.sleep(min(4.0, max(0.0, end - time.time())))
            if time.time() < end:
                self.wake_if_asleep()

    def start(self):
        self.awake()
        self.shell(f"am start -W --display {self.display} -n {self.package}/{ACTIVITY} -f 0x10008000 --ei abook.demo.books 200")


def scenarios(p, s, c):
    """name -> (số lần lặp, đang ở Đang nghe?, các bước, giây ghi vệt, khung dựng mỗi lần lặp). Giống các bài của :benchmark."""
    def tabs():
        for t in (s["tabStudio"], s["tabSettings"], s["tabLibrary"], s["tabSettings"], s["tabStudio"], s["tabLibrary"]): p.tap(t, 0.6)

    def grid():
        for _ in range(3): p.swipe(0.5, 0.75, 0.5, 0.2, 120, 0.9)
        for _ in range(3): p.swipe(0.5, 0.2, 0.5, 0.75, 120, 0.9)

    def push():
        for _ in range(3): p.tap(s["firstBook"], 0.9); p.back(0.9)

    def openclose():
        for _ in range(3): p.tap(s["miniOpen"], 0.9); p.tap(s["collapse"], 0.9)

    def readalong():
        for _ in range(3): p.tap(s["modeRead"], 1.0); p.tap(s["modeListen"], 1.0)
        p.tap(s["collapse"], 0.9)

    def seek():
        for _ in range(3):
            p.swipe(c["SEEK_LEFT"], c["SEEK_Y"], c["SEEK_RIGHT"], c["SEEK_Y"], 600, 0.4)
            p.swipe(c["SEEK_RIGHT"], c["SEEK_Y"], c["SEEK_LEFT"], c["SEEK_Y"], 600, 0.4)
        p.tap(s["collapse"], 0.9)

    def sheets():
        for _ in range(3): p.tap(s["speed"], 0.9); p.back(0.9); p.tap(s["sleep"], 0.9); p.back(0.9)
        p.tap(s["collapse"], 0.9)

    return {
        "cold": (10, None, None, 6, 4), "tabs": (8, False, tabs, 14, 1), "grid": (8, False, grid, 14, 0), "openclose": (5, False, openclose, 14, 1),
        "readalong": (5, True, readalong, 14, 0), "push": (8, False, push, 14, 1), "seek": (5, True, seek, 14, 0), "sheets": (5, True, sheets, 16, 0),
    }


MIN_FRAMES = {"cold": 4}
CONFIG = """buffers { size_kb: 65536 fill_policy: RING_BUFFER }
data_sources { config { name: "linux.ftrace" ftrace_config {
  ftrace_events: "sched/sched_switch" ftrace_events: "power/cpu_frequency"
  atrace_categories: "gfx" atrace_categories: "view" atrace_categories: "dalvik" atrace_categories: "am" atrace_categories: "input"
  atrace_apps: "%s" } } }
data_sources { config { name: "android.surfaceflinger.frametimeline" } }
%s
data_sources { config { name: "linux.process_stats" process_stats_config { scan_all_processes_on_start: true } } }
duration_ms: %d
"""


def record(phone, seconds, compose_trace):
    proc = subprocess.Popen([phone.adb_path, "-P", os.environ.get("ADB_PORT", "5037"), "-s", phone.serial, "shell", "perfetto --txt -c - -o /data/misc/perfetto-traces/fb.pftrace"],
                            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=phone.env, text=True)
    proc.stdin.write(CONFIG % (phone.package, 'data_sources { config { name: "track_event" } }' if compose_trace else "", seconds * 1000))
    proc.stdin.close()
    time.sleep(2.0)
    return proc


def frames_of(path, package):
    """[(cpu ms, overrun ms hoặc None)] của mọi khung app vẽ trong vệt, theo thứ tự thời gian."""
    from perfetto.trace_processor import TraceProcessor
    tp = TraceProcessor(trace=path)
    q = lambda sql: list(tp.query(sql))
    # Tiến trình app: theo tên, hay (mở nguội: vệt bắt đầu trước lúc đổi tên) tiến trình tên zygote vẽ nhiều khung nhất.
    rows = q("select p.upid, count(*) c from slice s join thread_track t on s.track_id=t.id join thread using(utid) join process p using(upid) "
             f"where s.name like 'DrawFrame%' and (p.name='{package}' or p.name like 'zygote%' or p.name like '<pre%') group by p.upid order by c desc")
    if not rows:
        return []
    upid = rows[0].upid
    main = q(f"select utid from thread where upid={upid} and tid=(select pid from process where upid={upid})")[0].utid
    do_frame = {x.name.split()[-1]: x.ts for x in q(f"select s.name, s.ts from slice s join thread_track t on s.track_id=t.id where t.utid={main} and s.name like 'Choreographer#doFrame %'")}
    out = {}
    for x in q(f"select s.name, s.ts, s.dur from slice s join thread_track t on s.track_id=t.id join thread using(utid) where thread.upid={upid} and s.name like 'DrawFrame%' order by s.ts"):
        token = x.name.split()[-1]
        if token in do_frame:
            out[token] = [(x.ts + x.dur - do_frame[token]) / 1e6, None]
    expected = {x.surface_frame_token: x.ts + x.dur for x in q(f"select surface_frame_token, ts, dur from expected_frame_timeline_slice where upid={upid}")}
    for x in q(f"select surface_frame_token, ts, dur from actual_frame_timeline_slice where upid={upid}"):
        if str(x.surface_frame_token) in out and x.surface_frame_token in expected:
            out[str(x.surface_frame_token)][1] = (x.ts + x.dur - expected[x.surface_frame_token]) / 1e6
    return list(out.values())


def pct(values, p):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(p * len(ordered)))] if ordered else float("nan")


def judge(iterations, builds, period):
    """Tách khung dựng (nặng nhất mỗi lần lặp) khỏi phần còn lại và chấm theo ngân sách. Trả về dict số đo + PASS/FAIL từng mức."""
    steady, built = [], []
    for frames in iterations:
        ordered = sorted(frames, key=lambda f: f[0], reverse=True)
        built += [f[0] for f in ordered[:builds]]
        steady += [f[0] for f in ordered[builds:]]
    every = [f[0] for frames in iterations for f in frames]
    over = [f[1] for frames in iterations for f in frames if f[1] is not None]
    res = dict(frames=len(every), p50=pct(every, .5), p90=pct(every, .9), p95=pct(every, .95), p99=pct(every, .99), max=max(every, default=float("nan")),
               over_p=sum(1 for c in every if c > period), ov_p95=pct(over, .95),
               steady_p95=pct(steady, .95), steady_p99=pct(steady, .99), steady_over_share=(sum(1 for c in steady if c > period) / len(steady)) if steady else 0.0,
               build_max=max(built, default=0.0))
    res["ok_p95"] = res["steady_p95"] <= 0.75 * period
    res["ok_p99"] = res["steady_p99"] <= period
    res["ok_over"] = res["steady_over_share"] <= 0.01
    res["ok_build"] = res["build_max"] <= 2 * period
    return res


def run(phone, name, spec, out_dir, period, args):
    iters, in_player, steps, seconds, builds = spec
    iters = args.iters or iters
    iterations = []
    phone.shell(f"am force-stop {phone.package}")
    time.sleep(1.5)
    spots, _ = load_spots()
    # Lần lặp khởi động (--warmup, mặc định 1) chạy đúng kịch bản nhưng không tính: lần đầu sau khi cài, GL biên dịch shader của mọi thứ app vẽ lần đầu rồi nhớ trên
    # đĩa (shader_compile / driver_compile_shader trong vệt, ~20-70 ms một khung trên OPPO); Macrobenchmark cũng có lượt khởi động trước khi đo.
    i = -args.warmup
    retries = 0
    while i < iters:
        measured = i >= 0
        if name == "cold":
            phone.shell(f"am force-stop {phone.package}")
            phone.nap(2.5)
            proc = record(phone, seconds, args.compose_trace) if measured else None
            phone.start()
            phone.nap(3.0)
        else:
            phone.start()
            time.sleep(2.2)
            phone.guard()  # cửa sổ khác đang ở trên cùng (người dùng đang dùng máy): Unsafe, dừng cả lần đo - không chờ, không thử lại
            if in_player:
                phone.tap(spots["miniOpen"], 1.0)
            if measured:
                phone.shell(f"dumpsys gfxinfo {phone.package} reset")
                if args.compose_trace:
                    # Bản -PcomposeTrace chỉ ghi tên composable sau khi nhận broadcast này (tracing-perfetto).
                    phone.shell(f"am broadcast -a androidx.tracing.perfetto.action.ENABLE_TRACING -n {phone.package}/androidx.tracing.perfetto.TracingReceiver")
                    time.sleep(1.5)
                proc = record(phone, seconds, args.compose_trace)
            steps()
        if not measured:
            i += 1
            continue
        while proc.poll() is None:
            phone.nap(3.0)
        open(os.path.join(out_dir, f"{name}_{i}.gfx"), "w", encoding="utf-8").write(phone.shell(f"dumpsys gfxinfo {phone.package}"))
        path = os.path.join(out_dir, f"{name}_{i}.pftrace")
        phone.run("pull", "/data/misc/perfetto-traces/fb.pftrace", path)
        frames = frames_of(path, phone.package)
        if len(frames) < MIN_FRAMES.get(name, 20) and retries < 3 * iters:
            # App không vẽ khung nào (ai đó đang dùng máy: cửa sổ khác giành tiền cảnh, hay màn tắt): bỏ lần lặp này, đo lại.
            retries += 1
            print(name, i, len(frames), "khung - bỏ, đo lại", flush=True)
            if os.path.exists(path):
                os.remove(path)
            time.sleep(20)
            continue
        iterations.append(frames)
        print(name, i, len(frames), "khung", flush=True)
        if not args.keep_traces and os.path.exists(path):
            os.remove(path)
        i += 1
    res = judge(iterations, builds, period)
    res.update(scenario=name, period_ms=period)
    json.dump(res, open(os.path.join(out_dir, f"{name}.json"), "w"))
    return res


class VirtualDisplay:
    """Một màn hình ảo do scrcpy mở (cửa sổ của nó đặt ngoài vùng nhìn thấy); `close()` chỉ tắt đúng tiến trình đã mở, theo PID."""

    def __init__(self, adb, serial, package, size, log_path):
        env = dict(os.environ, ADB=adb, ANDROID_ADB_SERVER_PORT=os.environ.get("ADB_PORT", "5037"), MSYS_NO_PATHCONV="1")
        self.log = open(log_path, "w", encoding="utf-8")
        self.proc = subprocess.Popen(
            [SCRCPY, "-s", serial, f"--new-display={size}", f"--start-app={package}", "--no-audio", "--no-clipboard-autosync", "--no-power-on", "--window-x=-10000", "--window-y=-10000",
             "--window-width=200", "--window-height=400", "--max-fps=60"],
            stdout=self.log, stderr=subprocess.STDOUT, env=env, stdin=subprocess.DEVNULL)
        self.id, self.size = None, None
        deadline = time.time() + 40
        while time.time() < deadline and self.id is None:
            time.sleep(0.5)
            if self.proc.poll() is not None:
                break
            found = re.search(r"New display: (\d+)x(\d+)/\d+ \(id=(\d+)\)", open(log_path, encoding="utf-8", errors="replace").read())
            if found:
                self.size, self.id = (int(found.group(1)), int(found.group(2))), int(found.group(3))
        if self.id is None:
            self.close()
            raise SystemExit(f"scrcpy không mở được màn hình ảo (xem {log_path})")

    def close(self):
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.log.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--package", required=True)
    ap.add_argument("--serial", required=True)
    ap.add_argument("--adb", default="adb")
    ap.add_argument("--scenarios", default="")
    ap.add_argument("--iters", type=int, default=0)
    ap.add_argument("--warmup", type=int, default=1)
    ap.add_argument("--out", default="frames_out")
    ap.add_argument("--keep-traces", action="store_true")
    ap.add_argument("--compose-trace", action="store_true")
    ap.add_argument("--display", type=int, default=0, help="số hiệu màn hình nhận thao tác và chạy app (mặc định 0 = màn hình thật)")
    ap.add_argument("--virtual-display", action="store_true", help="mở màn hình ảo bằng scrcpy và đo trên đó")
    ap.add_argument("--vd-size", default="", help="WxH/dpi của màn hình ảo; mặc định theo màn hình thật của máy")
    ap.add_argument("--hz", type=float, default=0.0, help="tần số quét để tính P; mặc định đọc từ SurfaceFlinger")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    probe = Phone(args.adb, args.serial, args.package)
    vd = None
    try:
        if args.virtual_display:
            size = args.vd_size or f"{probe.w}x{probe.h}/" + (re.search(r"(\d+)\s*$", probe.shell("wm density").strip().splitlines()[-1]).group(1))
            vd = VirtualDisplay(args.adb, args.serial, args.package, size, os.path.join(args.out, "scrcpy.log"))
            print(f"màn hình ảo id={vd.id} {vd.size[0]}x{vd.size[1]}", flush=True)
            phone = Phone(args.adb, args.serial, args.package, vd.id, vd.size)
        else:
            phone = Phone(args.adb, args.serial, args.package, args.display)
        hz = args.hz or phone.refresh_hz()
        period = 1000.0 / hz
        spots, consts = load_spots()
        table = scenarios(phone, spots, consts)
        names = [n for n in args.scenarios.split(",") if n] or list(table)
        print(f"tần số quét {hz:.1f} Hz -> P = {period:.1f} ms; ngân sách: p95 <= {0.75 * period:.1f}, p99 <= {period:.1f}, khung > P <= 1 %, khung dựng <= {2 * period:.1f} ms")
        results = []
        try:
            results = [run(phone, n, table[n], args.out, period, args) for n in names]
        except Unsafe as why:
            phone.shell(f"am force-stop {phone.package}")
            print(f"DỪNG AN TOÀN: {why}. Đã gửi {phone.sent} thao tác tới màn hình {phone.display}; thao tác kế tiếp KHÔNG được gửi; đã force-stop {phone.package}.", flush=True)
            return 3
        print("\nkịch bản   khung   p50   p90   p95   p99   max  >P(%)  overrun p95 | sau khi bỏ khung dựng: p95 p99 >P% | khung dựng max | đạt p95/p99/>P/dựng")
        for r in results:
            flags = "/".join("đạt" if r[k] else "TRƯỢT" for k in ("ok_p95", "ok_p99", "ok_over", "ok_build"))
            print(f"{r['scenario']:<10} {r['frames']:5d} {r['p50']:5.1f} {r['p90']:5.1f} {r['p95']:5.1f} {r['p99']:5.1f} {r['max']:5.1f} {100 * r['over_p'] / max(1, r['frames']):5.1f}  "
                  f"{r['ov_p95']:6.1f} | {r['steady_p95']:5.1f} {r['steady_p99']:5.1f} {100 * r['steady_over_share']:4.1f} | {r['build_max']:6.1f} | {flags}")
        return 0
    finally:
        if vd:
            # Dừng app TRƯỚC khi đóng màn hình ảo: không để Android dời activity của nó sang màn hình thật khi màn hình ảo biến mất.
            probe.shell(f"am force-stop {args.package}")
            vd.close()


if __name__ == "__main__":
    sys.exit(main())
