import { S } from "../shared/strings.generated";
import { MoreInfo, SettingsBlock } from "@/shared/SettingsNav";
import { MotionRegion } from "@/shared/MotionRegion";
import { Fold } from "@/shared/Collapse";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Switch } from "./Switch";
import { ShieldAlert, Smartphone } from "lucide-react";
import { useId, useEffect, useRef, useState } from "react";
import { toast } from "@/shared/toast";
import { api } from "@/studio/api";
import { DialogActions, Button, ContentSkeleton, Dialog, InlineError } from "@/shared/ui";
import { cn } from "@/shared/cn";
import { useListPresence } from "@/shared/motion";
import { formatDate, formatRelative } from "@/shared/format";
import { SYNC_SWITCH_LABEL } from "@/shared/syncSwitch";

// Hợp đồng với server (webui/server.py: sync_view). Máy chủ đồng bộ chỉ chạy khi người dùng bật; mã ghép nối chỉ
// có khi người dùng bấm "Ghép thiết bị mới", sống 5 phút, dùng một lần, sai 5 lần là bị huỷ. Cùng mã ghép cả điện
// thoại lẫn trình duyệt của Studio từ xa (webui/remote_studio.py).

export interface SyncDevice {
  id: string;
  name: string;
  pairedAt: number;
  lastSeen: number;
  /** Được điều khiển sản xuất khi Studio từ xa bật - theo từng thiết bị, không theo công tắc chung. */
  studio?: boolean;
}

export interface SyncView {
  enabled: boolean;
  wanted: boolean;
  error: string;
  name: string;
  port: number;
  addresses: string[];
  /** Trong `addresses`, địa chỉ trên card mạng riêng ảo (Tailscale, ZeroTier, WireGuard... - sync.away_addresses). */
  awayAddresses: string[];
  pairing: { code: string; expiresAt: number } | null;
  pairingBlocked: boolean;
  /** Vân tay SHA-256 chứng chỉ TLS của máy này (webui/tls.py), nhóm 4 ký tự; "" khi đồng bộ tắt. */
  fingerprint: string;
  devices: SyncDevice[];
  /** Studio từ xa (webui/remote_studio.py): thiết bị đã ghép được điều khiển sản xuất. */
  remoteStudio: boolean;
  /** Cổng đồng bộ qua Bluetooth (webui/bluetooth.py) - null khi đồng bộ tắt. */
  bluetooth: { running: boolean; channel: number; error: string; connections: number } | null;
}

/** Địa chỉ của máy này cho thiết bị khác: trong nhà (LAN) và khi ở ngoài (mạng riêng ảo - máy chủ nhận theo card mạng, không
 *  riêng Tailscale), nói rõ cái nào để làm gì. Soát 29-09: chủ sách tưởng khác mạng là không dùng được, vì giao diện ghép mọi
 *  địa chỉ bằng "hoặc" mà không nói địa chỉ nào để làm gì. */
function Where({ sync, scheme = true }: { sync: SyncView; scheme?: boolean }) {
  const away = sync.addresses.filter((address) => sync.awayAddresses.includes(address));
  const home = sync.addresses.filter((address) => !away.includes(address));
  const show = (list: string[]) => (
    <span className="font-medium text-fg tabular-nums">{list.map((address) => `${scheme ? "https://" : ""}${address}:${sync.port}`).join(S.s_hoac_cffdc32e)}</span>
  );
  return (
    <>
      {home.length > 0 && show(home)}
      {home.length > 0 && away.length > 0 && S.s_trong_nha_hoac_de6d3fe2}
      {away.length > 0 && (
        <>
          {show(away)}{S.s_khi_o_ngoai_thiet_bi_kia_vao_cung_mang_rie_d9eb417b}</>
      )}
    </>
  );
}

