import {renderToString} from 'react-dom/server';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
// Đang dừng ở chương 1, bấm "Chương sau": lời lưu chỗ ở chương 1 (gửi lúc rời chương) về SAU khi đã sang chương 2 không được làm trình phát
// tưởng chương 2 đã lưu - không thì chỗ đầu chương 2 không bao giờ được lưu và lần mở sau quay về chương 1.
const h=vi.hoisted(()=>({effects:[] as any[]}));
vi.mock('react',async original=>({...await original<typeof import('react')>(),useEffect:(run:any,deps:any[]=[])=>h.effects.push({run,deps})}));
vi.mock('@/listen/OnlineVoicePrompt',()=>({OnlineVoicePrompt:()=>null}));
vi.mock('sonner',()=>({toast:Object.assign(vi.fn(),{error:vi.fn(),warning:vi.fn(),dismiss:vi.fn()})}));
import {SourceProvider} from '@/listen/source';
import {PlayerProvider,usePlayer} from '@/listen/player';
const chapters=[1,2].map(id=>({id,index:id,title:`Chương ${id}`,fullTitle:`Chương ${id}`,subtitle:'',duration:100,available:true}));
const book={id:'b',title:'Sách',narrator:'Giọng',complete:true,chapters,state:{chapters:{}}} as any;
beforeEach(()=>{
  h.effects=[];
  vi.stubGlobal('window',Object.assign(new EventTarget(),{location:{href:'http://localhost/',search:''},setTimeout:()=>0,clearTimeout:()=>{},setInterval:()=>0,clearInterval:()=>{}}));
  vi.stubGlobal('navigator',{});
  vi.stubGlobal('localStorage',undefined);
});
afterEach(()=>vi.unstubAllGlobals());

it('ACK muộn của chương cũ không che việc lưu đầu chương mới',async()=>{
  const handlers=new Map<string,()=>void>();
  const engine={time:10,duration:100,paused:true,ended:false,load:vi.fn(),play:vi.fn(),pause:vi.fn(),stop:vi.fn(),seek:vi.fn(),setRate:vi.fn(),setVolume:vi.fn(),
    on:(name:string,fn:()=>void)=>{handlers.set(name,fn);return()=>{};}} as any;
  const waiting:(()=>void)[]=[];
  const saveProgress=vi.fn((..._args:unknown[])=>new Promise<void>(resolve=>waiting.push(resolve)));
  const source={kind:'desktop',audioUrl:()=>'/audio',saveProgress,setRate:async()=>{},book:async()=>book} as any;
  let player:any;function Probe(){player=usePlayer();return null;}
  renderToString(<QueryClientProvider client={new QueryClient()}><SourceProvider source={source}><PlayerProvider engine={engine} keyboard={false}><Probe/></PlayerProvider></SourceProvider></QueryClientProvider>);
  player.prepare(book,chapters,1,10);
  h.effects.find(e=>e.run.toString().includes('syncClock')).run();
  engine.time=50; // đã nghe tới 0:50 rồi dừng
  player.next(); // rời chương 1: lưu 0:50 của chương 1
  await vi.waitFor(()=>expect(saveProgress).toHaveBeenCalledTimes(1));
  expect(saveProgress.mock.calls[0].slice(0,3)).toEqual(['b',1,50]);
  engine.time=0;
  waiting.shift()!(); // máy chủ trả lời lần lưu chương 1 sau khi đã sang chương 2
  await new Promise(resolve=>setTimeout(resolve,0));
  handlers.get('duration')!(); // chương 2 nạp xong, vẫn đang dừng: lưu đầu chương 2
  await vi.waitFor(()=>expect(saveProgress).toHaveBeenCalledTimes(2));
  expect(saveProgress.mock.calls[1].slice(0,3)).toEqual(['b',2,0]);
});
