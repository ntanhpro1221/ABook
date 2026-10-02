// "Chia thành nhiều tập" ở trình tạo sách (abook/webui/volumes.py): máy ĐỀ XUẤT chỗ cắt, người dùng bấm mới áp và sửa được
// từng chỗ cắt theo số chương. Chỗ cắt lưu bằng ĐƯỜNG DẪN file chương đầu của mỗi tập (không phải số thứ tự) - bỏ một chương
// hay đổi thứ tự thì chỗ cắt vẫn đứng đúng chương; số chương chỉ là cách hiện và cách nhập.

export interface VolumeProposal {
  /** Nơi máy thấy ranh giới: mỗi thư mục / mỗi file EPUB một tập, hay tiêu đề chương gọi tên tập ("Tập 2"). */
  source: "folders" | "epubs" | "headings";
  /** Thứ tự chương khi chia (thư mục xếp theo tên tự nhiên); null = giữ thứ tự quét. */
  order: string[] | null;
  volumes: { label: string; start: number; startPath: string; chapters: number; firstTitle: string }[];
}

/** Như volumes.MAX_VOLUMES của máy chủ. */
export const MAX_VOLUMES = 99;

interface HasPath {
  path: string;
}

/** Các chương theo thứ tự của đề xuất (`order`); chương không có trong `order` đứng cuối, giữ thứ tự cũ. */
export function inOrder<T extends HasPath>(files: T[], order: string[] | null | undefined): T[] {
  if (!order) return files;
  const rank = new Map(order.map((path, index) => [path, index]));
  return [...files].sort((a, b) => (rank.get(a.path) ?? order.length) - (rank.get(b.path) ?? order.length));
}

/** Số chương đầu (từ 1, trong số chương còn chọn) của mỗi tập. `ordered`: mọi chương theo thứ tự chia; `excluded`: chương người
 *  dùng đã bỏ tay. Chương đầu tập bị bỏ thì tập bắt đầu ở chương còn lại kế tiếp (tập không biến mất); tập đầu luôn từ chương 1,
 *  chỗ cắt trùng nhau gộp một. */
export function startNumbers(ordered: HasPath[], startPaths: string[] | null | undefined, excluded: ReadonlySet<string> = new Set()): number[] {
  const number = new Map<string, number>();
  for (const file of ordered) if (!excluded.has(file.path)) number.set(file.path, number.size + 1);
  const found = new Set<number>([1]);
  for (const path of startPaths ?? []) {
    const from = ordered.findIndex((file) => file.path === path);
    for (let index = from; from >= 0 && index < ordered.length; index += 1) {
      const kept = number.get(ordered[index].path);
      if (kept !== undefined) {
        found.add(kept);
        break;
      }
    }
  }
  return [...found].sort((a, b) => a - b);
}

export interface VolumeRange {
  start: number;
  end: number;
  chapters: number;
}

export function ranges(starts: number[], total: number): VolumeRange[] {
  return starts.map((start, position) => {
    const end = (starts[position + 1] ?? total + 1) - 1;
    return { start, end, chapters: end - start + 1 };
  });
}

/** Đưa chỗ cắt thứ `position` (từ 1, không phải tập đầu) tới chương `number`; ngoài khoảng giữa hai chỗ cắt bên cạnh thì null. */
export function moveStart(starts: number[], position: number, number: number, total: number): number[] | null {
  if (position < 1 || position >= starts.length || !Number.isInteger(number)) return null;
  if (number <= starts[position - 1] || number >= (starts[position + 1] ?? total + 1)) return null;
  return starts.map((value, index) => (index === position ? number : value));
}

/** Thêm chỗ cắt ở chương `number` (phải là chương 2…total và chưa là chỗ cắt). */
export function addStart(starts: number[], number: number, total: number): number[] | null {
  if (!Number.isInteger(number) || number < 2 || number > total || starts.includes(number) || starts.length >= MAX_VOLUMES) return null;
  return [...starts, number].sort((a, b) => a - b);
}

export function removeStart(starts: number[], position: number): number[] {
  return position < 1 ? starts : starts.filter((_value, index) => index !== position);
}

/** Tên các sách sẽ tạo - như máy chủ đặt (continuation.continued_title): tập 1 giữ tên, tập sau "Tên · Phần N". Chỉ để HIỆN. */
export function volumeTitles(title: string, count: number): string[] {
  const base = title.replace(/\s*(?:\(phần\s*\d+\)|[·|:—–-]\s*phần\s*\d+)\s*$/i, "").trim() || title.trim();
  return Array.from({ length: count }, (_value, index) => (index === 0 ? title.trim() : `${base} · Phần ${index + 1}`));
}
