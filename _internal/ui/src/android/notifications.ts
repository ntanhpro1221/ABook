import { toast } from "sonner";
import { EbookPlayer } from "./plugins";

// Quyền hiện thông báo của Android 13+ (khay thông báo và màn khoá có nút tạm dừng / tua). Hộp xin quyền của hệ thống từng bật ngay lúc chọn giọng và
// chặn lần nghe đầu cho tới khi người nghe trả lời (soát điện thoại 03-10). Giờ: phát trước; một lần duy nhất sau khi đã có tiếng, nói vì sao rồi người nghe
// bấm "Cho phép" mới tới hộp hệ thống. Từ chối / bỏ qua: Cài đặt › Nghe có một dòng và nút mở cài đặt thông báo của ABook.

export type NotificationState = "granted" | "off";

export type NotificationApi = Pick<typeof EbookPlayer, "notificationAccess" | "requestNotificationAccess">;

const ASKED_KEY = "abook-notification-asked";

interface Memory {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

function browserMemory(): Memory | null {
  try {
    return localStorage;
  } catch {
    return null;
  }
}

export async function notificationState(api: Pick<NotificationApi, "notificationAccess"> = EbookPlayer): Promise<NotificationState> {
  try {
    return (await api.notificationAccess()).state;
  } catch {
    return "granted"; // không đọc được thì đừng làm phiền
  }
}

export const NOTIFICATION_WHY = "Để có nút tạm dừng và tua ở khay thông báo và màn khoá, cho phép ABook hiện thông báo.";

/** Nói vì sao rồi mời xin quyền, tối đa MỘT lần (nhớ lại, kể cả khi người nghe bỏ qua câu này). `notify` hiện câu + nút "Cho phép" (gọi `allow`).
 *  Trả true nếu đã mời. */
export async function offerNotificationAccess(
  api: NotificationApi = EbookPlayer,
  notify: (message: string, allow: () => void) => void = (message, allow) =>
    void toast(message, { id: "notification-access", duration: 20_000, action: { label: "Cho phép", onClick: allow }, cancel: { label: "Để sau", onClick: () => undefined } }),
  memory: Memory | null = browserMemory(),
): Promise<boolean> {
  try {
    if (memory?.getItem(ASKED_KEY)) return false;
  } catch {
    /* không đọc được bộ nhớ thì coi như chưa hỏi */
  }
  if ((await notificationState(api)) === "granted") return false;
  try {
    memory?.setItem(ASKED_KEY, "1");
  } catch {
    /* không nhớ được thì thôi */
  }
  notify(NOTIFICATION_WHY, () => void api.requestNotificationAccess().catch(() => undefined));
  return true;
}

export function openNotificationSettings(): Promise<void> {
  return EbookPlayer.openNotificationSettings();
}
