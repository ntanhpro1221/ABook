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

const KNOWN: { pattern: RegExp; summary: string; hint: string; studioHint?: string }[] = [
  {
    pattern: /out of memory|CUBLAS_STATUS_ALLOC_FAILED|CUDA error: .*memory|OutOfMemoryError|bad allocation/i,
    summary: "Card đồ hoạ hết bộ nhớ.",
    hint: "Đóng các app khác đang dùng card đồ hoạ (trò chơi, trình duyệt có video...) rồi bấm Tiếp tục.",
  },
  {
    pattern: /ollama|11434|actively refused|Connection refused|ConnectionError|Max retries exceeded/i,
    summary: "Chưa kết nối được Ollama (phần chạy mô hình phân tích).",
    hint: "Mở Ollama (biểu tượng ở khay hệ thống) rồi bấm Tiếp tục.",
    // App có Studio: Ollama là bản riêng của Studio, tự bật khi làm sách - không có biểu tượng khay để mở (soát UX a20).
    studioHint: "Studio tự bật Ollama riêng của nó nên không có gì để mở tay: bấm Tiếp tục để thử lại; nếu vẫn lỗi, vào Dự án bấm Sửa Studio.",
  },
  {
    pattern: /No space left|ENOSPC|disk full|WinError 112|not enough space|disk quota/i,
    summary: "Ổ đĩa hết chỗ trống.",
    hint: "Giải phóng dung lượng ở ổ chứa thư viện sách rồi bấm Tiếp tục.",
  },
];

/** Lỗi thô -> câu cho người nghe + việc nên làm + nguyên văn. Lỗi lạ: "Có lỗi khi làm sách" (không đọc nguyên văn lên mặt).
 *  `bundledStudio`: app đóng gói có Studio (Ollama riêng, không có biểu tượng khay) - lời khuyên theo đó.
 *  `redo`: phân tích đã bị ngắt giữa chừng - nút chính của trang là "Làm lại phân tích từ đầu", "Tiếp tục" chỉ là lối phụ có giá
 *  (stopText.asksBeforeResume), nên lời khuyên chỉ nút chính (soát a88 T3). */
export function friendlyError(raw: string, bundledStudio = false, redo = false): FriendlyError {
  const detail = raw.trim();
  const known = KNOWN.find((entry) => entry.pattern.test(detail));
  const advice = (hint: string) => (redo ? hint.replace(/([Bb])ấm Tiếp tục/g, "$1ấm Làm lại phân tích từ đầu") : hint);
  if (known) return { summary: known.summary, hint: advice((bundledStudio && known.studioHint) || known.hint), detail };
  return { summary: "Có lỗi khi làm sách.", hint: advice("Bấm Tiếp tục để thử lại; nếu vẫn lỗi, mở Chi tiết bên dưới để gửi cho người hỗ trợ."), detail };
}

const OFFLINE = /getaddrinfo failed|\[Errno 11001\]|WinError 11001|WinError 10051|WinError 10060|Network is unreachable|Temporary failure in name resolution|Name or service not known|timed out|Connection (?:aborted|reset)|RemoteDisconnected|IncompleteRead/i;

/** Lỗi dừng dở của bước "Cài Studio" (studio_setup `error`): mất mạng giữa chừng nói bằng lời người nghe và chỉ việc làm tiếp;
 *  nguyên văn vẫn trả lại ở `detail` cho "Chi tiết". Lỗi khác: nguyên văn như cũ (đã là tiếng Việt do máy chủ viết). */
export function friendlySetupError(raw: string): { summary: string; detail: string } {
  const detail = raw.trim();
  if (OFFLINE.test(detail)) return { summary: "Mất mạng giữa chừng - bấm Cài tiếp để làm tiếp.", detail };
  return { summary: detail, detail: "" };
}
