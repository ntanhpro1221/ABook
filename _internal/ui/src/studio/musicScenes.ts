import { formatSize } from "@/shared/format";

// Một mảnh nhạc "nối tiếp" (`continued`, music_select.choose): đoạn dài được cắt mảnh để nhạc biến đổi nhẹ, nhưng người nghe
// nghe MỘT bài chạy liền - nên tab Nhạc nền không bày nó như một lựa chọn riêng trùng bài mà ghi gọn "tiếp bài của đoạn trên".

interface SceneChoice {
  link: string | null;
  continued?: boolean;
  pinned?: boolean;
  silenced?: boolean;
}

/** Mảnh này chỉ chơi tiếp bài của đoạn trên (chưa bị ghim / để im lặng riêng) - hiện gọn, không đủ bộ nút. */
export function isContinuation(scene: SceneChoice): boolean {
  return Boolean(scene.continued && scene.link && !scene.pinned && !scene.silenced);
}

export const CONTINUED_NOTE = "↳ tiếp bài của đoạn trên";

/** Lời nút "Đổi bài": ở mảnh nối tiếp, ghim bài mới vào đây nên đổi từ chỗ này trở đi (các mảnh sau nối theo bài mới). */
export function swapButton(scene: SceneChoice): { text: string; title?: string } {
  return isContinuation(scene)
    ? { text: "Đổi từ đây", title: "Đổi bài từ chỗ này trở đi - các đoạn nối tiếp sau đó chơi theo bài mới; phần trên giữ nguyên" }
    : { text: "Đổi bài" };
}

// Danh mục cũ chưa gửi tên: dùng bảng có sẵn (cùng bộ với build_catalog.EMOTION_VI).
const EMOTION_VI: Record<string, string> = {
  peacefulness: "bình yên", tenderness: "dịu dàng", nostalgia: "hoài niệm", sadness: "buồn", joy: "vui tươi",
  playful: "tinh nghịch", power: "hào hùng", wonder: "kỳ vĩ", tension: "căng thẳng", fear: "rùng rợn",
  anger: "giận dữ", mystery: "bí ẩn", moved: "xúc động",
};
const MOOD_SHOWN = 0.5; // cường độ từ mức này mới gọi tên
const MOOD_MAX = 2;      // tối đa hai cảm xúc mạnh nhất - pha trộn thì hiện cả hai ("buồn · dịu dàng")
// Không cảm xúc nào đủ mạnh: gọi tên theo đúng các trục máy dùng chọn bài (valence, tension của đoạn, cùng thang [-1, 1] với bài trong
// danh mục, 0 = trung tính). Tension âm là thư thái, nên "căng" chỉ tính phần dương, ngưỡng như cường độ cảm xúc (soát UX a60: 71 đoạn
// tension > 0,3 sau học sinh NN-lite vẫn hiện "êm" vì nhãn chỉ đọc cảm xúc từng câu).
const TENSE_FROM = 0.5;
const SAD_TO = -0.4;
const BRIGHT_FROM = 0.4;

/** Phần của một đoạn mà nhãn không khí cần. */
export interface SceneMood {
  valence: number;
  tension?: number;
  /** 13 cường độ cảm xúc độc lập 0..1 - không cộng thành 1, đoạn có thể vừa buồn vừa dịu. */
  emotions?: Record<string, number>;
}

/** Không khí của đoạn: các cảm xúc mạnh nhất (cường độ độc lập, nên có thể hai cảm xúc cùng cao); không cảm xúc nào đủ mạnh thì
 *  gọi theo vui/buồn và căng thẳng máy đã dùng để chọn bài - "căng thẳng", "buồn", "tươi vui", còn lại "êm" (đoạn kể bình thường). */
export function moodOf(scene: SceneMood, names?: Record<string, string>): string {
  const strong = Object.entries(scene.emotions ?? {})
    .filter(([, value]) => value >= MOOD_SHOWN)
    .sort((a, b) => b[1] - a[1])
    .slice(0, MOOD_MAX)
    .map(([key]) => names?.[key] ?? EMOTION_VI[key] ?? key);
  if (strong.length) return strong.join(" · ");
  if ((scene.tension ?? 0) >= TENSE_FROM) return "căng thẳng";
  if (scene.valence <= SAD_TO) return "buồn";
  if (scene.valence >= BRIGHT_FROM) return "tươi vui";
  return "êm";
}

/** Lượt tải sẵn nhạc nền của cuốn (GET /music `download`): bài thứ `done` trong `total`, MB đã tải / tổng (0 = chưa biết cỡ). */
export interface MusicDownload {
  active: boolean;
  done: number;
  total: number;
  doneBytes?: number;
  totalBytes?: number;
}

/** Dòng tiến độ ở tab Nhạc nền: MB khi biết cỡ (soát UX a23: tải 190 MB mà không báo gì), không thì đếm bài. */
export function downloadText(download: MusicDownload): string {
  const tracks = `bài ${Math.min(download.done + 1, download.total)}/${download.total}`;
  if (!download.totalBytes) return `Đang tải sẵn nhạc nền: ${tracks}`;
  return `Đang tải sẵn nhạc nền: ${formatSize(download.doneBytes ?? 0)} / ${formatSize(download.totalBytes)} (${tracks})`;
}

/** Phần đã xong (0-1) cho vạch tiến độ. */
export function downloadShare(download: MusicDownload): number {
  if (download.totalBytes) return (download.doneBytes ?? 0) / download.totalBytes;
  return download.total ? download.done / download.total : 0;
}
