import { useQuery } from "@tanstack/react-query";
import { api } from "./api";

// Model đọc hiểu truyện cho riêng một cuốn (server.analysis_models): mặc định của app, hay một model khác đang có trong Ollama
// - để thử một model mới trên sách thật mà không đổi mặc định (đổi mặc định là việc của chủ sách, file khoá config.py).
// Gập trong "Nâng cao" (soát UX 01-10: danh sách toàn tên kỹ thuật, người không rành không biết chọn gì - mặc định là đúng).

interface AnalysisModel {
  name: string;
  size: number;
  parameters: string;
  quantization: string;
}

interface AnalysisModels {
  default: string;
  models: AnalysisModel[];
  /** Hỏi được Ollama không (Ollama tắt thì danh sách rỗng). */
  reachable: boolean;
}

/** Tên model như người đọc thấy: bỏ đuôi ":latest" (Ollama tự thêm). */
export const modelLabel = (name: string) => name.replace(/:latest$/, "");

const gigabytes = (bytes: number) => `${(bytes / 1e9).toFixed(1).replace(".", ",")} GB`;

/** Gợi ý một dòng cho model khác (chỉ từ những gì Ollama báo): cỡ và nặng nhẹ so với mặc định. Model nặng hơn = cần card đồ hoạ
 *  nhiều bộ nhớ hơn và chạy chậm hơn; "bộ nhớ card" ước theo cỡ file model, chưa tính phần ngữ cảnh. */
export function modelHint(model: AnalysisModel, defaultSize = 0): string {
  const parts: string[] = [];
  // "4.0B" -> "4 tỉ tham số": người đọc không cần biết ký hiệu B (soát UX a5 01-10).
  const billions = Number.parseFloat(model.parameters);
  if (Number.isFinite(billions) && /b$/i.test(model.parameters.trim())) parts.push(`${String(Math.round(billions * 10) / 10).replace(".", ",")} tỉ tham số`);
  else if (model.parameters) parts.push(model.parameters);
  if (model.size) {
    parts.push(`khoảng ${gigabytes(model.size)} bộ nhớ card`);
    if (defaultSize > 0) {
      if (model.size > defaultSize * 1.3) parts.push("nặng và chậm hơn mặc định");
      else if (model.size < defaultSize * 0.75) parts.push("nhẹ và nhanh hơn mặc định");
    }
  }
  return parts.join(" · ");
}

/** Dòng trong danh sách "bản khác": nói nặng nhẹ (người chọn cần biết trước), tên kỹ thuật ở cuối để phân biệt các bản cùng cỡ. */
export function experimentalLabel(model: AnalysisModel, defaultSize = 0): string {
  const hint = modelHint(model, defaultSize);
  return `Bản thử nghiệm${hint ? ` · ${hint}` : ""} (${modelLabel(model.name)})`;
}

/** Bước xác nhận: bộ phân tích nào sẽ đọc hiểu truyện, nói bằng lời người nghe hiểu (tên kỹ thuật chỉ khi là bản thử nghiệm). */
export function analysisChoiceLabel(chosen: string, seedModel?: string): string {
  return chosen
    ? `Bản thử nghiệm “${modelLabel(chosen)}” (${seedModel === chosen ? "như phần trước" : "chỉ cuốn này"})`
    : "Mặc định của ABook";
}

/** Model mặc định + các model đang có (bước Chất lượng và bước Xác nhận dùng chung một lần hỏi). */
export function useAnalysisModels() {
  return useQuery({
    queryKey: ["analysis-models"],
    queryFn: () => api<AnalysisModels>("/api/analysis-models"),
    staleTime: 60_000,
  });
}

/** Ô chọn ở bước Chất lượng; không có model nào khác mặc định (hay Ollama tắt) thì không hiện gì - không có gì để chọn. */
export function AnalysisModelPicker({ value, onChange }: { value: string; onChange: (model: string) => void }) {
  const { data } = useAnalysisModels();
  if (!data) return null;
  const others = data.models.filter((model) => modelLabel(model.name) !== modelLabel(data.default));
  if (!others.length) return null;
  const defaultSize = data.models.find((model) => modelLabel(model.name) === modelLabel(data.default))?.size ?? 0;
  return (
    <details className="group mt-8 max-w-2xl" open={Boolean(value)}>
      <summary className="cursor-pointer text-sm font-medium text-fg-2 hover:text-fg">
        Nâng cao: bộ phân tích truyện{value ? ` - bản thử nghiệm` : ""}
      </summary>
      <p className="mt-2 text-[13px] text-fg-2 text-pretty">
        Bộ phân tích đoán ai nói câu nào, cảm xúc ra sao. Không chắc thì để mặc định - bản khác chỉ dùng cho cuốn này, khi muốn thử một
        bản mới trên sách thật.
      </p>
      <label htmlFor="analysis-model" className="sr-only">
        Bộ phân tích truyện
      </label>
      <select
        id="analysis-model"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="mt-2 h-9 w-full max-w-lg rounded-lg border border-line bg-panel px-2.5 text-sm text-fg outline-none focus-visible:border-accent"
      >
        <option value="">Mặc định của ABook (khuyên dùng)</option>
        <optgroup label="Bản khác (thử nghiệm)">
          {others.map((model) => (
            <option key={model.name} value={model.name}>
              {experimentalLabel(model, defaultSize)}
            </option>
          ))}
        </optgroup>
      </select>
      {/* Tên kỹ thuật (tag trong Ollama) chỉ ở chú thích nhỏ, cho người cần biết đúng bản nào. */}
      <p className="mt-1.5 text-[13px] text-fg-2 text-pretty">
        {value
          ? "Bản thử nghiệm: chưa được kiểm trên nhiều truyện, kết quả có thể kém hơn mặc định."
          : "Mặc định: máy đề xuất cho hầu hết các truyện, không cần chỉnh gì."}
      </p>
      <p className="mt-1 text-xs text-fg-3 break-all">Tên kỹ thuật: {modelLabel(value || data.default)}</p>
    </details>
  );
}
