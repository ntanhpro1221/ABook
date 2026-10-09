import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AudioLines, Check, Pause, Play, RotateCcw, Search, UserPlus } from "lucide-react";
import { createContext, useContext, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { useClip } from "@/listen/clip";
import { cn } from "@/shared/cn";
import { formatNumber } from "@/shared/format";
import { Button, Dialog, EmptyState, Kbd, Segmented } from "@/shared/ui";
import { api, suggestionOf, urls, type BookSummary } from "./api";
import { ReadingProblem } from "./ReadingProblem";
import { useTryReading } from "./TryReading";
import { applyWhen, PENDING_NOTE, refreshAfterDecision, UNDO_MS, undoAction, useWhenApplied } from "./decisions";
import { keepRequests, pickedLines, pickNote, toggleLine, type LineRef, type SpeakerRequest } from "./minorGroups";
import { decidedTitle, inboxLead, midSentence, rerecordSentence, sentence } from "./workText";

// "Việc cần duyệt" (docs/STUDIO_REVIEW.md, webui/work_items.py): chỗ máy nghi ngờ, xếp theo lợi trên mỗi lần bấm. Máy đã tự
// quyết và dây chuyền KHÔNG chờ ai - đây là nơi người sửa ít nhất mà được nhiều nhất. Cách đọc tên sửa được ngay trên thẻ
// (bước 2): mong muốn ghi vào overrides.json, dây chuyền áp ở ranh giới chương và thu lại những câu có tên ấy.

export type WorkKind = "speaker" | "turn" | "gender" | "vocative" | "alias" | "bracket" | "shared-voice" | "pronunciation" | "unnamed" | "audio" | "narrator";

interface WorkExample {
  segmentId: number;
  chapterId: number;
  chapterTitle: string;
  seq: number;
  text: string;
  speaker: string;
  /** Câu đã có bản thu (nghe được); câu chưa thu chỉ là ví dụ ngữ cảnh. */
  hasAudio: boolean;
  /** Câu mà lựa chọn trên thẻ sẽ đổi người nói (thẻ lượt đối đáp: các câu xen kẽ). */
  changes?: boolean;
  /** Thẻ vai phụ cả cuốn: mã câu, để bỏ chọn từng câu. */
  stableId?: string;
  /** Thẻ “Ai nói câu này”: câu liền trước và liền sau (mọi người nói) làm ngữ cảnh để quyết ai nói. */
  before?: string;
  after?: string;
}

export interface WorkItem {
  kind: WorkKind;
  key: string;
  title: string;
  problem: string;
  affected: number;
  doubt: number;
  score: number;
  options: string[];
  current: string;
  examples: WorkExample[];
  /** Việc cách đọc tên: chữ gốc trong sách, và cách đọc người nghe đã ghi mà dây chuyền chưa áp (nếu có). */
  surface?: string;
  requested?: string | null;
  /** Đã quyết mà chỉ áp khi làm lại sách (thẻ người kể của đoạn đã phân tích xong): không tính vào "chờ áp dụng", xếp cuối. */
  redoOnly?: boolean;
  /** Việc gán người nói ("Ai nói câu này", người gọi, vai phụ không tên): các câu (mã ổn định + băm chữ, để yêu cầu
   *  không áp nhầm câu đã đổi) và các lựa chọn bấm được. */
  lines?: { stableId: string; textSha256: string }[];
  /** Thẻ chuỗi lượt đối đáp: mọi câu của chuỗi - phạm vi "Cả chuỗi" thay cho các câu xen kẽ trong `lines`. Thẻ 『』: mọi
   *  câu 『』 của dự án - phạm vi "Cả cuốn", và quy ước đi theo các phần sau. */
  allLines?: { stableId: string; textSha256: string }[];
  /** Nhãn hai phạm vi khi khác "Câu xen kẽ / Cả chuỗi" (thẻ 『』: "Chương này / Cả cuốn"). */
  scopeLabels?: [string, string];
  /** `name`: tên người khi nhãn nút không phải là tên ("Gộp vào Kati"). */
  choices?: { label: string; value: string; name?: string }[];
  currentValue?: string;
  /** Nhãn nút giữ nguyên khi "Giữ <người đang nói>" không đúng nghĩa (bí danh: "Hai người khác nhau"). */
  keepLabel?: string;
  /** `false`: máy không đề xuất ai (thẻ theo độ tin logprob chỉ nói máy chưa chắc) - chip đầu không tô như gợi ý của máy. */
  suggested?: boolean;
  /** Thẻ bí danh: tên được hỏi, để hiển thị ("“Thiên Biến Vạn Hóa” là Krai") - `current` là nhãn lựa chọn, không phải tên. */
  subject?: string;
  /** Việc giọng/giới của nhân vật ("Nam hay nữ", "Chung giọng"): mỗi lựa chọn là một yêu cầu POST /voice; giữ nguyên thì
   *  ghi yêu cầu rỗng cho từng người trong `keepCharacters` (thẻ thôi hỏi). */
  voiceChoices?: VoiceChoice[];
  keepCharacters?: string[];
  /** Chương của các câu thẻ sẽ đổi (hay của câu ví dụ) - "Duyệt trước khi thu" hỏi trước thẻ ở chương sắp thu. */
  chapters?: number[];
  /** Thẻ vai phụ không tên cả cuốn: `examples` là mọi câu của nhóm, người nghe bỏ chọn câu không phải trước khi chọn người. */
  pick?: boolean;
  /** Giữ nguyên thẻ nhóm: mỗi vai giữ người của nó - một yêu cầu cho mỗi vai. */
  keepGroups?: SpeakerRequest[];
  /** Thẻ vai phụ cả cuốn: tên đề nghị cho "là một người mới tên “…”" (cả nhóm thành MỘT người có giọng riêng). */
  newPerson?: string;
  /** Thẻ đã quyết: cách rút đúng lần bấm ấy (`POST /{endpoint}` với `withdraw`) - nút "Hoàn tác" của mục "Đã quyết". */
  undo?: { endpoint: string; decisions: Record<string, unknown>[] };
  /** Thẻ người kể của đoạn (webui/narrator_cards.py): đoạn nào, người kể của sách, ứng viên, và điều cần biết trước khi bấm
   *  (đoạn đã phân tích xong thì chỉ áp khi làm lại sách). */
  narratorSection?: {
    chapterIndex: number;
    fromSeq: number;
    toSeq: number;
    narrator: string;
    appliesNote: string;
    choices: { label: string; value: string }[];
  };
}

interface VoiceChoice {
  label: string;
  character: string;
  gender?: string;
  preset?: string;
  avoid?: string;
  /** Cái giá của lựa chọn: "giữ giọng đang đọc", "đổi giọng, thu lại 12 câu". */
  note?: string;
  /** Câu báo khi đã ghi: "Noah là nữ", "đổi giọng Rhine". */
  done?: string;
  /** Máy khuyên lựa chọn này (tách hai người chung giọng: đổi người ít câu hơn). Thẻ giới không khuyên gì. */
  recommended?: boolean;
}

export interface WorkView {
  items: WorkItem[];
  counts: Partial<Record<WorkKind, number>>;
}

const KIND_LABEL: Record<WorkKind, string> = {
  speaker: "Ai nói câu này",
  turn: "Lượt đối đáp",
  pronunciation: "Cách đọc tên",
  gender: "Nam hay nữ",
  vocative: "Người gọi hay người nói",
  alias: "Một người hai tên",
  bracket: "Lời trong 『』",
  "shared-voice": "Chung giọng",
  unnamed: "Vai phụ không tên",
  audio: "Bản thu lỗi",
  narrator: "Người kể của đoạn",
};

const PAGE = 40;

export function useWork(bookId: string) {
  return useQuery({
    queryKey: ["work", bookId],
    queryFn: () => api<WorkView>(`/api/books/${bookId}/work`),
    enabled: Boolean(bookId),
    staleTime: 60_000,
  });
}

export function useWorkCount(bookId: string) {
  const { data } = useWork(bookId);
  // Việc đã quyết (đang chờ áp dụng) không còn là việc cần làm - soát UX 29-09: số không giảm sau khi quyết.
  return data?.items.filter((item) => !item.requested).length ?? 0;
}

/** Việc đã quyết chờ gì: sách đang dở thì tự áp khi chạy tiếp; sách ĐÃ XONG không tự chạy lại - phải bấm "Áp dụng thay
 *  đổi" (soát UX 29-09: thẻ từng nói "chờ … chạy tiếp" cả ở sách đã xong). */
const PendingHint = createContext("chờ áp dụng khi sách chạy tiếp");

function Example({ bookId, example, picked, onPick }: { bookId: string; example: WorkExample; picked?: boolean; onPick?: () => void }) {
  const clip = useClip();
  const id = `work-${example.segmentId}`;
  const playing = clip.current === id;
  return (
    <li className={cn("flex items-start gap-2 text-sm", onPick && !picked && "opacity-60")}>
      {onPick && (
        <input
          type="checkbox"
          checked={picked}
          onChange={onPick}
          aria-label={`Gồm câu này: ${example.text}`}
          className="mt-1.5 size-4 shrink-0 accent-[var(--accent)]"
        />
      )}
      {example.hasAudio ? (
        <button
          type="button"
          onClick={() => clip.toggle(id, urls.sample(bookId, example.segmentId))}
          aria-label={playing ? "Dừng" : `Nghe câu: ${example.text}`}
          className="mt-0.5 grid size-7 shrink-0 place-items-center rounded-full bg-hover text-fg-2 hover:text-fg"
        >
          {playing ? <Pause className="size-3.5" fill="currentColor" strokeWidth={0} /> : <Play className="size-3.5 translate-x-[1px]" fill="currentColor" strokeWidth={0} />}
        </button>
      ) : (
        <span className="mt-0.5 size-7 shrink-0" aria-hidden />
      )}
      <div className="min-w-0">
        {example.before && <p className="line-clamp-2 text-fg-3" aria-label="Câu liền trước">{example.before}</p>}
        {/* Nhãn đứng NGAY TRÊN câu được hỏi (không phải trên câu trước mờ - dễ đọc nhầm là nhãn của câu ấy); vạch bên trái đánh dấu đúng câu đang hỏi
            khi có câu trước/sau làm ngữ cảnh. */}
        <div className={cn((example.before || example.after) && "border-l-2 border-accent pl-2")}>
          <div className="text-xs text-fg-3">
            {example.chapterTitle} · {example.seq === 0 ? "tiêu đề chương" : `câu ${example.seq}`}
            {example.speaker && ` · máy gán: ${example.speaker}`}
            {example.changes && <span className="font-semibold text-accent-text"> · sẽ đổi</span>}
            {!example.hasAudio && " · chưa thu"}
          </div>
          <p className="text-fg">{example.text}</p>
        </div>
        {example.after && <p className="line-clamp-2 text-fg-3" aria-label="Câu liền sau">{example.after}</p>}
      </div>
    </li>
  );
}

// Sửa cách đọc một tên ngay trên thẻ. Không chờ gì: ghi xong là xong phần người; dây chuyền áp ở ranh giới chương kế
// tiếp (hoặc lần chạy tới) và thu lại đúng những câu có tên ấy - kể cả sách đã xong.
function PronunciationFix({ bookId, item, onOpenNames }: { bookId: string; item: WorkItem; onOpenNames?: (name: string) => void }) {
  const client = useQueryClient();
  const pending = useContext(PendingHint);
  const when = useWhenApplied(bookId);
  const [value, setValue] = useState(item.requested ?? item.current);
  // Lỗi nằm ngay dưới ô nhập, không chỉ trong toast 4 giây (soát UX 29-09: "Hên-kơ" bị từ chối mà không biết sửa chỗ nào).
  const [problem, setProblem] = useState("");
  const [suggestion, setSuggestion] = useState("");
  const save = useMutation({
    mutationFn: (spokenForm: string) =>
      api<{ surface: string; spokenForm: string; requestedAt: number }>(`/api/books/${bookId}/pronunciation`, {
        method: "POST",
        body: { surface: item.surface, spokenForm },
      }),
    onSuccess: ({ spokenForm, requestedAt }) => {
      refreshAfterDecision(client, bookId);
      const keep = spokenForm === item.current;
      // `previous`: cách máy đọc lúc bấm - máy chủ xin lại cách ấy nếu cách mới đã vào sách.
      const action = undoAction(
        client,
        bookId,
        "pronunciation",
        [{ surface: item.surface, requestedAt, previous: item.current, keep }],
        item.requested
          ? `Trở lại quyết định trước: “${item.surface}” đọc là “${item.requested}”.`
          : `“${item.surface}” lại đọc là “${item.current}”.`,
      );
      // Giữ đúng cách máy đang đọc thì không có gì để thu lại - soát UX 29-09: báo "sẽ thu lại" làm người nghe hoảng.
      if (keep) {
        toast.success(`Giữ cách đọc “${spokenForm}”`, { description: "Không phải thu lại câu nào.", action, duration: UNDO_MS });
        return;
      }
      toast.success(`Đã ghi: “${item.surface}” đọc là “${spokenForm}”`, {
        description: `Các câu có tên này sẽ được thu lại. ${when}`,
        action,
        duration: UNDO_MS,
      });
    },
    // Lỗi chỉ nằm dưới ô nhập - thêm toast là báo một lỗi hai lần (soát UX 29-09).
    onError: (error: Error) => {
      setProblem(error.message);
      setSuggestion(suggestionOf(error));
    },
  });
  const typed = value.trim();
  const inputId = `spoken-${item.key}`;
  const use = (spoken: string) => {
    setValue(spoken);
    setProblem("");
    setSuggestion("");
    save.mutate(spoken);
  };
  // "Nghe thử" cách đang gõ trước khi lưu: máy chê cách đọc thì hiện đúng chỗ lỗi của "Đọc thế này".
  const tryIt = useTryReading({
    bookId,
    surface: item.surface ?? "",
    spoken: typed,
    disabled: Boolean(problem),
    onRejected: (message, suggestionText) => {
      setProblem(message);
      setSuggestion(suggestionText);
    },
  });
  return (
    <div className="mt-3">
      {item.requested && (
        <p className="mb-2 flex items-center gap-1.5 text-xs text-fg-2">
          <Check className="size-3.5 text-success" />
          {/* "Giữ" cách máy đang đọc không đổi gì trong sách - không bảo bấm "Áp dụng thay đổi" (soát UX 29-09). */}
          {item.requested === item.current ? `Giữ “${item.requested}” - không cần áp dụng.` : `Đã ghi “${item.requested}” - ${pending}.`}
        </p>
      )}
      <form
        className="flex flex-wrap items-center gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          if (typed) save.mutate(typed);
        }}
      >
        <Button data-choice size="sm" variant="secondary" disabled={save.isPending} onClick={() => save.mutate(item.current)}>
          Đúng rồi, giữ “{item.current}”
        </Button>
        <label htmlFor={inputId} className="text-xs text-fg-2">
          hoặc đọc là
        </label>
        <input
          id={inputId}
          aria-label={`Cách đọc mới cho ${item.surface}`}
          placeholder={`vd ${item.current}`}
          value={value}
          onChange={(event) => {
            setValue(event.target.value);
            setProblem("");
            setSuggestion("");
          }}
          spellCheck={false}
          autoComplete="off"
          aria-invalid={problem ? true : undefined}
          aria-describedby={problem ? `${inputId}-problem` : undefined}
          className={cn(
            "h-8 w-40 rounded-lg border bg-panel px-2.5 text-sm text-fg outline-none focus-visible:border-accent",
            problem ? "border-danger" : "border-line",
          )}
        />
        {tryIt.button}
        <Button
          size="sm"
          variant="primary"
          type="submit"
          loading={save.isPending}
          disabled={!typed || typed === item.current || typed === item.requested}
        >
          Đọc thế này
        </Button>
        {/* Thẻ chỉ hỏi tên máy kém chắc; mọi tên khác (kể cả tên đã chọn) sửa ở tab Nhân vật, mục "Cách đọc tên". */}
        {onOpenNames && (
          <Button size="sm" variant="ghost" type="button" onClick={() => onOpenNames(item.surface ?? "")}>
            Mọi cách đọc tên…
          </Button>
        )}
      </form>
      {tryIt.note && <div className="mt-1.5">{tryIt.note}</div>}
      <ReadingProblem id={`${inputId}-problem`} problem={problem} suggestion={suggestion} onUse={use} />
    </div>
  );
}

