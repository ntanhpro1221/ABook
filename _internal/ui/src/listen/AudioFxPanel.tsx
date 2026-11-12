import { formatBalance } from "@/shared/number";
import { S } from '@/shared/strings.generated';
import { ValuePicker } from '@/shared/ValuePicker';
import { VALUE_SPECS, formatNumber, type ValueSpec } from '@/shared/valuePickerLogic';
import { Switch } from '@/desktop/Switch';
import { useState, type ReactNode } from 'react';
import { MotionRegion } from '@/shared/MotionRegion';
import { TonePage, type ToneLeaveGuard } from './TonePage';
import { toast } from '@/shared/toast';
import { Button } from '@/shared/ui';
import { Collapse } from '@/shared/Collapse';
import { signedNumber } from './labels';
import { resetAudioFx, setAudioFx, useAudioFx, voiceLevel, withVoiceLevel, audioBookOnly, setAudioBookOnly, useTones } from './audioFx';

/** Trang Âm thanh (DESIGN.md "Âm thanh khi nghe"), cùng thứ tự với Android / Qt: Giọng đọc 0-200 % (100 % = gốc) → Nhạc nền (`music`, ngay dưới) →
 *  Âm sắc một hàng cuộn ngang (dải tần chỉ khi Tự chỉnh) → Mono, Cân bằng, Bỏ khoảng lặng → Riêng sách này → Cao độ ở cuối → Về mặc định (mọi thứ, áp ngay). */
export function AudioFxPanel({setVolume,music,leaveGuard}:{setVolume:(value:number)=>void;music?:ReactNode;leaveGuard?:ToneLeaveGuard}) {
  const fx=useAudioFx();
  const update:typeof setAudioFx=(value)=>{try {setAudioFx(value);} catch {toast.error(S.s_copy_c669a3bf438d);}};
  const voice=voiceLevel(fx)*100;
  const tones=useTones();
  const [toneOpen,setToneOpen]=useState(false);
  return <MotionRegion motionKey={toneOpen} slideIndex={toneOpen?1:0}><div data-audio-fx className="flex min-w-0 flex-col gap-1">
    {toneOpen?<TonePage onBack={()=>setToneOpen(false)} leaveGuard={leaveGuard}/>:<>
    <FxSlider label={S.s_giong_doc_11f2548d} spec={VALUE_SPECS.voice} value={Math.round(voice)} suffix="%" onChange={v=>{const next=withVoiceLevel(v/100);setVolume(next.volume);update({boost:next.boost});}}/>
    {/* Dòng Nhạc nền là dòng menu (có lề 8 px và biểu tượng): trong tấm Âm thanh (không phải hộp nổi) chữ phải thẳng cột với Giọng đọc, Âm sắc, Mono - bỏ lề và biểu tượng đầu dòng. */}
    {music&&<div className="min-w-0 [&_[data-player-menu-row]]:px-0 [&_[data-player-menu-row]_svg]:!-ml-1 [[data-radix-popper-content-wrapper]_&_[data-player-menu-row]]:w-[calc(100%+0.5rem)]">{music}</div>}
    <button type="button" aria-label={S.s_am_sac_8c2f4e1a} className="flex min-h-12 items-center justify-between gap-3 py-2 text-sm" onClick={()=>setToneOpen(true)} data-tone-open><span>{S.s_am_sac_8c2f4e1a}</span><span className="min-w-0 max-w-[60%] break-words text-right text-fg-2">{tones.name}{tones.scoped&&<small className="block">{S.s_copy_0aedb2b2cf2b}</small>}</span></button>
    <FxSwitch label={S.s_copy_6f00156cec07} checked={fx.mono} onChange={mono=>update({mono})}/>
    <FxSlider label={S.s_can_bang_8b88211d} spec={VALUE_SPECS.balance} value={Math.round(fx.balance*100)} format={formatBalance} onChange={v=>update({balance:v/100})}/>
    <FxSwitch label={S.s_copy_289e1cff4cbc} checked={fx.skipSilence} onChange={skipSilence=>update({skipSilence})}/>
    <p className="text-xs text-fg-2">{S.s_copy_b09b5fb2264a}</p>
    <Collapse open={fx.skipSilence}>
      <FxSlider label={S.s_copy_8e18e6dd7fd9} spec={VALUE_SPECS.silenceDb} value={fx.silenceDb} suffix=" dBFS" onChange={silenceDb=>update({silenceDb})}/>
      <FxSlider label={S.s_copy_19adc1b298a9} spec={VALUE_SPECS.silenceSeconds} value={fx.silenceSeconds} suffix=" s" onChange={silenceSeconds=>update({silenceSeconds})}/>
      <FxSlider label={S.s_copy_483cdfec9d5f} spec={capped(VALUE_SPECS.keepSeconds,fx.silenceSeconds)} value={fx.keepSeconds} suffix=" s" onChange={keepSeconds=>update({keepSeconds})}/>
    </Collapse>
    <FxSwitch label={S.s_copy_0aedb2b2cf2b} checked={audioBookOnly()} onChange={value=>{try{setAudioBookOnly(value);}catch{toast.error(S.s_copy_c669a3bf438d);}}}/>
    <FxSlider label={S.s_copy_519c2d65ca4c} spec={VALUE_SPECS.pitch} value={fx.pitch} suffix={S.s_copy_e9d6329e8255} onChange={pitch=>update({pitch})}/>
    <Button variant="ghost" size="sm" className="self-start px-0" onClick={()=>{try{resetAudioFx();setVolume(1);}catch{toast.error(S.s_copy_c669a3bf438d);}}}>{S.s_ve_mac_dinh_4eb6b300}</Button>
  </>}</div></MotionRegion>;
}
function FxSwitch({label,checked,onChange}:{label:string;checked:boolean;onChange:(value:boolean)=>void}) {
  return <label className="flex min-h-12 items-center justify-between gap-4 text-sm">{label}
    <Switch label={label} checked={checked} onCheckedChange={onChange}/>
  </label>;
}
/** Núm âm thanh = bộ chọn giá trị hàng gọn (DESIGN mục 6): tên + giá trị (chạm để gõ), thước giữa -/+, chip tiêu biểu.
 *  Thanh có hai phía (Cao độ, ngưỡng dBFS): số đang chọn có dấu, dấu trừ thật. */
function FxSlider({format,label,spec,value,suffix=' dB',disabled=false,onChange}:{label:string;spec:ValueSpec;value:number;suffix?:string;format?:(v:number)=>string;disabled?:boolean;onChange:(value:number)=>void}) {
  return <ValuePicker dense spec={spec} value={value} disabled={disabled} label={label} format={format ?? (v=>`${spec.min<0?signedNumber(v):formatNumber(spec,v)}${suffix}`)} chipLabel={v=>formatNumber(spec,v)} onPreview={onChange} onChange={onChange}/>;
}
/** "Giữ khoảng nghỉ" không quá "Dài tối thiểu". */
function capped(spec:ValueSpec,max:number):ValueSpec {
  const top=Math.min(spec.max,max);
  return {...spec,max:top,typical:spec.typical.filter(v=>v<=top)};
}
