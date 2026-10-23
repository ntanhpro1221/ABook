import { formatNumber } from "@/shared/format";
import { estimateText } from "./voiceTryText";

// Công tắc B "Ngôi tôi tự kể" (webui/teller_mode.py, abook/teller_voice.py): chữ và phép tính cái giá dùng chung cho
// trình tạo sách và trang dự án.

export interface TellerPlan {
  /** "on": bật sẽ đổi giọng những câu này; "off": tắt trả đúng những câu B đã chuyển. */
  direction: "on" | "off";
  /** Số câu đổi giọng, trong đó `recorded` câu đã thu nên phải thu lại. */
  lines: number;
  recorded: number;
  seconds: number;
  measured: boolean;
  tellers: string[];
}

export interface TellerModeView {
  available: boolean;
  mode: "narrator" | "teller";
  /** Đã phân vai: đổi là áp ngay. Chưa: chỉ ghi ý muốn, máy áp sau khi phân vai. */
  castLocked: boolean;
  applied: boolean;
  plan: TellerPlan | null;
  /** `false` ở điện thoại mở file dự án: chỉ xem được, đổi ở máy tính có Studio (cần thu lại). */
  editableHere?: boolean;
}

export const TELLER_TITLE = "Ngôi tôi tự kể";

/** Câu thay cho nút đổi ở nơi không đổi được (điện thoại mở file dự án). */
export const TELLER_ELSEWHERE = "Đổi ở máy tính có Studio (cần thu lại).";

export function tellerHint(on: boolean): string {
  return on
    ? "Lời kể ngôi tôi đọc bằng giọng của họ."
    : "Mặc định: giọng dẫn kể, nhân vật đọc lời thoại.";
}

/** Có cần hỏi lại trước khi đổi không: chỉ khi đã có câu thu sẽ bị bỏ. */
export function needsConfirm(view: TellerModeView | undefined): boolean {
  return Boolean(view?.castLocked && view.plan && view.plan.recorded > 0);
}

/** Cái giá của lần đổi, nói như người nghe thấy: bao nhiêu câu phải thu lại, mất khoảng bao lâu. */
export function costText(plan: TellerPlan | null | undefined, turningOn: boolean): string {
  if (!plan || !plan.lines) return turningOn ? "Chưa có câu lời kể nào cần đổi giọng." : "Không còn câu nào để trả lại giọng dẫn.";
  const who = plan.tellers.length ? plan.tellers.join(", ") : "người kể";
  const what = turningOn
    ? `${formatNumber(plan.lines)} câu lời kể sẽ đọc bằng giọng của ${who}`
    : `${formatNumber(plan.lines)} câu lời kể sẽ trở về giọng dẫn`;
  if (!plan.recorded) return `${what}. Chưa câu nào trong số đó được thu nên không phải thu lại gì.`;
  // Bản thu hiện có của những câu ấy bị bỏ, không lấy lại được: nói số ấy ra, ở cả hai chiều.
  return `${what}. ${formatNumber(plan.recorded)} bản thu hiện có của những câu ấy sẽ bị bỏ và thu lại, ${estimateText(plan.seconds, plan.measured)}. Bản thu cũ không lấy lại được.`;
}
