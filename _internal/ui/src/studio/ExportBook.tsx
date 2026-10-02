import { AlertTriangle, FileAudio, FolderArchive, FolderDown, RefreshCw } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { cn } from "@/shared/cn";
import { coverArtwork } from "@/shared/cover";
import { formatNumber } from "@/shared/format";
import { Button, Dialog, radioGroupKeys, radioTabIndex } from "@/shared/ui";
import { api, type BookSummary } from "./api";
import { pickFolder, useAppInfo, useParts } from "./data";

// Xuất ngay trong Studio (soát UX a6 01-10, H1-H2: người làm sách phải sang Thư viện nghe mới tìm thấy "Xuất", và bản xuất
// lặng lẽ thiếu chương / bỏ qua sửa chưa áp). Hộp nói trước bản xuất sẽ có gì, rồi mới hỏi chỗ lưu.

type Kind = "mp3" | "abook" | "abookproj";
/** Truyện chia nhiều phần bằng "Làm tiếp cuốn này": xuất riêng phần đang xem hay cả bộ. */
type Scope = "part" | "series";

type PartResult = { part: number; title: string };
type SeriesResult = { folder: string; parts: PartResult[]; skipped: PartResult[]; partsTotal: number; files?: number; size?: number };

const KINDS: { value: Kind; title: string; detail: string; icon: typeof FolderDown }[] = [
  { value: "mp3", title: "Thư mục MP3", detail: "Mỗi chương một file, có tên sách, tên chương, bìa - nghe bằng mọi trình phát.", icon: FolderDown },
  { value: "abook", title: "File .abook", detail: "Cả cuốn trong một file: bìa, chữ đọc theo, nhân vật - mở bằng ABook ở máy khác.", icon: FileAudio },
  {
    value: "abookproj",
    title: "Cả dự án (.abookproj)",
    detail: "Sổ dự án, audio đã thu, nguồn chương - để sao lưu hay làm tiếp ở máy khác. Mở file là có lại dự án trong Studio.",
    icon: FolderArchive,
  },
];

const SAVING: Record<Kind, [string, string, string]> = {
  mp3: ["Chọn nơi lưu bản xuất", "Đang xuất sách…", "Không xuất được"],
  abook: ["Chọn nơi lưu file sách", "Đang đóng gói sách…", "Không xuất được"],
  abookproj: ["Chọn nơi lưu file dự án", "Đang đóng gói dự án…", "Không gói được dự án"],
};

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
  const parts = useParts(book.id).data?.parts ?? [];
  const missing = book.chapters.missingAudio ?? 0;
  const ready = Math.max(0, book.chapters.completed - missing);
  const total = book.chapters.total;
  const run = async () => {
    let target = "";
    if (info?.dialogs) {
      const picked = await pickFolder(SAVING[kind][0], "").catch(() => null);
      if (!picked) return;
      target = picked;
    }
    setBusy(true);
    const pending = toast.loading(SAVING[kind][1], {
      description: kind === "abookproj" ? undefined : wholeSeries ? `${parts.length} phần` : `${ready} chương`,
    });
    try {
      const result =
        kind === "mp3"
          ? await api<{ folder: string; files: number } & Partial<SeriesResult>>(`/api/books/${book.id}/export`, {
              method: "POST",
              body: { target, cover: coverArtwork(book.title), series: wholeSeries },
            })
          : await api<{ folder: string; file: string; size: number; missingSources?: string[] } & Partial<SeriesResult>>(
              `/api/books/${book.id}/${kind === "abook" ? "bookfile" : "projectfile"}`,
              { method: "POST", body: { target, series: wholeSeries } },
            );
      const lost = "missingSources" in result ? (result.missingSources?.length ?? 0) : 0;
      const skipped = result.skipped?.length ? ` · chưa có chương nào nên bỏ qua: ${result.skipped.map((part) => `Phần ${part.part}`).join(", ")}` : "";
      const title = result.parts
        ? kind === "mp3"
          ? `Đã xuất ${result.files ?? 0} chương của ${result.parts.length} phần`
          : `Đã xuất ${result.parts.length} file sách`
        : kind === "mp3"
          ? `Đã xuất ${"files" in result ? result.files : ready} chương`
          : kind === "abook"
            ? "Đã xuất file sách"
            : "Đã gói dự án";
      toast.success(title, {
        id: pending,
        description:
          (result.parts && kind === "abook"
            ? `${result.folder} · mỗi phần một file .abook riêng`
            : "file" in result
              ? `${result.file} · ${Math.round(result.size / 1048576)} MB`
              : result.folder) +
          skipped +
          (lost ? ` · ${lost} file nguồn chương đã bị dời hay xoá nên không có trong gói` : ""),
        action: info?.remote
          ? undefined
          : { label: "Mở thư mục", onClick: () => void api("/api/reveal-export", { method: "POST", body: { folder: result.folder } }) },
      });
      onOpenChange(false);
    } catch (error) {
      toast.error(SAVING[kind][2], { id: pending, description: (error as Error).message });
    } finally {
      setBusy(false);
    }
  };
  const whole = kind === "abookproj";
  // Cả bộ chỉ nói được về MỌI phần chung chung: số chương xong của phần khác không nằm trong tóm tắt của sách này.
  const wholeSeries = scope === "series" && parts.length > 1 && !whole;
  const warnings = (
    whole
      ? [book.running && "Dự án đang chạy - gói khi nó đã chạy xong hoặc đã dừng."]
      : [
          !wholeSeries && ready < total && `${formatNumber(total - ready)}/${formatNumber(total)} chương chưa có audio${missing ? ` (${missing} chương mất file)` : ""} - không có trong bản xuất.`,
          wholeSeries && "Phần nào chưa có chương xong sẽ bị bỏ qua; phần đang chạy chỉ có các chương đã xong tới lúc này.",
          !wholeSeries && book.running && "Sách đang chạy - bản xuất chỉ gồm các chương đã xong tới lúc này.",
        ]
  ).filter(Boolean) as string[];
  // Studio từ xa (trình duyệt máy khác) không gói dự án: file nằm ở máy tính, việc của người ngồi trước nó.
  const kinds = info?.remote ? KINDS.filter((item) => item.value !== "abookproj") : KINDS;
  const kindValues = kinds.map((item) => item.value);
  const scopeValues: Scope[] = ["part", "series"];
  return (
    <Dialog open={open} onOpenChange={onOpenChange} width="max-w-lg" title={`Xuất “${book.title}”`}
      description={wholeSeries ? `Các chương nghe được của cả ${parts.length} phần sẽ vào bản xuất.` : `${formatNumber(ready)} chương nghe được sẽ vào bản xuất.`}>
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
        <p className="mt-3 text-sm text-fg-2 text-pretty">Mỗi phần là một file .abook riêng, cùng nằm trong một thư mục của bộ.</p>
      )}
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
        <Button variant="ghost" onClick={() => onOpenChange(false)}>
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
    </Dialog>
  );
}
