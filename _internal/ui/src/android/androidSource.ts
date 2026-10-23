import { Capacitor } from "@capacitor/core";
import type { Cast, ListenBook, ListeningSession, ListeningState, Script } from "@/listen/model";
import { bookProgress, textBookProgress } from "./progress";
import type { ListenSource, SearchText } from "@/listen/source";
import type { VieneuBackend } from "@/listen/VieneuModuleCard";
import { EbookLibrary, EbookPlayer, ReadAloud, type LocalBook } from "./plugins";
import { phonePrepare } from "./readAloud";
import { phoneTextImport } from "./textImport";
import { recentFirst } from "@/listen/librarySort";

// Phía Nghe trên Android: đọc sách đã tải về máy, và sách trên máy tính nghe thẳng qua mạng (EbookLibrary). Audio chương do lõi phát native mở thẳng từ
// file, nên audioUrl không dùng tới; câu mẫu nhân vật phát trong WebView qua đường dẫn file đã chuyển đổi.

let root = "";
export async function initAndroidSource(): Promise<void> {
  root = (await EbookLibrary.info()).root;
}

function fileUrl(bookId: string, relative: string): string {
  return Capacitor.convertFileSrc(`${root}/books/${bookId}/${relative}`);
}

function toListenBook(book: LocalBook, withChapters: boolean): ListenBook {
  const chapters = book.chapters.map((chapter) => ({
    id: chapter.id,
    index: chapter.index,
    title: chapter.title,
    subtitle: chapter.subtitle,
    fullTitle: chapter.fullTitle,
    duration: chapter.duration,
    available: chapter.available && Boolean(chapter.file),
    audioVersion: chapter.sha256,
    wordsVersion: chapter.wordsVersion ?? book.wordsVersion,
    part: chapter.part ?? null,
    state: chapter.text && !chapter.file ? ("text" as const) : null,
    ...(chapter.skip?.length ? { skip: chapter.skip } : {}),
  }));
  const textOnly = chapters.length > 0 && chapters.every((chapter) => chapter.state === "text");
  const state: ListeningState = { ...book.state, chapters: book.state?.chapters ?? {}, bookmarks: book.state?.bookmarks ?? [] };
  return {
    id: book.id,
    title: book.title,
    author: book.author ?? "",
    narrator: book.narrator,
    duration: chapters.filter((chapter) => chapter.available).reduce((sum, chapter) => sum + chapter.duration, 0),
    chaptersTotal: book.chaptersTotal,
    chaptersAvailable: chapters.filter((chapter) => chapter.available).length,
    complete: book.complete,
    // Cuốn chỉ có chữ (.abook phiên bản 5): chương nào cũng chưa có audio mà có chữ.
    stage: textOnly ? ("text" as const) : null,
    // Trên điện thoại không biết máy tính còn đang làm hay không: chỉ biết cuốn này chưa đủ chương.
    producing: false,
    paused: !book.complete,
    updatedAt: state.updatedAt ?? null,
    addedAt: book.addedAt ?? null,
    state,
    progress: textOnly ? textBookProgress(state, chapters) : bookProgress(state, chapters.filter((chapter) => chapter.available), book.complete),
    lastChapterTitle: chapters.find((chapter) => chapter.id === state.last?.chapterId)?.fullTitle ?? "",
    cover: book.cover
      ? { url: `${fileUrl(book.id, book.cover.file)}?v=${book.cover.version}`, color: book.cover.color, width: book.cover.width, height: book.cover.height }
      : null,
    chapters: withChapters ? chapters : undefined,
    parts: book.parts ?? [],
    // Liên kết bộ truyện ("Làm tiếp cuốn này") đi cùng gói sách: giữ nguyên, đổi tên một phần không làm mất nhóm (soát a97 V2).
    series: book.series ?? null,
    // Nghe thẳng từ thiết bị ghép (Peers.kt): "Trên <tên máy>"; từ máy tính chính: "Trên máy tính".
    remote: book.sourceName ? { computer: book.sourceName } : Boolean(book.streamed),
    // Dự án Studio của máy tính nhận phần sửa của cuốn (máy tính chính hay máy tính ghép thêm): mở Studio của máy ấy ở đúng cuốn.
    studio: Boolean(book.studio && book.capabilities?.sync),
    records: book.records,
    capabilities: book.capabilities,
    edits: book.edits ?? 0,
    wishes: book.wishes ?? 0,
    editsSync: book.editsSync,
  };
}

