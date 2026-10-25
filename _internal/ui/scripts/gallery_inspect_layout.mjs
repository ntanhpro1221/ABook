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
    let first = glyph(chars[0]), last = glyph(chars.at(-1));
    if (!first || !last) continue;
    // Số tabular thẳng cột theo ô chữ số chứ không theo mực ("1" có lề trái rộng hơn "2"): đo mép bằng ô.
    if (/tabular-nums/.test(s.fontVariantNumeric) && /^[\d\s:.,×%/−+–-]+$/.test(run.node.textContent.trim())) {
      const range = document.createRange(); range.selectNodeContents(run.node);
      const box = range.getBoundingClientRect();
      first = { ...first, x: box.x, width: first.x + first.width - box.x };
      last = { ...last, width: box.right - last.x };
    }
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
        // Mốc cùng cạnh của flow; không so nút ở giữa với cột bên cạnh.
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
  // Một mặt nổi là cột độc lập. Đầu đề đặt mốc trái, nút đóng đặt mốc phải;
  // body chỉ lấy cạnh ngoài của hàng, không lấy chữ nằm sau icon hay trong ô nhập.
  const edgeSeen = new Set();
  function edge(el, ink, side, value, reference, scope, metric = `surface-ink-${side}`) {
    if (!ink || !reference) return;
    const actual = side === "left" ? ink.x : right(ink), delta = actual - value;
    columns.push({ selector: selector(el), side, value: actual, referenceValue: value, delta, metric });
    const key = `${selector(el)}:${side}`;
    if (edgeSeen.has(key) || Math.abs(delta) < (metric === "panel-tab-left" || metric.startsWith("player-column-") ? 1.01 : 1.99) || Math.abs(delta) > 22.01) return;
    edgeSeen.add(key);
    add("INK EDGE", el, el.textContent || el.getAttribute("aria-label") || "svg", [ink, reference],
      { metric, value: actual, referenceValue: value, delta, tolerance: 1, listSelector: selector(scope), reason: "ink differs from the surface content column" });
  }
  function leading(el) {
    const pieces = inkTexts.filter((t) => el.contains(t.element)).map((t) => visible(t.element, t.ink, true)).filter(Boolean);
    for (const svg of el.querySelectorAll("svg")) { const ink = iconInk(svg); if (ink) pieces.push(ink); }
    return union(pieces);
  }
  const surfaces = all.filter((el) => el.matches('[role="dialog"],.sheet-surface') && visible(el, rect(el.getBoundingClientRect())));
  for (const surface of surfaces) {
    const title = inkTexts.find((t) => surface.contains(t.element) && t.element.closest('h1,h2,[role="heading"]'));
    const body = surface.querySelector(".sheet-body") ?? surface;
    if (!title || !body) continue;
    const close = surface.querySelector('[data-sheet-grip] button,button[aria-label="Đóng"]'), closeInk = close && controlInk(close);
    const left = title.first.x, end = closeInk ? right(closeInk) : right(rect(surface.getBoundingClientRect())) - (left - surface.getBoundingClientRect().x);
    const insetSurface = (el) => {
      for (let p = el.parentElement; p && p !== body; p = p.parentElement) {
        const s = css(p);
        if (Number.parseFloat(s.borderLeftWidth) > 0 && s.borderLeftStyle !== "none") return true;
      }
      return false;
    };
    const candidates = [...body.querySelectorAll(controlSelector)].filter((el) => !el.parentElement.closest(controlSelector) && !el.matches('[role="menuitem"],[data-player-menu-row]'));
    for (const el of candidates) {
      const box = visible(el, rect(el.getBoundingClientRect()));
      if (!box || insetSurface(el) || Number.parseFloat(css(el).borderLeftWidth) > 0 && css(el).borderLeftStyle !== "none" ||
        !transparent(css(el).backgroundColor) && !el.hasAttribute("data-current-choice")) continue;
      const ink = controlInk(el);
      if (!ink) continue;
      if (Math.abs(box.x - left) < 23) edge(el, ink, "left", left, title.first, surface);
      if (closeInk && Math.abs(right(box) - end) < 23 && box.width < body.clientWidth / 2) edge(el, ink, "right", end, closeInk, surface);
    }
    for (const t of inkTexts.filter((t) => body.contains(t.element) && !t.control && t.singleLine && Math.abs(t.first.x - left) < 23)) {
      if (t.element.closest('input,textarea,[role="tablist"]') || insetSurface(t.element) || !aligned(t.element, "left", body) ||
        inkTexts.some((o) => o !== t && o.element === t.element && o.first.x < t.first.x - 1 && Math.abs(o.first.y - t.first.y) < 2)) continue;
      let followsIcon = false;
      for (let p = t.element; p && p !== body; p = p.parentElement) {
        if (/flex/.test(css(p).display) && !css(p).flexDirection.startsWith("column")) for (const svg of p.querySelectorAll("svg")) {
          const b = iconInk(svg);
          if (b && b.x < t.first.x && right(b) > t.first.x - 24 && Math.abs(b.y - t.first.y) < 16) followsIcon = true;
        }
      }
      if (followsIcon) continue;
      let badge = false;
      for (let p = t.element; p && p !== body; p = p.parentElement) if (!transparent(css(p).backgroundColor) && p.getBoundingClientRect().height < t.original.height + 16) badge = true;
      if (badge) continue;
      edge(t.element, t.first, "left", left, title.first, surface);
    }
  }
  // Icon cuối hàng bấm được: đo riêng mực glyph, không gộp với nhãn.
  for (const svg of all.filter((el) => el.matches("svg") && owner(el))) {
    const el = owner(svg), box = rect(el.getBoundingClientRect()), ink = iconInk(svg);
    if (!ink || svg !== el.lastElementChild || !/flex|grid/.test(css(el).display) || box.width < 100 || el.closest('[role="tablist"],[role="menu"],[role="listbox"]')) continue;
    if (Number.parseFloat(css(el).borderRightWidth) > 0 && css(el).borderRightStyle !== "none") continue;
    const s = css(el), end = right(box) - Number.parseFloat(s.paddingRight) - Number.parseFloat(s.borderRightWidth);
    if (Math.abs(right(svg.getBoundingClientRect()) - end) <= 6) edge(svg, ink, "right", end, rect(el.getBoundingClientRect()), el, "trailing-icon-right");
  }
  // Nút cuối đầu trang và icon điều hướng cùng dùng cạnh nội dung làm mốc.
  for (const el of all.filter((e) => e.matches("main button,main a") && e.querySelector("svg"))) {
    const box = visible(el, rect(el.getBoundingClientRect())), ink = controlInk(el);
    if (!box || !ink || box.width > 64 || inkTexts.some((t) => el.contains(t.element))) continue;
    for (let parent = el.parentElement; parent && parent !== el.closest("main"); parent = parent.parentElement) {
      const s = css(parent), b = rect(parent.getBoundingClientRect());
      if (b.width < 300 || !parent.querySelector("h1") || !/flex|grid/.test(s.display) || s.flexDirection.startsWith("column")) continue;
      const heading = parent.querySelector("h1").getBoundingClientRect();
      if (Math.min(heading.bottom, box.y + box.height) <= Math.max(heading.y, box.y)) continue;
      const end = right(b) - Number.parseFloat(s.paddingRight) - Number.parseFloat(s.borderRightWidth);
      if (Math.abs(right(box) - end) < 24) edge(el, ink, "right", end, b, parent, "heading-control-right");
      break;
    }
  }
  for (const aside of all.filter((el) => el.matches("aside") && el.querySelector('nav'))) {
    const logo = aside.firstElementChild?.querySelector('img,[class~="bg-accent"]'), box = logo && visible(logo, rect(logo.getBoundingClientRect()));
    if (!box) continue;
    for (const svg of aside.querySelectorAll('a > svg')) edge(svg, iconInk(svg), "left", box.x, box, aside, "navigation-icon-left");
  }
  // Cột trình phát theo lề trong của aside, kể cả khi chỉ có một dòng chữ.
  for (const aside of all.filter((el) => el.matches('.now-playing > aside'))) {
    const raw = rect(aside.getBoundingClientRect()), s = css(aside);
    const box = { x: raw.x + Number.parseFloat(s.paddingLeft), y: raw.y, width: raw.width - Number.parseFloat(s.paddingLeft) - Number.parseFloat(s.paddingRight) - Number.parseFloat(s.borderRightWidth), height: raw.height };
    if (!box) continue;
    const controls = [...aside.querySelectorAll("button")].filter((el) => !el.closest('[role="dialog"],[role="menu"]'));
    for (const el of controls) {
      const b = rect(el.getBoundingClientRect()), ink = controlInk(el);
      if (!ink || b.width > box.width / 2) continue;
      for (const side of ["left", "right"]) if (Math.abs((side === "left" ? b.x : right(b)) - (side === "left" ? box.x : right(box))) < 23)
        edge(el, ink, side, side === "left" ? box.x : right(box), box, aside, `player-column-${side}`);
    }
  }
  // Tab và nội dung panel chung cạnh nội dung của tab đầu.
  for (const tabs of all.filter((el) => el.matches('.now-playing [role="tablist"]'))) {
    const tab = tabs.querySelector('[role="tab"]'), icon = tab?.querySelector("svg");
    if (!tab || !icon || !visible(tab, rect(tab.getBoundingClientRect()))) continue;
    const box = rect(tab.getBoundingClientRect()), value = box.x + Number.parseFloat(css(tab).paddingLeft);
    edge(icon, iconInk(icon), "left", value, box, tabs, "panel-tab-left");
    const container = tabs.parentElement.parentElement;
    const reading = container.querySelector('.reading-surface > div'), panel = container.querySelector('[role="tabpanel"]');
    if (reading && visible(reading, rect(reading.getBoundingClientRect()))) edge(reading, rect(reading.getBoundingClientRect()), "left", value, box, container, "panel-content-left");
    if (panel) for (const row of panel.querySelectorAll('button[data-current]')) {
      const b = rect(row.getBoundingClientRect());
      if (visible(row, b)) edge(row, leading(row), "left", value, box, container, "panel-row-left");
    }
  }
  // Ghi chú và hàng lựa chọn của popover dùng cạnh đệm chung; ô dành cho dấu chọn vẫn chiếm chỗ khi ẩn.
  for (const surface of surfaces.filter((el) => !el.matches('.sheet-surface') && el.parentElement.matches('[data-radix-popper-content-wrapper]'))) {
    const sb = rect(surface.getBoundingClientRect());
    const choices = [...surface.querySelectorAll('button[aria-pressed],button[data-current-choice]')].filter((el) => css(el).textAlign === "left" && el.getBoundingClientRect().width > sb.width * 0.6);
    const samples = choices.map((el) => ({ element: el, first: rect(el.getBoundingClientRect()), value: el.getBoundingClientRect().x + Number.parseFloat(css(el).paddingLeft) }));
    const reference = majority(samples, 1);
    if (reference) for (const t of inkTexts.filter((t) => surface.contains(t.element) && !t.control && Math.abs(t.first.x - reference.value) < 22))
      edge(t.element, t.first, "left", reference.value, reference.first, surface, "popover-note-left");
    // Điều khiển bên phải hàng menu chung cạnh với giá trị chữ.
    const rows = [...surface.querySelectorAll('[data-player-menu-row]')];
    const values = rows.flatMap((row) => {
      const t = inkTexts.filter((t) => row.contains(t.element)).at(-1);
      const end = right(row.getBoundingClientRect()) - Number.parseFloat(css(row).paddingRight);
      return t && t.singleLine && t.element.closest('span') && Math.abs(right(t.last) - end) < 2 ? [{ ...t, value: right(t.last) }] : [];
    });
    // Một giá trị vẫn đủ làm mốc khi đã sát cạnh đệm của hàng.
    const end = majority(values, 1) ?? (values.length === 1 ? values[0] : null);
    if (end) for (const slot of rows.filter((row) => row.querySelector('button') && !row.matches('button'))) {
      const buttons = [...slot.querySelectorAll('button')], last = buttons.at(-1);
      if (last) edge(last, controlInk(last), "right", end.value, end.last, surface, "popover-control-right");
    }
  }
  // Đệm trong nền riêng: đo mực nhìn thấy của thẻ, nhãn và lựa chọn; không đo nền mặt chứa/ô nhập.
  const fills = [];
  const surfaceColor = (el) => { for (let p = el; p; p = p.parentElement) if (!transparent(css(p).backgroundColor)) return css(p).backgroundColor; return "rgba(0, 0, 0, 0)"; };
  for (const el of all) {
    const s = css(el), box = visible(el, rect(el.getBoundingClientRect()));
    if (!box || transparent(s.backgroundColor) || s.backgroundColor === surfaceColor(el.parentElement) ||
      el.matches('svg,svg *,input,textarea,select,option,main,aside,header,footer,[role="dialog"],[role="menu"],[role="listbox"],.sheet-surface') ||
      el.querySelector('img,canvas') || el.closest('[data-overlay]')) continue;
    // Tô từ trong câu văn liên tục không tạo một hộp nội dung riêng.
    if (s.display === "inline" && el.parentElement?.closest('p,[data-sentence]')) continue;
    const ownTexts = inkTexts.filter((t) => el.contains(t.element) && !t.element.closest('svg'));
    if (!ownTexts.length || box.height > 150) continue;
    const ink = leading(el);
    if (!ink) continue;
    for (const side of ["left", "right"]) {
      const value = side === "left" ? ink.x - box.x : right(box) - right(ink);
      fills.push({ selector: selector(el), side, value });
      if (value < 5.99) add("FILL INSET", el, el.textContent, [box, ink], { metric: `fill-inset-${side}`, value, referenceValue: 6, delta: value - 6, tolerance: 0, reason: "ink has less than 6 px inset inside its visible fill" });
    }
    const parent = el.parentElement;
    if (!parent || !el.matches('[aria-pressed="true"],[aria-selected="true"],[data-current-choice]') || !/flex/.test(css(parent).display) || css(parent).flexDirection.startsWith("column") || css(parent).flexWrap === "wrap") continue;
    const siblings = [...parent.children].filter((c) => c !== el && c.matches(controlSelector) && !c.matches('[aria-pressed],[aria-selected],[role="radio"],[role="tab"]') && visible(c, rect(c.getBoundingClientRect())));
    const last = siblings.sort((a, b) => right(b.getBoundingClientRect()) - right(a.getBoundingClientRect()))[0];
    if (last && right(last.getBoundingClientRect()) - right(box) > 8.01) add("FILL INSET", el, parent.textContent, [box, rect(last.getBoundingClientRect())],
      { metric: "selection-fill-end", value: right(box), referenceValue: right(last.getBoundingClientRect()), delta: right(box) - right(last.getBoundingClientRect()), tolerance: 8, otherSelector: selector(last), reason: "selection fill stops before the last control of its row" });
  }
  const isHeader = (el) => el.matches('header,footer,h1,h2,h3,h4,[role="heading"]');
  // Khối gập nối khối gập là một hàng của dãy gập (vạch chia 1px, sát nhau - styles.css), không phải phần mới.
  const role = (el) => el.matches(".settings-block[data-fold] + .settings-block[data-fold]") ? "settings-fold-run" : el.matches(".settings-block") ? "settings-block" : el.matches('section,[role="region"]') ? "section" : el.matches('.settings-row,li,[role="listitem"],button,a,[role="menuitem"],[role="option"]') ? `row:${el.getAttribute("role") ?? el.localName}` : null;
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
    // Hàng nút chữ trơn (bộ lọc, tab chữ) xếp bằng gap: khoảng giữa nét chữ liền nhau phải đều. Hộp chạm tối thiểu căn giữa chữ ngắn làm
    // khoảng nhìn thấy lệch (Thư viện "Tất cả · Nghe dở · Chưa nghe · Xong", 25-10). Tab chia đều bề ngang thì khoảng theo độ dài chữ - bỏ qua.
    const flow = css(parent);
    const words = children.filter((el) => el.matches(controlSelector) && !el.querySelector("svg") && inkTexts.some((t) => t.control === el && t.singleLine));
    if (words.length >= 3 && /flex/.test(flow.display) && !flow.flexDirection.startsWith("column") && !/space-|stretch/.test(flow.justifyContent)) {
      const boxes = words.map((el) => rect(el.getBoundingClientRect()));
      const sameLine = boxes.every((b, i) => !i || (b.x >= right(boxes[i - 1]) - 1 && Math.min(b.y + b.height, boxes[i - 1].y + boxes[i - 1].height) - Math.max(b.y, boxes[i - 1].y) > b.height / 2));
      const equalWidths = boxes.every((b) => Math.abs(b.width - boxes[0].width) <= 1);
      if (sameLine && !equalWidths) {
        const inks = words.map(controlInk);
        const spans = inks.slice(1).map((ink, i) => ({ element: words[i + 1], previous: words[i], value: ink.x - right(inks[i]), rect: ink, previousRect: inks[i] }));
        const sorted = spans.map((s) => s.value).sort((a, b) => a - b), median = sorted[Math.floor((sorted.length - 1) / 2)];
        const worst = [...spans].sort((a, b) => Math.abs(b.value - median) - Math.abs(a.value - median))[0];
        rhythms.push({ selector: selector(parent), role: "word-row", values: spans.map((s) => s.value) });
        if (sorted.at(-1) - sorted[0] > 2.01) add("RHYTHM", worst.element, parent.textContent, [worst.previousRect, worst.rect],
          { metric: "horizontal-ink-gap", value: worst.value, referenceValue: median, delta: worst.value - median, tolerance: 2, values: spans.map((s) => s.value),
            listSelector: selector(parent), previousSelector: selector(worst.previous), reason: "visible gaps between text controls in one row differ" });
      }
    }
  }
  // Nhãn inline + câu: so nét cuối nhãn với glyph đầu câu (kể cả dấu “), không so hộp span.
  const inlineSlots = new Map();
  for (let i = 1; i < inkTexts.length; i++) {
    const label = inkTexts[i - 1], next = inkTexts[i];
    if (label.element === next.element || !label.element.matches("span,b,strong,label") || !css(label.element).display.startsWith("inline") || label.element.contains(next.element)) continue;
    const between = document.createRange(); between.setStart(label.node, label.node.length); between.setEnd(next.node, 0);
    const overlap = Math.min(label.original.y + label.original.height, next.original.y + next.original.height) - Math.max(label.original.y, next.original.y);
    if (between.toString().trim() || !label.singleLine || overlap < Math.min(label.original.height, next.original.height) / 2 || next.first.x < right(label.last)) continue;
    let scope = label.element.parentElement;
    while (scope && !scope.contains(next.element)) scope = scope.parentElement;
    if (!scope || /flex|grid/.test(css(scope).display)) continue;
    const inlineBranch = (el) => { for (let p = el; p && p !== scope; p = p.parentElement) if (!css(p).display.startsWith("inline")) return false; return true; };
    if (!inlineBranch(label.element) || !inlineBranch(next.element)) continue;
    // Cùng đường cấu trúc trong một component, kể cả nhãn ở các paragraph khác nhau.
    const family = selector(scope).replace(/:nth-of-type\(\d+\)/g, "");
    const key = `${family}:${childPath(label.element, scope)}:${childPath(next.element, scope)}:${css(label.element).fontSize}:${css(next.element).fontSize}`;
    if (!inlineSlots.has(key)) inlineSlots.set(key, []);
    inlineSlots.get(key).push({ element: label.element, scope, value: next.first.x - right(label.last), rect: union([label.last, next.first]), next: next.element });
  }
  for (const samples of inlineSlots.values()) {
    if (samples.length < 3) continue;
    const reference = majority(samples, 1);
    if (!reference) continue;
    gaps.push({ selector: selector(reference.scope), metric: "ink-inline-text-gap", values: samples.map((s) => s.value) });
    for (const sample of samples) if (Math.abs(sample.value - reference.value) > 1.01) add("INK EDGE", sample.element, sample.scope.textContent,
      [sample.rect, reference.rect], { metric: "ink-inline-text-gap", value: sample.value, referenceValue: reference.value, delta: sample.value - reference.value, tolerance: 1,
        listSelector: selector(sample.scope), otherSelector: selector(sample.next), referenceSelector: selector(reference.element), reason: "label to first glyph gap differs from repeated inline majority" });
    // Một mốc giữa có thể nằm trong ±1 px của cả hai đầu dù hai đầu lệch >1 px.
    const sorted = [...samples].sort((a, b) => a.value - b.value), low = sorted[0], high = sorted.at(-1);
    if (high.value - low.value > 1.01 && samples.every((s) => Math.abs(s.value - reference.value) <= 1.01)) add("INK EDGE", high.element, high.scope.textContent,
      [high.rect, low.rect], { metric: "ink-inline-text-gap", value: high.value, referenceValue: low.value, delta: high.value - low.value, tolerance: 1,
        listSelector: selector(high.scope), otherSelector: selector(high.next), referenceSelector: selector(low.element), reason: "repeated inline ink gaps span more than 1 px" });
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
  return { columns, gaps, rhythms, fills, firstBlock };
}
