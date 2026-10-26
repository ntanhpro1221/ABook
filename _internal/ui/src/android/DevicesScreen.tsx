import { MotionRegion } from "@/shared/MotionRegion";
import { SectionHeading } from "@/shared/SectionHeading";
import { MotionPresence } from "@/shared/MotionPresence";
import * as Switch from "@radix-ui/react-switch";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type LucideIcon, Bluetooth, CheckCircle2, Copy, Download, HardDrive, Keyboard, Laptop, Link2, Loader2, Pencil, RefreshCw, Search, Smartphone, Trash2, Unplug, Wifi, X } from "lucide-react";
import { useId, useEffect, useRef, useState } from "react";
import { toast } from "@/shared/toast";
import { BookCover } from "@/shared/BookCover";
import { useBackLayer } from "@/shared/backStack";
import { cn } from "@/shared/cn";
import { formatFingerprint, formatLength, formatSize } from "@/shared/format";
import { SYNC_SWITCH_LABEL } from "@/shared/syncSwitch";
import { DialogActions, Button, Dialog, IconButton, Progress, SelectionMark } from "@/shared/ui";
import { useUnpair } from "@/shared/useUnpair";
import { BackgroundNote } from "./BackgroundNote";
import { BLUETOOTH_DENIED, BLUETOOTH_REASON, bluetoothStep } from "./bluetoothPermission";
import { connectionRoute } from "@/shared/connectionRoute";
import { useDownloadProgress } from "./downloads";
import { hasNewAudio, hasNewMeta, hasNewWords } from "./bookUpdates";
import { openRelease } from "./UpdateNotice";
import { isDownloading, storedEntries, useStorage, type RemovableFromPhone, type StoredFolder } from "./storage";
import { ErrorDetails } from "@/shared/ErrorDetails";
import { isUnpaired, nativeError, toastNativeError } from "./nativeError";
import { useListenLibrary } from "@/listen/source";
import { Collapse, Fold } from "@/shared/Collapse";
import { useListPresence, withViewTransition } from "@/shared/motion";
import { MoreInfo } from "@/shared/SettingsNav";
import { EbookLibrary, type DownloadEvent, type RemoteBook, type ShareStatus } from "./plugins";

// Cài đặt › Thiết bị: ghép máy, chia sẻ, chẩn đoán và dung lượng. Sách của máy đã ghép nằm trong Thư viện.

/** Trang tải ABook cho máy tính (chữ chép được; lõi native chỉ mở địa chỉ bắt đầu bằng ".../ABook/" - LibraryPlugin.openRelease). */
export const DESKTOP_RELEASES = "https://github.com/ntanhpro1221/ABook/releases";

/** Mở đầu cho người chỉ có điện thoại (soát a66): máy tính thêm được gì và lấy ABook máy tính ở đâu - rồi mới tới các bước ghép nối. */
export function ComputerIntro() {
  const copy = () =>
    void navigator.clipboard
      .writeText(DESKTOP_RELEASES)
      .then(() => toast.success("Đã chép địa chỉ"), () => toast.error("Chưa chép được - giữ ngón tay lên địa chỉ để chọn rồi chép"));
  return (
    <div>
      <div className="flex min-h-[3.5rem] items-center gap-3 py-3">
        <Laptop className="size-5 shrink-0 text-fg-2" />
        <div className="min-w-0 flex-1">
          <SectionHeading>Studio máy tính</SectionHeading>
          <p className="text-sm text-fg-2">Tạo sách nói rồi nghe ở đây.</p>
        </div>
      </div>
      <div className="flex min-h-[3.5rem] items-center gap-3 border-t border-line py-2">
        <Download className="size-5 shrink-0 text-fg-2" />
        <a href={DESKTOP_RELEASES} className="flex min-h-[48px] min-w-0 flex-1 items-center text-left text-base font-medium text-accent-text" onClick={(event) => { event.preventDefault(); void openRelease(DESKTOP_RELEASES); }}>Tải ABook Windows</a>
        {/* Nút icon cuối hàng: bù nửa phần ô rộng hơn icon để mực chạm mép cột như mọi hàng (ô chạm 48 px trên cảm ứng). */}
        <IconButton label="Chép địa chỉ" icon={Copy} className="ink-end-icon -mr-2.5 pointer-coarse:-mr-4" onClick={copy} />
      </div>
    </div>
  );
}