// Gán người nói - một câu ("Ai nói câu này", người gọi) hay mọi câu của một vai phụ: mỗi ứng viên một nút, người máy nghi
// nhất đứng đầu. Không chờ gì - ghi xong là xong phần người; dây chuyền gán câu cho người ấy (mượn đúng giọng sẵn có của
// họ) ở ranh giới chương, câu đã thu thì thu lại.
type Scope = "alternate" | "all";

function SpeakerFix({
  bookId,
  item,
  onOpenScript,
  scope = "alternate",
  onScope,
  picked,
}: {
  bookId: string;
  item: WorkItem;
  onOpenScript?: OpenScript;
  scope?: Scope;
  onScope?: (scope: Scope) => void;
  /** Thẻ vai phụ cả cuốn: những câu người nghe còn chọn. */
  picked?: LineRef[];
}) {
  const client = useQueryClient();
  const lines = picked ?? (scope === "all" && item.allLines ? item.allLines : item.lines);
  const pending = useContext(PendingHint);
  const when = useWhenApplied(bookId);
  // "Người khác…": người nói chưa có trong lựa chọn - kể cả người máy CHƯA TỪNG gán câu nào (linh thể nói trong 『』):
  // gõ tên + chọn giới, dây chuyền tạo người ấy và cấp giọng riêng như bước phân vai.
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const save = useMutation({
    mutationFn: ({ speaker, newGender }: { speaker: string; newGender?: string }) =>
      api<{ lines: number; speaker: string; alias?: boolean; requestedAt: number }>(`/api/books/${bookId}/speaker`, {
        method: "POST",
        body: {
          lines,
          speaker,
          newGender: newGender ?? "",
          // "Một người hai tên": gộp là quyết cả ở cấp tên - phần sau của cuốn ("Làm tiếp cuốn này") tự hiểu.
          ...(item.kind === "alias" && speaker !== item.currentValue ? { alias: item.currentValue } : {}),
          // Thẻ 『』 phạm vi "Cả cuốn": quy ước của cả cuốn, các phần sau tự áp.
          ...(item.kind === "bracket" && scope === "all" ? { bracketRule: true } : {}),
        },
      }),
    onSuccess: ({ speaker, alias, requestedAt }) => {
      refreshAfterDecision(client, bookId);
      const which = (lines?.length ?? 1) > 1 ? `${lines?.length} câu này` : "câu này";
      const keep = speaker === item.currentValue;
      // Gộp tên / quy ước 『』 cả cuốn còn ghi ở cấp TÊN cho các phần sau - hoàn tác chỉ lùi được phần câu, nên không mời.
      const back = item.requested
        ? `Trở lại quyết định trước: ${which} của ${midSentence(item.requested)}.`
        : item.pick
          ? `${sentence(which)} trở lại chờ duyệt.`
          : `${sentence(which)} lại là của ${midSentence(item.current)}.`;
      const undo = alias ? {} : { action: undoAction(client, bookId, "speaker", [{ lines, requestedAt, keep }], back), duration: UNDO_MS };
      if (keep) {
        toast.success(item.keepLabel ? `Đã ghi: ${item.keepLabel}` : `Giữ nguyên: ${which} của ${midSentence(item.current)}`, {
          description: "Việc này sẽ không hiện lại.",
          ...undo,
        });
        return;
      }
      const choice = item.choices?.find((option) => option.value === speaker);
      const label = choice?.name ?? choice?.label ?? speaker;
      toast.success(`Đã ghi: ${which} của ${midSentence(label)}`, {
        description:
          `Câu đã thu sẽ được thu lại bằng giọng của người ấy. ${when}` +
          (alias && item.kind === "bracket"
            ? " Lời trong 『』 ở các chương và các phần sau của cuốn cũng tự về người này."
            : alias
              ? ` Các phần sau của cuốn cũng tự hiểu “${item.subject ?? item.current}” là ${label}.`
              : ""),
        ...undo,
      });
    },
    onError: (error: Error) => toast.error("Chưa ghi được người nói", { description: error.message }),
  });
  // Thẻ nhóm giữ nguyên: mỗi vai giữ người của nó - vài yêu cầu, một nút hoàn tác cho cả nhóm.
  const keepAll = useMutation({
    mutationFn: async (requests: SpeakerRequest[]) => {
      const made: Record<string, unknown>[] = [];
      for (const request of requests) {
        const { requestedAt } = await api<{ requestedAt: number }>(`/api/books/${bookId}/speaker`, { method: "POST", body: request });
        made.push({ lines: request.lines, requestedAt, keep: true });
      }
      return made;
    },
    onSuccess: (made) => {
      refreshAfterDecision(client, bookId);
      toast.success(`Đã ghi: ${item.keepLabel ?? "Giữ nguyên"}`, {
        description: "Không câu nào phải thu lại; việc này sẽ không hiện lại.",
        action: undoAction(client, bookId, "speaker", made, "Thẻ hỏi lại như trước khi bấm."),
        duration: UNDO_MS,
      });
    },
    onError: (error: Error) => {
      refreshAfterDecision(client, bookId);
      toast.error("Chưa ghi được", { description: error.message });
    },
  });
  const busy = save.isPending || keepAll.isPending;
  const none = !lines?.length;
  // Quá nhiều chip (thẻ 『』 có thể 12 người): chừa MAX_CHIPS đầu (và lựa chọn đã ghi), phần còn lại nằm trong “Người khác…”.
  const everyChoice = item.choices ?? [];
  const isAnswer = (choice: { label: string; name?: string }) => Boolean(item.requested) && [choice.name, choice.label].includes(item.requested!);
  const shownChoices = everyChoice.filter((choice, index) => index < MAX_CHIPS || isAnswer(choice) || GENERIC_PEOPLE.has(choice.label));
  const moreChoices = everyChoice.filter((choice) => !shownChoices.includes(choice));
  // Gợi ý tên bằng chính tên trong sách, không phải tên truyện nào đó (soát UX a13 #6).
  const sample = everyChoice.map((choice) => choice.name ?? choice.label).find((text) => text && !GENERIC_PEOPLE.has(text) && !/^(Tất cả là|Giữ) /.test(text));
  return (
    <div className="mt-3">
      {item.requested && (
        <p className="mb-2 flex items-center gap-1.5 text-xs text-fg-2">
          <Check className="size-3.5 text-success" />
          {/* Gộp tên là ở cấp TÊN cho cả cuốn và các phần sau, không phải "câu này của X" (soát UX 29-09). */}
          {item.kind === "alias"
            ? `Đã ghi: “${item.subject ?? item.current}” là ${midSentence(item.requested)} - cả cuốn và các phần sau.`
            : `Đã ghi: ${(item.lines?.length ?? 1) > 1 ? `${item.lines?.length} câu này` : "câu này"} của ${midSentence(item.requested)} - ${pending}.`}
        </p>
      )}
      {item.allLines && item.lines && onScope && (
        <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-fg-2">
          <span>Đổi người nói cho</span>
          <Segmented<Scope>
            label="Đổi người nói cho những câu nào"
            value={scope}
            onChange={onScope}
            options={[
              { value: "alternate", label: `${item.scopeLabels?.[0] ?? "Câu xen kẽ"} · ${item.lines.length}` },
              { value: "all", label: `${item.scopeLabels?.[1] ?? "Cả chuỗi"} · ${item.allLines.length}` },
            ]}
          />
        </div>
      )}
      {item.allLines && item.lines && onScope && (
        <p className="mb-2 text-xs text-fg-3">
          {item.scopeLabels
            ? `${item.scopeLabels[0]}: chỉ những câu 『』 của chương này. ${item.scopeLabels[1]}: mọi câu 『』 của sách, và các phần làm sau cũng theo.`
            : "Câu xen kẽ: chỉ những câu đánh dấu “sẽ đổi”. Cả chuỗi: mọi câu của chuỗi này - khi cả chuỗi là lời của một người."}
        </p>
      )}
      <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="Ai nói câu này">
        {shownChoices.map((choice, index) => (
          <Button data-choice
            key={choice.value}
            size="sm"
            // Đã quyết thì tô lựa chọn của người nghe, không phải gợi ý đầu của máy.
            variant={(item.requested ? [choice.name, choice.label].includes(item.requested) : index === 0 && item.kind !== "unnamed" && item.suggested !== false)
              ? "primary" : "secondary"}
            aria-pressed={item.requested ? [choice.name, choice.label].includes(item.requested) : undefined}
            disabled={busy || none}
            onClick={() => save.mutate({ speaker: choice.value })}
          >
            {choice.label}
          </Button>
        ))}
        {item.currentValue && (
          <Button data-choice size="sm" variant="ghost" disabled={busy} onClick={() => save.mutate({ speaker: item.currentValue! })}>
            {item.keepLabel ?? (item.kind === "unnamed" ? "Đúng là vai phụ" : `Giữ ${item.current}`)}
          </Button>
        )}
        {/* Vai phụ ngôi ba (lính gác) không phải ai trong danh sách - cả nhóm có thể là MỘT người mới, có giọng riêng. */}
        {item.newPerson && (
          <Button data-choice size="sm" variant="secondary" disabled={busy || none} onClick={() => save.mutate({ speaker: item.newPerson!, newGender: "unknown" })}>
            Là một người mới tên “{item.newPerson}”
          </Button>
        )}
        {item.keepGroups && item.keepGroups.length > 0 && (
          <Button data-choice size="sm" variant="ghost" disabled={busy} onClick={() => keepAll.mutate(keepRequests(item))}>
            {item.keepLabel ?? "Giữ nguyên"}
          </Button>
        )}
        {/* Thẻ "một người hai tên" hỏi hai tên có phải một người - chọn người thứ ba lạc chủ đề (soát UX 29-09). */}
        {item.kind !== "alias" && (
          <Button size="sm" variant="ghost" icon={UserPlus} aria-expanded={creating} onClick={() => setCreating((value) => !value)}>
            Người khác…
          </Button>
        )}
        {/* Thẻ chỉ gợi vài người; tab Kịch bản tìm được mọi nhân vật trong sách - mở đúng câu này ở đó (soát UX 29-09). */}
        {onOpenScript && item.lines?.length === 1 && item.examples?.[0] && (
          <Button size="sm" variant="ghost" icon={Search} onClick={() => onOpenScript(item.examples![0].chapterId, item.lines![0].stableId)}>
            Chọn người khác trong truyện…
          </Button>
        )}
        {/* Thẻ nhóm chỉ in vài câu làm ví dụ ("Hai người chung một tên" có thể 16 câu): đọc đủ ngữ cảnh ở tab Kịch bản trước khi
            quyết, mở đúng chương, tại câu đầu của nhóm. */}
        {onOpenScript && (item.lines?.length ?? 0) > (item.examples?.length ?? 0) && item.examples?.[0] && (
          <Button size="sm" variant="ghost" icon={Search} onClick={() => onOpenScript(item.examples![0].chapterId, item.lines![0].stableId, false)}>
            Đọc cả {item.lines!.length} câu trong Kịch bản
          </Button>
        )}
      </div>
      {creating && (
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          {moreChoices.length > 0 && (
            <div className="flex w-full flex-wrap items-center gap-1.5" role="group" aria-label="Những người khác trong sách">
              {moreChoices.map((choice) => (
                <Button key={choice.value} size="sm" variant="secondary" disabled={busy || none} onClick={() => save.mutate({ speaker: choice.value })}>
                  {choice.label}
                </Button>
              ))}
              <span className="text-xs text-fg-3">hay đặt tên một người mới:</span>
            </div>
          )}
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder={sample ? `Tên người nói (vd ${sample})` : "Tên người nói"}
            aria-label="Tên người nói mới"
            maxLength={80}
            className="h-8 min-w-0 flex-1 rounded-lg border border-line bg-panel px-2.5 text-sm outline-none focus-visible:border-accent"
          />
          <span className="text-xs text-fg-2">Giới (bấm để lưu):</span>
          {(
            [
              ["male", "Nam"],
              ["female", "Nữ"],
              ["unknown", "Không rõ"],
            ] as const
          ).map(([gender, label]) => (
            <Button
              key={gender}
              size="sm"
              variant="secondary"
              disabled={!name.trim() || busy || none}
              aria-label={`Lưu người nói mới, giới: ${label.toLowerCase()}`}
              onClick={() => save.mutate({ speaker: name.trim(), newGender: gender })}
            >
              {label}
            </Button>
          ))}
        </div>
      )}
    </div>
  );
}

