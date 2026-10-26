// @vitest-environment happy-dom
// Chủ sách 26-10 (video mở Đang nghe): "toàn bộ cửa sổ mới được phóng ra từ dòng thu nhỏ... bìa, tên, tên chương, nút play... sẽ lerp (scale,
// move, fade màu) từ bản cũ sang bản mới". Đo trên một khung giả có hộp thật: màn nở từ đúng hộp của thanh, phần chung bay từ đúng chỗ cũ.
import { afterEach, expect, it, vi } from "vitest";
import { barClip, morphNowPlaying, partTransform, unsharedBlocks } from "./nowPlayingMorph";

const boxes = new Map<string, DOMRect>();
afterEach(() => { vi.restoreAllMocks(); document.body.replaceChildren(); boxes.clear(); });

function stage() {
  document.body.innerHTML = `
    <section data-np-source id="bar"><div data-np="cover" id="bar-cover"></div><div data-np="chapter" id="bar-chapter">Chương 1</div>
      <div data-np="book" id="bar-book">Sách</div><button data-np="play" id="bar-play"></button></section>
    <section id="screen"><header id="top">ĐANG NGHE</header>
      <div id="cover-block"><button id="cover-button"><div data-np="cover" id="np-cover"></div></button></div>
      <div id="titles"><h2 data-np="chapter" id="np-chapter">Chương 1</h2><p data-np="book" id="np-book">Sách</p><p id="credit">Nhạc</p></div>
      <div id="transport"><button id="back15"></button><button data-np="play" id="np-play"></button><button id="next15"></button></div></section>`;
  const set = (id: string, x: number, y: number, w: number, h: number) => boxes.set(id, new DOMRect(x, y, w, h));
  set("bar", 0, 786, 412, 65); set("bar-cover", 12, 796, 44, 44); set("bar-chapter", 68, 798, 280, 20); set("bar-book", 68, 818, 280, 16); set("bar-play", 356, 796, 44, 44);
  set("screen", 0, 0, 412, 915); set("top", 0, 40, 412, 48); set("cover-block", 0, 100, 412, 380); set("cover-button", 16, 100, 380, 380); set("np-cover", 16, 100, 380, 380);
  set("titles", 16, 520, 380, 56); set("np-chapter", 16, 520, 380, 28); set("np-book", 16, 550, 380, 20); set("credit", 16, 572, 380, 16);
  set("transport", 16, 640, 380, 72); set("back15", 40, 652, 48, 48); set("np-play", 170, 640, 72, 72); set("next15", 324, 652, 48, 48);
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(function (this: HTMLElement) { return boxes.get(this.id) ?? new DOMRect(0, 0, 0, 0); });
  const animate = vi.fn(function (this: Element) { return { currentTime: 0, cancel: vi.fn(), finished: new Promise(() => undefined) } as unknown as Animation; });
  Element.prototype.animate = animate as unknown as Element["animate"];
  return { screen: document.getElementById("screen")!, animate };
}
const call = (animate: ReturnType<typeof vi.fn>, id: string) => animate.mock.calls.find((_, index) => (animate.mock.contexts[index] as Element).id === id);

it("mở: cả màn nở từ đúng hộp của thanh nhỏ", () => {
  const { screen, animate } = stage();
  expect(morphNowPlaying(screen, "open")).not.toBeNull();
  const frames = call(animate, "screen")![0] as { clipPath: string[] };
  expect(frames.clipPath).toEqual([barClip(boxes.get("screen")!, boxes.get("bar")!), "inset(0px 0px 0px 0px round 0px)"]);
  expect(frames.clipPath[0]).toBe("inset(786px 0px 64px 0px round 0px)");
});

it("mở: bìa, tên chương, tên sách, nút phát bay từ chỗ trên thanh; chữ co giãn đều, không méo", () => {
  const { screen, animate } = stage();
  morphNowPlaying(screen, "open");
  for (const [part, from, to] of [["cover", "bar-cover", "np-cover"], ["chapter", "bar-chapter", "np-chapter"], ["book", "bar-book", "np-book"], ["play", "bar-play", "np-play"]] as const) {
    const [first, last] = call(animate, to)![0] as Keyframe[];
    expect(first.transform).toBe(partTransform(part, boxes.get(from)!, boxes.get(to)!));
    expect(last.transform).toBe("none");
  }
  expect(partTransform("chapter", boxes.get("bar-chapter")!, boxes.get("np-chapter")!)).toMatch(/scale\(0\.714\d*\)$/);
});

it("phần riêng của màn (thanh đầu, nút tua, dòng nhạc) chuyển động riêng, không kéo phần chung theo", () => {
  const { screen, animate } = stage();
  morphNowPlaying(screen, "open");
  const shared = new Set(["np-cover", "np-chapter", "np-book", "np-play"].map((id) => document.getElementById(id)!));
  expect(unsharedBlocks(screen, shared).map((el) => el.id)).toEqual(["top", "credit", "back15", "next15"]);
  for (const id of ["top", "credit", "back15", "next15"]) expect((call(animate, id)![0] as Keyframe[])[0].transform).toMatch(/translateY\(\d+(\.\d+)?px\) scale\(0\.92\)/);
  for (const id of ["cover-block", "titles", "transport", "cover-button"]) expect(call(animate, id)).toBeUndefined();
});

it("đóng: thu về đúng hộp của thanh (thứ tự khung ngược lại)", () => {
  const { screen, animate } = stage();
  morphNowPlaying(screen, "close");
  expect((call(animate, "screen")![0] as { clipPath: string[] }).clipPath.at(-1)).toBe("inset(786px 0px 64px 0px round 0px)");
  expect((call(animate, "np-cover")![0] as Keyframe[]).at(-1)!.transform).toBe(partTransform("cover", boxes.get("bar-cover")!, boxes.get("np-cover")!));
});

it("không có thanh nhỏ (chưa dựng / cao 0): trả null để đường CSS lo", () => {
  const { screen } = stage();
  boxes.set("bar", new DOMRect(0, 851, 412, 0));
  expect(morphNowPlaying(screen, "open")).toBeNull();
});
