import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pause, Play, Search, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { useClip } from "@/listen/clip";
import { useCast } from "@/listen/source";
import { cn } from "@/shared/cn";
import { formatNumber, shownReading } from "@/shared/format";
import { Button } from "@/shared/ui";
import { api, suggestionOf, urls, type BookSummary } from "./api";
import { ReadingProblem } from "./ReadingProblem";
import { SharedReadingsOffer, useSharedEntry } from "./sharedReadings";
import { refreshAfterDecision, UNDO_MS, undoAction, useWhenApplied } from "./decisions";

// Tab Nhân vật, mục "Cách đọc tên" (webui/name_readings.py): mọi tên riêng máy đọc thế nào - kể cả tên máy chắc và cách
// người nghe đã chọn, hai thứ hộp việc không bao giờ hỏi lại. Sửa ở đây đi đúng đường của thẻ cách đọc: ghi mong muốn,
// dây chuyền áp ở ranh giới chương và thu lại những câu có tên ấy.

interface NameReading {
  surface: string;
  spoken: string;
  /** Cách đọc đang nằm trong sách là người nghe chọn (không phải máy đoán). */
  byListener: boolean;
  lines: number;
  /** Cách đọc người nghe đã ghi mà dây chuyền chưa áp. */
  requested: string | null;
  example: { segmentId: number; chapterTitle: string; seq: number; text: string; hasAudio: boolean } | null;
}

const PAGE = 30;

export function useNameReadings(bookId: string) {
  return useQuery({
    queryKey: ["pronunciations", bookId],
    queryFn: () => api<{ items: NameReading[]; unseen: number }>(`/api/books/${bookId}/pronunciations`),
  });
}

/** So tên không phân biệt hoa thường, dấu, gạch nối hay khoảng trắng: gõ "hen" thấy "Hên-cơ", "dac lat" thấy "Đác-lát",
 *  "lusien" thấy "Lu-si-en" (soát UX 29-09: đ không tự bỏ dấu khi tách NFD, gạch nối chặn khớp). */
/** Sách đã phân tích xong chưa - đọc bản của trang dự án trong bộ nhớ đệm (không hỏi thêm máy chủ); không có bản ấy thì
 *  coi như đã phân tích (cách hiện cũ). */
function useAnalyzed(bookId: string): boolean {
  const book = useQuery<{ book: BookSummary }>({ queryKey: ["book", bookId], enabled: false }).data?.book;
  return !book || (book.segments.total > 0 && book.segments.analyzed === book.segments.total);
}

function fold(text: string): string {
  return text.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase().replace(/đ/g, "d").replace(/[\s\-‐-―]/g, "");
}

/** `focus`: mở từ nút "Mọi cách đọc tên…" trên thẻ hộp việc - cuộn tới mục khi danh sách đã tải; `name`: tên của thẻ ấy,
 *  điền sẵn vào ô tìm. */
