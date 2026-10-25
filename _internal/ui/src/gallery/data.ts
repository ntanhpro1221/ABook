import type { Cast, CastMember, ListenBook, ListenChapter, ListeningSession, ListeningState, NightSession, Script, ScriptSegment, SeriesLink } from "@/listen/model";
import type { LocalBook, ManifestChapter } from "@/android/plugins";
import type { ImportPreview, ImportPreviewChapter } from "@/listen/textImport";
import { bookProgress, textBookProgress } from "@/android/progress";
import { NOW_SECONDS } from "./clock";

// Thư viện giả của phòng trưng bày: mười cuốn tiếng Việt tự đặt tên, văn bản tự viết (không chép truyện thật). Một nguồn duy nhất,
// hai hình dạng: `listenBook` cho máy chủ giả của máy tính (như webui/listen_view.py), `localBook` cho lõi giả của điện thoại (book.json).

const HOUR = 3600;
const DAY = 24 * HOUR;
const ago = (seconds: number) => NOW_SECONDS - seconds;

export interface GalleryChapter {
  id: number;
  title: string;
  subtitle: string;
  duration: number;
  available: boolean;
  /** Chương chỉ có chữ (sách nhập từ EPUB). */
  text?: boolean;
  part?: number;
}

export interface GalleryBook {
  id: string;
  title: string;
  author: string;
  narrator: string;
  chapters: GalleryChapter[];
  /** Máy chủ: dự án đang chạy (đang làm), hay tạm dừng (`pauseReason`). */
  producing?: boolean;
  pauseReason?: "battery" | "listener" | null;
  /** Ước lượng tới chương đầu (thẻ "Đang làm · chương đầu sau khoảng X"). */
  eta?: { phase: string; seconds: number } | null;
  imported?: boolean;
  /** Điện thoại: sách trên máy tính chưa tải (nghe thẳng). */
  streamed?: boolean;
  series?: SeriesLink | null;
  cover?: { file: string; color: string } | null;
  addedAt: number;
  state: ListeningState;
}

/** Tên chương: lấy lần lượt từ danh sách, hết thì tự đánh số. */
function chapters(count: number, names: string[], options: { available?: number; seed?: number; text?: boolean } = {}): GalleryChapter[] {
  const available = options.available ?? count;
  let seed = options.seed ?? 7;
  return Array.from({ length: count }, (_, index) => {
    seed = (seed * 9301 + 49297) % 233280;
    const duration = Math.round(1180 + (seed / 233280) * 1500);
    return {
      id: index + 1,
      title: `Chương ${index + 1}`,
      subtitle: names[index] ?? "",
      duration: index < available ? duration : 0,
      available: !options.text && index < available,
      text: options.text,
    };
  });
}

/** Trạng thái nghe: đã nghe hết `done` chương đầu, đang dở chương kế ở `seconds`. */
function listening(book: { chapters: GalleryChapter[] }, done: number, seconds: number, at: number, extra: Partial<ListeningState> = {}): ListeningState {
  const chapterStates: ListeningState["chapters"] = {};
  book.chapters.slice(0, done).forEach((chapter, index) => {
    chapterStates[String(chapter.id)] = { heard: chapter.duration, done: true, duration: chapter.duration, at: at - (done - index) * DAY };
  });
  const current = book.chapters[done];
  if (current && seconds > 0) chapterStates[String(current.id)] = { heard: seconds, done: false, duration: current.duration, at };
  return {
    chapters: chapterStates,
    ...(current ? { last: { chapterId: current.id, seconds, at } } : {}),
    updatedAt: at,
    ...extra,
  };
}

const FOG = [
  "Thành phố không có bình minh", "Người đưa thư lúc nửa đêm", "Những ô cửa đóng kín", "Chiếc chìa khoá bằng đồng", "Tháp chuông phía bắc",
  "Bức thư không người nhận", "Tiếng còi tàu trên sông", "Ngôi chợ dưới chân cầu", "Kẻ bán đèn lồng", "Bản đồ vẽ tay", "Đêm không trăng",
  "Lời hẹn ở bến phà", "Mưa trên mái tôn", "Cánh cửa thứ bảy", "Con mèo màu tro", "Gương mặt trong sương",
];

