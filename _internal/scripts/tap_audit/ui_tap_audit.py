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

CONTROLS = 'button,a[href],input,[role=button],[role=menuitem],[role=option],[role=tab],[role=switch],[role=checkbox],textarea,select'
JS = r'''(() => {
 const controls = CONTROLS;
 const visible = e => {const r=e.getBoundingClientRect(),s=getComputedStyle(e);return r.width>0&&r.height>0&&s.visibility!=='hidden'&&s.display!=='none'&&s.opacity!=='0'&&r.left+r.width/2>=0&&r.top+r.height/2>=0&&r.left+r.width/2<innerWidth&&r.top+r.height/2<innerHeight&&!e.closest('[inert]')};
 const label = e => e.getAttribute('aria-label')||e.textContent.trim().replace(/\s+/g,' ').slice(0,110)||e.getAttribute('placeholder')||e.tagName;
 const layers = () => [...document.querySelectorAll('[role=dialog],[role=alertdialog],[role=menu],[role=listbox]')].filter(visible).filter(e=>e.getAttribute('data-state')!=='closed');
 const top = () => layers().sort((a,b)=>(parseInt(getComputedStyle(a).zIndex)||0)-(parseInt(getComputedStyle(b).zIndex)||0)).at(-1);
 const find = (spec,root=document,offscreen=false) => [...root.querySelectorAll(spec.selector||controls)].filter(e=>offscreen ? e.getClientRects().length>0&&!e.closest('[inert]') : visible(e)).find(e=>!spec.text || (spec.exact ? label(e)===spec.text : label(e).includes(spec.text)));
 const inspect = e => {const r=e.getBoundingClientRect(),x=r.left+r.width/2,y=r.top+r.height/2,h=document.elementFromPoint(x,y),anc=[];for(let p=e;p;p=p.parentElement)if(getComputedStyle(p).pointerEvents==='none')anc.push(p.tagName+(p.id?'#'+p.id:'')+(p.getAttribute('role')?'[role='+p.getAttribute('role')+']':''));
 // Radix intentionally locks BODY but restores pointer-events:auto on modal content.
 // Record EVERY ancestor; ancestors outside the current layer are not blockers when
 // the layer explicitly restores hit testing. The elementFromPoint check is decisive.
 const layer=e.closest('[role=dialog],[role=alertdialog],[role=menu],[role=listbox]');let blocked=[];for(let p=e;p;p=p.parentElement){if(getComputedStyle(p).pointerEvents==='none')blocked.push(p.tagName);if(p===layer)break;}
 return {label:label(e),tag:e.tagName,disabled:e.matches(':disabled')||e.hasAttribute('data-disabled')||e.getAttribute('aria-disabled')==='true',x,y,hit:!!h&&(h===e||e.contains(h)),hitElement:h?label(h):null,pointerEvents:getComputedStyle(e).pointerEvents,noneAncestors:anc,blockedInLayer:blocked};};
 window.tapAudit={visible,label,layers,top,find,inspect,controls};return true;
})()'''.replace('CONTROLS', json.dumps(CONTROLS))