export function NameReadings({ bookId, focus = false, name = "" }: { bookId: string; focus?: boolean; name?: string }) {
  const { data } = useNameReadings(bookId);
  const analyzed = useAnalyzed(bookId);
  // Dàn nhân vật đứng TRÊN mục này: cuộn khi nó đã hiện (cùng truy vấn với CastList, không tải thêm) - cuộn sớm hơn thì
  // dàn nhân vật hiện ra sau đẩy mục xuống khỏi màn.
  const { isSuccess: castShown } = useCast(bookId);
  useEffect(() => {
    if (!focus || !data || !castShown) return;
    const frame = requestAnimationFrame(() =>
      document.getElementById("name-readings-title")?.scrollIntoView({ block: "start", behavior: "smooth" }),
    );
    return () => cancelAnimationFrame(frame);
  }, [focus, data, castShown]);
  const [query, setQuery] = useState(name);
  const [limit, setLimit] = useState(PAGE);
  useEffect(() => {
    if (name) setQuery(name);
  }, [name]);
  if (!data || (!data.items.length && !data.unseen)) return null;
  const typed = query.trim();
  const needle = fold(typed);
  const found = needle
    ? data.items.filter((item) => fold(item.surface).includes(needle) || fold(item.requested ?? item.spoken).includes(needle))
    : data.items;
  // Tên chưa có dòng nào (máy không coi là tên riêng, hay chưa gặp): gõ đúng một từ mà KHÔNG khớp tên nào thì mời thêm cách
  // đọc cho nó - chỉ là một nút; ô nhập chỉ mở khi bấm (soát UX 29-09: ô mở sẵn giành con trỏ ngay sau chữ đầu, "Lan"+Enter
  // thành luật "L đọc là an" cho cả cuốn).
  const addable = !found.length && /^[\p{L}\p{M}'’-]+$/u.test(typed);
  const counted = data.items.filter((item) => item.lines > 0).length;
  return (
    <section className="mt-8" aria-labelledby="name-readings-title">
      <h3 id="name-readings-title" className="scroll-mt-16 text-sm font-semibold">
        Cách đọc tên{" "}
        <span className="font-normal text-fg-2">
          · {analyzed ? `${formatNumber(counted)} tên trong phần này` : "chưa phân tích - tên hiện ra sau bước ấy"}
        </span>
      </h3>
      <p className="mt-1 max-w-prose text-sm text-fg-2">
        Tên riêng máy đọc thế nào. Nghe câu mẫu, sai thì sửa ngay trên dòng - các câu có tên ấy sẽ được thu lại.
      </p>
      <SharedReadingsOffer bookId={bookId} />
      <div className="relative mt-3 max-w-sm">
        <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-fg-3" aria-hidden />
        <input
          id="name-readings-search"
          type="search"
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            setLimit(PAGE);
          }}
          placeholder="Tìm tên, hoặc gõ một tên để thêm cách đọc"
          aria-label="Tìm tên"
          autoComplete="off"
          spellCheck={false}
          className="h-9 w-full rounded-lg border border-line bg-panel pl-8 pr-8 text-sm outline-none focus-visible:border-accent [&::-webkit-search-cancel-button]:hidden"
        />
        {query && (
          <button
            type="button"
            onClick={() => setQuery("")}
            aria-label="Xoá ô tìm"
            className="absolute right-1.5 top-1/2 grid size-6 -translate-y-1/2 place-items-center rounded-md text-fg-3 hover:text-fg"
          >
            <X className="size-3.5" />
          </button>
        )}
      </div>
      {(found.length > 0 || addable) && (
        <ul className="mt-3 divide-y divide-line rounded-xl border border-line bg-panel">
          {found.slice(0, limit).map((item) => (
            <ReadingRow key={item.surface} bookId={bookId} item={item} />
          ))}
          {addable && <ReadingRow key={`new-${typed}`} bookId={bookId} item={{ surface: typed, spoken: "", byListener: false, lines: 0, requested: null, example: null }} fresh />}
        </ul>
      )}
      {!found.length && !addable && typed && <p className="mt-3 text-sm text-fg-2">Không có tên nào khớp “{typed}”.</p>}
      {found.length > limit && (
        <button type="button" onClick={() => setLimit((value) => value + PAGE * 3)} className="mt-3 text-sm font-medium text-fg-2 hover:text-fg">
          Xem thêm {formatNumber(found.length - limit)} tên
        </button>
      )}
      {data.unseen > 0 && !typed && (
        <p className="mt-2 text-xs text-fg-3">{formatNumber(data.unseen)} tên khác của cuốn không có câu nào trong phần này.</p>
      )}
    </section>
  );
}

