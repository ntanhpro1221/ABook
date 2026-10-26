import { Bell, Clapperboard, Laptop } from "lucide-react";
import { useNavigate } from "react-router";
import { Button, EmptyState, LoadError, Skeleton } from "@/shared/ui";
import { LoadingCrossfade } from "@/shared/MotionPresence";
import { MotionRegion } from "@/shared/MotionRegion";
import { ScreenHeader } from "@/shared/ScreenHeader";
import { useListPresence } from "@/shared/motion";
import { StudioAlertsRow } from "./DevicesScreen";
import { openStudioComputer, useStudioComputersQuery } from "./StudioOpen";

/** Studio từ xa: mỗi máy tính một hàng; trang dự án vẫn do Studio hiện có mở. */
export function StudioScreen() {
  const navigate = useNavigate();
  const query = useStudioComputersQuery();
  const computers = query.data?.computers ?? [];
  const failed = query.isError && !computers.length;
  const rows = useListPresence(computers, computer => computer.key);
  return <div className="px-[20px] pb-10">
    <ScreenHeader title="Studio" />
    <LoadingCrossfade loading={query.isLoading} placeholder={<div className="mt-8 space-y-4"><Skeleton className="h-14 w-full" /><Skeleton className="h-14 w-full" /></div>}>
      <MotionRegion fadeThrough motionKey={failed ? "error" : computers.length ? "computers" : "empty"}>
        {failed ? <LoadError what="Studio" error={query.error} onRetry={() => void query.refetch()} className="mt-8" /> : !computers.length ? <EmptyState
          icon={Clapperboard} title="Studio trên máy tính" className="mt-12"
          action={<Button variant="primary" onClick={() => navigate("/settings/devices")}>Nối máy tính</Button>}>
          Nối máy tính để làm sách nói và xem tiến độ.
        </EmptyState> : <>
          <ul className="mt-8 divide-y divide-line">{rows.map(({ key, item, state, ref }) => <li key={key} ref={ref} className="motion-row" data-state={state} inert={state === "exit"}>
            <div className="flex items-center gap-3 py-4">
              <Laptop className="size-5 shrink-0 text-fg-2" />
              <div className="min-w-0 flex-1"><div className="truncate text-base font-medium">{item.name}</div>
                <MotionRegion as="p" className="mt-1 truncate text-sm text-fg-2">{item.listenOnly ? "Bật Điều khiển từ xa trên máy tính." : "Tạo sách nói từ xa"}</MotionRegion>
              </div>
              {/* -mr-3.5 bù đúng phần đệm px-3.5 của nút ghost cỡ md: chữ thẳng mép phải với công tắc ở hàng dưới. */}
              <Button variant="ghost" disabled={item.listenOnly} className="-mr-3.5" onClick={() => void openStudioComputer(item)}>Mở Studio</Button>
            </div>
          </li>)}
            <li><StudioAlertsRow icon={Bell} /></li>
          </ul>
        </>}
      </MotionRegion>
    </LoadingCrossfade>
  </div>;
}
