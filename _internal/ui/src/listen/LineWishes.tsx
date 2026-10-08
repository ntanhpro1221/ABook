import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, Clock, MessageSquareQuote, RefreshCw, Type, UserRound, X } from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";
import { toast } from "sonner";
import { cn } from "@/shared/cn";
import { studioNeed } from "@/shared/capabilities";
import { Button, Dialog } from "@/shared/ui";
import { api } from "@/studio/api";
import { refreshAfterDecision, UNDO_MS, undoAction, WAITING_STUDIO } from "@/studio/decisions";
import { EditReading } from "@/studio/NameReadings";
import { DeliveryMenu, deliveryText, KINDS, LineQuote, NARRATOR, SpeakerMenu, type ChapterScript, type Delivery, type Line, type Person } from "@/studio/ScriptTab";
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
  speaker?: { name: string; shown: string; requestedAt: number };
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

/** Mọi người có giọng của cuốn: người nói trong chương này đứng trước (kèm số câu trong chương), người khác sau. */
function peopleOf(cast: Cast | undefined, script: Script): { here: Person[]; others: Person[] } {
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
function waitingItems(wish: LineWish | undefined): { key: string; text: string; section: string; requestedAt: number }[] {
  const items: { key: string; text: string; section: string; requestedAt: number }[] = [];
  if (wish?.speaker) items.push({ key: "speaker", text: `Người nói: ${wish.speaker.shown}`, section: "speakers", requestedAt: wish.speaker.requestedAt });
  if (wish?.delivery) {
    const { kind, emotion, intensity, spoken } = wish.delivery;
    const parts = [
      kind ? `loại câu: ${KINDS.find((item) => item.value === kind)?.label.toLowerCase() ?? kind}` : "",
      emotion ? `cảm xúc: ${deliveryText(emotion, intensity).toLowerCase()}` : "",
      spoken !== undefined ? (spoken ? `đọc là “${spoken}”` : "trả về chữ của sách") : "",
    ].filter(Boolean);
    items.push({ key: "delivery", text: `Cách đọc câu - ${parts.join(", ") || "đã ghi"}`, section: "lines", requestedAt: wish.delivery.requestedAt });
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
      <Icon className="mt-0.5 size-4 shrink-0 text-fg-2" />
      <span className="min-w-0 flex-1">
        <span className="block text-sm font-medium">{title}</span>
        <span className="block text-xs text-fg-2">{note}</span>
      </span>
      {trailing !== undefined ? trailing : disabled ? null : <ChevronRight className="mt-0.5 size-4 shrink-0 text-fg-3" />}
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

function WordView({ bookId, text, names, need, onBack }: { bookId: string; text: string; names: NameWish[]; need: string; onBack: () => void }) {
  const [word, setWord] = useState<string | null>(null);
  const words = useMemo(() => wordsOf(text), [text]);
  const pending = word ? names.find((item) => sameWord(item.surface, word)) : undefined;
  // Chưa có xưởng để thu thử: "Nghe thử" bằng giọng đọc của máy.
  const aloud = useReadAloudTry(bookId);
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
                "inline-flex h-8 items-center gap-1 rounded-full border px-2.5 text-sm pointer-coarse:h-10",
                word === item ? "border-accent bg-accent-soft text-accent-text" : "border-line hover:bg-hover",
              )}
            >
              {waiting && <Clock className="size-3" />}
              {item}
            </button>
          );
        })}
      </div>
      {word && (
        <div className="rounded-xl border border-line p-3" data-name-editor>
          <div className="mb-2 text-sm">
            <span className="font-semibold">{word}</span>
            {pending && (
              <span className="text-xs font-medium text-accent-text">
                {" "}
                · đang chờ máy làm sách: <span className="whitespace-nowrap">“{pending.spokenForm}”</span>
              </span>
            )}
          </div>
          <EditReading
            key={word}
            bookId={bookId}
            item={{ surface: word, spoken: "", byListener: false, lines: 0, requested: pending?.spokenForm ?? null, example: null }}
            fresh={!pending}
            waiting={need}
            aloud={aloud}
            onDone={() => setWord(null)}
          />
        </div>
      )}
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
  onClose,
}: {
  book: ListenBook;
  script: Script;
  segmentIndex: number | null;
  wishes: WishesView | undefined;
  onClose: () => void;
}) {
  const client = useQueryClient();
  const { data: cast } = useCast(book.id);
  const [view, setView] = useState<View>("menu");
  const segment = segmentIndex === null ? undefined : script.segments[segmentIndex];
  const wish = segment?.stableId ? wishes?.lines[segment.stableId] : undefined;
  const people = useMemo(() => peopleOf(cast, script), [cast, script]);
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
  const identified = Boolean(line?.stableId && line.textSha256);
  const speech = line?.kind === "dialogue" || line?.kind === "thought";
  const hasAudio = script.timed;
  const close = () => {
    setView("menu");
    onClose();
  };
  const done = () => {
    refreshAfterDecision(client, book.id);
    refreshAfterEdit(client, book.id);
  };
  const ref = line ? { stableId: line.stableId, textSha256: line.textSha256 } : { stableId: "", textSha256: "" };

  const speaker = useMutation({
    mutationFn: (person: Person) =>
      api<{ requestedAt: number }>(`/api/books/${book.id}/speaker`, {
        method: "POST",
        body: { lines: [ref], speaker: person.value, newGender: person.newGender ?? "" },
      }),
    onSuccess: ({ requestedAt }, person) => {
      done();
      toast.success(`Đã ghi: câu này của ${person.label}`, {
        description: WAITING_STUDIO,
        action: undoAction(client, book.id, "speaker", [{ lines: [ref], requestedAt, keep: false }], "Câu này trở lại như trước khi đổi người nói."),
        duration: UNDO_MS,
      });
      close();
    },
    onError: (error: Error) => toast.error("Chưa ghi được người nói", { description: error.message }),
  });
  const delivery = useMutation({
    mutationFn: (change: Delivery) => api(`/api/books/${book.id}/line`, { method: "POST", body: { ...ref, ...change } }),
    onSuccess: () => {
      done();
      toast.success("Đã ghi cách đọc câu này", { description: WAITING_STUDIO });
      close();
    },
    onError: (error: Error) => toast.error("Chưa ghi được", { description: error.message }),
  });
  const retake = useMutation({
    mutationFn: () => api(`/api/books/${book.id}/review`, { method: "POST", body: { verdict: "redo", stableId: ref.stableId, chapterId: script.chapterId } }),
    onSuccess: () => {
      done();
      toast.success("Đã ghi: thu lại câu này", {
        description: WAITING_STUDIO,
        action: {
          label: "Hoàn tác",
          onClick: () =>
            void api(`/api/books/${book.id}/review`, { method: "POST", body: { verdict: null, stableId: ref.stableId } })
              .then(done)
              .catch((error: Error) => toast.error("Không hoàn tác được", { description: error.message })),
        },
        duration: UNDO_MS,
      });
      close();
    },
    onError: (error: Error) => toast.error("Chưa ghi được", { description: error.message }),
  });
  const withdraw = useMutation({
    mutationFn: (item: { section: string; requestedAt: number }) =>
      api(`/api/books/${book.id}/pending-changes/withdraw`, {
        method: "POST",
        body: { section: item.section, key: ref.stableId, keys: [ref.stableId], requestedAt: item.requestedAt },
      }),
    onSuccess: done,
    onError: (error: Error) => toast.error("Không bỏ được thay đổi này", { description: error.message }),
  });

  const items = waitingItems(wish);
  const title = view === "speaker" ? (line?.kind === "thought" ? "Ai nghĩ câu này?" : "Ai nói câu này?") : view === "delivery" ? "Cách đọc câu này" : view === "word" ? "Cách đọc một tên" : "Sửa câu này";
  return (
    <Dialog open={segment !== undefined} onOpenChange={(open) => !open && close()} width="max-w-md" title={title}>
      {line && (
        <div className="max-h-[68dvh] space-y-3 overflow-y-auto overscroll-contain pr-0.5">
          <LineQuote line={line} />
          {!identified && (
            <p className="rounded-lg bg-hover px-3 py-2 text-sm text-fg-2">
              Câu này chưa có mã trong file sách (sách đóng gói bằng bản cũ của ABook) nên chưa ghi được yêu cầu cho riêng câu. Cách đọc một tên vẫn ghi được.
            </p>
          )}
          {view === "menu" && (
            <>
              {items.length > 0 && (
                <div className="rounded-xl bg-info-soft px-3 py-2 text-sm" role="status">
                  <p className="flex items-center gap-1.5 font-medium">
                    <Clock className="size-4 shrink-0 text-info" /> Đang chờ máy làm sách
                  </p>
                  <ul className="mt-1 space-y-1">
                    {items.map((item) => (
                      <li key={item.key} className="flex items-center gap-2 text-fg-2">
                        <span className="min-w-0 flex-1 text-pretty">{item.text}</span>
                        <button
                          type="button"
                          disabled={withdraw.isPending}
                          onClick={() => withdraw.mutate(item)}
                          aria-label={`Bỏ: ${item.text}`}
                          className="inline-flex shrink-0 items-center gap-1 rounded-md px-1.5 py-0.5 text-xs font-medium text-accent-text hover:bg-hover"
                        >
                          <X className="size-3" /> Bỏ
                        </button>
                      </li>
                    ))}
                  </ul>
                  <p className="mt-1.5 text-xs text-fg-2">{WAITING_STUDIO}</p>
                </div>
              )}
              <div>
                <MenuRow
                  icon={UserRound}
                  title={line.kind === "thought" ? "Ai nghĩ câu này" : "Ai nói câu này"}
                  note={
                    !identified
                      ? "chưa có mã câu trong file sách"
                      : !speech
                        ? "Lời kể không có người nói - muốn gán người, đổi câu thành lời thoại ở “Cách đọc câu”"
                        : wish?.speaker
                          ? `Đang chờ máy làm sách: ${wish.speaker.shown}`
                          : `Hiện là ${line.label}`
                  }
                  disabled={!identified || !speech}
                  onClick={() => setView("speaker")}
                />
                <MenuRow
                  icon={MessageSquareQuote}
                  title="Cách đọc câu"
                  note="Loại câu, cảm xúc, chữ đem đọc"
                  disabled={!identified}
                  onClick={() => setView("delivery")}
                />
                <MenuRow icon={Type} title="Cách đọc một tên trong câu" note="Chọn từ máy đọc sai, gõ cách đọc đúng" onClick={() => setView("word")} />
                <MenuRow
                  icon={RefreshCw}
                  title="Thu lại câu này"
                  note={!identified ? "chưa có mã câu trong file sách" : !hasAudio ? "Chương này chưa có audio - chưa có gì để thu lại" : wish?.retake ? "Đã ghi - đang chờ máy làm sách" : "Đọc lại một lần khác, giọng như cũ"}
                  disabled={!identified || !hasAudio || Boolean(wish?.retake) || retake.isPending}
                  onClick={() => retake.mutate()}
                  trailing={null}
                />
              </div>
            </>
          )}
          {view === "speaker" && (
            <>
              <SpeakerMenu line={line} script={chapterScript} onPick={(person) => speaker.mutate(person)} phone />
              <Button size="sm" variant="ghost" icon={ChevronLeft} onClick={() => setView("menu")}>
                Quay lại
              </Button>
            </>
          )}
          {view === "delivery" && (
            <>
              <DeliveryMenu bookId={book.id} line={line} script={chapterScript} onSave={(change) => delivery.mutate(change)} wide noWorkshop />
              <Button size="sm" variant="ghost" icon={ChevronLeft} onClick={() => setView("menu")}>
                Quay lại
              </Button>
            </>
          )}
          {view === "word" && <WordView bookId={book.id} text={line.text} names={wishes?.pronunciations ?? []} need={need} onBack={() => setView("menu")} />}
        </div>
      )}
    </Dialog>
  );
}
