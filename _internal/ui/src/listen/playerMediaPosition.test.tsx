import {QueryClient, QueryClientProvider} from '@tanstack/react-query';
import {renderToString} from 'react-dom/server';
import {beforeEach, afterEach, expect, it, vi} from 'vitest';
const h=vi.hoisted(()=>({effects:[] as {run:()=>any,deps:readonly unknown[]}[],nullIndex:0,track:{bookId:'book',bookTitle:'Sach',narrator:'Giong',chapterId:1,chapterTitle:'Chuong 1',bookCover:null}}));
vi.mock('react',async original=>{
 const react=await original<typeof import('react')>();
 return {...react,useEffect:(run:()=>any,deps:readonly unknown[]=[])=>h.effects.push({run,deps}),
   useState:(initial:any)=>react.useState(initial===null && h.nullIndex++===0 ? h.track : initial)};
});
vi.mock('@/listen/OnlineVoicePrompt',()=>({OnlineVoicePrompt:()=>null}));
vi.mock('sonner',()=>({toast:Object.assign(vi.fn(),{dismiss:vi.fn(),info:vi.fn(),success:vi.fn()})}));
import {SourceProvider} from '@/listen/source';
import {PlayerProvider, usePlayer} from '@/listen/player';
const cleanups:(()=>void)[]=[];
beforeEach(()=>{
 h.effects=[];h.nullIndex=0;vi.useFakeTimers();
 vi.stubGlobal('window',Object.assign(new EventTarget(),{location:{href:'http://localhost/',search:''},setInterval,clearInterval,setTimeout,clearTimeout,requestAnimationFrame:()=>0,cancelAnimationFrame:()=>{}}));
 vi.stubGlobal('navigator',{mediaSession:{setActionHandler:vi.fn(),setPositionState:vi.fn()}});
 vi.stubGlobal('MediaMetadata',class {constructor(data:any){Object.assign(this,data)}});
});
afterEach(()=>{cleanups.splice(0).forEach(f=>f());vi.useRealTimers();vi.unstubAllGlobals()});
it('tua khi đang dừng báo lại vị trí mới cho điều khiển media của hệ thống (soát a104 F5)',async()=>{
 let actions!:ReturnType<typeof usePlayer>;
 const handlers=new Map<string,(()=>void)[]>();let time=60;
 const fire=(type:string)=>handlers.get(type)?.forEach(f=>f());
 const engine={get time(){return time},duration:300,paused:true,ended:false,
 load:vi.fn(),play:vi.fn(),pause:vi.fn(),stop:vi.fn(),seek:(at:number)=>{time=at;fire('time');fire('seeked')},setRate:vi.fn(),setVolume:vi.fn(),
 on:(type:string,f:()=>void)=>{handlers.set(type,[...(handlers.get(type)??[]),f]);return()=>{}}};
 const chapters=[{id:1,title:'Chuong 1',fullTitle:'Chuong 1',available:true,duration:300}];
 const book={id:'book',title:'Sach',narrator:'Giong',chapters,complete:true,state:{chapters:{}}};
 const source={kind:'desktop',audioUrl:()=>'/audio',saveProgress:vi.fn().mockResolvedValue({}),beginProgress:vi.fn().mockResolvedValue({}),setRate:async()=>{},book:async()=>book};
 function Capture(){actions=usePlayer();return null}
 renderToString(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{queryFn:async()=>[],retry:false}}})}><SourceProvider source={source as never}><PlayerProvider engine={engine as never} keyboard={false}><Capture/></PlayerProvider></SourceProvider></QueryClientProvider>);
 actions.prepare(book as never,chapters as never,1,60);
 for(const effect of h.effects.filter(e=>e.deps.includes(engine)||e.run.toString().includes('setActionHandler'))){const cleanup=effect.run();if(typeof cleanup==='function')cleanups.push(cleanup)}
 expect(navigator.mediaSession.setPositionState).toHaveBeenLastCalledWith({duration:300,playbackRate:1,position:60});
 const seekTo=(navigator.mediaSession.setActionHandler as any).mock.calls.find((c:any[])=>c[0]==='seekto')[1];
 seekTo({seekTime:20});for(let i=0;i<20;i++)await Promise.resolve();
 expect(time).toBe(20);
 expect(navigator.mediaSession.setPositionState).toHaveBeenLastCalledWith({duration:300,playbackRate:1,position:20});
 vi.advanceTimersByTime(60_000); // đang dừng: không có nhịp nào khác, vị trí vẫn ở chỗ vừa tua
 expect(navigator.mediaSession.setPositionState).toHaveBeenLastCalledWith({duration:300,playbackRate:1,position:20});
});
