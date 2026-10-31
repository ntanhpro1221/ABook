import { useId } from "react";
import { MotionRegion } from "@/shared/MotionRegion";
import { useMutation } from "@tanstack/react-query";
import { toast } from "@/shared/toast";
import { Switch } from "@/desktop/Switch";
import { api } from "./api";
import { AUTO_PICK_LABEL, autoNext, autoOn, localDigest, trackNote, type LocalMusicView, type LocalTrack } from "./musicLocal";

/** Dòng tự chọn của một bài trong Nhạc của tôi (công tắc `auto`, music_local.py): nhãn ngắn ("Chưa phân tích", "Có lời") và công tắc "Tự chọn" - bật =
 *  máy được tự chọn bài này. `canOverride`: máy này tự chọn nhạc (máy tính) nên có công tắc; điện thoại không tự chọn nên chỉ hiện nhãn. `showNote`:
 *  có hiện nhãn không (điện thoại không nói bài đã phân tích, chỉ nói bài chưa). Không có gì để hiện thì không vẽ gì. */
export function AutoPickNote({ track, canOverride, onView, showNote = true }: {
  track: LocalTrack;
  canOverride: boolean;
  onView: (view: LocalMusicView) => void;
  showNote?: boolean;
}) {
  const id = useId();
  const change = useMutation({
    mutationFn: (auto: "on" | "off" | null) => api<LocalMusicView>(`/api/music/local/${localDigest(track.link)}/auto`, { method: "POST", body: { auto } }),
    onSuccess: onView,
    onError: (error: Error) => toast.error("Chưa đổi được", { description: error.message }),
  });
  const note = showNote ? trackNote(track) : "";
  if (!note && !canOverride) return <MotionRegion as="span" />;
  return (
    <MotionRegion as="span" className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-fg-2">
      {note && <span>{note}</span>}
      {canOverride && (
        <span className="flex h-6 items-center gap-2">
          <Switch id={id} label={`${AUTO_PICK_LABEL}: ${track.title}`} checked={autoOn(track)} disabled={change.isPending} onCheckedChange={() => change.mutate(autoNext(track))} />
          <label htmlFor={id}>{AUTO_PICK_LABEL}</label>
        </span>
      )}
    </MotionRegion>
  );
}
