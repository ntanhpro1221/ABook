import type { MusicCredit, MusicCue } from "@/listen/musicBed";
import type { PlaylistQueue } from "@/listen/playlistBed";
import type { Bookmark, Cast, ListenBook, ListeningRecord, ListeningSession, ListeningState, NightSession, Script } from "@/listen/model";
import type { ListenSource } from "@/listen/source";
import type { AddedBook, ImportPreview, TextImport } from "@/listen/textImport";
import { ReadAloudError, type ReadAloudClip, type ReadAloudVoice } from "@/listen/readAloud";
import { ApiError, api, mediaUrl } from "@/studio/api";
import { pickFiles, pickFolder } from "@/studio/data";
import { paragraphsFor, type PrepareStatus } from "@/listen/prepareAhead";

function fileName(path: string): string {
  return path.split(/[\\/]/).filter(Boolean).pop() ?? path;
}

/** "Thêm sách từ file…" trên máy tính: máy chủ cục bộ đọc file bằng `abook/importers.py` (webui/textbook.py). Có hộp thoại của
 *  cửa sổ app thì chọn file / thư mục ở đó; không (chạy trong trình duyệt) thì dán đường dẫn. */
export function desktopTextImport(dialogs: boolean): TextImport {
  return {
    typedPath: true,
    choose: dialogs
      ? async (kind) => {
          if (kind === "folder") {
            const path = await pickFolder("Chọn thư mục có các chương TXT");
            return path ? { ref: path, name: fileName(path) } : null;
          }
          const paths = await pickFiles("Chọn một file sách (EPUB, DOCX, PDF, TXT)");
          if (paths.length > 1) throw new Error("Chọn một file sách thôi. Truyện nhiều file TXT thì để vào một thư mục rồi chọn thư mục ấy.");
          return paths[0] ? { ref: paths[0], name: fileName(paths[0]) } : null;
        }
      : undefined,
    preview: (choice, options) =>
      api<ImportPreview>("/api/listen/import/preview", { method: "POST", body: { path: choice.ref, splitChapters: Boolean(options?.splitChapters) } }),
    add: (choice, title, separate, options) =>
      api<AddedBook>("/api/listen/import", {
        method: "POST",
        body: {
          path: choice.ref,
          title,
          separate: Boolean(separate),
          splitChapters: Boolean(options?.splitChapters),
          // Chương người dùng giữ + tên mới; không đổi gì thì không gửi (máy chủ lấy các chương mặc định).
          ...(options?.chapters ? { chapters: options.chapters } : {}),
        },
      }),
  };
}

