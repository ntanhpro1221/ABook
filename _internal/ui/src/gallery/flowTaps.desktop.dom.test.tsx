// @vitest-environment happy-dom
// DESIGN.md §2 "Luồng sử dụng" trên máy tính: đếm chạm bằng máy như flowTaps.phone - mỗi cú bấm trong app một chạm, mỗi lần mở hộp chọn
// file / thư mục của hệ thống (POST /api/dialog/...) cũng một chạm.
import { afterEach, expect, it, vi } from "vitest";
import { installPlatform } from "./boot";
import { click, find, waitFor } from "./actions";
import { ENTRIES } from "./entries";

const cancel = Animation.prototype.cancel;
Animation.prototype.cancel = function () { this.finished?.catch(() => undefined); cancel.call(this); };
installPlatform("desktop");
vi.setConfig({ testTimeout: 30_000 });
let unmount: (() => void) | undefined;
let taps = 0;
let speaking = false;
const requested: string[] = [];
const created: Record<string, unknown>[] = [];
afterEach(() => { unmount?.(); unmount = undefined; document.body.replaceChildren(); vi.restoreAllMocks(); });

// Hộp chọn của hệ thống, quét chương và tạo dự án: phòng trưng bày không giả (ảnh tĩnh không cần), luồng thì cần.
const BOOK = "D:/Truyện/Tiệm sách trên gác xép.epub";
const CHAPTERS = ["D:/Truyện/Gác xép/001.txt", "D:/Truyện/Gác xép/002.txt"];
function json(body: unknown) {
  return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
}
async function start(id: string) {
  const { runEntry } = await import("./run");
  const host = document.createElement("div"); document.body.append(host);
  unmount = await runEntry(ENTRIES.find(entry => entry.id === id)!, "light", host, { quiet: 120 });
  const gallery = globalThis.fetch;
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const path = (typeof input === "string" ? input : input instanceof URL ? input.href : input.url).replace(/^https?:\/\/[^/]+/, "");
    const method = (init?.method ?? "GET").toUpperCase();
    requested.push(path);
    if (path.startsWith("/api/readaloud/clip")) speaking = true;
    if (method === "POST" && path === "/api/dialog/files") { taps++; return json({ paths: [BOOK] }); }
    if (method === "POST" && path === "/api/dialog/folder") { taps++; return json({ path: "D:/Truyện/Gác xép" }); }
    if (method === "POST" && path === "/api/scan") return json({
      files: CHAPTERS.map((file, index) => ({ path: file, name: file.split("/").pop(), title: `Chương ${index + 1}`, firstLine: "Chiều thứ Năm.", words: 2400, audioSeconds: 900, chars: 9800, bytes: 14000 })),
      skipped: [], missing: [], subfolders: [], suggestedTitle: "Tiệm Sách Trên Gác Xép", totals: { chapters: 2, words: 4800, audioSeconds: 1800 },
    });
    if (method === "POST" && path === "/api/books") { created.push(JSON.parse(String(init?.body ?? "{}"))); return json({ id: "gac-xep-moi" }); }
    return gallery(input, init);
  });
  taps = 0;
  speaking = false;
}
const tap = (target: string | RegExp, within?: ParentNode) => { taps++; return click(target, within); };
const playing = () => Boolean(find(/^Tạm dừng/));

it("L2 nghe tiếp: 1 chạm từ Thư viện", async () => {
  await start("desktop/library-full");
  await tap(/^Nghe tiếp /);
  await waitFor(playing, "đang phát");
  expect(taps).toBe(1);
});

it("L3 mở trình phát: 1 chạm vào thanh phát", async () => {
  await start("desktop/player-playing");
  await tap("Mở màn hình đang nghe");
  await waitFor(() => find(/^Thu nhỏ/) || document.querySelector('[role="dialog"][data-state="open"]'), "trình phát");
  expect(taps).toBe(1);
});

