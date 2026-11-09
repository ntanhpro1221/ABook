// @vitest-environment happy-dom
import {expect,it,vi} from 'vitest';
import {DEFAULT_FX} from './audioFx';
import {CHUNK_FRAMES,WARMUP_FRAMES,attachSilenceSkip,mp3Frame,scanSilence,silenceCuts} from './silenceSkip';
import { eventually } from "@/testing/eventually";

const FX={...DEFAULT_FX,skipSilence:true};

/** 16-bit PCM WAV of one channel. */
function wav(pcm:Float32Array,rate:number):Uint8Array {
  const out=new Uint8Array(44+pcm.length*2),view=new DataView(out.buffer);
  const text=(at:number,value:string)=>{for(let i=0;i<4;i++)out[at+i]=value.charCodeAt(i);};
  text(0,'RIFF');view.setUint32(4,36+pcm.length*2,true);text(8,'WAVE');text(12,'fmt ');view.setUint32(16,16,true);
  view.setUint16(20,1,true);view.setUint16(22,1,true);view.setUint32(24,rate,true);view.setUint32(28,rate*2,true);
  view.setUint16(32,2,true);view.setUint16(34,16,true);text(36,'data');view.setUint32(40,pcm.length*2,true);
  pcm.forEach((x,i)=>view.setInt16(44+i*2,Math.round(x*32767),true));
  return out;
}
async function* pieces(bytes:Uint8Array,size:number):AsyncIterable<Uint8Array> {
  for(let at=0;at<bytes.length;at+=size)yield bytes.slice(at,at+size);
}

// MPEG-1 Layer III, 128 kb/s, 44.1 kHz, no padding: 417 bytes, 1152 samples. Byte 4 carries the test's "level".
const SAMPLES=1152,RATE=44100;
function mp3(loud:boolean[],info=false):Uint8Array {
  const frames=[...(info?[null]:[]),...loud],out=new Uint8Array(frames.length*417);
  frames.forEach((level,i)=>{
    out.set([0xff,0xfb,0x90,0x00],i*417);
    if(level===null)out.set([...'Info'].map(c=>c.charCodeAt(0)),i*417+36);
    else out[i*417+4]=level?1:0;
  });
  return out;
}
/** Decodes the test frames into PCM at 44.1 kHz and records how much PCM any one call held. */
function decoder() {
  const calls:number[]=[];
  const decode=vi.fn(async(bytes:ArrayBuffer)=>{
    const data=new Uint8Array(bytes),levels:number[]=[];
    for(let at=0;at<data.length;) {
      const frame=mp3Frame(data,at);if(!frame)throw new Error('bad frame');
      if(!String.fromCharCode(...data.subarray(at+36,at+40)).includes('Info'))levels.push(data[at+4]);
      at+=frame.length;
    }
    const pcm=new Float32Array(levels.length*SAMPLES);levels.forEach((l,i)=>pcm.fill(l?.2:0,i*SAMPLES,(i+1)*SAMPLES));
    calls.push(levels.length);
    return {numberOfChannels:2,sampleRate:RATE,length:pcm.length,getChannelData:()=>pcm} as unknown as AudioBuffer;
  });
  return {decode,calls};
}
function expected(loud:boolean[]) {
  const pcm=new Float32Array(loud.length*SAMPLES);loud.forEach((l,i)=>pcm.fill(l?.2:0,i*SAMPLES,(i+1)*SAMPLES));
  return silenceCuts([pcm,pcm],RATE,FX);
}

it('scans an MP3 chapter a chunk at a time and finds the same cuts as a whole-file scan',async()=>{
  // ~3 minutes: speech, silences of 10 s straddling chunk edges, one short pause that stays.
  const loud=Array.from({length:CHUNK_FRAMES*4+321},(_,i)=>!((i>1100 && i<1500) || (i>2350 && i<2420) || (i>3550 && i<3990)));
  const {decode,calls}=decoder(),seen:number[]=[];
  const cuts=await scanSilence(pieces(mp3(loud,true),7919),decode,FX,found=>seen.push(found.length),()=>true);
  expect(cuts).toEqual(expected(loud));
  expect(cuts.length).toBe(2);
  expect(calls.length).toBeGreaterThan(4);
  expect(Math.max(...calls)).toBeLessThanOrEqual(CHUNK_FRAMES+WARMUP_FRAMES); // never the whole chapter
  expect(seen[0]).toBe(0);expect(seen.at(-1)).toBe(2); // cuts arrive while the chapter is still downloading
});

