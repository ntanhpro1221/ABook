import { renderToString } from 'react-dom/server';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { textScript } from '@/listen/textScript';

const h = vi.hoisted(() => ({ effects: [] as any[], book: null as any, script: null as any,
  chapterParam: '1' as string | undefined, params: new URLSearchParams(), source: {} as any,
  chapterQuery: vi.fn(), navigate: vi.fn(), states: [] as any[] }));
vi.mock('sonner',()=>({toast:{error:vi.fn()}}));
vi.mock('react', async original => {
  const r = await original<typeof import('react')>();
  return { ...r, useEffect: (run: any, deps: any[]) => h.effects.push({run, deps}),
    useState: (value: any) => { const pair = r.useState(value); const setter = vi.fn(pair[1]); h.states.push(setter); return [pair[0], setter]; } };
});
vi.mock('react-router', () => ({ useParams: () => ({id:'b', chapterId:h.chapterParam}),
  useSearchParams: () => [h.params], useLocation: () => ({key:'open'}), useNavigate: () => h.navigate }));
vi.mock('@/listen/source', () => ({ useSource: () => h.source, useListenBook: () => ({data:h.book}),
  useChapterScript: (_id: any, chapter: any) => { h.chapterQuery(chapter); return {data:h.script,isLoading:false}; } }));
vi.mock('@/listen/player', () => ({ usePlayer: () => ({track:null,playing:false}) }));
vi.mock('@/listen/ReadAlongText', () => ({ ReadAlongText: () => null, JumpToPlaying: () => null,
  usePlayingSentence: () => -1, useListenFrom: () => ({canSpeak:false,canListen:false,listenFrom:()=>false}),
  useFollowVoice: () => ({input:{},onScroll:()=>{},follow:()=>{},showJump:false}) }));
vi.mock('@/listen/SentenceMenu', () => ({ useSentenceMenu: () => ({lineEdit:null,readingEdit:false,selected:null,select:vi.fn()}) }));
vi.mock('@/listen/FindInBook', () => ({ FindInBook: () => null }));
vi.mock('@/shared/title', () => ({usePageTitle:()=>{}}));
vi.mock('@/shared/media', () => ({useMediaQuery:()=>false}));
import { ReaderScreen } from '@/listen/ReaderScreen';

function walk(tree: any, predicate: (node: any) => boolean): any[] {
  if (!tree || typeof tree !== 'object') return [];
  if (Array.isArray(tree)) return tree.flatMap(x=>walk(x,predicate));
  return [...(predicate(tree)?[tree]:[]), ...walk(tree.props?.children,predicate)];
}
function mount() {
  let tree:any;
  function Probe() { tree = ReaderScreen({}); return null; }
  renderToString(<Probe/>);
  const node = walk(tree,n=>n.type==='div' && !!n.props.onScroll)[0];
  const scrollIntoView=vi.fn();
  const box={getBoundingClientRect:()=>({top:0,bottom:500}), scrollTo:vi.fn(),
    querySelector:vi.fn(()=>({scrollIntoView})),
    querySelectorAll:()=>[{dataset:{index:'50'},getBoundingClientRect:()=>({top:0,bottom:100})}]};
  node.props.ref.current=box;
  return {tree,node,box,scrollIntoView};
}
beforeEach(()=>{
  vi.useFakeTimers(); h.effects=[];h.states=[];h.chapterQuery.mockClear(); h.params=new URLSearchParams();h.chapterParam='1';
  const data=new Map<string,string>();
  vi.stubGlobal('localStorage',{getItem:(k:string)=>data.get(k)??null,setItem:(k:string,v:string)=>data.set(k,v)});
  vi.stubGlobal('window',Object.assign(new EventTarget(),{setTimeout,clearTimeout,setInterval,clearInterval,requestAnimationFrame:(f:any)=>{f();return 1;}}));
  vi.stubGlobal('document',Object.assign(new EventTarget(),{visibilityState:'visible'}));
  h.source={saveReading:vi.fn().mockResolvedValue(undefined)};
  h.book={id:'b',title:'Sách',chapters:[1,2,3,4].map(id=>({id,title:`Chương ${id}`,state:'text'})),state:{chapters:{}}};
  h.script=textScript(1,'Chương 1',Array.from({length:60},(_,i)=>`Đoạn ${i}`).join('\n\n'));
});
afterEach(()=>{vi.useRealTimers();vi.unstubAllGlobals();});
it('mở /read chọn chương 4 đã lưu trên máy này',()=>{
  h.chapterParam=undefined;
  localStorage.setItem('abook-reading-b#default',JSON.stringify({chapterId:4,index:50,at:Date.now()/1000}));
  mount();
  expect(h.chapterQuery).toHaveBeenLastCalledWith(expect.objectContaining({id:4}));
});
it('rời màn trước 2 giây vẫn lưu local và flush hồ sơ',async()=>{
  const {node}=mount();
  const cleanupEffect=h.effects.find(e=>e.run.toString().includes('visibilitychange'));
  expect(cleanupEffect).toBeTruthy(); const cleanup=cleanupEffect.run();
  node.props.onScroll(); vi.advanceTimersByTime(1500); cleanup(); vi.advanceTimersByTime(5000);
  expect(localStorage.getItem('abook-reading-b#default')).not.toBeNull();
  expect(h.source.saveReading).toHaveBeenCalled();
});
it('bản local mới hơn thắng reading cũ của nguồn',()=>{
  h.book.state.reading={chapterId:1,index:10,at:1};
  localStorage.setItem('abook-reading-b#default',JSON.stringify({chapterId:1,index:50,at:100}));
  const {box}=mount();
  h.effects.find(e=>e.run.toString().includes('restored.current')).run();
  expect(box.querySelector).toHaveBeenCalledWith('[data-index="50"]');
});
it('năm nút cỡ chữ có nhãn số riêng',()=>{
  const {tree}=mount();
  const sizes=walk(tree,n=>n.type==='button' && /^Cỡ chữ \d+$/.test(n.props['aria-label']??''));
  expect(sizes).toHaveLength(5);
  expect(sizes.map(n=>n.props['aria-label']??n.props.children)).toEqual([16,18,20,22,24].map(size=>`Cỡ chữ ${size}`));
});
it('vị trí thông báo chỉ đổi style của toaster, không lan biến qua html xuống cả chương',()=>{
  const style={getPropertyValue:()=>'',setProperty:vi.fn(),removeProperty:vi.fn()};
  Object.assign(document,{querySelectorAll:()=>[{style}]});
  let resize=()=>{}, bottom=56;
  const disconnect=vi.fn();
  vi.stubGlobal('ResizeObserver',class { constructor(run:()=>void){resize=run;} observe(){} disconnect=disconnect; });
  const {tree}=mount();
  walk(tree,n=>n.type==='header')[0].props.ref.current={getBoundingClientRect:()=>({bottom})};
  const cleanup=h.effects.find(e=>e.run.toString().includes('toastOffset')).run();
  expect(style.setProperty).toHaveBeenCalledWith('--toast-top','64px');
  bottom=72;resize();expect(style.setProperty).toHaveBeenLastCalledWith('--toast-top','80px');
  cleanup();expect(style.removeProperty).toHaveBeenCalledWith('--toast-top');
  expect(disconnect).toHaveBeenCalledOnce();
});

