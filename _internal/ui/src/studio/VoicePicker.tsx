import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Play } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { useClip } from "@/listen/clip";
import { cn } from "@/shared/cn";
import { excerpt, formatNumber } from "@/shared/format";
import { Button, Dialog, Progress, Segmented, Skeleton, Vu } from "@/shared/ui";
import { api, urls } from "./api";
import { refreshAfterDecision, UNDO_MS, undoAction, useWhenApplied } from "./decisions";
import { modulePercent } from "./musicLocal";
import { groupByEngine, moduleNote, plainGroupLabels, sharedText, takenText, type EngineModuleStatus, type EngineVoice } from "./voiceEngines";
import { useVoiceTry } from "./VoiceTry";
import { byGender, rerecordText, type GenderFilter, type Rerecord } from "./voiceTryText";

// "Đổi giọng" một nhân vật (webui/voice_picker.py): mọi giọng dùng được cho nhân vật, nghe thử từng giọng, giọng đang dùng,
// giọng máy gợi ý cho từng giới, và ai đang dùng giọng ấy cùng mấy chương. Chọn xong đi đúng đường của thẻ "Nam hay nữ"
// (POST /voice): dây chuyền áp ở ranh giới chương kế tiếp, bậc âm sắc do bộ cấp giọng của bước phân vai quyết (không trùng
// người cùng chương), câu đã thu của người ấy được thu lại. Không phải dừng sách. Giọng nhóm theo máy đọc: VieNeu (mọi giọng phân vai
// tự động) rồi máy khác chỉ chọn tay (ZeroTTS, Supertonic - tải thêm một lần, nút tải ngay trong hộp). Soát UX Studio mục 13:
// mỗi giọng nghe được cả câu mẫu chung (▶) lẫn một câu của chính nhân vật đọc bằng giọng ấy (VoiceTry.tsx), lọc Nam / Nữ / Tất
// cả, và hộp nói trước đổi giọng sẽ thu lại bao nhiêu câu, hết chừng bao lâu. Người kể dùng chính hộp này (soát UX a23, B21:
// voice_picker.narrator_choices) - giọng kể chuyện của danh mục, giọng nhân vật đang giữ thì không chọn được, không hỏi giới.

type Gender = "male" | "female";
const GENDER_WORD: Record<Gender, string> = { male: "nam", female: "nữ" };

interface VoiceOption extends EngineVoice {
  gender: Gender;
  genderLabel: string;
  region: string;
  style: string;
  preview: boolean;
  current: boolean;
  /** Giọng người nghe đã chọn mà chưa vào sách. */
  pending: boolean;
  suggested: boolean;
  /** Chất giọng của giọng máy khác ("Nữ · Trưởng thành · Rõ ràng"); rỗng với VieNeu (đã có miền + phong cách). */
  description: string;
  /** Chỉ hộp người kể: nhân vật đang giữ giọng này - không chọn được. */
  takenBy?: string[];
}

interface VoiceChoices {
  character: { value: string; label: string; gender: string; lines: number; chapters: number };
  current: string;
  /** Lựa chọn chưa vào sách (tên giọng nó sẽ thành; "" khi chưa biết) - bỏ được bằng `requestedAt` như "Hoàn tác". */
  pending: { name: string; requestedAt: number } | null;
  voices: VoiceOption[];
  /** Mô-đun tải thêm của máy đọc khác, theo tên máy. */
  modules?: Record<string, EngineModuleStatus>;
  /** Câu "Nghe thử bằng câu của sách" sẽ đọc; null: người này chưa có câu nào - chỉ có câu mẫu chung. */
  tryLine?: { segmentId: number; text: string } | null;
  /** Đổi giọng là thu lại mọi câu đã thu của người này. */
  rerecord?: Rerecord;
}

