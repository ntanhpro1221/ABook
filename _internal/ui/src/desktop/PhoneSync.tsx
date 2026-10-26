import { MoreInfo, SettingsBlock } from "@/shared/SettingsNav";
import { MotionRegion } from "@/shared/MotionRegion";
import { Fold } from "@/shared/Collapse";
import * as SwitchPrimitive from "@radix-ui/react-switch";
import { feedback } from "@/shared/feedback";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
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
    <span className="font-medium text-fg tabular-nums">{list.map((address) => `${scheme ? "https://" : ""}${address}:${sync.port}`).join(" hoặc ")}</span>
  );
  return (
    <>
      {home.length > 0 && show(home)}
      {home.length > 0 && away.length > 0 && " trong nhà, hoặc "}
      {away.length > 0 && (
        <>
          {show(away)} khi ở ngoài (thiết bị kia vào cùng mạng riêng ảo)
        </>
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
      if (enabled && !data.enabled) toast.error("Chưa bật được đồng bộ", { description: data.error });
      // Tắt xong không có gì đổi trên màn ngoài công tắc: nói một câu để biết đã tắt thật (soát UX a17).
      else if (!enabled && !data.enabled) toast("Đã tắt chia sẻ qua Wi-Fi");
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
      toast.success(`Đã bỏ ghép ${name}`);
    },
    onError,
  });
  // Đổi tên thiết bị đã ghép (soát a68 lỗi 16: tên thô "Google sdk_gphone64_x86_64").
  const rename = useMutation({
    mutationFn: ({ id, name }: { id: string; name: string }) => api<SyncView>(`/api/sync/devices/${id}/name`, { method: "POST", body: { name } }),
    onSuccess: (data, { name }) => {
      onSuccess(data);
      toast.success(`Đã đổi tên thành “${name}”`);
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

export function Switch({
  id,
  checked,
  onCheckedChange,
  disabled,
  ariaDisabled,
  label,
  labelledBy,
  describedBy,
}: {
  id?: string;
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  disabled?: boolean;
  ariaDisabled?: boolean;
  /** Tên cho trình đọc màn hình khi không có <label htmlFor> trỏ tới công tắc (soát UX 29-09: "Lịch đêm" chỉ đọc "switch"). */
  label?: string;
  /** <label> bọc cả tên lẫn đoạn mô tả dài: tên là phần tử mang mã này, đoạn mô tả đọc riêng (`describedBy`) - không thì tên đọc lên dài
   *  300+ chữ (soát a31). */
  labelledBy?: string;
  describedBy?: string;
}) {
  return (
    <SwitchPrimitive.Root
      id={id}
      aria-label={label}
      aria-labelledby={labelledBy}
      aria-describedby={describedBy}
      checked={checked}
      onCheckedChange={(value) => {
        if (ariaDisabled) return;
        feedback("toggle");
        onCheckedChange(value);
      }}
      disabled={disabled}
      aria-disabled={ariaDisabled || undefined}
      className="ui-switch touch-hit focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus disabled:opacity-50 aria-disabled:opacity-50"
    >
      <SwitchPrimitive.Thumb className="motion-switch-thumb" />
    </SwitchPrimitive.Root>
  );
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
            <p className="text-sm font-semibold">Mã ghép thiết bị</p>
            <p className="mt-2 text-[0.8125rem] text-fg-2">Trên máy kia: Cài đặt › Thiết bị → chọn {sync.name} → nhập mã.</p>
            <MoreInfo label="Cách dùng mã" className="mt-2">
              Mã dùng một lần để máy kia nghe thư viện này.
              {sync.addresses.length > 0 && <span className="block">Địa chỉ: <Where sync={sync} scheme={false} /></span>}
              {sync.remoteStudio && <span className="block">Trình duyệt: mở <Where sync={sync} /> rồi nhập mã.</span>}
            </MoreInfo>
          </div>
          {/* Mã và dòng hết hạn cùng một trục giữa (soát UX a19): khoảng cách chữ thừa sau số cuối đã được bù ở bên trái. */}
          <div className="text-center">
            <div
              aria-label={`Mã ghép nối: ${code.split("").join(" ")}`}
              className="pl-[0.14em] text-[2.125rem] font-semibold leading-none tracking-[0.14em] text-accent-text tabular-nums"
            >
              {code.slice(0, 3)}
              <span className="inline-block w-3" />
              {code.slice(3)}
            </div>
            <div className="mt-2 text-xs text-fg-2 tabular-nums">
              Hết hạn sau {minutes}:{seconds}
            </div>
          </div>
        </div>
        {/* Dòng vân tay dài (64 ký tự): để NGOÀI hàng hướng dẫn / mã, không thì nó chiếm hết bề rộng và đẩy mã xuống dưới. */}
        {sync.fingerprint && <p className="mt-3 break-all text-xs text-fg-3" title="Đối chiếu vân tay với máy kia">Vân tay: {sync.fingerprint}</p>}
        <DialogActions>
          {/* Chỉ huỷ mã đang hiện, không gỡ thiết bị nào - "Huỷ ghép" dễ hiểu thành gỡ thiết bị (soát UX 29-09). */}
          <Button size="sm" variant="ghost" onClick={onCancel}>
            Huỷ mã này
          </Button>
        </DialogActions>
      </MotionRegion>
    );
  }
  if (sync.pairingBlocked) {
    return (
      <MotionRegion as="div" motionKey="blocked" className="flex items-start gap-3 py-4">
        <ShieldAlert className="mt-0.5 glyph shrink-0 text-warning" />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold">Mã bị khoá</p>
          <p className="mt-0.5 text-[0.8125rem] text-fg-2">
            Sai 5 lần; chỉ tạo mã mới khi bạn đang ghép thiết bị.
          </p>
        </div>
        <Button size="sm" onClick={onPair} loading={busy}>
          Tạo mã mới
        </Button>
      </MotionRegion>
    );
  }
  return (
    <MotionRegion motionKey="idle"><Button icon={Smartphone} onClick={onPair} loading={busy}>
      Ghép thiết bị mới
    </Button></MotionRegion>
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
    if (added) toast.success(`Đã ghép ${added.name}`);
  }, [sync]);

  // Khung chờ / lỗi và nội dung có CÙNG gốc (vùng ngoài cùng bên dưới): tải xong thì mờ qua, không gỡ cả cây làm khung chờ mất cứng.
  if (error && !sync) return <MotionRegion as="div" className="motion-reveal"><SettingsBlock title="Máy này" id="phone"><MotionRegion fadeThrough className="py-3.5"><InlineError message="Bạn hãy thử tải lại cài đặt kết nối." onRetry={() => void refetch()} /></MotionRegion></SettingsBlock></MotionRegion>;
  if (!sync) return <MotionRegion as="div" className="motion-reveal"><SettingsBlock title="Máy này" id="phone"><MotionRegion fadeThrough className="py-3.5"><ContentSkeleton count={2} label="Đang tải kết nối" /></MotionRegion></SettingsBlock></MotionRegion>;
  const wanted = toggle.isPending ? Boolean(toggle.variables) : sync.wanted;
  const failing = sync.wanted && !sync.enabled;
  const studioWanted = studio.isPending ? Boolean(studio.variables) : sync.remoteStudio;

  return (
    // Hai khối cài đặt như mọi trang: "Máy này" (mọi thứ của chính máy tính) rồi "Máy đã ghép" - cùng nhãn mục, cùng khoảng
    // cách giữa khối (trước đây danh sách thiết bị là tiêu đề con bên trong, sát hàng trên 17 px, và "Kết nối" rơi xuống dưới nó).
    <MotionRegion as="div" className="motion-reveal">
      <SettingsBlock title="Máy này" id="phone">
      <div className="space-y-5 py-3.5">
      <div className="flex items-center justify-between gap-6">
        <label htmlFor="phone-sync" className="min-w-0 cursor-pointer">
          <span className="block text-[0.9375rem] font-medium">{SYNC_SWITCH_LABEL}</span>
          <span className={cn("mt-0.5 block text-xs leading-snug", failing ? "text-danger" : "text-fg-2")}>
            {sync.enabled
              ? `Máy cùng mạng thấy máy này là “${sync.name}”.`
              : failing
                ? sync.error || "Chưa mở được cổng đồng bộ."
                : "Đang tắt - máy khác không thấy máy này."}
          </span>
        </label>
        {/* Tên ngắn cho trình đọc màn hình: nhãn bọc cả dòng mô tả dài (soát a27 lỗi 11). */}
        <Switch id="phone-sync" label={SYNC_SWITCH_LABEL} checked={wanted} disabled={toggle.isPending} onCheckedChange={(value) => toggle.mutate(value)} />
      </div>

      {failing && (
        <Button size="sm" onClick={() => toggle.mutate(true)} loading={toggle.isPending}>
          Thử lại
        </Button>
      )}

      {sync.enabled && (
        <>
          <Fold storageKey="phone-sync.pair" title="Ghép thiết bị" summary={sync.pairing ? "Đang hiện mã ghép" : "Điện thoại, máy tính bảng"} defaultOpen={Boolean(sync.pairing)} bodyClassName="pb-3">
          <PairingPanel
            sync={sync}
            busy={pair.isPending}
            onPair={() => pair.mutate()}
            onCancel={() => cancel.mutate()}
          />
          </Fold>
          <Fold storageKey="phone-sync.permissions" title="Quyền điều khiển" summary={studioWanted ? "Đang bật" : "Đang tắt"} bodyClassName="pb-3">
          <div className="flex items-center justify-between gap-6">
            <label htmlFor="remote-studio" className="min-w-0 cursor-pointer">
              <span className="block text-sm font-medium">Điều khiển từ xa</span>
              <span id="remote-studio-hint" className="mt-0.5 block text-[0.8125rem] text-fg-2 text-pretty">
                {studioWanted ? (
                  <>
                    Mở <Where sync={sync} /> trên thiết bị đã ghép để làm sách từ xa.
                  </>
                ) : (
                  "Tắt: thiết bị đã ghép chỉ tải và nghe sách."
                )}
              </span>
            </label>
            <Switch
              id="remote-studio"
              label="Điều khiển từ xa"
              describedBy="remote-studio-hint"
              checked={studioWanted}
              disabled={studio.isPending}
              onCheckedChange={(value) => (value ? setConfirmStudio(true) : studio.mutate(false))}
            />
          </div>
          <Dialog footer={<DialogActions>
              <Button variant="ghost" onClick={() => setConfirmStudio(false)}>
                Để sau
              </Button>
              <Button
                variant="primary"
                loading={studio.isPending}
                onClick={() => {
                  studio.mutate(true);
                  setConfirmStudio(false);
                }}
              >
                Cho phép
              </Button>
            </DialogActions>}
            open={confirmStudio}
            onOpenChange={setConfirmStudio}
            title="Bật Studio từ xa?"
            description="Bật quyền riêng cho từng thiết bị để mở Studio trong trình duyệt."
          >

          </Dialog>
          </Fold>
          <Fold storageKey="phone-sync.connection" title="Kết nối" summary="Địa chỉ và Bluetooth" bodyClassName="space-y-2 pb-3">
          {sync.bluetooth && (
            <p className="text-xs text-fg-3">
              {sync.bluetooth.running
                ? `Bluetooth: điện thoại đã ghép nối được cả khi khác Wi-Fi${
                    sync.bluetooth.connections ? ` - ${sync.bluetooth.connections} đang kết nối` : ""
                  }.`
                : sync.bluetooth.error}
            </p>
          )}
          {sync.addresses.length > 0 && (
            <p className="text-xs text-fg-3">
              Điện thoại không thấy máy này? Chọn “Nhập địa chỉ” rồi gõ{" "}
              <Where sync={sync} scheme={false} />.
            </p>
          )}
          {/* Chủ sách 29-09 hỏi khác mạng có dùng được không: app không cần gì riêng - mạng riêng ảo người dùng tự cài cho
              máy này một địa chỉ điện thoại tới được, và điện thoại học địa chỉ ấy mỗi lần mở Thư viện (SyncLink.refreshRoutes). */}
          <p className="text-xs text-fg-3">
            Ngoài nhà: nghe sách đã tải, hoặc nối mạng riêng ảo để nghe thẳng.
          </p>
          </Fold>
        </>
      )}
      </div>
      </SettingsBlock>
      {sync.enabled && (
        <SettingsBlock title="Máy đã ghép" id="paired">
          <div className="py-3.5">
            {deviceRows.length === 0 ? (
              // Người mới chưa có app trên điện thoại: nói chỗ lấy (chữ chọn được, không phải liên kết - trong cửa sổ app một
              // liên kết có thể điều hướng chính cửa sổ).
              <p className="select-text text-[0.8125rem] leading-relaxed text-fg-2">
                Chưa có thiết bị. App Android: file <span className="font-medium text-fg">.apk</span> ở{" "}
                <span className="font-medium text-fg">github.com/ntanhpro1221/ABook/releases</span>. iPhone, iPad: nghe bằng trình duyệt.
              </p>
            ) : (
              <ul className="divide-y divide-line">
                {deviceRows.map(({ key, state, item: device, ref }) => (
                  // Điện thoại hẹp + công tắc "Điều khiển sản xuất": hàng tự xuống dòng thay vì bóp tên máy còn "NGDtuanh-…".
                  <li key={key} ref={ref} className="motion-row" data-state={state} inert={state === "exit"}>
                  <Fold storageKey={`phone-sync.device.${device.id}`} title={device.name} summary={`Lần cuối ${formatRelative(device.lastSeen)}`} bodyClassName="flex flex-wrap items-center gap-3 pb-3">
                    <Smartphone className="glyph shrink-0 text-fg-3" />
                    <div className="min-w-0 flex-1 basis-44">
                      <div className="truncate text-sm font-medium">{device.name}</div>
                      <div className="text-xs text-fg-2">
                        Kết nối lần cuối {formatRelative(device.lastSeen)} · ghép ngày {formatDate(device.pairedAt)}
                      </div>
                    </div>
                    {sync.remoteStudio && (
                      <label className="flex shrink-0 cursor-pointer items-center gap-2 text-xs text-fg-2">
                        Điều khiển sản xuất
                        <Switch
                          label={`Điều khiển sản xuất từ ${device.name}`}
                          checked={Boolean(device.studio)}
                          disabled={deviceStudio.isPending}
                          onCheckedChange={(enabled) => deviceStudio.mutate({ id: device.id, enabled })}
                        />
                      </label>
                    )}
                    <Button size="sm" variant="ghost" onClick={() => setRenaming({ id: device.id, draft: device.name })}>
                      Đổi tên
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => setRemoving(device)}>
                      Bỏ ghép
                    </Button>
                  </Fold>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </SettingsBlock>
      )}

      <Dialog footer={<DialogActions>
          <Button variant="ghost" onClick={() => setRemoving(null)}>
            Giữ lại
          </Button>
          <Button
            variant="danger"
            onClick={() => {
              if (removing) revoke.mutate({ id: removing.id, name: removing.name });
              setRemoving(null);
            }}
          >
            Bỏ ghép
          </Button>
        </DialogActions>}
        open={removing !== null}
        onOpenChange={(open) => !open && setRemoving(null)}
        title={`Bỏ ghép ${removing?.name ?? "thiết bị"}?`}
        description="Dừng tải và đồng bộ; giữ sách đã tải."
      >

      </Dialog>
      <Dialog footer={<DialogActions>
            <Button type="button" variant="ghost" onClick={() => setRenaming(null)}>
              Để nguyên
            </Button>
            <Button type="submit" form={dialogForm1} variant="primary" disabled={!renaming?.draft.trim()} loading={rename.isPending}>
              Lưu
            </Button>
          </DialogActions>}
        open={renaming !== null}
        onOpenChange={(open) => !open && setRenaming(null)}
        title="Đổi tên thiết bị"
        description="Tên hiện ở danh sách thiết bị đã ghép của máy này."
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
            aria-label="Tên thiết bị"
            className="h-10 w-full rounded-control border border-line bg-panel px-3 text-sm outline-none focus:border-focus"
          />

        </form>
      </Dialog>
    </MotionRegion>
  );
}
