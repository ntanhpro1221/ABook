// Quy tắc 10–11 độc lập: không đổi hình học hay tập ứng viên của quy tắc 1–9.
export function createLayoutHelpers() {
  function majority(samples, tolerance) {
    if (!samples.length) return null;
    const cluster = samples.map((sample) => samples.filter((s) => Math.abs(s.value - sample.value) <= tolerance + 0.01))
      .sort((a, b) => b.length - a.length)[0];
    // Không chọn một phía tuỳ tiện khi không có đa số tuyệt đối.
    if (cluster.length < 2 || cluster.length <= samples.length / 2) return null;
    const value = [...cluster].sort((a, b) => a.value - b.value)[Math.floor((cluster.length - 1) / 2)].value;
    return cluster.find((s) => s.value === value);
  }
  return { majority };
}

export function crossFrameRhythm(stories) {
  const groups = new Map(), findings = [];
  for (const story of stories) {
    const block = story.layout?.firstBlock;
    if (!block || story.error) continue;
    const key = JSON.stringify([story.platform, story.theme, story.group, block.family]);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push({ story, ...block, value: block.rect.y });
  }
  for (const samples of groups.values()) {
    const reference = createLayoutHelpers().majority(samples, 1);
    if (!reference) continue;
    for (const sample of samples) if (Math.abs(sample.value - reference.value) > 1.01) {
      findings.push({ rule: "RHYTHM", story: sample.story.id, theme: sample.story.theme,
        selector: sample.selector, context: sample.context, text: sample.text, crop: sample.crop,
        rects: [sample.rect], metric: "first-block-top", value: sample.value,
        referenceValue: reference.value, delta: sample.value - reference.value, tolerance: 1,
        referenceStory: reference.story.id, referenceSelector: reference.selector, referenceCrop: reference.crop,
        reason: "first content block differs from gallery group majority" });
    }
  }
  return findings;
}

