// @vitest-environment node
import { readFileSync } from "node:fs";
import { createServer } from "node:http";
import { expect, it } from "vitest";
import { browserAvailable, launch, findBrowser, connect, openPage, evaluate } from "./gallery_browser.mjs";
import { inspectionExpression, settle } from "./gallery_inspect.mjs";

it.skipIf(!browserAvailable)("resolves Vietnamese tab overhangs without hiding a real uneven gap", async () => {
  const fonts = new URL('../node_modules/@fontsource/be-vietnam-pro/', import.meta.url);
  const css = [400, 500].map(weight => readFileSync(new URL(`${weight}.css`, fonts), 'utf8').replaceAll('./files/', '/fonts/')).join('\n');
  const server = createServer((request, response) => {
    if (request.url.startsWith('/fonts/')) {
      response.setHeader('Content-Type', 'font/woff2');
      response.end(readFileSync(new URL('files/' + request.url.slice(7), fonts))); return;
    }
    response.end(`<!doctype html><meta charset="utf-8"><style>${css}
      body{margin:0;background:white;color:black}#tabs{display:flex;gap:24px;position:absolute;left:704.90625px;top:92px}
      button{display:inline-flex;align-items:center;height:44px;padding:0;border:0;background:none;color:inherit;font:500 14px/20px "Be Vietnam Pro"}
      .label{display:inline-flex;align-items:baseline;gap:6px}.count{font-size:12px;font-weight:400;line-height:16px}
      </style><div id="tabs"><button><span class="label">Chương<span class="count">24</span></span></button><button>Lịch sử</button><button>Nhân vật</button></div>`);
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  let browser, cdp;
  try {
    browser = await launch(findBrowser(), { disableGpu: true }); cdp = await connect(browser.endpoint);
    const page = await openPage(cdp, { width: 1440, height: 900, scale: 1, mobile: false, theme: 'light' });
    await cdp.send('Page.navigate', { url: `http://127.0.0.1:${server.address().port}/` }, page.sessionId);
    await settle(cdp, page.sessionId, 10000);
    const rhythm = result => result.findings.filter(f => f.metric === 'horizontal-ink-gap');
    expect(rhythm(await evaluate(cdp, page.sessionId, inspectionExpression(false)))).toEqual([]);
    await evaluate(cdp, page.sessionId, `document.querySelector('#tabs button:last-child').style.marginLeft='4px'`);
    const broken = rhythm(await evaluate(cdp, page.sessionId, inspectionExpression(false)));
    expect(broken).toHaveLength(1);
    expect(Math.abs(broken[0].delta)).toBeGreaterThan(2);
    expect(broken[0].tolerance).toBe(2);
  } finally { cdp?.close(); await browser?.close(); await new Promise(resolve => server.close(resolve)); }
}, 60000);
