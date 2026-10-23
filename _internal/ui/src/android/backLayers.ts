// Nút Back (và vuốt cạnh - Android gửi cùng một sự kiện) của điện thoại, theo đúng một thứ tự:
//   1. lớp trên cùng: hộp / menu / tấm trượt Radix (gửi Esc, đường bàn phím máy tính đang đi), hay lớp tự đăng ký (shared/backStack.ts:
//      panel trong màn Đang nghe, bước con trong hộp, khung ghép thiết bị…), hay thông báo có nút (Hoàn tác…);
//   2. trang trước trong lịch sử;
//   3. không có lịch sử (mở từ thông báo, file ngoài, app khôi phục): trang cha (Cài đặt › Giọng đọc -> Cài đặt -> Thư viện);
//   4. chỉ ở Thư viện mới thu nhỏ app.
// Radix đã giữ sẵn ngăn xếp lớp (DismissableLayer: chỉ lớp trên cùng nhận Esc), nên không đăng ký lại hàng chục Dialog/Sheet/Menu.
import { topBackLayer, type BackLayer } from "@/shared/backStack";
import { backOrder } from "@/shared/backOrder";
import { dismissToastElement } from "@/shared/toast";

/** Vai trò ARIA của nội dung các lớp Radix chặn thao tác phía dưới; tooltip cố ý không có trong đây. */
const LAYER_ROLES = new Set(["dialog", "alertdialog", "menu", "listbox"]);

type LayerElement = { getAttribute(name: string): string | null; contains?(other: unknown): boolean; getAnimations?(): { finish(): void }[] };
type LayerDocument = {
  querySelectorAll(selector: string): ArrayLike<LayerElement>;
  querySelector?(selector: string): unknown;
  dispatchEvent(event: Event): boolean;
};

/** Phần tử có phải nội dung một lớp đang mở (không phải lớp đang đóng dở trong hiệu ứng). */
export function isOpenLayer(element: LayerElement): boolean {
  return element.getAttribute("data-state") === "open" && LAYER_ROLES.has(element.getAttribute("role") ?? "");
}

/** Các lớp Radix đang mở theo thứ tự trong trang: Portal gắn lớp mở sau xuống cuối body, nên phần tử cuối là lớp trên cùng. */
export function openLayers(doc: LayerDocument = document): LayerElement[] {
  return Array.from(doc.querySelectorAll('[data-state="open"]')).filter(isOpenLayer);
}

export function hasOpenLayer(doc: LayerDocument = document): boolean {
  return openLayers(doc).length > 0;
}

/** Lớp Radix đã đóng mà còn trong trang để chạy hiệu ứng đóng (a120). Trong lúc ấy Radix vẫn coi nó là lớp "cao nhất": một Esc gửi cho hộp bên
 *  dưới sẽ bị bỏ qua - Back bấm nhanh hai lần (đóng menu rồi đóng hộp) mất lần thứ hai. */
export function closingLayers(doc: LayerDocument = document): LayerElement[] {
  return Array.from(doc.querySelectorAll('[data-state="closed"]')).filter((element) => LAYER_ROLES.has(element.getAttribute("role") ?? ""));
}

/** Gửi Esc cho lớp trên cùng; có lớp đang đóng dở thì chờ nó rời trang (tối đa `limit` ms - hiệu ứng đóng dài nhất 200 ms) rồi mới gửi. */
export function sendEscape(doc: LayerDocument, wait: (step: () => void) => void = (step) => window.setTimeout(step, 16), limit = 400): void {
  const send = () => doc.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true, cancelable: true }));
  if (!closingLayers(doc).length) {
    send();
    return;
  }
  // Back kế tiếp là ý định mới: kết thúc ảnh đang ra để Radix nhả lớp ngay ở nhịp kế, không bắt người dùng chờ hết 150–200 ms.
  for (const layer of closingLayers(doc)) {
    for (const animation of layer.getAnimations?.() ?? []) {
      try { animation.finish(); } catch { /* hoạt ảnh vừa bị huỷ */ }
    }
  }
  const started = Date.now();
  const check = () => {
    if (!closingLayers(doc).length || Date.now() - started >= limit) send();
    else wait(check);
  };
  wait(check);
}