it("L4 nhảy chương: 2 chạm từ trình phát", async () => {
  await start("desktop/player-full");
  await tap("Chương");
  await tap(/^Tháp chuông phía bắc/);
  await waitFor(() => requested.some(path => path.includes("/chapters/5")), "chương mới");
  expect(taps).toBe(2);
});

it("L5 hẹn giờ ngủ: 2 chạm từ trình phát", async () => {
  await start("desktop/player-full");
  await tap("Hẹn giờ ngủ");
  await tap("30 phút");
  await waitFor(() => find(/^Hẹn giờ ngủ.+30|^Hẹn giờ.*còn/) || document.body.textContent?.match(/(29|30):\d\d/), "đã hẹn giờ");
  expect(taps).toBe(2);
});

it("L7 đọc theo chữ: 1 chạm từ trình phát", async () => {
  await start("desktop/player-full");
  await tap("Đọc theo");
  await waitFor(() => /\/read\//.test(window.location.hash) || document.querySelector("[data-index]"), "chữ đọc theo");
  expect(taps).toBe(1);
});

it("L5 tốc độ: ≤ 2 chạm từ thanh phát", async () => {
  await start("desktop/player-playing");
  await tap(/^Tốc độ đọc/);
  await tap("1,5×");
  await waitFor(() => find(/^Tốc độ đọc: 1,5×/), "tốc độ mới");
  expect(taps).toBeLessThanOrEqual(2);
});

it("L8 chọn cuốn khác: nghe thẳng từ bìa 1 chạm", async () => {
  await start("desktop/library-full");
  await tap("Nghe Mùa Hoa Gạo Bên Sông");
  await waitFor(() => find(/^Tạm dừng Mùa Hoa Gạo/) || (playing() && document.body.textContent?.includes("Mùa Hoa Gạo Bên Sông")), "phát cuốn mới");
  expect(taps).toBe(1);
});

it("L10 tạo sách nói: Studio -> Dự án mới -> chọn file -> Bắt đầu ≤ 3 chạm", async () => {
  await start("desktop/studio-projects");
  created.length = 0;
  await tap("Dự án mới");
  await waitFor(() => window.location.hash === "#/studio/new", "trình tạo sách");
  await tap(/^(Bắt đầu|Tạo sách)$/);
  await waitFor(() => created.length > 0, "tạo dự án");
  expect(taps).toBeLessThanOrEqual(3);
});

it("L11 theo dõi Studio: tiến độ ở thanh bên, không cần chạm", async () => {
  await start("desktop/library-full");
  const sidebar = document.querySelector("aside, nav") as HTMLElement;
  expect(sidebar.textContent).toMatch(/\d+%/);
});

// Cuối tệp: sách vừa thêm chưa có audio - "Nghe" gọi đọc máy, phòng trưng bày không bao giờ trả clip nên phiên nghe còn treo sau bài này.
it("L1 lần đầu mở: Thư viện trống tới lúc nghe ≤ 4 chạm", async () => {
  await start("desktop/library-empty");
  await tap("Thêm sách");
  await tap("Thêm vào thư viện");
  await waitFor(() => window.location.hash.startsWith("#/book/"), "trang sách vừa thêm");
  await tap(/^Nghe( tiếp| ngay)?( · .+)?$/);
  // Lần đầu đọc bằng giọng trực tuyến: hỏi trước khi gửi chữ tới máy chủ (onlineConsent.ts, 08d630e0) - quyết định quyền riêng tư thật, chỉ một
  // lần mỗi nhà cung cấp; tính riêng, không nới đích của luồng.
  const consent = await waitFor(() => speaking || playing() || document.querySelector<HTMLElement>('[role="dialog"][data-state="open"]'), "nghe hay hộp hỏi");
  if (consent instanceof HTMLElement && consent.textContent?.includes("Giọng đọc trực tuyến")) await click("Nghe", consent);
  await waitFor(() => speaking || playing(), "bắt đầu nghe (đọc máy hay phát)");
  expect(taps).toBeLessThanOrEqual(4);
});
