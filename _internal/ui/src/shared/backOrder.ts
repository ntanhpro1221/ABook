// Một đồng hồ cho lớp DOM (Radix/toast) và lớp state; chỉ lớp có hành động mới chặn Back.
let sequence = 0;
const orders = new WeakMap<object, number>();
export const nextBackOrder = () => ++sequence;
export const backOrder = (element: object | null | undefined) => element ? orders.get(element) ?? 0 : 0;
export function markBackOpen(element: object): number {
  const order = backOrder(element) || nextBackOrder();
  orders.set(element, order);
  return order;
}

export function installBackOrder(doc: Document = document): () => void {
  let previous = new Set<Element>();
  const scan = () => {
    const current = new Set(Array.from(doc.querySelectorAll('[data-state="open"][role="dialog"], [data-state="open"][role="alertdialog"], [data-state="open"][role="menu"], [data-state="open"][role="listbox"], [data-sonner-toast]:not([data-removed="true"])')).filter((el) =>
      !el.closest('[inert], [aria-hidden="true"]') && (!el.hasAttribute("data-sonner-toast") || Boolean(el.querySelector("[data-button]"))),
    ));
    for (const el of previous) if (!current.has(el)) orders.delete(el);
    // Sonner chèn toast mới lên đầu DOM: cùng một commit thì đánh dấu cũ trước.
    for (const el of Array.from(current).sort((a, b) => Number(b.getAttribute("data-index")) - Number(a.getAttribute("data-index")))) markBackOpen(el);
    previous = current;
  };
  scan();
  const observer = new MutationObserver(scan);
  observer.observe(doc.body, { subtree: true, childList: true, attributes: true, attributeFilter: ["data-state", "data-removed"] });
  return () => { observer.disconnect(); for (const el of previous) orders.delete(el); };
}
