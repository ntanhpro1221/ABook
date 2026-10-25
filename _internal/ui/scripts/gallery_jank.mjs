// node scripts/gallery_jank.mjs --dist <gallery> --out <results> [--only player,sort,reader,sheet,cold-player,cold-reader]
// Cùng cửa sổ 600 ms từ lần chạm, không finish hoạt ảnh hay bỏ lượt đầu khỏi số đo.
import { mkdirSync, writeFileSync, readFileSync, readdirSync } from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { createHash } from 'node:crypto';
import { parseArgs, findBrowser, serve, launch, connect, evaluate, openPage, waitUntil, STILL } from './gallery_browser.mjs';

export const percentile = (values, q) => values.length ? [...values].sort((a,b) => a-b)[Math.ceil(values.length*q)-1] : 0;
export function frameStats(intervals) {
  return { frames: intervals.length, janky: intervals.filter(ms => ms > 20).length, jankPct: intervals.length ? intervals.filter(ms => ms > 20).length*100/intervals.length : 0,
    p90: percentile(intervals, .9), p99: percentile(intervals, .99), max: Math.max(0, ...intervals) };
}
export function analyseTrace(events) {
  const marker = events.find(e => e.name === 'jank-start');
  if (!marker) throw new Error('Trace thiếu mốc chạm');
  const start = marker.ts, end = start + 600000;
  const main = events.find(e => e.name === 'thread_name' && e.pid === marker.pid && e.args?.name === 'CrRendererMain');
  const inside = e => e.ts >= start && e.ts < end;
  const nodes = new Map(), cpu = new Map(), samples=[];
  const profile=events.find(e=>e.pid===marker.pid && e.tid===(main?.tid ?? marker.tid) && e.name==='Profile');
  let sampleAt=profile?.args?.data?.startTime ?? start;
  for (const e of events.filter(e => e.pid === marker.pid && e.name === 'ProfileChunk' && e.id===profile?.id).sort((a,b)=>a.ts-b.ts)) {
    const data=e.args.data;
    for (const node of data.cpuProfile?.nodes ?? []) nodes.set(node.id,node);
    for (const [i,id] of (data.cpuProfile?.samples ?? []).entries()) {
      const us=data.timeDeltas?.[i] ?? 0; sampleAt+=us;
      if(sampleAt>=start && sampleAt<end) { cpu.set(id,(cpu.get(id) ?? 0)+us); samples.push({id,ts:sampleAt,us}); }
    }
  }
  const stackOf=id=>{const stack=[];let node=nodes.get(id);for(let i=0;i<12 && node;i++,node=nodes.get(node.parent))stack.push(node.callFrame);return stack;};
  const duration = e => (e.dur ?? 0)/1000;
  const brief = e => ({ name: e.name, at: (e.ts-start)/1000, ms: duration(e), data: e.args?.data ?? e.args?.beginData ?? {},
    children: events.filter(c => c.pid === e.pid && c.tid === e.tid && c.ph === 'X' && c !== e && c.ts >= e.ts && c.ts+(c.dur ?? 0) <= e.ts+e.dur && c.dur >= 2000)
      .sort((a,b) => b.dur-a.dur).slice(0,12).map(c => ({ name:c.name, ms:duration(c), data:c.args?.data ?? c.args?.beginData ?? {} })) });
  const renderer = events.filter(e => e.pid === marker.pid && e.tid === (main?.tid ?? marker.tid) && inside(e) && e.ph === 'X');
  // ProfileChunk giữ cây callFrame và mẫu CPU trong trace gốc; JS stack trực tiếp ở FunctionCall/EventDispatch.
  return { mainThread: { pid: marker.pid, tid: main?.tid ?? marker.tid },
    longTasks: renderer.filter(e => e.name === 'RunTask' && e.dur >= 20000).sort((a,b) => b.dur-a.dur).slice(0,8).map(e=>{
      const weights=new Map();for(const s of samples.filter(s=>s.ts>=e.ts && s.ts<e.ts+e.dur))weights.set(s.id,(weights.get(s.id)??0)+s.us);
      return {...brief(e),cpuStacks:[...weights].sort((a,b)=>b[1]-a[1]).slice(0,5).map(([id,us])=>({selfMs:us/1000,stack:stackOf(id)}))};
    }),
    cpuStacks: [...cpu].sort((a,b)=>b[1]-a[1]).slice(0,20).map(([id,us]) => ({selfMs:us/1000,stack:stackOf(id)})),
    expensive: renderer.filter(e => /UpdateLayoutTree|Layout$|FunctionCall|EventDispatch|Paint$|PrePaint/.test(e.name) && e.dur >= 2000).sort((a,b) => b.dur-a.dur).slice(0,18).map(brief),
    gpu: events.filter(e => inside(e) && /GPUTask|RasterTask/.test(e.name) && e.dur >= 2000).sort((a,b) => b.dur-a.dur).slice(0,8).map(brief),
    style: renderer.filter(e => e.name === 'UpdateLayoutTree').map(e => ({ at:(e.ts-start)/1000, ms:duration(e), elements:e.args?.elementCount ?? e.args?.data?.elementCount ?? e.args?.beginData?.elementCount, ...e.args })),
    profileChunks: events.filter(e => e.name === 'ProfileChunk').length };
}

