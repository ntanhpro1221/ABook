import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactElement } from "react";
import { renderToString } from "react-dom/server";
import { MemoryRouter } from "react-router";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { ClipProvider } from "@/listen/clip";
import { TooltipProvider } from "@/shared/ui";
import type { BookSummary } from "./api";
import { adoptSummary } from "./data";

// Soát a88: V1 trạng thái "đang dừng", V5 phản hồi máy chủ vào bộ nhớ đệm ngay, T4 sự cố nói nguyên nhân, T5 vì sao cuốn xếp hàng chờ.

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

vi.mock("@/listen/player", () => ({ usePlayer: () => ({ track: null, close: () => undefined }) }));

function book(extra: Partial<BookSummary> = {}): BookSummary {
  return {
    id: "b1", path: "D:/x/sach", title: "Sách thử", status: "analyzing", stage: "analysis", phase: "analysis", statusLabel: "Đang phân tích truyện",
    running: true, interrupted: false, starting: false, startError: "", createdAt: 1, updatedAt: 1, lastError: "", paused: null, canPause: true,
    settings: { profile: "high_quality", profileLabel: "Chất lượng cao", narrator: "" },
    chapters: { total: 10, completed: 0, failed: 0, working: 0 },
    segments: { total: 100, analyzed: 40, pending: 60, recorded: 0, finished: 0, failed: 0 },
    progress: { overall: 0.2, analysis: 0.4, synthesis: 0 }, audioSeconds: 0, eta: null, position: null,
    ...extra,
  } as BookSummary;
}

function html(element: ReactElement): string {
  return renderToString(
    <QueryClientProvider client={new QueryClient()}>
      <TooltipProvider>
        <ClipProvider>
          <MemoryRouter>{element}</MemoryRouter>
        </ClipProvider>
      </TooltipProvider>
    </QueryClientProvider>,
  );
}

describe("nút điều khiển khi đang dừng", () => {
  it("đang chạy bình thường: Tạm dừng là nút chính bấm được, Dừng nằm trong \"…\"", async () => {
    const { Actions } = await import("./ProjectScreen");
    const out = html(<Actions book={book()} />);
    const buttons = [...out.matchAll(/<button[^>]*>[\s\S]*?<\/button>/g)].map(([button]) => button);
    const pause = buttons.find((button) => button.replace(/<[^>]+>/g, "") === "Tạm dừng");
    expect(pause).toContain("bg-accent");
    expect(pause).not.toMatch(/disabled=""|aria-disabled="true"/);
    expect(out).not.toContain("Đang dừng…");
    expect(out).toContain("Tuỳ chọn dự án Sách thử");
  });

  it("đã bấm Dừng: nút chính 'Đang dừng…' bị khoá, không còn Tạm dừng / Dừng nào bấm được (V1)", async () => {
    const { Actions } = await import("./ProjectScreen");
    const out = html(<Actions book={book({ stopping: true, canPause: false, statusLabel: "Đang dừng…" })} />);
    const buttons = [...out.matchAll(/<button[^>]*>(?:(?!<\/button>).)*<\/button>/g)].map((match) => match[0]);
    const stopping = buttons.find((button) => button.includes("Đang dừng…"));
    expect(stopping).toContain('aria-disabled="true"');
    expect(buttons.some((button) => ["Dừng", "Tạm dừng"].includes(button.replace(/<[^>]+>/g, "")))).toBe(false);
  });
});

describe("cuốn xếp hàng sau cuốn đang tạm dừng", () => {
  it("nói tên cuốn kia và việc cần làm (T5)", async () => {
    const { Actions } = await import("./ProjectScreen");
    const out = html(
      <Actions book={book({ running: false, queuePosition: 1, queueWaitsOn: { id: "a", title: "Sách A", paused: "listener" } })} />,
    );
    expect(out).toContain("Chờ lượt");
    expect(out).toContain("Sách A");
    expect(out).toContain("chưa tới lượt");
  });
});

describe("sự cố nói nguyên nhân", () => {
  it("máy sập hiện nguyên nhân do supervisor ghi, kèm lối làm lại (T4)", async () => {
    const { RunEnd } = await import("./ProjectScreen");
    const crashed = html(<RunEnd end={{ state: "failed", detail: "worker thoát với exit code 3221225477", exitCode: 1 }} redo />);
    expect(crashed).toContain("3221225477");
    expect(crashed).toContain("Làm lại phân tích từ đầu");
    expect(crashed).not.toMatch(/bấm Tiếp tục/i);
    const lost = html(<RunEnd end={{ state: "lost", detail: "supervisor không còn chạy", exitCode: null }} redo={false} />);
    expect(lost).toContain("bị ngắt đột ngột");
    expect(lost).toContain("Bấm Tiếp tục");
  });
});

describe("phản hồi của máy chủ vào bộ nhớ đệm", () => {
  it("trang sách và thư viện đổi ngay theo phản hồi, chương giữ nguyên (V5)", () => {
    const client = new QueryClient();
    const before = book();
    client.setQueryData(["book", "b1"], { book: before, chapters: [{ id: 7 }] });
    client.setQueryData(["library"], { root: "D:/x", books: [before, book({ id: "b2" })] });
    const after = book({ paused: "listener", statusLabel: "Đang tạm dừng…" });
    adoptSummary(client, after);
    expect(client.getQueryData<{ book: BookSummary; chapters: unknown[] }>(["book", "b1"])).toEqual({ book: after, chapters: [{ id: 7 }] });
    const library = client.getQueryData<{ books: BookSummary[] }>(["library"]);
    expect(library?.books.map((entry) => entry.paused ?? null)).toEqual(["listener", null]);
    client.setQueryData(["book", "zzz"], undefined);
    adoptSummary(client, book({ id: "zzz" }));
    expect(client.getQueryData(["book", "zzz"])).toBeUndefined();
  });
});