class CDP:
    def __init__(self, ws): self.ws,self.seq = ws,0
    async def call(self, method, **params):
        self.seq+=1; ident=self.seq
        await self.ws.send(json.dumps(dict(id=ident,method=method,params=params)))
        while True:
            msg=json.loads(await asyncio.wait_for(self.ws.recv(),20))
            if msg.get('id')==ident:
                if 'error' in msg: raise RuntimeError(msg['error'])
                return msg.get('result',{})
    async def evaluate(self, expression):
        r=await self.call('Runtime.evaluate',expression=expression,returnByValue=True,awaitPromise=True)
        if r.get('exceptionDetails'): raise RuntimeError(r['exceptionDetails'])
        return r['result'].get('value')
    async def settle(self):
        await self.evaluate("new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))")
        await self.evaluate("Promise.race([Promise.allSettled(document.getAnimations().filter(a=>a.effect?.getComputedTiming().iterations!==Infinity).map(a=>a.finished)),new Promise(r=>setTimeout(r,2000))])")
        await asyncio.sleep(.15)
    async def key(self, key, code=None):
        for kind in ('keyDown','keyUp'):
            await self.call('Input.dispatchKeyEvent',type=kind,key=key,code=code or key,windowsVirtualKeyCode=27 if key=='Escape' else 65 if key=='a' else 0)
    async def point(self, p, touch=False):
        if touch:
            await self.call('Input.dispatchTouchEvent',type='touchStart',touchPoints=[dict(x=p['x'],y=p['y'],id=1)])
            await self.call('Input.dispatchTouchEvent',type='touchEnd',touchPoints=[])
        else:
            await self.call('Input.dispatchMouseEvent',type='mouseMoved',x=p['x'],y=p['y'])
            for kind in ('mousePressed','mouseReleased'):
                await self.call('Input.dispatchMouseEvent',type=kind,x=p['x'],y=p['y'],button='left',clickCount=1)
    async def select(self,spec,within=False,scroll=True):
        root='tapAudit.top()' if within else 'document'
        expr=f'tapAudit.find({json.dumps(spec,ensure_ascii=False)},{root})'
        if scroll:
            # scrollIntoView is layout only. All activation uses CDP coordinates.
            await self.evaluate(f'(()=>{{const e=tapAudit.find({json.dumps(spec,ensure_ascii=False)},{root},true);if(e)e.scrollIntoView({{block:"nearest",inline:"nearest"}});return !!e}})()')
            await self.settle()
        for _ in range(30):
            p=await self.evaluate(f'(()=>{{const e={expr};return e?tapAudit.inspect(e):null}})()')
            if p: return p
            await asyncio.sleep(.1)
        raise RuntimeError('visible target missing: '+json.dumps(spec,ensure_ascii=False))
    async def step(self,spec):
        p=await self.select(spec)
        if not p['hit'] or p['blockedInLayer'] or p['disabled']: raise RuntimeError('opening step cannot receive pointer: '+str(p))
        await self.point(p);await self.settle()

def free_port():
    with socket.socket() as s: s.bind(('127.0.0.1',0));return s.getsockname()[1]

