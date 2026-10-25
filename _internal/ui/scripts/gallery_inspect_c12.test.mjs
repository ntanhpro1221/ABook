// @vitest-environment node
import { beforeAll, describe, expect, it } from 'vitest';
import { layoutFixtures } from './gallery_inspect_layout_fixture.mjs';
import { browserAvailable } from './gallery_browser.mjs';
import { crossFrameTitles } from './gallery_inspect_layout.mjs';

it('cùng chân chữ vẫn bắt tiêu đề sai y hoặc cỡ quá 1 px', () => {
  const frame = (id,y,fontSize) => ({id,platform:'phone',theme:'light',layout:{screenTitle:{baseline:44,rect:{x:20,y,width:120,height:32},frameTop:0,fontSize,selector:'h1'}}});
  const findings = crossFrameTitles([frame('library',20,'24px'),frame('studio',20,'24px'),frame('settings',22,'26px')]);
  expect(findings.map(f=>f.metric)).toEqual(['screen-title-top','screen-title-size']);
  expect(crossFrameTitles([frame('a',20,'24px'),frame('b',21,'25px')])).toEqual([]);
});

describe.skipIf(!browserAvailable)('c12: kiểm hình học trường nhập và menu trên Edge', () => {
  let results;
  beforeAll(async () => { results = await layoutFixtures({ fixture:'layout-c12.html' }); },60000);
  it('bắt đúng select nửa cột, nút viền, ảnh thiếu cỡ, phần trăm thụt và menu lệch', () => {
    for(const r of results) {
      const ids = metric => r.findings.filter(f=>f.metric===metric).map(f=>f.selector);
      expect(ids('select-column-width')).toEqual(['#select-bad']);
      expect(ids('outlined-button')).toEqual(['#outline-bad']);
      expect(ids('image-dimensions')).toEqual(['#image-bad']);
      expect(ids('remote-status-inset')).toEqual(['#remote-bad']);
      expect(ids('submenu-gap')).toEqual(['#submenu-bad']);
      expect(ids('submenu-align')).toEqual(['#submenu-bad']);
      expect(ids('toast-lines')).toEqual([]);
    }
  });
});