// Nhúng vào trang bằng toString; các helper DOM được truyền từ inspector hiện tại.
export function inspectLayout({ all, texts, css, rect, union, visible, hidden, selector, add, shape, childPath }, h) {
  const { majority } = h;
  const canvas = document.createElement("canvas"), ctx = canvas.getContext("2d");
  const inkTexts = [], iconCache = new Map(), columns = [], gaps = [], rhythms = [];
  const right = (r) => r.x + r.width;
  const transparent = (value) => value === "transparent" || /rgba\([^)]*,\s*0\)$/.test(value);
  const controlSelector = 'button,a[href],[role="button"],[role="menuitem"],[role="option"]';
  const owner = (el) => el.closest(controlSelector);
  const branch = (el, parent) => { let p = el; while (p?.parentElement && p.parentElement !== parent) p = p.parentElement; return p; };
  const distinct = (samples) => samples.filter((s, i) => samples.findIndex((o) => o.node === s.node) === i);
  const segments = new Intl.Segmenter("vi", { granularity: "grapheme" });
  for (const run of distinct(texts)) {
    if (run.element.closest('svg,[aria-hidden="true"],[data-overlay]')) continue;
    const s = css(run.element);
    if (s.writingMode !== "horizontal-tb" || s.direction === "rtl") continue;
    const chars = [...segments.segment(run.node.textContent)].filter((c) => c.segment.trim());
    if (!chars.length) continue;
    ctx.font = `${s.fontStyle} ${s.fontWeight} ${s.fontSize} ${s.fontFamily}`;
    ctx.fontKerning = s.fontKerning;
    function glyph(c) {
      const range = document.createRange(); range.setStart(run.node, c.index); range.setEnd(run.node, c.index + c.segment.length);
      const r = range.getBoundingClientRect(), m = ctx.measureText(c.segment);
      const total = m.fontBoundingBoxAscent + m.fontBoundingBoxDescent;
      if (!(total > 0) || !(r.width > 0)) return null;
      const scale = r.height / total;
      return { x: r.x - m.actualBoundingBoxLeft * scale, y: r.y + (m.fontBoundingBoxAscent - m.actualBoundingBoxAscent) * scale,
        width: (m.actualBoundingBoxLeft + m.actualBoundingBoxRight) * scale,
        height: (m.actualBoundingBoxAscent + m.actualBoundingBoxDescent) * scale };
    }
    const first = glyph(chars[0]), last = glyph(chars.at(-1));
    if (!first || !last) continue;
    // Chỉ so cạnh phải khi chữ nằm trên một dòng; dòng cuối xuống hàng không phải mép cột.
    const singleLine = Math.abs(first.y - last.y) < Number.parseFloat(s.fontSize);
    inkTexts.push({ ...run, ink: union([first, last]), first, last, singleLine, control: owner(run.element) });
  }
  function iconInk(svg) {
    if (iconCache.has(svg)) return iconCache.get(svg);
    const pieces = [...svg.querySelectorAll("path,rect,circle,ellipse,line,polyline,polygon,use")].flatMap((p) => {
      if (hidden(p)) return [];
      const s = css(p), stroke = s.stroke !== "none" && Number(s.strokeOpacity) > 0 ? Number.parseFloat(s.strokeWidth) / 2 : 0;
      if (!stroke && (s.fill === "none" || Number(s.fillOpacity) === 0)) return [];
      try {
        const b = p.getBBox(), m = p.getScreenCTM();
        if (!m) return [];
        const nonScaling = s.vectorEffect === "non-scaling-stroke";
        const pad = nonScaling ? 0 : stroke;
        const points = [[b.x - pad, b.y - pad], [b.x + b.width + pad, b.y - pad], [b.x - pad, b.y + b.height + pad], [b.x + b.width + pad, b.y + b.height + pad]]
          .map(([x, y]) => ({ x: m.a * x + m.c * y + m.e, y: m.b * x + m.d * y + m.f, width: 0, height: 0 }));
        const box = union(points);
        if (nonScaling) { box.x -= stroke; box.y -= stroke; box.width += 2 * stroke; box.height += 2 * stroke; }
        return [visible(svg, box, true)].filter(Boolean);
      } catch { return []; }
    });
    const result = union(pieces); iconCache.set(svg, result); return result;
  }
  function controlInk(el) {
    const pieces = inkTexts.filter((t) => t.control === el).map((t) => t.ink);
    for (const svg of el.querySelectorAll("svg")) if (owner(svg) === el) pieces.push(iconInk(svg));
    return union(pieces.filter(Boolean));
  }
  function aligned(el, side, end) {
    for (let p = el; p && p !== end; p = p.parentElement) {
      const s = css(p);
      const intrinsicControl = p === el && owner(el) === el && el.getBoundingClientRect().width < (el.parentElement?.getBoundingClientRect().width ?? innerWidth) * 0.8;
      if (!intrinsicControl && (s.textAlign === "center" || /flex|grid/.test(s.display) && s.justifyContent === "center")) return false;
      if (side === "right" && (s.textAlign === "right" || s.justifyContent === "flex-end")) return true;
      const parent = p.parentElement;
      if (side === "right" && parent && p === parent.lastElementChild && parent.children.length > 1) {
        const ps = css(parent);
        if (/flex/.test(ps.display) && !ps.flexDirection.startsWith("column") && (ps.justifyContent === "space-between" || [...parent.children].some((c) => Number(css(c).flexGrow) > 0)) || /grid/.test(ps.display) && ps.gridTemplateColumns.split(" ").length > 1) return true;
      }
    }
    return side === "left";
  }
  // Cột = cùng flow/scroll scope, >=2 nhãn ở các nhánh dọc riêng, cạnh nét chữ tụ trong 1 px.
  for (const el of all.filter((e) => e.matches(controlSelector))) {
    const box = visible(el, rect(el.getBoundingClientRect())), s = css(el);
    if (!box || !transparent(s.backgroundColor) || Number.parseFloat(s.borderLeftWidth) > 0 && s.borderLeftStyle !== "none" || el.closest('nav,[role="tablist"],[role="menu"],[role="listbox"]')) continue;
    const ink = controlInk(el);
    if (!ink) continue;
    const foundSides = new Set();
    for (let parent = el.parentElement; parent && parent !== document.documentElement; parent = parent.parentElement) {
      const ps = css(parent), current = branch(el, parent), pb = rect(parent.getBoundingClientRect());
      if (!current || parent === document.body) break;
      if (/flex/.test(ps.display) && !ps.flexDirection.startsWith("column") || /grid/.test(ps.display) && ps.gridTemplateColumns.split(" ").length > 1) continue;
      for (const side of ["left", "right"]) {
        if (foundSides.has(side) || !aligned(el, side, current.parentElement)) continue;
        const refs = inkTexts.filter((t) => !t.control && parent.contains(t.element) && branch(t.element, parent) !== current && aligned(t.element, side, parent))
          .filter((t) => side === "left" || t.singleLine)
          .map((t) => ({ ...t, value: side === "left" ? t.first.x : right(t.last), branch: branch(t.element, parent) }));
        // Références du même bord de flow; ne pas comparer un bouton au milieu à une colonne voisine.
        const nearby = refs.filter((t) => Math.abs((side === "left" ? box.x : right(box)) - t.value) <= 21);
        const reference = majority(nearby, 1);
        if (!reference || new Set(nearby.filter((t) => Math.abs(t.value - reference.value) <= 1.01).map((t) => t.branch)).size < 2) continue;
        if (Math.abs((side === "left" ? box.x : right(box)) - reference.value) > 2 && (side === "left" ? Number.parseFloat(s.marginLeft) : Number.parseFloat(s.marginRight)) >= 0) continue;
        const value = side === "left" ? ink.x : right(ink), delta = value - reference.value;
        columns.push({ selector: selector(el), side, value, referenceValue: reference.value, delta });
        foundSides.add(side);
        if (Math.abs(delta) >= 1.99 && Math.abs(delta) <= 20.01) add("INK EDGE", el, el.textContent || el.getAttribute("aria-label") || "svg", [ink, reference.ink],
          { metric: `ink-${side}`, value, referenceValue: reference.value, delta, tolerance: 1, referenceSelector: selector(reference.element), listSelector: selector(parent), reason: "transparent control ink inset from text column" });
      }
      if (/auto|scroll/.test(ps.overflowY) || parent.matches('main,[role="dialog"],[role="menu"]') || pb.width > innerWidth || !transparent(ps.backgroundColor) || Number.parseFloat(ps.borderLeftWidth) > 0 && ps.borderLeftStyle !== "none") break;
    }
  }
  const isHeader = (el) => el.matches('header,footer,h1,h2,h3,h4,[role="heading"]');
  const role = (el) => el.matches(".settings-block") ? "settings-block" : el.matches('section,[role="region"]') ? "section" : el.matches('.settings-row,li,[role="listitem"],button,a,[role="menuitem"],[role="option"]') ? `row:${el.getAttribute("role") ?? el.localName}` : null;
  for (const parent of all) {
    const children = [...parent.children].filter((el) => visible(el, rect(el.getBoundingClientRect())) && !isHeader(el));
    const rows = new Map();
    for (const row of children) {
      if (!role(row)) continue;
      const key = shape(row);
      if (!rows.has(key)) rows.set(key, []);
      rows.get(key).push(row);
    }
    // Khoảng icon–chữ: cấu trúc giống nhau; cố ý KHÔNG gộp theo danh tính glyph.
    for (const siblings of rows.values()) {
      if (siblings.length < 3) continue;
      const boxes = siblings.map((row) => rect(row.getBoundingClientRect()));
      if (boxes.some((b, i) => i && b.y < boxes[i - 1].y + boxes[i - 1].height - 1)) continue;
      const slots = new Map();
      for (const row of siblings) for (const svg of row.querySelectorAll("svg")) {
        const icon = iconInk(svg);
        if (!icon || icon.width > 32 || icon.height > 32) continue;
        const next = inkTexts.filter((t) => row.contains(t.element) && t.first.x >= right(icon) - 1 && t.first.y < icon.y + icon.height + 4 && t.first.y + t.first.height > icon.y - 4)
          .sort((a, b) => a.first.x - b.first.x)[0];
        if (!next) continue;
        const key = `${childPath(svg, row)}:${childPath(next.element, row)}`;
        if (!slots.has(key)) slots.set(key, []);
        slots.get(key).push({ element: svg, row, value: next.first.x - right(icon), rect: union([icon, next.first]) });
      }
      for (const samples of slots.values()) {
        const reference = majority(samples, 1);
        if (!reference) continue;
        gaps.push({ selector: selector(parent), values: samples.map((s) => s.value) });
        for (const sample of samples) if (Math.abs(sample.value - reference.value) > 1.01) add("INK EDGE", sample.element, sample.row.textContent,
          [sample.rect, reference.rect], { metric: "ink-icon-text-gap", value: sample.value, referenceValue: reference.value, delta: sample.value - reference.value, tolerance: 1,
            listSelector: selector(parent), referenceSelector: selector(reference.element), reason: "icon to first glyph gap differs from sibling majority" });
      }
    }
    // Đo giữa các phần tử liên tiếp cùng vai; không nhảy qua vai khác/khối ẩn để tạo khoảng giả.
    const samples = [];
    for (let i = 1; i < children.length; i++) {
      const previous = children[i - 1], current = children[i], key = role(current);
      if (!key || role(previous) !== key) continue;
      const a = rect(previous.getBoundingClientRect()), b = rect(current.getBoundingClientRect());
      if (Math.abs(a.x - b.x) > 1 || Math.abs(a.width - b.width) > 1 || b.y < a.y + a.height - 1) continue;
      samples.push({ key, element: current, previous, value: b.y - a.y - a.height, rect: b, previousRect: a });
    }
    for (const key of new Set(samples.map((s) => s.key))) {
      const same = samples.filter((s) => s.key === key), reference = majority(same, 2);
      rhythms.push({ selector: selector(parent), role: key, values: same.map((s) => s.value) });
      if (!reference) continue;
      for (const sample of same) if (Math.abs(sample.value - reference.value) > 2.01) add("RHYTHM", sample.element, sample.element.textContent,
        [sample.previousRect, sample.rect], { metric: "vertical-gap", value: sample.value, referenceValue: reference.value, delta: sample.value - reference.value, tolerance: 2,
          listSelector: selector(parent), referenceSelector: selector(reference.element), previousSelector: selector(sample.previous), reason: "gap differs from same-role sibling majority" });
    }
  }
  // Khung có header trang + các section là cùng một họ nội dung. Dialog và trang đang cuộn không so với trang gốc.
  let firstBlock = null;
  if (!all.some((e) => e.matches('[role="dialog"],[role="alertdialog"]') && visible(e, rect(e.getBoundingClientRect())))) {
    const settings = document.querySelector(".settings-detail") ?? document.querySelector(".settings-page");
    const scope = settings ?? document.querySelector("main");
    const blocks = scope ? [...scope.querySelectorAll('.settings-block,main > section,[data-content-block]')].filter((el) => visible(el, rect(el.getBoundingClientRect()))) : [];
    const first = blocks[0];
    if (first && scope.scrollTop === 0 && !first.closest('[role="dialog"]')) {
      firstBlock = { family: settings ? "settings-block" : "section", selector: selector(first), rect: rect(first.getBoundingClientRect()), text: first.textContent.trim().slice(0, 160),
        context: [{ tag: first.localName, classes: [...first.classList], data: {} }] };
    }
  }
  return { columns, gaps, rhythms, firstBlock };
}
