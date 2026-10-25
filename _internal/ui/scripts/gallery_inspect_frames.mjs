// Hộp thoại đã là mặt nổi; nhóm bên trong dùng khoảng trắng thay khung (DESIGN 4–6).
export function inspectFrames({ all, css, rect, visible, selector, add }) {
  const transparent = value => value === "transparent" || /rgba\([^)]*,\s*0\)$/.test(value);
  // Cùng token cho tiêu đề mục đứng riêng / gập mở, ở mọi frame (kể cả người dùng phóng chữ).
  const rem = Number.parseFloat(css(document.documentElement).fontSize);
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
      const range = document.createRange(); range.selectNodeContents(title);
      const lines = new Set([...range.getClientRects()].filter(r => r.width > 0 && r.height > 0).map(r => Math.round(r.y)));
      if (lines.size > 1 || el.querySelector('[data-description]')?.textContent?.trim()) add('LINE BREAK', title, title.textContent, [rect(title.getBoundingClientRect())],
        { metric: 'toast-lines', value: lines.size, referenceValue: 1, delta: lines.size - 1, reason: 'Toast feedback uses one short line; details open on request' });
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
