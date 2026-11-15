// @vitest-environment node
import { readFileSync } from 'node:fs';
import { expect, it } from 'vitest';
import { browserAvailable, launch, findBrowser, connect, openPage, evaluate, waitUntil } from './gallery_browser.mjs';

const probe = readFileSync(new URL('./probes/affordance.js', import.meta.url), 'utf8');
it.skipIf(!browserAvailable)('detects plain actions and false accent with rendered DOM, including nested controls', async () => {
  const browser = await launch(findBrowser());
  let cdp;
  try {
    cdp = await connect(browser.endpoint);
    const page = await openPage(cdp, { width: 900, height: 700, scale: 1, mobile: false, theme: 'light' });
    const html = '<style>:root{--accent-text:#8a5309}button{display:block;border:0;background:transparent;font:16px sans-serif;color:#1a1814;padding:8px}p{color:#8a5309}</style>' +
      '<button>Plain action</button><button style="color:#8a5309">Accent action</button><button>Icon action<svg width="16" height="16"><circle cx="8" cy="8" r="7"/></svg></button>' +
      '<div role="button">Outer action<button>Inner<svg width="16" height="16"><circle cx="8" cy="8" r="7"/></svg></button></div>' +
      '<p>False accent</p><button disabled style="color:#8a5309">Disabled accent</button>' +
      '<button aria-label="Close sheet"><span aria-hidden="true" style="display:block;width:40px;height:4px;background:#777;border-radius:2px"></span></button>' +
      '<div role="group" style="position:relative;width:160px"><button aria-pressed="true">Selected tab</button><span data-sliding-indicator style="position:absolute;bottom:0;left:0;width:90px;height:2px;background:#d4912b"></span></div>' +
      '<div style="position:relative;width:80px;height:80px"><svg style="pointer-events:none" width="40" height="40"><circle cx="20" cy="20" r="18"/></svg><button aria-label="Open picture" style="position:absolute;inset:0"></button></div>';
    await cdp.send('Page.navigate', { url: 'data:text/html;charset=utf-8,' + encodeURIComponent(html) }, page.sessionId);
    await waitUntil(cdp, page.sessionId, "document.body?.textContent.includes('Plain action')", 10000, 'affordance fixture');
    const findings = await evaluate(cdp, page.sessionId, probe);
    expect(findings).toContain('AFFORDANCE_CLICK button Plain action');
    expect(findings).toContain('AFFORDANCE_CLICK div Outer actionInner');
    expect(findings).toContain('AFFORDANCE_ACCENT p False accent');
    expect(findings).toContain('AFFORDANCE_ACCENT button Disabled accent');
    expect(findings.some(f => f.includes('Accent action') || f.includes('Icon action'))).toBe(false);
    expect(findings.some(f => f.includes('Selected tab') || f.includes('Open picture') || f.includes('Close sheet'))).toBe(false);
  } finally { cdp?.close(); await browser.close(); }
});
