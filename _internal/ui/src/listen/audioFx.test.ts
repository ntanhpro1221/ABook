// @vitest-environment happy-dom
import {beforeEach,expect,it,vi} from 'vitest';
import {DEFAULT_FX,FX_PRESETS,getAudioFx,safeFx,setAudioFx,selectAudioBook,setAudioBookOnly,audioBookOnly} from './audioFx';
import {silenceCuts,silenceDestination,attachSilenceSkip} from './silenceSkip';
import {PeakLimiter,PitchShifter,stereoGains} from './audioFxProcessor.js';

beforeEach(()=>{localStorage.clear();selectAudioBook('');setAudioFx({...DEFAULT_FX});});
it('persists EQ, manual bands, boost and pitch independently',()=>{
  setAudioFx({enabled:true,preset:1,bands:[...FX_PRESETS[1]],boost:12,pitch:-3});
  expect(JSON.parse(localStorage.getItem('abook.audioFx')!).pitch).toBe(-3);
  setAudioFx({enabled:false});expect(getAudioFx().bands).toEqual(FX_PRESETS[1]);
  expect(getAudioFx().boost).toBe(12);expect(getAudioFx().pitch).toBe(-3);
});
it('rejects nonfinite settings and clamps bounds',()=>{
  const fx=safeFx({pitch:NaN,bass:99,boost:Infinity,bands:[-99,99,NaN],preset:9});
  expect(fx).toEqual({...DEFAULT_FX,enabled:false,pitch:0,bass:12,boost:0,bands:[-12,12,0,0,0],preset:4});
});
it('links the limiter envelope and never crosses -1 dBFS',()=>{
  const limiter=new PeakLimiter();let peak=0;
  for(let i=0;i<96000;i++) {const x=i===0?100:8*Math.sin(2*Math.PI*220*i/48000),gain=limiter.gain(Math.abs(x));peak=Math.max(peak,Math.abs(x*gain));}
  expect(peak).toBeLessThanOrEqual(10**(-1/20)+1e-12);
});
it.each([-6,-3,3,6])('pitch %s shifts a 220 Hz tone within 3 percent, with fixed frame count',(pitch)=>{
  const source=Float64Array.from({length:96000},(_,i)=>.2*Math.sin(2*Math.PI*220*i/48000));
  const shifter=new PitchShifter(2**(pitch/12));const output=source.map(x=>shifter.tick(x));
  expect(output.length).toBe(source.length);
  const spectrum=new PitchShifter(1,32768,4096);
  for(let i=0;i<32768;i++) spectrum.real[i]=output[i+24000]*(.5-.5*Math.cos(2*Math.PI*i/32768));
  spectrum.fft();let bin=1,peak=0;
  for(let i=1;i<16384;i++) {const mag=Math.hypot(spectrum.real[i],spectrum.imag[i]);if(mag>peak){peak=mag;bin=i;}}
  const hz=bin*48000/32768,expected=220*2**(pitch/12);
  console.info(`AUDIOFX pitch=${pitch} f0=${hz} expected=${expected} frames=${output.length}`);
  expect(Math.abs(hz/expected-1)).toBeLessThan(.03);
});
it('zero pitch leaves samples identical',()=>{
  const shifter=new PitchShifter();for(let i=0;i<1000;i++){const x=Math.sin(i);expect(shifter.tick(x)).toBe(x);}
});
it('isolates complete profiles and restores the shared settings when disabled',()=>{
  setAudioFx({boost:3,speed:1.5,volume:.7});selectAudioBook('A');expect(audioBookOnly()).toBe(false);
  setAudioBookOnly(true);setAudioFx({boost:9,speed:2,volume:.4,mono:true});
  selectAudioBook('B');expect(getAudioFx().boost).toBe(3);expect(getAudioFx().speed).toBe(1.5);expect(getAudioFx().volume).toBe(.7);
  selectAudioBook('A');expect(getAudioFx().boost).toBe(9);expect(getAudioFx().mono).toBe(true);
  setAudioBookOnly(false);expect(getAudioFx().speed).toBe(1.5);expect(getAudioFx().volume).toBe(.7);
  selectAudioBook('A');expect(audioBookOnly()).toBe(false);expect(getAudioFx().boost).toBe(3);
});
it('keeps speech and structural pauses, cuts only long silence and seeks in source time',()=>{
  const l=new Float32Array(6800),r=new Float32Array(6800);
  for(const [from,to] of [[0,100],[1600,1700],[6700,6800]]) {l.fill(.1,from,to);r.fill(.2,from,to);}
  const cuts=silenceCuts([l,r],1000,{...DEFAULT_FX,skipSilence:true});
  expect(cuts).toEqual([{from:2.45,to:5.95}]);
  expect(silenceDestination(cuts,2.449)).toBe(null);expect(silenceDestination(cuts,2.45)).toBe(5.95);
  expect(silenceDestination(cuts,6.7)).toBe(null); // final sentence/subtitle remains at source 6.7 s
  expect(6.8-cuts.reduce((s,c)=>s+c.to-c.from,0)).toBeCloseTo(3.3);
});
it.each([1500,3000,3001,5000])('strict threshold and nonzero retained tail %s',(length)=>{
  const cuts=silenceCuts([new Float32Array(length)],1000,{...DEFAULT_FX,skipSilence:true});
  expect(cuts.length).toBe(length>3000?1:0);
  if(cuts.length)expect(length/1000-(cuts[0].to-cuts[0].from)).toBeCloseTo(1.5);
});
it('requires both channels to be quiet and defaults off',()=>{
  expect(silenceCuts([new Float32Array(5000)],1000,DEFAULT_FX)).toEqual([]);
  expect(silenceCuts([new Float32Array(5000),new Float32Array(5000).fill(.01)],1000,{...DEFAULT_FX,skipSilence:true})).toEqual([]);
  expect(safeFx({keepSeconds:0,silenceSeconds:0}).keepSeconds).toBe(1.5);
});
it('mono matrix averages both channels then attenuates the correct side',()=>{
  for(const mono of [false,true])for(const b of [-1,-.5,0,.5,1]) {
    const g=stereoGains(mono,b),l=.2*g[0]+.6*g[2],r=.2*g[1]+.6*g[3];
    expect(l).toBeCloseTo((mono?.4:.2)*(1-Math.max(0,b)),12);
    expect(r).toBeCloseTo((mono?.4:.6)*(1+Math.min(0,b)),12);
  }
});
it('scans when metadata arrives after attaching, then seeks on the original clock',async()=>{
  const audio=new Audio();audio.src='https://localhost/chapter.wav';
  Object.defineProperty(audio,'duration',{value:NaN,writable:true,configurable:true});
  Object.defineProperty(audio,'paused',{value:true,writable:true,configurable:true});
  Object.defineProperty(audio,'seeking',{value:false,writable:true,configurable:true});
  const pcm=new Float32Array(6800).fill(.2);pcm.fill(0,100,1600);pcm.fill(0,1700,6700);
  const fetcher=vi.fn().mockResolvedValue({ok:true,arrayBuffer:async()=>new ArrayBuffer(1)});
  vi.stubGlobal('fetch',fetcher);
  const ctx={decodeAudioData:async()=>({numberOfChannels:1,sampleRate:1000,getChannelData:()=>pcm})} as unknown as AudioContext;
  const detach=attachSilenceSkip(audio,ctx,()=>({...DEFAULT_FX,skipSilence:true}),()=>()=>{});
  try {
    expect(fetcher).not.toHaveBeenCalled();
    Object.defineProperty(audio,'duration',{value:6.8});audio.dispatchEvent(new Event('loadedmetadata'));
    await vi.waitFor(()=>expect(fetcher).toHaveBeenCalledTimes(1));
    audio.currentTime=2.46;Object.defineProperty(audio,'paused',{value:false});audio.dispatchEvent(new Event('play'));
    await vi.waitFor(()=>expect(audio.currentTime).toBe(5.95));
  } finally {detach();vi.unstubAllGlobals();}
});