def load_scenarios(path):
    specs=json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(specs,list) or not specs: raise ValueError('scenarios must be a nonempty list')
    names=set()
    def target(value):
        if not isinstance(value,dict) or not any(isinstance(value.get(k),str) and value[k] for k in ('selector','text')):
            raise ValueError('target requires selector or text')
        for key in ('exact','closes'):
            if key in value and not isinstance(value[key],bool): raise ValueError(key+' must be boolean')
        if 'type' in value and value['type']!='input': raise ValueError('unsupported probe type')
    for spec in specs:
        if not isinstance(spec,dict): raise ValueError('scenario must be an object')
        name=spec.get('name')
        if not isinstance(name,str) or not name or name in names: raise ValueError('unique scenario name required')
        names.add(name)
        if not isinstance(spec.get('path'),str) or not spec['path'].startswith('#/'): raise ValueError('hash route required')
        if not isinstance(spec.get('steps'),list) or not spec['steps']: raise ValueError('opening steps required')
        for value in [*spec['steps'],spec.get('probe'),spec.get('background')]: target(value)
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
    def check(name,ok,**evidence): report['checks'].append(dict(name=name,pass_=bool(ok),**evidence))
    try:
        w,h=s.get('viewport',[412,915])
        await c.call('Emulation.setDeviceMetricsOverride',width=w,height=h,deviceScaleFactor=1,mobile=w<600)
        await c.call('Emulation.setTouchEmulationEnabled',enabled=True,maxTouchPoints=1)
        await c.call('Page.navigate',url='about:blank')
        await asyncio.sleep(.1)
        await c.call('Page.navigate',url=base.rstrip('/')+'/'+s.get('path',''))
        await asyncio.sleep(1)
        await c.evaluate(JS)
        for step in s['steps']:
            await c.step(step)
            opened=await c.evaluate("(()=>{const e=tapAudit.top();return e?{role:e.role,elements:[...e.querySelectorAll(tapAudit.controls)].filter(tapAudit.visible).map(tapAudit.inspect)}:null})()")
            if opened:
                report['openingLayers'].append(opened)
                check('opening layer controls reachable',all(e['disabled'] or (e['hit'] and not e['blockedInLayer']) for e in opened['elements']),role=opened['role'])
        await c.settle()
        layer=await c.evaluate("(()=>{const e=tapAudit.top();if(!e)return null;window.__tapLayer=e;return {role:e.role,title:e.textContent.slice(0,150),body:getComputedStyle(document.body).pointerEvents}})()")
        check('layer opened',layer is not None,layer=layer)
        if not layer: raise RuntimeError('no open top layer')
        if inject:
            injected=await c.evaluate("(()=>{const e=tapAudit.top();if(getComputedStyle(document.body).pointerEvents!=='none')return false;e.style.pointerEvents='none';return true})()")
            report['injected']=injected
            check('fault injection precondition: body locked',injected)
        report['elements']=await c.evaluate("[...__tapLayer.querySelectorAll(tapAudit.controls)].filter(tapAudit.visible).map(tapAudit.inspect)")
        check('nonempty control coverage',len(report['elements'])>0)
        for e in report['elements']:
            # Disabled controls intentionally have pointer-events:none; report, do not activate.
            e['status']='SKIP_DISABLED' if e['disabled'] else 'PASS' if e['hit'] and not e['blockedInLayer'] else 'FAIL'
        safe=s['probe']
        for touch in (False,True):
            mode='touch' if touch else 'mouse'
            if not await c.evaluate('__tapLayer.isConnected && tapAudit.visible(__tapLayer) && __tapLayer.dataset.state!=="closed"'):
                # A blocked tap can fall through to the scrim and dismiss the modal.
                # Reopen to test the other input modality independently, still via coordinates.
                for step in s['steps']: await c.step(step)
                await c.evaluate('window.__tapLayer=tapAudit.top();true')
                if inject: await c.evaluate("__tapLayer.style.pointerEvents='none';true")
            p=await c.select(safe,within=True)
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
            remains=await c.evaluate('__tapLayer.isConnected && tapAudit.visible(__tapLayer) && __tapLayer.dataset.state!=="closed"')
            if safe.get('closes'):
                check(mode+' cancel closes confirmation',not remains)
                check(mode+' cancel releases body lock',await c.evaluate('getComputedStyle(document.body).pointerEvents!=="none"'))
                # Reopen with real coordinate clicks so touch and final Escape are also tested.
                for step in s['steps']: await c.step(step)
                await c.evaluate('window.__tapLayer=tapAudit.top();true')
                if inject: await c.evaluate("__tapLayer.style.pointerEvents='none';true")
            else:
                check(mode+' layer remains open',remains)
        await c.key('Escape');await c.settle()
        check('layer closed',await c.evaluate('!__tapLayer.isConnected || __tapLayer.dataset.state==="closed" || !tapAudit.visible(__tapLayer)'))
        body=await c.evaluate('getComputedStyle(document.body).pointerEvents')
        check('body pointer lock released',body!='none',pointerEvents=body)
        p=await c.select(s['background'])
        check('background center reaches control',p['hit'] and not p['blockedInLayer'],element=p)
    except Exception as e: check('execution',False,error=str(e))
    report['status']='PASS' if all(x['pass_'] for x in report['checks']) and all(e['status']!='FAIL' for e in report['elements']) else 'FAIL'
    return report

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
            for _ in range(100):
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
            if os.name=='nt':
                await asyncio.to_thread(subprocess.run,['taskkill','/PID',str(proc.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            else:
                import signal
                try: os.killpg(proc.pid,signal.SIGTERM)
                except ProcessLookupError: pass
            try: proc.wait(timeout=10)
            except subprocess.TimeoutExpired: proc.kill();proc.wait()
            cleanup['edgeExited']=proc.poll() is not None
        for attempt in range(30):
            try: shutil.rmtree(str(profile));break
            except FileNotFoundError: break
            except OSError:
                if attempt==29: raise
                await asyncio.sleep(.2)
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
    p.add_argument('--inject-fault',action='store_true',help='negative control: pointer-events:none on top layer while body locked')
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