function useSync() {
  const client = useQueryClient();
  const query = useQuery({
    queryKey: ["sync"],
    queryFn: () => api<SyncView>("/api/sync"),
    // Đang hiện mã: hỏi dày để báo "đã ghép" ngay khi điện thoại nhập xong.
    refetchInterval: (current) => (current.state.data?.pairing ? 1500 : 10000),
  });
  const onSuccess = (data: SyncView) => client.setQueryData(["sync"], data);
  const onError = (error: Error) => toast.error(error.message);
  const toggle = useMutation({
    mutationFn: (enabled: boolean) => api<SyncView>("/api/sync", { method: "POST", body: { enabled } }),
    onSuccess: (data, enabled) => {
      onSuccess(data);
      if (enabled && !data.enabled) toast.error(S.s_chua_bat_duoc_dong_bo_9927f58c, { description: data.error });
      // Tắt xong không có gì đổi trên màn ngoài công tắc: nói một câu để biết đã tắt thật (soát UX a17).
      else if (!enabled && !data.enabled) toast(S.s_da_tat_chia_se_qua_wi_fi_c818faf6);
    },
    onError,
  });
  const pair = useMutation({ mutationFn: () => api<SyncView>("/api/sync/pairing", { method: "POST" }), onSuccess, onError });
  const cancel = useMutation({ mutationFn: () => api<SyncView>("/api/sync/pairing", { method: "DELETE" }), onSuccess, onError });
  const revoke = useMutation({
    mutationFn: ({ id }: { id: string; name: string }) => api<SyncView>(`/api/sync/devices/${id}`, { method: "DELETE" }),
    // Bỏ ghép xong nói một câu (soát a68 lỗi 15): dòng thiết bị biến mất không đủ để biết đã xong và hệ quả là gì.
    onSuccess: (data, { name }) => {
      onSuccess(data);
      toast.success(S.s_da_bo_ghep_0_d1ec976d(name));
    },
    onError,
  });
  // Đổi tên thiết bị đã ghép (soát a68 lỗi 16: tên thô "Google sdk_gphone64_x86_64").
  const rename = useMutation({
    mutationFn: ({ id, name }: { id: string; name: string }) => api<SyncView>(`/api/sync/devices/${id}/name`, { method: "POST", body: { name } }),
    onSuccess: (data, { name }) => {
      onSuccess(data);
      toast.success(S.s_da_doi_ten_thanh_0_268ec88c(name));
    },
    onError,
  });
  const studio = useMutation({
    mutationFn: (enabled: boolean) => api<SyncView>("/api/sync/studio", { method: "POST", body: { enabled } }),
    onSuccess,
    onError,
  });
  const deviceStudio = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      api<SyncView>(`/api/sync/devices/${id}/studio`, { method: "POST", body: { enabled } }),
    onSuccess,
    onError,
  });
  return { ...query, toggle, pair, cancel, revoke, rename, studio, deviceStudio };
}

function useSecondsLeft(until: number | undefined): number {
  const [now, setNow] = useState(() => Date.now() / 1000);
  useEffect(() => {
    if (!until) return;
    setNow(Date.now() / 1000);
    const timer = window.setInterval(() => setNow(Date.now() / 1000), 1000);
    return () => window.clearInterval(timer);
  }, [until]);
  return until ? Math.max(0, Math.ceil(until - now)) : 0;
}

