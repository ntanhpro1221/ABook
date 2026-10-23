import { MotionRegion } from "@/shared/MotionRegion";
import { useMutation } from "@tanstack/react-query";
import { Loader2, Search } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { toast } from "@/shared/toast";
import { latestRequest, wasAborted } from "@/shared/latestRequest";
import { Button, Dialog } from "@/shared/ui";
import { api, ApiError } from "@/studio/api";

/** Tên nguồn bìa như người đọc biết (máy chủ trả tên hàm: "google_books"). */
const PROVIDER_NAMES: Record<string, string> = { itunes: "iTunes", open_library: "Open Library", google_books: "Google Books" };

export interface FoundCover {
  provider: string;
  title: string;
  author: string;
  thumb: string;
  url: string;
}

/** Lời đáp của `GET /api/books/<mã>/cover/search?q=` (webui/cover_search.py; điện thoại: CoverSearch.kt, cùng JSON). */
export interface CoverSearchResult {
  query: string;
  results: FoundCover[];
  failed: string[];
}

/** Câu báo "chưa hỏi được nguồn nào" - dùng chung để hai nơi hiện cùng một câu. */
export function failedSourcesNote(failed: string[]): string {
  return `Chưa hỏi được ${failed.map((name) => PROVIDER_NAMES[name] ?? name.replace("_", " ")).join(", ")} lần này (mạng chậm hay trang ấy không trả lời) - thử lại sau, hoặc dùng ảnh có sẵn trên máy.`;
}

/**
 * "Tìm bìa trên mạng": iTunes, Open Library, Google Books theo tên bộ truyện. Truyện mạng dịch thường không có trên các nguồn này,
 * nên chỉ là gợi ý - người dùng chọn, không bao giờ tự đặt. Máy tính hỏi qua server (webui/cover_search.py), điện thoại qua lõi
 * native (CoverSearch.kt); ảnh được chọn thì `PUT /cover {url}` và nơi nhận tự tải, chỉ từ các nguồn đã cho phép.
 * `doneNote`: dòng mô tả của thông báo "Đã đặt ảnh bìa" (Studio: điện thoại nhận ảnh ở lần đồng bộ sau).
 * `onBusy`: đang đặt ảnh đã chọn (trang chủ coi như đang bận, không cho đặt bìa khác chen vào). Đóng hộp thì huỷ yêu cầu còn chạy:
 * lời đáp về muộn không hiện đè lên, ảnh chọn xong mà bị bỏ không đè lên bìa người dùng đặt sau (máy chủ cũng kiểm thứ tự).
 */
export function CoverSearchDialog({
  bookId,
  defaultQuery,
  open,
  onOpenChange,
  onChosen,
  doneNote,
  onBusy,
}: {
  bookId: string;
  defaultQuery: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onChosen: () => void;
  doneNote?: string;
  onBusy?: (busy: boolean) => void;
}) {
  const [query, setQuery] = useState(defaultQuery);
  const searches = useRef(latestRequest());
  const choices = useRef(latestRequest());
  // Ảnh nhỏ tải lỗi (nguồn xoá ảnh, mạng đứt giữa chừng): bỏ khỏi lưới, không để ô trống mà vẫn bấm chọn được.
  const [broken, setBroken] = useState<ReadonlySet<string>>(new Set());
  const search = useMutation({
    mutationFn: (q: string) =>
      api<CoverSearchResult>(`/api/books/${bookId}/cover/search?q=${encodeURIComponent(q)}`, { signal: searches.current.next() }),
    onError: (error: Error) => {
      if (!wasAborted(error)) toast.error("Chưa tìm được bìa", { description: error.message });
    },
  });
  const choose = useMutation({
    mutationFn: (found: FoundCover) =>
      api(`/api/books/${bookId}/cover`, { method: "PUT", body: { url: found.url }, signal: choices.current.next() }),
    onSuccess: () => {
      onChosen();
      onOpenChange(false);
      toast.success("Đã đặt ảnh bìa", doneNote ? { description: doneNote } : undefined);
    },
    onError: (error: Error) => {
      // Bị huỷ (đóng hộp) hay bị bìa đặt sau lấn (máy chủ trả 409): người dùng đã tự quyết, không báo lỗi.
      if (wasAborted(error) || (error instanceof ApiError && error.status === 409)) return;
      toast.error("Chưa đặt được ảnh này", { description: error.message });
    },
  });
  useEffect(() => {
    onBusy?.(choose.isPending);
    return () => onBusy?.(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [choose.isPending]);
  useEffect(() => {
    const pending = [searches.current, choices.current];
    return () => pending.forEach((request) => request.cancel());
  }, []);
  const changeOpen = (next: boolean) => {
    if (!next) {
      searches.current.cancel();
      choices.current.cancel();
    }
    onOpenChange(next);
  };
  useEffect(() => {
    if (open && !search.data && !search.isPending) search.mutate(query);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);
  const results = (search.data?.results ?? []).filter((found) => !broken.has(found.thumb));
  const failed = search.data?.failed ?? [];
  return (
    <Dialog
      open={open}
      onOpenChange={changeOpen}
      title="Tìm ảnh bìa trên mạng"
      description="Từ iTunes, Open Library và Google Books. Truyện mạng dịch thường không có ở đó - khi ấy dùng ảnh có sẵn trên máy."
      width="max-w-3xl"
    ><MotionRegion>
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
          aria-label="Tên sách để tìm bìa"
          className="h-10 min-w-0 flex-1 rounded-lg border border-line bg-bg px-3 text-sm outline-none focus:border-focus"
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
                  <img
                    src={found.thumb}
                    alt=""
                    loading="lazy"
                    className="size-full object-cover"
                    onError={() => setBroken((now) => new Set(now).add(found.thumb))}
                  />
                  {choose.isPending && choose.variables?.url === found.url && (
                    <div className="absolute inset-0 grid place-items-center bg-black/40 text-white">
                      <Loader2 className="size-5 animate-spin" />
                    </div>
                  )}
                </div>
                <div className="mt-1.5 line-clamp-2 text-xs font-medium">{found.title}</div>
                <div className="truncate text-[0.6875rem] text-fg-3">{found.provider}</div>
              </button>
            ))}
          </div>
        ) : search.data ? (
          <p className="py-10 text-center text-sm text-fg-2">Không thấy bìa nào. Thử tên tiếng Anh, bỏ số tập, hoặc dùng ảnh có sẵn trên máy.</p>
        ) : null}
        {failed.length > 0 && <p className="mt-3 text-xs text-fg-3">{failedSourcesNote(failed)}</p>}
      </div>
    </MotionRegion></Dialog>
  );
}
