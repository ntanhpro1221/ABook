import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { wordIndexAt, sentenceIndexAt } from '@/listen/words';
import { sleepLeftMs } from '@/listen/sleep';
const h = vi.hoisted(() => ({ listener: null as any }));
vi.mock('@/android/plugins', () => ({ EbookPlayer: {
  addListener: vi.fn((_kind, listener) => { h.listener=listener; return Promise.resolve({remove(){}}); }),
  getState: vi.fn(() => new Promise(()=>{})),
} }));
vi.mock('@/android/androidSource', () => ({ chapterFiles: new Map(), chapterTextEntry: ()=>'texts/1.txt' }));
vi.mock('@/android/notifications', () => ({ offerNotificationAccess: vi.fn() }));
vi.mock('sonner',()=>({toast:{error:vi.fn()}}));
import { NativeAudioEngine } from '@/android/nativeEngine';
const base = { bookId:'b', bookTitle:'Sách', chapterId:1, chapterTitle:'Một', position:10, duration:30, playing:true, buffering:true, rate:3,
  sleep:{mode:'minutes',minutes:1,remaining:60,counting:false} };
beforeEach(()=> { vi.useFakeTimers(); vi.setSystemTime(100000); vi.stubGlobal('window',{setTimeout,clearTimeout}); });
afterEach(()=>{vi.useRealTimers();vi.unstubAllGlobals();});
it('holds sentence and word while native buffers at 3x',()=>{
  const engine = new NativeAudioEngine(); h.listener({...base});
  expect(engine.time).toBe(10);
  const words: [number,number][] = [[10000,10200],[10200,10400],[10400,10800]];
  expect(wordIndexAt(words,engine.time*1000)).toBe(0);
  vi.advanceTimersByTime(400);
  expect(engine.time).toBe(10);
  expect(wordIndexAt(words,engine.time*1000)).toBe(0);
  expect(sentenceIndexAt([0,11],engine.time)).toBe(0);
  expect(sentenceIndexAt([0,11],base.position)).toBe(0);
  h.listener({...base});
  expect(engine.time).toBe(10);
  expect(sentenceIndexAt([0,11],engine.time)).toBe(0);
});
it('holds sleep timer when counting is false',()=>{
  const engine = new NativeAudioEngine(); h.listener({...base});
  vi.advanceTimersByTime(400);
  expect(sleepLeftMs(engine.sleep,Date.now())).toBe(60000);
  expect(base.sleep.remaining).toBe(60);
});
it('interpolates playback and holds paused position',()=>{
  const engine = new NativeAudioEngine(); h.listener({...base,buffering:false});
  vi.advanceTimersByTime(400); expect(engine.time).toBeCloseTo(11.2);
  h.listener({...base,playing:false}); vi.advanceTimersByTime(400); expect(engine.time).toBe(10);
});

it('counts sleep only when native counting is true',()=>{
 const engine=new NativeAudioEngine(); h.listener({...base,buffering:false,sleep:{...base.sleep,counting:true}});
 vi.advanceTimersByTime(400); expect(sleepLeftMs(engine.sleep,Date.now())).toBe(59600);
 h.listener({...base,playing:false}); vi.advanceTimersByTime(400); expect(sleepLeftMs(engine.sleep,Date.now())).toBe(60000);
});