function ReadingRow({ bookId, item, fresh = false }: { bookId: string; item: NameReading; fresh?: boolean }) {
  const analyzed = useAnalyzed(bookId);
  const sharedHere = useSharedEntry(item.surface, item.requested ?? item.spoken);
  const clip = useClip();
  const [editing, setEditing] = useState(false);
  const example = item.example;
  const id = example ? `reading-${example.segmentId}` : "";
  const playing = Boolean(id) && clip.current === id;
  return (
    <li className="flex flex-wrap items-center gap-x-3 gap-y-2 px-3 py-2.5">
      {example?.hasAudio ? (
        <button
          type="button"
          onClick={() => clip.toggle(id, urls.sample(bookId, example.segmentId))}
          aria-label={playing ? "Dừng" : `Nghe câu có ${item.surface}: ${example.text}`}
          title={`${example.chapterTitle} · câu ${example.seq}`}
          className="grid size-8 shrink-0 place-items-center rounded-full bg-hover text-fg-2 hover:text-fg"
        >
          {playing ? <Pause className="size-3.5" fill="currentColor" strokeWidth={0} /> : <Play className="size-3.5 translate-x-[1px]" fill="currentColor" strokeWidth={0} />}
        </button>
      ) : (
        <span className="size-8 shrink-0" aria-hidden />
      )}
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-baseline gap-x-1.5">
          <span className="font-semibold">{item.surface}</span>
          {item.spoken && (
            <>
              <span className="text-sm text-fg-2">đọc là</span>
              <span className="whitespace-nowrap font-medium">“{shownReading(item.spoken)}”</span>
            </>
          )}
        </div>
        <div className="tabular text-xs text-fg-2">
          {fresh
            ? "Không có trong danh sách - máy đọc theo chữ"
            : !analyzed && !item.lines
              ? "chưa phân tích tới"
              : `${formatNumber(item.lines)} câu · ${item.byListener ? "đã chọn" : item.spoken ? "máy đoán" : "chưa có trong sách"}`}
          {sharedHere && <span className="text-fg-3"> · dùng chung</span>}
          {item.requested && (
            <span className="font-medium text-accent-text">
              {" "}
              · chờ áp dụng: <span className="whitespace-nowrap">“{item.requested}”</span>
            </span>
          )}
        </div>
      </div>
      {editing ? (
        <EditReading bookId={bookId} item={item} onDone={() => setEditing(false)} fresh={fresh} />
      ) : (
        <Button size="sm" variant="ghost" onClick={() => setEditing(true)} aria-label={`${fresh ? "Thêm" : "Sửa"} cách đọc ${item.surface}`}>
          {fresh ? `Thêm cách đọc cho “${item.surface}”` : "Sửa"}
        </Button>
      )}
    </li>
  );
}

/** Tên riêng có cách đọc nằm trong một câu - so như TTS khớp: nguyên từ, không phân biệt hoa thường, GIỮ dấu ("hàn" không
 *  phải "Han"). Mỗi tên một lần, theo thứ tự xuất hiện. */
export function useNamesInLine(bookId: string, text: string): NameReading[] {
  const { data } = useNameReadings(bookId);
  return useMemo(() => {
    if (!data) return [];
    const index = new Map(data.items.map((item) => [item.surface.normalize("NFC").toLowerCase(), item]));
    const found = new Map<string, NameReading>();
    for (const word of text.normalize("NFC").match(/[\p{L}\p{M}\p{N}_]+/gu) ?? []) {
      const item = index.get(word.toLowerCase());
      if (item) found.set(item.surface, item);
    }
    return [...found.values()];
  }, [data, text]);
}

