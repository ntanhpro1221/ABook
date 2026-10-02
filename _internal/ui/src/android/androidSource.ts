import { Capacitor } from "@capacitor/core";
import type { Cast, ListenBook, ListeningSession, ListeningState, Script } from "@/listen/model";
import { bookProgress } from "./progress";
import type { ListenSource } from "@/listen/source";
import { EbookLibrary, EbookPlayer, type LocalBook } from "./plugins";

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
    part: chapter.part ?? null,
  }));
  const state: ListeningState = { ...book.state, chapters: book.state?.chapters ?? {}, bookmarks: book.state?.bookmarks ?? [] };
  return {
    id: book.id,
    title: book.title,
    narrator: book.narrator,
    duration: chapters.filter((chapter) => chapter.available).reduce((sum, chapter) => sum + chapter.duration, 0),
    chaptersTotal: book.chaptersTotal,
    chaptersAvailable: chapters.filter((chapter) => chapter.available).length,
    complete: book.complete,
    // Trên điện thoại không biết máy tính còn đang làm hay không: chỉ biết cuốn này chưa đủ chương.
    producing: false,
    paused: !book.complete,
    updatedAt: state.updatedAt ?? null,
    state,
    progress: bookProgress(state, chapters.filter((chapter) => chapter.available), book.complete),
    lastChapterTitle: chapters.find((chapter) => chapter.id === state.last?.chapterId)?.fullTitle ?? "",
    cover: book.cover
      ? { url: `${fileUrl(book.id, book.cover.file)}?v=${book.cover.version}`, color: book.cover.color, width: book.cover.width, height: book.cover.height }
      : null,
    chapters: withChapters ? chapters : undefined,
    parts: book.parts ?? [],
    // Nghe thẳng từ thiết bị ghép (Peers.kt): "Trên <tên máy>"; từ máy tính chính: "Trên máy tính".
    remote: book.sourceName ? { computer: book.sourceName } : Boolean(book.streamed),
    records: book.records,
    capabilities: book.capabilities,
    edits: book.edits ?? 0,
  };
}

/** Tên file của chương trong gói - lõi phát native cần nó. */
export const chapterFiles = new Map<string, Map<number, string>>();

export const androidSource: ListenSource = {
  kind: "android",
  async library() {
    const { books } = await EbookLibrary.localBooks();
    // Sách trên máy tính chưa tải cũng là sách của thư viện này (nghe thẳng - Streaming.kt). Máy tính không trả lời
    // thì chúng không hiện: bấm vào mà không nghe được chỉ làm người nghe bối rối.
    const streamed = await EbookLibrary.streamableBooks().then((reply) => reply.books).catch(() => []);
    return [...books, ...streamed].map((book) => toListenBook(book, false));
  },
  async book(id) {
    const book = await EbookLibrary.book({ id });
    chapterFiles.set(id, new Map(book.chapters.filter((chapter) => chapter.file).map((chapter) => [chapter.id, chapter.file!])));
    return toListenBook(book, true);
  },
  async script(bookId, chapterId) {
    const { text } = await EbookLibrary.readText({ id: bookId, path: `scripts/${chapterId}.json` });
    return JSON.parse(text) as Script;
  },
  async cast(bookId) {
    const { text } = await EbookLibrary.readText({ id: bookId, path: "cast.json" });
    return JSON.parse(text) as Cast;
  },
  audioUrl: (bookId, chapterId) => fileUrl(bookId, chapterFiles.get(bookId)?.get(chapterId) ?? ""),
  sampleUrl: (bookId, sampleId) => fileUrl(bookId, `samples/${sampleId}.wav`),
  voiceUrl: () => "",
  saveProgress: (id, chapterId, seconds, duration) => EbookLibrary.progress({ id, chapterId, seconds, duration }),
  setChapterDone: (id, chapterId, done) => EbookLibrary.setChapterDone({ id, chapterId, done }),
  setFinished: (id, finished) => EbookLibrary.setFinished({ id, finished }),
  setRate: (id, rate) => EbookLibrary.setRate({ id, rate }),
  addBookmark: (id, chapterId, seconds, note) => EbookLibrary.addBookmark({ id, chapterId, seconds, note }),
  refreshListening: async (id) => {
    await EbookLibrary.syncState({ id });
  },
  updateBookmark: (id, markId, note) => EbookLibrary.updateBookmark({ id, markId, note }),
  deleteBookmark: (id, markId) => EbookLibrary.deleteBookmark({ id, markId }),
  restoreBookmark: async (id, mark) => {
    await EbookLibrary.addBookmark({ id, chapterId: mark.chapterId, seconds: mark.seconds, note: mark.note });
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
  saveBook: async (id) => {
    const reply = await EbookLibrary.saveBook({ id });
    return { saved: reply.saved, file: reply.name, size: reply.size, edits: reply.edits };
  },
  records: {
    create: async (id, name) => (await EbookLibrary.createRecord({ id, name })).records,
    activate: async (id, record) => (await EbookLibrary.activateRecord({ id, record })).records,
    rename: async (id, record, name) => (await EbookLibrary.renameRecord({ id, record, name })).records,
    remove: async (id, record) => (await EbookLibrary.deleteRecord({ id, record })).records,
  },
};
