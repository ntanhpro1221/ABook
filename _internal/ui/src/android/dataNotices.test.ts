// Kiểm lệnh gốc; trình bày và Back của toast kiểm riêng trong layoutC11.dom.test.tsx.
vi.mock("@/shared/ToastDetails", () => ({ prepareToast: (args: unknown[]) => args }));
import { afterEach, expect, it, vi } from "vitest";
const h = vi.hoisted(() => ({ warning: vi.fn() }));
vi.mock("sonner", () => ({ toast: { warning: h.warning } }));
import { showDataNotices } from "./dataNotices";
afterEach(() => vi.unstubAllGlobals());

it("báo bản gốc được giữ và không báo lặp mỗi lần tải thư viện", () => {
  const data = new Map<string, string>();
  vi.stubGlobal("localStorage", { getItem: (key: string) => data.get(key) ?? null, setItem: (key: string, value: string) => data.set(key, value) });
  const text = "Một phần hồ sơ của bạn bị hỏng. Bản gốc được giữ ở records.json.corrupt-1.";
  showDataNotices([text]);
  showDataNotices([text]);
  expect(h.warning).toHaveBeenCalledTimes(1);
  expect(h.warning).toHaveBeenCalledWith(text, expect.anything());
});

it("không đọc được localStorage vẫn báo và giữ bản native", () => {
  vi.stubGlobal("localStorage", { getItem: () => { throw new Error("blocked"); }, setItem: () => { throw new Error("blocked"); } });
  const text = "Bản cũ của bạn đã được giữ an toàn.";
  showDataNotices([text]);
  expect(h.warning).toHaveBeenCalledWith(text, expect.anything());
});
