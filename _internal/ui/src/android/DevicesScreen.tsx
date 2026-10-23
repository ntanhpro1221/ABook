import * as Switch from "@radix-ui/react-switch";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bluetooth, CheckCircle2, ChevronRight, Copy, Download, FileAudio, Laptop, Link2, Loader2, Pencil, RefreshCw, Search, Smartphone, Trash2, Unplug, Wifi, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { BookCover } from "@/shared/BookCover";
import { cn } from "@/shared/cn";
import { formatFingerprint, formatLength, formatSize } from "@/shared/format";
import { SYNC_SWITCH_LABEL } from "@/shared/syncSwitch";
import { Button, Dialog, EmptyState, Progress } from "@/shared/ui";
import { useUnpair } from "@/shared/useUnpair";
import { BackgroundNote } from "./BackgroundNote";
import { BLUETOOTH_DENIED, BLUETOOTH_REASON, bluetoothStep } from "./bluetoothPermission";
import { connectionRoute } from "@/shared/connectionRoute";
import { useDownloadProgress } from "./downloads";
import { pickBookFile } from "./imports";
import { hasNewAudio, hasNewMeta, hasNewWords } from "./bookUpdates";
import { OpenStudioButton, useStudioComputers } from "./StudioOpen";
import { openRelease } from "./UpdateNotice";
import { isDownloading, storedEntries, useStorage, type RemovableFromPhone, type StoredFolder } from "./storage";
import { ErrorDetails } from "@/shared/ErrorDetails";
import { isUnpaired, nativeError, toastNativeError } from "./nativeError";
import { useListenLibrary } from "@/listen/source";
import { EbookLibrary, type DownloadEvent, type RemoteBook, type ShareStatus } from "./plugins";

// "Tải sách": lấy sách từ máy tính qua Wi-Fi. Ghép nối một lần bằng mã 6 số hiện trong Cài đặt của máy tính;
// sau đó chỉ cần mở màn hình này để thấy sách mới và chương mới.

/** Trang tải ABook cho máy tính (chữ chép được; lõi native chỉ mở địa chỉ bắt đầu bằng ".../ABook/" - LibraryPlugin.openRelease). */
export const DESKTOP_RELEASES = "https://github.com/ntanhpro1221/ABook/releases";

/** Mở đầu cho người chỉ có điện thoại (soát a66): máy tính thêm được gì và lấy ABook máy tính ở đâu - rồi mới tới các bước ghép nối. */
function ComputerIntro() {
  const copy = () =>
    void navigator.clipboard
      .writeText(DESKTOP_RELEASES)
      .then(() => toast.success("Đã chép địa chỉ"), () => toast.error("Chưa chép được - giữ ngón tay lên địa chỉ để chọn rồi chép"));
  return (
    <div className="rounded-2xl border border-line bg-panel p-5 text-sm">
      <div className="flex items-center gap-3">
        <div className="grid size-11 shrink-0 place-items-center rounded-xl bg-accent-soft text-accent-text">
          <Laptop className="size-5" />
        </div>
        <h2 className="font-semibold">Có thêm máy tính thì sao?</h2>
      </div>
      <p className="mt-3 text-pretty text-fg-2">
        Điện thoại đã tự đọc được mọi sách bằng Nghe ngay. ABook trên máy tính còn làm được sách nói nhiều giọng bằng Studio (cần card đồ hoạ
        NVIDIA) - mỗi nhân vật một giọng - rồi gửi sang đây để bạn nghe tiếp trên điện thoại.
      </p>
      <p className="mt-2 text-fg-2">Tải ABook cho máy tính (Windows) ở:</p>
      <p className="mt-1 select-text break-all font-medium text-fg">{DESKTOP_RELEASES.replace("https://", "")}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        <Button size="sm" variant="secondary" icon={Copy} onClick={copy}>
          Chép địa chỉ
        </Button>
        <Button size="sm" variant="ghost" onClick={() => void openRelease(DESKTOP_RELEASES)}>
          Mở trang tải
        </Button>
      </div>
    </div>
  );
}

