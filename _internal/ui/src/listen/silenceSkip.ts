import type { AudioFxSettings } from './audioFx';

export interface SilenceCut { from:number; to:number }

/** Streaming form of `silenceCuts`: PCM arrives a block at a time and only the run in progress is remembered,
 * so a chapter of any length costs one block of samples, not the whole chapter. Same verdicts sample for sample. */
export class SilenceScanner {
  readonly cuts:SilenceCut[]=[];
  private start=-1;
  private at=0;
  private readonly floor:number;
  private readonly minimum:number;
  private readonly keep:number;
  constructor(private readonly rate:number,fx:AudioFxSettings) {
    this.floor=10**(fx.silenceDb/20);this.minimum=Math.round(fx.silenceSeconds*rate);this.keep=Math.round(fx.keepSeconds*rate);
  }
  /** Samples heard so far, on the source clock. */
  get position():number {return this.at;}
  push(channels:Float32Array[]):void {
    if(!channels.length)return;
    const length=Math.min(...channels.map(c=>c.length));
    for(let i=0;i<length;i++) {
      const quiet=channels.every(c=>Number.isFinite(c[i]) && Math.abs(c[i])<=this.floor);
      if(quiet){if(this.start<0)this.start=this.at+i;}else this.close(this.at+i);
    }
    this.at+=length;
  }
  /** Move the clock to a known source position (the next MP3 chunk starts on a frame boundary) without touching the run. */
  seek(position:number):void {this.at=Math.max(this.at,position);}
  finish():SilenceCut[] {this.close(this.at);return this.cuts;}
  private close(end:number):void {
    if(this.start>=0 && end-this.start>this.minimum) {
      const left=Math.floor(this.keep/2);
      this.cuts.push({from:(this.start+left)/this.rate,to:(end-(this.keep-left))/this.rate});
    }
    this.start=-1;
  }
}

/** Scan unprocessed source PCM. Peak on EVERY channel, not RMS after gain.
 * Keep both edges, preserve short/structural pauses (including 1.5 s scene breaks). */
export function silenceCuts(channels:Float32Array[],rate:number,fx:AudioFxSettings):SilenceCut[] {
  if(!fx.skipSilence || !channels.length)return [];
  const scanner=new SilenceScanner(rate,fx);scanner.push(channels);return scanner.finish();
}
export function silenceDestination(cuts:SilenceCut[],seconds:number):number|null {
  const cut=cuts.find(c=>seconds>=c.from && seconds<c.to);
  return cut?.to??null;
}

// ---- MP3 framing: enough of the header to cut the stream on frame boundaries and know each frame's sample count.
const MPEG1_L3=[0,32,40,48,56,64,80,96,112,128,160,192,224,256,320];
const MPEG2_L3=[0,8,16,24,32,40,48,56,64,80,96,112,128,144,160];
const RATES=[44100,48000,32000];
export interface Mp3Frame { length:number; samples:number; rate:number }
export function mp3Frame(bytes:Uint8Array,at:number):Mp3Frame|null {
  if(at+4>bytes.length || bytes[at]!==0xff || (bytes[at+1]&0xe0)!==0xe0)return null;
  const version=(bytes[at+1]>>3)&3,layer=(bytes[at+1]>>1)&3,bitrateIndex=bytes[at+2]>>4,rateIndex=(bytes[at+2]>>2)&3;
  if(version===1 || layer!==1 || bitrateIndex===0 || bitrateIndex===15 || rateIndex===3)return null;
  const mpeg1=version===3,rate=RATES[rateIndex]/(mpeg1?1:version===2?2:4);
  const bitrate=(mpeg1?MPEG1_L3:MPEG2_L3)[bitrateIndex]*1000,padding=(bytes[at+2]>>1)&1;
  return {length:Math.floor((mpeg1?144:72)*bitrate/rate)+padding,samples:mpeg1?1152:576,rate};
}
function id3Length(bytes:Uint8Array):number|null {
  if(bytes.length<10)return null;
  if(bytes[0]!==0x49 || bytes[1]!==0x44 || bytes[2]!==0x33)return 0;
  return 10+(((bytes[6]&0x7f)<<21)|((bytes[7]&0x7f)<<14)|((bytes[8]&0x7f)<<7)|(bytes[9]&0x7f))+((bytes[5]&0x10)?10:0);
}
// The LAME/Xing header frame ("Xing" or "Info" in its side info) carries no audio: decoders drop it.
const INFO_TAGS=[[0x58,0x69,0x6e,0x67],[0x49,0x6e,0x66,0x6f]];
function isInfoFrame(bytes:Uint8Array,at:number,length:number):boolean {
  const end=Math.min(at+length,at+64)-4;
  for(let i=at;i<=end;i++)if(INFO_TAGS.some(tag=>tag.every((b,k)=>bytes[i+k]===b)))return true;
  return false;
}

/** How long a chunk is (source frames), and how many frames before it are decoded again and dropped so the decoder's
 * bit reservoir and overlap are warm at the chunk's first kept frame. */
