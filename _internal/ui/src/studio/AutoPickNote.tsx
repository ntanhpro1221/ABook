import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { Button } from "@/shared/ui";
import { api } from "./api";
import { autoLabel, autoSwitch, localDigest, type LocalMusicView, type LocalTrack } from "./musicLocal";

/** Dòng tự chọn của một bài trong Nhạc của tôi (công tắc `auto`, music_local.py): nhãn khi bài không được máy tự chọn (có vẻ có lời hay bạn đã tắt) và
 *  nút đổi công tắc. `canOverride`: máy này tự chọn nhạc (máy tính) nên có nút; điện thoại không tự chọn nên chỉ hiện nhãn. `idleLabel`: dòng thay
 *  nhãn khi bài ở mặc định và bình thường (vd. trạng thái phân tích). Không có gì để hiện thì không vẽ gì. */
export function AutoPickNote({ track, canOverride, onView, idleLabel }: {
  track: LocalTrack;
  canOverride: boolean;
  onView: (view: LocalMusicView) => void;
  idleLabel?: string;
}) {
  const change = useMutation({
    mutationFn: (auto: "on" | "off" | null) => api<LocalMusicView>(`/api/music/local/${localDigest(track.link)}/auto`, { method: "POST", body: { auto } }),
    onSuccess: onView,
    onError: (error: Error) => toast.error("Không đổi được", { description: error.message }),
  });
  const label = autoLabel(track) ?? idleLabel;
  if (!label && !canOverride) return null;
  const switcher = autoSwitch(track);
  return (
    <span className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-fg-2">
      {label && <span>{label}</span>}
      {canOverride && (
        <Button size="sm" variant="ghost" className="h-6 px-2 text-xs" aria-label={`${switcher.text}: ${track.title}`} loading={change.isPending} onClick={() => change.mutate(switcher.next)}>
          {switcher.text}
        </Button>
      )}
    </span>
  );
}
