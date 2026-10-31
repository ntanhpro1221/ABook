"""Thử SMTC thật bằng HWND không bao giờ được show; mọi tiến trình con đều CREATE_NO_WINDOW."""
import json
import os
from pathlib import Path
import subprocess
import time
import ctypes

root = Path(__file__).resolve().parent.parent
folder = Path("D:/Novels/native_desk_proto/smtc_task")
folder.mkdir(parents=True, exist_ok=True)
result = folder / "hidden_host.json"
env = dict(os.environ, ABOOK_SMTC_HOST_RESULT=str(result))
env["PATH"] = "D:/Novels/native_desk_proto/qt611/6.10.3/msvc2022_64/bin;" + env["PATH"]
ctypes.windll.kernel32.SetErrorMode(0x0001 | 0x0002 | 0x8000)
log = []
with (folder / "hidden_host.log").open("wb") as output:
    host = subprocess.Popen([str(root / "build/SmtcHost.exe")], env=env, stdout=output, stderr=output,
                            creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        for _ in range(40):
            probe = subprocess.run([str(root / "build/SmtcProbe.exe")], capture_output=True, encoding="utf-8",
                                   creationflags=subprocess.CREATE_NO_WINDOW, timeout=10)
            if probe.returncode == 0 and "PlaybackStatus=4" in probe.stdout:
                log.append(probe.stdout)
                break
            if host.poll() is not None:
                raise RuntimeError(f"Hidden host exited {host.returncode}: {probe.stdout}")
            time.sleep(.25)
        else:
            raise RuntimeError(f"No hidden-window session: {probe.stdout}")
        for command, key, expected in [("--next", "chapter", 2), ("--previous", "chapter", 1), ("--seek=42", "position", 42)]:
            probe = subprocess.run([str(root / "build/SmtcProbe.exe"), command], capture_output=True, encoding="utf-8",
                                   creationflags=subprocess.CREATE_NO_WINDOW, timeout=10)
            log.append(probe.stdout)
            assert probe.returncode == 0
            for _ in range(30):
                state = json.loads(result.read_bytes())
                if state[key] == expected:
                    break
                time.sleep(.1)
            assert state[key] == expected and state["ui_thread"] and not state["visible"] and not state["foreground"]
            log.append(json.dumps(state))
        probe = subprocess.run([str(root / "build/SmtcProbe.exe"), "--pause"], capture_output=True, encoding="utf-8",
                               creationflags=subprocess.CREATE_NO_WINDOW, timeout=10)
        log.append(probe.stdout)
        assert probe.returncode == 0
        host.wait(timeout=10)
        state = json.loads(result.read_bytes())
        log.append(json.dumps(state, ensure_ascii=False))
        assert host.returncode == 0 and state["phase"] == "pause_reached_player"
        assert not state["playing"] and state["ui_thread"] and not state["visible"] and not state["foreground"]
        log.append("PASS: native hidden HWND -> GSMTC -> TryPauseAsync -> Player::pause on UI thread")
    finally:
        if host.poll() is None:
            host.kill()
            host.wait()
        text = "\n".join(log)
        (folder / "probe_output.txt").write_text(text, encoding="utf-8")
        print(text)
