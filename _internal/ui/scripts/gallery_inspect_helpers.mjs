// Các phép tính thuần dùng chung giữa Vitest và trình duyệt (nhúng bằng toString, không bundler).
export function createInspectorHelpers() {
  const rect = (r) => ({ x: r.x ?? r.left, y: r.y ?? r.top, width: r.width, height: r.height });
  function intersection(a, b, tolerance = 1) {
    const x = Math.max(a.x, b.x), y = Math.max(a.y, b.y);
    const width = Math.min(a.x + a.width, b.x + b.width) - x;
    const height = Math.min(a.y + a.height, b.y + b.height) - y;
    return width > tolerance && height > tolerance ? { x, y, width, height } : null;
  }
  function union(rects) {
    if (!rects.length) return null;
    const x = Math.min(...rects.map((r) => r.x)), y = Math.min(...rects.map((r) => r.y));
    return { x, y, width: Math.max(...rects.map((r) => r.x + r.width)) - x, height: Math.max(...rects.map((r) => r.y + r.height)) - y };
  }
  function overflow(metrics, style) {
    const clamp = Number.parseInt(style.webkitLineClamp ?? style.lineClamp, 10) > 0;
    return {
      x: /^(hidden|clip)$/.test(style.overflowX) && style.textOverflow !== "ellipsis" && metrics.scrollWidth > metrics.clientWidth + 1,
      y: /^(hidden|clip)$/.test(style.overflowY) && !clamp && metrics.scrollHeight > metrics.clientHeight + 1,
    };
  }
  const luminance = (rgb) => rgb.slice(0, 3).map((c) => c / 255).map((c) => c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4).reduce((v, c, i) => v + c * [0.2126, 0.7152, 0.0722][i], 0);
  function contrastRatio(a, b) {
    const x = luminance(a), y = luminance(b);
    return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05);
  }
  const composite = (fg, bg) => [...fg.slice(0, 3).map((c, i) => c * fg[3] + bg[i] * (1 - fg[3])), 1];
  function graphicOverlap(text, graphic) {
    // Chữ SVG cùng hệ toạ độ (glyph mới) thuộc chính hình; chữ HTML đè lên SVG (glyph cũ) thì không.
    if (graphic.element.contains(text.element)) return null;
    const overlay = text.element.closest("[data-overlay]");
    if (overlay?.contains(graphic.element)) return null;
    return intersection(text.rect, graphic.rect);
  }
  function siblingDifferences(samples, tolerance = 1) {
    // Layout values are floats. A 0.001 px rounding residue is not a defect.
    tolerance += 0.01;
    // Hàng gần nhiều hàng khác nhất làm mốc; hoà thì lấy hàng đầu. Hai hàng vẫn có mốc rõ ràng.
    const reference = samples.reduce((best, sample) => {
      const score = (s) => samples.filter((other) => Math.abs(other.value - s.value) <= tolerance).length;
      return score(sample) > score(best) ? sample : best;
    }, samples[0]);
    if (!reference) return [];
    const differences = samples.filter((s) => Math.abs(s.value - reference.value) > tolerance)
      .map((sample) => ({ sample, reference, delta: sample.value - reference.value }));
    // Chuỗi 0 / 1 / 2 vẫn lệch 2 px dù hàng giữa cách cả hai đầu đúng 1 px.
    if (!differences.length) {
      const low = samples.reduce((a, b) => a.value < b.value ? a : b), high = samples.reduce((a, b) => a.value > b.value ? a : b);
      if (high.value - low.value > tolerance) differences.push({ sample: high, reference: low, delta: high.value - low.value });
    }
    return differences;
  }
  return { rect, intersection, union, overflow, luminance, contrastRatio, composite, graphicOverlap, siblingDifferences };
}

