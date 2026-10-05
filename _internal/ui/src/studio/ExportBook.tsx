import { AlertTriangle, CheckCircle2, FileAudio, FolderArchive, FolderDown, FolderOpen, RefreshCw } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { cn } from "@/shared/cn";
import { coverArtwork } from "@/shared/cover";
import { formatNumber, formatSize } from "@/shared/format";
import { Button, Dialog, Progress, radioGroupKeys, radioTabIndex } from "@/shared/ui";
import { api, type BookSummary } from "./api";
import { pickFolder, useAppInfo, useParts } from "./data";
import { WordTimingsRow } from "./WordTimings";

// Xuất ngay trong Studio (soát UX a6 01-10, H1-H2: người làm sách phải sang Thư viện nghe mới tìm thấy "Xuất", và bản xuất
// lặng lẽ thiếu chương / bỏ qua sửa chưa áp). Hộp nói trước bản xuất sẽ có gì, rồi mới hỏi chỗ lưu.

type Kind = "mp3" | "abook" | "abookproj";
/** Truyện chia nhiều phần bằng "Làm tiếp cuốn này": xuất riêng phần đang xem hay cả bộ. */
type Scope = "part" | "series";
/** Cả bộ ra `.abook`: gộp một file (mặc định), hay mỗi phần một file. */
type Layout = "single" | "perPart";

/** Thẻ nhớ / USB định dạng FAT32 không chứa nổi file lớn hơn 4 GiB. */
const FAT32_LIMIT = 4 * 1024 ** 3;

type PartResult = { part: number; title: string };
type SeriesResult = {
  folder: string;
  parts: PartResult[];
  skipped: PartResult[];
  partsTotal: number;
  files?: number;
  size?: number;
  /** Chỉ có khi cả bộ nằm trong MỘT file. */
  file?: string;
};

const KINDS: { value: Kind; title: string; detail: string; icon: typeof FolderDown }[] = [
  { value: "mp3", title: "Thư mục MP3", detail: "Mỗi chương một file, có tên sách, tên chương, bìa - nghe bằng mọi trình phát.", icon: FolderDown },
  { value: "abook", title: "File .abook", detail: "Cả cuốn trong một file: bìa, chữ đọc theo, nhân vật - mở bằng ABook ở máy khác.", icon: FileAudio },
  {
    value: "abookproj",
    title: "Cả dự án (.abookproj)",
    detail:
      "Sổ dự án, audio đã thu, nguồn chương, nhạc nền - để sao lưu hay làm tiếp ở máy khác. Mở file là có lại dự án trong Studio; điện thoại mở file này cũng nghe được các chương đã xong.",
    icon: FolderArchive,
  },
];

const SAVING: Record<Kind, [string, string, string]> = {
  mp3: ["Chọn nơi lưu bản xuất", "Đang xuất sách…", "Không xuất được"],
  abook: ["Chọn nơi lưu file sách", "Đang đóng gói sách…", "Không xuất được"],
  abookproj: ["Chọn nơi lưu file dự án", "Đang đóng gói dự án…", "Không gói được dự án"],
};

/** Bản xuất đã xong, hiện ngay trong hộp: nói đã lưu ở đâu và cho mở thư mục (trước đây chỉ có một thông báo thoáng qua). */
type Finished = { title: string; detail: string; folder: string };

const revealFolder = (folder: string) => void api("/api/reveal-export", { method: "POST", body: { folder } });

