r"""Bật máy chủ Ollama ẨN nếu nó chưa chạy - cho các bước ngoài dây chuyền cần `ollama create` (serve_lora.py, ollama_like.py).

    runtime/.venv/Scripts/python.exe scripts/model_eval/ollama_up.py

Vì sao: gọi CLI `ollama` khi máy chủ tắt thì Windows tự mở app khay + bộ cập nhật (docs/AGENTS). Sau khi máy khởi động
lại (28-09) không ai bật máy chủ, và hàng GPU đi thẳng tới `ollama create`. Làm y như `OllamaBookAnalyzer.ensure_available`
(analysis.py): `ollama serve` với CREATE_NO_WINDOW, stdout/stderr vào `runtime/logs/ollama-server.log` kèm dòng đánh dấu ai
bật. Tiến trình máy chủ sống tiếp sau khi script này thoát.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

URL = "http://127.0.0.1:11434/api/tags"
LOG = Path(__file__).resolve().parents[2] / "runtime" / "logs" / "ollama-server.log"


def running() -> bool:
    try:
        with urllib.request.urlopen(URL, timeout=3) as response:
            return response.status == 200
    except OSError:
        return False


def main() -> int:
    if running():
        print("Ollama đã chạy")
        return 0
    executable = shutil.which("ollama")
    if not executable:
        print("không thấy ollama trên PATH")
        return 1
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("ab") as log:
        log.write(f"\n--- ollama_up.py started Ollama at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n".encode())
        subprocess.Popen(
            [executable, "serve"], stdin=subprocess.DEVNULL, stdout=log, stderr=log,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0,
        )
    for _ in range(60):
        time.sleep(1)
        if running():
            print("đã bật Ollama ẩn")
            return 0
    print("Ollama không lên sau 60 giây - xem", LOG)
    return 1


if __name__ == "__main__":
    sys.exit(main())
