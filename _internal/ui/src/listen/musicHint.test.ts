import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { resetSceneMusicHint, SCENE_MUSIC_HINT, SCENE_MUSIC_HINT_KEY, takeSceneMusicHint, tellSceneMusic } from "./musicHint";

function fakeStore(initial: Record<string, string> = {}) {
  const data = { ...initial };
  return { data, getItem: (key: string) => data[key] ?? null, setItem: (key: string, value: string) => void (data[key] = value) };
}

describe("nhắc một lần khi nhạc nền theo cảnh kêu lần đầu", () => {
  beforeEach(() => resetSceneMusicHint());

  it("lần đầu trên máy thì nhắc và ghi nhớ; máy đã nhắc rồi thì thôi", () => {
    const store = fakeStore();
    expect(takeSceneMusicHint(store)).toBe(true);
    expect(store.data[SCENE_MUSIC_HINT_KEY]).toBe("1");
    resetSceneMusicHint();
    expect(takeSceneMusicHint(store)).toBe(false);
  });

  it("trong một phiên chỉ nhắc một lần dù bộ nhớ trống", () => {
    expect(takeSceneMusicHint(fakeStore())).toBe(true);
    expect(takeSceneMusicHint(fakeStore())).toBe(false);
  });

  it("bộ nhớ hỏng hay không có thì vẫn nhắc đúng một lần, không ném lỗi", () => {
    const broken = {
      getItem: () => {
        throw new Error("chặn");
      },
      setItem: () => {
        throw new Error("chặn");
      },
    };
    expect(takeSceneMusicHint(broken)).toBe(true);
    resetSceneMusicHint();
    expect(takeSceneMusicHint(null)).toBe(true);
    expect(takeSceneMusicHint(null)).toBe(false);
  });

  it("lời nhắc nói với người nghe: nhạc đổi theo cảnh và chọn nhạc khác ở đâu", () => {
    expect(SCENE_MUSIC_HINT).toContain("đổi theo cảnh");
    expect(SCENE_MUSIC_HINT).toMatch(/chọn ở nút Nhạc nền/);
  });
});

describe("lời nhắc nhạc chờ lời mời quan trọng (soát a66)", () => {
  beforeEach(() => {
    resetSceneMusicHint();
    vi.useFakeTimers();
  });
  afterEach(() => vi.useRealTimers());

  it("lời mời xin quyền thông báo đang hiện: chưa hiện nhắc nhạc, nó đi rồi mới hiện - một lần", () => {
    let busy = true;
    const show = vi.fn();
    tellSceneMusic(() => busy, show);
    vi.advanceTimersByTime(3000);
    expect(show).not.toHaveBeenCalled();
    busy = false;
    vi.advanceTimersByTime(1000);
    expect(show).toHaveBeenCalledTimes(1);
    vi.advanceTimersByTime(5000);
    expect(show).toHaveBeenCalledTimes(1);
  });

  it("không có lời mời nào: hiện ngay", () => {
    const show = vi.fn();
    tellSceneMusic(() => false, show);
    expect(show).toHaveBeenCalledTimes(1);
  });
});
