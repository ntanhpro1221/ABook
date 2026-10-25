import { MoreInfo } from "@/shared/SettingsNav";
import { MotionRegion } from "@/shared/MotionRegion";
import { SlidingIndicator } from "@/shared/SlidingIndicator";
import { Fold } from "@/shared/Collapse";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import * as Popover from "@radix-ui/react-popover";
import { useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { AlertTriangle, BookOpenText, Check, ChevronDown, ChevronLeft, ChevronRight, Clock, Pause, Play, RefreshCw, Search, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties, type KeyboardEvent } from "react";
import { useSearchParams } from "react-router";
import { toast } from "@/shared/toast";
import { hueOf } from "@/listen/BookScreen";
import { useClip } from "@/listen/clip";
import { cn } from "@/shared/cn";
import { formatNumber } from "@/shared/format";
import { useMediaQuery } from "@/shared/media";
import { Button, EmptyState, FilterRow, IconButton, Kbd, Segmented, Sheet, Skeleton, ContentSkeleton, InlineError } from "@/shared/ui";
import { api, urls } from "./api";
import { NameInLine, useNamesInLine } from "./NameReadings";
import { UNDO_MS, optimistic, undoAction, undoSteps, usePendingNote, useWhenApplied } from "./decisions";
import { seenDelivery, seenFor, theirDelivery, verdictWord, warnElsewhere, type SeenDelivery } from "./elsewhere";
import { findRanges, splitByRanges, wrapIndex } from "./scriptFind";

// Tab "Kịch bản" (webui/casting_review.py, docs/STUDIO_REVIEW.md mục 3): đọc cả chương như kịch bản - câu nào của ai - và
// đổi người nói của bất kỳ câu thoại hay nội tâm nào. Hộp "Việc cần duyệt" chỉ đưa ra chỗ máy nghi; ở đây người nghe duyệt
// cả chương. Sửa đi đúng đường của thẻ "Ai nói câu này" (POST /speaker -> overrides.json -> dây chuyền áp ở ranh giới
// chương, câu đã thu thì thu lại), nên không có gì phải chờ; mỗi lần sửa hay xác nhận là một nhãn cho vòng học.

export interface Person {
  value: string;
  label: string;
  lines: number;
  /** "Người mới…": người nghe tạo người nói chưa có trong sách - giới để dây chuyền chọn giọng như bước phân vai. */
  newGender?: "male" | "female" | "unknown";
}

interface Hint {
  kind: "turn" | "vocative" | "address" | "unsure";
  note: string;
  suggest?: string;
}

interface Wish {
  value: string;
  label: string;
  state: "pending" | "applied" | "refused";
  reason?: string;
}

export interface Line {
  segmentId: number;
  stableId: string;
  textSha256: string;
  seq: number;
  paragraph: number | null;
  text: string;
  kind: string;
  speaker: string;
  current: string;
  label: string;
  editable: boolean;
  hasAudio: boolean;
  hint: Hint | null;
  wish: Wish | null;
  /** Cảm xúc / mức của câu (sách đời cũ không có: null) và yêu cầu sửa cách đọc của người nghe. */
  emotion: string | null;
  intensity: number | null;
  lineWish: LineWish | null;
  /** Chữ người nghe sửa đang được đọc thay câu gốc (đã áp); null = đọc đúng chữ sách. */
  spoken: string | null;
  /** Người nghe đã xin thu lại câu này và dây chuyền chưa thu; null = không có yêu cầu nào đang chờ. */
  retake?: "pending" | null;
  /** Phán quyết "Nghe lại" của câu (reviews.json): "Thu lại" gửi nó làm `seen` - máy kia vừa quyết khác thì được hỏi. */
  verdict?: "ok" | "redo" | null;
}

interface LineWish {
  kind: string;
  emotion: string;
  intensity: number | null;
  /** Chữ đem đọc đang chờ áp ("" = trả về chữ sách). */
  spoken?: string;
  state: "pending" | "applied" | "refused";
  reason?: string;
}

export interface Delivery {
  kind?: string;
  emotion?: string;
  intensity?: number;
  speaker?: string;
  /** Người nói là người MỚI (chưa có trong sách) với giới này: đi đường "Người mới…" của POST /speaker sau khi câu thành lời thoại. */
  newGender?: "male" | "female" | "unknown";
  spoken?: string;
}

interface LineReply {
  elsewhere?: { delivery: SeenDelivery | null };
  requestedAt?: number;
  /** Mốc của yêu cầu người mới (chỉ khi `newGender`): Hoàn tác rút nó trước, rồi mới rút cách đọc câu. */
  speakerAt?: number;
}

/** Gửi cách đọc một câu (POST /line), dùng chung cho tab Kịch bản và trang đọc của cuốn mở từ file. Người nói MỚI cần hai bước - dây
 *  chuyền áp cách đọc câu (lời kể thành lời thoại) trước, người mới sau (store.speaker_request_problem xét yêu cầu câu đang chờ); bước sau hỏng
 *  (tên trùng...) thì rút luôn bước đầu, không để câu thành lời thoại mà chưa có người nói. */
export async function postLineFix(bookId: string, ref: { stableId: string; textSha256: string }, change: Delivery, wish: SeenDelivery | null | undefined): Promise<LineReply> {
  const { newGender, speaker, ...rest } = change;
  const url = `/api/books/${bookId}`;
  const seen = seenDelivery(wish);
  if (!newGender) return api<LineReply>(`${url}/line`, { method: "POST", body: { ...ref, ...rest, ...(speaker ? { speaker } : {}), seen } });
  const made = await api<LineReply>(`${url}/line`, { method: "POST", body: { ...ref, ...rest, seen } });
  try {
    const person = await api<{ requestedAt?: number }>(`${url}/speaker`, { method: "POST", body: { lines: [ref], speaker, newGender } });
    return { ...made, speakerAt: person.requestedAt };
  } catch (error) {
    if (made.requestedAt) await api(`${url}/line`, { method: "POST", body: { stableId: ref.stableId, withdraw: true, requestedAt: made.requestedAt } }).catch(() => undefined);
    throw error;
  }
}

/** "Hoàn tác" của một lần sửa cách đọc câu (thông báo sau POST /line): rút đúng lần bấm ấy; `answer` là lời đáp của `postLineFix`. */
export function undoLineFix(client: QueryClient, bookId: string, ref: { stableId: string; textSha256: string }, answer: LineReply) {
  const steps: { endpoint: string; decision: Record<string, unknown> }[] = [];
  if (answer.speakerAt) steps.push({ endpoint: "speaker", decision: { lines: [ref], requestedAt: answer.speakerAt } });
  steps.push({ endpoint: "line", decision: { stableId: ref.stableId, requestedAt: answer.requestedAt } });
  return undoSteps(client, bookId, steps, "Câu này trở lại như trước khi sửa cách đọc.");
}

export interface ChapterScript {
  chapterId: number;
  index: number;
  title: string;
  previous: number | null;
  next: number | null;
  castReady: boolean;
  /** Người kể "tôi" của CHƯƠNG NÀY (null: chương kể ngôi ba) và chip của người ấy trong chương (null: chưa nói câu nào). */
  firstPerson: { value: string; label: string; chip?: string | null } | null;
  cast: Person[];
  others: Person[];
  lines: Line[];
}

interface ChapterEntry {
  chapterId: number;
  index: number;
  title: string;
  lines: number;
  speech: number;
  hints: number;
  decided: number;
}

interface Contents {
  castReady: boolean;
  chapters: ChapterEntry[];
}

export type Filter = "all" | "speech" | "doubt";
const FILTERS: Filter[] = ["all", "speech", "doubt"];

/** Ô tìm chữ: chữ đang gõ và chỗ khớp đang đứng (số thứ tự; chuyển vòng). */
interface FindState {
  text: string;
  at: number;
}

export const NARRATOR = "NARRATOR";
export const UNNAMED = "UNNAMED";
const FIXED: Person[] = [
  { value: NARRATOR, label: "Người kể", lines: 0 },
  { value: UNNAMED, label: "Vai phụ không tên", lines: 0 },
];
// Gán nhanh bằng phím số: người nói nhiều nhất của chương đứng trước.
const HOTKEYS = 9;
// Nhịp hỏi nhẹ xem cửa sổ khác có sửa gì không (ms).
const STAMP_MS = 6000;
// Bộ cảm xúc của khâu phân tích (analysis.ALLOWED_EMOTIONS) và bốn mức cường độ.
export const EMOTIONS: [string, string][] = [
  ["neutral", "Bình thường"],
  ["happy", "Vui"],
  ["sad", "Buồn"],
  ["angry", "Giận"],
  ["afraid", "Sợ"],
  ["surprised", "Ngạc nhiên"],
  ["tender", "Dịu dàng"],
  ["sarcastic", "Mỉa mai"],
  ["excited", "Hào hứng"],
  ["tired", "Mệt mỏi"],
  ["whispering", "Thì thầm"],
];
const EMOTION_LABEL = Object.fromEntries(EMOTIONS) as Record<string, string>;
const LEVELS = ["Nhẹ", "Vừa", "Mạnh", "Rất mạnh"];
export const KINDS = [
  { value: "narration", label: "Lời kể" },
  { value: "dialogue", label: "Lời thoại" },
  { value: "thought", label: "Nội tâm" },
];

export function deliveryText(emotion: string, intensity: number | null): string {
  const label = EMOTION_LABEL[emotion] ?? emotion;
  return intensity ? `${label} · ${LEVELS[intensity]?.toLowerCase() ?? intensity}` : label;
}

/** Cách đọc một câu nói bằng lời ("loại câu: nội tâm, cảm xúc: buồn"); "" khi không đặt gì. */
export function deliveryWords({ kind, emotion, intensity, spoken }: SeenDelivery): string {
  return [
    kind ? `loại câu: ${KINDS.find((item) => item.value === kind)?.label.toLowerCase() ?? kind}` : "",
    emotion ? `cảm xúc: ${deliveryText(emotion, intensity).toLowerCase()}` : "",
    spoken != null ? (spoken ? `đọc là “${spoken}”` : "trả về chữ của sách") : "",
  ]
    .filter(Boolean)
    .join(", ");
}

function hue(label: string): CSSProperties {
  return { ["--hue" as string]: hueOf(label) };
}

/** Bỏ dấu để gõ "tuan" tìm được "Tuấn". */
function fold(text: string): string {
  return text.normalize("NFD").replace(/\p{Diacritic}/gu, "").replace(/đ/g, "d").replace(/Đ/g, "D").toLowerCase();
}

function isSpeech(line: Line): boolean {
  return line.kind === "dialogue" || line.kind === "thought";
}

/** Câu hiện ra theo bộ lọc; "Máy nghi" giữ câu nói liền trước mỗi chỗ nghi làm ngữ cảnh (mờ). Chip người nói (`who`) LỌC: chỉ câu nói của người
 *  ấy (đang chờ đổi người thì tính theo người mới), kể cả khi lọc "Máy nghi" (soát UX a23 B18). */
export function visibleLines(lines: Line[], filter: Filter, who: string | null): { line: Line; context: boolean }[] {
  const out: { line: Line; context: boolean }[] = [];
  if (who) {
    for (const line of lines) {
      if (!isSpeech(line) || (line.wish?.state === "pending" ? line.wish.value : line.current) !== who) continue;
      if (filter !== "doubt" || line.hint) out.push({ line, context: false });
    }
    return out;
  }
  if (filter !== "doubt") {
    for (const line of lines) if (filter === "all" || isSpeech(line)) out.push({ line, context: false });
    return out;
  }
  let previous: Line | null = null;
  for (const line of lines) {
    if (!isSpeech(line)) continue;
    if (line.hint) {
      if (previous && !out.some((entry) => entry.line.stableId === previous!.stableId)) out.push({ line: previous, context: true });
      out.push({ line, context: false });
    }
    previous = line;
  }
  return out;
}

function chapterExtras(chapter: ChapterEntry): string {
  return [
    chapter.speech ? `${formatNumber(chapter.speech)} câu nói` : "chỉ lời kể",
    chapter.hints ? `${chapter.hints} chỗ nghi` : "",
    chapter.decided ? `${chapter.decided} đã quyết` : "",
  ]
    .filter(Boolean)
    .join(" · ");
}

function chapterLabel(chapter: ChapterEntry): string {
  return chapter.title || `Chương ${chapter.index}`;
}

interface UndoStack {
  stack: { current: (() => boolean)[] };
  push: (undo: () => boolean) => void;
}

/** Ctrl+Z hoàn tác lần ghi gần nhất (soát UX a6 01-10): mọi lần ghi người nói của tab - từng câu hay cả chương - đẩy vào đây.
 *  Mỗi mục trả `false` khi lần ấy đã được hoàn tác (bằng nút trên thông báo). */
function useUndoStack(): UndoStack {
  const stack = useRef<(() => boolean)[]>([]);
  const push = useCallback((undo: () => boolean) => {
    stack.current = [...stack.current.slice(-19), undo];
  }, []);
  return { stack, push };
}

/** `nameOf`: tên hiện của một người nói từ mã của họ (để báo "trước đó đang là …"). */
function useAssign(bookId: string, chapterId: number, onUndoable: (undo: () => boolean) => void, nameOf: (value: string) => string) {
  const client = useQueryClient();
  const when = useWhenApplied(bookId);
  return useMutation({
    mutationFn: ({ lines, value, newGender }: { lines: Line[]; value: string; label: string; newGender?: Person["newGender"] }) =>
      api<{ lines: number; speaker: string; requestedAt: number; elsewhere?: Record<string, string> }>(`/api/books/${bookId}/speaker`, {
        method: "POST",
        body: {
          lines: lines.map((line) => ({ stableId: line.stableId, textSha256: line.textSha256 })),
          speaker: value,
          newGender: newGender ?? "",
          // Điều cửa sổ này đang thấy cho từng câu: máy chủ so với điều thật sự đang ghi, khác thì báo "vừa được sửa ở cửa sổ khác" (B19).
          seen: seenFor(lines, Object.fromEntries(lines.map((line) => [line.stableId, line.wish?.value ?? ""]))),
        },
      }),
    // Hiện ngay trên câu; bản thật về khi chương tải lại. Không ghi được thì câu trở lại như trước (onError).
    onMutate: ({ lines, value, label }) => {
      const ids = new Set(lines.map((line) => line.stableId));
      return optimistic<ChapterScript>(client, ["casting", bookId, chapterId], (data) => ({
        ...data,
        lines: data.lines.map((item) =>
          ids.has(item.stableId) ? { ...item, wish: { value, label, state: value === item.current ? "applied" : "pending" } } : item,
        ),
      }));
    },
    onSuccess: ({ lines: recorded, requestedAt, elsewhere }, { lines, value, label }) => {
      const line = lines[0];
      const replaced = Object.entries(elsewhere ?? {});
      const keep = lines.every((item) => value === item.current);
      // Như hộp việc: gán nhầm người thì "Hoàn tác" trả câu về đúng như trước lần bấm này (studio/decisions.ts). Nút trên
      // thông báo và Ctrl+Z dùng CHUNG một lần hoàn tác - bấm cả hai không hoàn tác hai lần.
      const action = undoAction(
        client,
        bookId,
        "speaker",
        [{ lines: lines.map((item) => ({ stableId: item.stableId, textSha256: item.textSha256 })), requestedAt, keep }],
        lines.length > 1
          ? `${lines.length} câu trở lại như trước.`
          : line.wish?.state === "pending"
            ? `Trở lại quyết định trước: câu này của ${line.wish.label}.`
            : `Câu này lại là của ${line.label}.`,
      );
      let used = false;
      const run = () => {
        if (used) return false;
        used = true;
        action.onClick();
        return true;
      };
      onUndoable(run);
      // Không chặn: lần ghi đã vào; nói để người nghe biết mình vừa thay một lựa chọn mới hơn những gì màn này thấy - "Lấy của máy kia"
      // là hoàn tác lần ghi này (yêu cầu nó thay trở lại).
      if (replaced.length) warnElsewhere(replaced.length, replaced[0][1] ? nameOf(replaced[0][1]) : "", run);
      const undo = { action: { label: action.label, onClick: run }, duration: UNDO_MS };
      if (keep) {
        toast.success(recorded > 1 ? `Đã xác nhận ${recorded} câu của ${label}` : `Đã xác nhận: câu này của ${line.label}`, {
          description: "Máy sẽ không hỏi lại những câu này.",
          ...undo,
        });
        return;
      }
      toast.success(recorded > 1 ? `Đã ghi: ${recorded} câu của ${label}` : `Đã ghi: câu này của ${label}`, {
        // Chỉ câu đã thu mới phải thu lại - sách chưa thu thì không hứa điều ấy (soát UX a23).
        description: `${
          lines.some((item) => item.hasAudio) ? "Câu đã thu sẽ được thu lại bằng giọng của người ấy." : "Câu chưa thu nên không phải thu lại."
        } ${when}`,
        ...undo,
      });
    },
    onError: (error: Error, _variables, context) => {
      context?.restore();
      toast.error("Chưa ghi được người nói", { description: error.message });
    },
    onSettled: () => {
      void client.invalidateQueries({ queryKey: ["casting", bookId] });
      void client.invalidateQueries({ queryKey: ["work", bookId] });
    },
  });
}

// "Chương này đúng": người nghe đã đọc hết chương - ghi nhận người nói của mọi câu chưa ai quyết, trừ câu máy còn nghi.
// Mỗi xác nhận là một nhãn đúng cho vòng học (scripts/model_eval/listener_labels.py); dây chuyền áp thì không đổi gì.
function useConfirmChapter(bookId: string, onUndoable: (undo: () => boolean) => void, nameOf: (value: string) => string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (lines: Line[]) => {
      const groups = new Map<string, Line[]>();
      for (const line of lines) groups.set(line.current, [...(groups.get(line.current) ?? []), line]);
      // Mỗi nhóm một yêu cầu: giữ `requestedAt` của từng lần ghi để một nút Hoàn tác lùi được cả chương.
      const made: Record<string, unknown>[] = [];
      const elsewhere: Record<string, string> = {};
      let count = 0;
      for (const [speaker, group] of groups) {
        const refs = group.map((line) => ({ stableId: line.stableId, textSha256: line.textSha256 }));
        try {
          const answer = await api<{ lines: number; requestedAt: number; elsewhere?: Record<string, string> }>(`/api/books/${bookId}/speaker`, {
            method: "POST",
            body: { speaker, lines: refs, seen: Object.fromEntries(group.map((line) => [line.stableId, line.wish?.value ?? ""])) },
          });
          Object.assign(elsewhere, answer.elsewhere ?? {});
          count += answer.lines;
          made.push({ lines: refs, requestedAt: answer.requestedAt, keep: true });
        } catch (error) {
          // Các nhóm trước đã ghi thật (mỗi nhóm một yêu cầu): nói đúng số, không báo như chưa làm gì (soát a83 B11).
          if (count > 0) throw new Error(`Mới xác nhận được ${count} câu, còn lại chưa ghi: ${(error as Error).message}. Bạn bấm xác nhận lại - những câu đã ghi sẽ không bị làm lại.`);
          throw error;
        }
      }
      return { count, made, elsewhere };
    },
    onSuccess: ({ count, made, elsewhere }) => {
      // Nút trên thông báo và Ctrl+Z dùng CHUNG một lần hoàn tác (như sửa người nói từng câu).
      const action = undoAction(client, bookId, "speaker", made, `${count} câu trở lại chờ duyệt.`);
      let used = false;
      const run = () => {
        if (used) return false;
        used = true;
        action.onClick();
        return true;
      };
      onUndoable(run);
      const replaced = Object.values(elsewhere);
      if (replaced.length) warnElsewhere(replaced.length, replaced[0] ? nameOf(replaced[0]) : "", run);
      toast.success(`Đã xác nhận ${count} câu là đúng`, {
        description: "Máy sẽ không hỏi lại những câu này và học từ chúng.",
        action: { label: action.label, onClick: run },
        duration: UNDO_MS,
      });
    },
    onError: (error: Error) => toast.error("Chưa xác nhận được", { description: error.message }),
    onSettled: () => {
      void client.invalidateQueries({ queryKey: ["casting", bookId] });
      void client.invalidateQueries({ queryKey: ["work", bookId] });
    },
  });
}

