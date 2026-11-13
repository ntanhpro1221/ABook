import { useEffect, useRef, useState, type MutableRefObject } from 'react';
import { MoreHorizontal, Plus } from 'lucide-react';
import * as Slider from '@radix-ui/react-slider';
import { Switch } from '@/desktop/Switch';
import { S } from '@/shared/strings.generated';
import { Button } from '@/shared/ui';
import { useSheetPage } from './sheetPages';
import { BackButton } from '@/shared/ScreenHeader';
import { Collapse } from '@/shared/Collapse';
import { toast } from '@/shared/toast';
import { useBackLayer } from '@/shared/backStack';
import { changeTone, getTones, useTones } from './audioFx';
import { signedNumber } from './labels';
import { BUILTIN_TONES, type ToneLibrary } from './tonePresets';

/** Việc chữ của trang (Lưu, Đổi tên, Tạo âm sắc): chữ nhấn, ô chạm 48 - như TextAction của Android, TextLink accent của Qt. */
const LINK='flex min-h-12 items-center text-sm font-medium text-accent-text hover:underline';
// Xoá: chữ màu nguy hiểm, không hổ phách như Đổi tên / Nhân bản cạnh nó (soát 10-11 L13).
const DANGER_LINK='flex min-h-12 items-center text-sm font-medium text-danger hover:underline';
const BANDS=[S.s_tone_band_0,S.s_tone_band_1,S.s_tone_band_2,S.s_tone_band_3,S.s_tone_band_4];
const db=(value:number)=>S.s_tone_db(signedNumber(value));

/** Một đường cong âm sắc (lớn và nhỏ dùng chung, Android drawTone): điểm i ở tâm cột i trong năm cột, ±12 dB chạm mép, nối mềm, hai đầu kéo phẳng ra mép. */
function tonePoints(bands:number[],width:number,height:number,pad:number){return bands.map((v,i)=>[width*(i+.5)/bands.length,height/2-v/12*(height/2-pad)] as const);}
function tonePath(bands:number[],width:number,height:number,pad:number){
  const p=tonePoints(bands,width,height,pad);
  return `M0 ${p[0][1]}L${p[0][0]} ${p[0][1]}`+p.slice(1).map(([x,y],i)=>{const [ax,ay]=p[i],mid=(ax+x)/2;return `C${mid} ${ay} ${mid} ${y} ${x} ${y}`;}).join('')+`L${width} ${p[p.length-1][1]}`;
}
/** Một chấm tròn ở (x, y): đoạn dài 0 nét tròn - vẫn tròn khi khung giãn ngang (preserveAspectRatio none). */
const dotPath=(x:number,y:number)=>`M${x} ${y}H${x}`;
/** Đường cong xem trước của một dòng: 48 × 24, mực phụ (đang chọn: nhấn). */
function ToneThumb({bands,chosen}:{bands:number[];chosen:boolean}){
  return <svg aria-hidden viewBox="0 0 48 24" className={`h-6 w-12 shrink-0 ${chosen?'text-accent':'text-fg-2'}`}><path d={tonePath(bands,48,24,2)} fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>;
}

export type ToneLeaveGuard = MutableRefObject<((leave:()=>void)=>void)|null>;
/**
 * Trang Âm sắc (cùng bố cục Android / Qt): đầu trang ← + tên; vùng chỉnh ở trên (tên đang dùng, đường cong trong khung có vạch 0 dB, năm thanh dọc) để
 * chọn một âm sắc là thấy ngay đường cong đổi; danh sách Có sẵn / Của tôi ở dưới. Dòng: dấu chọn tròn, tên, đường cong nhỏ; dòng Của tôi có nút …
 * (Đổi tên / Nhân bản / Xoá), kéo cả dòng hay Alt+↑/↓ để xếp lại; "Tạo âm sắc" ở cuối nhóm.
 */
