import { toast } from "sonner";

// Lần đầu nhạc nền theo cảnh kêu lên (máy tính và điện thoại dùng chung): người nghe chưa chọn gì mà đã có nhạc, nên nói một lần rằng nhạc tự đổi theo cảnh và đổi ở đâu.
// Nhớ trên máy (localStorage); không đọc / ghi được thì cứ nhắc mỗi phiên một lần - không để lỗi bộ nhớ chặn trình phát.

export const SCENE_MUSIC_HINT_KEY = "abook:scene-music-hint";
export const SCENE_MUSIC_HINT = {
  title: "Nhạc nền đổi theo cảnh",
  description: "Bạn muốn nhạc khác thì chọn ở nút Nhạc nền (hình nốt nhạc).",
} as const;

type Store = Pick<Storage, "getItem" | "setItem">;

let toldThisSession = false;

function browserStore(): Store | null {
  try {
    return typeof localStorage === "undefined" ? null : localStorage;
  } catch {
    return null;
  }
}

/** Có nên nhắc lúc này không - và ghi nhớ là đã nhắc (mỗi máy một lần, mỗi phiên một lần nếu không ghi nhớ được). */
export function takeSceneMusicHint(store: Store | null = browserStore()): boolean {
  if (toldThisSession) return false;
  try {
    if (store?.getItem(SCENE_MUSIC_HINT_KEY)) return false;
    store?.setItem(SCENE_MUSIC_HINT_KEY, "1");
  } catch {
    // không ghi nhớ được: nhắc một lần trong phiên này
  }
  toldThisSession = true;
  return true;
}

/** Lời mời cần người nghe bấm (xin quyền thông báo của điện thoại - android/notifications.ts): đang hiện thì lời nhắc nhạc chờ nó đi rồi mới hiện.
 *  Hiện chồng lên thì lời mời bị đẩy xuống ngay lúc ngón tay đang tới nút "Cho phép" - lần bấm đầu trượt (soát a66). */
export const PRIORITY_TOASTS: readonly string[] = ["notification-access"];
const WAIT_STEP_MS = 1000;

function priorityShowing(): boolean {
  return toast.getToasts().some((item) => PRIORITY_TOASTS.includes(String(item.id)) && !("dismiss" in item && item.dismiss));
}

/** Bài đầu tiên của nhạc nền theo cảnh vừa kêu: nhắc một lần - sau lời mời quan trọng nếu nó đang hiện. */
export function tellSceneMusic(busy: () => boolean = priorityShowing, show: () => void = showSceneMusicHint): void {
  if (!takeSceneMusicHint()) return;
  const tell = () => (busy() ? void setTimeout(tell, WAIT_STEP_MS) : show());
  tell();
}

function showSceneMusicHint(): void {
  toast(SCENE_MUSIC_HINT.title, { id: "scene-music-hint", duration: 12_000, description: SCENE_MUSIC_HINT.description });
}

/** Kiểm thử: quên mọi nhắc nhở của phiên. */
export function resetSceneMusicHint(): void {
  toldThisSession = false;
}
