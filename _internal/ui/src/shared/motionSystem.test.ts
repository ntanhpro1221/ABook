// @vitest-environment node
// a120: hệ chuyển động một chỗ (shared/motion.ts) - đổi trang / Đang nghe / đổi giao diện qua View Transition có đường dự phòng, lớp tự dựng chờ
// hiệu ứng đóng, danh sách thêm / xoá, <details> mở / gập.
import { readFileSync } from "node:fs";
import { describe, expect, it, vi } from "vitest";
import { exitCompletion, fallbackSnapshot, measureMotionRow, mergeRows, MOTION, navMotion, presenceMounted, settleRows, toggleDetails, withViewTransition, type DetailsLike, type PresentRow } from "./motion";

function fakeTransitionDocument(withApi = true, visibility = "visible") {
  const dataset: Record<string, string | undefined> = {};
  const finishers: (() => void)[] = [];
  const calls: string[] = [];
  const doc = {
    documentElement: { dataset: dataset as DOMStringMap },
    visibilityState: visibility,
    startViewTransition: withApi
      ? (update: () => void) => {
          calls.push(`start nav=${dataset.nav} vt=${dataset.vt}`);
          update();
          return { ready: Promise.resolve(), finished: new Promise<void>((resolve) => finishers.push(resolve)) };
        }
      : undefined,
  };
  return { doc, dataset, calls, finishers };
}

const tick = () => new Promise((resolve) => setTimeout(resolve, 0));

it("ảnh fallback chỉ là hình cũ: không role/id/name để Back hay radio nhận nhầm, giữ cuộn và tự gỡ dù thiếu animationend", () => {
  vi.useFakeTimers();
  try {
    const child = { removeAttribute: vi.fn(), scrollTop: 0, scrollLeft: 0 };
    const remove = vi.fn();
    const clone = {
      style: { setProperty: vi.fn() }, classList: { add: vi.fn() },
      removeAttribute: vi.fn(), setAttribute: vi.fn(), remove,
      querySelectorAll: (selector: string) => selector === ".motion-snapshot" ? [] : [child], addEventListener: vi.fn(), scrollTop: 0, scrollLeft: 0,
    };
    const target = {
      getBoundingClientRect: () => ({ top: 20, left: 10, width: 360, height: 600 }),
      cloneNode: () => clone, querySelectorAll: () => [{ scrollTop: 12, scrollLeft: 0 }], scrollTop: 150, scrollLeft: 0,
    };
    const append = vi.fn();
    const doc = { body: { append }, querySelector: () => target, documentElement: { dataset: {} } } as unknown as Parameters<typeof fallbackSnapshot>[0];
    vi.stubGlobal("window", { setTimeout, clearTimeout });
    vi.stubGlobal("getComputedStyle", () => Object.assign(["--bg"], { getPropertyValue: () => "#fff", backgroundColor: "rgba(0, 0, 0, 0)" }));
    fallbackSnapshot(doc, "back");
    expect(append).toHaveBeenCalledWith(clone);
    expect(clone.removeAttribute).toHaveBeenCalledWith("role");
    expect(clone.removeAttribute).toHaveBeenCalledWith("id");
    expect(child.removeAttribute).toHaveBeenCalledWith("name");
    expect(clone.setAttribute).toHaveBeenCalledWith("inert", "");
    expect(clone.setAttribute).toHaveBeenCalledWith("aria-hidden", "true");
    expect(clone.scrollTop).toBe(150);
    expect(child.scrollTop).toBe(12);
    vi.runAllTimers();
    expect(remove).toHaveBeenCalledTimes(1);
  } finally { vi.unstubAllGlobals(); vi.useRealTimers(); }
});