it('ẩn trang và pagehide flush ngay chỗ vừa cuộn, lỗi giữ pending và thử lại',async()=>{
  h.source.saveReading.mockRejectedValueOnce(new Error('không ghi được'));
  const {node}=mount();
  const cleanup=h.effects.find(e=>e.run.toString().includes('visibilitychange')).run();
  node.props.onScroll();
  Object.assign(document,{visibilityState:'hidden'});
  document.dispatchEvent(new Event('visibilitychange'));
  await vi.advanceTimersByTimeAsync(0);
  expect(h.source.saveReading).toHaveBeenCalledTimes(1);
  expect(JSON.parse(localStorage.getItem('abook-reading-b#default')!).pending).toBe(true);
  window.dispatchEvent(new Event('pagehide'));
  await vi.advanceTimersByTimeAsync(0);
  expect(h.source.saveReading).toHaveBeenCalledTimes(2);
  expect(JSON.parse(localStorage.getItem('abook-reading-b#default')!).pending).toBe(false);
  cleanup();
});

it('ACK cũ không xác nhận nhầm lần cuộn mới hơn',async()=>{
  let ack!: () => void;
  h.source.saveReading.mockImplementationOnce(()=>new Promise<void>(resolve=>{ack=resolve;}));
  const {node}=mount();
  const cleanup=h.effects.find(e=>e.run.toString().includes('visibilitychange')).run();
  node.props.onScroll();
  await vi.advanceTimersByTimeAsync(2000);
  node.props.onScroll();
  ack();
  await vi.advanceTimersByTimeAsync(0);
  expect(JSON.parse(localStorage.getItem('abook-reading-b#default')!).pending).toBe(true);
  await vi.advanceTimersByTimeAsync(2000);
  expect(JSON.parse(localStorage.getItem('abook-reading-b#default')!).pending).toBe(false);
  cleanup();
});

it('chỗ đọc local có revision hỏng được cấp lại revision an toàn trước khi thử gửi', async()=>{
  h.book.state._clock=2;
  h.book.state.reading={chapterId:1,index:10,at:100,rev:{counter:2,node:'server'}};
  localStorage.setItem('abook-reading-b#default',JSON.stringify({chapterId:1,index:50,at:200,pending:true,rev:{counter:1e100,node:'peer'}}));
  mount();
  const cleanup=h.effects.find(e=>e.run.toString().includes('visibilitychange')).run();
  await vi.advanceTimersByTimeAsync(5000);
  expect(h.source.saveReading).toHaveBeenCalledWith('b',1,50,expect.objectContaining({rev:expect.objectContaining({counter:3})}),undefined);
  expect(JSON.parse(localStorage.getItem('abook-reading-b#default')!).pending).toBe(false);
  cleanup();
});

it('ACK từ epoch trước không xác nhận nhầm counter trùng trong epoch mới', async()=>{
  let ack!:()=>void;
  h.source.saveReading.mockImplementationOnce(()=>new Promise<void>(resolve=>{ack=resolve;}));
  const {node}=mount();
  const cleanup=h.effects.find(e=>e.run.toString().includes('visibilitychange')).run();
  node.props.onScroll();
  await vi.advanceTimersByTimeAsync(2000);
  const place=JSON.parse(localStorage.getItem('abook-reading-b#default')!);
  localStorage.setItem('abook-reading-b#default',JSON.stringify({...place,rev:{...place.rev,epoch:'1'},pending:true}));
  ack();
  await vi.advanceTimersByTimeAsync(0);
  expect(JSON.parse(localStorage.getItem('abook-reading-b#default')!).pending).toBe(true);
  cleanup();
});
