import type { ListenChapter, Script, ScriptSegment } from "./model";

// Chữ của một chương CHỈ-CÓ-CHỮ (sách giai đoạn 0, `texts/<mã>.txt` - docs/LISTEN_ANYTHING.md mục 1) thành hình dạng mà màn đọc
// (ReaderScreen) đã đọc được: các đoạn như một kịch bản không có mốc thời gian (`timed: false`). Máy tính và điện thoại dùng
// chung hàm này - máy chủ / plugin chỉ đưa chữ ra, không dựng kịch bản giả.

const NEWLINES = /\r\n?/g;
const BLANK_LINE = /\n[ \t ]*\n/;
const SPACES = /\s+/g;

function squeeze(text: string): string {
  return text.replace(SPACES, " ").trim();
}

/** Mã chú thích của trang web chép lẫn vào chữ ("[note54360]") - không phải chữ truyện, đọc lên là đọc "note năm bốn ba sáu không". Đúng mẫu của máy tính
 *  (text_processing.INLINE_REFERENCE_MARKER_PATTERN, bước chuẩn hoá trước khi tách câu); "[Note]" không số, "[1]" giữ nguyên. Kotlin: Paragraphs.withoutNoteMarkers. */
const NOTE_MARKER = /\[\s*note\d+\s*\]/gi;

export function withoutNoteMarkers(text: string): string {
  return text.replace(NOTE_MARKER, "");
}

