"""Run selected existing test executables safely; does not rebuild or modify output paths."""
from pathlib import Path
import json
import os
import sys
from guarded_process import run_guarded
from hidden_suite import wait_for_machine
root=Path(__file__).resolve().parents[1]
label=sys.argv[1]
out=root/"build/idlecpu2-evidence"/label;out.mkdir(parents=True,exist_ok=True)
qt="D:/Novels/native_desk_proto/qt611/6.10.3/msvc2022_64"
native="--native" in sys.argv
env=dict(os.environ,QT_QPA_PLATFORM="windows" if native else "offscreen",PATH=qt+"/bin"+os.pathsep+os.environ["PATH"])
if native:env.update(ABOOK_GUARDED_NATIVE="1",QT_D3D_NO_VBLANK_THREAD="1")
for name in [arg for arg in sys.argv[2:] if arg!="--native"]:
    wait=wait_for_machine()
    with (out/(name+".log")).open("wb") as log:
        try:
            audit=run_guarded([str(root/"build"/(name+".exe")),"-o",str(out/(name+".txt"))+",txt"],cwd=root,env=env,log=log)
        except Exception as error:
            (out/(name+"-failure.json")).write_text(json.dumps(dict(error=str(error)),indent=2),encoding="utf-8",newline="\n")
            raise
    audit["machine_wait"]=wait
    (out/(name+"-audit.json")).write_text(json.dumps(audit,indent=2),encoding="utf-8",newline="\n")
    print(name,audit,flush=True)
    if audit["exit_code"]:raise SystemExit(audit["exit_code"])
