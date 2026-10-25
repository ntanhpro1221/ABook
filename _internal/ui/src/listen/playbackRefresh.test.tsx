import {renderToString} from 'react-dom/server';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
const h=vi.hoisted(()=>({effects:[] as any[],fresh:null as any}));
vi.mock('react',async original=>({...await original<typeof import('react')>(),useEffect:(run:any,deps:any[]=[])=>h.effects.push({run,deps})}));
vi.mock('@/listen/source',async original=>({...await original<typeof import('@/listen/source')>(),useListenBook:()=>({data:h.fresh})}));
vi.mock('@/listen/OnlineVoicePrompt',()=>({OnlineVoicePrompt:()=>null}));
vi.mock('sonner',()=>({toast:Object.assign(vi.fn(),{error:vi.fn(),warning:vi.fn(),dismiss:vi.fn()})}));
import {SourceProvider,chapterScriptQuery} from '@/listen/source';
import {PlayerProvider,usePlayer} from '@/listen/player';
import {textScript} from '@/listen/textScript';
const chapters=[1,2].map(id=>({id,index:id,title:`Chương ${id}`,fullTitle:`Chương ${id}`,subtitle:'',duration:id===1?100:0,available:id===1}));
const book={id:'b',title:'Sách',narrator:'Giọng',complete:false,chapters,state:{chapters:{}}} as any;
beforeEach(()=>{
  h.effects=[];h.fresh={...book,complete:true,chapters:chapters.map(c=>({...c,available:true,duration:100}))};
  vi.stubGlobal('window',Object.assign(new EventTarget(),{location:{href:'http://localhost/',search:''}}));
  vi.stubGlobal('navigator',{});
});
afterEach(()=>vi.unstubAllGlobals());
it('chương vừa hoàn tất vào ngay hàng đợi, giữ chương và vị trí đang phát',()=>{
  const engine={time:10,duration:100,paused:true,ended:false,load:vi.fn(),play:vi.fn(),pause:vi.fn(),stop:vi.fn(),seek:vi.fn(),setRate:vi.fn(),setVolume:vi.fn(),on:()=>()=>{}} as any;
  const source={kind:'desktop',audioUrl:()=>'/audio',saveProgress:async()=>{},setRate:async()=>{},book:async()=>h.fresh} as any;
  let player:any;function Probe(){player=usePlayer();return null;}
  renderToString(<QueryClientProvider client={new QueryClient()}><SourceProvider source={source}><PlayerProvider engine={engine} keyboard={false}><Probe/></PlayerProvider></SourceProvider></QueryClientProvider>);
  player.prepare(book,chapters,1,10);
  const metadata=h.effects.filter(e=>e.deps.includes(h.fresh));
  expect(metadata).toHaveLength(1);metadata[0].run();
  expect(engine.time).toBe(10);
  engine.load.mockClear();
  player.jumpTo(2,40); // useListenFrom -> jumpTo khi tìm thấy một câu ở chương vừa xong
  player.next();
  expect(engine.load).toHaveBeenCalled();
  // Đối chứng: nạp lại cuốn với hàng đợi mới thì cùng lệnh nhảy tới chương 2 chạy.
  player.play(h.fresh,h.fresh.chapters,1,10);
  engine.load.mockClear();player.jumpTo(2,40);
  expect(engine.load).toHaveBeenCalledWith(expect.objectContaining({url:'/audio'}),40,true);
});
it('hỏi lại script đã mở khi chương chuyển sang có audio',async()=>{
  const script=vi.fn(async()=>({chapterId:2,timed:false,segments:[],duration:0}));
  const source={script} as any;const client=new QueryClient();
  await client.fetchQuery(chapterScriptQuery(source,'b',chapters[1] as any));
  script.mockResolvedValue({chapterId:2,timed:true,segments:[],duration:100});
  const received=await client.fetchQuery(chapterScriptQuery(source,'b',h.fresh.chapters[1]));
  expect(script).toHaveBeenCalledTimes(2);expect(received.timed).toBe(true);
  client.clear();
});
it('bản audio hoặc mốc chữ đổi cùng thời lượng vẫn hỏi lại kịch bản',async()=>{
  const script=vi.fn(async()=>({chapterId:1,timed:true,segments:[],duration:100}));
  const source={script} as any; const client=new QueryClient();
  const first={...chapters[0],audioVersion:'a',wordsVersion:'w1'};
  await client.fetchQuery(chapterScriptQuery(source,'b',first));
  await client.fetchQuery(chapterScriptQuery(source,'b',{...first,wordsVersion:'w2'}));
  await client.fetchQuery(chapterScriptQuery(source,'b',{...first,audioVersion:'b',wordsVersion:'w2'}));
  expect(script).toHaveBeenCalledTimes(3);
  client.clear();
});
it('desktop giữ bản chữ đang phát qua thay skip và nhận bản mới khi nạp lại chương',async()=>{
  const chapter={...chapters[0],state:'text',speech:true};
  const textBook={...book,stage:'text',chapters:[chapter]};
  h.fresh={...textBook,chapters:[{...chapter,skip:['Trans: Lan']}]};
  const raw='Chương 1\n\nTrans: Lan\n\nCâu truyện.';
  const engine={time:0,duration:100,paused:true,ended:false,load:vi.fn(),play:vi.fn(),pause:vi.fn(),stop:vi.fn(),seek:vi.fn(),setRate:vi.fn(),setVolume:vi.fn(),on:()=>()=>{}} as any;
  const source={kind:'desktop',audioUrl:()=>'',chapterText:async()=>raw,readAloudVoices:async()=>[],saveProgress:async()=>{},setRate:async()=>{},book:async()=>h.fresh} as any;
  const client=new QueryClient(); let player:any;
  function Probe(){player=usePlayer();return null;}
  renderToString(<QueryClientProvider client={client}><SourceProvider source={source}><PlayerProvider engine={engine} keyboard={false}><Probe/></PlayerProvider></SourceProvider></QueryClientProvider>);
  player.prepare(textBook,[chapter],1,0);
  const speech=engine.load.mock.calls[0][0].speech;
  speech.onScript(textScript(1,'Chương 1',raw));
  h.effects.find(e=>e.deps.includes(h.fresh)).run();
  client.removeQueries({queryKey:['listen','script','b']});
  expect(client.getQueryData<any>(['playing-script','b']).segments[1].text).toBe('Trans: Lan');
  player.play(h.fresh,h.fresh.chapters,1,0);
  await vi.waitFor(()=>expect(engine.load).toHaveBeenCalledTimes(2));
  const next=await engine.load.mock.calls[1][0].speech.script();
  expect(next.segments[1].text).toBe('Câu truyện.');
  client.clear();
});
it('phím tua né ô nhập, contenteditable, dialog, slider và phím có Ctrl',()=>{
  class Element {
    isContentEditable=false; role=''; inDialog=false;
    constructor(public tagName:string){}
    closest(selector:string){
      if(this.inDialog&&selector.includes('[role="dialog"]'))return this;
      return this.role&&selector.includes(`[role="${this.role}"]`)?this:null;
    }
    getAttribute(){return this.role;}
  }
  vi.stubGlobal('HTMLElement',Element);const body=new Element('BODY');vi.stubGlobal('document',{body,createElement:()=>({getContext:()=>null})});
  const listeners=new Map<string,any[]>();
  vi.stubGlobal('window',{location:{search:''},addEventListener:(name:string,fn:any)=>listeners.set(name,[...(listeners.get(name)??[]),fn]),removeEventListener:()=>{}});
  const engine={time:10,duration:100,paused:true,ended:false,load:vi.fn(),play:vi.fn(),pause:vi.fn(),stop:vi.fn(),seek:vi.fn(),setRate:vi.fn(),setVolume:vi.fn(),on:()=>()=>{}} as any;
  const source={kind:'desktop',audioUrl:()=>'/audio',saveProgress:async()=>{},setRate:async()=>{},book:async()=>h.fresh} as any;
  let player:any;function Probe(){player=usePlayer();return null;}
  renderToString(<QueryClientProvider client={new QueryClient()}><SourceProvider source={source}><PlayerProvider engine={engine}><Probe/></PlayerProvider></SourceProvider></QueryClientProvider>);
  player.prepare(book,chapters,1,10);
  h.effects.find(e=>e.run.toString().includes('keyboardNavigation')).run();
  const onKey=listeners.get('keydown')!.at(-1);
  const editable=new Element('DIV');editable.isContentEditable=true;
  const dialog=new Element('BUTTON');dialog.inDialog=true;
  const slider=new Element('SPAN');slider.role='slider';
  for(const target of [new Element('INPUT'),new Element('TEXTAREA'),new Element('SELECT'),editable,dialog,slider]){
    onKey({target,key:'ArrowRight',preventDefault:vi.fn()});expect(engine.seek).not.toHaveBeenCalled();
  }
  onKey({target:body,key:'ArrowRight',ctrlKey:true,preventDefault:vi.fn()});expect(engine.seek).not.toHaveBeenCalled();
  onKey({target:body,key:'ArrowRight',preventDefault:vi.fn()});expect(engine.seek).toHaveBeenCalledWith(25);
});
