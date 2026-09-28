import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Play } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { useClip } from "@/listen/clip";
import { cn } from "@/shared/cn";
import { formatNumber } from "@/shared/format";
import { Button, Dialog, Segmented, Skeleton, Vu } from "@/shared/ui";
import { api, urls } from "./api";

// "Đổi giọng" một nhân vật (webui/voice_picker.py): mọi giọng dùng được cho nhân vật, nghe thử từng giọng, giọng đang dùng,
// giọng máy gợi ý cho từng giới, và ai đang dùng giọng ấy cùng mấy chương. Chọn xong đi đúng đường của thẻ "Nam hay nữ"
// (POST /voice): dây chuyền áp ở ranh giới chương kế tiếp, bậc âm sắc do bộ cấp giọng của bước phân vai quyết (không trùng
// người cùng chương), câu đã thu của người ấy được thu lại. Không phải dừng sách.

type Gender = "male" | "female";

interface VoiceOption {
  name: string;
  gender: Gender;
  genderLabel: string;
  region: string;
  style: string;
  preview: boolean;
  current: boolean;
  suggested: boolean;
  /** Người CÙNG CHƯƠNG với nhân vật đang dùng giọng gốc này (máy sẽ lấy bậc âm sắc khác họ). */
  sharedWith: { label: string; chapters: number }[];
  /** Số người khác dùng giọng gốc này mà không cùng chương. */
  otherUsers: number;
}

interface VoiceChoices {
  character: { value: string; label: string; gender: string; lines: number; chapters: number };
  current: string;
  voices: VoiceOption[];
}

function sharedText(voice: VoiceOption): string {
  const others = voice.otherUsers ? `${voice.otherUsers} người khác dùng, không cùng chương` : "";
  if (!voice.sharedWith.length) return others || "Chưa ai dùng";
  const people = voice.sharedWith.map((person) => `${person.label} (${person.chapters} chương)`).join(", ");
  return `Cùng chương với ${people} - máy lấy bậc âm sắc khác${others ? ` · ${others}` : ""}`;
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
  const save = useMutation({
    mutationFn: (voice: VoiceOption) =>
      api(`/api/books/${bookId}/voice`, { method: "POST", body: { character: data!.character.value, preset: voice.name } }),
    onSuccess: (_result, voice) => {
      void client.invalidateQueries({ queryKey: ["work", bookId] });
      void client.invalidateQueries({ queryKey: ["book", bookId] });
      void client.invalidateQueries({ queryKey: ["library"] });
      toast.success(`Đã ghi: ${data!.character.label} đọc bằng giọng ${voice.name}`, {
        description: "Mọi câu đã thu của người ấy sẽ đọc lại bằng giọng mới. Thu lại khi sách chạy tiếp - sách đã xong thì bấm “Áp dụng thay đổi” ở trang dự án.",
      });
      close();
    },
    onError: (failure: Error) => toast.error("Chưa đổi được giọng", { description: failure.message }),
  });
  const voices = (data?.voices ?? []).filter((voice) => voice.gender === shown);
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
          <Segmented<Gender>
            label="Giọng nam hay nữ"
            value={shown}
            onChange={setGender}
            options={[
              { value: "male", label: "Giọng nam" },
              { value: "female", label: "Giọng nữ" },
            ]}
          />
          <ul className="mt-3 max-h-[min(60vh,460px)] space-y-1 overflow-y-auto pr-1">
            {voices.map((voice) => (
              <li key={voice.name} className={cn("flex items-center gap-3 rounded-xl px-2 py-2", voice.current ? "bg-accent-soft" : "hover:bg-hover")}>
                <PreviewButton voice={voice} />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className="font-medium">{voice.name}</span>
                    {voice.current && <span className="rounded-full bg-panel px-2 py-px text-[11px] font-medium text-accent-text">Đang dùng</span>}
                    {voice.suggested && !voice.current && (
                      <span className="rounded-full bg-info-soft px-2 py-px text-[11px] font-medium text-info">Máy gợi ý</span>
                    )}
                  </div>
                  <div className={cn("mt-0.5 text-xs", voice.sharedWith.length ? "text-warning" : "text-fg-2")}>
                    Miền {voice.region} · {voice.style} · {sharedText(voice)}
                  </div>
                </div>
                <Button
                  size="sm"
                  variant={voice.suggested && !voice.current ? "primary" : "secondary"}
                  disabled={voice.current || save.isPending}
                  onClick={() => save.mutate(voice)}
                >
                  {voice.current ? "Đang dùng" : "Chọn"}
                </Button>
              </li>
            ))}
          </ul>
          <p className="mt-3 text-xs leading-relaxed text-fg-3">
            Giọng đang có người dùng vẫn chọn được: máy lấy bậc âm sắc khác để hai người không nghe giống nhau trong cùng
            chương. Chọn giọng khác giới là đổi luôn giới của nhân vật.
          </p>
        </>
      )}
    </Dialog>
  );
}
