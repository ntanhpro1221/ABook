import { useQuery } from "@tanstack/react-query";
import { api } from "./api";

// Model đọc hiểu truyện cho riêng một cuốn (server.analysis_models): mặc định của app, hay một model khác đang có trong Ollama
// - để thử một model mới trên sách thật mà không đổi mặc định (đổi mặc định là việc của chủ sách, file khoá config.py).

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

const bare = (name: string) => name.replace(/:latest$/, "");

function describe(model: AnalysisModel): string {
  const size = model.size ? `${(model.size / 1e9).toFixed(1).replace(".", ",")} GB` : "";
  return [model.name, model.parameters, model.quantization, size].filter(Boolean).join(" · ");
}

/** Ô chọn ở bước Chất lượng; không có model nào khác mặc định (hay Ollama tắt) thì không hiện gì - không có gì để chọn. */
export function AnalysisModelPicker({ value, onChange }: { value: string; onChange: (model: string) => void }) {
  const { data } = useQuery({
    queryKey: ["analysis-models"],
    queryFn: () => api<AnalysisModels>("/api/analysis-models"),
    staleTime: 60_000,
  });
  if (!data) return null;
  const others = data.models.filter((model) => bare(model.name) !== bare(data.default));
  if (!others.length) return null;
  return (
    <div className="mt-8 max-w-2xl">
      <label htmlFor="analysis-model" className="text-sm font-medium">
        Model đọc hiểu truyện
      </label>
      <p className="mt-0.5 text-[13px] text-fg-2 text-pretty">
        Model đoán ai nói câu nào, cảm xúc ra sao. Mặc định là model của app; chọn model khác chỉ dùng cho cuốn này - để thử
        một model mới trên sách thật.
      </p>
      <select
        id="analysis-model"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="mt-2 h-9 w-full max-w-lg rounded-lg border border-line bg-panel px-2.5 text-sm text-fg outline-none focus-visible:border-accent"
      >
        <option value="">{data.default} (mặc định)</option>
        {others.map((model) => (
          <option key={model.name} value={model.name}>
            {describe(model)}
          </option>
        ))}
      </select>
    </div>
  );
}
