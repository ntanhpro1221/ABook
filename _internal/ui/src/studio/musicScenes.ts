import { S } from "../shared/strings.generated";
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

export const CONTINUED_NOTE = S.s_tiep_bai_cua_doan_tren_79bb9e24;

/** Lời nút "Đổi bài": ở mảnh nối tiếp, ghim bài mới vào đây nên đổi từ chỗ này trở đi (các mảnh sau nối theo bài mới). */
export function swapButton(scene: SceneChoice): { text: string; title?: string } {
  return isContinuation(scene)
    ? { text: S.s_doi_tu_day_a54eee44, title: S.s_doi_bai_tu_cho_nay_tro_di_cac_doan_noi_tie_983def0c }
    : { text: S.s_doi_bai_7b81488f };
}

// Danh mục cũ chưa gửi tên: dùng bảng có sẵn (cùng bộ với build_catalog.EMOTION_VI).
const EMOTION_VI: Record<string, string> = {
  peacefulness: S.s_binh_yen_9e77ef15, tenderness: S.s_diu_dang_deaaa55a, nostalgia: S.s_hoai_niem_799529ae, sadness: S.s_buon_a474e7e0, joy: S.s_vui_tuoi_8ebbee23,
  playful: S.s_tinh_nghich_f27e1115, power: S.s_hao_hung_fec61823, wonder: S.s_ky_vi_ac54ac08, tension: S.s_cang_thang_48be6812, fear: S.s_rung_ron_e9a9ecec,
  anger: S.s_gian_du_1565d541, mystery: S.s_bi_an_ace8c102, moved: S.s_xuc_dong_bc36f9eb,
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
  if ((scene.tension ?? 0) >= TENSE_FROM) return S.s_cang_thang_48be6812;
  if (scene.valence <= SAD_TO) return S.s_buon_a474e7e0;
  if (scene.valence >= BRIGHT_FROM) return S.s_tuoi_vui_43fac912;
  return S.s_em_07866b70;
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
  const tracks = S.s_bai_0_1_515d0997(Math.min(download.done + 1, download.total), download.total);
  if (!download.totalBytes) return S.s_dang_tai_san_nhac_nen_0_ca14ae35(tracks);
  return S.s_dang_tai_san_nhac_nen_0_1_2_48ce53ca(formatSize(download.doneBytes ?? 0), formatSize(download.totalBytes), tracks);
}

/** Phần đã xong (0-1) cho vạch tiến độ. */
export function downloadShare(download: MusicDownload): number {
  if (download.totalBytes) return (download.doneBytes ?? 0) / download.totalBytes;
  return download.total ? download.done / download.total : 0;
}
