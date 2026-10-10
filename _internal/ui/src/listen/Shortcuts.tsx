import { useEffect, useState, type ReactNode } from "react";
import { Dialog, Kbd } from "@/shared/ui";

// Phím tắt của máy tính: MỘT danh sách cho Cài đặt › Phím tắt và cho hộp mở bằng phím "?" (hay nút "Phím tắt" ở màn Đang nghe).

export const SHORTCUTS_EVENT = "abook:shortcuts";

/** Mở hộp phím tắt (nút ở màn Đang nghe và phím "?" cùng đi qua đây). */
export function openShortcuts() {
  window.dispatchEvent(new CustomEvent(SHORTCUTS_EVENT));
}

const SHORTCUTS: [ReactNode, string][] = [
  [<Kbd key="space">Space</Kbd>, "Phát / tạm dừng"],
  [<><Kbd>←</Kbd> <Kbd>→</Kbd></>, "Lùi / tới 15 giây"],
  [<><Kbd>Shift</Kbd> + <Kbd>←</Kbd> <Kbd>→</Kbd></>, "Chương trước / sau"],
  [<Kbd key="b">B</Kbd>, "Thêm dấu trang"],
  [<Kbd key="m">M</Kbd>, "Tắt / bật tiếng"],
  [<><Kbd>[</Kbd> <Kbd>]</Kbd></>, "Giảm / tăng tốc độ đọc"],
  [<Kbd key="esc">Esc</Kbd>, "Thu nhỏ màn hình đang nghe"],
  [<Kbd key="help">?</Kbd>, "Xem các phím tắt này"],
];

export function ShortcutList() {
  return (
    <dl className="max-w-md space-y-2.5 text-sm">
      {SHORTCUTS.map(([keys, label]) => (
        <div key={label} className="flex items-center justify-between gap-4">
          <dt className="text-fg-2">{label}</dt>
          <dd className="flex items-center gap-1 text-fg-2">{keys}</dd>
        </div>
      ))}
    </dl>
  );
}

/** Đang gõ chữ (ô nhập, vùng soạn thảo): "?" là một ký tự, không phải lệnh. */
function isTyping(target: EventTarget | null): boolean {
  const element = target as HTMLElement | null;
  return Boolean(element && (element.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(element.tagName)));
}

/** Hộp phím tắt, một chỗ duy nhất của cả app: phím "?" (khi không gõ chữ) hay `openShortcuts()` mở nó. */
export function ShortcutsHost() {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "?" || event.defaultPrevented || event.ctrlKey || event.metaKey || event.altKey) return;
      if (isTyping(event.target) || document.querySelector("[role='dialog']")) return;
      event.preventDefault();
      setOpen(true);
    };
    const onOpen = () => setOpen(true);
    window.addEventListener("keydown", onKey);
    window.addEventListener(SHORTCUTS_EVENT, onOpen);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener(SHORTCUTS_EVENT, onOpen);
    };
  }, []);
  return (
    <Dialog open={open} onOpenChange={setOpen} title="Phím tắt" description="Dùng được ở mọi màn hình, trừ khi đang gõ chữ.">
      <ShortcutList />
    </Dialog>
  );
}
