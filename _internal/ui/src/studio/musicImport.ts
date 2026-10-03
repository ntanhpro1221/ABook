import { api } from "./api";
import { pickFiles } from "./data";
import { mergeImports, type ImportResult } from "./musicLocal";

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

/** Nhập một file. Không cần mô-đun "Phân tích nhạc": máy chưa có nó thì bài ở "chưa phân tích" (thẻ + độ dài đọc ngay trên máy). */
async function importOne(path: string): Promise<ImportResult> {
  return api<ImportResult>("/api/music/local/import", { method: "POST", body: { paths: [path] } });
}

/** Mở hộp chọn file rồi nhập. Lỗi lúc mở hộp chọn file thì ném; lỗi giữa lượt nhập thì trả trong `error` cùng phần đã nhập được. */
export async function importMusic(progress: MusicProgress): Promise<MusicImportOutcome> {
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
      const latest = await importOne(path);
      results.push(latest);
      progress(index + 1, paths.length, latest);
    }
  } catch (error) {
    return { result: results.length ? mergeImports(results) : null, error: error instanceof Error ? error : new Error(String(error)) };
  }
  return { result: mergeImports(results) };
}