export const CHUNK_FRAMES=1200; // ~30 s at 44.1 kHz
export const WARMUP_FRAMES=12;

type Decode=(bytes:ArrayBuffer)=>Promise<AudioBuffer>;
class Unscannable extends Error {}

function concat(a:Uint8Array,b:Uint8Array):Uint8Array {
  if(!a.length)return b;
  const out=new Uint8Array(a.length+b.length);out.set(a);out.set(b,a.length);return out;
}

/** Reads the chapter as it downloads and scans it a chunk at a time: MP3 in decoded chunks of `CHUNK_FRAMES` frames,
 * PCM WAV straight from the bytes. Never holds more than one chunk of PCM. Reports every new cut through `found`. */
export async function scanSilence(body:AsyncIterable<Uint8Array>,decode:Decode,fx:AudioFxSettings,
  found:(cuts:SilenceCut[])=>void,alive:()=>boolean):Promise<SilenceCut[]> {
  let pending:Uint8Array=new Uint8Array(0),kind:'mp3'|'wav'|null=null,scanner:SilenceScanner|null=null;
  // MP3 state: frame boundaries inside `pending`, the source sample where the next kept frame starts.
  let frames:{at:number;frame:Mp3Frame}[]=[],cursor=0,started=false,clock=0,first=true,decodeRate=0;
  // WAV state.
  let wav:{channels:number;bits:number;float:boolean;remaining:number}|null=null,inData=false;
  const report=()=>{if(scanner && alive())found(scanner.cuts.slice());};
  const decodeChunk=async(final:boolean)=>{
    const warm=first?0:Math.min(WARMUP_FRAMES,frames.length);
    const keep=final?frames.length-warm:Math.min(CHUNK_FRAMES,frames.length-warm);
    if(keep<=0)return;
    const used=frames.slice(0,warm+keep),last=used[used.length-1];
    const bytes=pending.slice(used[0].at,last.at+last.frame.length);
    const buffer=await decode(bytes.buffer as ArrayBuffer);
    if(!alive())return;
    const rate=buffer.sampleRate;
    if(!scanner){scanner=new SilenceScanner(rate,fx);decodeRate=rate;}
    if(rate!==decodeRate)throw new Unscannable('rate');
    const scale=rate/used[0].frame.rate,want=Math.round(used.slice(warm).reduce((s,f)=>s+f.frame.samples,0)*scale);
    const channels=Array.from({length:buffer.numberOfChannels},(_,i)=>buffer.getChannelData(i));
    const length=Math.min(...channels.map(c=>c.length)),skip=first?0:Math.max(0,length-want);
    scanner.push(channels.map(c=>c.subarray(skip,Math.min(length,skip+want))));
    clock+=want;scanner.seek(clock);first=false;
    // Keep the warm-up frames for the next chunk, drop the rest of the bytes.
    const next=frames.slice(warm+keep-Math.min(WARMUP_FRAMES,warm+keep)),base=next.length?next[0].at:pending.length;
    pending=pending.slice(base);frames=next.map(f=>({at:f.at-base,frame:f.frame}));cursor-=base;
    report();
  };
  const frameMp3=()=>{
    while(cursor+4<=pending.length) {
      const frame=mp3Frame(pending,cursor);
      if(!frame){
        if(!started){cursor++;if(cursor>65536)throw new Unscannable('sync');continue;}
        cursor++;continue; // lost sync mid-stream: find the next frame header
      }
      if(cursor+frame.length>pending.length)break;
      // Only trust a sync word once the next one lines up, so random 0xFFE bits in a tag or junk are skipped.
      if(!started){
        const after=mp3Frame(pending,cursor+frame.length);
        if(!after && cursor+frame.length+4<=pending.length){cursor++;continue;}
        if(!after)break;
        started=true;
        if(isInfoFrame(pending,cursor,frame.length)){cursor+=frame.length;continue;}
      }
      frames.push({at:cursor,frame});cursor+=frame.length;
    }
  };
  const readWav=():boolean=>{
    // RIFF header, then chunks until "data".
    let at=12;
    while(at+8<=pending.length) {
      const id=String.fromCharCode(...pending.subarray(at,at+4)),size=new DataView(pending.buffer,pending.byteOffset+at+4,4).getUint32(0,true);
      if(id==='fmt '){
        if(at+8+16>pending.length)return false;
        const view=new DataView(pending.buffer,pending.byteOffset+at+8,16),format=view.getUint16(0,true);
        const channels=view.getUint16(2,true),rate=view.getUint32(4,true),bits=view.getUint16(14,true);
        const float=format===3 || (format===0xfffe && bits===32);
        if(!(format===1 || format===3 || format===0xfffe) || !(bits===16 || (float && bits===32)) || !channels || !rate)throw new Unscannable('wav');
        wav={channels,bits,float,remaining:0};scanner=new SilenceScanner(rate,fx);
      } else if(id==='data'){
        if(!wav)throw new Unscannable('wav');
        wav.remaining=size;pending=pending.slice(at+8);return true;
      }
      at+=8+size+(size&1);
    }
    return false;
  };
  const pushWav=(final:boolean)=>{
    if(!wav || !scanner)return;
    const frameBytes=wav.channels*wav.bits/8,usable=Math.min(pending.length,wav.remaining);
    const count=Math.floor(usable/frameBytes);
    if(!count || (!final && count<48000))return;
    const view=new DataView(pending.buffer,pending.byteOffset,count*frameBytes);
    const channels=Array.from({length:wav.channels},()=>new Float32Array(count));
    for(let i=0;i<count;i++)for(let c=0;c<wav.channels;c++){
      const at=(i*wav.channels+c)*wav.bits/8;
      channels[c][i]=wav.float?view.getFloat32(at,true):view.getInt16(at,true)/32768;
    }
    scanner.push(channels);wav.remaining-=count*frameBytes;pending=pending.slice(count*frameBytes);report();
  };
  for await (const piece of body) {
    if(!alive())return [];
    pending=concat(pending,piece);
    if(kind===null){
      const tag=id3Length(pending);
      if(tag===null)continue;
      const text=String.fromCharCode(...pending.subarray(0,Math.min(12,pending.length)));
      if(text.startsWith('RIFF')){if(pending.length<12)continue;if(!text.endsWith('WAVE'))throw new Unscannable('riff');kind='wav';}
      else {if(pending.length<tag+4)continue;kind='mp3';cursor=tag;}
    }
    if(kind==='wav'){if(!inData){if(!readWav())continue;inData=true;}pushWav(false);}
    else {frameMp3();while(frames.length>=(first?0:WARMUP_FRAMES)+CHUNK_FRAMES && alive())await decodeChunk(false);}
  }
  if(!alive())return [];
  if(kind==='wav')pushWav(true);
  else if(kind==='mp3'){frameMp3();if(frames.length)await decodeChunk(true);}
  if(!scanner)throw new Unscannable('empty');
  const done=(scanner as SilenceScanner).finish();report();return done;
}

