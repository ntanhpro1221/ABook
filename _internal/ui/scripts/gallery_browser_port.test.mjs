import { expect, it } from 'vitest';
import { readDevToolsPort, parseArgs } from './gallery_browser.mjs';
import { main } from './gallery_inspect.mjs';
it('static geometry sweep is explicit and cannot pretend to gate dynamic sheets', async()=>{
  expect(parseArgs(['--static-only']).staticOnly).toBe(true);
  await expect(main(['--static-only','--out','unused'])).rejects.toThrow('cannot gate SHEET GEOMETRY');
});
it.each(['EBUSY','EACCES','EPERM','ENOENT'])('cổng Edge vừa ghi: %s là chờ đọc lại, không làm hỏng lượt đo',code=>{
  let locked=true;
  const read=()=>{if(locked)throw Object.assign(new Error('writing'),{code});return '9222\r\n/devtools/browser/a\r\n';};
  expect(readDevToolsPort('port',read)).toEqual([]);
  locked=false;expect(readDevToolsPort('port',read).map(s=>s.trim())).toEqual(['9222','/devtools/browser/a']);
});
it('không che lỗi đọc khác',()=>{
  expect(()=>readDevToolsPort('port',()=>{throw Object.assign(new Error('disk'),{code:'EIO'});})).toThrow('disk');
});
it('nội dung chưa đủ dòng vẫn ở trạng thái chờ của launch',()=>{
  expect(readDevToolsPort('port',()=> '9222\n')).toEqual(['9222']);
});
