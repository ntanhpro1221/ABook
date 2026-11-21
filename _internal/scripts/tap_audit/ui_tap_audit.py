"""Coordinate-only Edge/CDP overlay audit. No Playwright, DOM click(), or app patches.

Python 3.11+, websockets and httpx. Run run.py for an isolated fixture.
"""
from __future__ import annotations
import argparse
import asyncio
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import httpx
import websockets

def find_browser(override=None):
    """Find an installed Edge/Chrome without assuming a user or install drive."""
    if override:
        path=Path(override).expanduser()
        if path.is_file(): return str(path.resolve())
        found=shutil.which(override)
        if found: return found
        raise FileNotFoundError(f'Edge/Chrome executable not found: {override}')
    for name in ('msedge', 'msedge.exe', 'google-chrome', 'chrome', 'chromium', 'chromium-browser'):
        found=shutil.which(name)
        if found: return found
    for key in ('PROGRAMFILES(X86)', 'PROGRAMFILES', 'LOCALAPPDATA'):
        base=os.environ.get(key)
        if not base: continue
        for suffix in ('Microsoft/Edge/Application/msedge.exe', 'Google/Chrome/Application/chrome.exe'):
            path=Path(base)/suffix
            if path.is_file(): return str(path.resolve())
    raise FileNotFoundError('Edge/Chrome not found; install a browser or pass --edge PATH')

def limit_cpu():
    """Bound simultaneous CPU work to at most four logical CPUs; Edge inherits it."""
    for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','RAYON_NUM_THREADS','UV_THREADPOOL_SIZE'):
        os.environ[key]='4'
    os.environ['CUDA_VISIBLE_DEVICES']='-1'
    if os.name=='nt':
        import ctypes
        k=ctypes.WinDLL('kernel32',use_last_error=True)
        k.GetCurrentProcess.restype=ctypes.c_void_p
        handle=k.GetCurrentProcess();available=ctypes.c_size_t();system=ctypes.c_size_t()
        if not k.GetProcessAffinityMask(ctypes.c_void_p(handle),ctypes.byref(available),ctypes.byref(system)):
            raise ctypes.WinError(ctypes.get_last_error())
        bits=[1<<n for n in range(available.value.bit_length()) if available.value&(1<<n)][:4]
        mask=sum(bits)
        if not k.SetProcessAffinityMask(ctypes.c_void_p(handle),ctypes.c_size_t(mask)):
            raise ctypes.WinError(ctypes.get_last_error())
        return mask
    if hasattr(os,'sched_getaffinity'):
        cpus=sorted(os.sched_getaffinity(0))[:4];os.sched_setaffinity(0,cpus);return cpus

