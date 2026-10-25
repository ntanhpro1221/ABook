// Hộp thoại đã là mặt nổi; nhóm bên trong dùng khoảng trắng thay khung (DESIGN 4–6).
export function inspectFrames({ all, css, rect, visible, selector, add }) {
  const transparent = value => value === "transparent" || /rgba\([^)]*,\s*0\)$/.test(value);
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
  return { listEdges };
}
