import {renderToString} from 'react-dom/server';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
// Phím tắt của trình phát (máy tính): giữ phím không bắn lặp việc bật / tắt, và Space sau một phím mũi tên vẫn là phát / tạm dừng.
const h=vi.hoisted(()=>({effects:[] as any[]}));
vi.mock('react',async original=>({...await original<typeof import('react')>(),useEffect:(run:any,deps:any[]=[])=>h.effects.push({run,deps})}));
vi.mock('@/listen/OnlineVoicePrompt',()=>({OnlineVoicePrompt:()=>null}));
vi.mock('sonner',()=>({toast:Object.assign(vi.fn(),{error:vi.fn(),warning:vi.fn(),dismiss:vi.fn()})}));
import {SourceProvider} from '@/listen/source';
import {PlayerProvider,usePlayer} from '@/listen/player';
const chapters=[1,2,3].map(id=>({id,index:id,title:`Chương ${id}`,fullTitle:`Chương ${id}`,subtitle:'',duration:100,available:true}));
const book={id:'b',title:'Sách',narrator:'Giọng',complete:true,chapters,state:{chapters:{}}} as any;
class Element {
  isContentEditable=false; role='';
  constructor(public tagName:string){}
  closest(selector:string){return this.role&&selector.includes(`[role="${this.role}"]`)?this:null;}
  getAttribute(){return this.role;}
}
let listeners:Map<string,any[]>;let engine:any;
beforeEach(()=>{
  h.effects=[];listeners=new Map();
  vi.stubGlobal('HTMLElement',Element);
  vi.stubGlobal('document',{body:new Element('BODY'),createElement:()=>({getContext:()=>null})});
  vi.stubGlobal('window',{location:{search:''},addEventListener:(name:string,fn:any)=>listeners.set(name,[...(listeners.get(name)??[]),fn]),removeEventListener:()=>{},setTimeout:()=>0,clearTimeout:()=>{},setInterval:()=>0,clearInterval:()=>{}});
  vi.stubGlobal('navigator',{});
  engine={time:10,duration:100,paused:true,ended:false,load:vi.fn(),play:vi.fn(),pause:vi.fn(),stop:vi.fn(),seek:vi.fn(),setRate:vi.fn(),setVolume:vi.fn(),on:()=>()=>{}};
  const source={kind:'desktop',audioUrl:()=>'/audio',saveProgress:async()=>{},setRate:async()=>{},book:async()=>book} as any;
  let player:any;function Probe(){player=usePlayer();return null;}
  renderToString(<QueryClientProvider client={new QueryClient()}><SourceProvider source={source}><PlayerProvider engine={engine}><Probe/></PlayerProvider></SourceProvider></QueryClientProvider>);
  player.prepare(book,chapters,1,10);
  h.effects.find(e=>e.run.toString().includes('keyboardNavigation')).run();
  // Đang phát: Space là tạm dừng (đường đồng bộ, đếm được).
  engine.paused=false;engine.load.mockClear();engine.play.mockClear();engine.pause.mockClear();engine.seek.mockClear();
});
afterEach(()=>vi.unstubAllGlobals());
/** Như trình duyệt: mọi bộ nghe keydown (cả bộ bắt ở pha capture) nhận cùng một sự kiện. */
const press=(event:Record<string,unknown>)=>{for(const listener of listeners.get('keydown')!)listener({preventDefault:vi.fn(),...event});};
const toggles=()=>engine.play.mock.calls.length+engine.pause.mock.calls.length+engine.load.mock.calls.length;

it('giữ Space: chỉ lần nhấn đầu bật / tắt, các lần bàn phím tự lặp thì không',()=>{
  const body=document.body;
  press({target:body,key:' '});
  expect(toggles()).toBe(1);
  press({target:body,key:' ',repeat:true});
  press({target:body,key:' ',repeat:true});
  expect(toggles()).toBe(1);
});

it('giữ Shift+→ không nhảy qua nhiều chương',()=>{
  press({target:document.body,key:'ArrowRight',shiftKey:true});
  const once=engine.load.mock.calls.length;
  expect(once).toBe(1);
  press({target:document.body,key:'ArrowRight',shiftKey:true,repeat:true});
  expect(engine.load.mock.calls.length).toBe(once);
});

it('bấm chuột vào một nút, tua bằng → rồi Space: vẫn là phát / tạm dừng, không bấm lại nút ấy',()=>{
  const button=new Element('BUTTON');
  for(const listener of listeners.get('pointerdown')!)listener({target:button});
  press({target:button,key:'ArrowRight'});
  expect(engine.seek).toHaveBeenCalled();
  const space={target:button,key:' ',preventDefault:vi.fn()};
  for(const listener of listeners.get('keydown')!)listener(space);
  expect(space.preventDefault).toHaveBeenCalled();
  expect(toggles()).toBe(1);
});

it('Tab tới một nút rồi Space: Space kích hoạt nút ấy (không cướp phím)',()=>{
  const button=new Element('BUTTON');
  press({target:button,key:'Tab'});
  press({target:button,key:' '});
  expect(toggles()).toBe(0);
});
