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
import { Button, EmptyState, IconButton, Kbd, Segmented, Skeleton } from "@/shared/ui";
import { api, urls } from "./api";

// Tab "Kịch bản" (webui/casting_review.py, docs/STUDIO_REVIEW.md mục 3): đọc cả chương như kịch bản - câu nào của ai - và
// đổi người nói của bất kỳ câu thoại hay nội tâm nào. Hộp "Việc cần anh" chỉ đưa ra chỗ máy nghi; ở đây người nghe duyệt
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
  firstPerson: { value: string; label: string } | null;
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

function useAssign(bookId: string, chapterId: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ line, value, newGender }: { line: Line; value: string; label: string; newGender?: Person["newGender"] }) =>
      api<{ lines: number; speaker: string }>(`/api/books/${bookId}/speaker`, {
        method: "POST",
        body: { lines: [{ stableId: line.stableId, textSha256: line.textSha256 }], speaker: value, newGender: newGender ?? "" },
      }),
    // Hiện ngay trên câu; bản thật về khi chương tải lại.
    onMutate: ({ line, value, label }) => {
      client.setQueryData<ChapterScript>(["casting", bookId, chapterId], (data) =>
        data && {
          ...data,
          lines: data.lines.map((item) =>
            item.stableId === line.stableId ? { ...item, wish: { value, label, state: value === item.current ? "applied" : "pending" } } : item,
          ),
        },
      );
    },
    onSuccess: (_result, { line, value, label }) => {
      if (value === line.current) {
        toast.success(`Đã xác nhận: câu này của ${line.label}`, { description: "Máy sẽ không hỏi lại câu này." });
        return;
      }
      toast.success(`Đã ghi: câu này của ${label}`, {
        description: "Áp ở ranh giới chương kế tiếp; câu đã thu sẽ được thu lại bằng giọng của người ấy.",
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
      toast.success("Đã ghi cách đọc câu này", { description: "Áp ở ranh giới chương kế tiếp; câu đã thu sẽ được thu lại." }),
    onError: (error: Error) => toast.error("Chưa ghi được", { description: error.message }),
    onSettled: () => {
      void client.invalidateQueries({ queryKey: ["casting", bookId] });
      void client.invalidateQueries({ queryKey: ["work", bookId] });
    },
  });
}

// Bảng sửa cách đọc một câu: loại đoạn, cảm xúc, mức. Lời kể thành lời thoại / nội tâm thì phải chọn người nói (một câu
// thoại luôn có chủ). Mức do khâu phân tích hiệu chỉnh lại theo cảm xúc - thì thầm, dịu dàng tối đa "Vừa".
function DeliveryMenu({ line, script, onSave }: { line: Line; script: ChapterScript; onSave: (change: Delivery) => void }) {
  const waiting = line.lineWish?.state === "pending" ? line.lineWish : null;
  const [kind, setKind] = useState(waiting?.kind || line.kind);
  const [emotion, setEmotion] = useState(waiting?.emotion || line.emotion || "neutral");
  const [level, setLevel] = useState(waiting?.intensity ?? line.intensity ?? 0);
  const [speaker, setSpeaker] = useState<string>("");
  // Chữ đem đọc (STUDIO_REVIEW mục 7): sửa lỗi chữ / cách viết lạ của riêng câu này - sách giữ nguyên chữ của nó.
  const reading = line.spoken ?? line.text;
  const [words, setWords] = useState(waiting?.spoken || reading);
  const needsSpeaker = line.kind === "narration" && kind !== "narration";
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
    <div className="w-[min(88vw,340px)] space-y-3 p-1.5">
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
        {needsSpeaker && !speaker ? "Chọn người nói trước" : "Lưu cách đọc"}
      </Button>
    </div>
  );
}

