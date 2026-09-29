import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AudioLines, Check, Pause, Play, Search, UserPlus } from "lucide-react";
import { createContext, useContext, useState } from "react";
import { toast } from "sonner";
import { useClip } from "@/listen/clip";
import { cn } from "@/shared/cn";
import { formatNumber } from "@/shared/format";
import { Button, EmptyState, Segmented } from "@/shared/ui";
import { api, suggestionOf, urls, type BookSummary } from "./api";
import { ReadingProblem } from "./ReadingProblem";
import { applyWhen, PENDING_NOTE, refreshAfterDecision, UNDO_MS, undoAction, useWhenApplied } from "./decisions";

// "Việc cần duyệt" (docs/STUDIO_REVIEW.md, webui/work_items.py): chỗ máy nghi ngờ, xếp theo lợi trên mỗi lần bấm. Máy đã tự
// quyết và dây chuyền KHÔNG chờ ai - đây là nơi người sửa ít nhất mà được nhiều nhất. Cách đọc tên sửa được ngay trên thẻ
// (bước 2): mong muốn ghi vào overrides.json, dây chuyền áp ở ranh giới chương và thu lại những câu có tên ấy.

type WorkKind = "speaker" | "turn" | "gender" | "vocative" | "alias" | "bracket" | "shared-voice" | "pronunciation" | "unnamed" | "audio";

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
}

