// Nhãn âm sắc của một người ("trầm hẳn", "sáng hẳn") là SO VỚI GIỌNG GỐC mà máy chỉnh để hai người cùng giọng khác nhau
// (webui/humanize.voice_tone) - đứng một mình người nghe không biết "trầm hơn cái gì" (soát UX a8 07-10).
const FROM_BASE = new Set(["trầm hẳn", "hơi trầm", "sáng hẳn", "hơi sáng"]);

/** Chữ hiện sau tên giọng: "trầm hẳn" -> "chỉnh trầm hẳn so với giọng gốc"; nhãn lạ giữ nguyên. */
export function toneLabel(tone: string): string {
  const text = tone.trim();
  return FROM_BASE.has(text) ? `chỉnh ${text} so với giọng gốc` : text;
}
