"""Người gác pin: rút điện ngoài ý muốn thì giữ pin cho lâu, báo để dời việc sang máy khác, sắp hết pin thì đóng việc
rồi hẹn tắt máy - có nút huỷ cho người đang ngồi cạnh máy.

    pythonw scripts/run_detached.py <python> scripts/power_guard.py      # gác, chạy rời (sống qua phiên Claude)
    python scripts/power_guard.py --wait                                 # chuông: thoát khi có sự kiện pin mới (<= 30 phút)
    python scripts/power_guard.py --status                               # pin, ước lượng, việc GPU đang có

Chủ sách 29-09: "căn pin cho phù hợp chứ không phải cứ thấy pin tụt chút là tắt trong khi on battery vẫn chạy được lâu".
Vì sao tạm dừng việc GPU ngay khi chạy pin: 24-09 sạc rút lúc 22:50, GPU bị hạ xuống 480 MHz / 15 W và phân tích tụt từ
56 xuống 3,8 tok/s - việc GPU trên pin chậm ~15 lần mà vẫn ăn pin; tạm dừng (không giết) thì cắm lại là chạy tiếp đúng
chỗ. Windows tự ngủ đông ở 2%, nên đóng việc + hẹn tắt phải xảy ra trước đó, theo THỜI GIAN CÒN LẠI ước từ tốc độ tụt thật
chứ không theo một con số % (máy nghỉ GPU còn chạy pin được hàng giờ).

Các bậc (mỗi bậc một dòng trong runtime/power_events.log - chuông `--wait` đọc file ấy):
  PAUSED   rút sạc > 60 giây: tạm dừng cây tiến trình của các việc GPU (hàng đợi, đo, huấn luyện, dây chuyền) và máy chủ
           Ollama của chúng.
  LONG     chạy pin > 15 phút: không phải rút nhầm - lúc dời việc sang Mac / cloud (việc của Claude, chuông báo).
  WARN     còn <= 25 phút: dời việc gấp, ghi kế hoạch chạy lại vào bộ nhớ.
  STOPPED  còn <= 12 phút hay <= 8%, hai lần đo liền: đóng các việc ấy.
  SHUTDOWN hẹn tắt máy sau 180 giây + hộp "Không tắt máy" (bấm = `shutdown /a`, ghi DECLINED, không hỏi lại lần chạy pin ấy).
  AC_BACK  cắm sạc lại: chạy tiếp việc đã tạm dừng, huỷ lệnh tắt đang hẹn.
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
# Chạy từ bản chép trong runtime/ (đổi nhánh worktree không làm mất file hộp thoại giữa lúc hẹn tắt) hay từ scripts/.
RUNTIME = HERE if HERE.name == "runtime" else HERE.parent / "runtime"
EVENTS = RUNTIME / "power_events.log"

POLL_SECONDS = 20
GRACE_SECONDS = 60
LONG_SECONDS = 15 * 60
WARN_MINUTES = 25.0
STOP_MINUTES = 12.0
STOP_PERCENT = 8
LOW_POLLS = 2
RATE_WINDOW_SECONDS = 600
RATE_MIN_SPAN_SECONDS = 180
SHUTDOWN_DELAY_SECONDS = 180

# Việc GPU của máy này là CÂY tiến trình mọc từ các gốc này: hàng GPU và ranh giới (bash chạy rời), dây chuyền sản xuất.
JOB_ROOTS = re.compile(r"gpu_queue_|boundary\.sh|run_book_job\.py|narrator_ab|train_\w+\.py|eval_models\.py")


@dataclass
class Reading:
    at: float  # giây, đồng hồ đơn điệu
    ac: bool
    percent: int | None  # None = Windows không biết
    seconds_left: int | None  # ước lượng của Windows, None = chưa biết


@dataclass
class State:
    unplugged_at: float | None = None
    samples: list[tuple[float, int]] = field(default_factory=list)
    paused: bool = False
    long_told: bool = False
    warned: bool = False
    stopped: bool = False
    shutdown_pending: bool = False
    declined: bool = False
    low_polls: int = 0


def remaining_minutes(state: State, reading: Reading) -> float | None:
    """Phút còn lại, ước THẬN TRỌNG: nhỏ hơn của (a) Windows và (b) tốc độ tụt % trong 10 phút gần nhất (cần >= 3 phút
    số liệu - % nhảy từng 1 nên khoảng ngắn hơn là nhiễu). Chưa có cái nào thì None: chỉ ngưỡng % còn tác dụng."""
    estimates = []
    if reading.seconds_left is not None and reading.seconds_left > 0:
        estimates.append(reading.seconds_left / 60)
    window = [(at, percent) for at, percent in state.samples if reading.at - at <= RATE_WINDOW_SECONDS]
    if len(window) >= 2 and window[-1][0] - window[0][0] >= RATE_MIN_SPAN_SECONDS and reading.percent is not None:
        dropped = window[0][1] - window[-1][1]
        minutes = (window[-1][0] - window[0][0]) / 60
        if dropped > 0:
            estimates.append(reading.percent / (dropped / minutes))
    return min(estimates) if estimates else None


def decide(state: State, reading: Reading) -> list[str]:
    """Bậc kế tiếp cho một lần đo - thuần (test được). Trả các việc phải làm theo thứ tự."""
    if reading.ac:
        actions = []
        if state.unplugged_at is not None:
            if state.paused and not state.stopped:
                actions.append("resume")
            if state.shutdown_pending:
                actions.append("abort")
            actions.append("ac_back")
        state.__init__()  # lần rút sau là một lần mới
        return actions
    actions = []
    if state.unplugged_at is None:
        state.unplugged_at = reading.at
        state.samples = []
    if reading.percent is not None:
        state.samples.append((reading.at, reading.percent))
        state.samples = [(at, p) for at, p in state.samples if reading.at - at <= RATE_WINDOW_SECONDS]
    on_battery = reading.at - state.unplugged_at
    if not state.paused and not state.stopped and on_battery >= GRACE_SECONDS:
        state.paused = True
        actions.append("pause")
    if not state.long_told and on_battery >= LONG_SECONDS:
        state.long_told = True
        actions.append("long")
    left = remaining_minutes(state, reading)
    if not state.warned and left is not None and left <= WARN_MINUTES:
        state.warned = True
        actions.append("warn")
    low = (left is not None and left <= STOP_MINUTES) or (reading.percent is not None and reading.percent <= STOP_PERCENT)
    state.low_polls = state.low_polls + 1 if low else 0
    if state.low_polls >= LOW_POLLS and not state.stopped:
        state.stopped = True
        actions.append("stop")
        if not state.declined:
            state.shutdown_pending = True
            actions.append("shutdown")
    return actions


# ---- máy thật ------------------------------------------------------------------------------------------------------


class _PowerStatus(ctypes.Structure):
    _fields_ = [("ac", ctypes.c_ubyte), ("flag", ctypes.c_ubyte), ("percent", ctypes.c_ubyte), ("saver", ctypes.c_ubyte),
                ("seconds", ctypes.c_ulong), ("full", ctypes.c_ulong)]


def read_power() -> Reading:
    status = _PowerStatus()
    ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status))
    # ac: 0 = pin, 1 = cắm sạc, 255 = không rõ (máy bàn không pin -> coi như cắm sạc).
    return Reading(at=time.monotonic(), ac=status.ac != 0,
                   percent=None if status.percent == 255 else int(status.percent),
                   seconds_left=None if status.seconds in (0xFFFFFFFF, -1) else int(status.seconds))


def log_event(kind: str, detail: str = "") -> None:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {kind} {detail}".rstrip()
    with EVENTS.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def job_processes():
    """Gốc việc GPU + mọi tiến trình con cháu, bỏ chính tiến trình này - kèm máy chủ Ollama (`ollama serve` do ollama_up.py
    bật tách khỏi cây, và các llama-server của nó): tạm dừng mà để máy chủ chạy thì nó làm nốt câu trả lời đang dở ở 15 W
    (có khi vài phút pin); dừng cả nó thì GPU nghỉ ngay, cắm lại là cả hai chạy tiếp đúng chỗ. Đóng việc thì tắt luôn, cho
    khỏi giữ VRAM khi chủ sách bấm "Không tắt máy"."""
    import psutil

    me = os.getpid()
    found: dict[int, "psutil.Process"] = {}
    for process in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            command = " ".join(process.info["cmdline"] or [])
            name = (process.info["name"] or "").lower()
        except (psutil.Error, TypeError):
            continue
        if process.info["pid"] == me or "power_guard.py" in command:
            continue
        server = name == "llama-server.exe" or (name == "ollama.exe" and " serve" in command)
        if not server and not JOB_ROOTS.search(command):
            continue
        found[process.pid] = process
        try:
            for child in process.children(recursive=True):
                found.setdefault(child.pid, child)
        except psutil.Error:
            continue
    return list(found.values())


def describe(processes) -> str:
    names = []
    for process in processes[:12]:
        try:
            names.append(f"{process.pid}:{process.name()}")
        except Exception:  # noqa: BLE001 - tiến trình có thể vừa thoát
            continue
    return ", ".join(names)


def act(action: str, state: State, reading: Reading, left: float | None, paused: list) -> None:
    import psutil

    level = f"pin {reading.percent}%" + (f", còn ~{left:.0f} phút" if left is not None else "")
    if action == "pause":
        paused[:] = job_processes()
        for process in paused:
            try:
                process.suspend()
            except psutil.Error:
                pass
        log_event("PAUSED", f"{level}; tạm dừng {len(paused)} tiến trình: {describe(paused)}")
    elif action == "resume":
        for process in paused:
            try:
                process.resume()
            except psutil.Error:
                pass
        log_event("RESUMED", f"chạy tiếp {len(paused)} tiến trình")
        paused.clear()
    elif action == "long":
        log_event("LONG", f"{level}; chạy pin đã 15 phút - không phải rút nhầm, dời việc sang máy khác")
    elif action == "warn":
        log_event("WARN", f"{level}; dời việc gấp, ghi kế hoạch chạy lại")
    elif action == "stop":
        victims = job_processes()
        # Con trước cha: cha không kịp đẻ con mới; tiến trình đang bị tạm dừng vẫn giết được.
        for process in sorted(victims, key=lambda p: -len(_ancestors(p))):
            try:
                process.kill()
            except psutil.Error:
                pass
        paused.clear()
        log_event("STOPPED", f"{level}; đóng {len(victims)} tiến trình: {describe(victims)}")
    elif action == "shutdown":
        message = (f"ABook: pin sắp hết ({reading.percent}%) - máy tự tắt sau {SHUTDOWN_DELAY_SECONDS // 60} phút. "
                   "Muốn giữ máy: bấm 'Không tắt máy' trên hộp thoại, hoặc chạy: shutdown /a")
        subprocess.run(["shutdown", "/s", "/t", str(SHUTDOWN_DELAY_SECONDS), "/c", message],
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), check=False)
        pythonw = Path(sys.executable).with_name("pythonw.exe")
        subprocess.Popen([str(pythonw if pythonw.exists() else sys.executable), str(Path(__file__).resolve()), "--dialog",
                          str(SHUTDOWN_DELAY_SECONDS)], creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        log_event("SHUTDOWN", f"{level}; hẹn tắt máy sau {SHUTDOWN_DELAY_SECONDS} giây")
    elif action == "abort":
        subprocess.run(["shutdown", "/a"], creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), check=False)
        _close_dialogs()
        log_event("ABORTED", "có điện lại: huỷ lệnh tắt máy")
    elif action == "ac_back":
        log_event("AC_BACK", f"cắm sạc lại ({reading.percent}%)")


def _ancestors(process) -> list:
    try:
        return process.parents()
    except Exception:  # noqa: BLE001
        return []


def _close_dialogs() -> None:
    import psutil

    for process in psutil.process_iter(["cmdline"]):
        command = " ".join(process.info["cmdline"] or [])
        if "power_guard.py" in command and "--dialog" in command:
            try:
                process.kill()
            except psutil.Error:
                pass


def new_events(position: int) -> tuple[list[str], int]:
    """Các dòng sự kiện ghi thêm từ `position` (byte) và vị trí mới - đọc liên tục, không dòng nào lọt giữa hai lần đo."""
    try:
        with EVENTS.open("rb") as handle:
            handle.seek(position)
            data = handle.read()
    except OSError:
        return [], position
    return data.decode("utf-8", errors="replace").splitlines(), position + len(data)


def guard() -> int:
    state, paused = State(), []
    log_event("GUARD", f"gác pin bắt đầu (pid {os.getpid()})")
    position = EVENTS.stat().st_size if EVENTS.exists() else 0
    while True:
        try:
            reading = read_power()
            left = remaining_minutes(state, reading) if not reading.ac else None
            for action in decide(state, reading):
                act(action, state, reading, left, paused)
        except Exception as exc:  # noqa: BLE001 - một lần đo/làm hỏng không được giết người gác: lần sau đo lại
            log_event("ERROR", f"{type(exc).__name__}: {exc}"[:300])
        time.sleep(POLL_SECONDS)
        lines, position = new_events(position)
        if state.shutdown_pending and any(" DECLINED" in line for line in lines):
            # Chủ sách đang ở cạnh máy và bấm "Không tắt": không hỏi lại trong lần chạy pin này; Windows vẫn ngủ đông ở 2%.
            state.shutdown_pending, state.declined = False, True


def dialog(seconds: int) -> int:
    """Hộp đếm ngược có nút "Không tắt máy" - bấm là `shutdown /a` + ghi DECLINED."""
    import tkinter as tk

    root = tk.Tk()
    root.title("ABook - pin sắp hết")
    root.attributes("-topmost", True)
    left = [seconds]
    label = tk.Label(root, font=("Segoe UI", 12), padx=24, pady=16, justify="left")
    label.pack()

    def keep() -> None:
        subprocess.run(["shutdown", "/a"], creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), check=False)
        log_event("DECLINED", "chủ sách bấm 'Không tắt máy'")
        root.destroy()

    tk.Button(root, text="Không tắt máy", font=("Segoe UI", 12, "bold"), padx=16, pady=6, command=keep).pack(pady=(0, 16))

    def tick() -> None:
        label.config(text=f"Pin sắp hết. Các việc nặng đã đóng.\nMáy tự tắt sau {left[0]} giây.")
        left[0] -= 1
        if left[0] >= 0:
            root.after(1000, tick)

    tick()
    root.mainloop()
    return 0


def wait(limit: int = 1800) -> int:
    """Chuông: thoát (in dòng mới) khi power_events.log có sự kiện mới - trần 30 phút như mọi phép chờ (luật 18-09)."""
    start = EVENTS.stat().st_size if EVENTS.exists() else 0
    deadline = time.monotonic() + limit
    while time.monotonic() < deadline:
        if EVENTS.exists() and EVENTS.stat().st_size > start:
            with EVENTS.open("r", encoding="utf-8") as handle:
                handle.seek(start)
                print(handle.read().strip(), flush=True)
            return 0
        time.sleep(5)
    reading = read_power()
    print(f"chuông pin: không có sự kiện trong {limit // 60} phút ({'cắm sạc' if reading.ac else 'PIN'} {reading.percent}%)")
    return 0


def status() -> int:
    reading = read_power()
    print(f"{'cắm sạc' if reading.ac else 'PIN'} {reading.percent}% | Windows ước còn "
          f"{'?' if reading.seconds_left is None else f'{reading.seconds_left // 60} phút'}")
    print("việc GPU:", describe(job_processes()) or "(không có)")
    if EVENTS.exists():
        print("sự kiện cuối:", EVENTS.read_text(encoding="utf-8").strip().splitlines()[-3:])
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wait", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--dialog", type=int)
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if args.dialog is not None:
        return dialog(args.dialog)
    if args.wait:
        return wait()
    if args.status:
        return status()
    return guard()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
