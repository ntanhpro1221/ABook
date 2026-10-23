import { toast as sonner, type ExternalToast } from "sonner";

// Sonner không đưa ID lên DOM. Giữ ID thật (cả string lẫn number) trên lớp CSS
// của từng toast, để Back đóng đúng thông báo dù không dựng nút đóng.
const prefix = "abook-toast-id-";
let sequence = 0;
function options(value?: ExternalToast): ExternalToast {
  const id = value?.id ?? `abook-toast-${++sequence}`;
  return { ...value, id, className: `${value?.className ?? ""} ${prefix}${encodeURIComponent(JSON.stringify(id))}` };
}
const toastArgs = (args: unknown[]) => (args[1] as ExternalToast | undefined)?.action || (args[1] as ExternalToast | undefined)?.cancel
  ? [args[0], options(args[1] as ExternalToast)] : args;
const methods = new Set(["success", "info", "warning", "error", "custom", "message", "promise", "loading"]);
const wrapped = new WeakMap<Function, Function>();
export const toast: typeof sonner = new Proxy(sonner, {
  apply(target, self, args) { return Reflect.apply(target, self, toastArgs(args)); },
  get(target, key, receiver) {
    const method = Reflect.get(target, key, receiver);
    if (!methods.has(String(key))) return method;
    if (!wrapped.has(method)) wrapped.set(method, new Proxy(method, {
      apply(fn, self, args) { return Reflect.apply(fn, self, toastArgs(args)); },
    }));
    return wrapped.get(method);
  },
});

export function dismissToastElement(element: HTMLElement): boolean {
  const token = Array.from(element.classList ?? []).find((name) => name.startsWith(prefix));
  if (!token) return false;
  const id: unknown = JSON.parse(decodeURIComponent(token.slice(prefix.length)));
  if (typeof id !== "string" && typeof id !== "number") return false;
  toast.dismiss(id);
  // Back liên tiếp không được chọn lại toast đang chờ Sonner commit exit.
  element.dataset.removed = "true";
  element.inert = true;
  return true;
}