async function traceConnection(endpoint, stacks) {
  const ws = new WebSocket(endpoint); await new Promise(resolve => ws.addEventListener('open', resolve, { once:true }));
  let next = 0, events = [], complete;
  const pending = new Map();
  ws.addEventListener('message', ({data}) => {
    const m = JSON.parse(data);
    if (m.method === 'Tracing.dataCollected') events.push(...m.params.value);
    if (m.method === 'Tracing.tracingComplete') complete?.();
    if (pending.has(m.id)) { const p = pending.get(m.id); pending.delete(m.id); m.error ? p.reject(new Error(m.error.message)) : p.resolve(m.result); }
  });
  const send = (method, params = {}) => new Promise((resolve,reject) => { const id=++next; pending.set(id,{resolve,reject}); ws.send(JSON.stringify({id,method,params})); });
  return { start: async () => { events=[]; await send('Tracing.start', { categories:'toplevel,devtools.timeline,disabled-by-default-devtools.timeline,disabled-by-default-devtools.timeline.frame,blink.user_timing,v8.execute,disabled-by-default-v8.cpu_profiler,gpu'+(stacks?',disabled-by-default-devtools.timeline.stack,disabled-by-default-devtools.timeline.invalidationTracking':''), transferMode:'ReportEvents' }); },
    end: async () => { const done = new Promise(resolve => { complete=resolve; }); await send('Tracing.end'); await done; return events; }, close:() => ws.close() };
}
const sleep = ms => new Promise(resolve => setTimeout(resolve,ms));
async function tap(cdp, session, label) {
  const point = await evaluate(cdp, session, `(() => { const label=${JSON.stringify(label)}; const el=[...document.querySelectorAll('button,a')].find(el => !el.closest('[inert],[aria-hidden=true]') && [el.getAttribute('aria-label'),el.textContent?.trim()].some(name=>name && (label.startsWith('^')?name.startsWith(label.slice(1)):name===label))); if (!el) throw Error('Không thấy nút '+label); const r=el.getBoundingClientRect(); return {x:r.x+r.width/2,y:r.y+r.height/2}; })()`);
  await cdp.send('Input.dispatchTouchEvent', { type:'touchStart',touchPoints:[point] },session);
  await cdp.send('Input.dispatchTouchEvent', { type:'touchEnd',touchPoints:[] },session);
}
async function main() {
  const stacks=process.argv.includes('--stacks');
  const args=parseArgs(process.argv.slice(2).filter(arg=>arg!=='--stacks')); if(!args.out) throw Error('Cần --out');
  mkdirSync(args.out,{recursive:true});
  const local=await serve(args.dist), executable=findBrowser(args.browser), browser=await launch(executable,{preserveProfile:true});
  const cdp=await connect(browser.endpoint), tracing=await traceConnection(browser.endpoint,stacks), samples=[];
  const metadata={ browser:await cdp.send('Browser.getVersion'), gpu:(await cdp.send('SystemInfo.getInfo')).gpu, executable,stacks, width:412,height:915,dpr:2.625,cpu:6,windowMs:600,thresholdMs:20,
    assets:Object.fromEntries(readdirSync(path.join(args.dist,'assets')).filter(f=>/\.(js|css)$/.test(f)).map(f=>[f,createHash('sha256').update(readFileSync(path.join(args.dist,'assets',f))).digest('hex')])), started:new Date().toISOString() };
  try {
    for (const group of args.only ?? ['player','sort','reader','sheet','cold-player','cold-reader']) {
      const page=await openPage(cdp,{width:412,height:915,scale:2.625,mobile:true,theme:args.theme});
      const session=page.sessionId;
      await cdp.send('Emulation.setCPUThrottlingRate',{rate:6},session);
      const url=`${local.base}?frame=phone/${group.endsWith('reader')?'book':group==='sheet'?'player-full':'library-full'}&theme=${args.theme}`;
      const navigate = async run => {
        await cdp.send('Page.navigate',{url:`${url}&jankRun=${run}`},session);
        await waitUntil(cdp,session,`window.__gallery?.ready && new URLSearchParams(location.search).get('jankRun')===${JSON.stringify(String(run))}`,args.timeout,group);
      };
      await navigate(0);
      await evaluate(cdp,session,'document.fonts.ready.then(()=>true)');
      for(let run=0;run<5;run++) {
        if(group.startsWith('cold-') && run>0) { await navigate(run); await evaluate(cdp,session,'document.fonts.ready.then(()=>true)'); }
        for(const interaction of group==='player'?['player-open','player-close']:group==='sort'?['sort-open','sort-close']:group==='sheet'?['sheet-open','sheet-close']:group==='cold-player'?['player-first-open']:group==='cold-reader'?['reader-first-open']:['reader-open']) {
          await evaluate(cdp,session,STILL);
          await sleep(200);
          await tracing.start();
          await evaluate(cdp,session,`new Promise(resolve => requestAnimationFrame(t => { window.__jank={start:t,last:t,intervals:[],done:false}; performance.mark('jank-start'); const tick=n=>{ const p=window.__jank; p.intervals.push(n-p.last); p.last=n; if(n-p.start<600) requestAnimationFrame(tick); else {p.done=true;performance.mark('jank-end');} }; requestAnimationFrame(tick); resolve(true); }))`);
          if(interaction==='sort-close' || interaction==='sheet-close') {
            await cdp.send('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27},session);
            await cdp.send('Input.dispatchKeyEvent',{type:'keyUp',key:'Escape',code:'Escape',windowsVirtualKeyCode:27},session);
          } else await tap(cdp,session,{'player-open':'Mở màn hình đang nghe','player-first-open':'Mở màn hình đang nghe','player-close':'Thu nhỏ','sort-open':'Xếp theo','reader-open':'Đọc','reader-first-open':'Đọc','sheet-open':'^Tốc độ đọc'}[interaction]);
          await waitUntil(cdp,session,'window.__jank.done',10000,'khung hình');
          const probe=await evaluate(cdp,session,`({...window.__jank,errors:window.__gallery.errors,missing:window.__gallery.missing, nowPlaying:document.querySelector('.now-playing')?.dataset.state, menu:!!document.querySelector('[role=menu][data-state=open]'),sheet:!!document.querySelector('.motion-sheet[data-state=open]'),reader:!!document.querySelector('[data-reader-scroll]')})`);
          if(probe.errors.length || probe.missing.length) throw Error(JSON.stringify(probe));
          if(interaction.startsWith('player-') && interaction.endsWith('open') && probe.nowPlaying!=='open' || interaction==='player-close' && probe.nowPlaying==='open' || interaction==='sort-open' && !probe.menu || interaction==='sort-close' && probe.menu || interaction.startsWith('reader-') && !probe.reader || interaction==='sheet-open' && !probe.sheet || interaction==='sheet-close' && probe.sheet) throw Error('Thao tác không tới đích: '+JSON.stringify(probe));
          const events=await tracing.end(), stats=frameStats(probe.intervals);
          const sample={interaction,run,cold:run===0 || group.startsWith('cold-'),spanMs:probe.last-probe.start,...stats,intervals:probe.intervals,trace:analyseTrace(events)}; samples.push(sample);
          writeFileSync(path.join(args.out,`${interaction}-${run}.trace.json`),JSON.stringify({traceEvents:events}));
          writeFileSync(path.join(args.out,'results.json'),JSON.stringify({metadata,samples},null,2));
          console.log(interaction,run,JSON.stringify(stats));
          if(group==='reader') { await evaluate(cdp,session,'history.back()'); await sleep(800); }
        }
      }
      await cdp.send('Target.closeTarget',{targetId:page.targetId});
    }
  } finally { tracing.close(); cdp.close(); await browser.close(); local.server.close(); }
  const rows=[...new Set(samples.map(s=>s.interaction))].map(name=>{const s=samples.filter(s=>s.interaction===name);return `| ${name} | ${s.map(s=>s.jankPct.toFixed(1)).join(', ')} | ${Math.min(...s.map(s=>s.jankPct)).toFixed(1)}–${Math.max(...s.map(s=>s.jankPct)).toFixed(1)} | ${s.map(s=>s.p99.toFixed(1)).join(', ')} |`;});
  const frame=f=>`${f.functionName||'(anonymous)'}${f.url?' ('+path.basename(f.url)+':'+(f.lineNumber+1)+':'+(f.columnNumber+1)+')':''}`;
  const details=samples.map(s=>`\n### ${s.interaction} / ${s.run}${s.cold?' (fresh app)':''}\n\n`+
    `Style recalc (ms / elements): ${s.trace.style.filter(e=>e.ms>=2).sort((a,b)=>b.ms-a.ms).slice(0,6).map(e=>`${e.ms.toFixed(1)} / ${e.elements??'unknown'}`).join('; ')||'none >=2 ms'}.\n\n`+
    s.trace.longTasks.slice(0,4).map(t=>`- Main task ${t.ms.toFixed(1)} ms at +${t.at.toFixed(1)} ms: ${t.children.slice(0,4).map(c=>`${c.name} ${c.ms.toFixed(1)} ms`).join(', ')}.\n`+
      t.cpuStacks.filter(c=>!/^\((program|idle|root)\)$/.test(c.stack[0]?.functionName??'')).slice(0,2).map(c=>`  Sampled stack (${c.selfMs.toFixed(1)} ms weight): ${c.stack.slice(0,8).map(frame).join(' ← ')}.\n`).join('')).join('')+
    `\nGPU/raster top: ${s.trace.gpu.slice(0,3).map(e=>`${e.name} ${e.ms.toFixed(1)} ms`).join('; ')||'none >=2 ms'}.\n`).join('');
  writeFileSync(path.join(args.out,'summary.md'),`| Interaction | Jank % (5 runs) | Range % | p99 ms (5 runs) |\n|---|---|---|---|\n${rows.join('\n')}\n${details}`);
}
if(process.argv[1] && import.meta.url===pathToFileURL(path.resolve(process.argv[1])).href) await main();
