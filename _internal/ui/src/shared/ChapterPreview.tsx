import { Pencil } from "lucide-react";
import { useRef, useState } from "react";
import { cn } from "./cn";
import { formatNumber } from "./format";

/** Một hàng của danh sách chương xem trước: tên (dòng đầu của chương nếu có), số chữ và số ký tự. Cùng hàng chữ với danh sách chương
 *  ở bước "Chọn các chương" của trình tạo sách Studio (studio/NewProjectScreen.tsx). */
export interface PreviewChapter {
  /** Số thứ tự của hàng (từ 1) trong danh sách đầy đủ, dùng khi chọn / đổi tên; không có thì lấy vị trí trong `chapters`. */
  index?: number;
  title: string;
  /** Dòng đầu của chương; khác `title` thì hiện dòng này làm tên và `title` ở dòng phụ. */
  firstLine?: string;
  words: number;
  chars: number;
  /** Mục rất ngắn (bìa, trang bản quyền?): gắn nhãn nhỏ để người nghe biết vì sao nó chưa được tích. */
  short?: boolean;
  /** Phần có vẻ không phải truyện (bìa, bản quyền, mục lục…): lý do máy thấy, hiện ra để người nghe biết vì sao nó chưa được tích. */
  matter?: string;
}

/** Cho người dùng chọn chương nào vào sách và đổi tên chương ("Thêm sách từ file…"). Trạng thái do chỗ gọi giữ. */
export interface ChapterChoice {
  picked: ReadonlySet<number>;
  /** Tên đã đổi, theo số thứ tự hàng. */
  names: Readonly<Record<number, string>>;
  onPick: (index: number, on: boolean) => void;
  /** Người dùng xong việc gõ tên mới (Enter hay rời ô); chỗ gọi tự bỏ tên rỗng / trùng tên cũ. */
  onRename: (chapter: { index: number; title: string }, value: string) => void;
  disabled?: boolean;
}

/** `titleFirst`: tên chương làm dòng chính, dòng đầu của chương ở dòng phụ khi khác ("Thêm sách từ file…": tên ấy là tên sẽ lưu).
 *  `choice`: mỗi hàng có ô chọn và tên bấm để sửa. Tên dài xuống dòng (tối đa 2 dòng), không cắt một dòng như trước. */
export function ChapterPreview({ chapters, className, titleFirst = false, choice }: {
  chapters: PreviewChapter[];
  className?: string;
  titleFirst?: boolean;
  choice?: ChapterChoice;
}) {
  const [editing, setEditing] = useState<number | null>(null);
  const cancelled = useRef(false); // Esc huỷ: ô mất con trỏ ngay sau đó không được lưu
  return (
    <div className={cn("max-h-[340px] overflow-y-auto rounded-xl border border-line bg-panel", className)}>
      {chapters.map((chapter, position) => {
        const index = chapter.index ?? position + 1;
        const on = choice ? choice.picked.has(index) : true;
        const renamed = choice?.names[index];
        const title = renamed ?? (titleFirst ? chapter.title : chapter.firstLine || chapter.title);
        const sub = chapter.firstLine && chapter.firstLine !== chapter.title ? (titleFirst || renamed !== undefined ? chapter.firstLine : chapter.title) : "";
        const finish = (value: string) => {
          if (!cancelled.current) choice?.onRename({ index, title: chapter.title }, value);
          cancelled.current = false;
          setEditing(null);
        };
        return (
          <div
            key={index}
            className={cn(
              "grid items-center gap-2 border-b border-line px-3 py-2 [contain-intrinsic-size:auto_48px] [content-visibility:auto] last:border-b-0",
              choice ? "grid-cols-[20px_28px_minmax(0,1fr)_64px] sm:grid-cols-[20px_36px_minmax(0,1fr)_90px]" : "grid-cols-[40px_minmax(0,1fr)_90px]",
              !on && "opacity-60",
            )}
          >
            {choice && (
              // Ô chọn 14 px: nhãn bao ngoài nới vùng chạm lên 40 px ở màn hẹp / cảm ứng (touch-hit), bấm vào vùng nới cũng tích / bỏ tích.
              <label className="touch-hit grid size-5 place-items-center">
                <input
                  type="checkbox"
                  checked={on}
                  disabled={choice.disabled}
                  onChange={(event) => choice.onPick(index, event.target.checked)}
                  aria-label={`Đưa vào sách: ${renamed ?? chapter.title}`}
                  className="size-4 accent-[var(--accent)]"
                />
              </label>
            )}
            <span className="tabular text-xs text-fg-2">{position + 1}</span>
            <div className="min-w-0">
              {choice && editing === index ? (
                <input
                  autoFocus
                  defaultValue={renamed ?? chapter.title}
                  aria-label="Tên chương"
                  data-escape-local
                  maxLength={160}
                  onFocus={(event) => event.target.select()}
                  onBlur={(event) => finish(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") event.currentTarget.blur();
                    else if (event.key === "Escape") {
                      cancelled.current = true;
                      event.currentTarget.blur();
                    }
                  }}
                  className="h-8 w-full rounded-lg border border-accent bg-bg px-2 text-sm font-medium outline-none"
                />
              ) : choice ? (
                <button
                  type="button"
                  disabled={choice.disabled}
                  onClick={() => setEditing(index)}
                  title="Bấm để đổi tên chương"
                  className="group flex w-full items-start gap-1.5 rounded text-left text-sm font-medium hover:text-accent-text focus-visible:outline-2 focus-visible:outline-accent"
                >
                  <span className="line-clamp-2 min-w-0 break-words">{title}</span>
                  <Pencil className="mt-0.5 size-3 shrink-0 text-fg-3 group-hover:text-accent-text" aria-hidden />
                </button>
              ) : (
                <div className="line-clamp-2 break-words text-sm font-medium">{title}</div>
              )}
              {sub && <div className="line-clamp-1 break-words text-xs text-fg-2">{sub}</div>}
              {chapter.matter ? (
                <div className="text-xs text-fg-3">{chapter.matter} - có vẻ không phải truyện, tích nếu muốn nghe</div>
              ) : (
                chapter.short && <div className="text-xs text-fg-3">rất ngắn - có thể là bìa / trang bản quyền</div>
              )}
            </div>
            <div className="tabular text-right text-xs text-fg-2">
              <div>{formatNumber(chapter.words)} chữ</div>
              {chapter.chars > 0 && <div className="text-fg-3">{formatNumber(chapter.chars)} ký tự</div>}
            </div>
          </div>
        );
      })}
    </div>
  );
}
