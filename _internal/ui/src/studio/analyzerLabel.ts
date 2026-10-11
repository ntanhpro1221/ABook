/** Tên model phân tích cho người dùng: "abook-analyzer:v4" -> "Model phân tích bản 4". Model khác (tự chọn ở Cài đặt) giữ tên của nó. */
export function analyzerLabel(model: string): string {
  const name = model.replace(/:latest$/, "");
  const own = /^abook-analyzer:v(\d+)$/.exec(name);
  return own ? `Model phân tích bản ${own[1]}` : `Phân tích bằng ${name}`;
}

/** Giọng kể ở dòng thông tin đầu trang dự án: đang chờ đổi thì giọng SẼ dùng + "(chờ áp dụng)", không phải giọng cũ như chưa có
 *  gì (soát UX a24). */
export function narratorLabel(settings: { narrator: string; narratorPending?: string }): string {
  if (settings.narratorPending) return `Giọng kể ${settings.narratorPending} (chờ áp dụng)`;
  return settings.narrator ? `Giọng kể ${settings.narrator}` : "";
}
