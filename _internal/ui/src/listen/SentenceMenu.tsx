import { useBackLayer } from "@/shared/backStack";
import { Copy, Pencil, Play, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { toast } from "@/shared/toast";
import { cn } from "@/shared/cn";
import { lineEditing } from "@/shared/capabilities";
import { useAppInfo } from "@/studio/data";
import { canEditBook } from "./EditBook";
import { lineToEdit, type LineToEdit } from "./follow";
import { useWishes, WaitingMark } from "./lineWishData";
import { lazyComponent } from "@/shared/lazyScreen";
import { canTeachWords, wordOf } from "./readings";
import type { ListenBook, ListenChapter, Script, ScriptSegment } from "./model";
import { WordReadingDialog } from "./WordReadings";
import { keepFocus } from "./menuSlot";

// Chọn một câu của văn bản đọc theo rồi làm gì với nó - MỘT chỗ cho màn Đọc (ReaderScreen) và tab "Đọc theo" của màn "Đang nghe" (PlayerViews):
// nghe từ câu ấy, chép, sửa cách đọc một từ (cuốn chỉ có chữ), sửa câu này (cuốn có audio). Giữ ngón tay / bấm chuột phải vào
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
/** Hộp "Sửa câu này" (kéo theo các bảng chọn của tab Kịch bản) ở chunk riêng: nạp khi trang đọc / Đọc theo mở, không trong gói đầu. */
const LineWishDialog = lazyComponent(() => import("./LineWishes").then((module) => module.LineWishDialog));

const BAR_LABEL = "max-sm:sr-only";
const BAR_BUTTON = "inline-flex min-h-[48px] min-w-[48px] items-center justify-center gap-2 rounded-control px-3 py-2.5 text-sm font-medium text-accent-text hover:bg-hover disabled:opacity-60";

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

  const copySentence = (sentence: number) => {
    const text = script?.segments[sentence]?.text ?? "";
    void navigator.clipboard.writeText(text).then(
      () => {
        select(null);
        toast.success("Đã chép câu", { id: "copied" });
      },
      () => toast.error("Chưa chép được"),
    );
  };

  const barBox = useRef<HTMLDivElement>(null);
  useBackLayer(selected !== null, () => select(null), barBox);
  const bar: ReactNode =
    selected !== null && script ? (
      <div ref={barBox} className="flex flex-col items-center gap-2">
        <div className="pointer-events-auto flex flex-wrap items-center justify-center gap-2 rounded-cover bg-panel p-1 shadow-float ring-1 ring-line">
          {canListen && (
            <button
              type="button"
              onClick={() => onListen(selected)}
              {...keepFocus}
              className={BAR_BUTTON}
            >
              <Play className="size-4" fill="currentColor" strokeWidth={0} /> <span className="sm:hidden">Nghe từ đây</span>
              <span className="max-sm:hidden">Nghe từ câu này</span>
            </button>
          )}
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
          <p className="pointer-events-auto max-w-sm rounded-cover bg-panel px-3 py-1.5 text-center text-xs text-fg-2 shadow-float ring-1 ring-line">
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
    </>
  );

  return { lineEdit, readingEdit, editable, waitingMark, selected, select, wordMenu, bar, dialogs };
}
