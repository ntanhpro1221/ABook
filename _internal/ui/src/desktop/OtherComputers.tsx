import { S } from "../shared/strings.generated";
import { MotionRegion } from "@/shared/MotionRegion";
import { AnimatedRows, MotionPresence } from "@/shared/MotionPresence";
import { Fold } from "@/shared/Collapse";
import * as DropdownMenu from "@/shared/DropdownMenu";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bluetooth, Clapperboard, Laptop, Moon, Radar, RefreshCw, Smartphone, Stethoscope, Unplug } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { toast } from "@/shared/toast";
import { api, ApiError } from "@/studio/api";
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

const MENU_ITEM = "flex h-auto cursor-default items-start gap-2 rounded-control px-2 py-2 text-sm outline-none data-[disabled]:opacity-60 data-[highlighted]:bg-hover";

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
  const [confirmation, setConfirmation] = useState<{ fingerprint: string; short: string; address: string; code: string } | null>(null);
  const confirm = confirmation?.address === address && confirmation.code === code ? confirmation : null;
  const validCode = /^(?:[0-9]{6})(?:[0-9a-f]{64})?$/i.test(code.replace(/[\s-]/g, ""));
  // Thiết bị đã ghép ở Windows và dịch vụ ABook qua SDP; lỗi hay rỗng thì thôi, không chặn gì.
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
    mutationFn: (fingerprint: string = "") => api<ComputersView>("/api/computers", { method: "POST", body: { address, code, fingerprint } }),
    onSuccess: (view) => {
      // Máy vừa ghép = máy có trong danh sách mới mà danh sách cũ chưa có: nói tên thật, không để mẫu “<tên máy>” (soát UX a11).
      const known = new Set(data?.computers.map((computer) => computer.id));
      const name = view.computers.find((computer) => !known.has(computer.id))?.name;
      done(view);
      setAddress("");
      setCode("");
      setConfirmation(null);
      toast.success(name ? S.s_da_ghep_0_a04998dd(name) : S.s_da_ghep_2bd0972f);
    },
    onError: (error: Error) => {
      const detail = error instanceof ApiError ? error.detail.confirm as { fingerprint: string; short: string } | undefined : undefined;
      if (detail) setConfirmation({ ...detail, address, code });
      else { setConfirmation(null); toast.error(S.s_chua_ghep_duoc_e27b68c8, { description: error.message }); }
    },
  });
  const refresh = useMutation({
    mutationFn: () => api<ComputersView>("/api/computers/refresh", { method: "POST" }),
    onSuccess: done,
  });
  const stopWaiting = useMutation({
    mutationFn: (id: string) => api<ComputersView>(`/api/computers/${id}/stop-waiting`, { method: "POST" }),
    onSuccess: done,
  });
  // Bỏ ghép xoá thư mục đệm của máy ấy (phần đã tải, phần sửa chưa gửi): có gì để mất thì hỏi trước, nói rõ mất gì và giữ gì (shared/unpair.ts).
  const unpair = useUnpair<Computer>({
    self: S.s_may_tinh_8eafc226,
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
      toast.success(address ? S.s_da_chon_bluetooth_du_phong_4a0a6048 : S.s_khong_dung_bluetooth_du_phong_nua_0283e9c4);
    },
    onError: (error: Error) => toast.error(S.s_chua_chon_duoc_078e7435, { description: error.message }),
  });
  const discover = useMutation({
    mutationFn: () => api<{ found: FoundComputer[] }>("/api/computers/discover"),
    onError: (error: Error) => toast.error(S.s_chua_tim_duoc_9359cd73, { description: error.message }),
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
  if (error && !data) return <MotionRegion fadeThrough><InlineError message={S.s_ban_hay_kiem_tra_ket_noi_roi_tai_lai_thiet_cedab5c7} onRetry={() => void refetch()} /></MotionRegion>;
  if (isLoading || !data) return <MotionRegion fadeThrough><ContentSkeleton count={2} label={S.s_dang_tai_thiet_bi_09ddbf1d} /></MotionRegion>;
  // Đã ghép rồi thì không mời ghép lại.
  const pairedAddresses = new Set(data.computers.filter((computer) => isBluetoothHost(computer.host)).map((computer) => bluetoothAddress(computer)));
  const unpaired = devices.filter((device) => device.services?.includes("release") && !pairedAddresses.has(device.address));
  const unpairedDev = devices.filter((device) => device.services?.includes("dev") && !pairedAddresses.has(`${device.address}@dev`.toUpperCase()));
  return (
    <MotionRegion as="div" className="motion-reveal space-y-4">
      <MotionPresence open={Boolean(data.broken)}>
        <p className="text-sm text-warning" role="status">
          {data.broken}
        </p>
      </MotionPresence>
      {/* Ghép / bỏ ghép: hàng mở / khép tại chỗ như PhoneSync; đổi trong hàng (đang chờ, lỗi) thì hàng tự mờ qua. data-motion-live: cả
          khối không mờ lại theo từng hàng. */}
      <MotionPresence open={data.computers.length > 0}>
        <div data-motion-live="">
        <AnimatedRows className="divide-y divide-line" items={data.computers} keyOf={(computer) => computer.id}>
          {(computer) => (
            <MotionRegion>
              <Fold storageKey={`other-computers.${computer.id}`} title={computer.name} heading="h3" summary={computer.waking ? S.s_dang_cho_4257d45b : computer.error ? S.s_can_kiem_tra_d549619d : S.s_da_ghep_2bd0972f} bodyClassName="flex flex-wrap items-center gap-3 pb-3">
              <Laptop className="size-5 shrink-0 text-fg-2" />
              <div className="min-w-0 flex-1">
                {computer.waking ? (
                  <div className="text-xs text-fg-2" role="status">
                    <Moon className="mr-2 -mt-1 inline size-3.5 align-middle" aria-hidden />
                    {wakingLine(computer)}
                    <button
                      type="button"
                      className="ml-2 rounded-control text-accent-text underline-offset-2 hover:underline disabled:opacity-60"
                      disabled={stopWaiting.isPending}
                      onClick={() => stopWaiting.mutate(computer.id)}
                    >{S.s_thoi_cho_6bf8a752}</button>
                  </div>
                ) : (
                  // Lời báo lỗi dài (chứng chỉ máy kia đổi...) xuống dòng cho đọc hết, không cắt giữa chừng.
                  <div data-motion-live className={cn("text-xs", computer.error ? "text-danger [overflow-wrap:anywhere]" : "truncate text-fg-2")}>
                    {computer.error
                      ? computer.error
                      : `${routeLine(computer, devices)}${computer.lastSeen ? S.s_thay_0_45bf670a(formatRelative(computer.lastSeen)) : ""}`}
                  </div>
                )}
                {computer.fingerprint && (
                  // 8 ký tự đầu đủ để đối chiếu với máy kia; đủ 64 ký tự ở chú giải khi rê chuột vào.
                  <div className="mt-1 break-words text-caption text-fg-3" title={formatFingerprint(computer.fingerprint)}>{S.s_van_tay_8abdcdf0}{formatFingerprint(computer.fingerprint).slice(0, 9)}…
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
                  aria-label={S.s_mo_studio_cua_0_07ada8e5(computer.name)}
                >{S.s_mo_studio_84ec0a81}</Button>
              )}
              {computer.kind === "phone" && (
                <Button size="sm" variant="ghost" icon={Stethoscope} onClick={() => setDiagnosing(computer)} aria-label={S.s_chan_doan_0_b8c06668(computer.name)}>{S.s_chan_doan_906791d5}</Button>
              )}
              {!isBluetoothHost(computer.host) && (
                <BluetoothFallback
                  computer={computer}
                  devices={devices}
                  busy={setBluetooth.isPending}
                  onChoose={(address) => setBluetooth.mutate({ id: computer.id, address })}
                />
              )}
              <IconButton label={S.s_hoi_lai_thu_vien_bfe2a0e8} icon={RefreshCw} size="sm" disabled={refresh.isPending} onClick={() => refresh.mutate()} className="max-sm:hidden" />
              <Button size="sm" variant="ghost" icon={RefreshCw} disabled={refresh.isPending} onClick={() => refresh.mutate()} className="sm:hidden" aria-label={S.s_hoi_lai_thu_vien_bfe2a0e8}>{S.s_hoi_lai_1dc3bd7a}</Button>
              <IconButton label={S.s_bo_ghep_0_56c3fd6f(computer.name)} icon={Unplug} size="sm" onClick={() => void unpair.start(computer)} className="max-sm:hidden" />
              <Button size="sm" variant="ghost" icon={Unplug} onClick={() => void unpair.start(computer)} className="text-danger sm:hidden max-sm:order-first max-sm:mr-auto" aria-label={S.s_bo_ghep_0_56c3fd6f(computer.name)}>{S.s_bo_ghep_64f921f9}</Button>
              </div>
              </Fold>
            </MotionRegion>
          )}
        </AnimatedRows>
        </div>
      </MotionPresence>
      <Fold storageKey="other-computers.pair" title={S.s_ghep_may_601e4c98} summary={S.s_nghe_sach_cua_may_tinh_khac_31628082} bodyClassName="space-y-3 pb-3">
      <div className="space-y-2">
        <Button variant="ghost" icon={Radar} loading={discover.isPending} onClick={() => discover.mutate()}>{S.s_tu_tim_3f09ad05}</Button>
        {discover.data &&
          (discover.data.found.length ? (
            <ul className="divide-y divide-line">
              {discover.data.found.map((found) => (
                <li key={`${found.host}:${found.port}`} className="flex items-center gap-3 py-2">
                  {found.kind === "phone" ? (
                    <Smartphone className="size-5 shrink-0 text-fg-2" aria-label={S.s_dien_thoai_2f73f175} />
                  ) : (
                    <Laptop className="size-5 shrink-0 text-fg-2" aria-label={S.s_may_tinh_8eafc226} />
                  )}
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-medium">{found.name}</div>
                    <div className="truncate text-xs text-fg-2">
                      {found.host}:{found.port}
                    </div>
                  </div>
                  {found.paired ? (
                    <span className="text-xs text-fg-2">{S.s_da_ghep_2bd0972f}</span>
                  ) : (
                    <Button size="sm" variant="ghost" onClick={() => choose(found)}>{S.s_chon_1171ca97}</Button>
                  )}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-fg-2">{S.s_chua_thay_thiet_bi_192c6e9e}</p>
          ))}
      </div>
      <form
        className="flex flex-wrap items-end gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          setConfirmation(null);
          pair.mutate("");
        }}
      >
        <label className="min-w-0 flex-1 text-xs text-fg-2 max-sm:basis-full" htmlFor="other-computer-address">{S.s_dia_chi_may_kia_e746667e}<input
            id="other-computer-address"
            value={address}
            onChange={(event) => { setAddress(event.target.value); setConfirmation(null); }}
            placeholder={S.s_192_168_1_20_hoac_dia_chi_bluetooth_326669dc}
            inputMode="url"
            autoComplete="off"
            spellCheck={false}
            className="mt-1 block h-9 w-full rounded-control border border-line bg-panel px-3 text-sm text-fg outline-none focus-visible:border-focus"
          />
        </label>
        <label className="min-w-32 flex-1 text-xs text-fg-2" htmlFor="other-computer-code">{S.s_pair_code_or_string}<input
            id="other-computer-code"
            ref={codeInput}
            value={code}
            onChange={(event) => { setCode(event.target.value.slice(0, 100)); setConfirmation(null); }}
            placeholder="123456"
            inputMode="text"
            autoComplete="off"
            className="mt-1 block h-9 w-full rounded-control border border-line bg-panel px-3 text-sm text-fg outline-none focus-visible:border-focus"
          />
        </label>
        <Button type="submit" size="md" variant="ghost" loading={pair.isPending} disabled={!address.trim() || !validCode}>{S.s_ket_noi_02ca3cba}</Button>
      </form>
      {confirm && <div role="status" className="space-y-2">
        <p>{S.s_pair_fingerprint_label}{confirm.short}</p>
        <p>{S.s_pair_fingerprint_help}</p>
        <Button type="button" disabled={pair.isPending} onClick={() => pair.mutate(confirm.fingerprint)}>{S.s_pair_fingerprint_confirm}</Button>
      </div>}
      {/* Toast biến mất sau vài giây; lý do không ghép được ở lại dưới ô địa chỉ cho tới lần thử kế (soát UX a17). */}
      {pair.isError && !confirm && (
        <p role="alert" className="text-body-small text-danger text-pretty">{S.s_chua_ghep_duoc_160c13b4}{pair.error.message}
        </p>
      )}
      {unpaired.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs text-fg-2">{S.s_khac_wi_fi_chon_may_da_ghep_bluetooth_f451876c}</p>
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
      {unpairedDev.map((device) => (
        <Button key={`${device.address}@dev`} size="sm" variant="ghost" icon={Bluetooth}
          onClick={() => { setAddress(`${device.address}@dev`); codeInput.current?.focus(); }}>
          {device.name}{S.s_ban_thu_7ef7942e}</Button>
      ))}
      <p className="text-xs text-fg-2">{S.s_may_kia_cai_dat_thiet_bi_bat_daa5df50}{SYNC_SWITCH_LABEL}{S.s_de_lay_ma_ghep_mot_chieu_de_nghe_thu_vien_bea7e639}</p>
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
      <Tooltip label={S.s_dung_bluetooth_a7d4c199}>
        <DropdownMenu.Trigger
          aria-label={S.s_dung_bluetooth_cho_0_82d05e59(computer.name)}
          disabled={busy}
          className={cn(
            "inline-flex size-8 shrink-0 items-center justify-center rounded-control transition-colors hover:bg-hover hover:text-fg data-[state=open]:bg-hover data-[state=open]:text-fg max-sm:h-9 max-sm:w-auto max-sm:px-3",
            current ? "text-accent-text" : "text-fg-2",
          )}
        >
          <Bluetooth className="glyph" strokeWidth={2} />
          <span className="ml-2 text-sm sm:hidden">{S.s_bluetooth_8bb29098}</span>
        </DropdownMenu.Trigger>
      </Tooltip>
      <DropdownMenu.Portal>
        <DropdownMenu.Content align="end" sideOffset={6} collisionPadding={12} className="z-50 max-h-[var(--radix-dropdown-menu-content-available-height)] overflow-y-auto overscroll-contain min-w-56 max-w-80 rounded-cover border border-line bg-panel p-2 shadow-float"><MotionRegion>
          <DropdownMenu.Label className="px-2 pb-1 pt-1 text-xs font-medium text-fg-3">{S.s_qua_bluetooth_983cecc1}</DropdownMenu.Label>
          {!devices.length && (
            <p className="px-2 py-2 text-xs text-fg-3">{S.s_ghep_thiet_bi_trong_cai_dat_windows_truoc_53fc93c2}</p>
          )}
          {devices.map((device) => (
            <DropdownMenu.Item key={device.address} onSelect={() => onChoose(device.address)} className={MENU_ITEM}>
              <SelectionMark selected={device.address === current} />
              <span className="min-w-0 flex-1 text-pretty [overflow-wrap:anywhere]">
                {device.name} <span className="text-fg-3">· {deviceKindLabel(device.kind)}</span>
                {device.address === current && <span className="sr-only">{S.s_dang_chon_19938ba6}</span>}
              </span>
            </DropdownMenu.Item>
          ))}
          <DropdownMenu.Item disabled={!current} onSelect={() => onChoose("")} className={cn(MENU_ITEM, "text-fg-2")}>{S.s_khong_dung_30db3c31}</DropdownMenu.Item>
        </MotionRegion></DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}