CONTROLS = 'button,a[href],input,[role=button],[role=menuitem],[role=menuitemcheckbox],[role=menuitemradio],[role=option],[role=tab],[role=switch],[role=checkbox],[role=radio],[role=slider],textarea,select'
# A deadline bounds failure; elapsed time is never evidence that a page is ready.
# Every deadline is scaled for machine load with the same factor as tests/timing.py
# (ABOOK_TEST_TIME_SCALE, default 5): a busy machine only makes a FAILURE slower.
TIME_SCALE = max(1.0, float(os.environ.get('ABOOK_TEST_TIME_SCALE', '5')))
READY_TIMEOUT = 15 * TIME_SCALE
OPENING_JS = r'''(() => {
 window.__toastFrames={count:0,blocked:[],pointerBlocked:[],running:true};
 const sample=()=>{
  const f=window.__toastFrames;if(!f.running)return;f.count++;
  const e=tapAudit.top();
  if(e)for(const b of e.querySelectorAll(tapAudit.controls))if(tapAudit.visible(b)){
   const p=tapAudit.inspect(b);
   if(!p.disabled&&p.hitToast)f.blocked.push(p);
   // Mid-motion, a hit on the layer's own inert surface (no other control) is a
   // transient dead zone inside the layer, not a tap reaching something else.
   // Settled layers still require the exact control (opening layer controls reachable).
   const surface=!p.hit&&p.pointerEvents!=='none'&&!p.blockedInLayer.length&&!!tapAudit.surfaceHit?.(b,p,e);
   if(!p.disabled&&!surface&&(p.pointerEvents==='none'||!p.hit||p.blockedInLayer.length))f.pointerBlocked.push(tapAudit.explain?tapAudit.explain(b,p,e):p);
  }
  requestAnimationFrame(sample);
 };requestAnimationFrame(sample);
})()'''
# Evidence for a popup trigger that was tapped but left no layer: who got the
# pointer, where focus went, and every aria-expanded / layer mount and unmount.
TRACE_JS = r'''(trigger => {
 const t0=performance.now(),log=window.__stepTrace=[];window.__stepTrigger=trigger;const name=n=>n?.getAttribute?.('aria-label')||n?.getAttribute?.('role')||n?.tagName;
 const rec=(...x)=>{if(log.length<80)log.push([Math.round(performance.now()-t0),...x])};
 for(const ty of ['pointerdown','pointerup','click','focusin','focusout'])document.addEventListener(ty,e=>rec(ty,name(e.target),e.isTrusted,!!e.target?.closest?.('[data-sonner-toast]')),true);
 const layer='[role=dialog],[role=alertdialog],[role=menu],[role=listbox]';
 new MutationObserver(ms=>{for(const m of ms){if(m.type==='attributes')rec(m.attributeName+'='+m.target.getAttribute(m.attributeName),name(m.target));
  for(const n of m.addedNodes)if(n.nodeType===1&&(n.matches(layer)||n.querySelector(layer)))rec('layer+',name(n.matches(layer)?n:n.querySelector(layer)));
  for(const n of m.removedNodes)if(n.nodeType===1){if(n.matches(layer)||n.querySelector(layer))rec('layer-',name(n.matches(layer)?n:n.querySelector(layer)));
   if(n===trigger||n.contains(trigger))rec('trigger removed with',n.tagName+'.'+String(n.className||'').slice(0,60),name(m.target));}}})
  .observe(document.body,{subtree:true,childList:true,attributes:true,attributeFilter:['aria-expanded']});
 return true;
})'''
SETTLE_JS = r'''new Promise((resolve, reject) => {
 const start=performance.now();let previous='',stable=0;
 const tick=()=>{
  const boxes=[...document.querySelectorAll('main,[role=main],.now-playing,[role=dialog],[role=menu],[role=listbox],button,input')]
    .map(e=>{const r=e.getBoundingClientRect();return [r.x,r.y,r.width,r.height,e.getAttribute('data-state')];});
  const current=JSON.stringify(boxes);
  const moving=document.getAnimations().some(a=>a.playState!=='finished'&&a.playState!=='idle'&&a.effect?.getComputedTiming().endTime!==Infinity);
  stable=current===previous&&!moving&&document.fonts.status==='loaded'?stable+1:0;previous=current;
  if(stable>=3)return resolve(true);
  const limit=globalThis.__tapSettleMs||15000;
  if(performance.now()-start>limit)return reject(Error('UI motion/geometry did not settle within '+limit/1000+'s'));
  requestAnimationFrame(tick);
 };requestAnimationFrame(tick);
})'''
JS = r'''(() => {
 const controls = CONTROLS;
 // "Visible" = the control's center is painted, so a hit-test there is evidence.
 // Clipping follows CSS: overflow (not visible) clips only descendants whose
 // containing-block chain passes through it (fixed/absolute escape others, and
 // html/body overflow belongs to the viewport); clip-path inset() clips every
 // descendant (MotionRegion slides content in under an inset cut).
 const insetBox = (s,p,b) => {const m=/^inset\(([^)]*?)(?:\sround\s[^)]*)?\)$/.exec(s.clipPath||'');if(!m)return null;const v=m[1].trim().split(/\s+/);const [t,r,bo,l]=[v[0],v[1]??v[0],v[2]??v[0],v[3]??v[1]??v[0]];const sx=p.offsetWidth?b.width/p.offsetWidth:1,sy=p.offsetHeight?b.height/p.offsetHeight:1;const len=(x,size,scale)=>x.endsWith('%')?parseFloat(x)/100*b[size]:(parseFloat(x)||0)*scale;return {left:b.left+len(l,'width',sx),right:b.right-len(r,'width',sx),top:b.top+len(t,'height',sy),bottom:b.bottom-len(bo,'height',sy)}};
 const containsFixed = s => s.transform!=='none'||s.filter!=='none'||(s.perspective&&s.perspective!=='none')||/paint|layout|strict|content/.test(s.contain||'');
 const visible = e => {const r=e.getBoundingClientRect(),x=r.left+r.width/2,y=r.top+r.height/2;let opacity=1,mode='normal';for(let p=e;p;p=p.parentElement){const s=getComputedStyle(p);opacity*=Number(s.opacity);if(s.visibility!=='visible'||s.display==='none'||opacity<.05||p.inert)return false;const b=p.getBoundingClientRect();const cut=insetBox(s,p,b);if(cut&&(x<cut.left||x>=cut.right||y<cut.top||y>=cut.bottom))return false;if(p!==e){const block=mode==='normal'||mode==='abs'&&(s.position!=='static'||containsFixed(s))||mode==='fixed'&&containsFixed(s);if(block){mode='normal';if(p!==document.body&&p!==document.documentElement&&(/auto|scroll|hidden|clip/.test(s.overflowY)&&(y<b.top||y>=b.bottom)||/auto|scroll|hidden|clip/.test(s.overflowX)&&(x<b.left||x>=b.right)))return false;}}if(s.position==='fixed')mode='fixed';else if(s.position==='absolute')mode='abs';}return r.width>0&&r.height>0&&x>=0&&y>=0&&x<innerWidth-1&&y<innerHeight-1};
 const label = e => e.getAttribute('aria-label')||e.textContent.trim().replace(/\s+/g,' ').slice(0,110)||e.getAttribute('placeholder')||e.tagName;
 const layers = () => [...document.querySelectorAll('[role=dialog],[role=alertdialog],[role=menu],[role=listbox]')].filter(visible).filter(e=>e.getAttribute('data-state')!=='closed');
 const top = () => {const all=layers();return all.filter(e=>!all.some(other=>e!==other&&e.contains(other))).at(-1)};
 const find = (spec,root=document,offscreen=false) => [...(root?.querySelectorAll(spec.selector||controls)??[])].filter(e=>offscreen ? e.getClientRects().length>0&&!e.closest('[inert]') : visible(e)).find(e=>!spec.text || (spec.exact ? label(e)===spec.text : label(e).includes(spec.text)));
 const inspect = e => {const r=e.getBoundingClientRect(),x=r.left+r.width/2,y=r.top+r.height/2,h=document.elementFromPoint(x,y),anc=[];for(let p=e;p;p=p.parentElement)if(getComputedStyle(p).pointerEvents==='none')anc.push(p.tagName+(p.id?'#'+p.id:'')+(p.getAttribute('role')?'[role='+p.getAttribute('role')+']':''));
 // Radix intentionally locks BODY but restores pointer-events:auto on modal content.
 // Record EVERY ancestor; ancestors outside the current layer are not blockers when
 // the layer explicitly restores hit testing. The elementFromPoint check is decisive.
 // Con có pointer-events:auto vẫn nhận chạm trong cha pointer-events:none; hit-test xác nhận đường thật.
 const blocked=getComputedStyle(e).pointerEvents==='none'?[e.tagName]:[];
 const toast=h?.closest('[data-sonner-toast]');const close=toast?.querySelector('[data-close-button]');const cr=close?.getBoundingClientRect();
 return {label:label(e),tag:e.tagName,disabled:e.matches(':disabled')||e.hasAttribute('data-disabled')||e.getAttribute('aria-disabled')==='true',x,y,hit:!!h&&(h===e||e.contains(h)||(!!(e.id||e.getAttribute('data-tap-proxy-for'))&&h.closest('[data-tap-proxy-for]')?.getAttribute('data-tap-proxy-for')===(e.getAttribute('data-tap-proxy-for')||e.id))),hitElement:h?label(h):null,hitTag:h?h.tagName:null,pointerEvents:getComputedStyle(e).pointerEvents,noneAncestors:anc,blockedInLayer:blocked,hitToast:!!toast,toastClose:cr?{x:cr.left+cr.width/2,y:cr.top+cr.height/2}:null};};
 // Triage evidence for a blocked sample: what paints/clips the control and what took the hit.
 const explain = (b,p,root) => {const box=n=>{const s=getComputedStyle(n),r=n.getBoundingClientRect();return [n.tagName,String(n.className||'').slice(0,40),s.position,s.overflowX+'/'+s.overflowY,s.clipPath,s.transform,!!n.inert,[r.left,r.top,r.width,r.height].map(Math.round)]};const chain=[];for(let n=b;n&&n!==root.parentElement;n=n.parentElement)chain.push(box(n));const hits=[];for(let n=document.elementFromPoint(p.x,p.y);n&&hits.length<6;n=n.parentElement)hits.push(box(n));return {...p,chain,hitChain:hits}};
 const surfaceHit = (b,p,root) => {const h=document.elementFromPoint(p.x,p.y);if(!h||!root.contains(h))return false;const c=h.closest(controls);return !c||!root.contains(c)||c===b||b.contains(c)};
 window.tapAudit={visible,label,layers,top,find,inspect,explain,surfaceHit,controls};return true;
})()'''.replace('CONTROLS', json.dumps(CONTROLS))

