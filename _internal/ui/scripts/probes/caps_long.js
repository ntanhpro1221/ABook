// Nhãn HOA dài: DESIGN 5.5 - chữ hoa giãn chỉ cho nhãn phần, tối đa 3 chữ; phần mô tả xuống chữ thường 12 px. Dò mọi phần tử đang hiện có
// text-transform: uppercase mà chữ nhìn thấy dài hơn 3 chữ. Dùng: gallery_shots --probe scripts/probes/caps_long.js
(() => {
  const out = [];
  const seen = new Set();
  for (const el of document.querySelectorAll('body *')) {
    if (!el.childNodes.length || getComputedStyle(el).textTransform !== 'uppercase') continue;
    // Chỉ chữ do chính phần tử này vẽ (chữ của con riêng được xét ở con ấy).
    const own = [...el.childNodes].filter(n => n.nodeType === 3).map(n => n.textContent).join(' ').trim();
    const text = own || (el.children.length ? '' : (el.textContent || '').trim());
    if (!text || el.getClientRects().length === 0 || el.closest('[aria-hidden="true"]')) continue;
    const words = text.split(/\s+/).filter(w => /[\p{L}\p{N}]/u.test(w));
    if (words.length > 3 && !seen.has(text)) { seen.add(text); out.push(`${words.length} chữ HOA: ${text.slice(0, 70)}`); }
  }
  return out;
})()
