import { S } from "../shared/strings.generated";
import { MoreInfo } from "@/shared/SettingsNav";
import { MotionRegion } from "@/shared/MotionRegion";
import { AnimatedRows } from "@/shared/MotionPresence";
import { useInfiniteQuery, useMutation, useQuery, useQueryClient, type InfiniteData } from "@tanstack/react-query";
import { AlertTriangle, Check, Clock, Ear, FileText, ListMusic, Loader2, PenLine, Play, RotateCcw, ShieldCheck, Square, VolumeX } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { toast } from "@/shared/toast";
import { useClip, type ClipSource } from "@/listen/clip";
import { cn } from "@/shared/cn";
import { formatPercent } from "@/shared/format";
import { DotJoin } from "@/shared/DotJoin";
import { DecisionButton, Button, EmptyState, FilterRow, Kbd, Vu, ContentSkeleton, InlineError } from "@/shared/ui";
import { api, urls } from "./api";
import { useCachedBook } from "./data";
import { retryUnlessGone } from "./polling";
import { useProducingRefetch } from "./liveRefresh";
import { usePendingNote } from "./decisions";
import { letterShortcutsOn } from "@/shared/letterShortcuts";
import { verdictWord, warnElsewhere } from "./elsewhere";
import { matchPhrase, matchShort, notRecordedYet, shortcutHint, spokenEditLabel } from "./reviewText";

// "Cần nghe lại": câu mà khâu tự kiểm tra không chắc (webui/reviews.py). Nghe từng câu, bấm Ổn hoặc Cần thu lại.
// "Cần thu lại" ghi một yêu cầu cho dây chuyền (overrides.json `retakes`): câu được thu lại bằng hạt giống MỚI ở lần chạy
// tới - sách đã xong thì nút "Áp dụng thay đổi" ở trang dự án. Lỗi đọc sai chữ/tên thì sửa ở tab Kịch bản, thu lại y chữ
// không chữa được.

type Kind = "failed" | "unverified" | "name-low" | "text-low" | "name" | "text";

interface ReviewItem {
  segmentId: number;
  stableId: string;
  audioSha256: string;
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
  nextCursor: string | null;
  remaining: number;
}

// Mức nặng nói bằng MÀU CHỮ của dòng lý do, không bằng viên chữ riêng: hỏng và chưa kiểm được cần để ý, lệch nhẹ thì chỉ là chữ phụ (soát 25-10).
const KIND_INK: Record<Kind, string> = {
  failed: "text-danger",
  unverified: "text-warning",
  "name-low": "text-fg-2",
  "text-low": "text-fg-2",
  name: "text-fg-2",
  text: "text-fg-2",
};

export function useReviewCount(bookId: string) {
  const refetchInterval = useProducingRefetch(bookId);
  const { data } = useQuery({
    queryKey: ["review", bookId, false],
    queryFn: () => api<ReviewView>(`/api/books/${bookId}/review`),
    enabled: Boolean(bookId),
    refetchInterval,
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
      toast.success(lines.length > 1 ? S.s_da_ghi_cach_doc_cho_0_cau_2f1fdc9b(lines.length) : S.s_da_ghi_cach_doc_cau_nay_0db96b25);
      onDone(spoken);
    } catch (error) {
      toast.error(S.s_chua_ghi_duoc_9fa87a7d, { description: (error as Error).message });
    } finally {
      setBusy(false);
    }
  };
  return (
    <form
      className="mt-2 py-2.5"
      onSubmit={(event) => {
        event.preventDefault();
        void save([item]);
      }}
    >
      <label htmlFor={`spoken-${item.stableId}`} className="text-xs font-medium text-fg-2">{S.s_cach_doc_94265da7}</label>
      <input
        id={`spoken-${item.stableId}`}
        value={value}
        autoFocus
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Escape") onDone(null);
        }}
        className="mt-1 h-9 w-full rounded-control border border-line bg-bg px-2.5 text-[0.9375rem] outline-none focus-visible:border-focus"
      />
      <p className="mt-1 text-xs text-fg-3">{S.s_viet_cach_doc_thanh_tieng_de_trong_de_dung_0f9e441a}</p>
      <div className="mt-2 flex flex-wrap gap-1.5">
        <Button type="submit" size="sm" variant="primary" loading={busy} disabled={!value.trim() && !item.spoken}>{S.s_luu_e91f26c0}</Button>
        {twins.length > 0 && (
          <Button size="sm" variant="ghost" disabled={busy} onClick={() => void save([item, ...twins])}>{S.s_luu_8c00346c}{twins.length + 1}{S.s_cau_b07e1008}</Button>
        )}
        <Button size="sm" variant="ghost" disabled={busy} onClick={() => onDone(null)}>{S.s_huy_96732485}</Button>
      </div>
    </form>
  );
}