function fogVolume(volume: number, available = 16): GalleryChapter[] {
  return chapters(16, FOG, { seed: volume * 13, available });
}

const fog1Chapters = fogVolume(1);
const fog2Chapters = fogVolume(2);
const fog3Chapters = fogVolume(3);
const lighthouseChapters = chapters(18, ["Hòn đảo cuối bản đồ", "Ngọn đèn thứ nhất", "Người khách đi thuyền nan", "Sổ nhật ký phủ muối", "Bão tháng Chín",
  "Những con hải âu", "Ánh sáng không tắt", "Tín hiệu từ đất liền", "Cuộc gọi lúc ba giờ sáng", "Bậc thang xoắn ốc"], { seed: 3 });
const kapokChapters = chapters(12, ["Tháng Ba về", "Con đò ngang", "Chợ phiên đầu làng", "Lá thư của chị", "Mùa nước nổi", "Đám cưới bên sông"], { seed: 5 });
const familyChapters = chapters(10, ["Ngôi nhà ba gian", "Ông nội", "Giỗ đầu", "Cây khế sau vườn", "Những người con đi xa"], { seed: 9 });
const hourglassChapters = chapters(24, ["Cát chảy ngược", "Người thợ thổi thuỷ tinh", "Ngày thứ một trăm", "Căn phòng không cửa sổ", "Hai chiếc bóng"], { seed: 11, available: 5 });
const starsChapters = chapters(30, ["Kính viễn vọng cũ", "Sao Hôm", "Đêm trên đồi cát", "Người vẽ trời", "Chòm sao thứ mười ba", "Ngọn núi không tên",
  "Trạm khí tượng bỏ hoang", "Mưa sao băng", "Bức điện cuối cùng"], { seed: 17, available: 9 });
const atticChapters = chapters(14, ["Tiệm sách trên gác xép", "Cuốn sổ bìa xanh", "Khách quen ngày thứ Năm", "Mùi giấy cũ", "Bức tranh treo ngược",
  "Người không mua sách", "Một buổi chiều mưa"], { seed: 19, text: true });
const cloudChapters = chapters(8, ["Bản Mây", "Ruộng bậc thang", "Ông lão chăn dê", "Chợ tình", "Đường về"], { seed: 23 });
const winterChapters = chapters(12, ["Thư thứ nhất"], { seed: 29, available: 0 });

const fog1: GalleryBook = {
  id: "suong-mu-1", title: "Thành Phố Sương Mù · Tập 1", author: "Lâm Hạ Vy", narrator: "Ngọc Lan", chapters: fog1Chapters,
  cover: { file: "covers/suong-mu-1.svg", color: "#36506b" }, addedAt: ago(62 * DAY),
  state: { ...listening({ chapters: fog1Chapters }, 16, 0, ago(9 * DAY)), finished: true, finishedAt: ago(9 * DAY) },
};

const fog2: GalleryBook = {
  id: "suong-mu-2", title: "Thành Phố Sương Mù · Tập 2", author: "Lâm Hạ Vy", narrator: "Ngọc Lan", chapters: fog2Chapters,
  cover: { file: "covers/suong-mu-2.svg", color: "#4b3f6b" }, addedAt: ago(30 * DAY),
  state: listening({ chapters: fog2Chapters }, 3, 734, ago(40 * 60), { rate: 1.15 }),
};

const fog3: GalleryBook = {
  id: "suong-mu-3", title: "Thành Phố Sương Mù · Tập 3", author: "Lâm Hạ Vy", narrator: "Ngọc Lan", chapters: fog3Chapters,
  cover: { file: "covers/suong-mu-3.svg", color: "#2f5d58" }, addedAt: ago(2 * DAY),
  state: { chapters: {} },
};