/** Một tên trong bảng sửa cách đọc của câu (tab Kịch bản): đọc thế nào + sửa ngay - cho CẢ CUỐN, như mục "Cách đọc tên". */
export function NameInLine({ bookId, item }: { bookId: string; item: NameReading }) {
  const [editing, setEditing] = useState(false);
  // Trình bày như mục "Cách đọc tên" ở tab Nhân vật: đang đọc gì, và (nếu có) cách đọc đang chờ áp dụng.
  return (
    <div className="flex flex-wrap items-center gap-x-2 gap-y-1.5" data-name-editor>
      <span className="min-w-0 flex-1 text-sm">
        <span className="font-semibold">{item.surface}</span>
        {item.spoken && <span className="text-fg-2"> đọc là </span>}
        {item.spoken && <span className="whitespace-nowrap font-medium">“{shownReading(item.spoken)}”</span>}
        {item.requested && (
          <span className="text-xs font-medium text-accent-text">
            {" "}
            · chờ áp dụng: <span className="whitespace-nowrap">“{item.requested}”</span>
          </span>
        )}
      </span>
      {editing ? (
        // Hàng riêng dưới tên: bảng chỉ rộng ~340 px, chung hàng thì tên bị ép thành cột chữ hẹp.
        <div className="w-full">
          <EditReading bookId={bookId} item={item} onDone={() => setEditing(false)} fresh={false} />
        </div>
      ) : (
        <Button size="sm" variant="ghost" onClick={() => setEditing(true)} aria-label={`Sửa cách đọc ${item.surface}`}>
          Sửa
        </Button>
      )}
    </div>
  );
}

