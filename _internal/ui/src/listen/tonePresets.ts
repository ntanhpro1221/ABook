import catalog from '../../../abook/webui/assets/tone_presets.json';
import { S } from '@/shared/strings.generated';
import { TONE_NAMES } from './toneLabels.generated';

export const TONE_CATALOG = catalog;
export interface TonePreset { id:string; name:string; bands:number[] }
export interface ToneSelection { id:string; bands:number[] }
export interface ToneDocument { mine:TonePreset[]; shared:ToneSelection; books:Record<string,ToneSelection>; drafts:Record<string,number[]> }
export const BUILTIN_TONES:TonePreset[] = catalog.presets.map(p=>({id:p.id,name:TONE_NAMES[p.id as keyof typeof TONE_NAMES],bands:p.bands}));
const gains=(value:unknown)=>catalog.frequencies.map((_,i)=>{
  const n=Array.isArray(value)?value[i]:0; return typeof n==='number'&&Number.isFinite(n)?Math.max(-12,Math.min(12,n)):0;
});
const off=():ToneSelection=>({id:'off',bands:catalog.presets[0].bands.slice()});
const equal=(a:number[],b:number[])=>a.every((v,i)=>v===b[i]);
export interface DeletedTone { preset:TonePreset; index:number; shared:ToneSelection|null; books:Record<string,ToneSelection>; draft?:number[] }

/** Local listener data only. Playback settings consume the resolved bands, never platform presets. */
export class ToneLibrary {
  data:ToneDocument;
  book='';
  constructor(value:unknown={}) {
    const d=(value&&typeof value==='object'?value:{}) as Partial<ToneDocument>;
    const ids=new Set<string>();
    const mine=(Array.isArray(d.mine)?d.mine:[]).filter(p=>p&&typeof p.id==='string'&&p.id.startsWith('user:')&&typeof p.name==='string'&&p.name.trim()&&!ids.has(p.id)&&!!ids.add(p.id))
      .map(p=>({id:p.id,name:p.name.trim().slice(0,80),bands:gains(p.bands)}));
    const selection=(v:ToneSelection|undefined):ToneSelection=>v&&(v.id==='draft'||BUILTIN_TONES.some(p=>p.id===v.id)||mine.some(p=>p.id===v.id))?{id:v.id,bands:gains(v.bands)}:off();
    this.data={mine,shared:selection(d.shared),books:Object.fromEntries(Object.entries(d.books&&typeof d.books==='object'?d.books:{}).map(([k,v])=>[k,selection(v)])),drafts:Object.fromEntries(Object.entries(d.drafts??{}).filter(([id])=>mine.some(p=>p.id===id)).map(([id,v])=>[id,gains(v)]))};
  }
  get scoped(){return !!this.book&&Object.hasOwn(this.data.books,this.book);}
  get selected(){return this.scoped?this.data.books[this.book]:this.data.shared;}
  get preset(){return [...BUILTIN_TONES,...this.data.mine].find(p=>p.id===this.selected.id);}
  get name(){return this.dirty||this.selected.id==='draft'?S.s_tone_draft:this.preset?.name??S.s_tat_3286064e;}
  get dirty(){return this.selected.id.startsWith('user:')&&!!this.preset&&!equal(this.selected.bands,this.preset.bands);}
  get hasEdits(){return Object.keys(this.data.drafts).length>0;}
  prepareLeave(){const id=Object.keys(this.data.drafts)[0];if(id)this.select(id);return !!id;}
  discard(){delete this.data.drafts[this.selected.id];this.select(this.selected.id);}
  private put(value:ToneSelection){if(this.scoped)this.data.books[this.book]=value;else this.data.shared=value;}
  scope(enabled:boolean){if(!this.book||enabled===this.scoped)return;if(enabled)this.data.books[this.book]={...this.selected,bands:this.selected.bands.slice()};else delete this.data.books[this.book];}
  select(id:string){const p=[...BUILTIN_TONES,...this.data.mine].find(p=>p.id===id);if(p)this.put({id,bands:(this.data.drafts[id]??p.bands).slice()});}
  edit(index:number,value:number){if(index<0||index>=catalog.frequencies.length)return;const s=this.selected,bands=gains(s.bands.map((n,i)=>i===index?value:n));if(s.id.startsWith('user:')){if(equal(bands,this.preset!.bands))delete this.data.drafts[s.id];else this.data.drafts[s.id]=bands;}this.put({id:s.id.startsWith('user:')?s.id:'draft',bands});}
  save(name:string,overwrite=false){
    name=name.trim().slice(0,80);if(!name)return null;
    delete this.data.drafts[this.selected.id];
    const id=overwrite&&this.selected.id.startsWith('user:')?this.selected.id:`user:${crypto.randomUUID()}`;
    const p={id,name,bands:this.selected.bands.slice()},index=this.data.mine.findIndex(p=>p.id===id);
    if(index>=0)this.data.mine[index]=p;else this.data.mine.push(p);
    if(this.data.shared.id===id)this.data.shared={id,bands:p.bands.slice()};
    for(const [book,s] of Object.entries(this.data.books))if(s.id===id)this.data.books[book]={id,bands:p.bands.slice()};
    this.put({id,bands:p.bands.slice()});return id;
  }
  rename(id:string,name:string){const p=this.data.mine.find(p=>p.id===id);if(p&&name.trim())p.name=name.trim().slice(0,80);}
  duplicate(id:string,name:string){const p=this.data.mine.find(p=>p.id===id);if(!p||!name.trim())return;this.data.mine.push({id:`user:${crypto.randomUUID()}`,name:name.trim().slice(0,80),bands:p.bands.slice()});}
  move(id:string,to:number){const from=this.data.mine.findIndex(p=>p.id===id);if(from<0)return;const [p]=this.data.mine.splice(from,1);this.data.mine.splice(Math.max(0,Math.min(this.data.mine.length,to)),0,p);}
  delete(id:string):DeletedTone|null{
    const index=this.data.mine.findIndex(p=>p.id===id);if(index<0)return null;
    const [preset]=this.data.mine.splice(index,1),shared=this.data.shared.id===id?this.data.shared:null,books:Record<string,ToneSelection>={};
    if(shared)this.data.shared=off();
    for(const [book,s] of Object.entries(this.data.books))if(s.id===id){books[book]=s;this.data.books[book]=off();}
    const draft=this.data.drafts[id];delete this.data.drafts[id];return {preset,index,shared,books,draft};
  }
  undo(token:DeletedTone){if(this.data.mine.some(p=>p.id===token.preset.id))return;this.data.mine.splice(Math.min(token.index,this.data.mine.length),0,token.preset);if(token.draft)this.data.drafts[token.preset.id]=token.draft;if(token.shared&&this.data.shared.id==='off')this.data.shared=token.shared;for(const [b,s] of Object.entries(token.books))if(this.data.books[b]?.id==='off')this.data.books[b]=s;}
}
