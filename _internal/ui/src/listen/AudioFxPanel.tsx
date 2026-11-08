import * as Slider from '@radix-ui/react-slider';
import * as Switch from '@radix-ui/react-switch';
import { toast } from '@/shared/toast';
import { Button, ChoiceRow } from '@/shared/ui';
import { FX_BANDS, FX_LABELS, FX_PRESETS, setAudioFx, useAudioFx, audioBookOnly, setAudioBookOnly } from './audioFx';

export function AudioFxPanel({volume,setVolume}:{volume:number;setVolume:(value:number)=>void}) {
  const fx=useAudioFx();
  const update:typeof setAudioFx=(value)=>{try {setAudioFx(value);} catch {toast.error('Chưa lưu được âm thanh. Bạn hãy thử lại.');}};
  return <div data-audio-fx className="flex min-w-0 flex-col gap-1">
    <p className="pb-2 text-xs text-fg-2">Dùng chung mặc định. Chỉ chỉnh giọng đọc; nhạc nền có mức riêng.</p>
    <FxSwitch label="Riêng sách này" checked={audioBookOnly()} onChange={value=>{try{setAudioBookOnly(value);}catch{toast.error('Chưa lưu được âm thanh. Bạn hãy thử lại.');}}}/>
    <FxSlider label="Âm lượng" value={volume*100} min={0} max={100} suffix="%" onChange={v=>setVolume(v/100)}/>
    <FxSlider label="Tăng âm" value={fx.boost} min={0} max={12} onChange={boost=>update({boost})}/>
    <FxSlider label="Cao độ" value={fx.pitch} min={-6} max={6} step={.5} suffix=" bán âm" onChange={pitch=>update({pitch})}/>
    <Button variant="ghost" size="sm" className="self-start px-0" onClick={()=>update({pitch:0})}>Về mặc định</Button>
    <FxSwitch label="Mono" checked={fx.mono} onChange={mono=>update({mono})}/>
    <FxSlider label="Cân bằng" value={fx.balance*100} min={-100} max={100} suffix="% (trái / phải)" onChange={v=>update({balance:v/100})}/>
    <FxSwitch label="Bỏ khoảng lặng" checked={fx.skipSilence} onChange={skipSilence=>update({skipSilence})}/>
    <p className="text-xs text-fg-2">Giữ nhịp nghỉ; chỉ rút khoảng lặng dài.</p>
    <FxSlider label="Ngưỡng lặng" value={fx.silenceDb} min={-80} max={-45} suffix=" dBFS" disabled={!fx.skipSilence} onChange={silenceDb=>update({silenceDb})}/>
    <FxSlider label="Dài tối thiểu" value={fx.silenceSeconds} min={2} max={10} step={.5} suffix=" s" disabled={!fx.skipSilence} onChange={silenceSeconds=>update({silenceSeconds})}/>
    <FxSlider label="Giữ khoảng nghỉ" value={fx.keepSeconds} min={1.5} max={Math.min(3,fx.silenceSeconds)} step={.1} suffix=" s" disabled={!fx.skipSilence} onChange={keepSeconds=>update({keepSeconds})}/>
    <label className="flex min-h-12 items-center justify-between gap-4 text-sm">Equalizer
      <Switch.Root aria-label="Equalizer" checked={fx.enabled} onCheckedChange={enabled=>update({enabled})} className="h-6 w-10 rounded-full bg-line data-[state=checked]:bg-accent">
        <Switch.Thumb className="block size-5 translate-x-0.5 rounded-full bg-panel transition-transform duration-motion-fast data-[state=checked]:translate-x-[18px]"/>
      </Switch.Root>
    </label>
    <span className="text-sm">Preset</span>
    <ChoiceRow label="Preset" value={String(fx.preset)} options={[...FX_LABELS.map((label,i)=>({value:String(i),label})),{value:'-1',label:'Tự chỉnh'}]} onChange={value=>{const i=Number(value);update(i<0?{enabled:true,preset:-1}:{enabled:true,preset:i,bass:0,bands:[...FX_PRESETS[i]]});}}/>
    {FX_BANDS.map((label,i)=><FxSlider key={label} label={label} value={fx.bands[i]} min={-12} max={12} disabled={!fx.enabled} onChange={value=>update({preset:-1,bands:fx.bands.map((v,j)=>j===i?value:v)})}/>)}
    <FxSlider label="Tăng trầm" value={fx.bass} min={0} max={12} disabled={!fx.enabled} onChange={bass=>update({preset:-1,bass})}/>
  </div>;
}
function FxSwitch({label,checked,onChange}:{label:string;checked:boolean;onChange:(value:boolean)=>void}) {
  return <label className="flex min-h-12 items-center justify-between gap-4 text-sm">{label}
    <Switch.Root aria-label={label} checked={checked} onCheckedChange={onChange} className="h-6 w-10 rounded-full bg-line data-[state=checked]:bg-accent">
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
