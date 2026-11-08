// @vitest-environment happy-dom
import {beforeEach,expect,it} from 'vitest';
import {DEFAULT_FX,FX_PRESETS,getAudioFx,safeFx,setAudioFx} from './audioFx';
import {PeakLimiter,PitchShifter} from './audioFxProcessor.js';

beforeEach(()=>{localStorage.clear();setAudioFx({...DEFAULT_FX});});
it('persists EQ, manual bands, boost and pitch independently',()=>{
  setAudioFx({enabled:true,preset:1,bands:[...FX_PRESETS[1]],boost:12,pitch:-3});
  expect(JSON.parse(localStorage.getItem('abook.audioFx')!).pitch).toBe(-3);
  setAudioFx({enabled:false});expect(getAudioFx().bands).toEqual(FX_PRESETS[1]);
  expect(getAudioFx().boost).toBe(12);expect(getAudioFx().pitch).toBe(-3);
});
it('rejects nonfinite settings and clamps bounds',()=>{
  const fx=safeFx({pitch:NaN,bass:99,boost:Infinity,bands:[-99,99,NaN],preset:9});
  expect(fx).toEqual({enabled:false,pitch:0,bass:12,boost:0,bands:[-12,12,0,0,0],preset:4});
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
