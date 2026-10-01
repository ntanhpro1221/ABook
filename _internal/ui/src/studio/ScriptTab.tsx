import * as Popover from "@radix-ui/react-popover";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, BookOpenText, Check, ChevronDown, ChevronLeft, ChevronRight, Clock, Pause, Play, Search } from "lucide-react";
import { useEffect, useMemo, useRef, useState, type CSSProperties, type KeyboardEvent } from "react";
import { useSearchParams } from "react-router";
import { toast } from "sonner";
import { hueOf } from "@/listen/BookScreen";
import { useClip } from "@/listen/clip";
import { cn } from "@/shared/cn";
import { formatNumber } from "@/shared/format";
import { useMediaQuery } from "@/shared/media";
import { Button, EmptyState, IconButton, Kbd, Segmented, Sheet, Skeleton } from "@/shared/ui";
import { api, urls } from "./api";
import { NameInLine, useNamesInLine } from "./NameReadings";
import { UNDO_MS, undoAction, usePendingNote, useWhenApplied } from "./decisions";

// Tab "Kịch bản" (webui/casting_review.py, docs/STUDIO_REVIEW.md mục 3): đọc cả chương như kịch bản - câu nào của ai - và
// đổi người nói của bất kỳ câu thoại hay nội tâm nào. Hộp "Việc cần duyệt" chỉ đưa ra chỗ máy nghi; ở đây người nghe duyệt
// cả chương. Sửa đi đúng đường của thẻ "Ai nói câu này" (POST /speaker -> overrides.json -> dây chuyền áp ở ranh giới
// chương, câu đã thu thì thu lại), nên không có gì phải chờ; mỗi lần sửa hay xác nhận là một nhãn cho vòng học.

interface Person {
  value: string;
  label: string;
  lines: number;
  /** "Người mới…": người nghe tạo người nói chưa có trong sách - giới để dây chuyền chọn giọng như bước phân vai. */
  newGender?: "male" | "female" | "unknown";
}

interface Hint {
  kind: "speaker" | "turn" | "vocative";
  note: string;
  suggest?: string;
}

interface Wish {
  value: string;
  label: string;
  state: "pending" | "applied" | "refused";
  reason?: string;
}

