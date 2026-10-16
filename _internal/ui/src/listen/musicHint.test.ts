import { beforeEach, describe, expect, it } from "vitest";
import { resetSceneMusicHint, SCENE_MUSIC_HINT, SCENE_MUSIC_HINT_KEY, takeSceneMusicHint } from "./musicHint";

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
    expect(SCENE_MUSIC_HINT.title).toContain("đổi theo cảnh");
    expect(SCENE_MUSIC_HINT.description).toMatch(/^Bạn .*Nhạc nền/);
  });
});
