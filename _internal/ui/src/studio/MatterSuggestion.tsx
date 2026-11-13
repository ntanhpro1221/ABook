import { S } from "../shared/strings.generated";
import type { ScannedFile } from "@/studio/api";
import { formatNumber } from "@/shared/format";
import { matterFiles } from "@/studio/scanView";

/** Trang phụ của file sách (bìa, bản quyền, mục lục, mục rất ngắn - cùng luật với Nghe ngay): có trong sách nhưng CHƯA tích; tích trang nào bạn muốn nghe. */
export function MatterSuggestion({ files, keep, onKeep }: { files: ScannedFile[]; keep: string[]; onKeep: (path: string, on: boolean) => void }) {
  const rows = matterFiles(files);
  if (!rows.length) return null;
  const kept = new Set(keep);
  return (
    <div className="mt-4 py-4 text-sm">
      <p className="font-medium">{formatNumber(rows.length)}{S.s_trang_phu_chua_chon_fa525053}</p>
      <p className="mt-1 text-fg-2">{S.s_bia_ban_quyen_muc_luc_hay_trang_ten_sach_n_49213805}</p>
      <ul className="mt-2 space-y-1">
        {rows.map((row) => (
          <li key={row.path}>
            <label className="touch-row flex items-start gap-3">
              <input
                type="checkbox"
                checked={kept.has(row.path)}
                onChange={(event) => onKeep(row.path, event.target.checked)}
                className="mt-1 size-4 shrink-0 accent-[var(--accent)]"
              />
              <span className="min-w-0">
                <span className="block font-medium">{row.matter}</span>
                <span className="block truncate text-xs text-fg-2">{row.firstLine || row.name}</span>
              </span>
            </label>
          </li>
        ))}
      </ul>
    </div>
  );
}
