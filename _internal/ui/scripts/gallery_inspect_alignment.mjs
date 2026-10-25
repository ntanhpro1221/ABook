// Quy tắc 12–13: chỉ đọc DOM, không chèn probe làm đổi layout đang đo.
export function inspectAlignment({ all, texts, css, rect, visible, selector, add }) {
  const ctx = document.createElement("canvas").getContext("2d");
  const right = (r) => r.x + r.width, bottom = (r) => r.y + r.height;
  const overlap = (a, b) => Math.min(bottom(a), bottom(b)) - Math.max(a.y, b.y);
  const clear = (value) => value === "transparent" || /rgba\([^)]*,\s*0\)$/.test(value);
  const painted = (el) => {
    const s = css(el);
    return !clear(s.backgroundColor) || s.backgroundImage !== "none" || ["Top", "Right", "Bottom", "Left"].some((side) =>
      Number.parseFloat(s[`border${side}Width`]) > 0 && !/none|hidden/.test(s[`border${side}Style`]) && !clear(s[`border${side}Color`]));
  };
  const branch = (el, parent) => { let p = el; while (p.parentElement && p.parentElement !== parent) p = p.parentElement; return p; };
  const common = (a, b) => { for (let p = a; p; p = p.parentElement) if (p.contains(b)) return p; };
  const row = (el) => /grid/.test(css(el).display) || /flex/.test(css(el).display) && !css(el).flexDirection.startsWith("column");
  const runs = [], seen = new Set();
  for (const run of texts) {
    if (seen.has(run.node) || run.element.closest('svg,[aria-hidden="true"],[data-overlay]')) continue;
    seen.add(run.node);
    const s = css(run.element), start = run.node.textContent.search(/\S/u);
    if (start < 0 || s.writingMode !== "horizontal-tb" || s.direction === "rtl") continue;
    const range = document.createRange(); range.setStart(run.node, start); range.setEnd(run.node, start + [...run.node.textContent.slice(start)][0].length);
    const line = rect(range.getBoundingClientRect());
    if (!visible(run.element, line)) continue;
    ctx.font = `${s.fontStyle} ${s.fontWeight} ${s.fontSize} ${s.fontFamily}`;
    const metrics = ctx.measureText(run.node.textContent.slice(start, start + 1));
    const total = metrics.fontBoundingBoxAscent + metrics.fontBoundingBoxDescent;
    if (!(total > 0 && line.height > 0)) continue;
    runs.push({ ...run, line, baseline: line.y + metrics.fontBoundingBoxAscent * line.height / total, fontSize: Number.parseFloat(s.fontSize) });
  }
  function centred(run, end) {
    for (let p = run.element; p && p !== end; p = p.parentElement) {
      if (p.matches('img,svg,[role="img"]')) return true;
      const s = css(p), box = rect(p.getBoundingClientRect());
      if (painted(p) && Math.abs(box.width - box.height) < 1 && box.width <= 64 && Number.parseFloat(s.borderRadius) >= box.width / 2) return true;
      // Badge/chip: nền riêng, cao một dòng. Không miễn cả hàng nhiều cột có nền.
      if (painted(p) && !p.matches('button,a,input,select,textarea') && box.height <= run.line.height + 12 && box.width <= run.original.width + 28) return true;
      // Chữ căn giữa trong điều khiển một dòng có hộp cố định có baseline độc lập.
      if (p.matches('button,[role="button"]') && (s.alignItems === "center" || s.textAlign === "center") &&
        texts.filter((r) => p.contains(r.element)).every((r) => overlap(r.original, run.line) >= Math.min(r.original.height, run.line.height) / 2)) return true;
    }
    return false;
  }
  const baselines = [], controls = [];
  const landmark = (el) => el.closest('main,aside,nav,footer,[role="dialog"],[role="alertdialog"],[role="menu"],[role="toolbar"]');
  for (let i = 0; i < runs.length; i++) for (let j = i + 1; j < runs.length; j++) {
    const a = runs[i], b = runs[j];
    if (a.element === b.element || landmark(a.element) !== landmark(b.element) || overlap(a.line, b.line) < Math.min(a.line.height, b.line.height) * 0.5 ||
      !(right(a.original) <= b.original.x + 1 || right(b.original) <= a.original.x + 1)) continue;
    const parent = common(a.element, b.element);
    if (!parent || parent === document.body || parent === document.documentElement) continue;
    if (row(parent)) {
      const ab = branch(a.element, parent), bb = branch(b.element, parent);
      if (ab === bb) continue;
      // Compare the first line of each column, never a coincident metadata line below it.
      if ([a, b].some((r) => runs.find((t) => branch(t.element, parent) === branch(r.element, parent) && parent.contains(t.element)) !== r)) continue;
    } else {
      // Inline label + following text, with no intervening block/independent column.
      const inline = (r) => { for (let p = r.element; p && p !== parent; p = p.parentElement) if (!css(p).display.startsWith("inline")) return false; return true; };
      if (!inline(a) || !inline(b) || /flex|grid/.test(css(parent).display)) continue;
    }
    if (centred(a, parent) || centred(b, parent)) continue;
    const delta = b.baseline - a.baseline;
    baselines.push({ selector: selector(a.element), otherSelector: selector(b.element), value: b.baseline, referenceValue: a.baseline, delta, fontSizes: [a.fontSize, b.fontSize] });
    if (Math.abs(delta) > 1.01) add("BASELINE", b.element, `${a.text} · ${b.text}`, [a.original, b.original],
      { ...baselines.at(-1), selector: selector(b.element), referenceSelector: selector(a.element), otherSelector: selector(a.element), metric: "alphabetic-baseline", tolerance: 1, reason: "side-by-side first text lines have different alphabetic baselines" });
  }
  const segmented = '[data-segmented],[role="radiogroup"]';
  const controlSelector = `input:not([type="checkbox"]):not([type="radio"]):not([type="range"]):not([type="hidden"]),select,textarea,button,[role="combobox"],${segmented}`;
  const segments = all.filter((el) => el.matches(segmented) && painted(el));
  const boxes = all.filter((el) => el.matches(controlSelector) && painted(el) &&
    !segments.some((group) => group !== el && group.contains(el))).flatMap((el) => {
    const box = rect(el.getBoundingClientRect());
    if (!visible(el, box) || el.matches("textarea") && el.rows !== 1) return [];
    return [{ el, box }];
  });
  for (const a of boxes) {
    const neighbours = boxes.filter((b) => b !== a && landmark(a.el) === landmark(b.el) && b.box.x >= right(a.box) - 1 && overlap(a.box, b.box) > 0 && !a.el.contains(b.el) && !b.el.contains(a.el) &&
      (() => { const parent = common(a.el, b.el); return parent && row(parent) && parent !== document.body && parent !== document.documentElement; })())
      .sort((b, c) => b.box.x - c.box.x);
    const b = neighbours[0];
    if (!b) continue;
    const parent = common(a.el, b.el);
    if (!parent || !row(parent) || parent === document.body || parent === document.documentElement) continue;
    const topDelta = b.box.y - a.box.y, bottomDelta = bottom(b.box) - bottom(a.box), delta = b.box.height - a.box.height;
    controls.push({ selector: selector(b.el), referenceSelector: selector(a.el), value: b.box.height, referenceValue: a.box.height, delta, topDelta, bottomDelta });
    if (Math.max(Math.abs(delta), Math.abs(topDelta), Math.abs(bottomDelta)) > 1.01) add("CONTROL HEIGHT", b.el,
      `${a.el.getAttribute("aria-label") ?? a.el.textContent} · ${b.el.getAttribute("aria-label") ?? b.el.textContent}`, [a.box, b.box],
      { ...controls.at(-1), metric: "visible-control-height", tolerance: 1, reason: "adjacent painted controls differ in height or top/bottom alignment" });
  }
  // Menu/popover: các hàng cùng vai phải cao đều dù cấu trúc DOM khác nhau.
  for (const surface of all.filter((el) => el.matches('[role="menu"],[data-radix-popper-content-wrapper] > [role="dialog"]'))) {
    const rows = [...surface.querySelectorAll('[role="menuitem"],[role="option"],[data-player-menu-row]')]
      .filter((el) => visible(el, rect(el.getBoundingClientRect())) && !el.parentElement.closest('[data-player-menu-row]'));
    const groups = new Map();
    for (const el of rows) {
      // Dòng có nhãn + lời giải thích tự cao theo số dòng thực; không ép nó bằng hàng một dòng hay một lời giải thích ngắn hơn.
      if (el.querySelector('span.block + span.block')) continue;
      const key = el.hasAttribute("data-player-menu-row") ? "player-row" : el.getAttribute("role");
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push({ el, box: rect(el.getBoundingClientRect()) });
    }
    for (const group of groups.values()) {
      if (group.length < 2) continue;
      const reference = group.map((r) => ({ ...r, votes: group.filter((o) => Math.abs(o.box.height - r.box.height) <= 1.01).length }))
        .sort((a, b) => b.votes - a.votes)[0];
      for (const r of group) if (Math.abs(r.box.height - reference.box.height) > 1.01) add("CONTROL HEIGHT", r.el, r.el.textContent,
        [r.box, reference.box], { metric: "menu-row-height", value: r.box.height, referenceValue: reference.box.height, delta: r.box.height - reference.box.height,
          tolerance: 1, referenceSelector: selector(reference.el), reason: "same-role rows in one menu differ in visible height" });
    }
  }
  return { baselines, controls };
}
