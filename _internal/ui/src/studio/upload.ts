import { api } from "@/studio/api";
import { formatSize } from "@/studio/musicLocal";

/**
 * Studio trong trình duyệt (từ xa hay ngay trên máy tính): máy đang xem không đưa được đường dẫn nào trên máy tính, nên nó
 * gửi các chương TXT (hay file EPUB / DOCX / PDF) vào thư viện của máy tính (`POST /api/sources/upload`,
 * webui/actions.upload_source - `<thư viện>/Nguồn tải lên/`, giữ mãi như nguồn trên máy: dây chuyền đọc lại nguồn mỗi lần
 * chạy tiếp), từng file một, rồi trả các thư mục trên máy tính để trình tạo sách đi tiếp như khi chọn thư mục. Gửi byte
 * nguyên vẹn (base64): bảng mã do dây chuyền nhận, như với file trên máy.
 */

/** Trần mỗi file của máy tính (webui/actions.MAX_SOURCE_UPLOAD): kiểm trước khi gửi, khỏi chờ gửi xong mới bị từ chối. */
export const UPLOAD_LIMIT = 8 * 1024 * 1024;
const LIMIT_MB = UPLOAD_LIMIT / 2 ** 20;
const ACCEPTED = /\.(txt|epub|docx|pdf)$/i;
export const UPLOAD_ACCEPT =
  ".txt,.epub,.docx,.pdf,text/plain,application/epub+zip,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document";

/** Một file người dùng chọn hay kéo vào. `path`: "Truyện/Tập 1/001.txt" khi chọn / kéo cả thư mục, "" khi là file lẻ. */
export interface Picked {
  name: string;
  size: number;
  path: string;
}

export interface UploadGroup<T extends Picked> {
  /** Thư mục gửi tới máy tính: "<lần gửi>", "<lần gửi>/<thư mục đã chọn>" hay "<lần gửi>/<thư mục>/<thư mục con>". */
  folder: string;
  files: T[];
  /** File lẻ: trình tạo sách quét từng file như "Chọn từng file" (tách một file cả truyện thì thư mục chương thay chỗ nó). */
  loose: boolean;
}

export interface UploadPlan<T extends Picked> {
  groups: UploadGroup<T>[];
  /** File lẻ không phải file truyện (ảnh, .mobi...). */
  rejected: string[];
  /** File truyện lớn hơn UPLOAD_LIMIT. */
  tooBig: string[];
  /** File trong thư mục mà trình tạo sách không lấy (không phải file truyện, nằm sâu hơn một tầng thư mục con). */
  ignored: number;
  bytes: number;
}

const collator = new Intl.Collator("vi", { numeric: true, sensitivity: "base" });
const byName = <T extends Picked>(a: T, b: T) => collator.compare(a.name, b.name);

/** "Tải lên 05-10-2026 18h22 ab12": mỗi lần gửi một thư mục riêng, hai lần gửi trong cùng phút không trộn chương vào nhau. */
export function batchName(now: Date, tag: string): string {
  const two = (value: number) => String(value).padStart(2, "0");
  return `Tải lên ${two(now.getDate())}-${two(now.getMonth() + 1)}-${now.getFullYear()} ${two(now.getHours())}h${two(now.getMinutes())} ${tag}`;
}

/**
 * Những gì sẽ gửi, theo đúng cách trình tạo sách đọc một đường dẫn: file lẻ vào thư mục của lần gửi; chọn cả thư mục thì
 * chỉ lấy file nằm ngay trong nó (tên thư mục còn nguyên - máy gợi ý nó làm tên sách), còn nếu nó chỉ có thư mục con (mỗi
 * tập một thư mục) thì mỗi thư mục con thành một tập, như "Dùng cả N thư mục". Thứ tự theo tên (2 trước 10).
 */
export function planUpload<T extends Picked>(files: T[], batch: string): UploadPlan<T> {
  const plan: UploadPlan<T> = { groups: [], rejected: [], tooBig: [], ignored: 0, bytes: 0 };
  const loose: T[] = [];
  const roots = new Map<string, { top: T[]; subs: Map<string, T[]> }>();
  for (const file of files) {
    const parts = file.path.split("/").filter(Boolean);
    const inFolder = parts.length > 1;
    if (!ACCEPTED.test(file.name) || parts.length > 3) {
      if (inFolder) plan.ignored += 1;
      else plan.rejected.push(file.name);
      continue;
    }
    if (file.size > UPLOAD_LIMIT) {
      plan.tooBig.push(file.name);
      continue;
    }
    if (!inFolder) {
      loose.push(file);
      continue;
    }
    const root = roots.get(parts[0]) ?? { top: [], subs: new Map<string, T[]>() };
    roots.set(parts[0], root);
    if (parts.length === 2) root.top.push(file);
    else root.subs.set(parts[1], [...(root.subs.get(parts[1]) ?? []), file]);
  }
  if (loose.length) plan.groups.push({ folder: batch, files: loose.sort(byName), loose: true });
  for (const name of [...roots.keys()].sort(collator.compare)) {
    const root = roots.get(name)!;
    if (root.top.length) {
      plan.groups.push({ folder: `${batch}/${name}`, files: root.top.sort(byName), loose: false });
      for (const sub of root.subs.values()) plan.ignored += sub.length;
      continue;
    }
    for (const sub of [...root.subs.keys()].sort(collator.compare)) {
      plan.groups.push({ folder: `${batch}/${name}/${sub}`, files: root.subs.get(sub)!.sort(byName), loose: false });
    }
  }
  plan.bytes = plan.groups.reduce((sum, group) => sum + group.files.reduce((total, file) => total + file.size, 0), 0);
  return plan;
}