const lighthouse: GalleryBook = {
  id: "hai-dang", title: "Người Gác Hải Đăng Cuối Cùng", author: "Trần Vĩnh Khang", narrator: "Quang Minh", chapters: lighthouseChapters,
  addedAt: ago(45 * DAY), state: listening({ chapters: lighthouseChapters }, 6, 1310, ago(2 * DAY + 3 * HOUR)),
};

const kapok: GalleryBook = {
  id: "hoa-gao", title: "Mùa Hoa Gạo Bên Sông", author: "Nguyễn Thị Diệu Linh", narrator: "Mai Anh", chapters: kapokChapters,
  cover: { file: "covers/hoa-gao.svg", color: "#8a3b2e" }, addedAt: ago(20 * DAY), state: listening({ chapters: kapokChapters }, 1, 402, ago(5 * DAY)),
};

const family: GalleryBook = {
  id: "nha-ho-do", title: "Chuyện Nhà Họ Đỗ", author: "Đỗ Minh Triết", narrator: "Hữu Phước", chapters: familyChapters, addedAt: ago(120 * DAY),
  state: { ...listening({ chapters: familyChapters }, 10, 0, ago(31 * DAY)), finished: true, finishedAt: ago(31 * DAY) },
};

const hourglass: GalleryBook = {
  id: "dong-ho-cat", title: "Ký Ức Của Chiếc Đồng Hồ Cát", author: "Phạm Gia Hân", narrator: "Thu Hà", chapters: hourglassChapters, producing: true,
  eta: { phase: "synthesis", seconds: 3 * HOUR + 20 * 60 }, addedAt: ago(3 * DAY), state: listening({ chapters: hourglassChapters }, 2, 95, ago(HOUR * 20)),
};

const stars: GalleryBook = {
  id: "vi-sao-lac", title: "Bản Đồ Những Vì Sao Lạc", author: "Vũ Hoàng Nam", narrator: "Tuấn Kiệt", chapters: starsChapters, producing: true,
  pauseReason: "battery", eta: { phase: "synthesis", seconds: 9 * HOUR }, addedAt: ago(8 * DAY), state: { chapters: {} },
};

const attic: GalleryBook = {
  id: "gac-xep", title: "Tiệm Sách Trên Gác Xép", author: "Hà Thanh Tâm", narrator: "", chapters: atticChapters, imported: true, addedAt: ago(6 * DAY),
  state: { chapters: {}, reading: { chapterId: 2, index: 4, at: ago(3 * DAY) } as ListeningState["reading"], updatedAt: ago(3 * DAY) },
};

const cloud: GalleryBook = {
  id: "lang-may", title: "Đường Về Làng Mây", author: "Lò Văn Sơn", narrator: "Mai Anh", chapters: cloudChapters, addedAt: ago(DAY), streamed: true,
  state: { chapters: {} },
};

const winter: GalleryBook = {
  id: "thu-mua-dong", title: "Mười Hai Bức Thư Gửi Mùa Đông", author: "Kiều Bích Ngọc", narrator: "Thu Hà", chapters: winterChapters, producing: true,
  eta: { phase: "analysis", seconds: 50 * 60 }, addedAt: ago(HOUR), state: { chapters: {} },
};

fog2.series = null;

export const BOOKS: GalleryBook[] = [fog2, lighthouse, hourglass, kapok, stars, attic, fog3, fog1, family, cloud, winter];

export function findBook(id: string): GalleryBook | undefined {
  return BOOKS.find((book) => book.id === id);
}

function listenChapters(book: GalleryBook): ListenChapter[] {
  return book.chapters.map((chapter, index) => ({
    id: chapter.id,
    index,
    title: chapter.title,
    subtitle: chapter.subtitle,
    fullTitle: chapter.subtitle ? `${chapter.title}: ${chapter.subtitle}` : chapter.title,
    duration: chapter.duration,
    available: chapter.available,
    audioVersion: chapter.available ? `v${chapter.id}` : "",
    part: chapter.part ?? null,
    state: chapter.text ? ("text" as const) : null,
  }));
}

const isComplete = (book: GalleryBook) => !book.producing && !book.imported && book.chapters.every((chapter) => chapter.available);

