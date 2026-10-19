import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useId, useRef, useState } from "react";
import { toast } from "sonner";
import { Button, Segmented } from "@/shared/ui";
import { api } from "@/studio/api";
import { formatSize } from "@/studio/musicLocal";
import { desktopSupertonic, useModuleStatus, type VieneuBackend } from "./VieneuModuleCard";
import { SUPERTONIC_COPY, VOICE_SPEED_KEY } from "./vieneuModule";
import {
  needsFastDownload,
  VOICE_SPEED_OPTIONS,
  VOICE_SPEED_TITLE,
  voiceSpeedDescription,
  voiceSpeedLine,
  type VoiceSpeedChoice,
  type VoiceSpeedStatus,
  type VoiceSpeedVoice,
} from "./voiceSpeed";

/** Nơi cài đặt sống: máy tính hỏi máy chủ cục bộ, điện thoại hỏi plugin ReadAloud (android/SettingsScreen.tsx). Cùng hình trạng thái. */
export interface VoiceSpeedBackend {
  status(): Promise<VoiceSpeedStatus>;
  set(choice: VoiceSpeedChoice): Promise<VoiceSpeedStatus>;
}

export const desktopVoiceSpeed: VoiceSpeedBackend = {
  status: () => api<VoiceSpeedStatus>("/api/readaloud/voice-speed"),
  set: (choice) => api<VoiceSpeedStatus>("/api/readaloud/voice-speed", { method: "POST", body: { choice } }),
};

const KEY = VOICE_SPEED_KEY;

/** "Tốc độ giọng trên máy": Tự động / Chất lượng cao nhất / Nhanh hơn, một lựa chọn cho cả máy; dưới đó mỗi giọng đã tải nói đang dùng bậc nào và vì sao.
 *  Muốn bậc nhanh mà chưa có bản nhanh hơn: nút tải kèm cỡ (tải qua thẻ của mô-đun ấy, nên tiến độ hiện ở thẻ). Chỉ giọng Supertonic có hai bậc;
 *  chưa tải Supertonic thì cài đặt vẫn hiện, chỉ không có dòng giọng nào. */
export function VoiceSpeedSetting({
  backend = desktopVoiceSpeed,
  supertonic = desktopSupertonic,
}: { backend?: VoiceSpeedBackend; supertonic?: VieneuBackend } = {}) {
  const client = useQueryClient();
  const id = useId();
  const [busy, setBusy] = useState(false);
  const { data: status } = useQuery({ queryKey: KEY, queryFn: () => backend.status() });
  // Thẻ mô-đun tải / đo xong (cùng khoá truy vấn với thẻ): số đo hay bản nhanh hơn vừa đổi - hỏi lại dòng này.
  const supertonicCard = useModuleStatus(supertonic, SUPERTONIC_COPY);
  const working = supertonicCard.working;
  const wasWorking = useRef(false);
  useEffect(() => {
    if (wasWorking.current && !working) void client.invalidateQueries({ queryKey: KEY });
    wasWorking.current = working;
  }, [working, client]);
  if (!status) return null;
  const choose = async (choice: VoiceSpeedChoice) => {
    setBusy(true);
    try {
      client.setQueryData(KEY, await backend.set(choice));
      // Thẻ mô-đun mời / thôi mời tải bản nhanh hơn theo lựa chọn mới.
      void client.invalidateQueries({ queryKey: ["readaloud", SUPERTONIC_COPY.key] });
    } catch (error) {
      toast.error("Chưa đổi được tốc độ giọng", { description: (error as Error).message });
    } finally {
      setBusy(false);
    }
  };
  const download = async (voice: VoiceSpeedVoice) => {
    try {
      client.setQueryData(["readaloud", SUPERTONIC_COPY.key], await supertonic.start([voice.fastChoice]));
    } catch (error) {
      toast.error("Chưa tải được bản nhanh hơn", { description: (error as Error).message });
    }
  };
  return (
    <div className="max-w-xl space-y-2">
      <h3 id={`${id}-title`} className="text-sm font-semibold">{VOICE_SPEED_TITLE}</h3>
      <Segmented
        value={status.choice}
        onChange={(choice) => void (busy || choose(choice))}
        options={VOICE_SPEED_OPTIONS}
        label={VOICE_SPEED_TITLE}
        wrap
      />
      <p className="text-[0.8125rem] text-fg-2 text-pretty">{voiceSpeedDescription(status.choice)}</p>
      <ul className="space-y-1.5">
        {status.voices.map((voice) => {
          const downloading = supertonicCard.status?.state === "downloading";
          return (
            <li key={voice.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[0.8125rem] text-pretty">
              <span className="min-w-0 flex-1">{voiceSpeedLine(voice, status.choice)}</span>
              {needsFastDownload(voice) && (
                <Button size="sm" variant="secondary" loading={downloading} disabled={working} onClick={() => void download(voice)}>
                  {`Tải (${formatSize(voice.fastBytes)})`}
                </Button>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
