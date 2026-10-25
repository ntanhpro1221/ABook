import { MotionRegion } from "@/shared/MotionRegion";
import { MotionPresence } from "@/shared/MotionPresence";
import { useQueryClient } from "@tanstack/react-query";
import { Laptop } from "lucide-react";
import { useEffect, useState } from "react";
import { watchUntilBack } from "@/listen/peerBack";
import { cn } from "@/shared/cn";
import { homePage, PEER_SILENT_EVENT, peerBarLine } from "@/shared/peerStudio";
import { Button } from "@/shared/ui";
import { api, currentPeer, type AppInfo } from "@/studio/api";
import { useAppInfo } from "@/studio/data";

/** Máy kia không trả lời (câu của máy chủ, "" khi đang trả lời): nghe sự kiện của api.ts, hỏi lại mỗi vài giây (listen/peerBack.ts)
 *  và khi máy ấy trả lời thì tải lại mọi thứ đang xem - người dùng không phải bấm gì. `onBack`: việc thêm khi máy ấy về. */
export function usePeerSilent(onBack?: () => void): string {
  const client = useQueryClient();
  const [silent, setSilent] = useState("");
  useEffect(() => {
    if (!currentPeer()) return;
    const listener = (event: Event) => setSilent((event as CustomEvent<string>).detail || "Máy kia không trả lời");
    window.addEventListener(PEER_SILENT_EVENT, listener);
    return () => window.removeEventListener(PEER_SILENT_EVENT, listener);
  }, []);
  useEffect(() => {
    if (!silent) return;
    return watchUntilBack(
      () => api<AppInfo>("/api/app").then(() => true),
      () => {
        setSilent("");
        onBack?.();
        void client.invalidateQueries();
      },
    );
  }, [silent, client, onBack]);
  return silent;
}

/** Thanh trên cùng khi đang mở Studio của máy tính đã ghép (`?peer=`, webui/peer_studio.py): máy nào, máy ấy có trả lời không, và
 *  đường về máy này. Trang của chính máy này: không hiện gì. */
export function PeerBar() {
  const info = useAppInfo().data;
  const silent = usePeerSilent();
  const content = () => {
  if (!currentPeer() || !info?.peer) return null;
  return (
    <div
      role="status"
      className={cn(
        "transition-colors duration-(--motion-medium) shrink-0 border-b border-line py-2 text-sm",
        silent || info.listenOnly ? "bg-warning-soft text-fg" : "bg-info-soft text-fg",
      )}
    >
      {/* Như dải mất mạng: nền tràn cả bề ngang, nội dung thẳng lề trang bên dưới (page-x, khung 1180) - từng thụt 14 px (soát 25-10). */}
      <div className="page-x mx-auto flex max-w-[1180px] items-center gap-3 max-sm:flex-wrap">
        <Laptop className="ink-start size-4 shrink-0 text-fg-2" aria-hidden />
        <MotionRegion as="span" className="min-w-0 flex-1 text-pretty">{peerBarLine(info.peer.name, { silent, listenOnly: info.listenOnly })}</MotionRegion>
        <Button size="sm" variant="secondary" onClick={() => window.location.assign(homePage(window.location.search))}>
          Về máy này
        </Button>
      </div>
    </div>
  );
  };
  return <MotionPresence open={Boolean(currentPeer() && info?.peer)} className="shrink-0">{content()}</MotionPresence>;
}