describe("withViewTransition (đổi trang, Đang nghe, đổi giao diện)", () => {
  it("API huỷ trước callback cập nhật: thao tác vẫn chạy đúng một lần và không để cờ VT treo", async () => {
    let callback = () => {};
    const dataset = {} as DOMStringMap;
    const doc = { documentElement: { dataset }, startViewTransition: (update: () => void) => {
      callback = update;
      return { ready: Promise.reject(new Error("skipped")), finished: Promise.reject(new Error("skipped")) };
    } };
    let runs = 0;
    withViewTransition(() => runs++, "back", doc, (run) => run());
    await tick();
    callback();
    expect(runs).toBe(1);
    expect(dataset.vt).toBeUndefined();
  });
  it("không có View Transitions: đổi thẳng, đúng một lần, không đánh dấu gì", () => {
    const { doc, dataset } = fakeTransitionDocument(false);
    let runs = 0;
    expect(withViewTransition(() => runs++, "forward", doc, (run) => run())).toBe(false);
    expect(runs).toBe(1);
    expect(dataset.vt).toBeUndefined();
  });

  it("cửa sổ đang ẩn (thu nhỏ): đổi thẳng - trình duyệt sẽ huỷ chuyển cảnh thành lỗi", () => {
    const { doc, calls } = fakeTransitionDocument(true, "hidden");
    let runs = 0;
    withViewTransition(() => runs++, "back", doc, (run) => run());
    expect(runs).toBe(1);
    expect(calls).toEqual([]);
  });

  it("có API: ghi hướng lên <html> cho CSS trước khi chụp, chạy thay đổi một lần, gỡ dấu khi xong", async () => {
    const { doc, dataset, calls, finishers } = fakeTransitionDocument();
    let runs = 0;
    expect(withViewTransition(() => runs++, "back", doc, (run) => run())).toBe(true);
    expect(calls).toEqual(["start nav=back vt=1"]);
    expect(runs).toBe(1);
    expect(dataset.nav).toBe("back");
    finishers[0]();
    await tick();
    expect(dataset.vt).toBeUndefined();
    expect(dataset.nav).toBeUndefined();
  });

  it("lần chuyển sau đè lần trước: lần trước xong muộn không gỡ dấu của lần sau (Back bấm liên tiếp)", async () => {
    const { doc, dataset, finishers } = fakeTransitionDocument();
    let runs = 0;
    withViewTransition(() => runs++, "forward", doc, (run) => run());
    withViewTransition(() => runs++, "back", doc, (run) => run());
    expect(runs).toBe(2);
    finishers[0]();
    await tick();
    expect(dataset.nav).toBe("back");
    finishers[1]();
    await tick();
    expect(dataset.nav).toBeUndefined();
  });

  it("startViewTransition ném lỗi: thay đổi vẫn chạy đúng một lần", () => {
    let runs = 0;
    const doc = {
      documentElement: { dataset: {} as DOMStringMap },
      startViewTransition: (): never => {
        throw new Error("InvalidStateError");
      },
    };
    withViewTransition(() => runs++, "none", doc, (run) => run());
    expect(runs).toBe(1);
  });
});

describe("navMotion: hướng chuyển trang", () => {
  const at = (pathname: string, idx: number) => ({ pathname, idx });
  it("trình tạo sách dùng ?step=: đi tới/lùi có chuyển trục dù cùng pathname", () => {
    expect(navMotion("PUSH", { ...at("/studio/new", 1), search: "?step=1" }, { ...at("/studio/new", 2), search: "?step=2" })).toBe("forward");
    expect(navMotion("POP", { ...at("/studio/new", 2), search: "?step=2" }, { ...at("/studio/new", 1), search: "?step=1" })).toBe("back");
  });
  it("mở sâu hơn = tới; Back = lùi; thay chỗ khác trang (nhóm cài đặt ở hai cột) = mờ qua; chỉ đổi ?tab= = trang đứng yên", () => {
    expect(navMotion("PUSH", at("/", 0), at("/book/a", 1))).toBe("forward");
    expect(navMotion("POP", at("/book/a", 1), at("/", 0))).toBe("back");
    expect(navMotion("POP", at("/", 0), at("/book/a", 1))).toBe("forward"); // nút Tới của trình duyệt
    expect(navMotion("REPLACE", at("/book/a", 1), at("/book/a", 1))).toBe("none");
    expect(navMotion("REPLACE", at("/settings/voice", 1), at("/settings/gestures", 1))).toBe("through");
    expect(navMotion("PUSH", at("/settings", 1), at("/settings/voice", 2))).toBe("forward");
    expect(navMotion("POP", at("/settings/voice", 2), at("/settings", 1))).toBe("back");
  });
  it("giữa các mục gốc (tab dưới, thanh bên) là ngang hàng", () => {
    expect(navMotion("PUSH", at("/", 0), at("/studio", 1))).toBe("through");
    expect(navMotion("POP", at("/settings", 2), at("/studio", 1))).toBe("through");
  });
  it("cùng trang, chỉ đổi ?tìm / # bằng PUSH: không chuyển vùng trang", () => {
    expect(navMotion("PUSH", at("/book/a", 1), at("/book/a", 2))).toBe("none");
  });
});

