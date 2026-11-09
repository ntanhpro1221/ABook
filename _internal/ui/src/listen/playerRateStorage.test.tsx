import {renderToString} from 'react-dom/server';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
// Đổi tốc độ khi bộ nhớ trang bị chặn (chế độ riêng tư) hay đầy: tốc độ vẫn đổi ngay, chỉ báo là chưa lưu được - như âm lượng.
const h=vi.hoisted(()=>({effects:[] as any[],toast:null as any}));
vi.mock('react',async original=>({...await original<typeof import('react')>(),useEffect:(run:any,deps:any[]=[])=>h.effects.push({run,deps})}));
vi.mock('@/listen/OnlineVoicePrompt',()=>({OnlineVoicePrompt:()=>null}));
vi.mock('sonner',()=>{h.toast=Object.assign(vi.fn(),{error:vi.fn(),warning:vi.fn(),success:vi.fn(),dismiss:vi.fn()});return {toast:h.toast};});
import {SourceProvider} from '@/listen/source';
import {PlayerProvider,usePlayer} from '@/listen/player';
import {S} from '@/shared/strings.generated';
const chapters=[1,2].map(id=>({id,index:id,title:`Chương ${id}`,fullTitle:`Chương ${id}`,subtitle:'',duration:100,available:true}));
const book={id:'b',title:'Sách',narrator:'Giọng',complete:true,chapters,state:{chapters:{}}} as any;
let engine:any,player:any;
beforeEach(()=>{
  h.effects=[];
  vi.stubGlobal('document',{body:{},createElement:()=>({getContext:()=>null})});
  vi.stubGlobal('window',{location:{search:''},addEventListener:()=>{},removeEventListener:()=>{},setTimeout:()=>0,clearTimeout:()=>{},setInterval:()=>0,clearInterval:()=>{}});
  vi.stubGlobal('navigator',{});
  engine={time:10,duration:100,paused:false,ended:false,load:vi.fn(),play:vi.fn(),pause:vi.fn(),stop:vi.fn(),seek:vi.fn(),setRate:vi.fn(),setVolume:vi.fn(),on:()=>()=>{}};
  const source={kind:'desktop',audioUrl:()=>'/audio',saveProgress:async()=>{},setRate:async()=>{},book:async()=>book} as any;
  function Probe(){player=usePlayer();return null;}
  renderToString(<QueryClientProvider client={new QueryClient()}><SourceProvider source={source}><PlayerProvider engine={engine}><Probe/></PlayerProvider></SourceProvider></QueryClientProvider>);
  player.prepare(book,chapters,1,10);
});
afterEach(()=>vi.unstubAllGlobals());

it.each(['SecurityError','QuotaExceededError'])('đổi tốc độ khi localStorage ném %s: tốc độ vẫn áp, có báo chưa lưu',(name)=>{
  const broken=()=>{throw new DOMException('blocked',name);};
  vi.stubGlobal('localStorage',{getItem:broken,setItem:broken,removeItem:broken,clear:broken,key:broken,length:0});
  engine.setRate.mockClear();
  expect(()=>player.setRate(1.5)).not.toThrow();
  expect(engine.setRate).toHaveBeenLastCalledWith(1.5);
  expect(h.toast.error).toHaveBeenCalledWith(S.s_copy_51e8a9a73804);
});