function Row({
  as: Tag = "li",
  bookId,
  item,
  twins,
  onVerdict,
  onOpenScript,
  onSpoken,
}: {
  as?: "li" | "div";
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
  const unplayable = item.kind === "failed" ? S.s_cau_nay_chua_thu_duoc_chua_co_gi_de_nghe_3e5fa33a : S.s_ban_thu_rieng_cua_cau_nay_da_duoc_don_sau_552e64b0;
  return (
    <Tag
      data-review-row={item.stableId}
      className={cn("grid grid-cols-[40px_minmax(0,1fr)] items-start gap-x-3 gap-y-1 rounded-control px-3 py-3 transition-[opacity,background-color] duration-motion-fast sm:grid-cols-[40px_minmax(0,1fr)_auto]", handled(item) && !editing ? "opacity-70" : "hover:bg-hover")}
    >
      {source ? (
        <button
          type="button"
          aria-label={playing ? S.s_dung_11554138 : S.s_nghe_cau_0_4329fb13(item.text)}
          onClick={() => clip.toggle(id, source)}
          className={cn(
            "grid size-10 place-items-center rounded-full transition-colors",
            playing ? "bg-accent text-accent-ink" : "bg-hover text-fg hover:bg-line",
          )}
        >
          <MotionRegion as="span" className="grid size-4 place-items-center">{playing && clip.loading ? <Loader2 className="size-4 animate-spin" /> : playing ? <Vu className="h-3" /> : <Play className="size-4 translate-x-[1px]" fill="currentColor" strokeWidth={0} />}</MotionRegion>
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
        {/* Câu trước, rồi MỘT dòng nói vì sao nó ở đây (lý do · chương). Lý do mang màu mức nặng, không còn viên chữ riêng. */}
        <p className="text-base leading-snug">{item.text}</p>
        <DotJoin className="mt-1 text-xs text-fg-2" parts={[<span key="reason" className={KIND_INK[item.kind]}>{item.reason}</span>, item.chapterTitle]} />
        {/* Máy nghe ra đúng chữ thì không có gì để so - chỉ hiện khi KHÁC câu (soát 25-10). */}
        {item.heard && !sameText(item.heard, item.text) && (
          <p className="mt-1 text-[0.8125rem] leading-snug text-fg-2">
            <Ear className="mr-1 inline size-3.5 -translate-y-px" />{S.s_may_nghe_ra_31219589}{item.heard}”
            {item.similarity !== null && <span className="tabular text-fg-3" title={matchPhrase(formatPercent(item.similarity))}> · {matchShort(formatPercent(item.similarity))}</span>}
          </p>
        )}
        {!source && <p className="mt-1 text-xs text-fg-2">{unplayable}.</p>}
        {item.pendingSpoken !== null ? (
          <p className="mt-1 flex items-start gap-1.5 text-xs text-fg-2">
            <Clock className="mt-px size-3.5 shrink-0" />
            <span>
              {item.pendingSpoken ? <>{S.s_se_doc_la_a0124031}<span className="text-fg">{item.pendingSpoken}</span>”</> : S.s_se_doc_lai_dung_chu_sach_32abc746} - {pendingNote}.
            </span>
          </p>
        ) : (
          item.spoken && (
            <p className="mt-1 text-xs text-fg-2">{S.s_dang_doc_la_00f0085c}<span className="text-fg">{item.spoken}</span>
            </p>
          )
        )}
        <MotionRegion>
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
          // Mở ngữ cảnh dùng mực phụ để hai nút phán quyết giữ vai trò chính.
          <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1">
            {item.textSha256 && (
              <button type="button" onClick={() => setEditing(true)} className="touch-hit inline-flex items-center gap-1 text-xs font-medium text-fg-2 hover:text-fg hover:underline">
                <PenLine className="size-3.5" /> {spokenEditLabel(twins.length)}
              </button>
            )}
            {onOpenScript && (item.verdict === "redo" || item.kind === "failed") && (
              <button type="button" onClick={() => onOpenScript(item.chapterId, item.stableId)} className="touch-hit inline-flex items-center gap-1 text-xs font-medium text-fg-2 hover:text-fg hover:underline">
                <FileText className="size-3.5" />{S.s_mo_kich_ban_c25fa46f}</button>
            )}
          </div>
        )}
        </MotionRegion>
      </div>
      {/* Hai phán quyết là việc chính của hàng: có biểu tượng, cao bằng điều khiển; đã chọn thì mang sắc trạng thái.
          Điện thoại: xuống dưới câu, thẳng mép chữ; máy tính: bên phải, nút cuối kéo lề -12 px để chữ thẳng mép phải nội dung. */}
      <div className="col-start-2 -ml-3.5 flex gap-1 sm:col-start-3 sm:row-start-1 sm:ml-0 sm:-mr-3">
        {/* Không có gì để nghe thì không phán "Ổn" được - chỉ còn thu lại (soát UX 29-09). */}
        {source && (
          <DecisionButton
            variant="ghost"
            icon={Check}
            aria-pressed={item.verdict === "ok"}
            onClick={() => onVerdict(item.verdict === "ok" ? null : "ok")}
            className={item.verdict === "ok" ? "bg-success-soft text-success hover:bg-success-soft hover:text-success" : "text-accent-text hover:text-accent-text"}
          >{S.s_on_cec6d53a}</DecisionButton>
        )}
        <DecisionButton
          variant="ghost"
          icon={RotateCcw}
          aria-pressed={item.verdict === "redo"}
          onClick={() => onVerdict(item.verdict === "redo" ? null : "redo")}
          className={item.verdict === "redo" ? "bg-danger-soft text-danger hover:bg-danger-soft hover:text-danger" : "text-accent-text hover:text-accent-text"}
        >
          {source ? S.s_can_thu_lai_540b83e3 : S.s_thu_lai_cau_nay_034c2834}
        </DecisionButton>
      </div>
    </Tag>
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
  const live = useRef<{ items: ReviewItem[]; judge: (item: ReviewItem, value: ReviewItem["verdict"]) => void }>({
    items: [],
    judge: () => undefined,
  });
  const playing = useRef<{ id: string | null; index: number }>({ id: null, index: 0 });
  const playAt = (from: number) => {
    const next = live.current.items.slice(Math.max(from, 0)).find((item) => clipOf(bookId, item));
    const source = next && clipOf(bookId, next);
    if (!next || !source) {
      setContinuous(false);
      toast.success(S.s_da_nghe_het_cac_cau_trong_danh_sach_3526b3a6);
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
      if (event.ctrlKey || event.metaKey || event.altKey || !letterShortcutsOn()) return;
      if (event.target instanceof Element && event.target.closest("input, textarea, select, [contenteditable=true]")) return;
      const key = event.key.toLowerCase();
      if (key !== "o" && key !== "r") return;
      const index = live.current.items.findIndex((item) => `review-${item.segmentId}` === playing.current.id);
      if (index < 0) return;
      event.preventDefault();
      live.current.judge(live.current.items[index], key === "o" ? "ok" : "redo");
      clip.stop(); // sang câu kế ngay (hiệu ứng ở trên bắt lúc clip dừng)
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [continuous, clip]);
  const unrecorded = notRecordedYet(useCachedBook(bookId).data?.book.segments);
  const refetchInterval = useProducingRefetch(bookId); // sách đang chạy: câu cần nghe lại mới hiện tự (soát a90 V4)
  const { data: pages, isLoading, error, refetch, fetchNextPage, hasNextPage, isFetchingNextPage } = useInfiniteQuery({
    queryKey: ["review", bookId, showMinor, filter],
    initialPageParam: "",
    queryFn: ({ pageParam }) => {
      const query = new URLSearchParams({ filter, ...(showMinor ? { all: "1" } : {}), ...(pageParam ? { cursor: pageParam } : {}) });
      return api<ReviewView>(`/api/books/${bookId}/review?${query}`);
    },
    getNextPageParam: (last) => last.nextCursor ?? undefined,
    refetchInterval,
  });
  const data = pages && { ...pages.pages[0], items: pages.pages.flatMap((page) => page.items) };
  const verdict = useMutation({
    // `seen`: phán quyết màn này đang thấy cho câu - máy/cửa sổ khác vừa quyết khác thì hỏi giữ của mình hay lấy của máy kia (soát a27 lỗi 4).
    mutationFn: (body: { stableId: string; chapterId: number; audioSha256: string; verdict: ReviewItem["verdict"]; seen: ReviewItem["verdict"] }) =>
      api<{ elsewhere?: Record<string, string> }>(`/api/books/${bookId}/review`, {
        method: "POST",
        body: { stableId: body.stableId, chapterId: body.chapterId, audioSha256: body.audioSha256, verdict: body.verdict, seen: { [body.stableId]: body.seen ?? "" } },
      }),
    onSuccess: ({ elsewhere }, body) => {
      const theirs = elsewhere?.[body.stableId];
      if (theirs === undefined) return;
      warnElsewhere(1, verdictWord(theirs), () =>
        void api(`/api/books/${bookId}/review`, {
          method: "POST",
          body: { stableId: body.stableId, chapterId: body.chapterId, audioSha256: body.audioSha256, verdict: theirs || null },
        }).finally(() => void client.invalidateQueries({ queryKey: ["review", bookId] })),
      );
    },
    onMutate: async (body) => {
      // Cập nhật ngay trên màn hình; hỏi lại máy chủ sau.
      const key = ["review", bookId, showMinor, filter];
      await client.cancelQueries({ queryKey: key });
      const previous = client.getQueryData<InfiniteData<ReviewView>>(key);
      if (previous) {
        client.setQueryData<InfiniteData<ReviewView>>(key, {
          ...previous,
          pages: previous.pages.map((page) => ({ ...page,
            items: page.items.map((item) => (item.stableId === body.stableId ? { ...item, verdict: body.verdict } : item)),
          })),
        });
      }
    },
    onSettled: () => {
      void client.invalidateQueries({ queryKey: ["review", bookId] });
      // "Cần thu lại" là một yêu cầu cho dây chuyền: trang dự án đếm nó vào nút "Áp dụng thay đổi".
      void client.invalidateQueries({ queryKey: ["book", bookId] });
      void client.invalidateQueries({ queryKey: ["library"] });
    },
    onError: (error: Error) => toast.error(S.s_chua_ghi_duoc_phan_quyet_nghe_0e587881, { description: error.message }),
  });

  const refresh = () => {
    void client.invalidateQueries({ queryKey: ["review", bookId] });
    void client.invalidateQueries({ queryKey: ["book", bookId] });
    void client.invalidateQueries({ queryKey: ["library"] });
    void client.invalidateQueries({ queryKey: ["casting", bookId] });
  };
  if (error && !data) return <MotionRegion fadeThrough><InlineError className="mt-6" message={S.s_ban_hay_kiem_tra_ket_noi_roi_tai_lai_cau_c_9183426a} onRetry={() => void refetch()} /></MotionRegion>;
  if (isLoading || !data) return <MotionRegion fadeThrough><ContentSkeleton shape="cards" className="mt-6" label={S.s_dang_tai_cau_nghe_eba43082} /></MotionRegion>;
  const items = data.items.filter((item) => (filter === "todo" ? !handled(item) : handled(item)));
  const judge = (item: ReviewItem, value: ReviewItem["verdict"]) => {
    const index = items.findIndex((current) => current.stableId === item.stableId);
    if (index < 0) return; // Hàng đang ra chỉ giữ hình, không được gửi thêm phán quyết.
    // Câu vừa phán rời danh sách đang lọc: đưa tiêu điểm sang câu kế (hay câu trước), đừng để nó rơi về đầu trang.
    const leaves = filter === "todo" ? value !== null : value === null;
    if (leaves) setFocusAfter((items[index + 1] ?? items[index - 1])?.stableId ?? EMPTY);
    verdict.mutate({ stableId: item.stableId, chapterId: item.chapterId, audioSha256: item.audioSha256, verdict: value, seen: item.verdict });
  };
  const minor = (data.counts.name ?? 0) + (data.counts.text ?? 0);
  live.current = { items, judge };
  const playableCount = items.filter((item) => clipOf(bookId, item)).length;
  return (
    <MotionRegion as="div" className="motion-reveal mt-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-fg-2 text-pretty">
          {data.pending ? (
            <>
              <span className="font-semibold text-fg">{data.pending}{S.s_cau_b07e1008}</span>{S.s_nghe_roi_chon_on_hoac_can_thu_lai_1f69221d}</>
          ) : unrecorded ? (
            S.s_chua_co_ban_thu_se_co_sau_khi_thu_am_c61d063f
          ) : (
            S.s_da_xem_het_cac_cau_dang_lo_c91d08e4
          )}
        </p>
        <FilterRow<"todo" | "done">
          label={S.s_loc_8812e325}
          value={filter}
          onChange={setFilter}
          options={[
            { value: "todo", label: S.s_chua_xem_2fb1e370 },
            { value: "done", label: S.s_da_xem_95526f88 },
          ]}
        />
      </div>
      {playableCount > 1 && (
        <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1.5">
          {continuous ? (
            <Button size="sm" variant="ghost" className="-ml-3" icon={Square} onClick={() => { setContinuous(false); clip.stop(); }}>{S.s_dung_nghe_lien_fff6a5f1}</Button>
          ) : (
            <Button size="sm" variant="ghost" className="-ml-3" icon={ListMusic} onClick={() => { setContinuous(true); playAt(0); }}>{S.s_nghe_lien_4fca5416}{playableCount}{S.s_cau_b07e1008}</Button>
          )}
          {shortcutHint(continuous) && (
            <span className="hidden items-center gap-1.5 text-xs text-fg-3 md:inline-flex">{S.s_dang_nghe_lien_58d38e56}<Kbd>{S.s_o_c4694f2e}</Kbd>{S.s_on_eb909324}<Kbd>{S.s_r_8c257489}</Kbd>{S.s_can_thu_lai_roi_sang_cau_ke_2b70eb21}</span>
          )}
        </div>
      )}
      {data.redoChapters.length > 0 && (
        <div className="mt-3 py-2.5 text-sm text-danger">
          <p>{data.redoChapters.length}{S.s_chuong_cho_thu_lai_sua_chu_o_kich_ban_11e7f43e}</p>
          <MoreInfo>{S.s_chay_tiep_hoac_ap_dung_thay_doi_de_thu_lai_7f582c5b}</MoreInfo>
        </div>
      )}
        {/* Đổi bộ lọc: cả danh sách trượt theo hướng mục vừa chọn; danh sách mới dựng lại từ đầu, không lẫn hàng cũ đang mờ ra. */}
        <MotionRegion motionKey={filter} slideIndex={filter === "todo" ? 0 : 1}>
        <AnimatedRows key={filter} className="rows-inset -mx-3 mt-3 [--rows-inset:calc(var(--spacing)*3)]" items={items} keyOf={(item) => item.stableId}>
          {(item) => (
            <Row as="div"
              key={item.stableId}
              bookId={bookId}
              item={item}
              twins={items.filter((other) => other.stableId !== item.stableId && other.textSha256 && sameText(other.text, item.text))}
              onVerdict={(value) => judge(item, value)}
              onOpenScript={onOpenScript}
              onSpoken={() => {
                const index = items.findIndex((current) => current.stableId === item.stableId);
                setFocusAfter((items[index + 1] ?? items[index - 1])?.stableId ?? EMPTY);
                refresh();
              }}
            />
          )}
        </AnimatedRows>
        </MotionRegion>
      {!items.length && (
        <div data-review-row={EMPTY} tabIndex={-1} className="rounded-cover outline-none">
          <EmptyState icon={ShieldCheck} title={filter === "todo" ? (unrecorded ? S.s_chua_co_ban_thu_9897618d : S.s_da_xem_het_75fa60d3) : S.s_chua_danh_dau_cau_nao_6b8e8be3} className="mt-4">
            {filter === "todo"
              ? unrecorded
                ? S.s_may_kiem_tung_cau_ngay_khi_thu_xong_cau_na_3fe114af
                : S.s_moi_cau_dang_lo_deu_da_co_phan_quyet_7c2be09b
              : S.s_nghe_mot_cau_roi_bam_on_hoac_can_thu_lai_c3dfde28}
          </EmptyState>
        </div>
      )}
      {hasNextPage && (
        <Button className="mt-4" variant="ghost" disabled={isFetchingNextPage} onClick={() => void fetchNextPage()}>
          {isFetchingNextPage ? S.s_dang_tai_465b1987 : S.s_tai_tiep_con_0_cau_cb00c39b(pages?.pages.at(-1)?.remaining ?? 0)}
        </Button>
      )}
      {minor > 0 && (
        <button type="button" onClick={() => setShowMinor((value) => !value)} className="touch-row mt-4 text-sm font-medium text-fg-2 hover:text-fg">
          {showMinor ? S.s_an_9c7a6c2d : S.s_hien_79d3e7eb} {minor}{S.s_cau_nhe_4de0ab6f}</button>
      )}
    </MotionRegion>
  );
}