// Người kể của một ĐOẠN khác người kể "tôi" của sách: ba lựa chọn - đúng (đoạn không do người ấy kể), không (giữ nguyên), hay chọn
// người khác. Lô phân tích chưa chạy sẽ theo lựa chọn; đoạn đã phân tích xong thì chỉ áp khi làm lại sách (thẻ nói rõ).
function NarratorFix({ bookId, item }: { bookId: string; item: WorkItem }) {
  const client = useQueryClient();
  const section = item.narratorSection!;
  const [choosing, setChoosing] = useState(false);
  const [name, setName] = useState("");
  const where = { chapterIndex: section.chapterIndex, fromSeq: section.fromSeq, toSeq: section.toSeq };
  const save = useMutation({
    mutationFn: (body: { action: "accept" | "choose" | "keep"; narrator?: string }) =>
      api<{ action: string; narrator: string }>(`/api/books/${bookId}/narrator-section`, { method: "POST", body: { ...where, ...body } }),
    onSuccess: ({ action, narrator }) => {
      refreshAfterDecision(client, bookId);
      const back = item.requested ? `Trở lại quyết định trước: ${item.requested}.` : "Thẻ hỏi lại như trước khi bấm.";
      toast.success(
        action === "keep" ? `Giữ nguyên: đoạn này vẫn do ${item.current} kể` : narrator ? `Đã ghi: đoạn này do ${narrator} kể` : `Đã ghi: đoạn này không phải ${item.current} kể`,
        {
          description: section.appliesNote || "Phần chưa phân tích sẽ theo lựa chọn này.",
          action: undoAction(client, bookId, "narrator-section", [where], back),
          duration: UNDO_MS,
        },
      );
    },
    onError: (error: Error) => toast.error("Chưa ghi được người kể", { description: error.message }),
  });
  const typed = name.trim();
  return (
    <div className="mt-3">
      {section.appliesNote && !(item.requested && item.redoOnly) && <p className="mb-2 text-xs text-fg-2">{section.appliesNote}</p>}
      {item.requested && (
        <p className="mb-2 flex items-center gap-1.5 text-xs text-fg-2">
          <Check className="size-3.5 text-success" />
          {item.redoOnly ? "Đã ghi - áp khi làm lại sách." : `Đã ghi: ${item.requested}.`}
        </p>
      )}
      <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="Người kể của đoạn">
        <Button data-choice size="sm" variant={item.requested === "Đổi người kể" ? "primary" : "secondary"} disabled={save.isPending} onClick={() => save.mutate({ action: "accept" })}>
          Không phải {item.current} kể - đoạn kể ngôi thứ ba
        </Button>
        <Button data-choice size="sm" variant={item.requested === "Giữ nguyên" ? "primary" : "ghost"} disabled={save.isPending} onClick={() => save.mutate({ action: "keep" })}>
          Giữ {item.current} là người kể
        </Button>
        <Button size="sm" variant="ghost" icon={UserPlus} aria-expanded={choosing} onClick={() => setChoosing((value) => !value)}>
          Người kể là ai khác…
        </Button>
      </div>
      {choosing && (
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          {section.choices.map((choice) => (
            <Button key={choice.value} size="sm" variant="secondary" disabled={save.isPending} onClick={() => save.mutate({ action: "choose", narrator: choice.value })}>
              {choice.label}
            </Button>
          ))}
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Tên người kể"
            aria-label="Tên người kể của đoạn"
            maxLength={80}
            className="h-8 min-w-0 flex-1 rounded-lg border border-line bg-panel px-2.5 text-sm outline-none focus-visible:border-accent"
          />
          <Button size="sm" variant="primary" disabled={!typed || save.isPending} onClick={() => save.mutate({ action: "choose", narrator: typed })}>
            Đặt người kể
          </Button>
        </div>
      )}
    </div>
  );
}

