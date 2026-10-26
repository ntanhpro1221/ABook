// @vitest-environment happy-dom
// DESIGN.md §2 "Luồng sử dụng": mỗi luồng có số chạm đích - đổi giao diện mà làm luồng dài thêm là lùi. Đếm bằng máy trên phòng trưng
// bày điện thoại: mỗi cú bấm trong app là một chạm, mỗi lần mở hộp chọn file của hệ thống cũng là một chạm (người dùng phải chọn ở đó).
import { readFileSync } from "node:fs";
import { afterEach, expect, it, vi } from "vitest";
import { installPlatform } from "./boot";
import { click, find, waitFor } from "./actions";
import { ENTRIES } from "./entries";
import { ebookLibrary, ebookPlayer } from "./phoneNative";

const cancel = Animation.prototype.cancel;
Animation.prototype.cancel = function () { this.finished?.catch(() => undefined); cancel.call(this); };
installPlatform("phone");
vi.setConfig({ testTimeout: 30_000 });
let unmount: (() => void) | undefined;
let taps = 0;
afterEach(() => { unmount?.(); unmount = undefined; document.body.replaceChildren(); vi.restoreAllMocks(); });

async function start(id: string) {
  const { runEntry } = await import("./run");
  const host = document.createElement("div"); document.body.append(host);
  unmount = await runEntry(ENTRIES.find(entry => entry.id === id)!, "light", host, { quiet: 120 });
  const pick = ebookLibrary.pickSource;
  vi.spyOn(ebookLibrary, "pickSource").mockImplementation((options) => { taps++; return pick(options); });
  taps = 0;
}
const tap = (target: string | RegExp, within?: ParentNode) => { taps++; return click(target, within); };
const nav = () => document.querySelector('nav[aria-label="Điều hướng"]')!;

it("L1 lần đầu mở: Thư viện trống tới lúc nghe ≤ 4 chạm", async () => {
  await start("phone/library-empty");
  const load = vi.spyOn(ebookPlayer, "load");
  await tap("Thêm sách");
  await tap("Thêm vào thư viện");
  await waitFor(() => window.location.hash.startsWith("#/book/"), "trang sách vừa thêm");
  await tap(/^Nghe( ngay)?$/);
  await waitFor(() => load.mock.calls.length > 0, "bắt đầu nghe");
  expect(taps).toBeLessThanOrEqual(4);
});

it("L2 nghe tiếp: 1 chạm từ Thư viện", async () => {
  await start("phone/library-full");
  const load = vi.spyOn(ebookPlayer, "load"), play = vi.spyOn(ebookPlayer, "play"), toggle = vi.spyOn(ebookPlayer, "toggle");
  await tap(/^Nghe tiếp /);
  await waitFor(() => load.mock.calls.length + play.mock.calls.length + toggle.mock.calls.length > 0, "phát");
  expect(taps).toBe(1);
});

it("L3 mở trình phát: 1 chạm vào thanh phát thu nhỏ", async () => {
  await start("phone/player-mini");
  await tap("Mở màn hình đang nghe");
  await waitFor(() => find("Thu nhỏ"), "trình phát");
  expect(taps).toBe(1);
});

it("L4 nhảy chương: 2 chạm từ trình phát", async () => {
  await start("phone/player-full");
  const jump = vi.spyOn(ebookPlayer, "jumpTo"), load = vi.spyOn(ebookPlayer, "load");
  await tap("Chương");
  await tap(/^Tháp chuông phía bắc/);
  await waitFor(() => jump.mock.calls.length + load.mock.calls.length > 0, "nhảy chương");
  expect(taps).toBe(2);
});

it("L5 hẹn giờ ngủ và tốc độ: mỗi việc 2 chạm từ trình phát", async () => {
  await start("phone/player-full");
  const sleep = vi.spyOn(ebookPlayer, "setSleep"), rate = vi.spyOn(ebookPlayer, "setRate");
  await tap("Hẹn giờ ngủ");
  await tap("30 phút");
  await waitFor(() => sleep.mock.calls.length > 0, "hẹn giờ");
  expect(taps).toBe(2);
  await start("phone/player-full");
  await tap(/^Tốc độ đọc/);
  await tap("1,5×");
  await waitFor(() => rate.mock.calls.length > 0, "đổi tốc độ");
  expect(taps).toBe(2);
});