function listed(names: string[]): string {
  const shown = names.slice(0, 3).map((name) => `“${name}”`).join(", ");
  return names.length > 3 ? `${shown} và ${names.length - 3} file khác` : shown;
}

/** Lời nhắc về những file không gửi (nói ra, không bỏ âm thầm), hay null khi không bỏ file nào. */
export function planNotice(plan: UploadPlan<Picked>): string | null {
  const lines = [
    plan.rejected.length ? `${listed(plan.rejected)} không phải file truyện - chỉ nhận .txt, .epub, .docx, .pdf.` : "",
    plan.tooBig.length ? `${listed(plan.tooBig)} lớn hơn ${LIMIT_MB} MB - máy tính chỉ nhận file tới ${LIMIT_MB} MB.` : "",
  ].filter(Boolean);
  return lines.length ? lines.join(" ") : null;
}

export interface UploadProgress {
  files: number;
  totalFiles: number;
  bytes: number;
  totalBytes: number;
}

/** "Đang gửi 3/12 file · 1,2 MB / 4,5 MB". */
export function progressLabel(progress: UploadProgress): string {
  return `Đang gửi ${progress.files}/${progress.totalFiles} file · ${formatSize(progress.bytes)} / ${formatSize(progress.totalBytes)}`;
}

/** Gửi từng file của kế hoạch; trả đường dẫn trên máy tính để quét, theo thứ tự của kế hoạch: từng file lẻ, thư mục của mỗi nhóm thư mục. */
export async function sendPlan(
  plan: UploadPlan<Picked & { file: File }>,
  onProgress: (progress: UploadProgress) => void,
): Promise<string[]> {
  const totalFiles = plan.groups.reduce((sum, group) => sum + group.files.length, 0);
  const progress = { files: 0, totalFiles, bytes: 0, totalBytes: plan.bytes };
  onProgress({ ...progress });
  const paths: string[] = [];
  for (const group of plan.groups) {
    let folder = "";
    for (const picked of group.files) {
      const result = await api<{ folder: string; path: string }>("/api/sources/upload", {
        method: "POST",
        body: { folder: group.folder, name: picked.name, data: await toBase64(picked.file) },
      });
      folder = result.folder;
      if (group.loose) paths.push(result.path);
      progress.files += 1;
      progress.bytes += picked.size;
      onProgress({ ...progress });
    }
    if (!group.loose) paths.push(folder);
  }
  return paths;
}

/** Ô chọn file (cả khi chọn thư mục: `webkitRelativePath`). */
export function pickedFromInput(list: FileList): (Picked & { file: File })[] {
  return [...list].map((file) => ({ file, name: file.name, size: file.size, path: file.webkitRelativePath || "" }));
}

/** Trình duyệt này chọn được cả thư mục? Điện thoại có thuộc tính nhưng không mở được hộp chọn thư mục. */
export function canPickFolder(): boolean {
  return typeof document !== "undefined" && "webkitdirectory" in document.createElement("input")
    && !window.matchMedia?.("(pointer: coarse)").matches;
}

/**
 * File kéo thả vào: file lẻ, hay cả thư mục (đọc tới tầng thư mục con - sâu hơn trình tạo sách không lấy). Phải gọi ngay
 * trong sự kiện `drop`: qua một `await` là trình duyệt xoá danh sách kéo thả.
 */
export function pickedFromDrop(transfer: DataTransfer): Promise<(Picked & { file: File })[]> {
  const entries = [...transfer.items].map((item) => item.webkitGetAsEntry?.() ?? null);
  if (!entries.some(Boolean)) return Promise.resolve(pickedFromInput(transfer.files));
  return Promise.all(entries.map((entry) => (entry ? walk(entry, 0) : Promise.resolve([])))).then((lists) => lists.flat());
}

async function walk(entry: FileSystemEntry, depth: number): Promise<(Picked & { file: File })[]> {
  if (entry.isFile) {
    const file = await new Promise<File>((resolve, reject) => (entry as FileSystemFileEntry).file(resolve, reject));
    return [{ file, name: file.name, size: file.size, path: depth ? entry.fullPath.replace(/^\/+/, "") : "" }];
  }
  if (depth >= 2) return [];
  const reader = (entry as FileSystemDirectoryEntry).createReader();
  const children: FileSystemEntry[] = [];
  // readEntries trả từng mẻ (Chrome: 100 mục) - đọc tới khi hết.
  for (;;) {
    const batch = await new Promise<FileSystemEntry[]>((resolve, reject) => reader.readEntries(resolve, reject));
    if (!batch.length) break;
    children.push(...batch);
  }
  return (await Promise.all(children.map((child) => walk(child, depth + 1)))).flat();
}

async function toBase64(file: File): Promise<string> {
  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary = "";
  for (let start = 0; start < bytes.length; start += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(start, start + 0x8000));
  }
  return btoa(binary);
}
