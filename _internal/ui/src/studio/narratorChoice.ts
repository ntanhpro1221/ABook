import type { Voice } from "./api";

// Giọng dẫn của sách kể ngôi thứ nhất (abook/teller_voice.py): người dùng không tự chọn giọng thì để máy chọn cùng giới với người kể
// "tôi". Hai việc thuần của trình tạo sách: khi nào coi giọng dẫn là "do máy chọn", và giọng đề xuất của một giới.

export type TellerGender = "male" | "female";

/** Giới trong danh sách giọng của máy chủ ("Nam" / "Nữ"). */
const VOICE_GENDER: Record<TellerGender, string> = { male: "Nam", female: "Nữ" };

export interface NarratorDraft {
  /** Người dùng đã bấm một giọng (hay "Dùng lại" giọng phần trước, hay áp mẫu có ghi giọng kể). */
  narratorPicked?: boolean;
  firstPerson: string;
  /** "Làm tiếp cuốn này": giọng kể đến từ sách trước, đã là lựa chọn. ("Sửa thiết lập" điền `narratorPicked` đúng như lúc tạo.) */
  seed?: unknown;
}

/** Giọng dẫn là của máy (gửi `narrator` rỗng): có người kể "tôi", người dùng chưa chọn giọng nào, không phải sách nối tiếp, và
 *  giọng đang hiện không phải giọng mặc định người dùng đã đặt trong Cài đặt. */
export function narratorIsAuto(draft: NarratorDraft, preferred: string | undefined, voices: readonly Pick<Voice, "name">[] | undefined): boolean {
  if (!draft.firstPerson.trim() || draft.narratorPicked || draft.seed) return false;
  return !(preferred && voices?.some((voice) => voice.name === preferred));
}

/** Giọng kể chuyện máy đề xuất cho một giới (nam: Phạm Tuyên, nữ: Ngọc Linh). */
export function recommendedFor(voices: readonly Voice[] | undefined, gender: TellerGender | undefined): string | undefined {
  if (!gender) return undefined;
  return voices?.find((voice) => voice.recommended && voice.gender === VOICE_GENDER[gender])?.name;
}
