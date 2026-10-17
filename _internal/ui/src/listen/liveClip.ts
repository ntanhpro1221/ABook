import { ReadAloudError, type ReadAloudClip } from "./readAloud";
import type { WordSpan } from "./words";

// Clip Edge đang được đọc, nhận DẦN từ máy chủ (abook/webui/server.py `ClipStream`, `POST /api/readaloud/clip` có `stream: true`): người nghe nghe được sau khoảng 2 giây
// thay vì chờ đọc xong cả đoạn. Lời đáp là chuỗi bản ghi: 1 byte loại + 4 byte độ dài (big-endian) + nội dung.
//   A: byte MP3 (nối thẳng vào phần trước)   W: JSON {words, duration_ms, heard_ms} - mốc chữ tạm, thay bản trước
//   E: JSON {url, duration_ms, words} - xong (giống JSON thường)   X: JSON {message, reason} - lỗi sau khi đã phát
//   C: JSON {word} - một mảnh giữa clip hỏng (uxfix63): tiếng sẽ dừng trước chữ `word` của clip, phần trước vẫn về hết rồi mới tới X

export const CLIP_STREAM_TYPE = "application/vnd.abook.clipstream";

export type LiveEvent = "audio" | "words" | "cut" | "done" | "failed";

/** Edge trả MP3 CBR 48 kbps (abook/readaloud/edge.py BITRATE_BPS): 6 byte mỗi ms - đổi số byte đã về ra thời lượng tiếng đã có. */
export const MP3_BYTES_PER_MS = 6;

/** Mốc (ms) đặt cho chữ chưa có tiếng khi tô sáng ([LiveClip.shownWords]): xa hơn mọi đoạn có thể dài, vẫn hữu hạn. */
export const UNHEARD_MS = 1e9;

/** Kết quả cuối của clip phát luồng (bản ghi E): file đã nằm trong bộ đệm của máy chủ, `bytes` = mọi khúc đã nhận nối lại. */
export interface LiveFinal {
  url: string;
  durationMs: number;
  words: WordSpan[];
  bytes: Blob;
}

/** Clip đang về. Bộ máy phát nối `chunks` vào MediaSource ([LiveFeed]) và nghe `on` để cập nhật mốc chữ / độ dài khi xong / bỏ clip khi hỏng. */
export class LiveClip {
  /** Các khúc MP3 đã về, theo thứ tự (giữ cả khi đã nối vào MediaSource: phần tử audio dựng lại giữa chừng thì nối lại từ đầu). */
  readonly chunks: Uint8Array[] = [];
  /** Mốc chữ tạm tính trên phần đã phát (chữ chưa tới đứng cuối phần ấy); `[]` tới bản ghi W đầu. */
  words: WordSpan[] = [];
  /** Mốc kết thúc (ms) của chữ THẬT cuối cùng Edge đã báo, theo bản W mới nhất (máy chủ cũ / chưa có W: null): chữ có mốc bắt đầu từ đây trở đi là chữ chưa tới, bị dồn về cuối phần đã phát. */
  heardMs: number | null = null;
  /** Chữ (đếm trong clip) tiếng sẽ dừng trước nó - bản ghi C, một mảnh giữa clip đã hỏng hẳn trong lúc các mảnh trước còn đang về; null khi chưa có. Bộ máy xin phần tiếp từ chữ ấy NGAY. */
  cutAt: number | null = null;
  state: "open" | "done" | "failed" = "open";
  final: LiveFinal | null = null;
  error: ReadAloudError | null = null;
  private listeners = new Set<(event: LiveEvent) => void>();

  on(listener: (event: LiveEvent) => void): () => void {
    this.listeners.add(listener);
    return () => void this.listeners.delete(listener);
  }

  private bytes = 0;

  /** Thời lượng tiếng (ms) của các byte đã về ([MP3_BYTES_PER_MS]). */
  get receivedMs(): number {
    return this.bytes / MP3_BYTES_PER_MS;
  }

  push(chunk: Uint8Array): void {
    this.chunks.push(chunk);
    this.bytes += chunk.length;
    this.fire("audio");
  }

  /** Mốc chữ để TÔ SÁNG: như [words], nhưng chữ chưa tới (bắt đầu từ [heardMs] trở đi - máy chủ dồn chúng về cuối phần đã có) bị đẩy ra xa mọi chỗ tiếng có thể tới. Không thì khi tiếng chạm hết phần đã có mà bản W kế chưa về,
   *  "chữ cuối đã bắt đầu" là chữ cuối đoạn và nó sáng lóe rồi quay lại (a59d); đẩy đi thì tô đứng yên ở chữ cuối đã có tiếng. Chưa có `heardMs` (máy chủ cũ): giữ nguyên. */
  get shownWords(): WordSpan[] {
    const heard = this.heardMs;
    if (heard === null) return this.words;
    return this.words.map((span): WordSpan => (span[0] >= heard ? [UNHEARD_MS, UNHEARD_MS] : span));
  }

  setWords(words: WordSpan[], heardMs: number | null = null): void {
    this.words = words;
    this.heardMs = heardMs;
    this.fire("words");
  }

