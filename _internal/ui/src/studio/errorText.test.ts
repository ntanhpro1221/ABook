import { describe, expect, it } from "vitest";
import { friendlyError } from "./errorText";

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

  it("lỗi lạ: câu chung, nguyên văn chỉ nằm ở chi tiết", () => {
    const shown = friendlyError("  KeyError: 'speaker'  ");
    expect(shown.summary).toBe("Có lỗi khi làm sách.");
    expect(shown.summary).not.toContain("KeyError");
    expect(shown.detail).toBe("KeyError: 'speaker'");
  });
});
