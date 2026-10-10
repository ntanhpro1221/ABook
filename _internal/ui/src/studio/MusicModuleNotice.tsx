import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Button, Progress } from "@/shared/ui";
import { api } from "./api";
import { CANCELLED_NOTE, formatSize, moduleLabel, modulePercent, preciseBusy, preciseLabel, preciseOffered, sceneButton, sceneCard, type LocalMusicView } from "./musicLocal";

/** Nút dài ("Tải model nhạc theo đoạn cùng Phân tích nhạc (820 MB)") xuống dòng thay vì tràn ra ngoài ở màn 375 px (Button mặc định không ngắt dòng, cao 32 px). */
const WRAP = "h-auto min-h-8 whitespace-normal py-1.5 text-left";

/** Thẻ duy nhất của mô-đun "Phân tích nhạc" (máy tính và điện thoại): nhập nhạc chạy không cần nó, nó chỉ cho máy NGHE nhạc để hiểu không khí
 *  của từng bài. Người dùng thấy tổng dung lượng và bấm mới tải (không bao giờ tự tải, nhất là khi đang dùng dữ liệu di động); có bản mới thì
 *  nói "có bản mới - N MB" và một lần bấm chỉ tải phần đổi; cập nhật xong KHÔNG tự phân tích lại bài cũ - hiện nút "Phân tích lại N bài".
 *  Máy tính đủ RAM còn có tuỳ chọn "Đo cảm xúc nhạc chính xác hơn" (tải thêm một model lớn, mặc định tắt) khi mô-đun đã sẵn sàng, và
 *  "Nhạc theo sát từng đoạn trong chương" (model nhỏ, tải khi bấm; máy chưa dùng được thì thẻ nói lý do). Máy tính có nút Huỷ khi đang tải (phần đã tải giữ để lần sau làm tiếp).
 *  `onlyScene`: chưa nhập bài nào - chỉ thẻ “theo sát từng đoạn” (và tiến độ khi nó đang tải) có nghĩa, các thẻ còn lại đợi có bài. */
export function MusicModuleNotice({ view, queryKey, onlyScene = false }: { view: LocalMusicView | undefined; queryKey: readonly unknown[]; onlyScene?: boolean }) {
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
  const precise = !onlyScene && preciseOffered(module) ? module.precise : null;
  const scene = sceneCard(module);
  const calm = module.state === "ready" && !module.analysing && !module.restart && stale === 0;
  const downloadingModule = module.state === "downloading";
  const showModule = !calm && (!onlyScene || downloadingModule);
  if (!showModule && !precise && !scene) return null;
  const post = async (path: string, body?: Record<string, unknown>) => {
    setStarting(true);
    try {
      client.setQueryData(queryKey, await api<LocalMusicView>(path, { method: "POST", body }));
    } finally {
      setStarting(false);
    }
  };
  const cancel = async (path: string) => {
    setStarting(true);
    try {
      client.setQueryData(queryKey, await api<LocalMusicView>(path, { method: "POST", body: {} }));
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
      {showModule && (
        <div className="space-y-1.5">
          <p className={failed ? "text-danger" : undefined}>{label}</p>
          {downloadingModule && (
            <div className="flex items-center gap-3">
              <Progress value={modulePercent(module) / 100} size="sm" running label="Đang tải Phân tích nhạc" className="flex-1" />
              {module.cancellable && (
                <Button size="sm" variant="ghost" loading={starting} onClick={() => void cancel("/api/music/local/module/cancel")}>
                  Huỷ
                </Button>
              )}
            </div>
          )}
          {action && (
            <div className="flex flex-wrap items-center gap-2">
              {action === "install" ? (
                <Button size="sm" variant="secondary" className={WRAP} loading={starting} onClick={() => void post("/api/music/local/module")}>
                  {failed ? "Thử lại" : module.stopped ? `Tải lại phần chạy (${formatSize(module.outdatedBytes ?? module.total)})` : updating ? `Cập nhật Phân tích nhạc (${formatSize(module.outdatedBytes ?? module.total)})` : `Tải Phân tích nhạc (${formatSize(module.total)})`}
                </Button>
              ) : (
                <Button size="sm" variant="secondary" className={WRAP} loading={starting} onClick={() => void post("/api/music/local/reanalyse")}>
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
      {scene && (
        <div className="space-y-1.5">
          <p className="font-medium text-fg">Nhạc theo sát từng đoạn trong chương</p>
          <p>Một model nhỏ đọc chữ từng đoạn rồi đoán đoạn nào vui hơn, căng hơn mức chung của chương, để nhạc đổi theo đúng chỗ truyện lúc căng lúc dịu. Chạy trên máy này, không cần mạng sau khi tải; chưa tải thì nhạc chọn như trước.</p>
          {onlyScene && module.cancelled && !downloadingModule && !scene.unavailable && <p>{CANCELLED_NOTE}</p>}
          {scene.unavailable ? (
            <p>{scene.unavailable}.</p>
          ) : (
            !downloadingModule && (
              <Button size="sm" variant="secondary" className={WRAP} loading={starting} onClick={() => void post("/api/music/local/module", { scene: true })}>
                {sceneButton(scene.scene)}
              </Button>
            )
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
          {precise.state === "downloading" && module.cancellable && (
            <Button size="sm" variant="ghost" loading={starting} onClick={() => void cancel("/api/music/local/precise/cancel")}>
              Huỷ
            </Button>
          )}
          {precise.state !== "downloading" && (
            <div className="flex flex-wrap items-center gap-2">
              <Button size="sm" variant="secondary" className={WRAP} loading={starting} onClick={() => void post("/api/music/local/precise", { enabled: precise.state !== "ready" })}>
                {precise.state === "error" ? "Thử lại" : precise.state === "missing" ? `Tải tiếp đo cảm xúc (${formatSize(precise.bytes)})` : precise.state === "ready" ? "Tắt đo cảm xúc chính xác hơn" : precise.present ? "Bật đo cảm xúc chính xác hơn" : `Tải và bật đo cảm xúc (${formatSize(precise.bytes)})`}
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