/** Dấu kết câu ở cuối dòng: dòng như vậy là trọn một đoạn, không phải dòng bị máy dàn trang bẻ giữa câu. */
const SENTENCE_END = /[.!?…"”»’)」』】。！？~–—]$/;
/** Dài hơn mọi khổ dòng của máy dàn trang: chắc chắn là trọn một đoạn. */
const WHOLE_LINE = 200;

/** Một đoạn chữ thường (không có dòng ngăn cảnh): các dòng của một khối giữa hai dòng trống, hay phần của khối giữa hai dòng ngăn cảnh. Bị bẻ giữa
 *  câu thì nối lại thành một đoạn; còn nếu đa số dòng (trừ dòng cuối) kết thúc bằng dấu kết câu, hay có dòng dài hơn mọi khổ dòng, thì đó là file
 *  mỗi dòng một đoạn chỉ có vài dòng trống (vd sau tên chương) - mỗi dòng một đoạn, để cả chương không dồn thành một đoạn khổng lồ (khi đọc to,
 *  mỗi đoạn là một đoạn âm thanh). */
function textParagraphs(lines: string[]): string[] {
  if (lines.length < 2) return lines;
  const ended = lines.slice(0, -1).filter((line) => SENTENCE_END.test(line)).length;
  return ended * 2 > lines.length - 1 || lines.some((line) => line.length > WHOLE_LINE) ? lines : [lines.join(" ")];
}

/** Một đoạn của chương: chữ, và có phải dòng ngăn cảnh không ([isSceneBreakLine], kể cả luật "đứng riêng một đoạn"). */
export interface Paragraph {
  text: string;
  sceneBreak: boolean;
}

const plain = (texts: string[]): Paragraph[] => texts.map((text) => ({ text, sceneBreak: false }));

/** Các đoạn của một khối giữa hai dòng trống. Dòng ngăn cảnh ("***", "◆") luôn là một đoạn riêng - không nối vào câu trước / sau - để chỗ đổi cảnh
 *  còn là một chỗ của chương (xem [sceneBreakGaps]); phần chữ ở hai bên nó chia như [textParagraphs]. Khối chỉ có MỘT dòng là dòng "đứng riêng". */
function blockParagraphs(block: string): Paragraph[] {
  const lines = block.split("\n").map(squeeze).filter(Boolean);
  const out: Paragraph[] = [];
  let run: string[] = [];
  for (const line of lines) {
    if (!isSceneBreakLine(line, lines.length === 1)) {
      run.push(line);
      continue;
    }
    out.push(...plain(textParagraphs(run)), { text: line, sceneBreak: true });
    run = [];
  }
  out.push(...plain(textParagraphs(run)));
  return out;
}

// ---- dòng ngăn cảnh -----------------------------------------------------------------------------------------------------------------
// Bản TS của text_processing.is_scene_break_line (Kotlin: Paragraphs.isSceneBreakLine); cả ba chạy cùng bộ ví dụ tests/fixtures/scene_break/cases.json.
// Dòng chỉ gồm ký hiệu ngăn cảnh không đọc lên: người nghe nghe một quãng lặng SCENE_BREAK_MS thay cho nó (sách nói của Studio cũng nghỉ chừng ấy).

/** Quãng lặng ở chỗ đổi cảnh (ms) - text_processing.SCENE_BREAK_MS. */
export const SCENE_BREAK_MS = 1500;
/** Ký hiệu kiểu đường kẻ: một dấu đơn lẻ có thể là dấu câu / gạch thoại / tiêu đề markdown, nên cần từ SCENE_BREAK_MIN_RULE_GLYPHS dấu. */
export const SCENE_BREAK_RULE_GLYPHS = "*~-=_#+·•‧・—–―‒─━═┄┈╌";
export const SCENE_BREAK_MIN_RULE_GLYPHS = 3;
/** ... trừ khi dòng đứng riêng một đoạn: khi ấy một-hai dấu trong nhóm này cũng đủ. "—" / "–" không vào nhóm: một đoạn chỉ có "—" có thể là lời thoại im lặng. */
export const SCENE_BREAK_ALONE_GLYPHS = "*~-=#";
/** Ký hiệu trang trí: một dấu đã đủ. Không có dấu chấm, "…", ngoặc, nháy hay ?! - dòng "..." hay dòng chỉ có ngoặc kép không phải ngăn cảnh. */
export const SCENE_BREAK_ORNAMENT_GLYPHS = "◆◇◈○●◎□■▪▫▲△▽▼★☆✦✧✱✲✶✷✻✽❖❀✿❁※⁂⁕⋆◦♦♢◊⸻§";
export const SCENE_BREAK_MAX_GLYPHS = 40;

/** Dòng chỉ có ký hiệu ngăn cảnh ("***", "* * *", "◆", "◇◇◇", "———", "~~~", "＊＊＊"), không chữ không số. `alone`: dòng đứng riêng một đoạn (khối giữa
 *  hai dòng trống chỉ có dòng này) - khi ấy "*", "-", "--" cũng là ngăn cảnh (text_processing.is_scene_break_line). */
export function isSceneBreakLine(line: string, alone = false): boolean {
  const glyphs = Array.from(line.normalize("NFKC")).filter((char) => !SPACE.test(char));
  if (!glyphs.length || glyphs.length > SCENE_BREAK_MAX_GLYPHS) return false;
  const rule = glyphs.filter((char) => SCENE_BREAK_RULE_GLYPHS.includes(char)).length;
  if (rule + glyphs.filter((char) => SCENE_BREAK_ORNAMENT_GLYPHS.includes(char)).length !== glyphs.length) return false;
  if (rule === 0) return true;
  if (alone && glyphs.every((char) => SCENE_BREAK_ALONE_GLYPHS.includes(char))) return true;
  return glyphs.length >= SCENE_BREAK_MIN_RULE_GLYPHS;
}

const SPEAKABLE = /[\p{L}\p{N}]/u;
const SPACE = /\s/u;

/** Đoạn có chữ hay số để đọc lên (không phải "* * *", "…"). */
export function isSpeakable(text: string): boolean {
  return SPEAKABLE.test(text);
}

/** Quãng lặng (ms) của từng đoạn (`sceneBreak` của đoạn do [splitParagraphs] đặt; đoạn dựng tay không có thì xét theo chữ): chỉ dòng ngăn cảnh ĐẦU của một chuỗi dòng ngăn cảnh liền nhau có quãng lặng, và chỉ khi có đoạn đọc được ở cả
 *  trước lẫn sau nó (đầu chương hay cuối chương không có cảnh nào để ngăn; hai dòng "***" liền nhau lặng một lần) - đúng như segment_chapter_text
 *  đặt `break_ms` lên câu trước dòng ngăn. Các đoạn còn lại 0. Dòng "..." (không đọc được nhưng không phải ngăn cảnh) không cắt chuỗi. */
export function sceneBreakGaps(items: readonly { text: string; sceneBreak?: boolean }[]): number[] {
  const gaps = items.map(() => 0);
  let spoken = false;
  let first = -1;
  items.forEach(({ text, sceneBreak }, index) => {
    if (sceneBreak ?? isSceneBreakLine(text)) {
      if (spoken && first < 0) first = index;
    } else if (isSpeakable(text)) {
      if (first >= 0) gaps[first] = SCENE_BREAK_MS;
      first = -1;
      spoken = true;
    }
  });
  return gaps;
}

/** Các đoạn của chương. File có dòng trống ngăn đoạn: đoạn là phần giữa hai dòng trống, xuống dòng trong đoạn là dòng bị bẻ của máy
 *  dàn trang (nối bằng dấu cách) - trừ khối mà các dòng là trọn đoạn ([textParagraphs]). File KHÔNG có dòng trống nào (TXT mỗi dòng
 *  một đoạn): mỗi dòng là một đoạn. Kèm cờ dòng ngăn cảnh; với luật "đứng riêng" (text_processing: đoạn = giữa hai dòng trống) file không có dòng trống
 *  là MỘT đoạn nên chỉ khi cả file có đúng một dòng thì dòng ấy mới đứng riêng. */
export function splitParagraphs(text: string): Paragraph[] {
  const clean = withoutNoteMarkers(text).replace(NEWLINES, "\n");
  if (BLANK_LINE.test(clean)) return clean.split(BLANK_LINE).flatMap(blockParagraphs);
  const lines = clean.split("\n").map(squeeze).filter(Boolean);
  return lines.map((line) => ({ text: line, sceneBreak: isSceneBreakLine(line, lines.length === 1) }));
}

export function paragraphsOf(text: string): string[] {
  return splitParagraphs(text).map((paragraph) => paragraph.text);
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
      const shown = squeeze(withoutNoteMarkers(line)); // `skip` ghi từ chữ đã bỏ mã chú thích (BookImport.creditLines)
      if (!shown || seen >= CREDIT_WINDOW) return true;
      seen += 1;
      return !skip.includes(shown);
    })
    .join("\n");
}

