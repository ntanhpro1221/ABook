// Quy tắc 16–17: đo hình học, không đổi tiêu điểm hay vị trí cuộn khi soi.
export function inspectEdges({ all, css, rect, hidden, selector, add }) {
  // styles.css :focus-visible: outline 2 px + offset 2 px.
  const ring = 4, tolerance = 0.5;
  const shown = (el) => !hidden(el) && !el.closest('[inert],.motion-snapshot') && el.getBoundingClientRect().width > 0 && el.getBoundingClientRect().height > 0;
  const label = (el) => el.getAttribute('aria-label') || el.textContent || el.localName;
  const paddingBox = (el) => {
    const b = el.getBoundingClientRect(), s = css(el);
    // clientWidth/Height làm tròn số nguyên: tab có border 1 px và chiều cao nửa px sẽ bị nhận nhầm là nằm trọn bên trong.
    return { left: b.left + Number.parseFloat(s.borderLeftWidth), top: b.top + Number.parseFloat(s.borderTopWidth),
      right: b.right - Number.parseFloat(s.borderRightWidth), bottom: b.bottom - Number.parseFloat(s.borderBottomWidth) };
  };
  for (const el of all) {
    if (!el.matches('button,a[href],input:not([type="hidden"]),select,textarea,[tabindex],[role="radio"],[role="tab"],[role="switch"]') || !shown(el)
      || el.matches(':disabled') || el.hasAttribute('tabindex') && el.tabIndex < 0 && !el.matches('button,a[href],input,select,textarea,[role="radio"],[role="tab"],[role="switch"]')) continue;
    const r = el.getBoundingClientRect();
    for (let a = el.parentElement; a && a !== document.body; a = a.parentElement) {
      const s = css(a), p = paddingBox(a);
      if (s.overflowX === 'visible' && s.overflowY === 'visible') continue;
      const inside = r.left >= p.left - tolerance && r.right <= p.right + tolerance && r.top >= p.top - tolerance && r.bottom <= p.bottom + tolerance;
      // Không quy lỗi vòng cho hàng đang nằm ngoài cửa sổ cuộn.
      if (!inside) { if (/auto|scroll/.test(s.overflowX + s.overflowY)) break; continue; }
      const margin = Number.parseFloat(s.overflowClipMargin.match(/[\d.]+px/)?.[0]) || 0;
      const cut = [];
      for (const [axis, low, high] of [['X', 'left', 'right'], ['Y', 'top', 'bottom']]) {
        const overflow = s[`overflow${axis}`];
        // Clip-margin có thể tính từ border-box/content-box; scroll/hidden không dùng nó.
        const edgeExtra = (edge) => overflow !== 'clip' ? 0 : margin
          + (s.overflowClipMargin.includes('border-box') ? Number.parseFloat(s[`border${edge[0].toUpperCase() + edge.slice(1)}Width`]) : 0)
          - (s.overflowClipMargin.includes('content-box') ? Number.parseFloat(s[`padding${edge[0].toUpperCase() + edge.slice(1)}`]) : 0);
        if (overflow === 'visible') continue;
        // Mép khung cuộn mà phía ấy còn nội dung cuộn tới: hàng đang lấp ló ở mép cuộn, không phải vòng bị cắt (soát 140 V3: "Đọc theo" sát đáy
        // trình phát co lại sau bảng hẹn giờ). Tab tới thì scroll-padding của khung cuộn chừa chỗ cho vòng.
        const scrollable = /auto|scroll/.test(overflow);
        const pos = axis === 'X' ? a.scrollLeft : a.scrollTop, room = axis === 'X' ? a.scrollWidth - a.clientWidth : a.scrollHeight - a.clientHeight;
        if (r[low] - ring < p[low] - edgeExtra(low) - tolerance && !(scrollable && pos > 0.5)) cut.push(low);
        if (r[high] + ring > p[high] + edgeExtra(high) + tolerance && !(scrollable && room - pos > 0.5)) cut.push(high);
      }
      if (cut.length) {
        add('FOCUS RING CLIPPED', el, label(el), [rect(r)], { ring, cut, otherSelector: selector(a), overflow: `${s.overflowX}/${s.overflowY}`, reason: 'Vòng tiêu điểm vượt mép cắt của tổ tiên', clipClasses: [...a.classList] });
        break;
      }
    }
  }
  const corners = ['TopLeft', 'TopRight', 'BottomRight', 'BottomLeft'];
  const radii = (el) => {
    const b = el.getBoundingClientRect(), s = css(el);
    const values = corners.map((corner) => {
      const parts = s[`border${corner}Radius`].split(/\s+/);
      const length = (v, size) => Number.parseFloat(v) * (v.endsWith('%') ? size / 100 : 1);
      return [length(parts[0], b.width), length(parts[1] ?? parts[0], b.height)];
    });
    // CSS Backgrounds: một hệ số chung cho cả tám bán kính, kể cả góc elip.
    const f = Math.min(1, b.width / (values[0][0] + values[1][0]), b.width / (values[3][0] + values[2][0]),
      b.height / (values[0][1] + values[3][1]), b.height / (values[1][1] + values[2][1]));
    return values.map((v) => v.map((n) => n * f));
  };
  const filled = (el) => {
    const s = css(el), color = s.backgroundColor;
    return s.backgroundImage !== 'none' || color !== 'transparent' && !/rgba\([^)]*,\s*0\)|\/\s*0\)/.test(color);
  };
  const point = (b, i) => [i === 0 || i === 3 ? b.left : b.right, i < 2 ? b.top : b.bottom];
  for (const el of all) {
    if (css(el).position !== 'absolute' || !shown(el) || !filled(el)) continue;
    const b = el.getBoundingClientRect(), own = radii(el), candidates = [];
    for (let p = el; p && p !== document.body; p = p.parentElement) {
      if (p !== el) candidates.push(p);
      for (let s = p.previousElementSibling; s; s = s.previousElementSibling) candidates.push(s);
    }
    for (const box of candidates) {
      if (!shown(box)) continue;
      const ref = box.getBoundingClientRect(), used = radii(box);
      if (b.left < ref.left - 1 || b.right > ref.right + 1 || b.top < ref.top - 1 || b.bottom > ref.bottom + 1) continue;
      for (let i = 0; i < 4; i++) {
        const a = point(b, i), c = point(ref, i);
        if (Math.abs(a[0] - c[0]) > 1 || Math.abs(a[1] - c[1]) > 1 || !used[i].some((n, axis) => n - own[i][axis] > 1)) continue;
        let clipped = false;
        for (let p = el.parentElement; p; p = p.parentElement) {
          const s = css(p), pr = p.getBoundingClientRect(), pc = point(pr, i), radius = radii(p)[i];
          if (s.overflowX !== 'visible' && s.overflowY !== 'visible' && Math.abs(pc[0] - c[0]) <= 1 && Math.abs(pc[1] - c[1]) <= 1
            && radius.every((n, axis) => n >= used[i][axis] - 1)) { clipped = true; break; }
          if (p === box || p === box.parentElement) break;
        }
        if (!clipped) add('CORNER MISMATCH', el, label(el), [rect(b), rect(ref)], { corner: corners[i], usedRadius: own[i], referenceRadius: used[i], otherSelector: selector(box), reason: 'Lớp phủ không theo góc bo đã dùng của hộp' });
      }
      // Một lớp phủ chỉ cần một hộp tham chiếu trùng góc.
      if (used.some((v) => v.some((n) => n > 1)) && corners.some((_, i) => point(b, i).every((n, axis) => Math.abs(n - point(ref, i)[axis]) <= 1))) break;
    }
  }
  return {};
}
