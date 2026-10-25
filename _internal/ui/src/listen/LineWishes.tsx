import { withViewTransition } from "@/shared/motion";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, Clock, MessageSquareQuote, RefreshCw, Type, UserRound, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { toast, toastDone } from "@/shared/toast";
import { useBackLayer } from "@/shared/backStack";
import { cn } from "@/shared/cn";
import { AnimatedRows, MotionPresence } from "@/shared/MotionPresence";
import { MotionRegion } from "@/shared/MotionRegion";
import { studioNeed, syncsToComputer } from "@/shared/capabilities";
import { holderName } from "@/shared/editsSync";
import { Button, Dialog } from "@/shared/ui";
import { api } from "@/studio/api";
import { refreshAfterDecision, retakeWhen, UNDO_MS, undoAction, undoToast, waitingStudio } from "@/studio/decisions";
import { theirDelivery, verdictWord, warnElsewhere } from "@/studio/elsewhere";
import { EditReading } from "@/studio/NameReadings";
import { reachSummary, useReach } from "@/studio/readingReach";
import { DeliveryMenu, deliveryWords, LineQuote, NARRATOR, postLineFix, SpeakerMenu, undoLineFix, type ChapterScript, type Delivery, type Line, type Person } from "@/studio/ScriptTab";
import { cleanName } from "./BookScreen";
import { refreshAfterEdit } from "./EditBook";
import type { Cast, CastMember, ListenBook, Script, ScriptSegment } from "./model";
import { useReadAloudTry } from "./readings";
import { useCast } from "./source";

// Sửa MỘT CÂU từ trang đọc, trên cuốn không có xưởng (file .abook trên máy tính hay điện thoại - docs/EDITING.md, P2a). Cùng
// những việc tab Kịch bản của Studio làm cho cuốn có xưởng - ai nói câu này, loại câu / cảm xúc / chữ đem đọc, cách đọc một tên,
// thu lại câu - đi cùng các đường POST /speaker, /line, /pronunciation, /review. Khác ở chỗ ghi: ý muốn nằm trong lớp sửa của
// file sách và chờ Studio ("Đang chờ Studio"), không áp vào giọng đọc nào. Dùng lại đúng các bảng chọn của tab Kịch bản.

/** Ý muốn của một câu đang chờ Studio (GET /wishes): người nói, cách đọc, thu lại. */
export interface LineWish {
  /** `newGender`: người nghe TẠO người này (chưa có trong sách) - chọn lại ở câu khác cần cùng giới. */
  speaker?: { name: string; shown: string; requestedAt: number; newGender?: "male" | "female" | "unknown"; held?: boolean };
  delivery?: { kind: string; emotion: string; intensity: number | null; spoken?: string; requestedAt: number };
  retake?: { requestedAt: number };
}

export interface NameWish {
  key: string;
  surface: string;
  spokenForm: string;
  requestedAt: number;
}

export interface WishesView {
  pronunciations: NameWish[];
  lines: Record<string, LineWish>;
}

/** Ý muốn theo từng câu của cuốn không có xưởng - trang đọc đánh dấu "đang chờ Studio" ngay trên câu. */
export function useWishes(bookId: string, enabled: boolean) {
  return useQuery({
    queryKey: ["wishes", bookId],
    enabled,
    queryFn: () => api<WishesView>(`/api/books/${bookId}/wishes`),
  });
}

function sameWord(a: string, b: string): boolean {
  return a.normalize("NFC").toLocaleLowerCase("vi") === b.normalize("NFC").toLocaleLowerCase("vi");
}

/** Mọi người có giọng của cuốn: người nói trong chương này đứng trước (kèm số câu trong chương), người khác sau. Người nghe vừa TẠO (đang chờ
 *  máy làm sách, chưa có trong dàn nhân vật) cũng có ở cuối - chọn được cho câu khác, không phải tạo lại cùng tên (soát a70). */
