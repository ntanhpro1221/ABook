import { BookmarkPlus, Copy, Pencil, Play, X } from "lucide-react";
import { useCallback, useEffect, useState, type ReactNode } from "react";
import { toast } from "sonner";
import { cn } from "@/shared/cn";
import { lineEditing } from "@/shared/capabilities";
import { excerpt } from "@/shared/format";
import { Button, Dialog } from "@/shared/ui";
import { useAppInfo } from "@/studio/data";
import { canEditBook } from "./EditBook";
import { lineToEdit, type LineToEdit } from "./follow";
import { LineWishDialog, useWishes, WaitingMark } from "./LineWishes";
import { canTeachWords, wordOf } from "./readings";
import type { ListenBook, ListenChapter, Script, ScriptSegment } from "./model";
import { useListenMutations } from "./source";
import { reportWriteFailure } from "./recordWrites";
import { makeAnchor } from "./readingAnchor";
import { WordReadingDialog } from "./WordReadings";

// Chọn một câu của văn bản đọc theo rồi làm gì với nó - MỘT chỗ cho màn Đọc (ReaderScreen) và tab "Đọc theo" của màn "Đang nghe" (PlayerViews):
// nghe từ câu ấy, đặt dấu trang, chép, sửa cách đọc một từ (cuốn chỉ có chữ), sửa câu này (cuốn có audio). Giữ ngón tay / bấm chuột phải vào
// một chữ mở thẳng việc sửa chữ ấy; loại sách không sửa được chữ thì chọn câu (thanh có "Chép" thay cho menu chép của hệ thống).

/** Màn đọc / trình phát được sửa gì ở thiết bị này. `editing`: false ở thiết bị điều khiển từ xa (sửa từng câu / mở Studio không có ở đó).
 *  `teachWords`: dạy giọng đọc một từ (PUT readings, máy tính cho cả thiết bị từ xa có quyền sửa) - mặc định theo `editing`.
 *  `onOpenStudioScript`: máy tính, cuốn có xưởng - mở đúng câu ở tab Kịch bản của Studio, nơi sửa thật. */
export interface SentenceEditing {
  editing?: boolean;
  teachWords?: boolean;
  onOpenStudioScript?: (bookId: string, chapterId: number, stableId: string) => void;
}

// Thanh nổi dưới câu đang chọn: điện thoại chỉ còn biểu tượng cho nút phụ (nhãn vẫn cho trình đọc màn hình) để cả thanh nằm MỘT hàng, không che chữ đang đọc.
const BAR_LABEL = "max-sm:sr-only";
const BAR_BUTTON = "inline-flex min-h-[48px] items-center gap-2 rounded-full bg-panel px-4 py-2.5 text-sm font-semibold shadow-float ring-1 ring-line disabled:opacity-60";
const keepFocus = { onMouseDown: (event: { preventDefault: () => void }) => event.preventDefault() };

/** Ghi chú cho dấu trang vừa đặt (nút "Ghi chú" trên thông báo "Đã đặt dấu trang"). */
function BookmarkNoteDialog({ bookId, mark, onClose }: { bookId: string; mark: { id: string; quote: string } | null; onClose: () => void }) {
  const mutations = useListenMutations(bookId);
  const [note, setNote] = useState("");
  useEffect(() => setNote(""), [mark]);
  const save = () =>
    mutations.updateBookmark.mutate(
      { id: mark!.id, note: note.trim() },
      { onSuccess: onClose, onError: (error) => reportWriteFailure(error, "Chưa lưu được ghi chú") },
    );
  return (
    <Dialog open={mark !== null} onOpenChange={(open) => !open && onClose()} width="max-w-md" title="Ghi chú cho dấu trang" description={mark ? `“${excerpt(mark.quote)}”` : undefined}>
      <form
        className="space-y-3"
        onSubmit={(event) => {
          event.preventDefault();
          if (note.trim()) save();
        }}
      >
        <textarea
          autoFocus
          value={note}
          maxLength={500}
          rows={3}
          onChange={(event) => setNote(event.target.value)}
          aria-label="Ghi chú"
          placeholder="vd Đoạn hay, nghe lại"
          className="w-full rounded-lg border border-line bg-bg px-3 py-2 text-sm outline-none focus:border-focus"
        />
        <div className="flex justify-end gap-2">
          <Button size="sm" variant="ghost" type="button" onClick={onClose}>
            Thôi
          </Button>
          <Button size="sm" variant="primary" type="submit" disabled={!note.trim()} loading={mutations.updateBookmark.isPending}>
            Lưu ghi chú
          </Button>
        </div>
      </form>
    </Dialog>
  );
}

/** Câu đang chọn và mọi việc làm được với nó. Đổi chương (hay cuốn) thì bỏ câu / chữ đang chọn - câu số 3 của chương trước không phải câu số 3
 *  của chương này (soát a70). `onListen`: nghe từ một câu (nút "Nghe từ câu này"). */
