/** Mức nhạc nền dưới giọng đọc (dB, nhỏ hơn giọng bấy nhiêu) người nghe chọn được - tab Nhạc nền của Studio và hộp sửa sách
 *  trên trang nghe dùng chung. -20 là mặc định của máy (music_plan.DEFAULT_LEVEL_DB). */
export const DEFAULT_LEVEL_DB = -20;

export const MUSIC_LEVELS: [number, string][] = [
  [-14, "To"],
  [-17, "Hơi to"],
  [-20, "Vừa (mặc định)"],
  [-24, "Nhỏ"],
  [-28, "Rất nhỏ"],
];

/** Danh sách mức cho ô chọn: các mức có sẵn, thêm mức hiện tại của sách nếu nó không trùng mức nào (sách đóng gói ở -18 dB). */
export function levelOptions(current: number): [number, string][] {
  return MUSIC_LEVELS.some(([value]) => value === current)
    ? MUSIC_LEVELS
    : [...MUSIC_LEVELS, [current, `${String(current).replace(".", ",")} dB (của sách)`] as [number, string]].sort((a, b) => b[0] - a[0]);
}