// Giọng / giới của một nhân vật: một lần bấm. Dây chuyền chọn giọng mới như bước phân vai (mọi người khác giữ giọng) và
// chỉ thu lại khi giọng thật sự đổi - ghi chú dưới mỗi nút nói trước cái giá ấy.
function VoiceFix({ bookId, item }: { bookId: string; item: WorkItem }) {
  const client = useQueryClient();
  const pending = useContext(PendingHint);
  const when = useWhenApplied(bookId);
  const save = useMutation({
    mutationFn: async ({ requests }: { requests: Omit<VoiceChoice, "label" | "note" | "done" | "recommended">[]; label: string; keep: boolean; note?: string }) => {
      const made: { character: string; requestedAt: number }[] = [];
      for (const request of requests) {
        const { requestedAt } = await api<{ requestedAt: number }>(`/api/books/${bookId}/voice`, { method: "POST", body: request });
        made.push({ character: request.character, requestedAt });
      }
      return made;
    },
    onSuccess: (made, { label, keep, note }) => {
      refreshAfterDecision(client, bookId);
      // Nói cụ thể điều gì trở lại, như thẻ cách đọc và thẻ người nói (soát UX 30-09: "Thẻ hỏi lại như trước khi bấm").
      const heard = item.current === "Giọng nam" || item.current === "Giọng nữ" ? item.current.toLowerCase() : "giọng đang có";
      const back =
        item.kind === "gender" && item.subject
          ? item.requested
            ? `Trở lại quyết định trước: ${item.subject} là ${item.requested.toLowerCase()}.`
            : `${item.subject} lại để máy quyết - vẫn đọc bằng ${heard}.`
          : item.requested
            ? `Trở lại quyết định trước: ${item.requested}.`
            : item.kind === "shared-voice"
              ? "Hai người lại dùng chung giọng như trước."
              : "Thẻ hỏi lại như trước khi bấm.";
      const undo = { action: undoAction(client, bookId, "voice", made.map((decision) => ({ ...decision, keep })), back), duration: UNDO_MS };
      if (keep) {
        toast.success(`Đã ghi: ${label}`, { description: "Việc này sẽ không hiện lại.", ...undo });
        return;
      }
      // Lựa chọn nói trước cái giá ("giữ giọng đang đọc" / "đổi giọng, thu lại N câu") - thông báo nói đúng cái giá ấy, không
      // rào "nếu giọng phải đổi" khi giọng giữ nguyên (soát UX 29-09).
      toast.success(`Đã ghi: ${label}`, {
        description: note?.startsWith("giữ giọng")
          ? "Giọng đang đọc giữ nguyên - không phải thu lại câu nào."
          : `${rerecordSentence(note)} ${when}`,
        ...undo,
      });
    },
    onError: (error: Error) => toast.error("Chưa ghi được", { description: error.message }),
  });
  return (
    <div className="mt-3">
      {item.requested && (
        <p className="mb-2 flex items-center gap-1.5 text-xs text-fg-2">
          <Check className="size-3.5 text-success" />
          Đã ghi: {item.requested} - {pending}.
        </p>
      )}
      <div className="flex flex-wrap items-start gap-2" role="group" aria-label="Chọn">
        {(item.voiceChoices ?? []).map((choice) => (
          <div key={`${choice.character}-${choice.label}`} className="flex flex-col items-start gap-0.5">
            <Button data-choice
              size="sm"
              variant={(item.requested ? [choice.done, choice.label].includes(item.requested) : choice.recommended) ? "primary" : "secondary"}
              disabled={save.isPending}
              onClick={() =>
                save.mutate({
                  requests: [{ character: choice.character, gender: choice.gender, preset: choice.preset, avoid: choice.avoid }],
                  label: choice.done ?? choice.label,
                  keep: false,
                  note: choice.note,
                })
              }
            >
              {choice.label}
            </Button>
            {choice.note && <span className="px-0.5 text-[11px] text-fg-3">{choice.note}</span>}
          </div>
        ))}
        {item.keepCharacters && item.keepCharacters.length > 0 && (
          <Button data-choice
            size="sm"
            variant="ghost"
            disabled={save.isPending}
            onClick={() =>
              save.mutate({
                requests: item.keepCharacters!.map((character) => ({ character })),
                label: item.keepLabel ?? "Giữ nguyên",
                keep: true,
              })
            }
          >
            {item.keepLabel ?? "Giữ nguyên"}
          </Button>
        )}
      </div>
    </div>
  );
}