function PairingPanel(props: Parameters<typeof PairingContent>[0]) {
  return <MotionRegion><PairingContent {...props} /></MotionRegion>;
}
function PairingContent({ sync, onPair, onCancel, busy }: { sync: SyncView; onPair: () => void; onCancel: () => void; busy: boolean }) {
  const secondsLeft = useSecondsLeft(sync.pairing?.expiresAt);
  if (sync.pairing && secondsLeft > 0) {
    const { code } = sync.pairing;
    const minutes = Math.floor(secondsLeft / 60);
    const seconds = String(secondsLeft % 60).padStart(2, "0");
    return (
      // Ba pha (mã / mã bị khoá / nút) dùng chung một vùng khoá theo pha: khung cũ (viền, nền, đệm) nằm trong ảnh mờ ra, không đổi cứng;
      // đồng hồ đếm ngược không làm vùng mờ lại.
      <MotionRegion as="div" motionKey="code" className="py-5" aria-live="polite">
        <div className="flex flex-wrap items-center justify-between gap-6">
          <div className="min-w-0">
            <p className="text-sm font-semibold">{S.s_ma_ghep_thiet_bi_02370316}</p>
            <p className="mt-2 text-[0.8125rem] text-fg-2">{S.s_tren_may_kia_cai_dat_thiet_bi_chon_7cad8e7a}{sync.name}{S.s_nhap_ma_8a077ab3}</p>
            <MoreInfo label={S.s_cach_dung_ma_ae1cba85} className="mt-2">{S.s_ma_dung_mot_lan_de_may_kia_nghe_thu_vien_n_a41fb816}{sync.addresses.length > 0 && <span className="block">{S.s_dia_chi_9945f0f4}<Where sync={sync} scheme={false} /></span>}
              {sync.remoteStudio && <span className="block">{S.s_trinh_duyet_mo_78712782}<Where sync={sync} />{S.s_roi_nhap_ma_fdfaf308}</span>}
            </MoreInfo>
          </div>
          {/* Mã và dòng hết hạn cùng một trục giữa (soát UX a19): khoảng cách chữ thừa sau số cuối đã được bù ở bên trái. */}
          <div className="text-center">
            <div
              aria-label={S.s_ma_ghep_noi_0_77e0df8a(code.split("").join(" "))}
              className="pl-[0.14em] text-[2.125rem] font-semibold leading-none tracking-[0.14em] text-accent-text tabular-nums"
            >
              {code.slice(0, 3)}
              <span className="inline-block w-3" />
              {code.slice(3)}
            </div>
            <div data-motion-live className="mt-2 text-xs text-fg-2 tabular">{S.s_het_han_sau_34497ee1}{minutes}:{seconds}
            </div>
          </div>
        </div>
        {/* Dòng vân tay dài (64 ký tự): để NGOÀI hàng hướng dẫn / mã, không thì nó chiếm hết bề rộng và đẩy mã xuống dưới. */}
        {sync.fingerprint && <p className="mt-3 break-all text-xs text-fg-3" title={S.s_doi_chieu_van_tay_voi_may_kia_18aa9fb1}>{S.s_van_tay_8b70c9dd}{sync.fingerprint}</p>}
        <DialogActions>
          {/* Chỉ huỷ mã đang hiện, không gỡ thiết bị nào - "Huỷ ghép" dễ hiểu thành gỡ thiết bị (soát UX 29-09). */}
          <Button size="sm" variant="ghost" onClick={onCancel}>{S.s_huy_ma_1b0a6559}</Button>
        </DialogActions>
      </MotionRegion>
    );
  }
  if (sync.pairingBlocked) {
    return (
      <MotionRegion as="div" motionKey="blocked" className="flex items-start gap-3 py-4">
        <ShieldAlert className="mt-0.5 glyph shrink-0 text-warning" />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold">{S.s_ma_bi_khoa_48579bd8}</p>
          <p className="mt-0.5 text-[0.8125rem] text-fg-2">{S.s_sai_5_lan_chi_tao_ma_moi_khi_ban_dang_ghep_6f3c0e90}</p>
        </div>
        <Button size="sm" onClick={onPair} loading={busy}>{S.s_tao_ma_moi_0b393b03}</Button>
      </MotionRegion>
    );
  }
  return (
    <MotionRegion motionKey="idle"><Button icon={Smartphone} onClick={onPair} loading={busy}>{S.s_ghep_thiet_bi_moi_e22fb590}</Button></MotionRegion>
  );
}

const NO_DEVICES: SyncDevice[] = [];

