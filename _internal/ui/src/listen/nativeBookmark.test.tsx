import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderToString } from 'react-dom/server';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
vi.mock('sonner',()=>({toast:Object.assign(vi.fn(),{dismiss:vi.fn(),info:vi.fn(),success:vi.fn(),warning:vi.fn()})}));
vi.mock('@/listen/OnlineVoicePrompt',()=>({OnlineVoicePrompt:()=>null}));
vi.mock('@/listen/readAloudVoice',async(original)=>({...await original<typeof import('@/listen/readAloudVoice')>(),voicesOf:async()=>[]}));
import { SourceProvider } from '@/listen/source';
import { PlayerProvider, usePlayer } from '@/listen/player';
import { textScript } from '@/listen/textScript';
import { timedTextScript, estimatedStarts } from '@/listen/readAloud';
import { textFingerprint } from '@/listen/readingAnchor';
beforeEach(()=>{
 vi.stubGlobal('window',Object.assign(new EventTarget(),{location:{href:'http://localhost/',search:''},setTimeout,clearTimeout}));
 vi.stubGlobal('navigator',{});
});
afterEach(()=>vi.unstubAllGlobals());
function mount(script=false){
 const chapter={id:1,title:'Một',fullTitle:'Một',available:false,state:'text',speech:true,duration:0};
 const book={id:'b',title:'B',narrator:'',complete:true,chapters:[chapter],state:{chapters:{},bookmarks:[]}};
 const engine:any={native:true,bookId:'',chapterId:1,time:6,duration:12,paused:true,rate:1,ended:false,sleep:{kind:'off'},
   loadQueue:vi.fn(),play:vi.fn(),pause:vi.fn(),stop:vi.fn(),seek:vi.fn(),setRate:vi.fn(),setVolume:vi.fn(),on:()=>()=>{},
   addBookmark:vi.fn(async()=>({id:'m',chapterId:1,seconds:6,note:'',at:1}))};
 const source:any={kind:'android',book:async()=>book,setRate:async()=>{},audioUrl:()=>''};
 const client=new QueryClient({defaultOptions:{queries:{retry:false,gcTime:0}}});
 if(script){
   const plain=textScript(1,'Một',['A','B','C','D'].map(x=>x.repeat(28)).join('\n\n'));
   const starts=estimatedStarts(plain.segments);
   client.setQueryData(['listen','script','b',1,'text'],timedTextScript(plain,{textHash:textFingerprint(plain.segments.map(s=>s.text)),segments:starts.map(start=>({start,end:start+2}))}));
 }
 let actions!:ReturnType<typeof usePlayer>;
 function Capture(){actions=usePlayer();return null;}
 renderToString(<QueryClientProvider client={client}><SourceProvider source={source}><PlayerProvider engine={engine} keyboard={false}><Capture/></PlayerProvider></SourceProvider></QueryClientProvider>);
 actions.prepare(book as any,[chapter] as any,1,0);
 return {actions,engine,client};
}
it('no script leaves sentence capture to native',async()=>{
 const {actions,engine,client}=mount();
 await actions.addBookmark();
 expect(engine.addBookmark).toHaveBeenCalledWith('',undefined);
 client.clear();
});
it('cached script sends sentence and anchor',async()=>{
 const {actions,engine,client}=mount(true);
 await actions.addBookmark();
 expect(engine.addBookmark).toHaveBeenCalledWith('',expect.objectContaining({index:3,quote:'D'.repeat(28),anchor:expect.objectContaining({segment:3,charOffset:0})}));
 client.clear();
});
