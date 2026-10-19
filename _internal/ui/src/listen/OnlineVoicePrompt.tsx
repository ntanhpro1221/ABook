import { Play, Square } from "lucide-react";
import { useEffect, useState, useSyncExternalStore } from "react";
import { cn } from "@/shared/cn";
import { Button, Dialog } from "@/shared/ui";
import { chooseVoiceText, onlinePromptText, pendingConsent, spokenVoiceName, subscribeConsent } from "./onlineConsent";
import { useNowPlaying } from "./player";
import { useSource } from "./source";
import { useVoiceSample } from "./VoiceSettings";
import { revealVoiceSettings } from "./voiceSettingsLink";

/** Hộp hỏi trước lần đầu đọc bằng giọng trực tuyến (onlineConsent.ts). Gắn một lần trong PlayerProvider - máy tính và điện thoại như nhau. */
export function OnlineVoicePrompt() {
  const request = useSyncExternalStore(subscribeConsent, pendingConsent);
  const [choosing, setChoosing] = useState(false);
  const { setExpanded } = useNowPlaying();
  // Nghe thử từng giọng trước khi chọn - cùng câu mẫu và cùng đường với nút "Thử giọng" của Cài đặt (soát a64).
  const source = useSource();
  const sample = useVoiceSample((voice, text) => (source.readAloudSample ? source.readAloudSample(voice, text) : Promise.reject(new Error("Chưa nghe thử được giọng này."))));
  useEffect(() => setChoosing(false), [request]);
  if (!request) return null;
  const { voice, voices, answer } = request;
  return (
    <Dialog
      open
      onOpenChange={(open) => !open && answer(null)}
      title={choosing ? "Chọn giọng đọc" : "Giọng đọc trực tuyến"}
      description={choosing ? chooseVoiceText(voices, voice) : onlinePromptText(voice)}
      width="max-w-md"
    >
      {choosing ? (
        <div className="flex max-h-[50vh] flex-col gap-0.5 overflow-y-auto">
          {voices.map((item) => {
            const playing = sample.playing === item.id;
            return (
              <div key={item.id}>
                <div className="flex items-center gap-1">
                  <button
                    type="button"
                    onClick={() => {
                      sample.stop();
                      answer(item.id, true);
                    }}
                    className={cn(
                      "flex min-h-[44px] min-w-0 flex-1 items-center justify-between gap-2 rounded-lg px-3 text-left text-sm hover:bg-hover",
                      item.id === voice.id && "font-semibold",
                    )}
                  >
                    <span className="truncate">{spokenVoiceName(item.name)}</span>
                    <span className="shrink-0 text-xs font-normal text-fg-2">{item.online ? "trực tuyến" : "của máy"}</span>
                  </button>
                  {source.readAloudSample && (
                    <Button
                      size="sm"
                      variant="ghost"
                      className="touch-row shrink-0"
                      icon={playing ? Square : Play}
                      loading={sample.loading === item.id}
                      onClick={() => (playing ? sample.stop() : void sample.play(item.id))}
                      aria-label={`${playing ? "Dừng" : "Nghe thử"} giọng ${spokenVoiceName(item.name)}`}
                    >
                      {playing ? "Dừng" : "Nghe thử"}
                    </Button>
                  )}
                </div>
                {sample.failed?.voice === item.id && <p className="px-3 pb-1 text-[0.8125rem] text-danger text-pretty" role="alert">{sample.failed.message}</p>}
              </div>
            );
          })}
          {/* Danh sách chỉ có giọng ĐANG dùng được; giọng chạy trên máy (VieNeu, Supertonic) chưa tải thì không có mặt - chỉ đường tới nơi tải, hộp chưa phát gì. */}
          <button
            type="button"
            onClick={() => {
              request.answer(null);
              setExpanded(false);
              // Hộp nằm ngoài Router (PlayerProvider bao ngoài HashRouter): đổi trang bằng địa chỉ, Router tự theo.
              window.location.hash = "#/settings";
              revealVoiceSettings("vieneu-module");
            }}
            className="mt-1 flex min-h-[44px] flex-col items-start justify-center rounded-lg border-t border-line px-3 py-2 text-left text-sm text-accent-text hover:bg-hover"
          >
            <span>Tải giọng chạy trên máy…</span>
            <span className="text-xs font-normal text-fg-2">VieNeu, Supertonic - đọc được cả khi không có mạng</span>
          </button>
        </div>
      ) : (
        <div className="flex flex-wrap justify-end gap-2">
          <Button variant="ghost" onClick={() => setChoosing(true)}>
            Chọn giọng khác
          </Button>
          <Button variant="primary" data-autofocus onClick={() => answer(voice.id)}>
            Nghe
          </Button>
        </div>
      )}
    </Dialog>
  );
}
