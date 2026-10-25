import { toast as sonner, type ExternalToast } from "sonner";

// Sonner không đưa ID lên DOM. Giữ ID thật (cả string lẫn number) trên lớp CSS
// của từng toast, để Back đóng đúng thông báo dù không dựng nút đóng.
const prefix = "abook-toast-id-";
let sequence = 0;
function options(value?: ExternalToast): ExternalToast {
  const id = value?.id ?? `abook-toast-${++sequence}`;
  return { ...value, id, className: `${value?.className ?? ""} ${prefix}${encodeURIComponent(JSON.stringify(id))}` };
}
const toastArgs = (args: unknown[]) => (args[1] as ExternalToast | undefined)?.action
  ? [args[0], options(args[1] as ExternalToast)] : args;
const methods = new Set(["success", "info", "warning", "error", "custom", "message", "promise", "loading"]);
const wrapped = new WeakMap<Function, Function>();
// Thông báo = MỘT dòng + tối đa MỘT nút (DESIGN 6; soát 25-10 C6): kiểu dữ liệu chặn ngay lúc dựng - không `cancel` (nút thứ hai) ở loại nào, và không
// `description` (dòng mô tả) ở loại không phải lỗi: chi tiết cần thiết vào chữ của chính dòng, phần còn lại vào chỗ người dùng đang xem. Lỗi / cảnh báo
// (cần người dùng biết lý do) và thông báo đang chạy (`loading`: số tiến độ) được giữ một dòng mô tả ngắn.
type Title = Parameters<typeof sonner>[0];
export type ToastOptions = Omit<ExternalToast, "cancel">;
type Options = ToastOptions;
type Quiet = Omit<Options, "description">;
type Method<Data> = (message: Title, data?: Data) => string | number;
export type Toast = Omit<typeof sonner, "success" | "info" | "message" | "warning" | "error" | "loading"> & Method<Quiet> & {
  success: Method<Quiet>;
  info: Method<Quiet>;
  message: Method<Quiet>;
  warning: Method<Options>;
  error: Method<Options>;
  loading: Method<Options>;
};
export const toast = new Proxy(sonner, {
  apply(target, self, args) { return Reflect.apply(target, self, toastArgs(args)); },
  get(target, key, receiver) {
    const method = Reflect.get(target, key, receiver);
    if (!methods.has(String(key))) return method;
    if (!wrapped.has(method)) wrapped.set(method, new Proxy(method, {
      apply(fn, self, args) { return Reflect.apply(fn, self, toastArgs(args)); },
    }));
    return wrapped.get(method);
  },
}) as unknown as Toast;

/** "Xong" của việc dài (xuất file, tải về): trơn thì MỘT dòng; xong mà thiếu gì đó (`note`: chương / nhạc / nguồn chưa có) thì đổi thành cảnh báo cùng dòng ấy,
 *  `note` là dòng mô tả duy nhất - không chồng "xong" với lưu ý trong một thông báo hai tầng. */
export function toastDone(title: Title, note: string | undefined, options: Quiet = {}): string | number {
  return note ? toast.warning(title, { ...options, description: note }) : toast.success(title, options);
}

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