describe("lớp tự dựng chờ hiệu ứng đóng (usePresence)", () => {
  it("chờ animationend của chính lớp; sự kiện con không gỡ lớp; timer không gọi lần hai", () => {
    vi.useFakeTimers();
    try {
      const done = vi.fn();
      const exit = exitCompletion(done, MOTION.mediumOut);
      const parent = {};
      exit.end({ target: {}, currentTarget: parent });
      expect(done).not.toHaveBeenCalled();
      exit.end({ target: parent, currentTarget: parent });
      expect(done).toHaveBeenCalledTimes(1);
      vi.runAllTimers();
      expect(done).toHaveBeenCalledTimes(1);
    } finally { vi.useRealTimers(); }
  });
  it("không có animationend vẫn gỡ sau giới hạn; mở lại thì huỷ cả timer lẫn callback cũ", () => {
    vi.useFakeTimers();
    try {
      const done = vi.fn();
      exitCompletion(done, MOTION.mediumOut);
      vi.advanceTimersByTime(MOTION.mediumOut + 79);
      expect(done).not.toHaveBeenCalled();
      vi.advanceTimersByTime(1);
      expect(done).toHaveBeenCalledTimes(1);
      const old = exitCompletion(done, MOTION.mediumOut);
      old.cancel();
      old.end({ target: null, currentTarget: null });
      vi.runAllTimers();
      expect(done).toHaveBeenCalledTimes(1);
    } finally { vi.useRealTimers(); }
  });
  it("đóng rồi mà hiệu ứng chưa xong thì vẫn còn; xong (animationend / hẹn giờ) thì gỡ; mở lại thì còn ngay", () => {
    expect(presenceMounted(true, false, false)).toBe(true);
    expect(presenceMounted(false, true, false)).toBe(true);
    expect(presenceMounted(false, true, true)).toBe(false);
    expect(presenceMounted(true, true, true)).toBe(true);
    expect(presenceMounted(false, false, false)).toBe(false);
  });
  it("ra nhanh hơn vào ở mọi bậc", () => {
    expect(MOTION.fastOut).toBeLessThan(MOTION.fast);
    expect(MOTION.mediumOut).toBeLessThan(MOTION.medium);
    expect(MOTION.slowOut).toBeLessThan(MOTION.slow);
  });
});

