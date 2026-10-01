import { AlertTriangle, FileAudio, FolderDown, RefreshCw } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { cn } from "@/shared/cn";
import { coverArtwork } from "@/shared/cover";
import { formatNumber } from "@/shared/format";
import { Button, Dialog } from "@/shared/ui";
import { api, type BookSummary } from "./api";
import { pickFolder, useAppInfo } from "./data";

// Xuất ngay trong Studio (soát UX a6 01-10, H1-H2: người làm sách phải sang Thư viện nghe mới tìm thấy "Xuất", và bản xuất
// lặng lẽ thiếu chương / bỏ qua sửa chưa áp). Hộp nói trước bản xuất sẽ có gì, rồi mới hỏi chỗ lưu.

type Kind = "mp3" | "abook";

const KINDS: { value: Kind; title: string; detail: string; icon: typeof FolderDown }[] = [
  { value: "mp3", title: "Thư mục MP3", detail: "Mỗi chương một file, có tên sách, tên chương, bìa - nghe bằng mọi trình phát.", icon: FolderDown },
  { value: "abook", title: "File .abook", detail: "Cả cuốn trong một file: bìa, chữ đọc theo, nhân vật - mở bằng ABook ở máy khác.", icon: FileAudio },
];

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
  const missing = book.chapters.missingAudio ?? 0;
  const ready = Math.max(0, book.chapters.completed - missing);
  const total = book.chapters.total;
  const run = async () => {
    let target = "";
    if (info?.dialogs) {
      const picked = await pickFolder(kind === "mp3" ? "Chọn nơi lưu bản xuất" : "Chọn nơi lưu file sách", "").catch(() => null);
      if (!picked) return;
      target = picked;
    }
    setBusy(true);
    const pending = toast.loading(kind === "mp3" ? "Đang xuất sách…" : "Đang đóng gói sách…", { description: `${ready} chương` });
    try {
      const result =
        kind === "mp3"
          ? await api<{ folder: string; files: number }>(`/api/books/${book.id}/export`, {
              method: "POST",
              body: { target, cover: coverArtwork(book.title) },
            })
          : await api<{ folder: string; file: string; size: number }>(`/api/books/${book.id}/bookfile`, { method: "POST", body: { target } });
      toast.success(kind === "mp3" ? `Đã xuất ${"files" in result ? result.files : ready} chương` : "Đã xuất file sách", {
        id: pending,
        description: "file" in result ? `${result.file} · ${Math.round(result.size / 1048576)} MB` : result.folder,
        action: info?.remote
          ? undefined
          : { label: "Mở thư mục", onClick: () => void api("/api/reveal-export", { method: "POST", body: { folder: result.folder } }) },
      });
      onOpenChange(false);
    } catch (error) {
      toast.error("Không xuất được", { id: pending, description: (error as Error).message });
    } finally {
      setBusy(false);
    }
  };
  const warnings = [
    ready < total && `${formatNumber(total - ready)}/${formatNumber(total)} chương chưa có audio${missing ? ` (${missing} chương mất file)` : ""} - không có trong bản xuất.`,
    book.running && "Sách đang chạy - bản xuất chỉ gồm các chương đã xong tới lúc này.",
  ].filter(Boolean) as string[];
  return (
    <Dialog open={open} onOpenChange={onOpenChange} width="max-w-lg" title={`Xuất “${book.title}”`}
      description={`${formatNumber(ready)} chương nghe được sẽ vào bản xuất.`}>
      <div className="grid gap-2" role="radiogroup" aria-label="Kiểu bản xuất">
        {KINDS.map(({ value, title, detail, icon: Icon }) => (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={kind === value}
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
      {(warnings.length > 0 || Boolean(book.pendingChanges)) && (
        <div className="mt-3 space-y-1.5 rounded-xl bg-warning-soft p-3 text-sm">
          {warnings.map((line) => (
            <p key={line} className="flex items-start gap-2">
              <AlertTriangle className="mt-0.5 size-4 shrink-0 text-warning" />
              <span className="text-pretty">{line}</span>
            </p>
          ))}
          {Boolean(book.pendingChanges) && (
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
        <Button variant="primary" icon={kind === "mp3" ? FolderDown : FileAudio} loading={busy} disabled={!ready} onClick={() => void run()}>
          {info?.dialogs ? "Chọn nơi lưu và xuất" : "Xuất"}
        </Button>
      </div>
    </Dialog>
  );
}