export function TonePage({onBack,leaveGuard}:{onBack:()=>void;leaveGuard?:ToneLeaveGuard}) {
  const lib=useTones(),page=useRef<HTMLDivElement>(null),pending=useRef<(()=>void)|null>(null);
  const [asking,setAsking]=useState(false),[naming,setNaming]=useState<{id?:string;duplicate?:boolean;leave?:boolean}|null>(null),[name,setName]=useState('');
  const [menu,setMenu]=useState<string|null>(null);
  const run=(fn:(l:ToneLibrary)=>void)=>{try{changeTone(fn);return true;}catch{toast.error(S.s_copy_c669a3bf438d);return false;}};
  const leave=(action:()=>void)=>{if(lib.hasEdits){run(l=>l.prepareLeave());pending.current=action;setAsking(true);}else action();};
  const latestLeave=useRef(leave);latestLeave.current=leave;
  useEffect(()=>{if(leaveGuard)leaveGuard.current=action=>latestLeave.current(action);return()=>{if(leaveGuard)leaveGuard.current=null;};},[leaveGuard]);
  const finish=()=>{if(getTones().hasEdits){run(l=>l.prepareLeave());setAsking(true);return;}setAsking(false);const action=pending.current;pending.current=null;action?.();};
  useEffect(()=>{if(asking||naming)page.current?.lastElementChild?.scrollIntoView({block:'end'});},[asking,naming]);
  useBackLayer(true,()=>naming?setNaming(null):asking?setAsking(false):leave(onBack),page);
  // Trong tấm trượt (điện thoại) đầu tấm thành "← Âm sắc"; hộp nổi máy tính không có đầu tấm nên trang tự vẽ.
  const inSheet=useSheetPage(true,S.s_am_sac_8c2f4e1a,()=>leave(onBack));
  const suggest=()=>S.s_tone_suggest(lib.data.mine.length+1);
  const form=(value:string,kind:NonNullable<typeof naming>)=>{setMenu(null);setName(value);setNaming(kind);};
  const current=lib.selected;
  const remove=(id:string)=>{setMenu(null);let token:ReturnType<ToneLibrary['delete']>=null;if(!run(l=>{token=l.delete(id);})||!token)return;const deleted=token;toast(S.s_tone_deleted,{action:{label:S.s_hoan_tac_e72ff675,onClick:()=>{run(l=>l.undo(deleted));}}});};
  const move=(id:string,by:number)=>run(l=>l.move(id,l.data.mine.findIndex(x=>x.id===id)+by));
  const row=(p:typeof BUILTIN_TONES[number],mine:boolean)=>{const chosen=current.id===p.id;return <div key={p.id} data-tone-id={p.id} className="border-b border-line"
    draggable={mine||undefined} onDragStart={mine?e=>e.dataTransfer.setData('text/plain',p.id):undefined}
    onDragOver={mine?e=>e.preventDefault():undefined} onDrop={mine?e=>{e.preventDefault();run(l=>l.move(e.dataTransfer.getData('text/plain'),l.data.mine.findIndex(x=>x.id===p.id)));}:undefined}>
    <div className="flex min-h-14 items-center gap-2">
      <button type="button" role="radio" aria-checked={chosen} aria-label={p.name} title={mine?S.s_tone_drag:undefined} className="flex min-h-14 min-w-0 flex-1 items-center gap-3 py-2 text-left"
        onClick={()=>run(l=>l.select(p.id))} onKeyDown={mine?e=>{if(e.altKey&&(e.key==='ArrowUp'||e.key==='ArrowDown')){e.preventDefault();move(p.id,e.key==='ArrowUp'?-1:1);}}:undefined}>
        <span aria-hidden className={`grid size-5 shrink-0 place-items-center rounded-full ring-2 ring-inset transition-colors duration-motion-fast ${chosen?'ring-accent':'ring-fg-2'}`}><span className={`size-2.5 rounded-full bg-accent transition-transform duration-motion-fast ${chosen?'scale-100':'scale-0'}`}/></span>
        <span className="min-w-0 flex-1 break-words">{p.name}</span><ToneThumb bands={p.bands} chosen={chosen}/>
      </button>
      {mine&&<button type="button" aria-label={S.s_them_tuy_chon_cho_0_82a2cf4d(p.name)} aria-expanded={menu===p.id} className="-mr-3 flex size-12 shrink-0 items-center justify-center rounded-control text-fg-2 hover:text-fg" onClick={()=>setMenu(menu===p.id?null:p.id)}><MoreHorizontal className="size-5"/></button>}
    </div>
    {mine&&<Collapse open={menu===p.id}><div className="flex flex-wrap gap-x-6 pb-1 pl-8">
      <button type="button" className={LINK} onClick={()=>form(p.name,{id:p.id})}>{S.s_doi_ten_a2a0dc70}</button>
      <button type="button" className={LINK} onClick={()=>form(suggest(),{id:p.id,duplicate:true})}>{S.s_tone_duplicate}</button>
      <button type="button" className={DANGER_LINK} onClick={()=>remove(p.id)}>{S.s_xoa_777195ab}</button>
    </div></Collapse>}
  </div>;};
  return <div ref={page} data-tone-page className="flex min-w-0 flex-col">
    {!inSheet&&<div className="flex min-h-12 items-center"><BackButton label={S.s_quay_lai_6d793582} onClick={()=>leave(onBack)}/><p className="font-medium">{S.s_am_sac_8c2f4e1a}</p></div>}
    <div className="flex min-h-12 items-center justify-between gap-3"><p className="min-w-0 font-medium" aria-live="polite">{lib.name}</p>
      {(current.id==='draft'||lib.dirty)&&<button type="button" className={LINK} onClick={()=>form(suggest(),{})}>{S.s_tone_save}</button>}</div>
    <svg viewBox="0 0 300 80" preserveAspectRatio="none" role="img" aria-label={S.s_am_sac_8c2f4e1a} className="box-content h-20 w-full rounded-control border border-line py-3 text-accent">
      <path d="M0 40H300" stroke="var(--line)" strokeDasharray="4 4" vectorEffect="non-scaling-stroke"/>
      <path d={tonePath(current.bands,300,80,2)} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" vectorEffect="non-scaling-stroke"/>
      {tonePoints(current.bands,300,80,2).map(([x,y],i)=><path key={i} d={dotPath(x,y)} stroke="currentColor" strokeWidth="6" strokeLinecap="round" vectorEffect="non-scaling-stroke"/>)}
    </svg>
    <div className="flex pt-2">{BANDS.map((label,i)=><div key={label} className="flex min-w-0 flex-1 flex-col items-center gap-1 text-xs text-fg-2">
      {db(current.bands[i])}
      <Slider.Root orientation="vertical" aria-label={label} min={-12} max={12} step={1} value={[current.bands[i]]} onValueChange={([v])=>run(l=>l.edit(i,v))} onDoubleClick={()=>run(l=>l.edit(i,0))}
        className="relative flex h-32 w-12 touch-none flex-col items-center">
        <Slider.Track className="relative w-1 grow rounded-full bg-line"><span aria-hidden className="absolute top-1/2 -left-1.5 h-px w-4 bg-fg-2"/><span aria-hidden className="absolute inset-x-0 rounded-full bg-accent" style={{top:`${50-Math.max(0,current.bands[i])/24*100}%`,height:`${Math.abs(current.bands[i])/24*100}%`}}/></Slider.Track>
        <Slider.Thumb aria-label={label} aria-valuetext={db(current.bands[i])} className="block size-3.5 rounded-full bg-accent outline-none focus-visible:ring-2 focus-visible:ring-focus"/>
      </Slider.Root>
      <span>{label}</span></div>)}</div>
    <p className="pt-2 text-center text-xs text-fg-2">{S.s_tone_reset}</p>
    <h3 className="pt-4 pb-1 text-sm text-fg-2">{S.s_tone_builtins}</h3>
    <div role="radiogroup" aria-label={S.s_tone_builtins}>{BUILTIN_TONES.map(p=>row(p,false))}</div>
    <h3 className="pt-4 pb-1 text-sm text-fg-2">{S.s_tone_mine}</h3>
    <div role="radiogroup" aria-label={S.s_tone_mine}>{lib.data.mine.map(p=>row(p,true))}</div>
    <button type="button" data-tone-add className={`${LINK} gap-3`} onClick={()=>form(suggest(),{})}><Plus aria-hidden className="size-5"/>{S.s_tone_add}</button>
    <label className="mt-2 flex min-h-12 items-center justify-between gap-3 text-sm">{S.s_copy_0aedb2b2cf2b}<Switch label={S.s_copy_0aedb2b2cf2b} checked={lib.scoped} onCheckedChange={value=>run(l=>l.scope(value))}/></label>
    {asking&&<div className="flex flex-col gap-2 rounded-control border border-line p-3" role="group" aria-label={S.s_tone_leave}><p>{S.s_tone_leave}</p><Button onClick={()=>{if(run(l=>l.save(l.preset?.name??suggest(),true)))finish();}}>{S.s_tone_overwrite}</Button><Button onClick={()=>form(suggest(),{leave:true})}>{S.s_tone_new}</Button><Button variant="ghost" onClick={()=>{if(run(l=>l.discard()))finish();}}>{S.s_tone_discard}</Button></div>}
    {naming&&<form className="flex flex-col gap-2 border-t border-line py-3" onSubmit={e=>{e.preventDefault();const kind=naming;if(run(l=>{if(kind.duplicate)l.duplicate(kind.id!,name);else if(kind.id)l.rename(kind.id,name);else l.save(name);})){setNaming(null);if(kind.leave)finish();}}}><label className="text-sm">{S.s_tone_name}<input autoFocus maxLength={80} value={name} onChange={e=>setName(e.target.value)} className="mt-2 min-h-12 w-full rounded-control border border-line bg-panel px-3 text-fg"/></label><Button type="submit" disabled={!name.trim()}>{S.s_luu_e91f26c0}</Button><Button type="button" variant="ghost" onClick={()=>setNaming(null)}>{S.s_tone_back}</Button></form>}
  </div>;
}
