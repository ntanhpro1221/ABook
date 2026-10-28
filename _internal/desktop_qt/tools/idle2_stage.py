"""Round 2 component stages. Immutable executables and full hidden120 raw evidence."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import statistics
import uuid
import measure
import idle_ab
from hidden_suite import wait_for_machine
from measure_mini import reset

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build/idlecpu2-evidence"
class SharedMachineBusy(RuntimeError):
    pass


def dump(path, value):
    path.write_text(json.dumps(value, indent=1), encoding="utf-8", newline="\n")


def summary(got):
    events = {n: t + got["d"]["epoch_offset_ms"] for t,n in got["d"]["events"]}
    begin,end = events["hide_begin"]+5000,events["hide_end"]
    memory = [x for x in got["memory_samples"] if begin <= x[0] <= end]
    if len(memory)<100: raise RuntimeError("Missing settled samples")
    dt = (memory[-1][0]-memory[0][0])/1000
    series = [(t,rows) for t,rows in got["thread_samples"] if begin<=t<=end]
    tids = {r["id"] for _,rows in series for r in rows}
    threads=[]
    for tid in tids:
        samples=[(t,r) for t,rows in series for r in rows if r["id"]==tid]
        first,last=samples[0],samples[-1]
        threads.append(dict(identity=last[1], cpu_core_pct=(last[1]["cpu_s"]-first[1]["cpu_s"])/dt*100,
            scheduler_dispatches_s=(last[1]["context_switches"]-first[1]["context_switches"])/dt,
            partial_lifetime=len(samples)!=len(series)))
    trace=Path(got["app_log"]).read_text(encoding="utf-8",errors="replace")
    raw_events={n:t for t,n in got["d"]["events"]}
    frames=got["d"]["frames"]
    waits={}
    for name in ("mix","reader"):
        points=[(int(t),int(n)) for t,n in re.findall(name+r"_wakes epoch_ms=(\d+) count=(\d+)",trace) if begin<=int(t)<=end]
        waits[name]=(points[-1][1]-points[0][1])/((points[-1][0]-points[0][0])/1000) if len(points)>1 else None
    return dict(steady_s=dt,cpu_core_pct=(memory[-1][3]-memory[0][3])/dt*100,
        private_commit_mb=statistics.median(x[1] for x in memory),working_set_mb=statistics.median(x[2] for x in memory),
        threads=sorted(threads,key=lambda r:r["cpu_core_pct"],reverse=True),wait_returns_s=waits,
        main_dispatcher_iterations=re.findall(r"idle_main_dispatcher_wakes=(\d+)",trace),
        timer_deliveries=re.findall(r"idle_timer (.+) count=(\d+)",trace),
        event_deliveries=re.findall(r"idle_event (.+) count=(\d+)",trace),
        device_empty=trace.count("mix_device_empty"),foreground_events=got["foreground_events"],
        battery_status_at_launch=got["battery_status_at_launch"],battery_status_at_end=got["battery_status_at_end"],
        shared_busy=got["shared_busy"],exe_sha256=got["exe_sha256"],
        visible_frames=sum(t<raw_events["hide_begin"] for t in frames),
        hidden_frames=sum(raw_events["hide_begin"]<=t<=raw_events["hide_end"] for t in frames),
        restored_frames=sum(t>raw_events["hide_end"] for t in frames),
        graphics_release_records=re.findall(r"graphics_idle_release .+",trace))


def run(label,exe,speed=1,native=False,event_audit=False):
    stage=OUT/label;stage.mkdir(parents=True,exist_ok=True)
    immutable=stage/"ABookDesk.exe"
    sha=hashlib.sha256(exe.read_bytes()).hexdigest()
    if immutable.exists() and hashlib.sha256(immutable.read_bytes()).hexdigest()!=sha:
        raise RuntimeError("Stage executable is immutable; choose a new label")
    if not immutable.exists():shutil.copyfile(exe,immutable)
    raw=stage/"raw.json"
    if raw.exists():
        old=json.loads(raw.read_bytes())
        if old.get("accepted"):
            print("KEEP",label,flush=True);return
        if old.get("shared_busy"): raise SharedMachineBusy("Previous contaminated attempt retained")
        raise RuntimeError("Previous unsuccessful stage retained; choose a new label")
    idle_ab.OUT=OUT
    fixture=idle_ab.prepare_fixture()
    data=json.loads((fixture/"_base/listening.json").read_bytes())
    for record in data["records"].values():record["state"]["rate"]=speed
    from abook.webui.listening_schema import clean_profiles
    cleaned=clean_profiles(data)
    if any(r["state"].get("rate")!=speed for r in cleaned["records"].values()):
        raise RuntimeError("Controlled rate did not survive listening schema validation")
    data=cleaned
    dump(fixture/"_base/listening.json",data)
    books=json.loads((fixture/"audio_books.json").read_bytes())
    qt=Path("D:/Novels/native_desk_proto/qt611/6.10.3/msvc2022_64")
    local=stage/"local";local.mkdir(exist_ok=True)
    env=dict(ABOOK_PREFERENCES=str(fixture/"prefs.json"),ABOOK_HOST_PYTHON="D:/Novels/ABook/_internal/runtime/.venv/Scripts/python.exe",
        ABOOK_HOST_APP=str(ROOT.parent),ABOOK_BENCH_SCENARIO="mini",ABOOK_BENCH_BOOK=books["a"],
        ABOOK_MUTE="1",ABOOK_AUDIO_TRACE="1",ABOOK_IDLE_AUDIT="1",ABOOK_SMTC="1",LOCALAPPDATA=str(local),
        QT_SCALE_FACTOR="1",QT_QPA_PLATFORM="windows" if native else "offscreen",QT_QUICK_BACKEND="rhi" if native else "software",
        ABOOK_BENCH_HIDDEN_DESKTOP="1",QT_QPA_FONTDIR=str(ROOT/"fonts"),QT_QPA_PLATFORM_PLUGIN_PATH=str(qt/"plugins/platforms"),
        PATH=str(qt/"bin")+os.pathsep+os.environ["PATH"])
    # Direct probes resolve thread starts as in idlecpu. Module lists stay diagnostic only.
    if native:env.update(ABOOK_CAPTURE_MODULES="1",QT_LOGGING_RULES="qt.scenegraph.renderloop.debug=true;qt.rhi.general.debug=true;qt.qpa.screen.updates.debug=true")
    if event_audit:env["ABOOK_IDLE_EVENTS"]="1"
    wait=wait_for_machine();reset(fixture);(fixture/"listening.json.journal").write_bytes(b"")
    print("START",label,sha,"speed",speed,"wait",wait["seconds"],flush=True)
    got=measure.launch(immutable.resolve(),env,True,timeout_seconds=190)
    got.update(label=label,speed=speed,native=native,machine_wait=wait,exe_sha256=sha)
    if got.get("app_log"):
        shutil.copyfile(got["app_log"],stage/"app.log");got["app_log"]=str(stage/"app.log")
    if got.get("ok"):
        ev={n:t for t,n in got["d"]["events"]}
        audio={}
        for n in ev:
            if n.startswith("audio:"):
                _,tag,ch,pos,playing=n.split(":");audio[tag]=dict(chapter=int(ch),position=float(pos),playing=int(playing))
        wall=(ev["hide_end"]-ev["hide_begin"])/1000
        media=audio["hide_end"]["position"]-audio["hide_begin"]["position"]
        trace=(stage/"app.log").read_text(encoding="utf-8",errors="replace")
        got.update(hidden_wall_s=wall,hidden_media_s=media,audio=audio)
        got["desktop_pass"] = bool(got.get("desktop_verified_before_resume")) and got.get("actual_thread_desktop")==[got.get("desktop_verified_before_resume")]
        frames=got["d"]["frames"]
        got["native_render_pass"] = not native or (any(f<ev["hide_begin"] for f in frames)
            and any(f>ev["hide_end"] for f in frames) and not any(ev["hide_begin"]+5000<=f<=ev["hide_end"] for f in frames))
        markers=[n for _,n in got["d"]["events"]]
        got["accepted"]=(got["exit_code"]==0 and not got["forced_termination"] and got["foreground_events"]==0
            and not got["shared_busy"] and abs(media-wall*speed)<0.1 and wall>=120 and all(v["playing"] for v in audio.values())
            and "mix_device_empty" not in trace and "mix_playing" in markers and "mix_failed" not in markers
            and got["desktop_pass"] and got["native_render_pass"])
    dump(raw,got)
    if got.get("shared_busy"): raise SharedMachineBusy("Foreign workload started during stage; raw retained")
    if not got.get("accepted"):raise RuntimeError("Unaccepted stage: raw retained "+str(raw))
    result=summary(got);result.update(hidden_wall_s=wall,hidden_media_s=media,speed=speed,native=native,event_audit=event_audit)
    dump(stage/"summary.json",result)
    from idle2_report import refresh
    refresh()
    print("RESULT",label,{k:v for k,v in result.items() if k not in {"threads","timer_deliveries"}},flush=True)


if __name__=="__main__":
    ap=argparse.ArgumentParser();ap.add_argument("label");ap.add_argument("--exe",type=Path,default=ROOT/"dist/ABookDesk.exe")
    ap.add_argument("--speed",type=float,default=1);ap.add_argument("--native",action="store_true")
    ap.add_argument("--event-audit",action="store_true",help="separate diagnostic; count Qt event targets without adding a timer")
    a=ap.parse_args();label=a.label
    while True:
        try:
            run(label,a.exe,a.speed,a.native,a.event_audit)
            break
        except SharedMachineBusy as exc:
            print("REQUEUE",str(exc),label,flush=True)
            label=a.label+"-retry-"+uuid.uuid4().hex[:8]
