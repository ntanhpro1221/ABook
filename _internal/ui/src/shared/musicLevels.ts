import { S } from "./strings.generated";
import { formatDecimal } from "./number";
import mix from "../../../abook/webui/assets/music_mix.json";

/** Mức nhạc nền dưới giọng đọc (dB, nhỏ hơn giọng bấy nhiêu): thanh trượt "Mức nhạc nền" của tab Nhạc nền trong Studio, hộp sửa
 *  sách và menu Nhạc nền của trình phát dùng chung. Miền, bước, mặc định đọc từ music_mix.json - một file cho máy chủ
 *  (music_plan.clamp_level), Android và Qt; chữ từng mức theo bảng chung tests/fixtures/settings/ranges.json "musicLevel". */
export const LEVEL_MIN_DB = mix.levelMinDb;
export const LEVEL_MAX_DB = mix.levelMaxDb;
export const LEVEL_STEP_DB = mix.levelStepDb;
export const DEFAULT_LEVEL_DB = mix.levelDefaultDb;

export const LEVEL_TITLE = S.s_muc_nhac_nen_a45588ff;
export const LEVEL_RESET = S.s_ve_mac_dinh_4eb6b300;

/** Năm vùng của thanh trượt, từ to tới nhỏ: mức >= cận dưới thì mang tên vùng ấy. Năm mức cũ (-14, -17, -20, -24, -28) nằm giữa
 *  vùng của chính tên mình. Vùng nhỏ nhất kèm lời "rõ lời": nhạc khó che lời đọc nhất (MIX_QA mục 7.1). */
const ZONES: [number, string][] = [
  [-15.5, S.s_to_f4b06ef6],
  [-18.5, S.s_hoi_to_953a7b53],
  [-21.5, S.s_vua_8af1c03b],
  [-25.5, S.s_nho_9c1511d3],
];
const QUIETEST = S.s_rat_nho_ro_loi_0afefef2;

export function clampLevel(value: number): number {
  return Math.min(LEVEL_MAX_DB, Math.max(LEVEL_MIN_DB, value));
}

/** Tên vùng của một mức: "To", "Hơi to", "Vừa", "Nhỏ", "Rất nhỏ (rõ lời)". */
export function levelLabel(value: number): string {
  return ZONES.find(([from]) => value >= from)?.[1] ?? QUIETEST;
}

/** Số của mức như người Việt viết: "-18,5 dB"; đúng mức mặc định thì thêm "(mặc định)". */
export function levelNumber(value: number): string {
  const text = `${formatDecimal(value)} dB`;
  return value === DEFAULT_LEVEL_DB ? S.s_0_mac_dinh_8b7237cd(text) : text;
}