/** Hình dạng `/api/listen/library` + `/api/listen/books/<id>` của máy chủ máy tính. */
export function listenBook(book: GalleryBook, withChapters: boolean): ListenBook {
  const items = listenChapters(book);
  const available = items.filter((chapter) => chapter.available);
  const textOnly = Boolean(book.imported && book.chapters.every((chapter) => chapter.text));
  const complete = isComplete(book) || textOnly;
  return {
    id: book.id,
    title: book.title,
    remote: book.streamed ? { computer: "Máy phòng khách" } : false,
    author: book.author,
    narrator: book.narrator,
    duration: available.reduce((sum, chapter) => sum + chapter.duration, 0),
    chaptersTotal: items.length,
    chaptersAvailable: available.length,
    complete,
    producing: Boolean(book.producing),
    paused: !complete && !book.producing,
    pauseReason: book.producing ? book.pauseReason ?? null : null,
    imported: Boolean(book.imported),
    stage: textOnly ? "text" : null,
    studioProject: book.imported ? null : book.id,
    updatedAt: book.state.updatedAt ?? null,
    addedAt: book.addedAt,
    state: book.state,
    progress: textOnly ? textBookProgress(book.state, items) : bookProgress(book.state, available, complete),
    lastChapterTitle: items.find((chapter) => chapter.id === book.state.last?.chapterId)?.fullTitle ?? "",
    cover: book.cover ? { url: `./${book.cover.file}`, color: book.cover.color, width: 600, height: 900, version: 1 } : null,
    eta: book.eta ?? null,
    series: book.series ?? null,
    chapters: withChapters ? items : undefined,
    parts: [],
    records: [{ id: "r1", name: "Của tôi", active: true, createdAt: book.addedAt, updatedAt: book.state.updatedAt ?? null }],
    capabilities: { toolchain: true, workshop: !book.imported, link: false, sync: false, local: true },
    edits: 0,
    wishes: 0,
  };
}

/** Hình dạng book.json của sách trên điện thoại (EbookLibrary.localBooks / book). */
export function localBook(book: GalleryBook): LocalBook {
  const chapters: ManifestChapter[] = listenChapters(book).map((chapter) => ({
    id: chapter.id,
    index: chapter.index,
    title: chapter.title,
    subtitle: chapter.subtitle,
    fullTitle: chapter.fullTitle,
    duration: chapter.duration,
    available: chapter.available,
    file: chapter.available ? `audio/${String(chapter.id).padStart(3, "0")}.mp3` : null,
    size: Math.round(chapter.duration * 8000),
    script: chapter.available ? `scripts/${chapter.id}.json` : null,
    sha256: chapter.available ? `sha-${book.id}-${chapter.id}` : undefined,
    ...(chapter.state === "text" ? { state: "text" as const, text: `texts/${chapter.id}.txt` } : {}),
  }));
  const available = chapters.filter((chapter) => chapter.available);
  return {
    format: "abook-1",
    id: book.id,
    title: book.title,
    author: book.author,
    narrator: book.narrator,
    duration: available.reduce((sum, chapter) => sum + chapter.duration, 0),
    chaptersTotal: chapters.length,
    chaptersAvailable: available.length,
    complete: isComplete(book) || Boolean(book.imported),
    version: "1",
    chapters,
    parts: [],
    series: book.series ?? null,
    samples: [],
    cover: book.cover ? { file: book.cover.file, version: 1, color: book.cover.color, width: 600, height: 900 } : null,
    addedAt: book.addedAt,
    state: book.state,
    bytes: available.length * 14_000_000,
    streamed: book.streamed,
    studio: !book.imported,
    records: [{ id: "r1", name: "Của tôi", active: true, createdAt: book.addedAt, updatedAt: book.state.updatedAt ?? null }],
    capabilities: { toolchain: false, workshop: false, link: !book.imported, sync: !book.imported, local: true },
    edits: book.imported ? 2 : 0,
    wishes: 0,
    editsSync: { pending: 0, last: null },
  };
}

// --- Văn bản (tự viết) ---------------------------------------------------------------------------------------------

type Line = [kind: "narration" | "dialogue" | "thought", speaker: string, text: string];

