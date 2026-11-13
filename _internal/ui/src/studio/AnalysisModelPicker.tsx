import { formatDecimal } from "@/shared/number";
import { S } from "../shared/strings.generated";
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
  if (Number.isFinite(billions) && /b$/i.test(model.parameters.trim())) parts.push(S.s_0_ti_tham_so_b28c5d22(formatDecimal(billions, 1)));
  else if (model.parameters) parts.push(model.parameters);
  if (model.size) {
    parts.push(S.s_khoang_0_bo_nho_card_58802271(formatSize(model.size)));
    if (defaultSize > 0) {
      if (model.size > defaultSize * 1.3) parts.push(S.s_nang_va_cham_hon_mac_dinh_91d5acea);
      else if (model.size < defaultSize * 0.75) parts.push(S.s_nhe_va_nhanh_hon_mac_dinh_dce4bb68);
    }
  }
  return parts.join(" · ");
}

/** Nói cỡ và bộ nhớ cần dùng; khoá model chỉ là giá trị của lựa chọn. */
export function experimentalLabel(model: AnalysisModel, defaultSize = 0): string {
  const hint = modelHint(model, defaultSize);
  return S.s_ban_thu_nghiem_0_2606182c(hint ? ` · ${hint}` : "");
}

/** Bước xác nhận dùng tên dễ đọc; khoá model chỉ gửi máy chủ. */
export function analysisChoiceLabel(chosen: string, seedModel?: string): string {
  return chosen
    ? S.s_ban_thu_nghiem_0_158876c9(seedModel === chosen ? S.s_nhu_phan_truoc_74dc8ee9 : S.s_chi_cuon_nay_eaf5b949)
    : S.s_mac_dinh_cua_abook_2fc069a4;
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
      <summary className="cursor-pointer text-sm font-medium text-fg-2 hover:text-fg">{S.s_bo_phan_tich_truyen_9a52f60b}</summary>
      <p className="mt-2 text-body-small text-fg-2 text-pretty">{S.s_chi_chon_ban_khac_khi_muon_thu_tren_cuon_n_d2d4143b}</p>
      <label htmlFor="analysis-model" className="sr-only">{S.s_bo_phan_tich_truyen_9a52f60b}</label>
      <Select
        id="analysis-model"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="mt-2 w-full max-w-lg"
      >
        <option value="">{S.s_mac_dinh_khuyen_dung_60a7ae4e}</option>
        <optgroup label={S.s_ban_khac_thu_nghiem_73e6829a}>
          {others.map((model, index) => (
            <option key={model.name} value={model.name}>
              {index + 1}. {experimentalLabel(model, defaultSize)}
            </option>
          ))}
        </optgroup>
      </Select>
      <p className="mt-2 text-body-small text-fg-2 text-pretty">
        {value
          ? S.s_ban_thu_nghiem_chua_duoc_kiem_tren_nhieu_t_32fc14af
          : S.s_mac_dinh_may_de_xuat_cho_hau_het_cac_truye_ea11fe13}
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
