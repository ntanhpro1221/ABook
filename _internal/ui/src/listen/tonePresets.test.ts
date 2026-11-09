// @vitest-environment happy-dom
import {expect,it} from 'vitest';
import {BUILTIN_TONES,TONE_CATALOG,ToneLibrary} from './tonePresets';
import cases from '../../../abook/webui/assets/tone_response_cases.json';

it('creates, renames, duplicates, deletes, undoes and reorders without changing factory presets',()=>{
  const l=new ToneLibrary();l.select('clear');l.edit(0,7);expect(l.selected.id).toBe('draft');
  const id=l.save('  Mine 1  ')!;expect(l.name).toBe('Mine 1');l.rename(id,'Renamed');expect(l.name).toBe('Renamed');
  l.duplicate(id,'Copy');expect(l.data.mine).toHaveLength(2);const copy=l.data.mine[1].id;
  l.move(copy,0);expect(l.data.mine.map(p=>p.id)).toEqual([copy,id]);
  const token=l.delete(id)!;expect(l.selected.id).toBe('off');l.undo(token);expect(l.selected.id).toBe(id);
  expect(l.data.mine.map(p=>p.id)).toEqual([copy,id]);expect(BUILTIN_TONES[1].bands[0]).toBe(-4);
});
it('keeps global settings separate from books, persists and preserves a later choice on undo',()=>{
  const l=new ToneLibrary();l.select('warm');l.book='a';l.scope(true);l.select('clear');const id=l.save('Book')!;
  l.book='b';expect(l.selected.id).toBe('warm');l.book='a';expect(l.selected.id).toBe(id);
  const restored=new ToneLibrary(JSON.parse(JSON.stringify(l.data)));restored.book='a';expect(restored.selected.id).toBe(id);
  const token=restored.delete(id)!;restored.select('bright');restored.undo(token);expect(restored.selected.id).toBe('bright');
  restored.scope(false);expect(restored.selected.id).toBe('warm');expect(restored.scoped).toBe(false);
});
it('changes user bands as a draft until overwrite or save as new, without changing other presets',()=>{
  const l=new ToneLibrary();l.select('clear');const id=l.save('First')!;l.edit(2,12);expect(l.dirty).toBe(true);expect(l.preset!.bands[2]).toBe(2);
  l.save('First',true);expect(l.dirty).toBe(false);expect(l.data.mine).toHaveLength(1);expect(l.preset!.bands[2]).toBe(12);
  l.edit(1,-12);l.save('Second');expect(l.data.mine).toHaveLength(2);expect(l.data.mine[0].id).toBe(id);expect(l.data.mine[0].bands[1]).toBe(-2);
});
it('retains edits while auditioning other presets and resolves all edits only when leaving',()=>{
  const l=new ToneLibrary();l.select('clear');const id=l.save('First')!;l.edit(0,9);l.select('bright');
  expect(l.hasEdits).toBe(true);expect(l.dirty).toBe(false);l.select(id);expect(l.selected.bands[0]).toBe(9);
  const restored=new ToneLibrary(JSON.parse(JSON.stringify(l.data)));restored.select('warm');expect(restored.prepareLeave()).toBe(true);
  expect(restored.selected.id).toBe(id);restored.discard();expect(restored.hasEdits).toBe(false);expect(restored.selected.bands[0]).toBe(-4);
});
it('has visible Vietnamese labels for every built-in preset',()=>{
  expect(BUILTIN_TONES.map(p=>p.name)).toEqual(['Tắt','Giọng rõ','Ấm','Sáng','Bớt xì','Tai nghe nhỏ','Loa ngoài']);
});
it('rejects invalid names and nonfinite gains and clamps user input',()=>{
  const l=new ToneLibrary();expect(l.save(' ')).toBeNull();l.edit(0,99);l.edit(1,NaN);expect(l.selected.bands.slice(0,2)).toEqual([12,0]);
  expect(new ToneLibrary({mine:[{id:'off',name:'bad',bands:[]}],shared:{id:'missing'}}).selected.id).toBe('off');
});
it('uses the one shared 31-frequency fixture for every factory curve and sample rate',()=>{
  expect(cases.frequencies).toHaveLength(31);expect(cases.cases).toHaveLength(21);
  for(const c of cases.cases){expect(BUILTIN_TONES.find(p=>p.id===c.id)!.bands).toEqual(c.bands);expect(c.db).toHaveLength(31);}
  expect(TONE_CATALOG.q).toBe(1.4);
});
