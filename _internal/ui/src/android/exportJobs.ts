import { EbookLibrary, type RunningExport } from "./plugins";

// Xuất MP3 / M4B / sách nói chạy ở WorkManager nên sống lâu hơn giao diện: vuốt app khỏi danh sách gần đây hay WebView tải lại thì các bảng
// `runs` của ba màn xuất mất sạch, mà việc nền vẫn chạy. Mỗi màn xuất hỏi `exportJobs` lúc mở để nối lại lượt của kiểu mình (hiện lại tiến độ,
// nhận tiếp tin xong / lỗi) - một đường chung cho cả ba.

/** Gọi `adopt` cho mỗi lượt đang chạy thuộc kiểu `kind`. Không hỏi được (plugin cũ, lỗi) thì thôi - như trước. */
export function rejoinExports<K extends RunningExport["kind"]>(kind: K, adopt: (job: Extract<RunningExport, { kind: K }>) => void): void {
  void Promise.resolve()
    .then(() => EbookLibrary.exportJobs())
    .then(({ jobs }) => jobs.forEach((job) => job.kind === kind && adopt(job as Extract<RunningExport, { kind: K }>)))
    .catch(() => undefined);
}
