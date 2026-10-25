// Quy tắc 15: không dùng visible() có hit-test, vì chính lớp mất chạm cần bị bắt.
export function inspectTapReach({ css, rect, selector, add }) {
  const roles = '[role="dialog"],[role="alertdialog"],[role="menu"],[role="listbox"]';
  const controls = 'button,a[href],input,textarea,select,[role="button"],[role="menuitem"],[role="menuitemcheckbox"],[role="menuitemradio"],[role="option"],[role="tab"],[role="switch"],[role="checkbox"],[role="radio"],[role="slider"]';
  const shown = (el) => {
    let opacity = 1;
    for (let p = el; p; p = p.parentElement) {
      const s = css(p);
      opacity *= Number(s.opacity);
      if (s.display === "none" || s.visibility !== "visible" || p.hidden || p.inert || p.matches(roles) && p.dataset.state === "closed" || opacity < 0.05) return false;
      if (/^rect\(0px[, ]+0px[, ]+0px[, ]+0px\)$/.test(s.clip) || /^inset\(50%\)/.test(s.clipPath)) return false;
    }
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  };
  const inView = (el) => { const r = el.getBoundingClientRect(); return r.right > 0 && r.bottom > 0 && r.left < innerWidth && r.top < innerHeight; };
  const layers = [...document.querySelectorAll(roles)].filter((el) => shown(el) && inView(el));
  const layer = layers.filter((el) => !layers.some((other) => el !== other && el.contains(other))).at(-1)
    ?? [...document.querySelectorAll('main,[role="main"]')].filter((el) => shown(el) && inView(el)).at(-1);
  const toasts = [...document.querySelectorAll('[data-sonner-toast]:not([data-removed="true"]):not([data-visible="false"])')].filter((el) => shown(el) && inView(el));
  const tapToastOcclusions = [];
  // Toast là lớp phụ độc lập: nút đóng / Hoàn tác vẫn phải nhận chạm trong chính toast.
  for (const scope of [layer, ...toasts].filter(Boolean)) for (const el of scope.querySelectorAll(`${controls},[tabindex]`)) {
    if (scope === layer && el.closest("[data-sonner-toast]")) continue;
    if (!shown(el) || el.matches(":disabled,[disabled],[data-disabled]") || el.closest('[inert],[aria-disabled="true"]') || el.getAttribute("tabindex") === "-1" && !el.matches(controls)) continue;
    const box = el.getBoundingClientRect(), x = box.left + box.width / 2, y = box.top + box.height / 2;
    if (x < 0 || y < 0 || x >= innerWidth || y >= innerHeight) continue;
    // Chỉ miễn vùng cuộn thuộc lớp này; không bỏ qua lớp bị scrim che. Xét MỌI vùng cuộn tổ tiên trong lớp: hàng lọc cuộn ngang nằm trong trang
    // cuộn dọc, tâm đã khuất dưới mép trang (dưới thanh tab) là hàng cần cuộn tới - từng chỉ xét vùng gần nhất (chính hàng lọc) rồi dừng.
    let clipped = false;
    for (let p = el.parentElement; p && scope.contains(p) && !clipped; p = p.parentElement) {
      const s = css(p), r = p.getBoundingClientRect();
      const scrollX = /auto|scroll/.test(s.overflowX), scrollY = /auto|scroll/.test(s.overflowY);
      if (scrollX || scrollY) {
        // Tâm sát mép client trong 2 px cũng là hàng cần cuộn tới (kể cả vạch tiến độ đè 1–2 px).
        clipped = scrollX && (x <= r.left + p.clientLeft + 2 || x >= r.left + p.clientLeft + p.clientWidth - 2)
          || scrollY && (y <= r.top + p.clientTop + 2 || y >= r.top + p.clientTop + p.clientHeight - 2);
      }
    }
    if (clipped) continue;
    const hit = document.elementFromPoint(x, y), pe = css(el).pointerEvents;
    // Input phủ bởi chính label vẫn nhận thao tác qua hành vi mặc định của trình duyệt.
    const label = hit?.closest("label");
    if (el.matches("input") && label && scope.contains(label) && (label.control === el || label.contains(el))) continue;
    const toast = hit?.closest('[data-sonner-toast]');
    if (pe !== "none" && scope === layer && !layer.matches(roles) && toasts.includes(toast)) {
      // Trang thường bị thông báo tạm che là đúng thiết kế; vẫn giữ bằng chứng trong chi tiết khung.
      tapToastOcclusions.push({ selector: selector(el), text: (el.getAttribute("aria-label") || el.textContent || el.localName).trim(), rect: rect(box), toastSelector: selector(toast), hitSelector: selector(hit), pointerEvents: pe });
      continue;
    }
    if (pe === "none" || !hit || !scope.contains(hit) || scope === layer && layer.matches(roles) && toasts.includes(toast)) {
      const labelled = el.getAttribute("aria-labelledby")?.split(/\s+/).map((id) => document.getElementById(id)?.textContent ?? "").join(" ");
      const text = el.getAttribute("aria-label") || labelled || [...(el.labels ?? [])].map((label) => label.textContent).join(" ") || el.textContent || el.getAttribute("placeholder") || el.localName;
      add("TAP REACH", el, text, [rect(box)], { pointerEvents: pe, hitSelector: hit ? selector(hit) : null,
        hitText: hit ? (hit.getAttribute("aria-label") || hit.textContent || hit.localName).trim().slice(0, 160) : null, layerSelector: selector(scope) });
    }
  }
  return { tapLayer: layer ? selector(layer) : null, tapToastOcclusions };
}