/** Mở câu `stableId` của chương `chapterId` trong tab Kịch bản, ô chọn người nói mở sẵn. */
/** `pick`: mở sẵn ô chọn người nói ở câu ấy (mặc định) - thẻ nhóm mở để ĐỌC thì không, ô ấy che chữ. */
/** `card`: thẻ đang mở lối nhảy - trang dự án ghi nó vào địa chỉ để Back trở lại đúng thẻ ấy. */
type OpenScript = (chapterId: number, stableId: string, pick?: boolean, card?: string) => void;
type OpenNames = (name: string, card?: string) => void;
type OpenReview = (card?: string) => void;

// "Hoàn tác" bền của một mục đã quyết: toast chỉ sống vài giây, mà người duyệt thường nhận ra bấm nhầm khi đã xem sang thẻ khác.
// Đi đúng đường hoàn tác của toast (decisions.undoAction): máy chủ bỏ yêu cầu của đúng lần bấm ấy, hay nói thật khi dây chuyền
// đã đưa nó vào sách.
function UndoDecision({ bookId, item }: { bookId: string; item: WorkItem }) {
  const client = useQueryClient();
  const [asked, setAsked] = useState(false);
  const undo = item.undo!;
  return (
    <Button
      size="sm"
      variant="ghost"
      icon={RotateCcw}
      className="ml-auto"
      disabled={asked}
      aria-label={`Hoàn tác: ${decidedTitle(item) ?? item.title}`}
      onClick={() => {
        setAsked(true);
        undoAction(client, bookId, undo.endpoint, undo.decisions, "Việc này trở lại chờ bạn duyệt.").onClick();
        // Không hoàn tác được (đã vào sách) thì thẻ còn đó - mở nút lại để thử khi đổi ý.
        window.setTimeout(() => setAsked(false), 2500);
      }}
    >
      Hoàn tác
    </Button>
  );
}