/** `withGender`: lọc "Tất cả" - giọng nam và nữ chung một danh sách, nên nói giới ra. */
function voiceMeta(voice: VoiceOption, withGender = false): string {
  const parts = voice.description ? [voice.description] : [voice.region ? `Miền ${voice.region}` : "", voice.style];
  // Chất giọng của máy khác đã mở đầu bằng giới ("Nữ · Trưởng thành"): không nói hai lần.
  const about = [withGender && !voice.description ? voice.genderLabel : "", ...parts].filter(Boolean).join(" · ");
  return `${about} · ${voice.takenBy?.length ? takenText(voice.takenBy) : sharedText(voice, voice.current)}`;
}

/** Tên nhóm của một máy đọc, và - khi máy chưa có giọng ấy - lời nhắn + nút tải (tiến độ hỏi lại mỗi giây). */
function EngineHeader({ engine, label, status, onReady }: { engine: string; label: string; status?: EngineModuleStatus; onReady: () => void }) {
  const client = useQueryClient();
  const { data } = useQuery({
    queryKey: ["engine-module", engine],
    queryFn: () => api<EngineModuleStatus>(`/api/studio/${engine}`),
    initialData: status,
    enabled: status !== undefined,
    refetchInterval: (query) => (query.state.data?.state === "downloading" ? 1000 : false),
  });
  const current = data ?? status;
  useEffect(() => {
    if (status && status.state !== "ready" && current?.state === "ready") onReady();
  }, [current?.state, status, onReady]);
  const start = useMutation({
    mutationFn: () => api<EngineModuleStatus>(`/api/studio/${engine}`, { method: "POST", body: {} }),
    onSuccess: (next) => client.setQueryData(["engine-module", engine], next),
    onError: (failure: Error) => toast.error("Chưa tải được giọng", { description: failure.message }),
  });
  const cancel = useMutation({
    mutationFn: () => api<EngineModuleStatus>(`/api/studio/${engine}/cancel`, { method: "POST", body: {} }),
    onSuccess: (next) => client.setQueryData(["engine-module", engine], next),
    onError: (failure: Error) => toast.error("Chưa huỷ được việc tải giọng", { description: failure.message }),
  });
  const note = moduleNote(current);
  return (
    <div className="sticky top-0 z-10 bg-panel pb-1 pt-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-xs font-semibold tracking-wide text-fg-3">{label}</span>
        {current && ["missing", "error", "outdated"].includes(current.state) && (
          <Button size="sm" variant="secondary" loading={start.isPending} onClick={() => start.mutate()}>
            {current.state === "error" ? "Tải lại" : "Tải giọng"}
          </Button>
        )}
      </div>
      {note && <p className={cn("mt-0.5 text-xs", current?.state === "error" ? "text-danger" : "text-fg-2")}>{note}</p>}
      {current?.state === "downloading" && (
        <div className="mt-1 flex items-center gap-3">
          <Progress size="xs" running value={modulePercent(current) / 100} label={note ?? ""} className="flex-1" />
          {current.cancellable && (
            <Button size="sm" variant="ghost" loading={cancel.isPending} onClick={() => cancel.mutate()}>
              Huỷ
            </Button>
          )}
        </div>
      )}
    </div>
  );
}

function PreviewButton({ voice }: { voice: VoiceOption }) {
  const clip = useClip();
  const id = `voice-${voice.name}`;
  const active = clip.current === id;
  if (!voice.preview) return <span className="size-9 shrink-0" aria-hidden />;
  return (
    <button
      type="button"
      onClick={() => clip.toggle(id, urls.voice(voice.name))}
      aria-label={active ? "Dừng nghe thử" : `Nghe thử giọng ${voice.name}`}
      className={cn(
        "grid size-9 shrink-0 place-items-center rounded-full border transition-colors",
        active ? "border-accent bg-accent text-accent-ink" : "border-line text-fg-2 hover:border-line-strong hover:text-fg",
      )}
    >
      {active && clip.loading ? <Loader2 className="size-4 animate-spin" /> : active ? <Vu className="h-3" /> : <Play className="size-3.5 translate-x-[1px]" fill="currentColor" strokeWidth={0} />}
    </button>
  );
}