class CDP:
    def __init__(self, ws): self.ws,self.seq,self.toast_dismissals = ws,0,[]
    async def call(self, method, **params):
        self.seq+=1; ident=self.seq
        await self.ws.send(json.dumps(dict(id=ident,method=method,params=params)))
        while True:
            msg=json.loads(await asyncio.wait_for(self.ws.recv(),20*TIME_SCALE))
            if msg.get('method') == 'Runtime.exceptionThrown':
                if not hasattr(self, 'page_errors'): self.page_errors = []
                self.page_errors.append(msg.get('params', {}).get('exceptionDetails', {}))
            if msg.get('id')==ident:
                if 'error' in msg: raise RuntimeError(msg['error'])
                return msg.get('result',{})
    async def evaluate(self, expression):
        r=await self.call('Runtime.evaluate',expression=expression,returnByValue=True,awaitPromise=True)
        if r.get('exceptionDetails'): raise RuntimeError(r['exceptionDetails'])
        return r['result'].get('value')
    async def settle(self):
        # Re-sample each frame: React can mount another animation after the first
        # animation list was captured. A timeout must fail, never act as success.
        await self.evaluate(f'(globalThis.__tapSettleMs={round(READY_TIMEOUT*1000)},{SETTLE_JS})')

    async def navigate(self, url):
        await self.call('Page.navigate', url=url)
        deadline = asyncio.get_running_loop().time() + READY_TIMEOUT
        expression = f"location.href==={json.dumps(url)}&&document.readyState==='complete'&&!!document.querySelector('main button,[role=main] button')"
        while True:
            try:
                if await self.evaluate(expression): return
            except RuntimeError as exc:
                # Page.navigate may return before Chromium replaces its old JS
                # context. Retry this specific navigation event, not app errors.
                if not any(message in str(exc) for message in ('Execution context was destroyed', 'Cannot find context', 'Inspected target navigated')): raise
            if asyncio.get_running_loop().time() >= deadline:
                raise RuntimeError(f'Application did not mount within {READY_TIMEOUT:g}s: '+url)
            await asyncio.sleep(.05)
    async def wait_toast(self, timeout=3, publish=False):
        deadline = asyncio.get_running_loop().time() + timeout*TIME_SCALE
        while True:
            if publish:
                # A newly navigated shell may not have committed UpdateListener yet.
                # Keep sending the normal event until a real toast mounts; never fake its DOM.
                await self.evaluate("window.dispatchEvent(new CustomEvent('abook-update-failed',{detail:'Kiểm tra thông báo khi mở bảng'}))")
            if await self.evaluate("!!document.querySelector('[data-sonner-toast][data-mounted=\"true\"]:not([data-removed=\"true\"])')"):
                return True
            if asyncio.get_running_loop().time() >= deadline:
                return False
            await asyncio.sleep(.05)
    async def key(self, key, code=None):
        for kind in ('keyDown','keyUp'):
            await self.call('Input.dispatchKeyEvent',type=kind,key=key,code=code or key,windowsVirtualKeyCode=27 if key=='Escape' else 65 if key=='a' else 0)
    async def point(self, p, touch=False):
        if touch:
            await self.call('Input.dispatchTouchEvent',type='touchStart',touchPoints=[dict(x=p['x'],y=p['y'],id=1)])
            await asyncio.sleep(.06)
            await self.call('Input.dispatchTouchEvent',type='touchEnd',touchPoints=[])
        else:
            await self.call('Input.dispatchMouseEvent',type='mouseMoved',x=p['x'],y=p['y'])
            for kind in ('mousePressed','mouseReleased'):
                await self.call('Input.dispatchMouseEvent',type=kind,x=p['x'],y=p['y'],button='left',clickCount=1)
    async def select(self,spec,within=False,scroll=True):
        # An absent layer must never default the search back to the page below.
        root='(tapAudit.top()||null)' if within else 'document'
        expr=f'tapAudit.find({json.dumps(spec,ensure_ascii=False)},{root})'
        if scroll:
            # scrollIntoView is layout only. All activation uses CDP coordinates.
            await self.evaluate(f'(()=>{{const e=tapAudit.find({json.dumps(spec,ensure_ascii=False)},{root},true);if(e)e.scrollIntoView({{block:"nearest",inline:"nearest"}});return !!e}})()')
            await self.settle()
        deadline = asyncio.get_running_loop().time() + READY_TIMEOUT
        while True:
            p=await self.evaluate(f'(()=>{{const e={expr};return e?tapAudit.inspect(e):null}})()')
            if p:
                # Chỉ trang thường được thông báo tạm che. Trong bảng đang mở phải báo lỗi thiết kế.
                if not p['hit'] and p.get('hitToast') and not await self.evaluate('!!tapAudit.top()'):
                    close=p.get('toastClose')
                    if close:
                        # Xác nhận nút ✕ thật sự nhận chạm, rồi dùng CDP như người dùng.
                        reachable=await self.evaluate(f'!!document.elementFromPoint({close["x"]},{close["y"]})?.closest("[data-close-button]")')
                        if not reachable:
                            # A toast still sliding in or out (✕ off screen, busy machine) settles
                            # by itself; re-check within the deadline instead of failing the step.
                            if asyncio.get_running_loop().time() >= deadline: return p
                            await self.settle(); await asyncio.sleep(.05)
                            continue
                        await self.point(close,touch=await self.evaluate('innerWidth<600'))
                        self.toast_dismissals.append(dict(target=p['label'],method='close button',point=close))
                        await self.settle()
                    else:
                        self.toast_dismissals.append(dict(target=p['label'],method='wait for expiry'))
                        for _ in range(int(100*TIME_SCALE)):
                            await asyncio.sleep(.1)
                            p=await self.evaluate(f'(()=>{{const e={expr};return e?tapAudit.inspect(e):null}})()')
                            if not p or not p.get('hitToast'): break
                    continue
                return p
            if asyncio.get_running_loop().time() >= deadline: break
            await asyncio.sleep(.05)
        try:
            seen=await self.evaluate("[...document.querySelectorAll('button,[role=menuitem],[role=button],a,input,[role=slider]')].filter(e=>tapAudit.visible(e)).map(e=>tapAudit.label(e)).slice(0,40)")
        except Exception: seen=None
        raise RuntimeError('visible target missing: '+json.dumps(spec,ensure_ascii=False)+' (visible controls: '+json.dumps(seen,ensure_ascii=False)+')')
    async def step(self,spec,retapped=False):
        p=await self.select(spec)
        if not p['hit'] or p['blockedInLayer'] or p['disabled']: raise RuntimeError('opening step cannot receive pointer: '+str(p))
        state=f'tapAudit.find({json.dumps(spec,ensure_ascii=False)})?.getAttribute("aria-checked")'
        if 'checked' in spec:
            current=await self.evaluate(state)
            if current not in ('true','false'): raise RuntimeError('checked step requires a checkable control')
            if current==str(spec['checked']).lower(): return
        target=f'tapAudit.find({json.dumps(spec,ensure_ascii=False)})'
        # Only a closed trigger must open a layer; tapping an open one may close it.
        popup='checked' not in spec and await self.evaluate(f'(e=>!!e&&e.hasAttribute("aria-haspopup")&&e.getAttribute("aria-expanded")!=="true")({target})') is True
        if popup: await self.evaluate(f'({TRACE_JS})({target})')
        await self.point(p,touch=await self.evaluate('innerWidth<600'));await self.settle()
        if popup and not retapped and not await self.evaluate('!!tapAudit.top()'):
            # A page toast moved under the finger after select() hit-tested the trigger (busy
            # machine): the press went to the toast, not the trigger. Page toasts are a transient
            # cover (select dismisses them through their real close button); re-select and tap once.
            trace=await self.evaluate('window.__stepTrace')
            trace=trace if isinstance(trace,list) else []
            if any(e[1]=='pointerdown' and len(e)>4 and e[4] for e in trace):
                self.toast_dismissals.append(dict(target=p['label'],method='toast moved under the tap; re-select and tap again',trace=trace))
                return await self.step(spec,retapped=True)
        if popup:
            # A popup trigger's result is a live layer. Wait for it (bounded); if the tap did
            # not open it, fail here with the event trace instead of "target missing" later.
            deadline=asyncio.get_running_loop().time()+READY_TIMEOUT
            while not await self.evaluate('!!tapAudit.top()'):
                if asyncio.get_running_loop().time()>=deadline:
                    raise RuntimeError('popup trigger tapped but no layer opened: '+json.dumps(await self.evaluate('({trace:window.__stepTrace,triggerConnected:!!window.__stepTrigger?.isConnected,active:document.activeElement?.tagName})'),ensure_ascii=False))
                await asyncio.sleep(.05)
            # The opening tap must only open: its click lands under the finger, inside the layer
            # it just opened. If that selected an item or pressed Close, the trigger is no longer
            # expanded (the layer was replaced or closed by the same tap).
            if await self.evaluate('(e=>!!e&&e.isConnected&&e.hasAttribute("aria-expanded")&&e.getAttribute("aria-expanded")!=="true")(window.__stepTrigger)'):
                raise RuntimeError('opening tap also acted inside the layer it opened: '+json.dumps(await self.evaluate('({trace:window.__stepTrace,top:tapAudit.top()?.getAttribute("aria-label")||tapAudit.top()?.textContent?.slice(0,60)})'),ensure_ascii=False))
        if 'checked' in spec:
            # The switch reflects saved server state (no optimistic flip); a busy
            # machine answers later. Wait for that state, bounded by a deadline.
            deadline=asyncio.get_running_loop().time()+READY_TIMEOUT
            while await self.evaluate(state)!=str(spec['checked']).lower():
                if asyncio.get_running_loop().time()>=deadline:
                    raise RuntimeError('coordinate input did not set the requested checked state')
                await asyncio.sleep(.05)
            await self.settle()

    async def close_layers(self):
        for _ in range(8):
            if not await self.evaluate('!!tapAudit.top()'): return
            await self.key('Escape');await self.settle()
        raise RuntimeError('layers did not close after Escape')

    async def capture_layer(self):
        # Reopening can schedule an entering surface after the previous surface
        # finishes exiting. Never store an undefined reference between those phases.
        deadline = asyncio.get_running_loop().time() + READY_TIMEOUT
        while True:
            layer = await self.evaluate("(()=>{const e=tapAudit.top();if(!e)return null;window.__tapLayer=e;return {role:e.role,title:e.textContent.slice(0,150),body:getComputedStyle(document.body).pointerEvents}})()")
            if layer is not None:
                return layer
            if asyncio.get_running_loop().time() >= deadline: break
            await asyncio.sleep(.05)
        raise RuntimeError('layer did not open after coordinate input')

    async def negative_control(self, spec, report, check):
        """Bracket a scoped fault with healthy samples; never activate a broken UI.

        The positive audit owns trusted mouse/touch actions. Clicking through an
        intentionally broken layer can dismiss it and activate background actions,
        so it cannot be used as preparation for the next negative probe.
        """
        async def elements():
            return await self.evaluate("[...__tapLayer.querySelectorAll(tapAudit.controls)].filter(tapAudit.visible).map(tapAudit.inspect)")
        def healthy(items):
            return bool(items) and all(e['disabled'] or e['hit'] and not e['blockedInLayer'] for e in items)
        baseline = await elements()
        probes = {}
        for mode in ('mouse', 'touch'):
            target = spec.get('touchProbe', spec['probe']) if mode == 'touch' else spec['probe']
            probes[mode] = await self.select(target, within=True)
        baseline_ok = healthy(baseline) and all(p['hit'] and not p['blockedInLayer'] and not p['disabled'] for p in probes.values())
        evidence = report['negativeControl'] = dict(baseline=dict(healthy=baseline_ok, elements=baseline, probes=probes), detected={})
        check('negative baseline healthy before injection', baseline_ok)
        if not baseline_ok: raise RuntimeError('negative control baseline is not healthy')
        try:
            report['injected'] = await self.evaluate("(()=>{const e=__tapLayer;window.__tapOriginalPointer=[e.style.getPropertyValue('pointer-events'),e.style.getPropertyPriority('pointer-events')];e.style.setProperty('pointer-events','none','important');return e.isConnected&&getComputedStyle(e).pointerEvents==='none'})()")
            check('fault injection applied', report['injected'])
            report['elements'] = await elements()
            for e in report['elements']:
                e['status'] = 'SKIP_DISABLED' if e['disabled'] else 'PASS' if e['hit'] and not e['blockedInLayer'] else 'FAIL'
            for mode in ('mouse', 'touch'):
                target = spec.get('touchProbe', spec['probe']) if mode == 'touch' else spec['probe']
                # Do not settle/scroll/reopen between the injection and its sample.
                p = await self.select(target, within=True, scroll=False)
                evidence['detected'][mode] = p
                check(mode+' probe center reaches control', p['hit'] and not p['blockedInLayer'] and not p['disabled'], element=p)
        finally:
            await self.evaluate("(()=>{const [value,priority]=__tapOriginalPointer;value?__tapLayer.style.setProperty('pointer-events',value,priority):__tapLayer.style.removeProperty('pointer-events');return true})()")
            restored = await elements()
            evidence['restored'] = dict(healthy=healthy(restored), elements=restored)
            check('negative original pointer state restored healthy', evidence['restored']['healthy'])

