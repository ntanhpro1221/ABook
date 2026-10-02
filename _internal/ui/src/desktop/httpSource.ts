import type { MusicCredit, MusicCue } from "@/listen/musicBed";
import type { Bookmark, Cast, ListenBook, ListeningRecord, ListeningSession, ListeningState, NightSession, Script } from "@/listen/model";
import type { ListenSource } from "@/listen/source";
import { api, mediaUrl } from "@/studio/api";

/** Phía Nghe trên máy tính: đọc từ server cục bộ (abook/webui). */
export const httpSource: ListenSource = {
  kind: "desktop",
  library: () => api<ListenBook[]>("/api/listen/library"),
  book: (id) => api<ListenBook>(`/api/listen/books/${id}`),
  script: (bookId, chapterId) => api<Script>(`/api/books/${bookId}/chapters/${chapterId}/script`),
  cast: (bookId) => api<Cast>(`/api/books/${bookId}/cast`),
  musicCues: async (bookId, chapterId) => {
    const result = await api<{ cues: MusicCue[]; levelDb: number; credits?: Record<string, MusicCredit> }>(`/api/books/${bookId}/music/chapters/${chapterId}`);
    return { ...result, cues: result.cues.map((cue) => ({ ...cue, src: mediaUrl(cue.src) })) };
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