/** Phía Nghe trên máy tính: đọc từ server cục bộ (abook/webui). */
export const httpSource: ListenSource = {
  kind: "desktop",
  library: () => api<ListenBook[]>("/api/listen/library"),
  book: (id) => api<ListenBook>(`/api/listen/books/${id}`),
  script: (bookId, chapterId) => api<Script>(`/api/books/${bookId}/chapters/${chapterId}/script`),
  chapterText: async (bookId, chapterId) =>
    (await api<{ text: string }>(`/api/listen/books/${bookId}/chapters/${chapterId}/text`)).text,
  cast: (bookId) => api<Cast>(`/api/books/${bookId}/cast`),
  readAloudVoices: async () => {
    const voices = await api<(Omit<ReadAloudVoice, "gainDb"> & { gain_db?: number })[]>("/api/readaloud/voices");
    return voices.map(({ gain_db, ...voice }) => ({ ...voice, gainDb: gain_db ?? 0 }));
  },
  readAloudClip: async (voice, text, options) => {
    let clip: { url: string; duration_ms: number; words: [number, number][] } | { cached: false; reason: string };
    try {
      clip = await api<typeof clip>("/api/readaloud/clip", {
        method: "POST",
        body: { voice, text, cachedOnly: options?.cachedOnly, bookId: options?.bookId },
      });
    } catch (error) {
      // Máy chủ nói đúng lý do (offline / timeout / rejected / service...); mất kết nối tới chính máy chủ cục bộ là "service".
      if (error instanceof ApiError) throw new ReadAloudError(error.message, String(error.detail.reason ?? "service"));
      throw new ReadAloudError("Không gọi được giọng đọc.", "service");
    }
    // Chỉ tra bộ đệm mà chưa có: máy chủ trả 200 (không phải lỗi mạng), bộ máy đọc vẫn cần biết là "uncached".
    if ("cached" in clip) throw new ReadAloudError("Chưa đọc đoạn này.", clip.reason || "uncached");
    return { url: mediaUrl(clip.url), durationMs: clip.duration_ms, words: clip.words } satisfies ReadAloudClip;
  },
  readAloudSample: async (voice, text) => (await httpSource.readAloudClip!(voice, text)).url,
  // Máy chủ nhận chữ từng đoạn, chia đúng như trình phát (cùng khoá bộ đệm với lúc nghe).
  readAloudPrepare: async ({ voice, bookId, chapters, label }) => {
    const texts = await paragraphsFor(chapters, (id) => httpSource.chapterText(bookId, id));
    return api<PrepareStatus>("/api/readaloud/prepare", { method: "POST", body: { voice, texts, label, bookId } });
  },
  readAloudPrepareStatus: () => api<PrepareStatus>("/api/readaloud/prepare"),
  // Máy tính xách tay cũng mất mạng (tàu, máy bay): giọng trực tuyến làm trước vào bộ đệm clip như VieNeu (readaloud/prepare.py chung mọi giọng).
  readAloudPrepareOnline: true,
  readAloudPrepareCancel: () => api<PrepareStatus>("/api/readaloud/prepare", { method: "DELETE" }),
  musicCues: async (bookId, chapterId) => {
    const result = await api<{ cues: MusicCue[]; levelDb: number; credits?: Record<string, MusicCredit> }>(`/api/books/${bookId}/music/chapters/${chapterId}`);
    return { ...result, cues: result.cues.map((cue) => ({ ...cue, src: mediaUrl(cue.src) })) };
  },
  musicPlaylist: async (bookId) => {
    const result = await api<PlaylistQueue>(`/api/books/${bookId}/music/playlist`);
    return { ...result, tracks: result.tracks.map((track) => ({ ...track, src: mediaUrl(track.src) })) };
  },
  audioUrl: (bookId, chapterId) => mediaUrl(`/media/books/${bookId}/chapters/${chapterId}`),
  sampleUrl: (bookId, sampleId) => mediaUrl(`/media/books/${bookId}/samples/${sampleId}`),
  voiceUrl: (name) => mediaUrl(`/media/voices/${encodeURIComponent(name)}`),
  saveProgress: (bookId, chapterId, seconds, duration, record) =>
    api<ListeningState>(`/api/listen/books/${bookId}/progress`, { method: "POST", body: { chapterId, seconds, duration, record } }),
  setChapterDone: (bookId, chapterId, done) =>
    api<ListeningState>(`/api/listen/books/${bookId}/chapters/${chapterId}/done`, { method: "POST", body: { done } }),
  setFinished: (bookId, finished) =>
    api<ListeningState>(`/api/listen/books/${bookId}/finished`, { method: "POST", body: { finished } }),
  setRate: async (bookId, rate) => {
    await api(`/api/listen/books/${bookId}/rate`, { method: "POST", body: { rate } });
  },
  addBookmark: (bookId, chapterId, seconds, note, record) =>
    api<Bookmark>(`/api/listen/books/${bookId}/bookmarks`, { method: "POST", body: { chapterId, seconds, note, record } }),
  updateBookmark: async (bookId, id, note) => {
    await api(`/api/listen/books/${bookId}/bookmarks/${id}`, { method: "PUT", body: { note } });
  },
  deleteBookmark: async (bookId, id) => {
    await api(`/api/listen/books/${bookId}/bookmarks/${id}`, { method: "DELETE" });
  },
  restoreBookmark: async (bookId, mark) => {
    await api(`/api/listen/books/${bookId}/bookmarks/restore`, { method: "POST", body: mark });
  },
  lastNight: () => api<{ bookId: string; night: NightSession } | null>("/api/listen/night"),
  dismissNight: async (bookId, id) => {
    await api("/api/listen/night/dismiss", { method: "POST", body: { bookId, id } });
  },
  sessions: (bookId) => api<ListeningSession[]>(`/api/listen/books/${bookId}/sessions`),
  addSessionOnExit: (bookId, session, record) => {
    void fetch(mediaUrl(`/api/listen/books/${bookId}/sessions`), {
      method: "POST",
      keepalive: true,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...session, record }),
    }).catch(() => undefined);
  },
  addSession: async (bookId, session, record) => {
    await api(`/api/listen/books/${bookId}/sessions`, { method: "POST", body: { ...session, record } });
  },
  saveReading: async (bookId, chapterId, index) => {
    await api(`/api/listen/books/${bookId}/reading`, { method: "POST", body: { chapterId, index } });
  },
  saveNight: async (bookId, night) => {
    await api(`/api/listen/books/${bookId}/night`, { method: "POST", body: night });
  },
  saveBook: async (bookId, options) => {
    const result = await api<{ file: string; folder: string; size: number; edits: number }>(`/api/books/${bookId}/save`, {
      method: "POST",
      body: { ...(options?.folder ? { target: options.folder } : {}), ...(options?.as ? { as: options.as } : {}) },
    });
    return { saved: true, ...result };
  },
  records: {
    create: async (bookId, name) =>
      (await api<{ records: ListeningRecord[] }>(`/api/listen/books/${bookId}/records`, { method: "POST", body: { name } })).records,
    activate: async (bookId, recordId) =>
      (await api<{ records: ListeningRecord[] }>(`/api/listen/books/${bookId}/records/${recordId}/activate`, { method: "POST" })).records,
    rename: async (bookId, recordId, name) =>
      (await api<{ records: ListeningRecord[] }>(`/api/listen/books/${bookId}/records/${recordId}`, { method: "PUT", body: { name } })).records,
    remove: async (bookId, recordId) =>
      (await api<{ records: ListeningRecord[] }>(`/api/listen/books/${bookId}/records/${recordId}`, { method: "DELETE" })).records,
  },
};