function PairPanel() {
  const client = useQueryClient();
  const connection = useQuery({ queryKey: ["connection"], queryFn: () => EbookLibrary.connection() });
  const [computers, setComputers] = useState<{ host: string; port: number; name: string }[] | null>(null);
  const [target, setTarget] = useState<{ host: string; port: number; name: string } | null>(null);
  const [manual, setManual] = useState(false);
  const [address, setAddress] = useState("");
  const [code, setCode] = useState("");
  const [paired, setPaired] = useState<{ address: string; name: string; abook: boolean }[] | null>(null);
  // Trước khi Android hỏi quyền "Thiết bị ở gần": "explain" = một câu vì sao cần + nút Cho phép; "settings" = đã từ chối hẳn, chỉ tới Cài đặt.
  const [btAsk, setBtAsk] = useState<"explain" | "settings" | null>(null);
  // Lời giải thích hiện ở chỗ nút vừa bấm, thường sát mép dưới màn: cuộn cho thấy cả câu lẫn nút "Cho phép".
  const btBox = useRef<HTMLDivElement | null>(null);
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
    <div className="space-y-5">
      <div className="rounded-2xl border border-line bg-panel p-5">
        <div className="flex items-center gap-3">
          <div className="grid size-11 place-items-center rounded-xl bg-accent-soft text-accent-text">
            <Wifi className="size-5" />
          </div>
          <div>
            <h2 className="font-semibold">Đã có ABook trên máy tính? Kết nối</h2>
            <p className="text-sm text-fg-2">Điện thoại và máy tính cần cùng một mạng Wi-Fi.</p>
          </div>
        </div>
        <ol className="mt-4 space-y-1.5 text-sm text-fg-2">
          <li>1. Trên máy tính: mở ABook → Cài đặt → bật “{SYNC_SWITCH_LABEL}” → bấm “Ghép thiết bị mới”.</li>
          <li>2. Chọn máy tính bên dưới và nhập mã 6 số vừa hiện trên máy tính.</li>
        </ol>
      </div>

      {!manual && (
        <div>
          <div className="mb-2 flex items-center justify-between">
            <span className="text-sm font-semibold">Máy tính tìm thấy</span>
            <button type="button" onClick={() => discover.mutate()} className="flex items-center gap-1.5 text-sm text-accent-text">
              {discover.isPending ? <Loader2 className="size-4 animate-spin" /> : <Search className="size-4" />} Tìm lại
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
                    "flex w-full items-center gap-3 rounded-xl border p-3.5 text-left",
                    target?.host === computer.host ? "border-focus bg-accent-soft" : "border-line bg-panel",
                  )}
                >
                  <Laptop className="size-5 text-fg-2" />
                  <span className="flex-1">
                    <span className="block font-medium">{computer.name}</span>
                    <span className="block text-xs text-fg-2">{computer.host}</span>
                  </span>
                  {target?.host === computer.host && <CheckCircle2 className="size-5 text-accent-text" />}
                </button>
              ))}
            </div>
          ) : (
            <p className="rounded-xl bg-hover px-4 py-3 text-sm text-fg-2">
              {discover.isPending ? "Đang tìm trong mạng Wi-Fi…" : "Chưa thấy máy tính nào. Kiểm tra máy tính đã bật kết nối, hoặc nhập địa chỉ."}
            </p>
          )}
        </div>
      )}

      {!manual && (
        <div>
          {paired === null && btAsk ? (
            <div ref={btBox} className="space-y-3 rounded-xl bg-hover px-4 py-3 text-sm text-fg-2">
              <p className="text-pretty">{btAsk === "explain" ? BLUETOOTH_REASON : BLUETOOTH_DENIED}</p>
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
            <button type="button" onClick={() => void startBluetooth()} className="flex items-center gap-1.5 text-sm font-medium text-accent-text">
              {bluetooth.isPending ? <Loader2 className="size-4 animate-spin" /> : <Bluetooth className="size-4" />} Không chung Wi-Fi? Kết nối qua Bluetooth
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
                    "flex w-full items-center gap-3 rounded-xl border p-3.5 text-left",
                    target?.host === `bt:${device.address}` ? "border-focus bg-accent-soft" : "border-line bg-panel",
                  )}
                >
                  <Bluetooth className="size-5 text-fg-2" />
                  <span className="flex-1">
                    <span className="block font-medium">{device.name}</span>
                    <span className="block text-xs text-fg-2">Qua Bluetooth{device.abook ? " · có ABook" : ""}</span>
                  </span>
                  {target?.host === `bt:${device.address}` && <CheckCircle2 className="size-5 text-accent-text" />}
                </button>
              ))}
            </div>
          ) : (
            <p className="rounded-xl bg-hover px-4 py-3 text-sm text-fg-2">
              Chưa có máy tính nào ghép Bluetooth với điện thoại. Ghép trong Cài đặt Android → Bluetooth (máy tính bật
              Bluetooth và ABook), rồi thử lại.
            </p>
          )}
        </div>
      )}

      <button type="button" onClick={() => { setManual((value) => !value); setTarget(null); }} className="text-sm font-medium text-fg-2 underline underline-offset-4">
        {manual ? "Tự tìm máy tính" : "Nhập địa chỉ máy tính"}
      </button>
      {manual && (
        <input
          value={address}
          onChange={(event) => setAddress(event.target.value)}
          inputMode="url"
          placeholder="Ví dụ 192.168.1.20:47630"
          className="h-12 w-full rounded-xl border border-line bg-panel px-4 text-base outline-none focus:border-focus"
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
          className="tabular mt-1.5 h-14 w-full rounded-xl border border-line bg-panel text-center text-2xl font-semibold tracking-[0.5em] outline-none focus:border-focus"
        />
      </label>
      <Button variant="primary" size="lg" className="w-full" disabled={!ready} loading={pair.isPending} onClick={() => pair.mutate()}>
        Kết nối
      </Button>
    </div>
  );
}

