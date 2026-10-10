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

  it("lỗi lạ: câu chung, nguyên văn chỉ nằm ở chi tiết", () => {
    const shown = friendlyError("  KeyError: 'speaker'  ");
    expect(shown.summary).toBe("Có lỗi khi làm sách.");
    expect(shown.summary).not.toContain("KeyError");
    expect(shown.detail).toBe("KeyError: 'speaker'");
  });
});
