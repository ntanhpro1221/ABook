import { excerpt } from "@/shared/format";

// "Nghe thử" một cách đọc tên trước khi lưu (webui/reading_preview.py): phần thuần của nút - lời từ chối và dòng chú thích.

/** Máy chủ trả mã `reason` kèm lời từ chối; câu chữ cho người nghe nằm ở đây (máy chủ giữ mã, giao diện giữ chữ). */
const REFUSALS: Record<string, string> = {
  producing: "Đang làm sách - nghe thử khi máy rảnh",
  gpu: "Card đồ hoạ đang bận",
  studio: "Cần cài phần làm sách trước",
  busy: "Đang nghe thử câu khác - bấm lại sau ít giây",
};

/** Lời báo khi nghe thử bị từ chối: mã quen thì câu viết sẵn, không thì lời của máy chủ (đã là tiếng Việt). */
export function refusalText(reason: unknown, fallback: string): string {
  return (typeof reason === "string" && REFUSALS[reason]) || fallback;
}

/** Dòng dưới nút sau khi nghe: lúc thu thật sẽ nghe GẦN như vậy (âm thanh không phải lúc nào cũng tái lập từng byte), câu nào, giọng ai. */
export function previewCaption(text: string, speaker: string): string {
  return `Lúc thu thật sẽ nghe gần như vậy · câu “${excerpt(text, 70)}”${speaker ? ` · giọng ${speaker}` : ""}`;
}