export function RemoteRow({ book, progress, onDownload }: { book: RemoteBook; progress?: DownloadEvent; onDownload: () => void }) {
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
  return (
    <div className="flex items-center gap-3 py-3">
      <BookCover title={book.title} size="sm" className="size-14" />
      <div className="min-w-0 flex-1">
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
      </div>
      {downloading ? (
        <div className="flex shrink-0 items-center gap-1">
          <span className="tabular w-10 text-right text-xs font-semibold text-accent-text" aria-hidden>
            {percent}%
          </span>
          <button
            type="button"
            onClick={cancel}
            aria-label={`Huỷ tải ${book.title}`}
            className="grid size-10 place-items-center rounded-full text-fg-2"
          >
            <X className="size-4" />
          </button>
        </div>
      ) : book.downloaded && newChapters <= 0 && !newCover && !newWords && !newAudio && !newMeta ? (
        <span className="flex items-center gap-1 text-xs text-success">
          <CheckCircle2 className="size-4" /> Đã tải
        </span>
      ) : (
        <Button size="sm" variant={book.downloaded ? "secondary" : "primary"} icon={Download} onClick={onDownload}>
          {!book.downloaded ? "Tải" : newChapters > 0 ? `+${newChapters} chương` : newAudio ? "Cập nhật bản thu" : newCover ? "Cập nhật bìa" : newMeta ? "Cập nhật tên" : "Cập nhật chữ"}
        </Button>
      )}
    </div>
  );
}

