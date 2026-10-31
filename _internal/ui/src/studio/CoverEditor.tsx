import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Globe, ImagePlus, Trash2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { toast } from "@/shared/toast";
import { seriesOf } from "@/listen/model";
import { BookCover } from "@/shared/BookCover";
import { cn } from "@/shared/cn";
import { CoverSearchDialog } from "@/shared/CoverSearch";
import type { CoverImage } from "@/shared/cover";
import { useMediaQuery } from "@/shared/media";
import { Skeleton } from "@/shared/ui";
import { api, type BookSummary } from "./api";

// Ảnh bìa thật cho một cuốn (webui/covers.py): chọn file, kéo thả ảnh vào bìa, hoặc dán (Ctrl+V) khi đang ở trang
// sách. Máy chủ tự thu nhỏ và tính màu; ảnh đi theo sách sang điện thoại, màn hình khoá và file MP3 xuất ra.

const ACCEPT = "image/png,image/jpeg,image/webp,image/gif,image/bmp";

function readAsDataUrl(file: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error ?? new Error("Chưa đọc được file ảnh"));
    reader.readAsDataURL(file);
  });
}

function imageFromFiles(files: FileList | null | undefined): File | null {
  return Array.from(files ?? []).find((file) => file.type.startsWith("image/")) ?? null;
}

function imageFromItems(items: DataTransferItemList | null | undefined): File | null {
  for (const item of Array.from(items ?? [])) {
    const file = item.kind === "file" ? item.getAsFile() : null;
    if (file && file.type.startsWith("image/")) return file;
  }
  return null;
}

export function CoverEditor({ book }: { book: BookSummary & { cover?: CoverImage | null } }) {
  const client = useQueryClient();
  const input = useRef<HTMLInputElement | null>(null);
  const [dragging, setDragging] = useState(false);
  const refresh = () => {
    // Bìa hiện ở thư viện nghe, Studio, trình phát - làm mới mọi truy vấn có sách này.
    void client.invalidateQueries({ queryKey: ["book", book.id] });
    void client.invalidateQueries({ queryKey: ["library"] });
    void client.invalidateQueries({ queryKey: ["listen"] });
  };
  const upload = useMutation({
    mutationFn: async (file: Blob) =>
      api<{ cover: CoverImage | null }>(`/api/books/${book.id}/cover`, { method: "PUT", body: { image: await readAsDataUrl(file) } }),
    onSuccess: () => {
      refresh();
      toast.success("Đã đặt ảnh bìa");
    },
    onError: (error: Error) => toast.error("Chưa đặt được ảnh bìa", { description: error.message }),
  });
  const remove = useMutation({
    mutationFn: () => api(`/api/books/${book.id}/cover`, { method: "DELETE" }),
    onSuccess: () => {
      refresh();
      toast.success("Đã bỏ ảnh bìa");
    },
    onError: (error: Error) => toast.error("Chưa bỏ được ảnh bìa", { description: error.message }),
  });

  // Dán ảnh (Ctrl+V) ở bất kỳ đâu trên trang sách - trừ khi đang gõ vào ô chữ.
  useEffect(() => {
    const onPaste = (event: ClipboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (target?.closest("input, textarea, [contenteditable='true']")) return;
      const file = imageFromItems(event.clipboardData?.items);
      if (!file) return;
      event.preventDefault();
      upload.mutate(file);
    };
    document.addEventListener("paste", onPaste);
    return () => document.removeEventListener("paste", onPaste);
  }, [upload]);

  const [searching, setSearching] = useState(false);
  const [choosing, setChoosing] = useState(false); // ảnh mạng đã chọn đang về
  const busy = upload.isPending || remove.isPending || choosing;
  // Điện thoại: bìa nhỏ nằm cạnh tên sách (trang dự án chiếm ~590 px đầu màn nếu bìa to nằm trên tên), nút chỉ còn biểu tượng.
  const narrow = useMediaQuery("(max-width: 639px)");
  return (
    <div className="w-24 shrink-0 sm:w-44">
      <div
        className={cn("relative rounded-control transition-shadow duration-motion-fast", dragging && "ring-2 ring-accent ring-offset-2 ring-offset-bg")}
        onDragOver={(event) => {
          if (!Array.from(event.dataTransfer.items).some((item) => item.type.startsWith("image/"))) return;
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);
          const file = imageFromFiles(event.dataTransfer.files);
          if (file) upload.mutate(file);
          else toast.error("Chỉ thả được file ảnh (PNG, JPEG, WebP…)");
        }}
      >
        <BookCover title={book.title} part={book.series?.part} size={narrow ? "sm" : "lg"} image={book.cover} className="w-24 sm:w-44" />
          <div aria-hidden={!busy} className={cn("pointer-events-none absolute inset-0 grid place-items-center rounded-control bg-cover-overlay text-cover-ink transition-opacity duration-motion-fast", busy ? "opacity-100" : "opacity-0")}>
            <Skeleton className="h-full w-full" />
          </div>
      </div>
      {/* Biểu tượng / chữ đầu thẳng mép trái của bìa (soát 24-10): lề âm bù đệm của nút; điện thoại (chỉ biểu tượng, nền chạm 48 px) dồn biểu tượng về trái. */}
      <div className="mt-2 -ml-2 flex items-center gap-1 max-sm:ml-0">
        <button
          type="button"
          disabled={busy}
          onClick={() => input.current?.click()}
          aria-label={book.cover ? "Đổi ảnh bìa" : "Đặt ảnh bìa"}
          className="touch-box inline-flex h-8 items-center gap-1.5 rounded-control px-2 text-[0.8125rem] font-medium text-fg-2 hover:bg-hover hover:text-fg disabled:opacity-50 max-sm:!justify-start max-sm:px-0"
        >
          <ImagePlus className="ink-start size-4" /> {/* Hai chữ, không xuống dòng: nút đứng dưới bìa 154 px cạnh hai nút biểu tượng ("Đổi ảnh bìa" gãy dòng đè lên dòng gợi ý, soát 24-10). */}
          <span className="whitespace-nowrap max-sm:hidden">{book.cover ? "Đổi bìa" : "Đặt bìa"}</span>
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => setSearching(true)}
          aria-label="Tìm ảnh bìa trên mạng"
          title="Tìm ảnh bìa trên mạng"
          className="touch-box grid size-8 place-items-center rounded-control text-fg-2 hover:bg-hover hover:text-fg disabled:opacity-50"
        >
          <Globe className="size-4" />
        </button>
        {book.cover && (
          <button
            type="button"
            disabled={busy}
            onClick={() => remove.mutate()}
            aria-label="Bỏ ảnh bìa, dùng lại bìa vẽ từ tên sách"
            title="Bỏ ảnh bìa"
            className="touch-box grid size-8 place-items-center rounded-control text-fg-2 hover:bg-hover hover:text-fg disabled:opacity-50"
          >
            <Trash2 className="size-4" />
          </button>
        )}
      </div>
      <p className="text-xs text-fg-3 max-sm:hidden">Kéo hoặc dán ảnh</p>
      <CoverSearchDialog
        bookId={book.id}
        defaultQuery={seriesOf(book.title).series || book.title}
        open={searching}
        onOpenChange={setSearching}
        onChosen={refresh}
        onBusy={setChoosing}
        onChooseFile={() => input.current?.click()}
      />
      <input
        ref={input}
        type="file"
        accept={ACCEPT}
        className="hidden"
        onChange={(event) => {
          const file = event.target.files?.[0];
          event.target.value = "";
          if (file) upload.mutate(file);
        }}
      />
    </div>
  );
}
