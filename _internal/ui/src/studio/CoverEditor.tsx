import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Globe, ImagePlus, Loader2, Search, Trash2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { seriesOf } from "@/listen/model";
import { BookCover } from "@/shared/BookCover";
import { cn } from "@/shared/cn";
import type { CoverImage } from "@/shared/cover";
import { Button, Dialog } from "@/shared/ui";
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
        <BookCover title={book.title} size="lg" image={book.cover} className="w-44" />
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
      <CoverSearch book={book} open={searching} onOpenChange={setSearching} onChosen={refresh} />
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

interface Found {
  provider: string;
  title: string;
  author: string;
  thumb: string;
  url: string;
}

/**
 * "Tìm bìa trên mạng" (webui/cover_search.py): iTunes, Open Library, Google Books theo tên bộ truyện. Truyện mạng dịch
 * thường không có trên các nguồn này, nên chỉ là gợi ý - người dùng chọn, không bao giờ tự đặt.
 */
function CoverSearch({
  book,
  open,
  onOpenChange,
  onChosen,
}: {
  book: BookSummary;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onChosen: () => void;
}) {
  const [query, setQuery] = useState(() => seriesOf(book.title).series || book.title);
  const search = useMutation({
    mutationFn: (q: string) => api<{ results: Found[]; failed: string[] }>(`/api/books/${book.id}/cover/search?q=${encodeURIComponent(q)}`),
  });
  const choose = useMutation({
    mutationFn: (found: Found) => api(`/api/books/${book.id}/cover`, { method: "PUT", body: { url: found.url } }),
    onSuccess: () => {
      onChosen();
      onOpenChange(false);
      toast.success("Đã đặt ảnh bìa", { description: "Điện thoại nhận ảnh mới ở lần đồng bộ sau." });
    },
    onError: (error: Error) => toast.error("Chưa đặt được ảnh này", { description: error.message }),
  });
  useEffect(() => {
    if (open && !search.data && !search.isPending) search.mutate(query);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);
  const results = search.data?.results ?? [];
  const failed = search.data?.failed ?? [];
  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title="Tìm ảnh bìa trên mạng"
      description="Từ iTunes, Open Library và Google Books. Truyện mạng dịch thường không có ở đó - khi ấy dùng ảnh của bạn."
      width="max-w-3xl"
    >
      <form
        className="flex gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          search.mutate(query);
        }}
      >
        <input
          id="cover-search-query"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Tên sách (tiếng Anh thường cho nhiều kết quả hơn)"
          className="h-10 min-w-0 flex-1 rounded-lg border border-line bg-bg px-3 text-sm outline-none focus:border-accent"
        />
        <Button type="submit" variant="primary" icon={Search} loading={search.isPending}>
          Tìm
        </Button>
      </form>
      <div className="mt-4 max-h-[55vh] overflow-y-auto">
        {search.isPending ? (
          <p className="py-10 text-center text-sm text-fg-2">Đang hỏi các nguồn…</p>
        ) : results.length ? (
          <div className="grid grid-cols-[repeat(auto-fill,minmax(120px,1fr))] gap-3">
            {results.map((found) => (
              <button
                key={found.url}
                type="button"
                disabled={choose.isPending}
                onClick={() => choose.mutate(found)}
                className="group rounded-lg p-1.5 text-left hover:bg-hover disabled:opacity-50"
                title={`${found.title}${found.author ? " - " + found.author : ""} (${found.provider})`}
              >
                <div className="relative aspect-[2/3] overflow-hidden rounded-md bg-hover">
                  <img src={found.thumb} alt="" loading="lazy" className="size-full object-cover" />
                  {choose.isPending && choose.variables?.url === found.url && (
                    <div className="absolute inset-0 grid place-items-center bg-black/40 text-white">
                      <Loader2 className="size-5 animate-spin" />
                    </div>
                  )}
                </div>
                <div className="mt-1.5 line-clamp-2 text-xs font-medium">{found.title}</div>
                <div className="truncate text-[11px] text-fg-3">{found.provider}</div>
              </button>
            ))}
          </div>
        ) : search.data ? (
          <p className="py-10 text-center text-sm text-fg-2">Không thấy bìa nào. Thử tên tiếng Anh, bỏ số tập, hoặc dùng ảnh của bạn.</p>
        ) : null}
        {failed.length > 0 && (
          <p className="mt-3 text-xs text-fg-3">Không trả lời lần này: {failed.map((name) => name.replace("_", " ")).join(", ")}.</p>
        )}
      </div>
    </Dialog>
  );
}