function Card({ bookId, item, onOpenReview, onOpenScript, onOpenNames, active = false }: { bookId: string; item: WorkItem; onOpenReview: OpenReview; onOpenScript?: OpenScript; onOpenNames?: OpenNames; active?: boolean }) {
  // Thẻ chuỗi lượt đối đáp: đổi các câu xen kẽ (mặc định) hay cả chuỗi - câu "sẽ đổi" theo phạm vi đang chọn.
  const [scope, setScope] = useState<Scope>("alternate");
  // Thẻ vai phụ cả cuốn: câu người nghe bỏ chọn (mã câu), và mở cả danh sách hay chỉ vài câu đầu.
  const [left, setLeft] = useState<ReadonlySet<string>>(new Set());
  const [all, setAll] = useState(false);
  // Gán một phần rồi thì thẻ còn đúng những câu đã bỏ chọn - chúng phải hiện là đang chọn, không phải vẫn bỏ.
  const groupLines = item.pick ? (item.lines ?? []).map((line) => line.stableId).join(" ") : "";
  useEffect(() => setLeft(new Set()), [groupLines]);
  const picked = item.pick && item.lines ? pickedLines(item.lines, left) : undefined;
  const shownExamples = item.pick && !all ? item.examples.slice(0, PICK_PREVIEW) : item.examples;
  const openScript: OpenScript | undefined =
    onOpenScript && ((chapterId, stableId, pick) => onOpenScript(chapterId, stableId, pick, item.key));
  const openNames: OpenNames | undefined = onOpenNames && ((name) => onOpenNames(name, item.key));
  return (
    <li id={`work-${item.key}`} className={cn("scroll-mt-24 rounded-xl border bg-panel p-4", active ? "border-accent ring-2 ring-accent/25" : "border-line")}>
      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
        <span className="rounded-full bg-hover px-2 py-0.5 text-[11px] font-medium text-fg-2">{KIND_LABEL[item.kind]}</span>
        <h3 className="text-[15px] font-semibold">{decidedTitle(item) ?? item.title}</h3>
        {item.requested && item.undo && <UndoDecision bookId={bookId} item={item} />}
      </div>
      <p className="mt-1.5 text-sm text-fg-2">{item.problem}</p>
      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-fg-2">
        <span>
          Ảnh hưởng <span className="tabular font-semibold text-fg">{formatNumber(item.allLines && scope === "all" ? item.allLines.length : item.affected)}</span> câu
        </span>
        <span>
          {item.kind === "audio" ? "Trạng thái" : item.kind === "narrator" ? "Máy coi người kể là" : "Máy đang dùng"}: <span className="font-medium text-fg">{item.current}</span>
        </span>
      </div>
      {item.kind === "audio" ? (
        <Button size="sm" variant="secondary" icon={AudioLines} className="mt-3" onClick={() => onOpenReview(item.key)}>
          Nghe ở tab Cần nghe lại
        </Button>
      ) : item.kind === "pronunciation" && item.surface ? (
        <PronunciationFix bookId={bookId} item={item} onOpenNames={openNames} />
      ) : item.kind === "narrator" && item.narratorSection ? (
        <NarratorFix bookId={bookId} item={item} />
      ) : item.voiceChoices && item.voiceChoices.length > 0 ? (
        <VoiceFix bookId={bookId} item={item} />
      ) : item.lines && item.choices ? (
        <SpeakerFix bookId={bookId} item={item} onOpenScript={openScript} scope={scope} onScope={setScope} picked={picked} />
      ) : (
        <div className="mt-3 flex flex-wrap gap-1.5" aria-label="Lựa chọn">
          {item.options.map((option) => (
            <span key={option} className="rounded-lg border border-line px-2.5 py-1 text-xs text-fg-2">
              {option}
            </span>
          ))}
        </div>
      )}
      {item.examples.length > 0 && (
        <ul className="mt-3 space-y-2 border-t border-line pt-3">
          {picked && item.lines && (
            <li className="text-xs text-fg-2">{pickNote(picked.length, item.lines.length)} - bỏ chọn câu không phải của người ấy.</li>
          )}
          {shownExamples.map((example) => (
            <Example
              key={example.segmentId}
              bookId={bookId}
              example={item.allLines && scope === "all" ? { ...example, changes: true } : example}
              {...(picked && example.stableId
                ? { picked: !left.has(example.stableId), onPick: () => setLeft(toggleLine(left, example.stableId!)) }
                : {})}
            />
          ))}
        </ul>
      )}
      {item.pick && item.examples.length > PICK_PREVIEW && (
        <Button size="sm" variant="ghost" className="mt-2" aria-expanded={all} onClick={() => setAll((value) => !value)}>
          {all ? "Thu gọn" : `Xem cả ${item.examples.length} câu`}
        </Button>
      )}
    </li>
  );
}

/** Nhiều hơn ngần này lựa chọn thì phần còn lại gom vào “Người khác…”. */
const MAX_CHIPS = 6;
const GENERIC_PEOPLE = new Set(["Người kể", "Người kể đọc tất cả", "Vai phụ không tên"]);

/** Thẻ vai phụ cả cuốn hiện ngần này câu đầu; "Xem cả N câu" mở hết để bỏ chọn. */
const PICK_PREVIEW = 3;

// "Giữ như máy đang làm" cho cả loại thẻ đang lọc (soát UX a6 01-10, D2): sau khi soát vài thẻ thấy máy đúng gần hết, người
// làm sách bấm "giữ" từng thẻ một trong cả trăm thẻ. Một lần bấm (có hỏi lại) ghi đúng quyết định "giữ" mà từng thẻ ghi -
// không câu nào phải thu lại, máy thôi hỏi - và hoàn tác được cả nhóm.
const BULK_KINDS: WorkKind[] = ["pronunciation", "speaker", "turn", "vocative", "unnamed"];