const PASSAGE: Line[] = [
  ["narration", "", "Sương xuống từ lúc trời còn chưa tắt hẳn, phủ lên những mái ngói rêu một lớp trắng đục như sữa pha loãng."],
  ["narration", "", "Minh Khuê kéo cao cổ áo, men theo bức tường gạch cũ dẫn xuống bến sông."],
  ["dialogue", "Minh Khuê", "“Ông Tư ơi, ông còn thức không?”"],
  ["narration", "", "Cánh cửa gỗ kẽo kẹt mở ra một khe nhỏ, ánh đèn dầu vàng vọt hắt lên khuôn mặt nhăn nheo của người thợ sửa đồng hồ."],
  ["dialogue", "Ông Tư", "“Giờ này mà còn đi lang thang, cô không sợ sương nuốt mất à?”"],
  ["dialogue", "Minh Khuê", "“Cháu tìm được cái này trong ngăn kéo của mẹ.”"],
  ["narration", "", "Cô xoè bàn tay. Nằm giữa lòng bàn tay là một chiếc chìa khoá bằng đồng, răng cưa mòn vẹt, chuôi khắc hình một con cá chép."],
  ["narration", "", "Ông Tư nheo mắt nhìn rất lâu, rồi lặng lẽ lùi vào trong, ra hiệu cho cô bước theo."],
  ["thought", "Minh Khuê", "Ông ấy biết nó. Chắc chắn ông ấy biết."],
  ["narration", "", "Căn phòng nhỏ chật kín đồng hồ. Hàng chục chiếc kim cùng nhích một lúc, nghe như tiếng mưa rơi trên lá chuối."],
  ["dialogue", "Ông Tư", "“Ba mươi năm rồi tôi mới thấy lại nó. Mẹ cô chưa từng kể với cô về tháp chuông phía bắc sao?”"],
  ["dialogue", "Minh Khuê", "“Tháp chuông đó bị niêm phong từ trước khi cháu sinh ra.”"],
  ["dialogue", "Ông Tư", "“Niêm phong được cửa, chứ đâu niêm phong được ký ức.”"],
  ["narration", "", "Ngoài kia, tiếng bước chân ai đó chạy dồn dập trên mặt đá ướt. Bảo lao vào, hơi thở đứt quãng, tóc bết lại vì sương."],
  ["dialogue", "Bảo", "“Chị Khuê! Đèn trên tháp chuông… nó vừa sáng lên!”"],
  ["narration", "", "Cả ba cùng nhìn qua ô cửa kính mờ. Ở phía bắc thành phố, giữa màn sương dày đặc, một đốm sáng xanh nhạt đang chầm chậm nhấp nháy."],
  ["dialogue", "Ông Tư", "“Thế là bắt đầu rồi.”"],
  ["narration", "", "Ông nói khẽ, giọng như thể đã chờ khoảnh khắc ấy cả một đời."],
  ["narration", "", "Minh Khuê siết chặt chiếc chìa khoá. Kim loại lạnh buốt, nhưng không hiểu sao cô lại thấy nó đang ấm dần lên."],
  ["narration", "", "Sáng hôm sau, bà Hạnh bán xôi đầu ngõ kể rằng cả đêm bà nghe thấy tiếng chuông ngân, dù tháp ấy đã không còn quả chuông nào."],
  ["dialogue", "Bà Hạnh", "“Tôi sống ở đây năm mươi năm, chưa đêm nào sương lại dày như đêm qua.”"],
  ["narration", "", "Không ai trả lời bà. Những người qua đường chỉ cúi đầu, bước nhanh hơn một chút."],
];

