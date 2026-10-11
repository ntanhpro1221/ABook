import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Check, Clock, Ear, FileText, ListMusic, Loader2, PenLine, Play, RotateCcw, ShieldCheck, Square, VolumeX } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { useClip, type ClipSource } from "@/listen/clip";
import { cn } from "@/shared/cn";
import { formatPercent } from "@/shared/format";
import { Button, EmptyState, Kbd, Segmented, Vu } from "@/shared/ui";
import { api, urls } from "./api";
import { useCachedBook } from "./data";
import { retryUnlessGone } from "./polling";
import { usePendingNote } from "./decisions";
import { matchPhrase, notRecordedYet, shortcutHint, spokenEditLabel } from "./reviewText";

// "Cần nghe lại": câu mà khâu tự kiểm tra không chắc (webui/reviews.py). Nghe từng câu, bấm Ổn hoặc Cần thu lại.
// "Cần thu lại" ghi một yêu cầu cho dây chuyền (overrides.json `retakes`): câu được thu lại bằng hạt giống MỚI ở lần chạy
// tới - sách đã xong thì nút "Áp dụng thay đổi" ở trang dự án. Lỗi đọc sai chữ/tên thì sửa ở tab Kịch bản, thu lại y chữ
// không chữa được.

type Kind = "failed" | "unverified" | "name-low" | "text-low" | "name" | "text";

interface ReviewItem {
  segmentId: number;
  stableId: string;
  chapterId: number;
  chapterTitle: string;
  text: string;
  heard: string;
  similarity: number | null;
  speaker: string;
  kind: Kind;
  reason: string;
  playable: boolean;
  /** WAV riêng đã dọn nhưng câu có mốc trong file chương: nghe đoạn [start, end] giây của chương. */
  chapterClip: { start: number; end: number } | null;
  verdict: "ok" | "redo" | null;
  /** Băm chữ câu (rỗng ở sách rất cũ: không sửa chữ đem đọc được). */
  textSha256: string;
  /** Chữ đem đọc đã áp (null = đọc đúng chữ sách) và chữ người nghe vừa ghi mà chưa áp ("" = trả về chữ sách). */
  spoken: string | null;
  pendingSpoken: string | null;
}

/** Thứ để nghe một câu: bản thu riêng, hay đúng đoạn ấy trong file chương; null = chưa có gì để nghe. */
const clipOf = (bookId: string, item: ReviewItem): ClipSource | null =>
  item.playable
    ? { src: urls.sample(bookId, item.segmentId) }
    : item.chapterClip && { src: urls.chapterAudio(bookId, item.chapterId), ...item.chapterClip };

/** Câu đã có cách xử lý: phán quyết, hay chữ đem đọc mới đang chờ áp. */
const handled = (item: ReviewItem) => Boolean(item.verdict) || item.pendingSpoken !== null;
/** Cùng chữ, bỏ qua dấu câu và hoa thường: “Tách tách tách.” và “Tách tách tách!” là một câu tượng thanh. */
const letters = (text: string) => text.toLowerCase().replace(/[^\p{L}\p{N}]+/gu, " ").trim();
const sameText = (left: string, right: string) => letters(left) === letters(right);

interface ReviewView {
  counts: Record<Kind, number>;
  pending: number;
  redoChapters: number[];
  items: ReviewItem[];
}

const KIND_LABEL: Record<Kind, string> = {
  failed: "Hỏng",
  unverified: "Chưa kiểm được",
  "name-low": "Tên riêng lệch nhiều",
  // Câu lệch không vì tên riêng (soát UX a24): không gọi là "tên riêng".
  "text-low": "Đọc lệch nhiều",
  name: "Tên riêng lệch ít",
  text: "Đọc lệch ít",
};

const KIND_TONE: Record<Kind, string> = {
  failed: "bg-danger-soft text-danger",
  unverified: "bg-warning-soft text-warning",
  "name-low": "bg-info-soft text-info",
  "text-low": "bg-info-soft text-info",
  name: "bg-hover text-fg-2",
  text: "bg-hover text-fg-2",
};

