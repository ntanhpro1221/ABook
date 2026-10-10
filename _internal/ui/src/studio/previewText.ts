import { excerpt } from "@/shared/format";

// "Nghe thử" một cách đọc tên trước khi lưu (webui/reading_preview.py): phần thuần của nút - lời từ chối và dòng chú thích.

/** Máy chủ trả mã `reason` kèm lời từ chối; câu chữ cho người nghe nằm ở đây (máy chủ giữ mã, giao diện giữ chữ). */
const REFUSALS: Record<string, string> = {
  producing: "Máy đang làm một cuốn sách nên chưa nghe thử được - thử lại khi cuốn ấy xong",
  gpu: "Card đồ hoạ đang bận - thử lại sau ít phút",
  studio: "Cần cài phần làm sách trước khi nghe thử",
  busy: "Đang nghe thử câu khác - bấm lại sau ít giây",
};

/** Lời báo khi nghe thử bị từ chối: mã quen thì câu viết sẵn, không thì lời của máy chủ (đã là tiếng Việt). */
export function refusalText(reason: unknown, fallback: string, named = false): string {
  // `named`: máy chủ đã nói cuốn nào đang chặn và ở pha nào (busyBook) - câu ấy đúng hơn câu chung, giữ nguyên.
  if (reason === "producing" && named) return fallback;
  return (typeof reason === "string" && REFUSALS[reason]) || fallback;
}

/** Dòng dưới nút sau khi nghe: lúc thu thật sẽ nghe GẦN như vậy (âm thanh không phải lúc nào cũng tái lập từng byte), câu nào, giọng ai. */
export function previewCaption(text: string, speaker: string): string {
  return `Lúc thu thật sẽ nghe gần như vậy · câu “${excerpt(text, 70)}”${speaker ? ` · giọng ${speaker}` : ""}`;
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
  if (state.pending) return "Máy đang đọc thử - lần đầu có thể mất vài chục giây";
  if (state.refusal) return state.refusal;
  if (state.playing && state.caption) return `Đang phát · ${state.caption}`;
  if (state.caption) return `Đã nghe xong - bấm “Nghe thử” để nghe lại · ${state.caption}`;
  if (state.bookBusy) return "Máy đang làm sách này nên chưa nghe thử được - thử lại khi cuốn này xong";
  return null;
}