it('skips an ID3 tag and streams PCM WAV without decoding it',async()=>{
  const pcm=new Float32Array(9000).fill(.2);pcm.fill(0,1000,5000);
  const decode=vi.fn();
  expect(await scanSilence(pieces(wav(pcm,1000),333),decode,FX,()=>undefined,()=>true)).toEqual(silenceCuts([pcm],1000,FX));
  expect(decode).not.toHaveBeenCalled();
  const tagged=new Uint8Array(30+417*4);tagged.set([0x49,0x44,0x33,4,0,0,0,0,0,20]);tagged.set(mp3([true,true,true,true]),30);
  const {decode:mp3Decode}=decoder();
  expect(await scanSilence(pieces(tagged,100),mp3Decode,FX,()=>undefined,()=>true)).toEqual([]);
  expect(mp3Decode).toHaveBeenCalledTimes(1);
});

it.each([
  ['an unknown format',{ok:true,body:null,arrayBuffer:async()=>new Uint8Array(70000).fill(7).buffer}],
  ['a failed download',{ok:false,body:null,arrayBuffer:async()=>new ArrayBuffer(0)}],
])('tells the listener when %s cannot be scanned, and keeps playing',async(_name,response)=>{
  const audio=new Audio();audio.src='https://localhost/chapter.mp3';
  Object.defineProperty(audio,'duration',{value:60,configurable:true});
  vi.stubGlobal('fetch',vi.fn().mockResolvedValue(response));
  const unavailable=vi.fn();
  const detach=attachSilenceSkip(audio,{decodeAudioData:vi.fn()} as unknown as AudioContext,()=>FX,()=>()=>{},unavailable);
  try {await eventually(()=>expect(unavailable).toHaveBeenCalledTimes(1));}
  finally {detach();vi.unstubAllGlobals();}
});

it('tells the listener when the decoder refuses a chunk, but not after the chapter was left',async()=>{
  const audio=new Audio();audio.src='https://localhost/chapter.mp3';
  Object.defineProperty(audio,'duration',{value:60,configurable:true});
  vi.stubGlobal('fetch',vi.fn().mockResolvedValue({ok:true,body:null,arrayBuffer:async()=>mp3(Array(40).fill(true)).buffer}));
  const unavailable=vi.fn();
  let refuse!:(error:Error)=>void;
  const ctx={decodeAudioData:vi.fn(()=>new Promise((_,reject)=>{refuse=reject;}))} as unknown as AudioContext;
  const detach=attachSilenceSkip(audio,ctx,()=>FX,()=>()=>{},unavailable);
  try {
    await eventually(()=>expect(ctx.decodeAudioData).toHaveBeenCalled());
    refuse(new Error('EncodingError'));
    await eventually(()=>expect(unavailable).toHaveBeenCalledTimes(1));
  } finally {detach();vi.unstubAllGlobals();}
  const left=vi.fn();
  vi.stubGlobal('fetch',vi.fn().mockResolvedValue({ok:true,body:null,arrayBuffer:async()=>mp3(Array(40).fill(true)).buffer}));
  const again=attachSilenceSkip(audio,ctx,()=>FX,()=>()=>{},left);
  await eventually(()=>expect(ctx.decodeAudioData).toHaveBeenCalledTimes(2));
  again();refuse(new Error('EncodingError'));
  // The refusal reaches the scan's catch within a fixed number of microtasks; no timer involved.
  for(let i=0;i<50;i++)await Promise.resolve();
  expect(left).not.toHaveBeenCalled();
  vi.unstubAllGlobals();
});

it('scans when metadata arrives after attaching, then seeks on the original clock',async()=>{
  const audio=new Audio();audio.src='https://localhost/chapter.wav';
  Object.defineProperty(audio,'duration',{value:NaN,writable:true,configurable:true});
  Object.defineProperty(audio,'paused',{value:true,writable:true,configurable:true});
  Object.defineProperty(audio,'seeking',{value:false,writable:true,configurable:true});
  const pcm=new Float32Array(6800).fill(.2);pcm.fill(0,100,1600);pcm.fill(0,1700,6700);
  const fetcher=vi.fn().mockResolvedValue({ok:true,body:null,arrayBuffer:async()=>wav(pcm,1000).buffer});
  vi.stubGlobal('fetch',fetcher);
  const ctx={decodeAudioData:vi.fn()} as unknown as AudioContext;
  const detach=attachSilenceSkip(audio,ctx,()=>({...DEFAULT_FX,skipSilence:true}),()=>()=>{});
  try {
    expect(fetcher).not.toHaveBeenCalled();
    Object.defineProperty(audio,'duration',{value:6.8});audio.dispatchEvent(new Event('loadedmetadata'));
    await eventually(()=>expect(fetcher).toHaveBeenCalledTimes(1));
    audio.currentTime=2.46;Object.defineProperty(audio,'paused',{value:false});audio.dispatchEvent(new Event('play'));
    await eventually(()=>expect(audio.currentTime).toBe(5.95));
  } finally {detach();vi.unstubAllGlobals();}
});