/** Màn đọc của một chương chỉ có chữ. Đoạn đầu trùng tên chương là tiêu đề (file nguồn của Studio mở đầu bằng tên chương). `skip`: dòng
 *  người nghe bỏ khỏi phần đọc ([withoutLines]). */
export function textScript(chapterId: number, title: string, text: string, skip?: readonly string[]): Script {
  const paragraphs = splitParagraphs(withoutLines(text, skip));
  const heading = squeeze(title);
  const segments: ScriptSegment[] = paragraphs.map(({ text: paragraph, sceneBreak }, index) => ({
    id: index,
    paragraph: index,
    text: paragraph,
    kind: index === 0 && paragraph === heading ? "heading" : "narration",
    speaker: "",
    start: null,
    end: null,
    status: "text",
    ...(sceneBreak ? { sceneBreak } : {}),
  }));
  return { chapterId, title, timed: false, duration: 0, segments };
}

const sameLines = (a: readonly string[] | undefined, b: readonly string[] | undefined) =>
  (a?.length ?? 0) === (b?.length ?? 0) && (a ?? []).every((line, i) => line === b![i]);

/** Hàng đợi của trình phát giữ bản chương lúc nạp sách; người nghe tích / bỏ tích một dòng ghi công SAU ĐÓ (trang sách) thì `skip` của hàng đợi cũ đi:
 *  giọng đọc và kịch bản dựng sẵn cho chương kế vẫn lấy theo nó. Trả hàng đợi với `skip` mới nhất của sách (`fresh`); không có gì đổi thì trả đúng
 *  hàng đợi cũ (để không dựng lại gì). */
export function withFreshSkips(queue: ListenChapter[], fresh: readonly ListenChapter[] | undefined): ListenChapter[] {
  if (!fresh) return queue;
  const latest = new Map(fresh.map((chapter) => [chapter.id, chapter.skip]));
  if (queue.every((chapter) => !latest.has(chapter.id) || sameLines(chapter.skip, latest.get(chapter.id)))) return queue;
  return queue.map((chapter) => {
    if (!latest.has(chapter.id) || sameLines(chapter.skip, latest.get(chapter.id))) return chapter;
    const { skip: _old, ...rest } = chapter;
    const skip = latest.get(chapter.id);
    return skip?.length ? { ...rest, skip } : rest;
  });
}
