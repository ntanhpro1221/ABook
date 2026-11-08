import { S } from "../shared/strings.generated";
import { excerpt } from "@/shared/format";

// "Nghe thử" một cách đọc tên trước khi lưu (webui/reading_preview.py): phần thuần của nút - lời từ chối và dòng chú thích.

/** Máy chủ trả mã `reason` kèm lời từ chối; câu chữ cho người nghe nằm ở đây (máy chủ giữ mã, giao diện giữ chữ). */
const REFUSALS: Record<string, string> = {
  producing: S.s_may_dang_lam_sach_thu_lai_khi_xong_eea5a664,
  gpu: S.s_card_do_hoa_dang_ban_thu_lai_sau_it_phut_f63229bf,
  studio: S.s_cai_studio_de_nghe_thu_60d07d86,
  busy: S.s_dang_nghe_thu_cau_khac_bam_lai_sau_it_giay_8047fd55,
};

/** Lời báo khi nghe thử bị từ chối: mã quen thì câu viết sẵn, không thì lời của máy chủ (đã là tiếng Việt). */
export function refusalText(reason: unknown, fallback: string, named = false): string {
  // `named`: máy chủ đã nói cuốn nào đang chặn và ở pha nào (busyBook) - câu ấy đúng hơn câu chung, giữ nguyên.
  if (reason === "producing" && named) return fallback;
  return (typeof reason === "string" && REFUSALS[reason]) || fallback;
}

/** Dòng dưới nút sau khi nghe: lúc thu thật sẽ nghe GẦN như vậy (âm thanh không phải lúc nào cũng tái lập từng byte), câu nào, giọng ai. */
export function previewCaption(text: string, speaker: string): string {
  return S.s_luc_thu_that_se_nghe_gan_nhu_vay_cau_0_1_e031974e(excerpt(text, 70), speaker ? S.s_giong_0_8c67e1bb(speaker) : "");
}

/** Dòng trạng thái dưới nút "Nghe thử": đang chờ máy / đang phát / đã nghe xong / bị từ chối - luôn nói MỘT điều, để người nghe biết
 *  nút đã làm gì (soát UX a8: bấm xong không thấy gì). `bookBusy`: sách đang thu - nói trước, đừng đợi bị từ chối. */
export function tryNote(state: {
  pending: boolean;
  refusal: string;
  playing: boolean;
  caption: string | null;
  bookBusy: boolean;
}): string | null {
  if (state.pending) return S.s_may_dang_doc_thu_lan_dau_co_the_mat_vai_ch_51a539dc;
  if (state.refusal) return state.refusal;
  if (state.playing && state.caption) return S.s_dang_phat_0_b347d105(state.caption);
  if (state.caption) return S.s_da_nghe_xong_bam_nghe_thu_de_nghe_lai_0_7365513e(state.caption);
  if (state.bookBusy) return S.s_dang_lam_sach_ban_thu_lai_khi_xong_4414af8b;
  return null;
}
