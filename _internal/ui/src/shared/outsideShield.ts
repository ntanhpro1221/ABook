import { useCallback, useEffect, useState, type Ref } from "react";

// Bấm ra ngoài một lớp nổi (menu, Popover) chỉ ĐÓNG lớp, không tới thứ nằm dưới - cùng luật với Qt (Backdrop) và Android (SortMenu, nền của tấm).
// Soát 18-11 lần 4: Radix không modal (modal={false}, mọi Popover) để cú bấm ra ngoài đi tiếp - menu "Xếp theo" đóng VÀ cuốn sách dưới mở ra; còn
// modal thì khoá pointer-events / cuộn trên body (tính lại style cả trang). Ở đây: một lớp trong suốt phủ cả cửa sổ, chèn NGAY TRƯỚC khung popper của
// lớp trong body, cùng z-index (vẽ dưới bảng, trên mọi thứ đã có). Nó ở ngoài cả DOM lẫn cây React của bảng, nên Radix vẫn thấy cú nhấn "ra ngoài" và
// tự đóng (chuột lẫn chạm); còn cú bấm, hover, chuột phải, lăn thì dừng ở lớp này. Bảng bắt đầu đóng (data-state="closed") thì lớp thôi bắt.
export function attachOutsideShield(content: HTMLElement): () => void {
  const wrapper = content.closest<HTMLElement>("[data-radix-popper-content-wrapper]");
  const doc = content.ownerDocument;
  // Bảng không đưa ra body (nằm trong tấm của điện thoại, hay không có Portal): lớp chứa nó tự lo phần ngoài.
  if (!wrapper || wrapper.parentElement !== doc.body) return () => undefined;
  const cover = doc.createElement("div");
  cover.setAttribute("data-outside-shield", "");
  cover.setAttribute("aria-hidden", "true");
  const z = doc.defaultView?.getComputedStyle(content).zIndex;
  Object.assign(cover.style, { position: "fixed", top: "0", right: "0", bottom: "0", left: "0", zIndex: z && z !== "auto" ? z : "50", pointerEvents: "auto", touchAction: "none", cursor: "default" });
  const stop = (event: Event) => event.preventDefault();
  cover.addEventListener("wheel", stop, { passive: false });
  cover.addEventListener("contextmenu", stop);
  wrapper.before(cover);
  const closing = () => { cover.style.pointerEvents = content.getAttribute("data-state") === "closed" ? "none" : "auto"; };
  const watch = new MutationObserver(closing);
  watch.observe(content, { attributes: true, attributeFilter: ["data-state"] });
  return () => { watch.disconnect(); cover.remove(); };
}

/** Ref cho Content của lớp nổi: gắn lớp chặn khi bảng có mặt, gỡ khi bảng rời cây. Trả về ref đã gộp với ref của nơi gọi. */
export function useOutsideShield<T extends HTMLElement>(forwarded: Ref<T>): (node: T | null) => void {
  const [node, setNode] = useState<T | null>(null);
  useEffect(() => (node ? attachOutsideShield(node) : undefined), [node]);
  return useCallback((value: T | null) => {
    setNode(value);
    if (typeof forwarded === "function") forwarded(value);
    else if (forwarded) (forwarded as { current: T | null }).current = value;
  }, [forwarded]);
}