describe("danh sách thêm / xoá (useListPresence)", () => {
  it("chiều cao lấy từ nội dung (scrollHeight), kể cả khi hàng đang co về 0", () => {
    const setProperty = vi.fn();
    measureMotionRow({ firstElementChild: { scrollHeight: 92 }, style: { setProperty } } as unknown as HTMLElement);
    expect(setProperty).toHaveBeenCalledWith("--row-height", "92px");
    measureMotionRow(null);
  });
  type Item = { id: string; n?: number };
  const key = (item: Item) => item.id;
  const ids = (rows: PresentRow<Item>[]) => rows.map((row) => `${row.key}:${row.state}`);
  it("sắp xếp lại rồi thêm / xoá: hàng sống theo thứ tự mới, không giữ thứ tự màn cũ", () => {
    const old = mergeRows([], [{ id: "a" }, { id: "b" }, { id: "c" }], key, true);
    expect(ids(mergeRows(old, [{ id: "c" }, { id: "x" }, { id: "a" }], key))).toEqual(["b:exit", "c:idle", "x:enter", "a:idle"]);
    expect(ids(settleRows(mergeRows(old, [], key)))).toEqual([]);
  });
  it("lần dựng đầu không hàng nào mở ra (cả trang đã có hiệu ứng mở)", () => {
    expect(ids(mergeRows([], [{ id: "a" }, { id: "b" }], key, true))).toEqual(["a:idle", "b:idle"]);
  });
  it("hàng mới mở ra đúng chỗ của nó; hàng bị xoá khép lại TẠI CHỖ cũ rồi mới gỡ", () => {
    const shown = mergeRows([], [{ id: "a" }, { id: "b" }, { id: "c" }], key, true);
    const next = mergeRows(shown, [{ id: "x" }, { id: "a" }, { id: "c" }], key);
    expect(ids(next)).toEqual(["x:enter", "a:idle", "b:exit", "c:idle"]);
    expect(ids(settleRows(next))).toEqual(["x:idle", "a:idle", "c:idle"]);
  });
  it("hàng đang khép mà quay lại (Hoàn tác) thì mở ra lại, không nhân đôi", () => {
    const shown = mergeRows(mergeRows([], [{ id: "a" }, { id: "b" }], key, true), [{ id: "a" }], key);
    expect(ids(shown)).toEqual(["a:idle", "b:exit"]);
    expect(ids(mergeRows(shown, [{ id: "a" }, { id: "b" }], key))).toEqual(["a:idle", "b:enter"]);
  });
  it("hàng còn lại mang dữ liệu mới nhất", () => {
    const shown = mergeRows([], [{ id: "a", n: 1 }], key, true);
    expect(mergeRows(shown, [{ id: "a", n: 2 }], key)[0].item).toEqual({ id: "a", n: 2 });
  });
});

describe("<details> mở / gập có chuyển động", () => {
  type Frames = { from: string; to: string; duration: number };
  type FakeAnimation = { onfinish: (() => void) | null; oncancel: (() => void) | null; cancel(): void };
  function fakeDetails(open: boolean, heights = { summary: 30, full: 200 }) {
    const played: Frames[] = [];
    let last: FakeAnimation | null = null;
    const details: DetailsLike & { finish(): void } = {
      open,
      style: { height: "", overflow: "" },
      dataset: {} as DOMStringMap,
      getBoundingClientRect: () => ({ height: details.open ? heights.full : heights.summary }),
      querySelector: () => ({ getBoundingClientRect: () => ({ height: heights.summary }) }),
      animate: (frames, options) => {
        played.push({ from: String(frames[0].height), to: String(frames[1].height), duration: Number(options.duration) });
        const animation: FakeAnimation = { onfinish: null, oncancel: null, cancel: () => animation.oncancel?.() };
        last = animation;
        return animation;
      },
      finish: () => last?.onfinish?.(),
    };
    return { details, played };
  }

  it("mở: đặt open trước rồi kéo cao từ dòng tóm tắt tới đủ nội dung", () => {
    const { details, played } = fakeDetails(false);
    expect(toggleDetails(details, 0, false)).toBe(true);
    expect(details.open).toBe(true);
    expect(played).toEqual([{ from: "30px", to: "200px", duration: MOTION.medium }]);
    details.finish();
    expect(details.dataset.motion).toBeUndefined();
    expect(details.style.overflow).toBe("");
  });

  it("gập: khép tới dòng tóm tắt (cộng đệm), CHỈ bỏ open khi hiệu ứng xong - ra nhanh hơn vào", () => {
    const { details, played } = fakeDetails(true);
    toggleDetails(details, 8, false);
    expect(details.open).toBe(true);
    expect(played[0]).toEqual({ from: "200px", to: "38px", duration: MOTION.mediumOut });
    details.finish();
    expect(details.open).toBe(false);
  });

  it("bấm lại giữa chừng thì đảo chiều, không kẹt nửa vời", () => {
    const { details } = fakeDetails(true);
    toggleDetails(details, 0, false); // đang gập
    toggleDetails(details, 0, false); // đổi ý: mở lại
    expect(details.dataset.motion).toBe("opening");
    details.finish();
    expect(details.open).toBe(true);
    expect(details.dataset.motion).toBeUndefined();
  });

  it("xin giảm chuyển động chỉ fade; không có Web Animations vẫn giữ thân qua CSS fade và đảo chiều được", () => {
    const { details, played } = fakeDetails(false);
    toggleDetails(details, 0, true);
    expect(played[0].duration).toBe(MOTION.fast);
    expect(played[0].from).toBe("undefined"); // Reduced chỉ fade, không keyframe height.
    expect(played[0].to).toBe("undefined");
    const bare = { ...fakeDetails(false).details, animate: undefined };
    vi.useFakeTimers();
    try {
      expect(toggleDetails(bare, 0, false)).toBe(true);
      expect(bare.open).toBe(true);
      expect(bare.dataset.motionFallback).toBe("1");
      toggleDetails(bare, 0, false);
      expect(bare.open).toBe(true);
      expect(bare.dataset.motion).toBe("closing");
      toggleDetails(bare, 0, false); // Đảo chiều huỷ thời hạn đóng cũ.
      vi.runAllTimers();
      expect(bare.open).toBe(true);
      toggleDetails(bare, 0, false);
      vi.runAllTimers();
      expect(bare.open).toBe(false);
      expect(bare.dataset.motionFallback).toBeUndefined();
    } finally { vi.useRealTimers(); }
  });
});

