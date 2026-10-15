import { useEffect, useState, type ReactNode } from "react";
import { letterShortcutsOn, useLetterShortcuts } from "@/shared/letterShortcuts";
import { Dialog, Kbd } from "@/shared/ui";

// Phím tắt của máy tính: MỘT danh sách cho Cài đặt › Phím tắt và cho hộp mở bằng phím "?" (hay nút "Phím tắt" ở màn Đang nghe).

export const SHORTCUTS_EVENT = "abook:shortcuts";

/** Mở hộp phím tắt (nút ở màn Đang nghe và phím "?" cùng đi qua đây). */
export function openShortcuts() {
  window.dispatchEvent(new CustomEvent(SHORTCUTS_EVENT));
}

/** [phím, việc, là phím một chữ cái (tắt được ở Cài đặt › Phím tắt)]. */
const SHORTCUTS: [ReactNode, string, boolean][] = [
  [<Kbd key="space">Space</Kbd>, "Phát / tạm dừng", false],
  [<><Kbd>←</Kbd> <Kbd>→</Kbd></>, "Lùi / tới 15 giây", false],
  [<><Kbd>Shift</Kbd> + <Kbd>←</Kbd> <Kbd>→</Kbd></>, "Chương trước / sau", false],
  [<Kbd key="b">B</Kbd>, "Thêm dấu trang", true],
  [<Kbd key="m">M</Kbd>, "Tắt / bật tiếng", true],
  [<><Kbd>[</Kbd> <Kbd>]</Kbd></>, "Giảm / tăng tốc độ đọc", true],
  [<Kbd key="esc">Esc</Kbd>, "Thu nhỏ màn hình đang nghe", false],
  [<Kbd key="help">?</Kbd>, "Xem các phím tắt này", true],
];

/** Dòng mô tả công tắc "Phím tắt một chữ cái" (Cài đặt › Phím tắt). */
export const LETTER_SHORTCUTS_HINT =
  "B, M, [ ], ? khi nghe; J, K, 1–9 ở Việc cần duyệt; O, R khi nghe lại liền. Tắt nếu bạn nhập bằng giọng nói hay hay lỡ chạm phím - Space, mũi tên và Esc vẫn dùng được.";

/** `remote`: thiết bị ở xa (Studio từ xa) không đổi được cài đặt của máy tính - câu cuối không chỉ nó tới một công tắc nó không có. */
export function ShortcutList({ remote = false }: { remote?: boolean }) {
  const letters = useLetterShortcuts();
  return (
    <>
      <dl className="max-w-md space-y-2.5 text-sm">
        {SHORTCUTS.map(([keys, label, letter]) => (
          <div key={label} className="flex items-center justify-between gap-4">
            <dt className="text-fg-2">
              {label}
              {letter && !letters && " (đang tắt)"}
            </dt>
            <dd className={letter && !letters ? "flex items-center gap-1 text-fg-2 line-through" : "flex items-center gap-1 text-fg-2"}>{keys}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-3 max-w-md text-[0.8125rem] text-fg-2 text-pretty">
        {letters
          ? remote
            ? "Phím một chữ cái: B, M, [ ], ?, và J, K, 1–9, O, R ở Studio."
            : "Phím một chữ cái (B, M, [ ], ?, và J, K, 1–9, O, R ở Studio) tắt được ở Cài đặt › Phím tắt."
          : `Phím một chữ cái đang tắt${remote ? "" : " - bật lại ở Cài đặt › Phím tắt"}. Space, mũi tên và Esc vẫn dùng được; nút “Phím tắt” ở màn Đang nghe mở hộp này.`}
      </p>
    </>
  );
}

/** Đang gõ chữ (ô nhập, vùng soạn thảo): "?" là một ký tự, không phải lệnh. */
function isTyping(target: EventTarget | null): boolean {
  const element = target as HTMLElement | null;
  return Boolean(element && (element.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(element.tagName)));
}

/** Hộp phím tắt, một chỗ duy nhất của cả app: phím "?" (khi không gõ chữ) hay `openShortcuts()` mở nó. */
export function ShortcutsHost({ remote = false }: { remote?: boolean }) {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "?" || event.defaultPrevented || event.ctrlKey || event.metaKey || event.altKey || !letterShortcutsOn()) return;
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
      <ShortcutList remote={remote} />
    </Dialog>
  );
}
