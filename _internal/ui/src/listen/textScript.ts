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

/** Các đoạn của chương. File có dòng trống ngăn đoạn: đoạn là phần giữa hai dòng trống, xuống dòng trong đoạn là dòng bị bẻ của máy
 *  dàn trang (nối bằng dấu cách). File KHÔNG có dòng trống nào (TXT mỗi dòng một đoạn): mỗi dòng là một đoạn. */
export function paragraphsOf(text: string): string[] {
  const clean = text.replace(NEWLINES, "\n");
  const blocks = BLANK_LINE.test(clean) ? clean.split(/\n[ \t ]*\n/) : clean.split("\n");
  return blocks.map(squeeze).filter(Boolean);
}

/** Màn đọc của một chương chỉ có chữ. Đoạn đầu trùng tên chương là tiêu đề (file nguồn của Studio mở đầu bằng tên chương). */
export function textScript(chapterId: number, title: string, text: string): Script {
  const paragraphs = paragraphsOf(text);
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
