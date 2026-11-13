import { S } from "./strings.generated";
import { MotionRegion } from "@/shared/MotionRegion";
import { useMutation } from "@tanstack/react-query";
import { Loader2, Search } from "lucide-react";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { toast } from "@/shared/toast";
import { latestRequest, wasAborted } from "@/shared/latestRequest";
import { Button, ContentSkeleton, Dialog, EmptyState, InlineError } from "@/shared/ui";
import { api, ApiError } from "@/studio/api";
import { useFadeScroller } from "./scrollFade";

import { Reveal } from "./MotionPresence";
/** Tên nguồn bìa như người đọc biết (máy chủ trả tên hàm: "google_books"). */
const PROVIDER_NAMES: Record<string, string> = { itunes: "iTunes", open_library: S.s_open_library_11e9037f, google_books: S.s_google_books_8a341a41 };

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
  return S.s_chua_noi_duoc_0_thu_lai_hoac_chon_anh_tren_2aa913a7(failed.map((name) => PROVIDER_NAMES[name] ?? name.replace("_", " ")).join(", "));
}

/**
 * "Tìm bìa trên mạng": iTunes, Open Library, Google Books theo tên bộ truyện. Truyện mạng dịch thường không có trên các nguồn này,
 * nên chỉ là gợi ý - người dùng chọn, không bao giờ tự đặt. Máy tính hỏi qua server (webui/cover_search.py), điện thoại qua lõi
 * native (CoverSearch.kt); ảnh được chọn thì `PUT /cover {url}` và nơi nhận tự tải, chỉ từ các nguồn đã cho phép.
 * `onBusy`: đang đặt ảnh đã chọn (trang chủ coi như đang bận, không cho đặt bìa khác chen vào). Đóng hộp thì huỷ yêu cầu còn chạy:
 * lời đáp về muộn không hiện đè lên, ảnh chọn xong mà bị bỏ không đè lên bìa người dùng đặt sau (máy chủ cũng kiểm thứ tự).
 */
