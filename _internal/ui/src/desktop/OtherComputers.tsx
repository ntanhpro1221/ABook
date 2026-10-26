import { MotionRegion } from "@/shared/MotionRegion";
import { AnimatedRows, MotionPresence } from "@/shared/MotionPresence";
import { Fold } from "@/shared/Collapse";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bluetooth, Clapperboard, Laptop, Moon, Radar, RefreshCw, Smartphone, Stethoscope, Unplug } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { toast } from "@/shared/toast";
import { api } from "@/studio/api";
import { cn } from "@/shared/cn";
import { formatFingerprint, formatRelative } from "@/shared/format";
import { peerPage } from "@/shared/peerStudio";
import { SYNC_SWITCH_LABEL } from "@/shared/syncSwitch";
import { Button, ContentSkeleton, IconButton, InlineError, SelectionMark, Tooltip } from "@/shared/ui";
import type { UnsentEdits } from "@/shared/unpair";
import { useUnpair } from "@/shared/useUnpair";
import { bluetoothAddress, deviceKindLabel, isBluetoothHost, routeLine, wakingLine, type PairedDevice, type Waking } from "./computerRoutes";
import { PhoneDiagnostics } from "./PhoneDiagnostics";

// Máy tính khác (webui/remote_books.py): ghép bằng địa chỉ + mã 6 số đang hiện trên máy ấy - đúng mã điện thoại dùng - rồi
// thư viện của máy ấy hiện trong Thư viện của máy này ("Trên <máy>"). Chương tải về lần đầu nghe tới và được giữ lại, nên
// phần đã nghe vẫn nghe được khi máy kia tắt. Không chung Wi-Fi thì đi Bluetooth: ghép bằng địa chỉ Bluetooth của điện thoại
// (chọn từ thiết bị đã ghép ở Windows), hay máy đã ghép Wi-Fi có thêm đường Bluetooth dự phòng.

const MENU_ITEM = "flex h-auto cursor-default items-start gap-2 rounded-control px-2 py-1.5 text-sm outline-none data-[disabled]:opacity-60 data-[highlighted]:bg-hover";

interface Computer {
  id: string;
  name: string;
  host: string;
  port: number;
  connectedVia?: string;
  lastSeen?: number;
  error?: string;
  /** Vân tay chứng chỉ TLS máy kia đưa ra lúc ghép (hex) - hiện để đối chiếu với dòng "Vân tay" bên máy kia. */
  fingerprint?: string;
  /** Địa chỉ Bluetooth dự phòng của máy ghép qua Wi-Fi (webui/remote_books.py: máy tự tìm theo tên, hay chọn ở đây). */
  bt?: string;
  kind?: "phone" | "computer";
  /** Đang chờ máy ấy dậy: nối được tới máy mà ABook bên ấy chưa trả lời (điện thoại tắt màn hình). */
  waking?: Waking;
}

interface ComputersView {
  name: string;
  computers: Computer[];
  /** Danh sách máy đã ghép bị hỏng và đã làm lại: một dòng cho người dùng (máy chủ giữ bản hỏng). */
  broken?: string;
}

/** Máy tính ABook đang bật kết nối trong mạng (remote_books.discover - cùng cách điện thoại tìm máy tính). */
interface FoundComputer {
  name: string;
  host: string;
  port: number;
  paired: boolean;
  /** Điện thoại đang bật "Cho máy khác nghe thư viện này" (LibraryServer.kt) cũng trả lời. */
  kind?: "computer" | "phone";
}

