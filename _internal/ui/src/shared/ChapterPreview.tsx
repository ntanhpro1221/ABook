import { cn } from "./cn";
import { formatNumber } from "./format";

/** Một hàng của danh sách chương xem trước: tên (dòng đầu của chương nếu có), số chữ và số ký tự. Cùng hàng chữ với danh sách chương
 *  ở bước "Chọn các chương" của trình tạo sách Studio (studio/NewProjectScreen.tsx). */
export interface PreviewChapter {
  title: string;
  /** Dòng đầu của chương; khác `title` thì hiện dòng này làm tên và `title` ở dòng phụ. */
  firstLine?: string;
  words: number;
  chars: number;
}

export function ChapterPreview({ chapters, className }: { chapters: PreviewChapter[]; className?: string }) {
  return (
    <div className={cn("max-h-[340px] overflow-y-auto rounded-xl border border-line bg-panel", className)}>
      {chapters.map((chapter, index) => (
        <div
          key={index}
          className="grid grid-cols-[40px_minmax(0,1fr)_90px] items-center gap-2 border-b border-line px-3 py-2 [contain-intrinsic-size:auto_48px] [content-visibility:auto] last:border-b-0"
        >
          <span className="tabular text-xs text-fg-2">{index + 1}</span>
          <div className="min-w-0">
            <div className="truncate text-sm font-medium">{chapter.firstLine || chapter.title}</div>
            {chapter.firstLine && chapter.firstLine !== chapter.title && <div className="truncate text-xs text-fg-2">{chapter.title}</div>}
          </div>
          <div className="tabular text-right text-xs text-fg-2">
            <div>{formatNumber(chapter.words)} chữ</div>
            {chapter.chars > 0 && <div className="text-fg-3">{formatNumber(chapter.chars)} ký tự</div>}
          </div>
        </div>
      ))}
    </div>
  );
}
