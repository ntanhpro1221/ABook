import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { Button } from "@/shared/ui";
import { api } from "./api";
import { hasVocals, localDigest, vocalsLabel, type LocalMusicView, type LocalTrack } from "./musicLocal";

/** Dòng "Có vẻ có lời" của một bài trong Nhạc của tôi (đầu dò lời hát, music_local.py): máy không tự chọn bài này làm nền dưới giọng đọc, ghim tay thì
 *  vẫn được. `canOverride`: máy này tự chọn nhạc (máy tính) nên có nút "Vẫn dùng làm nhạc nền"; điện thoại không tự chọn nên chỉ hiện nhãn. */
export function VocalsNote({ track, canOverride, onView }: { track: LocalTrack; canOverride: boolean; onView: (view: LocalMusicView) => void }) {
  const allow = useMutation({
    mutationFn: (ok: boolean) => api<LocalMusicView>(`/api/music/local/${localDigest(track.link)}/vocals-ok`, { method: "POST", body: { ok } }),
    onSuccess: onView,
    onError: (error: Error) => toast.error("Không đổi được", { description: error.message }),
  });
  if (!hasVocals(track)) return null;
  const allowed = Boolean(track.vocalsOk);
  return (
    <span className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-fg-2">
      <span>{vocalsLabel(track)}</span>
      {canOverride && (
        <Button size="sm" variant="ghost" loading={allow.isPending} onClick={() => allow.mutate(!allowed)}>
          {allowed ? "Thôi, không dùng làm nhạc nền" : "Vẫn dùng làm nhạc nền"}
        </Button>
      )}
    </span>
  );
}
