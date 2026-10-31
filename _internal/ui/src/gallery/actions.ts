// Thao tác trên trang đã dựng để đưa nó tới trạng thái của mục trưng bày (mở menu, mở hộp thoại, gõ chữ...): bấm như người dùng
// bấm, tìm phần tử theo nhãn trợ năng hay chữ hiện ra - không với vào trong thành phần của app.

const CLICKABLE = "button, a, [role=button], [role=menuitem], [role=menuitemradio], [role=tab], [role=option], [role=switch], [role=radio], summary, label";

export async function waitFor<T>(find: () => T | null | undefined | false, what: string, timeout = 6000): Promise<T> {
  const started = performance.now();
  for (;;) {
    const found = find();
    if (found) return found;
    if (performance.now() - started > timeout) throw new Error(`Không thấy ${what}`);
    await new Promise((resolve) => setTimeout(resolve, 40));
  }
}

const norm = (text: string | null | undefined) => (text ?? "").replace(/\s+/g, " ").trim();

function matches(element: Element, target: string | RegExp): boolean {
  const names = [element.getAttribute("aria-label"), element.getAttribute("title"), element.textContent].map(norm);
  return names.some((name) => (typeof target === "string" ? name === target : target.test(name)));
}

function visible(element: Element): boolean {
  if (element.closest("[inert], [aria-hidden=true]")) return false;
  // happy-dom / jsdom (test) không bố cục - mọi hộp 0x0: coi như thấy.
  if (/HappyDOM|jsdom/.test(navigator.userAgent)) return true;
  const rect = element.getBoundingClientRect();
  return rect.width > 0 || rect.height > 0;
}

/** Phần tử bấm được có nhãn / chữ đúng `target` (chuỗi: trùng hẳn; RegExp: khớp). Lấy cái sau cùng trong cây: lớp mở sau (menu, hộp) nằm cuối. */
export function find(target: string | RegExp, within: ParentNode = document): HTMLElement | null {
  const all = [...within.querySelectorAll<HTMLElement>(CLICKABLE)].filter((element) => matches(element, target) && visible(element));
  return all[all.length - 1] ?? null;
}

export function findText(target: string | RegExp, within: ParentNode = document): boolean {
  const text = norm((within as Element).textContent ?? document.body.textContent);
  return typeof target === "string" ? text.includes(target) : target.test(text);
}

function press(element: HTMLElement): void {
  const init = { bubbles: true, cancelable: true, composed: true, button: 0, buttons: 1, pointerId: 1, pointerType: "mouse", isPrimary: true };
  const Pointer = typeof PointerEvent === "function" ? PointerEvent : MouseEvent;
  element.dispatchEvent(new Pointer("pointerdown", init));
  element.dispatchEvent(new MouseEvent("mousedown", init));
  element.focus?.();
  element.dispatchEvent(new Pointer("pointerup", { ...init, buttons: 0 }));
  element.dispatchEvent(new MouseEvent("mouseup", { ...init, buttons: 0 }));
  element.click();
}

/** Như `click` nhưng lấy phần tử ĐẦU trong cây (không phải cuối): nút "Thêm tuỳ chọn" của trang sách đứng trước nút cùng tên của thanh phát. */
export async function clickFirst(target: string | RegExp): Promise<HTMLElement> {
  const element = await waitFor(
    () => [...document.querySelectorAll<HTMLElement>(CLICKABLE)].find((candidate) => matches(candidate, target) && visible(candidate)) ?? null,
    `nút “${String(target)}”`,
  );
  press(element);
  await settle();
  return element;
}

/** Chờ phần tử hiện rồi bấm. */
export async function click(target: string | RegExp, within?: ParentNode): Promise<HTMLElement> {
  const element = await waitFor(() => find(target, within), `nút “${String(target)}”`);
  press(element);
  await settle();
  return element;
}

/** Chờ một chữ hiện trên trang. */
export async function see(target: string | RegExp): Promise<void> {
  await waitFor(() => findText(target), `chữ “${String(target)}”`);
}

/** Gõ vào ô nhập (theo nhãn / placeholder). */
export async function type(label: string | RegExp, text: string): Promise<void> {
  const input = await waitFor(
    () =>
      [...document.querySelectorAll<HTMLInputElement | HTMLTextAreaElement>("input, textarea")].find((element) =>
        [element.getAttribute("aria-label"), element.getAttribute("placeholder")].some((name) => name && (typeof label === "string" ? norm(name) === label : label.test(norm(name)))),
      ),
    `ô nhập “${String(label)}”`,
  );
  input.focus();
  const setter = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(input), "value")?.set;
  setter?.call(input, text);
  input.dispatchEvent(new Event("input", { bubbles: true }));
  await settle();
}

/** Nhấn một phím trên phần tử đang có tiêu điểm. */
export async function key(name: string): Promise<void> {
  const target = document.activeElement ?? document.body;
  target.dispatchEvent(new KeyboardEvent("keydown", { key: name, bubbles: true, cancelable: true }));
  target.dispatchEvent(new KeyboardEvent("keyup", { key: name, bubbles: true, cancelable: true }));
  await settle();
}

/** Đi tới một trang của app (router hash của app). */
export async function go(route: string): Promise<void> {
  window.location.hash = `#${route}`;
  await settle(200);
}

export function settle(ms = 120): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