export function ExportDialog({
  book,
  open,
  onOpenChange,
  onApplyFirst,
}: {
  book: BookSummary;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Còn thay đổi chờ áp: đóng hộp này, mở hộp "Áp dụng N thay đổi". */
  onApplyFirst: () => void;
}) {
  const { data: info } = useAppInfo();
  const [kind, setKind] = useState<Kind>("mp3");
  const [busy, setBusy] = useState(false);
  const [scope, setScope] = useState<Scope>("part");
  const [layout, setLayout] = useState<Layout>("single");
  const [finished, setFinished] = useState<Finished | null>(null);
  // Đóng hộp giữa lúc đang đóng gói: việc vẫn chạy, báo bằng thông báo nổi; hộp còn mở lúc xong thì báo ngay trong hộp.
  const openRef = useRef(open);
  openRef.current = open;
  const loadingToast = useRef<string | number | null>(null);
  const parts = useParts(book.id).data?.parts ?? [];
  const missing = book.chapters.missingAudio ?? 0;
  const ready = Math.max(0, book.chapters.completed - missing);
  const total = book.chapters.total;
  const wholeSeries = scope === "series" && parts.length > 1 && kind !== "abookproj";
  const oneFile = kind === "abook" && (!wholeSeries || layout === "single");
  // Cỡ ước lượng của file .abook (audio các chương nghe được): báo trước, và cảnh báo khi vượt giới hạn FAT32.
  const estimate = useQuery({
    queryKey: ["export-size", book.id, wholeSeries],
    enabled: open && kind === "abook",
    queryFn: () => api<{ bytes: number; parts: number; musicPending?: number }>(`/api/books/${book.id}/export-size${wholeSeries ? "?series=1" : ""}`),
    staleTime: 10_000,
  });
  const bytes = estimate.data?.bytes ?? 0;
  const musicPending = estimate.data?.musicPending ?? 0;
  const countText = kind === "abookproj" ? undefined : wholeSeries ? `${parts.length} phần` : `${ready} chương`;
  // Chỗ lưu nói trước khi bấm "Xuất": có hộp chọn thư mục của máy thì người dùng tự chọn, không thì vào thư mục "Đã xuất" của thư viện.
  const root = info?.libraryRoot ?? "";
  const savePlace = info?.dialogs
    ? "Bấm nút bên dưới rồi chọn thư mục để lưu."
    : root
      ? `Sẽ lưu vào thư mục “Đã xuất” trong thư viện: ${root}${root.includes("\\") ? "\\" : "/"}Đã xuất`
      : "Sẽ lưu vào thư mục “Đã xuất” trong thư viện.";
  const handleOpenChange = (next: boolean) => {
    if (!next && busy && loadingToast.current === null) {
      loadingToast.current = toast.loading(SAVING[kind][1], { description: countText });
    }
    if (!next) setFinished(null);
    onOpenChange(next);
  };
  useEffect(() => {
    if (open && loadingToast.current !== null) {
      toast.dismiss(loadingToast.current);
      loadingToast.current = null;
    }
    if (!open) setFinished(null);
  }, [open]);
  const run = async () => {
    let target = "";
    if (info?.dialogs) {
      const picked = await pickFolder(SAVING[kind][0], "").catch(() => null);
      if (!picked) return;
      target = picked;
    }
    setBusy(true);
    setFinished(null);
    try {
      const result =
        kind === "mp3"
          ? await api<{ folder: string; files: number } & Partial<SeriesResult>>(`/api/books/${book.id}/export`, {
              method: "POST",
              body: { target, cover: coverArtwork(book.title), series: wholeSeries },
            })
          : await api<{ folder: string; file: string; size: number; missingSources?: string[] } & Partial<SeriesResult>>(
              `/api/books/${book.id}/${kind === "abook" ? "bookfile" : "projectfile"}`,
              { method: "POST", body: { target, series: wholeSeries, ...(kind === "abook" && wholeSeries ? { single: layout === "single" } : {}) } },
            );
      const lost = "missingSources" in result ? (result.missingSources?.length ?? 0) : 0;
      const skipped = result.skipped?.length ? ` · chưa có chương nào nên bỏ qua: ${result.skipped.map((part) => `Phần ${part.part}`).join(", ")}` : "";
      // `file` chỉ có khi cả bộ (hay một phần) nằm trong MỘT file; cả bộ mỗi phần một file thì có `parts` mà không có `file`.
      const single = "file" in result && typeof result.file === "string";
      const title = result.parts
        ? kind === "mp3"
          ? `Đã xuất ${result.files ?? 0} chương của ${result.parts.length} phần`
          : single
            ? `Đã xuất cả bộ ${result.parts.length} phần trong một file sách`
            : `Đã xuất ${result.parts.length} file sách`
        : kind === "mp3"
          ? `Đã xuất ${"files" in result ? result.files : ready} chương`
          : kind === "abook"
            ? "Đã xuất file sách"
            : "Đã gói dự án";
      const detail =
        (result.parts && kind === "abook" && !single
          ? `${result.folder} · mỗi phần một file .abook riêng`
          : single
            ? `${result.file} · ${formatSize(result.size ?? 0)}`
            : result.folder) +
        skipped +
        (lost ? ` · ${lost} file nguồn chương đã bị dời hay xoá nên không có trong gói` : "");
      const pending = loadingToast.current;
      loadingToast.current = null;
      if (openRef.current) {
        setFinished({ title, detail, folder: result.folder });
      } else {
        toast.success(title, {
          id: pending ?? undefined,
          description: detail,
          action: info?.remote ? undefined : { label: "Mở thư mục", onClick: () => revealFolder(result.folder) },
        });
      }
    } catch (error) {
      const pending = loadingToast.current;
      loadingToast.current = null;
      toast.error(SAVING[kind][2], { id: pending ?? undefined, description: (error as Error).message });
    } finally {
      setBusy(false);
    }
  };
  const whole = kind === "abookproj";
  const warnings = (
    whole
      ? [book.running && "Dự án đang chạy - gói khi nó đã chạy xong hoặc đã dừng."]
      : [
          !wholeSeries && ready < total && `${formatNumber(total - ready)}/${formatNumber(total)} chương chưa có audio${missing ? ` (${missing} chương mất file)` : ""} - không có trong bản xuất.`,
          wholeSeries && "Phần nào chưa có chương xong sẽ bị bỏ qua; phần đang chạy chỉ có các chương đã xong tới lúc này.",
          !wholeSeries && book.running && "Sách đang chạy - bản xuất chỉ gồm các chương đã xong tới lúc này.",
          oneFile &&
            bytes > FAT32_LIMIT &&
            `File này sẽ lớn hơn 4 GB - thẻ nhớ hay USB định dạng FAT32 không chứa nổi.${wholeSeries ? " Chọn “Mỗi phần một file” nếu định chép vào đó." : ""}`,
        ]
  ).filter(Boolean) as string[];
  // Studio từ xa (trình duyệt máy khác) không gói dự án: file nằm ở máy tính, việc của người ngồi trước nó.
  const kinds = info?.remote ? KINDS.filter((item) => item.value !== "abookproj") : KINDS;
  const kindValues = kinds.map((item) => item.value);
  const scopeValues: Scope[] = ["part", "series"];
  const layoutValues: Layout[] = ["single", "perPart"];
  return (
    <Dialog open={open} onOpenChange={handleOpenChange} width="max-w-lg" title={`Xuất “${book.title}”`}
      description={wholeSeries ? `Các chương nghe được của cả ${parts.length} phần sẽ vào bản xuất.` : `${formatNumber(ready)} chương nghe được sẽ vào bản xuất.`}>
      {busy ? (
        <div className="py-2" role="status">
          <Progress value={0} indeterminate size="md" label={SAVING[kind][1]} />
          <p className="mt-3 text-sm font-semibold">{SAVING[kind][1]}</p>
          <p className="mt-1 text-sm text-fg-2 text-pretty">
            {countText ? `${countText}. ` : ""}Sách dài thì có thể mất vài phút. Đóng hộp này cũng được - việc vẫn chạy và báo khi xong.
          </p>
          <div className="mt-5 flex justify-end">
            <Button variant="ghost" onClick={() => handleOpenChange(false)}>
              Đóng, cứ để chạy
            </Button>
          </div>
        </div>
      ) : finished ? (
        <div className="py-2">
          <p className="flex items-center gap-2 text-sm font-semibold">
            <CheckCircle2 className="size-4 shrink-0 text-success" />
            {finished.title}
          </p>
          <p className="mt-2 break-all rounded-xl bg-sunken p-3 text-sm text-fg-2">{finished.detail}</p>
          <div className="mt-5 flex justify-end gap-2">
            {!info?.remote && (
              <Button variant="secondary" icon={FolderOpen} onClick={() => revealFolder(finished.folder)}>
                Mở thư mục
              </Button>
            )}
            <Button variant="primary" onClick={() => handleOpenChange(false)}>
              Xong
            </Button>
          </div>
        </div>
      ) : (
      <>
      {parts.length > 1 && !whole && (
        <div
          className="mb-3 grid grid-cols-2 gap-1 rounded-xl bg-sunken p-1 text-sm"
          role="radiogroup"
          aria-label="Phạm vi bản xuất"
          onKeyDown={radioGroupKeys(scopeValues, scope, setScope)}
        >
          {(
            [
              ["part", "Phần này"],
              ["series", `Cả bộ (${parts.length} phần)`],
            ] as const
          ).map(([value, label], index) => (
            <button
              key={value}
              type="button"
              role="radio"
              aria-checked={scope === value}
              tabIndex={radioTabIndex(scopeValues, scope, index)}
              onClick={() => setScope(value)}
              className={cn("rounded-lg px-3 py-1.5 font-medium", scope === value ? "bg-panel shadow-sm" : "text-fg-2")}
            >
              {label}
            </button>
          ))}
        </div>
      )}
      <div className="grid gap-2" role="radiogroup" aria-label="Kiểu bản xuất" onKeyDown={radioGroupKeys(kindValues, kind, setKind)}>
        {kinds.map(({ value, title, detail, icon: Icon }, index) => (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={kind === value}
            tabIndex={radioTabIndex(kindValues, kind, index)}
            onClick={() => setKind(value)}
            className={cn(
              "flex items-start gap-3 rounded-xl border p-3 text-left text-sm",
              kind === value ? "border-accent bg-accent-soft" : "border-line hover:bg-hover",
            )}
          >
            <Icon className="mt-0.5 size-4 shrink-0 text-accent-text" />
            <span className="min-w-0">
              <span className="block font-semibold">{title}</span>
              <span className="block text-fg-2">{detail}</span>
            </span>
          </button>
        ))}
      </div>
      {wholeSeries && kind === "abook" && (
        <>
          <div
            className="mt-3 grid grid-cols-2 gap-1 rounded-xl bg-sunken p-1 text-sm"
            role="radiogroup"
            aria-label="Cách chia file"
            onKeyDown={radioGroupKeys(layoutValues, layout, setLayout)}
          >
            {(
              [
                ["single", "Một file"],
                ["perPart", "Mỗi phần một file"],
              ] as const
            ).map(([value, label], index) => (
              <button
                key={value}
                type="button"
                role="radio"
                aria-checked={layout === value}
                tabIndex={radioTabIndex(layoutValues, layout, index)}
                onClick={() => setLayout(value)}
                className={cn("rounded-lg px-3 py-1.5 font-medium", layout === value ? "bg-panel shadow-sm" : "text-fg-2")}
              >
                {label}
              </button>
            ))}
          </div>
          <p className="mt-2 text-sm text-fg-2 text-pretty">
            {layout === "single"
              ? "Cả bộ trong một file .abook: nghe liền từ phần này sang phần khác, chỉ cần chép một file sang máy khác."
              : "Mỗi phần là một file .abook riêng, cùng nằm trong một thư mục của bộ."}
          </p>
        </>
      )}
      <p className="mt-3 text-sm text-fg-2 text-pretty">{savePlace}</p>
      {kind === "abook" && bytes > 0 && (
        <p className="mt-2 text-sm text-fg-2">
          Cỡ ước tính: khoảng {formatSize(bytes)}.
          {musicPending > 0 && ` Còn ${musicPending} bài nhạc nền chưa tải về máy - khi xuất sẽ tải và cộng thêm.`}
        </p>
      )}
      {kind === "abook" && !info?.remote && <WordTimingsRow bookId={book.id} running={Boolean(book.running)} />}
      {wholeSeries && kind === "mp3" && (
        <p className="mt-3 text-sm text-fg-2 text-pretty">Mỗi phần một thư mục con (“Phần 1 - …”, “Phần 2 - …”), cùng nằm trong một thư mục của bộ.</p>
      )}
      {(warnings.length > 0 || (!whole && Boolean(book.pendingChanges))) && (
        <div className="mt-3 space-y-1.5 rounded-xl bg-warning-soft p-3 text-sm">
          {warnings.map((line) => (
            <p key={line} className="flex items-start gap-2">
              <AlertTriangle className="mt-0.5 size-4 shrink-0 text-warning" />
              <span className="text-pretty">{line}</span>
            </p>
          ))}
          {!whole && Boolean(book.pendingChanges) && (
            <div className="flex flex-wrap items-center gap-x-2 gap-y-1.5">
              <AlertTriangle className="size-4 shrink-0 text-warning" />
              <span className="min-w-0 flex-1 text-pretty">
                Còn {book.pendingChanges} thay đổi chưa áp - bản xuất đọc như TRƯỚC khi sửa.
              </span>
              <Button size="sm" variant="secondary" icon={RefreshCw} onClick={() => { onOpenChange(false); onApplyFirst(); }}>
                Áp dụng trước
              </Button>
            </div>
          )}
        </div>
      )}
      <div className="mt-5 flex justify-end gap-2">
        <Button variant="ghost" onClick={() => handleOpenChange(false)}>
          Thôi
        </Button>
        <Button
          variant="primary"
          icon={KINDS.find((item) => item.value === kind)?.icon ?? FolderDown}
          loading={busy}
          disabled={whole ? Boolean(book.running) : !wholeSeries && !ready}
          onClick={() => void run()}
        >
          {info?.dialogs ? "Chọn nơi lưu và xuất" : "Xuất"}
        </Button>
      </div>
      </>
      )}
    </Dialog>
  );
}
