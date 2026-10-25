import { BookOpen, Plus } from "lucide-react";
import { useState } from "react";
import { MotionRegion } from "@/shared/MotionRegion";
import { Button, ContentSkeleton, EmptyState, InlineError, OfflineStrip } from "@/shared/ui";
import { ScreenHeader } from "@/shared/ScreenHeader";

export type StateStory = "skeleton" | "empty" | "error" | "offline";

/** Dùng đúng thành phần của app; nút trong mỗi mục đổi trạng thái để soát chuyển động. */
export function StateStories({ state }: { state: StateStory }) {
  const [ready, setReady] = useState(false);
  const [playing, setPlaying] = useState(false);
  return <div className="flex h-full flex-col">
    <OfflineStrip offline={state === "offline" && !ready} />
    {/* Cùng khung, cùng đầu màn và cùng khoảng cách với Thư viện thật: trống / lỗi đứng đúng chỗ của chúng trong app (soát 25-10). */}
    <main className="page-x mx-auto w-full max-w-[1180px] pb-16">
      <ScreenHeader title="Thư viện" subtitle={"\u00a0"} />
      <MotionRegion motionKey={[state, ready]} className={state === "empty" || state === "error" ? "mt-12" : "mt-8"}>
        {state === "skeleton" ? <ContentSkeleton shape="covers" count={4} label="Đang tải sách" />
          : state === "empty" && !ready ? <EmptyState icon={BookOpen} title="Thêm cuốn đầu tiên của bạn" action={<Button variant="primary" icon={Plus} onClick={() => setReady(true)}>Thêm sách</Button>} />
          : state === "error" && !ready ? <InlineError message="Bạn hãy kiểm tra kết nối rồi tải lại thư viện." onRetry={() => setReady(true)} />
          : <div className="space-y-5">
            <h2 className="text-lg font-medium">Thành Phố Sương Mù</h2>
            <MotionRegion as="p" motionKey={playing} className="text-sm text-fg-2">{playing ? "Bạn đang nghe chương 4." : "Bạn có thể nghe tiếp chương 4."}</MotionRegion>
            <Button variant="primary" onClick={() => setPlaying(value => !value)}>{playing ? "Tạm dừng" : "Nghe tiếp"}</Button>
            {state === "offline" && <Button variant="ghost" onClick={() => setReady(value => !value)}>{ready ? "Mất mạng" : "Kết nối lại"}</Button>}
          </div>}
      </MotionRegion>
    </main>
  </div>;
}
