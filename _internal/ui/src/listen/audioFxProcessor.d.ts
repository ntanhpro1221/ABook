export class PitchShifter {
  constructor(ratio?:number,n?:number,hop?:number);
  tick(value:number):number;
  fft(inverse?:boolean):void;
  real:Float64Array;
  imag:Float64Array;
}
export class PeakLimiter {
  constructor(rate?:number);
  gain(peak:number):number;
}
export function stereoGains(mono:boolean,balance:number):number[];
export function createStereoMatrix(ctx:BaseAudioContext,source:AudioNode):{output:ChannelMergerNode;update:(mono:boolean,balance:number,smooth?:boolean)=>void;dispose:()=>void};
