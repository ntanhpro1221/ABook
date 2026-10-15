import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToString } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";
import { exportedOnComputer, jobView } from "@/desktop/bookFileExport";
import { api, ApiError, type AppInfo } from "@/studio/api";
import { isListenOnly, pollDelay, retryUnlessGone } from "@/studio/polling";
import { OnComputerOnly } from "./OnComputerOnly";
import { LISTEN_ONLY_EVENT, onComputerLine } from "./peerStudio";

// Studio từ xa (soát a33): việc chỉ làm được trên máy tính được nói thẳng "Làm ở máy tính <tên>" thay vì ẩn im lặng hay bấm ra 403.

const show = (info: Partial<AppInfo>) => {
  const client = new QueryClient();
  client.setQueryData(["app"], info);
  return renderToString(
    <QueryClientProvider client={client}>
      <OnComputerOnly verb="Xoá dự án" />
    </QueryClientProvider>,
  );
};

describe("việc chỉ làm ở máy tính", () => {
  it("nói tên máy tính, hoặc chỉ 'máy tính' khi chưa biết tên", () => {
    expect(onComputerLine("Đổi", "NGD-PC")).toBe("Đổi ở máy tính NGD-PC");
    expect(onComputerLine("Tải giọng", "máy tính")).toBe("Tải giọng ở máy tính");
    expect(onComputerLine("Làm", "")).toBe("Làm ở máy tính");
  });

  it("chip dùng tên máy phục vụ trang, hay tên máy đang mở qua cầu nối", () => {
    expect(show({ remote: true, machine: "NGD-PC" })).toContain("Xoá dự án ở máy tính NGD-PC");
    expect(show({ remote: true, machine: "NGD-PC", peer: { name: "Máy văn phòng" } as AppInfo["peer"] })).toContain("Xoá dự án ở máy tính Máy văn phòng");
    expect(renderToString(<QueryClientProvider client={new QueryClient()}><OnComputerOnly verb="Đổi" /></QueryClientProvider>)).toContain("Đổi ở máy tính<");
  });
});

describe("xuất từ xa", () => {
  it("nói file nằm ở máy tính nào, chỉ có tên file", () => {
    expect(exportedOnComputer("NGD-PC", "Truyện.abook", "5 MB")).toBe("Đã xuất vào máy tính NGD-PC: Truyện.abook · 5 MB");
    expect(exportedOnComputer("NGD-PC", "")).toBe("Đã xuất vào máy tính NGD-PC");
    expect(exportedOnComputer("máy tính", "x.m4b")).toBe("Đã xuất vào máy tính: x.m4b");
  });

  it("kết quả không có thư mục (máy chủ giấu đường dẫn) không làm thông báo vỡ", () => {
    const view = jobView({ state: "done", result: { file: "Truyện.m4b", size: 1000 } as never });
    expect(view).toMatchObject({ kind: "success", description: expect.stringContaining("Truyện.m4b") });
    expect(jobView({ state: "done", result: { parts: [{}, {}] } as never })).toMatchObject({ kind: "success", description: "2 file" });
  });
});

describe("thiết bị bị đổi sang chỉ nghe giữa phiên", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("403 mang listenOnly thì không thử lại, không hỏi định kỳ", () => {
    const refused = new ApiError(403, "giờ chỉ nghe sách được", { listenOnly: true });
    expect(isListenOnly(refused)).toBe(true);
    expect(isListenOnly(new ApiError(403, "khác", {}))).toBe(false);
    expect(retryUnlessGone(0, refused)).toBe(false);
    expect(pollDelay(15_000, { error: refused, errorUpdateCount: 1 })).toBe(false);
  });

  it("api() báo cho app hỏi lại /api/app khi gặp 403 listenOnly", async () => {
    const seen: Event[] = [];
    const target = new EventTarget();
    target.addEventListener(LISTEN_ONLY_EVENT, (event) => seen.push(event));
    vi.stubGlobal("window", Object.assign(target, { location: { search: "", hash: "", pathname: "/", origin: "http://x" } }));
    vi.stubGlobal("fetch", async () => ({ ok: false, status: 403, text: async () => JSON.stringify({ error: "chỉ nghe", listenOnly: true }) }));
    await expect(api("/api/library")).rejects.toBeInstanceOf(ApiError);
    expect(seen).toHaveLength(1);
    vi.stubGlobal("fetch", async () => ({ ok: false, status: 403, text: async () => JSON.stringify({ error: "chỉ làm trên máy tính" }) }));
    await expect(api("/api/library")).rejects.toBeInstanceOf(ApiError);
    expect(seen).toHaveLength(1);
  });
});
