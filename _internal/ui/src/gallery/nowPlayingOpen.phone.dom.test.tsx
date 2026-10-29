// @vitest-environment happy-dom
// Chủ sách 26-10 (video mở Đang nghe): màn phải nở ra từ thanh phát nhỏ, không phải một cửa sổ khác trượt lên kèm mờ. Mở thật trên gallery
// điện thoại: màn được cắt từ đúng khung thanh rồi nở ra; không có hoạt ảnh kéo cao từ 0 hay hiện dần của chính màn (lỗi vùng rỗng cập nhật
// thành màn - cùng một MotionRegion - tự kéo cao 0 -> 915 px và mờ vào).
import { afterEach, expect, it, vi } from "vitest";
import { installPlatform } from "./boot";
import { waitFor } from "./actions";
import { ENTRIES } from "./entries";

const cancel = Animation.prototype.cancel;
Animation.prototype.cancel = function () { this.finished?.catch(() => undefined); cancel.call(this); };
installPlatform("phone");
vi.setConfig({ testTimeout: 30_000 });
let unmount: (() => void) | undefined;
afterEach(() => { unmount?.(); unmount = undefined; document.body.replaceChildren(); vi.restoreAllMocks(); });

it("bấm thanh phát nhỏ: màn Đang nghe nở ra từ đúng khung thanh, không kéo cao, không hiện dần cả màn", async () => {
  (window as unknown as { happyDOM: { setViewport(size: { width: number; height: number }): void } }).happyDOM.setViewport({ width: 412, height: 915 });
  const rect = HTMLElement.prototype.getBoundingClientRect;
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(function (this: HTMLElement) {
    if (this.matches("section.now-playing")) return new DOMRect(0, 0, 412, 915);
    if (this.matches("[data-np-source]")) return new DOMRect(0, 786, 412, 65);
    return this.matches("[data-np]") ? new DOMRect(16, 100, 120, 40) : rect.call(this);
  });
  const { runEntry } = await import("./run");
  const host = document.createElement("div"); document.body.append(host);
  unmount = await runEntry(ENTRIES.find(entry => entry.id === "phone/player-mini")!, "dark", host, { quiet: 120 });
  const animate = vi.spyOn(Element.prototype, "animate");
  const bar = await waitFor(() => document.querySelector<HTMLElement>('[data-np-source] [aria-label="Mở màn hình đang nghe"]'), "thanh phát nhỏ");
  bar.click();
  const screen = await waitFor(() => document.querySelector<HTMLElement>('section.now-playing[data-state="open"]'), "màn Đang nghe");
  const own = animate.mock.calls.filter((_, index) => animate.mock.contexts[index] === screen).map(([frames]) => frames as Record<string, unknown>);
  expect(own.some((frames) => Array.isArray(frames.clipPath) && frames.clipPath[0] === "inset(786px 0px 64px 0px round 0px)")).toBe(true);
  expect(JSON.stringify(own)).not.toMatch(/"height"/);
  expect(own.some((frames) => Array.isArray(frames) && frames.some((frame: Keyframe) => frame.opacity !== undefined))).toBe(false);
});
