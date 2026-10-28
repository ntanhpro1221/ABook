"""Refresh round 2 evidence tables without launching anything; retain round 1 verbatim."""
import json
from pathlib import Path
import re
import statistics

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"build/idlecpu2-evidence"
read=lambda p:json.loads(p.read_bytes())
def median(items,key):return statistics.median(x[key] for x in items)
def group(d,name):return sum(r["cpu_core_pct"] for r in d["threads"] if name in r["identity"].get("name",""))
def inventory():
    lines=['# Timer and wake call sites in final source','',
        'This is a complete text call-site inventory for production src/ and QML Timer declarations. It is not a claim that every site fires in the benchmark. Configured sleep/fades, in-flight requests, source buffering, jobs and shutdown may legitimately dispatch while hidden. Runtime event targets/counts are retained separately in the native event audits.','',
        '## C++ timers, deadlines and condition-variable waits','']
    for p in sorted((ROOT/'src').glob('*')):
        if p.suffix not in {'.cpp','.h'}:continue
        for n,line in enumerate(p.read_text(encoding='utf-8').splitlines(),1):
            if re.search(r'QTimer|\.setInterval\(|\bstartTimer\(|wait_for\(|readerCv\.wait|mixCv\.wait',line):
                lines.append(f'- `{p.name}:{n}`: `{line.strip()}`')
    lines += ['', '## QML Timer declarations and nearby source', '']
    for p in sorted((ROOT/'qml').rglob('*.qml')):
        source=p.read_text(encoding='utf-8').splitlines()
        for n,line in enumerate(source):
            if re.search(r'\bTimer\s*\{',line):
                lines += [f'### {p.name}:{n+1}', '', '```qml', *source[n:n+14], '```', '']
    (OUT/'timer-wake-inventory.md').write_text('\n'.join(lines),encoding='utf-8',newline='\n')
