import {renderToString} from 'react-dom/server';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
const h=vi.hoisted(()=>({night:null as any,book:null as any,scripts:{} as any,play:vi.fn().mockResolvedValue(undefined)}));
vi.mock('react',async original=>{const r=await original<typeof import('react')>();return {...r,useState:(v:any)=>r.useState(v===false?true:v)};});
vi.mock('@tanstack/react-query',()=>({useQuery:()=>({data:h.scripts}),useQueryClient:()=>({invalidateQueries:vi.fn()})}));
vi.mock('@/listen/source',()=>({useSource:()=>({book:async()=>h.book,dismissNight:async()=>{}}),useLastNight:()=>({data:{bookId:'b',night:h.night}}),useListenBook:()=>({data:h.book}),isMissing:()=>false}));
vi.mock('@/listen/LibraryScreen',()=>({usePlayListenBook:()=>h.play}));
vi.mock('@/listen/PlayerViews',()=>({sentenceAt:()=>null}));
import {MorningRecap} from '@/listen/MorningRecap';
function nodes(tree:any,predicate:(n:any)=>boolean):any[]{if(!tree||typeof tree!=='object')return [];if(Array.isArray(tree))return tree.flatMap(n=>nodes(n,predicate));return [...(predicate(tree)?[tree]:[]),...nodes(tree.props?.children,predicate)];}
beforeEach(()=>{
  h.play.mockClear();
  vi.useFakeTimers();const now=Date.now()/1000;
  h.night={id:'night',bookId:'b',bookTitle:'Sách',device:'desktop',startedAt:now-1000,endedAt:now-60,
    events:[{type:'timer',at:now-900,position:{chapterId:1,chapterTitle:'Chương 1',seconds:50}},
      {type:'touch',at:now-700,position:{chapterId:1,chapterTitle:'Chương 1',seconds:100}},
      {type:'stopped',at:now-60,position:{chapterId:2,chapterTitle:'Chương 2',seconds:10}}]};
  h.book={id:'b',state:{},chapters:[{id:1},{id:2}]};
  h.scripts=Object.fromEntries([1,2].map(id=>[id,{timed:true,segments:Array.from({length:31},(_,i)=>({id:i,text:`Câu ${i} chương ${id}`,start:i*10,end:i*10+10}))}]));
});
afterEach(()=>vi.useRealTimers());
function buttons(){let tree:any;function Probe(){tree=MorningRecap({});return null;}renderToString(<Probe/>);return nodes(tree,n=>n.type==='button');}
function choices(){return buttons().map(n=>n.props.children).filter(x=>typeof x==='object'&&Array.isArray(x)).flat().filter(x=>typeof x==='string'&&x.startsWith('Câu '));}
it('qua ranh giới chương: đủ câu đề xuất, cuối chương trước và đầu chương sau',()=>{
  expect(choices()).toContain('Câu 10 chương 1');
  expect(choices()).toContain('Câu 30 chương 1');
  expect(choices()).toContain('Câu 1 chương 2');
});
it('chọn câu chương sau phát đúng chương và mốc của câu ấy',async()=>{
  const button=buttons().find(n=>n.props.children?.includes?.('Câu 1 chương 2'));
  expect(button).toBeTruthy();
  button.props.onClick();
  await Promise.resolve();
  expect(h.play).toHaveBeenCalledWith(h.book,2,10);
});
it('khoảng nghe ba chương có đủ chương giữa dù chương ấy không có marker',()=>{
  h.book.chapters=[{id:1},{id:9},{id:2}];
  h.scripts[9]={timed:true,segments:[{id:0,text:'Câu giữa chương 9',start:0,end:10}]};
  expect(choices()).toContain('Câu giữa chương 9');
});
it('đối chứng cùng chương: khoảng câu có chứa mốc chạm máy và mốc tự dừng',()=>{
  h.night.events[2].position={chapterId:1,chapterTitle:'Chương 1',seconds:220};
  expect(choices()).toContain('Câu 10 chương 1');expect(choices()).toContain('Câu 22 chương 1');
});
