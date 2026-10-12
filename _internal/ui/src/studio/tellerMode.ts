import { formatNumber } from "@/shared/format";
import { estimateText } from "./voiceTryText";

// Công tắc B "Người kể xưng “tôi” tự kể chuyện" (webui/teller_mode.py, abook/teller_voice.py): chữ và phép tính cái giá dùng chung cho
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
}

export const TELLER_TITLE = "Người kể xưng “tôi” tự kể chuyện";

export function tellerHint(on: boolean): string {
  return on
    ? "Cả lời dẫn của những đoạn do “tôi” kể cũng đọc bằng giọng của họ, nên đoạn nghe như một người đang kể lại. Đoạn do người khác kể và đoạn ngôi ba vẫn dùng giọng dẫn."
    : "Mặc định: lời dẫn do một người kể đọc (cùng giới với “tôi”), còn lời “tôi” nói ra vẫn là giọng của họ.";
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
  return `${what}. Thu lại ${formatNumber(plan.recorded)} câu đã thu, ${estimateText(plan.seconds, plan.measured)}.`;
}
