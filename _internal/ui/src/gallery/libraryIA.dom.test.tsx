// @vitest-environment happy-dom
// Luồng thật trên cầu native giả: tab, Thiết bị và tải sách trong Thư viện.
import { afterEach, expect, it, vi } from "vitest";
import { installPlatform } from "./boot";
import { click, waitFor } from "./actions";
import { ENTRIES } from "./entries";
import { emitNative } from "./capacitor";
import { ebookLibrary } from "./phoneNative";
import { BOOKS, localBook } from "./data";

const cancel = Animation.prototype.cancel;
Animation.prototype.cancel = function () { this.finished?.catch(() => undefined); cancel.call(this); };
installPlatform("phone");
let unmount: (() => void) | undefined;
afterEach(() => { unmount?.(); unmount = undefined; document.body.replaceChildren(); vi.restoreAllMocks(); });

async function draw(id: string) {
  const { runEntry } = await import("./run");
  const host = document.createElement("div"); document.body.append(host);
  unmount = await runEntry(ENTRIES.find(entry => entry.id === id)!, "light", host, { quiet: 120 });
  return host;
}

it("ba tab là Thư viện · Studio · Cài đặt, không có tab Tải sách", async () => {
  await draw("phone/library-full");
  const nav = document.querySelector('nav[aria-label="Điều hướng"]')!;
  expect([...nav.querySelectorAll("a")].map(link => link.textContent)).toEqual(["Thư viện", "Studio", "Cài đặt"]);
  expect(nav.querySelector('[href="#/devices"]')).toBeNull();
});

it("ở trang sách thanh đáy vẫn tô Thư viện", async () => {
  await draw("phone/book");
  const nav = document.querySelector('nav[aria-label="Điều hướng"]')!;
  expect([...nav.querySelectorAll("a")].filter(link => link.classList.contains("text-accent-text")).map(link => link.textContent)).toEqual(["Thư viện"]);
});

it("Thiết bị ở cấp hai, tới được bằng hai chạm qua Cài đặt", async () => {
  await draw("phone/library-full");
  await click("Cài đặt", document.querySelector('nav[aria-label="Điều hướng"]')!);
  await click(/^Thiết bị/, document.querySelector('nav[aria-label="Nhóm cài đặt"]')!);
  await waitFor(() => document.querySelector("h1")?.textContent === "Thiết bị", "Thiết bị");
  expect(window.location.hash).toBe("#/settings/devices");
  expect(document.querySelector('[aria-label="Về Cài đặt"]')).not.toBeNull();
  expect(document.body.textContent).toContain("Điện thoại này");
  expect(document.body.textContent).toContain("Dung lượng");
});

it("Studio rỗng có một câu và lối Nối máy tính tới Thiết bị", async () => {
  await draw("phone/studio-empty");
  expect(document.querySelector("h1")?.textContent).toBe("Studio");
  expect(document.body.textContent).toContain("Nối máy tính của bạn để tạo sách nói.");
  await click("Nối máy tính");
  await waitFor(() => window.location.hash === "#/settings/devices", "đường nối máy");
});

it("Mở Studio dùng đúng lệnh mở máy đã ghép hiện có", async () => {
  const open = vi.spyOn(ebookLibrary, "openStudio");
  await draw("phone/studio");
  await click("Mở Studio");
  expect(open).toHaveBeenCalledWith({ computer: "" });
});

it("bộ sách trên điện thoại mở bảng đáy và Back đóng trước khi rời trang", async () => {
  await draw("phone/library-full");
  await click("Mở bộ Thành Phố Sương Mù");
  expect(document.querySelector('[role="dialog"][data-state="open"]')?.classList.contains("motion-sheet")).toBe(true);
  emitNative("App", "backButton", {});
  await waitFor(() => !document.querySelector('[role="dialog"][data-state="open"]'), "Back đóng bộ sách");
  expect(window.location.hash).toBe("#/");
});

it("sách điện thoại ghép có dấu nguồn và tải bằng đúng mã máy, mã sách", async () => {
  vi.spyOn(ebookLibrary, "remoteLibrary").mockImplementation(() => ({ books: [] }));
  vi.spyOn(ebookLibrary, "peerLibraries").mockImplementation(() => ({ peers: [{ key: "phone-b", name: "Máy của bạn", host: "192.168.1.20", books: [{
    id: "lang-may", remoteId: "original", title: "Đường Về Làng Mây", duration: 600, chaptersTotal: 1, chaptersAvailable: 1, downloaded: false, localChapters: 0,
  }] }] }));
  vi.spyOn(ebookLibrary, "streamableBooks").mockImplementation(() => ({ books: [{ ...localBook(BOOKS.find(book => book.id === "lang-may")!), sourceName: "Máy của bạn" }] }));
  const download = vi.spyOn(ebookLibrary, "download");
  await draw("phone/library-full");
  await waitFor(() => document.querySelector('[aria-label="Trên Máy của bạn"]'), "dấu nguồn điện thoại");
  await click("Tải");
  expect(download).toHaveBeenCalledWith({ bookId: "lang-may", source: "phone-b", remoteId: "original" });
});

it("nguồn máy kia và tiến độ tải ở ngay bìa, hủy tải giữ thư viện", async () => {
  await draw("phone/library-full");
  const mark = document.querySelector('[aria-label="Trên máy tính"]');
  expect(mark).not.toBeNull();
  emitNative("EbookLibrary", "download", { bookId: "lang-may", done: 42, total: 100, files: 4, filesTotal: 10 });
  await waitFor(() => document.querySelector('[aria-label="Đang tải Đường Về Làng Mây"]'), "tiến độ bìa");
  expect(document.body.textContent).toContain("42%");
  await click("Huỷ tải Đường Về Làng Mây");
  await waitFor(() => !document.querySelector('[aria-label="Huỷ tải Đường Về Làng Mây"]'), "kết thúc tải");
  expect(document.querySelector("h1")?.textContent).toBe("Thư viện");
});

it("gói nghe trực tiếp chưa về vẫn có bìa để tải, sách đã có không bị lặp", async () => {
  vi.spyOn(ebookLibrary, "streamableBooks").mockImplementation(() => ({ books: [] }));
  await draw("phone/library-full");
  expect(document.querySelectorAll('[aria-label="Mở Đường Về Làng Mây"]')).toHaveLength(1);
  expect(document.querySelectorAll('[aria-label="Mở Người Gác Hải Đăng Cuối Cùng"]')).toHaveLength(1);
  await click("Tải");
  await waitFor(() => document.querySelector('[aria-label="Đang tải Đường Về Làng Mây"]'), "tải từ danh mục");
});