// Báo về điện thoại khi máy tính sản xuất có tin (StudioAlerts.kt): sách xong, dừng vì lỗi, có việc mới cần duyệt.
// Cần công tắc Studio từ xa trên máy tính và quyền điều khiển sản xuất cho điện thoại này - như chính trang Studio.
function StudioAlertsRow() {
  const client = useQueryClient();
  const state = useQuery({ queryKey: ["studio-alerts"], queryFn: () => EbookLibrary.studioAlerts() });
  const change = useMutation({
    mutationFn: (enabled: boolean) => EbookLibrary.setStudioAlerts({ enabled }),
    onSuccess: (data) => {
      client.setQueryData(["studio-alerts"], data);
      if (data.enabled && !data.permitted) toast.error("Android chưa cho ABook đăng thông báo", { description: "Bật lại trong Cài đặt của máy > Ứng dụng > ABook > Thông báo." });
      else if (data.enabled) toast.success("Sẽ báo khi sách xong hay có việc cần duyệt", { description: "Máy tính cần bật \"Cho phép điều khiển sản xuất\"." });
    },
    onError: (error: Error) => toast.error("Chưa đổi được", { description: error.message }),
  });
  const enabled = state.data?.enabled ?? false;
  return (
    <div className="mt-3 flex items-center justify-between gap-4 rounded-2xl border border-line bg-panel px-4 py-3.5">
      <div className="min-w-0">
        <div className="text-[0.9375rem] font-medium">Báo khi sách xong hay có việc cần duyệt</div>
        <div className="mt-0.5 text-xs leading-snug text-fg-2">
          {enabled && state.data && !state.data.permitted
            ? "Android đang chặn thông báo của ABook."
            : "Điện thoại hỏi máy tính mỗi 15 phút và mỗi lần mở app."}
        </div>
      </div>
      <Switch.Root
        checked={enabled}
        disabled={change.isPending || state.isLoading}
        onCheckedChange={(value) => change.mutate(value)}
        aria-label="Báo khi sách xong hay có việc cần duyệt"
        className="relative h-7 w-12 shrink-0 rounded-full bg-switch-off transition-colors data-[state=checked]:bg-focus"
      >
        <Switch.Thumb className="block size-6 translate-x-0.5 rounded-full bg-white shadow transition-transform data-[state=checked]:translate-x-[22px]" />
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

// Thiết bị ghép ngoài máy tính chính (Peers.kt - mạng trạm bước 2): điện thoại khác bật "Cho máy khác nghe thư viện này",
// hay một máy tính nữa. Sách của chúng nghe thẳng được trong Thư viện ("Trên <tên>") và tải về như sách máy tính.
function PeersPanel() {
  const client = useQueryClient();
  const progress = useDownloadProgress();
  const libraries = useQuery({ queryKey: ["peer-libraries"], queryFn: () => EbookLibrary.peerLibraries(), retry: 0 });
  const connection = useQuery({ queryKey: ["connection"], queryFn: () => EbookLibrary.connection() });
  const [open, setOpen] = useState(false);
  const [found, setFound] = useState<{ host: string; port: number; name: string; kind?: string }[] | null>(null);
  const [address, setAddress] = useState("");
  const [code, setCode] = useState("");
  const [bonded, setBonded] = useState<{ address: string; name: string; kind: string }[] | null>(null);
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
    <section className="mt-8" aria-labelledby="peers-title">
      <div className="flex items-center justify-between gap-3">
        <h2 id="peers-title" className="text-lg font-semibold">
          Thiết bị khác
        </h2>
        <Button size="sm" variant="secondary" icon={Link2} onClick={() => { setOpen((value) => !value); if (!open) discover.mutate(); }}>
          Ghép thiết bị
        </Button>
      </div>
      <p className="mt-1 text-xs leading-snug text-fg-2">
        Điện thoại khác (bật “Cho máy khác nghe thư viện này” ở màn Tải sách của nó) hay một máy tính nữa. Sách của chúng nghe
        thẳng được trong Thư viện.
      </p>
      {open && (
        <div className="mt-3 space-y-3 rounded-2xl border border-line bg-panel p-4">
          {bonded === null ? (
            <button type="button" onClick={() => bluetooth.mutate()} className="flex items-center gap-1.5 text-sm font-medium text-accent-text">
              {bluetooth.isPending ? <Loader2 className="size-4 animate-spin" /> : <Bluetooth className="size-4" />} Không chung Wi-Fi? Ghép qua Bluetooth
            </button>
          ) : bonded.length ? (
            <div className="space-y-2">
              {bonded.map((device) => (
                <button
                  key={device.address}
                  type="button"
                  onClick={() => setAddress(`bt:${device.address}`)}
                  className={cn(
                    "flex w-full items-center gap-3 rounded-xl border p-3 text-left",
                    address === `bt:${device.address}` ? "border-focus bg-accent-soft" : "border-line",
                  )}
                >
                  <Bluetooth className="size-5 text-fg-2" />
                  <span className="flex-1">
                    <span className="block font-medium">{device.name}</span>
                    <span className="block text-xs text-fg-2">Qua Bluetooth · {device.kind === "phone" ? "điện thoại" : "máy tính"}</span>
                  </span>
                  {address === `bt:${device.address}` && <CheckCircle2 className="size-5 text-accent-text" />}
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
                    "flex w-full items-center gap-3 rounded-xl border p-3 text-left",
                    address === `${item.host}:${item.port}` ? "border-focus bg-accent-soft" : "border-line",
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
            className="h-11 w-full rounded-xl border border-line bg-panel px-3 text-base outline-none focus:border-focus"
          />
          <input
            value={code}
            onChange={(event) => setCode(event.target.value.replace(/\D/g, "").slice(0, 6))}
            inputMode="numeric"
            placeholder="Mã 6 số"
            className="tabular h-11 w-full rounded-xl border border-line bg-panel px-3 text-center text-lg tracking-[0.3em] outline-none focus:border-focus"
          />
          <Button variant="primary" className="w-full" disabled={!ready} loading={pair.isPending} onClick={() => pair.mutate()}>
            Ghép
          </Button>
        </div>
      )}
      {peers.map((peer) => (
        <div key={peer.key} className="mt-4 rounded-2xl border border-line bg-panel p-4">
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
                <Button size="sm" variant="secondary" icon={Link2} className="mt-2" onClick={() => void repair(peer)}>
                  Ghép lại
                </Button>
              )}
              <Fingerprint value={peer.fingerprint} />
            </div>
            <button type="button" onClick={() => void unpair.start(peer)} className="text-xs font-medium text-danger">
              Thôi ghép
            </button>
          </div>
          <div className="mt-2 divide-y divide-line">
            {peer.books.map((book) => (
              <RemoteRow
                key={book.id}
                book={book}
                progress={progress[book.id]}
                onDownload={() =>
                  void EbookLibrary.download({ bookId: book.id, source: peer.key, remoteId: book.remoteId }).catch(() => undefined)
                }
              />
            ))}
          </div>
        </div>
      ))}
      {unpair.dialog}
    </section>
  );
}

// Mạng trạm bước 2 (LibraryServer.kt): điện thoại PHỤC VỤ sách mở từ file cho máy đã ghép - máy tính nghe thẳng những cuốn chỉ
// có trên điện thoại (không phải bản soi sách của máy khác). Cùng giao thức cổng đồng bộ của máy tính, nên máy tính ghép như ghép một máy tính khác: Cài đặt →
// Máy tính khác → địa chỉ + mã 6 số hiện ở đây.
export function SharePanel() {
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
  return (
    <section className="mt-8 rounded-2xl border border-line bg-panel p-4" aria-labelledby="share-title">
      <div className="flex items-center justify-between gap-4">
        <div className="min-w-0">
          <h2 id="share-title" className="text-[0.9375rem] font-medium">Cho máy khác nghe thư viện này</h2>
          <p className="mt-0.5 text-xs leading-snug text-fg-2">
            Máy đã ghép nghe thẳng những cuốn bạn tự thêm từ file vào điện thoại này, không phải chép sang. Chia sẻ chạy cả khi ABook ở nền, cho
            tới khi tắt ở đây hay ở thông báo. Máy OPPO, Xiaomi… có thể cho ABook "ngủ" khi ở nền: máy tính sẽ chờ lâu hơn - mở ABook
            lên là trả lời ngay.
          </p>
        </div>
        <Switch.Root
          checked={enabled}
          disabled={run.isPending || status.isLoading}
          onCheckedChange={(value) => (value ? void turnOn() : run.mutate(() => EbookLibrary.setShare({ enabled: false })))}
          aria-label="Cho máy khác nghe thư viện này"
          className="relative h-7 w-12 shrink-0 rounded-full bg-switch-off transition-colors data-[state=checked]:bg-focus"
        >
          <Switch.Thumb className="block size-6 translate-x-0.5 rounded-full bg-white shadow transition-transform data-[state=checked]:translate-x-[22px]" />
        </Switch.Root>
      </div>
      {explain && !enabled && (
        <div className="mt-3 space-y-3 rounded-xl bg-hover px-4 py-3 text-sm text-fg-2">
          <p className="text-pretty">
            Trong lúc chia sẻ, ABook giữ một thông báo nhỏ để Android không tắt nó khi bạn tắt màn hình. Android sẽ hỏi bạn có cho ABook hiện
            thông báo không - từ chối thì chia sẻ vẫn chạy.
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
          Mở cài đặt để cho phép
        </Button>
      )}
      {/* Như các khung xuất: ẩn hẳn khi ABook đã được cho chạy nền, đọc lại mỗi lần bạn quay về từ Cài đặt. */}
      {enabled && (
        <BackgroundNote
          note="Khi tắt màn hình, máy có thể tạm dừng chia sẻ - máy tính sẽ phải chờ lâu hơn."
          action="Để máy tính khỏi phải chờ: cho ABook chạy nền"
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
          <details className="group text-sm">
            <summary className="flex min-h-9 cursor-pointer list-none items-center gap-1.5 text-fg-2 [&::-webkit-details-marker]:hidden">
              <ChevronRight className="size-4 transition-transform group-open:rotate-90" aria-hidden />
              Chi tiết
            </summary>
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
          </details>
          {pairing && left > 0 ? (
            <div className="rounded-xl bg-accent-soft p-4 text-center">
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
            <Button variant="secondary" className="w-full" icon={Link2} onClick={() => run.mutate(() => EbookLibrary.sharePair())}>
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
      <Dialog
        open={removing !== null}
        onOpenChange={(open) => !open && setRemoving(null)}
        title={`Thôi ghép ${removing?.name ?? "máy này"}?`}
        description="Máy này sẽ không nghe được thư viện của điện thoại nữa cho tới khi ghép lại. Sách nó đã tải về vẫn nghe được."
      >
        <div className="dialog-actions">
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
        </div>
      </Dialog>
    </section>
  );
}

/** Tên điện thoại này mà máy tính và các máy đã ghép thấy (soát a68 lỗi 16: "Google sdk_gphone64_x86_64"): đổi được, báo luôn cho các máy đã ghép. */
function DeviceNameRow() {
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
  if (!name) return null;
  return (
    <section className="mt-8 rounded-2xl border border-line bg-panel px-4 py-3.5" aria-labelledby="device-name-title">
      <div className="flex items-center gap-3">
        <Smartphone className="size-5 shrink-0 text-fg-2" />
        <div className="min-w-0 flex-1">
          <div id="device-name-title" className="text-xs text-fg-2">
            Tên điện thoại này (máy khác thấy)
          </div>
          <div className="truncate font-medium">{name}</div>
        </div>
        <Button size="sm" variant="ghost" icon={Pencil} onClick={() => setDraft(name)}>
          Đổi tên
        </Button>
      </div>
      <Dialog open={draft !== null} onOpenChange={(open) => !open && setDraft(null)} title="Đổi tên điện thoại này" description="Máy tính và các máy đã ghép thấy điện thoại bằng tên này.">
        <form
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
            className="h-12 w-full rounded-xl border border-line bg-panel px-4 text-base outline-none focus:border-focus"
          />
          <div className="dialog-actions">
            <Button type="button" variant="ghost" onClick={() => setDraft(null)}>
              Để nguyên
            </Button>
            <Button type="submit" variant="primary" disabled={!draft?.trim()} loading={rename.isPending}>
              Lưu
            </Button>
          </div>
        </form>
      </Dialog>
    </section>
  );
}

/** Sách trên máy: tổng, rồi từng thứ đang chiếm chỗ (nhiều nhất trước) để chọn cái xoá cho nhẹ máy - cuốn đã tải, và cả phần tải dở / gói nghe thẳng đã nhớ
 *  ("Xoá phần đã tải"; cuốn vẫn ở máy tính). Cuốn đang có lượt tải chạy thì chưa xoá được. */
export function StoragePanel({ storage, names }: { storage: { bytes: number; free: number; books: StoredFolder[] }; names?: ReadonlyMap<string, string> }) {
  const { data: library } = useListenLibrary();
  const progress = useDownloadProgress();
  const entries = storedEntries(storage.books, library ?? [], names);
  return (
    <section className="mt-8" aria-label="Dung lượng sách trên máy">
      <p className="text-center text-xs text-fg-3">
        Sách trên máy: {formatSize(storage.bytes)} · còn trống {formatSize(storage.free)}
      </p>
      {entries.length > 0 && (
        <ul className="mt-3 divide-y divide-line rounded-2xl border border-line bg-panel">
          {entries.map(({ id, title, bytes, kind }) => {
            const busy = isDownloading(progress[id]);
            return (
              <li key={id} className="flex items-center gap-3 px-4 py-2.5">
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm">{title}</div>
                  {kind === "partial" && <div className="text-xs text-fg-3">{busy ? "Đang tải" : "Phần đã tải, chưa thành sách trên máy"}</div>}
                </div>
                <div className="shrink-0 text-xs text-fg-2">{formatSize(bytes)}</div>
                <button
                  type="button"
                  disabled={busy}
                  aria-label={kind === "book" ? `Xoá ${title} khỏi điện thoại` : `Xoá phần đã tải của ${title}`}
                  onClick={() => window.dispatchEvent(new CustomEvent<RemovableFromPhone>("abook-remove-from-phone", { detail: { id, title, partial: kind === "partial" } }))}
                  className="grid size-9 shrink-0 place-items-center rounded-full text-fg-2 disabled:opacity-40"
                >
                  <Trash2 className="size-4" />
                </button>
              </li>
            );
          })}
        </ul>
      )}
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
  const progress = useDownloadProgress();
  const studioComputers = useStudioComputers();

  const [confirmUnpair, setConfirmUnpair] = useState(false);
  const computerName = connection.data?.name || connection.data?.host || "máy tính";
  const unpair = async (announce: boolean) => {
    await EbookLibrary.unpair();
    void client.invalidateQueries({ queryKey: ["connection"] });
    if (announce) toast.success(`Đã ngắt kết nối với ${computerName}`, { description: "Sách đã tải về vẫn ở điện thoại và nghe được." });
  };
  // Máy tính trả 401: nó đã thôi ghép điện thoại này - không phải tắt máy hay khác Wi-Fi (soát a68 lỗi 5). "Ghép lại" quên mã cũ rồi mở hộp
  // ghép với sẵn địa chỉ máy tính (PairPanel).
  const unpairedHere = remote.isError && isUnpaired(remote.error);
  const failure = remote.isError ? nativeError(remote.error) : null;

  return (
    <div className="px-4 pb-8 pt-4">
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-2xl font-bold tracking-tight">Tải sách</h1>
        <Button size="sm" variant="secondary" icon={FileAudio} onClick={() => void pickBookFile()}>
          Mở file sách
        </Button>
      </div>
      <div className="mt-5">
        {!connection.data?.paired ? (
          <>
            <ComputerIntro />
            <div className="mt-5">
              <PairPanel />
            </div>
            {/* Chưa ghép máy tính chính mà đã ghép máy tính khác (Peers): Studio của máy ấy vẫn mở được từ đây. */}
            <OpenStudioButton computers={studioComputers} className="mt-3 w-full" />
          </>
        ) : (
          <>
            <div className="flex items-center gap-3 rounded-2xl border border-line bg-panel p-4">
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
                  <Button size="sm" variant="secondary" icon={Link2} className="mt-2" onClick={() => void unpair(false)}>
                    Ghép lại
                  </Button>
                )}
                <Fingerprint value={connection.data.fingerprint} />
              </div>
              <button type="button" aria-label="Làm mới" onClick={() => void remote.refetch()} className="grid size-10 place-items-center rounded-full text-fg-2">
                <RefreshCw className={cn("size-4", remote.isFetching && "animate-spin")} />
              </button>
            </div>
            {/* Như Cài đặt → Điện thoại và thiết bị của máy tính (chủ sách 29-09: khác mạng có dùng được không): app không cần gì
                riêng - mạng riêng ảo cho máy tính một địa chỉ tới được, và điện thoại học địa chỉ ấy mỗi lần liệt kê sách. */}
            {remote.isError && !pinChanged(remote.error) && !unpairedHere && (
              <p className="mt-2 px-1 text-xs leading-snug text-fg-2">
                Ra khỏi nhà: sách đã tải về điện thoại vẫn nghe bình thường. Muốn nghe thẳng hay tải thêm từ máy tính khi ở ngoài,
                cho điện thoại và máy tính vào cùng một mạng riêng ảo (VPN - ví dụ Tailscale, ZeroTier, NetBird, WireGuard), rồi mở mục này
                một lần khi còn ở nhà - điện thoại tự nhớ đường.
              </p>
            )}
            {/* Studio từ xa: điện thoại không sản xuất, nhưng điều khiển được việc sản xuất của máy tính - hỏi máy nào khi ghép nhiều máy tính. */}
            <OpenStudioButton computers={studioComputers} className="mt-3 w-full" />
            <StudioAlertsRow />
            <div className="mt-5 divide-y divide-line">
              {/* Đã thôi ghép: danh sách cũ còn trong bộ đệm mà nút Tải không còn tác dụng - ẩn tới khi ghép lại. */}
              {unpairedHere ? null : remote.data?.books.length ? (
                remote.data.books.map((book) => (
                  <RemoteRow
                    key={book.id}
                    book={book}
                    progress={progress[book.id]}
                    onDownload={() => void EbookLibrary.download({ bookId: book.id }).catch(() => undefined)}
                  />
                ))
              ) : remote.isLoading ? (
                <p className="py-6 text-center text-sm text-fg-2">Đang lấy danh sách sách…</p>
              ) : remote.isError ? null : (
                <EmptyState icon={Download} title="Máy tính chưa có sách nghe được" className="py-8">
                  Sách hiện ở đây ngay khi chương đầu tiên được thu xong trên máy tính.
                </EmptyState>
              )}
            </div>
            <button type="button" onClick={() => setConfirmUnpair(true)} className="mt-6 flex items-center gap-2 text-sm text-fg-2">
              <Unplug className="size-4" /> Ngắt kết nối với máy tính này
            </button>
            <Dialog
              open={confirmUnpair}
              onOpenChange={setConfirmUnpair}
              title={`Ngắt kết nối với ${computerName}?`}
              description="Sách đã tải về vẫn ở điện thoại và nghe được. Muốn tải thêm hay nghe thẳng sách của máy tính này thì ghép lại bằng mã mới."
            >
              <div className="dialog-actions">
                <Button variant="ghost" onClick={() => setConfirmUnpair(false)}>
                  Để nguyên
                </Button>
                <Button
                  variant="danger"
                  onClick={() => {
                    setConfirmUnpair(false);
                    void unpair(true).catch((error) => toastNativeError("Chưa ngắt kết nối được", error));
                  }}
                >
                  Ngắt kết nối
                </Button>
              </div>
            </Dialog>
          </>
        )}
      </div>
      <DeviceNameRow />
      <PeersPanel />
      <SharePanel />
      {storage.data && <StoragePanel storage={storage.data} names={new Map((remote.data?.books ?? []).map((book) => [book.id, book.title]))} />}
    </div>
  );
}