/** "Thu lại câu này" (một câu hay cả nhóm Shift-chọn): cùng đường với nút của trình phát và "Cần thu lại" ở Cần nghe lại (POST /review
 *  verdict redo -> overrides.json `retakes`), một lần bấm một mốc. Chỉ câu ĐÃ THU mới có gì để thu lại - câu chưa thu bị bỏ qua và nói rõ. */
function useRetake(bookId: string, chapterId: number, onUndoable: (undo: () => boolean) => void) {
  const client = useQueryClient();
  const when = useWhenApplied(bookId);
  const body = (verdict: "redo" | null, lines: Line[]) => ({
    verdict,
    chapterId,
    lines: lines.map((line) => ({ stableId: line.stableId })),
    // Phán quyết màn này thấy cho từng câu: máy/cửa sổ khác vừa quyết khác thì hỏi giữ của mình hay lấy của máy kia (uxfix28 A).
    seen: Object.fromEntries(lines.map((line) => [line.stableId, line.verdict ?? ""])),
  });
  type Answer = { elsewhere?: Record<string, string> };
  // Lần ghi đã vào; máy kia vừa quyết khác thì hỏi - "Lấy của máy kia" ghi lại đúng phán quyết máy kia đã đặt cho từng câu.
  const warn = ({ elsewhere }: Answer) => {
    const replaced = Object.entries(elsewhere ?? {});
    if (!replaced.length) return;
    warnElsewhere(replaced.length, verdictWord(replaced[0][1]), () =>
      void Promise.all(
        replaced.map(([stableId, verdict]) => api(`/api/books/${bookId}/review`, { method: "POST", body: { verdict: verdict || null, stableId, chapterId } })),
      )
        .catch((error: Error) => toast.error("Chưa lấy lại được", { description: error.message }))
        .finally(refresh),
    );
  };
  const refresh = () => {
    void client.invalidateQueries({ queryKey: ["casting", bookId] });
    void client.invalidateQueries({ queryKey: ["work", bookId] });
    void client.invalidateQueries({ queryKey: ["book", bookId] });
  };
  const cancel = useMutation({
    mutationFn: (lines: Line[]) => api<Answer>(`/api/books/${bookId}/review`, { method: "POST", body: body(null, lines) }),
    onMutate: (lines) => {
      const ids = new Set(lines.map((line) => line.stableId));
      return optimistic<ChapterScript>(client, ["casting", bookId, chapterId], (data) => ({
        ...data,
        lines: data.lines.map((item) => (ids.has(item.stableId) ? { ...item, retake: null, verdict: null } : item)),
      }));
    },
    onSuccess: (answer) => {
      warn(answer);
      toast.success("Đã bỏ yêu cầu thu lại", { description: "Câu giữ nguyên bản thu hiện có." });
    },
    onError: (error: Error, _lines, context) => {
      context?.restore();
      toast.error("Chưa bỏ được", { description: error.message });
    },
    onSettled: refresh,
  });
  const ask = useMutation({
    mutationFn: (lines: Line[]) => api<Answer>(`/api/books/${bookId}/review`, { method: "POST", body: body("redo", lines) }),
    onMutate: (lines) => {
      const ids = new Set(lines.map((line) => line.stableId));
      return optimistic<ChapterScript>(client, ["casting", bookId, chapterId], (data) => ({
        ...data,
        lines: data.lines.map((item) => (ids.has(item.stableId) ? { ...item, retake: "pending" as const, verdict: "redo" as const } : item)),
      }));
    },
    onSuccess: (answer, lines) => {
      warn(answer);
      let used = false;
      const run = () => {
        if (used) return false;
        used = true;
        void api(`/api/books/${bookId}/review`, { method: "POST", body: body(null, lines) })
          .then(() => toast.success("Đã hoàn tác", { description: lines.length > 1 ? `${lines.length} câu không phải thu lại nữa.` : "Câu này không phải thu lại nữa." }))
          .catch((error: Error) => toast.error("Không hoàn tác được", { description: error.message }))
          .finally(refresh);
        return true;
      };
      onUndoable(run);
      toast.success(lines.length > 1 ? `Đã ghi: thu lại ${lines.length} câu` : "Đã ghi: thu lại câu này", {
        description: `Đọc lại một lần khác, giọng như cũ. ${when}`,
        action: { label: "Hoàn tác", onClick: run },
        duration: UNDO_MS,
      });
    },
    onError: (error: Error, _lines, context) => {
      context?.restore();
      toast.error("Chưa ghi được", { description: error.message });
    },
    onSettled: refresh,
  });
  return { ask, cancel };
}

