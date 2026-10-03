import { useQueryClient } from "@tanstack/react-query";
import { BookOpen, BookPlus, Copy, FileText, Folder, Loader2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router";
import { toast } from "sonner";
import { ChapterPreview } from "@/shared/ChapterPreview";
import { formatNumber } from "@/shared/format";
import { Button, Dialog } from "@/shared/ui";
import { groupSuggestions, setSkipLine, SuggestionChoices } from "./ReadingSuggestions";
import { useSource } from "./source";
import type { ImportChoice, ImportKind, ImportPreview } from "./textImport";

// "Thêm sách từ file…": EPUB / DOCX / PDF / thư mục TXT thành sách chỉ-có-chữ trong thư viện (docs/LISTEN_ANYTHING.md mục 1 và 2).
// Ba bước trong một hộp: chọn → xem danh sách chương (và gợi ý của máy) → thêm. Máy tính và điện thoại dùng chung; chỗ khác nhau
// (bộ chọn, ai đọc file) nằm ở `source.textImport`.

function cleanPath(value: string): string {
  return value.trim().replace(/^["']+|["']+$/g, "").trim();
}

/** Nút mở hộp "Thêm sách từ file…"; không hiện khi nguồn này không nhập được (`source.textImport` trống). */
export function AddBookButton({ variant = "secondary" }: { variant?: "secondary" | "ghost" | "primary" }) {
  const source = useSource();
  const [open, setOpen] = useState(false);
  if (!source.textImport) return null;
  return (
    <>
      <Button variant={variant} icon={BookPlus} onClick={() => setOpen(true)}>
        Thêm sách từ file…
      </Button>
      <AddBookDialog open={open} onOpenChange={setOpen} />
    </>
  );
}

export function AddBookDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const source = useSource();
  const importer = source.textImport;
  const client = useQueryClient();
  const navigate = useNavigate();
  const [choice, setChoice] = useState<ImportChoice | null>(null);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [title, setTitle] = useState("");
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState<"reading" | "adding" | null>(null);
  const [problem, setProblem] = useState("");
  // Gợi ý dòng ghi công người nghe chọn bỏ khỏi phần đọc (theo dòng); mặc định không bỏ dòng nào.
  const [skipped, setSkipped] = useState<ReadonlySet<string>>(new Set());
  const titleField = useRef<HTMLInputElement>(null);
  // Đọc xong file: con trỏ sang ô "Tên sách" (lúc mở hộp, `data-autofocus` của ô đường dẫn nhận con trỏ).
  useEffect(() => {
    if (!preview) return;
    titleField.current?.focus();
    titleField.current?.select();
  }, [preview]);
  if (!importer) return null;

  const clear = () => {
    setChoice(null);
    setPreview(null);
    setTitle("");
    setTyped("");
    setProblem("");
    setSkipped(new Set());
  };
  const reset = () => {
    if (choice) void importer.discard?.(choice).catch(() => undefined);
    clear();
  };
  const close = (next: boolean) => {
    if (busy === "adding") return;
    if (!next) reset();
    onOpenChange(next);
  };
  const read = async (picked: ImportChoice) => {
    setChoice(picked);
    setProblem("");
    setBusy("reading");
    try {
      const result = await importer.preview(picked);
      setPreview(result);
      setTitle(result.title);
    } catch (error) {
      setProblem((error as Error).message);
      void importer.discard?.(picked).catch(() => undefined);
      setChoice(null);
    } finally {
      setBusy(null);
    }
  };
  const choose = async (kind: ImportKind) => {
    if (!importer.choose) return;
    try {
      const picked = await importer.choose(kind);
      if (picked) await read(picked);
    } catch (error) {
      setProblem((error as Error).message);
    }
  };
  const openExisting = (id: string) => {
    reset();
    onOpenChange(false);
    navigate(`/book/${id}`);
  };
  const add = async (separate = false) => {
    if (!choice || !preview) return;
    setBusy("adding");
    try {
      const added = await importer.add(choice, title.trim(), separate);
      // Gợi ý người nghe đã chọn: bỏ dòng ấy khỏi phần đọc của cuốn mới (chữ trong sách không đổi). Hỏng thì sách vẫn đã vào thư
      // viện - gợi ý còn chờ ở trang sách.
      if (added.how === "new") {
        for (const group of groupSuggestions(preview.suggestions ?? []).filter((group) => skipped.has(group.line))) {
          await setSkipLine(added.id, group.line, group.chapters, true).catch(() => undefined);
        }
      }
      void client.invalidateQueries({ queryKey: ["listen"] });
      void client.invalidateQueries({ queryKey: ["storage"] });
      toast.success(added.how === "existing" ? "Cuốn này đã có trong thư viện" : "Đã thêm sách vào thư viện", {
        description: added.how === "existing" ? undefined : "Mới có chữ để đọc - chưa có âm thanh.",
      });
      clear(); // bản tạm đã dùng xong (native tự dọn)
      onOpenChange(false);
      navigate(`/book/${added.id}`);
    } catch (error) {
      toast.error("Chưa thêm được sách", { description: (error as Error).message });
    } finally {
      setBusy(null);
    }
  };

  // Ghi chú đổi định dạng; gợi ý dòng ghi công (luôn ở cuối `notes`, mỗi gợi ý một ghi chú) đã thành các ô chọn ở dưới.
  const notes = preview ? preview.notes.slice(0, preview.notes.length - (preview.suggestions?.length ?? 0)) : [];
  const groups = groupSuggestions(preview?.suggestions ?? []);

  return (
    <Dialog
      open={open}
      onOpenChange={close}
      width="max-w-2xl"
      title="Thêm sách từ file"
      description={
        preview
          ? "Xem danh sách chương trước khi thêm. Chữ của truyện được giữ nguyên - ABook chỉ đổi định dạng."
          : "EPUB, Word (DOCX), PDF có chữ, hay một thư mục mà mỗi file TXT là một chương. Sách vào Thư viện để đọc ngay."
      }
    >
      {!preview ? (
        <div>
          <div className="flex flex-wrap gap-2">
            {importer.choose && (
              <>
                <Button variant="primary" icon={busy === "reading" ? Loader2 : FileText} disabled={busy !== null} onClick={() => void choose("file")}>
                  {busy === "reading" ? "Đang đọc…" : "Chọn file sách"}
                </Button>
                <Button icon={Folder} disabled={busy !== null} onClick={() => void choose("folder")}>
                  Chọn thư mục TXT
                </Button>
              </>
            )}
          </div>
          {importer.typedPath && (
            <form
              className="mt-4 flex gap-2"
              onSubmit={(event) => {
                event.preventDefault();
                const path = cleanPath(typed);
                if (path) void read({ ref: path, name: path });
              }}
            >
              <input
                value={typed}
                data-autofocus
                onChange={(event) => setTyped(event.target.value)}
                aria-label="Đường dẫn file hay thư mục"
                placeholder={importer.choose ? "…hoặc dán đường dẫn file hay thư mục" : "Dán đường dẫn file sách hay thư mục TXT, ví dụ D:\\Truyện\\Tên truyện.epub"}
                className="h-10 flex-1 rounded-lg border border-line bg-bg px-3 text-sm outline-none placeholder:text-fg-3 focus:border-accent"
              />
              <Button type="submit" disabled={!cleanPath(typed) || busy !== null} loading={busy === "reading" && !importer.choose}>
                Mở
              </Button>
            </form>
          )}
          {problem && (
            <p role="alert" className="mt-3 text-sm text-danger">
              {problem}
            </p>
          )}
          <p className="mt-4 text-xs text-fg-3">PDF phải có chữ - PDF chụp từ máy quét thì ABook chưa đọc được.</p>
        </div>
      ) : (
        <div>
          <label className="block">
            <span className="text-sm font-medium">Tên sách</span>
            <input
              ref={titleField}
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              aria-invalid={!title.trim()}
              className="mt-1.5 h-11 w-full rounded-xl border border-line bg-bg px-3.5 text-[15px] font-medium outline-none focus:border-accent"
              placeholder="Tên hiển thị trong thư viện"
            />
          </label>
          {preview.author && <p className="mt-1.5 text-sm text-fg-2">Tác giả: {preview.author}</p>}
          <div className="tabular mt-4 text-sm text-fg-2">
            <span className="font-semibold text-fg">{preview.totals.chapters} chương</span> · {formatNumber(preview.totals.words)} chữ
          </div>
          {/* Tên chương đúng như sẽ lưu (trang sách, trình phát, màn đọc cùng thấy tên này); dòng đầu của chương ở dòng phụ. Một
              thước đo cho mỗi chương: số chữ. */}
          <ChapterPreview chapters={preview.chapters.map((chapter) => ({ ...chapter, chars: 0 }))} titleFirst className="mt-2" />
          {notes.length > 0 && (
            <div className="mt-3 rounded-xl border border-line bg-hover p-3 text-xs text-fg-2">
              <p className="font-medium text-fg">Máy đã đổi định dạng - chữ của truyện giữ nguyên</p>
              <ul className="mt-1 space-y-1">
                {notes.slice(0, 6).map((note) => (
                  <li key={note}>{note}</li>
                ))}
              </ul>
              {notes.length > 6 && <p className="mt-1">…và {notes.length - 6} ghi chú nữa.</p>}
            </div>
          )}
          {groups.length > 0 && (
            <div className="mt-3 rounded-xl border border-line bg-hover p-3">
              <p className="text-xs font-medium">Gợi ý cho phần đọc - ABook không tự sửa chữ của truyện</p>
              <p className="mt-0.5 text-xs text-fg-2">Bỏ một dòng chỉ là màn đọc và giọng đọc bỏ qua nó; đổi ý được ở trang sách.</p>
              <div className="mt-2 max-h-40 overflow-y-auto">
                <SuggestionChoices
                  groups={groups}
                  isOn={(group) => skipped.has(group.line)}
                  disabled={busy !== null}
                  onChange={(group, on) =>
                    setSkipped((current) => {
                      const next = new Set(current);
                      if (on) next.add(group.line);
                      else next.delete(group.line);
                      return next;
                    })
                  }
                />
              </div>
            </div>
          )}
          {preview.existing && (
            <p role="status" className="mt-3 rounded-xl border border-line bg-accent-soft p-3 text-sm text-accent-text">
              Cuốn này đã có trong thư viện: “{preview.existing.title}”.
            </p>
          )}
          <div className="mt-5 flex flex-wrap justify-end gap-2">
            <Button variant="ghost" disabled={busy !== null} onClick={reset}>
              Chọn lại
            </Button>
            {preview.existing ? (
              <>
                <Button icon={Copy} loading={busy === "adding"} disabled={!title.trim() || busy !== null} onClick={() => void add(true)}>
                  Thêm bản riêng
                </Button>
                <Button variant="primary" icon={BookOpen} disabled={busy !== null} onClick={() => openExisting(preview.existing!.id)}>
                  Mở cuốn đó
                </Button>
              </>
            ) : (
              <Button variant="primary" icon={BookPlus} loading={busy === "adding"} disabled={!title.trim()} onClick={() => void add()}>
                Thêm vào thư viện
              </Button>
            )}
          </div>
        </div>
      )}
    </Dialog>
  );
}
