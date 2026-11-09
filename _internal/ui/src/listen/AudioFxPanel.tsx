import { S } from '@/shared/strings.generated';
import * as Slider from '@radix-ui/react-slider';
import * as Switch from '@radix-ui/react-switch';
import { useState, type ReactNode } from 'react';
import { MotionRegion } from '@/shared/MotionRegion';
import { TonePage, type ToneLeaveGuard } from './TonePage';
import { toast } from '@/shared/toast';
import { Button } from '@/shared/ui';
import { Collapse } from '@/shared/Collapse';
import { signedNumber } from './labels';
import { VOICE_MAX, resetAudioFx, setAudioFx, useAudioFx, voiceLevel, withVoiceLevel, audioBookOnly, setAudioBookOnly, useTones } from './audioFx';

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
    <FxSlider label={S.s_giong_doc_11f2548d} value={Math.round(voice)} min={0} max={VOICE_MAX*100} step={5} suffix="%" onChange={v=>{const next=withVoiceLevel(v/100);setVolume(next.volume);update({boost:next.boost});}}/>
    {music}
    <button type="button" aria-label={S.s_am_sac_8c2f4e1a} className="flex min-h-12 items-center justify-between gap-3 py-2 text-sm" onClick={()=>setToneOpen(true)} data-tone-open><span>{S.s_am_sac_8c2f4e1a}</span><span className="min-w-0 max-w-[60%] break-words text-right text-fg-2">{tones.name}{tones.scoped&&<small className="block">{S.s_copy_0aedb2b2cf2b}</small>}</span></button>
    <FxSwitch label={S.s_copy_6f00156cec07} checked={fx.mono} onChange={mono=>update({mono})}/>
    <FxSlider label={S.s_can_bang_8b88211d} value={fx.balance*100} min={-100} max={100} suffix={S.s_copy_9bf94b95eb12} onChange={v=>update({balance:v/100})}/>
    <FxSwitch label={S.s_copy_289e1cff4cbc} checked={fx.skipSilence} onChange={skipSilence=>update({skipSilence})}/>
    <p className="text-xs text-fg-2">{S.s_copy_b09b5fb2264a}</p>
    <Collapse open={fx.skipSilence}>
      <FxSlider label={S.s_copy_8e18e6dd7fd9} value={fx.silenceDb} min={-80} max={-45} suffix=" dBFS" onChange={silenceDb=>update({silenceDb})}/>
      <FxSlider label={S.s_copy_19adc1b298a9} value={fx.silenceSeconds} min={2} max={10} step={.5} suffix=" s" onChange={silenceSeconds=>update({silenceSeconds})}/>
      <FxSlider label={S.s_copy_483cdfec9d5f} value={fx.keepSeconds} min={1.5} max={Math.min(3,fx.silenceSeconds)} step={.1} suffix=" s" onChange={keepSeconds=>update({keepSeconds})}/>
    </Collapse>
    <FxSwitch label={S.s_copy_0aedb2b2cf2b} checked={audioBookOnly()} onChange={value=>{try{setAudioBookOnly(value);}catch{toast.error(S.s_copy_c669a3bf438d);}}}/>
    <FxSlider label={S.s_copy_519c2d65ca4c} value={fx.pitch} min={-6} max={6} step={.5} suffix={S.s_copy_e9d6329e8255} onChange={pitch=>update({pitch})}/>
    <Button variant="ghost" size="sm" className="self-start px-0" onClick={()=>{try{resetAudioFx();setVolume(1);}catch{toast.error(S.s_copy_c669a3bf438d);}}}>{S.s_ve_mac_dinh_4eb6b300}</Button>
  </>}</div></MotionRegion>;
}
function FxSwitch({label,checked,onChange}:{label:string;checked:boolean;onChange:(value:boolean)=>void}) {
  return <label className="flex min-h-12 items-center justify-between gap-4 text-sm">{label}
    <Switch.Root aria-label={label} checked={checked} onCheckedChange={onChange} className="h-6 w-10 rounded-full bg-line data-[state=checked]:bg-accent">
      <Switch.Thumb className="block size-5 translate-x-0.5 rounded-full bg-panel transition-transform duration-motion-fast data-[state=checked]:translate-x-[18px]"/>
    </Switch.Root>
  </label>;
}
function FxSlider({label,value,min,max,step=1,suffix=' dB',disabled=false,onChange}:{label:string;value:number;min:number;max:number;step?:number;suffix?:string;disabled?:boolean;onChange:(value:number)=>void}) {
  // Thanh có hai phía (Cân bằng, Cao độ, ngưỡng dBFS): số có dấu, dấu trừ thật.
  const shown=min<0?signedNumber(value):value.toLocaleString('vi-VN',{maximumFractionDigits:1});
  return <div aria-disabled={disabled || undefined} className={`min-w-0 transition-opacity duration-motion-fast ${disabled?'opacity-50':''}`}>
    <div className="flex items-center justify-between gap-3 text-sm"><span>{label}</span><span className="tabular text-fg-2">{shown}{suffix}</span></div>
    <Slider.Root aria-label={label} min={min} max={max} step={step} value={[value]} disabled={disabled} onValueChange={([v])=>onChange(v)} className="relative flex h-11 w-full touch-none items-center">
      <Slider.Track className="relative h-1 grow rounded-full bg-line"><Slider.Range className="absolute h-full rounded-full bg-accent"/></Slider.Track>
      <Slider.Thumb aria-label={label} aria-valuetext={`${shown}${suffix}`} className="block size-3.5 rounded-full bg-accent outline-none focus-visible:ring-2 focus-visible:ring-focus"/>
    </Slider.Root>
  </div>;
}
