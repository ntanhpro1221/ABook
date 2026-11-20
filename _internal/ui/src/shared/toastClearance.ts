import { useEffect } from "react";

/** Recover layout coordinates before rounding the final shift. CSSOM serializes
 * animated translate with less precision than getBoundingClientRect: a 750.5px
 * base otherwise flips across .5 and restarts the 25px/26px transition forever. */
export function toastBaseBounds(top: number, bottom: number, translate: number) {
  const layout = (coordinate: number) => layoutCoordinate(coordinate - translate);
  return { top: layout(top), bottom: layout(bottom) };
}

export const layoutCoordinate = (coordinate: number) => Math.round(coordinate * 64) / 64;

/** Keep the committed target across half-pixel noise, including one layout unit.
 * Returning to the resting position must still clear the shift immediately. */
export function nextToastShift(wanted: number, committed: number) {
  return wanted !== 0 && Math.abs(wanted - committed) <= 0.5 + 1 / 64 ? committed : Math.round(wanted);
}

type Span = { top: number; bottom: number };

/** Dịch chuyển (px) đưa khối thông báo [top, top + height) ra khỏi mọi vật cản, tới khoảng trống gần nhất trong màn (lề 16);
 *  `hidden` khi có vật cản mà không còn khoảng nào đủ cao. Vật cản đã lọc theo chiều ngang của khối thông báo; `active` = đang có lớp/vùng cần tránh. */
export function toastPlacement(top: number, height: number, obstacles: readonly Span[], viewportHeight: number, active = obstacles.length > 0) {
  let spaces: Span[] = [{ top: 16, bottom: viewportHeight - 16 }];
  for (const o of obstacles) {
    spaces = spaces.flatMap(space => [
      { top: space.top, bottom: Math.min(space.bottom, o.top - 16) },
      { top: Math.max(space.top, o.bottom + 16), bottom: space.bottom },
    ]).filter(space => space.bottom - space.top >= height);
  }
  const targets = spaces.map(space => Math.max(space.top, Math.min(top, space.bottom - height)));
  const hidden = active && !targets.length;
  const wanted = active && targets.length ? targets.sort((a, b) => Math.abs(a - top) - Math.abs(b - top))[0] - top : 0;
  return { wanted, hidden };
}

/** Vùng điều khiển của trang mà thông báo không được che (DESIGN 6 Toast: "không được che nút"), ví dụ hàng nút của trình phát đầy đủ
 *  trên điện thoại nằm đúng chỗ thông báo đáy. Đánh dấu `data-toast-avoid` trên chính vùng có nút; vùng ẩn/inert không tính. */
export const TOAST_AVOID = "[data-toast-avoid]";

/** Bề mặt/khung nhận tiêu điểm bằng mã (trang, tấm, hộp, danh sách) không phải một nút: coi cả khung là vật cản thì thông báo hết chỗ. */
const FOCUS_SURFACE = 'html,body,main,section,[role="main"],[role="dialog"],[role="alertdialog"],[role="menu"],[role="listbox"],[role="region"],[data-sonner-toaster],[data-sonner-toaster] *';

/** Nút đang giữ tiêu điểm cũng là vật cản (soát a67: tiêu điểm không bao giờ nằm dưới thông báo). Thông báo tự dịch đi, trang KHÔNG cuộn vì thông
 *  báo (gate 24: tiêu điểm trở về hàng sách sau khi đóng Đang nghe, toaster còn đang dịch -188 px tránh hàng nút của màn ấy, bộ cuộn-tránh-thông-báo
 *  cũ cuộn trang 26 px và mọi mốc của trang lệch theo). */
function focusedControl(): HTMLElement | null {
  const el = document.activeElement;
  return el instanceof HTMLElement && !el.matches(FOCUS_SURFACE) ? el : null;
}

/** Giữ thông báo ngoài nội dung bảng/hộp, kể cả popover không khoá body, và ngoài các vùng điều khiển `data-toast-avoid`.
 *  Dịch cả toaster để Sonner giữ nguyên thứ tự, vuốt đóng và chuyển động của từng toast. */
