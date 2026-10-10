import * as SwitchPrimitive from "@radix-ui/react-switch";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ShieldAlert, Smartphone } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { api } from "@/studio/api";
import { Button, Dialog, Skeleton } from "@/shared/ui";
import { cn } from "@/shared/cn";
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
      else if (!enabled && !data.enabled) toast("Đã tắt chia sẻ qua Wi-Fi", { description: "Máy khác không kết nối vào máy này nữa cho tới khi bạn bật lại." });
    },
    onError,
  });
  const pair = useMutation({ mutationFn: () => api<SyncView>("/api/sync/pairing", { method: "POST" }), onSuccess, onError });
  const cancel = useMutation({ mutationFn: () => api<SyncView>("/api/sync/pairing", { method: "DELETE" }), onSuccess, onError });
  const revoke = useMutation({
    mutationFn: (id: string) => api<SyncView>(`/api/sync/devices/${id}`, { method: "DELETE" }),
    onSuccess,
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
  return { ...query, toggle, pair, cancel, revoke, studio, deviceStudio };
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
  label,
}: {
  id?: string;
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  disabled?: boolean;
  /** Tên cho trình đọc màn hình khi không có <label htmlFor> trỏ tới công tắc (soát UX 29-09: "Lịch đêm" chỉ đọc "switch"). */
  label?: string;
}) {
  return (
    <SwitchPrimitive.Root
      id={id}
      aria-label={label}
      checked={checked}
      onCheckedChange={onCheckedChange}
      disabled={disabled}
      className="touch-hit relative inline-flex h-6 w-11 shrink-0 items-center rounded-full bg-switch-off transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:opacity-50 data-[state=checked]:bg-accent"
    >
      <SwitchPrimitive.Thumb className="block size-5 translate-x-0.5 rounded-full bg-white shadow-sm transition-transform duration-150 data-[state=checked]:translate-x-[22px]" />
    </SwitchPrimitive.Root>
  );
}

function PairingPanel({ sync, onPair, onCancel, busy }: { sync: SyncView; onPair: () => void; onCancel: () => void; busy: boolean }) {
  const secondsLeft = useSecondsLeft(sync.pairing?.expiresAt);
  if (sync.pairing && secondsLeft > 0) {
    const { code } = sync.pairing;
    const minutes = Math.floor(secondsLeft / 60);
    const seconds = String(secondsLeft % 60).padStart(2, "0");
    return (
      <div className="rounded-xl border border-accent/35 bg-accent-soft p-5" aria-live="polite">
        <div className="flex flex-wrap items-center justify-between gap-6">
          <div className="min-w-0">
            <p className="text-sm font-semibold">Nhập mã này trên thiết bị cần ghép</p>
            <ol className="mt-2 list-decimal space-y-1 pl-4 text-[13px] text-fg-2">
              <li>
                Mở ABook trên điện thoại, vào <span className="font-medium text-fg">Tải sách</span>.
              </li>
              <li>
                Chọn máy <span className="font-medium text-fg">{sync.name}</span>.
              </li>
              <li>Gõ mã 6 số này. Mã chỉ dùng được một lần.</li>
            </ol>
            {/* Địa chỉ luôn hiện ở đây (máy tính khác không tự thấy máy này thì gõ địa chỉ), không chỉ khi bật điều khiển sản xuất. */}
            {sync.addresses.length > 0 && (
              <p className="mt-2 text-[13px] text-fg-2">
                Địa chỉ máy này: <Where sync={sync} scheme={false} /> - gõ vào ô “Địa chỉ máy kia” khi ghép từ máy tính khác.
              </p>
            )}
            {sync.remoteStudio && (
              <p className="mt-2 text-[13px] text-fg-2">
                Trình duyệt: mở <Where sync={sync} /> rồi gõ mã. Trình duyệt sẽ báo trang “không an toàn” vì chứng chỉ do
                chính máy này cấp - cứ chọn tiếp tục.
              </p>
            )}
          </div>
          {/* Mã và dòng hết hạn cùng một trục giữa (soát UX a19): khoảng cách chữ thừa sau số cuối đã được bù ở bên trái. */}
          <div className="text-center">
            <div
              aria-label={`Mã ghép nối: ${code.split("").join(" ")}`}
              className="pl-[0.14em] text-[34px] font-semibold leading-none tracking-[0.14em] text-accent-text tabular-nums"
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
        {sync.fingerprint && (
          <details className="group mt-3 text-[12px] text-fg-3">
            <summary className="cursor-pointer list-none text-fg-2 [&::-webkit-details-marker]:hidden">Chi tiết kỹ thuật</summary>
            <p className="mt-1 break-words">
              Vân tay của máy này: <span className="tabular-nums">{sync.fingerprint}</span>. Sau khi ghép, máy kia ghi lại vân tay này; đối chiếu
              với dòng “Vân tay” dưới tên máy này trên màn ghép của máy kia (máy tính: Cài đặt → Máy tính khác; điện thoại: màn Thiết bị).
            </p>
          </details>
        )}
        <div className="mt-4 flex justify-end">
          {/* Chỉ huỷ mã đang hiện, không gỡ thiết bị nào - "Huỷ ghép" dễ hiểu thành gỡ thiết bị (soát UX 29-09). */}
          <Button size="sm" variant="ghost" onClick={onCancel}>
            Huỷ mã này
          </Button>
        </div>
      </div>
    );
  }
  if (sync.pairingBlocked) {
    return (
      <div className="flex items-start gap-3 rounded-xl border border-warning/40 bg-warning-soft p-4">
        <ShieldAlert className="mt-0.5 size-[18px] shrink-0 text-warning" />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold">Mã đã bị huỷ vì nhập sai 5 lần</p>
          <p className="mt-0.5 text-[13px] text-fg-2">
            Nếu gõ nhầm thì tạo mã mới. Nếu không phải, có thiết bị lạ trong mạng đang đoán mã - đừng tạo mã khi
            chưa cần.
          </p>
        </div>
        <Button size="sm" onClick={onPair} loading={busy}>
          Tạo mã mới
        </Button>
      </div>
    );
  }
  return (
    <Button icon={Smartphone} onClick={onPair} loading={busy}>
      Ghép thiết bị mới
    </Button>
  );
}