export function useReviewCount(bookId: string) {
  const { data } = useQuery({
    queryKey: ["review", bookId, false],
    queryFn: () => api<ReviewView>(`/api/books/${bookId}/review`),
    enabled: Boolean(bookId),
    staleTime: 30_000,
    retry: retryUnlessGone,
    retryOnMount: false,
  });
  return data?.pending ?? 0;
}

const EMPTY = "empty";

type OpenScript = (chapterId: number, stableId: string) => void;

// Sửa chữ đem đọc ngay trên thẻ (soát UX a5/a6 01-10): câu tượng thanh ("Tách tách tách", "Coong…") hay chữ lạ hỏng sau mọi
// lần thử thì thu lại y chữ cũng hỏng y như cũ - viết lại thành chữ máy đọc được mới chữa được. Chữ của sách không đổi; câu
// được thu lại bằng chữ mới khi sách chạy tiếp. Câu giống hệt (tượng thanh hay lặp) sửa một lần cho cả nhóm.
function SpokenEditor({
  bookId,
  item,
  twins,
  onDone,
}: {
  bookId: string;
  item: ReviewItem;
  twins: ReviewItem[];
  onDone: (saved: string | null) => void;
}) {
  const [value, setValue] = useState(item.pendingSpoken ?? item.spoken ?? item.text);
  const [busy, setBusy] = useState(false);
  const save = async (lines: ReviewItem[]) => {
    setBusy(true);
    try {
      const spoken = value.trim() === item.text.trim() ? "" : value.trim();
      for (const line of lines) {
        await api(`/api/books/${bookId}/line`, { method: "POST", body: { stableId: line.stableId, textSha256: line.textSha256, spoken } });
      }
      toast.success(lines.length > 1 ? `Đã ghi cách đọc cho ${lines.length} câu` : "Đã ghi cách đọc câu này", {
        description: "Chữ của sách giữ nguyên; câu được thu lại bằng chữ mới.",
      });
      onDone(spoken);
    } catch (error) {
      toast.error("Chưa ghi được", { description: (error as Error).message });
    } finally {
      setBusy(false);
    }
  };
  return (
    <form
      className="mt-2 rounded-lg border border-line bg-panel p-2.5"
      onSubmit={(event) => {
        event.preventDefault();
        void save([item]);
      }}
    >
      <label htmlFor={`spoken-${item.stableId}`} className="text-xs font-medium text-fg-2">
        Máy đọc câu này thành
      </label>
      <input
        id={`spoken-${item.stableId}`}
        value={value}
        autoFocus
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Escape") onDone(null);
        }}
        className="mt-1 h-9 w-full rounded-lg border border-line bg-bg px-2.5 text-[15px] outline-none focus-visible:border-accent"
      />
      <p className="mt-1 text-xs text-fg-3">Viết như cách đọc thành tiếng, ví dụ “Tách tách tách” thành “tách, tách, tách”. Để trống là đọc đúng chữ sách.</p>
      <div className="mt-2 flex flex-wrap gap-1.5">
        <Button type="submit" size="sm" variant="primary" loading={busy} disabled={!value.trim() && !item.spoken}>
          Lưu
        </Button>
        {twins.length > 0 && (
          <Button size="sm" variant="secondary" disabled={busy} onClick={() => void save([item, ...twins])}>
            Lưu cho cả {twins.length + 1} câu giống hệt
          </Button>
        )}
        <Button size="sm" variant="ghost" disabled={busy} onClick={() => onDone(null)}>
          Huỷ
        </Button>
      </div>
    </form>
  );
}