export function useToastClearance(): void {
  useEffect(() => {
    let frame = 0;
    const resize = new ResizeObserver(() => schedule());
    const watched = new Set<Element>();
    const fades = new Map<HTMLElement, Animation>();
    const update = () => {
      frame = 0;
      // Không có thông báo: thôi luôn - quan sát style của cả trang chạy theo thanh tiến độ trình phát, không được đo layout mỗi khung.
      if (!document.querySelector('[data-sonner-toast][data-mounted="true"]:not([data-removed="true"])')) return;
      const focused = focusedControl();
      const layers = [...document.querySelectorAll<HTMLElement>(`[role="dialog"],[role="alertdialog"],[role="menu"],[role="listbox"],${TOAST_AVOID}`), ...(focused ? [focused] : [])]
        .filter(el => el.dataset.state !== "closed" && !el.closest('[hidden],[inert],[aria-hidden="true"]') && getComputedStyle(el).display !== "none" && getComputedStyle(el).visibility === "visible");
      const toasters = [...document.querySelectorAll<HTMLElement>("[data-sonner-toaster]")];
      for (const [el, fade] of fades) if (!el.isConnected) { fade.cancel(); fades.delete(el); }
      const observed = new Set<Element>([...layers, ...toasters.flatMap(el => [...el.querySelectorAll("[data-sonner-toast]")])]);
      for (const el of watched) if (!observed.has(el)) { resize.unobserve(el); watched.delete(el); }
      for (const el of observed) if (!watched.has(el)) { resize.observe(el); watched.add(el); }
      for (const toaster of toasters) {
        const toasts = [...toaster.querySelectorAll<HTMLElement>('[data-sonner-toast][data-mounted="true"]:not([data-removed="true"]):not([data-visible="false"])')];
        if (!toasts.length) continue;
        const boxes = toasts.map(el => el.getBoundingClientRect());
        const left = Math.min(...boxes.map(r => r.left)), right = Math.max(...boxes.map(r => r.right));
        const current = parseFloat(getComputedStyle(toaster).translate.split(/\s+/)[1]) || 0;
        const { top, bottom } = toastBaseBounds(Math.min(...boxes.map(r => r.top)), Math.max(...boxes.map(r => r.bottom)), current);
        const height = bottom - top;
        const obstacles: Span[] = [];
        for (const layer of layers) {
          const r = layer.getBoundingClientRect();
          // Bỏ riêng transform vào/ra của tấm; dùng vị trí đích ngay lúc bảng bắt đầu mở.
          const matrix = new DOMMatrixReadOnly(getComputedStyle(layer).transform === "none" ? undefined : getComputedStyle(layer).transform);
          const origin = getComputedStyle(layer).transformOrigin.split(" ").map(parseFloat);
          const layerTop = layoutCoordinate(r.top - matrix.m42 - (1 - matrix.m22) * origin[1]);
          const layerBottom = layerTop + layer.offsetHeight;
          if (!r.width || !r.height || r.right <= left || r.left >= right || layerBottom <= 0 || layerTop >= innerHeight) continue;
          obstacles.push({ top: layerTop, bottom: layerBottom });
        }
        // Hộp chiếm hết màn: mờ thông báo tạm thời, hiện lại khi có chỗ, không che mục trong hộp.
        const { wanted, hidden } = toastPlacement(top, height, obstacles, innerHeight, layers.length > 0);
        const shift = nextToastShift(wanted, Number.parseFloat(toaster.style.getPropertyValue("--toast-shift")) || 0);
        // Hộp đổi cỡ ngay trong lúc fade vào: bỏ fade cũ trước khi ẩn, không để nó làm toast sáng lại trên hộp.
        if (hidden || toaster.style.getPropertyValue("--toast-shift") !== `${shift}px`) { fades.get(toaster)?.cancel(); fades.delete(toaster); }
        if (toaster.style.getPropertyValue("--toast-shift") !== `${shift}px`) {
          toaster.style.setProperty("--toast-shift", `${shift}px`);
          if (!hidden && matchMedia("(prefers-reduced-motion: reduce)").matches) {
            const fade = toaster.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 120 });
            fades.set(toaster, fade);
            fade.onfinish = () => fades.delete(toaster);
          }
        }
        if (toaster.dataset.toastObscured !== String(hidden)) toaster.dataset.toastObscured = String(hidden);
        toaster.inert = hidden;
      }
      // Re-measure moving toast/surface bounds until their animations finish. Layer order
      // keeps controls safe on every intermediate frame, before clearance has settled.
      if ([...layers, ...toasters].some(el => (el.getAnimations?.({ subtree: true }) ?? []).some(a =>
        a.playState === "running" && a.effect?.getComputedTiming().iterations !== Infinity))) schedule();
    };
    const schedule = () => { if (!frame) frame = requestAnimationFrame(update); };
    const observer = new MutationObserver(schedule);
    observer.observe(document.body, { subtree: true, childList: true, attributes: true, attributeFilter: ["data-state", "data-mounted", "data-removed", "data-visible", "style", "inert", "aria-hidden"] });
    window.addEventListener("resize", schedule);
    document.addEventListener("animationend", schedule, true);
    document.addEventListener("focusin", schedule);
    document.addEventListener("focusout", schedule);
    schedule();
    return () => {
      observer.disconnect(); resize.disconnect(); cancelAnimationFrame(frame);
      for (const fade of fades.values()) fade.cancel();
      window.removeEventListener("resize", schedule);
      document.removeEventListener("animationend", schedule, true);
      document.removeEventListener("focusin", schedule);
      document.removeEventListener("focusout", schedule);
    };
  }, []);
}
