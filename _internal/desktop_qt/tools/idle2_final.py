"""Resume the final round-2 verification after the guarded full build succeeds."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'build/idlecpu2-evidence'
PY='D:/Novels/ABook/_internal/runtime/.venv/Scripts/python.exe'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,d):p.write_text(json.dumps(d,indent=2),encoding='utf-8',newline='\n')
def run(script,*args):
    print('JOB',script,args,flush=True)
    with (OUT/('final-'+script+'.log')).open('ab') as log:
        code=subprocess.call([PY,'-X','utf8',str(ROOT/'tools'/script),*map(str,args)],stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
    if code:raise RuntimeError(f'{script}: exit {code}; inspect final log')

def main():
    audit=ROOT/'build/hidden-evidence/build-idlecpu2-final-audit.json'
    while not audit.exists():time.sleep(2)
    result=json.loads(audit.read_bytes())
    if result['exit_code'] or result['foreground_events']:raise RuntimeError('Final full build failed')
    if not result.get('desktop_verified_before_resume'):raise RuntimeError('Build desktop was not verified')
    final=OUT/'final';final.mkdir(exist_ok=True)
    exe=ROOT/'dist/ABookDesk.exe';digest=sha(exe)
    if sha(ROOT/'build/ABookDesk.exe')!=digest:raise RuntimeError('build/dist differ')
    preserved=final/'ABookDesk.exe'
    if preserved.exists() and sha(preserved)!=digest:raise RuntimeError('Final artifact is immutable')
    if not preserved.exists():shutil.copyfile(exe,preserved)
    paths=[p for folder in ['src','tests','qml'] for p in (ROOT/folder).rglob('*') if p.is_file()]
    paths += [ROOT/'CMakeLists.txt',ROOT/'build.bat']
    manifest={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in paths}
    old=final/'source-manifest.json'
    if old.exists() and json.loads(old.read_bytes())!=manifest:raise RuntimeError('Final source changed')
    dump(old,manifest)
    dump(final/'provenance.json',dict(exe_sha256=digest,build_audit=str(audit)))
    paired=OUT/'paired';(paired/'baseline').mkdir(parents=True,exist_ok=True)
    baseline=OUT/'baseline/ABookDesk.exe'
    if sha(baseline)!='0d51d12c061705a82fd691e671586d8c54d96f794bb6df998c92e965b20a9d0f':raise RuntimeError('Wrong HEAD baseline')
    a=paired/'baseline/ABookDesk.exe'
    if a.exists() and sha(a)!=sha(baseline):raise RuntimeError('Paired baseline changed')
    if not a.exists():shutil.copyfile(baseline,a)
    run('idle_ab.py','--evidence',paired,'--rounds','4','--resume')
    rows=json.loads((paired/'ab.json').read_bytes())
    if len(rows)!=8 or any(d['exe_sha256']!=(sha(baseline) if d['label']=='A' else digest) for d in rows):raise RuntimeError('A/B provenance mismatch')
    run('idle2_stage.py','stage6-final-x1','--exe',preserved)
    run('idle2_stage.py','stage6-final-native','--exe',preserved,'--native','--event-audit')
    run('idle2_report.py')
    print('FINAL RUNTIME VERIFICATION COMPLETE',digest,flush=True)

if __name__=='__main__':main()
