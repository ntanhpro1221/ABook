import { friendlyError } from "./errorText";
import * as Popover from "@radix-ui/react-popover";

/** Lỗi của MỘT chương trong danh sách chương: một dòng ngắn cho người nghe (cùng `friendlyError` với khối lỗi của cả cuốn); bấm "Chi tiết"
 *  mở khung nổi có việc nên làm và nguyên văn lỗi kỹ thuật. Hàng chương cao cố định nên khung nổi, không đẩy hàng dưới. */
export function ChapterError({ raw, studio = false }: { raw: string; studio?: boolean }) {
  const shown = friendlyError(raw, studio);
  return (
    <Popover.Root>
      <Popover.Trigger className="block max-w-full cursor-pointer select-none truncate text-left text-xs text-danger">
        {shown.summary} <span className="underline underline-offset-2">Chi tiết</span>
      </Popover.Trigger>
      <Popover.Portal>
      <Popover.Content aria-label="Lỗi chương" align="start" sideOffset={4} collisionPadding={12} className="z-50 w-[min(32rem,calc(100vw-3rem))] rounded-lg border border-line bg-panel p-3 text-xs text-fg shadow-float">
        <p className="text-fg-2">{shown.hint}</p>
        {shown.detail && <p className="mt-2 max-h-40 select-text overflow-auto break-words font-mono text-[0.6875rem] text-fg-2">{shown.detail}</p>}
      </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
