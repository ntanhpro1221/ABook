import { letterShortcutsOn } from "@/shared/letterShortcuts";
import { focusCard, type CardFocusEnds } from "./useCardFocus";

/** Đọc danh sách sống lúc bấm phím, không dùng thứ tự DOM còn chứa hàng exit. */
export function workKeyHandler(items: () => readonly { key: string }[], cursor: () => number | null, select: (index: number | null) => void, ends: CardFocusEnds) {
  return (event: KeyboardEvent) => {
    if (event.ctrlKey || event.metaKey || event.altKey) return;
    if (event.key !== "Escape" && !letterShortcutsOn()) return;
    if (event.target instanceof Element && event.target.closest("input, textarea, select, [contenteditable=true], [role=dialog], [role=menu], [role=listbox]")) return;
    const list = items();
    if (!list.length) return;
    const at = cursor();
    const current = at === null ? null : Math.min(at, list.length - 1);
    if (event.key === "j" || event.key === "k") {
      event.preventDefault();
      const next = current === null ? 0 : Math.min(Math.max(current + (event.key === "j" ? 1 : -1), 0), list.length - 1);
      select(next);
      window.setTimeout(() => focusCard(`work-${list[next].key}`, ends), 0);
    } else if (/^[1-9]$/.test(event.key) && current !== null) {
      const choices = document.querySelectorAll<HTMLButtonElement>(`#work-${CSS.escape(list[current].key)} [data-choice]:not(:disabled)`);
      const choice = Array.from(choices).filter((button) => !button.closest("[inert]"))[Number(event.key) - 1];
      if (choice) { event.preventDefault(); choice.click(); }
    } else if (event.key === "Escape" && current !== null) select(null);
  };
}