const PLAIN = [
  "Tiệm sách nằm trên tầng ba của một ngôi nhà ống, phải leo qua một cầu thang gỗ hẹp đến mức hai người không thể đi ngược chiều.",
  "Chủ tiệm là một người đàn ông gầy, đeo kính tròn, lúc nào cũng có một cốc trà nguội bên cạnh quầy.",
  "Ông không bao giờ hỏi khách cần tìm gì. Ông chỉ nhìn họ một lúc, rồi đưa ra một cuốn sách, và hiếm khi nào ông đưa sai.",
  "Chiều thứ Năm nào cũng vậy, cô bé mặc áo len xanh lại ghé qua, ngồi ở góc cửa sổ và đọc cho đến khi trời tối.",
  "Hôm ấy, giữa hai trang của một cuốn sổ cũ, cô tìm thấy một tấm ảnh đen trắng chụp chính căn gác này, nhưng đầy những người lạ.",
  "***",
  "Mưa bắt đầu rơi. Tiếng mưa trên mái tôn lấn át cả tiếng xe ngoài phố, và căn phòng bỗng trở nên ấm áp lạ thường.",
  "“Cuốn ấy không bán đâu,” ông chủ nói mà không ngẩng lên. “Nhưng cháu cứ đọc hết, rồi để lại đúng chỗ cũ.”",
];

/** Kịch bản chương có audio: đoạn văn trên, mốc thời gian chia đều theo độ dài chương. */
export function chapterScript(book: GalleryBook, chapterId: number): Script {
  const chapter = book.chapters.find((item) => item.id === chapterId) ?? book.chapters[0];
  const heading = chapter.subtitle ? `${chapter.title}: ${chapter.subtitle}` : chapter.title;
  const lines: Line[] = [["narration", "", heading], ...PASSAGE];
  const total = chapter.duration || 1500;
  const weights = lines.map(([, , text]) => text.length + 20);
  const sum = weights.reduce((a, b) => a + b, 0);
  let at = 0;
  const segments: ScriptSegment[] = lines.map(([kind, speaker, text], index) => {
    const length = (weights[index] / sum) * total;
    const segment: ScriptSegment = {
      id: chapterId * 1000 + index,
      paragraph: index,
      text,
      kind: index === 0 ? "heading" : kind,
      speaker: speaker || "Người kể",
      start: Math.round(at * 10) / 10,
      end: Math.round((at + length - 0.6) * 10) / 10,
      status: "completed",
      stableId: `${book.id}-${chapterId}-${index}`,
    };
    at += length;
    return segment;
  });
  return { chapterId: chapter.id, title: heading, timed: true, duration: total, segments };
}

/** Chữ thô của chương chỉ-có-chữ. */
export function chapterText(book: GalleryBook, chapterId: number): string {
  const chapter = book.chapters.find((item) => item.id === chapterId) ?? book.chapters[0];
  return [`${chapter.title}: ${chapter.subtitle || "Không tên"}`, ...PLAIN].join("\n\n");
}

const GENDER_LABELS: Record<string, string> = { male: "Nam", female: "Nữ" };
const AGE_LABELS: Record<string, string> = { child: "Trẻ em", teen: "Thiếu niên", young: "Thanh niên", adult: "Trưởng thành", elderly: "Cao tuổi" };

// Như máy chủ (webui/humanize.py): giới và tuổi đã dịch sẵn sang tiếng Việt.
function member(name: string, gender: string, age: string, lines: number, voice: string, sampleId: number): CastMember {
  return {
    name,
    displayName: name,
    gender: GENDER_LABELS[gender] ?? "",
    age: AGE_LABELS[age] ?? "",
    lines,
    seconds: lines * 4.2,
    voice: { key: voice.toLowerCase().replace(/\s+/g, "-"), preset: voice.toLowerCase().replace(/\s+/g, "-"), label: voice, tone: gender === "female" ? "ấm, trong" : "trầm" },
    sampleId,
    firstChapter: "Chương 1",
  };
}

export function bookCast(book: GalleryBook): Cast {
  if (book.imported) return { narrator: { voice: "", lines: 0, seconds: 0 }, characters: [], extras: [] };
  return {
    narrator: { voice: book.narrator, lines: 1840, seconds: 23_400 },
    characters: [
      member("Minh Khuê", "female", "young", 412, "Bảo Trang", 4002),
      member("Ông Tư", "male", "elderly", 236, "Hữu Phước", 4004),
      member("Bảo", "male", "teen", 158, "Tuấn Kiệt", 4014),
      member("Bà Hạnh", "female", "adult", 61, "Mai Anh", 4020),
    ],
    extras: [member("Người lái đò", "male", "adult", 9, "Quang Minh", 4100)],
  };
}

