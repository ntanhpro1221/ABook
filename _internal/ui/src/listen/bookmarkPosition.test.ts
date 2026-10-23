import { expect, it } from 'vitest';
import { textScript } from '@/listen/textScript';
import { estimatedStarts } from '@/listen/readAloud';
import { bookmarkReadPath } from '@/listen/model';
import { sentenceIndexAt } from '@/listen/words';
import { makeAnchor } from '@/listen/readingAnchor';
import { readingIndex } from '@/listen/readingPosition';
it('seconds are only a fallback without a text position',()=>{
  const plain=textScript(1,'Một',['A','B','C','D'].map(char=>char.repeat(28)).join('\n\n'));
  const receivingStarts=estimatedStarts(plain.segments);
  expect(receivingStarts).toEqual([0,2,4,6]);
  // Máy đặt dấu đã đọc thật: mỗi đoạn 3s. BOOKMARK của PlaybackService gọi Playback.addBookmark("") không có index/quote.
  const heardStarts=[0,3,6,9];
  const mark={id:'mark',chapterId:1,seconds:6,note:'Câu cần nghe lại',at:1};
  expect(sentenceIndexAt(heardStarts,mark.seconds)).toBe(2);
  expect(bookmarkReadPath('b',mark)).toBeNull();
  // BookScreen/BookmarkPanel rơi về playBook/jumpTo(chapterId,mark.seconds): không có segment cho ReadAloud.startAt.
  expect(sentenceIndexAt(receivingStarts,mark.seconds)).toBe(3);
  // Đối chứng dấu có câu: địa chỉ giữ đúng câu, độc lập với tốc độ/clip của máy nhận.
  const anchored={...mark,index:2,quote:plain.segments[2].text};
  expect(bookmarkReadPath('b',anchored)).toContain('at=2');
});

it('the bookmark route retains an anchor that relocates after text moves',()=>{
 const paragraphs=['First paragraph.','Chosen sentence.','Last paragraph.'];
 const mark={id:'m',chapterId:1,seconds:6,note:'',at:1,index:1,quote:paragraphs[1],anchor:makeAnchor(paragraphs,1,1)};
 const params=new URL(bookmarkReadPath('b',mark)!,'http://localhost').searchParams;
 const script=textScript(1,'One',['New paragraph.',...paragraphs].join('\n\n'));
 expect(readingIndex(script,{index:Number(params.get('at')),anchor:JSON.parse(params.get('anchor')!),quote:params.get('quote')!})).toBe(2);
});

it('anchor-only bookmarks open the text position',()=>{
 const mark={id:'m',chapterId:1,seconds:6,note:'',at:1,anchor:{segment:2,charOffset:5,textHash:'fnv1a64:0000000000000000'}};
 const path=bookmarkReadPath('b',mark); expect(path).not.toBeNull();
 const params=new URL(path!,'http://localhost').searchParams;
 expect(params.get('at')).toBe('2'); expect(JSON.parse(params.get('anchor')!)).toEqual(mark.anchor);
});
