/** Tên dễ đọc; khoá kỹ thuật chỉ dùng gửi máy chủ, không đưa vào lời giải thích. */
export function analyzerLabel(model: string): string {
  const name = model.replace(/:latest$/, "");
  const own = /^abook-analyzer:v(\d+)$/.exec(name);
  return own ? `Bộ phân tích bản ${own[1]}` : "Bộ phân tích tuỳ chọn";
}

/** Giọng kể ở dòng thông tin đầu trang dự án: đang chờ đổi thì giọng SẼ dùng + "(chờ áp dụng)", không phải giọng cũ như chưa có
 *  gì (soát UX a24). */
export function narratorLabel(settings: { narrator: string; narratorPending?: string }): string {
  if (settings.narratorPending) return `Giọng kể ${settings.narratorPending} (chờ áp dụng)`;
  return settings.narrator ? `Giọng kể ${settings.narrator}` : "";
}