export function OtherComputers() {
  const client = useQueryClient();
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["computers"],
    queryFn: () => api<ComputersView>("/api/computers"),
    // Đang chờ một máy dậy: xem lại thường xuyên để thấy nó trả lời (hay hết hạn chờ).
    refetchInterval: (query) => (query.state.data?.computers.some((computer) => computer.waking) ? 2000 : false),
  });
  const waking = data?.computers.filter((computer) => computer.waking).map((computer) => computer.id).join(",") ?? "";
  const wasWaking = useRef("");
  useEffect(() => {
    // Một máy vừa thôi "đang ngủ" (đã trả lời, hay hết hạn): sách của nó có thể vừa hiện ra.
    if (wasWaking.current && wasWaking.current !== waking) void client.invalidateQueries({ queryKey: ["listen", "library"] });
    wasWaking.current = waking;
  }, [waking, client]);
  const [address, setAddress] = useState("");
  const [code, setCode] = useState("");
  // Thiết bị Bluetooth đã ghép ở Windows: chỉ đọc danh sách của hệ điều hành; lỗi hay rỗng thì thôi, không chặn gì.
  const paired = useQuery({
    queryKey: ["computers", "bluetooth"],
    queryFn: () => api<{ devices: PairedDevice[] }>("/api/computers/bluetooth"),
    staleTime: 30_000,
    retry: false,
  });
  const devices = paired.data?.devices ?? [];
  const done = (view: ComputersView) => {
    client.setQueryData(["computers"], view);
    void client.invalidateQueries({ queryKey: ["listen", "library"] });
  };
  const pair = useMutation({
    mutationFn: () => api<ComputersView>("/api/computers", { method: "POST", body: { address, code } }),
    onSuccess: (view) => {
      // Máy vừa ghép = máy có trong danh sách mới mà danh sách cũ chưa có: nói tên thật, không để mẫu “<tên máy>” (soát UX a11).
      const known = new Set(data?.computers.map((computer) => computer.id));
      const name = view.computers.find((computer) => !known.has(computer.id))?.name;
      done(view);
      setAddress("");
      setCode("");
      toast.success(name ? `Đã ghép ${name}` : "Đã ghép");
    },
    onError: (error: Error) => toast.error("Chưa ghép được", { description: error.message }),
  });
  const refresh = useMutation({
    mutationFn: () => api<ComputersView>("/api/computers/refresh", { method: "POST" }),
    onSuccess: done,
  });
  const stopWaiting = useMutation({
    mutationFn: (id: string) => api<ComputersView>(`/api/computers/${id}/stop-waiting`, { method: "POST" }),
    onSuccess: done,
  });
  // Thôi ghép xoá thư mục đệm của máy ấy (phần đã tải, phần sửa chưa gửi): có gì để mất thì hỏi trước, nói rõ mất gì và giữ gì (shared/unpair.ts).
  const unpair = useUnpair<Computer>({
    self: "máy tính",
    name: (computer) => computer.name,
    reachable: (computer) => {
      const current = data?.computers.find((item) => item.id === computer.id) ?? computer;
      return !current.error && !current.waking;
    },
    unsent: (computer) => api<UnsentEdits>(`/api/computers/${computer.id}/unsent`),
    run: async (computer, choice) => {
      const edits = choice === null ? "" : `?edits=${choice}`;
      done(await api<ComputersView>(`/api/computers/${computer.id}${edits}`, { method: "DELETE" }));
    },
  });
  const setBluetooth = useMutation({
    mutationFn: ({ id, address }: { id: string; address: string }) =>
      api<ComputersView>(`/api/computers/${id}/bluetooth`, { method: "POST", body: { address } }),
    onSuccess: (view, { address }) => {
      done(view);
      toast.success(address ? "Đã chọn Bluetooth dự phòng" : "Không dùng Bluetooth dự phòng nữa");
    },
    onError: (error: Error) => toast.error("Chưa chọn được", { description: error.message }),
  });
  const discover = useMutation({
    mutationFn: () => api<{ found: FoundComputer[] }>("/api/computers/discover"),
    onError: (error: Error) => toast.error("Không tìm được", { description: error.message }),
  });
  const codeInput = useRef<HTMLInputElement>(null);
  // Hộp "Chẩn đoán" của một điện thoại đã ghép (nhật ký + tình trạng, lấy qua kết nối đã ghép).
  const [diagnosing, setDiagnosing] = useState<Computer | null>(null);
  const lastDiagnosing = useRef(diagnosing);
  if (diagnosing) lastDiagnosing.current = diagnosing;
  const choose = (found: FoundComputer) => {
    setAddress(`${found.host}:${found.port}`);
    codeInput.current?.focus();
  };
  const chooseDevice = (device: PairedDevice) => {
    setAddress(device.address);
    codeInput.current?.focus();
  };
  if (error && !data) return <MotionRegion fadeThrough><InlineError message="Bạn hãy kiểm tra kết nối rồi tải lại thiết bị." onRetry={() => void refetch()} /></MotionRegion>;
  if (isLoading || !data) return <MotionRegion fadeThrough><ContentSkeleton count={2} label="Đang tải thiết bị" /></MotionRegion>;
  // Đã ghép rồi thì không mời ghép lại.
  const pairedAddresses = new Set(data.computers.filter((computer) => isBluetoothHost(computer.host)).map((computer) => bluetoothAddress(computer)));
  const unpaired = devices.filter((device) => !pairedAddresses.has(device.address));
  return (
    <MotionRegion as="div" className="motion-reveal space-y-4">
      <MotionPresence open={Boolean(data.broken)}>
        <p className="text-sm text-warning" role="status">
          {data.broken}
        </p>
      </MotionPresence>
      {/* Ghép / thôi ghép: hàng mở / khép tại chỗ như PhoneSync; đổi trong hàng (đang chờ, lỗi) thì hàng tự mờ qua. data-motion-live: cả
          khối không mờ lại theo từng hàng. */}
      <MotionPresence open={data.computers.length > 0}>
        <div data-motion-live="">
        <AnimatedRows className="divide-y divide-line" items={data.computers} keyOf={(computer) => computer.id}>
          {(computer) => (
            <MotionRegion>
              <Fold storageKey={`other-computers.${computer.id}`} title={computer.name} heading="h3" summary={computer.waking ? "Đang chờ" : computer.error ? "Cần kiểm tra" : "Đã ghép"} bodyClassName="flex flex-wrap items-center gap-3 pb-3">
              <Laptop className="size-5 shrink-0 text-fg-2" />
              <div className="min-w-0 flex-1">
                {computer.waking ? (
                  <div className="text-xs text-fg-2" role="status">
                    <Moon className="mr-1.5 -mt-0.5 inline size-3.5 align-middle" aria-hidden />
                    {wakingLine(computer)}
                    <button
                      type="button"
                      className="ml-2 rounded-control text-accent-text underline-offset-2 hover:underline disabled:opacity-60"
                      disabled={stopWaiting.isPending}
                      onClick={() => stopWaiting.mutate(computer.id)}
                    >
                      Thôi chờ
                    </button>
                  </div>
                ) : (
                  // Lời báo lỗi dài (chứng chỉ máy kia đổi...) xuống dòng cho đọc hết, không cắt giữa chừng.
                  <div className={cn("text-xs", computer.error ? "text-danger [overflow-wrap:anywhere]" : "truncate text-fg-2")}>
                    {computer.error
                      ? computer.error
                      : `${routeLine(computer, devices)}${computer.lastSeen ? ` · thấy ${formatRelative(computer.lastSeen)}` : ""}`}
                  </div>
                )}
                {computer.fingerprint && (
                  // 8 ký tự đầu đủ để đối chiếu với máy kia; đủ 64 ký tự ở chú giải khi rê chuột vào.
                  <div className="mt-0.5 break-words text-[0.6875rem] text-fg-3" title={formatFingerprint(computer.fingerprint)}>
                    Vân tay <span className="tabular-nums">{formatFingerprint(computer.fingerprint).slice(0, 9)}</span>…
                  </div>
                )}
              </div>
              {/* Điện thoại không có chú giải khi rê chuột: ba nút chỉ có biểu tượng thành ba nút có chữ, xuống hàng riêng (soát UX a11). */}
              <div className="ml-auto flex shrink-0 items-center gap-1 max-sm:w-full max-sm:justify-end max-sm:gap-2">
              {/* Studio của máy tính ấy ngay trong app này, bằng ghép sẵn có - không ghép lần hai (webui/peer_studio.py). */}
              {computer.kind === "computer" && (
                <Button
                  size="sm"
                  variant="ghost"
                  icon={Clapperboard}
                  onClick={() => window.location.assign(peerPage(window.location.search, computer.id))}
                  aria-label={`Mở Studio của ${computer.name}`}
                >
                  Mở Studio
                </Button>
              )}
              {computer.kind === "phone" && (
                <Button size="sm" variant="ghost" icon={Stethoscope} onClick={() => setDiagnosing(computer)} aria-label={`Chẩn đoán ${computer.name}`}>
                  Chẩn đoán
                </Button>
              )}
              {!isBluetoothHost(computer.host) && (
                <BluetoothFallback
                  computer={computer}
                  devices={devices}
                  busy={setBluetooth.isPending}
                  onChoose={(address) => setBluetooth.mutate({ id: computer.id, address })}
                />
              )}
              <IconButton label="Hỏi lại thư viện" icon={RefreshCw} size="sm" disabled={refresh.isPending} onClick={() => refresh.mutate()} className="max-sm:hidden" />
              <Button size="sm" variant="ghost" icon={RefreshCw} disabled={refresh.isPending} onClick={() => refresh.mutate()} className="sm:hidden" aria-label="Hỏi lại thư viện">
                Hỏi lại
              </Button>
              <IconButton label={`Thôi ghép ${computer.name}`} icon={Unplug} size="sm" onClick={() => void unpair.start(computer)} className="max-sm:hidden" />
              <Button size="sm" variant="ghost" icon={Unplug} onClick={() => void unpair.start(computer)} className="text-danger sm:hidden max-sm:order-first max-sm:mr-auto" aria-label={`Thôi ghép ${computer.name}`}>
                Thôi ghép
              </Button>
              </div>
              </Fold>
            </MotionRegion>
          )}
        </AnimatedRows>
        </div>
      </MotionPresence>
      <Fold storageKey="other-computers.pair" title="Ghép máy" summary="Nghe sách của máy tính khác" bodyClassName="space-y-3 pb-3">
      <div className="space-y-2">
        <Button variant="ghost" icon={Radar} loading={discover.isPending} onClick={() => discover.mutate()}>
          Tìm máy trong mạng
        </Button>
        {discover.data &&
          (discover.data.found.length ? (
            <ul className="divide-y divide-line">
              {discover.data.found.map((found) => (
                <li key={`${found.host}:${found.port}`} className="flex items-center gap-3 py-2">
                  {found.kind === "phone" ? (
                    <Smartphone className="size-5 shrink-0 text-fg-2" aria-label="điện thoại" />
                  ) : (
                    <Laptop className="size-5 shrink-0 text-fg-2" aria-label="máy tính" />
                  )}
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-medium">{found.name}</div>
                    <div className="truncate text-xs text-fg-2">
                      {found.host}:{found.port}
                    </div>
                  </div>
                  {found.paired ? (
                    <span className="text-xs text-fg-2">Đã ghép</span>
                  ) : (
                    <Button size="sm" variant="ghost" onClick={() => choose(found)}>
                      Chọn
                    </Button>
                  )}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-fg-2">Không thấy máy nào trong mạng này.</p>
          ))}
      </div>
      <form
        className="flex flex-wrap items-end gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          pair.mutate();
        }}
      >
        <label className="min-w-0 flex-1 text-xs text-fg-2 max-sm:basis-full" htmlFor="other-computer-address">
          Địa chỉ máy kia
          <input
            id="other-computer-address"
            value={address}
            onChange={(event) => setAddress(event.target.value)}
            placeholder="192.168.1.20 hoặc địa chỉ Bluetooth"
            inputMode="url"
            autoComplete="off"
            spellCheck={false}
            className="mt-1 block h-9 w-full rounded-control border border-line bg-panel px-2.5 text-sm text-fg outline-none focus-visible:border-focus"
          />
        </label>
        <label className="w-32 text-xs text-fg-2" htmlFor="other-computer-code">
          Mã 6 số
          <input
            id="other-computer-code"
            ref={codeInput}
            value={code}
            onChange={(event) => setCode(event.target.value.replace(/\D/g, "").slice(0, 6))}
            placeholder="123456"
            inputMode="numeric"
            autoComplete="off"
            className="tabular mt-1 block h-9 w-full rounded-control border border-line bg-panel px-2.5 text-sm text-fg outline-none focus-visible:border-focus"
          />
        </label>
        <Button type="submit" size="md" variant="ghost" loading={pair.isPending} disabled={!address.trim() || code.replace(/\D/g, "").length !== 6}>
          Kết nối
        </Button>
      </form>
      {/* Toast biến mất sau vài giây; lý do không ghép được ở lại dưới ô địa chỉ cho tới lần thử kế (soát UX a17). */}
      {pair.isError && (
        <p role="alert" className="text-[0.8125rem] text-danger text-pretty">
          Chưa ghép được: {pair.error.message}
        </p>
      )}
      {unpaired.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-xs text-fg-2">Khác Wi-Fi? Chọn máy đã ghép Bluetooth:</p>
          <ul className="flex flex-wrap gap-2">
            {unpaired.map((device) => (
              <li key={device.address}>
                <Button size="sm" variant="ghost" icon={Bluetooth} onClick={() => chooseDevice(device)}>
                  {device.name} · {deviceKindLabel(device.kind)}
                </Button>
              </li>
            ))}
          </ul>
        </div>
      )}
      <p className="text-xs text-fg-2">Máy kia: Cài đặt → Thiết bị → bật “{SYNC_SWITCH_LABEL}” để lấy mã; ghép một chiều để nghe thư viện của máy ấy.</p>
      </Fold>
      {unpair.dialog}
      {lastDiagnosing.current && <PhoneDiagnostics computer={lastDiagnosing.current} open={diagnosing !== null} onOpenChange={(open) => !open && setDiagnosing(null)} />}
    </MotionRegion>
  );
}

