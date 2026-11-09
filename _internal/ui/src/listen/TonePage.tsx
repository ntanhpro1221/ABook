import { useEffect, useRef, useState, type MutableRefObject } from 'react';
import { ArrowLeft, GripVertical } from 'lucide-react';
import * as Switch from '@radix-ui/react-switch';
import { S } from '@/shared/strings.generated';
import { Button } from '@/shared/ui';
import { toast } from '@/shared/toast';
import { useBackLayer } from '@/shared/backStack';
import { changeTone, getTones, useTones } from './audioFx';
import { BUILTIN_TONES, type ToneLibrary } from './tonePresets';

export type ToneLeaveGuard = MutableRefObject<((leave:()=>void)=>void)|null>;
export function TonePage({onBack,leaveGuard}:{onBack:()=>void;leaveGuard?:ToneLeaveGuard}) {
  const lib=useTones(),page=useRef<HTMLDivElement>(null),pending=useRef<(()=>void)|null>(null);
  const [asking,setAsking]=useState(false),[naming,setNaming]=useState<{id?:string;duplicate?:boolean;leave?:boolean}|null>(null),[name,setName]=useState('');
  const run=(fn:(l:ToneLibrary)=>void)=>{try{changeTone(fn);return true;}catch{toast.error(S.s_copy_c669a3bf438d);return false;}};
  const leave=(action:()=>void)=>{if(lib.hasEdits){run(l=>l.prepareLeave());pending.current=action;setAsking(true);}else action();};
  const latestLeave=useRef(leave);latestLeave.current=leave;
  useEffect(()=>{if(leaveGuard)leaveGuard.current=action=>latestLeave.current(action);return()=>{if(leaveGuard)leaveGuard.current=null;};},[leaveGuard]);
  const finish=()=>{if(getTones().hasEdits){run(l=>l.prepareLeave());setAsking(true);return;}setAsking(false);const action=pending.current;pending.current=null;action?.();};
  useEffect(()=>{if(asking||naming)page.current?.lastElementChild?.scrollIntoView({block:'end'});},[asking,naming]);
  useBackLayer(true,()=>naming?setNaming(null):asking?setAsking(false):leave(onBack),page);
  const suggest=()=>S.s_tone_suggest(lib.data.mine.length+1);
  const form=(value:string,kind:NonNullable<typeof naming>)=>{setName(value);setNaming(kind);};
  const current=lib.selected;
  const remove=(id:string)=>{let token:ReturnType<ToneLibrary['delete']>=null;if(!run(l=>{token=l.delete(id);})||!token)return;const deleted=token;toast(S.s_tone_deleted,{action:{label:S.s_hoan_tac_e72ff675,onClick:()=>{run(l=>l.undo(deleted));}}});};
  return <div ref={page} data-tone-page className="flex min-w-0 flex-col gap-2">
    <div className="flex min-h-12 items-center gap-3"><Button variant="ghost" size="sm" aria-label={S.s_tone_back} onClick={()=>leave(onBack)}><ArrowLeft className="size-5"/></Button><h2 className="font-semibold">{S.s_am_sac_8c2f4e1a}</h2></div>
    {[[S.s_tone_builtins,BUILTIN_TONES],[S.s_tone_mine,lib.data.mine]].map(([heading,items])=><section key={String(heading)}>
      <h3 className="py-2 text-xs font-semibold text-fg-2">{String(heading)}</h3>
      {(items as typeof BUILTIN_TONES).map(p=><div key={p.id} data-tone-id={p.id} className="flex min-h-12 items-center gap-2 border-b border-line" onDragOver={e=>e.preventDefault()} onDrop={e=>{e.preventDefault();run(l=>l.move(e.dataTransfer.getData('text/plain'),lib.data.mine.findIndex(x=>x.id===p.id)));}}>
        <button type="button" aria-label={p.name} className="min-h-12 min-w-0 flex-1 py-2 text-left text-sm" aria-pressed={current.id===p.id} onClick={()=>run(l=>l.select(p.id))}><span className={current.id===p.id?'font-semibold text-accent':''}>{p.name}</span><span aria-hidden className="float-right px-1">{current.id===p.id?'✓':''}</span></button>
        {p.id.startsWith('user:')&&<button type="button" draggable aria-label={S.s_tone_drag} title={p.name} className="flex size-12 shrink-0 touch-none items-center justify-center text-fg-2" onDragStart={e=>e.dataTransfer.setData('text/plain',p.id)}
          onPointerDown={e=>{e.currentTarget.setPointerCapture(e.pointerId);}}
          onPointerMove={e=>{if(!e.currentTarget.hasPointerCapture(e.pointerId)||!e.buttons)return;const id=document.elementFromPoint(e.clientX,e.clientY)?.closest('[data-tone-id]')?.getAttribute('data-tone-id');const to=lib.data.mine.findIndex(p=>p.id===id);if(to>=0)run(l=>l.move(p.id,to));}}
          onKeyDown={e=>{if(e.key==='ArrowUp'||e.key==='ArrowDown'){e.preventDefault();run(l=>l.move(p.id,l.data.mine.findIndex(x=>x.id===p.id)+(e.key==='ArrowUp'?-1:1)));}}}><GripVertical className="size-4"/></button>}
      </div>)}
    </section>)}
    {current.id.startsWith('user:')&&<div className="flex flex-wrap gap-x-4"><Button variant="ghost" onClick={()=>form(lib.preset?.name??suggest(),{id:current.id})}>{S.s_doi_ten_a2a0dc70}</Button><Button variant="ghost" onClick={()=>form(suggest(),{id:current.id,duplicate:true})}>{S.s_tone_duplicate}</Button><Button variant="ghost" onClick={()=>remove(current.id)}>{S.s_xoa_777195ab}</Button></div>}
    <p className="pt-2 text-sm font-semibold" aria-live="polite">{lib.name}</p>
    <svg viewBox="0 0 300 96" role="img" aria-label={S.s_am_sac_8c2f4e1a} className="h-24 w-full text-accent"><path d="M0 48H300" stroke="currentColor" opacity=".2"/><polyline points={current.bands.map((v,i)=>`${12+i*69},${48-v*3.4}`).join(' ')} fill="none" stroke="currentColor" strokeWidth="2"/>{current.bands.map((v,i)=><circle key={i} cx={12+i*69} cy={48-v*3.4} r="3" fill="currentColor"/>)}</svg>
    <div className="flex justify-between gap-1">{[S.s_tone_band_0,S.s_tone_band_1,S.s_tone_band_2,S.s_tone_band_3,S.s_tone_band_4].map((label,i)=><label key={label} className="flex min-w-0 flex-1 flex-col items-center gap-2 text-xs"><span className="tabular">{`${current.bands[i]} dB`}</span><input aria-label={label} aria-valuetext={`${`${current.bands[i]} dB`}`} type="range" min={-12} max={12} step={1} value={current.bands[i]} onChange={e=>run(l=>l.edit(i,Number(e.target.value)))} onDoubleClick={()=>run(l=>l.edit(i,0))} className="h-32 w-11 accent-accent [direction:rtl] [writing-mode:vertical-lr]"/><span>{label}</span></label>)}</div>
    <p className="text-xs text-fg-2">{S.s_tone_reset}</p>
    {(current.id==='draft'||lib.dirty)&&<Button onClick={()=>form(suggest(),{})}>{S.s_tone_save}</Button>}
    <label className="flex min-h-12 items-center justify-between gap-3 text-sm">{S.s_tone_scope}<Switch.Root aria-label={S.s_tone_scope} checked={lib.scoped} onCheckedChange={value=>run(l=>l.scope(value))} className="h-6 w-10 shrink-0 rounded-full bg-line data-[state=checked]:bg-accent"><Switch.Thumb className="block size-5 translate-x-0.5 rounded-full bg-panel transition-transform duration-motion-fast data-[state=checked]:translate-x-[18px]"/></Switch.Root></label>
    {asking&&<div className="flex flex-col gap-2 rounded-control border border-line p-3" role="group" aria-label={S.s_tone_leave}><p>{S.s_tone_leave}</p><Button onClick={()=>{if(run(l=>l.save(l.preset?.name??suggest(),true)))finish();}}>{S.s_tone_overwrite}</Button><Button onClick={()=>form(suggest(),{leave:true})}>{S.s_tone_new}</Button><Button variant="ghost" onClick={()=>{if(run(l=>l.discard()))finish();}}>{S.s_tone_discard}</Button></div>}
    {naming&&<form className="flex flex-col gap-2 border-t border-line py-3" onSubmit={e=>{e.preventDefault();const kind=naming;if(run(l=>{if(kind.duplicate)l.duplicate(kind.id!,name);else if(kind.id)l.rename(kind.id,name);else l.save(name);})){setNaming(null);if(kind.leave)finish();}}}><label className="text-sm">{S.s_tone_name}<input autoFocus maxLength={80} value={name} onChange={e=>setName(e.target.value)} className="mt-2 min-h-12 w-full rounded-control border border-line bg-panel px-3 text-fg"/></label><Button type="submit" disabled={!name.trim()}>{S.s_luu_e91f26c0}</Button><Button type="button" variant="ghost" onClick={()=>setNaming(null)}>{S.s_tone_back}</Button></form>}
  </div>;
}