function DeliveryChip({
  line,
  script,
  open,
  onOpenChange,
  onSave,
  quiet,
}: {
  line: Line;
  script: ChapterScript;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSave: (change: Delivery) => void;
  quiet: boolean;
}) {
  if (line.emotion === null) return null;
  const waiting = line.lineWish?.state === "pending" ? line.lineWish : null;
  const text = waiting
    ? deliveryText(waiting.emotion || line.emotion, waiting.intensity ?? line.intensity)
    : deliveryText(line.emotion, line.intensity);
  return (
    <Popover.Root open={open} onOpenChange={onOpenChange}>
      <Popover.Trigger asChild>
        <button
          type="button"
          onClick={(event) => event.stopPropagation()}
          aria-label={`Cách đọc: ${text}. Bấm để sửa`}
          className={cn(
            "inline-flex h-6 items-center gap-1 rounded-md px-1.5 text-[11px] font-medium text-fg-3 hover:bg-panel hover:text-fg focus-visible:opacity-100",
            quiet && !open && "opacity-0 group-hover:opacity-100",
            waiting && "text-fg-2",
          )}
        >
          {waiting && <Clock className="size-3" />}
          {text}
        </button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          align="start"
          sideOffset={6}
          collisionPadding={12}
          onCloseAutoFocus={(event) => event.preventDefault()}
          className="z-50 rounded-xl border border-line bg-panel p-1.5 shadow-float"
        >
          <DeliveryMenu line={line} script={script} onSave={onSave} />
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}

function SpeakerMenu({ line, script, onPick }: { line: Line; script: ChapterScript; onPick: (person: Person) => void }) {
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
        className="flex h-9 w-full items-center gap-2 rounded-lg px-2 text-left text-sm hover:bg-hover focus-visible:bg-hover focus-visible:outline-none"
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
          autoFocus
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
      <div className="mt-1.5 max-h-[min(60vh,360px)] overflow-y-auto">
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
  const waiting = line.wish?.state === "pending";
  const shown = waiting ? line.wish!.label : line.label;
  const Icon = waiting ? Clock : line.wish?.state === "applied" ? Check : ChevronDown;
  return (
    <Popover.Root open={open} onOpenChange={onOpenChange}>
      <Popover.Trigger asChild>
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
      </Popover.Trigger>
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
  dim,
  context,
  gap,
  menuOpen,
  onMenu,
  onActivate,
  onPick,
  deliveryOpen,
  onDelivery,
  onSaveDelivery,
  rowRef,
}: {
  bookId: string;
  line: Line;
  script: ChapterScript;
  active: boolean;
  dim: boolean;
  context: boolean;
  gap: boolean;
  menuOpen: boolean;
  onMenu: (open: boolean) => void;
  onActivate: () => void;
  onPick: (person: Person) => void;
  deliveryOpen: boolean;
  onDelivery: (open: boolean) => void;
  onSaveDelivery: (change: Delivery) => void;
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
      onFocus={speech ? onActivate : undefined}
      onClick={speech ? onActivate : undefined}
      className={cn(
        "group grid grid-cols-[minmax(0,1fr)_28px] gap-x-3 gap-y-1 rounded-lg px-2 py-1.5 outline-none lg:grid-cols-[160px_minmax(0,1fr)_28px]",
        gap && "mt-3",
        active && "bg-hover",
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
          <DeliveryChip line={line} script={script} open={deliveryOpen} onOpenChange={onDelivery} onSave={onSaveDelivery} quiet={!speech && !active} />
        )}
        {line.lineWish?.state === "pending" && (
          <p className="mt-0.5 flex items-center gap-1.5 text-xs text-fg-2">
            <Clock className="size-3.5 shrink-0" />
            Đã ghi cách đọc mới
            {line.lineWish.kind ? ` (${KINDS.find((item) => item.value === line.lineWish?.kind)?.label.toLowerCase()})` : ""}
            {line.lineWish.spoken !== undefined ? (line.lineWish.spoken ? ` - đọc là "${line.lineWish.spoken}"` : " - trả về chữ của sách") : ""} - áp ở
            ranh giới chương kế tiếp.
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
            Đã ghi {line.wish.label} (máy gán {line.label}) - áp ở ranh giới chương kế tiếp.
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

function ChapterScriptView({ bookId, script, filter, who }: { bookId: string; script: ChapterScript; filter: Filter; who: string | null }) {
  const assign = useAssign(bookId, script.chapterId);
  const fixLine = useLineFix(bookId, script.chapterId);
  const [active, setActive] = useState<string | null>(null);
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
  }, [script.chapterId]);

  const focusRow = (line: Line | undefined) => {
    if (!line) return;
    setActive(line.stableId);
    const element = rows.current.get(line.stableId);
    element?.focus({ preventScroll: true });
    element?.scrollIntoView({ block: "nearest" });
  };
  // Menu đóng (chọn xong hay Esc) thì tiêu điểm về lại câu, để ↑ ↓ và phím số làm tiếp từ đó.
  const backTo = (line: Line) => {
    setMenu(null);
    setDelivery(null);
    requestAnimationFrame(() => rows.current.get(line.stableId)?.focus({ preventScroll: true }));
  };
  const pick = (line: Line, person: Person, refocus = true) => {
    if (refocus) backTo(line);
    if (!script.castReady || !line.editable) return;
    if (line.wish && line.wish.value === person.value) return;
    assign.mutate({ line, value: person.value, label: person.label, newGender: person.newGender });
  };

  const onKeyDown = (event: KeyboardEvent<HTMLOListElement>) => {
    if (menu || delivery || event.altKey || event.ctrlKey || event.metaKey) return;
    const index = activeLine ? speechRows.indexOf(activeLine) : -1;
    if (event.key === "ArrowDown" || event.key === "j") {
      event.preventDefault();
      focusRow(speechRows[Math.min(index + 1, speechRows.length - 1)]);
    } else if (event.key === "ArrowUp" || event.key === "k") {
      event.preventDefault();
      focusRow(speechRows[Math.max(index - 1, 0)]);
    } else if ((event.key === "Enter" || event.key === " ") && activeLine) {
      event.preventDefault();
      if (script.castReady && activeLine.editable) setMenu(activeLine.stableId);
    } else if (event.key === "e" && activeLine && script.castReady && activeLine.emotion !== null) {
      event.preventDefault();
      setDelivery(activeLine.stableId);
    } else if (/^[1-9]$/.test(event.key) && activeLine) {
      const person = script.cast[Number(event.key) - 1];
      if (!person) return;
      event.preventDefault();
      pick(activeLine, person, false);
      focusRow(speechRows[index + 1] ?? activeLine);
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
    <ol aria-label={`Kịch bản ${script.title}`} onKeyDown={onKeyDown} className="mt-3">
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
            dim={Boolean(who) && (!isSpeech(line) || (line.wish?.state === "pending" ? line.wish.value : line.current) !== who)}
            context={context}
            gap={gap}
            menuOpen={menu === line.stableId}
            onMenu={(open) => {
              if (!open) return backTo(line);
              setMenu(line.stableId);
              setActive(line.stableId);
            }}
            onActivate={() => setActive(line.stableId)}
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
            rowRef={(element) => {
              if (element) rows.current.set(line.stableId, element);
              else rows.current.delete(line.stableId);
            }}
          />
        );
      })}
    </ol>
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
  return (
    <div className="mt-5">
      <p className="max-w-3xl text-sm text-fg-2">
        Đọc từng chương như kịch bản và sửa người nói của bất kỳ câu nào - bấm tên ở đầu câu. Sửa không dừng sách: dây chuyền
        áp ở ranh giới chương kế tiếp, câu đã thu thì thu lại bằng giọng của người mới. Câu máy nghi có dấu vàng.
      </p>
      <div className="mt-4 flex flex-wrap items-center gap-2">
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
              Người nói sửa được sau bước phân vai - lúc ấy mỗi nhân vật mới có giọng để gán. Giờ anh vẫn đọc được kịch bản máy
              đang hiểu.
            </p>
          )}
          {data.cast.length > 0 && (
            <div className="mt-4 flex flex-wrap items-center gap-1.5" role="group" aria-label="Người nói trong chương - bấm để làm nổi câu của họ">
              {data.cast.map((person, index) => (
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
          {data.castReady && data.cast.length > 0 && (
            <p className="mt-2 hidden flex-wrap items-center gap-1.5 text-xs text-fg-3 md:flex">
              Bàn phím: <Kbd>↑</Kbd> <Kbd>↓</Kbd> chọn câu · <Kbd>1</Kbd>–<Kbd>{Math.min(HOTKEYS, data.cast.length)}</Kbd> gán người theo số ở
              trên rồi sang câu kế · <Kbd>Enter</Kbd> mở danh sách
            </p>
          )}
          <ChapterScriptView bookId={bookId} script={data} filter={filter} who={who} />
          <ChapterFooter bookId={bookId} script={data} onNext={() => go(data.next)} />
        </>
      )}
    </div>
  );
}