interface WorkItem {
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
  /** Thẻ bí danh: tên được hỏi, để hiển thị ("“Thiên Biến Vạn Hóa” là Krai") - `current` là nhãn lựa chọn, không phải tên. */
  subject?: string;
  /** Việc giọng/giới của nhân vật ("Nam hay nữ", "Chung giọng"): mỗi lựa chọn là một yêu cầu POST /voice; giữ nguyên thì
   *  ghi yêu cầu rỗng cho từng người trong `keepCharacters` (thẻ thôi hỏi). */
  voiceChoices?: VoiceChoice[];
  keepCharacters?: string[];
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

interface WorkView {
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
};

const PAGE = 40;

export function useWorkCount(bookId: string) {
  const { data } = useQuery({
    queryKey: ["work", bookId],
    queryFn: () => api<WorkView>(`/api/books/${bookId}/work`),
    enabled: Boolean(bookId),
    staleTime: 60_000,
  });
  // Việc đã quyết (đang chờ áp dụng) không còn là việc cần làm - soát UX 29-09: số không giảm sau khi quyết.
  return data?.items.filter((item) => !item.requested).length ?? 0;
}

/** Việc đã quyết chờ gì: sách đang dở thì tự áp khi chạy tiếp; sách ĐÃ XONG không tự chạy lại - phải bấm "Áp dụng thay
 *  đổi" (soát UX 29-09: thẻ từng nói "chờ … chạy tiếp" cả ở sách đã xong). */
const PendingHint = createContext("chờ áp dụng khi sách chạy tiếp");

/** Chữ đầu viết hoa - "câu này" đứng đầu câu báo. */
function sentence(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/** Thẻ đã quyết nói KẾT QUẢ thay vì lặp câu hỏi ("Đọc “Arcanist” là…?" khi đã giữ - soát UX 29-09); null = giữ tiêu đề. */
function decidedTitle(item: WorkItem): string | null {
  const answer = item.requested;
  if (!answer) return null;
  if (item.kind === "pronunciation" && item.surface) {
    return answer === item.current ? `Giữ: “${item.surface}” đọc là “${answer}”` : `“${item.surface}” sẽ đọc là “${answer}”`;
  }
  if (item.voiceChoices?.length) return item.voiceChoices.find((choice) => choice.label === answer || choice.done === answer)?.done ?? null;
  if (item.kind === "alias") return `“${item.subject ?? item.current}” là ${midSentence(answer)}`;
  if (item.lines?.length) return `${item.lines.length > 1 ? `${item.lines.length} câu này` : "Câu này"} của ${midSentence(answer)}`;
  return null;
}

/** Nhãn nút ("Vai phụ không tên", "Người kể") đứng GIỮA câu thì viết thường chữ đầu - "…của vai phụ không tên" (soát UX
 *  29-09). Tên người giữ nguyên. */
function midSentence(label: string | null | undefined): string {
  const text = label ?? "";
  return text === "Vai phụ không tên" || text === "Người kể" ? text.charAt(0).toLowerCase() + text.slice(1) : text;
}

function Example({ bookId, example }: { bookId: string; example: WorkExample }) {
  const clip = useClip();
  const id = `work-${example.segmentId}`;
  const playing = clip.current === id;
  return (
    <li className="flex items-start gap-2 text-sm">
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
        <div className="text-xs text-fg-3">
          {example.chapterTitle} · {example.seq === 0 ? "tiêu đề chương" : `câu ${example.seq}`}
          {example.speaker && ` · máy gán: ${example.speaker}`}
          {example.changes && <span className="font-semibold text-accent-text"> · sẽ đổi</span>}
        </div>
        <p className="text-fg">{example.text}</p>
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
        <Button size="sm" variant="secondary" disabled={save.isPending} onClick={() => save.mutate(item.current)}>
          Đúng rồi, giữ "{item.current}"
        </Button>
        <label htmlFor={inputId} className="text-xs text-fg-2">
          hoặc đọc là
        </label>
        <input
          id={inputId}
          aria-label={`Cách đọc mới cho ${item.surface}`}
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
}: {
  bookId: string;
  item: WorkItem;
  onOpenScript?: OpenScript;
  scope?: Scope;
  onScope?: (scope: Scope) => void;
}) {
  const client = useQueryClient();
  const lines = scope === "all" && item.allLines ? item.allLines : item.lines;
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
          `Câu đã thu sẽ đọc lại bằng giọng của người ấy. ${when}` +
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
      <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="Ai nói câu này">
        {(item.choices ?? []).map((choice, index) => (
          <Button
            key={choice.value}
            size="sm"
            // Đã quyết thì tô lựa chọn của người nghe, không phải gợi ý đầu của máy.
            variant={(item.requested ? [choice.name, choice.label].includes(item.requested) : index === 0 && item.kind !== "unnamed")
              ? "primary" : "secondary"}
            aria-pressed={item.requested ? [choice.name, choice.label].includes(item.requested) : undefined}
            disabled={save.isPending}
            onClick={() => save.mutate({ speaker: choice.value })}
          >
            {choice.label}
          </Button>
        ))}
        {item.currentValue && (
          <Button size="sm" variant="ghost" disabled={save.isPending} onClick={() => save.mutate({ speaker: item.currentValue! })}>
            {item.keepLabel ?? (item.kind === "unnamed" ? "Đúng là vai phụ" : `Giữ ${item.current}`)}
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
            Tìm trong truyện…
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
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Tên người nói (vd Tọa Phu Đồng Tử)"
            aria-label="Tên người nói mới"
            maxLength={80}
            className="h-8 min-w-0 flex-1 rounded-lg border border-line bg-panel px-2.5 text-sm outline-none focus-visible:border-accent"
          />
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
              disabled={!name.trim() || save.isPending}
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
      const back = item.requested ? `Trở lại quyết định trước: ${item.requested}.` : "Thẻ hỏi lại như trước khi bấm.";
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
          : `Mọi câu của người ấy sẽ đọc lại bằng giọng mới. ${when}`,
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
            <Button
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
          <Button
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
type OpenScript = (chapterId: number, stableId: string, pick?: boolean) => void;

function Card({ bookId, item, onOpenReview, onOpenScript, onOpenNames }: { bookId: string; item: WorkItem; onOpenReview: () => void; onOpenScript?: OpenScript; onOpenNames?: (name: string) => void }) {
  // Thẻ chuỗi lượt đối đáp: đổi các câu xen kẽ (mặc định) hay cả chuỗi - câu "sẽ đổi" theo phạm vi đang chọn.
  const [scope, setScope] = useState<Scope>("alternate");
  return (
    <li className="rounded-xl border border-line bg-panel p-4">
      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
        <span className="rounded-full bg-hover px-2 py-0.5 text-[11px] font-medium text-fg-2">{KIND_LABEL[item.kind]}</span>
        <h3 className="text-[15px] font-semibold">{decidedTitle(item) ?? item.title}</h3>
      </div>
      <p className="mt-1.5 text-sm text-fg-2">{item.problem}</p>
      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-fg-2">
        <span>
          Ảnh hưởng <span className="tabular font-semibold text-fg">{formatNumber(item.affected)}</span> câu
        </span>
        <span>
          Máy đang dùng: <span className="font-medium text-fg">{item.current}</span>
        </span>
      </div>
      {item.kind === "audio" ? (
        <Button size="sm" variant="secondary" icon={AudioLines} className="mt-3" onClick={onOpenReview}>
          Nghe ở tab Cần nghe lại
        </Button>
      ) : item.kind === "pronunciation" && item.surface ? (
        <PronunciationFix bookId={bookId} item={item} onOpenNames={onOpenNames} />
      ) : item.voiceChoices && item.voiceChoices.length > 0 ? (
        <VoiceFix bookId={bookId} item={item} />
      ) : item.lines && item.choices ? (
        <SpeakerFix bookId={bookId} item={item} onOpenScript={onOpenScript} scope={scope} onScope={setScope} />
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
          {item.examples.map((example) => (
            <Example
              key={example.segmentId}
              bookId={bookId}
              example={item.allLines && scope === "all" ? { ...example, changes: true } : example}
            />
          ))}
        </ul>
      )}
    </li>
  );
}

export function WorkInbox(props: { book: BookSummary; onOpenReview: () => void; onOpenScript?: OpenScript; onOpenNames?: (name: string) => void }) {
  // Sách đang chạy áp ở ranh giới chương kế tiếp, không "chờ chạy tiếp" (studio/decisions.ts).
  const hint = PENDING_NOTE[applyWhen(props.book)];
  return (
    <PendingHint.Provider value={hint}>
      <WorkInboxBody {...props} />
    </PendingHint.Provider>
  );
}

function WorkInboxBody({ book, onOpenReview, onOpenScript, onOpenNames }: { book: BookSummary; onOpenReview: () => void; onOpenScript?: OpenScript; onOpenNames?: (name: string) => void }) {
  const bookId = book.id;
  const hint = useContext(PendingHint);
  const [kind, setKind] = useState<WorkKind | "all">("all");
  const [shown, setShown] = useState(PAGE);
  const { data, isLoading } = useQuery({
    queryKey: ["work", bookId],
    queryFn: () => api<WorkView>(`/api/books/${bookId}/work`),
  });
  if (isLoading || !data) return <div className="mt-6 text-sm text-fg-2">Đang tìm những chỗ máy chưa chắc…</div>;
  if (!data.items.length) {
    return (
      <EmptyState icon={AudioLines} title="Không có việc nào cần duyệt" className="py-10">
        Máy chắc chắn về mọi thứ đã làm tới giờ.
      </EmptyState>
    );
  }
  // Việc đã quyết (chờ áp dụng) xuống mục thu gọn cuối trang và không tính vào số đếm.
  const open = data.items.filter((item) => !item.requested);
  const decided = data.items.filter((item) => item.requested);
  // "Giữ" cách đang đọc là đã quyết mà không có gì chờ áp dụng - không đếm vào "chờ áp dụng" (soát UX 29-09).
  const waiting = decided.filter((item) => item.requested !== item.current).length;
  const counts: Partial<Record<WorkKind, number>> = {};
  for (const item of open) counts[item.kind] = (counts[item.kind] ?? 0) + 1;
  const kinds = (Object.keys(KIND_LABEL) as WorkKind[]).filter((value) => counts[value]);
  // Quyết xong việc cuối của loại đang lọc thì loại ấy biến khỏi thanh lọc - về "Tất cả", đừng để danh sách trống không lời.
  const active = kind !== "all" && !counts[kind] ? "all" : kind;
  const items = open.filter((item) => active === "all" || item.kind === active);
  return (
    <div className="mt-5">
      <p className="max-w-3xl text-sm text-fg-2">
        {/* Lời mở đầu theo trạng thái sách - soát UX 29-09: "đang chạy tiếp" hiện cả khi sách đã xong hay đang dừng. */}
        {book.running
          ? "Máy đã tự quyết và đang chạy tiếp - không có gì phải chờ."
          : book.phase === "done"
            ? "Sách đã xong - sửa xong thì bấm “Áp dụng thay đổi” ở trên để thu lại đúng các câu bị ảnh hưởng."
            : "Sách đang dừng - sửa bây giờ, lần chạy tiếp sẽ áp dụng."}{" "}
        Đây là những chỗ máy không chắc, xếp theo lợi: việc ở
        trên sửa một lần được nhiều câu nhất. Cách đọc tên, người nói từng câu, hai tên của một người, giới và giọng nhân
        vật đều sửa được ngay tại đây, không phải dừng sách.
      </p>
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
      <ol className={cn("mt-4 space-y-3")}>
        {items.slice(0, shown).map((item) => (
          <Card key={item.key} bookId={bookId} item={item} onOpenReview={onOpenReview} onOpenScript={onOpenScript} onOpenNames={onOpenNames} />
        ))}
      </ol>
      {items.length > shown && (
        <Button variant="secondary" size="sm" className="mt-4" onClick={() => setShown(shown + PAGE)}>
          Xem thêm {Math.min(PAGE, items.length - shown)} việc
        </Button>
      )}
      {!open.length && (
        <p className="mt-4 text-sm text-fg-2">
          Mọi việc đã có quyết định - {hint}.
        </p>
      )}
      {decided.length > 0 && (
        <details className="mt-6 rounded-xl border border-line px-4 py-3">
          <summary className="cursor-pointer text-sm font-medium text-fg-2">
            {waiting === decided.length ? `Đã quyết, chờ áp dụng · ${decided.length}` : `Đã quyết · ${decided.length} (${waiting} chờ áp dụng)`}
          </summary>
          <ol className="mt-3 space-y-3">
            {decided.map((item) => (
              <Card key={item.key} bookId={bookId} item={item} onOpenReview={onOpenReview} onOpenNames={onOpenNames} />
            ))}
          </ol>
        </details>
      )}
    </div>
  );
}