// Sách trên máy tính / thiết bị ghép nghe thẳng được: hỏi máy kia có thể chậm tới hàng chục giây (mạng chập chờn, nhiều gói sách đã đổi), nên danh sách sách
// đã tải không chờ nó - `library()` trả sách trên máy ngay (cộng lần trả lời trước của máy kia), hỏi máy kia chạy song song và, khi về mà có gì khác, báo
// `libraryChanged` để màn Thư viện lấy lại danh sách (soát a101 F2).
let streamedBooks: LocalBook[] = [];
let streamedAsk: Promise<void> | null = null;
const libraryListeners = new Set<() => void>();
/** Chờ thêm chừng này (ms) cho lần trả lời của máy kia: máy kia nhanh thì sách nghe thẳng vào danh sách ngay lần đầu, chậm thì thôi. */
export const STREAMED_GRACE_MS = 250;

function refreshStreamed(): Promise<void> {
  streamedAsk ??= EbookLibrary.streamableBooks()
    .then((reply) => reply.books, () => [] as LocalBook[]) // máy kia không trả lời thì sách của nó không hiện: bấm vào mà không nghe được chỉ làm người nghe bối rối
    .then((books) => {
      if (JSON.stringify(books) === JSON.stringify(streamedBooks)) return;
      streamedBooks = books;
      libraryListeners.forEach((listener) => listener());
    })
    .finally(() => {
      streamedAsk = null;
    });
  return streamedAsk;
}

/** Tên file của chương trong gói - lõi phát native cần nó. */
export const chapterFiles = new Map<string, Map<number, string>>();
/** Tên mục chữ của chương chỉ-có-chữ (`texts/<mã>.txt`). */
const chapterTexts = new Map<string, Map<number, string>>();

/** Tên mục chữ của một chương chỉ-có-chữ - lõi native đọc to chương ấy từ mục này. */
export function chapterTextEntry(bookId: string, chapterId: number): string {
  return chapterTexts.get(bookId)?.get(chapterId) ?? `texts/${chapterId}.txt`;
}

/** "Giọng VieNeu" trên điện thoại: lõi native tải, đo, gỡ (VieneuModule.kt) - cùng thẻ với máy tính, và khối lỗi của trình phát tải giọng ngay tại chỗ. */
export const phoneVieneu: VieneuBackend = {
  status: () => ReadAloud.vieneuStatus(),
  start: (choices) => ReadAloud.vieneuStart(choices ? { choices } : {}),
  measure: () => ReadAloud.vieneuMeasure(),
  remove: (choice) => ReadAloud.vieneuRemove({ choice }),
  cancel: () => ReadAloud.vieneuCancel(),
  voices: async () => (await ReadAloud.voices()).voices,
};

