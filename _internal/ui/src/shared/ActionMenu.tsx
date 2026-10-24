import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { useState, type ReactNode } from "react";
import { useMediaQuery } from "./media";
import { Sheet } from "./ui";

/** Cùng các mục Radix: điện thoại dùng Sheet, máy tính neo menu vào nút mở. */
export function ActionMenu({ trigger, children, title }: { trigger: ReactNode; children: ReactNode; title: string }) {
  const phone = useMediaQuery("(max-width: 640px)");
  const [open, setOpen] = useState(false);
  const content = <DropdownMenu.Content aria-label={title} align="end" sideOffset={6} collisionPadding={12}
    className="book-action-menu z-50 max-h-[var(--radix-dropdown-menu-content-available-height)] min-w-56 max-w-[min(22rem,calc(100vw-24px))] overflow-y-auto overscroll-contain rounded-[20px] bg-panel p-3 shadow-float"
    onCloseAutoFocus={phone ? event => event.preventDefault() : undefined}>
    {children}
  </DropdownMenu.Content>;
  return <DropdownMenu.Root modal={!phone} open={open} onOpenChange={setOpen}>
    <DropdownMenu.Trigger asChild>{trigger}</DropdownMenu.Trigger>
    {phone ? <Sheet open={open} onOpenChange={setOpen} title={title} className="book-action-sheet">{content}</Sheet> : <DropdownMenu.Portal>{content}</DropdownMenu.Portal>}
  </DropdownMenu.Root>;
}
