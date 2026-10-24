import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup, renderToString } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

// Cài đặt → Chẩn đoán trên điện thoại (android/Diagnostics.tsx, SettingsScreen): xem / gửi / xoá nhật ký qua plugin EbookLibrary. Plugin native là bản giả.
const h = vi.hoisted(() => ({
  diagnostics: vi.fn(),
  shareDiagnostics: vi.fn(),
  clearDiagnostics: vi.fn(),
  success: vi.fn(),
  error: vi.fn(),
  hook: null as unknown,
}));
vi.mock("./plugins", () => ({
  EbookPlayer: { configure: vi.fn(), listenPrefs: vi.fn() },
  EbookLibrary: { systemBars: vi.fn(), diagnostics: h.diagnostics, shareDiagnostics: h.shareDiagnostics, clearDiagnostics: h.clearDiagnostics },
  ReadAloud: {},
}));
vi.mock("sonner", () => ({ toast: { error: h.error, success: h.success } }));

import { CLEAR_HINT, DIAGNOSTICS_HINT, DIAGNOSTICS_MORE, DiagnosticsPanel, SEND_HINT, VIEW_LINES, useDiagnostics } from "./Diagnostics";
import { SettingsScreen } from "./SettingsScreen";
import { SettingsAt } from "@/shared/settingsAt";

function probe() {
  function Probe() {
    h.hook = useDiagnostics();
    return null;
  }
  renderToString(<Probe />);
  return h.hook as ReturnType<typeof useDiagnostics>;
}

beforeEach(() => {
  for (const mock of [h.diagnostics, h.shareDiagnostics, h.clearDiagnostics, h.success, h.error]) mock.mockReset();
  h.diagnostics.mockResolvedValue({ schema: 1, log: ["một", "hai"] });
  h.shareDiagnostics.mockResolvedValue({ shared: true });
  h.clearDiagnostics.mockResolvedValue({ cleared: true });
  Object.assign(globalThis, {
    localStorage: { getItem: () => null, setItem: () => undefined },
    window: Object.assign(new EventTarget(), {
      location: { search: "", hash: "", pathname: "/", origin: "http://127.0.0.1" },
      matchMedia: () => ({ matches: false, addEventListener: () => undefined, removeEventListener: () => undefined }),
    }),
  });
});

describe("mục Chẩn đoán của Cài đặt", () => {
  it("có ba việc: xem, gửi, xoá nhật ký; lời giải thích nói app che dữ liệu nhận diện được và bạn tự chọn nơi gửi", () => {
    const html = renderToString(
      <QueryClientProvider client={new QueryClient()}>
        <SettingsAt group="advanced" screen={<SettingsScreen />} />
      </QueryClientProvider>,
    );
    for (const text of ["Chẩn đoán", "Nhật ký", "Gửi nhật ký", "Xoá nhật ký"]) expect(html).toContain(text);
    expect(h.diagnostics).not.toHaveBeenCalled();
    // Dòng ngắn nói việc cần làm; chi tiết quyền riêng tư gập sau "Tìm hiểu thêm" nhưng vẫn đủ (chủ app 23-10: chữ dài khắp nơi).
    expect(DIAGNOSTICS_HINT).toContain("Xem lại trước khi gửi");
    expect(DIAGNOSTICS_HINT.length).toBeLessThanOrEqual(60);
    expect(DIAGNOSTICS_MORE).toContain("nhận ra được");
    expect(DIAGNOSTICS_MORE).not.toContain("không có mật khẩu");
    expect(DIAGNOSTICS_MORE).toContain("Chia sẻ thư viện");
    expect(SEND_HINT).toContain("Bạn chọn gửi cho ai");
    expect(CLEAR_HINT).toContain("văng");
  });

  it("xem: hỏi plugin với số dòng của màn xem", async () => {
    await probe().load();
    expect(h.diagnostics).toHaveBeenCalledWith({ lines: VIEW_LINES });
    h.diagnostics.mockRejectedValueOnce(new Error("không đọc được nhật ký"));
    await expect(probe().load()).resolves.toBeUndefined();
  });

  it("gửi: mở bảng chia sẻ; lỗi thì báo bằng tiếng Việt", async () => {
    await probe().send();
    expect(h.shareDiagnostics).toHaveBeenCalledTimes(1);
    expect(h.error).not.toHaveBeenCalled();
    h.shareDiagnostics.mockRejectedValueOnce(new Error("không mở được bảng chia sẻ"));
    await probe().send();
    expect(h.error).toHaveBeenCalledWith("Chưa gửi được nhật ký", { description: "không mở được bảng chia sẻ" });
  });

  it("xoá: gọi plugin rồi báo đã xoá; hỏng thì báo lý do", async () => {
    await probe().clear();
    expect(h.clearDiagnostics).toHaveBeenCalledTimes(1);
    expect(h.success).toHaveBeenCalledWith("Đã xoá nhật ký");
    h.clearDiagnostics.mockRejectedValueOnce(new Error("không xoá được"));
    await probe().clear();
    expect(h.error).toHaveBeenCalledWith("Chưa xoá được nhật ký", { description: "không xoá được" });
  });

  it("bảng xem hiện tóm tắt + nhật ký, hay lỗi", () => {
    const html = renderToStaticMarkup(<DiagnosticsPanel report={{ schema: 1, battery: { percent: 20 }, log: ["dòng cuối"] }} error="" loading={false} />);
    expect(html).toContain("20%");
    expect(html).toContain("dòng cuối");
    expect(renderToStaticMarkup(<DiagnosticsPanel report={null} error="Không đọc được nhật ký" loading={false} />)).toContain("Không đọc được nhật ký");
  });
});
