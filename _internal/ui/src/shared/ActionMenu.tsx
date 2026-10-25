import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { ChevronLeft } from "lucide-react";
import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { useBackLayer } from "./backStack";
import { cn } from "./cn";
import { useMediaQuery } from "./media";
import { MotionRegion } from "./MotionRegion";
import { Sheet } from "./ui";

// Trên điện thoại menu là một Sheet: menu con (Radix Sub) neo ngang bên cạnh mục mở nó nên rơi gần hết ra ngoài mép màn, và Esc/Back của Radix
// đóng cả menu lẫn Sheet. Ở đây menu con là MỘT BƯỚC ngay trong Sheet: danh sách chính trượt đi, bước con trượt vào từ phải, nút "Quay lại" ở đầu
// đưa về (trượt từ trái). Máy tính vẫn dùng menu con nổi của Radix. Nơi gọi chỉ dùng <ActionSubmenu> trong <ActionMenu>.

type StepApi = { phone: boolean; step: string | null; host: HTMLElement | null; go: (step: string | null) => void };
const StepContext = createContext<StepApi>({ phone: false, step: null, host: null, go: () => undefined });

/** Cùng các mục Radix: điện thoại dùng Sheet, máy tính neo menu vào nút mở. */
export function ActionMenu({ trigger, children, title }: { trigger: ReactNode; children: ReactNode; title: string }) {
  const phone = useMediaQuery("(max-width: 640px)");
  const [open, setOpen] = useState(false);
  // Bước con đang mở (null: danh sách chính) + hướng bước vừa rồi (null: chưa chuyển lần nào - bước đầu hiện cùng Sheet, không trượt).
  const [step, setStep] = useState<string | null>(null);
  const [direction, setDirection] = useState<"forward" | "back" | null>(null);
  const [host, setHost] = useState<HTMLElement | null>(null);
  const hostRef = useRef<HTMLElement | null>(null);
  const attach = useCallback((element: HTMLElement | null) => { hostRef.current = element; setHost(element); }, []);
  const go = useCallback((next: string | null) => { setDirection(next === null ? "back" : "forward"); setStep(next); }, []);
  // Mở lại thì về danh sách chính; đóng thì giữ nguyên để Sheet đang trượt xuống không đổi nội dung giữa chừng.
  const change = (next: boolean) => { if (next) { setStep(null); setDirection(null); } setOpen(next); };
  // Back của điện thoại (và Esc) về danh sách chính trước, chưa đóng cả Sheet: lớp nằm TRONG menu nên đứng trên nó (backLayers.dismissTopLayer).
  useBackLayer(phone && step !== null, () => go(null), hostRef);
  const escape = (event: KeyboardEvent) => { if (phone && step !== null) { event.preventDefault(); go(null); } };
  const content = <DropdownMenu.Content aria-label={title} align="end" sideOffset={6} collisionPadding={12}
    className="book-action-menu z-50 max-h-[var(--radix-dropdown-menu-content-available-height)] min-w-56 max-w-[min(22rem,calc(100vw-24px))] overflow-y-auto overscroll-contain rounded-[20px] bg-panel p-3 shadow-float"
    onEscapeKeyDown={escape}
    onCloseAutoFocus={phone ? event => event.preventDefault() : undefined}>
    {phone
      // MotionRegion lo chiều cao Sheet đổi theo bước (co/giãn êm); danh sách và bước con cùng ở đây, cái nào không phải bước hiện tại thì `hidden`
      // (hiện lại là .motion-step chạy lại). Danh sách KHÔNG gỡ khỏi cây: <ActionSubmenu> còn đó để đẩy bước con vào ô `host`.
      ? <MotionRegion motionKey={step}>
        <div hidden={step !== null} inert={step !== null} data-action-list className={cn(direction === "back" && "motion-step")} data-direction="back">{children}</div>
        <div ref={attach} hidden={step === null} inert={step === null} data-action-step={step ?? ""} className="motion-step" />
      </MotionRegion>
      : children}
  </DropdownMenu.Content>;
  return <StepContext.Provider value={{ phone, step, host, go }}>
    <DropdownMenu.Root modal={!phone} open={open} onOpenChange={change}>
      <DropdownMenu.Trigger asChild>{trigger}</DropdownMenu.Trigger>
      {phone ? <Sheet open={open} onOpenChange={change} title={title} className="book-action-sheet" onEscapeKeyDown={escape}>{content}</Sheet> : <DropdownMenu.Portal>{content}</DropdownMenu.Portal>}
    </DropdownMenu.Root>
  </StepContext.Provider>;
}

/** Menu con trong <ActionMenu>: máy tính là menu con nổi của Radix, điện thoại là một bước ngay trong Sheet (nút "Quay lại" ở đầu).
 *  `id`: tên bước (duy nhất trong menu); `label`: tên hiện cạnh nút "Quay lại"; `trigger`: ruột của mục mở menu con (biểu tượng, chữ, giá trị);
 *  `itemClassName`: kiểu của mục mở và của nút "Quay lại". */
export function ActionSubmenu({ id, label, trigger, itemClassName, children }: {
  id: string;
  label: string;
  trigger: ReactNode;
  itemClassName?: string;
  children: ReactNode;
}) {
  const { phone } = useContext(StepContext);
  if (!phone) {
    return <DropdownMenu.Sub>
      <DropdownMenu.SubTrigger className={itemClassName}>{trigger}</DropdownMenu.SubTrigger>
      <DropdownMenu.Portal>
        <DropdownMenu.SubContent sideOffset={4} collisionPadding={12} className="z-50 max-h-[70vh] w-72 overflow-y-auto rounded-xl border border-line bg-panel p-1.5 shadow-float">
          {children}
        </DropdownMenu.SubContent>
      </DropdownMenu.Portal>
    </DropdownMenu.Sub>;
  }
  return <PhoneSubmenu id={id} label={label} trigger={trigger} itemClassName={itemClassName}>{children}</PhoneSubmenu>;
}

function PhoneSubmenu({ id, label, trigger, itemClassName, children }: { id: string; label: string; trigger: ReactNode; itemClassName?: string; children: ReactNode }) {
  const { step, host, go } = useContext(StepContext);
  const active = step === id;
  const opener = useRef<HTMLDivElement>(null);
  const was = useRef(false);
  // Về danh sách chính thì tiêu điểm trả lại đúng mục vừa mở (mục ấy vừa hiện lại).
  useEffect(() => {
    if (was.current && !active) opener.current?.focus({ preventScroll: true });
    was.current = active;
  }, [active]);
  return <>
    <DropdownMenu.Item ref={opener} className={itemClassName} onSelect={(event) => { event.preventDefault(); go(id); }}>{trigger}</DropdownMenu.Item>
    {active && host && createPortal(<Step label={label} itemClassName={itemClassName}>{children}</Step>, host)}
  </>;
}

function Step({ label, itemClassName, children }: { label: string; itemClassName?: string; children: ReactNode }) {
  const { go } = useContext(StepContext);
  const back = useRef<HTMLDivElement>(null);
  useEffect(() => { back.current?.focus({ preventScroll: true }); }, []);
  return <>
    <DropdownMenu.Item ref={back} className={itemClassName} onSelect={(event) => { event.preventDefault(); go(null); }}>
      <ChevronLeft className="size-4" />
      <span className="flex-1">Quay lại</span>
      <span className="max-w-44 truncate text-xs text-fg-2">{label}</span>
    </DropdownMenu.Item>
    <DropdownMenu.Separator className="my-1 h-px bg-line" />
    {children}
  </>;
}
