import cases from '../../../abook/webui/assets/tone_response_cases.json';
import {createToneFilterNodes,connectToneNodes} from '@/listen/audioFx';

/** Exercises the production WebAudio nodes in Chromium, rather than a JS approximation. */
export async function toneProbe(){
  let worst=0,count=0;
  for(const c of cases.cases){
    const ctx=new OfflineAudioContext(2,256,c.rate),filters=createToneFilterNodes(ctx);
    filters.forEach((f,i)=>f.gain.value=c.bands[i]);
    const frequency=new Float32Array(cases.frequencies),total=new Float64Array(31).fill(1),phase=new Float32Array(31);
    for(const filter of filters){const response=new Float32Array(31);filter.getFrequencyResponse(frequency,response,phase);response.forEach((v,i)=>{total[i]*=v;});}
    total.forEach((v,i)=>{
      // WebAudio returns NaN above Nyquist; probe the equivalent aliased frequency used by the native sine tests.
      if(cases.frequencies[i]>c.rate/2){
        const folded=new Float32Array([Math.abs(c.rate-cases.frequencies[i])]);let value=1;
        for(const filter of filters){const mag=new Float32Array(1);filter.getFrequencyResponse(folded,mag,new Float32Array(1));value*=mag[0];}v=value;
      }
      const error=Math.abs(20*Math.log10(v)-c.db[i]);if(!Number.isFinite(error)||error>cases.toleranceDb)throw new Error(`${c.id} ${c.rate} ${i}: ${error}`);worst=Math.max(worst,error);count++;
    });
  }
  const ctx=new OfflineAudioContext(2,65536,48000),buffer=ctx.createBuffer(2,65536,48000);
  for(let ch=0;ch<2;ch++){const data=buffer.getChannelData(ch);for(let i=0;i<data.length;i++)data[i]=(i-32768)/32768*(ch?-1:1);}
  const source=ctx.createBufferSource();source.buffer=buffer;
  const filters=createToneFilterNodes(ctx);filters.forEach(f=>f.gain.value=12);
  connectToneNodes(source,filters,ctx.destination,false);source.start();const output=await ctx.startRendering();
  for(let ch=0;ch<2;ch++){const a=buffer.getChannelData(ch),b=output.getChannelData(ch);for(let i=0;i<a.length;i++)if(!Object.is(a[i],b[i]))throw new Error(`Off changed PCM at ${ch}/${i}`);}
  return {measurements:count,worstDb:worst,offBitExact:true};
}
