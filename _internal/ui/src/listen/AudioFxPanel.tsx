import { S } from '@/shared/strings.generated';
import { ValuePicker } from '@/shared/ValuePicker';
import { VALUE_SPECS, formatNumber, type ValueSpec } from '@/shared/valuePickerLogic';
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
    <FxSlider label={S.s_am_luong_5dafca26} spec={VALUE_SPECS.volume} value={Math.round(volume*100)} suffix="%" onChange={v=>setVolume(v/100)}/>
    <FxSlider label={S.s_copy_c77e16da718e} spec={VALUE_SPECS.boost} value={fx.boost} onChange={boost=>update({boost})}/>
    <FxSlider label={S.s_copy_519c2d65ca4c} spec={VALUE_SPECS.pitch} value={fx.pitch} suffix={S.s_copy_e9d6329e8255} onChange={pitch=>update({pitch})}/>
    <Button variant="ghost" size="sm" className="self-start px-0" onClick={()=>update({pitch:0})}>{S.s_ve_mac_dinh_4eb6b300}</Button>
    <FxSwitch label={S.s_copy_6f00156cec07} checked={fx.mono} onChange={mono=>update({mono})}/>
    <FxSlider label={S.s_can_bang_8b88211d} spec={VALUE_SPECS.balance} value={Math.round(fx.balance*100)} suffix={S.s_copy_9bf94b95eb12} onChange={v=>update({balance:v/100})}/>
    <FxSwitch label={S.s_copy_289e1cff4cbc} checked={fx.skipSilence} onChange={skipSilence=>update({skipSilence})}/>
    <p className="text-xs text-fg-2">{S.s_copy_b09b5fb2264a}</p>
    <FxSlider label={S.s_copy_8e18e6dd7fd9} spec={VALUE_SPECS.silenceDb} value={fx.silenceDb} suffix=" dBFS" disabled={!fx.skipSilence} onChange={silenceDb=>update({silenceDb})}/>
    <FxSlider label={S.s_copy_19adc1b298a9} spec={VALUE_SPECS.silenceSeconds} value={fx.silenceSeconds} suffix=" s" disabled={!fx.skipSilence} onChange={silenceSeconds=>update({silenceSeconds})}/>
    <FxSlider label={S.s_copy_483cdfec9d5f} spec={capped(VALUE_SPECS.keepSeconds,fx.silenceSeconds)} value={fx.keepSeconds} suffix=" s" disabled={!fx.skipSilence} onChange={keepSeconds=>update({keepSeconds})}/>
    <label className="flex min-h-12 items-center justify-between gap-4 text-sm">{S.s_copy_71255f2b6855}
      <Switch.Root aria-label={S.s_copy_71255f2b6855} checked={fx.enabled} onCheckedChange={enabled=>update({enabled})} className="relative h-6 w-10 rounded-full bg-line data-[state=checked]:bg-accent">
        <Switch.Thumb className="block size-5 translate-x-0.5 rounded-full bg-panel transition-transform duration-motion-fast data-[state=checked]:translate-x-[18px]"/>
      </Switch.Root>
    </label>
    <span className="text-sm">{S.s_copy_7252e7ce0085}</span>
    <ChoiceRow label={S.s_copy_7252e7ce0085} value={String(fx.preset)} options={[...FX_LABELS.map((label,i)=>({value:String(i),label})),{value:'-1',label:S.s_copy_e3518044ceec}]} onChange={value=>{const i=Number(value);update(i<0?{enabled:true,preset:-1}:{enabled:true,preset:i,bass:0,bands:[...FX_PRESETS[i]]});}}/>
    {FX_BANDS.map((label,i)=><FxSlider key={label} label={label} spec={VALUE_SPECS.eqBand} value={fx.bands[i]} disabled={!fx.enabled} onChange={value=>update({preset:-1,bands:fx.bands.map((v,j)=>j===i?value:v)})}/>)}
    <FxSlider label={S.s_copy_eb4635c58f1d} spec={VALUE_SPECS.bass} value={fx.bass} disabled={!fx.enabled} onChange={bass=>update({preset:-1,bass})}/>
  </div>;
}
function FxSwitch({label,checked,onChange}:{label:string;checked:boolean;onChange:(value:boolean)=>void}) {
  return <label className="flex min-h-12 items-center justify-between gap-4 text-sm">{label}
    <Switch.Root aria-label={label} checked={checked} onCheckedChange={onChange} className="relative h-6 w-10 rounded-full bg-line data-[state=checked]:bg-accent">
      <Switch.Thumb className="block size-5 translate-x-0.5 rounded-full bg-panel transition-transform duration-motion-fast data-[state=checked]:translate-x-[18px]"/>
    </Switch.Root>
  </label>;
}
/** Núm âm thanh = bộ chọn giá trị hàng gọn (DESIGN mục 6): tên + giá trị (chạm để gõ), thước giữa -/+, chip tiêu biểu. */
function FxSlider({label,spec,value,suffix=' dB',disabled=false,onChange}:{label:string;spec:ValueSpec;value:number;suffix?:string;disabled?:boolean;onChange:(value:number)=>void}) {
  return <ValuePicker dense className="py-1" spec={spec} value={value} disabled={disabled} label={label} format={v=>`${formatNumber(spec,v)}${suffix}`} chipLabel={v=>formatNumber(spec,v)} onPreview={onChange} onChange={onChange}/>;
}
/** "Giữ khoảng nghỉ" không quá "Dài tối thiểu". */
function capped(spec:ValueSpec,max:number):ValueSpec {
  const top=Math.min(spec.max,max);
  return {...spec,max:top,typical:spec.typical.filter(v=>v<=top)};
}
