import type { ReactNode } from "react";
import { OfflineStrip } from "./ui";

/** Khung điện thoại giữ dải mạng trong luồng, không che trang hay thanh phát. */
export function OfflineFrame({ children }: { children: ReactNode }) {
  return <div className="flex h-full min-h-0 flex-col"><OfflineStrip /><div className="min-h-0 flex-1">{children}</div></div>;
}
