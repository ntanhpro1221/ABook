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

function describe(model: AnalysisModel): string {
  const size = model.size ? `${(model.size / 1e9).toFixed(1).replace(".", ",")} GB` : "";
  const parameters = model.parameters.replace(".", ",");
  return [modelLabel(model.name), parameters && `${parameters} tham số`, size].filter(Boolean).join(" · ");
}

/** Ô chọn ở bước Chất lượng; không có model nào khác mặc định (hay Ollama tắt) thì không hiện gì - không có gì để chọn. */
export function AnalysisModelPicker({ value, onChange }: { value: string; onChange: (model: string) => void }) {
  const { data } = useQuery({
    queryKey: ["analysis-models"],
    queryFn: () => api<AnalysisModels>("/api/analysis-models"),
    staleTime: 60_000,
  });
  if (!data) return null;
  const others = data.models.filter((model) => modelLabel(model.name) !== modelLabel(data.default));
  if (!others.length) return null;
  return (
    <details className="group mt-8 max-w-2xl" open={Boolean(value)}>
      <summary className="cursor-pointer text-sm font-medium text-fg-2 hover:text-fg">
        Nâng cao: model đọc hiểu truyện{value ? ` - ${modelLabel(value)}` : ""}
      </summary>
      <p className="mt-2 text-[13px] text-fg-2 text-pretty">
        Model đoán ai nói câu nào, cảm xúc ra sao. Không chắc thì để mặc định - model khác chỉ dùng cho cuốn này, khi muốn thử
        một model mới trên sách thật.
      </p>
      <label htmlFor="analysis-model" className="sr-only">
        Model đọc hiểu truyện
      </label>
      <select
        id="analysis-model"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="mt-2 h-9 w-full max-w-lg rounded-lg border border-line bg-panel px-2.5 text-sm text-fg outline-none focus-visible:border-accent"
      >
        <option value="">{modelLabel(data.default)} (mặc định)</option>
        {others.map((model) => (
          <option key={model.name} value={model.name}>
            {describe(model)}
          </option>
        ))}
      </select>
    </details>
  );
}
