import type { Script, ScriptSegment } from "./model";

// Chữ của một chương CHỈ-CÓ-CHỮ (sách giai đoạn 0, `texts/<mã>.txt` - docs/LISTEN_ANYTHING.md mục 1) thành hình dạng mà màn đọc
// (ReaderScreen) đã đọc được: các đoạn như một kịch bản không có mốc thời gian (`timed: false`). Máy tính và điện thoại dùng
// chung hàm này - máy chủ / plugin chỉ đưa chữ ra, không dựng kịch bản giả.

const NEWLINES = /\r\n?/g;
const BLANK_LINE = /\n[ \t ]*\n/;
const SPACES = /\s+/g;

function squeeze(text: string): string {
  return text.replace(SPACES, " ").trim();
}

/** Dấu kết câu ở cuối dòng: dòng như vậy là trọn một đoạn, không phải dòng bị máy dàn trang bẻ giữa câu. */
const SENTENCE_END = /[.!?…"”»’)」』】。！？~–—]$/;
/** Dài hơn mọi khổ dòng của máy dàn trang: chắc chắn là trọn một đoạn. */
const WHOLE_LINE = 200;

/** Các dòng của một khối giữa hai dòng trống: bị bẻ giữa câu thì nối lại thành một đoạn; còn nếu đa số dòng (trừ dòng cuối) kết thúc
 *  bằng dấu kết câu, hay có dòng dài hơn mọi khổ dòng, thì đó là file mỗi dòng một đoạn chỉ có vài dòng trống (vd sau tên chương) -
 *  mỗi dòng một đoạn, để cả chương không dồn thành một đoạn khổng lồ (khi đọc to, mỗi đoạn là một đoạn âm thanh). */
function blockParagraphs(block: string): string[] {
  const lines = block.split("\n").map(squeeze).filter(Boolean);
  if (lines.length < 2) return lines;
  const ended = lines.slice(0, -1).filter((line) => SENTENCE_END.test(line)).length;
  return ended * 2 > lines.length - 1 || lines.some((line) => line.length > WHOLE_LINE) ? lines : [lines.join(" ")];
}

/** Các đoạn của chương. File có dòng trống ngăn đoạn: đoạn là phần giữa hai dòng trống, xuống dòng trong đoạn là dòng bị bẻ của máy
 *  dàn trang (nối bằng dấu cách) - trừ khối mà các dòng là trọn đoạn ([blockParagraphs]). File KHÔNG có dòng trống nào (TXT mỗi dòng
 *  một đoạn): mỗi dòng là một đoạn. */
export function paragraphsOf(text: string): string[] {
  const clean = text.replace(NEWLINES, "\n");
  const blocks = BLANK_LINE.test(clean) ? clean.split(/\n[ \t ]*\n/) : clean.split("\n");
  return BLANK_LINE.test(clean) ? blocks.flatMap(blockParagraphs) : blocks.map(squeeze).filter(Boolean);
}

/** Số dòng có chữ đầu chương mà luật dòng ghi công xét (text_processing.CREDIT_WINDOW_LINES). */
const CREDIT_WINDOW = 6;

/** Chữ của chương trừ các dòng người nghe đã chọn bỏ khỏi phần đọc (lớp sửa `skip` - gợi ý dòng ghi công của bộ nhập sách). Chỉ xét
 *  6 dòng có chữ đầu chương, đúng chỗ luật tìm ra chúng. Chữ của sách không đổi: chỉ màn đọc và đọc to không thấy dòng ấy. Kotlin:
 *  Paragraphs.withoutLines - lõi đọc to của điện thoại phải chia ra đúng các đoạn như màn đọc. */
export function withoutLines(text: string, skip: readonly string[] | undefined): string {
  if (!skip?.length) return text;
  let seen = 0;
  return text
    .replace(NEWLINES, "\n")
    .split("\n")
    .filter((line) => {
      const shown = squeeze(line);
      if (!shown || seen >= CREDIT_WINDOW) return true;
      seen += 1;
      return !skip.includes(shown);
    })
    .join("\n");
}

/** Màn đọc của một chương chỉ có chữ. Đoạn đầu trùng tên chương là tiêu đề (file nguồn của Studio mở đầu bằng tên chương). `skip`: dòng
 *  người nghe bỏ khỏi phần đọc ([withoutLines]). */
export function textScript(chapterId: number, title: string, text: string, skip?: readonly string[]): Script {
  const paragraphs = paragraphsOf(withoutLines(text, skip));
  const heading = squeeze(title);
  const segments: ScriptSegment[] = paragraphs.map((paragraph, index) => ({
    id: index,
    paragraph: index,
    text: paragraph,
    kind: index === 0 && paragraph === heading ? "heading" : "narration",
    speaker: "",
    start: null,
    end: null,
    status: "text",
  }));
  return { chapterId, title, timed: false, duration: 0, segments };
}
