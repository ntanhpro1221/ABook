import { toast } from "sonner";
import type { Script } from "@/listen/model";
import { mergeTimings, VOICE_CHANGED_EVENT, type ReadAloudTimings } from "@/listen/readAloud";
import { chosenVoice } from "@/listen/readAloudVoice";
import { ONLINE_CONSENT_EVENT, onlineConsents } from "@/listen/onlineConsent";
import { PREPARE_STATUS_KEY, type PrepareRequest, type PrepareStatus } from "@/listen/prepareAhead";
import type { ListenSource } from "@/listen/source";
import { EbookPlayer, ReadAloud, type ReadAloudPlugin } from "./plugins";

// "Nghe ngay" trên điện thoại: LÕI NATIVE (Media3 + TextToSpeech) tự đọc chương chỉ-có-chữ trong hàng đợi như mọi chương - tắt màn hình vẫn đọc
// tiếp. JavaScript chỉ (1) hỏi mốc thời gian câu / chữ mà lõi đã có (`ReadAloud.script`) khi lõi báo `readAloudScript`, ghi vào đúng khoá kịch bản
// chữ mà màn đọc dùng (cùng khoá ReadAloudEngine ghi trên máy tính), nên màn đọc sáng đoạn / chữ không có trường hợp riêng; (2) báo lõi giọng
// người nghe vừa chọn.

/** Phần của QueryClient mà bộ theo dõi dùng. */
export interface ScriptCache {
  getQueryData(key: readonly unknown[]): unknown;
  setQueryData(key: readonly unknown[], value: Script | PrepareStatus): unknown;
}

type PreparePlugin = Pick<ReadAloudPlugin, "preparePlan" | "prepareStart" | "prepareStatus" | "prepareCancel" | "prepareOptions">;

/** "Làm trước" của nguồn điện thoại (prepareAhead.ts): lõi native tự đọc chữ các chương (cùng cách chia đoạn với lúc nghe) và làm ở việc nền của
 *  WorkManager, nên chỉ gửi mã chương. Làm được cả giọng trực tuyến - để nghe khi không có mạng. */
export function phonePrepare(api: PreparePlugin = ReadAloud) {
  const ids = (request: PrepareRequest) => request.chapters.map((chapter) => chapter.id);
  return {
    readAloudPrepareOnline: true,
    readAloudPreparePlan: (request: PrepareRequest) => api.preparePlan({ bookId: request.bookId, voice: request.voice, chapterIds: ids(request) }),
    readAloudPrepare: (request: PrepareRequest) =>
      api.prepareStart({ bookId: request.bookId, voice: request.voice, chapterIds: ids(request), label: request.label, chargingOnly: request.chargingOnly }),
    readAloudPrepareStatus: () => api.prepareStatus(),
    readAloudPrepareCancel: () => api.prepareCancel(),
    readAloudPrepareOptions: (options: { chargingOnly: boolean }) => api.prepareOptions(options),
  } satisfies Partial<ListenSource>;
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
  configure: (options: { readAloudVoice?: string; readAloudBook?: string; readAloudOnlineOk?: string[] }) => unknown = (options) =>
    EbookPlayer.configure(options).catch(() => undefined),
  notify: (message: string) => unknown = (message) => toast(message, { duration: 8000 }),
): () => void {
  const handle = api.addListener("readAloudScript", (event) => void refreshScript(client, api, event.bookId, event.chapterId));
  // Lõi vừa đọc tạm một đoạn bằng giọng kế (khóa bị từ chối, hết hạn mức, mất mạng): nói cho người nghe, lõi đã lo chỉ nói một lần.
  const notice = api.addListener("readAloudNotice", (event) => void notify(event.message));
  // Tiến độ "Làm trước" (việc nền, kể cả khi màn này không mở menu): menu Giọng đọc và dấu ở danh sách chương thấy ngay.
  const prepare = api.addListener("readAloudPrepare", (status) => void client.setQueryData(PREPARE_STATUS_KEY, status));
  // Người nghe đổi giọng ở menu "Giọng đọc": lõi nhớ cho cuốn ấy (phát tiếp từ widget / xe hơi vẫn đúng giọng) và đọc các đoạn sau bằng giọng mới.
  const onVoice = (event: Event) => {
    const bookId = String((event as CustomEvent).detail ?? "");
    void configure({ readAloudVoice: chosenVoice(bookId), readAloudBook: bookId });
  };
  window.addEventListener(VOICE_CHANGED_EVENT, onVoice);
  // Đồng ý gửi chữ cho giọng trực tuyến: lõi chỉ tự sang chương chữ (chương trước hết, màn hình có thể đang tắt) khi giọng đang chọn đã được
  // đồng ý; chưa thì nó đứng ở đầu chương ấy và người nghe bấm phát - giao diện hỏi trước.
  const onConsent = () => void configure({ readAloudOnlineOk: onlineConsents() });
  onConsent();
  window.addEventListener(ONLINE_CONSENT_EVENT, onConsent);
  return () => {
    window.removeEventListener(VOICE_CHANGED_EVENT, onVoice);
    window.removeEventListener(ONLINE_CONSENT_EVENT, onConsent);
    void handle.then((listener) => listener.remove());
    void notice.then((listener) => listener.remove());
    void prepare.then((listener) => listener.remove());
  };
}