/** Mục "Điện thoại" trong Cài đặt: bật đồng bộ, ghép nối bằng mã 6 số, quản lý điện thoại đã ghép. */
export function PhoneSync() {
  const { data: sync, toggle, pair, cancel, revoke, studio, deviceStudio } = useSync();
  const [removing, setRemoving] = useState<SyncDevice | null>(null);
  // Bật điều khiển sản xuất từ xa phải hỏi lại (soát UX 29-09): thiết bị đã ghép bắt đầu / dừng sản xuất qua http trong mạng.
  const [confirmStudio, setConfirmStudio] = useState(false);
  const known = useRef<Set<string> | null>(null);

  // Điện thoại vừa nhập đúng mã: nó xuất hiện trong danh sách - báo ngay, người dùng đang nhìn vào máy tính.
  useEffect(() => {
    if (!sync) return;
    const previous = known.current;
    known.current = new Set(sync.devices.map((device) => device.id));
    const added = previous ? sync.devices.find((device) => !previous.has(device.id)) : undefined;
    if (added) toast.success(`Đã ghép ${added.name}`, { description: "Thiết bị này giờ tải được sách và đồng bộ chỗ đang nghe." });
  }, [sync]);

  if (!sync) return <Skeleton className="h-20" />;
  const wanted = toggle.isPending ? Boolean(toggle.variables) : sync.wanted;
  const failing = sync.wanted && !sync.enabled;
  const studioWanted = studio.isPending ? Boolean(studio.variables) : sync.remoteStudio;

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between gap-6">
        <label htmlFor="phone-sync" className="min-w-0 cursor-pointer">
          <span className="block text-sm font-medium">{SYNC_SWITCH_LABEL}</span>
          <span className={cn("mt-0.5 block text-[13px]", failing ? "text-danger" : "text-fg-2")}>
            {sync.enabled
              ? `Điện thoại và máy tính cùng mạng sẽ thấy máy này với tên “${sync.name}”.`
              : failing
                ? sync.error || "Chưa mở được cổng đồng bộ."
                : "Đang tắt - điện thoại và máy tính khác không tìm thấy máy này."}
          </span>
        </label>
        <Switch id="phone-sync" checked={wanted} disabled={toggle.isPending} onCheckedChange={(value) => toggle.mutate(value)} />
      </div>

      {failing && (
        <Button size="sm" onClick={() => toggle.mutate(true)} loading={toggle.isPending}>
          Thử lại
        </Button>
      )}

      {sync.enabled && (
        <>
          <PairingPanel
            sync={sync}
            busy={pair.isPending}
            onPair={() => pair.mutate()}
            onCancel={() => cancel.mutate()}
          />
          <div className="flex items-start justify-between gap-6">
            <label htmlFor="remote-studio" className="min-w-0 cursor-pointer">
              <span className="block text-sm font-medium">Cho phép điều khiển sản xuất từ thiết bị đã ghép</span>
              <span className="mt-0.5 block text-[13px] text-fg-2 text-pretty">
                {studioWanted ? (
                  <>
                    Trên điện thoại, máy tính bảng hay máy tính khác, mở <Where sync={sync} /> để xem tiến độ, bắt đầu
                    hay dừng, duyệt “Việc cần duyệt” và nghe sách. Lần đầu nhập mã ghép như điện thoại.
                  </>
                ) : (
                  "Đang tắt - thiết bị đã ghép chỉ tải và nghe sách."
                )}
              </span>
            </label>
            <Switch
              id="remote-studio"
              checked={studioWanted}
              disabled={studio.isPending}
              onCheckedChange={(value) => (value ? setConfirmStudio(true) : studio.mutate(false))}
            />
          </div>
          <Dialog
            open={confirmStudio}
            onOpenChange={setConfirmStudio}
            title="Cho thiết bị đã ghép điều khiển sản xuất?"
            description="Điện thoại, máy tính bảng hay máy tính đã ghép sẽ mở được Studio của máy này trong trình duyệt: xem tiến độ, bắt đầu hay dừng tạo sách, duyệt “Việc cần duyệt”. Mỗi thiết bị vẫn cần được cho phép riêng ở danh sách bên dưới."
          >
            <div className="flex justify-end gap-2">
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
            </div>
          </Dialog>
          <div>
            <h3 className="text-xs font-semibold uppercase tracking-[0.06em] text-fg-3">Thiết bị đã ghép</h3>
            {sync.devices.length === 0 ? (
              // Người mới chưa có app trên điện thoại: nói chỗ lấy (chữ chọn được, không phải liên kết - trong cửa sổ app một
              // liên kết có thể điều hướng chính cửa sổ).
              <p className="mt-2 select-text text-[13px] leading-relaxed text-fg-2">
                Chưa có thiết bị nào. Điện thoại Android chưa có app: tải file <span className="font-medium text-fg">.apk</span> ở{" "}
                <span className="font-medium text-fg">github.com/ntanhpro1221/ABook/releases</span> rồi cài. iPhone, iPad: không cần
                app - ghép rồi nghe bằng trình duyệt.
              </p>
            ) : (
              <ul className="mt-2 divide-y divide-line rounded-xl border border-line">
                {sync.devices.map((device) => (
                  // Điện thoại hẹp + công tắc "Điều khiển sản xuất": hàng tự xuống dòng thay vì bóp tên máy còn "NGDtuanh-…".
                  <li key={device.id} className="flex flex-wrap items-center gap-x-3 gap-y-2 px-4 py-3">
                    <Smartphone className="size-[18px] shrink-0 text-fg-3" />
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
                          checked={Boolean(device.studio)}
                          disabled={deviceStudio.isPending}
                          onCheckedChange={(enabled) => deviceStudio.mutate({ id: device.id, enabled })}
                        />
                      </label>
                    )}
                    <Button size="sm" variant="ghost" onClick={() => setRemoving(device)}>
                      Thôi ghép
                    </Button>
                  </li>
                ))}
              </ul>
            )}
          </div>
          {sync.bluetooth && (
            <p className="text-xs text-fg-3">
              {sync.bluetooth.running
                ? `Bluetooth: điện thoại đã ghép Bluetooth với máy này kết nối được cả khi không chung Wi-Fi${
                    sync.bluetooth.connections ? ` - ${sync.bluetooth.connections} đang kết nối` : ""
                  }.`
                : sync.bluetooth.error}
            </p>
          )}
          {sync.addresses.length > 0 && (
            <p className="text-xs text-fg-3">
              Điện thoại không tự thấy máy này? Chọn “Nhập địa chỉ máy tính” trên điện thoại rồi gõ{" "}
              <Where sync={sync} scheme={false} />.
            </p>
          )}
          {/* Chủ sách 29-09 hỏi khác mạng có dùng được không: app không cần gì riêng - mạng riêng ảo người dùng tự cài cho
              máy này một địa chỉ điện thoại tới được, và điện thoại học địa chỉ ấy mỗi lần mở Thư viện (SyncLink.refreshRoutes). */}
          <p className="text-xs text-fg-3">
            Ra khỏi nhà: sách đã tải về điện thoại thì nghe ở đâu cũng được. Muốn nghe thẳng từ máy này hay điều khiển từ xa,
            cho máy này và điện thoại vào cùng một mạng riêng ảo (VPN - ví dụ Tailscale, ZeroTier, NetBird, WireGuard), rồi mở Thư viện
            trên điện thoại một lần khi còn ở nhà - ra ngoài điện thoại tự nối qua đó.
          </p>
        </>
      )}

      <Dialog
        open={removing !== null}
        onOpenChange={(open) => !open && setRemoving(null)}
        title={`Thôi ghép ${removing?.name ?? "thiết bị"}?`}
        description="Thiết bị này sẽ không tải sách hay đồng bộ chỗ đang nghe được nữa, cho tới khi ghép lại. Sách đã tải về thiết bị vẫn nghe được."
      >
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={() => setRemoving(null)}>
            Để nguyên
          </Button>
          <Button
            variant="danger"
            onClick={() => {
              if (removing) revoke.mutate(removing.id);
              setRemoving(null);
            }}
          >
            Thôi ghép
          </Button>
        </div>
      </Dialog>
    </div>
  );
}
