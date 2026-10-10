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
import { chapterScriptQuery, useSource } from "./source";

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
      {snippet.match && <mark className="rounded bg-accent-soft px-0.5 font-semibold text-accent-text">{snippet.match}</mark>}
      {snippet.after}
    </>
  );
}

const count = (value: number) => value.toLocaleString("vi-VN");

/** Câu nói tình hình tìm kiếm cho người nghe. */
export function findStatus(query: string, progress: BookSearch | null, shown: number): string {
  if (!query.trim()) return `Gõ chữ hay câu cần tìm - không cần gõ dấu, hoa hay thường đều được.`;
  if (!foldedQuery(query)) return `Gõ ít nhất ${MIN_QUERY} ký tự.`;
  if (!progress) return "Đang tìm…";
  const failed = progress.failed > 0 ? ` ${count(progress.failed)} chương chưa đọc được nên chưa tìm trong đó.` : "";
  if (!progress.done) return `Đang tìm… đã xem ${count(progress.scanned)}/${count(progress.chapters)} chương, thấy ${count(progress.total)} chỗ.`;
  if (progress.total === 0) return `Không thấy “${query.trim()}” trong sách.${failed}`;
  const more = progress.total > shown ? ` Đang hiện ${count(shown)} kết quả đầu, còn ${count(progress.total - shown)} kết quả - gõ thêm chữ để thu hẹp.` : "";
  return `${count(progress.total)} kết quả.${more}${failed}`;
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
    const timer = window.setTimeout(() => {
      void searchBook({
        chapters: chapterList,
        load: (chapter) => {
          const full = chapterList.find((item) => item.id === chapter.id)!;
          return client.fetchQuery({ ...chapterScriptQuery(source, bookId, full), gcTime: 60_000 });
        },
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
    <Dialog open={open} onOpenChange={onOpenChange} width="max-w-xl" title="Tìm trong sách" description={book.title}>
      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-fg-3" />
        <input
          data-autofocus
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && hits[0]) pick(hits[0]);
            // ↓ từ ô tìm xuống kết quả đầu; trong danh sách ↑/↓ đi giữa các kết quả, ↑ ở kết quả đầu về ô tìm.
            else if (event.key === "ArrowDown" && hits.length) {
              event.preventDefault();
              results.current?.querySelector<HTMLElement>("button")?.focus();
            }
          }}
          aria-label="Chữ hay câu cần tìm"
          placeholder="Chữ hay câu cần tìm…"
          autoComplete="off"
          enterKeyHint="search"
          className="h-11 w-full rounded-xl border border-line bg-bg pl-9 pr-3 text-base outline-none focus:border-accent"
        />
      </div>
      <p role="status" className="mt-2 text-xs text-fg-2">
        {status}
      </p>
      {hits.length > 0 && (
        <ul
          ref={results}
          onKeyDown={(event) => {
            const step = event.key === "ArrowDown" ? 1 : event.key === "ArrowUp" ? -1 : 0;
            if (!step) return;
            const buttons = [...event.currentTarget.querySelectorAll<HTMLElement>("button")];
            const next = buttons.indexOf(document.activeElement as HTMLElement) + step;
            event.preventDefault();
            if (next < 0) event.currentTarget.parentElement?.querySelector<HTMLElement>("input")?.focus();
            else buttons[Math.min(next, buttons.length - 1)]?.focus();
          }}
          className="-mx-2 mt-2 max-h-[min(55dvh,28rem)] divide-y divide-line overflow-y-auto overscroll-contain"
        >
          {hits.map((hit) => (
            <li key={`${hit.chapterId}:${hit.sentence}`}>
              <button type="button" onClick={() => pick(hit)} className="block w-full rounded-lg px-2 py-2.5 text-left hover:bg-hover">
                <span className="block truncate text-xs font-medium text-fg-2">{labels.get(hit.chapterId)}</span>
                <span className="mt-0.5 block text-sm leading-relaxed">
                  <Excerpt snippet={hit.snippet} />
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </Dialog>
  );
}