describe("không chỗ nào bật tắt cứng: các chỗ chung đều đi qua hệ chuyển động", () => {
  const source = (path: string) => readFileSync(new URL(path, import.meta.url), "utf8");
  const css = source("../styles.css");

  it("hai nền đổi trang qua MotionHashRouter (View Transition + đường dự phòng), vùng trang mang tên chuyển cảnh", () => {
    for (const app of ["../android/App.tsx", "../desktop/App.tsx"]) {
      expect(source(app)).toContain("<MotionHashRouter>");
      expect(source(app)).not.toMatch(/<HashRouter>/);
    }
    expect(source("../android/App.tsx")).toMatch(/<main[^>]*className="page-motion/);
    expect(source("../desktop/Shell.tsx")).toMatch(/<main[^>]*className="page-motion/);
    expect(css).toMatch(/\.page-motion \{\s*view-transition-name: page;/);
  });

  it("hộp thoại, tấm trượt, nền tối, tooltip có chuyển động cả lúc mở lẫn lúc đóng (keyframe vào / ra khác tên cho Presence của Radix)", () => {
    const ui = source("./ui.tsx");
    expect(ui).toContain('className="motion-scrim');
    expect(ui).toContain('"motion-dialog ');
    expect(ui).toContain('"motion-sheet sheet-surface ');
    expect(ui).toContain('className="motion-tooltip ');
    for (const name of ["motion-dialog", "motion-sheet", "motion-scrim"]) {
      expect(css).toMatch(new RegExp(String.raw`\.${name}\[data-state="open"\] \{\s*animation: (motion-enter|fade-in) `));
      expect(css).toMatch(new RegExp(String.raw`\.${name}\[data-state="closed"\] \{\s*animation: (motion-exit|fade-out) `));
    }
    // Menu / bảng nổi / danh sách chọn của Radix: một luật chung cho mọi nơi.
    expect(css).toContain('[data-radix-popper-content-wrapper] > [data-state="closed"] {');
  });

  it("chuyển cảnh không nuốt chạm; xin giảm chuyển động chỉ bỏ phần dịch chỗ, vẫn hiện / mờ", () => {
    expect(css).toMatch(/::view-transition \{\s*pointer-events: none;/);
    expect(css).toMatch(/prefers-reduced-motion: reduce\) \{\s*:root \{\s*--motion-amount: 0;/);
    expect(css).not.toMatch(/transition-duration: 0ms/);
  });

  it("mọi <details> mở / gập có chuyển động: cài một lần ở cả hai lối vào", () => {
    expect(source("../main.tsx")).toContain("installDetailsMotion();");
    expect(source("../android/main.tsx")).toContain("installDetailsMotion();");
  });

  it("mở / đóng Đang nghe và đổi giao diện sáng / tối đi qua withViewTransition (kể cả khi xin giảm chuyển động)", () => {
    expect(source("../listen/player.tsx")).toContain("withViewTransition(() => setExpanded(value))");
    expect(source("../listen/player.tsx")).not.toContain("prefersReducedMotion()");
    expect(source("../android/settings.ts")).toContain("withViewTransition(set");
    expect(source("../desktop/App.tsx")).toContain("withViewTransition(() => (root.dataset.theme = next)");
  });
});
