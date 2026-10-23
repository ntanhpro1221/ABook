import { EbookLibrary, type RunningExport } from "./plugins";

// Xuất MP3 / M4B / sách nói chạy ở WorkManager nên sống lâu hơn giao diện: vuốt app khỏi danh sách gần đây hay WebView tải lại thì các bảng
// `runs` của ba màn xuất mất sạch, mà việc nền vẫn chạy. Mỗi màn xuất hỏi `exportJobs` lúc mở để nối lại lượt của kiểu mình (hiện lại tiến độ,
// nhận tiếp tin xong / lỗi) - một đường chung cho cả ba.

// Lượt đã nhận tin xong / dừng / lỗi: bản chụp việc đang chạy (exportJobs) có thể về SAU các tin ấy, và không được dựng lại thanh tiến độ (hay nút Dừng)
// cho lượt đã kết thúc. Một tập cho cả ba kiểu xuất (mã lượt là mã việc WorkManager, không trùng giữa các kiểu).
const ended = new Set<string>();

/** Ghi nhận lượt `run` đã kết thúc (gọi khi tin xong / dừng / lỗi tới). */
export function noteEnded(run: string | undefined): void {
  if (!run) return;
  ended.add(run);
  if (ended.size > 64) ended.delete(ended.values().next().value as string);
}

/** Lượt `run` đã nhận tin kết thúc? Tin tiến độ muộn của nó cũng bị bỏ. */
export function isEnded(run: string | undefined): boolean {
  return !!run && ended.has(run);
}

/** Gọi `adopt` cho mỗi lượt đang chạy thuộc kiểu `kind`, trừ lượt đã nhận tin kết thúc. Không hỏi được (plugin cũ, lỗi) thì thôi - như trước. */
export function rejoinExports<K extends RunningExport["kind"]>(kind: K, adopt: (job: Extract<RunningExport, { kind: K }>) => void): void {
  void Promise.resolve()
    .then(() => EbookLibrary.exportJobs())
    .then(({ jobs }) => jobs.forEach((job) => job.kind === kind && !isEnded(job.run) && adopt(job as Extract<RunningExport, { kind: K }>)))
    .catch(() => undefined);
}
