// @vitest-environment happy-dom
import { afterEach, describe, expect, it, vi } from "vitest";
import { settleLaunch } from "./App";

/** Hoạt ảnh giả: chỉ những trường settleLaunch đọc. */
function fakeAnimation(endTime: number) {
  const animation = { playState: "running", effect: { getComputedTiming: () => ({ endTime }) }, finish: vi.fn(() => { animation.playState = "finished"; }) };
  return animation;
}

describe("settleLaunch (màn chờ mở app)", () => {
  afterEach(() => { delete (document as { getAnimations?: unknown }).getAnimations; document.body.innerHTML = ""; });

  it("khung chờ còn thì bận và không đụng hoạt ảnh", () => {
    const page = document.createElement("main");
    page.innerHTML = '<div class="motion-loading-placeholder"></div>';
    const running = fakeAnimation(420);
    (document as { getAnimations?: unknown }).getAnimations = () => [running];
    expect(settleLaunch(page)).toBe(true);
    expect(running.finish).not.toHaveBeenCalled();
  });

  it("dựng xong: hoạt ảnh hữu hạn tới ngay trạng thái cuối (màn chờ chặn khung hình nên chúng không tự chạy), vòng lặp vô hạn để yên", () => {
    const page = document.createElement("main");
    const reveal = fakeAnimation(300);
    const spinner = fakeAnimation(Infinity);
    let list = [reveal, spinner];
    (document as { getAnimations?: unknown }).getAnimations = () => list.filter((a) => a.playState === "running");
    expect(settleLaunch(page)).toBe(true); // vừa kết thúc một hoạt ảnh: xem lại một nhịp
    expect(reveal.finish).toHaveBeenCalledOnce();
    expect(spinner.finish).not.toHaveBeenCalled();
    expect(settleLaunch(page)).toBe(false);
    list = [];
  });

  it("khung chờ đang thoát được kết thúc, không đợi animationend mới xét hoạt ảnh", () => {
    const page = document.createElement("main");
    page.innerHTML = '<div class="motion-loading-placeholder" data-state="closed"></div>';
    const exit = fakeAnimation(150);
    (document as { getAnimations?: unknown }).getAnimations = () => [exit];
    expect(settleLaunch(page)).toBe(true);
    expect(exit.finish).toHaveBeenCalledOnce();
    expect(settleLaunch(page)).toBe(false);
  });

  it("chỉ đợi ảnh trong phần trang đang thấy; ảnh lười dưới vùng cuộn hay bị ẩn không giữ màn chờ", () => {
    const page = document.createElement("main"), image = document.createElement("img");
    page.append(image);
    Object.defineProperty(image, "complete", { value: false });
    const box = (y: number, width = 100) => ({ x: 20, y, left: 20, top: y, right: 20 + width, bottom: y + 150, width, height: 150, toJSON() {} });
    page.getBoundingClientRect = () => ({ ...box(0, 412), bottom: 800, height: 800 });
    image.getBoundingClientRect = () => box(20);
    expect(settleLaunch(page)).toBe(true);
    image.loading = "lazy";
    image.getBoundingClientRect = () => box(10000);
    expect(settleLaunch(page)).toBe(false);
    image.getBoundingClientRect = () => box(20, 0);
    expect(settleLaunch(page)).toBe(false);
    image.getBoundingClientRect = () => box(-200);
    expect(settleLaunch(page)).toBe(false);
  });
});
