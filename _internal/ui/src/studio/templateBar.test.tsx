import { renderToString } from "react-dom/server";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import type { BookTemplate } from "./bookTemplates";

// "Mẫu thiết lập" ở trình tạo sách và ở Cài đặt khi vào Studio TỪ XA: trước đây thanh mẫu ẩn nút lưu (và ẩn cả thanh khi chưa có mẫu), mục Cài đặt
// không hiện - vì ghi cả danh sách qua PUT /api/preferences không đi qua được. Giờ mỗi việc là một thao tác (POST /api/book-templates).

const ln: BookTemplate = { name: "Light novel", narrator: "Đức Trí", profile: "balanced", analysisModel: "", startNow: false, precastWait: false };
const state = vi.hoisted(() => ({ templates: [] as unknown[], remote: false }));
const run = vi.hoisted(() => vi.fn());

vi.mock("@/studio/data", () => ({
  usePreferences: () => ({ data: { bookTemplates: state.templates }, update: vi.fn(), updating: false }),
  useAppInfo: () => ({ data: { remote: state.remote } }),
  useVoices: () => ({ data: [{ name: "Đức Trí" }] }),
  useBookTemplateOp: () => ({ run, running: false }),
}));
vi.mock("@/studio/AnalysisModelPicker", () => ({ useAvailableModelNames: () => undefined }));

beforeAll(() => {
  const globals = globalThis as unknown as Record<string, unknown>;
  globals.window ??= Object.assign(new EventTarget(), {
    location: { search: "", hash: "", pathname: "/", origin: "http://127.0.0.1" },
    matchMedia: () => ({ matches: false, addEventListener: () => undefined, removeEventListener: () => undefined }),
  });
});

beforeEach(() => {
  state.templates = [];
  state.remote = false;
  run.mockReset();
});

const draft = { narrator: "Đức Trí", profile: "balanced" as const, startNow: true };

describe("thanh mẫu thiết lập ở trình tạo sách", () => {
  it("qua Studio từ xa vẫn có nút lưu, kể cả khi chưa có mẫu nào", async () => {
    state.remote = true;
    const { TemplateBar } = await import("./TemplateBar");
    const html = renderToString(<TemplateBar draft={draft} onPick={() => undefined} />);
    expect(html).toContain("Lưu thành mẫu…");
    expect(html).toContain("Lưu các lựa chọn dưới đây thành mẫu");
  });

  it("trên máy tính cũng vậy, và liệt kê các mẫu đã lưu để chọn", async () => {
    state.templates = [ln];
    const { TemplateBar } = await import("./TemplateBar");
    const html = renderToString(<TemplateBar draft={draft} onPick={() => undefined} />);
    expect(html).toContain("Lưu thành mẫu…");
    expect(html).toContain("Light novel");
    expect(html).toContain("Mặc định");
  });
});

describe("mục Mẫu thiết lập trong Cài đặt", () => {
  it("liệt kê mẫu với Đổi tên và Xoá", async () => {
    state.templates = [ln];
    const { BookTemplates } = await import("../desktop/BookTemplates");
    const html = renderToString(<BookTemplates />);
    expect(html).toContain("Light novel");
    expect(html).toContain("Đổi tên");
    expect(html).toContain("Xoá");
    expect(html).toContain("Cân bằng");
    expect(html).toContain("chờ bấm bắt đầu");
  });

  it("chưa có mẫu thì nói chưa có", async () => {
    const { BookTemplates } = await import("../desktop/BookTemplates");
    expect(renderToString(<BookTemplates />)).toContain("Chưa có mẫu nào.");
  });
});