function useLineFix(bookId: string, chapterId: number) {
  const client = useQueryClient();
  const when = useWhenApplied(bookId);
  const refresh = () => {
    void client.invalidateQueries({ queryKey: ["casting", bookId] });
    void client.invalidateQueries({ queryKey: ["work", bookId] });
  };
  return useMutation({
    // `seen`: cách đọc màn này đang thấy cho câu - máy/cửa sổ khác vừa đổi khác thì được hỏi (uxfix28 A).
    mutationFn: ({ line, change }: { line: Line; change: Delivery }) => postLineFix(bookId, line, change, line.lineWish),
    onMutate: ({ line, change }) =>
      optimistic<ChapterScript>(client, ["casting", bookId, chapterId], (data) => ({
        ...data,
        lines: data.lines.map((item) =>
          item.stableId === line.stableId
            ? {
                ...item,
                lineWish: {
                  kind: change.kind ?? "",
                  emotion: change.emotion ?? "",
                  intensity: change.intensity ?? null,
                  ...(change.spoken !== undefined ? { spoken: change.spoken } : {}),
                  state: "pending",
                },
              }
            : item,
        ),
      })),
    onSuccess: (answer, { line }) => {
      const { elsewhere } = answer;
      if (elsewhere) {
        // "Lấy của máy kia": ghi lại những gì máy kia đã đặt (cách đọc câu không có Hoàn tác riêng); máy kia đã bỏ hết thì chỉ báo.
        const theirs = theirDelivery(elsewhere.delivery);
        const takeTheirs = () =>
          void api(`/api/books/${bookId}/line`, { method: "POST", body: { stableId: line.stableId, textSha256: line.textSha256, ...theirs } })
            .catch((error: Error) => toast.error("Chưa lấy lại được", { description: error.message }))
            .finally(refresh);
        warnElsewhere(1, elsewhere.delivery ? deliveryWords(elsewhere.delivery) : "", theirs ? takeTheirs : undefined);
      }
      // Hoàn tác như người nói / cách đọc tên / giọng: bấm nhầm một loại đoạn hay một chữ đem đọc thì rút được (soát a89 V7).
      toast.success("Đã ghi cách đọc câu này", {
        description: `${line.hasAudio ? "Câu đã thu sẽ được thu lại." : "Câu chưa thu nên không phải thu lại."} ${when}`,
        action: answer.requestedAt ? undoLineFix(client, bookId, line, answer) : undefined,
        duration: UNDO_MS,
      });
    },
    onError: (error: Error, _variables, context) => {
      context?.restore();
      toast.error("Chưa ghi được", { description: error.message });
    },
    onSettled: refresh,
  });
}

