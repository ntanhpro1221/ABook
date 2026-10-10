// Lỗi của lần làm sách (`book.lastError`) là dòng đầu của lỗi Python - đúng nguyên văn nhà phát triển, không phải lời cho người nghe.
// Lỗi hay gặp đổi sang câu tiếng Việt kèm việc nên làm; nguyên văn thu vào "Chi tiết" cho ai cần gửi đi hỏi.

export interface FriendlyError {
  /** Câu cho người nghe. */
  summary: string;
  /** Việc nên làm, nếu biết. */
  hint: string;
  /** Nguyên văn lỗi kỹ thuật. */
  detail: string;
}

const KNOWN: { pattern: RegExp; summary: string; hint: string }[] = [
  {
    pattern: /out of memory|CUBLAS_STATUS_ALLOC_FAILED|CUDA error: .*memory|OutOfMemoryError|bad allocation/i,
    summary: "Card đồ hoạ hết bộ nhớ.",
    hint: "Đóng các app khác đang dùng card đồ hoạ (trò chơi, trình duyệt có video...) rồi bấm Tiếp tục.",
  },
  {
    pattern: /ollama|11434|actively refused|Connection refused|ConnectionError|Max retries exceeded/i,
    summary: "Chưa kết nối được Ollama (phần chạy mô hình phân tích).",
    hint: "Mở Ollama (biểu tượng ở khay hệ thống) rồi bấm Tiếp tục.",
  },
  {
    pattern: /No space left|ENOSPC|disk full|WinError 112|not enough space|disk quota/i,
    summary: "Ổ đĩa hết chỗ trống.",
    hint: "Giải phóng dung lượng ở ổ chứa thư viện sách rồi bấm Tiếp tục.",
  },
];

/** Lỗi thô -> câu cho người nghe + việc nên làm + nguyên văn. Lỗi lạ: "Có lỗi khi làm sách" (không đọc nguyên văn lên mặt). */
export function friendlyError(raw: string): FriendlyError {
  const detail = raw.trim();
  const known = KNOWN.find((entry) => entry.pattern.test(detail));
  if (known) return { summary: known.summary, hint: known.hint, detail };
  return { summary: "Có lỗi khi làm sách.", hint: "Bấm Tiếp tục để thử lại; nếu vẫn lỗi, mở Chi tiết bên dưới để gửi cho người hỗ trợ.", detail };
}
