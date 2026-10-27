"""Kiểm bìa + pause của app thật qua launcher off-screen có foreground guard. Không dùng lượt này làm số đo A/B."""
import json
import os
from pathlib import Path
import subprocess
import threading
import time
import psutil
import measure

root = Path(__file__).resolve().parent.parent
folder = Path("D:/Novels/native_desk_proto/smtc_task")
fixture = Path("D:/Novels/native_desk_proto/deskqt_fixture_music")
books = json.loads((fixture / "audio_books.json").read_bytes())
exe = root / "dist/ABookDesk.exe"
stop = threading.Event()
observed = []
os.environ["ABOOK_BENCH_AUDIT_DIR"] = str(folder / "app_smoke_audit")

def probe():
    while not stop.wait(.5):
        # Launcher đang chờ job khác thì không được chạm phiên SMTC của họ.
        own = any((p.info["exe"] or "").replace("\\", "/").lower() == str(exe).replace("\\", "/").lower()
                  for p in psutil.process_iter(["exe"]))
        if not own:
            continue
        read = subprocess.run([str(root / "build/SmtcProbe.exe")], capture_output=True, encoding="utf-8",
                              creationflags=subprocess.CREATE_NO_WINDOW, timeout=10)
        if read.returncode != 0 or "PlaybackStatus=4" not in read.stdout or "ThumbnailBytes=" not in read.stdout:
            continue
        pause = subprocess.run([str(root / "build/SmtcProbe.exe"), "--pause"], capture_output=True, encoding="utf-8",
                               creationflags=subprocess.CREATE_NO_WINDOW, timeout=10)
        observed.append(pause.stdout)
        return

thread = threading.Thread(target=probe, daemon=True)
thread.start()
try:
    env = {"ABOOK_PREFERENCES": str(fixture / "prefs.json"),
           "ABOOK_HOST_PYTHON": "D:/Novels/ABook/_internal/runtime/.venv/Scripts/pythonw.exe",
           "ABOOK_HOST_APP": str(root.parent), "ABOOK_BENCH_SCENARIO": "player", "ABOOK_BENCH_BOOK": books["a"],
           "ABOOK_MUTE": "1", "ABOOK_SMTC": "1"}
    got = measure.launch(exe, env)
finally:
    stop.set()
    thread.join(12)
text = "\n".join(observed)
markers = [n for _, n in got.get("d", {}).get("events", []) if n.startswith("smtc_command:")]
text += "\n" + json.dumps({"ok": got.get("ok"), "why": got.get("why"), "foreground_events": got.get("foreground_events"),
                           "offscreen": got.get("offscreen"), "commands": markers}, ensure_ascii=False)
(folder / "app_probe_output.txt").write_text(text, encoding="utf-8")
print(text)
assert got.get("ok") and observed and "TryPauseAsync=1" in text and "smtc_command:1:playing=0" in markers
