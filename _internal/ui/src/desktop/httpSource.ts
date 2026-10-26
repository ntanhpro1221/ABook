import type { MusicCues } from "@/listen/musicBed";
import type { PlaylistQueue } from "@/listen/playlistBed";
import type { Cast, ListenBook, ListeningRecord, ListeningSession, ListeningState, NightSession, Script } from "@/listen/model";
import type { ListenSource, SearchText } from "@/listen/source";
import type { EditsSyncState } from "@/shared/editsSync";
import { itemFromPath } from "@/listen/importQueue";
import type { AddedBook, ImportPreview, PickedItem, TextImport } from "@/listen/textImport";
import { ReadAloudError, fetchClipBytes, type ClipOptions, type ReadAloudClip, type ReadAloudVoice } from "@/listen/readAloud";
import { CLIP_STREAM_TYPE, LOCAL_MIME, clipFromStream, liveClipsSupported } from "@/listen/liveClip";
import { tailFromWord } from "@/listen/words";
import { ApiError, api, apiOrStream, canStream, mediaUrl } from "@/studio/api";
import { watchAppDropPaths } from "@/studio/appDrops";
import { pickFiles, pickFolder } from "@/studio/data";
import { batchName, pickedFromDrop, planUpload, sendPlan, UPLOAD_LIMIT, type Picked } from "@/studio/upload";
import { toast } from "@/shared/toast";
import { paragraphsFor, type PreparePlan, type PrepareStatus, type ReadAloudCacheUsage } from "@/listen/prepareAhead";

function fileName(path: string): string {
  return path.split(/[\\/]/).filter(Boolean).pop() ?? path;
}

const DROP_LIMIT_MB = UPLOAD_LIMIT / 2 ** 20;

/** Cửa sổ app (Tauri): HTML5 không nhận file thả vào (WebView2 giao cho vỏ), nên vỏ đọc đường dẫn thật và phát `abook-drag` vào trang (main.rs). */
function watchAppDrops({ hover, drop }: Parameters<NonNullable<TextImport["watchDrops"]>>[0]): () => void {
  return watchAppDropPaths({ hover, drop: (paths) => drop(paths.map(itemFromPath)) });
}

/** Trình duyệt: trang không biết đường dẫn file thả vào, nên gửi từng file lên máy tính (cùng đường với Studio - studio/upload.ts) rồi đọc bản đã gửi. */
async function droppedItems(files: Promise<(Picked & { file: File })[]>): Promise<PickedItem[]> {
  const plan = planUpload(await files, batchName(new Date(), Math.random().toString(36).slice(2, 6)));
  const items: PickedItem[] = [
    ...plan.rejected.map((name) => ({ name, error: "ABook chưa đọc được loại file này - chỉ nhận EPUB, Word (DOCX), PDF có chữ, TXT." })),
    ...plan.tooBig.map((name) => ({ name, error: `File lớn hơn ${DROP_LIMIT_MB} MB - kéo vào trình duyệt chỉ gửi được file tới ${DROP_LIMIT_MB} MB. Mở bằng app ABook để thêm file lớn.` })),
  ];
  if (!plan.groups.length) return items;
  const sending = toast.loading("Đang gửi file lên máy tính");
  try {
    const result = await sendPlan(plan, () => undefined);
    if (result.error) throw result.error;
    return [...result.paths.map(itemFromPath), ...items];
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
          ...(options?.sourceFingerprint ? { sourceFingerprint: options.sourceFingerprint } : {}),
          ...(options?.footnotes ? { footnotes: options.footnotes } : {}),
          // Chương người dùng giữ + tên mới; không đổi gì thì không gửi (máy chủ lấy các chương mặc định).
          ...(options?.chapters ? { chapters: options.chapters } : {}),
        },
      }),
  };
}

