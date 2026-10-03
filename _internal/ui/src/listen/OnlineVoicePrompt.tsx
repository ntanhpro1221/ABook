import { useEffect, useState, useSyncExternalStore } from "react";
import { cn } from "@/shared/cn";
import { Button, Dialog } from "@/shared/ui";
import { onlinePromptText, pendingConsent, spokenVoiceName, subscribeConsent } from "./onlineConsent";

/** Hộp hỏi trước lần đầu đọc bằng giọng trực tuyến (onlineConsent.ts). Gắn một lần trong PlayerProvider - máy tính và điện thoại như nhau. */
export function OnlineVoicePrompt() {
  const request = useSyncExternalStore(subscribeConsent, pendingConsent);
  const [choosing, setChoosing] = useState(false);
  useEffect(() => setChoosing(false), [request]);
  if (!request) return null;
  const { voice, voices, answer } = request;
  return (
    <Dialog
      open
      onOpenChange={(open) => !open && answer(null)}
      title={choosing ? "Chọn giọng đọc" : "Giọng đọc trực tuyến"}
      description={choosing ? "Giọng của máy đọc ngay trên máy này, không gửi chữ đi đâu." : onlinePromptText(voice)}
      width="max-w-md"
    >
      {choosing ? (
        <div className="flex max-h-[50vh] flex-col gap-0.5 overflow-y-auto">
          {voices.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => answer(item.id)}
              className={cn(
                "flex min-h-[44px] items-center justify-between gap-2 rounded-lg px-3 text-left text-sm hover:bg-hover",
                item.id === voice.id && "font-semibold",
              )}
            >
              <span className="truncate">{spokenVoiceName(item.name)}</span>
              <span className="shrink-0 text-xs font-normal text-fg-2">{item.online ? "trực tuyến" : "của máy"}</span>
            </button>
          ))}
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
