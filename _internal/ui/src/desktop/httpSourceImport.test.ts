import { afterEach, expect, it, vi } from "vitest";
import { desktopTextImport } from "./httpSource";

afterEach(() => vi.unstubAllGlobals());

it("a84_04 sends the fingerprint of the exact preview with chapter choices", async () => {
  const fetchMock = vi.fn(async (_url: RequestInfo | URL, _init?: RequestInit) => new Response(JSON.stringify({ id: "b", how: "new", chapters: 1 }), { status: 200, headers: { "Content-Type": "application/json" } }));
  vi.stubGlobal("fetch", fetchMock);
  await desktopTextImport(false).add({ ref: "D:/book.txt", name: "book.txt" }, "Sách", false, { sourceFingerprint: "preview-sha", chapters: [{ index: 2 }] });
  expect(JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))).toMatchObject({ sourceFingerprint: "preview-sha", chapters: [{ index: 2 }] });
});
