/** Tên model phân tích cho người dùng: "abook-analyzer:v4" -> "Model phân tích bản 4". Model khác (tự chọn ở Cài đặt) giữ tên của nó. */
export function analyzerLabel(model: string): string {
  const name = model.replace(/:latest$/, "");
  const own = /^abook-analyzer:v(\d+)$/.exec(name);
  return own ? `Model phân tích bản ${own[1]}` : `Phân tích bằng ${name}`;
}
