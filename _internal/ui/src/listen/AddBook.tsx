import { S } from "../shared/strings.generated";
import { MotionRegion } from "@/shared/MotionRegion";
import { feedback } from "@/shared/feedback";
import { Fold } from "@/shared/Collapse";
import { useBackLayer } from "@/shared/backStack";
import { useMotionState } from "@/shared/motion";
import { useListPresence } from "@/shared/motion";
import { useQueryClient } from "@tanstack/react-query";
import { BookOpen, BookPlus, Check, CircleAlert, Copy, FileText, Folder, Loader2, Minus, Plus } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { useNavigate } from "react-router";
import { toast } from "@/shared/toast";
import { ChapterPreview } from "@/shared/ChapterPreview";
import { cn } from "@/shared/cn";
import { ErrorDetails } from "@/shared/ErrorDetails";
import { SectionHeading } from "@/shared/SectionHeading";
import { formatNumber } from "@/shared/format";
import { DialogActions, Button, ContentSkeleton, Dialog, InlineError } from "@/shared/ui";
import {
  addRest,
  advanceQueue,
  planPick,
  queueFocus,
  queueLabel,
  ReadCancelled,
  readSessions,
  settle,
  summarize,
  summaryText,
  waitingAfter,
  type QueueItem,
  type ReadSession,
} from "./importQueue";
import { FootnoteChoices } from "./FootnoteChoices";
import { groupSuggestions, setSkipLine, SuggestionChoices } from "./ReadingSuggestions";
import { useSource } from "./source";
import { technicalOf } from "@/studio/api";
import { useFadeScroller } from "@/shared/scrollFade";
import {
  chapterPicks,
  defaultPicked,
  footnotesToSend,
  isBookFile,
  isDefaultPick,
  NO_FOOTNOTES,
  pickedSuggestions,
  pickedTotals,
  readPreview,
  renameChapter,
  sameRows,
  splitHint,
  type ChapterNames,
  type AddedBook,
  type FootnoteChoice,
  type ImportChoice,
  type ImportKind,
  type ImportPreview,
  type PickedItem,
} from "./textImport";

import { Reveal } from "../shared/MotionPresence";
// "Thêm sách từ file…": EPUB / DOCX / PDF / thư mục TXT thành sách chỉ-có-chữ trong thư viện (docs/LISTEN_ANYTHING.md mục 1 và 2).
// Ba bước trong một hộp: chọn → xem danh sách chương (và gợi ý của máy) → thêm. Máy tính và điện thoại dùng chung; chỗ khác nhau
// (bộ chọn, ai đọc file) nằm ở `source.textImport`.

