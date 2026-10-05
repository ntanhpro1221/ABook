import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Button, Progress } from "@/shared/ui";
import { api } from "./api";
import { formatSize, moduleLabel, modulePercent, preciseBusy, preciseLabel, preciseOffered, type LocalMusicView } from "./musicLocal";

/** Thẻ duy nhất của mô-đun "Phân tích nhạc" (máy tính và điện thoại): nhập nhạc chạy không cần nó, nó chỉ cho máy NGHE nhạc để hiểu không khí
 *  của từng bài. Người dùng thấy tổng dung lượng và bấm mới tải (không bao giờ tự tải, nhất là khi đang dùng dữ liệu di động); có bản mới thì
 *  nói "có bản mới - N MB" và một lần bấm chỉ tải phần đổi; cập nhật xong KHÔNG tự phân tích lại bài cũ - hiện nút "Phân tích lại N bài".
 *  Máy tính đủ RAM còn có tuỳ chọn "Đo cảm xúc nhạc chính xác hơn" (tải thêm một model lớn, mặc định tắt) khi mô-đun đã sẵn sàng. */
export function MusicModuleNotice({ view, queryKey }: { view: LocalMusicView | undefined; queryKey: readonly unknown[] }) {
  const client = useQueryClient();
  const module = view?.module;
  const [starting, setStarting] = useState(false);
  const busy = module?.state === "downloading" || Boolean(module?.analysing) || preciseBusy(module?.precise);
  useEffect(() => {
    if (!busy) return;
    const timer = setInterval(() => {
      void api<LocalMusicView>("/api/music/local").then((next) => client.setQueryData(queryKey, next));
    }, 1000);
    return () => clearInterval(timer);
  }, [busy, client, queryKey]);
  if (!module) return null;
  const stale = module.stale ?? 0;
  const precise = preciseOffered(module) ? module.precise : null;
  const calm = module.state === "ready" && !module.analysing && !module.restart && stale === 0;
  if (calm && !precise) return null;
  const post = async (path: string, body?: Record<string, unknown>) => {
    setStarting(true);
    try {
      client.setQueryData(queryKey, await api<LocalMusicView>(path, { method: "POST", body }));
    } finally {
      setStarting(false);
    }
  };
  const failed = module.state === "error";
  const label = moduleLabel(module);
  const updating = module.state === "outdated";
  const action = busy || module.state === "unsupported" || module.restart ? null : stale > 0 && module.state === "ready" ? "reanalyse" : "install";
  return (
    <div role="status" className="space-y-3 text-xs text-fg-2">
      {!calm && (
        <div className="space-y-1.5">
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
      )}
      {precise && (
        <div className="space-y-1.5">
          <p className="font-medium text-fg">Đo cảm xúc nhạc chính xác hơn</p>
          <p className={precise.state === "error" ? "text-danger" : undefined}>{preciseLabel(precise)}</p>
          {precise.state === "downloading" && (
            <Progress value={precise.total > 0 ? precise.done / precise.total : 0} size="sm" running label="Đang tải bộ đo cảm xúc chính xác hơn" />
          )}
          {precise.state !== "downloading" && (
            <div className="flex flex-wrap items-center gap-2">
              <Button size="sm" variant="secondary" loading={starting} onClick={() => void post("/api/music/local/precise", { enabled: precise.state !== "ready" })}>
                {precise.state === "error" ? "Thử lại" : precise.state === "missing" ? `Tải tiếp (${formatSize(precise.bytes)})` : precise.state === "ready" ? "Tắt" : precise.present ? "Bật" : `Bật (tải ${formatSize(precise.bytes)})`}
              </Button>
              {precise.removable && (
                <Button size="sm" variant="ghost" loading={starting} onClick={() => void post("/api/music/local/precise/remove")}>
                  {`Xoá file (${formatSize(precise.bytes)})`}
                </Button>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
