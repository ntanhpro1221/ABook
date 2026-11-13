import { S } from "../shared/strings.generated";
import { MotionRegion } from "@/shared/MotionRegion";
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { ErrorDetails } from "@/shared/ErrorDetails";
import { MoreInfo } from "@/shared/SettingsNav";
import { spokenProgress } from "@/shared/progressSpeech";
import { Button, LiveText, Progress } from "@/shared/ui";
import { api } from "./api";
import { formatSize } from "@/shared/format";
import { moduleLabel, modulePercent, preciseBusy, preciseLabel, preciseOffered, type LocalMusicView } from "./musicLocal";

/** Nút dài ("Cập nhật Phân tích nhạc (820 MB)") xuống dòng thay vì tràn ra ngoài ở màn 375 px (Button mặc định không ngắt dòng, cao 32 px). */
const WRAP = "h-auto min-h-8 whitespace-normal py-2 text-left";

/** Thẻ duy nhất của mô-đun "Phân tích nhạc" (máy tính và điện thoại): nhập nhạc chạy không cần nó, nó chỉ cho máy NGHE nhạc để hiểu không khí
 *  của từng bài. Người dùng thấy tổng dung lượng và bấm mới tải (không bao giờ tự tải, nhất là khi đang dùng dữ liệu di động); có bản mới thì
 *  nói "có bản mới - N MB" và một lần bấm chỉ tải phần đổi; cập nhật xong KHÔNG tự phân tích lại bài cũ - hiện nút "Phân tích lại N bài".
 *  Máy tính đủ RAM còn có tuỳ chọn "Cảm xúc chính xác" (tải thêm một model lớn, mặc định tắt) khi mô-đun đã sẵn sàng.
 *  Máy tính có nút Huỷ khi đang tải (phần đã tải giữ để lần sau làm tiếp). */
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
  if (!module) return <MotionRegion />;
  const stale = module.stale ?? 0;
  const precise = preciseOffered(module) ? module.precise : null;
  const calm = module.state === "ready" && !module.analysing && !module.restart && stale === 0;
  const downloadingModule = module.state === "downloading";
  const showModule = !calm;
  if (!showModule && !precise) return <MotionRegion />;
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
    <MotionRegion role="status" className="space-y-3 text-xs text-fg-2">
      {showModule && (
        <div className="space-y-2">
          {/* Đang tải: % đổi liên tục trong vùng role=status - trình đọc màn hình chỉ đọc mốc 25 % (soát a31 A6). */}
          <p data-motion-live className={failed ? "text-danger" : undefined}>
            {downloadingModule ? <LiveText shown={label} spoken={spokenProgress(S.s_dang_tai_phan_tich_nhac_880839b5, modulePercent(module) / 100)} /> : label}
          </p>
          {failed && <ErrorDetails technical={module.errorDetail} className="text-danger" />}
          {module.state === "missing" && <MoreInfo label={S.s_phan_tich_nhac_a0082a10}>{S.s_tai_mot_lan_phan_tich_tren_may_roi_dung_kh_c1fb770b}</MoreInfo>}
          {downloadingModule && (
            <div className="flex items-center gap-3">
              <Progress value={modulePercent(module) / 100} indeterminate={module.total <= 0} size="sm" running label={S.s_dang_tai_phan_tich_nhac_880839b5} className="flex-1" />
              {module.cancellable && (
                <Button size="sm" variant="ghost" loading={starting} onClick={() => void cancel("/api/music/local/module/cancel")}>{S.s_huy_96732485}</Button>
              )}
            </div>
          )}
          {action && (
            <div className="flex flex-wrap items-center gap-2">
              {action === "install" ? (
                <Button size="sm" variant="ghost" className={WRAP} loading={starting} onClick={() => void post("/api/music/local/module")}>
                  {failed ? S.s_thu_lai_c58d068c : module.stopped ? S.s_tai_lai_0_31a8bdc1(formatSize(module.outdatedBytes ?? module.total)) : updating ? S.s_cap_nhat_0_618a3fa3(formatSize(module.outdatedBytes ?? module.total)) : S.s_tai_0_3463a4d8(formatSize(module.total))}
                </Button>
              ) : (
                <Button size="sm" variant="ghost" className={WRAP} loading={starting} onClick={() => void post("/api/music/local/reanalyse")}>
                  {S.s_phan_tich_0_bai_53fe1b94(stale)}
                </Button>
              )}
              {module.metered && action === "install" && !failed && (
                <span className="text-warning">{S.s_ban_dang_dung_du_lieu_di_dong_nen_doi_khi_4e21414f}</span>
              )}
            </div>
          )}
        </div>
      )}
      {precise && (
        <div className="space-y-2">
          <p className="font-medium text-fg">{S.s_cam_xuc_chinh_xac_eab97dc3}</p>
          <p data-motion-live className={precise.state === "error" ? "text-danger" : undefined}>
            {precise.state === "downloading" ? (
              <LiveText shown={preciseLabel(precise)} spoken={spokenProgress(S.s_dang_tai_bo_do_cam_xuc_chinh_xac_hon_94cbb498, precise.total > 0 ? precise.done / precise.total : null)} />
            ) : (
              preciseLabel(precise)
            )}
          </p>
          {precise.state === "error" && <ErrorDetails technical={precise.errorDetail} className="text-danger" />}
          {precise.state === "downloading" && (
            <Progress value={precise.total > 0 ? precise.done / precise.total : 0} indeterminate={!(precise.total > 0)} size="sm" running label={S.s_dang_tai_bo_do_cam_xuc_chinh_xac_hon_94cbb498} />
          )}
          {precise.state === "downloading" && module.cancellable && (
            <Button size="sm" variant="ghost" loading={starting} onClick={() => void cancel("/api/music/local/precise/cancel")}>{S.s_huy_96732485}</Button>
          )}
          {precise.state !== "downloading" && (
            <div className="flex flex-wrap items-center gap-2">
              <Button size="sm" variant="ghost" className={WRAP} loading={starting} onClick={() => void post("/api/music/local/precise", { enabled: precise.state !== "ready" })}>
                {precise.state === "error" ? S.s_thu_lai_c58d068c : precise.state === "missing" ? S.s_tai_tiep_0_67826e5b(formatSize(precise.bytes)) : precise.state === "ready" ? S.s_tat_do_cam_xuc_1435c1ed : precise.present ? S.s_bat_do_cam_xuc_d6c6ba08 : S.s_tai_0_3463a4d8(formatSize(precise.bytes))}
              </Button>
              {precise.removable && (
                <Button size="sm" variant="ghost" loading={starting} onClick={() => void post("/api/music/local/precise/remove")}>
                  {S.s_xoa_file_0_22ad15c7(formatSize(precise.bytes))}
                </Button>
              )}
            </div>
          )}
        </div>
      )}
    </MotionRegion>
  );
}
