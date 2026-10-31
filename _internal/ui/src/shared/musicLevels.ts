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

/** Lời kèm vài mức để người nghe biết chọn mức nào: -28 là mức nhạc khó che lời đọc nhất (MIX_QA mục 7.1). */
export const LEVEL_NOTES: Record<number, string> = {
  [-28]: "rõ lời",
};

/** Chữ một mức trong ô chọn: tên mức, thêm lời kèm trong ngoặc nếu có ("Rất nhỏ (rõ lời)"). */
export function levelText(value: number, name: string): string {
  const note = LEVEL_NOTES[value];
  return note ? `${name} (${note})` : name;
}

/** Danh sách mức cho ô chọn: các mức có sẵn, thêm mức hiện tại của sách nếu nó không trùng mức nào (sách đóng gói ở -18 dB). */
export function levelOptions(current: number): [number, string][] {
  return MUSIC_LEVELS.some(([value]) => value === current)
    ? MUSIC_LEVELS
    : [...MUSIC_LEVELS, [current, `${String(current).replace(".", ",")} dB (của sách)`] as [number, string]].sort((a, b) => b[0] - a[0]);
}
