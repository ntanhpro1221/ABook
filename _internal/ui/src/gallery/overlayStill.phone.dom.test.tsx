// @vitest-environment happy-dom
// Lớp phủ (bảng trượt, menu, hộp) nằm LÊN trên; nội dung bên dưới đứng yên. Chủ sách 26-10 (ảnh Đang nghe + "Thêm tuỳ chọn"): "sao giao diện
// bị đẩy lên khi cái này hiện ra?" - màn Đang nghe từng chừa lề dưới bằng chiều cao bảng, bìa co lại, cả màn nhảy lên.
import { afterEach, expect, it, vi } from "vitest";
import { installPlatform } from "./boot";
import { click, waitFor } from "./actions";
import { ENTRIES } from "./entries";

const cancel = Animation.prototype.cancel;
Animation.prototype.cancel = function () { this.finished?.catch(() => undefined); cancel.call(this); };
installPlatform("phone");
vi.setConfig({ testTimeout: 30_000 });
let unmount: (() => void) | undefined;
afterEach(() => { unmount?.(); unmount = undefined; document.body.replaceChildren(); vi.restoreAllMocks(); });

async function start(id: string) {
  // happy-dom không dàn trang: khung điện thoại thật và bảng có chiều cao thật, để màn nào muốn "chừa chỗ" theo bảng thì lộ ra.
  (window as unknown as { happyDOM: { setViewport(size: { width: number; height: number }): void } }).happyDOM.setViewport({ width: 412, height: 915 });
  const rect = HTMLElement.prototype.getBoundingClientRect;
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(function (this: HTMLElement) {
    return this.closest('[role="dialog"]') ? new DOMRect(0, 515, 412, 400) : rect.call(this);
  });
  const { runEntry } = await import("./run");
  const host = document.createElement("div"); document.body.append(host);
  unmount = await runEntry(ENTRIES.find(entry => entry.id === id)!, "light", host, { quiet: 120 });
}
// Dáng của màn bên dưới: lớp và style riêng của chính nó và mọi khối con (bìa, tên chương, nút) - happy-dom không dàn trang nên so thuộc tính.
const shape = (root: Element) => [root, ...root.querySelectorAll("*")]
  .filter(el => !el.closest('[role="dialog"]'))
  .map(el => `${el.tagName}.${el.getAttribute("class") ?? ""}|${el.getAttribute("style") ?? ""}`);

for (const opener of ["Tốc độ", "Hẹn giờ ngủ", "Chương", "Thêm tuỳ chọn"]) {
  it(`mở bảng "${opener}" trên Đang nghe: màn bên dưới không đổi dáng`, async () => {
    await start("phone/player-full");
    const screen = document.querySelector("section.now-playing")!;
    expect(screen).not.toBeNull();
    const before = shape(screen);
    await click(new RegExp(`^${opener}`));
    await waitFor(() => document.querySelector('[role="dialog"][data-state="open"]'), `bảng ${opener}`);
    await new Promise(resolve => setTimeout(resolve, 400));
    expect((screen as HTMLElement).style.paddingBottom).toBe("");
    expect(shape(screen).slice(0, 1)).toEqual(before.slice(0, 1));
  });
}
