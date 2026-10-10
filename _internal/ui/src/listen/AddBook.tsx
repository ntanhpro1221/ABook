import { useQueryClient } from "@tanstack/react-query";
import { BookOpen, BookPlus, Check, CircleAlert, Copy, FileText, Folder, Loader2, Minus } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { useNavigate } from "react-router";
import { toast } from "sonner";
import { ChapterPreview } from "@/shared/ChapterPreview";
import { cn } from "@/shared/cn";
import { formatNumber } from "@/shared/format";
import { Button, Dialog } from "@/shared/ui";
import {
  addRest,
  advanceQueue,
  planPick,
  queueFocus,
  queueLabel,
  settle,
  summarize,
  summaryText,
  waitingAfter,
  type QueueItem,
} from "./importQueue";
import { groupSuggestions, setSkipLine, SuggestionChoices } from "./ReadingSuggestions";
import { useSource } from "./source";
import {
  chapterPicks,
  defaultPicked,
  isBookFile,
  isDefaultPick,
  pickedSuggestions,
  pickedTotals,
  readPreview,
  renameChapter,
  splitLabel,
  type ChapterNames,
  type AddedBook,
  type ImportChoice,
  type ImportKind,
  type ImportPreview,
  type PickedItem,
} from "./textImport";

// "Thêm sách từ file…": EPUB / DOCX / PDF / thư mục TXT thành sách chỉ-có-chữ trong thư viện (docs/LISTEN_ANYTHING.md mục 1 và 2).
// Ba bước trong một hộp: chọn → xem danh sách chương (và gợi ý của máy) → thêm. Máy tính và điện thoại dùng chung; chỗ khác nhau
// (bộ chọn, ai đọc file) nằm ở `source.textImport`.

/** Dòng dưới toast "Đã thêm sách": sách chỉ có chữ đọc được ngay, nghe bằng giọng đọc - không nói "chưa có âm thanh" (nghe như không nghe được). */
const READY_NOTE = "Đọc được ngay; bấm Nghe ngay để nghe.";