/** Thông báo đang hiện có nút (Hoàn tác, Mở…): người dùng thấy như một hộp nổi, Back gỡ nó trước. */
export function hasActionToast(doc: LayerDocument = document): boolean {
  return Boolean(doc.querySelector?.("[data-sonner-toast]:not([data-removed='true']) [data-button]"));
}

/** Đóng lớp trên cùng nếu có; trả về true khi đã có lớp để đóng (Back không làm gì thêm). */
export function dismissTopLayer(
  doc: LayerDocument = document,
  top: BackLayer | undefined = topBackLayer(),
  _dismissToasts: () => void = () => undefined,
  wait?: (step: () => void) => void,
  dispatchEscape = true,
): boolean {
  const layers = openLayers(doc);
  const radixTop = layers[layers.length - 1];
  const selector = "[data-sonner-toast]:not([data-removed='true']) [data-button]";
  const toastButtons = Array.from(doc.querySelectorAll(selector)).filter((el) => el.getAttribute("data-button") !== null) as HTMLElement[];
  const toastButton = toastButtons.sort((a, b) => backOrder(b.closest("[data-sonner-toast]")) - backOrder(a.closest("[data-sonner-toast]")))[0]
    ?? doc.querySelector?.(selector) as HTMLElement | undefined;
  const toastElement = toastButton?.closest?.<HTMLElement>("[data-sonner-toast]");
  if (toastElement && backOrder(toastElement) > Math.max(top?.id ?? 0, backOrder(radixTop))) {
    if (dismissToastElement(toastElement)) return true;
    const close = toastElement.querySelector<HTMLButtonElement>("[data-close-button]");
    if (close) { close.click(); return true; }
  }
  // Lớp tự đăng ký đứng trên hộp Radix chỉ khi nó nằm TRONG hộp trên cùng (bước con của chính hộp ấy); còn lại hộp Radix mở sau, đóng trước.
  if (top && (!radixTop || radixTop.contains?.(top.element()) || (backOrder(radixTop) > 0 && top.id > backOrder(radixTop)))) {
    top.close();
    return true;
  }
  if (radixTop) {
    if (!dispatchEscape) return false; // Esc thật để Radix xử lý, không phát Esc đệ quy.
    sendEscape(doc, wait);
    return true;
  }
  if (top) {
    top.close();
    return true;
  }
  if (hasActionToast(doc)) {
    if (toastElement && dismissToastElement(toastElement)) return true;
    const close = toastElement?.querySelector<HTMLButtonElement>("[data-close-button]");
    if (close) close.click();
    return true;
  }
  return false;
}

/** Trang cha theo đường dẫn: /settings/voice -> /settings, /book/x/read/c -> /book/x, /book/x -> /, /settings -> /. */
export function parentPath(pathname: string): string {
  const parts = pathname.split("/").filter(Boolean);
  if (parts[0] === "book" && parts.length > 2) return `/book/${parts[1]}`;
  if (parts[0] === "settings" && parts.length > 1) return "/settings";
  return "/";
}

export type BackStep = { kind: "history" } | { kind: "replace"; to: string } | { kind: "minimize" };

/** Bước Back khi không còn lớp nào: `historyIndex` là vị trí trong lịch sử của Router (0 = trang đầu tiên của phiên). */
export function backStep(pathname: string, historyIndex: number): BackStep {
  if (pathname === "/" || pathname === "") return { kind: "minimize" };
  if (historyIndex > 0) return { kind: "history" };
  return { kind: "replace", to: parentPath(pathname) };
}

/** Vị trí trong lịch sử do react-router ghi vào history.state (`idx`). */
export function historyIndex(state: unknown = typeof window === "undefined" ? null : window.history.state): number {
  const idx = (state as { idx?: unknown } | null)?.idx;
  return typeof idx === "number" ? idx : 0;
}
