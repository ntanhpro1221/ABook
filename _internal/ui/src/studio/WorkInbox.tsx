import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AudioLines, Check, Pause, Play, UserPlus } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { useClip } from "@/listen/clip";
import { cn } from "@/shared/cn";
import { formatNumber } from "@/shared/format";
import { Button, EmptyState, Segmented } from "@/shared/ui";
import { api, urls } from "./api";

// "Việc cần anh" (docs/STUDIO_REVIEW.md, webui/work_items.py): chỗ máy nghi ngờ, xếp theo lợi trên mỗi lần bấm. Máy đã tự
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
  /** `name`: tên người khi nhãn nút không phải là tên ("Gộp vào Kati"). */
  choices?: { label: string; value: string; name?: string }[];
  currentValue?: string;
  /** Nhãn nút giữ nguyên khi "Giữ <người đang nói>" không đúng nghĩa (bí danh: "Hai người khác nhau"). */
  keepLabel?: string;
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
  return data?.items.length ?? 0;
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
          {example.chapterTitle} · câu {example.seq}
          {example.speaker && ` · máy gán: ${example.speaker}`}
        </div>
        <p className="text-fg">{example.text}</p>
      </div>
    </li>
  );
}

// Sửa cách đọc một tên ngay trên thẻ. Không chờ gì: ghi xong là xong phần người; dây chuyền áp ở ranh giới chương kế
// tiếp (hoặc lần chạy tới) và thu lại đúng những câu có tên ấy - kể cả sách đã xong.
function PronunciationFix({ bookId, item }: { bookId: string; item: WorkItem }) {
  const client = useQueryClient();
  const [value, setValue] = useState(item.requested ?? item.current);
  const save = useMutation({
    mutationFn: (spokenForm: string) =>
      api<{ surface: string; spokenForm: string }>(`/api/books/${bookId}/pronunciation`, {
        method: "POST",
        body: { surface: item.surface, spokenForm },
      }),
    onSuccess: ({ spokenForm }) => {
      void client.invalidateQueries({ queryKey: ["work", bookId] });
      void client.invalidateQueries({ queryKey: ["book", bookId] });
      void client.invalidateQueries({ queryKey: ["library"] });
      // Giữ đúng cách máy đang đọc thì không có gì để thu lại - soát UX 29-09: báo "sẽ thu lại" làm người nghe hoảng.
      if (spokenForm === item.current) {
        toast.success(`Giữ cách đọc "${spokenForm}"`, { description: "Không phải thu lại câu nào." });
        return;
      }
      toast.success(`Đã ghi: "${item.surface}" đọc là "${spokenForm}"`, {
        description: "Các câu có tên này sẽ được thu lại. Thu lại khi sách chạy tiếp - sách đã xong thì bấm “Áp dụng thay đổi” ở trang dự án.",
      });
    },
    onError: (error: Error) => toast.error("Chưa ghi được cách đọc", { description: error.message }),
  });
  const typed = value.trim();
  const inputId = `spoken-${item.key}`;
  return (
    <div className="mt-3">
      {item.requested && (
        <p className="mb-2 flex items-center gap-1.5 text-xs text-fg-2">
          <Check className="size-3.5 text-success" />
          Đã ghi "{item.requested}" - chờ áp dụng khi sách chạy tiếp.
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
          onChange={(event) => setValue(event.target.value)}
          spellCheck={false}
          autoComplete="off"
          className="h-8 w-40 rounded-lg border border-line bg-panel px-2.5 text-sm text-fg outline-none focus-visible:border-accent"
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
      </form>
    </div>
  );
}

// Gán người nói - một câu ("Ai nói câu này", người gọi) hay mọi câu của một vai phụ: mỗi ứng viên một nút, người máy nghi
// nhất đứng đầu. Không chờ gì - ghi xong là xong phần người; dây chuyền gán câu cho người ấy (mượn đúng giọng sẵn có của
// họ) ở ranh giới chương, câu đã thu thì thu lại.
function SpeakerFix({ bookId, item }: { bookId: string; item: WorkItem }) {
  const client = useQueryClient();
  // "Người khác…": người nói chưa có trong lựa chọn - kể cả người máy CHƯA TỪNG gán câu nào (linh thể nói trong 『』):
  // gõ tên + chọn giới, dây chuyền tạo người ấy và cấp giọng riêng như bước phân vai.
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const save = useMutation({
    mutationFn: ({ speaker, newGender }: { speaker: string; newGender?: string }) =>
      api<{ lines: number; speaker: string }>(`/api/books/${bookId}/speaker`, {
        method: "POST",
        body: { lines: item.lines, speaker, newGender: newGender ?? "" },
      }),
    onSuccess: ({ speaker }) => {
      void client.invalidateQueries({ queryKey: ["work", bookId] });
      void client.invalidateQueries({ queryKey: ["book", bookId] });
      void client.invalidateQueries({ queryKey: ["library"] });
      const which = (item.lines?.length ?? 1) > 1 ? `${item.lines?.length} câu này` : "câu này";
      if (speaker === item.currentValue) {
        toast.success(item.keepLabel ? `Đã ghi: ${item.keepLabel}` : `Giữ nguyên: ${which} của ${item.current}`, {
          description: "Việc này sẽ không hiện lại.",
        });
        return;
      }
      const choice = item.choices?.find((option) => option.value === speaker);
      const label = choice?.name ?? choice?.label ?? speaker;
      toast.success(`Đã ghi: ${which} của ${label}`, {
        description: "Câu đã thu sẽ đọc lại bằng giọng của người ấy. Thu lại khi sách chạy tiếp - sách đã xong thì bấm “Áp dụng thay đổi” ở trang dự án.",
      });
    },
    onError: (error: Error) => toast.error("Chưa ghi được người nói", { description: error.message }),
  });
  return (
    <div className="mt-3">
      {item.requested && (
        <p className="mb-2 flex items-center gap-1.5 text-xs text-fg-2">
          <Check className="size-3.5 text-success" />
          Đã ghi: {(item.lines?.length ?? 1) > 1 ? `${item.lines?.length} câu này` : "câu này"} của {item.requested} - chờ áp
          dụng khi sách chạy tiếp.
        </p>
      )}
      <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="Ai nói câu này">
        {(item.choices ?? []).map((choice, index) => (
          <Button
            key={choice.value}
            size="sm"
            variant={index === 0 ? "primary" : "secondary"}
            disabled={save.isPending}
            onClick={() => save.mutate({ speaker: choice.value })}
          >
            {choice.label}
          </Button>
        ))}
        {item.currentValue && (
          <Button size="sm" variant="ghost" disabled={save.isPending} onClick={() => save.mutate({ speaker: item.currentValue! })}>
            {item.keepLabel ?? `Giữ ${item.current}`}
          </Button>
        )}
        <Button size="sm" variant="ghost" icon={UserPlus} aria-expanded={creating} onClick={() => setCreating((value) => !value)}>
          Người khác…
        </Button>
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
  const save = useMutation({
    mutationFn: async ({ requests }: { requests: Omit<VoiceChoice, "label" | "note" | "done" | "recommended">[]; label: string; keep: boolean }) => {
      for (const request of requests) await api(`/api/books/${bookId}/voice`, { method: "POST", body: request });
    },
    onSuccess: (_result, { label, keep }) => {
      void client.invalidateQueries({ queryKey: ["work", bookId] });
      void client.invalidateQueries({ queryKey: ["book", bookId] });
      void client.invalidateQueries({ queryKey: ["library"] });
      if (keep) {
        toast.success(`Đã ghi: ${label}`, { description: "Việc này sẽ không hiện lại." });
        return;
      }
      toast.success(`Đã ghi: ${label}`, {
        description: "Nếu giọng phải đổi, mọi câu của người ấy sẽ đọc lại bằng giọng mới. Thu lại khi sách chạy tiếp - sách đã xong thì bấm “Áp dụng thay đổi” ở trang dự án.",
      });
    },
    onError: (error: Error) => toast.error("Chưa ghi được", { description: error.message }),
  });
  return (
    <div className="mt-3">
      {item.requested && (
        <p className="mb-2 flex items-center gap-1.5 text-xs text-fg-2">
          <Check className="size-3.5 text-success" />
          Đã ghi: {item.requested} - chờ áp dụng khi sách chạy tiếp.
        </p>
      )}
      <div className="flex flex-wrap items-start gap-2" role="group" aria-label="Chọn">
        {(item.voiceChoices ?? []).map((choice) => (
          <div key={`${choice.character}-${choice.label}`} className="flex flex-col items-start gap-0.5">
            <Button
              size="sm"
              variant={choice.recommended ? "primary" : "secondary"}
              disabled={save.isPending}
              onClick={() =>
                save.mutate({
                  requests: [{ character: choice.character, gender: choice.gender, preset: choice.preset, avoid: choice.avoid }],
                  label: choice.done ?? choice.label,
                  keep: false,
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

function Card({ bookId, item, onOpenReview }: { bookId: string; item: WorkItem; onOpenReview: () => void }) {
  return (
    <li className="rounded-xl border border-line bg-panel p-4">
      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
        <span className="rounded-full bg-hover px-2 py-0.5 text-[11px] font-medium text-fg-2">{KIND_LABEL[item.kind]}</span>
        <h3 className="text-[15px] font-semibold">{item.title}</h3>
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
        <PronunciationFix bookId={bookId} item={item} />
      ) : item.voiceChoices && item.voiceChoices.length > 0 ? (
        <VoiceFix bookId={bookId} item={item} />
      ) : item.lines && item.choices ? (
        <SpeakerFix bookId={bookId} item={item} />
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
            <Example key={example.segmentId} bookId={bookId} example={example} />
          ))}
        </ul>
      )}
    </li>
  );
}

export function WorkInbox({ bookId, onOpenReview }: { bookId: string; onOpenReview: () => void }) {
  const [kind, setKind] = useState<WorkKind | "all">("all");
  const [shown, setShown] = useState(PAGE);
  const { data, isLoading } = useQuery({
    queryKey: ["work", bookId],
    queryFn: () => api<WorkView>(`/api/books/${bookId}/work`),
  });
  if (isLoading || !data) return <div className="mt-6 text-sm text-fg-2">Đang tìm những chỗ máy chưa chắc…</div>;
  if (!data.items.length) {
    return (
      <EmptyState icon={AudioLines} title="Không có việc gì cần anh" className="py-10">
        Máy chắc chắn về mọi thứ đã làm tới giờ.
      </EmptyState>
    );
  }
  const kinds = (Object.keys(KIND_LABEL) as WorkKind[]).filter((value) => data.counts[value]);
  const items = data.items.filter((item) => kind === "all" || item.kind === kind);
  return (
    <div className="mt-5">
      <p className="max-w-3xl text-sm text-fg-2">
        Máy đã tự quyết và đang chạy tiếp - không có gì phải chờ anh. Đây là những chỗ nó không chắc, xếp theo lợi: việc ở
        trên sửa một lần được nhiều câu nhất. Cách đọc tên, người nói từng câu, hai tên của một người, giới và giọng nhân
        vật đều sửa được ngay tại đây, không phải dừng sách.
      </p>
      <div className="mt-4">
        <Segmented<WorkKind | "all">
          wrap
          label="Loại việc"
          value={kind}
          onChange={(value) => {
            setKind(value);
            setShown(PAGE);
          }}
          options={[
            { value: "all", label: `Tất cả · ${data.items.length}` },
            ...kinds.map((value) => ({ value, label: `${KIND_LABEL[value]} · ${data.counts[value]}` })),
          ]}
        />
      </div>
      <ol className={cn("mt-4 space-y-3")}>
        {items.slice(0, shown).map((item) => (
          <Card key={item.key} bookId={bookId} item={item} onOpenReview={onOpenReview} />
        ))}
      </ol>
      {items.length > shown && (
        <Button variant="secondary" size="sm" className="mt-4" onClick={() => setShown(shown + PAGE)}>
          Xem thêm {Math.min(PAGE, items.length - shown)} việc
        </Button>
      )}
    </div>
  );
}
