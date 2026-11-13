import { S } from "../shared/strings.generated";
import { MotionRegion } from "@/shared/MotionRegion";
import { Fold } from "@/shared/Collapse";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useId, useRef, useState } from "react";
import { toast } from "@/shared/toast";
import { Button, ChoiceRow } from "@/shared/ui";
import { api } from "@/studio/api";
import { formatSize } from "@/shared/format";
import { desktopSupertonic, useModuleStatus, type VieneuBackend } from "./VieneuModuleCard";
import { SUPERTONIC_COPY, VOICE_SPEED_KEY } from "./vieneuModule";
import {
  needsFastDownload,
  VOICE_SPEED_OPTIONS,
  VOICE_SPEED_TITLE,
  voiceSpeedDescription,
  voiceSpeedLabel,
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
  if (!status) return <MotionRegion />;
  const choose = async (choice: VoiceSpeedChoice) => {
    setBusy(true);
    try {
      client.setQueryData(KEY, await backend.set(choice));
      // Thẻ mô-đun mời / thôi mời tải bản nhanh hơn theo lựa chọn mới.
      void client.invalidateQueries({ queryKey: ["readaloud", SUPERTONIC_COPY.key] });
    } catch (error) {
      toast.error(S.s_chua_doi_duoc_toc_do_giong_e3562390, { description: (error as Error).message });
    } finally {
      setBusy(false);
    }
  };
  const download = async (voice: VoiceSpeedVoice) => {
    try {
      client.setQueryData(["readaloud", SUPERTONIC_COPY.key], await supertonic.start([voice.fastChoice]));
    } catch (error) {
      toast.error(S.s_chua_tai_duoc_ban_nhanh_hon_0011ec37, { description: (error as Error).message });
    }
  };
  return (
    <MotionRegion><Fold storageKey="voice.performance" title={S.s_hieu_nang_8c7b7526} summary={voiceSpeedLabel(status.choice)} bodyClassName="space-y-2 pb-3">
      <h3 id={`${id}-title`} className="text-sm font-medium">{VOICE_SPEED_TITLE}</h3>
      <ChoiceRow
        value={status.choice}
        onChange={(choice) => void (busy || choose(choice))}
        options={VOICE_SPEED_OPTIONS}
        label={VOICE_SPEED_TITLE}
        wrap
      />
      <p className="text-body-small text-fg-2 text-pretty">{voiceSpeedDescription(status.choice)}</p>
      <ul className="space-y-2">
        {status.voices.map((voice) => {
          const downloading = supertonicCard.status?.state === "downloading";
          return (
            <li key={voice.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 text-body-small text-pretty">
              <span className="min-w-0 flex-1">{voiceSpeedLine(voice, status.choice)}</span>
              {needsFastDownload(voice) && (
                <Button size="sm" variant="ghost" loading={downloading} disabled={working} onClick={() => void download(voice)}>
                  {S.s_tai_0_3463a4d8(formatSize(voice.fastBytes))}
                </Button>
              )}
            </li>
          );
        })}
      </ul>
    </Fold></MotionRegion>
  );
}