function peopleOf(cast: Cast | undefined, script: Script, wishes?: WishesView): { here: Person[]; others: Person[] } {
  const all: CastMember[] = [...(cast?.characters ?? []), ...(cast?.extras ?? []), ...(cast?.carried ?? [])].filter((person) => person.voice);
  const said = new Map<string, number>();
  for (const segment of script.segments) {
    if (segment.kind === "dialogue" || segment.kind === "thought") said.set(cleanName(segment.speaker).toLowerCase(), (said.get(cleanName(segment.speaker).toLowerCase()) ?? 0) + 1);
  }
  const here: Person[] = [];
  const others: Person[] = [];
  const seen = new Set<string>();
  for (const person of all) {
    if (seen.has(person.name)) continue;
    seen.add(person.name);
    const label = cleanName(person.displayName);
    const count = said.get(label.toLowerCase());
    if (count) here.push({ value: person.name, label, lines: count });
    else others.push({ value: person.name, label, lines: person.lines });
  }
  here.sort((a, b) => b.lines - a.lines);
  for (const wish of Object.values(wishes?.lines ?? {})) {
    const pending = wish.speaker;
    if (!pending?.newGender || seen.has(pending.name)) continue;
    seen.add(pending.name);
    others.push({ value: pending.name, label: pending.shown, lines: 0, newGender: pending.newGender });
  }
  return { here, others };
}

/** Một câu của chữ đọc theo -> `Line` của bảng chọn dùng chung với tab Kịch bản (không có hint, không có audio riêng). */
function lineOf(segment: ScriptSegment, index: number, people: Person[], wish: LineWish | undefined): Line {
  const speaker = cleanName(segment.speaker);
  const found = people.find((person) => person.label.toLowerCase() === speaker.toLowerCase());
  return {
    segmentId: segment.id,
    stableId: segment.stableId ?? "",
    textSha256: segment.textSha256 ?? "",
    seq: index,
    paragraph: segment.paragraph,
    text: segment.text,
    kind: segment.kind,
    speaker: segment.speaker,
    current: found?.value ?? (speaker ? speaker : NARRATOR),
    label: speaker || "Người kể",
    editable: true,
    hasAudio: false,
    hint: null,
    wish: wish?.speaker ? { value: wish.speaker.name, label: wish.speaker.shown, state: "pending" } : null,
    emotion: segment.emotion ?? null,
    intensity: segment.intensity ?? null,
    lineWish: wish?.delivery
      ? { kind: wish.delivery.kind, emotion: wish.delivery.emotion, intensity: wish.delivery.intensity, ...(wish.delivery.spoken !== undefined ? { spoken: wish.delivery.spoken } : {}), state: "pending" }
      : null,
    spoken: segment.spoken ?? null,
  };
}

/** Những gì đang chờ Studio của câu, nói bằng lời (cho hộp sửa câu). */
/** `held`: việc máy giữ sách đã nhận (đặt ở đó, hay điện thoại này đã gửi) - bỏ hay đổi bằng cách chọn lại ở đây, không rút được như việc chưa gửi. */
function waitingItems(wish: LineWish | undefined): { key: string; text: string; section: string; requestedAt: number; held?: boolean }[] {
  const items: { key: string; text: string; section: string; requestedAt: number; held?: boolean }[] = [];
  if (wish?.speaker) {
    items.push({ key: "speaker", text: `Người nói: ${wish.speaker.shown}`, section: "speakers", requestedAt: wish.speaker.requestedAt, held: wish.speaker.held });
  }
  if (wish?.delivery) {
    items.push({ key: "delivery", text: `Cách đọc câu - ${deliveryWords(wish.delivery) || "đã ghi"}`, section: "lines", requestedAt: wish.delivery.requestedAt });
  }
  if (wish?.retake) items.push({ key: "retake", text: "Thu lại câu này", section: "retakes", requestedAt: wish.retake.requestedAt });
  return items;
}

/** Dấu "đang chờ Studio" cạnh một câu trong trang đọc. */
export function WaitingMark({ className }: { className?: string }) {
  return <Clock aria-label="Đang chờ máy làm sách" role="img" className={cn("ml-1 inline size-[0.7em] align-[-0.05em] text-fg-3", className)} />;
}

type View = "menu" | "speaker" | "delivery" | "word";

