import type { Script } from "@/listen/model";
import { mergeTimings, VOICE_CHANGED_EVENT, type ReadAloudTimings } from "@/listen/readAloud";
import { chosenVoice } from "@/listen/readAloudVoice";
import { EbookPlayer, ReadAloud, type ReadAloudPlugin } from "./plugins";

// "Nghe ngay" trên điện thoại: LÕI NATIVE (Media3 + TextToSpeech) tự đọc chương chỉ-có-chữ trong hàng đợi như mọi chương - tắt màn hình vẫn đọc
// tiếp. JavaScript chỉ (1) hỏi mốc thời gian câu / chữ mà lõi đã có (`ReadAloud.script`) khi lõi báo `readAloudScript`, ghi vào đúng khoá kịch bản
// chữ mà màn đọc dùng (cùng khoá ReadAloudEngine ghi trên máy tính), nên màn đọc sáng đoạn / chữ không có trường hợp riêng; (2) báo lõi giọng
// người nghe vừa chọn.

/** Phần của QueryClient mà bộ theo dõi dùng. */
export interface ScriptCache {
  getQueryData(key: readonly unknown[]): unknown;
  setQueryData(key: readonly unknown[], value: Script): unknown;
}

export function textScriptKey(bookId: string, chapterId: number) {
  return ["listen", "script", bookId, chapterId, "text"] as const;
}

/** Lõi báo có mốc mới cho chương: hỏi lại và gắn vào kịch bản chữ đang có trong bộ nhớ (chưa mở chương thì thôi - lần mở sau
 *  `chapterScriptQuery` tự hỏi mốc). Trả true nếu đã cập nhật. */
export async function refreshScript(
  client: ScriptCache,
  api: Pick<ReadAloudPlugin, "script">,
  bookId: string,
  chapterId: number,
): Promise<boolean> {
  const key = textScriptKey(bookId, chapterId);
  if (!(client.getQueryData(key) as Script | undefined)) return false;
  let timings: ReadAloudTimings;
  try {
    timings = await api.script({ bookId, chapterId });
  } catch {
    return false;
  }
  const current = (client.getQueryData(key) as Script | undefined);
  if (!current) return false;
  client.setQueryData(key, mergeTimings(current, timings));
  return true;
}

/** Gọi một lần khi app mở. Trả hàm gỡ. */
export function watchReadAloud(
  client: ScriptCache,
  api: Pick<ReadAloudPlugin, "script" | "addListener"> = ReadAloud,
  configure: (options: { readAloudVoice: string }) => unknown = (options) => EbookPlayer.configure(options).catch(() => undefined),
): () => void {
  const handle = api.addListener("readAloudScript", (event) => void refreshScript(client, api, event.bookId, event.chapterId));
  // Người nghe đổi giọng ở menu "Giọng đọc": lõi đọc các đoạn sau bằng giọng mới.
  const onVoice = (event: Event) => {
    const bookId = String((event as CustomEvent).detail ?? "");
    void configure({ readAloudVoice: chosenVoice(bookId) });
  };
  window.addEventListener(VOICE_CHANGED_EVENT, onVoice);
  return () => {
    window.removeEventListener(VOICE_CHANGED_EVENT, onVoice);
    void handle.then((listener) => listener.remove());
  };
}