async function* chunks(response:Response):AsyncIterable<Uint8Array> {
  if(!response.body){yield new Uint8Array(await response.arrayBuffer());return;}
  const reader=response.body.getReader();
  try {for(;;){const {done,value}=await reader.read();if(done)return;if(value)yield value;}}
  finally {void reader.cancel().catch(()=>undefined);}
}

/** HTML media keeps its original clock when seeking across a verified silent
 * interval. Subtitles, progress, resume and read-aloud word anchors use that clock.
 * No speculative seek based on a live level meter. No fetch when disabled.
 * Live MediaSource clips retain their structural pauses and are never scanned.
 * The chapter is scanned while it downloads, a chunk at a time; when it cannot be scanned the listener is told
 * (`unavailable`) and the chapter plays on with its silences. */
export function attachSilenceSkip(audio:HTMLMediaElement,ctx:AudioContext,get:()=>AudioFxSettings,subscribe:(fn:()=>void)=>()=>void,
  unavailable:()=>void=()=>undefined) {
  let cuts:SilenceCut[]=[],generation=0,abort:AbortController|null=null,timer:ReturnType<typeof setInterval>|null=null;
  let signature='';
  const tick=()=>{
    if(audio.paused || audio.seeking || !get().skipSilence)return;
    const to=silenceDestination(cuts,audio.currentTime);
    if(to!==null)audio.currentTime=to;
  };
  const stopTimer=()=>{if(timer!==null)clearInterval(timer);timer=null;};
  const play=()=>{stopTimer();timer=setInterval(tick,20);tick();};
  const scan=()=>{
    const fx=get(),url=audio.currentSrc||audio.src;
    const next=JSON.stringify([url,Number.isFinite(audio.duration)?audio.duration:null,fx.skipSilence,fx.silenceDb,fx.silenceSeconds,fx.keepSeconds]);
    if(next===signature)return;
    signature=next;const epoch=++generation;cuts=[];abort?.abort();abort=null;
    if(!fx.skipSilence || !url || !Number.isFinite(audio.duration))return;
    const controller=new AbortController();abort=controller;
    const alive=()=>epoch===generation && !controller.signal.aborted;
    void fetch(url,{signal:controller.signal}).then(r=>{if(!r.ok)throw new Error('audio');return r;})
      .then(r=>scanSilence(chunks(r),bytes=>ctx.decodeAudioData(bytes),fx,found=>{if(alive()){cuts=found;tick();}},alive))
      .catch(()=>{if(alive())unavailable();});
  };
  const clear=()=>{signature='';++generation;cuts=[];abort?.abort();abort=null;stopTimer();};
  const off=subscribe(scan);
  audio.addEventListener('loadedmetadata',scan);audio.addEventListener('emptied',clear);
  audio.addEventListener('play',play);audio.addEventListener('pause',stopTimer);audio.addEventListener('ended',stopTimer);
  scan();if(!audio.paused)play();
  return ()=>{clear();off();audio.removeEventListener('loadedmetadata',scan);audio.removeEventListener('emptied',clear);audio.removeEventListener('play',play);audio.removeEventListener('pause',stopTimer);audio.removeEventListener('ended',stopTimer);};
}