export function useSentenceMenu({
  bookId,
  book,
  chapter,
  script,
  editing = true,
  teachWords = editing,
  onOpenStudioScript,
  canListen,
  onListen,
}: SentenceEditing & {
  bookId: string;
  book: ListenBook | undefined;
  chapter: ListenChapter | undefined;
  script: Script | undefined;
  canListen: boolean;
  onListen: (sentence: number) => void;
}) {
  const mutations = useListenMutations(bookId);
  const chapterId = chapter?.id ?? 0;
  // Chương chỉ có chữ (sách nhập từ EPUB / DOCX / PDF / TXT, chưa có audio): đọc được, không sửa từng câu; máy có giọng thì giọng máy đọc.
  const textOnly = chapter?.state === "text";
  // Sửa một câu (docs/EDITING.md, P2a): cuốn không có xưởng ghi ý muốn chờ Studio ngay tại đây; cuốn có xưởng sửa ở Studio; cuốn
  // nghe thẳng từ máy khác hay chưa cài Studio: nút vẫn hiện, mờ đi, kèm lý do.
  const lineEdit = editing && !textOnly ? lineEditing(book?.capabilities) : null;
  const wishes = useWishes(bookId, lineEdit?.mode === "wish");
  // Dấu "đang chờ Studio" sau câu: một hàm cố định tới khi danh sách việc chờ đổi - văn bản vẽ lại theo từng đoạn (ReadAlongText), hàm mới
  // mỗi lần vẽ thì đoạn nào cũng vẽ lại.
  const waitingMark = useCallback(
    (segment: ScriptSegment) => (segment.stableId && wishes.data?.lines[segment.stableId] ? <WaitingMark /> : null),
    [wishes.data],
  );
  // "Đọc từ này là…": cuốn chỉ có chữ của máy này - giữ (hay bấm chuột phải) một chữ để dạy giọng đọc cách đọc nó cho cả cuốn.
  // Thiết bị chỉ được nghe thì không dạy giọng đọc từ đây (máy tính từ chối): việc ấy ở máy tính, trang sách có dòng nói rõ.
  const { data: appInfo } = useAppInfo();
  const readingEdit = canTeachWords({ allowed: teachWords, textOnly, canEdit: canEditBook(book), listenOnly: Boolean(appInfo?.listenOnly) });
  const [readingWord, setReadingWord] = useState<string | null>(null);
  // Câu của hộp "Đọc từ này là…" mở từ nút “Sửa cách đọc” (cho chọn từ trong câu); giữ một chữ thì cũng kèm câu để đổi sang từ khác.
  const [readingSentence, setReadingSentence] = useState("");
  const [readingAt, setReadingAt] = useState<number | undefined>(undefined); // thứ tự chữ vừa giữ trong câu ấy
  // Cuốn có audio: giữ một chữ mở hộp “Sửa câu này” thẳng ở bước sửa cách đọc từ ấy (cùng việc với cuốn chỉ có chữ).
  const [wishWord, setWishWord] = useState<string | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [selectedWord, setSelectedWord] = useState(-1);
  // Hộp "Sửa câu này" giữ đúng câu đã mở (chương + bản chữ lúc mở), không theo giọng sang chương sau (follow.lineToEdit).
  const [editingLine, setEditingLine] = useState<LineToEdit<Script> | null>(null);
  const [noting, setNoting] = useState<{ id: string; quote: string } | null>(null);
  const editable = Boolean(lineEdit || readingEdit);

  useEffect(() => {
    setSelected(null);
    setSelectedWord(-1);
  }, [bookId, chapterId]);

  /** Chọn một câu (và chữ đã bấm trong câu, -1 nếu không biết) để hiện thanh việc của nó. */
  const select = useCallback((sentence: number | null, word = -1) => {
    setSelected(sentence);
    setSelectedWord(sentence === null ? -1 : word);
  }, []);

  // Giữ một chữ (điện thoại) / bấm chuột phải (máy tính): sửa cách đọc chữ ấy - cuốn chỉ có chữ lưu thẳng, cuốn có audio ghi thành việc chờ máy
  // làm sách. Loại sách không sửa chữ được ở đây: chọn câu, thanh việc có "Chép" (thay menu chép / chia sẻ của hệ thống).
  const wordMenu = (sentence: number, word: number) => {
    const text = script?.segments[sentence]?.text ?? "";
    if (readingEdit) {
      setReadingSentence(text);
      setReadingAt(word);
      setReadingWord(wordOf(text, word) || null);
      return;
    }
    const held = wordOf(text, word);
    if (lineEdit?.mode === "wish" && held && script) {
      setWishWord(held);
      setEditingLine(lineToEdit(script, sentence));
      return;
    }
    select(sentence, word);
  };

  // Dấu trang theo câu: giữ vị trí câu + ~60 chữ đầu câu; chương có audio thì thêm giờ bắt đầu câu để trình phát cũng tới được.
  const bookmarkSentence = (sentence: number) => {
    const segment = script?.segments[sentence];
    if (!segment) return;
    mutations.addBookmark.mutate(
      { chapterId, seconds: segment.start ?? 0, note: "", sentence: { index: sentence, quote: segment.text,
        anchor: makeAnchor(script!.segments.map((part) => part.text), sentence, 0) } },
      {
        onSuccess: (mark) => {
          select(null);
          if (mark.existing) {
            toast("Đã có dấu trang ở câu này", { id: "bookmark-existing", description: excerpt(segment.text) });
            return;
          }
          toast.success("Đã đặt dấu trang", {
            id: "bookmark",
            duration: 8000,
            description: excerpt(segment.text),
            action: { label: "Ghi chú", onClick: () => setNoting({ id: mark.id, quote: segment.text }) },
            cancel: { label: "Hoàn tác", onClick: () => mutations.deleteBookmark.mutate(mark.id) },
          });
        },
        onError: (error) => reportWriteFailure(error, "Chưa đặt được dấu trang"),
      },
    );
  };
  const copySentence = (sentence: number) => {
    const text = script?.segments[sentence]?.text ?? "";
    void navigator.clipboard.writeText(text).then(
      () => {
        select(null);
        toast.success("Đã chép câu", { id: "copied", description: excerpt(text) });
      },
      () => toast.error("Chưa chép được"),
    );
  };

  const bar: ReactNode =
    selected !== null && script ? (
      <div className="flex flex-col items-center gap-2">
        <div className="pointer-events-auto flex flex-wrap items-center justify-center gap-2">
          {canListen && (
            <button
              type="button"
              onClick={() => onListen(selected)}
              {...keepFocus}
              className="inline-flex min-h-[48px] items-center gap-2 rounded-full bg-fg px-5 py-2.5 text-sm font-semibold text-bg shadow-float"
            >
              <Play className="size-4" fill="currentColor" strokeWidth={0} /> <span className="sm:hidden">Nghe từ đây</span>
              <span className="max-sm:hidden">Nghe từ câu này</span>
            </button>
          )}
          <button type="button" onClick={() => bookmarkSentence(selected)} {...keepFocus} className={BAR_BUTTON}>
            <BookmarkPlus className="size-4" /> <span className={BAR_LABEL}>Đặt dấu trang ở câu này</span>
          </button>
          {readingEdit && (
            <button
              type="button"
              onClick={() => {
                const text = script.segments[selected]?.text ?? "";
                setReadingSentence(text);
                setReadingAt(selectedWord >= 0 ? selectedWord : undefined);
                setReadingWord(selectedWord >= 0 ? wordOf(text, selectedWord) : "");
              }}
              {...keepFocus}
              className={BAR_BUTTON}
            >
              <Pencil className="size-4" /> <span className={BAR_LABEL}>Sửa cách đọc</span>
            </button>
          )}
          {lineEdit && (
            <button
              type="button"
              disabled={lineEdit.mode === "blocked"}
              onClick={() => {
                const stableId = script.segments[selected]?.stableId;
                if (lineEdit.mode === "wish") setEditingLine(lineToEdit(script, selected));
                else if (lineEdit.mode === "studio" && stableId) onOpenStudioScript?.(bookId, chapterId, stableId);
              }}
              {...keepFocus}
              className={BAR_BUTTON}
            >
              <Pencil className="size-4" /> <span className={BAR_LABEL}>{lineEdit.mode === "studio" ? "Sửa trong Studio" : "Sửa câu này"}</span>
            </button>
          )}
          <button type="button" onClick={() => copySentence(selected)} {...keepFocus} className={BAR_BUTTON}>
            <Copy className="size-4" /> <span className={BAR_LABEL}>Chép câu</span>
          </button>
          <button type="button" aria-label="Bỏ chọn câu" onClick={() => select(null)} {...keepFocus} className={cn(BAR_BUTTON, "px-3")}>
            <X className="size-4" />
          </button>
        </div>
        {lineEdit?.mode === "blocked" && (
          <p className="pointer-events-auto max-w-sm rounded-xl bg-panel px-3 py-1.5 text-center text-xs text-fg-2 shadow-float ring-1 ring-line">
            Sửa câu này: {lineEdit.note}
          </p>
        )}
      </div>
    ) : null;

  const dialogs: ReactNode = (
    <>
      {readingEdit && <WordReadingDialog bookId={bookId} word={readingWord} sentence={readingSentence} wordIndex={readingAt} onClose={() => setReadingWord(null)} />}
      {lineEdit?.mode === "wish" && book && script && (
        <LineWishDialog
          book={book}
          script={editingLine?.script ?? script}
          segmentIndex={editingLine?.index ?? null}
          wishes={wishes.data}
          word={wishWord}
          onClose={() => {
            setEditingLine(null);
            setWishWord(null);
          }}
        />
      )}
      <BookmarkNoteDialog bookId={bookId} mark={noting} onClose={() => setNoting(null)} />
    </>
  );

  return { lineEdit, readingEdit, editable, waitingMark, selected, select, wordMenu, bar, dialogs };
}
