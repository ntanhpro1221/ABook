import { describe, expect, it } from "vitest";
import { friendlyError, friendlySetupError } from "./errorText";

describe("friendlyError", () => {
  it("nói thẳng khi card đồ hoạ hết bộ nhớ, kèm việc nên làm", () => {
    const shown = friendlyError("RuntimeError: CUDA out of memory. Tried to allocate 2.00 GiB");
    expect(shown.summary).toBe("Card đồ hoạ hết bộ nhớ.");
    expect(shown.hint).toContain("bấm Tiếp tục");
    expect(shown.detail).toContain("CUDA out of memory");
  });

  it("nhận ra Ollama không chạy và ổ đĩa đầy", () => {
    expect(friendlyError("httpx.ConnectError: [WinError 10061] No connection could be made because the target machine actively refused it").summary).toContain("Ollama");
    expect(friendlyError("OSError: [Errno 28] No space left on device").summary).toBe("Ổ đĩa hết chỗ trống.");
    expect(friendlyError("OSError: [WinError 112] There is not enough space on the disk").summary).toBe("Ổ đĩa hết chỗ trống.");
  });

  it("app có Studio: lời về Ollama không bảo mở biểu tượng khay (Ollama riêng của Studio không có)", () => {
    const raw = "httpx.ConnectError: actively refused it";
    expect(friendlyError(raw).hint).toContain("khay hệ thống");
    const bundled = friendlyError(raw, true);
    expect(bundled.hint).not.toContain("khay");
    expect(bundled.hint).toContain("Sửa Studio");
    expect(friendlyError("OSError: [Errno 28] No space left on device", true).hint).toContain("Giải phóng");
  });

  it("cài Studio dở vì mất mạng: lời cho người nghe, nguyên văn ở Chi tiết", () => {
    const raw = "Lỗi ở bước ollama: URLError: <urlopen error [Errno 11001] getaddrinfo failed>";
    const shown = friendlySetupError(raw);
    expect(shown.summary).toBe("Mất mạng giữa chừng - bấm Cài tiếp để làm tiếp.");
    expect(shown.detail).toBe(raw);
    expect(friendlySetupError("Đã dừng - bấm Cài tiếp để làm tiếp từ bước dở.")).toEqual({ summary: "Đã dừng - bấm Cài tiếp để làm tiếp từ bước dở.", detail: "" });
  });

  it("phân tích bị ngắt: lời khuyên chỉ nút chính 'Làm lại phân tích từ đầu', không bảo bấm Tiếp tục (a88 T3)", () => {
    for (const raw of ["RuntimeError: CUDA out of memory", "httpx.ConnectError: actively refused it", "OSError: [Errno 28] No space left on device", "KeyError: 'x'"]) {
      expect(friendlyError(raw).hint).toMatch(/[Bb]ấm Tiếp tục/);
      for (const studio of [false, true]) {
        const redo = friendlyError(raw, studio, true).hint;
        expect(redo).not.toMatch(/[Bb]ấm Tiếp tục/);
        expect(redo).toMatch(/Làm lại phân tích từ đầu/);
      }
    }
  });

  it("đĩa đầy của SQLite và cổng tài nguyên được nhận là thiếu đĩa, nói số GB còn lại (a96)", () => {
    expect(friendlyError("sqlite3.OperationalError: database or disk is full").summary).toBe("Ổ đĩa hết chỗ trống.");
    const gate = friendlyError("disk free 4.0 GB", true);
    expect(gate.summary).toBe("Ổ đĩa chứa thư viện sách chỉ còn 4.0 GB.");
    expect(gate.hint).toContain("Giải phóng thêm dung lượng");
    expect(friendlyError("disk free 8.0 GB", true, true).hint).not.toMatch(/[Bb]ấm Tiếp tục/);
  });

  it("model phân tích không sẵn sàng: không khẳng định là lỗi kết nối; Studio biết model mất thì nói thẳng và chỉ Sửa Studio (a96)", () => {
    const raw = "Ollama/Qwen model abook-analyzer:v4 không sẵn sàng. Pipeline dừng thay vì âm thầm hạ chất lượng phân tích toàn book.";
    const unknown = friendlyError(raw, true);
    expect(unknown.summary).toContain("Ollama chưa chạy hoặc chưa có model");
    expect(unknown.hint).toContain("Sửa Studio");
    const lost = friendlyError(raw, true, false, true);
    expect(lost.summary).toBe("Studio mất model phân tích truyện (file đã bị xoá hay hỏng).");
    expect(lost.hint).toContain("Sửa Studio");
    expect(lost.detail).toBe(raw);
    expect(friendlyError(raw, true, true, true).hint).toContain("Làm lại phân tích từ đầu");
    // Không có model mất thì lỗi kết nối thật vẫn là lỗi kết nối.
    expect(friendlyError("httpx.ConnectError: actively refused it", true, false, false).summary).toContain("kết nối được Ollama");
  });

  it("lỗi lạ: câu chung, nguyên văn chỉ nằm ở chi tiết", () => {
    const shown = friendlyError("  KeyError: 'speaker'  ");
    expect(shown.summary).toBe("Có lỗi khi làm sách.");
    expect(shown.summary).not.toContain("KeyError");
    expect(shown.detail).toBe("KeyError: 'speaker'");
  });
});
