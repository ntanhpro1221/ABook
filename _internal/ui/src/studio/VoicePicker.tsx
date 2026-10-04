import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Play } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { useClip } from "@/listen/clip";
import { cn } from "@/shared/cn";
import { formatNumber } from "@/shared/format";
import { Button, Dialog, Progress, Segmented, Skeleton, Vu } from "@/shared/ui";
import { api, urls } from "./api";
import { refreshAfterDecision, UNDO_MS, undoAction, useWhenApplied } from "./decisions";
import { modulePercent } from "./musicLocal";
import { groupByEngine, moduleNote, sharedText, type EngineModuleStatus, type EngineVoice } from "./voiceEngines";

// "Đổi giọng" một nhân vật (webui/voice_picker.py): mọi giọng dùng được cho nhân vật, nghe thử từng giọng, giọng đang dùng,
// giọng máy gợi ý cho từng giới, và ai đang dùng giọng ấy cùng mấy chương. Chọn xong đi đúng đường của thẻ "Nam hay nữ"
// (POST /voice): dây chuyền áp ở ranh giới chương kế tiếp, bậc âm sắc do bộ cấp giọng của bước phân vai quyết (không trùng
// người cùng chương), câu đã thu của người ấy được thu lại. Không phải dừng sách. Giọng nhóm theo máy đọc: VieNeu (mọi giọng phân vai
// tự động) rồi máy khác chỉ chọn tay (ZeroTTS, Supertonic - tải thêm một lần, nút tải ngay trong hộp).

type Gender = "male" | "female";

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
}

interface VoiceChoices {
  character: { value: string; label: string; gender: string; lines: number; chapters: number };
  current: string;
  /** Lựa chọn chưa vào sách (tên giọng nó sẽ thành; "" khi chưa biết) - bỏ được bằng `requestedAt` như "Hoàn tác". */
  pending: { name: string; requestedAt: number } | null;
  voices: VoiceOption[];
  /** Mô-đun tải thêm của máy đọc khác, theo tên máy. */
  modules?: Record<string, EngineModuleStatus>;
}

function voiceMeta(voice: VoiceOption): string {
  const about = voice.description || [voice.region ? `Miền ${voice.region}` : "", voice.style].filter(Boolean).join(" · ");
  return `${about} · ${sharedText(voice)}`;
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
  const note = moduleNote(current);
  return (
    <div className="sticky top-0 z-10 bg-panel pb-1 pt-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-xs font-semibold uppercase tracking-wide text-fg-3">{label}</span>
        {current && ["missing", "error", "outdated"].includes(current.state) && (
          <Button size="sm" variant="secondary" loading={start.isPending} onClick={() => start.mutate()}>
            {current.state === "error" ? "Tải lại" : "Tải giọng"}
          </Button>
        )}
      </div>
      {note && <p className={cn("mt-0.5 text-xs", current?.state === "error" ? "text-danger" : "text-fg-2")}>{note}</p>}
      {current?.state === "downloading" && <Progress className="mt-1" size="xs" running value={modulePercent(current) / 100} label={note ?? ""} />}
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
  const [gender, setGender] = useState<Gender | null>(null);
  useEffect(() => setGender(null), [person?.name]);
  const currentGender = data?.voices.find((voice) => voice.current)?.gender;
  const shown: Gender = gender ?? currentGender ?? (data?.character.gender === "female" ? "female" : "male");
  const close = () => {
    clip.stop();
    onClose();
  };
  const when = useWhenApplied(bookId);
  // Tên như tiêu đề hộp ("Oliver"), không phải khoá sổ in hoa ("OLIVER") - soát UX 30-09.
  const name = person?.displayName || data?.character.label || "";
  const save = useMutation({
    mutationFn: (voice: VoiceOption) =>
      api<{ requestedAt: number }>(`/api/books/${bookId}/voice`, { method: "POST", body: { character: data!.character.value, preset: voice.name } }),
    onSuccess: ({ requestedAt }, voice) => {
      // Dòng nhân vật hiện "Chờ áp dụng" ngay (store.pending_voices), không đợi lần làm mới sau 60 giây.
      refreshAfterDecision(client, bookId);
      const character = data!.character;
      // Chọn nhầm giọng trong danh sách dài: "Hoàn tác" như thẻ giọng trong hộp việc (studio/decisions.ts).
      toast.success(`Đã ghi: ${name} đọc bằng giọng ${voice.name}`, {
        description: `Mọi câu đã thu của người ấy sẽ đọc lại bằng giọng mới. ${when}`,
        action: undoAction(
          client,
          bookId,
          "voice",
          [{ character: character.value, requestedAt, keep: false }],
          // Không nói tên giọng cũ: người ấy có thể đang có một giọng chờ áp khác, và hoàn tác trả về đúng giọng chờ ấy.
          `Giọng của ${name} trở lại như trước khi đổi.`,
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
  const voices = (data?.voices ?? []).filter((voice) => voice.gender === shown);
  const groups = groupByEngine(voices);
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
          <Segmented<Gender>
            label="Giọng nam hay nữ"
            value={shown}
            onChange={setGender}
            options={[
              { value: "male", label: "Giọng nam" },
              { value: "female", label: "Giọng nữ" },
            ]}
          />
          <div className="mt-3 max-h-[min(60vh,460px)] overflow-y-auto pr-1">
            {groups.map((group) => (
              <section key={group.engine} aria-label={`Giọng ${group.label}`}>
                {groups.length > 1 || group.engine !== "vieneu" ? (
                  <EngineHeader engine={group.engine} label={group.label} status={data.modules?.[group.engine]} onReady={reload} />
                ) : null}
                <ul className="space-y-1">
            {group.voices.map((voice) => (
              <li key={voice.name} className={cn("flex items-center gap-3 rounded-xl px-2 py-2", voice.current ? "bg-accent-soft" : "hover:bg-hover")}>
                <PreviewButton voice={voice} />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className="font-medium">{voice.name}</span>
                    {voice.current && <span className="rounded-full bg-panel px-2 py-px text-[11px] font-medium text-accent-text">Đang dùng</span>}
                    {voice.pending && !voice.current && (
                      <span className="rounded-full bg-warning-soft px-2 py-px text-[11px] font-medium text-warning">Chờ áp dụng</span>
                    )}
                    {voice.suggested && !voice.current && !voice.pending && (
                      <span className="rounded-full bg-info-soft px-2 py-px text-[11px] font-medium text-info">Máy gợi ý</span>
                    )}
                  </div>
                  <div className={cn("mt-0.5 text-xs", voice.sharedWith.length ? "text-warning" : "text-fg-2")}>{voiceMeta(voice)}</div>
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
                    disabled={voice.current || voice.pending || !voice.installed || save.isPending || keep.isPending}
                    onClick={() => save.mutate(voice)}
                  >
                    {voice.current ? "Đang dùng" : voice.pending ? "Đã chọn" : "Chọn"}
                  </Button>
                )}
              </li>
            ))}
                </ul>
              </section>
            ))}
          </div>
          <p className="mt-3 text-xs leading-relaxed text-fg-3">
            Giọng đang có người dùng vẫn chọn được: máy lấy bậc âm sắc khác để hai người không nghe giống nhau trong cùng
            chương. Chọn giọng khác giới là đổi luôn giới của nhân vật. Giọng ZeroTTS và Supertonic chỉ có một âm sắc: hai người
            cùng chương chung giọng ấy sẽ nghe giống hệt nhau.
          </p>
        </>
      )}
    </Dialog>
  );
}
