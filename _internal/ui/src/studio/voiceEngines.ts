import { S } from "../shared/strings.generated";
import { formatSize } from "@/shared/format";
import { CANCELLED_NOTE, modulePercent } from "./musicLocal";

// Giọng trong "Đổi giọng" (webui/voice_picker.py) đến từ nhiều máy đọc: VieNeu (mọi giọng phân vai) và máy khác người nghe chọn tay
// (ZeroTTS - mô-đun tải thêm, webui/zerotts_module.py). Phần tính toán thuần của hộp ở đây để thử được không cần giao diện.

export interface EngineVoice {
  name: string;
  engine: string;
  engineLabel: string;
  installed: boolean;
  /** Người chung preset sẽ nghe cùng giọng. */
  sharedWith: { label: string; chapters: number }[];
  otherUsers: number;
}

/** Trạng thái mô-đun tải thêm của một máy đọc (zerotts_module.status). */
export interface EngineModuleStatus {
  state: "missing" | "downloading" | "ready" | "outdated" | "error" | "unsupported";
  done: number;
  total: number;
  bytes: number;
  error: string;
  /** Lần tải vừa rồi bị người nghe huỷ (phần đã tải giữ lại, bấm tải thì làm tiếp). */
  cancelled?: boolean;
  /** Đang tải và huỷ được: hộp hiện nút "Huỷ". */
  cancellable?: boolean;
  /** Giọng đã tải xong từng lần nhưng một phần bị mất hay hỏng (file cắt cụt, sai bản): nút tải là nút SỬA đúng phần ấy. */
  damaged?: boolean;
}

export interface EngineGroup<V extends EngineVoice> {
  engine: string;
  label: string;
  installed: boolean;
  voices: V[];
}

/** Nhóm theo máy đọc, giữ thứ tự máy chủ gửi (VieNeu trước) và thứ tự giọng trong mỗi nhóm. */
export function groupByEngine<V extends EngineVoice>(voices: readonly V[]): EngineGroup<V>[] {
  const groups: EngineGroup<V>[] = [];
  for (const voice of voices) {
    let group = groups.find((item) => item.engine === voice.engine);
    if (!group) {
      group = { engine: voice.engine, label: voice.engineLabel, installed: voice.installed, voices: [] };
      groups.push(group);
    }
    group.voices.push(voice);
  }
  return groups;
}

/** Tên nhóm cho người nghe: máy đọc chính (VieNeu) là "Giọng chính", các máy khác là "Giọng thêm" (đánh số khi có hai nhóm thêm
 *  trở lên) - tên máy đọc là chuyện nội bộ. Trả về nhãn theo thứ tự `groups`. */
export function plainGroupLabels(groups: readonly { engine: string }[]): string[] {
  const extras = groups.filter((group) => group.engine !== "vieneu").length;
  let seen = 0;
  return groups.map((group) => (group.engine === "vieneu" ? S.s_giong_chinh_4a3858e3 : extras > 1 ? S.s_giong_them_0_fc9c414c(++seen) : S.s_giong_them_f6d2cefe));
}

/** `current`: giọng người này đang đọc - không nói "Chưa ai dùng" về một giọng đang được dùng. */
export function sharedText(voice: EngineVoice, current = false): string {
  const others = voice.otherUsers ? S.s_0_nguoi_khac_dung_khong_cung_chuong_9e46519d(voice.otherUsers) : "";
  if (!voice.sharedWith.length) return others || (current ? S.s_giong_dang_doc_cho_nguoi_nay_16983253 : S.s_chua_ai_dung_3ba5b001);
  const people = voice.sharedWith.map((person) => S.s_0_1_chuong_a776ede8(person.label, person.chapters)).join(", ");
  const after = S.s_hai_nguoi_se_nghe_giong_het_nhau_958bdccc;
  return S.s_cung_chuong_voi_0_1_2_fce54130(people, after, others ? ` · ${others}` : "");
}

/** Hộp "Đổi giọng" của người kể: giọng nhân vật đang giữ không chọn được - nói của ai (tối đa ba tên). */
export function takenText(takenBy: string[]): string {
  const named = takenBy.slice(0, 3).join(", ");
  const rest = takenBy.length > 3 ? S.s_va_0_nguoi_khac_cc066f39(takenBy.length - 3) : "";
  return S.s_dang_la_giong_cua_0_1_nguoi_ke_can_giong_r_9f7b35e6(named, rest);
}

/** Dòng ghi chú dưới tên nhóm của một máy đọc chưa sẵn sàng trên máy này; null khi đã dùng được. */
export function moduleNote(status: EngineModuleStatus | undefined): string | null {
  if (!status || status.state === "ready") return null;
  if (status.state === "downloading") return S.s_dang_tai_giong_0_1_c53995be(formatSize(status.total), modulePercent(status));
  if (status.state === "error") return status.error || S.s_chua_tai_duoc_giong_thu_lai_b81aafc6;
  if (status.state === "unsupported") return S.s_may_nay_chua_dung_duoc_nhung_giong_nay_89504253;
  const cancelled = status.cancelled ? `${CANCELLED_NOTE} ` : "";
  if (status.damaged) return S.s_0_giong_nay_da_tai_nhung_mot_phan_bi_mat_h_d97ecfc6(cancelled);
  if (status.state === "outdated") return S.s_0_co_ban_giong_moi_1_tai_de_dung_tiep_c24fe37d(cancelled, formatSize(status.bytes));
  return S.s_0_may_doc_khac_can_tai_them_1_mot_lan_058187fb(cancelled, formatSize(status.bytes));
}
