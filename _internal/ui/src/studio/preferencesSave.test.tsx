// Kiểm lệnh gốc; trình bày và Back của toast kiểm riêng trong layoutC11.dom.test.tsx.
vi.mock("@/shared/ToastDetails", () => ({ prepareToast: (args: unknown[]) => args }));
import { renderToString } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const h = vi.hoisted(() => ({ options: null as null | { onError?: (error: Error) => void; onSuccess?: (data: unknown) => void }, error: vi.fn(), setQueryData: vi.fn() }));
vi.mock("@tanstack/react-query", () => ({
  useQueryClient: () => ({ setQueryData: h.setQueryData, invalidateQueries: vi.fn() }),
  useQuery: () => ({ data: { theme: "light" } }),
  useMutation: (options: typeof h.options) => {
    h.options = options;
    return { mutate: vi.fn(), isPending: false };
  },
}));
vi.mock("sonner", () => ({ toast: { error: h.error, success: vi.fn(), warning: vi.fn() } }));
import { usePreferences } from "./data";

// Lưu tuỳ chọn thất bại không được im lặng (soát a100 V3).
beforeEach(() => h.error.mockReset());

describe("usePreferences", () => {
  it("lỗi lưu được báo bằng tiếng Việt kèm lời của máy chủ", () => {
    function Probe() {
      usePreferences();
      return null;
    }
    renderToString(<Probe />);
    expect(h.options?.onError).toBeTypeOf("function");
    h.options!.onError!(new Error("Thư mục này nằm trong vùng cài đặt, chọn thư mục khác."));
    expect(h.error).toHaveBeenCalledWith("Chưa lưu được cài đặt", expect.objectContaining({ description: "Thư mục này nằm trong vùng cài đặt, chọn thư mục khác." }));
  });

  it("lưu xong thì cập nhật bộ nhớ đệm bằng bản máy chủ trả về", () => {
    function Probe() {
      usePreferences();
      return null;
    }
    renderToString(<Probe />);
    h.options!.onSuccess!({ theme: "dark" });
    expect(h.setQueryData).toHaveBeenCalledWith(["preferences"], { theme: "dark" });
  });
});
