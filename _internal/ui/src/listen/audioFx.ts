import { useSyncExternalStore } from 'react';
import { toast } from '@/shared/toast';

export const FX_FREQUENCIES = [80,250,1000,4000,12000];
export const FX_BANDS = ['80 Hz','250 Hz','1 kHz','4 kHz','12 kHz'];
export const FX_LABELS = ['Phẳng','Rõ lời','Trầm ấm','Bổng','Giảm chói'];
export const FX_PRESETS = [[0,0,0,0,0],[-4,-2,2,3,-2],[4,2,0,-1,-2],[-2,-1,0,2,4],[0,0,0,-3,-5]];
export interface AudioFxSettings { enabled:boolean; preset:number; bands:number[]; bass:number; boost:number; pitch:number }
export const DEFAULT_FX: AudioFxSettings = {enabled:false,preset:0,bands:[0,0,0,0,0],bass:0,boost:0,pitch:0};
const number = (value:unknown,lo:number,hi:number) => typeof value==='number' && Number.isFinite(value)?Math.max(lo,Math.min(hi,value)):0;
export function safeFx(value:Partial<AudioFxSettings>): AudioFxSettings {
  return {enabled:value.enabled===true,preset:Math.round(number(value.preset,-1,4)),
    bands:FX_BANDS.map((_,i)=>number(value.bands?.[i],-12,12)),bass:number(value.bass,0,12),boost:number(value.boost,0,12),pitch:number(value.pitch,-6,6)};
}
function read(): AudioFxSettings { try { return safeFx(JSON.parse(localStorage.getItem('abook.audioFx')??'{}')); } catch { return {...DEFAULT_FX}; } }
let current = read();
const listeners = new Set<()=>void>();
const subscribe = (listener:()=>void) => { listeners.add(listener); return ()=>{listeners.delete(listener);}; };
export function getAudioFx() { return current; }
export function setAudioFx(value:Partial<AudioFxSettings>) {
  const next=safeFx({...current,...value});
  // Persist before publishing: callers surface storage errors through the existing toast.
  localStorage.setItem('abook.audioFx',JSON.stringify(next)); current=next;
  for (const listener of listeners) listener();
}
export function useAudioFx() { return useSyncExternalStore(subscribe,getAudioFx); }
export function appVolume() { try {const n=Number(localStorage.getItem('abook.appVolume')??'.9');return Number.isFinite(n)?Math.max(0,Math.min(1,n)):.9;}catch{return .9;} }

/** One shared context, a separate graph per narration element. Music never attaches here. */
let context: AudioContext | null = null;
let moduleReady: Promise<void> | null = null;
const graphs = new WeakMap<HTMLMediaElement,{dispose:()=>void;reset:()=>void}>();
export function attachAudioFx(audio:HTMLMediaElement): ()=>void {
  if (typeof HTMLMediaElement==='undefined' || !(audio instanceof HTMLMediaElement)) return ()=>{};
  if (graphs.has(audio)) return graphs.get(audio)!.dispose;
  if (typeof AudioContext==='undefined') return ()=>{};
  context??=new AudioContext();
  const ctx=context;
  const source=ctx.createMediaElementSource(audio);
  const filters=FX_FREQUENCIES.map(frequency=>{const f=ctx.createBiquadFilter();f.type='peaking';f.frequency.value=Math.min(frequency,ctx.sampleRate*.45);f.Q.value=1.4;return f;});
  const bass=ctx.createBiquadFilter(); bass.type='lowshelf';bass.frequency.value=120;
  const gain=ctx.createGain(), compressor=ctx.createDynamicsCompressor();
  compressor.threshold.value=-1; compressor.knee.value=0;compressor.ratio.value=20;compressor.attack.value=.001;compressor.release.value=.08;
  let upstream:AudioNode=source;
  for (const node of [...filters,bass,gain,compressor]) {upstream.connect(node);upstream=node;}
  let worklet:AudioWorkletNode|null=null, disposed=false, previousPitch=0;
  compressor.connect(ctx.destination);
  const update=()=>{
    const fx=current, at=ctx.currentTime;
    filters.forEach((filter,i)=>filter.gain.setTargetAtTime(fx.enabled?fx.bands[i]:0,at,.015));
    bass.gain.setTargetAtTime(fx.enabled?fx.bass:0,at,.015);
    gain.gain.setTargetAtTime(10**(fx.boost/20),at,.015);
    if (worklet && fx.pitch!==previousPitch) {worklet.port.postMessage({pitch:fx.pitch});previousPitch=fx.pitch;}
  };
  const unsubscribe=subscribe(update); update();
  const resume=()=>{void ctx.resume().catch(()=>{});};
  const reset=()=>{worklet?.port.postMessage({reset:true});};
  audio.addEventListener('play',resume); audio.addEventListener('seeking',reset);
  if (ctx.audioWorklet) {
    moduleReady??=ctx.audioWorklet.addModule(new URL('./audioFxProcessor.js',import.meta.url).href);
    void moduleReady.then(()=>{
      if (disposed) return;
      worklet=new AudioWorkletNode(ctx,'abook-audio-fx',{processorOptions:{pitch:current.pitch}});
      worklet.port.postMessage({pitch:current.pitch});previousPitch=current.pitch;
      compressor.disconnect();compressor.connect(worklet);worklet.connect(ctx.destination);
    }).catch(()=>{toast.error('Chưa bật được âm thanh. Bạn hãy mở lại app.');});
  }
  const dispose=()=>{
    if (disposed) return;
    disposed=true;unsubscribe();audio.removeEventListener('play',resume);audio.removeEventListener('seeking',reset);
    for (const node of [source,...filters,bass,gain,compressor,worklet]) node?.disconnect();
    worklet?.port.close();graphs.delete(audio);
  };
  graphs.set(audio,{dispose,reset});
  return dispose;
}