def free_port():
    with socket.socket() as s: s.bind(('127.0.0.1',0));return s.getsockname()[1]

def load_scenarios(path):
    specs=json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(specs,list) or not specs: raise ValueError('scenarios must be a nonempty list')
    names=set()
    def target(value):
        if not isinstance(value,dict) or not any(isinstance(value.get(k),str) and value[k] for k in ('selector','text')):
            raise ValueError('target requires selector or text')
        for key in ('exact','closes','checked'):
            if key in value and not isinstance(value[key],bool): raise ValueError(key+' must be boolean')
        if 'type' in value and value['type']!='input': raise ValueError('unsupported probe type')
        if 'expect' in value and (not isinstance(value['expect'],str) or not value['expect']): raise ValueError('expect must be an expression')
    for spec in specs:
        if not isinstance(spec,dict): raise ValueError('scenario must be an object')
        name=spec.get('name')
        if not isinstance(name,str) or not name or name in names: raise ValueError('unique scenario name required')
        names.add(name)
        if not isinstance(spec.get('path'),str) or not spec['path'].startswith('#/'): raise ValueError('hash route required')
        if not isinstance(spec.get('steps'),list) or not spec['steps']: raise ValueError('opening steps required')
        for value in [*spec['steps'],spec.get('probe'),spec.get('background')]: target(value)
        if 'touchProbe' in spec: target(spec['touchProbe'])
        if 'reopenSteps' in spec:
            if not isinstance(spec['reopenSteps'],list) or not spec['reopenSteps']: raise ValueError('reopening steps required')
            for value in spec['reopenSteps']: target(value)
        viewport=spec.get('viewport',[412,915])
        if not isinstance(viewport,list) or len(viewport)!=2 or any(type(n) is not int or n<=0 for n in viewport):
            raise ValueError('viewport must contain two positive integers')
    return specs

