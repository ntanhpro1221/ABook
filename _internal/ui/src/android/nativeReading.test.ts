import {expect,it,vi} from 'vitest';
const h = vi.hoisted(() => ({saveReading: vi.fn().mockResolvedValue({})}));
vi.mock('@/android/plugins',()=>({EbookLibrary:h,EbookPlayer:{},ReadAloud:{}}));
vi.mock('@/android/readAloud',()=>({phonePrepare:()=>({})}));
vi.mock('@/android/textImport',()=>({phoneTextImport:{}}));
import {androidSource} from '@/android/androidSource';
it('nguồn Android lưu anchor, thời điểm và đúng hồ sơ qua native',async()=>{
  expect(androidSource.saveReading).toBeTypeOf('function');
  const position = {chapterId:4,index:50,at:100,anchor:{segment:50,charOffset:0,textHash:'fnv1a64:0000000000000000'}};
  await androidSource.saveReading!('b',4,50,position,'r-one');
  expect(h.saveReading).toHaveBeenCalledWith({id:'b',...position,record:'r-one'});
});
