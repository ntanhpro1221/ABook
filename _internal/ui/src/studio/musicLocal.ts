// "Nhạc của tôi": nhạc người dùng tự nhập (abook/webui/music_local.py, docs/MUSIC_IMPORT.md). Phần thuần (không React) để thử riêng.

/** Một bài trong kho của máy (music_local.LocalMusic.info). `analysed` false = chưa có bộ phân tích âm thanh cho ra không khí
 *  của bài: máy không tự chọn nó, nhưng ghim tay được. */
export interface LocalTrack {
  link: string;
  title: string;
  creator: string;
  duration: number;
  analysed: boolean;
  name: string;
  album?: string;
  genre?: string;
  bytes: number;
}

/** Bộ đọc nhạc (ffmpeg) của máy tính: bản app chỉ-nghe tải ở lần nhập đầu tiên (abook/webui/ffmpeg_setup.py). */
export interface MusicReader {
  state: "idle" | "downloading" | "ready" | "error";
  done: number;
  total: number;
  /** Lý do tải hỏng, tiếng Việt; rỗng nếu không lỗi. */
  error: string;
  /** Dùng được ngay (đã tải xong, hay máy có sẵn ffmpeg). */
  ready: boolean;
}

export interface LocalMusicView {
  tracks: LocalTrack[];
  /** Đã có bộ phân tích âm thanh trên máy này chưa. */
  analyzer: boolean;
  /** Máy tính có; điện thoại đọc nhạc ở lõi native nên không có. */
  reader?: MusicReader;
}

export interface ImportResult extends LocalMusicView {
  added: LocalTrack[];
  existing: LocalTrack[];
  failed: string[];
  /** Máy chưa có bộ đọc nhạc: chưa nhập gì, bộ đọc đang được tải - đợi `reader.ready` rồi gửi lại đúng các file ấy. */
  needsReader?: boolean;
}

export const LOCAL_PREFIX = "local:";

export function isLocal(link: string): boolean {
  return link.startsWith(LOCAL_PREFIX);
}

/** Mã sha1 (40 hex) của file trong link `local:<sha1>`; link khác dạng -> null. */
export function localDigest(link: string): string | null {
  const digest = isLocal(link) ? link.slice(LOCAL_PREFIX.length) : "";
  return /^[0-9a-f]{40}$/.test(digest) ? digest : null;
}

/** Đường "Nghe thử" một bài: bài của tôi qua kho của máy này, bài danh mục qua đường danh mục. */
export function previewPath(link: string): string {
  const digest = localDigest(link);
  return digest ? `/api/music/local/${digest}/file` : `/api/music/track?link=${encodeURIComponent(link)}`;
}

/** Trạng thái phân tích, nói bằng điều người nghe thấy (không nói model nào). */
export function analysisLabel(track: Pick<LocalTrack, "analysed">): string {
  return track.analysed ? "Đã phân tích - máy có thể tự chọn" : "Chưa phân tích - máy chưa tự chọn, bạn vẫn ghim được";
}

/** Gộp kết quả của nhiều lượt nhập (mỗi file một lượt, để thấy tiến độ). Danh sách bài lấy của lượt cuối. */
export function mergeImports(results: ImportResult[]): ImportResult {
  const last = results[results.length - 1];
  return {
    tracks: last?.tracks ?? [],
    analyzer: last?.analyzer ?? false,
    added: results.flatMap((result) => result.added),
    existing: results.flatMap((result) => result.existing),
    failed: results.flatMap((result) => result.failed),
  };
}

/** Câu báo sau khi nhập: nói rõ bao nhiêu bài đã vào, bao nhiêu đã có sẵn, file nào không nhập được và vì sao. */
export function importSummary(result: Pick<ImportResult, "added" | "existing" | "failed">): {
  kind: "success" | "warning" | "error";
  title: string;
  description?: string;
} {
  const { added, existing, failed } = result;
  const parts: string[] = [];
  if (added.length) parts.push(`${added.length} bài mới`);
  if (existing.length) parts.push(`${existing.length} bài đã có sẵn từ trước`);
  if (!added.length && !existing.length) {
    return { kind: "error", title: failed.length > 1 ? "Không nhập được file nào" : "Không nhập được file này", description: failed.join("\n") };
  }
  const title = `Đã nhập: ${parts.join(", ")}`;
  const unanalysed = added.filter((track) => !track.analysed).length;
  const notes: string[] = [];
  if (failed.length) notes.push(failed.join("\n"));
  if (unanalysed) notes.push(`${unanalysed} bài chưa phân tích - máy chưa tự chọn, bạn ghim được ở “Đổi bài”.`);
  return { kind: failed.length ? "warning" : "success", title, description: notes.join("\n") || undefined };
}