def result_status(results):
    """A missing, malformed or internally inconsistent report can never pass."""
    if not isinstance(results,list) or not results: return 'FAIL'
    for result in results:
        if not isinstance(result,dict) or result.get('status')!='PASS': return 'FAIL'
        checks=result.get('checks');elements=result.get('elements')
        if not isinstance(checks,list) or not checks or not all(isinstance(c,dict) and c.get('pass_') is True for c in checks): return 'FAIL'
        if not isinstance(elements,list) or not elements or not all(isinstance(e,dict) and e.get('status') in ('PASS','SKIP_DISABLED') for e in elements): return 'FAIL'
    return 'PASS'

async def scenario(c,base,s,inject):
    report=dict(name=s['name'],checks=[],elements=[],openingLayers=[])
    c.toast_dismissals=[]
    c.page_errors=[]
    def check(name,ok,**evidence): report['checks'].append(dict(name=name,pass_=bool(ok),**evidence))
    try:
        w,h=s.get('viewport',[412,915])
        await c.call('Emulation.setDeviceMetricsOverride',width=w,height=h,deviceScaleFactor=1,mobile=w<600)
        await c.call('Emulation.setTouchEmulationEnabled',enabled=True,maxTouchPoints=1)
        await c.call('Page.navigate',url='about:blank')
        await c.navigate(base.rstrip('/')+'/'+s.get('path',''))
        await c.evaluate(JS)
        for step in s['steps']:
            # Exercise the real shared toaster through the shell's normal event, on
            # every screen. Never dismiss it to make an open layer pass.
            check('real toast mounted before opening layer',await c.wait_toast(publish=True))
            await c.settle()
            await c.evaluate(OPENING_JS)
            await c.step(step)
            frames=await c.evaluate("(()=>{const f=window.__toastFrames;f.running=false;return f})()")
            check('toast never covers a layer control during motion',frames['count']>0 and not frames['blocked'],frames=frames)
            check('visible layer controls receive pointer events throughout opening', frames['count']>0 and not frames['pointerBlocked'], frames=frames)
            opened=await c.evaluate("(()=>{const e=tapAudit.top();return e?{role:e.role,elements:[...e.querySelectorAll(tapAudit.controls)].filter(tapAudit.visible).map(tapAudit.inspect)}:null})()")
            if opened:
                report['openingLayers'].append(opened)
                check('opening layer controls reachable',all(e['disabled'] or (e['hit'] and not e['blockedInLayer']) for e in opened['elements']),role=opened['role'])
        await c.settle()
        layer=await c.capture_layer()
        check('layer opened',layer is not None,layer=layer)
        if not layer: raise RuntimeError('no open top layer')
        report['elements']=await c.evaluate("[...__tapLayer.querySelectorAll(tapAudit.controls)].filter(tapAudit.visible).map(tapAudit.inspect)")
        check('nonempty control coverage',len(report['elements'])>0)
        for e in report['elements']:
            # Disabled controls intentionally have pointer-events:none; report, do not activate.
            e['status']='SKIP_DISABLED' if e['disabled'] else 'PASS' if e['hit'] and not e['blockedInLayer'] else 'FAIL'
        if inject:
            await c.negative_control(s, report, check)
        for touch in (() if inject else (False,True)):
            safe=s.get('touchProbe',s['probe']) if touch else s['probe']
            mode='touch' if touch else 'mouse'
            if not await c.evaluate('__tapLayer.isConnected && tapAudit.visible(__tapLayer) && __tapLayer.dataset.state!=="closed"'):
                # A blocked tap can fall through to the scrim and dismiss the modal.
                # Reopen to test the other input modality independently, still via coordinates.
                await c.close_layers()
                for step in s.get('reopenSteps',s['steps']): await c.step(step)
                await c.capture_layer()
            p=await c.select(safe,within=True)
            check(mode+' probe center reaches control',p['hit'] and not p['blockedInLayer'] and not p['disabled'],element=p)
            await c.evaluate("(()=>{window.__tapEvents=[];for(const t of ['pointerdown','click','touchstart'])__tapLayer.addEventListener(t,e=>__tapEvents.push({type:t,trusted:e.isTrusted,target:tapAudit.label(e.target)}),{once:true});return true})()")
            await c.point(p,touch=touch);await c.settle()
            ev=await c.evaluate('__tapEvents')
            check(mode+' trusted click delivered inside layer',any(e['type']=='click' and e['trusted'] for e in ev),events=ev)
            if safe.get('type')=='input':
                # Select existing text with physical key events, no value assignment.
                await c.call('Input.dispatchKeyEvent',type='keyDown',key='a',code='KeyA',modifiers=2,windowsVirtualKeyCode=65)
                await c.call('Input.dispatchKeyEvent',type='keyUp',key='a',code='KeyA',modifiers=2,windowsVirtualKeyCode=65)
                await c.call('Input.insertText',text='abc')
                value=await c.evaluate(f'(()=>{{const e=tapAudit.find({json.dumps(safe,ensure_ascii=False)},__tapLayer);return e?.value}})()')
                check(mode+' insertText value',value=='abc',value=value)
            if safe.get('expect'):
                effect=False
                for _ in range(30):
                    effect=await c.evaluate(safe['expect'])
                    if effect: break
                    await asyncio.sleep(.1)
                check(mode+' action changed UI state',effect,expression=safe['expect'])
            remains=await c.evaluate('__tapLayer.isConnected && tapAudit.visible(__tapLayer) && __tapLayer.dataset.state!=="closed"')
            if safe.get('closes'):
                check(mode+' action closes layer',not remains)
                # Reopen with real coordinate clicks so touch and final Escape are also tested.
                await c.close_layers()
                for step in s.get('reopenSteps',s['steps']): await c.step(step)
                await c.capture_layer()
            else:
                check(mode+' layer remains open',remains)
                # Mục con mở tại chỗ trong menu (set140): chọn xong thì mục con khép, menu cha ở lại - mở lại mục con cho lượt chạm.
                for step in s.get('inlineReopen',[]): await c.step(step)
        await c.close_layers()
        check('layer closed',await c.evaluate('!__tapLayer.isConnected || __tapLayer.dataset.state==="closed" || !tapAudit.visible(__tapLayer)'))
        body=await c.evaluate('getComputedStyle(document.body).pointerEvents')
        check('body pointer lock released',body!='none',pointerEvents=body)
        p=await c.select(s['background'])
        check('background center reaches control',p['hit'] and not p['blockedInLayer'],element=p)
    except Exception as e:
        check('execution',False,error=str(e))
        try:
            report['failurePage'] = await c.evaluate("({url:location.href,text:document.body.innerText.slice(0,5000),html:document.body.innerHTML.slice(0,5000)})")
            report['pageErrors'] = c.page_errors
        except Exception as capture_error:
            report['failurePageError'] = str(capture_error)
    report['toastDismissals']=c.toast_dismissals
    report['status']='PASS' if all(x['pass_'] for x in report['checks']) and all(e['status']!='FAIL' for e in report['elements']) else 'FAIL'
    return report

