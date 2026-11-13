// @vitest-environment happy-dom
import {act} from 'react';
import {createRoot, type Root} from 'react-dom/client';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {TonePage} from './TonePage';
import {changeTone,getTones,selectAudioBook} from './audioFx';

let host:HTMLDivElement,root:Root;
const button=(text:string)=>{const b=[...host.querySelectorAll('button')].find(b=>b.textContent===text||b.getAttribute('aria-label')===text);if(!b)throw new Error(`Missing ${text}`);return b;};
const click=async(text:string)=>{await act(async()=>button(text).click());};
const submit=async()=>{await act(async()=>host.querySelector('form')!.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true})));};
beforeEach(async()=>{
  Object.assign(globalThis,{IS_REACT_ACT_ENVIRONMENT:true});HTMLElement.prototype.scrollIntoView=vi.fn();
  vi.spyOn(HTMLElement.prototype,'animate').mockImplementation(()=>({cancel(){},onfinish:null,finished:Promise.resolve()}) as unknown as Animation);
  localStorage.clear();selectAudioBook('tone-ui');changeTone(l=>{l.data.mine=[];l.data.books={};l.data.drafts={};l.select('off');});
  host=document.createElement('div');document.body.append(host);root=createRoot(host);
});
afterEach(async()=>{await act(async()=>root.unmount());host.remove();});
it('shows all built-in names, creates a named preset, duplicates, reorders and deletes without confirmation',async()=>{
  await act(async()=>root.render(<TonePage onBack={()=>{}}/>));
  for(const name of ['Tắt','Giọng rõ','Ấm','Sáng','Bớt xì','Tai nghe nhỏ','Loa ngoài'])expect(button(name)).toBeDefined();
  await click('Giọng rõ');expect(button('Giọng rõ').getAttribute('aria-checked')).toBe('true');expect(button('Ấm').getAttribute('aria-checked')).toBe('false');
  // Số âm là dấu trừ thật, không gạch nối.
  expect(host.textContent).toContain('−4 dB');expect(host.textContent).not.toMatch(/-\d+ dB/);
  await act(async()=>changeTone(l=>l.edit(0,8)));expect(host.textContent).toContain('Tự chỉnh (chưa lưu)');
  await click('Lưu âm sắc');expect((host.querySelector('input[maxlength]') as HTMLInputElement).value).toBe('Của tôi 1');await submit();
  expect(getTones().data.mine).toHaveLength(1);await click('Thêm tuỳ chọn: Của tôi 1');await click('Nhân bản');await submit();expect(getTones().data.mine).toHaveLength(2);
  const copy=getTones().data.mine[1];await act(async()=>button(copy.name).dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowUp',altKey:true,bubbles:true})));
  expect(getTones().data.mine[0].id).toBe(copy.id);await click(`Thêm tuỳ chọn: ${copy.name}`);await click('Xoá');expect(getTones().data.mine).toHaveLength(1);expect(host.querySelector('[role=alertdialog]')).toBeNull();
  await click('Tạo âm sắc');await submit();expect(getTones().data.mine).toHaveLength(2);
});
it.each(['Lưu đè','Lưu thành mới'])('asks only when leaving an edited user preset: %s',async(choice)=>{
  changeTone(l=>{l.select('clear');l.save('Original');});const id=getTones().selected.id;const back=vi.fn();
  await act(async()=>root.render(<TonePage onBack={back}/>));await act(async()=>changeTone(l=>l.edit(2,9)));
  expect(host.textContent).not.toContain('Lưu thay đổi?');await click('Sáng');expect(host.textContent).not.toContain('Lưu thay đổi?');
  await click('Quay lại');expect(back).not.toHaveBeenCalled();expect(host.textContent).toContain('Lưu thay đổi?');expect(getTones().selected.id).toBe(id);
  await click(choice);if(choice==='Lưu thành mới')await submit();expect(back).toHaveBeenCalledOnce();
  expect(getTones().data.mine).toHaveLength(choice==='Lưu đè'?1:2);expect(getTones().data.mine[0].bands[2]).toBe(choice==='Lưu đè'?9:2);
});
it('guards a parent close and applies book scope independently of other books',async()=>{
  changeTone(l=>{l.select('warm');l.save('Original');l.edit(1,6);});const close=vi.fn(),guard={current:null as ((leave:()=>void)=>void)|null};
  await act(async()=>root.render(<TonePage onBack={()=>{}} leaveGuard={guard}/>));
  await act(async()=>guard.current!(close));expect(close).not.toHaveBeenCalled();await click('Bỏ thay đổi');expect(close).toHaveBeenCalledOnce();
  const input=host.querySelector('[role=switch]') as HTMLButtonElement;await act(async()=>input.click());expect(getTones().scoped).toBe(true);
  await click('Giọng rõ');await act(async()=>selectAudioBook('other'));expect(getTones().selected.id).not.toBe('clear');
});
