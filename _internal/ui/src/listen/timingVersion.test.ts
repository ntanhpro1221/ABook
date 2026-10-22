import { expect, it } from 'vitest';
import { mergeTimings } from '@/listen/readAloud';
import { textScript } from '@/listen/textScript';
import { textFingerprint } from '@/listen/readingAnchor';
import { timedTextScript } from '@/listen/readAloud';

it('từ chối mốc native khi bản chữ đã bỏ dòng ghi công',()=>{
  const text='Chương 1\n\nTrans: Lan\n\nCâu đầu câu đầu.\n\nCâu thứ hai nữa.';
  const original=textScript(1,'Chương 1',text);
  const timings={textHash:textFingerprint(original.segments.map(s=>s.text)),segments:original.segments.map((_,i)=>({start:i*10,end:(i+1)*10}))};
  const changed=textScript(1,'Chương 1',text,['Trans: Lan']);
  const merged=mergeTimings(changed,timings);

  expect(original.segments[1].text).toBe('Trans: Lan'); // audio hiện tại
  expect(merged).toBe(changed);
  expect(merged.timed).toBe(false);
  expect(merged.segments.length).toBe(3);
  expect(timings.segments.length).toBe(4);
});

it('cùng số đoạn nhưng khác chữ vẫn từ chối; đúng băm mới ghép mốc',()=>{
  const base=textScript(1,'','Đoạn thứ nhất.\n\nĐoạn thứ hai.');
  const stamp=textFingerprint(base.segments.map(s=>s.text));
  const timings={textHash:stamp,segments:[{start:0,end:10},{start:10,end:20}]};
  expect(mergeTimings(base,timings).timed).toBe(true);
  const changed=textScript(1,'','Đoạn mới khác.\n\nĐoạn thứ hai.');
  expect(mergeTimings(changed,timings)).toBe(changed);
});

it('chương native đang phát giữ bản chữ và mốc cũ, lần nạp sau nhận cả hai bản mới',()=>{
  const raw='Chương 1\n\nTrans: Lan\n\nCâu đầu.\n\nCâu sau.';
  const old=textScript(1,'Chương 1',raw);
  const changed=textScript(1,'Chương 1',raw,['Trans: Lan']);
  const timings={active:true,paragraphs:old.segments.map(s=>s.text),textHash:textFingerprint(old.segments.map(s=>s.text)),segments:old.segments.map((_,i)=>({start:i*10,end:(i+1)*10}))};
  const playing=timedTextScript(changed,timings);
  expect(playing.segments[1].text).toBe('Trans: Lan');
  expect(playing.segments[1].start).toBe(10);
  const next=timedTextScript(changed,{active:true,paragraphs:changed.segments.map(s=>s.text),textHash:textFingerprint(changed.segments.map(s=>s.text)),segments:changed.segments.map((_,i)=>({start:i*10,end:(i+1)*10}))});
  expect(next.segments[1].text).toBe('Câu đầu.');
  expect(next.segments[1].start).toBe(10);
});
