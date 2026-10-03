import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Globe, ImagePlus, Loader2, Trash2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { seriesOf } from "@/listen/model";
import { BookCover } from "@/shared/BookCover";
import { cn } from "@/shared/cn";
import { CoverSearchDialog } from "@/shared/CoverSearch";
import type { CoverImage } from "@/shared/cover";
import { api, type BookSummary } from "./api";

// Ảnh bìa thật cho một cuốn (webui/covers.py): chọn file, kéo thả ảnh vào bìa, hoặc dán (Ctrl+V) khi đang ở trang
// sách. Máy chủ tự thu nhỏ và tính màu; ảnh đi theo sách sang điện thoại, màn hình khoá và file MP3 xuất ra.

const ACCEPT = "image/png,image/jpeg,image/webp,image/gif,image/bmp";

function readAsDataUrl(file: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error ?? new Error("Không đọc được file ảnh"));
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
      toast.success("Đã đặt ảnh bìa", { description: "Điện thoại nhận ảnh mới ở lần đồng bộ sau." });
    },
    onError: (error: Error) => toast.error("Chưa đặt được ảnh bìa", { description: error.message }),
  });
  const remove = useMutation({
    mutationFn: () => api(`/api/books/${book.id}/cover`, { method: "DELETE" }),
    onSuccess: () => {
      refresh();
      toast.success("Đã bỏ ảnh bìa", { description: "Sách dùng lại bìa vẽ từ tên." });
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
  const busy = upload.isPending || remove.isPending;
  return (
    <div className="w-44 shrink-0">
      <div
        className={cn("relative rounded-lg", dragging && "ring-2 ring-accent ring-offset-2 ring-offset-bg")}
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
        <BookCover title={book.title} part={book.series?.part} size="lg" image={book.cover} className="w-44" />
        {busy && (
          <div className="absolute inset-0 grid place-items-center rounded-lg bg-black/40 text-white">
            <Loader2 className="size-6 animate-spin" />
          </div>
        )}
      </div>
      <div className="mt-2 flex items-center gap-1">
        <button
          type="button"
          disabled={busy}
          onClick={() => input.current?.click()}
          className="inline-flex h-8 items-center gap-1.5 rounded-lg px-2 text-[13px] font-medium text-fg-2 hover:bg-hover hover:text-fg disabled:opacity-50"
        >
          <ImagePlus className="size-4" /> {book.cover ? "Đổi ảnh bìa" : "Đặt ảnh bìa"}
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => setSearching(true)}
          aria-label="Tìm ảnh bìa trên mạng"
          title="Tìm ảnh bìa trên mạng"
          className="grid size-8 place-items-center rounded-lg text-fg-2 hover:bg-hover hover:text-fg disabled:opacity-50"
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
            className="grid size-8 place-items-center rounded-lg text-fg-2 hover:bg-hover hover:text-fg disabled:opacity-50"
          >
            <Trash2 className="size-4" />
          </button>
        )}
      </div>
      <p className="px-2 text-xs text-fg-3">Hoặc kéo thả / dán ảnh vào đây.</p>
      <CoverSearchDialog
        bookId={book.id}
        defaultQuery={seriesOf(book.title).series || book.title}
        open={searching}
        onOpenChange={setSearching}
        onChosen={refresh}
        doneNote="Điện thoại nhận ảnh mới ở lần đồng bộ sau."
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