function EditReading({ bookId, item, onDone, fresh }: { bookId: string; item: NameReading; onDone: () => void; fresh: boolean }) {
  const client = useQueryClient();
  const when = useWhenApplied(bookId);
  // Ô sửa hiện như dòng bên cạnh (“Rên-ta-rô”, chữ đầu mỗi từ viết hoa - soát UX 30-09); lưu mà chỉ khác hoa thường thì
  // gửi đúng cách đang lưu (`asStored`), không thành một thay đổi bắt thu lại các câu.
  const [value, setValue] = useState(shownReading(item.requested ?? item.spoken ?? ""));
  const asStored = (text: string) =>
    [item.requested, item.spoken].find((saved) => saved && saved.toLocaleLowerCase("vi") === text.toLocaleLowerCase("vi")) ?? text;
  const [problem, setProblem] = useState("");
  const [suggestion, setSuggestion] = useState("");
  // "Dùng cho mọi sách": cùng cách đọc vào từ điển chung (webui/shared_readings.py) - sách mới có tên này tự dùng.
  // Tên đã có trong cách đọc chung: ô tự tích - lưu là sửa luôn mục chung (soát UX 01-10: không biết tên nào đã dùng chung).
  const sharedEntry = useSharedEntry(item.surface);
  const [everywhere, setEverywhere] = useState(Boolean(sharedEntry));
  useEffect(() => {
    if (sharedEntry) setEverywhere(true);
  }, [sharedEntry]);
  const save = useMutation({
    mutationFn: (spokenForm: string) =>
      api<{ surface: string; spokenForm: string; requestedAt: number }>(`/api/books/${bookId}/pronunciation`, {
        method: "POST",
        body: { surface: item.surface, spokenForm, ...(everywhere ? { everywhere: true } : {}) },
      }),
    onSuccess: ({ spokenForm, requestedAt }) => {
      refreshAfterDecision(client, bookId);
      if (everywhere) void client.invalidateQueries({ queryKey: ["shared-readings"] });
      const shared = everywhere ? " Đã thêm vào cách đọc chung - sách mới có tên này tự dùng." : "";
      onDone();
      const keep = spokenForm === item.spoken;
      // Như thẻ trong hộp việc: sửa nhầm thì "Hoàn tác" trả về đúng như trước lần lưu này (`previous` = cách đang đọc).
      const undo = {
        action: undoAction(
          client,
          bookId,
          "pronunciation",
          // `shared`: lần lưu này cũng đưa cách đọc vào từ điển chung - hoàn tác gỡ luôn mục ấy (soát UX 01-10).
          [{ surface: item.surface, requestedAt, previous: item.spoken, keep, ...(everywhere ? { shared: spokenForm } : {}) }],
          (item.requested
            ? `Trở lại cách đọc chờ áp trước đó: “${shownReading(item.requested)}”.`
            : item.spoken
              ? `“${item.surface}” lại đọc là “${shownReading(item.spoken)}”.`
              : `Đã bỏ cách đọc vừa thêm cho “${item.surface}”.`) + (everywhere ? " Đã bỏ khỏi cách đọc chung." : ""),
        ),
        duration: UNDO_MS,
      };
      if (keep) {
        toast.success(`Giữ cách đọc “${shownReading(spokenForm)}”`, { description: `Không phải thu lại câu nào.${shared}`, ...undo });
        return;
      }
      toast.success(`Đã ghi: “${item.surface}” đọc là “${shownReading(spokenForm)}”`, {
        // Tên chưa có câu nào trong phần này (vừa thêm): không có gì để thu lại - nói đúng điều ấy (soát UX 29-09).
        description: item.lines
          ? `Các câu có tên này sẽ được thu lại. ${when}${shared}`
          : `Phần này chưa có câu nào có tên này - cách đọc sẽ được dùng khi tên xuất hiện.${shared}`,
        ...undo,
      });
    },
    onError: (error: Error) => {
      setProblem(error.message);
      setSuggestion(suggestionOf(error));
    },
  });
  const typed = value.trim();
  const inputId = `reading-${fold(item.surface)}`;
  const use = (spoken: string) => {
    setValue(spoken);
    setProblem("");
    setSuggestion("");
    save.mutate(spoken);
  };
  // Lỗi nằm DƯỚI cụm ô nhập, cùng bề rộng với cụm - trước đây dòng lỗi rộng hết dòng kéo cả cụm từ mép phải vào giữa.
  return (
    <div className="flex w-full flex-col gap-1 sm:w-auto sm:max-w-sm">
    <form
      className="flex w-full flex-wrap items-center gap-2"
      onSubmit={(event) => {
        event.preventDefault();
        if (typed) save.mutate(asStored(typed));
      }}
    >
      <input
        id={inputId}
        autoFocus
        value={value}
        onChange={(event) => {
          setValue(event.target.value);
          setProblem("");
          setSuggestion("");
        }}
        onKeyDown={(event) => {
          if (event.key === "Escape") onDone();
        }}
        placeholder="vd Hên-khơ"
        aria-label={`Cách đọc mới cho ${item.surface}`}
        aria-invalid={problem ? true : undefined}
        aria-describedby={problem ? `${inputId}-problem` : undefined}
        spellCheck={false}
        autoComplete="off"
        className={cn(
          "h-8 min-w-0 flex-1 rounded-lg border bg-panel px-2.5 text-sm text-fg outline-none focus-visible:border-accent sm:w-44 sm:flex-none",
          problem ? "border-danger" : "border-line",
        )}
      />
      {/* "Huỷ" trước "Lưu": nút ở đúng chỗ nút "Sửa" vừa bấm là "Lưu" (mờ khi chưa đổi gì) - bấm đúp không huỷ ngay. */}
      <Button size="sm" variant="ghost" type="button" onClick={onDone}>
        Huỷ
      </Button>
      <Button
        size="sm"
        variant="primary"
        type="submit"
        loading={save.isPending}
        // Chưa đổi gì (ô hiện chữ đầu viết hoa - so không phân biệt hoa thường) thì chỉ lưu khi đưa vào cách đọc chung.
        disabled={!typed || (!fresh && !everywhere && asStored(typed) === (item.requested ?? item.spoken))}
      >
        Lưu
      </Button>
      <label className="flex basis-full items-center gap-1.5 text-xs text-fg-2">
        <input type="checkbox" checked={everywhere} onChange={(event) => setEverywhere(event.target.checked)} className="accent-[var(--color-accent)]" />
        Dùng cho mọi sách
      </label>
    </form>
      <ReadingProblem id={`${inputId}-problem`} problem={problem} suggestion={suggestion} onUse={use} className="" />
    </div>
  );
}
