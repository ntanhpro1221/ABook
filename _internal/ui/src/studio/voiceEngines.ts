import { formatSize, modulePercent } from "./musicLocal";

// Giọng trong "Đổi giọng" (webui/voice_picker.py) đến từ nhiều máy đọc: VieNeu (mọi giọng phân vai) và máy khác người nghe chọn tay
// (ZeroTTS - mô-đun tải thêm, webui/zerotts_module.py). Phần tính toán thuần của hộp ở đây để thử được không cần giao diện.

export interface EngineVoice {
  name: string;
  engine: string;
  engineLabel: string;
  installed: boolean;
  /** Giọng chỉ có một âm sắc (máy khác VieNeu): hai người chung giọng nghe như một. */
  oneStep: boolean;
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

export function sharedText(voice: EngineVoice): string {
  const others = voice.otherUsers ? `${voice.otherUsers} người khác dùng, không cùng chương` : "";
  if (!voice.sharedWith.length) return others || "Chưa ai dùng";
  const people = voice.sharedWith.map((person) => `${person.label} (${person.chapters} chương)`).join(", ");
  const after = voice.oneStep ? "hai người sẽ nghe giống hệt nhau" : "máy lấy bậc âm sắc khác";
  return `Cùng chương với ${people} - ${after}${others ? ` · ${others}` : ""}`;
}

/** Dòng ghi chú dưới tên nhóm của một máy đọc chưa sẵn sàng trên máy này; null khi đã dùng được. */
export function moduleNote(status: EngineModuleStatus | undefined): string | null {
  if (!status || status.state === "ready") return null;
  if (status.state === "downloading") return `Đang tải giọng (${formatSize(status.total)}) ${modulePercent(status)}%`;
  if (status.state === "error") return status.error || "Chưa tải được giọng - thử lại.";
  if (status.state === "outdated") return `Có bản giọng mới (${formatSize(status.bytes)}) - tải để dùng tiếp.`;
  if (status.state === "unsupported") return "Máy này chưa dùng được những giọng này.";
  return `Máy đọc khác: cần tải thêm ${formatSize(status.bytes)}, một lần.`;
}
