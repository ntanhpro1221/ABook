// @vitest-environment happy-dom
// "Nhạc trong sách" liệt kê MỌI bài cuốn dùng (bookmusic2): gói chỉ có nhạc `local:` của người làm sách từng ghi "Chưa có nhạc" khi sách vẫn phát
// nhạc. Bài kho nhạc không có là dòng "Đi kèm sách" (tên theo book.json, số đoạn, không nghe thử / tải, không vào "Lưu tất cả"); chạm mở sheet ở
// mức có dữ liệu (tên, người sáng tác, ba cảm xúc của đoạn đầu tiên dùng bài khi mốc có). Thứ tự = thứ tự nghe.
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TooltipProvider } from "@/shared/ui";
import { eventually } from "@/testing/eventually";
import { S } from "@/shared/strings.generated";
vi.mock("../listen/player", async (original) => ({
  ...(await original<typeof import("../listen/player")>()),
  usePlayer: () => ({ playing: false, pause: vi.fn() }),
}));
import { BookMusic, type BookMusicTrack } from "./BookMusic";

const FLOAT = "local:" + "a".repeat(40);
const PHANTOM = "local:" + "b".repeat(40);
const CATALOG = "https://example.invalid/melody.mp3";
const packaged: BookMusicTrack[] = [
  { link: FLOAT, title: "float flower (MONSTER)", creator: "Kuniaki Haishima", scenes: 4, scene: "1:0", bundled: true, saved: false, downloaded: false,
    mood: [{ id: "sadness", score: 0.8 }, { id: "nostalgia", score: 0.6 }, { id: "tenderness", score: 0.3 }] },
  { link: PHANTOM, title: "幻影の挽歌 (HUNTER×HUNTER (2011))", creator: "Yoshihisa Hirano (平野義久)", scenes: 2, scene: "1:136729", bundled: true, saved: false, downloaded: false, mood: [] },
];
const catalog: BookMusicTrack = { link: CATALOG, title: "Audit melody", creator: "Kevin MacLeod", scenes: 3, scene: "1:60000", bytes: 1024, saved: false, downloaded: false };

let root: Root, host: HTMLDivElement, client: QueryClient;
let book: { tracks: BookMusicTrack[]; missingBytes: number; unsaved: string[] };

beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  vi.spyOn(HTMLElement.prototype, "animate").mockImplementation(() => ({ cancel: vi.fn(), onfinish: null, finished: Promise.resolve() }) as unknown as Animation);
  client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
    const path = String(input);
    const data = path.includes("/api/books/a/music/library") ? book
      : { styles: [], emotions: [{ id: "sadness", label: "buồn" }, { id: "nostalgia", label: "hoài niệm" }], playlists: [], active: {}, failed: {} };
    return new Response(JSON.stringify(data), { status: 200, headers: { "Content-Type": "application/json" } });
  }));
});
afterEach(async () => {
  await act(() => root.unmount()); client.clear(); document.body.replaceChildren(); vi.restoreAllMocks(); vi.unstubAllGlobals();
});

const render = () => act(() => root.render(<QueryClientProvider client={client}><TooltipProvider><BookMusic bookId="a" /></TooltipProvider></QueryClientProvider>));
const rows = () => [...host.querySelectorAll<HTMLElement>('[role="listitem"]')];
const saveAll = () => [...host.querySelectorAll<HTMLButtonElement>("button")].find((button) => button.textContent?.includes("Lưu tất cả"));

it("a book of packaged tracks lists every one, named from book.json, with nothing to save", async () => {
  book = { tracks: packaged, missingBytes: 0, unsaved: [] };
  await render();
  await eventually(() => expect(rows()).toHaveLength(2));
  expect(host.textContent).not.toContain(S.s_chua_co_nhac_ed5dc66e);
  expect(rows()[0].textContent).toContain("float flower (MONSTER)");
  expect(rows()[0].textContent).toContain(`Kuniaki Haishima${S.s_bundled_track}`); // DotJoin vẽ dấu · bằng CSS
  expect(rows()[0].textContent).toContain(S.s_0_doan_c2eb5200(4));
  expect(rows()[1].textContent).toContain("幻影の挽歌");
  expect(host.querySelectorAll("[data-bundled-track]")).toHaveLength(2);
  expect(host.querySelector(".music-row-preview button, button.music-row-preview")).toBeNull();
  expect(saveAll(), "không có gì để lưu: không có nút Lưu tất cả").toBeUndefined();
});

it("tapping a packaged track opens its sheet with the scene's mood", async () => {
  book = { tracks: packaged, missingBytes: 0, unsaved: [] };
  await render();
  await eventually(() => expect(rows()).toHaveLength(2));
  await act(() => rows()[0].querySelector<HTMLButtonElement>("button")!.click());
  await eventually(() => expect(document.querySelector("[data-bundled-sheet]")).not.toBeNull());
  const sheet = document.querySelector<HTMLElement>('[role="dialog"]')!;
  expect(sheet.textContent).toContain("float flower (MONSTER)");
  expect(sheet.textContent).toContain(S.s_bundled_track_note);
  await eventually(() => expect(sheet.textContent).toContain(S.s_bundled_scene_mood("buồn")));
  expect(sheet.querySelectorAll("li")).toHaveLength(3);
  expect(sheet.textContent).not.toContain(S.s_luu_e91f26c0);
});

it("a mixed book keeps catalog rows whole, in listening order, and saves only them", async () => {
  book = { tracks: [packaged[0], catalog, packaged[1]], missingBytes: 1024, unsaved: [CATALOG] };
  await render();
  await eventually(() => expect(rows()).toHaveLength(3));
  expect(rows().map((row) => row.querySelector("[data-bundled-track]") !== null)).toEqual([true, false, true]);
  expect(rows()[1].textContent).toContain("Audit melody");
  expect(rows()[1].querySelector(`button[aria-label="${S.s_nghe_thu_fa024065}"]`)).not.toBeNull();
  await act(() => saveAll()!.click());
  const saved = vi.mocked(fetch).mock.calls.find(([url]) => String(url).includes("/api/music/library/save"));
  expect(JSON.parse(String(saved?.[1]?.body)).links).toEqual([CATALOG]);
});

it("a book without music still says so", async () => {
  book = { tracks: [], missingBytes: 0, unsaved: [] };
  await render();
  await eventually(() => expect(host.textContent).toContain(S.s_chua_co_nhac_ed5dc66e));
  expect(rows()).toHaveLength(0);
});