it("L7 đọc theo chữ: 1 chạm từ trình phát", async () => {
  await start("phone/player-full");
  await tap("Đọc theo");
  await waitFor(() => /\/read\//.test(window.location.hash) || document.querySelector("[data-index]"), "chữ đọc theo");
  expect(taps).toBe(1);
});

it("L8 chọn cuốn khác: ≤ 2 chạm từ Thư viện (qua trang sách hay nghe thẳng)", async () => {
  await start("phone/library-full");
  const load = vi.spyOn(ebookPlayer, "load");
  await tap("Mở Người Gác Hải Đăng Cuối Cùng");
  await waitFor(() => window.location.hash.startsWith("#/book/"), "trang sách");
  await tap(/^Nghe( tiếp| ngay)?( · .+)?$/);
  await waitFor(() => load.mock.calls.some(([options]) => String(options.bookId).length > 0), "phát cuốn mới");
  expect(taps).toBeLessThanOrEqual(2);
  await click("Về Thư viện");
  await waitFor(() => find("Nghe Mùa Hoa Gạo Bên Sông"), "Thư viện");
  load.mockClear(); taps = 0;
  await tap("Nghe Mùa Hoa Gạo Bên Sông");
  await waitFor(() => load.mock.calls.length > 0, "nghe thẳng từ bìa");
  expect(taps).toBe(1);
});

it("L9 sách ở máy kia nằm ngay trong Thư viện: nghe hay tải 1 chạm", async () => {
  await start("phone/library-full");
  const load = vi.spyOn(ebookPlayer, "load"), download = vi.spyOn(ebookLibrary, "download");
  await tap("Nghe Đường Về Làng Mây");
  await waitFor(() => load.mock.calls.length > 0, "nghe sách máy kia");
  expect(taps).toBe(1);
  taps = 0;
  await tap("Tải");
  await waitFor(() => download.mock.calls.length > 0, "tải sách máy kia");
  expect(taps).toBe(1);
});

it("L9 chưa ghép: Cài đặt > Thiết bị đã hiện máy tìm thấy và ô mã ghép - 2 chạm", async () => {
  await start("phone/devices-unpaired");
  await click("Thư viện", nav());
  await waitFor(() => window.location.hash === "#/", "Thư viện");
  await tap("Cài đặt", nav());
  await tap(/^Thiết bị/, document.querySelector('nav[aria-label="Nhóm cài đặt"]')!);
  await waitFor(() => find(/^Máy tính phòng khách/) && document.querySelector('[aria-label="Mã ghép nối"], input'), "máy tìm thấy và ô mã ghép");
  expect(taps).toBe(2);
});

it("L12 sửa cách đọc: chọn câu rồi Sửa cách đọc - 2 chạm khi đang đọc theo", async () => {
  await start("phone/reader-text");
  const sentence = await waitFor(() => document.querySelector<HTMLElement>("[data-index]"), "câu");
  taps++; sentence.click();
  await tap("Sửa cách đọc");
  await waitFor(() => document.querySelector('[role="dialog"][data-state="open"]'), "hộp sửa cách đọc");
  expect(taps).toBe(2);
});

it("L13 cài đặt: không mục nào ở cấp ba", async () => {
  await start("phone/settings");
  const groups = () => [...document.querySelectorAll<HTMLAnchorElement>('nav[aria-label="Nhóm cài đặt"] a')];
  const count = groups().length;
  expect(count).toBeGreaterThan(3);
  for (let index = 0; index < count; index++) {
    const link = await waitFor(() => groups()[index], `nhóm ${index}`);
    const href = link.getAttribute("href")!;
    link.click();
    await waitFor(() => window.location.hash === href && !document.querySelector('nav[aria-label="Nhóm cài đặt"]'), href);
    await new Promise(resolve => setTimeout(resolve, 150));
    const deeper = [...document.querySelectorAll<HTMLAnchorElement>("a[href^='#/settings/']")].map(item => item.getAttribute("href")!)
      .filter(target => target.split("/").length > href.split("/").length);
    expect(deeper, href).toEqual([]);
    await click("Cài đặt", nav());
  }
});

it("L13 cài đặt: bảng đường đi chỉ có /settings/:group, không có đường cấp ba", () => {
  for (const app of ["../android/App.tsx", "../desktop/App.tsx"]) {
    const routes = [...readFileSync(new URL(app, import.meta.url), "utf8").matchAll(/path="(\/settings[^"]*)"/g)].map(match => match[1]);
    expect(routes, app).toEqual(["/settings/:group?"]);
  }
});
