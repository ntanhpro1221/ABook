import { createElement, isValidElement, useEffect, useRef, useState, type ReactNode } from "react";
import { toast as sonner, type ExternalToast } from "sonner";
import { useBackLayer } from "./backStack";
import { MotionRegion } from "./MotionRegion";
import { MotionPresence } from "./MotionPresence";
import { Button } from "./ui";

type Content = ReactNode | (() => ReactNode);
const shown = (value: Content) => typeof value === "function" ? value() : value;

/** Thông báo chỉ xác nhận một dòng; chi tiết dài mở theo yêu cầu, không mở thêm hộp thoại lên hộp đang sửa. */
export function ToastDetails({ title, description, action, toastId }: { title: Content; description?: Content; action?: ReactNode; toastId?: string | number }) {
  const [open, setOpen] = useState(false);
  const content = useRef<HTMLDivElement>(null);
  const host = useRef<HTMLSpanElement>(null), trigger = useRef<HTMLButtonElement>(null);
  const [above, setAbove] = useState(false);
  const duration = useRef<number | undefined>(undefined);
  const changeOpen = (next: boolean) => {
    setOpen(next);
    if (next) setAbove((trigger.current?.getBoundingClientRect().top ?? 0) > window.innerHeight / 2);
    const item = sonner.getToasts().find(item => item.id === toastId);
    if (!item || !("title" in item)) return;
    if (next) duration.current = item.duration;
    // Giữ thông báo khi đang đọc chi tiết, kể cả trên màn cảm ứng không có rê chuột.
    const publish = item.type === "error" || item.type === "warning" || item.type === "info" || item.type === "success" || item.type === "loading" ? sonner[item.type] : sonner;
    publish(item.title, { ...item, duration: next ? Infinity : duration.current ?? 4000 });
  };
  useBackLayer(open, () => changeOpen(false), content, trigger);
  useEffect(() => {
    if (!open) return;
    const outside = (event: PointerEvent) => { if (event.target instanceof Node && !host.current?.contains(event.target)) changeOpen(false); };
    document.addEventListener("pointerdown", outside);
    return () => document.removeEventListener("pointerdown", outside);
  }, [open]);
  return <span ref={host} className="contents">
    <button ref={trigger} type="button" data-button aria-expanded={open} onClick={() => changeOpen(!open)} className="toast-details-action">Chi tiết</button>
    {/* Neo vào chính toast: không chịu hai hệ toạ độ do transform của Sonner, không tạo lớp dialog thứ hai. */}
    <MotionPresence open={open} className={`absolute right-0 z-50 w-[min(320px,calc(100vw-32px))] ${above ? "bottom-[calc(100%+12px)]" : "top-[calc(100%+12px)]"}`}>
    <div ref={content} role="region" aria-label="Chi tiết thông báo" className="max-h-[60dvh] overflow-y-auto rounded-cover bg-panel p-[16px] text-sm text-fg shadow-float">
      <MotionRegion className="space-y-3 text-pretty">
        <p className="font-medium">{shown(title)}</p>
        {description && <div className="break-words text-fg-2">{shown(description)}</div>}
        {action}
      </MotionRegion>
    </div></MotionPresence>
  </span>;
}

/** Tách trình bày khỏi lệnh thông báo: mọi nơi gọi giữ nguyên lý do lỗi và hành động, lớp dùng chung rút gọn phần nhìn thấy. */
export function prepareToast(args: unknown[], identify: (value: ExternalToast) => ExternalToast = value => value): unknown[] {
  const value = args[1] as ExternalToast | undefined, title = args[0] as Content;
  // Tiêu đề luôn hiện đủ chữ (xuống dòng, không cắt "…" - chủ sách 25-10); chỉ dòng mô tả dài mới vào Chi tiết.
  if (!value?.description) return args;
  const prepared = identify({ ...value, description: undefined, cancel: undefined });
  const original = value?.action;
  const action = original && typeof original === "object" && !isValidElement(original) && "label" in original ? createElement(ToastAction, { ...original,
    onClick: event => { original.onClick(event); if (!event.defaultPrevented) sonner.dismiss(prepared.id); } }) : original;
  prepared.action = createElement(ToastDetails, { title, description: value?.description, action, toastId: prepared.id });
  return [title, prepared];
}

export function ToastAction({ label, onClick }: { label: ReactNode; onClick: (event: React.MouseEvent<HTMLButtonElement>) => void }) {
  return <Button variant="ghost" size="sm" className="edge-start-action" onClick={onClick}>{label}</Button>;
}