/** Máy ghép qua Wi-Fi: menu chọn thiết bị Bluetooth đã ghép làm đường dự phòng khi Wi-Fi hỏng (Wi-Fi vẫn đi trước). */
export function BluetoothFallback({
  computer,
  devices,
  busy,
  onChoose,
}: {
  computer: Computer;
  devices: PairedDevice[];
  busy: boolean;
  onChoose: (address: string) => void;
}) {
  const current = bluetoothAddress(computer);
  return (
    <DropdownMenu.Root>
      <Tooltip label="Dự phòng qua Bluetooth…">
        <DropdownMenu.Trigger
          aria-label={`Dự phòng qua Bluetooth cho ${computer.name}`}
          disabled={busy}
          className={cn(
            "inline-flex size-8 shrink-0 items-center justify-center rounded-control transition-colors hover:bg-hover hover:text-fg data-[state=open]:bg-hover data-[state=open]:text-fg max-sm:h-9 max-sm:w-auto max-sm:px-2.5",
            current ? "text-accent-text" : "text-fg-2",
          )}
        >
          <Bluetooth className="glyph" strokeWidth={2} />
          <span className="ml-1.5 text-sm sm:hidden">Bluetooth</span>
        </DropdownMenu.Trigger>
      </Tooltip>
      <DropdownMenu.Portal>
        <DropdownMenu.Content align="end" sideOffset={6} collisionPadding={12} className="z-50 max-h-[var(--radix-dropdown-menu-content-available-height)] overflow-y-auto overscroll-contain min-w-56 max-w-80 rounded-cover border border-line bg-panel p-1.5 shadow-float"><MotionRegion>
          <DropdownMenu.Label className="px-2 pb-1 pt-0.5 text-xs font-medium text-fg-3">Đường Bluetooth</DropdownMenu.Label>
          {!devices.length && (
            <p className="px-2 py-1.5 text-xs text-fg-3">
              Ghép thiết bị trong Cài đặt Windows trước.
            </p>
          )}
          {devices.map((device) => (
            <DropdownMenu.Item key={device.address} onSelect={() => onChoose(device.address)} className={MENU_ITEM}>
              <SelectionMark selected={device.address === current} />
              <span className="min-w-0 flex-1 text-pretty [overflow-wrap:anywhere]">
                {device.name} <span className="text-fg-3">· {deviceKindLabel(device.kind)}</span>
                {device.address === current && <span className="sr-only">, đang chọn</span>}
              </span>
            </DropdownMenu.Item>
          ))}
          <DropdownMenu.Item disabled={!current} onSelect={() => onChoose("")} className={cn(MENU_ITEM, "text-fg-2")}>
            Không dùng
          </DropdownMenu.Item>
        </MotionRegion></DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}
