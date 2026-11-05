import mix from "../../../abook/webui/assets/music_mix.json";

/** Mức nhạc nền dưới giọng đọc (dB, nhỏ hơn giọng bấy nhiêu): thanh trượt "Mức nhạc nền" của tab Nhạc nền trong Studio, hộp sửa
 *  sách và menu Nhạc nền của trình phát dùng chung. Miền, bước, mặc định đọc từ music_mix.json - một file cho máy chủ
 *  (music_plan.clamp_level), Android và Qt; chữ từng mức theo bảng chung tests/fixtures/settings/ranges.json "musicLevel". */
export const LEVEL_MIN_DB = mix.levelMinDb;
export const LEVEL_MAX_DB = mix.levelMaxDb;
export const LEVEL_STEP_DB = mix.levelStepDb;
export const DEFAULT_LEVEL_DB = mix.levelDefaultDb;

export const LEVEL_TITLE = "Mức nhạc nền";
export const LEVEL_RESET = "Về mặc định";

/** Năm vùng của thanh trượt, từ to tới nhỏ: mức >= cận dưới thì mang tên vùng ấy. Năm mức cũ (-14, -17, -20, -24, -28) nằm giữa
 *  vùng của chính tên mình. Vùng nhỏ nhất kèm lời "rõ lời": nhạc khó che lời đọc nhất (MIX_QA mục 7.1). */
const ZONES: [number, string][] = [
  [-15.5, "To"],
  [-18.5, "Hơi to"],
  [-21.5, "Vừa"],
  [-25.5, "Nhỏ"],
];
const QUIETEST = "Rất nhỏ (rõ lời)";

export function clampLevel(value: number): number {
  return Math.min(LEVEL_MAX_DB, Math.max(LEVEL_MIN_DB, value));
}

/** Tên vùng của một mức: "To", "Hơi to", "Vừa", "Nhỏ", "Rất nhỏ (rõ lời)". */
export function levelLabel(value: number): string {
  return ZONES.find(([from]) => value >= from)?.[1] ?? QUIETEST;
}

/** Số của mức như người Việt viết: "-18,5 dB"; đúng mức mặc định thì thêm "(mặc định)". */
export function levelNumber(value: number): string {
  const text = `${String(value).replace(".", ",")} dB`;
  return value === DEFAULT_LEVEL_DB ? `${text} (mặc định)` : text;
}