interface Line {
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

interface Delivery {
  kind?: string;
  emotion?: string;
  intensity?: number;
  speaker?: string;
  spoken?: string;
}

interface ChapterScript {
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

type Filter = "all" | "speech" | "doubt";

const NARRATOR = "NARRATOR";
const UNNAMED = "UNNAMED";
const FIXED: Person[] = [
  { value: NARRATOR, label: "Người kể", lines: 0 },
  { value: UNNAMED, label: "Vai phụ không tên", lines: 0 },
];
// Gán nhanh bằng phím số: người nói nhiều nhất của chương đứng trước.
const HOTKEYS = 9;
// Bộ cảm xúc của khâu phân tích (analysis.ALLOWED_EMOTIONS) và bốn mức cường độ.
const EMOTIONS: [string, string][] = [
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
const KINDS = [
  { value: "narration", label: "Lời kể" },
  { value: "dialogue", label: "Lời thoại" },
  { value: "thought", label: "Nội tâm" },
];

function deliveryText(emotion: string, intensity: number | null): string {
  const label = EMOTION_LABEL[emotion] ?? emotion;
  return intensity ? `${label} · ${LEVELS[intensity]?.toLowerCase() ?? intensity}` : label;
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

function chapterLabel(chapter: ChapterEntry): string {
  const extras = [
    chapter.speech ? `${formatNumber(chapter.speech)} câu nói` : "chỉ lời kể",
    chapter.hints ? `${chapter.hints} chỗ nghi` : "",
    chapter.decided ? `${chapter.decided} đã quyết` : "",
  ].filter(Boolean);
  return `${chapter.title || `Chương ${chapter.index}`} — ${extras.join(" · ")}`;
}

function useAssign(bookId: string, chapterId: number, onUndoable: (undo: () => void) => void) {
  const client = useQueryClient();
  const when = useWhenApplied(bookId);
  return useMutation({
    mutationFn: ({ lines, value, newGender }: { lines: Line[]; value: string; label: string; newGender?: Person["newGender"] }) =>
      api<{ lines: number; speaker: string; requestedAt: number }>(`/api/books/${bookId}/speaker`, {
        method: "POST",
        body: { lines: lines.map((line) => ({ stableId: line.stableId, textSha256: line.textSha256 })), speaker: value, newGender: newGender ?? "" },
      }),
    // Hiện ngay trên câu; bản thật về khi chương tải lại.
    onMutate: ({ lines, value, label }) => {
      const ids = new Set(lines.map((line) => line.stableId));
      client.setQueryData<ChapterScript>(["casting", bookId, chapterId], (data) =>
        data && {
          ...data,
          lines: data.lines.map((item) =>
            ids.has(item.stableId) ? { ...item, wish: { value, label, state: value === item.current ? "applied" : "pending" } } : item,
          ),
        },
      );
    },
    onSuccess: ({ requestedAt }, { lines, value, label }) => {
      const line = lines[0];
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
        if (used) return;
        used = true;
        action.onClick();
      };
      onUndoable(run);
      const undo = { action: { label: action.label, onClick: run }, duration: UNDO_MS };
      if (keep) {
        toast.success(lines.length > 1 ? `Đã xác nhận ${lines.length} câu của ${label}` : `Đã xác nhận: câu này của ${line.label}`, {
          description: "Máy sẽ không hỏi lại những câu này.",
          ...undo,
        });
        return;
      }
      toast.success(lines.length > 1 ? `Đã ghi: ${lines.length} câu của ${label}` : `Đã ghi: câu này của ${label}`, {
        description: `Câu đã thu sẽ đọc lại bằng giọng của người ấy. ${when}`,
        ...undo,
      });
    },
    onError: (error: Error) => toast.error("Chưa ghi được người nói", { description: error.message }),
    onSettled: () => {
      void client.invalidateQueries({ queryKey: ["casting", bookId] });
      void client.invalidateQueries({ queryKey: ["work", bookId] });
    },
  });
}

// "Chương này đúng": người nghe đã đọc hết chương - ghi nhận người nói của mọi câu chưa ai quyết, trừ câu máy còn nghi.
// Mỗi xác nhận là một nhãn đúng cho vòng học (scripts/model_eval/listener_labels.py); dây chuyền áp thì không đổi gì.
function useConfirmChapter(bookId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (lines: Line[]) => {
      const groups = new Map<string, Line[]>();
      for (const line of lines) groups.set(line.current, [...(groups.get(line.current) ?? []), line]);
      for (const [speaker, group] of groups) {
        await api(`/api/books/${bookId}/speaker`, {
          method: "POST",
          body: { speaker, lines: group.map((line) => ({ stableId: line.stableId, textSha256: line.textSha256 })) },
        });
      }
      return lines.length;
    },
    onSuccess: (count) =>
      toast.success(`Đã xác nhận ${count} câu`, { description: "Máy sẽ không hỏi lại những câu này; mỗi câu là một nhãn đúng để học." }),
    onError: (error: Error) => toast.error("Chưa xác nhận được", { description: error.message }),
    onSettled: () => {
      void client.invalidateQueries({ queryKey: ["casting", bookId] });
      void client.invalidateQueries({ queryKey: ["work", bookId] });
    },
  });
}

function useLineFix(bookId: string, chapterId: number) {
  const client = useQueryClient();
  const when = useWhenApplied(bookId);
  return useMutation({
    mutationFn: ({ line, change }: { line: Line; change: Delivery }) =>
      api(`/api/books/${bookId}/line`, {
        method: "POST",
        body: { stableId: line.stableId, textSha256: line.textSha256, ...change },
      }),
    onMutate: ({ line, change }) => {
      client.setQueryData<ChapterScript>(["casting", bookId, chapterId], (data) =>
        data && {
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
        },
      );
    },
    onSuccess: () =>
      toast.success("Đã ghi cách đọc câu này", { description: `Câu đã thu sẽ được thu lại. ${when}` }),
    onError: (error: Error) => toast.error("Chưa ghi được", { description: error.message }),
    onSettled: () => {
      void client.invalidateQueries({ queryKey: ["casting", bookId] });
      void client.invalidateQueries({ queryKey: ["work", bookId] });
    },
  });
}

// Bảng sửa cách đọc một câu: loại đoạn, cảm xúc, mức. Lời kể thành lời thoại / nội tâm thì phải chọn người nói (một câu
// thoại luôn có chủ). Mức do khâu phân tích hiệu chỉnh lại theo cảm xúc - thì thầm, dịu dàng tối đa "Vừa".
function DeliveryMenu({ bookId, line, script, onSave, wide = false }: { bookId: string; line: Line; script: ChapterScript; onSave: (change: Delivery) => void; wide?: boolean }) {
  const waiting = line.lineWish?.state === "pending" ? line.lineWish : null;
  const [kind, setKind] = useState(waiting?.kind || line.kind);
  const [emotion, setEmotion] = useState(waiting?.emotion || line.emotion || "neutral");
  const [level, setLevel] = useState(waiting?.intensity ?? line.intensity ?? 0);
  const [speaker, setSpeaker] = useState<string>("");
  // Chữ đem đọc (STUDIO_REVIEW mục 7): sửa lỗi chữ / cách viết lạ của riêng câu này - sách giữ nguyên chữ của nó.
  const reading = line.spoken ?? line.text;
  const [words, setWords] = useState(waiting?.spoken || reading);
  const needsSpeaker = line.kind === "narration" && kind !== "narration";
  const names = useNamesInLine(bookId, line.text);
  const change: Delivery = {};
  if (kind !== line.kind) change.kind = kind;
  if (line.emotion !== null && emotion !== line.emotion) change.emotion = emotion;
  if (line.intensity !== null && level !== line.intensity) change.intensity = level;
  if (needsSpeaker && speaker) change.speaker = speaker;
  const cleaned = words.replace(/\s+/g, " ").trim();
  if (cleaned !== reading.replace(/\s+/g, " ").trim()) {
    if (!cleaned) {
      if (line.spoken) change.spoken = ""; // ô trống: trả về chữ của sách
    } else change.spoken = cleaned === line.text.trim() ? "" : cleaned;
  }
  const ready = Object.keys(change).length > 0 && (!needsSpeaker || Boolean(speaker));
  return (
    <div className={cn("space-y-3 p-1.5", wide ? "w-full" : "w-[min(88vw,340px)]")} data-delivery-menu>
      {/* Mục tên nằm cuối bảng, dưới nếp cuộn - chỉ lối xuống đó ngay đầu bảng (soát UX 29-09). */}
      {names.length > 0 && (
        <button
          type="button"
          onClick={(event) => event.currentTarget.closest("[data-delivery-menu]")?.querySelector("[data-names-section]")?.scrollIntoView({ block: "nearest", behavior: "smooth" })}
          className="text-xs font-medium text-accent-text hover:underline"
        >
          Sửa cách đọc {names.length} tên trong câu ↓
        </button>
      )}
      <div>
        <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-fg-3">Loại đoạn</div>
        <Segmented label="Loại đoạn" value={kind} onChange={setKind} options={KINDS} />
      </div>
      {needsSpeaker && (
        <div>
          <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-fg-3">Ai nói câu này?</div>
          <div className="flex flex-wrap gap-1.5">
            {script.cast.slice(0, 8).map((person) => (
              <button
                key={person.value}
                type="button"
                aria-pressed={speaker === person.value}
                onClick={() => setSpeaker(person.value)}
                className={cn(
                  "rounded-full border px-2.5 py-1 text-xs font-medium",
                  speaker === person.value ? "border-accent bg-accent-soft text-accent-text" : "border-line text-fg-2 hover:bg-hover",
                )}
              >
                {person.label}
              </button>
            ))}
          </div>
        </div>
      )}
      {line.emotion !== null && (
        <div>
          <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-fg-3">Cảm xúc</div>
          <div className="grid grid-cols-3 gap-1">
            {EMOTIONS.map(([value, label]) => (
              <button
                key={value}
                type="button"
                aria-pressed={emotion === value}
                onClick={() => setEmotion(value)}
                className={cn(
                  "h-8 rounded-lg px-1 text-xs font-medium",
                  emotion === value ? "bg-accent-soft text-accent-text ring-1 ring-accent/40" : "text-fg-2 hover:bg-hover",
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
          <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-fg-3">Mức</div>
          <Segmented
            label="Mức"
            value={String(level)}
            onChange={(value) => setLevel(Number(value))}
            options={LEVELS.map((label, index) => ({ value: String(index), label }))}
          />
          <p className="mt-1.5 text-[11px] leading-snug text-fg-3">Máy giữ mức trong tầm giọng đọc được: thì thầm, dịu dàng tối đa "Vừa".</p>
        </div>
      )}
      <label className="block">
        <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wider text-fg-3">Chữ đem đọc</span>
        <textarea
          id={`spoken-${line.stableId}`}
          value={words}
          onChange={(event) => setWords(event.target.value)}
          rows={Math.min(5, Math.max(2, Math.ceil(words.length / 42)))}
          className="w-full resize-y rounded-lg border border-line bg-panel px-2.5 py-1.5 text-sm leading-relaxed outline-none focus:border-accent"
        />
        <span className="mt-1 block text-[11px] leading-snug text-fg-3">
          Sửa lỗi chữ hay cách viết lạ của riêng câu này; sách và phần đọc theo giữ nguyên.
          {line.spoken ? " Xoá hết rồi lưu để trả về chữ của sách." : ""}
        </span>
      </label>
      {line.spoken && (
        <button type="button" className="text-xs font-medium text-accent-text" onClick={() => setWords(line.text)}>
          Trả về chữ của sách
        </button>
      )}
      <Button size="sm" variant="primary" className="w-full" disabled={!ready} onClick={() => onSave(change)}>
        {needsSpeaker && !speaker ? "Chọn người nói trước" : "Lưu cho câu này"}
      </Button>
      {/* Tên riêng trong câu đọc sai là sai ở MỌI câu có tên ấy: sửa ngay tại đây, cho cả cuốn (mục "Cách đọc tên" ở tab
          Nhân vật) - tách khỏi nút "Lưu cách đọc" vốn chỉ cho riêng câu này. */}
      {names.length > 0 && (
        <div className="border-t border-line pt-3" data-names-section>
          <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-fg-3">Tên trong câu · sửa cho cả cuốn</div>
          <div className="space-y-2">
            {names.map((item) => (
              <NameInLine key={item.surface} bookId={bookId} item={item} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function DeliveryChip({
  bookId,
  line,
  script,
  open,
  onOpenChange,
  onSave,
  quiet,
}: {
  bookId: string;
  line: Line;
  script: ChapterScript;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSave: (change: Delivery) => void;
  quiet: boolean;
}) {
  const phone = useMediaQuery("(max-width: 639px)");
  if (line.emotion === null) return null;
  const waiting = line.lineWish?.state === "pending" ? line.lineWish : null;
  const text = waiting
    ? deliveryText(waiting.emotion || line.emotion, waiting.intensity ?? line.intensity)
    : deliveryText(line.emotion, line.intensity);
  const trigger = (
    <button
      type="button"
      onClick={(event) => event.stopPropagation()}
      aria-label={`Cách đọc: ${text}. Bấm để sửa`}
      className={cn(
        // Màn cảm ứng: nút chỉ 24 px - nới vùng chạm theo chiều dọc lên ~44 px (soát UX 29-09).
        "relative inline-flex h-6 items-center gap-1 rounded-md px-1.5 text-[11px] font-medium text-fg-3 hover:bg-panel hover:text-fg focus-visible:opacity-100 pointer-coarse:after:absolute pointer-coarse:after:inset-x-0 pointer-coarse:after:-inset-y-2.5 pointer-coarse:after:content-['']",
        quiet && !open && "opacity-0 group-hover:opacity-100",
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
      <Sheet open={open} onOpenChange={onOpenChange} title="Cách đọc câu này" trigger={trigger} onEscapeKeyDown={keepOpenForNameEditor}>
        <LineQuote line={line} />
        <DeliveryMenu bookId={bookId} line={line} script={script} onSave={onSave} wide />
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
          onCloseAutoFocus={(event) => event.preventDefault()}
          onEscapeKeyDown={keepOpenForNameEditor}
          // Bảng cao hơn màn nhỏ (655 px trong khung 486 px: đỉnh ra ngoài màn, không với tới) - cuộn trong phần còn trống.
          className="z-50 max-h-[var(--radix-popover-content-available-height)] overflow-y-auto overscroll-contain rounded-xl border border-line bg-panel p-1.5 shadow-float"
        >
          <DeliveryMenu bookId={bookId} line={line} script={script} onSave={onSave} />
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}

/** Tấm trượt trên điện thoại che mất đúng câu vừa chạm (soát UX 30-09) - trích lại câu ấy ở đầu tấm. */
function LineQuote({ line }: { line: Line }) {
  return <p className="mx-1.5 mt-2 line-clamp-3 rounded-lg bg-hover px-3 py-2 text-sm leading-snug text-fg-2">{line.text}</p>;
}

/** `phone`: trong tấm trượt - ô tìm không tự bật bàn phím (bàn phím che danh sách người của chương, lối chọn chính). */
function SpeakerMenu({ line, script, onPick, phone = false }: { line: Line; script: ChapterScript; onPick: (person: Person) => void; phone?: boolean }) {
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
        <span className="avatar grid size-6 shrink-0 place-items-center rounded-full text-[11px] font-bold" style={hue(person.label)} aria-hidden>
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
    <div>
      <label className="flex h-9 items-center gap-2 rounded-lg border border-line bg-panel-2 px-2.5 focus-within:border-accent">
        <Search className="size-4 shrink-0 text-fg-3" />
        <input
          autoFocus={!phone}
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
      <div className={cn("mt-1.5 overflow-y-auto", phone ? "max-h-[60dvh]" : "max-h-[min(60vh,360px)]")}>
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
                <div className="px-2 pb-1 pt-1.5 text-[11px] font-semibold uppercase tracking-wider text-warning">Máy gợi ý</div>
                {item(suggested)}
              </>
            )}
            {script.cast.length > 0 && (
              <>
                <div className="px-2 pb-1 pt-1.5 text-[11px] font-semibold uppercase tracking-wider text-fg-3">Nói trong chương này</div>
                {script.cast.map((person, index) => item(person, index < HOTKEYS ? index + 1 : undefined))}
              </>
            )}
            <div className="px-2 pb-1 pt-1.5 text-[11px] font-semibold uppercase tracking-wider text-fg-3">Khác</div>
            {FIXED.map((person) => item(person))}
          </>
        )}
      </div>
    </div>
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
      className="avatar inline-flex h-7 max-w-full items-center gap-1 rounded-full px-2.5 text-[13px] font-semibold transition-[filter] hover:brightness-95 disabled:cursor-default disabled:hover:brightness-100"
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
          onCloseAutoFocus={(event) => event.preventDefault()}
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
  dim,
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
  rowRef,
}: {
  bookId: string;
  line: Line;
  script: ChapterScript;
  active: boolean;
  /** Nằm trong nhóm câu đang chọn (Shift): phím số / chọn người áp cho cả nhóm. */
  selected: boolean;
  dim: boolean;
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
  rowRef: (element: HTMLLIElement | null) => void;
}) {
  const clip = useClip();
  const id = `script-${line.segmentId}`;
  const playing = clip.current === id;
  const speech = isSpeech(line);
  const suggested = line.hint?.suggest ? [...script.cast, ...script.others].find((person) => person.value === line.hint?.suggest) : undefined;
  return (
    <li
      ref={rowRef}
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
        "group grid grid-cols-[minmax(0,1fr)_28px] gap-x-3 gap-y-1 rounded-lg px-2 py-1.5 outline-none lg:grid-cols-[160px_minmax(0,1fr)_28px]",
        gap && "mt-3",
        active && "bg-hover",
        selected && "bg-accent-soft ring-1 ring-inset ring-accent/40",
        speech && "focus-visible:ring-2 focus-visible:ring-accent/50",
        (dim || context) && "opacity-45",
      )}
    >
      <div className={cn("col-span-2 min-w-0 lg:col-span-1", !speech && "hidden lg:block")}>
        {speech && <SpeakerChip line={line} script={script} open={menuOpen} onOpenChange={onMenu} onPick={onPick} />}
      </div>
      <div className="min-w-0">
        <p className={cn("text-[15px] leading-relaxed", speech ? "text-fg" : "text-fg-2", line.kind === "thought" && "italic")}>
          {line.kind === "thought" && <span className="mr-1.5 rounded bg-hover px-1.5 py-px align-[1px] text-[11px] font-medium not-italic text-fg-2">nghĩ</span>}
          {line.text}
        </p>
        {line.spoken && (
          <p className="mt-0.5 text-xs text-fg-2">
            Đọc là: <span className="text-fg">{line.spoken}</span>
          </p>
        )}
        {script.castReady && (
          <DeliveryChip bookId={bookId} line={line} script={script} open={deliveryOpen} onOpenChange={onDelivery} onSave={onSaveDelivery} quiet={!speech && !active} />
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
      <div>
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
    </li>
  );
}

function ChapterScriptView({
  bookId,
  script,
  filter,
  who,
  wantedLine = null,
  pickLine = true,
  people,
  onPicked,
}: {
  bookId: string;
  script: ChapterScript;
  filter: Filter;
  who: string | null;
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
  const undos = useRef<(() => void)[]>([]);
  const assign = useAssign(bookId, script.chapterId, (undo) => {
    undos.current = [...undos.current.slice(-19), undo];
  });
  const fixLine = useLineFix(bookId, script.chapterId);
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
  const shown = useMemo(() => {
    const out: { line: Line; context: boolean }[] = [];
    if (filter !== "doubt") {
      for (const line of script.lines) if (filter === "all" || isSpeech(line)) out.push({ line, context: false });
      return out;
    }
    let previous: Line | null = null;
    for (const line of script.lines) {
      if (!isSpeech(line)) continue;
      if (line.hint) {
        if (previous && !out.some((entry) => entry.line.stableId === previous!.stableId)) out.push({ line: previous, context: true });
        out.push({ line, context: false });
      }
      previous = line;
    }
    return out;
  }, [script.lines, filter]);
  const speechRows = shown.filter((entry) => isSpeech(entry.line)).map((entry) => entry.line);
  const activeLine = speechRows.find((line) => line.stableId === active) ?? null;

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
      const undo = undos.current.pop();
      if (!undo) return;
      event.preventDefault();
      undo();
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
    return (
      <EmptyState icon={BookOpenText} title={filter === "doubt" ? "Máy không nghi câu nào trong chương này" : "Chương này chỉ có lời kể"} className="py-10">
        {filter === "doubt" ? "Chọn “Cả chương” để đọc lại toàn bộ." : "Không có câu nói nào để gán người."}
      </EmptyState>
    );
  }
  return (
    <>
      {selected.length > 1 && (
        <p className="mt-3 flex flex-wrap items-center gap-x-2 gap-y-1 rounded-lg bg-accent-soft px-3 py-1.5 text-[13px]" role="status">
          <span className="font-semibold">Đang chọn {selected.length} câu</span>
          <span className="text-fg-2">- phím số hay chọn người ở một câu trong nhóm gán cả {selected.length} câu · Esc bỏ chọn</span>
        </p>
      )}
      <ol aria-label={`Kịch bản ${script.title}`} aria-multiselectable onKeyDown={onKeyDown} className="mt-3">
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
            dim={Boolean(who) && (!isSpeech(line) || (line.wish?.state === "pending" ? line.wish.value : line.current) !== who)}
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
            rowRef={(element) => {
              if (element) rows.current.set(line.stableId, element);
              else rows.current.delete(line.stableId);
            }}
          />
        );
      })}
      </ol>
    </>
  );
}

function ChapterFooter({ bookId, script, onNext }: { bookId: string; script: ChapterScript; onNext: () => void }) {
  const confirm = useConfirmChapter(bookId);
  const open = script.lines.filter((line) => line.editable && !line.wish && !line.hint);
  const doubtful = script.lines.filter((line) => line.editable && !line.wish && line.hint).length;
  return (
    <div className="mt-6 flex flex-wrap items-center justify-between gap-3 border-t border-line pt-4">
      {script.castReady && open.length > 0 ? (
        <div className="min-w-0">
          <Button size="sm" variant="secondary" icon={Check} loading={confirm.isPending} onClick={() => confirm.mutate(open)}>
            Chương này đúng - xác nhận {open.length} câu
          </Button>
          <p className="mt-1 text-xs text-fg-3">
            Ghi nhận người nói của các câu chưa ai quyết{doubtful ? `, trừ ${doubtful} câu máy còn nghi` : ""}. Mỗi câu là một nhãn đúng để máy học.
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
        <button type="button" onClick={onNext} className="inline-flex items-center gap-1 text-sm font-medium text-fg-2 hover:text-fg">
          Chương sau <ChevronRight className="size-4" />
        </button>
      )}
    </div>
  );
}

export function ScriptTab({ bookId }: { bookId: string }) {
  const [params, setParams] = useSearchParams();
  const [filter, setFilter] = useState<Filter>("all");
  const [who, setWho] = useState<string | null>(null);
  // Người gán qua ô tìm (vai phụ, người của chương khác): thêm vào chú giải với số kế tiếp để câu sau gán bằng một phím.
  const [added, setAdded] = useState<Person[]>([]);
  const contents = useQuery({
    queryKey: ["casting", bookId],
    queryFn: () => api<Contents>(`/api/books/${bookId}/casting`),
  });
  const chapters = contents.data?.chapters ?? [];
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
    setParams(
      (previous) => {
        const next = new URLSearchParams(previous);
        next.set("chapter", String(id));
        return next;
      },
      { replace: true },
    );
  };

  if (contents.isLoading) return <Skeleton className="mt-6 h-40 rounded-xl" />;
  if (!chapters.length) {
    return (
      <EmptyState icon={BookOpenText} title="Chưa có kịch bản" className="py-10">
        Kịch bản hiện ra khi máy đã phân tích xong chương đầu tiên: câu nào là lời kể, câu nào của ai.
      </EmptyState>
    );
  }
  const data = script.data?.chapterId === chapterId ? script.data : undefined;
  const entry = chapters.find((chapter) => chapter.chapterId === chapterId);
  const doubts = data?.lines.filter((line) => line.hint).length ?? entry?.hints ?? 0;
  const said = (person: Person) =>
    data?.lines.filter((line) => isSpeech(line) && (line.wish?.state === "pending" ? line.wish.value : line.current) === person.value).length ?? 0;
  const people: Person[] = data
    ? [
        ...data.cast,
        ...added.filter((person) => !data.cast.some((item) => item.value === person.value)).map((person) => ({ ...person, lines: said(person) })),
      ]
    : [];
  return (
    <div className="mt-5">
      <p className="max-w-3xl text-sm text-fg-2">
        Đọc từng chương như kịch bản và sửa người nói của bất kỳ câu nào - bấm tên ở đầu câu. Sửa không dừng sách: sửa được áp
        khi sách chạy tiếp (sách đã xong: nút “Áp dụng thay đổi”), câu đã thu thì thu lại bằng giọng của người mới. Câu máy nghi có dấu vàng.
      </p>
      {/* Chương + chú giải người nói DÍNH khi cuộn (soát UX a6 01-10: cuộn xuống giữa chương là quên phím 4 là ai, muốn sang
          chương sau phải cuộn ngược lên đầu). */}
      <div className="sticky top-0 z-10 -mx-2 mt-2 bg-bg/95 px-2 pb-2 pt-2 backdrop-blur">
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex w-full min-w-0 items-center gap-1 sm:w-auto sm:max-w-full">
          <IconButton label="Chương trước" icon={ChevronLeft} disabled={!data?.previous} onClick={() => go(data?.previous ?? null)} />
          <select
            id="script-chapter"
            aria-label="Chương"
            value={chapterId}
            onChange={(event) => go(Number(event.target.value))}
            className="h-9 min-w-0 flex-1 rounded-lg border border-line bg-panel px-2.5 text-sm text-fg outline-none focus-visible:border-accent sm:w-[440px] sm:flex-initial"
          >
            {chapters.map((chapter) => (
              <option key={chapter.chapterId} value={chapter.chapterId}>
                {chapterLabel(chapter)}
              </option>
            ))}
          </select>
          <IconButton label="Chương sau" icon={ChevronRight} disabled={!data?.next} onClick={() => go(data?.next ?? null)} />
        </div>
        <div className="max-w-full overflow-x-auto sm:ml-auto">
          <Segmented<Filter>
            label="Hiện câu nào"
            value={filter}
            onChange={setFilter}
            options={[
              { value: "all", label: "Cả chương" },
              { value: "speech", label: "Chỉ lời nói" },
              { value: "doubt", label: `Máy nghi · ${doubts}` },
            ]}
          />
        </div>
      </div>
      {data && people.length > 0 && (
        <div className="mt-2 flex flex-wrap items-center gap-1.5" role="group" aria-label="Người nói trong chương - bấm để làm nổi câu của họ">
          {people.map((person, index) => (
            <button
              key={person.value}
              type="button"
              aria-pressed={who === person.value}
              onClick={() => setWho(who === person.value ? null : person.value)}
              className={cn(
                "inline-flex h-7 items-center gap-1.5 rounded-full border py-0 pl-1 pr-2.5 text-[13px] font-medium transition-opacity",
                who === person.value ? "border-line-strong bg-panel" : "border-transparent hover:bg-hover",
                who && who !== person.value && "opacity-50",
              )}
            >
              <span className="avatar grid size-5 place-items-center rounded-full text-[10px] font-bold" style={hue(person.label)} aria-hidden>
                {index < HOTKEYS ? index + 1 : ""}
              </span>
              {person.label}
              <span className="tabular text-fg-3">{formatNumber(person.lines)}</span>
            </button>
          ))}
        </div>
      )}
      {data?.castReady && people.length > 0 && (
        <p className="mt-1.5 hidden flex-wrap items-center gap-1.5 text-xs text-fg-3 md:flex">
          Bàn phím: <Kbd>↑</Kbd> <Kbd>↓</Kbd> chọn câu (<Kbd>Shift</Kbd> chọn nhiều) · <Kbd>1</Kbd>–<Kbd>{Math.min(HOTKEYS, people.length)}</Kbd> gán
          người theo số rồi sang câu kế · <Kbd>Enter</Kbd> danh sách · <Kbd>P</Kbd> nghe câu · <Kbd>Ctrl</Kbd>+<Kbd>Z</Kbd> hoàn tác
        </p>
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
              Người nói sửa được sau bước phân vai - lúc ấy mỗi nhân vật mới có giọng để gán. Trong lúc chờ, vẫn đọc được kịch
              bản máy đang hiểu.
            </p>
          )}
          {/* Chương kể ngôi thứ nhất: máy gán nhầm câu của người khác cho "tôi" nhiều nhất (8B-v5 trên bộ LN: 97/276 câu gán cho
              người kể là sai) - mời soát riêng câu của người kể trước. */}
          {data.castReady && data.firstPerson?.chip && who !== data.firstPerson.chip && (
            <p className="mt-3 flex flex-wrap items-center gap-x-2 gap-y-1 text-[13px] text-fg-2">
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
            filter={filter}
            who={who}
            wantedLine={params.get("line")}
            pickLine={params.get("pick") !== "0"}
            people={people}
            onPicked={(person) =>
              setAdded((current) =>
                person.value === UNNAMED || current.some((item) => item.value === person.value)
                  ? current
                  : [...current, person],
              )
            }
          />
          <ChapterFooter bookId={bookId} script={data} onNext={() => go(data.next)} />
        </>
      )}
    </div>
  );
}
