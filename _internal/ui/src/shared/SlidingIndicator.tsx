import { useLayoutEffect, useRef } from "react";
import { cn } from "./cn";

const ACTIVE = '[aria-checked="true"], [aria-pressed="true"], [aria-selected="true"], [data-state="active"]';

/** Gạch chân của mục đang chọn LƯỚT từ mục cũ sang mục mới, không bật/tắt tại chỗ (chủ sách 23-10, 25-10: "tuyệt đối không thích bật tắt").
 *  Đặt làm con của khung `relative` chứa các mục (hàng tab, hàng lọc, ChoiceRow); tự tìm mục đang chọn, đo vị trí theo khung, dời bằng transform.
 *  Lần đặt đầu (mở trang, khung vừa hiện) không lướt - chỉ lướt khi người dùng đổi mục; gạch chân 2 px ở đáy mục. */
export function SlidingIndicator({ variant, className }: { variant: "line"; className?: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  useLayoutEffect(() => {
    const bar = ref.current;
    const host = bar?.parentElement;
    if (!bar || !host) return;
    let placed = false;
    let frame = 0;
    const items = new Set<Element>();
    const resize = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(() => schedule());
    const place = () => {
      frame = 0;
      for (const child of Array.from(host.children)) if (child !== bar && !items.has(child)) { items.add(child); resize?.observe(child); }
      const active = Array.from(host.querySelectorAll<HTMLElement>(ACTIVE)).find((element) => element !== bar && element.offsetParent === host);
      if (!active || !active.offsetWidth) { bar.style.opacity = "0"; placed = false; return; }
      const height = 2;
      const top = active.offsetTop + active.offsetHeight - 2;
      // Gạch chân dài đúng bằng chữ khi mục rộng hơn chữ (tab chia đều trên điện thoại): đo phần tử [data-indicator-target] trong mục.
      // Dùng offset (không dùng getBoundingClientRect) để không lệch khi cả trang đang phóng / trượt vào.
      const target = active.querySelector<HTMLElement>("[data-indicator-target]");
      const inner = target && target.offsetParent === active ? target : null;
      if (!placed) bar.style.transition = "none";
      bar.style.transform = `translate(${active.offsetLeft + (inner?.offsetLeft ?? 0)}px, ${top}px)`;
      bar.style.width = `${inner?.offsetWidth ?? active.offsetWidth}px`;
      bar.style.height = `${height}px`;
      bar.style.opacity = "1";
      if (!placed) { void bar.offsetWidth; bar.style.transition = ""; placed = true; }
    };
    const schedule = () => { if (!frame) frame = requestAnimationFrame(place); };
    place();
    resize?.observe(host);
    const mutations = new MutationObserver(schedule);
    mutations.observe(host, { subtree: true, childList: true, attributes: true, attributeFilter: ["aria-checked", "aria-pressed", "aria-selected", "data-state"] });
    void document.fonts?.ready.then(schedule);
    return () => { cancelAnimationFrame(frame); mutations.disconnect(); resize?.disconnect(); };
  }, [variant]);
  return (
    <span
      ref={ref}
      aria-hidden
      data-sliding-indicator={variant}
      className={cn(
        "pointer-events-none absolute left-0 top-0 opacity-0 transition-[transform,width,height,opacity] duration-motion-medium ease-standard motion-reduce:transition-[opacity]",
        "bg-accent",
        className,
      )}
    />
  );
}