export function CoverSearchPanel({
  bookId,
  defaultQuery,
  active,
  onClose,
  onChosen,
  onBusy,
  onChooseFile,
}: {
  bookId: string;
  defaultQuery: string;
  /** Đang hiện (hộp mở / bước đang đứng): lần đầu hiện thì tự tìm theo tên sách. */
  active: boolean;
  onClose: () => void;
  onChosen: () => void;
  onBusy?: (busy: boolean) => void;
  onChooseFile: () => void;
}) {
  const scrollFade = useFadeScroller<HTMLDivElement>();
  const open = active;
  const [query, setQuery] = useState(defaultQuery);
  const searches = useRef(latestRequest());
  const choices = useRef(latestRequest());
  // Ảnh nhỏ tải lỗi (nguồn xoá ảnh, mạng đứt giữa chừng): bỏ khỏi lưới, không để ô trống mà vẫn bấm chọn được.
  const [broken, setBroken] = useState<ReadonlySet<string>>(new Set());
  const search = useMutation({
    mutationFn: (q: string) =>
      api<CoverSearchResult>(`/api/books/${bookId}/cover/search?q=${encodeURIComponent(q)}`, { signal: searches.current.next() }),
  });
  const choose = useMutation({
    mutationFn: (found: FoundCover) =>
      api(`/api/books/${bookId}/cover`, { method: "PUT", body: { url: found.url }, signal: choices.current.next() }),
    onSuccess: () => {
      onChosen();
      onClose();
      toast.success(S.s_da_dat_anh_bia_90470364);
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
  const close = () => {
    searches.current.cancel();
    choices.current.cancel();
    onClose();
  };
  useEffect(() => {
    // Hộp đóng hay rời bước bằng Back / ✕: lượt tìm và lượt đặt bìa đang bay không được về sau đó.
    if (!active) { searches.current.cancel(); choices.current.cancel(); }
  }, [active]);
  useLayoutEffect(() => {
    // Hộp không bị gỡ khi đóng: lỗi đặt bìa của lần mở trước không được hiện lại cạnh kết quả mới - gỡ trước khi vẽ, không chớp một khung.
    if (open) choose.reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);
  useEffect(() => {
    if (open && !search.data && !search.isPending) search.mutate(query);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);
  const results = (search.data?.results ?? []).filter((found) => !broken.has(found.thumb));
  const failed = search.data?.failed ?? [];
  return (
    <MotionRegion>
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
          placeholder={S.s_ten_sach_tieng_anh_thuong_cho_nhieu_ket_qu_82eea1b6}
          aria-label={S.s_ten_sach_de_tim_bia_4f406cde}
          className="touch-box h-[40px] min-w-0 flex-1 rounded-control border border-line bg-bg px-3 text-sm outline-none focus:border-focus"
        />
        <Button type="submit" variant="primary" className="touch-box h-10 min-h-10 max-sm:min-h-[48px] pointer-coarse:min-h-[48px]" icon={Search} loading={search.isPending}>{S.s_tim_bbe47492}</Button>
      </form>
      <div ref={scrollFade.ref} style={scrollFade.style} className="mt-4 max-h-[55vh] overflow-y-auto">
        {search.isPending ? (
          <ContentSkeleton shape="covers" count={4} label={S.s_dang_tim_anh_bia_af1f4a20} />
        ) : search.isError && !wasAborted(search.error) ? (
          <InlineError message={S.s_ban_hay_kiem_tra_ket_noi_roi_tim_lai_anh_b_887a4046} onRetry={() => search.mutate(query)} />
        ) : results.length ? (
          <div className="grid grid-cols-[repeat(auto-fill,minmax(120px,1fr))] gap-3">
            {results.map((found) => (
              <button
                key={found.url}
                type="button"
                disabled={choose.isPending}
                onClick={() => choose.mutate(found)}
                className="group rounded-control p-2 text-left hover:bg-hover disabled:opacity-50"
                title={`${found.title}${found.author ? " - " + found.author : ""} (${found.provider})`}
              >
                <div className="relative aspect-[2/3] overflow-hidden rounded-control bg-hover">
                  <img
                    src={found.thumb}
                    width={2}
                    height={3}
                    alt=""
                    loading="lazy"
                    className="size-full object-cover"
                    onError={() => setBroken((now) => new Set(now).add(found.thumb))}
                  />
                  <Reveal when={choose.isPending && choose.variables?.url === found.url}><div className="absolute inset-0 grid place-items-center bg-cover-overlay text-cover-ink">
                      <Loader2 className="size-5 animate-spin" />
                    </div></Reveal>
                </div>
                <div className="mt-2 line-clamp-2 text-xs font-medium">{found.title}</div>
                <div className="truncate text-caption text-fg-3">{found.provider}</div>
              </button>
            ))}
          </div>
        ) : search.data && !failed.length ? (
          <EmptyState icon={Search} title={S.s_ban_hay_chon_anh_tren_may_006585b2} className="py-8" action={<Button onClick={() => { close(); onChooseFile(); }}>{S.s_chon_anh_41ecf092}</Button>} />
        ) : null}
        <InlineError open={failed.length > 0} message={S.s_ban_hay_kiem_tra_ket_noi_roi_tim_lai_cac_n_c69012d6} onRetry={() => search.mutate(query)} />
        <InlineError open={choose.isError && !wasAborted(choose.error) && !(choose.error instanceof ApiError && choose.error.status === 409)} message={S.s_ban_hay_kiem_tra_ket_noi_roi_dat_lai_anh_b_86cb5b41} onRetry={() => { if (choose.variables) choose.mutate(choose.variables); }} />
      </div>
    </MotionRegion>
  );
}

/** Tìm ảnh bìa trong hộp riêng - chỉ cho nơi không đứng trong một hộp khác (Studio). Trong hộp "Sửa sách" nó là một bước của chính hộp ấy
 * (EditBook), không phải hộp thứ hai đè lên (audit140 V9). */
export function CoverSearchDialog({ open, onOpenChange, ...panel }: Omit<Parameters<typeof CoverSearchPanel>[0], "active" | "onClose"> & { open: boolean; onOpenChange: (open: boolean) => void }) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange} title={COVER_SEARCH_TITLE} description={COVER_SEARCH_NOTE} width="max-w-[560px]">
      <CoverSearchPanel {...panel} active={open} onClose={() => onOpenChange(false)} />
    </Dialog>
  );
}

export const COVER_SEARCH_TITLE = S.s_tim_anh_bia_9825b3d1;
export const COVER_SEARCH_NOTE = S.s_ban_chon_anh_tu_cac_nguon_sach_hoac_tren_m_ca23c898;
