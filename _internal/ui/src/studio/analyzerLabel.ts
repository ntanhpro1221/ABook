import { S } from "../shared/strings.generated";
/** Tên dễ đọc; khoá kỹ thuật chỉ dùng gửi máy chủ, không đưa vào lời giải thích. */
export function analyzerLabel(model: string): string {
  const name = model.replace(/:latest$/, "");
  const own = /^abook-analyzer:v(\d+)$/.exec(name);
  return own ? S.s_bo_phan_tich_ban_0_131547c1(own[1]) : S.s_bo_phan_tich_tuy_chon_eed83d3d;
}

/** Giọng kể ở dòng thông tin đầu trang dự án: đang chờ đổi thì giọng SẼ dùng + "(chờ áp dụng)", không phải giọng cũ như chưa có
 *  gì (soát UX a24). */
export function narratorLabel(settings: { narrator: string; narratorPending?: string }): string {
  if (settings.narratorPending) return S.s_giong_ke_0_cho_ap_dung_d7c4e7f9(settings.narratorPending);
  return settings.narrator ? S.s_giong_ke_0_958dd853(settings.narrator) : "";
}
