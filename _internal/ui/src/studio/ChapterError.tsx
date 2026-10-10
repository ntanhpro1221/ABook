import { friendlyError } from "./errorText";

/** Lỗi của MỘT chương trong danh sách chương: một dòng ngắn cho người nghe (cùng `friendlyError` với khối lỗi của cả cuốn); bấm "Chi tiết"
 *  mở khung nổi có việc nên làm và nguyên văn lỗi kỹ thuật. Hàng chương cao cố định nên khung nổi, không đẩy hàng dưới. */
export function ChapterError({ raw }: { raw: string }) {
  const shown = friendlyError(raw);
  return (
    <details className="relative text-xs text-danger">
      <summary className="cursor-pointer select-none truncate">
        {shown.summary} <span className="underline underline-offset-2">Chi tiết</span>
      </summary>
      <div className="absolute left-0 top-full z-20 mt-1 w-[min(32rem,calc(100vw-3rem))] rounded-lg border border-line bg-panel p-3 text-fg shadow-float">
        <p className="text-fg-2">{shown.hint}</p>
        {shown.detail && <p className="mt-2 max-h-40 select-text overflow-auto break-words font-mono text-[11px] text-fg-2">{shown.detail}</p>}
      </div>
    </details>
  );
}