  cut(word: number): void {
    if (this.state !== "open" || this.cutAt !== null) return;
    this.cutAt = word;
    this.fire("cut");
  }

  finish(final: LiveFinal): void {
    if (this.state !== "open") return;
    this.final = final;
    this.words = final.words;
    this.state = "done";
    this.fire("done");
  }

  fail(error: ReadAloudError): void {
    if (this.state !== "open") return;
    this.error = error;
    this.state = "failed";
    this.fire("failed");
  }

  private fire(event: LiveEvent): void {
    [...this.listeners].forEach((listener) => listener(event));
  }
}

export interface ClipRecord {
  kind: string;
  body: Uint8Array;
}

/** Tách bản ghi từ các khúc mạng: khúc mạng có thể cắt giữa bản ghi, phần dở được đệm lại tới khúc sau. */
export class RecordReader {
  private pending = new Uint8Array(0);

  push(data: Uint8Array): ClipRecord[] {
    if (data.length) {
      const joined = new Uint8Array(this.pending.length + data.length);
      joined.set(this.pending);
      joined.set(data, this.pending.length);
      this.pending = joined;
    }
    const out: ClipRecord[] = [];
    let at = 0;
    while (this.pending.length - at >= 5) {
      const size = new DataView(this.pending.buffer, this.pending.byteOffset + at + 1, 4).getUint32(0, false);
      if (this.pending.length - at - 5 < size) break;
      out.push({ kind: String.fromCharCode(this.pending[at]), body: this.pending.slice(at + 5, at + 5 + size) });
      at += 5 + size;
    }
    this.pending = this.pending.slice(at);
    return out;
  }

  /** Còn byte chưa thành bản ghi trọn vẹn (luồng đứt giữa bản ghi)? */
  get dangling(): boolean {
    return this.pending.length > 0;
  }
}

const decoder = new TextDecoder();
const json = (body: Uint8Array): Record<string, unknown> => JSON.parse(decoder.decode(body)) as Record<string, unknown>;
const spans = (value: unknown): WordSpan[] => (Array.isArray(value) ? (value as WordSpan[]) : []);

/** Đọc lời đáp phát luồng của máy chủ. Trả clip NGAY khi bản ghi A đầu tiên về (`durationMs` 0 = chưa biết, bộ máy giữ độ dài ước; `words` rỗng; `live` là phần còn lại đang về);
 *  lỗi trước byte đầu (X, đứt kết nối) thì ném `ReadAloudError` như lúc máy chủ trả lỗi. Sau đó vẫn đọc tiếp trong nền: W / E / X / đứt kết nối cập nhật `live`. `toUrl`: đổi đường dẫn
 *  máy chủ trả sang địa chỉ dùng được (mã phiên). */
export function clipFromStream(body: ReadableStream<Uint8Array> | null, toUrl: (path: string) => string): Promise<ReadAloudClip> {
  const lost = () => new ReadAloudError("Mất kết nối với giọng đọc giữa chừng.", "service");
  if (!body) return Promise.reject(lost());
  const reader = body.getReader();
  const records = new RecordReader();
  const live = new LiveClip();
  return new Promise<ReadAloudClip>((resolve, reject) => {
    let opened = false;
    const open = () => {
      if (opened) return;
      opened = true;
      resolve({ url: "", durationMs: 0, words: [], live });
    };
    const handle = (record: ClipRecord) => {
      if (record.kind === "A") {
        live.push(record.body);
        open();
      } else if (record.kind === "W") {
        const tentative = json(record.body);
        live.setWords(spans(tentative.words), typeof tentative.heard_ms === "number" ? tentative.heard_ms : null);
      } else if (record.kind === "E") {
        const done = json(record.body);
        live.finish({ url: toUrl(String(done.url)), durationMs: Number(done.duration_ms), words: spans(done.words), bytes: new Blob(live.chunks as BlobPart[], { type: "audio/mpeg" }) });
        open();
      } else if (record.kind === "C") {
        live.cut(Number(json(record.body).word));
      } else if (record.kind === "X") {
        const failure = json(record.body);
        throw new ReadAloudError(String(failure.message || "Giọng đọc không phản hồi."), String(failure.reason || "service"));
      }
    };
    const fail = (error: unknown) => {
      const reason = error instanceof ReadAloudError ? error : lost();
      if (!opened) reject(reason);
      else live.fail(reason);
    };
    void (async () => {
      try {
        for (;;) {
          const { done, value } = await reader.read();
          if (done) break;
          for (const record of records.push(value)) handle(record);
        }
      } catch (error) {
        fail(error);
        return;
      }
      if (live.state === "open") fail(lost()); // hết luồng mà chưa có E / X: đứt kết nối
    })();
  });
}

/** Trình duyệt phát được MP3 qua MediaSource (phát luồng clip). */
export function liveClipsSupported(): boolean {
  try {
    return typeof MediaSource !== "undefined" && typeof MediaSource.isTypeSupported === "function" && MediaSource.isTypeSupported("audio/mpeg");
  } catch {
    return false;
  }
}
