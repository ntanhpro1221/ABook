import type { AudioFxSettings } from './audioFx';

export interface SilenceCut { from:number; to:number }
/** Scan unprocessed source PCM. Peak on EVERY channel, not RMS after gain.
 * Keep both edges, preserve short/structural pauses (including 1.5 s scene breaks). */
export function silenceCuts(channels:Float32Array[],rate:number,fx:AudioFxSettings):SilenceCut[] {
  if(!fx.skipSilence || !channels.length)return [];
  const cuts:SilenceCut[]=[],floor=10**(fx.silenceDb/20),length=Math.min(...channels.map(c=>c.length));
  let start=-1;
  const finish=(end:number)=>{
    if(start>=0 && end-start>Math.round(fx.silenceSeconds*rate)) {
      const keep=Math.round(fx.keepSeconds*rate),left=Math.floor(keep/2);
      cuts.push({from:(start+left)/rate,to:(end-(keep-left))/rate});
    }
    start=-1;
  };
  for(let i=0;i<length;i++) {
    const quiet=channels.every(c=>Number.isFinite(c[i]) && Math.abs(c[i])<=floor);
    if(quiet){if(start<0)start=i;}else finish(i);
  }
  finish(length);return cuts;
}
export function silenceDestination(cuts:SilenceCut[],seconds:number):number|null {
  const cut=cuts.find(c=>seconds>=c.from && seconds<c.to);
  return cut?.to??null;
}

/** HTML media keeps its original clock when seeking across a verified silent
 * interval. Subtitles, progress, resume and read-aloud word anchors use that clock.
 * No speculative seek based on a live level meter. No fetch when disabled.
 * Live MediaSource clips retain their structural pauses and are never scanned. */
export function attachSilenceSkip(audio:HTMLMediaElement,ctx:AudioContext,get:()=>AudioFxSettings,subscribe:(fn:()=>void)=>()=>void) {
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
    abort=new AbortController();
    void fetch(url,{signal:abort.signal}).then(r=>{if(!r.ok)throw new Error('audio');return r.arrayBuffer();})
      .then(bytes=>epoch===generation?ctx.decodeAudioData(bytes):null)
      .then(buffer=>{
        if(!buffer || epoch!==generation)return;
        cuts=silenceCuts(Array.from({length:buffer.numberOfChannels},(_,i)=>buffer.getChannelData(i)),buffer.sampleRate,fx);
        tick();
      }).catch(()=>{/* Playback remains intact if a streamed source cannot be scanned. */});
  };
  const clear=()=>{signature='';++generation;cuts=[];abort?.abort();abort=null;stopTimer();};
  const off=subscribe(scan);
  audio.addEventListener('loadedmetadata',scan);audio.addEventListener('emptied',clear);
  audio.addEventListener('play',play);audio.addEventListener('pause',stopTimer);audio.addEventListener('ended',stopTimer);
  scan();if(!audio.paused)play();
  return ()=>{clear();off();audio.removeEventListener('loadedmetadata',scan);audio.removeEventListener('emptied',clear);audio.removeEventListener('play',play);audio.removeEventListener('pause',stopTimer);audio.removeEventListener('ended',stopTimer);};
}