function MenuRow({ icon: Icon, title, note, disabled, onClick, trailing }: { icon: typeof UserRound; title: string; note: ReactNode; disabled?: boolean; onClick: () => void; trailing?: ReactNode }) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className="flex w-full items-start gap-3 rounded-xl px-3 py-2.5 text-left hover:bg-hover disabled:cursor-default disabled:opacity-60 disabled:hover:bg-transparent"
    >
      <Icon className="mt-line-icon size-4 shrink-0 text-fg-2" />
      <span className="min-w-0 flex-1">
        <span className="block text-sm font-medium">{title}</span>
        <span className="block text-xs text-fg-2">{note}</span>
      </span>
      {trailing !== undefined ? trailing : disabled ? null : <ChevronRight className="ink-end mt-line-icon size-4 shrink-0 text-fg-3" />}
    </button>
  );
}

/** Các từ của câu, mỗi từ một lần - để chọn từ muốn sửa cách đọc (cách đọc lưu theo từng từ). */
function wordsOf(text: string): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const word of text.normalize("NFC").match(/[\p{L}\p{M}\p{N}]+(?:['’-][\p{L}\p{M}\p{N}]+)*/gu) ?? []) {
    const key = word.toLocaleLowerCase("vi");
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(word);
  }
  return out;
}

function WordView({ bookId, text, names, need, later, onWithdraw, onBack, initial = null }: {
  bookId: string;
  text: string;
  names: NameWish[];
  need: string;
  /** Lời hứa sau khi ghi (decisions.waitingStudio) và vế "thu lại khi nào" (decisions.retakeWhen) - cùng một ý ở hộp và ở thông báo. */
  later: string;
  /** Bỏ cách đọc đang chờ của một từ. */
  onWithdraw: (name: NameWish) => void;
  onBack: () => void;
  initial?: string | null;
}) {
  const [word, setWord] = useState<string | null>(initial);
  const words = useMemo(() => wordsOf(text), [text]);
  const pending = word ? names.find((item) => sameWord(item.surface, word)) : undefined;
  // Chưa có xưởng để thu thử: "Nghe thử" bằng giọng đọc của máy.
  const aloud = useReadAloudTry(bookId);
  // Trước khi ghi: từ ấy có trong bao nhiêu câu, bao nhiêu câu đã thu sẽ phải thu lại (như ô "Thêm cách đọc cho từ bất kỳ" của Studio).
  const reach = useReach(bookId, word ?? "", Boolean(word)).data;
  return (
    <div className="space-y-3">
      <p className="text-sm text-fg-2">Chạm vào từ máy đọc sai (thường là tên riêng). Cách đọc lưu cho cả cuốn: mọi câu có từ ấy.</p>
      <div className="flex flex-wrap gap-1.5" role="group" aria-label="Các từ trong câu">
        {words.map((item) => {
          const waiting = names.find((entry) => sameWord(entry.surface, item));
          return (
            <button
              key={item}
              type="button"
              aria-pressed={word === item}
              onClick={() => setWord(word === item ? null : item)}
              className={cn(
                "touch-row inline-flex min-h-10 items-center gap-1 px-2.5 text-sm transition-colors duration-motion-medium",
                word === item ? "text-accent-text underline underline-offset-4" : "text-fg-2 hover:bg-hover",
              )}
            >
              {waiting && <Clock className="size-3" />}
              {item}
            </button>
          );
        })}
      </div>
      {/* Chạm chip từ: khung sửa mở ra; đổi sang từ khác thì mờ qua; chạm lại thì khép (không bật tắt). */}
      <MotionPresence open={Boolean(word)}>
        <MotionRegion motionKey={word} className="rounded-xl border border-line p-3" data-name-editor>
          <MotionRegion className="mb-2 text-sm">
            <span className="font-semibold">{word}</span>
            {pending && (
              <span className="text-xs font-medium text-accent-text">
                {" "}
                · đang chờ máy làm sách: <span className="whitespace-nowrap">“{pending.spokenForm}”</span>
              </span>
            )}
            {pending && (
              <button
                type="button"
                onClick={() => onWithdraw(pending)}
                aria-label={`Bỏ cách đọc “${pending.surface}”`}
                className="ml-1.5 inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-xs font-medium text-accent-text hover:bg-hover"
              >
                <X className="size-3" /> Bỏ
              </button>
            )}
          </MotionRegion>
          <MotionPresence open={Boolean(reach && reach.surface === word)}>
            {reach && (
              <p className={cn("tabular mb-2 text-xs", reach.blocked ? "text-warning" : "text-fg-2")} data-reading-reach>
                {reachSummary(reach, later)}
              </p>
            )}
          </MotionPresence>
          {word && <EditReading
            key={word}
            bookId={bookId}
            item={{ surface: word, spoken: "", byListener: false, lines: 0, requested: pending?.spokenForm ?? null, example: null }}
            fresh={!pending}
            waiting={need}
            aloud={aloud}
            reach={reach?.surface === word ? reach : undefined}
            onDone={() => setWord(null)}
          />}
        </MotionRegion>
      </MotionPresence>
      <Button size="sm" variant="ghost" icon={ChevronLeft} onClick={onBack}>
        Quay lại
      </Button>
    </div>
  );
}

/** Hộp "Sửa câu này" của trang đọc (cuốn không có xưởng). `segmentIndex`: câu đang chọn trong `script.segments`. */
export function LineWishDialog({
  book,
  script,
  segmentIndex,
  wishes,
  word: heldWord = null,
  onClose,
}: {
  book: ListenBook;
  script: Script;
  segmentIndex: number | null;
  wishes: WishesView | undefined;
  /** Chữ người nghe vừa giữ (đường “giữ chữ”, như cuốn chỉ có chữ): hộp mở thẳng ở bước sửa cách đọc từ ấy. null: mở ở menu câu. */
  word?: string | null;
  onClose: () => void;
}) {
  const client = useQueryClient();
  const { data: cast } = useCast(book.id);
  const [view, setView] = useState<View>(heldWord ? "word" : "menu");
  // Từ mở ở bước sửa cách đọc: chữ vừa giữ, hay từ bấm "Sửa" trong danh sách cách đọc của câu.
  const [pickedWord, setPickedWord] = useState<string | null>(null);
  // Hộp vừa mở (câu khác) thì bước đầu hiện cùng hộp; chỉ bước người dùng tự chuyển mới trượt (.motion-step).
  const [moved, setMoved] = useState(false);
  const goView = (next: View) => {
    withViewTransition(() => { setMoved(true); setView(next); });
  };
  useEffect(() => {
    setView(heldWord ? "word" : "menu");
    setMoved(false);
    setPickedWord(null);
  }, [segmentIndex, heldWord]);
  // Bước con (Ai nói / Cách đọc / Sửa một từ) mở từ menu câu: Back của điện thoại về menu câu trước, chưa đóng cả hộp.
  const body = useRef<HTMLDivElement | null>(null);
  useBackLayer(view !== "menu" && !heldWord, () => {
    setPickedWord(null);
    goView("menu");
  }, body);
  const segment = segmentIndex === null ? undefined : script.segments[segmentIndex];
  const wish = segment?.stableId ? wishes?.lines[segment.stableId] : undefined;
  const people = useMemo(() => peopleOf(cast, script, wishes), [cast, script, wishes]);
  const line = segment && segmentIndex !== null ? lineOf(segment, segmentIndex, [...people.here, ...people.others], wish) : null;
  const chapterScript: ChapterScript = {
    chapterId: script.chapterId,
    index: 0,
    title: script.title,
    previous: null,
    next: null,
    castReady: true,
    firstPerson: null,
    cast: people.here.length ? people.here : people.others,
    others: people.here.length ? people.others : [],
    lines: [],
  };
  const need = studioNeed(book.capabilities) ?? "cần Studio";
  // Cuốn tải từ máy khác: thay đổi gửi sang máy ấy và áp ngay ở đó - lời hứa nói thế (decisions.waitingStudio).
  const holder = syncsToComputer(book.capabilities) ? holderName(book.remote) : null;
  const promise = waitingStudio(holder);
  const identified = Boolean(line?.stableId && line.textSha256);
  const speech = line?.kind === "dialogue" || line?.kind === "thought";
  const hasAudio = script.timed;
  const close = () => {
    goView("menu");
    onClose();
  };
  const done = () => {
    refreshAfterDecision(client, book.id);
    refreshAfterEdit(client, book.id);
  };
  const ref = line ? { stableId: line.stableId, textSha256: line.textSha256 } : { stableId: "", textSha256: "" };

  const speaker = useMutation({
    mutationFn: (person: Person) =>
      api<{ requestedAt: number; elsewhere?: Record<string, string> }>(`/api/books/${book.id}/speaker`, {
        method: "POST",
        // `seen`: người nói câu này đang chờ mà hộp thấy - cửa sổ khác vừa ghi khác thì được báo (soát a27 lỗi 4). Người nói máy giữ sách đặt
        // (`held`) không nằm trong lớp sửa của máy này: so với nó thì lần ghi nào cũng thành "vừa được sửa ở máy khác".
        body: { lines: [ref], speaker: person.value, newGender: person.newGender ?? "", seen: { [ref.stableId]: wish?.speaker && !wish.speaker.held ? wish.speaker.name : "" } },
      }),
    onSuccess: ({ requestedAt, elsewhere }, person) => {
      done();
      const action = undoAction(client, book.id, "speaker", [{ lines: [ref], requestedAt, keep: false }], "Câu này trở lại như trước khi đổi người nói.");
      const was = Object.values(elsewhere ?? {});
      if (was.length) warnElsewhere(1, was[0] ? (people.here.concat(people.others).find((item) => item.value === was[0])?.label ?? was[0]) : "", action.onClick);
      toast.success(`Đã ghi: câu này của ${person.label}`, {
        action,
        duration: UNDO_MS,
      });
      close();
    },
    onError: (error: Error) => toast.error("Chưa ghi được người nói", { description: error.message }),
  });
  const delivery = useMutation({
    // `seen`: cách đọc câu này đang chờ mà hộp thấy - cửa sổ/máy khác vừa ghi khác thì được hỏi (uxfix28 A).
    mutationFn: (change: Delivery) => postLineFix(book.id, ref, change, wish?.delivery),
    onSuccess: (answer) => {
      const { elsewhere } = answer;
      done();
      if (elsewhere) {
        const theirs = theirDelivery(elsewhere.delivery);
        const takeTheirs = () =>
          void api(`/api/books/${book.id}/line`, { method: "POST", body: { ...ref, ...theirs } })
            .then(done)
            .catch((error: Error) => toast.error("Chưa lấy lại được", { description: error.message }));
        warnElsewhere(1, elsewhere.delivery ? deliveryWords(elsewhere.delivery) : "", theirs ? takeTheirs : undefined);
      }
      toast.success("Đã ghi cách đọc câu này", {
        action: answer.requestedAt ? undoLineFix(client, book.id, ref, answer) : undefined,
        duration: UNDO_MS,
      });
      close();
    },
    onError: (error: Error) => toast.error("Chưa ghi được", { description: error.message }),
  });
  const retake = useMutation({
    // `seen`: hộp có thấy câu này đang chờ thu lại không - máy kia vừa xin/bỏ khác thì được hỏi (uxfix28 A).
    mutationFn: () =>
      api<{ elsewhere?: Record<string, string> }>(`/api/books/${book.id}/review`, {
        method: "POST",
        body: { verdict: "redo", stableId: ref.stableId, chapterId: script.chapterId, seen: { [ref.stableId]: wish?.retake ? "redo" : "" } },
      }),
    onSuccess: ({ elsewhere }) => {
      done();
      const theirs = elsewhere?.[ref.stableId];
      if (theirs !== undefined) {
        warnElsewhere(1, verdictWord(theirs), () =>
          void api(`/api/books/${book.id}/review`, { method: "POST", body: { verdict: theirs || null, stableId: ref.stableId, chapterId: script.chapterId } })
            .then(done)
            .catch((error: Error) => toast.error("Chưa lấy lại được", { description: error.message })),
        );
      }
      toast.success("Đã ghi: thu lại câu này", {
        action: {
          label: "Hoàn tác",
          onClick: () =>
            void api<{ sent?: boolean }>(`/api/books/${book.id}/review`, { method: "POST", body: { verdict: null, stableId: ref.stableId } })
              .then((answer) => {
                done();
                // Câu đã gửi sang máy giữ sách rồi: chỉ nhờ được máy ấy rút lại - nói đúng điều đó, đừng làm như đã xong.
                if (answer?.sent) toastDone(...undoToast(false, true));
              })
              .catch((error: Error) => toast.error("Không hoàn tác được", { description: error.message })),
        },
        duration: UNDO_MS,
      });
      close();
    },
    onError: (error: Error) => toast.error("Chưa ghi được", { description: error.message }),
  });
  const withdraw = useMutation({
    // `key`: mục cần bỏ - mã câu (người nói, cách đọc câu, thu lại) hay khoá từ (cách đọc một từ).
    mutationFn: (item: { section: string; requestedAt: number; key?: string }) =>
      api(`/api/books/${book.id}/pending-changes/withdraw`, {
        method: "POST",
        body: { section: item.section, key: item.key ?? ref.stableId, keys: [item.key ?? ref.stableId], requestedAt: item.requestedAt },
      }),
    onSuccess: done,
    onError: (error: Error) => toast.error("Không bỏ được thay đổi này", { description: error.message }),
  });
  const withdrawName = (name: NameWish) => withdraw.mutate({ section: "pronunciations", key: name.key, requestedAt: name.requestedAt });

  // Đang chờ của câu: việc của riêng câu + cách đọc đang chờ của các từ trong câu (sửa / bỏ ngay tại đây - soát a70: trước chỉ bỏ được ở trang sách).
  const sentenceWords = line ? wordsOf(line.text) : [];
  const names = (wishes?.pronunciations ?? []).filter((name) => sentenceWords.some((word) => sameWord(word, name.surface)));
  const items: { key: string; text: string; section: string; requestedAt: number; held?: boolean; name?: NameWish }[] = [
    ...waitingItems(wish),
    ...names.map((name) => ({ key: `name:${name.key}`, text: `Cách đọc “${name.surface}”: “${name.spokenForm}”`, section: "pronunciations", requestedAt: name.requestedAt, name })),
  ];
  const title = view === "speaker" ? (line?.kind === "thought" ? "Ai nghĩ câu này?" : "Ai nói câu này?") : view === "delivery" ? "Cách đọc câu này" : view === "word" ? "Đọc từ này là…" : "Sửa câu này";
  return (
    <Dialog open={segment !== undefined} onOpenChange={(open) => !open && close()} width="max-w-md" title={title}>
      {line && (
        <div ref={body} className="max-h-[68dvh] space-y-3 overflow-y-auto overscroll-contain pr-0.5">
          <LineQuote line={line} />
          {!identified && (
            <p className="rounded-lg bg-hover px-3 py-2 text-sm text-fg-2">
              File sách này làm bằng ABook bản cũ nên chưa ghi được việc riêng cho từng câu (người nói, cách đọc câu, thu lại). Sửa cách đọc một từ vẫn
              được; muốn sửa từng câu, làm lại file bằng ABook mới.
            </p>
          )}
          {/* Đổi bước (menu câu <-> Ai nói / Cách đọc / Sửa một từ): bước mới trượt vào như đổi trang - từ phải khi đi sâu, từ trái khi về menu. */}
          <div key={view} className={cn("space-y-3", moved && "motion-step")} data-direction={view === "menu" ? "back" : undefined}>
          {view === "menu" && (
            <>
              {/* Hộp không đóng khi bấm "Bỏ": hàng khép tại chỗ, khối khép khi hết việc, câu chốt mờ qua (soát chuyển động 139). */}
              <MotionPresence open={items.length > 0}>
                <div className="rounded-xl bg-info-soft px-3 py-2 text-sm" role="status">
                  <p className="flex items-center gap-1.5 font-medium">
                    <Clock className="size-4 shrink-0 text-info" /> Đang chờ máy làm sách
                  </p>
                  <AnimatedRows items={items} keyOf={(item) => item.key} className="mt-1">
                    {(item) => (
                      <div className="flex items-center gap-2 pb-1 text-fg-2">
                        <span className="min-w-0 flex-1 text-pretty">{item.text}</span>
                        {item.name && (
                          <button
                            type="button"
                            onClick={() => {
                              setPickedWord(item.name!.surface);
                              goView("word");
                            }}
                            aria-label={`Sửa cách đọc “${item.name.surface}”`}
                            className="inline-flex shrink-0 items-center gap-1 rounded-md px-1.5 py-0.5 text-xs font-medium text-accent-text hover:bg-hover"
                          >
                            Sửa
                          </button>
                        )}
                        {item.held ? (
                          <span className="shrink-0 text-xs text-fg-3">đã ở {holder ?? "máy tính"}</span>
                        ) : (
                          <button
                            type="button"
                            disabled={withdraw.isPending}
                            onClick={() => (item.name ? withdrawName(item.name) : withdraw.mutate(item))}
                            aria-label={`Bỏ: ${item.text}`}
                            className="inline-flex shrink-0 items-center gap-1 rounded-md px-1.5 py-0.5 text-xs font-medium text-accent-text hover:bg-hover"
                          >
                            <X className="size-3" /> Bỏ
                          </button>
                        )}
                      </div>
                    )}
                  </AnimatedRows>
                  {/* Chỉ có việc đã ở máy giữ sách (đặt ở đó): không có gì "đã gửi" từ máy này - chỉ nói khi nào giọng đổi. */}
                  <MotionRegion as="p" className="mt-0.5 text-xs text-fg-2">
                    {holder && items.every((item) => item.held) ? `Giọng đọc chưa đổi: Studio sẽ thu lại ${retakeWhen(holder)}.` : promise}
                  </MotionRegion>
                </div>
              </MotionPresence>
              <MotionRegion>
                <MenuRow
                  icon={UserRound}
                  title={line.kind === "thought" ? "Ai nghĩ câu này" : "Ai nói câu này"}
                  note={
                    !identified
                      ? "chưa sửa được từng câu ở file làm bằng ABook bản cũ"
                      : !speech
                        ? "Lời kể không có người nói - muốn gán người, đổi câu thành lời thoại ở “Cách đọc câu”"
                        : wish?.speaker
                          ? `Đang chờ máy làm sách: ${wish.speaker.shown}`
                          : `Hiện là ${line.label}`
                  }
                  disabled={!identified || !speech}
                  onClick={() => goView("speaker")}
                />
                <MenuRow
                  icon={MessageSquareQuote}
                  title="Cách đọc câu"
                  note="Loại câu, cảm xúc, chữ đem đọc"
                  disabled={!identified}
                  onClick={() => goView("delivery")}
                />
                <MenuRow icon={Type} title="Sửa cách đọc một từ" note="Chọn từ máy đọc sai, gõ cách đọc đúng" onClick={() => goView("word")} />
                <MenuRow
                  icon={RefreshCw}
                  title="Thu lại câu này"
                  note={!identified ? "chưa sửa được từng câu ở file làm bằng ABook bản cũ" : !hasAudio ? "Chương này chưa có audio - chưa có gì để thu lại" : wish?.retake ? "Đã ghi - đang chờ máy làm sách" : "Đọc lại một lần khác, giọng như cũ"}
                  disabled={!identified || !hasAudio || Boolean(wish?.retake) || retake.isPending}
                  onClick={() => retake.mutate()}
                  trailing={null}
                />
              </MotionRegion>
            </>
          )}
          {view === "speaker" && (
            <>
              <SpeakerMenu line={line} script={chapterScript} onPick={(person) => speaker.mutate(person)} phone />
              <Button size="sm" variant="ghost" icon={ChevronLeft} onClick={() => goView("menu")}>
                Quay lại
              </Button>
            </>
          )}
          {view === "delivery" && (
            <>
              <DeliveryMenu bookId={book.id} line={line} script={chapterScript} onSave={(change) => delivery.mutate(change)} wide noWorkshop />
              <Button size="sm" variant="ghost" icon={ChevronLeft} onClick={() => goView("menu")}>
                Quay lại
              </Button>
            </>
          )}
          {view === "word" && (
            <WordView
              key={`${segmentIndex}:${pickedWord ?? heldWord}`}
              initial={pickedWord ?? heldWord}
              bookId={book.id}
              text={line.text}
              names={wishes?.pronunciations ?? []}
              need={need}
              later={retakeWhen(holder)}
              onWithdraw={withdrawName}
              onBack={() => {
                setPickedWord(null);
                goView("menu");
              }}
            />
          )}
          </div>
        </div>
      )}
    </Dialog>
  );
}
