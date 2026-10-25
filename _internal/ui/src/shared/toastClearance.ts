import { useEffect } from "react";

/** Giữ thông báo ngoài nội dung bảng/hộp, kể cả popover không khoá body.
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
      const layers = [...document.querySelectorAll<HTMLElement>('[role="dialog"],[role="alertdialog"],[role="menu"],[role="listbox"]')]
        .filter(el => el.dataset.state !== "closed" && !el.closest('[hidden],[inert]') && getComputedStyle(el).display !== "none" && getComputedStyle(el).visibility === "visible");
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
        const top = Math.min(...boxes.map(r => r.top)) - current, bottom = Math.max(...boxes.map(r => r.bottom)) - current;
        const height = bottom - top;
        let spaces = [{ top: 16, bottom: innerHeight - 16 }];
        for (const layer of layers) {
          const r = layer.getBoundingClientRect();
          // Bỏ riêng transform vào/ra của tấm; dùng vị trí đích ngay lúc bảng bắt đầu mở.
          const matrix = new DOMMatrixReadOnly(getComputedStyle(layer).transform === "none" ? undefined : getComputedStyle(layer).transform);
          const origin = getComputedStyle(layer).transformOrigin.split(" ").map(parseFloat);
          const layerTop = r.top - matrix.m42 - (1 - matrix.m22) * origin[1];
          const layerBottom = layerTop + layer.offsetHeight;
          if (!r.width || !r.height || r.right <= left || r.left >= right || layerBottom <= 0 || layerTop >= innerHeight) continue;
          spaces = spaces.flatMap(space => [
            { top: space.top, bottom: Math.min(space.bottom, layerTop - 16) },
            { top: Math.max(space.top, layerBottom + 16), bottom: space.bottom },
          ]).filter(space => space.bottom - space.top >= height);
        }
        const targets = spaces.filter(space => space.bottom - space.top >= height)
          .map(space => Math.max(space.top, Math.min(top, space.bottom - height)));
        // Hộp chiếm hết màn: mờ thông báo tạm thời, hiện lại khi có chỗ, không che mục trong hộp.
        const hidden = layers.length > 0 && !targets.length;
        const shift = layers.length && targets.length ? Math.round(targets.sort((a, b) => Math.abs(a - top) - Math.abs(b - top))[0] - top) : 0;
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
    };
    const schedule = () => { if (!frame) frame = requestAnimationFrame(update); };
    const observer = new MutationObserver(schedule);
    observer.observe(document.body, { subtree: true, childList: true, attributes: true, attributeFilter: ["data-state", "data-mounted", "data-removed", "data-visible", "style"] });
    window.addEventListener("resize", schedule);
    document.addEventListener("animationend", schedule, true);
    schedule();
    return () => {
      observer.disconnect(); resize.disconnect(); cancelAnimationFrame(frame);
      for (const fade of fades.values()) fade.cancel();
      window.removeEventListener("resize", schedule);
      document.removeEventListener("animationend", schedule, true);
    };
  }, []);
}
