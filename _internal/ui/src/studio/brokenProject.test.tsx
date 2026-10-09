import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToString } from "react-dom/server";
import { MemoryRouter } from "react-router";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { RowBoundary } from "@/shared/RowBoundary";
import type { BookSummary } from "./api";

// Dự án hỏng: server chỉ trả {id, path, title, broken} - không có segments/chapters (server.py, books.append). Trước đây menu "…"
// đọc book.segments.analyzed lúc vẽ nên cả Studio trắng trang, hàng "Không đọc được" và nút xoá cũng chết theo.

beforeAll(() => {
  const store = new Map<string, string>();
  const globals = globalThis as unknown as Record<string, unknown>;
  globals.localStorage = {
    getItem: (key: string) => store.get(key) ?? null,
    setItem: (key: string, value: string) => void store.set(key, value),
    removeItem: (key: string) => void store.delete(key),
  } as Storage;
  globals.window ??= Object.assign(new EventTarget(), {
    location: { search: "", hash: "", pathname: "/", origin: "http://127.0.0.1" },
    matchMedia: () => ({ matches: false, addEventListener: () => undefined, removeEventListener: () => undefined }),
    localStorage: globals.localStorage,
  });
});

// Menu "…" mở hộp xoá/đổi tên, hai hộp ấy cần trình phát (đóng cuốn đang nghe trước khi xoá).
vi.mock("@/listen/player", () => ({ usePlayer: () => ({ track: null, close: () => undefined }) }));

const broken = { id: "b1", path: "D:/x/hong", title: "hong", broken: "no such column: status" } as unknown as BookSummary;

describe("dự án hỏng", () => {
  it("menu … vẽ được dù tóm tắt không có segments", async () => {
    const { ProjectMenu } = await import("./ProjectScreen");
    const html = renderToString(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter>
          <ProjectMenu book={broken} rename={false} />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(html).toContain("Tuỳ chọn dự án hong");
  });

  it("hàng lỗi khi vẽ chỉ thay bằng dòng báo, không lan ra ngoài", () => {
    // renderToString không gọi error boundary; thử đúng hai nửa của lớp: bắt lỗi rồi vẽ phần thay thế.
    expect(RowBoundary.getDerivedStateFromError()).toEqual({ failed: true });
    const boundary = new RowBoundary({ fallback: <p>Không đọc được dự án này</p>, children: <p>hàng</p> });
    expect(renderToString(<>{boundary.render()}</>)).toContain("hàng");
    boundary.state = { failed: true };
    expect(renderToString(<>{boundary.render()}</>)).toContain("Không đọc được dự án này");
  });
});
