// Real gallery journeys, per-rAF matrices, artwork bounds and screenshots (CPU only).
import { mkdirSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { serve, launch, connect, openPage, evaluate, waitUntil, findBrowser } from './gallery_browser.mjs';

const out = path.resolve(process.argv[2]); mkdirSync(out, { recursive: true });
const local = await serve(process.argv[3] ?? path.resolve(import.meta.dirname, '../dist/gallery'));
const browser = await launch(findBrowser(), { disableGpu: true });
const cdp = await connect(browser.endpoint);
const report = { browser: await cdp.send('Browser.getVersion'), journeys: [] };
try {
  const page = await openPage(cdp, { width: 1440, height: 900, scale: 1, mobile: false, theme: 'light', isolated: true });
  const session = page.sessionId;
  await cdp.send('Page.navigate', { url: `${local.base}?frame=desktop/library-full&theme=light` }, session);
  await waitUntil(cdp, session, 'window.__gallery?.ready', 30000, 'gallery');
  const ev = code => evaluate(cdp, session, code);
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const shot = async name => {
    const { data } = await cdp.send('Page.captureScreenshot', { format: 'png' }, session);
    writeFileSync(path.join(out, name + '.png'), Buffer.from(data, 'base64'));
  };
  async function journey(name, selector) {
    await sleep(500);
    const point = await ev(`(() => {
      const el = document.querySelector(${JSON.stringify(selector)}); if (!el) throw Error('Missing ${selector}');
      const r = el.getBoundingClientRect(); return {x:r.x+r.width/2,y:r.y+r.height/2};
    })()`);
    await ev(`(() => {
      window.__ledgerFrames = []; const start = performance.now();
      const rect = e => { if (!e) return null; const r=e.getBoundingClientRect(); return {x:r.x,y:r.y,w:r.width,h:r.height}; };
      const sample = () => {
        const page=document.querySelector('.page-motion'), flight=document.querySelector('[data-book-cover-flight]');
        const style=page && getComputedStyle(page);
        window.__ledgerFrames.push({t:performance.now()-start,page:rect(page),transform:style?.transform,opacity:style?.opacity,
          flight:rect(flight), flightOpacity:flight && getComputedStyle(flight).opacity, flightTo:flight?.dataset.flightTo,
          animations:document.getAnimations().filter(a=>a.effect?.getComputedTiming().endTime!==Infinity).map(a=>({
            name:a.animationName??'',frames:a.effect.getKeyframes(),duration:a.effect.getTiming().duration}))});
        if(performance.now()-start<800) requestAnimationFrame(sample);
      }; requestAnimationFrame(sample);
    })()`);
    await cdp.send('Input.dispatchMouseEvent', { type: 'mousePressed', button: 'left', clickCount: 1, ...point }, session);
    await cdp.send('Input.dispatchMouseEvent', { type: 'mouseReleased', button: 'left', clickCount: 1, ...point }, session);
    for (let i = 0; i < 5; i++) { await sleep(55); await shot(`${name}-${i}`); }
    await sleep(600);
    const frames = await ev('window.__ledgerFrames');
    const moving = frames.filter(f => f.transform && f.transform !== 'none');
    const flight = frames.filter(f => f.flight);
    const intermediate = flight.filter(f=>Math.abs(f.flight.x-flight[0].flight.x)>1 || Math.abs(f.flight.y-flight[0].flight.y)>1);
    const pass = moving.length >= 3 && (!name.startsWith('book') || intermediate.length >= 3 && flight.every(f=>Number(f.flightOpacity)===1));
    report.journeys.push({ name, pass, frames });
    console.log(`${pass ? 'PASS' : 'FAIL'} ${name}: ${moving.length} geometric page frames, ${flight.length} artwork frames`);
  }
  await journey('book-in', 'button:has(> [data-book-cover="dong-ho-cat"])');
  await journey('book-back', 'button[aria-label="Về Thư viện"]');
  await journey('settings-in', 'a[href="#/settings"]');
  await journey('settings-back', 'a[href="#/"]');
  report.pass = report.journeys.every(j=>j.pass);
} catch (error) { report.error = error.stack; report.pass = false; }
finally {
  cdp.close(); await browser.close(); await new Promise(r=>local.server.close(r));
  writeFileSync(path.join(out, 'motion.json'), JSON.stringify(report,null,2)+'\n');
}
process.exitCode = report.pass ? 0 : 1;