function BulkKeep({ bookId, kind, items }: { bookId: string; kind: WorkKind; items: WorkItem[] }) {
  const client = useQueryClient();
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const pronunciation = kind === "pronunciation";
  const keepable = items.filter((item) => (pronunciation ? Boolean(item.surface) : keepRequests(item).length > 0));
  if (!BULK_KINDS.includes(kind) || keepable.length < 2) return null;
  const run = async () => {
    setBusy(true);
    const decisions: Record<string, unknown>[] = [];
    let done = 0;
    try {
      for (const item of keepable) {
        if (pronunciation) {
          const { requestedAt } = await api<{ requestedAt: number }>(`/api/books/${bookId}/pronunciation`, {
            method: "POST",
            body: { surface: item.surface, spokenForm: item.current },
          });
          decisions.push({ surface: item.surface, requestedAt, previous: item.current, keep: true });
        } else {
          // Thẻ vai phụ cả cuốn giữ người của từng vai: một yêu cầu cho mỗi vai.
          for (const request of keepRequests(item)) {
            const { requestedAt } = await api<{ requestedAt: number }>(`/api/books/${bookId}/speaker`, { method: "POST", body: request });
            decisions.push({ lines: request.lines, requestedAt, keep: true });
          }
        }
        done += 1;
      }
      toast.success(`Đã giữ như máy đang làm cho ${done} thẻ`, {
        description: "Không câu nào phải thu lại; máy sẽ không hỏi lại những thẻ này.",
        action: undoAction(client, bookId, pronunciation ? "pronunciation" : "speaker", decisions, `${done} thẻ trở lại chờ duyệt.`),
        duration: UNDO_MS,
      });
    } catch (error) {
      toast.error(`Mới giữ được ${done}/${keepable.length} thẻ`, { description: (error as Error).message });
    } finally {
      setBusy(false);
      setConfirm(false);
      refreshAfterDecision(client, bookId);
    }
  };
  return (
    <>
      <Button size="sm" variant="ghost" icon={Check} className="mt-3" onClick={() => setConfirm(true)}>
        Giữ như máy đang làm - cả {keepable.length} thẻ “{KIND_LABEL[kind]}”…
      </Button>
      <Dialog
        open={confirm}
        onOpenChange={setConfirm}
        title={`Giữ cả ${keepable.length} thẻ “${KIND_LABEL[kind]}”?`}
        description={
          pronunciation
            ? "Mọi tên trong các thẻ này giữ đúng cách máy đang đọc. Không câu nào phải thu lại; máy thôi hỏi. Hoàn tác được ngay sau đó."
            : "Mọi câu trong các thẻ này giữ đúng người máy đang gán. Không câu nào phải thu lại; máy thôi hỏi. Hoàn tác được ngay sau đó."
        }
      >
        <div className="mt-5 flex justify-end gap-2">
          <Button variant="ghost" onClick={() => setConfirm(false)}>
            Thôi
          </Button>
          <Button variant="primary" icon={Check} loading={busy} onClick={() => void run()}>
            Giữ cả {keepable.length} thẻ
          </Button>
        </div>
      </Dialog>
    </>
  );
}

interface InboxProps {
  book: BookSummary;
  onOpenReview: OpenReview;
  onOpenScript?: OpenScript;
  onOpenNames?: OpenNames;
  /** Bộ lọc loại việc và thẻ cần cuộn tới, nằm trong địa chỉ trang - Back từ Kịch bản trở lại đúng chỗ đang duyệt. */
  kind?: string | null;
  focus?: string | null;
  onKind?: (kind: WorkKind | "all") => void;
  /** Thẻ đang nằm ở màn "Duyệt trước khi thu": không hiện lại ở đây, chỉ nói còn bao nhiêu và đường mở màn ấy. */
  inPrecast?: Set<string>;
  onOpenPrecast?: () => void;
}

/** Một nhóm thẻ việc chọn sẵn (màn "Duyệt trước khi thu"): đúng thẻ của hộp việc, sửa ngay trên thẻ như ở đó. */
export function WorkCards({ book, items, onOpenReview, onOpenScript, onOpenNames }: {
  book: BookSummary;
  items: WorkItem[];
  onOpenReview: OpenReview;
  onOpenScript?: OpenScript;
  onOpenNames?: OpenNames;
}) {
  return (
    <PendingHint.Provider value={PENDING_NOTE[applyWhen(book)]}>
      <ol className="mt-3 space-y-3">
        {items.map((item) => (
          <Card key={item.key} bookId={book.id} item={item} onOpenReview={onOpenReview} onOpenScript={onOpenScript} onOpenNames={onOpenNames} />
        ))}
      </ol>
    </PendingHint.Provider>
  );
}

export function WorkInbox(props: InboxProps) {
  // Sách đang chạy áp ở ranh giới chương kế tiếp, không "chờ chạy tiếp" (studio/decisions.ts).
  const hint = PENDING_NOTE[applyWhen(props.book)];
  return (
    <PendingHint.Provider value={hint}>
      <WorkInboxBody {...props} />
    </PendingHint.Provider>
  );
}

/** Số thay đổi đang chờ áp dụng trong các thẻ đã quyết: hai thẻ cùng quyết một câu (“Ai nói câu này” + “Người gọi hay người nói”) là MỘT thay đổi -
 *  khớp số trên nút “Áp dụng N thay đổi”. “Giữ” cách đang đọc là đã quyết mà không có gì chờ áp dụng. */
export function waitingChanges(decided: WorkItem[]): number {
  const changes = new Set<string>();
  for (const item of decided) {
    if (item.requested === item.current) continue;
    const lines = item.lines?.map((line) => line.stableId).sort();
    changes.add(lines?.length ? `lines:${lines.join(",")}` : `key:${item.key}`);
  }
  return changes.size;
}

