// Một chính sách chờ cho mọi lời gọi từ giao diện web tới máy chủ cục bộ (studio/api.ts, listen/readAloud.ts fetchClipBytes); bản Qt: desktop_qt/src/hostwait.h + hostcall.cpp.
// Lời gọi hỏng khi KHÔNG CÓ BYTE NÀO về trong IDLE chừng ấy, không phải sau một tổng thời gian: câu trả lời dài mà vẫn đang về không bị cắt.

export const IDLE_MS = 30_000;
// Việc nặng: máy chủ làm xong cả việc rồi mới trả lời nên suốt lúc đó không byte nào về - đọc giọng (hạn Edge của chính máy chủ là TOTAL_TIMEOUT
// 90 s + 1 s, abook/readaloud/edge.py: lỗi kèm lý do của nó luôn tới trước), quét/tách nguồn, kể ngôi "tôi", tạo sách, dựng lại nhạc, nghe thử cách đọc.
export const LONG_IDLE_MS = 100_000;
// Máy chủ im quá hạn thì gửi lại đúng lời gọi ấy thêm một lần (huỷ cũng làm máy chủ thôi việc: server.py _peer_gone), rồi mới báo hết hạn.
export const ATTEMPTS = 2;
// Chốt chặn cuối của trình phát: chờ âm thanh lâu thế này nghĩa là mọi lời gọi ở dưới đã có lượt báo lỗi của nó.
export const STALL_MS = ATTEMPTS * LONG_IDLE_MS + 15_000;

// Danh sách việc nặng, giống từng chữ ở desktop_qt/src/hostwait.h và net/HostWait.kt (tests/test_host_wait_parity.py); `*` là đúng một đoạn đường dẫn.
export const LONG_WORK = [
  "/api/readaloud/clip",
  "/api/books/*/voice/preview",
  "/api/books/*/pronunciation/preview",
  "/api/books/*/music/rebuild",
  "/api/scan",
  "/api/sources/split",
  "/api/first-person",
  "/api/books",
];

/** Đường dẫn (bỏ phần `?...`) khớp một mục của [LONG_WORK]. */
export function isLongWork(path: string): boolean {
  const query = path.indexOf("?");
  const parts = (query < 0 ? path : path.slice(0, query)).split("/");
  return LONG_WORK.some((pattern) => {
    const want = pattern.split("/");
    return want.length === parts.length && want.every((part, at) => part === "*" || part === parts[at]);
  });
}

export const idleMs = (path: string): number => (isLongWork(path) ? LONG_IDLE_MS : IDLE_MS);

/** Máy chủ im quá hạn ở mọi lượt gửi. */
export class HostTimeout extends Error {
  constructor() {
    super("Máy chưa trả lời kịp.");
  }
}

/** Đọc hết thân lời đáp, mỗi khúc về là `alive()` (thân không đọc dần được thì đọc một lần). */
export async function readBytes(response: Response, alive: () => void): Promise<Uint8Array> {
  const reader = response.body?.getReader();
  if (!reader) return new Uint8Array(await response.arrayBuffer());
  const parts: Uint8Array[] = [];
  let size = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    alive();
    parts.push(value);
    size += value.length;
  }
  const all = new Uint8Array(size);
  let at = 0;
  for (const part of parts) {
    all.set(part, at);
    at += part.length;
  }
  return all;
}

export async function readText(response: Response, alive: () => void): Promise<string> {
  if (!response.body?.getReader) return response.text(); // thân không đọc dần được: một lần
  return new TextDecoder().decode(await readBytes(response, alive));
}

/** Một lời gọi theo chính sách chờ: `start` gửi (có tín hiệu huỷ), `read` đọc lời đáp và gọi `alive()` mỗi khi có byte về. Im quá `idle` ms thì huỷ lượt đó và gửi lại một lần, im nữa thì ném [HostTimeout].
 *  `outer`: người gọi bỏ lời gọi - lỗi gốc ném ra như cũ, không gửi lại. `read` trả về (kể cả khi chỉ giao thân lời đáp cho nơi đọc dần) là hết hạn canh; tín hiệu `outer` vẫn huỷ được thân ấy. */
export async function watchedCall<T>(
  start: (signal: AbortSignal) => Promise<Response>,
  idle: number,
  read: (response: Response, alive: () => void) => Promise<T>,
  outer?: AbortSignal,
): Promise<T> {
  for (let attempt = 1; ; ++attempt) {
    const controller = new AbortController();
    let stalled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const alive = () => {
      clearTimeout(timer);
      timer = setTimeout(() => {
        stalled = true;
        controller.abort();
      }, idle);
    };
    const relay = () => controller.abort();
    if (outer?.aborted) controller.abort();
    else outer?.addEventListener("abort", relay, { once: true });
    alive();
    try {
      const response = await start(controller.signal);
      alive();
      return await read(response, alive);
    } catch (error) {
      outer?.removeEventListener("abort", relay);
      if (!stalled || outer?.aborted) throw error;
      if (attempt >= ATTEMPTS) throw new HostTimeout();
    } finally {
      clearTimeout(timer);
    }
  }
}

/** GET một file của máy chủ cục bộ (clip đã xong) theo chính sách chờ: trả lời đã đọc hết, dựng lại thành Response để nơi gọi dùng như `fetch`. */
export async function fetchWatched(url: string, fetcher: typeof fetch = fetch): Promise<Response> {
  return watchedCall(
    (signal) => fetcher(url, { signal }),
    IDLE_MS,
    async (response, alive) => new Response(response.status === 204 ? null : ((await readBytes(response, alive)) as BlobPart), { status: response.status, headers: response.headers }),
  );
}
