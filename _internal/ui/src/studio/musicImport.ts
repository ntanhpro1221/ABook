import { api } from "./api";
import { pickFiles } from "./data";
import { mergeImports, type ImportResult, type LocalMusicView, type MusicReader } from "./musicLocal";

// Nhập "Nhạc của tôi" (docs/MUSIC_IMPORT.md): một cửa cho mọi nơi có nút "Nhập nhạc của tôi…". Máy tính: hộp chọn file của máy
// (`/api/dialog/files`) rồi nhập từng file qua `/api/music/local/import`; điện thoại: hộp chọn file của hệ thống + nhập ở lõi
// native (android/musicImport.ts đăng ký ở đây) - cùng JSON `ImportResult` ở cả hai nơi.

/** Tiến độ: đã xong `done` / `total` file; `latest` = lời đáp của file vừa nhập (kèm danh sách bài mới nhất). */
export type MusicProgress = (done: number, total: number, latest?: ImportResult) => void;

/** Cách nhập riêng của nền tảng: chọn file + nhập hết, trả kết quả gộp; null = người dùng không chọn file nào. */
export type NativeMusicImport = (progress: MusicProgress) => Promise<ImportResult | null>;

let native: NativeMusicImport | null = null;

export function setNativeMusicImport(next: NativeMusicImport | null): void {
  native = next;
}

/** Nền tảng này nhập nhạc bằng lõi native (điện thoại) - không cần hộp chọn file của máy chủ. */
export function hasNativeMusicImport(): boolean {
  return native !== null;
}

export interface MusicImportOutcome {
  /** Kết quả gộp của những file đã nhập; null = người dùng không chọn file nào. */
  result: ImportResult | null;
  /** Dừng giữa chừng (mất kết nối, máy chủ lỗi...): `result` vẫn là phần đã vào. */
  error?: Error;
}

/** Báo tình trạng bộ đọc nhạc lúc phải tải nó (lần nhập đầu trên máy chỉ-nghe); null = không còn gì để báo. */
export type ReaderNotice = (reader: MusicReader | null) => void;

let readerDecision: ((retry: boolean) => void) | null = null;
let readerPollMs = 1000;

/** Bộ đọc nhạc tải hỏng và đang đợi người dùng: "Thử lại" tải lại rồi nhập tiếp đúng các file ấy. */
export function retryMusicReader(): void {
  readerDecision?.(true);
}

/** Bộ đọc nhạc tải hỏng và đang đợi người dùng: bỏ lượt nhập này. */
export function cancelMusicReader(): void {
  readerDecision?.(false);
}

/** Chỉ để thử: khoảng cách giữa hai lần hỏi tiến độ tải. */
export function setReaderPollInterval(ms: number): void {
  readerPollMs = ms;
}

/** Phần trăm đã tải của bộ đọc nhạc, 0..100. */
export function readerPercent(reader: Pick<MusicReader, "done" | "total">): number {
  return reader.total > 0 ? Math.min(100, Math.floor((reader.done / reader.total) * 100)) : 0;
}

/** Câu báo cho người dùng khi bộ đọc nhạc đang tải hay tải hỏng. */
export function readerLabel(reader: MusicReader): string {
  if (reader.state === "error") return `Không tải được bộ đọc nhạc: ${reader.error}`;
  return `Đang tải bộ đọc nhạc (~30 MB, một lần) ${readerPercent(reader)}%`;
}

/** Đợi bộ đọc nhạc tải xong: hỏi `/api/music/local` ~mỗi giây; lỗi thì đợi người dùng bấm "Thử lại" (POST .../reader) hay bỏ. */
async function waitForReader(first: MusicReader | undefined, onReader?: ReaderNotice): Promise<void> {
  let reader = first;
  try {
    for (;;) {
      if (!reader) throw new Error("Máy chủ không báo tình trạng bộ đọc nhạc");
      if (reader.ready) return;
      onReader?.(reader);
      if (reader.state === "error") {
        const reason = reader.error;
        const retry = await new Promise<boolean>((resolve) => {
          readerDecision = resolve;
        });
        readerDecision = null;
        if (!retry) throw new Error(`Không tải được bộ đọc nhạc: ${reason}`);
        reader = (await api<LocalMusicView>("/api/music/local/reader", { method: "POST" })).reader;
        continue;
      }
      await new Promise((resolve) => setTimeout(resolve, readerPollMs));
      reader = (await api<LocalMusicView>("/api/music/local")).reader;
    }
  } finally {
    readerDecision = null;
    onReader?.(null);
  }
}

/** Nhập một file; máy chưa có bộ đọc nhạc thì đợi nó tải xong rồi gửi lại đúng file ấy. */
async function importOne(path: string, onReader?: ReaderNotice): Promise<ImportResult> {
  for (;;) {
    const latest = await api<ImportResult>("/api/music/local/import", { method: "POST", body: { paths: [path] } });
    if (!latest.needsReader) return latest;
    await waitForReader(latest.reader, onReader);
  }
}

/** Mở hộp chọn file rồi nhập. Lỗi lúc mở hộp chọn file thì ném; lỗi giữa lượt nhập thì trả trong `error` cùng phần đã nhập được. */
export async function importMusic(progress: MusicProgress, onReader?: ReaderNotice): Promise<MusicImportOutcome> {
  if (native) {
    try {
      return { result: await native(progress) };
    } catch (error) {
      return { result: null, error: error instanceof Error ? error : new Error(String(error)) };
    }
  }
  const paths = await pickFiles("Chọn nhạc của bạn", "", "music");
  if (!paths.length) return { result: null };
  const results: ImportResult[] = [];
  progress(0, paths.length);
  try {
    // Từng file một: thấy tiến độ, và một file hỏng không làm mất những file đã vào.
    for (const [index, path] of paths.entries()) {
      const latest = await importOne(path, onReader);
      results.push(latest);
      progress(index + 1, paths.length, latest);
    }
  } catch (error) {
    return { result: results.length ? mergeImports(results) : null, error: error instanceof Error ? error : new Error(String(error)) };
  }
  return { result: mergeImports(results) };
}
