import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Button, Progress } from "@/shared/ui";
import { api } from "./api";
import { formatSize, moduleLabel, modulePercent, type LocalMusicView } from "./musicLocal";

/** Thẻ duy nhất của mô-đun "Phân tích nhạc" (máy tính và điện thoại): nhập nhạc chạy không cần nó, nó chỉ cho máy NGHE nhạc để hiểu không khí
 *  của từng bài. Người dùng thấy tổng dung lượng và bấm mới tải (không bao giờ tự tải, nhất là khi đang dùng dữ liệu di động); có bản mới thì
 *  nói "có bản mới - N MB" và một lần bấm chỉ tải phần đổi; cập nhật xong KHÔNG tự phân tích lại bài cũ - hiện nút "Phân tích lại N bài". */
export function MusicModuleNotice({ view, queryKey }: { view: LocalMusicView | undefined; queryKey: readonly unknown[] }) {
  const client = useQueryClient();
  const module = view?.module;
  const [starting, setStarting] = useState(false);
  const busy = module?.state === "downloading" || Boolean(module?.analysing);
  useEffect(() => {
    if (!busy) return;
    const timer = setInterval(() => {
      void api<LocalMusicView>("/api/music/local").then((next) => client.setQueryData(queryKey, next));
    }, 1000);
    return () => clearInterval(timer);
  }, [busy, client, queryKey]);
  if (!module) return null;
  const stale = module.stale ?? 0;
  const calm = module.state === "ready" && !module.analysing && !module.restart && stale === 0;
  if (calm) return null;
  const post = async (path: string) => {
    setStarting(true);
    try {
      client.setQueryData(queryKey, await api<LocalMusicView>(path, { method: "POST" }));
    } finally {
      setStarting(false);
    }
  };
  const failed = module.state === "error";
  const label = moduleLabel(module);
  const updating = module.state === "outdated";
  const action = busy || module.state === "unsupported" || module.restart ? null : stale > 0 && module.state === "ready" ? "reanalyse" : "install";
  return (
    <div role="status" className="space-y-1.5 text-xs text-fg-2">
      <p className={failed ? "text-danger" : undefined}>{label}</p>
      {module.state === "downloading" && (
        <Progress value={modulePercent(module) / 100} size="sm" running label="Đang tải Phân tích nhạc" />
      )}
      {action && (
        <div className="flex flex-wrap items-center gap-2">
          {action === "install" ? (
            <Button size="sm" variant="secondary" loading={starting} onClick={() => void post("/api/music/local/module")}>
              {failed ? "Thử lại" : updating ? `Cập nhật Phân tích nhạc (${formatSize(module.outdatedBytes ?? module.total)})` : `Phân tích nhạc (${formatSize(module.total)})`}
            </Button>
          ) : (
            <Button size="sm" variant="secondary" loading={starting} onClick={() => void post("/api/music/local/reanalyse")}>
              {`Phân tích lại ${stale} bài bằng bản mới`}
            </Button>
          )}
          {module.metered && action === "install" && !failed && (
            <span className="text-warning">Bạn đang dùng dữ liệu di động - nên đợi khi có Wi-Fi.</span>
          )}
        </div>
      )}
    </div>
  );
}