export const androidSource: ListenSource = {
  kind: "android",
  vieneu: phoneVieneu,
  async library() {
    // Sách trên máy tính chưa tải cũng là sách của thư viện này (nghe thẳng - Streaming.kt). Hỏi máy tính chạy song song, không chặn sách đã tải.
    const asking = refreshStreamed();
    const { books } = await EbookLibrary.localBooks();
    await Promise.race([asking, new Promise<void>((resolve) => setTimeout(resolve, STREAMED_GRACE_MS))]);
    // Hai nguồn nối nhau không phải thứ tự "nghe gần đây": xếp theo lần nghe cuối (cùng khoá với máy tính) - soát a97 T1.
    return recentFirst([...books, ...streamedBooks].map((book) => toListenBook(book, false)));
  },
  libraryChanged(listener) {
    libraryListeners.add(listener);
    return () => {
      libraryListeners.delete(listener);
    };
  },
  async book(id) {
    const book = await EbookLibrary.book({ id });
    chapterFiles.set(id, new Map(book.chapters.filter((chapter) => chapter.file).map((chapter) => [chapter.id, chapter.file!])));
    chapterTexts.set(id, new Map(book.chapters.filter((chapter) => chapter.text).map((chapter) => [chapter.id, chapter.text!])));
    return toListenBook(book, true);
  },
  async chapterText(bookId, chapterId) {
    return (await EbookLibrary.readText({ id: bookId, path: chapterTextEntry(bookId, chapterId) })).text;
  },
  // Ô "Tìm trong sách": một lượt qua cầu cho cả lô chương (như `search-texts` của máy tính) - sách 2000 chương không phải đi hàng trăm lượt.
  searchTexts: async (bookId, chapters) => {
    const { texts } = await EbookLibrary.readTexts({
      id: bookId,
      paths: chapters.map((chapter) => (chapter.text ? chapterTextEntry(bookId, chapter.id) : `scripts/${chapter.id}.json`)),
    });
    const found: SearchText[] = [];
    // Lõi trả phần đầu khi chữ quá nhiều: chương nào không có trong `texts` thì bên hỏi xin lại (bookSearch.ts).
    texts.forEach((raw, index) => {
      const chapter = chapters[index];
      if (raw === null || raw === "") return void found.push({ id: chapter.id, failed: true });
      if (chapter.text) return void found.push({ id: chapter.id, text: raw });
      try {
        const script = JSON.parse(raw) as Script;
        found.push({ id: chapter.id, segments: script.segments.map((segment) => ({ text: segment.text, ...(segment.sceneBreak ? { sceneBreak: true } : {}) })) });
      } catch {
        found.push({ id: chapter.id, failed: true });
      }
    });
    return found;
  },
  // "Nghe ngay": lõi native tự đọc chương chữ bằng giọng của máy (TextToSpeech); JS chỉ hỏi giọng và mốc (android/readAloud.ts).
  readAloudVoices: async () => (await ReadAloud.voices()).voices,
  readAloudTimings: (bookId, chapterId) => ReadAloud.script({ bookId, chapterId }),
  voiceWarm: (voice) => {
    void ReadAloud.warmVoice({ voice }).catch(() => undefined);
  },
  readAloudSample: async (voice, text, options) => Capacitor.convertFileSrc((await ReadAloud.sample({ voice, text, ...options })).path),
  // "Làm trước": việc nền native đọc sẵn các chương tới (khi đang sạc, Wi-Fi) để nghe không cần mạng hay không phải chờ giọng chậm.
  ...phonePrepare(),
  textImport: phoneTextImport,
  async script(bookId, chapterId) {
    const { text } = await EbookLibrary.readText({ id: bookId, path: `scripts/${chapterId}.json` });
    return JSON.parse(text) as Script;
  },
  async cast(bookId) {
    const { text } = await EbookLibrary.readText({ id: bookId, path: "cast.json" });
    // Sách chỉ-có-chữ không có cast.json (chưa phân vai): dàn nhân vật rỗng.
    return (text ? JSON.parse(text) : { narrator: { voice: "", lines: 0, seconds: 0 }, characters: [], extras: [] }) as Cast;
  },
  audioUrl: (bookId, chapterId) => fileUrl(bookId, chapterFiles.get(bookId)?.get(chapterId) ?? ""),
  sampleUrl: (bookId, sampleId) => fileUrl(bookId, `samples/${sampleId}.wav`),
  voiceUrl: () => "",
  saveProgress: (id, chapterId, seconds, duration, _record, anchor) => EbookLibrary.progress({ id, chapterId, seconds, duration, anchor }),
  saveReading: async (id, chapterId, index, position, record) => {
    await EbookLibrary.saveReading({ id, ...position, chapterId, index, record });
  },
  setChapterDone: (id, chapterId, done, record) => EbookLibrary.setChapterDone({ id, chapterId, done, record }),
  setFinished: (id, finished, record) => EbookLibrary.setFinished({ id, finished, record }),
  setRate: (id, rate, record) => EbookLibrary.setRate({ id, rate, record }),
  setVoice: (id, voice, record) => EbookLibrary.setVoice({ id, voice, record }),
  addBookmark: (id, chapterId, seconds, note, record, sentence) => EbookLibrary.addBookmark({ id, chapterId, seconds, note, ...sentence, record }),
  refreshListening: async (id) => {
    await EbookLibrary.syncState({ id });
  },
  updateBookmark: (id, markId, note, record) => EbookLibrary.updateBookmark({ id, markId, note, record }),
  deleteBookmark: (id, markId, record) => EbookLibrary.deleteBookmark({ id, markId, record }),
  restoreBookmark: async (id, mark) => {
    // Hoàn tác đúng ID và lúc đặt dấu gốc; lõi gỡ bia mộ để đồng bộ không xoá dấu lần nữa.
    await EbookLibrary.restoreBookmark({ id, mark });
  },
  async sessions(bookId) {
    const book = await EbookLibrary.book({ id: bookId });
    return ((book.state as { sessions?: ListeningSession[] }).sessions ?? []).slice();
  },
  async lastNight() {
    const { session } = await EbookPlayer.lastNight();
    return session?.bookId ? { bookId: session.bookId, night: session } : null;
  },
  dismissNight: () => EbookPlayer.dismissLastNight(),
  sendEdits: (id) => EbookLibrary.sendEdits({ id }),
  saveBook: async (id, options) => {
    const reply = await EbookLibrary.saveBook({ id, as: options?.as, ask: options?.ask });
    return { saved: reply.saved, file: reply.name, size: reply.size, edits: reply.edits };
  },
  shareBook: async (id) => {
    await EbookLibrary.shareBook({ id });
  },
  records: {
    create: async (id, name) => (await EbookLibrary.createRecord({ id, name })).records,
    activate: async (id, record) => (await EbookLibrary.activateRecord({ id, record })).records,
    rename: async (id, record, name) => (await EbookLibrary.renameRecord({ id, record, name })).records,
    remove: async (id, record) => (await EbookLibrary.deleteRecord({ id, record })).records,
    move: async (id, record, book) => (await EbookLibrary.moveRecord({ id, record, book })).records,
  },
};
