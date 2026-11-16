import { formatBalance } from "@/shared/number";
import { useDestructiveConfirm } from "../shared/DestructiveConfirm";
import { S } from '@/shared/strings.generated';
import { ValuePicker } from '@/shared/ValuePicker';
import { VALUE_SPECS, formatNumber, type ValueSpec } from '@/shared/valuePickerLogic';
import { SheetSection, SheetSwitch as FxSwitch, SheetLink } from '@/shared/SheetControls';
import { useState, type ReactNode } from 'react';
import { MotionRegion } from '@/shared/MotionRegion';
import { TonePage, type ToneLeaveGuard } from './TonePage';
import { toast } from '@/shared/toast';
import { Button } from '@/shared/ui';
import { Collapse } from '@/shared/Collapse';
import { signedNumber } from './labels';
import { resetAudioFx, setAudioFx, useAudioFx, voiceLevel, withVoiceLevel, audioBookOnly, setAudioBookOnly, useTones } from './audioFx';

import { Reveal } from "../shared/MotionPresence";
/** Shared voice, music and listening sections; audio updates keep their existing paths. */
export function AudioFxPanel({setVolume,music,leaveGuard}:{setVolume:(value:number)=>void;music?:ReactNode;leaveGuard?:ToneLeaveGuard}) {
  const deletion=useDestructiveConfirm();
  const fx=useAudioFx();
  const update:typeof setAudioFx=(value)=>{try {setAudioFx(value);} catch {toast.error(S.s_copy_c669a3bf438d);}};
  const voice=voiceLevel(fx)*100;
  const tones=useTones();
  const [toneOpen,setToneOpen]=useState(false);
  return <MotionRegion motionKey={toneOpen} slideIndex={toneOpen?1:0}><div data-audio-fx className="flex min-w-0 flex-col gap-1">{deletion.dialog}
    {toneOpen?<TonePage onBack={()=>setToneOpen(false)} leaveGuard={leaveGuard}/>:<>
    <SheetSection first title={S.s_giong_doc_11f2548d}>
    <FxSlider label={S.s_am_luong_5dafca26} spec={VALUE_SPECS.voice} value={Math.round(voice)} suffix="%" onChange={v=>{const next=withVoiceLevel(v/100);setVolume(next.volume);update({boost:next.boost});}}/>
    <SheetLink label={S.s_am_sac_8c2f4e1a} onClick={()=>setToneOpen(true)} value={tones.name + (tones.scoped ? " · " + S.s_copy_0aedb2b2cf2b : "")}/>
    <FxSlider label={S.s_copy_519c2d65ca4c} spec={VALUE_SPECS.pitch} value={fx.pitch} suffix={S.s_copy_e9d6329e8255} onChange={pitch=>update({pitch})}/>
    </SheetSection>
    <Reveal when={Boolean(music)}><div className="min-w-0">{music}</div></Reveal>
    <SheetSection title={S.s_nghe_a43aafef}>
    <FxSwitch label={S.s_copy_6f00156cec07} checked={fx.mono} onChange={mono=>update({mono})}/>
    <FxSlider label={S.s_can_bang_8b88211d} spec={VALUE_SPECS.balance} value={Math.round(fx.balance*100)} format={formatBalance} onChange={v=>update({balance:v/100})}/>
    <FxSwitch label={S.s_copy_289e1cff4cbc} checked={fx.skipSilence} hint={S.s_copy_b09b5fb2264a} onChange={skipSilence=>update({skipSilence})}/>
    <Collapse open={fx.skipSilence}>
      <FxSlider label={S.s_copy_8e18e6dd7fd9} spec={VALUE_SPECS.silenceDb} value={fx.silenceDb} suffix="\u00a0dBFS" onChange={silenceDb=>update({silenceDb})}/>
      <FxSlider label={S.s_copy_19adc1b298a9} spec={VALUE_SPECS.silenceSeconds} value={fx.silenceSeconds} suffix={SECONDS} onChange={silenceSeconds=>update({silenceSeconds})}/>
      <FxSlider label={S.s_copy_483cdfec9d5f} spec={capped(VALUE_SPECS.keepSeconds,fx.silenceSeconds)} value={fx.keepSeconds} suffix={SECONDS} onChange={keepSeconds=>update({keepSeconds})}/>
    </Collapse>
    <FxSwitch label={S.s_copy_0aedb2b2cf2b} checked={audioBookOnly()} onChange={value=>{try{setAudioBookOnly(value);}catch{toast.error(S.s_copy_c669a3bf438d);}}}/>
    </SheetSection>
    <Button variant="ghost" size="sm" className="self-start px-0" onClick={()=>deletion.confirm({title:S.s_reset_question,description:S.s_reset_detail,label:S.s_ve_mac_dinh_4eb6b300,run:()=>{resetAudioFx();setVolume(1);}})}>{S.s_ve_mac_dinh_4eb6b300}</Button>
  </>}</div></MotionRegion>;
}
/** Đơn vị dính số (DESIGN "Số và đơn vị"): không xuống dòng giữa số và đơn vị. */
const DECIBELS = '\u00a0dB', SECONDS = '\u00a0s';
/** Núm âm thanh = bộ chọn giá trị hàng gọn (DESIGN mục 6): tên + giá trị (chạm để gõ), thước giữa -/+, chip tiêu biểu.
 *  Thanh có hai phía (Cao độ, ngưỡng dBFS): số đang chọn có dấu, dấu trừ thật. */
function FxSlider({format,label,spec,value,suffix=DECIBELS,disabled=false,onChange}:{label:string;spec:ValueSpec;value:number;suffix?:string;format?:(v:number)=>string;disabled?:boolean;onChange:(value:number)=>void}) {
  return <ValuePicker dense spec={spec} value={value} disabled={disabled} label={label} format={format ?? (v=>`${spec.min<0?signedNumber(v):formatNumber(spec,v)}${suffix}`)} chipLabel={v=>formatNumber(spec,v)} onPreview={onChange} onChange={onChange}/>;
}
/** "Giữ khoảng nghỉ" không quá "Dài tối thiểu". */
function capped(spec:ValueSpec,max:number):ValueSpec {
  const top=Math.min(spec.max,max);
  return {...spec,max:top,typical:spec.typical.filter(v=>v<=top)};
}