/** Mục "Điện thoại" trong Cài đặt: bật đồng bộ, ghép nối bằng mã 6 số, quản lý điện thoại đã ghép. */
export function PhoneSync() {
  const dialogForm1 = useId();
  const { data: sync, error, refetch, toggle, pair, cancel, revoke, rename, studio, deviceStudio } = useSync();
  const [removing, setRemoving] = useState<SyncDevice | null>(null);
  const [renaming, setRenaming] = useState<{ id: string; draft: string } | null>(null);
  // Bật điều khiển sản xuất từ xa phải hỏi lại (soát UX 29-09): thiết bị đã ghép bắt đầu / dừng sản xuất qua http trong mạng.
  const [confirmStudio, setConfirmStudio] = useState(false);
  const known = useRef<Set<string> | null>(null);
  // Thiết bị vừa ghép / vừa bỏ ghép: hàng mở ra hay khép lại tại chỗ (shared/motion.ts useListPresence).
  const deviceRows = useListPresence(sync?.devices ?? NO_DEVICES, (device) => device.id);

  // Điện thoại vừa nhập đúng mã: nó xuất hiện trong danh sách - báo ngay, người dùng đang nhìn vào máy tính.
  useEffect(() => {
    if (!sync) return;
    const previous = known.current;
    known.current = new Set(sync.devices.map((device) => device.id));
    const added = previous ? sync.devices.find((device) => !previous.has(device.id)) : undefined;
    if (added) toast.success(S.s_da_ghep_0_a04998dd(added.name));
  }, [sync]);

  // Khung chờ / lỗi và nội dung có CÙNG gốc (vùng ngoài cùng bên dưới): tải xong thì mờ qua, không gỡ cả cây làm khung chờ mất cứng.
  if (error && !sync) return <MotionRegion as="div" className="motion-reveal"><SettingsBlock title={S.s_may_nay_4668c138} id="phone"><MotionRegion fadeThrough className="py-3.5"><InlineError message={S.s_ban_hay_thu_tai_lai_cai_dat_ket_noi_db777637} onRetry={() => void refetch()} /></MotionRegion></SettingsBlock></MotionRegion>;
  if (!sync) return <MotionRegion as="div" className="motion-reveal"><SettingsBlock title={S.s_may_nay_4668c138} id="phone"><MotionRegion fadeThrough className="py-3.5"><ContentSkeleton count={2} label={S.s_dang_tai_ket_noi_e4acf571} /></MotionRegion></SettingsBlock></MotionRegion>;
  const wanted = toggle.isPending ? Boolean(toggle.variables) : sync.wanted;
  const failing = sync.wanted && !sync.enabled;
  const studioWanted = studio.isPending ? Boolean(studio.variables) : sync.remoteStudio;

  return (
    // Hai khối cài đặt như mọi trang: "Máy này" (mọi thứ của chính máy tính) rồi "Máy đã ghép" - cùng nhãn mục, cùng khoảng
    // cách giữa khối (trước đây danh sách thiết bị là tiêu đề con bên trong, sát hàng trên 17 px, và "Kết nối" rơi xuống dưới nó).
    <MotionRegion as="div" className="motion-reveal">
      <SettingsBlock title={S.s_may_nay_4668c138} id="phone">
      <div className="space-y-5 py-3.5">
      <div className="flex items-center justify-between gap-6">
        <label htmlFor="phone-sync" className="min-w-0 cursor-pointer">
          <span className="block text-[0.9375rem] font-medium">{SYNC_SWITCH_LABEL}</span>
          <span className={cn("mt-0.5 block text-xs leading-snug", failing ? "text-danger" : "text-fg-2")}>
            {sync.enabled
              ? S.s_may_cung_mang_thay_may_nay_la_0_ad5d3423(sync.name)
              : failing
                ? sync.error || S.s_chua_mo_duoc_cong_dong_bo_8f2a1744
                : S.s_dang_tat_may_khac_khong_thay_may_nay_8924a002}
          </span>
        </label>
        {/* Tên ngắn cho trình đọc màn hình: nhãn bọc cả dòng mô tả dài (soát a27 lỗi 11). */}
        <Switch id="phone-sync" label={SYNC_SWITCH_LABEL} checked={wanted} disabled={toggle.isPending} onCheckedChange={(value) => toggle.mutate(value)} />
      </div>

      {failing && (
        <Button size="sm" onClick={() => toggle.mutate(true)} loading={toggle.isPending}>{S.s_thu_lai_c58d068c}</Button>
      )}

      {sync.enabled && (
        <>
          <Fold storageKey="phone-sync.pair" title={S.s_ghep_thiet_bi_8de1f23c} summary={sync.pairing ? S.s_dang_hien_ma_ghep_e97b43a2 : S.s_dien_thoai_may_tinh_bang_4ade8e1e} defaultOpen={Boolean(sync.pairing)} bodyClassName="pb-3">
          <PairingPanel
            sync={sync}
            busy={pair.isPending}
            onPair={() => pair.mutate()}
            onCancel={() => cancel.mutate()}
          />
          </Fold>
          <Fold storageKey="phone-sync.permissions" title={S.s_quyen_dieu_khien_e895c2b8} summary={studioWanted ? S.s_dang_bat_70767620 : S.s_dang_tat_53bfa8b7} bodyClassName="pb-3">
          <div className="flex items-center justify-between gap-6">
            <label htmlFor="remote-studio" className="min-w-0 cursor-pointer">
              <span className="block text-sm font-medium">{S.s_dieu_khien_tu_xa_1db316de}</span>
              <span id="remote-studio-hint" className="mt-0.5 block text-[0.8125rem] text-fg-2 text-pretty">
                {studioWanted ? (
                  <>{S.s_mo_05587fd6}<Where sync={sync} />{S.s_tren_thiet_bi_da_ghep_de_lam_sach_tu_xa_b780f10e}</>
                ) : (
                  S.s_tat_thiet_bi_da_ghep_chi_tai_va_nghe_sach_284777c7
                )}
              </span>
            </label>
            <Switch
              id="remote-studio"
              label={S.s_dieu_khien_tu_xa_1db316de}
              describedBy="remote-studio-hint"
              checked={studioWanted}
              disabled={studio.isPending}
              onCheckedChange={(value) => (value ? setConfirmStudio(true) : studio.mutate(false))}
            />
          </div>
          <Dialog footer={<DialogActions>
              <Button variant="ghost" onClick={() => setConfirmStudio(false)}>{S.s_de_sau_9be0a7ab}</Button>
              <Button
                variant="primary"
                loading={studio.isPending}
                onClick={() => {
                  studio.mutate(true);
                  setConfirmStudio(false);
                }}
              >{S.s_cho_phep_f1a437f5}</Button>
            </DialogActions>}
            open={confirmStudio}
            onOpenChange={setConfirmStudio}
            title={S.s_bat_studio_tu_xa_46f8566d}
            description={S.s_bat_quyen_rieng_cho_tung_thiet_bi_de_mo_st_c9ba843b}
          >

          </Dialog>
          </Fold>
          <Fold storageKey="phone-sync.connection" title={S.s_ket_noi_02ca3cba} summary={S.s_dia_chi_va_bluetooth_affb4f78} bodyClassName="space-y-2 pb-3">
          {sync.bluetooth && (
            <p className="text-xs text-fg-3">
              {sync.bluetooth.running
                ? S.s_bluetooth_dien_thoai_da_ghep_noi_duoc_ca_k_4e4c2f78(sync.bluetooth.connections ? S.s_0_dang_ket_noi_fb5f34f5(sync.bluetooth.connections) : "")
                : sync.bluetooth.error}
            </p>
          )}
          {sync.addresses.length > 0 && (
            <p className="text-xs text-fg-3">{S.s_dien_thoai_khong_thay_may_nay_chon_nhap_di_7b0a56f9}{" "}
              <Where sync={sync} scheme={false} />.
            </p>
          )}
          {/* Chủ sách 29-09 hỏi khác mạng có dùng được không: app không cần gì riêng - mạng riêng ảo người dùng tự cài cho
              máy này một địa chỉ điện thoại tới được, và điện thoại học địa chỉ ấy mỗi lần mở Thư viện (SyncLink.refreshRoutes). */}
          <p className="text-xs text-fg-3">{S.s_ngoai_nha_nghe_sach_da_tai_hoac_noi_mang_r_43556c4f}</p>
          </Fold>
        </>
      )}
      </div>
      </SettingsBlock>
      {sync.enabled && (
        <SettingsBlock title={S.s_may_da_ghep_c2103758} id="paired">
          <div className="py-3.5">
            {deviceRows.length === 0 ? (
              // Người mới chưa có app trên điện thoại: nói chỗ lấy (chữ chọn được, không phải liên kết - trong cửa sổ app một
              // liên kết có thể điều hướng chính cửa sổ).
              <p className="select-text text-[0.8125rem] leading-relaxed text-fg-2">{S.s_chua_co_thiet_bi_app_android_file_b9da7146}<span className="font-medium text-fg">{S.s_apk_f33f6ac9}</span>{S.s_o_3584ba4c}{" "}
                <span className="font-medium text-fg">{S.s_github_com_ntanhpro1221_abook_releases_4d97effb}</span>{S.s_iphone_ipad_nghe_bang_trinh_duyet_9ae77923}</p>
            ) : (
              <ul className="divide-y divide-line">
                {deviceRows.map(({ key, state, item: device, ref }) => (
                  // Điện thoại hẹp + công tắc "Điều khiển sản xuất": hàng tự xuống dòng thay vì bóp tên máy còn "NGDtuanh-…".
                  <li key={key} ref={ref} className="motion-row" data-state={state} inert={state === "exit"}>
                  <Fold storageKey={`phone-sync.device.${device.id}`} title={device.name} summary={S.s_lan_cuoi_0_97f1a485(formatRelative(device.lastSeen))} bodyClassName="flex flex-wrap items-center gap-3 pb-3">
                    <Smartphone className="glyph shrink-0 text-fg-3" />
                    <div className="min-w-0 flex-1 basis-44">
                      <div className="truncate text-sm font-medium">{device.name}</div>
                      <div data-motion-live className="text-xs text-fg-2">{S.s_ket_noi_lan_cuoi_1ffb25d2}{formatRelative(device.lastSeen)}{S.s_ghep_ngay_04227336}{formatDate(device.pairedAt)}
                      </div>
                    </div>
                    {sync.remoteStudio && (
                      <label className="flex shrink-0 cursor-pointer items-center gap-2 text-xs text-fg-2">{S.s_dieu_khien_san_xuat_a7babdec}<Switch
                          label={S.s_dieu_khien_san_xuat_tu_0_99c2c38a(device.name)}
                          checked={Boolean(device.studio)}
                          disabled={deviceStudio.isPending}
                          onCheckedChange={(enabled) => deviceStudio.mutate({ id: device.id, enabled })}
                        />
                      </label>
                    )}
                    <Button size="sm" variant="ghost" onClick={() => setRenaming({ id: device.id, draft: device.name })}>{S.s_doi_ten_a2a0dc70}</Button>
                    <Button size="sm" variant="ghost" onClick={() => setRemoving(device)}>{S.s_bo_ghep_64f921f9}</Button>
                  </Fold>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </SettingsBlock>
      )}

      <Dialog footer={<DialogActions>
          <Button variant="ghost" onClick={() => setRemoving(null)}>{S.s_giu_lai_3c3ba2db}</Button>
          <Button
            variant="danger"
            onClick={() => {
              if (removing) revoke.mutate({ id: removing.id, name: removing.name });
              setRemoving(null);
            }}
          >{S.s_bo_ghep_64f921f9}</Button>
        </DialogActions>}
        open={removing !== null}
        onOpenChange={(open) => !open && setRemoving(null)}
        title={S.s_bo_ghep_0_e98b86ca(removing?.name ?? S.s_thiet_bi_37816a2c)}
        description={S.s_dung_tai_va_dong_bo_giu_sach_da_tai_b948aef5}
      >

      </Dialog>
      <Dialog footer={<DialogActions>
            <Button type="button" variant="ghost" onClick={() => setRenaming(null)}>{S.s_de_nguyen_2f029b4a}</Button>
            <Button type="submit" form={dialogForm1} variant="primary" disabled={!renaming?.draft.trim()} loading={rename.isPending}>{S.s_luu_e91f26c0}</Button>
          </DialogActions>}
        open={renaming !== null}
        onOpenChange={(open) => !open && setRenaming(null)}
        title={S.s_doi_ten_thiet_bi_102b76be}
        description={S.s_ten_hien_o_danh_sach_thiet_bi_da_ghep_cua_4261490a}
      >
        <form id={dialogForm1}
          onSubmit={(event) => {
            event.preventDefault();
            if (!renaming?.draft.trim()) return;
            rename.mutate({ id: renaming.id, name: renaming.draft.trim() }, { onSuccess: () => setRenaming(null) });
          }}
          className="flex flex-col gap-4"
        >
          <input
            data-autofocus
            value={renaming?.draft ?? ""}
            onChange={(event) => setRenaming((current) => current && { ...current, draft: event.target.value.slice(0, 80) })}
            aria-label={S.s_ten_thiet_bi_525223a8}
            className="h-10 w-full rounded-control border border-line bg-panel px-3 text-sm outline-none focus:border-focus"
          />

        </form>
      </Dialog>
    </MotionRegion>
  );
}
