import type { ReadAloudVoice } from "./readAloud";

// Danh sách giọng ở Cài đặt: các giọng của một mô-đun đều ghi tên mô-đun trong ngoặc ("Nhẹ (VieNeu Nano)") - lặp mười một lần trong một danh sách.
// Gom theo mô-đun: tiêu đề nhóm một lần, mỗi giọng chỉ còn tên của nó. Tên đầy đủ vẫn dùng ở chỗ khác (trình phát, nhãn đọc màn hình).

export interface VoiceSection {
  /** Tên mô-đun làm tiêu đề phụ; null khi cả nhóm chung một mô-đun (tiêu đề của nhóm đã nói rồi). */
  label: string | null;
  voices: { voice: ReadAloudVoice; shown: string }[];
}

const SUFFIX = /^(.*\S)\s+\(([^()]+)\)$/;

/** Tách tên "Nhẹ (VieNeu Nano)" thành tên giọng + tên mô-đun; tên không có ngoặc cuối thì mô-đun là null. */
export function splitVoiceName(name: string): { shown: string; module: string | null } {
  const found = SUFFIX.exec(name);
  return found ? { shown: found[1], module: found[2] } : { shown: name, module: null };
}

/** Chia các giọng của một nhóm theo mô-đun (giữ thứ tự xuất hiện). Có tiêu đề phụ chỉ khi nhóm có từ hai mô-đun trở lên; giọng không ghi
 *  mô-đun giữ nguyên tên và nằm ở đầu, không tiêu đề. */
export function voiceSections(list: ReadAloudVoice[]): VoiceSection[] {
  const parts = list.map((voice) => ({ voice, ...splitVoiceName(voice.name) }));
  // Chỉ coi là mô-đun khi có từ hai giọng cùng ngoặc cuối - một giọng lẻ ("Microsoft An (vi-VN)") giữ nguyên tên.
  const counts = new Map<string, number>();
  for (const part of parts) if (part.module !== null) counts.set(part.module, (counts.get(part.module) ?? 0) + 1);
  const shared = [...counts].filter(([, count]) => count >= 2).map(([module]) => module);
  const sections: VoiceSection[] = [];
  const loose = parts.filter((part) => part.module === null || !shared.includes(part.module));
  if (loose.length) sections.push({ label: null, voices: loose.map((part) => ({ voice: part.voice, shown: part.voice.name })) });
  for (const module of shared) {
    sections.push({
      label: shared.length > 1 ? module : null,
      voices: parts.filter((part) => part.module === module).map((part) => ({ voice: part.voice, shown: part.shown })),
    });
  }
  return sections;
}
