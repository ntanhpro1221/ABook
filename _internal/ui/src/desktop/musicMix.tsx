import { useState } from "react";
import { MUSIC_MIX_HINT, type MusicExportState } from "./listenExport";

// Ô "Kèm nhạc nền" dùng chung cho mọi hộp xuất (sách Nghe ngay và Studio trên máy tính, "Xuất sách nói" / "Xuất M4B" trên điện thoại):
// file riêng, không kéo theo phần chỉ máy tính mới có.

/** Ô "Kèm nhạc nền" (chỉ dựng khi cuốn có kế hoạch nhạc - `MusicExportState.available`). */
export function MusicMixOption({ checked, onChange, disabled }: { checked: boolean; onChange: (on: boolean) => void; disabled?: boolean }) {
  return (
    <label className="flex items-start gap-2.5 text-sm">
      <input
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(event) => onChange(event.target.checked)}
        className="mt-0.5 size-4 shrink-0 accent-[var(--accent)]"
      />
      <span className="min-w-0">
        <span className="block font-medium">Kèm nhạc nền</span>
        <span className="block text-xs text-fg-2">{MUSIC_MIX_HINT}</span>
      </span>
    </label>
  );
}

/** Lựa chọn "Kèm nhạc nền" của hộp cho cuốn `bookId`: theo công tắc Nhạc nền của cuốn (`state.enabled`) cho tới khi người dùng tự tích / bỏ tích
 *  (nhớ riêng cho cuốn ấy - hộp mở cho cuốn khác thì lại theo công tắc). Cuốn không có kế hoạch nhạc: luôn tắt. */
export function useMusicChoice(state: MusicExportState | undefined, bookId: string): [boolean, (on: boolean) => void] {
  const [chosen, setChosen] = useState<MusicChosen | null>(null);
  return [musicChecked(state, chosen, bookId), (on) => setChosen({ bookId, on })];
}

/** Lần tích / bỏ tích gần nhất của người dùng, của cuốn nào. */
export type MusicChosen = { bookId: string; on: boolean };

/** Ô "Kèm nhạc nền" đang tích không (`useMusicChoice`). */
export function musicChecked(state: MusicExportState | undefined, chosen: MusicChosen | null, bookId: string): boolean {
  if (!state?.available) return false;
  return chosen?.bookId === bookId ? chosen.on : state.enabled;
}
