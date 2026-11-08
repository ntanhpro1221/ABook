// Self-contained ES module: Vite emits this file for AudioWorklet.addModule.
// STFT phase vocoder: fixed input/output hop, frequency remapping changes pitch only.
export class PitchShifter {
  constructor(ratio = 1, n = 2048, hop = 256) {
    this.n = n; this.hop = hop; this.ratio = ratio; this.at = 0;
    for (const name of ['input','real','imag','last','phase','sum','magnitudes','frequencies']) this[name] = new Float64Array(n);
    this.output = new Float64Array(hop);
    this.window = Float64Array.from({length:n}, (_,i) => .5 - .5 * Math.cos(2*Math.PI*i/n));
  }
  fft(inverse = false) {
    const {real:r, imag:i, n} = this;
    for (let a=1,b=0;a<n;a++) {
      let bit=n>>1; for (;b&bit;bit>>=1) b^=bit; b^=bit;
      if (a<b) { [r[a],r[b]]=[r[b],r[a]]; [i[a],i[b]]=[i[b],i[a]]; }
    }
    for (let width=2;width<=n;width*=2) {
      const angle=(inverse?2:-2)*Math.PI/width, wr=Math.cos(angle), wi=Math.sin(angle);
      for (let start=0;start<n;start+=width) {
        let cr=1,ci=0;
        for (let j=0;j<width/2;j++) {
          const a=start+j,b=a+width/2, tr=r[b]*cr-i[b]*ci,ti=r[b]*ci+i[b]*cr;
          r[b]=r[a]-tr; i[b]=i[a]-ti; r[a]+=tr; i[a]+=ti;
          const next=cr*wr-ci*wi; ci=cr*wi+ci*wr; cr=next;
        }
      }
    }
    if (inverse) for (let k=0;k<n;k++) { r[k]/=n; i[k]/=n; }
  }
  frame() {
    const {n,hop,ratio,real,imag,window,input,last,phase,magnitudes:m,frequencies:f,sum}=this;
    for (let k=0;k<n;k++) { real[k]=input[k]*window[k]; imag[k]=0; }
    this.fft(); m.fill(0); f.fill(0);
    for (let k=0;k<=n/2;k++) {
      const angle=Math.atan2(imag[k],real[k]), expected=2*Math.PI*k*hop/n;
      let delta=angle-last[k]-expected; last[k]=angle;
      delta-=2*Math.PI*Math.round(delta/(2*Math.PI));
      const frequency=(k+delta*n/(2*Math.PI*hop))*ratio;
      const j=Math.round(k*ratio), magnitude=Math.hypot(real[k],imag[k]);
      if (j<=n/2) { m[j]+=magnitude; f[j]+=magnitude*frequency; }
    }
    real.fill(0); imag.fill(0);
    for (let k=0;k<=n/2;k++) {
      phase[k]+=2*Math.PI*(m[k]?f[k]/m[k]:k)*hop/n;
      phase[k]%=2*Math.PI;
      real[k]=m[k]*Math.cos(phase[k]); imag[k]=m[k]*Math.sin(phase[k]);
      if (k>0 && k<n/2) { real[n-k]=real[k]; imag[n-k]=-imag[k]; }
    }
    this.fft(true);
    const normalization=3*n/(8*hop); // sum of Hann squared over overlap
    for (let k=0;k<n;k++) sum[k]+=real[k]*window[k]/normalization;
    this.output.set(sum.subarray(0,hop)); sum.copyWithin(0,hop); sum.fill(0,n-hop);
    input.copyWithin(0,hop); input.fill(0,n-hop);
  }
  tick(value) {
    if (this.ratio===1) return value;
    this.input[this.n-this.hop+this.at]=value;
    const out=this.output[this.at];
    if (++this.at===this.hop) { this.at=0; this.frame(); }
    return out;
  }
}

/** Stereo matrix, downmix before balance. Shared by live graph and offline QA. */
export function stereoGains(mono,balance) {
  const b=Number.isFinite(balance)?Math.max(-1,Math.min(1,balance)):0;
  const left=1-Math.max(0,b),right=1+Math.min(0,b);
  return [mono?.5*left:left,mono?.5*right:0,mono?.5*left:0,mono?.5*right:right];
}
export function createStereoMatrix(ctx,source) {
  const stereo=ctx.createGain();stereo.channelCount=2;stereo.channelCountMode='explicit';
  const split=ctx.createChannelSplitter(2),output=ctx.createChannelMerger(2);
  const matrix=Array.from({length:4},()=>ctx.createGain());
  source.connect(stereo);stereo.connect(split);
  matrix.forEach((node,i)=>{node.gain.value=i===0||i===3?1:0;split.connect(node,Math.floor(i/2));node.connect(output,0,i%2);});
  return {output,update(mono,balance,smooth=true){stereoGains(mono,balance).forEach((v,i)=>{if(smooth)matrix[i].gain.setTargetAtTime(v,ctx.currentTime,.015);else matrix[i].gain.value=v;});},
    dispose(){for(const node of [stereo,split,output,...matrix])node.disconnect();}};
}

export class PeakLimiter {
  constructor(rate=48000) { this.envelope=1; this.release=Math.exp(-1/(rate*.08)); }
  gain(peak) {
    const ceiling=10**(-1/20), target=peak>ceiling?ceiling/peak:1;
    this.envelope=Math.min(target,1-(1-this.envelope)*this.release);
    return this.envelope;
  }
}

if (typeof registerProcessor==='function') {
  class AudioFxProcessor extends AudioWorkletProcessor {
    constructor(options) {
      super(); this.pitch=options?.processorOptions?.pitch??0; this.shifters=[]; this.limiter=new PeakLimiter(sampleRate);
      this.port.onmessage=({data}) => {
        if (data.pitch!==undefined) this.pitch=data.pitch;
        if (data.reset || data.pitch!==undefined) this.shifters=[];
      };
    }
    process(inputs,outputs) {
      const source=inputs[0], target=outputs[0];
      for (let ch=0;ch<target.length;ch++) {
        const shifter=this.shifters[ch]??(this.shifters[ch]=new PitchShifter(2**(this.pitch/12)));
        const channel=source[ch]??source[0];
        for (let i=0;i<target[ch].length;i++) target[ch][i]=shifter.tick(Number.isFinite(channel?.[i])?channel[i]:0);
      }
      for (let i=0;i<(target[0]?.length??0);i++) {
        let peak=0; for (const ch of target) peak=Math.max(peak,Math.abs(ch[i]));
        const gain=this.limiter.gain(peak);
        for (const ch of target) ch[i]*=gain;
      }
      return true;
    }
  }
  registerProcessor('abook-audio-fx',AudioFxProcessor);
}
