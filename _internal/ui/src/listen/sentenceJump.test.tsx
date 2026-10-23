import { renderToString } from 'react-dom/server';
import { expect, it, vi } from 'vitest';
import { textScript } from '@/listen/textScript';
import { estimatedStarts, timedTextScript } from '@/listen/readAloud';
import { textFingerprint } from '@/listen/readingAnchor';
import { sentenceIndexAt } from '@/listen/words';
const h=vi.hoisted(()=>({playBook:vi.fn(), jumpTo:vi.fn(), track:{bookId:'a'}}));
vi.mock('@/listen/LibraryScreen',()=>({usePlayListenBook:()=>h.playBook}));
vi.mock('@/listen/player',()=>({usePlayer:()=>({track:h.track,jumpTo:h.jumpTo})}));
import { useListenFrom } from '@/listen/ReadAlongText';
it('sentence jump carries identity across different voice timelines',()=>{
  const plain=textScript(1,'Một','Đoạn một dài vừa đủ.\n\nĐoạn hai dài vừa đủ.\n\nĐoạn ba cần nghe.');
  const starts=estimatedStarts(plain.segments);
  // ReadAloud.peek/fromCache dùng voiceId của cuốn A: chưa có clip A cho chữ B nên chỉ có mốc ước.
  const shown=timedTextScript(plain,{textHash:textFingerprint(plain.segments.map(s=>s.text)),segments:plain.segments.map((_s,i)=>({start:starts[i],end:i+1<starts.length?starts[i+1]:starts[i]+2}))});
  const chapter={id:1,title:'Một',fullTitle:'Một',state:'text',speech:true,available:false};
  const book={id:'b',title:'B',chapters:[chapter],state:{voice:'voice-b'}} as any;
  let listen:any;
  function Probe(){listen=useListenFrom('b',book,chapter as any,shown);return null;}
  renderToString(<Probe/>);
  h.playBook.mockClear();expect(listen.listenFrom(2)).toBe(true);
  const [,chapterId,at,extra]=h.playBook.mock.lastCall!;
  expect(chapterId).toBe(1);expect(at).toBe(starts[2]);expect(extra.word).toEqual({segment:2,word:0});
  // Playback.load -> useVoiceOf(B) -> chapFor -> fromCache: clip giọng B đã làm sẵn có mốc thật 0,2,4.
  expect(sentenceIndexAt([0,2,4],at)).toBe(1);
  expect(sentenceIndexAt([0,2,4],at)).not.toBe(2);
  // Đối chứng: bấm chữ đầu cùng câu mang chính xác danh tính câu, không phụ thuộc đồng hồ.
  expect(listen.listenFrom(2,0)).toBe(true);
  expect(h.playBook.mock.lastCall![3].word).toEqual({segment:2,word:0});
});


it('same book uses segment and audio books retain seconds',()=>{
 const script=textScript(1,'M?t','C?u m?t.\n\nC?u hai.');
 const chapter={id:1,state:'text',speech:true} as any;
 let listen:any;
 function Probe(){listen=useListenFrom('a',undefined,chapter,script); return null;}
 renderToString(<Probe/>); h.jumpTo.mockClear();
 expect(listen.listenFrom(1)).toBe(true); expect(h.jumpTo.mock.lastCall![3]).toEqual({segment:1,word:0});
 chapter.state=undefined; chapter.speech=false; script.timed=true; script.segments[1].start=7;
 renderToString(<Probe/>); expect(listen.listenFrom(1)).toBe(true);
 expect(h.jumpTo.mock.lastCall![1]).toBe(7); expect(h.jumpTo.mock.lastCall![3]).toBeUndefined();
});
