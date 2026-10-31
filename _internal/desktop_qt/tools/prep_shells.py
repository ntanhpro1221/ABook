"""prep_shells.py <int150 _internal> <rel437 _internal> <out>: two packaged layouts with the SAME embedded Python.

out/tauri = rel437 shell exe + its resources/{python,app}   (what the 0.4.133 installer puts on disk)
out/qt    = int150 Qt dist + resources/python (same Python) + resources/app (int150 abook, Copy-App rules)
"""
import shutil
import subprocess
import sys
from pathlib import Path

int150, rel437, out = (Path(a) for a in sys.argv[1:4])
which = sys.argv[4] if len(sys.argv) > 4 else "both"
tauri_src = rel437 / "shell/src-tauri"
tauri, qt = out / "tauri", out / "qt"
for target in (tauri, qt):
    if target.exists() and which in (target.name, "both"):
        shutil.move(str(target), str(out / f"_old_{target.name}_{len(list(out.glob('_old_*')))}"))

if which in ("tauri", "both"):
    tauri.mkdir(parents=True)
    shutil.copy2(tauri_src / "target/release/ABook.exe", tauri / "ABook.exe")
    shutil.copytree(tauri_src / "resources", tauri / "resources")
if which == "tauri":
    sys.exit(0)

shutil.copytree(int150 / "desktop_qt/dist", qt)
shutil.copytree(tauri_src / "resources/python", qt / "resources/python")
app = qt / "resources/app"
studio_only = {"cmudict.dict", "voice_previews"}
shutil.copytree(int150 / "abook", app / "abook",
                ignore=lambda d, names: [n for n in names if n == "__pycache__" or n in studio_only or n.endswith(".pyc")])
for name in ("pyproject.toml", "uv.lock", "LICENSE"):
    if (int150 / name).exists():
        shutil.copy2(int150 / name, app / name)
shutil.copy2(int150 / "shell/python/studio-requirements.txt", app)
shutil.copytree(tauri_src / "resources/app/vcruntime", app / "vcruntime")
subprocess.run([str(qt / "resources/python/python.exe"), "-m", "compileall", "-q", "-j", "0", str(app / "abook")],
               check=True, creationflags=0x08000000)
for target in (tauri, qt):
    size = sum(p.stat().st_size for p in target.rglob("*") if p.is_file())
    print(target.name, f"{size / 1e6:.1f} MB")
