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
});