function Row({
  bookId,
  item,
  twins,
  onVerdict,
  onOpenScript,
  onSpoken,
}: {
  bookId: string;
  item: ReviewItem;
  twins: ReviewItem[];
  onVerdict: (verdict: ReviewItem["verdict"]) => void;
  onOpenScript?: OpenScript;
  onSpoken: () => void;
}) {
  const clip = useClip();
  const pendingNote = usePendingNote(bookId);
  const [editing, setEditing] = useState(false);
  const id = `review-${item.segmentId}`;
  const playing = clip.current === id;
  const source = clipOf(bookId, item);
  // Câu hỏng chưa từng có bản thu; câu khác có thể đã mất WAV riêng khi dọn dẹp. Nút tắt thì phải nói vì sao.
  const unplayable = item.kind === "failed" ? "Câu này chưa thu được, chưa có gì để nghe" : "Bản thu riêng của câu này đã được dọn sau khi ghép chương - nghe câu này trong chương";
  return (
    <li
      data-review-row={item.stableId}
      className={cn("grid grid-cols-[40px_minmax(0,1fr)_auto] items-start gap-3 rounded-xl px-3 py-3", handled(item) && !editing ? "opacity-70" : "hover:bg-hover")}
    >
      {source ? (
        <button
          type="button"
          aria-label={playing ? "Dừng" : `Nghe câu: ${item.text}`}
          onClick={() => clip.toggle(id, source)}
          className={cn(
            "grid size-10 place-items-center rounded-full transition-colors",
            playing ? "bg-accent text-accent-ink" : "bg-hover text-fg hover:bg-line",
          )}
        >
          {playing && clip.loading ? <Loader2 className="size-4 animate-spin" /> : playing ? <Vu className="h-3" /> : <Play className="size-4 translate-x-[1px]" fill="currentColor" strokeWidth={0} />}
        </button>
      ) : (
        // Không có gì để nghe thì không có nút ▶ nhìn như bấm được: một dấu nói thẳng lý do (câu hỏng / đã dọn bản thu).
        <span
          role="img"
          aria-label={unplayable}
          title={unplayable}
          className={cn("grid size-10 place-items-center rounded-full", item.kind === "failed" ? "bg-danger-soft text-danger" : "bg-hover text-fg-3")}
        >
          {item.kind === "failed" ? <AlertTriangle className="size-4" /> : <VolumeX className="size-4" />}
        </span>
      )}
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className={cn("rounded-md px-1.5 py-0.5 font-semibold", KIND_TONE[item.kind])}>{KIND_LABEL[item.kind]}</span>
          <span className="text-fg-2">{item.chapterTitle}</span>
          {item.speaker && <span className="text-fg-2">· {item.speaker}</span>}
          {item.similarity !== null && (
            <span className="tabular text-fg-2" title="Máy nghe lại bản thu và so với chữ của câu: 100% là nghe ra đúng từng chữ">
              · {matchPhrase(formatPercent(item.similarity))}
            </span>
          )}
        </div>
        <p className="mt-1 text-[15px] leading-snug">{item.text}</p>
        {item.heard && (
          <p className="mt-1 text-[13px] leading-snug text-fg-2">
            <Ear className="mr-1 inline size-3.5 -translate-y-px" />
            Máy nghe ra: “{item.heard}”
          </p>
        )}
        <p className="mt-1 text-xs text-fg-2">{item.reason}</p>
        {!source && <p className="mt-1 text-xs text-fg-2">{unplayable}.</p>}
        {item.pendingSpoken !== null ? (
          <p className="mt-1 flex items-start gap-1.5 text-xs text-fg-2">
            <Clock className="mt-px size-3.5 shrink-0" />
            <span>
              {item.pendingSpoken ? <>Sẽ đọc là “<span className="text-fg">{item.pendingSpoken}</span>”</> : "Sẽ đọc lại đúng chữ sách"} - {pendingNote}.
            </span>
          </p>
        ) : (
          item.spoken && (
            <p className="mt-1 text-xs text-fg-2">
              Đang đọc là: <span className="text-fg">{item.spoken}</span>
            </p>
          )
        )}
        {editing ? (
          <SpokenEditor
            bookId={bookId}
            item={item}
            twins={twins}
            onDone={(saved) => {
              setEditing(false);
              if (saved !== null) onSpoken();
            }}
          />
        ) : (
          item.textSha256 && (
            <button
              type="button"
              onClick={() => setEditing(true)}
              className="mt-1.5 mr-3 inline-flex items-center gap-1 text-xs font-medium text-accent-text hover:underline"
            >
              <PenLine className="size-3.5" /> {spokenEditLabel(twins.length)}
            </button>
          )
        )}
        {onOpenScript && (item.verdict === "redo" || item.kind === "failed") && (
          <button
            type="button"
            onClick={() => onOpenScript(item.chapterId, item.stableId)}
            className="mt-1.5 inline-flex items-center gap-1 text-xs font-medium text-accent-text hover:underline"
          >
            <FileText className="size-3.5" /> Sửa câu này ở tab Kịch bản
          </button>
        )}
      </div>
      <div className="flex gap-1.5">
        {/* Không có gì để nghe thì không phán "Ổn" được - chỉ còn thu lại (soát UX 29-09). */}
        {source && (
          <button
            type="button"
            aria-pressed={item.verdict === "ok"}
            onClick={() => onVerdict(item.verdict === "ok" ? null : "ok")}
            className={cn(
              "inline-flex h-9 items-center gap-1.5 rounded-lg px-3 text-sm font-medium",
              item.verdict === "ok" ? "bg-success-soft text-success" : "border border-line hover:bg-hover",
            )}
          >
            <Check className="size-4" /> Ổn
          </button>
        )}
        <button
          type="button"
          aria-pressed={item.verdict === "redo"}
          onClick={() => onVerdict(item.verdict === "redo" ? null : "redo")}
          className={cn(
            "inline-flex h-9 items-center gap-1.5 rounded-lg px-3 text-sm font-medium",
            item.verdict === "redo" ? "bg-danger-soft text-danger" : "border border-line hover:bg-hover",
          )}
        >
          <RotateCcw className="size-4" /> {source ? "Cần thu lại" : "Thu lại câu này"}
        </button>
      </div>
    </li>
  );
}