export function VoicePicker({
  bookId,
  person,
  onClose,
}: {
  bookId: string;
  person: { name: string; displayName: string } | null;
  onClose: () => void;
}) {
  const client = useQueryClient();
  const clip = useClip();
  const { data, isLoading, error } = useQuery({
    queryKey: ["voice-choices", bookId, person?.name],
    queryFn: () => api<VoiceChoices>(`/api/books/${bookId}/voices?character=${encodeURIComponent(person!.name)}`),
    enabled: person !== null,
  });
  const [gender, setGender] = useState<GenderFilter | null>(null);
  useEffect(() => setGender(null), [person?.name]);
  const currentGender = data?.voices.find((voice) => voice.current)?.gender;
  const shown: GenderFilter = gender ?? currentGender ?? (data?.character.gender === "female" ? "female" : "male");
  const tryVoice = useVoiceTry(bookId);
  const close = () => {
    clip.stop();
    onClose();
  };
  const when = useWhenApplied(bookId);
  // Tên như tiêu đề hộp ("Oliver"), không phải khoá sổ in hoa ("OLIVER") - soát UX 30-09.
  const name = person?.displayName || data?.character.label || "";
  const narrator = data?.character.value === "NARRATOR";
  // Giọng khác giới với nhân vật: hỏi ngay trong hộp trước khi ghi (soát UX a13 #4) - đổi giọng khác giới là đổi luôn giới của người ấy.
  const [crossing, setCrossing] = useState<VoiceOption | null>(null);
  useEffect(() => setCrossing(null), [person?.name]);
  const save = useMutation({
    mutationFn: ({ voice, withGender }: { voice: VoiceOption; withGender: boolean }) =>
      api<{ requestedAt: number }>(`/api/books/${bookId}/voice`, {
        method: "POST",
        // Có `gender` thì giới ghi cùng giọng (cùng đường overrides `voices`): dòng "chờ áp dụng" ở tab Nhân vật hiện giới mới.
        body: { character: data!.character.value, preset: voice.name, ...(withGender ? { gender: voice.gender } : {}) },
      }),
    onSuccess: ({ requestedAt }, { voice, withGender }) => {
      // Dòng nhân vật hiện "Chờ áp dụng" ngay (store.pending_voices), không đợi lần làm mới sau 60 giây.
      refreshAfterDecision(client, bookId);
      const character = data!.character;
      const who = narrator ? "người kể" : "người ấy";
      // Chọn nhầm giọng trong danh sách dài: "Hoàn tác" như thẻ giọng trong hộp việc (studio/decisions.ts).
      toast.success(`Đã ghi: ${name} đọc bằng giọng ${voice.name}${withGender ? ` và là ${GENDER_WORD[voice.gender]}` : ""}`, {
        description: `${data!.rerecord?.lines ? `Thu lại ${formatNumber(data!.rerecord.lines)} câu đã thu của ${who} bằng giọng mới.` : `Chưa câu nào của ${who} được thu nên không phải thu lại gì.`} ${when}`,
        action: undoAction(
          client,
          bookId,
          "voice",
          [{ character: character.value, requestedAt, keep: false }],
          // Không nói tên giọng cũ: người ấy có thể đang có một giọng chờ áp khác, và hoàn tác trả về đúng giọng chờ ấy.
          `Giọng${withGender ? " và giới" : ""} của ${name} trở lại như trước khi đổi.`,
        ),
        duration: UNDO_MS,
      });
      close();
    },
    onError: (failure: Error) => toast.error("Chưa đổi được giọng", { description: failure.message }),
  });
  // Bỏ lựa chọn chưa vào sách - cùng đường "Hoàn tác" (POST /voice withdraw), dùng được bất cứ lúc nào trước khi máy áp.
  const keep = useMutation({
    mutationFn: (pending: { name: string; requestedAt: number }) =>
      api<{ undone: number }>(`/api/books/${bookId}/voice`, {
        method: "POST",
        body: { character: data!.character.value, withdraw: true, requestedAt: pending.requestedAt },
      }),
    onSuccess: (_answer, pending) => {
      refreshAfterDecision(client, bookId);
      toast.success(pending.name ? `Đã bỏ lựa chọn ${pending.name}` : "Đã bỏ lựa chọn giọng", {
        description: `Giọng của ${name} trở lại như trước khi chọn.`,
      });
      close();
    },
    onError: (failure: Error) => toast.error("Chưa bỏ được lựa chọn", { description: failure.message }),
  });
  // Chọn một giọng: cùng giới (hay chưa biết giới) ghi luôn; khác giới thì hỏi trước. Người kể không có giới để đổi.
  const choose = (voice: VoiceOption) => {
    const known = data?.character.gender;
    if (!narrator && (known === "male" || known === "female") && known !== voice.gender) setCrossing(voice);
    else save.mutate({ voice, withGender: false });
  };
  const voices = byGender(data?.voices ?? [], shown);
  const groups = groupByEngine(voices);
  const groupLabels = plainGroupLabels(groups);
  const reload = () => client.invalidateQueries({ queryKey: ["voice-choices", bookId, person?.name] });
  return (
    <Dialog
      open={person !== null}
      onOpenChange={(open) => {
        if (!open) close();
      }}
      title={`Giọng của ${person?.displayName ?? ""}`}
      description={
        data
          ? `${formatNumber(data.character.lines)} câu ở ${data.character.chapters} chương · đang đọc bằng ${data.current || "chưa có giọng"}`
          : undefined
      }
      width="max-w-xl"
    >
      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 5 }, (_, index) => (
            <Skeleton key={index} className="h-12 rounded-xl" />
          ))}
        </div>
      ) : error || !data ? (
        <p className="text-sm text-danger">{(error as Error | null)?.message ?? "Không đọc được danh sách giọng."}</p>
      ) : (
        <>
          {data.pending && (
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2 rounded-xl bg-warning-soft px-3 py-2 text-sm">
              <span className="text-pretty">
                Chờ áp dụng: đổi sang <span className="font-medium">{data.pending.name || "giọng khác"}</span>
              </span>
              <Button size="sm" variant="secondary" loading={keep.isPending} disabled={save.isPending} onClick={() => keep.mutate(data.pending!)}>
                Giữ {data.current || "giọng đang dùng"}
              </Button>
            </div>
          )}
          {data.rerecord && <p className="mb-2 text-sm text-pretty text-fg-2">{rerecordText(name, data.rerecord)}</p>}
          {crossing && (
            <div role="alert" className="mb-3 rounded-xl bg-warning-soft px-3 py-2 text-sm">
              <p className="text-pretty">
                {name} đang là {GENDER_WORD[data.character.gender as Gender]} - giọng {crossing.name} là giọng {GENDER_WORD[crossing.gender]}. Đổi cả giới của {name} thành {GENDER_WORD[crossing.gender]}?
              </p>
              <div className="mt-2 flex flex-wrap gap-2">
                <Button size="sm" variant="primary" loading={save.isPending} onClick={() => save.mutate({ voice: crossing, withGender: true })}>
                  Đổi giọng và giới
                </Button>
                <Button size="sm" variant="ghost" disabled={save.isPending} onClick={() => setCrossing(null)}>
                  Thôi, giữ như cũ
                </Button>
              </div>
            </div>
          )}
          <Segmented<GenderFilter>
            label="Lọc giọng theo giới"
            value={shown}
            onChange={setGender}
            options={[
              { value: "male", label: "Nam" },
              { value: "female", label: "Nữ" },
              { value: "all", label: "Tất cả" },
            ]}
          />
          <div className="mt-2 space-y-0.5">
            <p className="text-xs text-pretty text-fg-3">
              {data.tryLine
                ? `Nút sách đọc câu “${excerpt(data.tryLine.text, 70)}” của ${name} bằng giọng ấy; nút ▶ là câu mẫu chung.`
                : `${name} chưa có câu nào để đọc thử - nút ▶ là câu mẫu chung của giọng.`}
            </p>
            {tryVoice.note}
          </div>
          <div className="mt-3 max-h-[min(60vh,460px)] overflow-y-auto pr-1">
            {groups.map((group, index) => (
              <section key={group.engine} aria-label={groupLabels[index]}>
                {groups.length > 1 || group.engine !== "vieneu" ? (
                  <EngineHeader engine={group.engine} label={groupLabels[index]} status={data.modules?.[group.engine]} onReady={reload} />
                ) : null}
                <ul className="space-y-1">
            {group.voices.map((voice) => (
              <li key={voice.name} className={cn("flex items-center gap-3 rounded-xl px-2 py-2", voice.current ? "bg-accent-soft" : "hover:bg-hover")}>
                <PreviewButton voice={voice} />
                {data.tryLine &&
                  tryVoice.button({ character: data.character.value, preset: voice.name }, voice.name, {
                    fallbackUrl: voice.preview ? urls.voice(voice.name) : undefined,
                    compact: true,
                    disabled: !voice.installed,
                  })}
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className={cn("font-medium", voice.takenBy?.length && "text-fg-2")}>{voice.name}</span>
                    {voice.current && <span className="rounded-full bg-panel px-2 py-px text-[11px] font-medium text-accent-text">Đang dùng</span>}
                    {voice.pending && !voice.current && (
                      <span className="rounded-full bg-warning-soft px-2 py-px text-[11px] font-medium text-warning">Chờ áp dụng</span>
                    )}
                    {voice.suggested && !voice.current && !voice.pending && (
                      <span className="rounded-full bg-info-soft px-2 py-px text-[11px] font-medium text-info">Máy gợi ý</span>
                    )}
                  </div>
                  <div className={cn("mt-0.5 text-xs", voice.sharedWith.length && !voice.takenBy?.length ? "text-warning" : "text-fg-2")}>
                    {voiceMeta(voice, shown === "all")}
                  </div>
                </div>
                {voice.current && data.pending ? (
                  // Đã chọn giọng khác mà chưa vào sách: giọng đang dùng chọn lại được - là bỏ lựa chọn kia.
                  <Button size="sm" variant="secondary" loading={keep.isPending} disabled={save.isPending} onClick={() => keep.mutate(data.pending!)}>
                    Giữ giọng này
                  </Button>
                ) : (
                  <Button
                    size="sm"
                    variant={voice.suggested && !voice.current && !voice.pending ? "primary" : "secondary"}
                    disabled={voice.current || voice.pending || !voice.installed || Boolean(voice.takenBy?.length) || save.isPending || keep.isPending}
                    onClick={() => choose(voice)}
                  >
                    {voice.current ? "Đang dùng" : voice.pending ? "Đã chọn" : voice.takenBy?.length ? "Nhân vật dùng" : "Chọn"}
                  </Button>
                )}
              </li>
            ))}
                </ul>
              </section>
            ))}
          </div>
          {narrator ? (
            <p className="mt-3 text-xs leading-relaxed text-fg-3">
              Người kể cần giọng riêng nên giọng nhân vật đang dùng không chọn được. Câu kể đã thu được thu lại bằng giọng mới; câu
              chưa thu đọc luôn bằng giọng mới. Không phải tạo lại sách.
            </p>
          ) : (
            <p className="mt-3 text-xs leading-relaxed text-fg-3">
              Giọng đang có người dùng vẫn chọn được: máy lấy bậc âm sắc khác để hai người không nghe giống nhau trong cùng
              chương. Chọn giọng khác giới thì hộp hỏi trước, vì đó là đổi luôn giới của nhân vật. Các giọng thêm chỉ có một âm sắc: hai người cùng chương
              chung giọng ấy sẽ nghe giống hệt nhau.
            </p>
          )}
        </>
      )}
    </Dialog>
  );
}