/** Xin clip phát luồng ([clipFromStream]): hỏi thật (không chỉ tra bộ đệm), chỗ chờ đã biết giây (không `whole`), và hoặc là đoạn người nghe đang đứng chờ (rank 0) mà trình duyệt phát được MP3 qua MediaSource,
 *  hoặc là giọng trên máy (`onDevice`: cả đoạn đọc trước - đoạn kế mà người nghe tới khi còn đang đọc dở nhập luồng được) mà trình duyệt phát được FLAC ([LOCAL_MIME]). */
export function wantsLiveClip(options?: ClipOptions): boolean {
  if (!options || options.cachedOnly || options.whole || !canStream()) return false;
  return (options.rank === 0 && liveClipsSupported()) || (options.onDevice === true && liveClipsSupported(LOCAL_MIME));
}

/** Hỏi máy chủ một clip (chưa tải file audio): ném `ReadAloudError` với đúng lý do máy chủ nêu. Đoạn người nghe đang chờ được phát dần ([wantsLiveClip]): trả clip ngay khi byte đầu về, trong đó
 *  `live` là phần còn lại đang về; máy chủ có clip trong bộ đệm / không phát luồng được thì vẫn trả JSON như thường. */
async function requestClip(voice: string, text: string, options?: ClipOptions): Promise<ReadAloudClip> {
  type Reply = { url: string; duration_ms: number; words: [number, number][] } | { cached: false; reason: string };
  // Bấm giữa đoạn ([ClipOptions.tailFrom]): chỉ đọc phần đuôi từ chữ ấy (phát luồng, nghe sau ~2 giây) - trừ khi đã có cả đoạn trong bộ đệm của máy chủ (nghe ngay, mốc đủ) hay không phát luồng được.
  const from = options?.tailFrom ?? 0;
  const tail = from > 0 ? tailFromWord(text, from) : null;
  const stream = wantsLiveClip(options) && (from <= 0 || tail !== null);
  if (stream && tail !== null) {
    try {
      return await requestClip(voice, text, { ...options, cachedOnly: true, tailFrom: undefined });
    } catch (error) {
      if (!(error instanceof ReadAloudError) || error.reason !== "uncached") throw error;
    }
  }
  const init = {
    method: "POST",
    body: {
      voice,
      text: stream && tail !== null ? tail : text,
      cachedOnly: options?.cachedOnly,
      bookId: options?.bookId,
      readings: options?.readings,
      rank: options?.rank,
      // Giọng trên máy cũng phát luồng (từng khúc vừa đọc xong) khi trình duyệt nhận được FLAC qua MediaSource; `rate`: máy chủ chờ đủ tiếng cho tốc độ đang nghe, `soundLeft`: hết tiếng thì
      // thôi chờ.
      ...(stream
        ? {
            stream: true,
            ...(liveClipsSupported(LOCAL_MIME) ? { localStream: true } : {}),
            ...(options?.rate ? { rate: options.rate } : {}),
            ...(options?.soundLeft !== undefined ? { soundLeft: options.soundLeft } : {}),
          }
        : {}),
    },
    signal: options?.signal, // bộ máy bỏ lượt này: kết nối đóng, máy chủ thôi đọc (server.py _peer_gone)
  };
  let clip: Reply | ReadAloudClip;
  try {
    clip = stream
      ? await apiOrStream<Reply, ReadAloudClip>("/api/readaloud/clip", init, CLIP_STREAM_TYPE, (response) => clipFromStream(response.body, mediaUrl, options?.signal))
      : await api<Reply>("/api/readaloud/clip", init);
  } catch (error) {
    if (options?.signal?.aborted) throw new ReadAloudError("Đã bỏ đoạn này.", "cancelled");
    // Máy chủ nói đúng lý do (offline / timeout / rejected / service...); mất kết nối tới chính máy chủ cục bộ là "service".
    if (error instanceof ReadAloudError) throw error;
    if (error instanceof ApiError) throw new ReadAloudError(error.message, String(error.detail.reason ?? "service"));
    throw new ReadAloudError("Không gọi được giọng đọc.", "service");
  }
  const tailed = stream && tail !== null ? { fromWord: from } : {};
  if ("durationMs" in clip) return { ...clip, ...tailed }; // clip phát luồng đã dựng sẵn
  // Chỉ tra bộ đệm mà chưa có: máy chủ trả 200 (không phải lỗi mạng), bộ máy đọc vẫn cần biết là "uncached".
  if ("cached" in clip) throw new ReadAloudError("Chưa đọc đoạn này.", clip.reason || "uncached");
  return { url: mediaUrl(clip.url), durationMs: clip.duration_ms, words: clip.words, ...tailed };
}