EXIT_TIMEOUT = 60 * TIME_SCALE


def edge_tree(pid):
    """Our Edge root and every descendant, captured before the kill (children are re-parented after)."""
    try:
        import psutil
        root=psutil.Process(pid)
        return [root,*root.children(recursive=True)]
    except Exception:
        return []


def wait_tree_exit(tree, timeout):
    """Processes of `tree` still running after `timeout` seconds (empty = all exited)."""
    if not tree: return []
    import psutil
    _,alive=psutil.wait_procs(tree,timeout=timeout)
    return alive


async def remove_profile(profile, timeout=EXIT_TIMEOUT):
    # Windows releases handles a moment after process exit (and antivirus may hold them):
    # retry until a deadline; the deadline bounds failure, it is never readiness.
    deadline=asyncio.get_running_loop().time()+timeout
    while True:
        try: shutil.rmtree(str(profile));return
        except FileNotFoundError: return
        except OSError:
            if asyncio.get_running_loop().time()>=deadline: raise
            await asyncio.sleep(.2)


async def run(args):
    args.edge=find_browser(args.edge)
    affinity=limit_cpu()
    started=time.monotonic();port=free_port()
    profile=Path(tempfile.mkdtemp(prefix='abook-tapaudit-edge-')).resolve()
    proc=None; cleanup={}
    try:
        flags=[args.edge,'--headless=new','--inprivate','--disable-sync','--disable-extensions','--no-first-run',f'--user-data-dir={profile}',f'--remote-debugging-port={port}','--remote-debugging-address=127.0.0.1','--disable-gpu','--renderer-process-limit=2','--num-raster-threads=1','--js-flags=--single-threaded','about:blank']
        proc=subprocess.Popen(flags,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                              creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0,
                              start_new_session=os.name!='nt')
        async with httpx.AsyncClient(trust_env=False) as http:
            for _ in range(int(100*TIME_SCALE)):
                try:
                    tabs=(await http.get(f'http://127.0.0.1:{port}/json/list')).json()
                    page=next(t for t in tabs if t['type']=='page');break
                except Exception: await asyncio.sleep(.1)
            else: raise RuntimeError('Edge CDP did not start')
        async with websockets.connect(page['webSocketDebuggerUrl'],max_size=16*1024*1024) as ws:
            c=CDP(ws);await c.call('Page.enable');await c.call('Runtime.enable')
            browser=await c.call('Browser.getVersion')
            specs=load_scenarios(args.scenarios)
            results=[]
            for s in specs:
                if args.only and args.only not in s['name']: continue
                r=await scenario(c,args.url,s,args.inject_fault);results.append(r)
                if not args.json:
                    print(f"{r['status']:4} | {r['name']}",flush=True)
                    for e in r['elements']: print(f"  {e['status']:13} | {e['label']}",flush=True)
                    for x in r['checks']:
                        if not x['pass_']: print('  FAIL | '+json.dumps(x,ensure_ascii=False),flush=True)
            payload=dict(url=args.url,injected=args.inject_fault,seconds=round(time.monotonic()-started,3),browser=browser,cpuAffinity=affinity,results=results)
    finally:
        if proc:
            # Kill ONLY our Edge process tree, including renderer children, before removing profile.
            tree=edge_tree(proc.pid)
            if os.name=='nt':
                await asyncio.to_thread(subprocess.run,['taskkill','/PID',str(proc.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            else:
                import signal
                try: os.killpg(proc.pid,signal.SIGTERM)
                except ProcessLookupError: pass
            try: proc.wait(timeout=10*TIME_SCALE)
            except subprocess.TimeoutExpired: proc.kill();proc.wait()
            # Children (crashpad, utility, renderers) outlive the root on a busy machine and keep
            # profile files open: wait for every one of them, not a fixed number of retries.
            alive=await asyncio.to_thread(wait_tree_exit,tree,EXIT_TIMEOUT)
            cleanup['edgeExited']=proc.poll() is not None and not alive
        await remove_profile(profile)
        cleanup['profileRemoved']=not profile.exists()
    payload['cleanup']=cleanup
    payload['status']=result_status(results)
    return payload

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--url',required=True)
    p.add_argument('--scenarios',default=str(Path(__file__).resolve().parent/'scenarios.json'))
    p.add_argument('--edge')
    p.add_argument('--json',action='store_true',help='emit JSON only on stdout')
    p.add_argument('--output',help='also save JSON report')
    p.add_argument('--inject-fault',action='store_true',help='negative control: pointer-events:none on every top layer, including nonmodal popovers')
    p.add_argument('--only',help='scenario name substring')
    args=p.parse_args()
    try: payload=asyncio.run(run(args))
    except FileNotFoundError as exc:
        print(str(exc),file=sys.stderr); return 2
    if args.output: Path(args.output).write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    if args.json: print(json.dumps(payload,ensure_ascii=False,indent=2))
    else: print(f"{payload['status']} | {len(payload['results'])} scenarios | {payload['seconds']}s")
    return int(payload['status']!='PASS')

if __name__=='__main__': sys.exit(main())
