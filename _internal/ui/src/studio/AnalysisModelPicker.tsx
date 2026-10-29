import { formatSize } from "@/shared/format";
import { Select } from "@/shared/ui";
import { MotionRegion } from "@/shared/MotionRegion";
import { toggleDetails, type DetailsLike } from "@/shared/motion";
import { useEffect, useRef, useState, type ReactNode } from "react";
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

/** Chuẩn hoá khoá để đối chiếu các bản đã có trên máy. */
export const modelLabel = (name: string) => name.replace(/:latest$/, "");

/** Gợi ý một dòng cho model khác (chỉ từ những gì Ollama báo): cỡ và nặng nhẹ so với mặc định. Model nặng hơn = cần card đồ hoạ
 *  nhiều bộ nhớ hơn và chạy chậm hơn; "bộ nhớ card" ước theo cỡ file model, chưa tính phần ngữ cảnh. */
export function modelHint(model: AnalysisModel, defaultSize = 0): string {
  const parts: string[] = [];
  // "4.0B" -> "4 tỉ tham số": người đọc không cần biết ký hiệu B (soát UX a5 01-10).
  const billions = Number.parseFloat(model.parameters);
  if (Number.isFinite(billions) && /b$/i.test(model.parameters.trim())) parts.push(`${String(Math.round(billions * 10) / 10).replace(".", ",")} tỉ tham số`);
  else if (model.parameters) parts.push(model.parameters);
  if (model.size) {
    parts.push(`khoảng ${formatSize(model.size)} bộ nhớ card`);
    if (defaultSize > 0) {
      if (model.size > defaultSize * 1.3) parts.push("nặng và chậm hơn mặc định");
      else if (model.size < defaultSize * 0.75) parts.push("nhẹ và nhanh hơn mặc định");
    }
  }
  return parts.join(" · ");
}

/** Nói cỡ và bộ nhớ cần dùng; khoá model chỉ là giá trị của lựa chọn. */
export function experimentalLabel(model: AnalysisModel, defaultSize = 0): string {
  const hint = modelHint(model, defaultSize);
  return `Bản thử nghiệm${hint ? ` · ${hint}` : ""}`;
}

/** Bước xác nhận dùng tên dễ đọc; khoá model chỉ gửi máy chủ. */
export function analysisChoiceLabel(chosen: string, seedModel?: string): string {
  return chosen
    ? `Bản thử nghiệm (${seedModel === chosen ? "như phần trước" : "chỉ cuốn này"})`
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

/** Tên các model dùng được cho một cuốn (model mặc định + model Ollama đang có), hay undefined khi chưa biết (chưa tải xong, Ollama tắt). */
export function useAvailableModelNames(): string[] | undefined {
  const { data } = useAnalysisModels();
  return data?.reachable ? [data.default, ...data.models.map((model) => model.name)] : undefined;
}

/** Ô chọn ở bước Chất lượng; không có model nào khác mặc định (hay Ollama tắt) thì không hiện gì - không có gì để chọn. */
export function AnalysisModelPicker({ value, onChange }: { value: string; onChange: (model: string) => void }) {
  const { data } = useAnalysisModels();
  if (!data) return <MotionRegion />;
  const others = data.models.filter((model) => modelLabel(model.name) !== modelLabel(data.default));
  if (!others.length) return <MotionRegion />;
  const defaultSize = data.models.find((model) => modelLabel(model.name) === modelLabel(data.default))?.size ?? 0;
  return (
    <MotionRegion>
    <OpenWith open={Boolean(value)}>
      <summary className="cursor-pointer text-sm font-medium text-fg-2 hover:text-fg">
        Bộ phân tích truyện
      </summary>
      <p className="mt-2 text-[0.8125rem] text-fg-2 text-pretty">
        Chỉ chọn bản khác khi muốn thử trên cuốn này.
      </p>
      <label htmlFor="analysis-model" className="sr-only">
        Bộ phân tích truyện
      </label>
      <Select
        id="analysis-model"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="mt-2 w-full max-w-lg"
      >
        <option value="">Mặc định (khuyên dùng)</option>
        <optgroup label="Bản khác (thử nghiệm)">
          {others.map((model, index) => (
            <option key={model.name} value={model.name}>
              {index + 1}. {experimentalLabel(model, defaultSize)}
            </option>
          ))}
        </optgroup>
      </Select>
      <p className="mt-1.5 text-[0.8125rem] text-fg-2 text-pretty">
        {value
          ? "Bản thử nghiệm: chưa được kiểm trên nhiều truyện, kết quả có thể kém hơn mặc định."
          : "Mặc định: máy đề xuất cho hầu hết các truyện, không cần chỉnh gì."}
      </p>
    </OpenWith>
    </MotionRegion>
  );
}

/** <details> mở theo giá trị (chọn mẫu ở TemplateBar đặt / bỏ model) mà không qua bấm: mở / gập bằng toggleDetails như khi bấm (installDetailsMotion
 *  chỉ bắt cú bấm), không đổi thuộc tính `open` cứng. Lúc dựng thì mở sẵn theo giá trị, không chuyển động. */
function OpenWith({ open, children }: { open: boolean; children: ReactNode }) {
  const box = useRef<HTMLDetailsElement>(null);
  const [initial] = useState(open);
  useEffect(() => {
    const details = box.current;
    if (!details || details.dataset.motion || details.open === open) return;
    toggleDetails(details as unknown as DetailsLike);
  }, [open]);
  return <details ref={box} className="group mt-8 max-w-2xl" open={initial}>{children}</details>;
}
