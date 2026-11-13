import { S } from "../shared/strings.generated";
import { MotionRegion } from "@/shared/MotionRegion";
import { useQueryClient } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router";
import { Dialog } from "@/shared/ui";
import { searchBook, type BookSearch, type FoldedChapter } from "./bookSearch";
import type { FindHit, Snippet } from "./findText";
import { foldedQuery, MIN_QUERY } from "./findText";
import type { ListenBook } from "./model";
import { usePlayer } from "./player";
import { chapterScriptQuery, chapterTexts, useSource } from "./source";
import { useFadeScroller } from "@/shared/scrollFade";

// "Tìm trong sách": gõ một chữ / một câu, bấm một kết quả là mở màn đọc đúng câu ấy (`?at=` - ReaderScreen); đang nghe cuốn này thì nghe tiếp từ câu đó.
// Máy tính và điện thoại dùng chung; chữ lấy qua nguồn dữ liệu (bookSearch.ts), nên sách nói, sách chỉ-chữ và sách nghe thẳng từ máy khác đều tìm được.

/** Chờ người gõ ngừng tay chừng này (ms) rồi mới tìm. */
const TYPING_MS = 250;

/** Địa chỉ màn đọc mở đúng câu `hit.sentence` của chương; `play`: nghe từ câu ấy. */
export function readerUrl(bookId: string, hit: Pick<FindHit, "chapterId" | "sentence">, play: boolean): string {
  return `/book/${bookId}/read/${hit.chapterId}?at=${hit.sentence}${play ? "&play=1" : ""}`;
}

function Excerpt({ snippet }: { snippet: Snippet }) {
  return (
    <>
      {snippet.before}
      {snippet.match && <mark className="rounded-control bg-accent-soft px-1 font-medium text-accent-text">{snippet.match}</mark>}
      {snippet.after}
    </>
  );
}

const count = (value: number) => value.toLocaleString("vi-VN");

/** Câu nói tình hình tìm kiếm cho người nghe. */
export function findStatus(query: string, progress: BookSearch | null, shown: number): string {
  if (!query.trim()) return S.s_go_chu_hay_cau_can_tim_khong_can_go_dau_ho_d1bb2734;
  if (!foldedQuery(query)) return S.s_go_it_nhat_0_ky_tu_745a8caa(MIN_QUERY);
  if (!progress) return S.s_dang_tim_58376830;
  const failed = progress.failed > 0 ? S.s_0_chuong_chua_doc_duoc_nen_chua_tim_trong_79d02fce(count(progress.failed)) : "";
  if (!progress.done) return S.s_dang_tim_da_xem_0_1_chuong_thay_2_cho_9fa24430(count(progress.scanned), count(progress.chapters), count(progress.total));
  if (progress.total === 0) return S.s_khong_thay_0_trong_sach_1_1967bf94(query.trim(), failed);
  const more = progress.total > shown ? S.s_dang_hien_0_ket_qua_dau_con_1_ket_qua_go_t_ba693cdb(count(shown), count(progress.total - shown)) : "";
  return S.s_0_ket_qua_1_2_8dad3320(count(progress.total), more, failed);
}

