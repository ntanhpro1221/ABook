import { BookPlus } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { AddBookDialog } from "./AddBook";
import { useSource } from "./source";
import type { PickedItem } from "./textImport";

// Kéo file vào màn Thư viện (máy tính): thả một hay nhiều file thì mở "Thêm sách từ file" ở đúng hàng xem trước như khi chọn nhiều file. Nguồn nào nhận
// file thả thì có `textImport.watchDrops` (cửa sổ app nhận đường dẫn từ vỏ Tauri, trình duyệt gửi file lên máy tính - desktop/httpSource.ts).

const dialogOpen = () => Boolean(document.querySelector('[role="dialog"]'));

export function DropToAdd({ onBookFile }: { onBookFile?: (path: string) => Promise<void | boolean> }) {
  const watch = useSource().textImport?.watchDrops;
  const [hovering, setHovering] = useState(false);
  const [dropped, setDropped] = useState<PickedItem[] | null>(null);
  useEffect(() => {
    if (!watch) return;
    return watch({
      hover: (on) => setHovering(on && !dialogOpen()),
      drop: (items) => {
        if (!items.length) return;
        if (dialogOpen()) toast("Đang có một hộp mở", { description: "Đóng nó rồi thả lại file nhé." });
        else setDropped(items);
      },
    });
  }, [watch]);
  if (!watch) return null;
  return (
    <>
      {hovering && (
        <div className="pointer-events-none fixed inset-0 z-[60] grid place-items-center bg-bg/80 p-6 backdrop-blur-sm">
          <div className="flex max-w-md flex-col items-center gap-3 rounded-2xl border-2 border-dashed border-accent bg-accent-soft px-10 py-12 text-center">
            <BookPlus className="size-10 text-accent-text" strokeWidth={1.75} />
            <p className="text-lg font-semibold">Thả để thêm sách</p>
            <p className="text-sm text-fg-2">EPUB, Word (DOCX), PDF có chữ, TXT hay file sách .abook. Thả nhiều file một lúc cũng được.</p>
          </div>
        </div>
      )}
      <AddBookDialog open={dropped !== null} onOpenChange={(open) => !open && setDropped(null)} onBookFile={onBookFile} initial={dropped} />
    </>
  );
}