// Bảng sửa cách đọc một câu: loại đoạn, cảm xúc, mức. Lời kể thành lời thoại / nội tâm thì phải chọn người nói (một câu
// thoại luôn có chủ). Mức do khâu phân tích hiệu chỉnh lại theo cảm xúc - thì thầm, dịu dàng tối đa "Vừa".
// `noWorkshop`: cuốn không có xưởng - tên riêng không có danh sách sẵn (cần sổ phân tích), nên không có mục "Tên trong câu" ở đây:
// trang đọc có hộp riêng chọn từ trong câu (listen/LineWishes.tsx).
export function DeliveryMenu({
  bookId,
  line,
  script,
  onSave,
  wide = false,
  noWorkshop = false,
  dirty,
}: {
  bookId: string;
  line: Line;
  script: ChapterScript;
  onSave: (change: Delivery) => void;
  wide?: boolean;
  noWorkshop?: boolean;
  /** Bảng còn lựa chọn chưa lưu không - chỗ mở bảng báo khi người nghe đóng (Esc, bấm ra ngoài) mà chưa lưu. */
  dirty?: { current: boolean };
}) {
  const waiting = line.lineWish?.state === "pending" ? line.lineWish : null;
  const [kind, setKind] = useState(waiting?.kind || line.kind);
  const [emotion, setEmotion] = useState(waiting?.emotion || line.emotion || "neutral");
  const [level, setLevel] = useState(waiting?.intensity ?? line.intensity ?? 0);
  // Lời kể thành lời thoại: chọn người nói bằng chính SpeakerMenu của "Ai nói câu này" (tìm, người của chương, người khác, “Người mới…”).
  const [picked, setPicked] = useState<Person | null>(null);
  const speaker = picked?.value ?? "";
  // Chữ đem đọc (STUDIO_REVIEW mục 7): sửa lỗi chữ / cách viết lạ của riêng câu này - sách giữ nguyên chữ của nó.
  const reading = line.spoken ?? line.text;
  const [words, setWords] = useState(waiting?.spoken || reading);
  const needsSpeaker = line.kind === "narration" && kind !== "narration";
  const names = useNamesInLine(bookId, line.text, !noWorkshop);
  const change: Delivery = {};
  if (kind !== line.kind) change.kind = kind;
  if (line.emotion !== null && emotion !== line.emotion) change.emotion = emotion;
  if (line.intensity !== null && level !== line.intensity) change.intensity = level;
  if (needsSpeaker && speaker) {
    change.speaker = speaker;
    if (picked?.newGender) change.newGender = picked.newGender;
  }
  const cleaned = words.replace(/\s+/g, " ").trim();
  if (cleaned !== reading.replace(/\s+/g, " ").trim()) {
    if (!cleaned) {
      if (line.spoken) change.spoken = ""; // ô trống: trả về chữ của sách
    } else change.spoken = cleaned === line.text.trim() ? "" : cleaned;
  }
  const ready = Object.keys(change).length > 0 && (!needsSpeaker || Boolean(speaker));
  // Khác lúc mở bảng (kể cả lựa chọn đang chờ áp đã điền sẵn) = còn thứ chưa lưu.
  const unsaved =
    kind !== (waiting?.kind || line.kind) ||
    emotion !== (waiting?.emotion || line.emotion || "neutral") ||
    level !== (waiting?.intensity ?? line.intensity ?? 0) ||
    Boolean(needsSpeaker && speaker) ||
    words !== (waiting?.spoken || reading);
  useEffect(() => {
    if (dirty) dirty.current = unsaved;
  }, [dirty, unsaved]);
  return (
    <MotionRegion as="div" className={cn("space-y-3 p-1.5", wide ? "w-full" : "w-[min(88vw,340px)]")} data-delivery-menu>
      {/* Mục tên nằm cuối bảng, dưới nếp cuộn - chỉ lối xuống đó ngay đầu bảng (soát UX 29-09). */}
      <div>
        <div className="mb-1.5 label-section text-fg-2">Loại đoạn</div>
        <Segmented label="Loại đoạn" value={kind} onChange={setKind} options={KINDS} />
      </div>
      {needsSpeaker && (
        <div>
          <div className="mb-1.5 label-section text-fg-2">Ai nói câu này?</div>
          {picked ? (
            <div className="flex items-center gap-2 rounded-lg border border-accent bg-accent-soft px-2.5 py-1.5 text-sm text-accent-text">
              <span className="min-w-0 flex-1 truncate font-medium">
                {picked.label}
                {picked.newGender ? " · người mới" : ""}
              </span>
              <button type="button" className="shrink-0 text-xs font-medium underline" onClick={() => setPicked(null)}>
                Đổi
              </button>
            </div>
          ) : (
            <div className="rounded-lg border border-line p-1">
              <SpeakerMenu line={line} script={script} onPick={setPicked} embedded />
            </div>
          )}
        </div>
      )}
      <Fold storageKey="delivery.emotion" title="Cảm xúc" summary={deliveryText(emotion, level)} bodyClassName="space-y-3 px-3 pb-3">
      {line.emotion !== null && (
        <div>
          <div className="mb-1.5 label-section text-fg-2">Cảm xúc</div>
          <div className="relative grid grid-cols-3 gap-1">
            <SlidingIndicator variant="pill" className="rounded-lg bg-accent-soft ring-1 ring-accent/40" />
            {EMOTIONS.map(([value, label]) => (
              <button
                key={value}
                type="button"
                aria-pressed={emotion === value}
                onClick={() => setEmotion(value)}
                className={cn(
                  "relative h-8 rounded-lg px-1 text-xs font-medium transition-colors duration-motion-medium",
                  emotion === value ? "text-accent-text" : "text-fg-2 hover:bg-hover",
                )}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      )}
      {line.intensity !== null && (
        <div>
          <div className="mb-1.5 label-section text-fg-2">Mức</div>
          <Segmented
            label="Mức"
            value={String(level)}
            onChange={(value) => setLevel(Number(value))}
            options={LEVELS.map((label, index) => ({ value: String(index), label }))}
          />
          <p className="mt-1.5 text-[0.6875rem] leading-snug text-fg-3">Máy giữ mức trong tầm giọng đọc được: thì thầm, dịu dàng tối đa "Vừa".</p>
        </div>
      )}
      </Fold>
      <label className="block">
        <span className="mb-1.5 block label-section text-fg-2">Chữ đem đọc</span>
        <textarea
          id={`spoken-${line.stableId}`}
          aria-label="Chữ máy sẽ đọc thay cho câu này"
          placeholder="Gõ chữ muốn máy đọc (để trống: đọc đúng chữ của sách)"
          value={words}
          onChange={(event) => setWords(event.target.value)}
          rows={Math.min(5, Math.max(2, Math.ceil(words.length / 42)))}
          className="w-full resize-y rounded-lg border border-line bg-panel px-2.5 py-1.5 text-sm leading-relaxed outline-none focus:border-focus"
        />
        <span className="mt-1 block text-[0.6875rem] leading-snug text-fg-3">
          Chỉ sửa chữ đem đọc; sách giữ nguyên
          {line.spoken ? "; xoá hết để dùng chữ gốc." : ""}
        </span>
      </label>
      {line.spoken && (
        <button type="button" className="text-xs font-medium text-accent-text" onClick={() => setWords(line.text)}>
          Dùng chữ gốc
        </button>
      )}
      <Button size="sm" variant="primary" className="w-full" disabled={!ready} onClick={() => onSave(change)}>
        {needsSpeaker && !speaker ? "Chọn người nói trước" : "Lưu cho câu này"}
      </Button>
      {/* Tên riêng trong câu đọc sai là sai ở MỌI câu có tên ấy: sửa ngay tại đây, cho cả cuốn (mục "Cách đọc tên" ở tab
          Nhân vật) - tách khỏi nút "Lưu cách đọc" vốn chỉ cho riêng câu này. */}
      {names.length > 0 && (
        <Fold storageKey="delivery.names" title="Tên trong câu" summary={`${names.length} tên`} bodyClassName="px-3 pb-3"><div data-names-section>
          <div className="mb-1.5 label-section text-fg-2">Sửa tên cả cuốn</div>
          <div className="space-y-2">
            {names.map((item) => (
              <NameInLine key={item.surface} bookId={bookId} item={item} />
            ))}
          </div>
        </div></Fold>
      )}
    </MotionRegion>
  );
}

/** Cách đọc mặc định ("Bình thường · vừa", không có yêu cầu đang chờ): không phải thông tin, chỉ là lối vào sửa - nên hiện khi rê / chọn câu
 *  và đứng ở cột hành động bên phải câu (không chiếm một dòng dưới mọi câu thoại). */
function plainDelivery(line: Line): boolean {
  return line.lineWish?.state !== "pending" && line.emotion === "neutral" && (!line.intensity || line.intensity === 1);
}

function DeliveryChip({
  bookId,
  line,
  script,
  open,
  onOpenChange,
  onSave,
  quiet,
  active,
}: {
  bookId: string;
  line: Line;
  script: ChapterScript;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSave: (change: Delivery) => void;
  quiet: boolean;
  /** Câu đang được chọn: chip "mặc định" chỉ hiện ở câu này (hay khi rê chuột). */
  active: boolean;
}) {
  const phone = useMediaQuery("(max-width: 639px)");
  const dirty = useRef(false);
  if (line.emotion === null) return null;
  // Esc / bấm ra ngoài khi còn lựa chọn chưa lưu: bảng đóng và lựa chọn mất - nói ra thay vì lặng lẽ (soát UX a23).
  const dismiss = (next: boolean) => {
    if (!next && dirty.current) {
      toast("Chưa lưu cách đọc của câu này", { description: "Lựa chọn vừa rồi đã bỏ. Mở lại và bấm “Lưu cho câu này” để giữ." });
    }
    dirty.current = false;
    onOpenChange(next);
  };
  const waiting = line.lineWish?.state === "pending" ? line.lineWish : null;
  const text = waiting
    ? deliveryText(waiting.emotion || line.emotion, waiting.intensity ?? line.intensity)
    : deliveryText(line.emotion, line.intensity);
  // "Bình thường · vừa" là mặc định, không phải thông tin - lặp dưới mọi câu chỉ làm rối (soát UX a8, mục 20). Chỉ hiện khi khác
  // mặc định, hay khi chọn / rê vào câu (vẫn là lối vào sửa cách đọc).
  const hidden = plainDelivery(line) ? !active : quiet;
  const trigger = (
    <button
      type="button"
      onClick={(event) => event.stopPropagation()}
      aria-label={`Cách đọc: ${text}. Bấm để sửa`}
      className={cn(
        // Màn cảm ứng: nút chỉ 24 px - nới vùng chạm theo chiều dọc lên ~44 px (soát UX 29-09).
        "relative inline-flex h-6 items-center gap-1 rounded-md px-1.5 text-[0.6875rem] font-medium text-fg-3 hover:bg-panel hover:text-fg focus-visible:opacity-100 pointer-coarse:after:absolute pointer-coarse:after:inset-x-0 pointer-coarse:after:-inset-y-2.5 pointer-coarse:after:content-['']",
        // Màn chạm không có hover: nhãn hiện mờ thay vì ẩn hẳn (soát UX a13 #16).
        hidden && !open && "opacity-0 group-hover:opacity-100 pointer-coarse:opacity-60",
        waiting && "text-fg-2",
      )}
    >
      {waiting && <Clock className="size-3" />}
      {text}
    </button>
  );
  // Esc trong ô sửa cách đọc tên chỉ đóng ô ấy (EditReading tự lo), không đóng cả bảng (soát UX 29-09).
  const keepOpenForNameEditor = (event: globalThis.KeyboardEvent) => {
    if ((event.target as HTMLElement | null)?.closest?.("[data-name-editor]")) event.preventDefault();
  };
  // Điện thoại: tấm trượt từ đáy, rộng hết màn - bảng nổi neo vào nút 24 px bị ép sát mép, cuộn trong khung thấp.
  if (phone) {
    return (
      <Sheet open={open} onOpenChange={dismiss} title="Cách đọc câu này" trigger={trigger} onEscapeKeyDown={keepOpenForNameEditor}>
        <LineQuote line={line} />
        <DeliveryMenu bookId={bookId} line={line} script={script} onSave={onSave} wide dirty={dirty} />
      </Sheet>
    );
  }
  return (
    <Popover.Root open={open} onOpenChange={dismiss}>
      <Popover.Trigger asChild>{trigger}</Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          align="start"
          sideOffset={6}
          collisionPadding={12}
          onEscapeKeyDown={keepOpenForNameEditor}
          // Bảng cao hơn màn nhỏ (655 px trong khung 486 px: đỉnh ra ngoài màn, không với tới) - cuộn trong phần còn trống.
          className="z-50 max-h-[var(--radix-popover-content-available-height)] overflow-y-auto overscroll-contain rounded-xl border border-line bg-panel p-1.5 shadow-float"
        >
          <DeliveryMenu bookId={bookId} line={line} script={script} onSave={onSave} dirty={dirty} />
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}

/** Tấm trượt trên điện thoại che mất đúng câu vừa chạm (soát UX 30-09) - trích lại câu ấy ở đầu tấm. */
export function LineQuote({ line }: { line: Line }) {
  return <p className="mx-1.5 mt-2 line-clamp-3 rounded-lg bg-hover px-3 py-2 text-sm leading-snug text-fg-2">{line.text}</p>;
}

/** `phone`: trong tấm trượt - ô tìm không tự bật bàn phím (bàn phím che danh sách người của chương, lối chọn chính).
 *  `embedded`: nằm trong bảng khác (chọn người nói cho lời kể thành lời thoại ở bảng cách đọc câu): không giành con trỏ, danh sách thấp hơn, và không mời
 *  “Người kể” (một câu thoại phải có chủ). */
export function SpeakerMenu({
  line,
  script,
  onPick,
  phone = false,
  embedded = false,
}: {
  line: Line;
  script: ChapterScript;
  onPick: (person: Person) => void;
  phone?: boolean;
  embedded?: boolean;
}) {
  const [query, setQuery] = useState("");
  const everyone = [...script.cast, ...script.others];
  const suggested = line.hint?.suggest ? everyone.find((person) => person.value === line.hint?.suggest) : undefined;
  const found = query.trim() ? everyone.filter((person) => fold(person.label).includes(fold(query.trim()))).slice(0, 8) : [];
  const item = (person: Person, hotkey?: number) => {
    const current = person.value === line.current;
    return (
      <button
        key={person.value}
        type="button"
        onClick={() => onPick(person)}
        className="flex h-9 w-full items-center gap-2 rounded-lg px-2 text-left text-sm hover:bg-hover focus-visible:bg-hover focus-visible:outline-none pointer-coarse:h-11"
      >
        <span className="avatar grid size-6 shrink-0 place-items-center rounded-full text-[0.6875rem] font-bold" style={hue(person.label)} aria-hidden>
          {hotkey ?? person.label.slice(0, 1).toUpperCase()}
        </span>
        <span className="min-w-0 flex-1 truncate">
          {current ? `Đúng là ${person.label}` : person.label}
        </span>
        {current ? <Check className="size-4 shrink-0 text-success" /> : person.lines > 0 && <span className="tabular shrink-0 text-xs text-fg-3">{formatNumber(person.lines)}</span>}
      </button>
    );
  };
  return (
    <MotionRegion as="div">
      <label className="flex h-9 items-center gap-2 rounded-lg border border-line bg-panel-2 px-2.5 focus-within:border-focus">
        <Search className="size-4 shrink-0 text-fg-3" />
        <input
          autoFocus={!phone && !embedded}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && found[0]) onPick(found[0]);
          }}
          placeholder="Tìm người khác trong truyện…"
          aria-label="Tìm người nói"
          spellCheck={false}
          autoComplete="off"
          className="min-w-0 flex-1 bg-transparent text-sm text-fg outline-none placeholder:text-fg-3"
        />
      </label>
      <div className={cn("mt-1.5 overflow-y-auto", embedded ? "max-h-56" : phone ? "max-h-[60dvh]" : "max-h-[min(60vh,360px)]")}>
        {query.trim() ? (
          found.length ? (
            found.map((person) => item(person))
          ) : (
            // Người chưa từng được máy gán câu nào (linh thể nói trong 『』...): tạo người ấy - dây chuyền cấp giọng riêng
            // như bước phân vai, khác giọng người cùng chương.
            <div className="px-2 py-2.5">
              <p className="text-sm text-fg-2">Chưa có ai tên như thế trong truyện. Tạo người mới “{query.trim()}”:</p>
              <div className="mt-2 flex gap-1.5">
                {(
                  [
                    ["male", "Nam"],
                    ["female", "Nữ"],
                    ["unknown", "Không rõ"],
                  ] as const
                ).map(([gender, label]) => (
                  <button
                    key={gender}
                    type="button"
                    onClick={() => onPick({ value: query.trim(), label: query.trim(), lines: 0, newGender: gender })}
                    className="h-8 flex-1 rounded-lg border border-line text-xs font-medium text-fg-2 hover:bg-hover"
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>
          )
        ) : (
          <>
            {suggested && suggested.value !== line.current && (
              <>
                <div className="px-2 pb-1 pt-1.5 label-section text-warning">Máy gợi ý</div>
                {item(suggested)}
              </>
            )}
            {script.cast.length > 0 && (
              <>
                <div className="px-2 pb-1 pt-1.5 label-section text-fg-2">Nói trong chương này</div>
                {script.cast.map((person, index) => item(person, index < HOTKEYS ? index + 1 : undefined))}
              </>
            )}
            <div className="px-2 pb-1 pt-1.5 label-section text-fg-2">Khác</div>
            {FIXED.filter((person) => !embedded || person.value !== NARRATOR).map((person) => item(person))}
          </>
        )}
      </div>
    </MotionRegion>
  );
}

function SpeakerChip({
  line,
  script,
  open,
  onOpenChange,
  onPick,
}: {
  line: Line;
  script: ChapterScript;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onPick: (person: Person) => void;
}) {
  const phone = useMediaQuery("(max-width: 639px)");
  const waiting = line.wish?.state === "pending";
  const shown = waiting ? line.wish!.label : line.label;
  const Icon = waiting ? Clock : line.wish?.state === "applied" ? Check : ChevronDown;
  const trigger = (
    <button
      type="button"
      tabIndex={-1}
      disabled={!script.castReady || !line.editable}
      aria-label={`${line.kind === "thought" ? "Người nghĩ" : "Người nói"}: ${shown}. Bấm để đổi`}
      className="avatar inline-flex h-7 max-w-full items-center gap-1 rounded-full px-2.5 text-[0.8125rem] font-semibold transition-[filter] hover:brightness-95 disabled:cursor-default disabled:hover:brightness-100"
      style={hue(shown)}
    >
      <span className="truncate">{shown}</span>
      <Icon className={cn("size-3.5 shrink-0", line.wish?.state === "applied" && "text-success")} strokeWidth={2.25} />
    </button>
  );
  // Điện thoại: tấm trượt như bảng cách đọc câu - bảng nổi 288 px neo vào chip bị ép sát mép.
  if (phone) {
    return (
      <Sheet open={open} onOpenChange={onOpenChange} title={line.kind === "thought" ? "Ai nghĩ câu này?" : "Ai nói câu này?"} trigger={trigger}>
        <LineQuote line={line} />
        <div className="px-1.5 pt-2">
          <SpeakerMenu line={line} script={script} onPick={onPick} phone />
        </div>
      </Sheet>
    );
  }
  return (
    <Popover.Root open={open} onOpenChange={onOpenChange}>
      <Popover.Trigger asChild>{trigger}</Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          align="start"
          sideOffset={6}
          collisionPadding={12}
          className="z-50 w-72 rounded-xl border border-line bg-panel p-1.5 shadow-float"
        >
          <SpeakerMenu line={line} script={script} onPick={onPick} />
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}

function ScriptRow({
  bookId,
  line,
  script,
  active,
  selected,
  marks,
  markNow = false,
  context,
  gap,
  menuOpen,
  onMenu,
  onActivate,
  onExtend,
  onPick,
  deliveryOpen,
  onDelivery,
  onSaveDelivery,
  pendingNote,
  onRetake,
  onCancelRetake,
  rowRef,
}: {
  bookId: string;
  line: Line;
  script: ChapterScript;
  active: boolean;
  /** Nằm trong nhóm câu đang chọn (Shift): phím số / chọn người áp cho cả nhóm. */
  selected: boolean;
  /** Chỗ ô tìm chữ khớp trong câu (vị trí theo chữ gốc) và câu này có phải chỗ khớp đang đứng không. */
  marks?: [number, number][];
  markNow?: boolean;
  context: boolean;
  gap: boolean;
  menuOpen: boolean;
  onMenu: (open: boolean) => void;
  onActivate: () => void;
  /** Shift + bấm: chọn từ câu đang đứng tới câu này. */
  onExtend: () => void;
  onPick: (person: Person) => void;
  deliveryOpen: boolean;
  onDelivery: (open: boolean) => void;
  onSaveDelivery: (change: Delivery) => void;
  /** Vế "chờ áp dụng khi sách chạy tiếp" / "bấm “Áp dụng thay đổi”…" đúng với tình trạng sách (studio/decisions.ts). */
  pendingNote: string;
  /** "Thu lại câu này" (chỉ câu đã thu) và bỏ yêu cầu ấy khi còn chờ. */
  onRetake: () => void;
  onCancelRetake: () => void;
  rowRef: (element: HTMLLIElement | null) => void;
}) {
  const clip = useClip();
  const id = `script-${line.segmentId}`;
  const playing = clip.current === id;
  const speech = isSpeech(line);
  const suggested = line.hint?.suggest ? [...script.cast, ...script.others].find((person) => person.value === line.hint?.suggest) : undefined;
  return (
    <MotionRegion as="li"
      elementRef={rowRef}
      data-line={line.stableId}
      tabIndex={speech ? (active ? 0 : -1) : undefined}
      aria-selected={speech ? selected : undefined}
      onFocus={speech ? onActivate : undefined}
      onMouseDown={(event) => {
        // Shift + bấm chọn cả đoạn - không để trình duyệt bôi đen chữ giữa hai lần bấm.
        if (speech && event.shiftKey) event.preventDefault();
      }}
      onClick={speech ? (event) => (event.shiftKey ? onExtend() : onActivate()) : undefined}
      className={cn(
        "group transition-[background-color,box-shadow,opacity] duration-motion-fast grid grid-cols-[calc(var(--spacing)*7)_minmax(0,1fr)] gap-x-2 gap-y-1 rounded-lg px-2 py-1.5 outline-none lg:grid-cols-[10rem_calc(var(--spacing)*7)_minmax(0,1fr)]",
        gap && "mt-2",
        active && "bg-hover",
        selected && "bg-accent-soft ring-1 ring-inset ring-accent/40",
        speech && "focus-visible:ring-2 focus-visible:ring-focus",
        context && "opacity-45",
        marks?.length && !selected && (markNow ? "ring-2 ring-inset ring-warning/60" : "ring-1 ring-inset ring-warning/25"),
      )}
    >
      {/* Ô người nói: chip bấm được cho câu thoại; câu kể ghi nhãn "Người kể" mờ - cột không bỏ trống, bảng đọc như kịch bản. Chip / nhãn cao
          bằng dòng chữ đầu (24,5 px) nên tâm hai bên trùng nhau và hàng chỉ cao đúng nội dung. */}
      <div className={cn("col-span-2 min-w-0 lg:col-span-1", !speech && "hidden lg:block")}>
        {speech ? (
          <SpeakerChip line={line} script={script} open={menuOpen} onOpenChange={onMenu} onPick={onPick} />
        ) : (
          <span className="flex h-7 items-center truncate text-xs text-fg-3">{line.label || "Người kể"}</span>
        )}
      </div>
      {/* Nút nghe đứng ngay trước chữ (cột cố định, cao bằng dòng chữ đầu): luôn sát chữ dù câu ngắn hay dài, không trôi sang mép phải. */}
      <div className="flex justify-center">
        {line.hasAudio && (
          <button
            type="button"
            tabIndex={-1}
            onClick={(event) => {
              event.stopPropagation();
              clip.toggle(id, urls.sample(bookId, line.segmentId));
            }}
            aria-label={playing ? "Dừng" : `Nghe câu: ${line.text}`}
            className="grid size-7 place-items-center rounded-full text-fg-3 hover:bg-panel hover:text-fg"
          >
            {playing ? <Pause className="size-3.5" fill="currentColor" strokeWidth={0} /> : <Play className="size-3.5 translate-x-[1px]" fill="currentColor" strokeWidth={0} />}
          </button>
        )}
      </div>
      <div className="flex min-w-0 flex-wrap items-start gap-x-2 gap-y-0.5">
      <div className="min-w-0 max-w-[44rem] flex-1 basis-[min(100%,16rem)]">
        <p className={cn("text-[0.9375rem] leading-relaxed", speech ? "text-fg" : "text-fg-2", line.kind === "thought" && "italic")}>
          {line.kind === "thought" && <span className="mr-1.5 rounded bg-hover px-1.5 py-px align-[1px] text-[0.6875rem] font-medium not-italic text-fg-2">nghĩ</span>}
          {marks?.length ? (
            splitByRanges(line.text, marks).map(([part, hit], index) =>
              hit ? (
                <mark key={index} className="rounded-sm bg-warning-soft px-0.5 text-fg">
                  {part}
                </mark>
              ) : (
                part
              ),
            )
          ) : (
            line.text
          )}
        </p>
        {line.spoken && (
          <p className="mt-0.5 text-xs text-fg-2">
            Đọc là: <span className="text-fg">{line.spoken}</span>
          </p>
        )}
        {script.castReady && !plainDelivery(line) && (
          <DeliveryChip bookId={bookId} line={line} script={script} open={deliveryOpen} onOpenChange={onDelivery} onSave={onSaveDelivery} quiet={!speech && !active} active={active} />
        )}
        {line.lineWish?.state === "pending" && (
          <p className="mt-0.5 flex items-center gap-1.5 text-xs text-fg-2">
            <Clock className="size-3.5 shrink-0" />
            {line.lineWish.kind
              ? `Đã đổi loại câu: ${KINDS.find((item) => item.value === line.lineWish?.kind)?.label.toLowerCase()}`
              : "Đã ghi cách đọc câu"}
            {line.lineWish.spoken !== undefined ? (line.lineWish.spoken ? ` - đọc là "${line.lineWish.spoken}"` : " - trả về chữ của sách") : ""} -{" "}
            {pendingNote}.
          </p>
        )}
        {line.lineWish?.state === "refused" && (
          <p className="mt-0.5 flex items-center gap-1.5 text-xs text-danger">
            <AlertTriangle className="size-3.5 shrink-0" />
            Cách đọc mới không áp được: {line.lineWish.reason}
          </p>
        )}
        {line.hint && !context && (!line.wish || line.wish.state === "refused") && (
          <p className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-warning">
            <span className="inline-flex items-start gap-1.5">
              <AlertTriangle className="mt-px size-3.5 shrink-0" />
              {line.hint.note}
            </span>
            {suggested && script.castReady && suggested.value !== line.current && line.wish?.value !== suggested.value && (
              <button
                type="button"
                onClick={() => onPick(suggested)}
                className="rounded-md border border-warning/40 px-1.5 py-0.5 font-medium text-warning hover:bg-warning-soft"
              >
                Gán cho {suggested.label}
              </button>
            )}
          </p>
        )}
        {line.retake === "pending" && (
          <p className="mt-1 flex flex-wrap items-center gap-x-1.5 text-xs text-fg-2">
            <Clock className="size-3.5 shrink-0" />
            Đã xin thu lại câu này - {pendingNote}.
            <button
              type="button"
              onClick={(event) => {
                event.stopPropagation();
                onCancelRetake();
              }}
              className="font-medium text-accent-text hover:underline"
            >
              Bỏ
            </button>
          </p>
        )}
        {line.wish?.state === "pending" && (
          <p className="mt-1 flex items-center gap-1.5 text-xs text-fg-2">
            <Clock className="size-3.5 shrink-0" />
            Đã ghi {line.wish.label} (máy gán {line.label}) - {pendingNote}.
          </p>
        )}
        {line.wish?.state === "refused" && (
          <p className="mt-1 flex items-center gap-1.5 text-xs text-danger">
            <AlertTriangle className="size-3.5 shrink-0" />
            Yêu cầu {line.wish.label} không áp được: {line.wish.reason}
          </p>
        )}
      </div>
      {/* Việc phụ chỉ hiện khi rê / chọn câu (thu lại, cách đọc mặc định): sau cột chữ, không chiếm chỗ dưới câu. */}
      <div className="flex shrink-0 items-center gap-0.5">
        {/* Chỉ câu đã thu mới có gì để thu lại; câu chưa thu không có nút (chương chưa thu thì banner đầu tab đã nói). */}
        {line.hasAudio && line.retake !== "pending" && (
          <button
            type="button"
            tabIndex={-1}
            onClick={(event) => {
              event.stopPropagation();
              onRetake();
            }}
            aria-label={`Thu lại câu: ${line.text}`}
            title="Thu lại câu này (R)"
            className={cn(
              "grid size-7 place-items-center rounded-full text-fg-3 hover:bg-panel hover:text-fg focus-visible:opacity-100",
              !active && "opacity-0 group-hover:opacity-100 pointer-coarse:opacity-60",
            )}
          >
            <RefreshCw className="size-3.5" />
          </button>
        )}
        {script.castReady && plainDelivery(line) && (
          <DeliveryChip bookId={bookId} line={line} script={script} open={deliveryOpen} onOpenChange={onDelivery} onSave={onSaveDelivery} quiet={!speech && !active} active={active} />
        )}
      </div>
      </div>
    </MotionRegion>
  );
}

function nameOf(script: ChapterScript, value: string): string {
  return [...script.cast, ...script.others, ...FIXED].find((person) => person.value === value)?.label ?? value;
}

function ChapterScriptView({
  bookId,
  script,
  filter,
  who,
  find,
  onFound,
  onActive,
  wantedLine = null,
  pickLine = true,
  people,
  onPicked,
  undo: { stack: undos, push: pushUndo },
}: {
  bookId: string;
  script: ChapterScript;
  /** Ngăn xếp Ctrl+Z của cả tab (chương này lẫn nút "Xác nhận cả chương đúng"). */
  undo: UndoStack;
  filter: Filter;
  /** Chỉ xem câu của người này (chip người nói; null = tất cả). */
  who: string | null;
  /** Ô tìm chữ: chữ đang gõ và chỗ khớp đang đứng (mũi tên / Enter qua các chỗ khớp); `onFound` báo số câu khớp để ô hiện "2/7". */
  find: FindState;
  onFound: (count: number) => void;
  /** Câu đang chọn đổi (null = bỏ chọn): tab ghi vào URL để F5 về đúng chỗ (soát UX a23 B20). */
  onActive: (stableId: string | null) => void;
  /** Người gán bằng phím số (theo số trên chú giải): người nói của chương + người vừa gán qua ô tìm. */
  people: Person[];
  /** Vừa gán một người - người ngoài chú giải được thêm vào đó với số kế tiếp (soát UX a6 01-10). */
  onPicked: (person: Person) => void;
  /** Mở từ thẻ "Việc cần duyệt" (Tìm trong truyện…): tới câu này và mở sẵn ô chọn người nói. */
  wantedLine?: string | null;
  /** false: chỉ tới câu ấy để ĐỌC (thẻ nhóm "Đọc cả N câu") - không mở ô chọn che chữ. */
  pickLine?: boolean;
}) {
  // Ctrl+Z: hoàn tác lần gán gần nhất (soát UX a6 01-10: gán nhầm một phím số chỉ hoàn tác được trong vài giây thông báo).
  const assign = useAssign(bookId, script.chapterId, pushUndo, (value) => nameOf(script, value));
  const fixLine = useLineFix(bookId, script.chapterId);
  const retake = useRetake(bookId, script.chapterId, pushUndo);
  const clip = useClip();
  // Một lần cho cả chương, không mỗi câu một truy vấn.
  const pendingNote = usePendingNote(bookId);
  const [active, setActive] = useState<string | null>(null);
  // Nhiều câu liền nhau của cùng một người (Shift + ↑ ↓ hay Shift + bấm): một phím số gán cả nhóm.
  const [selected, setSelected] = useState<string[]>([]);
  const anchor = useRef<string | null>(null);
  const [menu, setMenu] = useState<string | null>(null);
  const [delivery, setDelivery] = useState<string | null>(null);
  const rows = useRef(new Map<string, HTMLLIElement>());

  // Câu hiện ra theo bộ lọc; "Máy nghi" giữ câu nói liền trước mỗi chỗ nghi làm ngữ cảnh (mờ).
  const shown = useMemo(() => visibleLines(script.lines, filter, who), [script.lines, filter, who]);
  // Chỗ ô tìm chữ khớp (trong câu đang hiện): theo thứ tự đọc, tô trên câu và nhảy tới bằng Enter.
  const matches = useMemo(() => {
    const out = new Map<string, [number, number][]>();
    if (!find.text.trim()) return out;
    for (const { line, context } of shown) {
      if (context) continue;
      const ranges = findRanges(line.text, find.text);
      if (ranges.length) out.set(line.stableId, ranges);
    }
    return out;
  }, [shown, find.text]);
  const matchIds = useMemo(() => [...matches.keys()], [matches]);
  const nowMatch = matchIds.length ? matchIds[wrapIndex(find.at, matchIds.length)] : null;
  useEffect(() => onFound(matchIds.length), [matchIds.length, onFound]);
  useEffect(() => {
    if (nowMatch) rows.current.get(nowMatch)?.scrollIntoView({ block: "center" });
    // Chỉ cuộn khi người nghe đổi chỗ khớp (gõ chữ mới, Enter), không mỗi lần câu được tải lại.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nowMatch, find.text, find.at]);
  const speechRows = shown.filter((entry) => isSpeech(entry.line)).map((entry) => entry.line);
  const activeLine = speechRows.find((line) => line.stableId === active) ?? null;
  useEffect(() => onActive(active), [active, onActive]);

  useEffect(() => {
    setActive(null);
    setMenu(null);
    setDelivery(null);
    setSelected([]);
    anchor.current = null;
  }, [script.chapterId]);

  useEffect(() => {
    const onKey = (event: globalThis.KeyboardEvent) => {
      if (!(event.ctrlKey || event.metaKey) || event.shiftKey || event.key.toLowerCase() !== "z") return;
      // Đang gõ trong ô chữ thì Ctrl+Z là của ô ấy.
      if (event.target instanceof Element && event.target.closest("input, textarea, select, [contenteditable=true]")) return;
      event.preventDefault();
      // Lần đã hoàn tác bằng nút trên thông báo thì bỏ qua, lấy lần trước nữa; hết thì nói ra thay vì im lặng (soát UX a23).
      let undone = false;
      while (!undone && undos.current.length) undone = undos.current.pop()!();
      if (!undone) toast("Không còn gì để hoàn tác", { description: "Ctrl+Z hoàn tác các lần gán người nói vừa làm ở tab này." });
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const range = (from: string | null, to: Line): string[] => {
    const start = speechRows.findIndex((line) => line.stableId === from);
    const end = speechRows.indexOf(to);
    if (start < 0 || end < 0) return [to.stableId];
    const [low, high] = start <= end ? [start, end] : [end, start];
    return speechRows.slice(low, high + 1).map((line) => line.stableId);
  };
  const focusRow = (line: Line | undefined, extend = false) => {
    if (!line) return;
    if (extend) {
      anchor.current ??= active ?? line.stableId;
      setSelected(range(anchor.current, line));
    } else {
      anchor.current = null;
      setSelected([]);
    }
    setActive(line.stableId);
    const element = rows.current.get(line.stableId);
    element?.focus({ preventScroll: true });
    element?.scrollIntoView({ block: "nearest" });
  };
  // Câu được mở từ thẻ "Việc cần duyệt": tới đó một lần và mở ô chọn người nói (tìm được mọi người trong truyện).
  const openedLine = useRef<string | null>(null);
  useEffect(() => {
    if (!wantedLine || openedLine.current === wantedLine) return;
    const line = script.lines.find((entry) => entry.stableId === wantedLine);
    if (!line) return;
    openedLine.current = wantedLine;
    requestAnimationFrame(() => {
      focusRow(line);
      // Mở từ thẻ là để đọc ngữ cảnh: câu ra GIỮA màn (focusRow chỉ cuộn "vừa đủ thấy" - hợp với ↑ ↓, còn ở đây câu nằm sát
      // thanh phát, không thấy câu sau).
      rows.current.get(line.stableId)?.scrollIntoView({ block: "center" });
      if (pickLine && script.castReady && line.editable) setMenu(line.stableId);
    });
    // focusRow đổi mỗi lần vẽ; chỉ chạy lại khi câu được mở hay nội dung chương đổi.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [wantedLine, script.lines]);
  // Menu đóng (chọn xong hay Esc) thì tiêu điểm về lại câu, để ↑ ↓ và phím số làm tiếp từ đó.
  const backTo = (line: Line) => {
    setMenu(null);
    setDelivery(null);
    requestAnimationFrame(() => rows.current.get(line.stableId)?.focus({ preventScroll: true }));
  };
  // Câu đang đứng nằm trong nhóm đã chọn thì gán cả nhóm; không thì chỉ câu ấy.
  const targets = (line: Line): Line[] =>
    selected.length > 1 && selected.includes(line.stableId) ? speechRows.filter((item) => selected.includes(item.stableId)) : [line];
  const pick = (line: Line, person: Person, refocus = true) => {
    if (refocus) backTo(line);
    if (!script.castReady || !line.editable) return;
    const group = targets(line);
    const lines = group.filter((item) => item.editable && !(item.wish && item.wish.value === person.value));
    if (!lines.length) return;
    onPicked(person);
    assign.mutate({ lines, value: person.value, label: person.label, newGender: person.newGender });
    // Chọn trong danh sách (Enter, bấm tên) cũng sang câu kế như phím số - soát UX a6: gán qua ô tìm xong phải tự bấm sang.
    const after = speechRows[speechRows.indexOf(group[group.length - 1]) + 1];
    if (refocus && after) requestAnimationFrame(() => focusRow(after));
  };

  // Thu lại câu đang đứng (hay cả nhóm Shift-chọn): chỉ câu đã thu và chưa xin; không câu nào thì nói vì sao thay vì im lặng.
  const askRetake = (line: Line) => {
    const group = targets(line);
    const lines = group.filter((item) => item.hasAudio && item.retake !== "pending");
    if (!lines.length) {
      const recorded = group.some((item) => item.hasAudio);
      toast(recorded ? "Câu này đã xin thu lại" : "Chưa thu câu này nên chưa có gì để thu lại", {
        description: recorded ? "Máy sẽ thu khi áp dụng thay đổi." : "Câu sẽ được thu lần đầu khi sách làm tới đó.",
      });
      return;
    }
    retake.ask.mutate(lines);
  };

  const onKeyDown = (event: KeyboardEvent<HTMLOListElement>) => {
    if (menu || delivery || event.altKey || event.ctrlKey || event.metaKey) return;
    const index = activeLine ? speechRows.indexOf(activeLine) : -1;
    if (event.key === "ArrowDown" || event.key === "j" || event.key === "J") {
      event.preventDefault();
      focusRow(speechRows[Math.min(index + 1, speechRows.length - 1)], event.shiftKey);
    } else if (event.key === "ArrowUp" || event.key === "k" || event.key === "K") {
      event.preventDefault();
      focusRow(speechRows[Math.max(index - 1, 0)], event.shiftKey);
    } else if (event.key === "Escape" && selected.length) {
      event.preventDefault();
      anchor.current = null;
      setSelected([]);
    } else if (event.key === "p" && activeLine?.hasAudio) {
      event.preventDefault();
      clip.toggle(`script-${activeLine.segmentId}`, urls.sample(bookId, activeLine.segmentId));
    } else if ((event.key === "Enter" || event.key === " ") && activeLine) {
      event.preventDefault();
      if (script.castReady && activeLine.editable) setMenu(activeLine.stableId);
    } else if (event.key === "/") {
      event.preventDefault();
      document.getElementById("script-find")?.focus();
    } else if ((event.key === "r" || event.key === "R") && activeLine) {
      event.preventDefault();
      askRetake(activeLine);
    } else if (event.key === "e" && activeLine && script.castReady && activeLine.emotion !== null) {
      event.preventDefault();
      setDelivery(activeLine.stableId);
    } else if (/^[1-9]$/.test(event.key) && activeLine) {
      const person = people[Number(event.key) - 1];
      if (!person) return;
      event.preventDefault();
      const group = targets(activeLine);
      pick(activeLine, person, false);
      focusRow(speechRows[speechRows.indexOf(group[group.length - 1]) + 1] ?? activeLine);
    }
  };

  if (!shown.length) {
    const label = people.find((person) => person.value === who)?.label ?? (who === UNNAMED ? "Chưa rõ" : "");
    return (
      <MotionRegion><EmptyState
        icon={BookOpenText}
        title={who ? `Không có câu nào của ${label} ở mục này` : filter === "doubt" ? "Máy không nghi câu nào trong chương này" : "Chương này chỉ có lời kể"}
        className="py-10"
      >
        {who ? "Bấm lại tên ở trên để xem mọi người nói." : filter === "doubt" ? "Chọn “Cả chương” để đọc lại toàn bộ." : "Không có câu nói nào để gán người."}
      </EmptyState></MotionRegion>
    );
  }
  return (
    <MotionRegion slideIndex={FILTERS.indexOf(filter)}>
      {selected.length > 1 && (
        <p className="mt-3 flex flex-wrap items-center gap-x-2 gap-y-1 rounded-lg bg-accent-soft px-3 py-1.5 text-[0.8125rem]" role="status">
          <span className="font-semibold">Đang chọn {selected.length} câu</span>
          <span className="text-fg-2">- phím số hay chọn người ở một câu trong nhóm gán cả {selected.length} câu · Esc bỏ chọn</span>
          {(() => {
            // Thu lại cả nhóm: chỉ những câu đã thu (câu chưa thu không có gì để thu lại).
            const group = speechRows.filter((item) => selected.includes(item.stableId));
            const recorded = group.filter((item) => item.hasAudio && item.retake !== "pending").length;
            return (
              <Button
                size="sm"
                variant="ghost"
                icon={RefreshCw}
                disabled={!recorded || retake.ask.isPending}
                onClick={() => askRetake(group[0])}
                title={recorded ? "" : "Các câu đang chọn chưa thu hay đã xin thu lại"}
              >
                {recorded ? `Thu lại ${recorded} câu` : "Chưa có bản thu"}
              </Button>
            );
          })()}
        </p>
      )}
      <ol aria-label={`Kịch bản ${script.title}`} aria-multiselectable onKeyDown={onKeyDown} className="-mx-2 mt-3">
      {shown.map(({ line, context }, index) => {
        const before = shown[index - 1]?.line;
        const gap = index > 0 && (filter === "doubt" ? !context && !shown[index - 1]?.context && before?.seq !== line.seq - 1 : line.paragraph !== before?.paragraph);
        return (
          <ScriptRow
            key={line.stableId}
            bookId={bookId}
            line={line}
            script={script}
            active={line.stableId === active}
            selected={selected.length > 1 && selected.includes(line.stableId)}
            marks={matches.get(line.stableId)}
            markNow={line.stableId === nowMatch}
            context={context}
            gap={gap}
            menuOpen={menu === line.stableId}
            onMenu={(open) => {
              if (!open) return backTo(line);
              setMenu(line.stableId);
              setActive(line.stableId);
            }}
            onActivate={() => {
              if (line.stableId !== active) {
                anchor.current = null;
                setSelected([]);
              }
              setActive(line.stableId);
            }}
            onExtend={() => {
              anchor.current ??= active ?? line.stableId;
              setSelected(range(anchor.current, line));
              setActive(line.stableId);
            }}
            onPick={(person) => pick(line, person)}
            deliveryOpen={delivery === line.stableId}
            onDelivery={(open) => {
              if (!open) return backTo(line);
              setDelivery(line.stableId);
            }}
            onSaveDelivery={(change) => {
              backTo(line);
              fixLine.mutate({ line, change });
            }}
            pendingNote={pendingNote}
            onRetake={() => askRetake(line)}
            onCancelRetake={() => retake.cancel.mutate([line])}
            rowRef={(element) => {
              if (element) rows.current.set(line.stableId, element);
              else rows.current.delete(line.stableId);
            }}
          />
        );
      })}
      </ol>
    </MotionRegion>
  );
}

function ChapterFooter({ bookId, script, onNext, onUndoable }: { bookId: string; script: ChapterScript; onNext: () => void; onUndoable: (undo: () => boolean) => void }) {
  const confirm = useConfirmChapter(bookId, onUndoable, (value) => nameOf(script, value));
  const open = script.lines.filter((line) => line.editable && !line.wish && !line.hint);
  const doubtful = script.lines.filter((line) => line.editable && !line.wish && line.hint).length;
  return (
    <div className="mt-6 flex flex-wrap items-center justify-between gap-3 border-t border-line pt-4">
      {script.castReady && open.length > 0 ? (
        <div className="min-w-0">
          <Button size="sm" variant="secondary" icon={Check} loading={confirm.isPending} onClick={() => confirm.mutate(open)}>
            Duyệt {open.length} câu
          </Button>
          <p className="mt-1 text-xs text-fg-3">
            Coi người nói của các câu chưa ai quyết là đúng{doubtful ? `, trừ ${doubtful} câu máy còn nghi` : ""}: máy thôi hỏi; Ctrl+Z để hoàn tác.
          </p>
        </div>
      ) : (
        <span className="text-xs text-fg-3">
          {!script.castReady
            ? ""
            : doubtful
              ? `Còn ${doubtful} câu máy nghi chưa ai quyết - xem các câu có dấu vàng ở trên.`
              : "Mọi câu nói trong chương đã có người quyết."}
        </span>
      )}
      {script.next !== null && (
        <button type="button" onClick={onNext} className="touch-row inline-flex items-center gap-1 text-sm font-medium text-fg-2 hover:text-fg">
          Chương sau <ChevronRight className="ink-end size-4" />
        </button>
      )}
    </div>
  );
}

/** Mục lục tab Kịch bản. `enabled: false`: chỉ đọc bản trong bộ nhớ đệm (vẫn mang queryFn thật - xem useCachedBook), để trang dự án
 *  biết mục lục đã về chưa mà hoãn những lượt hỏi nặng khác (số việc cần duyệt) cho tab mở trước. */
export function useCastingContents(bookId: string, enabled = true) {
  return useQuery({
    queryKey: ["casting", bookId],
    queryFn: () => api<Contents>(`/api/books/${bookId}/casting`),
    enabled,
  });
}

/** Mở menu chọn chương thì cuộn tới chương đang xem (giữa khung), không bắt đầu ở chương đầu của danh sách dài. */
function scrollToChecked(element: HTMLElement | null) {
  const checked = element?.querySelector<HTMLElement>("[data-state=checked]");
  if (element && checked) element.scrollTop = checked.getBoundingClientRect().top - element.getBoundingClientRect().top + element.scrollTop - element.clientHeight / 2;
}

/** Chọn chương: menu của app (Radix) thay ô chọn gốc của trình duyệt - mở ra có đánh dấu chương đang xem, kèm số câu nói / chỗ nghi từng chương. */
function ChapterMenu({ chapters, chapterId, narrow, onPick }: { chapters: ChapterEntry[]; chapterId: number | undefined; narrow: boolean; onPick: (id: number) => void }) {
  const current = chapters.find((chapter) => chapter.chapterId === chapterId);
  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>
        <button
          type="button"
          id="script-chapter"
          aria-label="Chương"
          className="-ml-2.5 inline-flex h-9 min-w-0 flex-1 items-center gap-1.5 rounded-lg px-2.5 text-sm font-medium transition-colors duration-motion-fast hover:bg-hover data-[state=open]:bg-hover sm:max-w-[26rem] sm:flex-initial"
        >
          <span className="truncate">{current ? chapterLabel(current) : ""}</span>
          <ChevronDown className="fold-chevron ink-end [--icon-w:14px] size-4 shrink-0 text-fg-3" aria-hidden />
        </button>
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content
          align="start"
          sideOffset={4}
          collisionPadding={12}
          className="z-50 max-h-[min(24rem,var(--radix-dropdown-menu-content-available-height))] w-[min(30rem,calc(100vw-1.5rem))] overflow-y-auto overscroll-contain rounded-xl border border-line bg-panel p-1.5 shadow-float"
          ref={scrollToChecked}
        >
          <DropdownMenu.RadioGroup value={String(chapterId ?? "")} onValueChange={(value) => { if (Number(value) !== chapterId) onPick(Number(value)); }}>
            {chapters.map((chapter) => (
              <DropdownMenu.RadioItem
                key={chapter.chapterId}
                value={String(chapter.chapterId)}
                className="flex min-h-9 cursor-default items-center gap-2 rounded-lg px-2 py-1.5 text-sm outline-none data-[highlighted]:bg-hover data-[state=checked]:text-accent-text"
              >
                <span className="grid size-4 shrink-0 place-items-center" aria-hidden>
                  <DropdownMenu.ItemIndicator>
                    <Check className="size-4" />
                  </DropdownMenu.ItemIndicator>
                </span>
                <span className="min-w-0 flex-1 truncate">{chapterLabel(chapter)}</span>
                {!narrow && <span className="shrink-0 text-xs text-fg-2">{chapterExtras(chapter)}</span>}
              </DropdownMenu.RadioItem>
            ))}
          </DropdownMenu.RadioGroup>
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}

export function ScriptTab({ bookId }: { bookId: string }) {
  const [params, setParams] = useSearchParams();
  const [filter, setFilter] = useState<Filter>("all");
  const [who, setWho] = useState<string | null>(null);
  // Ô tìm chữ trong chương đang xem (soát UX a23 B18): chữ gõ, chỗ khớp đang đứng, và số câu khớp (ChapterScriptView báo về).
  const [find, setFind] = useState<FindState>({ text: "", at: 0 });
  // F5 về đúng chỗ (B20): câu đang chọn nằm trong URL (`at`); chỉ đọc MỘT lần lúc mở - sau đó URL chạy theo con trỏ chứ không kéo nó.
  const restoreAt = useRef(params.get("at"));
  // `setParams` đổi danh tính mỗi lần URL đổi: giữ qua ref để `remember` đứng yên, không thì mỗi lần sang tab khác nó lại ghi `at` vào URL mới.
  const setParamsNow = useRef(setParams);
  setParamsNow.current = setParams;
  const remember = useCallback(
    (stableId: string | null) =>
      setParamsNow.current(
        (previous) => {
          if ((previous.get("at") ?? null) === stableId) return previous;
          const next = new URLSearchParams(previous);
          if (stableId) next.set("at", stableId);
          else next.delete("at");
          return next;
        },
        { replace: true },
      ),
    [],
  );
  const [found, setFound] = useState(0);
  // Người gán qua ô tìm (vai phụ, người của chương khác): thêm vào chú giải với số kế tiếp để câu sau gán bằng một phím.
  const [added, setAdded] = useState<Person[]>([]);
  const undo = useUndoStack();
  const narrow = useMediaQuery("(max-width: 639px)");
  const contents = useCastingContents(bookId);
  const chapters = contents.data?.chapters ?? [];
  // Hai cửa sổ cùng sửa một sách (B19): hỏi nhẹ lần ghi yêu cầu cuối mỗi vài giây khi tab đang hiện; đổi thì chương đang xem tải lại.
  const client = useQueryClient();
  const stamp = useQuery({
    queryKey: ["casting", bookId, "stamp"],
    queryFn: () => api<{ stamp: number }>(`/api/books/${bookId}/casting/stamp`),
    enabled: contents.isSuccess,
    refetchInterval: STAMP_MS,
  });
  const lastStamp = useRef<number | null>(null);
  useEffect(() => {
    const value = stamp.data?.stamp;
    if (value === undefined) return;
    if (lastStamp.current !== null && lastStamp.current !== value) {
      void client.invalidateQueries({ queryKey: ["casting", bookId] });
      void client.invalidateQueries({ queryKey: ["work", bookId] });
    }
    lastStamp.current = value;
  }, [stamp.data?.stamp, bookId, client]);
  const asked = Number(params.get("chapter")) || undefined;
  // Mở đầu ở chương đầu tiên có chỗ máy nghi - nơi người nghe sửa được nhiều nhất.
  const fallback = chapters.find((chapter) => chapter.hints > 0) ?? chapters.find((chapter) => chapter.speech > 0) ?? chapters[0];
  const chapterId = asked && chapters.some((chapter) => chapter.chapterId === asked) ? asked : fallback?.chapterId;
  const script = useQuery({
    queryKey: ["casting", bookId, chapterId],
    queryFn: () => api<ChapterScript>(`/api/books/${bookId}/casting/${chapterId}`),
    enabled: chapterId !== undefined,
  });
  const go = (id: number | null) => {
    if (id === null) return;
    setWho(null);
    restoreAt.current = null;
    setFind((previous) => ({ ...previous, at: 0 }));
    setParams(
      (previous) => {
        const next = new URLSearchParams(previous);
        next.set("chapter", String(id));
        return next;
      },
      { replace: true },
    );
  };

  if (contents.isError && !contents.data) return <MotionRegion fadeThrough><InlineError message="Bạn hãy kiểm tra kết nối rồi tải lại kịch bản." onRetry={() => void contents.refetch()} /></MotionRegion>;
  if (contents.isLoading) return <MotionRegion fadeThrough><ContentSkeleton className="mt-6" label="Đang tải kịch bản" /></MotionRegion>;
  if (!chapters.length) {
    return (
      <MotionRegion><EmptyState icon={BookOpenText} title="Chưa có kịch bản" className="py-10">
        Kịch bản hiện ra khi máy đã phân tích xong chương đầu tiên: câu nào là lời kể, câu nào của ai.
      </EmptyState></MotionRegion>
    );
  }
  if (script.isError && !script.data) return <MotionRegion fadeThrough><InlineError message="Bạn hãy kiểm tra kết nối rồi tải lại chương này." onRetry={() => void script.refetch()} /></MotionRegion>;
  const data = script.data?.chapterId === chapterId ? script.data : undefined;
  const entry = chapters.find((chapter) => chapter.chapterId === chapterId);
  const doubts = data?.lines.filter((line) => line.hint).length ?? entry?.hints ?? 0;
  const said = (person: Person) =>
    data?.lines.filter((line) => isSpeech(line) && (line.wish?.state === "pending" ? line.wish.value : line.current) === person.value).length ?? 0;
  // Câu "chưa rõ ai nói" (nhóm vô danh UNKNOWN/ANONYMOUS - gồm vai phụ không tên): không phải một người trong chú giải nên không có số phím.
  const unnamed =
    data?.lines.filter((line) => isSpeech(line) && (line.wish?.state === "pending" ? line.wish.value : line.current) === UNNAMED).length ?? 0;
  const people: Person[] = data
    ? [
        ...data.cast,
        ...added.filter((person) => !data.cast.some((item) => item.value === person.value)).map((person) => ({ ...person, lines: said(person) })),
      ]
    : [];
  return (
    <MotionRegion as="div" className="mt-5" motionKey={[filter, who, chapterId, Boolean(data), data?.castReady]}>
      <p className="max-w-3xl text-sm text-fg-2">
        Bấm tên để đổi người nói; dấu vàng là câu cần xem.
      </p>
      {data && data.lines.length > 0 && !data.lines.some((line) => line.hasAudio) && (
        <p className="mt-1 max-w-3xl text-sm text-fg-2">
          Thu xong chương sẽ nghe lại được từng câu.
        </p>
      )}
      {/* Chương + chú giải người nói DÍNH khi cuộn (soát UX a6 01-10: cuộn xuống giữa chương là quên phím 4 là ai, muốn sang
          chương sau phải cuộn ngược lên đầu). */}
      <div className="sticky top-0 z-10 -mx-2 mt-2 flex flex-col gap-2 bg-bg/95 px-2 pb-2 pt-2 backdrop-blur">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        {/* Tên chương (menu của app, không ô chọn gốc) rồi chương trước · sau. Chữ tên chương đứng đúng mép nội dung (nút lùi lề bằng đệm của nó). */}
        <div className="flex w-full min-w-0 items-center sm:w-auto sm:max-w-full">
          <ChapterMenu chapters={chapters} chapterId={chapterId} narrow={narrow} onPick={go} />
          <IconButton label="Chương trước" icon={ChevronLeft} disabled={!data?.previous} onClick={() => go(data?.previous ?? null)} />
          <IconButton label="Chương sau" icon={ChevronRight} disabled={!data?.next} onClick={() => go(data?.next ?? null)} />
        </div>
        {narrow && entry && <p className="w-full text-xs text-fg-3">{chapterExtras(entry)}</p>}
        <div className="relative flex h-9 w-full items-center rounded-lg border border-line bg-panel focus-within:border-focus sm:w-60">
          <Search className="pointer-events-none ml-2.5 size-4 shrink-0 text-fg-3" aria-hidden />
          <input
            id="script-find"
            type="search"
            value={find.text}
            onChange={(event) => setFind({ text: event.target.value, at: 0 })}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                setFind((previous) => ({ ...previous, at: previous.at + (event.shiftKey ? -1 : 1) }));
              } else if (event.key === "Escape" && find.text) {
                event.preventDefault();
                event.stopPropagation();
                setFind({ text: "", at: 0 });
              }
            }}
            placeholder="Tìm chữ trong chương…"
            aria-label="Tìm chữ trong chương này"
            autoComplete="off"
            spellCheck={false}
            className="h-full min-w-0 flex-1 bg-transparent px-2 text-sm text-fg outline-none placeholder:text-fg-3 [&::-webkit-search-cancel-button]:hidden"
          />
          {find.text.trim() && (
            <span className="tabular mr-2 shrink-0 text-xs text-fg-2" role="status" aria-live="polite">
              {found ? `${wrapIndex(find.at, found) + 1}/${found}` : "Không có"}
            </span>
          )}
        </div>
        <FilterRow<Filter>
          label="Hiện câu nào"
          className="sm:ml-auto"
          value={filter}
          onChange={setFilter}
          options={[
            { value: "all", label: "Cả chương" },
            { value: "speech", label: "Chỉ lời nói" },
            { value: "doubt", label: `Máy nghi · ${doubts}` },
          ]}
        />
      </div>
      {/* Chú giải người nói: cùng mép trái với thanh công cụ và hàng chữ (chip lùi 4 px để vòng chữ cái đầu chạm mép), cùng nhịp 8 px. */}
      {data && (people.length > 0 || unnamed > 0) && (
        <div className="-ml-1 flex flex-wrap items-center gap-1" role="group" aria-label="Người nói trong chương - bấm để chỉ xem câu của họ, bấm lại để xem tất cả">
          {[...people.map((person, index) => ({ person, badge: index < HOTKEYS ? String(index + 1) : "" })), ...(unnamed > 0 ? [{ person: { value: UNNAMED, label: "Chưa rõ", lines: unnamed }, badge: "?" }] : [])].map(
            ({ person, badge }) => (
              <button
                key={person.value}
                type="button"
                aria-pressed={who === person.value}
                title={person.value === UNNAMED ? "Câu máy chưa biết ai nói, và vai phụ không tên" : undefined}
                onClick={() => setWho(who === person.value ? null : person.value)}
                className={cn(
                  "inline-flex h-7 items-center gap-1.5 rounded-full py-0 pl-0.5 pr-2.5 text-[0.8125rem] font-medium transition-[opacity,background-color]",
                  who === person.value ? "bg-hover" : "hover:bg-hover",
                  who && who !== person.value && "opacity-50",
                )}
              >
                <span className="avatar grid size-6 place-items-center rounded-full text-[0.6875rem] font-bold" style={hue(person.label)} aria-hidden>
                  {badge}
                </span>
                {person.label}
                <span className="tabular text-fg-3">{formatNumber(person.lines)}</span>
              </button>
            ),
          )}
          {who && (
            <button type="button" onClick={() => setWho(null)} className="inline-flex h-7 items-center gap-1 rounded-full px-2 text-xs font-medium text-accent-text hover:bg-hover">
              <X className="size-3" /> Xem tất cả
            </button>
          )}
        </div>
      )}
      {data?.castReady && people.length > 0 && (
        <MoreInfo label="Phím tắt" className="hidden md:block">
          Bàn phím: <Kbd>↑</Kbd> <Kbd>↓</Kbd> chọn câu (<Kbd>Shift</Kbd> chọn nhiều) · <Kbd>1</Kbd>–<Kbd>{Math.min(HOTKEYS, people.length)}</Kbd> gán
          người theo số rồi sang câu kế · <Kbd>Enter</Kbd> danh sách · <Kbd>P</Kbd> nghe câu · <Kbd>R</Kbd> thu lại câu · <Kbd>/</Kbd> tìm chữ · <Kbd>Ctrl</Kbd>+<Kbd>Z</Kbd> hoàn tác
        </MoreInfo>
      )}
      </div>
      {!data ? (
        <div className="mt-4 space-y-2">
          {Array.from({ length: 8 }, (_, index) => (
            <Skeleton key={index} className="h-9 rounded-lg" />
          ))}
        </div>
      ) : (
        <>
          {!data.castReady && (
            <p className="mt-4 flex items-start gap-2 rounded-xl bg-info-soft p-3 text-sm text-fg">
              <Clock className="mt-0.5 size-4 shrink-0 text-info" />
              Sửa người nói được sau bước phân vai.
            </p>
          )}
          {/* Chương kể ngôi thứ nhất: máy gán nhầm câu của người khác cho "tôi" nhiều nhất (8B-v5 trên bộ LN: 97/276 câu gán cho
              người kể là sai) - mời soát riêng câu của người kể trước. */}
          {data.castReady && data.firstPerson?.chip && who !== data.firstPerson.chip && (
            <p className="mt-3 flex flex-wrap items-center gap-x-2 gap-y-1 text-[0.8125rem] text-fg-2">
              <span className="text-pretty">
                Chương kể ngôi thứ nhất: máy hay nhầm câu của người khác thành của “tôi”.
              </span>
              <Button size="sm" variant="ghost" onClick={() => setWho(data.firstPerson!.chip!)}>
                Soát câu của {data.cast.find((person) => person.value === data.firstPerson!.chip)?.label ?? data.firstPerson.label}
              </Button>
            </p>
          )}
          <ChapterScriptView
            bookId={bookId}
            script={data}
            undo={undo}
            filter={filter}
            who={who}
            find={find}
            onFound={setFound}
            onActive={remember}
            wantedLine={params.get("line") ?? restoreAt.current}
            pickLine={params.get("line") ? params.get("pick") !== "0" : false}
            people={people}
            onPicked={(person) =>
              setAdded((current) =>
                person.value === UNNAMED || current.some((item) => item.value === person.value)
                  ? current
                  : [...current, person],
              )
            }
          />
          <ChapterFooter bookId={bookId} script={data} onNext={() => go(data.next)} onUndoable={undo.push} />
        </>
      )}
    </MotionRegion>
  );
}
