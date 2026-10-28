"""Build/run the offline decoder profile under the existing owner-safe guard."""
from pathlib import Path
import hashlib
import json
import os
import sys
import subprocess
from guarded_process import run_guarded
from hidden_suite import wait_for_machine

root=Path(__file__).resolve().parents[1]
label=sys.argv[1]
out=root/"build/idlecpu2-evidence"/label
out.mkdir(parents=True,exist_ok=True)
qt="D:/Novels/native_desk_proto/qt611/6.10.3/msvc2022_64"
env=dict(os.environ,QT_QPA_PLATFORM="offscreen",PATH=qt+"/bin"+os.pathsep+os.environ["PATH"])
bat=out/"profile-build.bat"
bat.write_bytes(('call "C:/Program Files/Microsoft Visual Studio/18/Community/VC/Auxiliary/Build/vcvars64.bat" >nul\n'
    'set PATH=D:/Novels/native_desk_proto/qt/Tools/Ninja;%PATH%\n'
    f'"D:/Novels/native_desk_proto/qt/Tools/CMake_64/bin/cmake.exe" -S "{root}/tools/decode_profile" -B "{root}/build/decode_profile" -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH="{qt}"\n'
    'if errorlevel 1 exit /b 1\n'
    f'"D:/Novels/native_desk_proto/qt/Tools/CMake_64/bin/cmake.exe" --build "{root}/build/decode_profile"\n'
    'exit /b %errorlevel%\n').replace('\n','\r\n').encode())
wait_for_machine()
with (out/"build.log").open("wb") as log:audit=run_guarded(["cmd.exe","/d","/c",str(bat)],cwd=root,env=env,log=log)
(out/"build-audit.json").write_text(json.dumps(audit,indent=2),encoding="utf-8",newline="\n")
if audit["exit_code"]:raise SystemExit(audit["exit_code"])
exe=root/"build/decode_profile/DecodeProfile.exe"
def ac():
    got=subprocess.run(["powershell.exe","-NoProfile","-NonInteractive","-Command","(Get-CimInstance Win32_Battery).BatteryStatus"],capture_output=True,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
    values=[int(x) for x in got.stdout.split() if x.isdigit()]
    if values!=[2]:raise RuntimeError("Missing required BatteryStatus=2: "+str(values))
    return values
for i in range(1,4):
    wait=wait_for_machine()
    before=ac()
    with (out/f"profile-{i}.log").open("wb") as log:
        audit=run_guarded([str(exe),"D:/Novels/Audiobooks/book2/_book/001.mp3",str(out/f"profile-{i}.json")],cwd=root,env=env,log=log)
    audit.update(machine_wait=wait,battery_status_at_launch=before,battery_status_at_end=ac(),exe_sha256=hashlib.sha256(exe.read_bytes()).hexdigest())
    (out/f"audit-{i}.json").write_text(json.dumps(audit,indent=2),encoding="utf-8",newline="\n")
    if audit["exit_code"]:raise SystemExit(audit["exit_code"])
    print("PROFILE",label,i,flush=True)
