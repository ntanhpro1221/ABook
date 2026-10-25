// Hộp thoại đã là mặt nổi; nhóm bên trong dùng khoảng trắng thay khung (DESIGN 4–6).
export function inspectFrames({ all, css, rect, visible, selector, add }) {
  const transparent = value => value === "transparent" || /rgba\([^)]*,\s*0\)$/.test(value);
  // Cùng token cho tiêu đề mục đứng riêng / gập mở, ở mọi frame (kể cả người dùng phóng chữ).
  const rem = Number.parseFloat(css(document.documentElement).fontSize);
  for (const el of all) {
    const box = visible(el, rect(el.getBoundingClientRect()));
    if (!box) continue;
    const s = css(el);
    if (el.matches('button:not([role="switch"]):not([role="radio"]):not([role="checkbox"])')
      && ['Top','Right','Bottom','Left'].every(side => Number.parseFloat(s[`border${side}Width`]) > 0 && s[`border${side}Style`] !== 'none' && !transparent(s[`border${side}Color`])))
      add('SIBLING CONSISTENCY', el, el.textContent, [box], { metric: 'outlined-button', reason: 'Actions use plain text or a fill; borders belong to inputs' });
    if (el.matches('select[data-select-layout="column"]')) {
      const parent = el.parentElement, p = css(parent), b = parent.getBoundingClientRect();
      const width = b.width - Number.parseFloat(p.paddingLeft) - Number.parseFloat(p.paddingRight) - Number.parseFloat(p.borderLeftWidth) - Number.parseFloat(p.borderRightWidth);
      if (width - box.width > 1.01) add('SIBLING CONSISTENCY', el, el.getAttribute('aria-label') ?? el.textContent, [box],
        { metric: 'select-column-width', value: box.width, referenceValue: width, delta: box.width - width, tolerance: 1, reason: 'Field select must span its content column' });
    }
    if (el.matches('img') && (!el.hasAttribute('width') || !el.hasAttribute('height')))
      add('SIBLING CONSISTENCY', el, el.getAttribute('alt'), [box], { metric: 'image-dimensions', reason: 'Images reserve their dimensions before loading' });
    if (el.matches('[data-side="left"],[data-side="right"]') && el.matches('[role="menu"],[role="dialog"]')) {
      const trigger = el.dataset.submenuTrigger ? document.getElementById(el.dataset.submenuTrigger)
        : all.find(node => node.getAttribute('aria-controls') === el.id && el.id);
      const parent = trigger?.closest('[role="menu"][data-side],[role="dialog"][data-side]');
      if (!parent || parent === el) continue;
      const b = parent.getBoundingClientRect(), child = el.getBoundingClientRect();
      const gap = el.dataset.side === 'left' ? b.left - child.right : child.left - b.right;
      if (b.width + child.width + 8 <= innerWidth - 24 && Math.abs(gap - 8) > 1.01)
        add('RHYTHM', el, el.textContent, [box, rect(b)], { metric: 'submenu-gap', value: gap, referenceValue: 8, delta: gap - 8, tolerance: 1, reason: 'Submenus use the shared 8 px outer gap' });
      const y = parent.dataset.side === 'top' ? b.bottom - child.height : b.top;
      const expected = Math.max(12, Math.min(y, innerHeight - child.height - 12));
      if (Math.abs(child.top - expected) > 1.01) add('RHYTHM', el, el.textContent, [box, rect(b)],
        { metric: 'submenu-align', value: child.top, referenceValue: expected, delta: child.top - expected, tolerance: 1, reason: 'Submenu top or bottom aligns with its parent, within viewport collisions' });
    }
  }
  // Một thông tin một chỗ (soát ảnh 4x 26-10: "Tải · 42%" trên bìa và "42%" dưới tên cùng một thẻ). Cả thẻ đang ngoài vùng nhìn:
  // lặp số là lỗi của thẻ, không phụ thuộc chỗ cuộn.
  for (const el of all.filter(el => el.matches('[data-book-tile],li,[role="listitem"]') && !el.querySelector('[data-book-tile],li,[role="listitem"]'))) {
    // React tách "{n}%" thành nhiều nút chữ: gộp chữ trực tiếp theo phần tử rồi mới tìm số.
    const own = new Map();
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    for (let node = walker.nextNode(); node; node = walker.nextNode()) if (node.parentElement) own.set(node.parentElement, (own.get(node.parentElement) ?? '') + node.textContent);
    const seen = new Map();
    for (const [host, text] of own) {
      // Không dùng visible(): lớp chữ trên bìa (pointer-events none) không bao giờ là elementFromPoint nhưng vẫn hiện.
      const r = host.getBoundingClientRect();
      if (!r.width || !r.height || host.closest('[hidden],[inert],.sr-only') || css(host).visibility !== 'visible') continue;
      for (const match of text.matchAll(/\d+(?:[.,]\d+)?\s?%/g)) {
        const value = match[0].replace(/\s/g, '');
        if (seen.has(value) && seen.get(value) !== host) add('REPEATED LABEL', el, value, [rect(el.getBoundingClientRect())], { metric: 'repeated-value', reason: 'The same figure is shown twice inside one card or row' });
        seen.set(value, host);
      }
    }
  }
  const sectionHeadings = [];
  for (const el of all.filter(el => el.hasAttribute('data-section-title'))) {
    const box = visible(el, rect(el.getBoundingClientRect()));
    if (!box) continue;
    const s = css(el), size = Number.parseFloat(s.fontSize), weight = Number(s.fontWeight), transform = s.textTransform;
    sectionHeadings.push({ selector: selector(el), text: el.textContent, size, weight, transform });
    if (Math.abs(size - rem * 1.125) > .1 || weight !== 500 || transform !== 'none')
      add('SIBLING CONSISTENCY', el, el.textContent, [box], { metric: 'section-title-style', value: size, referenceValue: rem * 1.125,
        delta: size - rem * 1.125, weight, transform, reason: 'Section titles must use the same 18/500 sentence-case token across frames' });
  }
  for (const group of all.filter(el => el.matches('.choice-row,[data-choice-grid]'))) {
    for (const el of group.querySelectorAll('button')) {
      const box = visible(el, rect(el.getBoundingClientRect()));
      if (!box) continue;
      const s = css(el);
      if (!transparent(s.backgroundColor) || ['Top','Right','Bottom','Left'].every(side => Number.parseFloat(s[`border${side}Width`]) > 0 && !transparent(s[`border${side}Color`])))
        add('SIBLING CONSISTENCY', el, el.textContent, [box], { metric: 'choice-box', reason: 'Text choices must not use permanent fills or bordered boxes' });
    }
  }
  for (const el of all.filter(el => el.matches('.motion-dialog[role="dialog"]'))) {
    const box = visible(el, rect(el.getBoundingClientRect()));
    if (!box) continue;
    const s = css(el), padding = ['Top','Right','Bottom','Left'].map(side => Number.parseFloat(s[`padding${side}`]));
    if (padding.some(value => Math.abs(value - 24) > .1)) add('RHYTHM', el, el.textContent, [box],
      { metric: 'dialog-padding', value: padding[0], referenceValue: 24, delta: padding[0] - 24, reason: 'Modal padding must use the 24 px spacing token' });
  }
  for (const el of all.filter(el => el.matches('[data-sonner-toast]:not([data-removed="true"])'))) {
    const box = visible(el, rect(el.getBoundingClientRect()));
    if (!box) continue;
    const actions = el.querySelectorAll('[data-button]').length;
    if (actions > 1) add('SIBLING CONSISTENCY', el, el.textContent, [box], { metric: 'toast-action-count', value: actions, referenceValue: 1, delta: actions - 1, reason: 'A toast has at most one action' });
    const title = el.querySelector('[data-title]');
    if (title) {
      if (el.querySelector('[data-description]')?.textContent?.trim()) add('LINE BREAK', title, title.textContent, [rect(title.getBoundingClientRect())],
        { metric: 'toast-lines', reason: 'Toast titles wrap in full; extra explanation opens on request' });
    }
  }
  const control = el => el.matches('button,a,input,textarea,select,option,svg,svg *,[role="menu"],[role="menuitem"],[role="option"],[role="tooltip"]')
    || el.getBoundingClientRect().height <= 48 && el.querySelector('input:not([type="checkbox"]):not([type="radio"]),textarea,select');
  const card = el => {
    const s = css(el);
    return !control(el) && ['Top', 'Right', 'Bottom', 'Left'].every(side => Number.parseFloat(s[`border${side}Width`]) > 0
      && s[`border${side}Style`] !== 'none' && !transparent(s[`border${side}Color`]))
      && ['TopLeft', 'TopRight', 'BottomLeft', 'BottomRight'].some(corner => Number.parseFloat(s[`border${corner}Radius`]) > 0);
  };
  for (const el of all) {
    const box = visible(el, rect(el.getBoundingClientRect()));
    if (!box || !card(el) || el.matches('[role="dialog"]')) continue;
    for (let p = el.parentElement; p; p = p.parentElement) {
      if (p.matches('[role="dialog"]') || card(p)) {
        add('NESTED CARD', el, el.textContent, [box, rect(p.getBoundingClientRect())], { otherSelector: selector(p), reason: 'A bordered card is nested inside a card or dialog' });
        break;
      }
    }
  }
  // Giữ số đo cho từng danh sách, kể cả khi không có nền hay vạch trong khung nhìn.
  const listEdges = [];
  for (const list of all.filter(el => el.hasAttribute('data-list-edges'))) {
    const box = visible(list, rect(list.getBoundingClientRect()));
    if (!box) continue;
    const b = list.getBoundingClientRect(), s = css(list), left = b.left + Number.parseFloat(s.paddingLeft), end = b.right - Number.parseFloat(s.paddingRight);
    const lines = [], fills = [];
    for (const el of [list, ...list.querySelectorAll('*')]) {
      const r = visible(el, rect(el.getBoundingClientRect()));
      if (!r) continue;
      const st = css(el);
      const divider = ['Top','Bottom'].some(side => Number.parseFloat(st[`border${side}Width`]) === 1 && st[`border${side}Style`] !== 'none' && !transparent(st[`border${side}Color`]));
      const hairline = st.backgroundImage.includes('linear-gradient') && st.backgroundSize.endsWith('1px');
      if (divider || hairline) {
        const inset = hairline ? Number.parseFloat(st.backgroundSize.match(/100% - ([\d.]+)px/)?.[1]) / 2 || 0 : 0;
        const start = r.x + inset, stop = r.x + r.width - inset, over = Math.max(left - start, stop - end);
        lines.push({ selector: selector(el), left: start, right: stop, overhang: over });
        if (over > 1.01) add('INK EDGE', el, el.textContent, [r, box], { metric: 'list-hairline-overhang', value: over, referenceValue: 0, delta: over, otherSelector: selector(list), reason: 'List divider extends outside its content column' });
      }
      if (el !== list && el.matches('[role="row"],li,button,a') && !transparent(st.backgroundColor)) {
        const over = Math.max(left - r.x, r.x + r.width - end);
        fills.push({ selector: selector(el), left: r.x, right: r.x + r.width, overhang: over });
        if (over > 1.01) add('FILL INSET', el, el.textContent, [r, box], { metric: 'list-fill-overhang', value: over, referenceValue: 0, delta: over, otherSelector: selector(list), reason: 'Permanent row fill extends outside its content column' });
      }
    }
    listEdges.push({ selector: selector(list), name: list.getAttribute('data-list-edges'), left, right: end, lines, fills });
  }
  return { listEdges, sectionHeadings };
}