function cleanPath(value: string): string {
  return value.trim().replace(/^["']+|["']+$/g, "").trim();
}

export { isBookFile };

/** Nút mở hộp "Thêm sách từ file…"; không hiện khi nguồn này không nhập được (`source.textImport` trống). */
export function AddBookButton({
  variant = "ghost",
  size,
  onBookFile,
}: {
  variant?: "ghost" | "primary";
  size?: "sm" | "md" | "lg";
  /** Chọn hay dán một file .abook / .abookproj: mở nó (máy có đường mở file sách) thay vì báo "chưa đọc được". */
  onBookFile?: (path: string, session?: ReadSession) => Promise<void | boolean>;
}) {
  const source = useSource();
  const [open, setOpen] = useState(false);
  if (!source.textImport) return null;
  return (
    <>
      <Button variant={variant} size={size} icon={Plus} className="touch-row" onClick={() => setOpen(true)}>{S.s_them_sach_2a9d3708}</Button>
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
  onBookFile?: (path: string, session?: ReadSession) => Promise<void | boolean>;
  /** Thứ đã chọn sẵn (điện thoại: file app khác gửi tới - android/imports.ts; máy tính: file kéo thả vào thư viện - DropToAdd.tsx): hộp mở thẳng ở bước
   *  đọc file / xem trước. Nhiều file thì thành hàng xem trước. */
  initial?: ImportChoice | PickedItem[] | null;
}) {
  const scrollFade = useFadeScroller<HTMLDivElement>();
  const source = useSource();
  const importer = source.textImport;
  const client = useQueryClient();
  const navigate = useNavigate();
  const [choice, setChoice] = useState<ImportChoice | null>(null);
  const lastRead = useRef<ImportChoice | null>(null);
  // Các bước con do MotionRegion trong hộp chuyển động; reset khi đóng không chụp cả nền trang.
  const [preview, , setPreview] = useMotionState<ImportPreview | null>(null);
  const [title, setTitle] = useState("");
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState<"reading" | "adding" | null>(null);
  const [problem, setProblem] = useState("");
  const [technical, setTechnical] = useState(""); // nguyên văn lỗi không ngờ của máy chủ - thu trong "Chi tiết" dưới lời báo
  const fail = (error: unknown) => {
    setProblem((error as Error).message);
    setTechnical(technicalOf(error));
  };
  // Chọn / kéo thả nhiều file: hàng xem trước (importQueue.ts), mỗi cuốn qua đúng bước xem trước của một file. `null` = một file như trước. `queueRef` giữ
  // bản mới nhất cho các vòng async ("Thêm phần còn lại" đi qua nhiều cuốn trong một lần bấm).
  const [queue, setQueueState] = useState<QueueItem[] | null>(null);
  const queueRef = useRef<QueueItem[] | null>(null);
  const [currentId, setCurrentId] = useState<number | null>(null);
  const [working, setWorking] = useState("");
  // Hộp hỏi trong hộp thoại khi hàng còn sách chưa thêm: "close" = Esc / bấm ra ngoài, "again" = nút "Chọn lại" (cả hai bỏ cả hàng).
  const [confirmLeave, , setConfirmLeave] = useMotionState<"close" | "again" | null>(null);
  const setQueue = (next: QueueItem[] | null) => {
    queueRef.current = next;
    setQueueState(next);
  };
  // Gợi ý dòng ghi công người nghe chọn bỏ khỏi phần đọc (theo dòng); mặc định không bỏ dòng nào.
  const [skipped, setSkipped] = useState<ReadonlySet<string>>(new Set());
  // File TXT cả truyện: "Tách chương" theo N dòng “Chương N” - tích sẵn khi máy chắc (`splitIsSure`: từ 3 dòng), không thì chỉ đề xuất; bỏ tích được,
  // file của người dùng không bị sửa.
  const [split, setSplit] = useState(false);
  // Chú thích trong sách (EPUB / DOCX): đề xuất "Bỏ số gọi" và "Lời chú" (Giữ nguyên / Cuối chương / Bỏ lời chú) - mặc định giữ nguyên như file.
  const [footnotes, setFootnotes] = useState<FootnoteChoice>(NO_FOOTNOTES);
  // Chương nào vào sách (số thứ tự hàng của bước xem trước) và tên người dùng đã đổi. Mặc định như máy đề xuất: mọi chương trừ mục rất ngắn.
  const [picked, setPicked] = useState<ReadonlySet<number>>(new Set());
  const [names, setNames] = useState<ChapterNames>({});
  const titleField = useRef<HTMLInputElement>(null);
  const lastKind = useRef<ImportKind>("file");
  // Đọc xong file: con trỏ sang ô "Tên sách" (lúc mở hộp, `data-autofocus` của ô đường dẫn nhận con trỏ). Màn cảm ứng thì KHÔNG: bàn phím
  // ảo bật lên che mất nút "Thêm vào thư viện", mà tên đã điền sẵn và hiếm khi cần sửa (soát máy thật 03-10).
  const hasPreview = preview !== null; // tích / bỏ tích tách chương đọc lại bản xem trước: con trỏ không nhảy về ô tên
  useEffect(() => {
    if (!hasPreview || window.matchMedia?.("(any-pointer: coarse)").matches) return;
    titleField.current?.focus();
    titleField.current?.select();
  }, [hasPreview]);
  // Đọc thứ chọn sẵn đúng một lần (`read` dựng ở dưới, sau chỗ trả sớm khi nguồn không nhập được).
  const readInitial = useRef<((picked: ImportChoice | PickedItem[]) => Promise<void>) | null>(null);
  const initialRead = useRef<ImportChoice | PickedItem[] | null>(null);
  const reads = useRef(readSessions());
  useEffect(() => {
    if (!open) reads.current.cancel();
  }, [open]);
  useEffect(() => {
    if (!open || !initial || initialRead.current === initial) return;
    initialRead.current = initial;
    void readInitial.current?.(initial);
  }, [open, initial]);
  // DESIGN.md §2 L1 (Thêm sách -> chọn file -> xác nhận -> Nghe, ≤ 4 chạm): mở hộp là mở luôn bộ chọn file của hệ thống - bước chọn của hộp
  // (thư mục TXT, dán đường dẫn) nằm sau làm lối khác khi bạn huỷ bộ chọn, không bắt bấm thêm "Chọn file sách". Mỗi lần mở một lần.
  const pickOnOpen = useRef<(() => void) | null>(null);
  const pickedOnOpen = useRef(false);
  useEffect(() => {
    if (!open) pickedOnOpen.current = false;
    else if (!initial && !pickedOnOpen.current) {
      pickedOnOpen.current = true;
      pickOnOpen.current?.();
    }
  }, [open, initial]);
  // Hộp bị gỡ khỏi trang (rời màn hình) cũng bỏ lần đọc dở. Quên thứ chọn sẵn đã đọc: StrictMode (android/main.tsx) gỡ rồi gắn lại ngay,
  // lần gắn lại phải đọc lại file chia sẻ thay vì để nó mất theo lần đọc vừa huỷ.
  useEffect(() => () => {
    reads.current.cancel();
    initialRead.current = null;
  }, []);
  if (!importer) return <MotionRegion />;

  const clearPreview = () => {
    setChoice(null);
    setPreview(null);
    setTitle("");
    setSkipped(new Set());
    setSplit(false);
    setFootnotes(NO_FOOTNOTES);
    setPicked(new Set());
    setNames({});
  };
  const clear = () => {
    reads.current.cancel();
    // Đóng hộp / chọn lại đã bỏ bản chép: "Thử lại" sau đó không được đọc lại cuốn cũ.
    lastRead.current = null;
    setBusy(null);
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
  const confirmBox = useRef<HTMLDivElement>(null);
  const confirmButton = useRef<HTMLElement | null>(null);
  useBackLayer(open && confirmLeave !== null, () => setConfirmLeave(null), confirmBox, confirmButton);
  const close = (next: boolean) => {
    if (!next && confirmLeave !== null) { setConfirmLeave(null); return; }
    if (busy === "adding") return;
    if (!next && unfinished > 1) {
      confirmButton.current = document.activeElement as HTMLElement;
      setConfirmLeave((asked) => (asked === "close" ? null : "close")); // lần Esc thứ hai là "Quay lại"
      return;
    }
    if (!next) reset();
    onOpenChange(next);
  };
  // Đọc file thành bản xem trước: cả truyện trong một file mà máy chắc là nhiều chương thì mở sẵn với "tách" đã tích (bỏ tích được, danh sách
  // chương đổi theo).
  const loadPreview = async (picked: ImportChoice, session: ReadSession) => {
    session.still();
    setChoice(picked);
    const { preview: result, split: sure } = await session.wait(readPreview(
      { preview: (...args) => session.wait(importer.preview(...args)) }, picked,
    ));
    setPreview(result);
    setSkipped(new Set((result.suggestions ?? []).filter((row) => row.defaultOn).map((row) => row.line)));
    setPicked(defaultPicked(result.chapters));
    setTitle(result.title);
    setSplit(sure);
    setFootnotes(NO_FOOTNOTES);
  };
  const read = async (picked: ImportChoice) => {
    lastRead.current = picked;
    const session = reads.current.start();
    if (onBookFile && isBookFile(picked.ref)) {
      // Soát UX 05-10: dán đường dẫn .abook vào đây từng báo "Chưa đọc được file .abook" mà không chỉ sang "Mở file sách".
      setProblem("");
      setBusy("reading");
      try {
        await session.wait(onBookFile(picked.ref, session));
        clear();
        onOpenChange(false);
      } catch (error) {
        if (!(error instanceof ReadCancelled)) fail(error);
      } finally {
        if (session.active()) setBusy(null);
      }
      return;
    }
    setProblem("");
    setBusy("reading");
    try {
      await loadPreview(picked, session);
    } catch (error) {
      void importer.discard?.(picked).catch(() => undefined);
      // Bản chép đã bỏ thật (điện thoại xoá thư mục chép): "Thử lại" phải chọn lại file, không đọc lại chỗ không còn. Máy tính không chép (không discard) nên đọc lại đúng đường dẫn.
      if (importer.discard && lastRead.current === picked) lastRead.current = null;
      if (error instanceof ReadCancelled) return;
      fail(error);
      setChoice(null);
    } finally {
      if (session.active()) setBusy(null);
    }
  };
  // ---- Hàng nhiều file (importQueue.ts) -------------------------------------------------------------------------------------
  // File sách .abook / .abookproj còn lại (đã xếp cuối hàng) mở như "Mở file sách". Mở xong app sang trang sách, nên đây là việc cuối cùng.
  const openBookFiles = async (items: QueueItem[], session?: ReadSession) => {
    let next = items;
    for (const item of items) {
      session?.still();
      if (item.state !== "waiting" || !item.choice) continue;
      if (!onBookFile) {
        next = settle(next, item.id, { state: "error", note: S.s_o_day_chua_mo_duoc_file_sach_abook_dung_nu_47081bf0 });
        continue;
      }
      try {
        const opening = onBookFile(item.choice.ref, session);
        const ok = await (session ? session.wait(opening) : opening);
        next = ok === false ? settle(next, item.id, { state: "error", note: S.s_chua_mo_duoc_file_sach_nay_1bc6cc5d }) : settle(next, item.id, { state: "opened", note: S.s_da_them_e26b2fcb });
      } catch (error) {
        if (error instanceof ReadCancelled) throw error;
        next = settle(next, item.id, { state: "error", note: (error as Error).message });
      }
    }
    return next;
  };
  // Hàng xong: không file nào lỗi thì đóng hộp (một cuốn mới duy nhất thì mở trang sách, như thêm một file); có file lỗi thì giữ hộp để đọc lý do.
  const finish = (items: QueueItem[]) => {
    const summary = summarize(items);
    if (summary.failed > 0) return feedback("reject");
    if (summary.added) feedback("confirm");
    const added = items.filter((item) => item.state === "added");
    // Đúng một cuốn "đã có": toast cho nút đi thẳng tới cuốn đó (như nút "Mở cuốn đó" của hộp xem trước) thay vì bắt đi tìm trong thư viện.
    const known = summary.existing === 1 ? items.find((item) => item.state === "existing")?.bookId : undefined;
    clear();
    onOpenChange(false);
    (summary.added || summary.opened ? toast.success : toast)(summaryText(summary), {
      action: known ? { label: S.s_mo_cuon_do_75ab80a2, onClick: () => navigate(`/book/${known}`) } : undefined,
    });
    if (added.length === 1 && added[0].bookId && summary.opened === 0) navigate(`/book/${added[0].bookId}`);
  };
  // Sang cuốn kế trong hàng (advanceQueue): đọc nó cho bước xem trước; file không đọc được ghi lỗi vào hàng và đi tiếp, không chặn các cuốn sau.
  const goNext = async (start: QueueItem[]) => {
    const session = reads.current.start();
    clearPreview();
    setBusy("reading");
    try {
      const { items, current } = await advanceQueue(
        start,
        async (next, items) => {
          session.still();
          setCurrentId(next.id);
          setQueue(items);
          await loadPreview(next.choice!, session);
        },
        (items) => openBookFiles(items, session),
        (failed) => {
          void importer.discard?.(failed.choice!).catch(() => undefined);
          setChoice(null);
        },
      );
      session.still();
      setQueue(items);
      if (!current) finish(items);
    } catch (error) {
      if (!(error instanceof ReadCancelled)) fail(error);
    } finally {
      if (session.active()) setBusy(null);
    }
  };
  // Vừa chọn / kéo thả xong (planPick).
  const startPicked = async (items: PickedItem[]) => {
    const plan = planPick(items);
    if (plan.kind === "none") return;
    if (plan.kind === "single") {
      const only = plan.item;
      if ("error" in only) {
        setProblem(only.error);
        setTechnical("");
      }
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
  // Tích / bỏ tích "Tách thành N chương" hay một đề xuất về chú thích: đọc lại file với lựa chọn mới, danh sách chương xem trước đổi theo. Tên sách
  // người dùng đã sửa giữ nguyên; gợi ý ghi công, chương đã bỏ tích và tên chương đã đổi đặt lại vì danh sách chương đã khác (còn giữ khi danh
  // sách chương vẫn y như trước - chú thích chỉ đổi chữ trong chương).
  const reread = async (next: { split: boolean; footnotes: FootnoteChoice }) => {
    if (!choice) return;
    const session = reads.current.start();
    setBusy("reading");
    try {
      const result = await session.wait(importer.preview(choice, { splitChapters: next.split, footnotes: footnotesToSend(next.footnotes) }));
      if (!(preview && sameRows(preview.chapters, result.chapters))) {
        setPicked(defaultPicked(result.chapters));
        setNames({});
        setSkipped(new Set());
      }
      setPreview(result);
      setSplit(next.split);
      setFootnotes(next.footnotes);
    } catch (error) {
      if (error instanceof ReadCancelled) return;
      toast.error(S.s_chua_doc_lai_duoc_file_114c3abe, { description: (error as Error).message });
    } finally {
      if (session.active()) setBusy(null);
    }
  };
  const changeSplit = (on: boolean) => reread({ split: on, footnotes });
  const changeFootnotes = (next: FootnoteChoice) => reread({ split, footnotes: next });
  const choose = async (kind: ImportKind) => {
    if (!importer.choose) return;
    const session = reads.current.start();
    lastKind.current = kind;
    try {
      if (kind === "file" && importer.chooseMany) {
        const items = await importer.chooseMany();
        if (!session.active()) {
          for (const item of items) if ("choice" in item) void importer.discard?.(item.choice).catch(() => undefined);
          return;
        }
        await startPicked(items);
        return;
      }
      const picked = await importer.choose(kind);
      if (!session.active()) {
        if (picked && picked !== "opened") void importer.discard?.(picked).catch(() => undefined);
        return;
      }
      if (picked === "opened") {
        // File sách .abook chọn trong hộp này: nguồn đã mở nó (toast "Đã thêm sách" kèm nút mở), hộp không còn việc.
        clear();
        onOpenChange(false);
      } else if (picked) await read(picked);
    } catch (error) {
      if (session.active() && !(error instanceof ReadCancelled)) fail(error);
    }
  };
  pickOnOpen.current = importer.choose ? () => void choose("file") : null;
  // "Chọn lại" sau khi đã chọn file: mở thẳng bộ chọn file (thư mục nếu lần trước chọn thư mục) thay vì quay về hộp rồi bắt bấm thêm một lần
  // nữa (soát UX a9). Máy tính (có ô dán đường dẫn) thì về bước chọn như cũ.
  const chooseAgain = () => {
    // Còn các cuốn khác trong hàng: "Chọn lại" bỏ cả hàng - hỏi như Esc, không bỏ im lặng (soát UX a10).
    if (unfinished > 1 && confirmLeave !== "again") {
      confirmButton.current = document.activeElement as HTMLElement;
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
    const added = await importer.add(choice!, title.trim(), separate, {
      sourceFingerprint: preview!.sourceFingerprint,
      splitChapters: split,
      footnotes: footnotesToSend(footnotes),
      chapters: chapterPicks(preview!.chapters, picked, names),
    });
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
        const done = settle(items, currentId, added.how === "existing" ? { state: "existing", note: S.s_da_co_trong_thu_vien_3bb6eeb4, bookId: added.id } : { state: "added", bookId: added.id });
        setQueue(done);
        await goNext(done);
        return;
      }
      if (added.how !== "existing") feedback("confirm");
      if (added.how === "existing") toast.success(S.s_cuon_nay_da_co_trong_thu_vien_2aae08e1);
      else toast.success(S.s_da_them_0_ea40abe7(title.trim()));
      clear(); // bản tạm đã dùng xong (native tự dọn)
      onOpenChange(false);
      navigate(`/book/${added.id}`);
    } catch (error) {
      feedback("reject");
      toast.error(S.s_chua_them_duoc_sach_b327e086, { description: (error as Error).message });
    } finally {
      setBusy(null);
    }
  };
  // "Thêm phần còn lại" (addRest): cuốn đang xem thêm đúng như đang hiện, các cuốn sau dùng mặc định của bước xem trước. Cuốn nào lỗi thì ghi vào hàng
  // và đi tiếp.
  const addAll = async () => {
    const start = queueRef.current;
    if (!start || currentId === null || !choice || !preview) return;
    setBusy("adding");
    try {
      // Cuốn đang xem được thêm SAU các cuốn kế (addRest): cả lô vào thư viện đúng thứ tự đã chọn.
      const addNow = async (): Promise<Pick<QueueItem, "state" | "note" | "bookId">> => {
        setWorking(title.trim());
        if (known) return { state: "existing", note: existing ? S.s_da_co_trong_thu_vien_3bb6eeb4 : S.s_da_them_tu_file_nay_roi_42fe4ad5, bookId: known.id };
        try {
          const added = await addCurrent(false);
          return added.how === "existing" ? { state: "existing", note: S.s_da_co_trong_thu_vien_3bb6eeb4, bookId: added.id } : { state: "added", bookId: added.id };
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
      ? settle(items, currentId, { state: "existing", note: existing ? S.s_da_co_trong_thu_vien_3bb6eeb4 : S.s_da_them_tu_file_nay_roi_42fe4ad5, bookId: known.id })
      : settle(items, currentId, { state: "skipped", note: S.s_da_bo_qua_df41794e });
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
  // Cuốn đã có: bỏ qua là việc chính, đứng cuối chân hộp ở cả hai nền tảng.
  const skipAction = <Reveal when={queue}><Button variant={known ? "primary" : "ghost"} disabled={busy !== null} onClick={skipCurrent}>{S.s_bo_cuon_nay_ba5f36fe}</Button></Reveal>;

  return (
    <Dialog footer={queue && !preview ? (busy === null && (<DialogActions>
              <Button variant="primary" onClick={() => close(false)}>{S.s_xong_a6f4543a}</Button>
            </DialogActions>)) : (!preview ? (null) : (<DialogActions data-add-book-actions>
            <Button variant="ghost" disabled={busy !== null} onClick={chooseAgain}>{S.s_chon_lai_834274af}</Button>
            {!known && skipAction}
            <Reveal when={rest > 0}><Button disabled={!title.trim() || nothingPicked || busy !== null} loading={busy === "adding"} onClick={() => void addAll()}>{S.s_them_phan_con_lai_45b70e44}</Button></Reveal>
            {known ? (
              <>
                <Button icon={Copy} loading={busy === "adding"} disabled={!title.trim() || nothingPicked || busy !== null} onClick={() => void add(true)}>
                  {existing ? S.s_them_ban_rieng_fe9759e4 : S.s_van_them_ban_moi_f4832361}
                </Button>
                {/* Trong hàng, "Mở cuốn đó" bỏ dở các cuốn sau: ở đó nút chính là "Bỏ cuốn này" (cuốn này đã có rồi). */}
                <Reveal when={!queue}><Button variant="primary" icon={BookOpen} disabled={busy !== null} onClick={() => openExisting(known.id)}>{S.s_mo_cuon_do_75ab80a2}</Button></Reveal>
              </>
            ) : (
              <Button variant="primary" icon={BookPlus} loading={busy === "adding"} disabled={!title.trim() || nothingPicked || busy === "reading"} onClick={() => void add()}>{S.s_them_vao_thu_vien_cc27dafc}</Button>
            )}
            {known && skipAction}
          </DialogActions>))}
      open={open}
      onOpenChange={close}
      width="max-w-[560px]"
      title={preview ? (label ? S.s_0_xem_truoc_0b80ebc7(label) : S.s_xem_truoc_4282388c) : S.s_them_sach_2a9d3708}
      description={
        queue && !preview
          ? summaryText(summarize(queue))
          : preview
          ? undefined
          : S.s_epub_docx_pdf_co_chu_txt_hoac_file_abook_c_cc969e7b
      }
    ><MotionRegion fadeThrough>
      {confirmLeave && (
        <div
          ref={confirmBox}
          role="alertdialog"
          aria-label={confirmLeave === "again" ? S.s_chon_lai_khi_con_sach_chua_them_4b4c7b1a : S.s_dong_khi_con_sach_chua_them_0406a915}
          className="mb-4 py-4"
        >
          <p className="text-sm font-medium">
            {confirmLeave === "again"
              ? S.s_con_0_cuon_chua_them_vao_thu_vien_chon_lai_0dbdaa1f(unfinished)
              : S.s_con_0_cuon_chua_them_vao_thu_vien_dong_bay_91cf24f8(unfinished)}
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
              {confirmLeave === "again" ? S.s_bo_va_chon_lai_89f7d490 : S.s_bo_phan_con_lai_63a3c314}
            </Button>
            <Button variant="primary" onClick={() => setConfirmLeave(null)}>{S.s_quay_lai_them_sach_e5ac9359}</Button>
          </div>
        </div>
      )}
      {queue && !preview ? (
        <div>
          {busy === "reading" && (
            <ContentSkeleton count={1} label={S.s_dang_doc_1b09d2d9} />
          )}
          <QueueList items={queue} currentId={currentId} working={working} tall />

        </div>
      ) : !preview ? (
        <div className="add-book-choose">
          <div className="add-book-pick flex flex-wrap gap-2">
            {importer.choose && (
              <>
                <Button variant="primary" icon={busy === "reading" ? Loader2 : FileText} disabled={busy !== null} onClick={() => void choose("file")}>
                  {busy === "reading" ? S.s_dang_doc_1b09d2d9 : S.s_chon_file_sach_1f25282c}
                </Button>
                <Button icon={Folder} disabled={busy !== null} onClick={() => void choose("folder")}>{S.s_chon_thu_muc_txt_dd0d140c}</Button>
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
                data-autofocus={window.matchMedia?.("(any-pointer: coarse)").matches ? undefined : true}
                onChange={(event) => setTyped(event.target.value)}
                aria-label={S.s_duong_dan_file_hay_thu_muc_4a384785}
                aria-describedby={importer.choose ? undefined : "typed-path-hint"}
                placeholder={importer.choose ? S.s_hoac_dan_duong_dan_bb4837f7 : S.s_dan_duong_dan_file_hay_thu_muc_5bbc5845}
                className="h-[40px] min-w-0 flex-1 rounded-control border border-line bg-bg px-3 text-sm outline-none placeholder:text-fg-3 focus:border-focus"
              />
              <Button type="submit" className="-mr-4 h-10 min-h-10" disabled={!cleanPath(typed) || busy !== null} loading={busy === "reading" && !importer.choose}>{S.s_mo_741bd2c2}</Button>
            </form>
          )}
          {/* Gợi ý dài nằm dưới ô, không nhét vào chữ mờ trong ô - màn 390 px cắt cụt nó (soát a64). Có nút chọn file thì lời đầu hộp đã kể các
              loại file, không nhắc lại. */}
          {importer.typedPath && !importer.choose && (
            <p id="typed-path-hint" className="mt-2 text-pretty text-xs text-fg-3">{S.s_file_sach_epub_word_pdf_txt_hay_thu_muc_tx_3632db2b}</p>
          )}
          {busy === "reading" && <ContentSkeleton shape="cards" count={2} label={S.s_dang_doc_1b09d2d9} className="mt-4" />}
          {problem && (
            <div className="mt-3">
              <InlineError message={problem} onRetry={() => { if (lastRead.current) void read(lastRead.current); else void choose(lastKind.current); }} />
              {technical && <ErrorDetails technical={technical} />}
            </div>
          )}
        </div>
      ) : (
        <div>
          {queue && <QueueList items={queue} currentId={currentId} working={working} />}
          <label className={cn("block", queue && "mt-4")}>
            <span className="text-sm font-medium">{S.s_ten_sach_d54846eb}</span>
            <input
              ref={titleField}
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              aria-invalid={!title.trim()}
              className="touch-box mt-2 h-11 w-full rounded-cover border border-line bg-bg px-4 text-body font-medium outline-none focus:border-focus"
              placeholder={S.s_ten_hien_thi_trong_thu_vien_c48c7ac6}
            />
          </label>
          {preview.author && <p className="mt-2 text-sm text-fg-2">{S.s_tac_gia_3fe05994}{preview.author}</p>}
          <SectionHeading as="h3" className="mt-2">{S.s_chuong_2d157977}</SectionHeading>
          <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1 text-sm text-fg-2">
            <span>
              <span className="font-medium text-fg">
                {totals.chapters}
                {totals.chapters !== preview.chapters.length ? ` / ${preview.chapters.length}` : ""}{S.s_chuong_9e6a01dc}</span>{" "}
              · {formatNumber(totals.words)}{S.s_chu_6117d040}</span>
            {preview.chapters.length > 1 && (
              <span className="flex gap-3 text-xs">
                <button
                  type="button"
                  disabled={busy !== null}
                  className="touch-row inline-flex items-center text-accent-text hover:underline disabled:opacity-50"
                  onClick={() => setPicked(new Set(preview.chapters.map((chapter) => chapter.index)))}
                >{S.s_chon_het_9e8a7c2c}</button>
                <button type="button" disabled={busy !== null} className="touch-row inline-flex items-center text-accent-text hover:underline disabled:opacity-50" onClick={() => setPicked(new Set())}>{S.s_bo_chon_het_669fa50d}</button>
              </span>
            )}
          </div>
          {preview.splitOffer ? (
            <label className="mt-3 flex items-start gap-3 py-3 text-sm">
              <input
                type="checkbox"
                checked={split}
                disabled={busy !== null}
                onChange={(event) => void changeSplit(event.target.checked)}
                className="mt-1 size-4 shrink-0 accent-[var(--accent)]"
              />
              <span className="min-w-0">
                <span className="block font-medium">{S.s_tach_chuong_2f1df570}</span>
                <span className="block text-xs text-fg-2">{splitHint(preview)}</span>
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
            <p role="status" className="mt-2 text-sm text-danger">{S.s_chua_chon_chuong_nao_tich_it_nhat_mot_chuo_416cb9ec}</p>
          )}
          {notes.length > 0 && (
            <Fold storageKey="add-book.format" title={S.s_dinh_dang_36b746b6} summary={S.s_0_ghi_chu_0dffe4dd(notes.length)} className="mt-3" bodyClassName="px-3 pb-3 text-xs text-fg-2">
              <p className="font-medium text-fg">{S.s_may_da_doi_dinh_dang_chu_cua_truyen_giu_ng_bdfa175d}</p>
              <ul className="mt-1 space-y-1">
                {notes.slice(0, 6).map((note) => (
                  <li key={note}>{note}</li>
                ))}
              </ul>
              {notes.length > 6 && <p className="mt-1">{S.s_va_6e638075}{notes.length - 6}{S.s_ghi_chu_nua_fe5122f7}</p>}
            </Fold>
          )}
          {preview.footnotes && <Fold storageKey="add-book.footnotes" title={S.s_chu_thich_fc0aa279} className="mt-3" bodyClassName="px-3 pb-3"><FootnoteChoices offer={preview.footnotes} value={footnotes} disabled={busy !== null} onChange={(next) => void changeFootnotes(next)} /></Fold>}
          {groups.length > 0 && (
            <Fold storageKey="add-book.suggestions" title={S.s_goi_y_phan_doc_b268d95e} summary={S.s_0_nhom_5fc9eee6(groups.length)} className="mt-3" bodyClassName="px-3 pb-3">
              <div ref={scrollFade.ref} style={scrollFade.style} className="mt-2 max-h-40 overflow-y-auto">
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
            </Fold>
          )}
          {known && (
            <p role="status" className="mt-3 py-3 text-sm text-accent-text">
              {existing
                ? S.s_cuon_nay_da_co_trong_thu_vien_0_d8728110(existing.title)
                : S.s_ban_da_them_file_nay_thanh_0_1_chuong_68248830(sameSource!.title, sameSource!.chapters)}
            </p>
          )}
          {busy === "adding" && working && queue && (
            <ContentSkeleton className="mt-3" count={1} label={S.s_dang_them_457edcc3} />
          )}


        </div>
      )}
    </MotionRegion></Dialog>
  );
}

const STATE_TEXT: Record<Exclude<QueueItem["state"], "waiting">, string> = {
  added: S.s_da_them_e26b2fcb,
  existing: S.s_da_co_trong_thu_vien_3bb6eeb4,
  skipped: S.s_da_bo_qua_df41794e,
  opened: S.s_da_them_e26b2fcb,
  error: S.s_chua_doc_duoc_ad95887c,
};

/** Danh sách các file đã chọn kèm tình trạng từng cái: cuốn đang xem, cuốn đã thêm / bỏ, cuốn không đọc được (kèm lý do). */
export function QueueList({ items, currentId, working = "", tall }: { items: QueueItem[]; currentId: number | null; working?: string; tall?: boolean }) {
  const scrollFade = useFadeScroller<HTMLUListElement>();
  const rows = useListPresence(items, (item) => String(item.id));
  const focus = queueFocus(items, currentId, working);
  return (
    <ul ref={scrollFade.ref} style={scrollFade.style} aria-label={S.s_file_da_chon_e29eb975} className={cn("mt-3 space-y-2 overflow-y-auto py-3 text-xs", tall ? "max-h-72" : "max-h-36")}>
      {rows.map(({ item, key, state, ref }) => {
        const current = item.state === "waiting" && item.id === focus.id;
        let mark: ReactNode = <span className="block size-3 rounded-full border border-line-strong" />;
        if (item.state === "added" || item.state === "existing" || item.state === "opened") mark = <Check className="size-3.5 text-success" strokeWidth={3} />;
        else if (item.state === "error") mark = <CircleAlert className="size-3.5 text-danger" />;
        else if (item.state === "skipped") mark = <Minus className="size-3.5 text-fg-3" />;
        else if (current) mark = <span className="block size-3 rounded-full bg-accent" />;
        const said = item.state === "waiting" ? (current ? (focus.adding ? S.s_dang_them_457edcc3 : S.s_dang_xem_42cc3b08) : S.s_cho_8de7e9a5) : item.note ?? STATE_TEXT[item.state];
        return (
          <li key={key} ref={ref} aria-current={current ? "true" : undefined} className="motion-row" data-state={state} inert={state === "exit"}><div className="flex items-start gap-2">
            <MotionRegion as="span" className="mt-1 grid size-3.5 shrink-0 place-items-center">{mark}</MotionRegion>
            <span className="min-w-0 flex-1">
              <span className={cn("block break-words", current ? "font-medium text-fg" : "text-fg-2")}>{item.name}</span>
              <MotionRegion as="span" motionKey={said} className={cn("block text-pretty", item.state === "error" ? "text-danger" : "text-fg-3")}>{said}</MotionRegion>
            </span>
          </div></li>
        );
      })}
    </ul>
  );
}