function WorkInboxBody({ book, onOpenReview, onOpenScript, onOpenNames, kind: kindParam, focus, onKind, inPrecast, onOpenPrecast }: InboxProps) {
  const bookId = book.id;
  const hint = useContext(PendingHint);
  const [kind, setKindState] = useState<WorkKind | "all">(
    kindParam && kindParam in KIND_LABEL ? (kindParam as WorkKind) : "all",
  );
  const setKind = (value: WorkKind | "all") => {
    setKindState(value);
    onKind?.(value);
  };
  const [shown, setShown] = useState(PAGE);
  // Phím tắt (soát UX a6 01-10, D1): J / K chọn thẻ, 1-9 bấm lựa chọn thứ N của thẻ ấy - duyệt cả trăm thẻ không cần chuột.
  // Quyết xong thì thẻ rời danh sách, nên thẻ kế tự đứng vào đúng chỗ đang chọn.
  const [cursor, setCursorState] = useState<number | null>(null);
  const cursorRef = useRef<number | null>(null);
  const setCursor = (value: number | null) => {
    cursorRef.current = value;
    setCursorState(value);
  };
  const keys = useRef<{ items: WorkItem[] }>({ items: [] });
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.ctrlKey || event.metaKey || event.altKey) return;
      if (event.target instanceof Element && event.target.closest("input, textarea, select, [contenteditable=true], [role=dialog]")) return;
      const list = keys.current.items;
      if (!list.length) return;
      const current = cursorRef.current === null ? null : Math.min(cursorRef.current, list.length - 1);
      if (event.key === "j" || event.key === "k") {
        event.preventDefault();
        const next = current === null ? 0 : Math.min(Math.max(current + (event.key === "j" ? 1 : -1), 0), list.length - 1);
        setCursor(next);
        window.setTimeout(() => document.getElementById(`work-${list[next].key}`)?.scrollIntoView({ block: "nearest" }), 0);
      } else if (/^[1-9]$/.test(event.key) && current !== null) {
        const choices = document.querySelectorAll<HTMLButtonElement>(`#work-${CSS.escape(list[current].key)} [data-choice]:not(:disabled)`);
        const choice = choices[Number(event.key) - 1];
        if (choice) {
          event.preventDefault();
          choice.click();
        }
      } else if (event.key === "Escape" && current !== null) {
        setCursor(null);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // setCursor chỉ ghi ref + state - không cần gắn lại.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const { data, isLoading } = useQuery({
    queryKey: ["work", bookId],
    queryFn: () => api<WorkView>(`/api/books/${bookId}/work`),
  });
  // Trở lại từ Kịch bản (Back hay "Về Việc cần duyệt"): cuộn tới đúng thẻ vừa rời, mở đủ trang để thấy nó - một lần.
  const focused = useRef(false);
  useEffect(() => {
    if (focused.current || !focus || !data) return;
    focused.current = true;
    const index = data.items.filter((item) => !item.requested && (kind === "all" || item.kind === kind)).findIndex((item) => item.key === focus);
    if (index >= PAGE) setShown(Math.ceil((index + 1) / PAGE) * PAGE);
    window.setTimeout(() => document.getElementById(`work-${focus}`)?.scrollIntoView({ block: "center" }), 0);
  }, [focus, data, kind]);
  // Quyết xong việc cuối của loại đang lọc: về “Tất cả” cả trong địa chỉ trang, không thì tải lại (hay quay lại) vẫn lọc loại đã hết thẻ (soát UX a11).
  useEffect(() => {
    if (!data || kind === "all") return;
    if (!data.items.some((item) => !item.requested && item.kind === kind && !inPrecast?.has(item.key))) setKind("all");
    // setKind chỉ ghi state + gọi onKind - không cần gắn lại.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, kind, inPrecast]);
  if (isLoading || !data) return <div className="mt-6 text-sm text-fg-2">Đang tìm những chỗ máy chưa chắc…</div>;
  if (!data.items.length) {
    return (
      <EmptyState icon={AudioLines} title="Không có việc nào cần duyệt" className="py-10">
        Máy chắc chắn về mọi thứ đã làm tới giờ.
      </EmptyState>
    );
  }
  // Việc đã quyết (chờ áp dụng) xuống mục thu gọn cuối trang và không tính vào số đếm.
  const undecided = data.items.filter((item) => !item.requested);
  const open = inPrecast ? undecided.filter((item) => !inPrecast.has(item.key)) : undecided;
  const atReview = undecided.length - open.length;
  const answered = data.items.filter((item) => item.requested);
  // Đã ghi mà chỉ áp khi làm lại sách (đoạn người kể đã phân tích xong): nhóm riêng, không có nút "Áp dụng thay đổi" nào cho nó.
  const redo = answered.filter((item) => item.redoOnly);
  const decided = answered.filter((item) => !item.redoOnly);
  // "Giữ" cách đang đọc là đã quyết mà không có gì chờ áp dụng - không đếm vào "chờ áp dụng" (soát UX 29-09).
  const waiting = waitingChanges(decided);
  const counts: Partial<Record<WorkKind, number>> = {};
  for (const item of open) counts[item.kind] = (counts[item.kind] ?? 0) + 1;
  const kinds = (Object.keys(KIND_LABEL) as WorkKind[]).filter((value) => counts[value]);
  // Quyết xong việc cuối của loại đang lọc thì loại ấy biến khỏi thanh lọc - về "Tất cả", đừng để danh sách trống không lời.
  const active = kind !== "all" && !counts[kind] ? "all" : kind;
  const items = open.filter((item) => active === "all" || item.kind === active);
  keys.current.items = items.slice(0, shown);
  const at = cursor === null ? null : Math.min(cursor, Math.max(items.slice(0, shown).length - 1, 0));
  return (
    <div className="mt-5">
      {/* Lời mở đầu theo trạng thái sách - soát UX 29-09: "đang chạy tiếp" hiện cả khi sách đã xong hay đang dừng. */}
      <p className="max-w-3xl text-sm text-fg-2">{inboxLead(book)}</p>
      {atReview > 0 && (
        <div className="mt-4 flex flex-wrap items-center justify-between gap-2 rounded-xl border border-accent/30 bg-accent-soft px-4 py-3 text-sm">
          <span className="min-w-0 text-pretty">
            {atReview} việc về giọng, cách đọc tên và người nói ở các chương đầu đang nằm ở “Duyệt trước khi thu” - duyệt ở đó, không hiện lặp ở đây.
          </span>
          {onOpenPrecast && (
            <Button size="sm" variant="secondary" onClick={onOpenPrecast}>
              Mở màn duyệt
            </Button>
          )}
        </div>
      )}
      <div className="mt-4">
        <Segmented<WorkKind | "all">
          wrap
          label="Loại việc"
          value={active}
          onChange={(value) => {
            setKind(value);
            setShown(PAGE);
          }}
          options={[
            { value: "all", label: `Tất cả · ${open.length}` },
            ...kinds.map((value) => ({ value, label: `${KIND_LABEL[value]} · ${counts[value]}` })),
          ]}
        />
      </div>
      {active !== "all" && <BulkKeep bookId={bookId} kind={active} items={items} />}
      <p className="mt-2 hidden flex-wrap items-center gap-1.5 text-xs text-fg-3 md:flex">
        Bàn phím: <Kbd>J</Kbd> <Kbd>K</Kbd> chọn thẻ · <Kbd>1</Kbd>–<Kbd>9</Kbd> bấm lựa chọn thứ N của thẻ (đếm từ trái sang) ·{" "}
        <Kbd>Esc</Kbd> bỏ chọn
      </p>
      <ol className={cn("mt-3 space-y-3")}>
        {items.slice(0, shown).map((item, index) => (
          <Card key={item.key} bookId={bookId} item={item} active={index === at} onOpenReview={onOpenReview} onOpenScript={onOpenScript} onOpenNames={onOpenNames} />
        ))}
      </ol>
      {items.length > shown && (
        <Button variant="secondary" size="sm" className="mt-4" onClick={() => setShown(shown + PAGE)}>
          Xem thêm {Math.min(PAGE, items.length - shown)} việc
        </Button>
      )}
      {!open.length && atReview === 0 && (
        <p className="mt-4 text-sm text-fg-2">
          Mọi việc đã có quyết định{decided.length > 0 ? ` - ${hint}` : ""}.
        </p>
      )}
      {decided.length > 0 && (
        <details className="mt-6 rounded-xl border border-line px-4 py-3">
          <summary className="cursor-pointer text-sm font-medium text-fg-2">
            {waiting === decided.length ? `Đã quyết, chờ áp dụng · ${decided.length} việc` : `Đã quyết · ${decided.length} việc (${waiting} thay đổi chờ áp dụng)`}
          </summary>
          <ol className="mt-3 space-y-3">
            {decided.map((item) => (
              <Card key={item.key} bookId={bookId} item={item} onOpenReview={onOpenReview} onOpenNames={onOpenNames} />
            ))}
          </ol>
        </details>
      )}
      {redo.length > 0 && (
        <details className="mt-4 rounded-xl border border-line px-4 py-3">
          <summary className="cursor-pointer text-sm font-medium text-fg-2">Đã ghi, áp khi làm lại sách · {redo.length}</summary>
          <ol className="mt-3 space-y-3">
            {redo.map((item) => (
              <Card key={item.key} bookId={bookId} item={item} onOpenReview={onOpenReview} onOpenNames={onOpenNames} />
            ))}
          </ol>
        </details>
      )}
    </div>
  );
}
