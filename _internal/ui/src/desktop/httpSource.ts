import type { MusicCredit, MusicCue } from "@/listen/musicBed";
import type { PlaylistQueue } from "@/listen/playlistBed";
import type { Bookmark, Cast, ListenBook, ListeningRecord, ListeningSession, ListeningState, NightSession, Script } from "@/listen/model";
import type { ListenSource } from "@/listen/source";
import type { EditsSyncState } from "@/shared/editsSync";
import { itemFromPath } from "@/listen/importQueue";
import type { AddedBook, ImportPreview, PickedItem, TextImport } from "@/listen/textImport";
import { ReadAloudError, type ReadAloudClip, type ReadAloudVoice } from "@/listen/readAloud";
import { ApiError, api, mediaUrl } from "@/studio/api";
import { pickFiles, pickFolder } from "@/studio/data";
import { batchName, pickedFromDrop, planUpload, sendPlan, UPLOAD_LIMIT, type Picked } from "@/studio/upload";
import { toast } from "sonner";
import { paragraphsFor, type PrepareStatus } from "@/listen/prepareAhead";

function fileName(path: string): string {
  return path.split(/[\\/]/).filter(Boolean).pop() ?? path;
}

const DROP_LIMIT_MB = UPLOAD_LIMIT / 2 ** 20;

/** Cửa sổ app (Tauri): HTML5 không nhận file thả vào (WebView2 giao cho vỏ), nên vỏ đọc đường dẫn thật và phát `abook-drag` vào trang (main.rs). */
function watchAppDrops({ hover, drop }: Parameters<NonNullable<TextImport["watchDrops"]>>[0]): () => void {
  const listener = (event: Event) => {
    const detail = (event as CustomEvent<{ state?: string; paths?: string[] }>).detail;
    if (detail?.state === "enter") hover(true);
    else if (detail?.state === "leave") hover(false);
    else if (detail?.state === "drop") {
      hover(false);
      drop((detail.paths ?? []).map(itemFromPath));
    }
  };
  window.addEventListener("abook-drag", listener);
  return () => window.removeEventListener("abook-drag", listener);
}

/** Trình duyệt: trang không biết đường dẫn file thả vào, nên gửi từng file lên máy tính (cùng đường với Studio - studio/upload.ts) rồi đọc bản đã gửi. */
async function droppedItems(files: Promise<(Picked & { file: File })[]>): Promise<PickedItem[]> {
  const plan = planUpload(await files, batchName(new Date(), Math.random().toString(36).slice(2, 6)));
  const items: PickedItem[] = [
    ...plan.rejected.map((name) => ({ name, error: "ABook chưa đọc được loại file này - chỉ nhận EPUB, Word (DOCX), PDF có chữ, TXT." })),
    ...plan.tooBig.map((name) => ({ name, error: `File lớn hơn ${DROP_LIMIT_MB} MB - kéo vào trình duyệt chỉ gửi được file tới ${DROP_LIMIT_MB} MB. Mở bằng app ABook để thêm file lớn.` })),
  ];
  if (!plan.groups.length) return items;
  const sending = toast.loading("Đang gửi file lên máy tính…");
  try {
    return [...(await sendPlan(plan, () => undefined)).map(itemFromPath), ...items];
  } finally {
    toast.dismiss(sending);
  }
}

function watchBrowserDrops({ hover, drop }: Parameters<NonNullable<TextImport["watchDrops"]>>[0]): () => void {
  let depth = 0;
  const carriesFiles = (event: DragEvent) => Boolean(event.dataTransfer?.types.includes("Files"));
  const enter = (event: DragEvent) => {
    if (!carriesFiles(event)) return;
    depth += 1;
    hover(true);
  };
  const over = (event: DragEvent) => {
    if (!carriesFiles(event)) return;
    event.preventDefault(); // không chặn thì trình duyệt mở file ngay trong tab
    event.dataTransfer!.dropEffect = "copy";
  };
  const leave = (event: DragEvent) => {
    if (!carriesFiles(event)) return;
    depth = Math.max(0, depth - 1);
    if (!depth) hover(false);
  };
  const dropped = (event: DragEvent) => {
    if (!carriesFiles(event)) return;
    event.preventDefault();
    depth = 0;
    hover(false);
    // Phải đọc danh sách file ngay trong sự kiện (qua một await trình duyệt xoá nó).
    droppedItems(pickedFromDrop(event.dataTransfer!)).then(drop, (error: Error) =>
      toast.error("Không đọc được các file vừa thả", { description: error.message }),
    );
  };
  window.addEventListener("dragenter", enter);
  window.addEventListener("dragover", over);
  window.addEventListener("dragleave", leave);
  window.addEventListener("drop", dropped);
  return () => {
    window.removeEventListener("dragenter", enter);
    window.removeEventListener("dragover", over);
    window.removeEventListener("dragleave", leave);
    window.removeEventListener("drop", dropped);
  };
}

/** "Thêm sách từ file…" trên máy tính: máy chủ cục bộ đọc file bằng `abook/importers.py` (webui/textbook.py). Có hộp thoại của
 *  cửa sổ app thì chọn file / thư mục ở đó; không (chạy trong trình duyệt) thì dán đường dẫn. */
export function desktopTextImport(dialogs: boolean): TextImport {
  return {
    typedPath: true,
    choose: dialogs
      ? async (kind) => {
          if (kind !== "folder") return null; // file: chooseMany (chọn được nhiều file)
          const path = await pickFolder("Chọn thư mục có các chương TXT");
          return path ? { ref: path, name: fileName(path) } : null;
        }
      : undefined,
    chooseMany: dialogs ? async () => (await pickFiles("Chọn file sách (chọn được nhiều file một lúc)")).map(itemFromPath) : undefined,
    watchDrops: dialogs ? watchAppDrops : watchBrowserDrops,
    preview: (choice, options) =>
      api<ImportPreview>("/api/listen/import/preview", {
        method: "POST",
        body: { path: choice.ref, splitChapters: Boolean(options?.splitChapters), ...(options?.footnotes ? { footnotes: options.footnotes } : {}) },
      }),
    add: (choice, title, separate, options) =>
      api<AddedBook>("/api/listen/import", {
        method: "POST",
        body: {
          path: choice.ref,
          title,
          separate: Boolean(separate),
          splitChapters: Boolean(options?.splitChapters),
          ...(options?.footnotes ? { footnotes: options.footnotes } : {}),
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
        body: { voice, text, cachedOnly: options?.cachedOnly, bookId: options?.bookId, readings: options?.readings },
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
  readAloudSample: async (voice, text, options) => (await httpSource.readAloudClip!(voice, text, options)).url,
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
  addBookmark: (bookId, chapterId, seconds, note, record, sentence) =>
    api<Bookmark>(`/api/listen/books/${bookId}/bookmarks`, { method: "POST", body: { chapterId, seconds, note, record, index: sentence?.index, quote: sentence?.quote } }),
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
  // Cuốn của máy tính khác (webui/remote_books.py): phần sửa về máy ấy như điện thoại gửi về máy tính.
  sendEdits: (bookId) => api<EditsSyncState>(`/api/listen/books/${bookId}/edits/send`, { method: "POST" }),
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
    move: async (bookId, recordId, toBook) =>
      (await api<{ records: ListeningRecord[] }>(`/api/listen/books/${bookId}/records/${recordId}/move`, { method: "POST", body: { book: toBook } }))
        .records,
  },
};
