import { expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { mergeRows, settleRows } from "@/shared/motion";
import { StoragePanel } from "./DevicesScreen";
const h = vi.hoisted(() => ({ rows: [] as unknown[] }));
vi.mock("@/shared/motion", async (original) => ({ ...await original<typeof import("@/shared/motion")>(), useListPresence: () => h.rows }));
vi.mock("@/listen/source", () => ({ useListenLibrary: () => ({ data: [] }) }));
vi.mock("./downloads", () => ({ useDownloadProgress: () => ({}) }));
vi.mock("./plugins", () => ({ EbookLibrary: {}, EbookPlayer: {}, ReadAloud: {} }));

it("xoá cuốn cuối: ul giữ hàng exit cho tới lúc presence hoàn tất", () => {
  const entries = [{ id: "A", title: "Cuốn A", bytes: 10, kind: "partial" }];
  const rows = mergeRows(mergeRows([], entries, (entry) => entry.id, true), [], (entry) => entry.id);
  h.rows = rows;
  const render = () => renderToStaticMarkup(<StoragePanel storage={{ bytes: 0, free: 100, books: [] }} />);
  expect(render()).toContain('data-state="exit"');
  expect(render()).toContain("Cuốn A");
  h.rows = settleRows(rows);
  expect(render()).not.toContain("<ul");
});
