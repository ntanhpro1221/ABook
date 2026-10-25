// Đo đúng vòng kiểm mở app, không gọi settleLaunch thêm (gọi thêm sẽ kết thúc hoạt ảnh và làm sai số đo).
import { readFileSync, readdirSync, mkdirSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { parseArgs, findBrowser, serve, launch, connect, evaluate, openPage, waitUntil } from './gallery_browser.mjs';

const args = parseArgs(process.argv.slice(2));
if (!args.out) throw new Error('Cần --out');
const assets = path.join(args.dist, 'assets');
const chunk = readdirSync(assets).find(file => file.endsWith('.js') && /as settleLaunch/.test(readFileSync(path.join(assets, file), 'utf8')));
if (!chunk) throw new Error('Không thấy settleLaunch trong bản gallery');
const symbol = readFileSync(path.join(assets, chunk), 'utf8').match(/(\w+) as settleLaunch/)[1];
const local = await serve(args.dist), browser = await launch(findBrowser(args.browser), { preserveProfile: true });
const cdp = await connect(browser.endpoint), samples = [];
try {
  for (const id of args.only ?? ['phone/library-full', 'phone/library-empty', 'phone/library-error', 'phone/library-loading']) {
    for (const variant of id === 'phone/library-full' ? ['normal', 'delayed', 'offscreen'] : ['normal']) {
    for (let run = 0; run < 5; run++) {
      const page = await openPage(cdp, { width: 412, height: 915, scale: 2, mobile: true, theme: 'light' });
      await cdp.send('Page.addScriptToEvaluateOnNewDocument', { source: `(() => {
        const report = window.__launchProbe = { firstRender: null, settled: null, ready: null, calls: {}, checks: [] };
        new MutationObserver(() => { if (report.firstRender === null && document.querySelector('main > *')) {
          report.firstRender = performance.now();
          if ('${variant}' === 'offscreen') {
            const image = document.createElement('img'); image.loading = 'lazy'; image.width = 200; image.height = 300;
            image.src = './covers/suong-mu-1.svg?offscreen'; image.style.cssText = 'position:absolute;top:10000px;left:20px';
            document.querySelector('main').append(image);
          }
        } }).observe(document, { childList: true, subtree: true });
        const animations = document.getAnimations.bind(document);
        document.getAnimations = (...args) => {
          const list = animations(...args);
          if (new Error().stack.includes('at ${symbol} (')) {
            const moving = list.filter(a => a.playState === 'running' && a.effect?.getComputedTiming().endTime !== Infinity);
            report.checks.push({ at: performance.now(), moving: moving.length });
            if (!moving.length && report.settled === null) report.settled = performance.now();
          }
          return list;
        };
        let capacitor;
        Object.defineProperty(window, 'Capacitor', { configurable: true, get: () => capacitor, set: value => {
          capacitor = value;
          if (!value.nativePromise || value.nativePromise.__probe) return;
          const call = value.nativePromise;
          value.nativePromise = (...args) => {
            const key = args[0] + '.' + args[1]; report.calls[key] = (report.calls[key] ?? 0) + 1;
            if (key === 'EbookLibrary.appReady') report.ready = performance.now();
            const result = call(...args);
            return '${variant}' === 'delayed' && key === 'EbookLibrary.localBooks' ? new Promise(resolve => setTimeout(() => resolve(result), 280)) : result;
          };
          value.nativePromise.__probe = true;
        } });
      })();` }, page.sessionId);
      await cdp.send('Page.navigate', { url: `${local.base}?frame=${id}&theme=light` }, page.sessionId);
      await waitUntil(cdp, page.sessionId, 'window.__launchProbe?.ready !== null && window.__gallery?.ready', 12000, id);
      const result = await evaluate(cdp, page.sessionId, `({ ...window.__launchProbe, pendingImages: [...document.querySelectorAll('main img')].filter(i => !i.complete).map(i => ({ src: i.src, loading: i.loading, y: i.getBoundingClientRect().y })), placeholders: document.querySelectorAll('.motion-loading-placeholder').length })`);
      samples.push({ id, variant, run, ...result, settleMs: result.settled === null ? null : result.settled - result.firstRender, readyMs: result.ready - result.firstRender });
      console.log(id, variant, run, JSON.stringify({ settleMs: samples.at(-1).settleMs, readyMs: samples.at(-1).readyMs, pending: result.pendingImages.length }));
      await cdp.send('Target.closeTarget', { targetId: page.targetId });
    }
    }
  }
} finally { cdp.close(); await browser.close(); local.server.close(); }
mkdirSync(args.out, { recursive: true });
writeFileSync(path.join(args.out, 'launch.json'), JSON.stringify({ chunk, symbol, samples }, null, 2));
