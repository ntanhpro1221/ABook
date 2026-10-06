// "Tải về máy" cho sách "Trên máy khác" (webui/remote_books.py `Downloads`, như điện thoại tải sách của máy tính): chữ nói tình trạng
// bằng lời người nghe nhận ra - đang tải bao nhiêu, đã xong thì nghe được cả khi máy kia tắt, hỏng thì phần đã tải vẫn giữ.

/** Tình trạng tải của một cuốn (GET /api/listen/books/<mã>/download). */
export interface RemoteDownload {
  state: "none" | "running" | "done" | "failed" | "cancelled";
  files: number;
  filesDone: number;
  bytes: number;
  bytesDone: number;
  error: string;
}

/** Phần đã tải, 0..1: theo byte (chương, nhạc) khi biết cỡ, không thì theo số file. */
export function downloadFraction(status: RemoteDownload): number {
  if (status.state === "done") return 1;
  const fraction = status.bytes > 0 ? status.bytesDone / status.bytes : status.files > 0 ? status.filesDone / status.files : 0;
  return Math.max(0, Math.min(1, fraction));
}

export interface DownloadNote {
  tone: "running" | "done" | "error" | "paused";
  title: string;
  /** Câu phụ - để trống khi không cần. */
  detail: string;
  /** Nút trên dòng tình trạng: dừng khi đang tải, tải tiếp khi đã dừng / hỏng. */
  action: "cancel" | "resume" | null;
}

/** Dòng tình trạng dưới tên sách; `null` khi chưa tải gì và không có gì để nói. `computer`: tên máy giữ sách. */
export function downloadNote(status: RemoteDownload | null | undefined, computer: string): DownloadNote | null {
  if (!status) return null;
  const where = computer || "máy kia";
  const percent = `${Math.floor(downloadFraction(status) * 100)}%`;
  switch (status.state) {
    case "running":
      return { tone: "running", title: `Đang tải về máy… ${percent}`, detail: "Vẫn nghe được trong lúc tải", action: "cancel" };
    case "done":
      return { tone: "done", title: "Đã tải về máy", detail: `Nghe được cả khi ${where} tắt`, action: null };
    case "failed":
      return {
        tone: "error",
        title: `Chưa tải xong về máy (${percent})`,
        detail: `${status.error || "Máy kia không trả lời."} Phần đã tải vẫn giữ trên máy này.`,
        action: "resume",
      };
    case "cancelled":
      return { tone: "paused", title: `Đã dừng tải (${percent})`, detail: "Phần đã tải vẫn giữ trên máy này.", action: "resume" };
    default:
      return null;
  }
}

/** Mục trong menu của sách: tên + câu phụ, tuỳ tình trạng. */
export function downloadMenuLabel(status: RemoteDownload | null | undefined, computer: string): { label: string; hint: string; disabled: boolean } {
  const where = computer || "máy kia";
  if (status?.state === "running") return { label: "Dừng tải về máy", hint: `Đã tải ${Math.floor(downloadFraction(status) * 100)}%`, disabled: false };
  if (status?.state === "done") return { label: "Đã tải về máy", hint: `Nghe được cả khi ${where} tắt`, disabled: true };
  if (status && status.filesDone > 0) return { label: "Tải nốt về máy", hint: `Đã có ${Math.floor(downloadFraction(status) * 100)}% trên máy này`, disabled: false };
  return { label: "Tải về máy", hint: `Để nghe cả khi ${where} tắt`, disabled: false };
}
