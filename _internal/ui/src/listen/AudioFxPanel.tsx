import { S } from '@/shared/strings.generated';
import * as Slider from '@radix-ui/react-slider';
import * as Switch from '@radix-ui/react-switch';
import { toast } from '@/shared/toast';
import { Button, ChoiceRow } from '@/shared/ui';
import { FX_BANDS, FX_LABELS, FX_PRESETS, setAudioFx, useAudioFx, audioBookOnly, setAudioBookOnly } from './audioFx';

export function AudioFxPanel({volume,setVolume}:{volume:number;setVolume:(value:number)=>void}) {
  const fx=useAudioFx();
  const update:typeof setAudioFx=(value)=>{try {setAudioFx(value);} catch {toast.error(S.s_copy_c669a3bf438d);}};
  return <div data-audio-fx className="flex min-w-0 flex-col gap-1">
    <p className="pb-2 text-xs text-fg-2">{S.s_copy_d05a51c01f29}</p>
    <FxSwitch label={S.s_copy_0aedb2b2cf2b} checked={audioBookOnly()} onChange={value=>{try{setAudioBookOnly(value);}catch{toast.error(S.s_copy_c669a3bf438d);}}}/>
    <FxSlider label={S.s_am_luong_5dafca26} value={volume*100} min={0} max={100} suffix="%" onChange={v=>setVolume(v/100)}/>
    <FxSlider label={S.s_copy_c77e16da718e} value={fx.boost} min={0} max={12} onChange={boost=>update({boost})}/>
    <FxSlider label={S.s_copy_519c2d65ca4c} value={fx.pitch} min={-6} max={6} step={.5} suffix={S.s_copy_e9d6329e8255} onChange={pitch=>update({pitch})}/>
    <Button variant="ghost" size="sm" className="self-start px-0" onClick={()=>update({pitch:0})}>{S.s_ve_mac_dinh_4eb6b300}</Button>
    <FxSwitch label={S.s_copy_6f00156cec07} checked={fx.mono} onChange={mono=>update({mono})}/>
    <FxSlider label={S.s_can_bang_8b88211d} value={fx.balance*100} min={-100} max={100} suffix={S.s_copy_9bf94b95eb12} onChange={v=>update({balance:v/100})}/>
    <FxSwitch label={S.s_copy_289e1cff4cbc} checked={fx.skipSilence} onChange={skipSilence=>update({skipSilence})}/>
    <p className="text-xs text-fg-2">{S.s_copy_b09b5fb2264a}</p>
    <FxSlider label={S.s_copy_8e18e6dd7fd9} value={fx.silenceDb} min={-80} max={-45} suffix=" dBFS" disabled={!fx.skipSilence} onChange={silenceDb=>update({silenceDb})}/>
    <FxSlider label={S.s_copy_19adc1b298a9} value={fx.silenceSeconds} min={2} max={10} step={.5} suffix=" s" disabled={!fx.skipSilence} onChange={silenceSeconds=>update({silenceSeconds})}/>
    <FxSlider label={S.s_copy_483cdfec9d5f} value={fx.keepSeconds} min={1.5} max={Math.min(3,fx.silenceSeconds)} step={.1} suffix=" s" disabled={!fx.skipSilence} onChange={keepSeconds=>update({keepSeconds})}/>
    <label className="flex min-h-12 items-center justify-between gap-4 text-sm">{S.s_copy_71255f2b6855}
      <Switch.Root aria-label={S.s_copy_71255f2b6855} checked={fx.enabled} onCheckedChange={enabled=>update({enabled})} className="relative h-6 w-10 rounded-full bg-line data-[state=checked]:bg-accent">
        <Switch.Thumb className="block size-5 translate-x-0.5 rounded-full bg-panel transition-transform duration-motion-fast data-[state=checked]:translate-x-[18px]"/>
      </Switch.Root>
    </label>
    <span className="text-sm">{S.s_copy_7252e7ce0085}</span>
    <ChoiceRow label={S.s_copy_7252e7ce0085} value={String(fx.preset)} options={[...FX_LABELS.map((label,i)=>({value:String(i),label})),{value:'-1',label:S.s_copy_e3518044ceec}]} onChange={value=>{const i=Number(value);update(i<0?{enabled:true,preset:-1}:{enabled:true,preset:i,bass:0,bands:[...FX_PRESETS[i]]});}}/>
    {FX_BANDS.map((label,i)=><FxSlider key={label} label={label} value={fx.bands[i]} min={-12} max={12} disabled={!fx.enabled} onChange={value=>update({preset:-1,bands:fx.bands.map((v,j)=>j===i?value:v)})}/>)}
    <FxSlider label={S.s_copy_eb4635c58f1d} value={fx.bass} min={0} max={12} disabled={!fx.enabled} onChange={bass=>update({preset:-1,bass})}/>
  </div>;
}
function FxSwitch({label,checked,onChange}:{label:string;checked:boolean;onChange:(value:boolean)=>void}) {
  return <label className="flex min-h-12 items-center justify-between gap-4 text-sm">{label}
    <Switch.Root aria-label={label} checked={checked} onCheckedChange={onChange} className="relative h-6 w-10 rounded-full bg-line data-[state=checked]:bg-accent">
      <Switch.Thumb className="block size-5 translate-x-0.5 rounded-full bg-panel transition-transform duration-motion-fast data-[state=checked]:translate-x-[18px]"/>
    </Switch.Root>
  </label>;
}
function FxSlider({label,value,min,max,step=1,suffix=' dB',disabled=false,onChange}:{label:string;value:number;min:number;max:number;step?:number;suffix?:string;disabled?:boolean;onChange:(value:number)=>void}) {
  return <div aria-disabled={disabled || undefined} className={`min-w-0 transition-opacity duration-motion-fast ${disabled?'opacity-50':''}`}>
    <div className="flex items-center justify-between gap-3 text-sm"><span>{label}</span><span className="tabular text-fg-2">{value.toLocaleString('vi-VN',{maximumFractionDigits:1})}{suffix}</span></div>
    <Slider.Root aria-label={label} min={min} max={max} step={step} value={[value]} disabled={disabled} onValueChange={([v])=>onChange(v)} className="relative flex h-11 w-full touch-none items-center">
      <Slider.Track className="relative h-1 grow rounded-full bg-line"><Slider.Range className="absolute h-full rounded-full bg-accent"/></Slider.Track>
      <Slider.Thumb aria-label={label} aria-valuetext={`${value}${suffix}`} className="block size-3.5 rounded-full bg-accent outline-none focus-visible:ring-2 focus-visible:ring-focus"/>
    </Slider.Root>
  </div>;
}