export function FindInBook({ book, open, onOpenChange }: { book: ListenBook; open: boolean; onOpenChange: (open: boolean) => void }) {
  const source = useSource();
  const client = useQueryClient();
  const navigate = useNavigate();
  const player = usePlayer();
  const [query, setQuery] = useState("");
  const [progress, setProgress] = useState<BookSearch | null>(null);
  const cache = useRef(new Map<number, FoldedChapter>());
  const results = useRef<HTMLUListElement | null>(null);
  const scrollFade = useFadeScroller<HTMLUListElement>(results);
  const search = useRef<HTMLInputElement | null>(null);
  const bookId = book.id;
  const chapterList = book.chapters ?? [];

  // Chữ đã chuẩn hoá của các chương chỉ giữ trong lúc hộp mở (sách dày thì chiếm bộ nhớ); đóng hộp là thả.
  useEffect(() => {
    if (!open) cache.current = new Map();
  }, [open]);
  useEffect(() => {
    cache.current = new Map();
  }, [bookId]);

  useEffect(() => {
    setProgress(null);
    if (!open || !foldedQuery(query)) return undefined;
    const controller = new AbortController();
    const byId = new Map(chapterList.map((chapter) => [chapter.id, chapter]));
    const timer = window.setTimeout(() => {
      void searchBook({
        chapters: chapterList,
        load: (chapter) => client.fetchQuery({ ...chapterScriptQuery(source, bookId, byId.get(chapter.id)!), gcTime: 60_000 }),
        loadMany: source.searchTexts ? (lot) => chapterTexts(source, bookId, lot.map((chapter) => byId.get(chapter.id)!)) : undefined,
        query,
        cache: cache.current,
        signal: controller.signal,
        onUpdate: (next) => {
          if (!controller.signal.aborted) setProgress(next);
        },
      });
    }, TYPING_MS);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
    // chapterList đổi mỗi lần sách làm mới (5-30 giây): chỉ tìm lại khi từ khoá / sách / hộp đổi.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bookId, client, open, query, source]);

  const labels = new Map(chapterList.map((chapter) => [chapter.id, chapter.fullTitle || chapter.title]));
  const playingHere = player.playing && player.track?.bookId === bookId;
  const pick = (hit: FindHit) => {
    onOpenChange(false);
    navigate(readerUrl(bookId, hit, playingHere));
  };
  const hits = progress?.hits ?? [];
  const status = findStatus(query, progress, hits.length);

  return (
    <Dialog open={open} onOpenChange={onOpenChange} width="max-w-[560px]" title={S.s_tim_trong_sach_de3ccc5f} description={book.title}><MotionRegion>
      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-fg-3" />
        <input
          ref={search}
          data-autofocus
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={(event) => {
            // Enter chốt chữ đang soạn của bộ gõ (IME) không phải lệnh mở kết quả.
            if (event.nativeEvent.isComposing || event.keyCode === 229) return;
            if (event.key === "Enter" && hits[0]) pick(hits[0]);
            // ↓ từ ô tìm xuống kết quả đầu; trong danh sách ↑/↓ đi giữa các kết quả, ↑ ở kết quả đầu về ô tìm.
            else if (event.key === "ArrowDown" && hits.length) {
              event.preventDefault();
              results.current?.querySelector<HTMLElement>("button")?.focus();
            }
          }}
          aria-label={S.s_chu_hay_cau_can_tim_d9ab6029}
          placeholder={S.s_chu_hay_cau_can_tim_d9ab6029}
          autoComplete="off"
          enterKeyHint="search"
          className="touch-box h-11 w-full rounded-control border border-line bg-bg pl-10 pr-3 text-base outline-none focus:border-focus"
        />
      </div>
      <p data-motion-live role="status" className="mt-2 text-xs text-fg-2">
        {status}
      </p>
      {hits.length > 0 && (
        <div data-list-edges="book-search"><ul
          ref={scrollFade.ref} style={scrollFade.style}
          onKeyDown={(event) => {
            const step = event.key === "ArrowDown" ? 1 : event.key === "ArrowUp" ? -1 : 0;
            if (!step) return;
            const buttons = [...event.currentTarget.querySelectorAll<HTMLElement>("button")];
            const next = buttons.indexOf(document.activeElement as HTMLElement) + step;
            event.preventDefault();
            if (next < 0) search.current?.focus();
            else buttons[Math.min(next, buttons.length - 1)]?.focus();
          }}
          className="rows-inset -mx-3 mt-2 max-h-[min(55dvh,28rem)] overflow-y-auto overscroll-contain px-2 py-2 [--rows-inset:calc(var(--spacing)*1.5)]"
        >
          {hits.map((hit) => (
            <li key={`${hit.chapterId}:${hit.sentence}`}>
              <button type="button" onClick={() => pick(hit)} className="block w-full rounded-control px-2 py-3 text-left hover:bg-hover">
                <span className="block break-words text-xs font-medium text-fg-2">{labels.get(hit.chapterId)}</span>
                <span className="mt-1 block text-sm leading-relaxed">
                  <Excerpt snippet={hit.snippet} />
                </span>
              </button>
            </li>
          ))}
        </ul></div>
      )}
    </MotionRegion></Dialog>
  );
}
