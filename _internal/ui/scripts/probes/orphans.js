// Chữ mồ côi: khối chữ nhiều dòng mà dòng cuối chỉ còn một chữ (DESIGN: mô tả không rớt một chữ). Dùng: gallery_shots --probe.
(() => {
  const out = [];
  const blocks = new Set();
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    const t = walker.currentNode; if (!t.textContent.trim()) continue;
    let el = t.parentElement;
    while (el && getComputedStyle(el).display.startsWith('inline')) el = el.parentElement;
    if (el) blocks.add(el);
  }
  for (const el of blocks) {
    if (el.closest('.reading-surface,[aria-hidden="true"]')) continue;
    const r = document.createRange(); r.selectNodeContents(el);
    const rects = [...r.getClientRects()].filter(x => x.width > 0 && x.height > 4);
    if (!rects.length) continue;
    const tops = [...new Set(rects.map(x => Math.round(x.top)))].sort((a,b)=>a-b);
    if (tops.length < 2) continue;
    // words on last line
    const lastTop = tops[tops.length-1];
    const words = (el.innerText || '').trim().split(/\s+/);
    const tw = document.createTreeWalker(el, NodeFilter.SHOW_TEXT); let lastWords = [];
    while (tw.nextNode()) { const n = tw.currentNode; const re = /\S+/g; let m;
      while ((m = re.exec(n.data))) { const rr = document.createRange(); rr.setStart(n, m.index); rr.setEnd(n, m.index + m[0].length);
        const b = rr.getBoundingClientRect(); if (b.height && Math.abs(Math.round(b.top) - lastTop) <= 3) lastWords.push(m[0]); } }
    if (lastWords.length === 1 && words.length > 2) out.push(`${lastWords[0]} | ${(el.innerText||'').slice(0,60).replace(/\n/g,' ')}`);
  }
  return out;
})()
