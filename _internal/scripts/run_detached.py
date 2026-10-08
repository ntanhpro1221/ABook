"""Chạy một lệnh dài (vd `bash scripts/boundary.sh 17`) TÁCH khỏi phiên Claude, không mở cửa sổ nào.

    powershell: Start-Process -FilePath runtime\\.venv\\Scripts\\pythonw.exe `
        -ArgumentList 'scripts\\run_detached.py','bash','scripts/boundary.sh','17' `
        -WorkingDirectory <_internal> -WindowStyle Hidden

## Vì sao (24-09 20:4x)

Ranh giới thả bằng lệnh nền của phiên (`Bash run_in_background`) là con của phiên, nên chết khi phiên chết:
phiên đóng đêm 23-09 (lệnh nền thoát mã 4), `boundary.sh 16` chết theo, lô 16 vẫn tự xong lúc 24-09 15:15
nhưng không còn ai ghép sách và thả lô 17 - **mất 5,5 giờ sản xuất** cho tới khi phiên mới mở. Trong khi đó
daemon nhịp tim, thả bằng `Start-Process pythonw.exe`, đã sống qua mọi lần đổi phiên từ 18-09.

Nên script này là đúng cái khuôn ấy: `pythonw` (không console) khởi chạy lệnh và ĐỢI nó. Con phải mang
`CREATE_NO_WINDOW` - `pythonw` chỉ lo cho chính nó, và thiếu cờ ấy thì bash sẽ bật một cửa sổ terminal
(xem `tests/test_a_windowless_daemon_opens_no_window.py`, lỗi 21-09 của `heartbeat_daemon.py`).

Mã thoát và giờ chạy ghi vào `runtime/detached_runs.log`, vì không có ai đọc stdout của một tiến trình rời.

## Cha là WMI, không phải phiên (09-10 00:1x)

Đổi tài khoản làm app Claude khởi động lại lúc 00:04-00:13 và MỌI việc thả bằng `Start-Process pythonw` chết
theo (máy không khởi động lại): chuỗi GPU của Model, chuỗi nhạc, người gác pin, bộ giữ êm quạt. Chúng vẫn
là hậu duệ của app. Nên lần chạy đầu không tự làm việc: nó nhờ dịch vụ WMI (`Win32_Process.Create`) chạy lại
chính nó - cha mới là WmiPrvSE, ngoài cây của app; cùng phiên đăng nhập nên vẫn thấy GPU (phiên Model thử
00:2x). Tiến trình WMI tạo không kế thừa biến môi trường của người gọi (OMP_NUM_THREADS...), nên chúng được ghi
ra một file tạm cho lần chạy thứ hai đọc lại rồi xoá. WMI hỏng thì chạy ngay tại chỗ như trước.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "runtime" / "detached_runs.log"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if os.name == "nt" else 0
GIT_BASH = Path(r"C:\Program Files\Git\bin\bash.exe")
OUTSIDE = "--outside-claude"
ENV_DIR = ROOT / "runtime" / "detached_env"


def _resolve(program: str) -> str:
    """`bash` phải là Git Bash: `bash.exe` của WSL cũng nằm trên PATH và chạy một hệ điều hành khác."""
    if program == "bash" and GIT_BASH.is_file():
        return str(GIT_BASH)
    # Đường tương đối ("runtime/.venv/Scripts/python.exe") CreateProcess không tìm thấy (09-10: nhịp tim thả lại chết
    # câm vì thế) - đổi sang đường tuyệt đối dưới ROOT.
    local = ROOT / program
    if not Path(program).is_absolute() and local.is_file():
        return str(local.resolve())
    return shutil.which(program) or program


def _note(line: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} pid={os.getpid()} {line}\n")


def _relaunch_outside(argv: list[str]) -> bool:
    """Nhờ WMI chạy lại script này (cờ OUTSIDE + file môi trường); True khi WMI nhận lệnh."""
    if os.name != "nt":
        return False
    ENV_DIR.mkdir(parents=True, exist_ok=True)
    env_file = ENV_DIR / f"{os.getpid()}_{time.time_ns()}.json"
    env_file.write_text(json.dumps(dict(os.environ)), encoding="utf-8")
    command_line = subprocess.list2cmdline([sys.executable, str(Path(__file__).resolve()), OUTSIDE, str(env_file), *argv])
    quote = lambda value: "'" + value.replace("'", "''") + "'"  # noqa: E731 - chuỗi PowerShell nháy đơn
    script = (
        "$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments "
        f"@{{CommandLine={quote(command_line)}; CurrentDirectory={quote(str(ROOT))}}}; exit $r.ReturnValue"
    )
    try:
        done = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script], stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=NO_WINDOW, timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired):
        done = None
    if done is not None and done.returncode == 0:
        return True
    env_file.unlink(missing_ok=True)
    return False


def main(argv: list[str]) -> int:
    if argv[:1] == [OUTSIDE] and len(argv) >= 2:
        env_file = Path(argv[1])
        try:
            os.environ.update(json.loads(env_file.read_text(encoding="utf-8")))
            env_file.unlink()
        except (OSError, ValueError) as error:
            _note(f"không đọc được môi trường người gọi ({error}) - chạy với môi trường của WMI")
        argv = argv[2:]
    elif argv and _relaunch_outside(argv):
        return 0
    if not argv:
        _note("không có lệnh nào để chạy")
        return 2
    command = [_resolve(argv[0]), *argv[1:]]
    _note(f"bắt đầu: {' '.join(argv)}")
    try:
        completed = subprocess.run(
            command, cwd=str(ROOT), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, creationflags=NO_WINDOW,
        )
    except OSError as error:  # pythonw không có stderr: không ghi ở đây thì lỗi biến mất
        _note(f"không chạy được ({error}): {' '.join(argv)}")
        return 127
    _note(f"xong (mã {completed.returncode}): {' '.join(argv)}")
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