// Chạy hoàn toàn trong trang, chỉ trả dữ liệu JSON. Không đọc state nội bộ của React.
export function inspectPage({ phone = false } = {}, h, layoutInspector) {
  const { rect, intersection, union, overflow, contrastRatio, composite, graphicOverlap, siblingDifferences } = h;
  const viewport = { x: 0, y: 0, width: innerWidth, height: innerHeight };
  const findings = [], contacts = [], overlays = [];
  const styleCache = new Map();
  const css = (el) => {
    if (!styleCache.has(el)) styleCache.set(el, getComputedStyle(el));
    return styleCache.get(el);
  };
  function selector(el) {
    const parts = [];
    for (let item = el; item && item !== document.documentElement; item = item.parentElement) {
      if (item.id) { parts.unshift(`#${CSS.escape(item.id)}`); break; }
      const siblings = [...(item.parentElement?.children ?? [])].filter((s) => s.localName === item.localName);
      parts.unshift(`${item.localName}${siblings.length > 1 ? `:nth-of-type(${siblings.indexOf(item) + 1})` : ""}`);
    }
    return parts.join(" > ");
  }
  const surface = (el) => el.closest('[role="dialog"],[role="alertdialog"],[role="menu"],[role="listbox"],[role="tooltip"],[data-sonner-toast]');
  function hidden(el) {
    for (let p = el; p; p = p.parentElement) {
      const s = css(p);
      if (s.display === "none" || s.visibility !== "visible" || Number(s.opacity) === 0 || p.hidden || p !== el && s.contentVisibility === "hidden" || /^rect\(0px[, ]+0px[, ]+0px[, ]+0px\)$/.test(s.clip) || /^inset\(50%\)/.test(s.clipPath)) return true;
    }
    return false;
  }
  function visible(el, raw, graphic = false) {
    if (!raw || raw.width <= 0 || raw.height <= 0) return null;
    let clipped = intersection(raw, viewport, 0);
    for (let p = el; p && clipped; p = p.parentElement) {
      const s = css(p);
      if (s.display === "none" || s.visibility !== "visible" || Number(s.opacity) === 0 || p.hidden) return null;
      // content-visibility: hidden (trang bị màn Đang nghe phủ - android/App.tsx data-covered): con cháu không được vẽ, kích thước đo được là cũ.
      if (p !== el && s.contentVisibility === "hidden") return null;
      // sr-only dùng clip/clip-path: chữ vẫn có Range nhưng không có pixel nào được vẽ.
      if (/^rect\(0px[, ]+0px[, ]+0px[, ]+0px\)$/.test(s.clip) || /^inset\(50%\)/.test(s.clipPath)) return null;
      if (p !== document.body && p !== document.documentElement) {
        const box = rect(p.getBoundingClientRect());
        const clipX = /hidden|clip|auto|scroll/.test(s.overflowX), clipY = /hidden|clip|auto|scroll/.test(s.overflowY);
        if (clipX || clipY) clipped = intersection(clipped, { x: clipX ? box.x : clipped.x, y: clipY ? box.y : clipped.y, width: clipX ? box.width : clipped.width, height: clipY ? box.height : clipped.height }, 0);
      }
    }
    if (!clipped) return null;
    // Bỏ phần nền đã bị dialog/menu che; aria-hidden không đồng nghĩa với không nhìn thấy.
    const points = [0.2, 0.5, 0.8].map((t) => [clipped.x + clipped.width * t, clipped.y + clipped.height / 2]);
    if (!points.some(([x, y]) => {
      const top = document.elementFromPoint(x, y);
      const transparentSibling = top && !graphic && surface(el) === surface(top) && (() => {
        for (let p = top; p && !p.contains(el); p = p.parentElement) {
          const s = css(p);
          if (s.backgroundImage !== "none" || !["transparent", "rgba(0, 0, 0, 0)"].includes(s.backgroundColor)) return false;
        }
        return true;
      })();
      return top && (top === el || el.contains(top) || top.contains(el) || transparentSibling || (graphic && el.parentElement !== document.body && el.parentElement?.id !== "root" && el.parentElement?.contains(top) && surface(el) === surface(top)));
    })) return null;
    return clipped;
  }
  function add(rule, el, text, rects, details = {}) {
    const context = [];
    for (let p = el; p && context.length < 8; p = p.parentElement) context.push({ tag: p.localName, classes: [...p.classList], data: Object.fromEntries([...p.attributes].filter((a) => a.name.startsWith("data-")).map((a) => [a.name, a.value])) });
    findings.push({ rule, selector: selector(el), context, text: text.replace(/\s+/g, " ").trim().slice(0, 240), rects, ...details });
  }
  const all = [...document.body.querySelectorAll("*")];
  // Lớp mờ cuộn (aria-hidden, không nhận chạm, dải màu về trong suốt) là mặt nạ có chủ ý: chữ cuộn dưới nó mờ dần, thanh nổi nằm trên nó.
  const scrollFade = (el) => {
    const s = css(el);
    return el.getAttribute("aria-hidden") === "true" && s.pointerEvents === "none" && /gradient\(/.test(s.backgroundImage)
      && /rgba\([^()]*,\s*0\)|transparent|\/\s*0\)/.test(s.backgroundImage) && !el.querySelector("svg,img,canvas");
  };
  const graphics = all.filter((el) => el.matches("svg,img,canvas") || (css(el).backgroundImage !== "none" && !scrollFade(el)))
    .map((element) => ({ element, rect: visible(element, rect(element.getBoundingClientRect()), true) })).filter((g) => g.rect);
  const texts = [], renderedRuns = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    if (!node.textContent.trim()) continue;
    const element = node.parentElement;
    if (!element || element.closest("script,style,noscript,title,desc,option") || hidden(element)) continue;
    const range = document.createRange();
    const first = node.textContent.search(/\S/), last = node.textContent.trimEnd().length;
    range.setStart(node, first); range.setEnd(node, last);
    for (const raw of range.getClientRects()) {
      const original = rect(raw), shown = visible(element, original);
      if (original.width > 0 && original.height > 0) renderedRuns.push({ element, node, text: node.textContent, rect: original, original });
      if (shown) texts.push({ element, node, text: node.textContent, rect: shown, original });
    }
  }
  // Gom theo text node: chữ xuống nhiều dòng vẫn là một phát hiện và một crop.
  const reported = new Map();
  function once(rule, text, rects, details = {}) {
    let rules = reported.get(text.node);
    if (!rules) reported.set(text.node, (rules = new Map()));
    if (rules.has(rule)) { rules.get(rule).rects.push(...rects); return; }
    add(rule, text.element, text.text, rects, details);
    rules.set(rule, findings.at(-1));
  }
  const canvas = document.createElement("canvas"); canvas.width = canvas.height = 1;
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  const colors = new Map();
  function color(value) {
    if (!colors.has(value)) {
      ctx.clearRect(0, 0, 1, 1); ctx.fillStyle = value; ctx.fillRect(0, 0, 1, 1);
      const data = ctx.getImageData(0, 0, 1, 1).data;
      colors.set(value, [data[0], data[1], data[2], data[3] / 255]);
    }
    return colors.get(value);
  }
  function background(el) {
    const layers = [];
    const box = el.getBoundingClientRect(), cx = box.left + box.width / 2, cy = box.top + box.height / 2;
    for (let p = el; p; p = p.parentElement) {
      const s = css(p);
      if (s.backgroundImage !== "none") return null;
      // Lớp nền trượt của nhóm chọn (SlidingIndicator) là con của p vẽ dưới chữ, trên nền của p: chữ mục đang chọn nằm trên nó.
      const slide = p === el ? null : [...p.children].find((child) => child.matches("[data-sliding-indicator]") && (() => { const r = child.getBoundingClientRect(); return cx >= r.left && cx <= r.right && cy >= r.top && cy <= r.bottom; })());
      if (slide) {
        const under = color(css(slide).backgroundColor);
        layers.push(under);
        if (under[3] >= 0.999) break;
      }
      const rgba = color(s.backgroundColor);
      layers.push(rgba);
      if (rgba[3] >= 0.999) break;
    }
    let bg = [255, 255, 255, 1];
    for (const layer of layers.reverse()) bg = composite(layer, bg);
    return bg;
  }
  function scrollable(el, axis) {
    for (let p = el; p; p = p.parentElement) {
      const s = css(p), key = axis === "x" ? "overflowX" : "overflowY";
      if (/auto|scroll/.test(s[key]) && (axis === "x" ? p.scrollWidth > p.clientWidth : p.scrollHeight > p.clientHeight)) return true;
      if (axis === "y" && p === document.scrollingElement && !/hidden|clip/.test(s.overflowY) && p.scrollHeight > innerHeight) return true;
    }
    return false;
  }
  for (const text of texts) {
    const el = text.element, s = css(el);
    for (const graphic of graphics) {
      if (surface(el) !== surface(graphic.element)) continue;
      if (graphicOverlap(text, graphic)) once("TEXT-OVER-GRAPHIC", text, [text.rect, graphic.rect], { otherSelector: selector(graphic.element), graphic: graphic.element.localName });
    }
    const size = Number.parseFloat(s.fontSize);
    // getComputedStyle của SVG/transform là cỡ trước co giãn; số đo phải theo CSS px đã vẽ.
    let transformScale = 1;
    if (el instanceof SVGGraphicsElement) transformScale = Math.hypot(el.getScreenCTM()?.a ?? 1, el.getScreenCTM()?.b ?? 0);
    else {
      let matrix = new DOMMatrix();
      for (let p = el; p; p = p.parentElement) {
        const s = css(p);
        if (s.transform !== "none") matrix = new DOMMatrix(s.transform).multiply(matrix);
        if (s.scale && s.scale !== "none") {
          const scale = s.scale.split(" ").map(Number);
          matrix = new DOMMatrix().scale(scale[0], scale[1] ?? scale[0]).multiply(matrix);
        }
      }
      transformScale = Math.hypot(matrix.c, matrix.d);
    }
    const renderedSize = size * transformScale;
    if (renderedSize < 11) once("SMALL TEXT", text, [text.rect], { fontSize: renderedSize });
    const bg = background(el);
    const overImage = graphics.some((g) => g.element.matches("img,canvas") && intersection(g.rect, text.rect));
    if (bg && !overImage && !el.closest(":disabled,[aria-disabled=true],[inert]")) {
      let opacity = 1;
      for (let p = el; p; p = p.parentElement) opacity *= Number(css(p).opacity);
      const fg = [...color(s.color)]; fg[3] *= opacity;
      const ratio = contrastRatio(composite(fg, bg), bg);
      const bold = Number.parseInt(s.fontWeight, 10) >= 700;
      const threshold = renderedSize >= 24 || (renderedSize >= 18.66 && bold) ? 3 : 4.5;
      if (ratio + 0.001 < threshold) once("CONTRAST", text, [text.rect], { ratio: +ratio.toFixed(3), threshold, foreground: fg, background: bg, fontSize: renderedSize, disabled: Boolean(el.closest(":disabled,[aria-disabled=true]")) });
    }
  }
  function truncation(el, end, axis) {
    for (let p = el; p; p = p.parentElement) {
      const s = css(p);
      if ((axis === "x" && s.textOverflow === "ellipsis") || (axis === "y" && Number.parseInt(s.webkitLineClamp, 10) > 0)) return true;
      if (p === end) break;
    }
    return false;
  }
  for (const run of renderedRuns) {
    // A fully offscreen in-page keyboard link is revealed on focus; it is not clipped content.
    const link = run.element.closest('a[href^="#"]');
    if (link && document.activeElement !== link && link.hash.length > 1 && document.getElementById(decodeURIComponent(link.hash.slice(1))) && !intersection(run.rect, viewport, 0)) continue;
    const focusControl = run.element.closest('button,a');
    if (focusControl && document.activeElement !== focusControl && !intersection(run.rect, viewport, 0) && [...focusControl.classList].some((c) => /^focus:(?:translate-[xy]-0|transform-none)$/.test(c))) continue;
    const outsideX = run.rect.x < -1 || run.rect.x + run.rect.width > innerWidth + 1;
    const outsideY = run.rect.y < -1 || run.rect.y + run.rect.height > innerHeight + 1;
    if ((outsideX && !scrollable(run.element, "x") && !truncation(run.element, null, "x")) || (outsideY && !scrollable(run.element, "y") && !truncation(run.element, null, "y"))) {
      // Toàn bộ chữ có thể nằm ngoài viewport: crop mép gần nhất, giữ nguyên rect ngoài màn trong JSON.
      const edge = { x: Math.max(0, Math.min(innerWidth - 1, run.rect.x)), y: Math.max(0, Math.min(innerHeight - 1, run.rect.y)), width: 1, height: 1 };
      once("CLIPPED TEXT", run, [intersection(run.rect, viewport, 0) ?? edge], { reason: "outside viewport", originalRect: run.original });
    }
  }
  const inkCache = new Map();
  for (let i = 0; i < texts.length; i++) {
    for (let j = i + 1; j < texts.length; j++) {
      const a = texts[i], b = texts[j];
      if (a.node === b.node || !intersection(a.rect, b.rect)) continue;
      if (surface(a.element) !== surface(b.element)) continue;
      const overlay = a.element.closest("[data-overlay]");
      if (overlay?.contains(b.element)) continue;
      if (!inkCollision(a, b)) continue;
      // Rect lấy từ Range, không phải hộp bao của cả đoạn văn.
      add("TEXT-OVER-TEXT", a.element, `${a.text} ↔ ${b.text}`, [a.rect, b.rect], { otherSelector: selector(b.element) });
    }
  }
  // Range rectangles include the font's ascent/descent padding. Confirm candidate collisions
  // with per-character ink bounds; do this only for overlapping runs, not for the entire page.
  function inkRects(run) {
    if (inkCache.has(run)) return inkCache.get(run);
    const s = css(run.element), boxes = [];
    ctx.font = `${s.fontStyle || "normal"} ${s.fontWeight} ${s.fontSize} ${s.fontFamily || "sans-serif"}`;
    let offset = 0;
    for (const char of run.node.textContent) {
      const start = offset; offset += char.length;
      if (!char.trim()) continue;
      const range = document.createRange(); range.setStart(run.node, start); range.setEnd(run.node, offset);
      const m = ctx.measureText(char);
      for (const r of range.getClientRects()) {
        const total = m.fontBoundingBoxAscent + m.fontBoundingBoxDescent;
        if (!(total > 0)) { boxes.push(rect(r)); continue; }
        const scale = r.height / total;
        const box = { x: r.x, y: r.y + (m.fontBoundingBoxAscent - m.actualBoundingBoxAscent) * scale, width: r.width, height: (m.actualBoundingBoxAscent + m.actualBoundingBoxDescent) * scale };
        const shown = intersection(box, run.rect, 0);
        if (shown) boxes.push(shown);
      }
    }
    inkCache.set(run, boxes); return boxes;
  }
  function inkCollision(a, b) {
    if (a.node === b.node) return false;
    // SVG has a separate baseline/CTM; use its already transformed Range geometry.
    if (a.element.closest("svg") || b.element.closest("svg")) return true;
    if (!inkRects(a).some((x) => inkRects(b).some((y) => intersection(x, y, 0.5)))) return false;
    // Glyph bounding boxes still include empty corners and counters. Confirm actual
    // painted pixels in the candidate intersection, rather than treating ink boxes
    // as solid rectangles (e.g. a descender beside the next line's ascender).
    const area = intersection(a.rect, b.rect, 0), resolution = 4;
    function mask(run) {
      const layer = document.createElement("canvas");
      layer.width = Math.ceil(area.width * resolution); layer.height = Math.ceil(area.height * resolution);
      const paint = layer.getContext("2d", { willReadFrequently: true }), s = css(run.element);
      paint.font = `${s.fontStyle || "normal"} ${s.fontWeight} ${s.fontSize} ${s.fontFamily || "sans-serif"}`;
      paint.fillStyle = "black";
      let offset = 0;
      for (const char of run.node.textContent) {
        const start = offset; offset += char.length;
        if (!char.trim()) continue;
        const range = document.createRange(); range.setStart(run.node, start); range.setEnd(run.node, offset);
        const m = paint.measureText(char), total = m.fontBoundingBoxAscent + m.fontBoundingBoxDescent;
        if (!(total > 0) || !(m.width > 0)) continue;
        for (const r of range.getClientRects()) {
          if (!intersection(r, run.rect, 0)) continue;
          const scaleY = r.height / total, scaleX = r.width / m.width;
          paint.save();
          paint.setTransform(scaleX * resolution, 0, 0, scaleY * resolution,
            (r.x - area.x) * resolution, (r.y - area.y + m.fontBoundingBoxAscent * scaleY) * resolution);
          paint.fillText(char, 0, 0); paint.restore();
        }
      }
      return paint.getImageData(0, 0, layer.width, layer.height).data;
    }
    const first = mask(a), second = mask(b);
    let coverage = 0;
    for (let i = 3; i < first.length; i += 4) if (first[i] >= 128 && second[i] >= 128) coverage++;
    return coverage >= resolution * resolution;
  }
  for (const el of all) {
    const raw = rect(el.getBoundingClientRect()), shown = visible(el, raw);
    if (!shown) continue;
    const s = css(el);
    if (el.matches("[data-overlay]")) overlays.push({ selector: selector(el), reason: el.getAttribute("data-overlay") });
    // Chỉ xét hộp có chữ trực tiếp: tránh quy tội overflow ảnh/đồ trang trí cho toàn bộ main.
    const ownText = [...el.childNodes].some((n) => n.nodeType === Node.TEXT_NODE && n.textContent.trim());
    const textChild = renderedRuns.some((t) => el.contains(t.element));
    const excess = overflow(el, s);
    if ((ownText || textChild) && (excess.x || excess.y) && !el.matches("svg,svg *")) {
      const escaped = renderedRuns.some((t) => el.contains(t.element) && ((excess.x && !truncation(t.element, el, "x") && (t.original.x < raw.x - 1 || t.original.x + t.original.width > raw.x + el.clientWidth + 1)) || (excess.y && !truncation(t.element, el, "y") && (t.original.y < raw.y - 1 || t.original.y + t.original.height > raw.y + el.clientHeight + 1))));
      if (escaped) add("CLIPPED TEXT", el, el.textContent, [shown], { reason: "overflow", axes: excess, scroll: { width: el.scrollWidth, height: el.scrollHeight }, client: { width: el.clientWidth, height: el.clientHeight } });
    }
    const interactive = el.matches("button,a,[role=button],[role=switch],[role=tab],[role=menuitem],input");
    if (interactive || el.matches("svg")) {
      const label = el.getAttribute("aria-label") || el.getAttribute("title") || el.textContent?.trim() || el.closest("button,a,[aria-label]")?.getAttribute("aria-label") || el.getAttribute("placeholder") || el.localName;
      contacts.push({ selector: selector(el), text: label.slice(0, 180), kind: interactive ? "control" : "svg", rect: shown });
      if (phone && interactive && s.pointerEvents !== "none" && !el.matches(":disabled,[aria-disabled=true]")) {
        const hitRects = [raw];
        // touch-box nới hộp thật; touch-hit / sonner nới bằng ::after. Đọc kích thước pseudo đã giải CSS.
        const owners = [el];
        // Checkbox trong ChapterPreview có nhãn touch-hit 48 px; toàn bộ nhãn bấm được, không chỉ ô vuông 14 px.
        if (el.matches('input[type="checkbox"],input[type="radio"]')) owners.push(...(el.labels ?? []));
        for (const owner of new Set(owners)) {
          const box = rect(owner.getBoundingClientRect());
          if (owner !== el) hitRects.push(box);
          for (const pseudo of ["::before", "::after"]) {
            const p = getComputedStyle(owner, pseudo);
            if (p.content === "none" || p.content === "normal" || p.pointerEvents === "none" || p.position !== "absolute") continue;
            const width = Number.parseFloat(p.width), height = Number.parseFloat(p.height);
            if (!(width > 0 && height > 0)) continue;
            let x = box.x + owner.clientLeft + (Number.parseFloat(p.left) || 0), y = box.y + owner.clientTop + (Number.parseFloat(p.top) || 0);
            if (p.transform && p.transform !== "none") { const m = new DOMMatrix(p.transform); x += m.e; y += m.f; }
            hitRects.push({ x, y, width, height });
          }
        }
        const hit = union(hitRects);
        if (hit.width < 44 - 0.01 || hit.height < 44 - 0.01) add("TOUCH TARGET", el, label, [shown], { hitRect: hit, touchBox: el.classList.contains("touch-box"), disabled: el.matches(":disabled,[aria-disabled=true]") });
      }
    }
  }
  const rows = new Map();
  for (const graphic of graphics.filter((g) => g.element.matches("svg"))) {
    let child = graphic.element, parent = child.parentElement;
    while (parent && !/^(inline-)?flex$/.test(css(parent).display)) { child = parent; parent = parent.parentElement; }
    if (!parent || css(parent).flexDirection.startsWith("column")) continue;
    if (!rows.has(parent)) rows.set(parent, []);
    rows.get(parent).push({ ...graphic, child, strokeWidth: css(graphic.element).strokeWidth || graphic.element.getAttribute("stroke-width") });
  }
  for (const [parent, icons] of rows) {
    if (icons.length < 2 || new Set(icons.map((i) => i.child)).size < 2) continue;
    // A leading status glyph, chevron and overflow menu have different roles. Compare
    // repeated instances of the same glyph and control role, never every SVG in a flex row.
    const roles = icons.map((g) => `${iconIdentity(g.element)}:${g.element.closest("button,a,[role=button]")?.getAttribute("data-icon-role") ?? g.child.localName}`);
    if (new Set(roles).size !== 1) continue;
    const sizes = icons.map((g) => rect(g.element.getBoundingClientRect()));
    if (Math.max(...sizes.map((s) => s.width)) - Math.min(...sizes.map((s) => s.width)) > 2 || Math.max(...sizes.map((s) => s.height)) - Math.min(...sizes.map((s) => s.height)) > 2 || new Set(icons.map((g) => g.strokeWidth)).size > 1) {
      add("ICON SIZE MISMATCH", parent, icons.map((g) => g.element.closest("[aria-label]")?.getAttribute("aria-label") ?? "svg").join(" · "), icons.map((g) => g.rect), { reason: "inconsistent", icons: icons.map((g, i) => ({ selector: selector(g.element), ...sizes[i], strokeWidth: g.strokeWidth })) });
    }
  }
  // Quy tắc 8–9: cùng vị trí con trong các hàng của MỘT danh sách, không gom SVG cả trang.
  const iconSelector = 'svg,img,canvas,[aria-hidden="true"]';
  function iconIdentity(el) {
    // A fixed slot is layout, not the glyph. Its contents can switch CSS VU bars to
    // a pause SVG without changing the wrapper's classes or child path.
    const nested = !el.matches("svg") && el.querySelector("svg,img,canvas");
    if (nested) return `slot:${iconIdentity(nested)}`;
    const named = [...el.classList].find((c) => c.startsWith("lucide-") && c !== "lucide-icon");
    if (named) return named;
    if (el.matches("svg")) return `svg:${[...el.querySelectorAll("path,rect,circle,ellipse,line,polyline,polygon,use")].map((p) => p.localName + (p.getAttribute("d") ?? p.getAttribute("points") ?? "")).join("|")}`;
    return `${el.localName}:${[...el.classList].filter((c) => !/^(w-|h-|size-|opacity-|text-|bg-)/.test(c)).join(".")}:${[...el.children].map((c) => c.localName).join(",")}`;
  }
  function iconBox(el) {
    if (el.matches("svg")) {
      // getBoundingClientRect của SVG là viewport, có thể có lề trống. Đo nét thực rồi đổi sang CSS px.
      try {
        const b = el.getBBox(), m = el.getScreenCTM();
        if (!m || !b.width || !b.height) return null;
        // getBBox mặc định bỏ nét viền. Bù nửa stroke ở mỗi mép trước khi đổi hệ toạ độ.
        const stroke = Math.max(0, ...[el, ...el.querySelectorAll("path,rect,circle,ellipse,line,polyline,polygon,use")]
          .filter((p) => css(p).stroke && css(p).stroke !== "none" && !hidden(p))
          .map((p) => Number.parseFloat(css(p).strokeWidth) || 0)) / 2;
        b.x -= stroke; b.y -= stroke; b.width += stroke * 2; b.height += stroke * 2;
        const points = [[b.x, b.y], [b.x + b.width, b.y], [b.x, b.y + b.height], [b.x + b.width, b.y + b.height]]
          .map(([x, y]) => ({ x: m.a * x + m.c * y + m.e, y: m.b * x + m.d * y + m.f, width: 0, height: 0 }));
        return visible(el, union(points), true);
      } catch { return null; }
    }
    if (el.matches("img,canvas")) return visible(el, rect(el.getBoundingClientRect()), true);
    // Biểu tượng CSS (vd các cột VU): hợp các phần có nét/nền, bỏ hộp căn giữa rỗng bên ngoài.
    const pieces = [...el.querySelectorAll("svg,img,canvas,*")].map((child) => {
      if (child.matches("svg,img,canvas")) return iconBox(child);
      if (child.closest("svg") || hidden(child) || color(css(child).backgroundColor)[3] === 0) return null;
      // Hit-test từng cột sẽ coi hộp chữ trong suốt chồng lên là che mất cột. Kiểm độ hiện của cả icon.
      return visible(el, rect(child.getBoundingClientRect()), true);
    }).filter(Boolean);
    if (color(css(el).backgroundColor)[3] > 0) pieces.push(visible(el, rect(el.getBoundingClientRect()), true));
    return union(pieces.filter(Boolean));
  }
  const shape = (el) => el.matches(iconSelector) ? "icon" : `${el.localName}[${el.getAttribute("role") ?? ""}](${[...el.childNodes]
    .filter((n) => n.nodeType === Node.ELEMENT_NODE || (n.nodeType === Node.TEXT_NODE && n.textContent.trim()))
    .map((n) => n.nodeType === Node.TEXT_NODE ? "text" : shape(n)).join(",")})`;
  function childPath(el, row) {
    const steps = [];
    for (let p = el; p !== row; p = p.parentElement) steps.unshift([...p.parentElement.children].indexOf(p));
    return steps.join("/");
  }
  function measurements(row) {
    const values = new Map();
    const put = (key, element, box, metric, value, identity) => values.set(key, { element, rect: box, metric, value, identity });
    const runs = texts.filter((t) => row.contains(t.element) && !t.element.closest('svg,[data-overlay],[aria-hidden="true"]'));
    const nodes = new Set();
    for (const run of runs) {
      // Tô đậm/tô từ trong câu liên tục không tạo thêm cột căn lề.
      if (run.element.matches('mark,strong,em,b,i') && css(run.element).display === 'inline'
        && [...run.element.parentElement.childNodes].some(node => node.nodeType === Node.TEXT_NODE && node.textContent.trim())) continue;
      if (nodes.has(run.element)) continue;
      nodes.add(run.element);
      // React commonly emits separate text nodes for a prefix, interpolated number and
      // punctuation. They are one label; a closing quote is not a separate aligned column.
      const box = union(runs.filter((t) => t.element === run.element).map((t) => t.original));
      const key = `text:${childPath(run.element, row)}`;
      let branch = run.element, parent = branch.parentElement;
      // Nhãn có thể là text node trực tiếp của flex button/a, không có span bọc.
      if (/^(inline-)?flex$/.test(css(run.element).display) && !css(run.element).flexDirection.startsWith("column")) { branch = run.node; parent = run.element; }
      while (parent && parent !== row.parentElement && (!/^(inline-)?flex$/.test(css(parent).display) || css(parent).flexDirection.startsWith("column"))) { branch = parent; parent = parent.parentElement; }
      if (parent === row.parentElement) parent = null;
      const adjacent = (direction) => {
        let node = branch[direction];
        while (node && node.nodeType !== Node.ELEMENT_NODE && !node.textContent.trim()) node = node[direction];
        return node;
      };
      const previous = adjacent("previousSibling");
      const trailing = css(run.element).textAlign === "right" || (parent && !adjacent("nextSibling") && previous?.nodeType === Node.ELEMENT_NODE &&
        (Number(css(previous).flexGrow) > 0 || previous.matches('[role="progressbar"]') || /space-between|flex-end/.test(css(parent).justifyContent)));
      const alignedRight = trailing || sAlign(run.element, row) === "right";
      const align = sAlign(run.element, row);
      // Centered labels vary with content length. Compare their center, not their left edge.
      const metric = alignedRight ? "text-right" : align === "center" ? "text-center" : "text-left";
      const rowBox = rect(row.getBoundingClientRect());
      // Nhãn nối đuôi một đoạn chữ trong cùng hàng flex (tên · "Nam"): mép trái theo độ dài chữ đứng trước, không phải một cột phải thẳng.
      const followsText = metric === "text-left" && parent && previous?.nodeType === Node.ELEMENT_NODE && !previous.matches(iconSelector) && previous.textContent.trim();
      if (!followsText) put(`${key}:${metric}`, run.element, box, metric, (alignedRight ? box.x + box.width : align === "center" ? box.x + box.width / 2 : box.x) - rowBox.x);
      if (!parent || previous?.nodeType !== Node.ELEMENT_NODE) continue;
      // Icon dẫn tới chữ đầu của nhánh theo sau nó, không tới mọi nhãn/metadata trong nhánh ấy.
      if (runs.find((t) => branch === t.node || branch.contains(t.element))?.node !== run.node) continue;
      const icons = [previous, ...previous.querySelectorAll(iconSelector)].filter((el) => el.matches(iconSelector));
      const icon = icons.map((element) => ({ element, box: iconBox(element) })).find((i) => i.box && i.box.width <= 32 && i.box.height <= 32 && i.box.x < box.x);
      if (icon) {
        const identity = iconIdentity(icon.element);
        put(`${key}:gap:${identity}`, icon.element, union([icon.box, box]), "icon-text-gap", box.x - icon.box.x - icon.box.width, identity);
        put(`icon:${childPath(icon.element, row)}:width:${identity}`, icon.element, icon.box, "icon-width", icon.box.width, identity);
        // Overflow into a label is a defect even when the peer uses a different status glyph.
        const gap = box.x - icon.box.x - icon.box.width;
        if (gap < -1.01) add("SIBLING CONSISTENCY", icon.element, row.textContent, [icon.box, box], { metric: "icon-text-overlap", value: gap, threshold: -1.01, reason: "painted icon extends into label", listSelector: selector(row.parentElement) });
      }
    }
    for (const el of row.querySelectorAll('[role="progressbar"],progress')) {
      const box = visible(el, rect(el.getBoundingClientRect()));
      if (box) put(`progress:${childPath(el, row)}`, el, box, "progress-right", box.x + box.width - row.getBoundingClientRect().x);
    }
    return values;
  }
  const siblingGroups = [];
  function sAlign(el, row) {
    for (let p = el; p && p !== row.parentElement; p = p.parentElement) {
      const s = css(p);
      if (s.textAlign === "center" || s.textAlign === "right") return s.textAlign;
      if (/flex|grid/.test(s.display) && (s.justifyContent === "center" || s.alignItems === "center" && s.flexDirection?.startsWith("column"))) return "center";
    }
    return "left";
  }
  for (const parent of all) {
    const groups = new Map();
    for (const row of parent.children) {
      if (!row.matches('li,button,a,[role="listitem"],[role="menuitem"],[role="option"]') || !visible(row, rect(row.getBoundingClientRect()))) continue;
      // Same DOM shape is insufficient: option/selected/disabled variants and text typography
      // represent different layouts. Exclude visibility state from the topology as well.
      const state = [...row.querySelectorAll("*")].concat(row).flatMap((el) => {
        const attributes = ["aria-selected","aria-pressed","aria-disabled","data-state"].filter((a) => el.hasAttribute(a)).map((a) => `${a}=${el.getAttribute(a)}`);
        if (el.matches(":disabled")) attributes.push("disabled");
        return attributes.length ? [`${el === row ? "" : childPath(el, row)}:${attributes.join(":")}`] : [];
      }).join("|");
      const typography = texts.filter((t) => row.contains(t.element) && !t.element.closest('[aria-hidden="true"],[data-overlay]')).map((t) => `${childPath(t.element, row)}:${css(t.element).fontSize}:${css(t.element).textAlign}`).filter((s, i, a) => a.indexOf(s) === i).join("|");
      const key = `${shape(row)}|${state}|${typography}`;
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(row);
    }
    for (const siblings of groups.values()) {
      if (siblings.length < 2) continue;
      const boxes = siblings.map((el) => rect(el.getBoundingClientRect()));
      // Thanh công cụ ngang / lưới thẻ không phải danh sách hàng dọc.
      if (boxes.some((b, i) => i > 0 && b.y < boxes[i - 1].y + boxes[i - 1].height - 1)) continue;
      const samples = siblings.map((row) => ({ row, index: [...parent.children].indexOf(row) + 1, values: measurements(row) }));
      siblingGroups.push({ selector: selector(parent), rows: samples.map((s) => ({ rowIndex: s.index, selector: selector(s.row), measurements: [...s.values.values()].map((v) => ({ selector: selector(v.element), metric: v.metric, value: v.value })) })) });
      for (const key of new Set(samples.flatMap((s) => [...s.values.keys()]))) {
        const corresponding = samples.filter((s) => s.values.has(key)).map((s) => ({ ...s.values.get(key), rowIndex: s.index }));
        for (const { sample, reference, delta } of siblingDifferences(corresponding)) {
          add(sample.metric === "icon-width" ? "OPTICAL SIZE CONSISTENCY" : "SIBLING CONSISTENCY", sample.element, siblings.find((row) => row.contains(sample.element)).textContent,
            [sample.rect, reference.rect], { rowIndex: sample.rowIndex, referenceRowIndex: reference.rowIndex, referenceSelector: selector(reference.element), metric: sample.metric, value: sample.value, referenceValue: reference.value, delta, tolerance: 1, listSelector: selector(parent) });
        }
      }
    }
  }
  const layout = layoutInspector?.({ all, texts, css, rect, union, visible, hidden, selector, add, shape, childPath });
  return { findings, contacts, overlays, siblingGroups, layout, metrics: { textRuns: texts.length, graphics: graphics.length, viewport, devicePixelRatio, theme: document.documentElement.dataset.theme, animations: document.getAnimations().map((a) => a.playState), fonts: [...document.fonts].filter((f) => f.status === "loaded").map((f) => ({ family: f.family, weight: f.weight, status: f.status })) } };
}
