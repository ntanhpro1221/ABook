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