function cleanPath(value: string): string {
  return value.trim().replace(/^["']+|["']+$/g, "").trim();
}

export { isBookFile };

/** Nút mở hộp "Thêm sách từ file…"; không hiện khi nguồn này không nhập được (`source.textImport` trống). */
export function AddBookButton({
  variant = "secondary",
  size,
  onBookFile,
}: {
  variant?: "secondary" | "ghost" | "primary";
  size?: "sm" | "md" | "lg";
  /** Chọn hay dán một file .abook / .abookproj: mở nó (máy có đường mở file sách) thay vì báo "chưa đọc được". */
  onBookFile?: (path: string) => Promise<void | boolean>;
}) {
  const source = useSource();
  const [open, setOpen] = useState(false);
  if (!source.textImport) return null;
  return (
    <>
      <Button variant={variant} size={size} icon={BookPlus} className="touch-row" onClick={() => setOpen(true)}>
        Thêm sách từ file…
      </Button>
      <AddBookDialog open={open} onOpenChange={setOpen} onBookFile={onBookFile} />
    </>
  );
}

export function AddBookDialog({
  open,
  onOpenChange,
  onBookFile,
  initial,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onBookFile?: (path: string) => Promise<void | boolean>;
  /** Thứ đã chọn sẵn (điện thoại: file app khác gửi tới - android/imports.ts; máy tính: file kéo thả vào thư viện - DropToAdd.tsx): hộp mở thẳng ở bước
   *  đọc file / xem trước. Nhiều file thì thành hàng xem trước. */
  initial?: ImportChoice | PickedItem[] | null;
}) {
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
  // Chọn / kéo thả nhiều file: hàng xem trước (importQueue.ts), mỗi cuốn qua đúng bước xem trước của một file. `null` = một file như trước. `queueRef` giữ
  // bản mới nhất cho các vòng async ("Thêm tất cả phần còn lại" đi qua nhiều cuốn trong một lần bấm).
  const [queue, setQueueState] = useState<QueueItem[] | null>(null);
  const queueRef = useRef<QueueItem[] | null>(null);
  const [currentId, setCurrentId] = useState<number | null>(null);
  const [working, setWorking] = useState("");
  // Hộp hỏi trong hộp thoại khi hàng còn sách chưa thêm: "close" = Esc / bấm ra ngoài, "again" = nút "Chọn lại" (cả hai bỏ cả hàng).
  const [confirmLeave, setConfirmLeave] = useState<"close" | "again" | null>(null);
  const setQueue = (next: QueueItem[] | null) => {
    queueRef.current = next;
    setQueueState(next);
  };
  // Gợi ý dòng ghi công người nghe chọn bỏ khỏi phần đọc (theo dòng); mặc định không bỏ dòng nào.
  const [skipped, setSkipped] = useState<ReadonlySet<string>>(new Set());
  // File TXT cả truyện: "Tách theo N dòng “Chương N”" - tích sẵn khi máy chắc (`splitIsSure`: từ 3 dòng), không thì chỉ đề xuất; bỏ tích được,
  // file của người dùng không bị sửa.
  const [split, setSplit] = useState(false);
  // Chương nào vào sách (số thứ tự hàng của bước xem trước) và tên người dùng đã đổi. Mặc định như máy đề xuất: mọi chương trừ mục rất ngắn.
  const [picked, setPicked] = useState<ReadonlySet<number>>(new Set());
  const [names, setNames] = useState<ChapterNames>({});
  const titleField = useRef<HTMLInputElement>(null);
  const lastKind = useRef<ImportKind>("file");
  // Đọc xong file: con trỏ sang ô "Tên sách" (lúc mở hộp, `data-autofocus` của ô đường dẫn nhận con trỏ). Màn cảm ứng thì KHÔNG: bàn phím
  // ảo bật lên che mất nút "Thêm vào thư viện", mà tên đã điền sẵn và hiếm khi cần sửa (soát máy thật 03-10).
  const hasPreview = preview !== null; // tích / bỏ tích tách chương đọc lại bản xem trước: con trỏ không nhảy về ô tên
  useEffect(() => {
    if (!hasPreview || window.matchMedia?.("(pointer: coarse)").matches) return;
    titleField.current?.focus();
    titleField.current?.select();
  }, [hasPreview]);
  // Đọc thứ chọn sẵn đúng một lần (`read` dựng ở dưới, sau chỗ trả sớm khi nguồn không nhập được).
  const readInitial = useRef<((picked: ImportChoice | PickedItem[]) => Promise<void>) | null>(null);
  const initialRead = useRef<ImportChoice | PickedItem[] | null>(null);
  useEffect(() => {
    if (!open || !initial || initialRead.current === initial) return;
    initialRead.current = initial;
    void readInitial.current?.(initial);
  }, [open, initial]);
  if (!importer) return null;

  const clearPreview = () => {
    setChoice(null);
    setPreview(null);
    setTitle("");
    setSkipped(new Set());
    setSplit(false);
    setPicked(new Set());
    setNames({});
  };
  const clear = () => {
    clearPreview();
    setTyped("");
    setProblem("");
    setQueue(null);
    setCurrentId(null);
    setWorking("");
    setConfirmLeave(null);
  };
  const reset = () => {
    // Hàng: bản tạm của mọi cuốn chưa xong được bỏ (cuốn đang xem cũng nằm trong đó); một file thì như trước.
    const waiting = queueRef.current?.filter((item) => item.state === "waiting" && item.choice) ?? [];
    if (queueRef.current) for (const item of waiting) void importer.discard?.(item.choice!).catch(() => undefined);
    else if (choice) void importer.discard?.(choice).catch(() => undefined);
    clear();
  };
  // Esc / bấm ra ngoài khi hàng còn sách chưa thêm: hỏi ngay trong hộp, không bỏ cả hàng im lặng (soát UX a10).
  const unfinished = queue?.filter((item) => item.state === "waiting" && item.choice && !isBookFile(item.choice.ref)).length ?? 0;
  const close = (next: boolean) => {
    if (busy === "adding") return;
    if (!next && unfinished > 1) {
      setConfirmLeave((asked) => (asked === "close" ? null : "close")); // lần Esc thứ hai là "Quay lại"
      return;
    }
    if (!next) reset();
    onOpenChange(next);
  };
  // Đọc file thành bản xem trước: cả truyện trong một file mà máy chắc là nhiều chương thì mở sẵn với "tách" đã tích (bỏ tích được, danh sách
  // chương đổi theo).
  const loadPreview = async (picked: ImportChoice) => {
    setChoice(picked);
    const { preview: result, split: sure } = await readPreview(importer, picked);
    setPreview(result);
    setPicked(defaultPicked(result.chapters));
    setTitle(result.title);
    setSplit(sure);
  };
  const read = async (picked: ImportChoice) => {
    if (onBookFile && isBookFile(picked.ref)) {
      // Soát UX 05-10: dán đường dẫn .abook vào đây từng báo "Chưa đọc được file .abook" mà không chỉ sang "Mở file sách".
      setProblem("");
      setBusy("reading");
      try {
        await onBookFile(picked.ref);
        clear();
        onOpenChange(false);
      } catch (error) {
        setProblem((error as Error).message);
      } finally {
        setBusy(null);
      }
      return;
    }
    setProblem("");
    setBusy("reading");
    try {
      await loadPreview(picked);
    } catch (error) {
      setProblem((error as Error).message);
      void importer.discard?.(picked).catch(() => undefined);
      setChoice(null);
    } finally {
      setBusy(null);
    }
  };
  // ---- Hàng nhiều file (importQueue.ts) -------------------------------------------------------------------------------------
  // File sách .abook / .abookproj còn lại (đã xếp cuối hàng) mở như "Mở file sách". Mở xong app sang trang sách, nên đây là việc cuối cùng.
  const openBookFiles = async (items: QueueItem[]) => {
    let next = items;
    for (const item of items) {
      if (item.state !== "waiting" || !item.choice) continue;
      if (!onBookFile) {
        next = settle(next, item.id, { state: "error", note: "Ở đây chưa mở được file sách .abook - dùng nút “Mở file sách”." });
        continue;
      }
      try {
        const ok = await onBookFile(item.choice.ref);
        next = ok === false ? settle(next, item.id, { state: "error", note: "Không mở được file sách này." }) : settle(next, item.id, { state: "opened", note: "Đã mở" });
      } catch (error) {
        next = settle(next, item.id, { state: "error", note: (error as Error).message });
      }
    }
    return next;
  };
  // Hàng xong: không file nào lỗi thì đóng hộp (một cuốn mới duy nhất thì mở trang sách, như thêm một file); có file lỗi thì giữ hộp để đọc lý do.
  const finish = (items: QueueItem[]) => {
    const summary = summarize(items);
    if (summary.failed > 0) return;
    const added = items.filter((item) => item.state === "added");
    // Đúng một cuốn "đã có": toast cho nút đi thẳng tới cuốn đó (như nút "Mở cuốn đó" của hộp xem trước) thay vì bắt đi tìm trong thư viện.
    const known = summary.existing === 1 ? items.find((item) => item.state === "existing")?.bookId : undefined;
    clear();
    onOpenChange(false);
    (summary.added || summary.opened ? toast.success : toast)(summaryText(summary), {
      description: summary.added ? READY_NOTE : undefined,
      action: known ? { label: "Mở cuốn đó", onClick: () => navigate(`/book/${known}`) } : undefined,
    });
    if (added.length === 1 && added[0].bookId && summary.opened === 0) navigate(`/book/${added[0].bookId}`);
  };
  // Sang cuốn kế trong hàng (advanceQueue): đọc nó cho bước xem trước; file không đọc được ghi lỗi vào hàng và đi tiếp, không chặn các cuốn sau.
  const goNext = async (start: QueueItem[]) => {
    clearPreview();
    setBusy("reading");
    try {
      const { items, current } = await advanceQueue(
        start,
        async (next, items) => {
          setCurrentId(next.id);
          setQueue(items);
          await loadPreview(next.choice!);
        },
        openBookFiles,
        (failed) => {
          void importer.discard?.(failed.choice!).catch(() => undefined);
          setChoice(null);
        },
      );
      setQueue(items);
      if (!current) finish(items);
    } finally {
      setBusy(null);
    }
  };
  // Vừa chọn / kéo thả xong (planPick).
  const startPicked = async (items: PickedItem[]) => {
    const plan = planPick(items);
    if (plan.kind === "none") return;
    if (plan.kind === "single") {
      const only = plan.item;
      if ("error" in only) setProblem(only.error);
      else if ("opened" in only) {
        clear();
        onOpenChange(false);
      } else await read(only.choice);
      return;
    }
    setProblem("");
    setQueue(plan.items);
    await goNext(plan.items);
  };
  readInitial.current = (value) => (Array.isArray(value) ? startPicked(value) : read(value));
  // Tích / bỏ tích "Tách thành N chương": đọc lại file với lựa chọn mới, danh sách chương xem trước đổi theo. Tên sách người dùng đã sửa giữ
  // nguyên; gợi ý ghi công, chương đã bỏ tích và tên chương đã đổi đặt lại vì danh sách chương đã khác.
  const changeSplit = async (on: boolean) => {
    if (!choice) return;
    setBusy("reading");
    try {
      const result = await importer.preview(choice, { splitChapters: on });
      setPreview(result);
      setPicked(defaultPicked(result.chapters));
      setNames({});
      setSplit(on);
      setSkipped(new Set());
    } catch (error) {
      toast.error("Chưa đọc lại được file", { description: (error as Error).message });
    } finally {
      setBusy(null);
    }
  };
  const choose = async (kind: ImportKind) => {
    if (!importer.choose) return;
    lastKind.current = kind;
    try {
      if (kind === "file" && importer.chooseMany) {
        await startPicked(await importer.chooseMany());
        return;
      }
      const picked = await importer.choose(kind);
      if (picked === "opened") {
        // File sách .abook chọn trong hộp này: nguồn đã mở nó (toast "Đã thêm sách" kèm nút mở), hộp không còn việc.
        clear();
        onOpenChange(false);
      } else if (picked) await read(picked);
    } catch (error) {
      setProblem((error as Error).message);
    }
  };
  // "Chọn lại" sau khi đã chọn file: mở thẳng bộ chọn file (thư mục nếu lần trước chọn thư mục) thay vì quay về hộp rồi bắt bấm thêm một lần
  // nữa (soát UX a9). Máy tính (có ô dán đường dẫn) thì về bước chọn như cũ.
  const chooseAgain = () => {
    // Còn các cuốn khác trong hàng: "Chọn lại" bỏ cả hàng - hỏi như Esc, không bỏ im lặng (soát UX a10).
    if (unfinished > 1 && confirmLeave !== "again") {
      setConfirmLeave("again");
      return;
    }
    reset();
    if (importer.choose && !importer.typedPath) void choose(lastKind.current);
  };
  const openExisting = (id: string) => {
    reset();
    onOpenChange(false);
    navigate(`/book/${id}`);
  };
  // Thêm cuốn đang xem đúng như người dùng thấy (tên, chương đã tích, gợi ý đã chọn).
  const addCurrent = async (separate: boolean): Promise<AddedBook> => {
    const added = await importer.add(choice!, title.trim(), separate, { splitChapters: split, chapters: chapterPicks(preview!.chapters, picked, names) });
    // Gợi ý người nghe đã chọn: bỏ dòng ấy khỏi phần đọc của cuốn mới (chữ trong sách không đổi). Hỏng thì sách vẫn đã vào thư
    // viện - gợi ý còn chờ ở trang sách.
    if (added.how === "new") {
      for (const group of groups.filter((group) => skipped.has(group.line))) {
        await setSkipLine(added.id, group.line, group.chapters, true).catch(() => undefined);
      }
    }
    void client.invalidateQueries({ queryKey: ["listen"] });
    void client.invalidateQueries({ queryKey: ["storage"] });
    return added;
  };
  const add = async (separate = false) => {
    if (!choice || !preview) return;
    setBusy("adding");
    try {
      const added = await addCurrent(separate);
      const items = queueRef.current;
      if (items && currentId !== null) {
        // Trong hàng: cuốn này xong, sang cuốn kế (toast gộp ở cuối hàng).
        const done = settle(items, currentId, added.how === "existing" ? { state: "existing", note: "Đã có trong thư viện", bookId: added.id } : { state: "added", bookId: added.id });
        setQueue(done);
        await goNext(done);
        return;
      }
      toast.success(added.how === "existing" ? "Cuốn này đã có trong thư viện" : "Đã thêm sách vào thư viện", {
        description: added.how === "existing" ? undefined : READY_NOTE,
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
  // "Thêm tất cả phần còn lại" (addRest): cuốn đang xem thêm đúng như đang hiện, các cuốn sau dùng mặc định của bước xem trước. Cuốn nào lỗi thì ghi vào hàng
  // và đi tiếp.
  const addAll = async () => {
    const start = queueRef.current;
    if (!start || currentId === null || !choice || !preview) return;
    setBusy("adding");
    try {
      // Cuốn đang xem được thêm SAU các cuốn kế (addRest): cả lô vào thư viện đúng thứ tự đã chọn.
      const addNow = async (): Promise<Pick<QueueItem, "state" | "note" | "bookId">> => {
        setWorking(title.trim());
        if (known) return { state: "existing", note: existing ? "Đã có trong thư viện" : "Đã thêm từ file này rồi", bookId: known.id };
        try {
          const added = await addCurrent(false);
          return added.how === "existing" ? { state: "existing", note: "Đã có trong thư viện", bookId: added.id } : { state: "added", bookId: added.id };
        } catch (error) {
          return { state: "error", note: (error as Error).message };
        }
      };
      const items = await addRest(importer, start, currentId, addNow, { working: setWorking, changed: setQueue, openBooks: openBookFiles });
      void client.invalidateQueries({ queryKey: ["listen"] });
      void client.invalidateQueries({ queryKey: ["storage"] });
      setQueue(items);
      clearPreview();
      finish(items);
    } finally {
      setBusy(null);
      setWorking("");
    }
  };
  const skipCurrent = () => {
    const items = queueRef.current;
    if (!items || currentId === null) return;
    if (choice) void importer.discard?.(choice).catch(() => undefined);
    const rest = known
      ? settle(items, currentId, { state: "existing", note: existing ? "Đã có trong thư viện" : "Đã thêm từ file này rồi", bookId: known.id })
      : settle(items, currentId, { state: "skipped", note: "Bỏ qua" });
    setQueue(rest);
    void goNext(rest);
  };

  // Ghi chú đổi định dạng; gợi ý dòng ghi công (luôn ở cuối `notes`, mỗi gợi ý một ghi chú) đã thành các ô chọn ở dưới.
  const notes = preview ? preview.notes.slice(0, preview.notes.length - (preview.suggestions?.length ?? 0)) : [];
  // Gợi ý của những chương đang tích, đánh số theo mã chương trong sách sẽ thêm.
  const groups = groupSuggestions(preview ? pickedSuggestions(preview.suggestions ?? [], preview.chapters, picked) : []);
  const totals = preview ? pickedTotals(preview.chapters, picked) : { chapters: 0, words: 0 };
  const nothingPicked = preview !== null && picked.size === 0;
  // Cuốn "đã có trong thư viện" tính theo các chương MẶC ĐỊNH; tích khác đi là bộ chữ khác, cứ thêm - máy sẽ nói nếu hoá ra đã có.
  const existing = preview && isDefaultPick(preview.chapters, picked) ? preview.existing : null;
  // Cùng file đã thêm nhưng lần này chọn chương khác (hay tách chương khác): báo như trên, kèm "Vẫn thêm bản mới" - thêm cũng được, nhưng không im lặng.
  const sameSource = !existing ? (preview?.sameSource ?? null) : null;
  const known = existing ?? sameSource;
  const label = queue && currentId !== null ? queueLabel(queue, currentId) : "";
  const rest = queue && currentId !== null ? waitingAfter(queue, currentId).length : 0;

  return (
    <Dialog
      open={open}
      onOpenChange={close}
      width="max-w-2xl"
      title={preview && label ? `${label} - Thêm sách từ file` : "Thêm sách từ file"}
      description={
        queue && !preview
          ? summaryText(summarize(queue))
          : preview
          ? "Xem danh sách chương trước khi thêm. Chữ của truyện được giữ nguyên - ABook chỉ đổi định dạng."
          : "EPUB, Word (DOCX), PDF có chữ, một file TXT cả truyện, hay một thư mục mà mỗi file TXT là một chương. Sách vào Thư viện để đọc ngay. Chọn được nhiều file một lúc - từng cuốn hiện ra để xem lại trước khi thêm. Có file sách .abook (bạn bè gửi, tải về) thì chọn luôn ở đây."
      }
    >
      {confirmLeave && (
        <div
          role="alertdialog"
          aria-label={confirmLeave === "again" ? "Chọn lại khi còn sách chưa thêm" : "Đóng khi còn sách chưa thêm"}
          className="mb-4 rounded-xl border border-warning/40 bg-warning-soft p-3.5"
        >
          <p className="text-sm font-medium">
            {confirmLeave === "again"
              ? `Còn ${unfinished} cuốn chưa thêm vào thư viện. Chọn lại thì các cuốn ấy sẽ không được thêm.`
              : `Còn ${unfinished} cuốn chưa thêm vào thư viện. Đóng bây giờ thì các cuốn ấy sẽ không được thêm.`}
          </p>
          <div className="mt-3 flex flex-wrap justify-end gap-2">
            <Button
              variant="ghost"
              onClick={() => {
                if (confirmLeave === "again") {
                  chooseAgain();
                  return;
                }
                reset();
                onOpenChange(false);
              }}
            >
              {confirmLeave === "again" ? "Bỏ các cuốn còn lại và chọn lại" : "Bỏ các cuốn còn lại"}
            </Button>
            <Button variant="primary" onClick={() => setConfirmLeave(null)}>
              Quay lại thêm sách
            </Button>
          </div>
        </div>
      )}
      {queue && !preview ? (
        <div>
          {busy === "reading" && (
            <p role="status" className="flex items-center gap-2 text-sm text-fg-2">
              <Loader2 className="size-4 animate-spin" /> Đang đọc file kế tiếp…
            </p>
          )}
          <QueueList items={queue} currentId={currentId} working={working} tall />
          {busy === null && (
            <div className="mt-5 flex justify-end">
              <Button variant="primary" onClick={() => close(false)}>
                Xong
              </Button>
            </div>
          )}
        </div>
      ) : !preview ? (
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
                placeholder={importer.choose ? "…hoặc dán đường dẫn file hay thư mục" : "Dán đường dẫn file sách (EPUB, Word, PDF, TXT) hay thư mục TXT, ví dụ D:\\Truyện\\Tên truyện.epub"}
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
          {queue && <QueueList items={queue} currentId={currentId} working={working} />}
          <label className={cn("block", queue && "mt-4")}>
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
          <div className="tabular mt-4 flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1 text-sm text-fg-2">
            <span>
              <span className="font-semibold text-fg">
                {totals.chapters}
                {totals.chapters !== preview.chapters.length ? ` / ${preview.chapters.length}` : ""} chương
              </span>{" "}
              · {formatNumber(totals.words)} chữ
            </span>
            {preview.chapters.length > 1 && (
              <span className="flex gap-3 text-xs">
                <button
                  type="button"
                  disabled={busy !== null}
                  className="touch-row inline-flex items-center text-accent-text hover:underline disabled:opacity-50"
                  onClick={() => setPicked(new Set(preview.chapters.map((chapter) => chapter.index)))}
                >
                  Chọn hết
                </button>
                <button type="button" disabled={busy !== null} className="touch-row inline-flex items-center text-accent-text hover:underline disabled:opacity-50" onClick={() => setPicked(new Set())}>
                  Bỏ chọn hết
                </button>
              </span>
            )}
          </div>
          {preview.splitOffer ? (
            <label className="mt-3 flex items-start gap-2.5 rounded-xl border border-line bg-hover p-3 text-sm">
              <input
                type="checkbox"
                checked={split}
                disabled={busy !== null}
                onChange={(event) => void changeSplit(event.target.checked)}
                className="mt-0.5 size-4 shrink-0 accent-[var(--accent)]"
              />
              <span className="min-w-0">
                <span className="block font-medium">
                  {splitLabel(preview)}
                </span>
                <span className="block text-xs text-fg-2">
                  {split
                    ? "Mỗi dòng “Chương N” mở một chương mới; chữ của truyện giữ nguyên."
                    : "Cả truyện đang nằm trong một chương. Tích để có từng chương riêng - ABook chỉ cắt ở đầu các dòng ấy, không sửa chữ."}
                </span>
              </span>
            </label>
          ) : null}
          {/* Tên chương đúng như sẽ lưu (trang sách, trình phát, màn đọc cùng thấy tên này); dòng đầu của chương ở dòng phụ. Một
              thước đo cho mỗi chương: số chữ. */}
          <ChapterPreview
            chapters={preview.chapters.map((chapter) => ({ ...chapter, chars: 0 }))}
            titleFirst
            className="mt-2"
            choice={{
              picked,
              names,
              disabled: busy !== null,
              onPick: (index, on) =>
                setPicked((current) => {
                  const next = new Set(current);
                  if (on) next.add(index);
                  else next.delete(index);
                  return next;
                }),
              onRename: (chapter, value) => setNames((current) => renameChapter(current, chapter, value)),
            }}
          />
          {nothingPicked && (
            <p role="status" className="mt-2 text-sm text-danger">
              Chưa chọn chương nào - tích ít nhất một chương để thêm vào thư viện.
            </p>
          )}
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
              <p className="mt-0.5 text-xs text-fg-2">Bỏ dòng này chỉ khiến màn đọc và giọng đọc bỏ qua nó - chữ của sách vẫn giữ nguyên. Đổi ý được ở trang sách.</p>
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
          {known && (
            <p role="status" className="mt-3 rounded-xl border border-line bg-accent-soft p-3 text-sm text-accent-text">
              {existing
                ? `Cuốn này đã có trong thư viện: “${existing.title}”.`
                : `Bạn đã thêm file này thành “${sameSource!.title}” (${sameSource!.chapters} chương).`}
            </p>
          )}
          {busy === "adding" && working && queue && (
            <p role="status" className="mt-3 flex items-center gap-2 text-sm text-fg-2">
              <Loader2 className="size-4 shrink-0 animate-spin" /> <span className="min-w-0 truncate">Đang thêm “{working}”…</span>
            </p>
          )}
          <div className="mt-5 flex flex-wrap justify-end gap-2">
            <Button variant="ghost" disabled={busy !== null} onClick={chooseAgain}>
              Chọn lại
            </Button>
            {queue && (
              <Button variant={known ? "primary" : "ghost"} disabled={busy !== null} onClick={skipCurrent}>
                Bỏ cuốn này
              </Button>
            )}
            {rest > 0 && (
              <Button disabled={!title.trim() || nothingPicked || busy !== null} loading={busy === "adding"} onClick={() => void addAll()}>
                Thêm tất cả phần còn lại
              </Button>
            )}
            {known ? (
              <>
                <Button icon={Copy} loading={busy === "adding"} disabled={!title.trim() || nothingPicked || busy !== null} onClick={() => void add(true)}>
                  {existing ? "Thêm bản riêng" : "Vẫn thêm bản mới"}
                </Button>
                {/* Trong hàng, "Mở cuốn đó" bỏ dở các cuốn sau: ở đó nút chính là "Bỏ cuốn này" (cuốn này đã có rồi). */}
                {!queue && (
                  <Button variant="primary" icon={BookOpen} disabled={busy !== null} onClick={() => openExisting(known.id)}>
                    Mở cuốn đó
                  </Button>
                )}
              </>
            ) : (
              <Button variant="primary" icon={BookPlus} loading={busy === "adding"} disabled={!title.trim() || nothingPicked || busy === "reading"} onClick={() => void add()}>
                Thêm vào thư viện
              </Button>
            )}
          </div>
        </div>
      )}
    </Dialog>
  );
}

const STATE_TEXT: Record<Exclude<QueueItem["state"], "waiting">, string> = {
  added: "Đã thêm",
  existing: "Đã có trong thư viện",
  skipped: "Bỏ qua",
  opened: "Đã mở",
  error: "Chưa đọc được",
};

/** Danh sách các file đã chọn kèm tình trạng từng cái: cuốn đang xem, cuốn đã thêm / bỏ, cuốn không đọc được (kèm lý do). */
function QueueList({ items, currentId, working = "", tall }: { items: QueueItem[]; currentId: number | null; working?: string; tall?: boolean }) {
  const focus = queueFocus(items, currentId, working);
  return (
    <ul aria-label="Các file đã chọn" className={cn("mt-3 space-y-1.5 overflow-y-auto rounded-xl border border-line bg-hover p-2.5 text-xs", tall ? "max-h-72" : "max-h-36")}>
      {items.map((item) => {
        const current = item.state === "waiting" && item.id === focus.id;
        let mark: ReactNode = <span className="block size-3 rounded-full border border-line-strong" />;
        if (item.state === "added" || item.state === "existing" || item.state === "opened") mark = <Check className="size-3.5 text-success" strokeWidth={3} />;
        else if (item.state === "error") mark = <CircleAlert className="size-3.5 text-danger" />;
        else if (item.state === "skipped") mark = <Minus className="size-3.5 text-fg-3" />;
        else if (current) mark = <span className="block size-3 rounded-full bg-accent" />;
        const said = item.state === "waiting" ? (current ? (focus.adding ? "Đang thêm" : "Đang xem") : "Chờ") : item.note ?? STATE_TEXT[item.state];
        return (
          <li key={item.id} aria-current={current ? "true" : undefined} className="flex items-start gap-2">
            <span className="mt-0.5 grid size-3.5 shrink-0 place-items-center">{mark}</span>
            <span className="min-w-0 flex-1">
              <span className={cn("block truncate", current ? "font-semibold text-fg" : "text-fg-2")}>{item.name}</span>
              <span className={cn("block text-pretty", item.state === "error" ? "text-danger" : "text-fg-3")}>{said}</span>
            </span>
          </li>
        );
      })}
    </ul>
  );
}
