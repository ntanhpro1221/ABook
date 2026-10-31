"""Resumeable baseline capture. It never edits production source."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"build/idlecpu2-evidence"
audit=ROOT/"build/hidden-evidence/build-idlecpu2-baseline-audit.json"
while not audit.exists():time.sleep(2)
if json.loads(audit.read_bytes())["exit_code"]:raise RuntimeError("Baseline build failed")
initial=json.loads((OUT/"initial-source.json").read_bytes())
for path,sha in initial.items():
    if hashlib.sha256((ROOT.parents[1]/path).read_bytes()).hexdigest()!=sha:raise RuntimeError("Baseline source changed: "+path)
exe=ROOT/"dist/ABookDesk.exe"
target=OUT/"baseline";target.mkdir(exist_ok=True)
shutil.copyfile(exe,target/"ABookDesk.exe")
(target/"provenance.json").write_text(json.dumps(dict(head="ca49185705be9d3aef2973caa44eeab6f5a1ae35",exe_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),build_audit=str(audit)),indent=2),encoding="utf-8",newline="\n")
python="D:/Novels/ABook/_internal/runtime/.venv/Scripts/python.exe"
jobs=[("idle2_profile.py","profile-A"),("idle2_stage.py","stage0-A-x1","--exe",str(target/"ABookDesk.exe")),
      ("idle2_stage.py","stage0-A-x15","--exe",str(target/"ABookDesk.exe"),"--speed","1.5"),
      ("idle2_stage.py","stage0-A-native","--exe",str(target/"ABookDesk.exe"),"--native")]
for script,*args in jobs:
    with (OUT/("baseline-"+args[0]+".log")).open("wb") as log:
        code=subprocess.call([python,"-X","utf8",str(ROOT/"tools"/script),*args],stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
    if code:raise SystemExit(code)