export function PairPanel() {
  const client = useQueryClient();
  const connection = useQuery({ queryKey: ["connection"], queryFn: () => EbookLibrary.connection() });
  const [computers, setComputers] = useState<{ host: string; port: number; name: string }[] | null>(null);
  const [target, setTarget] = useState<{ host: string; port: number; name: string } | null>(null);
  const [manual, setManualNow] = useState(false);
  // Tự tìm <-> nhập địa chỉ: mờ chéo cả khung (View Transition), không thay chỗ tức thì.
  const setManual = (value: boolean) => withViewTransition(() => setManualNow(value));
  // Nhập tay: Back quay về tự tìm máy, chưa rời trang.
  useBackLayer(manual, () => setManual(false));
  const [address, setAddress] = useState("");
  const [code, setCode] = useState("");
  const [paired, setPaired] = useState<{ address: string; name: string; abook: boolean }[] | null>(null);
  // Trước khi Android hỏi quyền "Thiết bị ở gần": "explain" = một câu vì sao cần + nút Cho phép; "settings" = đã từ chối hẳn, chỉ tới Cài đặt.
  const [btAsk, setBtAsk] = useState<"explain" | "settings" | null>(null);
  // Lời giải thích hiện ở chỗ nút vừa bấm, thường sát mép dưới màn: cuộn cho thấy cả câu lẫn nút "Cho phép".
  const btBox = useRef<HTMLDivElement | null>(null);
  const btButton = useRef<HTMLButtonElement>(null);
  useBackLayer(btAsk !== null, () => setBtAsk(null), btBox, btButton);
  useEffect(() => {
    if (btAsk) btBox.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [btAsk]);
  const discover = useMutation({
    mutationFn: () => EbookLibrary.discover({ timeoutMs: 2500 }),
    onSuccess: ({ computers: found }) => {
      setComputers(found);
      if (found.length === 1) setTarget(found[0]);
    },
  });
  // Không chung Wi-Fi: máy tính đã ghép Bluetooth với điện thoại (Cài đặt Android) - cùng mã 6 số, đi qua Bluetooth.
  const bluetooth = useMutation({
    mutationFn: () => EbookLibrary.bluetoothDevices(),
    onSuccess: ({ devices }) => {
      const computersOnly = devices.filter((device) => device.kind === "computer" || device.abook);
      setPaired(computersOnly);
      if (computersOnly.length === 1) setTarget({ host: `bt:${computersOnly[0].address}`, port: 0, name: computersOnly[0].name });
    },
    onError: async (error: Error) => {
      // Vừa từ chối lần thứ hai (Android không hỏi nữa): chỉ đường tới Cài đặt thay vì một lời báo lặp lại mỗi lần bấm.
      const { state } = await EbookLibrary.bluetoothPermission().catch(() => ({ state: "prompt" as const }));
      if (bluetoothStep(state) === "settings") setBtAsk("settings");
      else toast.error("Chưa dùng được Bluetooth", { description: error.message });
    },
  });
  useEffect(() => {
    // Quay lại từ Cài đặt mà quyền đã bật: tìm máy luôn, không bắt bấm lại.
    if (btAsk !== "settings") return;
    const back = () => {
      if (document.visibilityState !== "visible") return;
      void EbookLibrary.bluetoothPermission().then(({ state }) => {
        if (bluetoothStep(state) !== "go") return;
        setBtAsk(null);
        bluetooth.mutate();
      }, () => undefined);
    };
    document.addEventListener("visibilitychange", back);
    return () => document.removeEventListener("visibilitychange", back);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [btAsk]);
  const startBluetooth = async () => {
    const { state } = await EbookLibrary.bluetoothPermission().catch(() => ({ state: "granted" as const }));
    const step = bluetoothStep(state);
    if (step === "go") bluetooth.mutate();
    else setBtAsk(step);
  };
  const pair = useMutation({
    mutationFn: () => {
      if (target?.host.startsWith("bt:")) {
        return EbookLibrary.pairBluetooth({ address: target.host.slice(3), code: code.replace(/\D/g, "") });
      }
      const host = target?.host ?? address.split(":")[0].trim();
      const port = target?.port ?? Number(address.split(":")[1] ?? 47630);
      return EbookLibrary.pair({ host, port, code: code.replace(/\D/g, "") });
    },
    onSuccess: ({ name }) => {
      toast.success(`Đã kết nối với ${name}`);
      void client.invalidateQueries({ queryKey: ["connection"] });
    },
    onError: (error: Error) => toastNativeError("Chưa kết nối được", error),
  });
  useEffect(() => {
    discover.mutate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  // Địa chỉ máy tính đã ghép lần trước (soát a68 lỗi 20): ghép lại sau khi máy tính thôi ghép không phải gõ lại - mở sẵn ô địa chỉ có nó.
  const lastAddress = connection.data?.lastAddress ?? "";
  const filled = useRef(false);
  useEffect(() => {
    if (filled.current || !lastAddress) return;
    filled.current = true;
    setAddress(lastAddress);
    setManual(true);
  }, [lastAddress]);
  const ready = (target || address.includes(".")) && code.replace(/\D/g, "").length === 6;
  return (
    <MotionRegion as="div" className="space-y-3">
      <div className="pb-1">
        <div className="flex items-center gap-3">
          <div className="flex shrink-0 items-center text-fg-2">
            <Wifi className="size-5" />
          </div>
          <div>
            <SectionHeading>Nối máy tính</SectionHeading>
            <p className="text-sm text-fg-2">Cùng Wi-Fi, mở Thiết bị trên máy tính.</p>
          </div>
        </div>
        <MoreInfo label="Cách lấy mã">Trong Cài đặt › Thiết bị của máy tính, bật “{SYNC_SWITCH_LABEL}” rồi chọn ghép thiết bị để lấy mã 6 số.</MoreInfo>
      </div>

      {!manual && (
        <div>
          <div className="mb-2 flex items-center justify-between">
            <span className="text-sm font-semibold">Máy tính tìm thấy</span>
            <button type="button" onClick={() => discover.mutate()} className="touch-hit flex items-center gap-1.5 text-sm font-medium text-accent-text">
              <MotionRegion as="span" className="inline-grid shrink-0 place-items-center">{discover.isPending ? <Loader2 className="size-4 animate-spin" /> : <Search className="size-4" />}</MotionRegion> Tìm lại
            </button>
          </div>
          {computers?.length ? (
            <div className="space-y-2">
              {computers.map((computer) => (
                <button
                  key={computer.host}
                  type="button"
                  onClick={() => setTarget(computer)}
                  className={cn(
                    "flex min-h-[3.5rem] w-full items-center gap-3 border-b border-line py-3 text-left hover:bg-hover",
                  )}
                >
                  <SelectionMark selected={target?.host === computer.host} />
                  <span className="flex-1">
                    <span className="block font-medium">{computer.name}</span>
                    <span className="block text-xs text-fg-2">{computer.host}</span>
                  </span>
                </button>
              ))}
            </div>
          ) : (
            <p className="py-3 text-sm text-fg-2">
              {discover.isPending ? "Đang tìm trong mạng Wi-Fi…" : "Chưa thấy máy tính nào. Kiểm tra máy tính đã bật kết nối, hoặc nhập địa chỉ."}
            </p>
          )}
        </div>
      )}

      {!manual && (
        <div>
          {paired === null && btAsk ? (
            <div ref={btBox} className="space-y-3 py-3 text-sm text-fg-2">
              <p className="text-pretty">{btAsk === "explain" ? BLUETOOTH_REASON : BLUETOOTH_DENIED}</p>
              {btAsk === "explain" && <MoreInfo label="Quyền Bluetooth">Chỉ tìm máy đã ghép Bluetooth để nhận sách; ABook không dò hay kết nối thiết bị khác.</MoreInfo>}
              <div className="flex flex-wrap gap-2">
                {btAsk === "explain" ? (
                  <Button size="sm" variant="primary" loading={bluetooth.isPending} onClick={() => { setBtAsk(null); bluetooth.mutate(); }}>
                    Cho phép
                  </Button>
                ) : (
                  <Button size="sm" variant="primary" onClick={() => void EbookLibrary.openAppSettings().catch((error: Error) => toast.error(error.message))}>
                    Mở Cài đặt
                  </Button>
                )}
                <Button size="sm" variant="ghost" onClick={() => setBtAsk(null)}>
                  Để sau
                </Button>
              </div>
            </div>
          ) : paired === null ? (
            <button ref={btButton} type="button" onClick={() => void startBluetooth()} className="touch-hit flex items-center gap-1.5 text-sm font-medium text-accent-text">
              <MotionRegion as="span" className="inline-grid shrink-0 place-items-center">{bluetooth.isPending ? <Loader2 className="size-4 animate-spin" /> : <Bluetooth className="ink-start-shift size-4 [--icon-w:16px]" />}</MotionRegion> Dùng Bluetooth
            </button>
          ) : paired.length ? (
            <div className="space-y-2">
              <span className="text-sm font-semibold">Máy tính đã ghép Bluetooth</span>
              {paired.map((device) => (
                <button
                  key={device.address}
                  type="button"
                  onClick={() => setTarget({ host: `bt:${device.address}`, port: 0, name: device.name })}
                  className={cn(
                    "flex min-h-[3.5rem] w-full items-center gap-3 border-b border-line py-3 text-left hover:bg-hover",
                  )}
                >
                  <SelectionMark selected={target?.host === `bt:${device.address}`} />
                  <span className="flex-1">
                    <span className="block font-medium">{device.name}</span>
                    <span className="block text-xs text-fg-2">Qua Bluetooth{device.abook ? " · có ABook" : ""}</span>
                  </span>
                </button>
              ))}
            </div>
          ) : (
            <p className="py-3 text-sm text-fg-2">
              Chưa có máy tính ghép Bluetooth. Ghép ở Cài đặt Android › Bluetooth rồi thử lại.
            </p>
          )}
        </div>
      )}

      <button type="button" onClick={() => withViewTransition(() => { setManualNow((value) => !value); setTarget(null); })} className="touch-hit flex items-center gap-1.5 text-sm font-medium text-accent-text">
        {/* Cùng một kiểu liên kết với "Dùng Bluetooth" (soát 24-10 T15: một hổ phách có biểu tượng, một xám gạch chân). */}
        {manual ? <Search className="size-4" /> : <Keyboard className="size-4" />} {manual ? "Tự tìm máy tính" : "Nhập địa chỉ"}
      </button>
      {manual && (
        <input
          value={address}
          onChange={(event) => setAddress(event.target.value)}
          inputMode="url"
          placeholder="Ví dụ 192.168.1.20:47630"
          className="device-input w-full px-3 text-base"
        />
      )}

      <label className="block">
        <span className="text-sm font-semibold">Mã ghép nối</span>
        <input
          value={code}
          onChange={(event) => setCode(event.target.value.replace(/\D/g, "").slice(0, 6))}
          inputMode="numeric"
          autoComplete="one-time-code"
          placeholder="••••••"
          className="device-input tabular mt-1.5 w-full text-center text-xl font-medium tracking-[0.5em]"
        />
      </label>
      <Button variant="primary" size="lg" className="w-full" disabled={!ready} loading={pair.isPending} onClick={() => pair.mutate()}>
        Kết nối
      </Button>
    </MotionRegion>
  );
}

export function RemoteRow({ book, progress, onDownload, compact = false }: { book: RemoteBook; progress?: DownloadEvent; onDownload: () => void; compact?: boolean }) {
  const newChapters = book.downloaded ? book.chaptersAvailable - book.localChapters : 0;
  const newCover = book.downloaded && (book.cover?.version ?? 0) !== (book.localCoverVersion ?? 0);
  const newWords = hasNewWords(book);
  const newAudio = hasNewAudio(book);
  const newMeta = hasNewMeta(book);
  const downloading = progress && !progress.finished && !progress.error && !progress.cancelled;
  const fraction = progress?.total ? (progress.done ?? 0) / progress.total : (progress?.files ?? 0) / Math.max(1, progress?.filesTotal ?? 1);
  const percent = Math.round(Math.max(0, Math.min(1, fraction)) * 100);
  // Huỷ dừng thật ở khối kế (LibraryPlugin.cancelDownload); phần đã về giữ lại, bấm Tải lần sau là tải tiếp.
  const cancel = () => void EbookLibrary.cancelDownload({ bookId: book.id }).catch((error) => toastNativeError("Chưa huỷ được", error));
  // Gọn (dưới thẻ sách ở Thư viện): hàng cao bằng nút để "Đã tải" và "Tải" của hai thẻ cạnh nhau cùng một dòng; nút ghost bù đệm trái
  // (edge-start-action) để mực thẳng mép tên sách như "Đã tải" (máy dò leading-control-inset).
  return (
    <MotionRegion as="div" data-remote-status={compact ? "compact" : undefined} className={compact ? "flex min-h-[var(--button-h)] flex-wrap items-center justify-between gap-1" : "flex items-center gap-3 py-3"}>
      {!compact && <BookCover title={book.title} size="sm" className="size-14" />}
      {!compact && <div className="min-w-0 flex-1">
        <div className="truncate font-semibold">{book.title}</div>
        <div className="text-xs text-fg-2">
          {book.chaptersAvailable}/{book.chaptersTotal} chương · {formatLength(book.duration)}
          {!book.downloaded && book.bytes ? ` · ${formatSize(book.bytes)}` : ""}
          {book.producing && " · đang làm"}
        </div>
        {downloading && (
          <Progress
            value={fraction}
            running
            size="xs"
            className="mt-2"
            label={`Đang tải ${book.title}`}
            valueText={progress?.total ? `đã tải ${percent}%, ${formatSize(progress.done ?? 0)} trên ${formatSize(progress.total)}` : `đã tải ${percent}%`}
          />
        )}
      </div>}
      {downloading && compact ? (
        // Dưới bìa: tiến độ đã hiện trên bìa (DownloadCover, cả bìa bộ) - hàng chỉ còn việc huỷ, cùng chỗ và kiểu với nút Tải.
        <Button size="sm" variant="ghost" icon={X} className="edge-start-action" onClick={cancel} aria-label={`Huỷ tải ${book.title}`}>Huỷ</Button>
      ) : downloading ? (
        <div className="flex shrink-0 items-center gap-1">
          <span data-remote-progress className="tabular w-10 text-right text-xs font-semibold text-accent-text" aria-hidden>
            {percent}%
          </span>
          <button
            type="button"
            onClick={cancel}
            aria-label={`Huỷ tải ${book.title}`}
            className="grid size-[44px] place-items-center rounded-full text-fg-2"
          >
            <X className="size-4" />
          </button>
        </div>
      ) : book.downloaded && newChapters <= 0 && !newCover && !newWords && !newAudio && !newMeta ? (
        <span className="flex items-center gap-1 text-xs text-success">
          <CheckCircle2 className="ink-start size-4" /> Đã tải
        </span>
      ) : (
        <Button size="sm" variant={compact ? "ghost" : book.downloaded ? "ghost" : "primary"} icon={Download} className={compact ? "edge-start-action" : undefined} onClick={onDownload}>
          {!book.downloaded ? "Tải" : newChapters > 0 ? `+${newChapters} chương` : newAudio ? "Cập nhật bản thu" : newCover ? "Cập nhật bìa" : newMeta ? "Cập nhật tên" : "Cập nhật chữ"}
        </Button>
      )}
    </MotionRegion>
  );
}

// Báo về điện thoại khi máy tính sản xuất có tin (StudioAlerts.kt): sách xong, dừng vì lỗi, có việc mới cần duyệt.
// Cần công tắc Studio từ xa trên máy tính và quyền điều khiển sản xuất cho điện thoại này - như chính trang Studio.
// Có `icon`: hàng nằm trong danh sách máy của màn Studio - cùng cột icon, cỡ chữ và khoảng đệm với các hàng máy ở trên.
export function StudioAlertsRow({ icon: Icon }: { icon?: LucideIcon } = {}) {
  const client = useQueryClient();
  const state = useQuery({ queryKey: ["studio-alerts"], queryFn: () => EbookLibrary.studioAlerts() });
  const change = useMutation({
    mutationFn: (enabled: boolean) => EbookLibrary.setStudioAlerts({ enabled }),
    onSuccess: (data) => {
      client.setQueryData(["studio-alerts"], data);
      if (data.enabled && !data.permitted) toast.error("Android chưa cho ABook đăng thông báo", { description: "Bật lại trong Cài đặt của máy > Ứng dụng > ABook > Thông báo." });
      else if (data.enabled) toast.success("Sẽ báo khi sách xong hay cần duyệt");
    },
    onError: (error: Error) => toast.error("Chưa đổi được", { description: error.message }),
  });
  const enabled = state.data?.enabled ?? false;
  return (
    <div className={cn("flex items-center", Icon ? "gap-3 py-4" : "mt-6 justify-between gap-4 py-3.5")}>
      {Icon && <Icon className="size-5 shrink-0 text-fg-2" />}
      <div className="min-w-0 flex-1">
        <div className={Icon ? "truncate text-base font-medium" : "text-[0.9375rem] font-medium"}>Báo từ Studio</div>
        <MotionRegion className={Icon ? "mt-1 truncate text-sm text-fg-2" : "mt-0.5 truncate text-xs leading-snug text-fg-2"}>
          {enabled && state.data && !state.data.permitted
            ? "Android đang chặn thông báo của ABook."
            : "Sách xong hoặc có việc cần bạn."}
        </MotionRegion>
      </div>
      <Switch.Root
        checked={enabled}
        disabled={change.isPending || state.isLoading}
        onCheckedChange={(value) => change.mutate(value)}
        aria-label="Báo từ Studio"
        className="ui-switch ui-switch-large"
      >
        <Switch.Thumb className="motion-switch-thumb" />
      </Switch.Root>
    </div>
  );
}

/** Lỗi Capacitor mang mã PIN_CHANGED (Pin.CODE): chứng chỉ máy kia đã đổi - `message` là câu bảo ghép lại. */
/** Vân tay chứng chỉ của máy đã ghép, để so với dòng "Vân tay" bên máy ấy; chưa có thì không hiện gì. */
function Fingerprint({ value }: { value?: string }) {
  const shown = formatFingerprint(value);
  if (!shown) return null;
  return (
    <div className="mt-0.5 break-words text-[0.6875rem] text-fg-3">
      Vân tay <span className="tabular-nums">{shown}</span>
    </div>
  );
}

/** Lời trạng thái Bluetooth của chia sẻ (BluetoothLink.kt) báo thiếu quyền "Thiết bị ở gần". */
export function needsNearbyPermission(status?: string): boolean {
  return Boolean(status && status.includes("Thiết bị ở gần"));
}

function pinChanged(error: unknown): error is Error {
  return error instanceof Error && (error as Error & { code?: string }).code === "PIN_CHANGED";
}

// Thiết bị ghép ngoài máy tính chính (Peers.kt - mạng trạm bước 2): điện thoại khác bật "Chia sẻ thư viện",
// hay một máy tính nữa. Sách của chúng nghe thẳng được trong Thư viện ("Trên <tên>") và tải về như sách máy tính.
function PeersPanel() {
  const client = useQueryClient();
  const libraries = useQuery({ queryKey: ["peer-libraries"], queryFn: () => EbookLibrary.peerLibraries(), retry: 0 });
  const connection = useQuery({ queryKey: ["connection"], queryFn: () => EbookLibrary.connection() });
  const [open, setOpen] = useState(false);
  const [found, setFound] = useState<{ host: string; port: number; name: string; kind?: string }[] | null>(null);
  const [address, setAddress] = useState("");
  const [code, setCode] = useState("");
  const [bonded, setBonded] = useState<{ address: string; name: string; kind: string }[] | null>(null);
  // Khung "Ghép thiết bị" mở ngay trong trang: Back của điện thoại gập nó lại trước khi rời trang.
  useBackLayer(open, () => setOpen(false));
  const discover = useMutation({
    mutationFn: () => EbookLibrary.discover({ timeoutMs: 2500 }),
    onSuccess: ({ computers }) => {
      const paired = new Set((libraries.data?.peers ?? []).map((peer) => peer.host));
      // Máy tính chính đã ghép ở trên; thiết bị đã ghép ở dưới - chỉ hiện máy mới.
      setFound(computers.filter((item) => item.host !== connection.data?.host && !paired.has(item.host)));
    },
  });
  // Không chung Wi-Fi: thiết bị đã ghép Bluetooth với điện thoại này ("bt:<địa chỉ>").
  const bluetooth = useMutation({
    mutationFn: () => EbookLibrary.bluetoothDevices(),
    onSuccess: ({ devices }) => setBonded(devices),
    onError: (error: Error) => toast.error("Chưa dùng được Bluetooth", { description: error.message }),
  });
  const pair = useMutation({
    mutationFn: () => {
      if (address.startsWith("bt:")) {
        return EbookLibrary.peerPairBluetooth({ address: address.slice(3), code: code.replace(/\D/g, "") });
      }
      const [host, port] = address.split(":");
      return EbookLibrary.peerPair({ host: host.trim(), port: Number(port ?? 47630), code: code.replace(/\D/g, "") });
    },
    onSuccess: ({ name }) => {
      toast.success(`Đã ghép ${name}`);
      setOpen(false);
      setCode("");
      setAddress("");
      void client.invalidateQueries({ queryKey: ["peer-libraries"] });
      void client.invalidateQueries({ queryKey: ["streamable"] });
    },
    onError: (error: Error) => toastNativeError("Chưa ghép được", error),
  });
  // Thiết bị đã thôi ghép điện thoại này: mở hộp ghép với sẵn địa chỉ của nó, chỉ còn nhập mã mới.
  const repair = async (peer: { key: string; host: string }) => {
    const known = await EbookLibrary.peers().then(({ peers: list }) => list.find((item) => item.key === peer.key), () => undefined);
    setAddress(known && !known.host.startsWith("bt:") ? `${known.host}:${known.port}` : known?.host ?? peer.host);
    setCode("");
    setOpen(true);
  };
  const peers = libraries.data?.peers ?? [];
  // Thôi ghép xoá các cuốn nghe thẳng của thiết bị, kể cả phần sửa chưa gửi: còn sửa thì hỏi trước (shared/unpair.ts).
  const unpair = useUnpair<(typeof peers)[number]>({
    self: "điện thoại",
    name: (peer) => peer.name,
    // Máy kia có đang trả lời không: hỏi lại thư viện của nó ngay lúc này (kết quả cũ trong bộ nhớ có thể đã quá lâu).
    reachable: (peer) => !libraries.data?.peers.find((item) => item.key === peer.key)?.error,
    unsent: async (peer) => {
      await libraries.refetch();
      return EbookLibrary.peerUnsent({ key: peer.key });
    },
    run: async (peer, choice) => {
      await EbookLibrary.peerForget({ key: peer.key, send: choice === "send", discard: choice === "discard" });
      void client.invalidateQueries({ queryKey: ["peer-libraries"] });
      void client.invalidateQueries({ queryKey: ["streamable"] });
    },
  });
  const ready = (address.includes(".") || address.startsWith("bt:")) && code.replace(/\D/g, "").length === 6;
  return (
    <MotionRegion as="section" className="mt-8" aria-labelledby="peers-title">
      <div className="flex items-center justify-between gap-3">
        {/* Cùng bậc với các tiêu đề mục khác của trang ("Studio trên máy tính", "Nối máy tính", "Máy tính tìm thấy"). */}
        <SectionHeading id="peers-title">
          Thiết bị khác
        </SectionHeading>
        <Button size="sm" variant="ghost" icon={Link2} className="settings-edge-action" onClick={() => { setOpen((value) => !value); if (!open) discover.mutate(); }}>
          Ghép thiết bị
        </Button>
      </div>
      <p className="mt-1 text-xs leading-snug text-fg-2">
        Sách máy kia hiện trong Thư viện.
      </p>
      {/* Khung ghép mở / khép có chuyển động (shared/Collapse) thay vì bật tắt. */}
      <Collapse open={open} className="pt-3">
        <div className="space-y-3 py-4">
          {bonded === null ? (
            <button type="button" onClick={() => bluetooth.mutate()} className="flex items-center gap-1.5 text-sm font-medium text-accent-text">
              <MotionRegion as="span" className="inline-grid shrink-0 place-items-center">{bluetooth.isPending ? <Loader2 className="size-4 animate-spin" /> : <Bluetooth className="size-4" />}</MotionRegion> Ghép Bluetooth
            </button>
          ) : bonded.length ? (
            <div className="space-y-2">
              {bonded.map((device) => (
                <button
                  key={device.address}
                  type="button"
                  onClick={() => setAddress(`bt:${device.address}`)}
                  className={cn(
                    "flex min-h-[3.5rem] w-full items-center gap-3 border-b border-line py-3 text-left hover:bg-hover",
                  )}
                >
                  <SelectionMark selected={address === `bt:${device.address}`} />
                  <span className="flex-1">
                    <span className="block font-medium">{device.name}</span>
                    <span className="block text-xs text-fg-2">Qua Bluetooth · {device.kind === "phone" ? "điện thoại" : "máy tính"}</span>
                  </span>
                </button>
              ))}
            </div>
          ) : (
            <p className="text-sm text-fg-2">Chưa có máy nào ghép Bluetooth với điện thoại này (Cài đặt Android → Bluetooth).</p>
          )}
          {discover.isPending ? (
            <p className="text-sm text-fg-2">Đang tìm trong mạng Wi-Fi…</p>
          ) : found?.length ? (
            <div className="space-y-2">
              {found.map((item) => (
                <button
                  key={item.host}
                  type="button"
                  onClick={() => setAddress(`${item.host}:${item.port}`)}
                  className={cn(
                    "flex min-h-[3.5rem] w-full items-center gap-3 border-b border-line py-3 text-left hover:bg-hover",
                  )}
                >
                  {item.kind === "phone" ? <Smartphone className="size-5 text-fg-2" /> : <Laptop className="size-5 text-fg-2" />}
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-medium">{item.name}</span>
                    <span className="block text-xs text-fg-2">{item.host}</span>
                  </span>
                </button>
              ))}
            </div>
          ) : (
            <p className="text-sm text-fg-2">Không thấy thiết bị nào - nhập địa chỉ đang hiện trên máy kia.</p>
          )}
          <input
            value={address}
            onChange={(event) => setAddress(event.target.value)}
            inputMode="url"
            placeholder="Địa chỉ, ví dụ 192.168.1.25:47630"
            className="device-input w-full px-3 text-base"
          />
          <input
            value={code}
            onChange={(event) => setCode(event.target.value.replace(/\D/g, "").slice(0, 6))}
            inputMode="numeric"
            placeholder="Mã 6 số"
            className="device-input tabular w-full px-3 text-center text-lg tracking-[0.3em]"
          />
          <Button variant="primary" className="w-full" disabled={!ready} loading={pair.isPending} onClick={() => pair.mutate()}>
            Ghép
          </Button>
        </div>
      </Collapse>
      {peers.map((peer) => (
        <div key={peer.key} className="mt-4 py-4">
          <div className="flex items-center gap-3">
            <Smartphone className="size-5 text-fg-2" />
            <div className="min-w-0 flex-1">
              <div className="truncate font-semibold">{peer.name}</div>
              <div className={cn("text-xs", peer.error || peer.unpaired ? "text-danger" : "text-fg-2")}>
                {peer.unpaired
                  ? `${peer.name} đã thôi ghép với điện thoại này`
                  : peer.pinChanged
                    ? peer.error
                    : peer.error
                      ? "Không kết nối được - máy tắt, khác mạng hay chưa bật cho nghe"
                      : `${peer.books.length} cuốn nghe được · ${connectionRoute(peer.connectedVia)}`}
              </div>
              {peer.error && !peer.pinChanged && <ErrorDetails technical={peer.technical} className="text-fg-2" />}
              {peer.unpaired && (
                <Button size="sm" variant="ghost" icon={Link2} className="mt-2" onClick={() => void repair(peer)}>
                  Ghép lại
                </Button>
              )}
              <Fingerprint value={peer.fingerprint} />
            </div>
            <button type="button" onClick={() => void unpair.start(peer)} className="text-xs font-medium text-danger">
              Thôi ghép
            </button>
          </div>

        </div>
      ))}
      {unpair.dialog}
    </MotionRegion>
  );
}

// Mạng trạm bước 2 (LibraryServer.kt): điện thoại PHỤC VỤ sách mở từ file cho máy đã ghép - máy tính nghe thẳng những cuốn chỉ
// có trên điện thoại (không phải bản soi sách của máy khác). Cùng giao thức cổng đồng bộ của máy tính, nên máy tính ghép như ghép một máy tính khác: Cài đặt →
// Máy tính khác → địa chỉ + mã 6 số hiện ở đây.
export function SharePanel({ bare = false }: { bare?: boolean }) {
  const client = useQueryClient();
  const status = useQuery({
    queryKey: ["share"],
    queryFn: () => EbookLibrary.shareStatus(),
    // Đang hiện mã: hỏi lại để thấy mã đã dùng (thiết bị mới hiện trong danh sách) hay hết hạn.
    refetchInterval: (query) => (query.state.data?.pairing ? 2000 : false),
  });
  const run = useMutation({
    mutationFn: (action: () => Promise<ShareStatus>) => action(),
    onSuccess: (data) => client.setQueryData(["share"], data),
    onError: (error: Error) => toast.error("Chưa làm được", { description: error.message }),
  });
  useEffect(() => {
    // Nút "Tắt chia sẻ" trên thông báo tắt công tắc ngoài màn hình này: hỏi lại để công tắc tắt theo.
    const handle = EbookLibrary.addListener("shareChanged", () => void client.invalidateQueries({ queryKey: ["share"] }));
    return () => void handle.then((listener) => listener.remove());
  }, [client]);
  // Bật chia sẻ lần đầu trên Android 13+: Android hỏi quyền thông báo (thông báo thường trực của ShareService) - nói trước một câu vì sao
  // thay vì để hộp của Android hiện ra không lời nào (soát a68 lỗi 21). Đã cho phép thông báo thì bật luôn.
  const [explain, setExplain] = useState(false);
  const turnOn = async () => {
    const { permitted } = await EbookLibrary.studioAlerts().catch(() => ({ permitted: true }));
    if (permitted) run.mutate(() => EbookLibrary.setShare({ enabled: true }));
    else setExplain(true);
  };
  // Thôi ghép một máy đang nghe thư viện của điện thoại này: hỏi trước như bên máy tính (máy ấy mất quyền nghe cho tới khi ghép lại).
  const [removing, setRemoving] = useState<{ id: string; name: string } | null>(null);
  const [now, setNow] = useState(() => Date.now() / 1000);
  const pairing = status.data?.pairing ?? null;
  useEffect(() => {
    if (!pairing) return;
    const timer = window.setInterval(() => setNow(Date.now() / 1000), 1000);
    return () => window.clearInterval(timer);
  }, [pairing]);
  const data = status.data;
  const enabled = data?.running ?? false;
  const left = pairing ? Math.max(0, Math.round(pairing.expiresAt - now)) : 0;
  const explainBox = useRef<HTMLDivElement>(null);
  const explainButton = useRef<HTMLButtonElement>(null);
  useBackLayer(explain && !enabled, () => setExplain(false), explainBox, explainButton);
  return (
    <MotionRegion as="section" className={bare ? "pt-4" : "mt-8 py-4"} aria-labelledby="share-title">
      <div className="flex items-center justify-between gap-4">
        <div className="min-w-0">
          <SectionHeading id="share-title">Chia sẻ thư viện</SectionHeading>
          <p className="mt-0.5 text-xs leading-snug text-fg-2">
            Máy đã ghép nghe được sách bạn thêm từ file, không cần chép sang.
          </p>
        </div>
        <Switch.Root
          ref={explainButton}
          checked={enabled}
          disabled={run.isPending || status.isLoading}
          onCheckedChange={(value) => (value ? void turnOn() : run.mutate(() => EbookLibrary.setShare({ enabled: false })))}
          aria-label="Chia sẻ thư viện"
          className="ui-switch ui-switch-large"
        >
          <Switch.Thumb className="motion-switch-thumb" />
        </Switch.Root>
      </div>
      {explain && !enabled && (
        <div ref={explainBox} className="mt-3 space-y-3 py-3 text-sm text-fg-2">
          <p className="text-pretty">
            Khi chia sẻ, ABook giữ một thông báo nhỏ để chạy tiếp lúc tắt màn hình.
          </p>
          <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              variant="primary"
              onClick={() => {
                setExplain(false);
                run.mutate(() => EbookLibrary.setShare({ enabled: true }));
              }}
            >
              Tiếp tục
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setExplain(false)}>
              Để sau
            </Button>
          </div>
        </div>
      )}
      {data?.error && <p className="mt-3 text-xs text-danger">{data.error}</p>}
      {enabled && data?.bluetooth?.status && (
        <p className="mt-2 flex items-center gap-1.5 text-xs text-fg-2">
          <Bluetooth className="size-3.5 shrink-0" />
          {data.bluetooth.status === "running"
            ? `Cả qua Bluetooth cho máy đã ghép${data.bluetooth.connections ? ` - ${data.bluetooth.connections} đang kết nối` : ""}`
            : data.bluetooth.status}
        </p>
      )}
      {/* Thiếu quyền "Thiết bị ở gần" thì chỉ nói là chưa đủ; nút mở thẳng trang quyền của ABook (Quyền › Thiết bị ở gần). */}
      {enabled && needsNearbyPermission(data?.bluetooth?.status) && (
        <Button
          variant="ghost"
          size="sm"
          icon={Bluetooth}
          className="mt-1 h-auto min-h-8 justify-start whitespace-normal py-1.5 text-left"
          onClick={() => void EbookLibrary.openAppSettings().catch((error: Error) => toast.error(error.message))}
        >
          Mở cài đặt
        </Button>
      )}
      {/* Như các khung xuất: ẩn hẳn khi ABook đã được cho chạy nền, đọc lại mỗi lần bạn quay về từ Cài đặt. */}
      {enabled && (
        <BackgroundNote
          note="Khi tắt màn hình, máy có thể tạm dừng chia sẻ - máy tính sẽ phải chờ lâu hơn."
        />
      )}
      {enabled && data && (
        <div className="mt-4 space-y-3 border-t border-line pt-4">
          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
            <dt className="text-fg-2">Tên</dt>
            <dd className="truncate">{data.name}</dd>
          </dl>
          {/* Địa chỉ và vân tay chứng chỉ (64 chữ số hex) là thứ để dò khi máy kia không tự thấy điện thoại: người nghe bình thường không cần,
              nên gập lại (soát UX a9). */}
          <Fold storageKey="devices.share.details" title="Chi tiết" heading="h3" className="rounded-none border-0 bg-transparent" bodyClassName="px-0">
            <dl className="mt-1 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 pl-5">
              <dt className="text-fg-2">Địa chỉ</dt>
              <dd className="tabular break-all">
                {data.addresses.length ? data.addresses.map((address) => `${address}:${data.port}`).join(", ") : "chưa vào mạng Wi-Fi nào"}
              </dd>
              {data.fingerprint && (
                <>
                  <dt className="text-fg-2">Vân tay</dt>
                  <dd className="tabular break-all text-xs">{data.fingerprint}</dd>
                </>
              )}
            </dl>
          </Fold>
          {pairing && left > 0 ? (
            <div className="py-4 text-center">
              <div className="text-xs text-fg-2">Nhập mã này trên máy kia</div>
              <div className="tabular mt-1 text-3xl font-bold tracking-[0.3em]">{pairing.code}</div>
              <div className="tabular mt-1 text-xs text-fg-2">
                còn {Math.floor(left / 60)}:{String(left % 60).padStart(2, "0")}
              </div>
              <div className="mt-1 text-xs text-fg-2">Máy kia chưa tự thấy điện thoại? Địa chỉ nằm ở mục Chi tiết phía trên.</div>
              <button type="button" onClick={() => run.mutate(() => EbookLibrary.shareCancelPairing())} className="mt-2 text-sm text-fg-2 underline underline-offset-4">
                Huỷ mã
              </button>
            </div>
          ) : (
            <Button variant="ghost" className="w-full" icon={Link2} onClick={() => run.mutate(() => EbookLibrary.sharePair())}>
              Ghép máy mới
            </Button>
          )}
          {data.blocked && <p className="text-xs text-danger">Nhập sai mã quá 5 lần - mã đã bị huỷ. Bấm “Ghép máy mới” để có mã khác.</p>}
          {data.devices.length > 0 && (
            <ul className="divide-y divide-line">
              {data.devices.map((device) => (
                <li key={device.id} className="flex items-center gap-3 py-2.5">
                  <Laptop className="size-4 shrink-0 text-fg-2" />
                  <span className="min-w-0 flex-1 truncate text-sm">{device.name}</span>
                  <button type="button" onClick={() => setRemoving(device)} className="text-xs font-medium text-danger">
                    Thôi ghép
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
      <Dialog footer={<DialogActions>
          <Button variant="ghost" onClick={() => setRemoving(null)}>
            Để nguyên
          </Button>
          <Button
            variant="danger"
            onClick={() => {
              if (removing) run.mutate(() => EbookLibrary.shareRevoke({ id: removing.id }));
              setRemoving(null);
            }}
          >
            Thôi ghép
          </Button>
        </DialogActions>}
        open={removing !== null}
        onOpenChange={(open) => !open && setRemoving(null)}
        title={`Thôi ghép ${removing?.name ?? "máy này"}?`}
        description="Máy ấy không nghe được thư viện này nữa; sách đã tải vẫn còn."
      >

      </Dialog>
    </MotionRegion>
  );
}

/** Tên điện thoại này mà máy tính và các máy đã ghép thấy (soát a68 lỗi 16: "Google sdk_gphone64_x86_64"): đổi được, báo luôn cho các máy đã ghép. */
function DeviceNameRow({ bare = false }: { bare?: boolean }) {
  const dialogForm1 = useId();
  const client = useQueryClient();
  const connection = useQuery({ queryKey: ["connection"], queryFn: () => EbookLibrary.connection() });
  const [draft, setDraft] = useState<string | null>(null);
  const rename = useMutation({
    mutationFn: (name: string) => EbookLibrary.setDeviceName({ name }),
    onSuccess: ({ name }) => {
      setDraft(null);
      toast.success(`Đã đổi tên thành “${name}”`);
      void client.invalidateQueries({ queryKey: ["connection"] });
      void client.invalidateQueries({ queryKey: ["share"] });
    },
    onError: (error: Error) => toastNativeError("Chưa đổi được tên", error),
  });
  const name = connection.data?.deviceName ?? "";
  // Tự lấy dữ liệu nên tự mang chuyển động: tên về muộn thì khối mở ra, đổi tên thì chữ mờ qua - không bật vào / thay cứng.
  return (
    <MotionPresence open={Boolean(name)}>
    <section className={bare ? "" : "mt-8 py-3.5"} aria-labelledby="device-name-title">
      <div className="flex items-center gap-3">
        <Smartphone className="size-5 shrink-0 text-fg-2" />
        <div className="min-w-0 flex-1">
          <div id="device-name-title" className="text-xs text-fg-2">
            Tên điện thoại
          </div>
          <MotionRegion className="truncate font-medium">{name}</MotionRegion>
        </div>
        <Button size="sm" variant="ghost" className="settings-edge-action" icon={Pencil} onClick={() => setDraft(name)}>
          Đổi tên
        </Button>
      </div>
      <Dialog footer={<DialogActions>
            <Button type="button" variant="ghost" onClick={() => setDraft(null)}>
              Để nguyên
            </Button>
            <Button type="submit" form={dialogForm1} variant="primary" disabled={!draft?.trim()} loading={rename.isPending}>
              Lưu
            </Button>
          </DialogActions>} open={draft !== null} onOpenChange={(open) => !open && setDraft(null)} title="Đổi tên điện thoại này" description="Máy tính và các máy đã ghép thấy điện thoại bằng tên này.">
        <form id={dialogForm1}
          onSubmit={(event) => {
            event.preventDefault();
            if (draft?.trim()) rename.mutate(draft.trim());
          }}
          className="flex flex-col gap-4"
        >
          <input
            data-autofocus
            value={draft ?? ""}
            onChange={(event) => setDraft(event.target.value.slice(0, 60))}
            aria-label="Tên điện thoại"
            className="device-input w-full px-3 text-base"
          />

        </form>
      </Dialog>
    </section>
    </MotionPresence>
  );
}

/** Sách trên máy: tổng, rồi từng thứ đang chiếm chỗ (nhiều nhất trước) để chọn cái xoá cho nhẹ máy - cuốn đã tải, và cả phần tải dở / gói nghe thẳng đã nhớ
 *  ("Xoá phần đã tải"; cuốn vẫn ở máy tính). Cuốn đang có lượt tải chạy thì chưa xoá được. */
export function StoragePanel({ storage, names, bare = false }: { storage: { bytes: number; free: number; books: StoredFolder[] }; names?: ReadonlyMap<string, string>; bare?: boolean }) {
  const { data: library } = useListenLibrary();
  const progress = useDownloadProgress();
  const entries = storedEntries(storage.books, library ?? [], names);
  // Xoá một cuốn: hàng khép lại tại chỗ (shared/motion.ts useListPresence).
  const rows = useListPresence(entries, (entry) => entry.id);
  return (
    <section className={bare ? "" : "mt-8"} aria-label="Dung lượng sách trên máy">
      {!bare && (
        <p className="text-center text-xs text-fg-3">
          Sách trên máy: {formatSize(storage.bytes)} · còn trống {formatSize(storage.free)}
        </p>
      )}
      {/* Khung (cả lề trên) khép lại sau khi hàng cuối khép xong / mở trước hàng đầu - không gắn / gỡ cứng. */}
      <MotionPresence open={rows.length > 0}>
        <ul className="mt-3 divide-y divide-line">
          {rows.map(({ key, state, ref, item: { id, title, bytes, kind } }) => {
            const busy = isDownloading(progress[id]);
            return (
              <li key={key} ref={ref} className="motion-row" data-state={state} inert={state === "exit"}>
              <div className="flex items-center gap-3 py-2.5">
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm">{title}</div>
                  {kind === "partial" && <MotionRegion motionKey={busy} className="text-xs text-fg-3">{busy ? "Đang tải" : "Phần đã tải, chưa thành sách trên máy"}</MotionRegion>}
                </div>
                <div className="shrink-0 text-xs text-fg-2">{formatSize(bytes)}</div>
                <button
                  type="button"
                  disabled={busy}
                  aria-label={kind === "book" ? `Xoá ${title} khỏi điện thoại` : `Xoá phần đã tải của ${title}`}
                  onClick={() => window.dispatchEvent(new CustomEvent<RemovableFromPhone>("abook-remove-from-phone", { detail: { id, title, partial: kind === "partial" } }))}
                  className="-mr-2.5 grid size-9 shrink-0 place-items-center rounded-full text-fg-2 disabled:opacity-40"
                >
                  <Trash2 className="size-4" />
                </button>
              </div>
              </li>
            );
          })}
        </ul>
      </MotionPresence>
    </section>
  );
}

export function DevicesScreen() {
  const client = useQueryClient();
  const connection = useQuery({ queryKey: ["connection"], queryFn: () => EbookLibrary.connection() });
  const remote = useQuery({
    queryKey: ["remote"],
    enabled: Boolean(connection.data?.paired),
    queryFn: () => EbookLibrary.remoteLibrary(),
    retry: 0,
  });
  useEffect(() => {
    if (remote.dataUpdatedAt) void client.invalidateQueries({ queryKey: ["connection"] });
  }, [client, remote.dataUpdatedAt]);
  const storage = useStorage();
  // Cùng khoá với SharePanel: chỉ để ghi dòng tóm tắt của khối gập "Điện thoại này".
  const share = useQuery({ queryKey: ["share"], queryFn: () => EbookLibrary.shareStatus() });

  const [confirmUnpair, setConfirmUnpair] = useState(false);
  const computerName = connection.data?.name || connection.data?.host || "máy tính";
  const unpair = async (announce: boolean) => {
    await EbookLibrary.unpair();
    void client.invalidateQueries({ queryKey: ["connection"] });
    if (announce) toast.success(`Đã bỏ ghép với ${computerName}`);
  };
  // Máy tính trả 401: nó đã thôi ghép điện thoại này - không phải tắt máy hay khác Wi-Fi (soát a68 lỗi 5). "Ghép lại" quên mã cũ rồi mở hộp
  // ghép với sẵn địa chỉ máy tính (PairPanel).
  const unpairedHere = remote.isError && isUnpaired(remote.error);
  const failure = remote.isError ? nativeError(remote.error) : null;

  return (
    <MotionRegion as="div" data-list-edges="devices" className="pb-8 pt-4">
      <div className="mt-5">
        {!connection.data?.paired ? (
          <>
            <PairPanel />
            <Fold storageKey="devices.install" title="Cài trên máy tính" className="mt-4">
              <ComputerIntro />
            </Fold>
          </>
        ) : (
          <>
            <div className="flex items-center gap-3 py-4">
              <Laptop className="size-5 text-fg-2" />
              <div className="min-w-0 flex-1">
                <div className="truncate font-semibold">
                  {connection.data.name || connection.data.host}
                </div>
                <div className={cn("text-xs", remote.isError ? "text-danger" : "text-fg-2")}>
                  {unpairedHere
                    ? `Máy tính ${computerName} đã thôi ghép với điện thoại này`
                    : remote.isError
                      ? pinChanged(remote.error)
                        ? remote.error.message
                        : "Không kết nối được - máy tính đang tắt hoặc khác mạng Wi-Fi"
                      : connectionRoute(connection.data.connectedVia)}
                </div>
                {remote.isError && !unpairedHere && !pinChanged(remote.error) && <ErrorDetails technical={failure?.technical} className="text-fg-2" />}
                {unpairedHere && (
                  <Button size="sm" variant="ghost" icon={Link2} className="mt-2" onClick={() => void unpair(false)}>
                    Ghép lại
                  </Button>
                )}
                <Fingerprint value={connection.data.fingerprint} />
              </div>
              <button type="button" aria-label="Làm mới" onClick={() => void remote.refetch()} className="touch-hit -mr-3 grid size-10 place-items-center rounded-full text-fg-2">
                <RefreshCw className={cn("size-4", remote.isFetching && "animate-spin")} />
              </button>
            </div>
            {/* Như Cài đặt → Điện thoại và thiết bị của máy tính (chủ sách 29-09: khác mạng có dùng được không): app không cần gì
                riêng - mạng riêng ảo cho máy tính một địa chỉ tới được, và điện thoại học địa chỉ ấy mỗi lần liệt kê sách. */}
            {remote.isError && !pinChanged(remote.error) && !unpairedHere && (
              <div className="mt-2 text-xs leading-snug text-fg-2">
                Sách đã tải vẫn nghe được khi ra ngoài.
                <MoreInfo label="Nghe khi ra ngoài">
                  Cho hai máy vào cùng một mạng riêng ảo (Tailscale, ZeroTier, NetBird, WireGuard), rồi mở mục này một lần khi còn ở nhà.
                </MoreInfo>
              </div>
            )}
            {/* Cùng cột icon / mép chữ với hàng máy tính ở trên. "Bỏ ghép", không "Ngắt kết nối": máy có khi đang chưa kết nối, việc làm là quên mã ghép. */}
            <button type="button" onClick={() => setConfirmUnpair(true)} className="touch-hit mt-2 flex items-center gap-3 text-sm text-fg-2">
              <Unplug className="size-5" /> Bỏ ghép
            </button>
            <Dialog footer={<DialogActions>
                <Button variant="ghost" onClick={() => setConfirmUnpair(false)}>
                  Để nguyên
                </Button>
                <Button
                  variant="danger"
                  onClick={() => {
                    setConfirmUnpair(false);
                    void unpair(true).catch((error) => toastNativeError("Chưa bỏ ghép được", error));
                  }}
                >
                  Bỏ ghép
                </Button>
              </DialogActions>}
              open={confirmUnpair}
              onOpenChange={setConfirmUnpair}
              title={`Bỏ ghép với ${computerName}?`}
              description="Sách đã tải vẫn nghe được. Muốn tải thêm thì ghép lại bằng mã mới."
            >

            </Dialog>
          </>
        )}
      </div>
      <PeersPanel />
      {/* Phần ít dùng gập lại, nhớ gấp / mở trên máy này (a120 - chủ app: "foldout chúng lại… chứ để hết một trang dài ơi là dài"). */}
      <Fold
        storageKey="devices.this"
        title="Điện thoại này"
        summary={[connection.data?.deviceName, share.data?.running ? "đang cho máy khác nghe" : "không chia sẻ"].filter(Boolean).join(" · ")}
        icon={<Smartphone className="ink-start size-5 [--icon-w:calc(var(--spacing)*5)]" />}
        className="mt-8 rounded-none border-0 bg-transparent"
      >
        <DeviceNameRow bare />
        <SharePanel bare />
      </Fold>
      {storage.data && (
        <Fold
          storageKey="devices.storage"
          title="Dung lượng trên máy"
          summary={`Sách ${formatSize(storage.data.bytes)} · còn trống ${formatSize(storage.data.free)}`}
          icon={<HardDrive className="size-5" />}
          className="mt-3 rounded-none border-0 bg-transparent"
        >
          <StoragePanel storage={storage.data} names={new Map((remote.data?.books ?? []).map((book) => [book.id, book.title]))} bare />
        </Fold>
      )}
    </MotionRegion>
  );
}
