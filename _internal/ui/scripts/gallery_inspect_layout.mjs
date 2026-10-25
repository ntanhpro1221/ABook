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

// Chân chữ tiêu đề màn giữa mọi khung cùng nền tảng và theme (không theo nhóm gallery: Thư viện, Studio, Cài đặt, màn con đều chung một đầu màn
// - shared/ScreenHeader). Không có đa số tuyệt đối thì lấy trung vị làm mốc: hai màn gốc lệch nhau vẫn bị bắt, không im lặng vì hoà.
export function crossFrameTitles(stories) {
  const groups = new Map(), findings = [];
  for (const story of stories) {
    const title = story.layout?.screenTitle;
    if (!title || story.error) continue;
    const key = JSON.stringify([story.platform, story.theme]);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push({ story, ...title, value: title.baseline });
  }
  for (const samples of groups.values()) {
    if (samples.length < 2) continue;
    const sorted = [...samples].sort((a, b) => a.value - b.value);
    const reference = createLayoutHelpers().majority(samples, 1) ?? sorted[Math.floor((sorted.length - 1) / 2)];
    for (const sample of samples) if (Math.abs(sample.value - reference.value) > 1.01) {
      findings.push({ rule: "RHYTHM", story: sample.story.id, theme: sample.story.theme,
        selector: sample.selector, context: sample.context, text: sample.text, crop: sample.crop,
        rects: [sample.rect], metric: "screen-title-baseline", value: sample.value,
        referenceValue: reference.value, delta: sample.value - reference.value, tolerance: 1,
        referenceStory: reference.story.id, referenceSelector: reference.selector, referenceCrop: reference.crop,
        reason: "screen title baseline differs from other screens on the same platform" });
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
    let partial = false;
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
        const shown = visible(svg, box, true);
        // Nét bị mép cuộn / lớp phủ cắt mất (một phần hay cả nét): hộp mực còn lại không phải hình của icon - đo nó thì khoảng icon-chữ sai (hàng chương lấp ló
        // dưới thanh phát, soát 140). Cả icon không đo được.
        if (!shown || Math.abs(shown.width - box.width) > 0.5 || Math.abs(shown.height - box.height) > 0.5) partial = true;
        return [shown].filter(Boolean);
      } catch { return []; }
    });
    const result = partial ? null : union(pieces); iconCache.set(svg, result); return result;
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
        // Mép phải: nút chữ cuối hàng của các hàng khác cũng là mốc - một cột chỉ có nút ở mép phải (Cài đặt > Nâng cao) vẫn có mép chung.
        const refs = inkTexts.filter((t) => (!t.control || side === "right" && t.control !== el) && parent.contains(t.element) && branch(t.element, parent) !== current && aligned(t.element, side, parent))
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
        // Icon bị mép cuộn / thanh phát che một phần không còn đủ mực để so gap với hàng nguyên vẹn.
        const full = rect(svg.getBoundingClientRect()), shown = visible(svg, full, true);
        if (!shown || ["x", "y", "width", "height"].some((key) => Math.abs(shown[key] - full[key]) > 0.5)) continue;
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
  // Nút xếp dọc (biểu tượng trên, nhãn dưới - ActionButton): ô biểu tượng phải nằm giữa nhãn. Kéo riêng biểu tượng đầu mút ra mép từng làm mực
  // lòi khỏi lề và tách khỏi nhãn (audit140 C1). So ô svg chứ không mực: glyph lệch tâm (RotateCcw) vẫn đúng chỗ.
  for (const el of all) {
    if (!el.matches(controlSelector)) continue;
    const svgs = [...el.querySelectorAll("svg")].filter((svg) => owner(svg) === el && !hidden(svg));
    const labels = inkTexts.filter((t) => t.control === el && t.singleLine);
    if (svgs.length !== 1 || labels.length !== 1) continue;
    const icon = rect(svgs[0].getBoundingClientRect()), label = labels[0].ink;
    if (!icon.width || icon.y + icon.height > label.y + 1 || Math.min(right(icon), right(label)) - Math.max(icon.x, label.x) <= 0) continue;
    const delta = icon.x + icon.width / 2 - (label.x + label.width / 2);
    if (Math.abs(delta) > 1.01) add("INK EDGE", el, el.textContent, [icon, label], { metric: "stacked-icon-center", value: icon.x + icon.width / 2, referenceValue: label.x + label.width / 2,
      delta, tolerance: 1, reason: "icon above a label is not centred on that label" });
  }
  // Nút canh giữa: phần THẤY ĐƯỢC phải đứng giữa vùng trong của nút. Dấu tích ẩn (opacity 0) giữ chỗ trước nhãn từng đẩy chữ "5 phút" lệch phải
  // 8 px (soát 141) - mắt không thấy dấu nhưng thấy chữ lệch. Đo hộp các con trực tiếp đang hiện (không mực: icon tam giác Play tự lệch quang học);
  // con đặt tuyệt đối (icon ghim mép trái ở chân bảng điện thoại) không tính.
  for (const el of all) {
    if (!el.matches(controlSelector) || hidden(el)) continue;
    const s = css(el);
    const centred = /flex/.test(s.display) ? s.justifyContent === "center" && s.flexDirection.startsWith("row") : s.textAlign === "center";
    if (!centred) continue;
    const parts = [...el.childNodes].flatMap((node) => {
      if (node.nodeType === Node.TEXT_NODE) {
        if (!node.textContent.trim()) return [];
        const range = document.createRange(); range.selectNodeContents(node); return [rect(range.getBoundingClientRect())];
      }
      if (node.nodeType !== Node.ELEMENT_NODE || hidden(node) || /absolute|fixed/.test(css(node).position)) return [];
      const r = rect(node.getBoundingClientRect()); return r.width > 0 && r.height > 0 ? [r] : [];
    });
    if (!parts.length || !inkTexts.some((t) => t.control === el)) continue;
    const content = union(parts), box = rect(el.getBoundingClientRect());
    const left = box.x + Number.parseFloat(s.paddingLeft) + Number.parseFloat(s.borderLeftWidth), inner = box.width - Number.parseFloat(s.paddingLeft) - Number.parseFloat(s.paddingRight)
      - Number.parseFloat(s.borderLeftWidth) - Number.parseFloat(s.borderRightWidth);
    if (!(inner > 0) || content.width > inner - 2) continue;
    const delta = content.x + content.width / 2 - (left + inner / 2);
    if (Math.abs(delta) > 1.01) add("INK EDGE", el, el.textContent, [box, content], { metric: "centred-ink-off-centre", value: content.x + content.width / 2, referenceValue: left + inner / 2,
      delta, tolerance: 1, reason: "a centred control's visible content is off its centre" });
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
  // Vạch chia 1 px trong khối lùi lề âm (-mx-3 để nền rê chuột tràn lề): vạch phải thụt theo nội dung, không thò ra ngoài cột của khung chứa
  // (DESIGN 5.5; audit140 C3: bảng Studio thò 10 px mỗi bên). Hộp có viền bốn phía là vật thể riêng - bỏ qua.
  for (const el of all) {
    const s = css(el);
    const top = Number.parseFloat(s.borderTopWidth) > 0 && !transparent(s.borderTopColor) && s.borderTopStyle !== "none";
    const bottom = Number.parseFloat(s.borderBottomWidth) > 0 && !transparent(s.borderBottomColor) && s.borderBottomStyle !== "none";
    if (!(top || bottom) || Number.parseFloat(s.borderLeftWidth) > 0 || Number.parseFloat(s.borderRightWidth) > 0) continue;
    const box = rect(el.getBoundingClientRect());
    if (!box.width || !visible(el, box)) continue;
    let bleed = null;
    for (let p = el, depth = 0; p && p.parentElement && depth < 4; p = p.parentElement, depth++) {
      const ps = css(p);
      if (Number.parseFloat(ps.marginLeft) < -0.5 || Number.parseFloat(ps.marginRight) < -0.5) { bleed = p; break; }
    }
    if (!bleed) continue;
    const frame = bleed.parentElement, fs = css(frame), fb = rect(frame.getBoundingClientRect());
    const left = fb.x + Number.parseFloat(fs.paddingLeft) + Number.parseFloat(fs.borderLeftWidth), rightEdge = right(fb) - Number.parseFloat(fs.paddingRight) - Number.parseFloat(fs.borderRightWidth);
    const over = Math.max(left - box.x, right(box) - rightEdge);
    if (over > 1.01) add("INK EDGE", el, el.textContent, [box, { x: left, y: box.y, width: rightEdge - left, height: 1 }],
      { metric: "hairline-overhang", value: over, referenceValue: 0, delta: over, tolerance: 1, listSelector: selector(bleed), reason: "a 1 px divider in a negative-margin block runs past its frame's content column" });
  }
  // Dấu nối "·" đứng cuối dòng ("Giọng Ngọc Lan ·") hay đầu dòng ("· 4 giờ 40 phút") - audit140 C7. Dấu có thể nằm trong text node riêng
  // (DotJoin cũ) nên so với glyph liền trước / liền sau theo thứ tự tài liệu, chỉ trong cùng một khối chữ.
  const block = (el) => { let p = el; while (p && css(p).display.startsWith("inline")) p = p.parentElement; return p; };
  const charRect = (node, index) => { const range = document.createRange(); range.setStart(node, index); range.setEnd(node, index + 1); const box = [...range.getClientRects()].find((r) => r.width > 0); return box ? rect(box) : null; };
  const glyphs = [];
  for (const run of inkTexts) {
    if (!run.node.textContent.includes("·") && !/^\s|\s$/.test(run.node.textContent)) { glyphs.push({ run, index: -1 }); continue; }
    for (let i = 0; i < run.node.textContent.length; i++) if (run.node.textContent[i].trim()) glyphs.push({ run, index: i, dot: run.node.textContent[i] === "·" });
  }
  for (let i = 0; i < glyphs.length; i++) {
    const g = glyphs[i];
    if (!g.dot) continue;
    const here = charRect(g.run.node, g.index), size = Number.parseFloat(css(g.run.element).fontSize);
    if (!here) continue;
    const near = (o) => { if (!o || block(o.run.element) !== block(g.run.element)) return null; return o.index < 0 ? (o === glyphs[i - 1] ? o.run.last : o.run.first) : charRect(o.run.node, o.index); };
    const before = near(glyphs[i - 1]), after = near(glyphs[i + 1]);
    const ends = after && after.y > here.y + size / 2, starts = before && before.y < here.y - size / 2;
    if (ends || starts) add("LINE BREAK", g.run.element, block(g.run.element)?.textContent ?? g.run.node.textContent, [here, ends ? after : before],
      { metric: ends ? "separator-ends-line" : "separator-starts-line", value: here.y, referenceValue: (ends ? after : before).y, delta: here.y - (ends ? after : before).y, tolerance: size / 2,
        reason: ends ? "a middle dot separator hangs at the end of a line" : "a middle dot separator begins a line" });
  }
  // Lớp nền đặc đặt tuyệt đối (nhãn, huy hiệu) che chữ trong cùng khung, kể cả chữ vẽ aria-hidden như tên trên bìa vẽ - audit140 V8: nhãn
  // "Máy phòng khách" che tên sách; TEXT-OVER-TEXT bỏ qua vì nhãn có nền riêng còn chữ bìa aria-hidden. Không dùng visible()/elementFromPoint:
  // nhãn thường pointer-events-none. Lớp nổi (dialog, menu, thông báo) là fixed nên không vào đây; nền chuyển màu (mờ mép cuộn) không tính.
  const shownChain = (el) => { for (let p = el; p; p = p.parentElement) { const s = css(p); if (s.display === "none" || s.visibility !== "visible" || Number(s.opacity) === 0 || p.hidden) return false; } return true; };
  const zOf = (el) => Number.parseInt(css(el).zIndex, 10) || 0;
  const paintsAbove = (overlay, textEl, frame) => {
    let p = textEl;
    while (p && p !== frame && css(p).position === "static") p = p.parentElement;
    if (!p || p === frame) return zOf(overlay) >= 0;
    if (zOf(overlay) !== zOf(p)) return zOf(overlay) > zOf(p);
    return !overlay.contains(p) && Boolean(p.compareDocumentPosition(overlay) & Node.DOCUMENT_POSITION_FOLLOWING);
  };
  for (const el of all) {
    const s = css(el);
    if (s.position !== "absolute" || transparent(s.backgroundColor) || !shownChain(el)) continue;
    const box = rect(el.getBoundingClientRect());
    if (box.width < 2 || box.height < 2) continue;
    const frame = el.offsetParent ?? el.parentElement;
    if (!frame) continue;
    // Phủ quá nửa khung (Đang nghe toàn màn trên máy tính) là một lớp, không phải nhãn đặt lên nội dung.
    const frameBox = rect(frame.getBoundingClientRect());
    if (box.width * box.height >= 0.5 * frameBox.width * frameBox.height) continue;
    const walker = document.createTreeWalker(frame, NodeFilter.SHOW_TEXT);
    let hit = null;
    for (let node = walker.nextNode(); node && !hit; node = walker.nextNode()) {
      const host = node.parentElement;
      if (!node.textContent.trim() || el.contains(host) || !shownChain(host) || !paintsAbove(el, host, frame)) continue;
      for (let i = 0; i < node.textContent.length && !hit; i++) {
        if (!node.textContent[i].trim()) continue;
        const range = document.createRange(); range.setStart(node, i); range.setEnd(node, i + 1);
        const glyph = [...range.getClientRects()].find((r) => r.width > 0);
        if (!glyph) continue;
        // Bỏ phần đệm ascent/descent của hộp dòng: chỉ thân chữ mới tính là bị che.
        const ink = { x: glyph.x, y: glyph.y + glyph.height * 0.2, width: glyph.width, height: glyph.height * 0.6 };
        if (Math.min(right(ink), right(box)) - Math.max(ink.x, box.x) > 1 && Math.min(ink.y + ink.height, box.y + box.height) - Math.max(ink.y, box.y) > 1) hit = { host, ink };
      }
    }
    if (hit) add("COVERED TEXT", el, `${el.textContent || el.getAttribute("aria-label") || ""} ↔ ${hit.host.textContent}`, [box, hit.ink],
      { metric: "overlay-covers-text", value: Math.min(right(hit.ink), right(box)) - Math.max(hit.ink.x, box.x), otherSelector: selector(hit.host), reason: "an absolutely placed solid layer is painted over text in the same frame" });
  }
  // Tiêu đề trong một tab lặp lại đúng tên tab đang chọn (tab "Nhân vật" mở ra nhóm gập "Nhân vật" - audit140 V2): chữ thừa, người đọc đã
  // biết mình đang ở đâu. So mẩu chữ đầu của tiêu đề với nhãn tab, bỏ số đếm cuối ("Chương 16").
  const labelOf = (text) => text.replace(/\s+/g, " ").trim().replace(/\s*\d+$/, "").toLocaleLowerCase("vi");
  for (const panel of all) {
    if (panel.getAttribute("role") !== "tabpanel" || !shownChain(panel)) continue;
    const id = panel.getAttribute("aria-labelledby");
    const tab = (id && document.getElementById(id)) || null;
    if (!tab || tab.getAttribute("aria-selected") !== "true") continue;
    const name = labelOf(tab.textContent ?? "");
    if (!name) continue;
    for (const heading of panel.querySelectorAll('h1,h2,h3,h4,h5,h6,[role="heading"]')) {
      if (!shownChain(heading)) continue;
      const walker = document.createTreeWalker(heading, NodeFilter.SHOW_TEXT);
      let first = walker.nextNode();
      while (first && !first.textContent.trim()) first = walker.nextNode();
      if (!first || labelOf(first.textContent) !== name) continue;
      add("REPEATED LABEL", first.parentElement, first.textContent, [rect(first.parentElement.getBoundingClientRect()), rect(tab.getBoundingClientRect())],
        { metric: "heading-repeats-tab", otherSelector: selector(tab), reason: "a heading inside a tab repeats the selected tab's label" });
    }
  }
  // Cùng một nhãn, hai việc (soát 140): hai nút cùng hiện một chữ mà biểu tượng khác nhau là hai hành động - người nghe không phân biệt được.
  // Nút lặp theo hàng (cùng biểu tượng) không tính; nút của màn nằm dưới hộp thoại (aria-hidden / inert, nút Tìm của trang sách sau hộp Tìm
  // ảnh bìa) cũng không.
  const iconSignature = (el) => [...el.querySelectorAll("svg")].filter((svg) => owner(svg) === el)
    .map((svg) => [...svg.querySelectorAll("path,rect,circle,ellipse,line,polyline,polygon")].map((p) => p.outerHTML.replace(/\s(class|style)="[^"]*"/g, "")).join("")).join("|");
  const labelled = all.filter((el) => el.matches(controlSelector) && shownChain(el) && !el.closest('[aria-hidden="true"],[inert]') && rect(el.getBoundingClientRect()).width > 0)
    .map((el) => ({ el, label: labelOf(el.textContent ?? ""), icon: iconSignature(el) })).filter((c) => c.label && c.icon);
  const sameLabel = new Set();
  // Giá trị trên nút mở được lặp ở lựa chọn đang chọn trong CHÍNH popup nó điều khiển.
  // Chỉ miễn khi có đủ quan hệ ARIA và trạng thái chọn; nhãn trùng của hai hành động khác vẫn báo.
  const showsSelectedChoice = (trigger, choice) => trigger.getAttribute("aria-expanded") === "true"
    && choice.matches('[aria-pressed="true"],[aria-selected="true"],[aria-checked="true"]')
    && (trigger.getAttribute("aria-controls") ?? "").split(/\s+/).some((id) => {
      const popup = document.getElementById(id);
      return popup?.matches('[role="dialog"],[role="listbox"],[role="menu"]') && popup.contains(choice);
    });
  for (const [i, a] of labelled.entries()) for (const b of labelled.slice(i + 1)) {
    if (a.label !== b.label || a.icon === b.icon || a.el.contains(b.el) || b.el.contains(a.el) || sameLabel.has(a.label)) continue;
    if (showsSelectedChoice(a.el, b.el) || showsSelectedChoice(b.el, a.el)) continue;
    sameLabel.add(a.label);
    add("REPEATED LABEL", b.el, b.el.textContent, [rect(a.el.getBoundingClientRect()), rect(b.el.getBoundingClientRect())],
      { metric: "label-names-two-actions", otherSelector: selector(a.el), reason: "two visible controls share a label but carry different icons, so one label names two actions" });
  }
  // Một hàng không vẽ cùng một icon hai lần: icon đầu hàng lặp lại trên nút của chính hàng ấy (thư mục trước đường dẫn + thư mục trên
  // "Đổi thư mục", loa ở nhãn + loa trên nút - audit140 P9). Chỉ so với icon trang trí (không nằm trong nút khác) để dãy thẻ cùng nút không bị tính.
  const svgSignature = (svg) => [...svg.querySelectorAll("path,rect,circle,ellipse,line,polyline,polygon")].map((p) => p.outerHTML.replace(/\s(class|style)="[^"]*"/g, "")).join("");
  const twiceRows = new Set();
  for (const el of all.filter((e) => e.matches(controlSelector) && shownChain(e) && !e.closest('[aria-hidden="true"],[inert]'))) {
    const mine = [...el.querySelectorAll("svg")].filter((svg) => owner(svg) === el && visible(svg, rect(svg.getBoundingClientRect())));
    if (!mine.length) continue;
    let row = el.parentElement;
    for (let depth = 0; row && depth < 3 && !(css(row).display.includes("flex") && !css(row).flexDirection.startsWith("column")); depth++) row = row.parentElement;
    if (!row || !css(row).display.includes("flex") || css(row).flexDirection.startsWith("column") || twiceRows.has(row)) continue;
    for (const svg of mine) {
      const signature = svgSignature(svg), own = rect(svg.getBoundingClientRect());
      if (!signature) continue;
      const twin = [...row.querySelectorAll("svg")].find((other) => {
        if (other === svg || el.contains(other) || other.closest(controlSelector) || svgSignature(other) !== signature || !shownChain(other)) return false;
        const box = visible(other, rect(other.getBoundingClientRect()));
        return box && Math.min(box.y + box.height, own.y + own.height) - Math.max(box.y, own.y) > own.height / 2;
      });
      if (!twin) continue;
      twiceRows.add(row);
      add("REPEATED LABEL", el, el.textContent || el.getAttribute("aria-label") || "svg", [rect(twin.getBoundingClientRect()), own],
        { metric: "row-icon-twice", otherSelector: selector(twin), reason: "one row draws the same icon twice, so the icon no longer tells its parts apart" });
      break;
    }
  }
  // Nút trong suốt xếp chồng trong một cột (Sửa sách: "Chọn ảnh bìa…" / "Tìm bìa…"): không có nền để làm mốc, nên mực của chúng phải chung
  // mép trái. Kéo giãn từng nút rồi canh giữa chữ làm icon lệch nhau theo độ dài nhãn (soát 25-10). Nút có nền/viền (chân hộp thoại) không tính.
  for (const parent of all) {
    const ps = css(parent);
    if (!/flex/.test(ps.display) || !ps.flexDirection.startsWith("column")) continue;
    const stack = [...parent.children].filter((c) => c.matches(controlSelector) && visible(c, rect(c.getBoundingClientRect())));
    if (stack.length < 2 || stack.length !== [...parent.children].filter((c) => visible(c, rect(c.getBoundingClientRect()))).length) continue;
    if (stack.some((c) => !transparent(css(c).backgroundColor) || Number.parseFloat(css(c).borderLeftWidth) > 0 && css(c).borderLeftStyle !== "none")) continue;
    const inks = stack.map((c) => ({ c, ink: controlInk(c) })).filter((s) => s.ink);
    if (inks.length < 2) continue;
    const xs = inks.map((s) => s.ink.x), low = Math.min(...xs), high = Math.max(...xs);
    if (high - low <= 1.01) continue;
    const worst = inks.find((s) => s.ink.x === high), best = inks.find((s) => s.ink.x === low);
    add("INK EDGE", worst.c, worst.c.textContent, [worst.ink, best.ink],
      { metric: "stacked-controls-left", value: high, referenceValue: low, delta: high - low, tolerance: 1, otherSelector: selector(best.c), reason: "transparent controls stacked in one column start their ink at different x" });
  }
  // Nút trong suốt cuối hàng mà ô của nó chạm mép phải hàng nhưng mực thụt vào >= 6 px ("Ghép thiết bị", nút chép ở Thiết bị điện thoại):
  // chỉ báo khi trong cùng cột có mực khác chạm đúng mép ấy, tức cột đã có mép phải chung mà nút này bỏ lỡ.
  for (const el of all.filter((e) => e.matches(controlSelector) && shownChain(e))) {
    const box = visible(el, rect(el.getBoundingClientRect()));
    if (!box || !transparent(css(el).backgroundColor) || el.closest('nav,[role="tablist"],[role="menu"],[role="listbox"],[role="dialog"]')) continue;
    const row = el.parentElement, rs = row && css(row);
    if (!row || !/flex/.test(rs.display) || rs.flexDirection.startsWith("column") || row.lastElementChild !== el) continue;
    const rb = rect(row.getBoundingClientRect()), inner = right(rb) - Number.parseFloat(rs.paddingRight) - Number.parseFloat(rs.borderRightWidth);
    const ink = controlInk(el);
    if (!ink || Math.abs(right(box) - inner) > 1.01 || inner - right(ink) < 5.99) continue;
    // Cột = tổ tiên cao nhất còn chung mép phải trong (cả trang Thiết bị, không chỉ mục chứa nút).
    let column = null;
    for (let p = row.parentElement; p && p !== document.body; p = p.parentElement) {
      const s = css(p), pr = right(rect(p.getBoundingClientRect())) - Number.parseFloat(s.paddingRight) - Number.parseFloat(s.borderRightWidth);
      if (Math.abs(pr - inner) > 1.01) break;
      column = p;
      if (/auto|scroll/.test(s.overflowY)) break;
    }
    if (!column || !inkTexts.some((t) => column.contains(t.element) && !row.contains(t.element) && Math.abs(right(t.last) - inner) <= 1.01)) continue;
    add("INK EDGE", el, el.textContent || el.getAttribute("aria-label") || "svg", [ink, { x: inner, y: ink.y, width: 1, height: ink.height }],
      { metric: "trailing-control-inset", value: right(ink), referenceValue: inner, delta: right(ink) - inner, tolerance: 1, listSelector: selector(column), reason: "trailing transparent control's hit box meets the row edge but its ink stops short of the column's shared right edge" });
  }
  // Lớp chồng lớp: hộp thoại mở đè lên hộp thoại khác (Sửa sách -> Tìm ảnh bìa, audit140 V9) hay bảng nổi che menu vừa mở nó (Nhạc nền đè menu
  // trình phát, C8). Bước kế tiếp đi trong cùng lớp (trượt sang bước có "Quay lại") hoặc mở bên cạnh menu. Menu/danh sách chọn bên trong hộp
  // thoại vẫn được; menu con nằm cạnh menu cha (chạm nhau vài px) cũng được.
  const layers = all.filter((el) => /^(dialog|alertdialog|menu)$/.test(el.getAttribute("role") ?? "") && shownChain(el))
    .map((el) => ({ el, role: el.getAttribute("role"), box: rect(el.getBoundingClientRect()) })).filter((l) => l.box.width > 0 && l.box.height > 0);
  for (let i = 0; i < layers.length; i++) for (let j = i + 1; j < layers.length; j++) {
    const a = layers[i], b = layers[j];
    if (a.el.contains(b.el) || b.el.contains(a.el)) continue;
    const dialogs = a.role !== "menu" && b.role !== "menu", overMenu = a.role === "menu" || b.role === "menu";
    if (!dialogs && !overMenu) continue;
    const w = Math.min(right(a.box), right(b.box)) - Math.max(a.box.x, b.box.x), hgt = Math.min(a.box.y + a.box.height, b.box.y + b.box.height) - Math.max(a.box.y, b.box.y);
    if (w <= 8 || hgt <= 8) continue;
    add("STACKED LAYERS", b.el, `${a.el.getAttribute("aria-label") || a.el.textContent?.slice(0, 40) || a.role} ↔ ${b.el.getAttribute("aria-label") || b.el.textContent?.slice(0, 40) || b.role}`,
      [a.box, b.box], { metric: dialogs ? "dialog-over-dialog" : "layer-over-menu", value: Math.min(w, hgt), otherSelector: selector(a.el), reason: "one floating layer is drawn over another instead of replacing it or opening beside it" });
  }
  // Mục điều hướng đang mở (aria-current="page"): nền trung tính + chữ đậm màu thường (DESIGN 6 "Điều hướng"). Chữ hổ phách dành cho
  // lựa chọn trong danh sách chọn; ở điều hướng nó đọc như một lựa chọn đã bấm (thanh bên, danh sách nhóm Cài đặt - soát 25-10).
  // Thanh tab đáy điện thoại giữ quy ước nền tảng (tab đang mở tô màu nhấn) - DESIGN 3.
  const bottomTabBar = (el) => { const nav = el.closest("nav"); const box = nav && nav.getBoundingClientRect(); return Boolean(box) && box.bottom >= innerHeight - 2 && box.width >= innerWidth * 0.9; };
  for (const el of all.filter((e) => e.matches('[aria-current="page"]') && shownChain(e) && !bottomTabBar(e))) {
    const probe = document.createElement("span");
    probe.style.color = "var(--accent-text)";
    el.append(probe);
    const accent = css(probe).color;
    probe.remove();
    if (!getComputedStyle(el).getPropertyValue("--accent-text").trim()) continue;
    const hit = inkTexts.find((t) => el.contains(t.element) && css(t.element).color === accent);
    if (hit) add("NAV ACCENT", el, el.textContent, [rect(el.getBoundingClientRect()), hit.ink],
      { metric: "nav-current-accent", reason: "current navigation item uses the accent text colour reserved for picked choices" });
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
  // Tiêu đề màn (h1 đầu tiên đang thấy, chưa cuộn, không bị lớp khác phủ): chân chữ phải trùng giữa mọi màn cùng nền tảng - đổi tab đáy thì tiêu đề
  // không nhảy (soát 25-10: Thư viện / Studio / Cài đặt điện thoại 54 / 46 / 40). Tiêu đề nằm trong nội dung (tên sách cạnh bìa: data-content-title)
  // và tiêu đề chương trong bài đọc (article) không phải đầu màn.
  let screenTitle = null;
  if (!all.some((e) => e.matches('[role="dialog"],[role="alertdialog"]') && visible(e, rect(e.getBoundingClientRect())))) {
    const heading = [...document.querySelectorAll("h1")].find((el) => !el.closest("[data-content-title],article") && visible(el, rect(el.getBoundingClientRect())));
    const scrolled = (el) => (document.scrollingElement?.scrollTop ?? 0) > 0 || (() => { for (let p = el.parentElement; p; p = p.parentElement) if (p.scrollTop > 0) return true; return false; })();
    const walker = heading && document.createTreeWalker(heading, NodeFilter.SHOW_TEXT);
    let node = walker?.nextNode();
    while (node && !node.textContent.trim()) node = walker.nextNode();
    if (node && !scrolled(heading)) {
      const at = node.textContent.search(/\S/), s = css(node.parentElement);
      const range = document.createRange(); range.setStart(node, at); range.setEnd(node, at + 1);
      const r = range.getBoundingClientRect();
      ctx.font = `${s.fontStyle} ${s.fontWeight} ${s.fontSize} ${s.fontFamily}`;
      const m = ctx.measureText(node.textContent[at]), total = m.fontBoundingBoxAscent + m.fontBoundingBoxDescent;
      const top = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
      if (total > 0 && r.height > 0 && top && (heading.contains(top) || top.contains(heading))) {
        const box = rect(heading.getBoundingClientRect());
        // Tính từ mép trên vùng nội dung của main: dải mất mạng / máy ghép nằm trong luồng phía trên đẩy cả trang xuống, đầu màn vẫn đúng chỗ
        // của nó; main lùi lên chừa chỗ vòng tiêu điểm (-mt-8px pt-8px) không làm đầu màn lệch.
        const main = heading.closest("main"), mainStyle = main && css(main);
        const frameTop = main ? main.getBoundingClientRect().top + Number.parseFloat(mainStyle.borderTopWidth) + Number.parseFloat(mainStyle.paddingTop) : 0;
        screenTitle = { baseline: r.y + m.fontBoundingBoxAscent * (r.height / total) - frameTop, frameTop, kind: heading.dataset.screenTitle ?? "unmarked", fontSize: s.fontSize,
          selector: selector(heading), rect: box, text: heading.textContent.trim().slice(0, 160), context: [{ tag: "h1", classes: [...heading.classList], data: { ...heading.dataset } }] };
      }
    }
  }
  return { columns, gaps, rhythms, fills, firstBlock, screenTitle };
}