export function ReviewQueue({ bookId, onOpenScript }: { bookId: string; onOpenScript?: OpenScript }) {
  const client = useQueryClient();
  const [showMinor, setShowMinor] = useState(false);
  const [filter, setFilter] = useState<"todo" | "done">("todo");
  const [focusAfter, setFocusAfter] = useState<string | null>(null);
  useEffect(() => {
    if (!focusAfter) return;
    const row = document.querySelector<HTMLElement>(`[data-review-row="${CSS.escape(focusAfter)}"]`);
    (row?.querySelector<HTMLElement>("button:not(:disabled)") ?? row)?.focus();
    setFocusAfter(null);
  });
  // "Nghe liền" (soát UX a6 01-10, E3): phát lần lượt mọi câu nghe được, phán bằng phím O / R ngay lúc nghe - không phải bấm
  // nghe rồi bấm phán từng câu. Câu vừa phán rời danh sách và câu kế phát luôn.
  const clip = useClip();
  const [continuous, setContinuous] = useState(false);
  const live = useRef<{ items: ReviewItem[]; judge: (index: number, value: ReviewItem["verdict"]) => void }>({
    items: [],
    judge: () => undefined,
  });
  const playing = useRef<{ id: string | null; index: number }>({ id: null, index: 0 });
  const playAt = (from: number) => {
    const next = live.current.items.slice(Math.max(from, 0)).find((item) => clipOf(bookId, item));
    const source = next && clipOf(bookId, next);
    if (!next || !source) {
      setContinuous(false);
      toast.success("Đã nghe hết các câu trong danh sách");
      return;
    }
    clip.toggle(`review-${next.segmentId}`, source);
    document.querySelector(`[data-review-row="${CSS.escape(next.stableId)}"]`)?.scrollIntoView({ block: "nearest" });
  };
  useEffect(() => {
    const was = playing.current.id;
    if (clip.current?.startsWith("review-")) {
      const index = live.current.items.findIndex((item) => `review-${item.segmentId}` === clip.current);
      playing.current = { id: clip.current, index: Math.max(index, 0) };
      return;
    }
    playing.current = { ...playing.current, id: null };
    if (!continuous || clip.current !== null || !was) return;
    // Câu vừa nghe còn trong danh sách thì sang câu sau nó; đã phán (rời danh sách) thì câu sau dồn lên đúng chỗ ấy.
    const still = live.current.items.findIndex((item) => `review-${item.segmentId}` === was);
    playAt(still >= 0 ? still + 1 : playing.current.index);
    // playAt đọc qua ref - chỉ chạy lại khi clip đổi hay bật / tắt nghe liền.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clip.current, continuous]);
  useEffect(() => {
    if (!continuous) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.ctrlKey || event.metaKey || event.altKey) return;
      if (event.target instanceof Element && event.target.closest("input, textarea, select, [contenteditable=true]")) return;
      const key = event.key.toLowerCase();
      if (key !== "o" && key !== "r") return;
      const index = live.current.items.findIndex((item) => `review-${item.segmentId}` === playing.current.id);
      if (index < 0) return;
      event.preventDefault();
      live.current.judge(index, key === "o" ? "ok" : "redo");
      clip.stop(); // sang câu kế ngay (hiệu ứng ở trên bắt lúc clip dừng)
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [continuous, clip]);
  const unrecorded = notRecordedYet(useCachedBook(bookId).data?.book.segments);
  const { data, isLoading } = useQuery({
    queryKey: ["review", bookId, showMinor],
    queryFn: () => api<ReviewView>(`/api/books/${bookId}/review${showMinor ? "?all=1" : ""}`),
  });
  const verdict = useMutation({
    mutationFn: (body: { stableId: string; chapterId: number; verdict: ReviewItem["verdict"] }) =>
      api(`/api/books/${bookId}/review`, { method: "POST", body }),
    onMutate: async (body) => {
      // Cập nhật ngay trên màn hình; hỏi lại máy chủ sau.
      const key = ["review", bookId, showMinor];
      const previous = client.getQueryData<ReviewView>(key);
      if (previous) {
        client.setQueryData<ReviewView>(key, {
          ...previous,
          items: previous.items.map((item) => (item.stableId === body.stableId ? { ...item, verdict: body.verdict } : item)),
        });
      }
    },
    onSettled: () => {
      void client.invalidateQueries({ queryKey: ["review", bookId] });
      // "Cần thu lại" là một yêu cầu cho dây chuyền: trang dự án đếm nó vào nút "Áp dụng thay đổi".
      void client.invalidateQueries({ queryKey: ["book", bookId] });
      void client.invalidateQueries({ queryKey: ["library"] });
    },
  });

  const refresh = () => {
    void client.invalidateQueries({ queryKey: ["review", bookId] });
    void client.invalidateQueries({ queryKey: ["book", bookId] });
    void client.invalidateQueries({ queryKey: ["library"] });
    void client.invalidateQueries({ queryKey: ["casting", bookId] });
  };
  if (isLoading || !data) return <div className="mt-6 text-sm text-fg-2">Đang tìm các câu cần nghe lại…</div>;
  const items = data.items.filter((item) => (filter === "todo" ? !handled(item) : handled(item)));
  const judge = (index: number, value: ReviewItem["verdict"]) => {
    const item = items[index];
    // Câu vừa phán rời danh sách đang lọc: đưa tiêu điểm sang câu kế (hay câu trước), đừng để nó rơi về đầu trang.
    const leaves = filter === "todo" ? value !== null : value === null;
    if (leaves) setFocusAfter((items[index + 1] ?? items[index - 1])?.stableId ?? EMPTY);
    verdict.mutate({ stableId: item.stableId, chapterId: item.chapterId, verdict: value });
  };
  const minor = (data.counts.name ?? 0) + (data.counts.text ?? 0);
  live.current = { items, judge };
  const playableCount = items.filter((item) => clipOf(bookId, item)).length;
  return (
    <div className="mt-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-fg-2 text-pretty">
          {data.pending ? (
            <>
              Còn <span className="font-semibold text-fg">{data.pending} câu</span> máy tự kiểm không chắc - nghe bằng tai rồi bấm Ổn hoặc
              Cần thu lại. Câu hỏng (chưa thu được) không có gì để nghe: sửa cách máy đọc câu ấy - tiếng động, chữ lạ - hay thu lại.
            </>
          ) : unrecorded ? (
            "Chưa có câu nào để kiểm - sẽ có sau khi thu âm."
          ) : (
            "Đã xem hết các câu đáng lo."
          )}
        </p>
        <Segmented<"todo" | "done">
          label="Lọc"
          value={filter}
          onChange={setFilter}
          options={[
            { value: "todo", label: "Chưa xem" },
            { value: "done", label: "Đã xem" },
          ]}
        />
      </div>
      {playableCount > 1 && (
        <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1.5">
          {continuous ? (
            <Button size="sm" variant="secondary" icon={Square} onClick={() => { setContinuous(false); clip.stop(); }}>
              Dừng nghe liền
            </Button>
          ) : (
            <Button size="sm" variant="secondary" icon={ListMusic} onClick={() => { setContinuous(true); playAt(0); }}>
              Nghe liền {playableCount} câu
            </Button>
          )}
          {shortcutHint(continuous) && (
            <span className="hidden items-center gap-1.5 text-xs text-fg-3 md:inline-flex">
              Đang nghe liền: <Kbd>O</Kbd> Ổn · <Kbd>R</Kbd> Cần thu lại - rồi sang câu kế
            </span>
          )}
        </div>
      )}
      {data.redoChapters.length > 0 && (
        <p className="mt-3 rounded-xl bg-danger-soft px-4 py-2.5 text-sm text-danger text-pretty">
          {data.redoChapters.length} chương có câu cần thu lại - các câu ấy được thu lại thành bản mới khi sách chạy tiếp (sách
          đã xong: nút “Áp dụng thay đổi” ở trang dự án). Câu đọc sai chữ hay sai tên thì sửa ở tab Kịch bản.
        </p>
      )}
      {items.length ? (
        <ul className="mt-3 space-y-1">
          {items.map((item, index) => (
            <Row
              key={item.stableId}
              bookId={bookId}
              item={item}
              twins={items.filter((other) => other.stableId !== item.stableId && other.textSha256 && sameText(other.text, item.text))}
              onVerdict={(value) => judge(index, value)}
              onOpenScript={onOpenScript}
              onSpoken={() => {
                setFocusAfter((items[index + 1] ?? items[index - 1])?.stableId ?? EMPTY);
                refresh();
              }}
            />
          ))}
        </ul>
      ) : (
        <div data-review-row={EMPTY} tabIndex={-1} className="rounded-xl outline-none">
          <EmptyState icon={ShieldCheck} title={filter === "todo" ? (unrecorded ? "Chưa có câu nào để kiểm" : "Không còn câu nào cần xem") : "Chưa đánh dấu câu nào"} className="mt-4">
            {filter === "todo"
              ? unrecorded
                ? "Máy kiểm từng câu ngay khi thu xong; câu nào đáng lo sẽ hiện ở đây."
                : "Mọi câu đáng lo đều đã có phán quyết."
              : "Nghe một câu rồi bấm Ổn hoặc Cần thu lại."}
          </EmptyState>
        </div>
      )}
      {minor > 0 && (
        <button type="button" onClick={() => setShowMinor((value) => !value)} className="mt-4 text-sm font-medium text-fg-2 hover:text-fg">
          {showMinor ? "Ẩn" : "Hiện"} {minor} câu lệch ít (thường vẫn ổn)
        </button>
      )}
    </div>
  );
}