/** Phía Nghe trên máy tính: đọc từ server cục bộ (abook/webui). */
export const httpSource: ListenSource = {
  kind: "desktop",
  library: () => api<ListenBook[]>("/api/listen/library"),
  book: (id) => api<ListenBook>(`/api/listen/books/${id}`),
  script: (bookId, chapterId) => api<Script>(`/api/books/${bookId}/chapters/${chapterId}/script`),
  chapterText: async (bookId, chapterId) =>
    (await api<{ text: string }>(`/api/listen/books/${bookId}/chapters/${chapterId}/text`)).text,
  // Ô "Tìm trong sách": một lần hỏi cho cả lô chương (server.py get_search_texts); `text`: các chương chỉ-có-chữ trong lô.
  searchTexts: async (bookId, chapters) => {
    const text = chapters.filter((chapter) => chapter.text).map((chapter) => chapter.id);
    const query = `chapters=${chapters.map((chapter) => chapter.id).join(",")}${text.length ? `&text=${text.join(",")}` : ""}`;
    return (await api<{ chapters: SearchText[] }>(`/api/listen/books/${bookId}/search-texts?${query}`)).chapters;
  },
  cast: (bookId) => api<Cast>(`/api/books/${bookId}/cast`),
  readAloudVoices: async () => {
    const voices = await api<(Omit<ReadAloudVoice, "gainDb"> & { gain_db?: number })[]>("/api/readaloud/voices");
    return voices.map(({ gain_db, ...voice }) => ({ ...voice, gainDb: gain_db ?? 0 }));
  },
  readAloudClip: async (voice, text, options) => {
    const clip = await requestClip(voice, text, options);
    if (clip.live) return clip; // đang về: chính luồng ấy là file (live.final.bytes khi xong), không tải lại
    // Tải luôn file audio bằng fetch ngay trong lượt xin clip: clip chỉ "về" khi đã đủ byte, lỗi tải = clip hỏng (cùng đường thử lại). Phần tử <audio> tự tải thì bị xếp sau các POST clip còn treo (a55).
    return { ...clip, bytes: await fetchClipBytes(clip.url) };
  },
  readAloudSample: async (voice, text, options) => (await requestClip(voice, text, options)).url,
  // Máy chủ nhận chữ từng đoạn, chia đúng như trình phát (cùng khoá bộ đệm với lúc nghe).
  readAloudPrepare: async ({ voice, bookId, chapters, label }) => {
    const texts = await paragraphsFor(chapters, (id) => httpSource.chapterText(bookId, id));
    return api<PrepareStatus>("/api/readaloud/prepare", { method: "POST", body: { voice, texts, label, bookId } });
  },
  readAloudPrepareStatus: () => api<PrepareStatus>("/api/readaloud/prepare"),
  // Ước trước khi bấm: số ký tự từng chương (chia đoạn đúng như lúc làm), máy chủ biết phần bộ đệm dành cho làm trước và tốc độ đo của giọng.
  readAloudPreparePlan: async ({ voice, bookId, chapters }) => {
    const chars = await Promise.all(
      chapters.map(async (chapter) => (await paragraphsFor([chapter], (id) => httpSource.chapterText(bookId, id))).reduce((sum, text) => sum + text.length, 0)),
    );
    return api<PreparePlan>("/api/readaloud/prepare/plan", { method: "POST", body: { voice, chars } });
  },
  readAloudCache: (bookId) => api<ReadAloudCacheUsage>(`/api/readaloud/cache?bookId=${encodeURIComponent(bookId)}`),
  readAloudCacheClear: (bookId) => api<ReadAloudCacheUsage>(`/api/readaloud/cache?bookId=${encodeURIComponent(bookId)}`, { method: "DELETE" }),
  // Cài đặt > Giọng đọc: cả máy, không riêng cuốn nào.
  readAloudCacheTotal: () => api<ReadAloudCacheUsage>("/api/readaloud/cache"),
  readAloudCacheClearAll: () => api<ReadAloudCacheUsage>("/api/readaloud/cache?all=1", { method: "DELETE" }),
  // Máy tính xách tay cũng mất mạng (tàu, máy bay): giọng trực tuyến làm trước vào bộ đệm clip như VieNeu (readaloud/prepare.py chung mọi giọng).
  readAloudPrepareOnline: true,
  readAloudPrepareCancel: () => api<PrepareStatus>("/api/readaloud/prepare", { method: "DELETE" }),
  musicCues: async (bookId, chapterId) => {
    const result = await api<MusicCues>(`/api/books/${bookId}/music/chapters/${chapterId}`);
    return { ...result, cues: result.cues.map((cue) => ({ ...cue, src: mediaUrl(cue.src) })) };
  },
  voiceWarm: (voice) => {
    void api(`/api/readaloud/warm?voice=${encodeURIComponent(voice)}`, { method: "POST" }).catch(() => undefined);
  },
  musicWarm: (link) => {
    void api(`/api/music/warm?link=${encodeURIComponent(link)}`, { method: "POST" }).catch(() => undefined);
  },
  musicPlaylist: async (bookId) => {
    const result = await api<PlaylistQueue>(`/api/books/${bookId}/music/playlist`);
    return { ...result, tracks: result.tracks.map((track) => ({ ...track, src: mediaUrl(track.src) })) };
  },
  audioUrl: (bookId, chapterId) => mediaUrl(`/media/books/${bookId}/chapters/${chapterId}`),
  sampleUrl: (bookId, sampleId) => mediaUrl(`/media/books/${bookId}/samples/${sampleId}`),
  voiceUrl: (name) => mediaUrl(`/media/voices/${encodeURIComponent(name)}`),
  beginProgress: (bookId, sessionId, record) => api(`/api/listen/books/${bookId}/progress/session`, { method: "POST", body: { sessionId, record } }),
  saveProgress: (bookId, chapterId, seconds, duration, record, anchor, delivery) =>
    api<ListeningState>(`/api/listen/books/${bookId}/progress`, { method: "POST", body: { chapterId, seconds, duration, record, anchor,
      sessionId: delivery?.sessionId, revision: delivery?.revision }, keepalive: delivery?.keepalive }),
  setChapterDone: (bookId, chapterId, done, record) =>
    api<ListeningState>(`/api/listen/books/${bookId}/chapters/${chapterId}/done`, { method: "POST", body: { done, record } }),
  setFinished: (bookId, finished, record) =>
    api<ListeningState>(`/api/listen/books/${bookId}/finished`, { method: "POST", body: { finished, record } }),
  setVoice: async (bookId, voice, record) => {
    await api(`/api/listen/books/${bookId}/voice`, { method: "POST", body: { voice, record } });
  },
  setRate: async (bookId, rate, record) => {
    await api(`/api/listen/books/${bookId}/rate`, { method: "POST", body: { rate, record } });
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
  saveReading: async (bookId, chapterId, index, position, record) => {
    await api(`/api/listen/books/${bookId}/reading`, { method: "POST", body: { ...position, chapterId, index, record } });
  },
  saveNight: async (bookId, night, record) => {
    await api(`/api/listen/books/${bookId}/night`, { method: "POST", body: { ...night, record } });
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