export function sessions(book: GalleryBook): ListeningSession[] {
  const last = book.state.last;
  if (!last) return [];
  return [0, 1, 2].map((index) => ({
    id: `s${index}`,
    device: index === 1 ? "Điện thoại của Hà" : "Máy tính phòng khách",
    startedAt: (last.at ?? NOW_SECONDS) - index * DAY - 1800,
    endedAt: (last.at ?? NOW_SECONDS) - index * DAY,
    listened: 1800 - index * 300,
    from: { chapterId: Math.max(1, last.chapterId - index - 1), seconds: 120 },
    to: { chapterId: Math.max(1, last.chapterId - index), seconds: last.seconds },
  }));
}

/** Đêm qua (thẻ "Tối qua bạn nghe tới đâu?"): hẹn 30 phút, nằm yên, tự dừng. */
export function lastNight(): NightSession {
  // 23:05 tối 24-10 (giờ Việt Nam): mục "Tối qua" mở lúc 7:20 sáng hôm sau.
  const start = Date.UTC(2026, 9, 24, 16, 5) / 1000;
  const position = (seconds: number) => ({ chapterId: 4, chapterTitle: "Chương 4: Chiếc chìa khoá bằng đồng", seconds });
  return {
    id: "night-1",
    device: "Điện thoại của Hà",
    bookId: fog2.id,
    bookTitle: fog2.title,
    startedAt: start,
    endedAt: start + 1900,
    events: [
      { type: "timer", at: start, minutes: 30, position: position(0) },
      { type: "touch", at: start + 640, position: position(640) },
      { type: "still", at: start + 900, position: position(900) },
      { type: "fading", at: start + 1770, position: position(1770) },
      { type: "stopped", at: start + 1800, position: position(1800) },
    ],
    timeline: [0, 300, 600, 900, 1200, 1500, 1800].map((seconds) => ({ ...position(seconds), at: start + seconds })),
  };
}

const INITIAL = new Map(BOOKS.map((book) => [book.id, JSON.stringify(book.state)]));

/** Trạng thái nghe về như lúc mở trang: mỗi mục trưng bày bắt đầu từ cùng một thư viện, dù mục trước đã bấm phát / đặt dấu. */
export function resetData(): void {
  for (const book of BOOKS) book.state = JSON.parse(INITIAL.get(book.id)!) as ListeningState;
}

/** Bước xem trước của "Thêm sách từ file…" (ImportPreview): một EPUB tự đặt, có trang bìa và trang bản quyền chưa tích. */
export function importPreview(): ImportPreview {
  const words = [3120, 2890, 3405, 2777, 3010, 2954, 3302];
  const chapters: ImportPreviewChapter[] = [
    { index: 0, title: "Bìa", firstLine: "Tiệm Sách Trên Gác Xép", words: 6, chars: 24, included: false, short: true, matter: "Trang bìa" },
    { index: 1, title: "Bản quyền", firstLine: "Bản quyền © Hà Thanh Tâm", words: 40, chars: 210, included: false, short: true, matter: "Trang bản quyền" },
    ...atticChapters.slice(0, 7).map((chapter, index) => ({
      index: index + 2,
      title: `${chapter.title}: ${chapter.subtitle}`,
      firstLine: PLAIN[index % PLAIN.length].slice(0, 80),
      words: words[index],
      chars: words[index] * 5,
    })),
  ];
  return {
    title: "Tiệm Sách Trên Gác Xép",
    author: "Hà Thanh Tâm",
    chapters,
    notes: ["Đầu mỗi chương có dòng “Nguồn: tự viết cho phòng trưng bày” - bạn có thể bỏ khỏi phần đọc."],
    existing: null,
    sameSource: null,
    hasCover: true,
    totals: { chapters: 7, words: words.reduce((a, b) => a + b, 0) },
  };
}
