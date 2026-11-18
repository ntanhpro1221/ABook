import { useCallback, useEffect, useRef, useState, type Ref } from "react";

// Bấm ra ngoài một lớp nổi (menu, Popover) chỉ ĐÓNG lớp, không tới thứ nằm dưới - cùng luật với Qt (Backdrop) và Android (SortMenu, nền của tấm).
// Soát 18-11 lần 4: Radix không modal (modal={false}, mọi Popover) để cú bấm ra ngoài đi tiếp - menu "Xếp theo" đóng VÀ cuốn sách dưới mở ra; còn
// modal thì khoá pointer-events / cuộn trên body (tính lại style cả trang). Ở đây: một lớp trong suốt phủ cả cửa sổ, chèn NGAY TRƯỚC khung popper của
// lớp trong body, cùng z-index (vẽ dưới bảng, trên mọi thứ đã có). Nó ở ngoài cả DOM lẫn cây React của bảng, nên Radix vẫn thấy cú nhấn "ra ngoài" và
// tự đóng (chuột lẫn chạm); còn cú bấm, hover, chuột phải, lăn thì dừng ở lớp này.
// Soát Chromium thật 18-11: Radix đóng menu ngay ở pointerdown; nếu lớp thôi bắt ngay lúc ấy thì phần CÒN LẠI của chính cú nhấn - mousedown/mouseup/
// click giả lập sau một cú CHẠM, contextmenu sau chuột phải - được trình duyệt dò lại vị trí và rơi xuống thẻ sách / nút "Về Thư viện" / câu trong
// trang đọc. Nên cú nhấn bắt đầu trên lớp giữ lớp (cả khi bảng đã đóng hay đã rời cây) tới khi nó xong (click / contextmenu / pointercancel) hoặc quá
// GESTURE_MS; sự kiện vẫn nổi lên document như thường (Radix đếm cú nhấn ngoài bị chặn thì KHÔNG đóng - đừng stopPropagation).
const GESTURE_MS = 1000;

/** Lớp chặn -> bảng sở hữu nó. Lớp nổi lồng trong lớp khác (Popover trong hộp thoại, Popover trong Popover) bỏ qua lớp chặn không phải của mình. */
const owners = new WeakMap<Element, Element>();

/** Cú nhấn trúng lớp chặn của một lớp nổi KHÁC: lớp ấy nằm trên và tự đóng; lớp ở dưới (hộp thoại, tấm, Popover cha) đứng yên. */
export function pressedForeignShield(target: EventTarget | null, own?: Element | null): boolean {
  const cover = target instanceof Element ? target.closest("[data-outside-shield]") : null;
  return !!cover && owners.get(cover) !== own;
}

export function attachOutsideShield(content: HTMLElement): () => void {
  const wrapper = content.closest<HTMLElement>("[data-radix-popper-content-wrapper]");
  const doc = content.ownerDocument;
  // Bảng không đưa ra body (nằm trong tấm của điện thoại, hay không có Portal): lớp chứa nó tự lo phần ngoài.
  if (!wrapper || wrapper.parentElement !== doc.body) return () => undefined;
  const cover = doc.createElement("div");
  cover.setAttribute("data-outside-shield", "");
  cover.setAttribute("aria-hidden", "true");
  owners.set(cover, content);
  const z = doc.defaultView?.getComputedStyle(content).zIndex;
  Object.assign(cover.style, { position: "fixed", top: "0", right: "0", bottom: "0", left: "0", zIndex: z && z !== "auto" ? z : "50", pointerEvents: "auto", touchAction: "none", cursor: "default" });
  const stop = (event: Event) => event.preventDefault();
  cover.addEventListener("wheel", stop, { passive: false });
  cover.addEventListener("contextmenu", stop);
  let held = false;
  let gone = false;
  let timer: ReturnType<typeof setTimeout> | undefined;
  const sync = () => {
    if (gone && !held) { cover.remove(); return; }
    cover.style.pointerEvents = content.getAttribute("data-state") === "closed" && !held ? "none" : "auto";
  };
  const release = () => { held = false; clearTimeout(timer); sync(); };
  cover.addEventListener("pointerdown", () => { held = true; clearTimeout(timer); timer = setTimeout(release, GESTURE_MS); });
  // Thả sau khi sự kiện kết thúc cú nhấn đã đi hết đường (Radix hoãn việc đóng Popover tới chính "click" này).
  for (const type of ["click", "contextmenu", "auxclick", "pointercancel"]) cover.addEventListener(type, () => { setTimeout(release, 0); });
  wrapper.before(cover);
  const watch = new MutationObserver(sync);
  watch.observe(content, { attributes: true, attributeFilter: ["data-state"] });
  return () => { watch.disconnect(); gone = true; sync(); };
}

type OutsideEvent = { target: EventTarget | null; preventDefault: () => void };

/** Cho Content của lớp nổi: `ref` gắn lớp chặn khi bảng có mặt, gỡ khi bảng rời cây (đã gộp với ref của nơi gọi); `onInteractOutside` bỏ qua
 *  cú nhấn trúng lớp chặn của lớp nổi lồng bên trong rồi mới gọi handler của nơi gọi. */
export function useOutsideShield<T extends HTMLElement, E extends OutsideEvent>(forwarded: Ref<T>, onInteractOutside?: (event: E) => void) {
  const [node, setNode] = useState<T | null>(null);
  const own = useRef<T | null>(null);
  useEffect(() => (node ? attachOutsideShield(node) : undefined), [node]);
  const ref = useCallback((value: T | null) => {
    own.current = value;
    setNode(value);
    if (typeof forwarded === "function") forwarded(value);
    else if (forwarded) (forwarded as { current: T | null }).current = value;
  }, [forwarded]);
  const guard = useCallback((event: E) => {
    if (pressedForeignShield(event.target, own.current)) { event.preventDefault(); return; }
    onInteractOutside?.(event);
  }, [onInteractOutside]);
  return { ref, onInteractOutside: guard };
}