def refresh():
    inventory()
    from idle_report import enrich, symbol
    verification=OUT/'final-verification.json'
    symbols_path=OUT/'symbols-final.json'
    symbols={(Path(s['module']).name.lower(),s['module_offset']):s for s in read(symbols_path)} if symbols_path.exists() else {}
    all_threads=[]
    baseline=read(OUT/"baseline/provenance.json")
    lines=["# Round 2 - minimized playback CPU", "", "**In progress. Target <=0.15% of one core is not yet established. No commits; Lead reviews.**", "",
        "A is rebuilt HEAD `ca49185705be9d3aef2973caa44eeab6f5a1ae35`, SHA `"+baseline["exe_sha256"]+"`. The guarded offscreen baseline full build passed 765 tests, 0 failed, 1 existing intentional glyph skip. **Isolation correction:** the inherited subprocess launcher did not marshal lpDesktop. Native test attempts were rejected on activation; accepted software runs used offscreen Qt with zero foreground events. The new native launcher verifies its actual startup desktop before resume; a no-window child independently confirms the assigned private desktop. Earlier private-desktop metadata is not proof of isolation. See the correction below. Locked quality hash verified `c91761232204fedd1052a507682d1eacf53c20275e1b81389a819b4b39de9886`; no `_internal/abook/` changes.", "",
        "Actual HEAD uses a shared WASAPI buffer of 1 second, a 500 ms lead and padding-based timer scheduling. Fresh x1.0 TimeStretch already bypasses Sonic; the final decoder creates Sonic lazily, borrows compressed frame bytes with QByteArrayView, bulk-copies stereo PCM and uses larger bounded hidden refills. The PCM ring remains 2 seconds at source speed.", "",
        "## Component stages", "", "Each successive accepted runtime stage changes one component. These individual 120-second samples identify costs but do not establish statistical improvement by themselves. Final four alternating A/B pairs appear below. CPU is elapsed kernel+user time divided by wall time, percent of **one core**. RAM is MiB. Private driver dispatch counts are scheduler dispatches, not exact wake counts.", "",
        "| Stage | Speed | CPU % | Decode % | Render % | Main % | Private MiB | WS MiB | Wall / media s |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    thread_lines=["# Round 2 full per-thread evidence", "", "CPU denominator is the settled process slice; partial thread lifetimes are marked. Scheduler dispatches include preemption. Start symbols can be nearest exports, with offsets retained; they are not automatically actual callback names.", ""]
    summaries=[]
    for folder in sorted(OUT.glob("stage*")):
        path=folder/"summary.json"
        if not path.exists():continue
        d=read(path);summaries.append((folder.name,d))
        rows=[dict(t,id=t['identity']['id'],name=t['identity'].get('name','')) for t in d['threads']]
        d['threads']=enrich(rows,read(folder/'raw.json'),folder/'ABookDesk.exe')
        all_threads.append(dict(label=folder.name,threads=d['threads']))
        lines.append(f"| [{folder.name}](_internal/desktop_qt/build/idlecpu2-evidence/{folder.name}/summary.json) | {d['speed']:g} | {d['cpu_core_pct']:.6f} | {group(d,'audio decode'):.6f} | {group(d,'audio render'):.6f} | {group(d,'ABook main'):.6f} | {d['private_commit_mb']:.2f} | {d['working_set_mb']:.2f} | {d['hidden_wall_s']:.3f} / {d['hidden_media_s']:.3f} |")
        thread_lines += ["## "+folder.name,"",f"Executable SHA `{d['exe_sha256']}`. Settled {d['steady_s']:.3f} s. Render/reader wait returns/s: {d['wait_returns_s']}. AC {d['battery_status_at_launch']}/{d['battery_status_at_end']}; zero foreground/starvation/shared-workload events.","",
            "| TID | Name | CPU % | Dispatch/s | Lifetime | Start owner + RVA | Symbol + displacement |",
            "|---:|---|---:|---:|---|---|---|"]
        for row in d["threads"]:
            i=row["identity"]
            resolved=symbol(i,symbols) if symbols else 'unresolved; nearest export '+i.get('symbol','?')+'+'+str(i.get('symbol_offset','?'))
            thread_lines.append(f"| {i['id']} | {i.get('name','')} | {row['cpu_core_pct']:.6f} | {row['scheduler_dispatches_s']:.3f} | {'partial' if row['partial_lifetime'] else 'complete'} | {Path(i.get('module','?')).name}+{i.get('module_offset','?')} | {resolved} |")
        thread_lines += ["", "Timer deliveries: `"+json.dumps(d["timer_deliveries"],ensure_ascii=False)+"`", ""]
    lines += ["", "All accepted rows require BatteryStatus 2 at launch/end, sampled AC throughout, no foreign build/test activity, zero foreground events, normal exit, zero endpoint-empty warnings and continuous playback. Raw samples, immutable executables and app logs are beside each summary. The first `stage0-A-x15` attempt was rejected: the seed fixture had stale book links and actually played at x1.0. Its raw data remains; corrected fixture links are verified by media/wall rate.", "",
        "## Offline decode profiles", "", "Continuous offline component timing uses the real chapter, 6 complete passes per speed and a separate untimed PCM-hash pass. It excludes networking, music, device output and idle-frequency behavior; do not present it as deployed CPU.", "",
        "| Profile | x1 CPU % | x1.5 CPU % | x1 decoder wall s | x1.5 Sonic wall s |",
        "|---|---:|---:|---:|---:|"]
    for folder in sorted(OUT.glob("profile-*")):
        rows=[read(p)["results"] for p in folder.glob("profile-[123].json")]
        if not rows:continue
        a=[r[0] for r in rows];b=[r[1] for r in rows]
        lines.append(f"| {folder.name} ({len(rows)} runs) | {median(a,'cpu_core_pct_per_media'):.6f} | {median(b,'cpu_core_pct_per_media'):.6f} | {median(a,'decoder_wall_s'):.6f} | {median(b,'stretch_wall_s'):.6f} |")
    lines += ["", "## Component comparisons", "", "Each row is an isolated source stage and a single 120-second sample on each side. Positive CPU delta means more measured CPU. These deltas are not statistical estimates; the repeated renderer measurement shows the run-to-run variation. Wait returns are actual app counters, not inferred scheduler dispatches.", "",
        "| Component | Before | After | CPU delta, percentage points | Render waits/s before -> after |",
        "|---|---:|---:|---:|---|"]
    comparisons=[('Decode','stage0-A-x1-controlled','stage1-decode-x1'),
        ('Render, 500-ms hidden deadline','stage1-decode-x1','stage2-render-x1'),
        ('Render, coalesced refill and 750-ms deadline','stage2-render-x1','stage2b-render-x1'),
        ('Renderer repeat on corrected launcher','stage2b-render-x1','stage2b-render-verified-x1'),
        ('30-second hidden persistence','stage2b-render-verified-x1','stage3-main-x1'),
        ('Graphics release, native D3D','stage3-native-before','stage4-native-after'),
        ('Audio-thread QoS experiment','stage4-graphics-x1','stage5-qos-x1'),
        ('Compressed-source fetch batching','stage7-before1','stage7-after1')]
    for title,a,b in comparisons:
        pa,pb=OUT/a/'summary.json',OUT/b/'summary.json'
        if not pa.exists() or not pb.exists():continue
        x,y=read(pa),read(pb)
        lines.append(f"| {title} | {x['cpu_core_pct']:.6f} | {y['cpu_core_pct']:.6f} | {y['cpu_core_pct']-x['cpu_core_pct']:+.6f} | {x['wait_returns_s']['mix']:.3f} -> {y['wait_returns_s']['mix']:.3f} |")
    notes=OUT/"round2-notes.md"
    if notes.exists(): lines += ["",notes.read_text(encoding="utf-8")]
    paired_dir=OUT/'paired'
    pairs=paired_dir/'ab.json'
    if pairs.exists():
        paired=read(pairs)
        lines += ["", "## Final alternating pairs", "", "Same idlecpu player scenario, real chapter 1 with music, first 5 seconds after minimize excluded. These short CPU-time windows are quantized in Windows accounting ticks. Native D3D probes are separate from the software A/B protocol.", "",
            "| Order | Round | Variant | Steady s | CPU % one core | Cycles/TSC proxy % | Private MiB | WS MiB |",
            "|---:|---:|---|---:|---:|---:|---:|---:|"]
        for i,d in enumerate(paired,1):
            f=lambda key: "unavailable" if d.get(key) is None else f"{d[key]:.3f}"
            lines.append(f"| {i} | {d['round']} | {d['label']} | {d['steady_s']:.3f} | {d['cpu_core_pct']:.6f} | {d['cycles_core_pct']:.6f} | {d['private_commit_mb']:.2f} | {d['working_set_mb']:.2f} |")
        for v in "AB":
            ds=[d for d in paired if d['label']==v]
            if ds: lines.append(f"| Median | | {v} | | **{median(ds,'cpu_core_pct'):.6f}** | **{median(ds,'cycles_core_pct'):.6f}** | **{median(ds,'private_commit_mb'):.2f}** | **{median(ds,'working_set_mb'):.2f}** |")
        lines += ['', 'Cycles/TSC is a frequency-dependent proxy, not elapsed CPU time. One 15.625-ms Windows CPU accounting tick is about 0.106 percentage point in these settled slices. Private commit and total working set are ABookDesk only; host Python and OS audio service are excluded.', '',
            '| Round | Variant | Render wait returns/s | Reader wait returns/s | Main dispatcher iterations/s |',
            '|---:|---|---:|---:|---:|']
        for d in paired:
            f=lambda key:'unavailable' if d.get(key) is None else f"{d[key]:.3f}"
            lines.append(f"| {d['round']} | {d['label']} | {f('render_wakes_s')} | {f('reader_wakes_s')} | {f('main_dispatcher_iterations_s')} |")
        lines += ['', 'Wait-return counters are app loop returns, including control/spurious work. Main counts Qt dispatcher iterations over the entire minimized interval; CPU and audio counters use the settled slice. Native thread tables report scheduler dispatches, which also include preemption.', '']
        # Include every captured lifetime, not only the first/last intersection.
        from idle_report import include_transient_threads, enrich
        full=[]
        for d in paired:
            raw=read(paired_dir/f"raw-{d['round']}-{d['label']}.json")
            assert raw['ok'] and raw['exit_code']==0 and not raw['shared_busy'] and not raw['foreground_events']
            assert raw['battery_status_at_launch']==raw['battery_status_at_end']==[2] and {p[1] for p in raw['power_samples']}=={1}
            ev={n:t+raw['d']['epoch_offset_ms'] for t,n in raw['d']['events']}
            include_transient_threads(d,raw,ev['min_begin']+5000,ev['min_end'])
            exe=OUT/("baseline/ABookDesk.exe" if d['label']=='A' else 'final/ABookDesk.exe')
            d['threads']=enrich(d['threads'],raw,exe);full.append(d);all_threads.append(d)
            thread_lines += ["## Pair "+str(d['round'])+" "+d['label'],"",f"Executable SHA `{d['exe_sha256']}`.","",
                "| TID | Name | CPU % | Dispatch/s | Lifetime | Start owner + RVA |",
                "|---:|---|---:|---:|---|---|"]
            for t in d['threads']:
                ident=t['identity']
                thread_lines.append(f"| {t['id']} | {t['name']} | {t['cpu_core_pct']:.6f} | {t['scheduler_dispatches_s']:.3f} | {t.get('coverage','complete')} | {Path(ident.get('module','?')).name}+{ident.get('module_offset','?')} |")
            thread_lines += [""]
        (paired_dir/'threads-final.json').write_text(json.dumps(full,indent=1),encoding='utf-8',newline='\n')
    (OUT/'threads-final.json').write_text(json.dumps(all_threads,indent=1),encoding='utf-8',newline='\n')
    if verification.exists():
        v=read(verification)
        lines += ["", "## Final verification", "", v['summary'], "", "Quality implementation SHA `"+v['quality_hash']+"`. HEAD `"+v['head']+"`; no commit. Final B SHA `"+v['exe_sha256']+"`. Full-build audit, source manifest and validation details are in [final-verification.json](_internal/desktop_qt/build/idlecpu2-evidence/final-verification.json)."]
        if pairs.exists() and len(paired)==8:
            b=[d for d in paired if d['label']=='B']
            long=read(OUT/v['hidden_summary'])
            target_met=median(b,'cpu_core_pct')<=0.15 and long['cpu_core_pct']<=0.15
            lines[2]=f"**{'Measured CPU target met' if target_met else 'CPU target missed'}. B median {median(b,'cpu_core_pct'):.6f}% of one core; final long hidden slice {long['cpu_core_pct']:.6f}%. No commits; Lead reviews.**"
    lines += ["", "Current status and continuation notes are in [_internal/desktop_qt/PROGRESS.md](_internal/desktop_qt/PROGRESS.md). Full stage thread tables: [thread-tables.md](_internal/desktop_qt/build/idlecpu2-evidence/thread-tables.md).", "", "---", "", "# Round 1 (preserved)", "", (OUT/"initial-report.md").read_text(encoding="utf-8")]
    (ROOT.parents[1]/"report.md").write_text("\n".join(lines),encoding="utf-8",newline="\n")
    (OUT/"thread-tables.md").write_text("\n".join(thread_lines),encoding="utf-8",newline="\n")
    print("Refreshed",len(summaries),"accepted stages")

if __name__=="__main__":refresh()
