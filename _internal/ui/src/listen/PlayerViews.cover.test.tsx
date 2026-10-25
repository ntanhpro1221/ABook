import { afterEach, expect, it, vi } from "vitest";
import type { ReactElement } from "react";

const state = vi.hoisted(() => ({ color: "", title: "Sách thử" }));
vi.mock("react", async (original) => ({
  ...await original<typeof import("react")>(),
  useState: (initial: unknown) => [typeof initial === "function" ? initial() : initial, vi.fn()],
  useRef: (value: unknown) => ({ current: value }),
  useCallback: (callback: unknown) => callback,
  useEffect: () => undefined,
  useDeferredValue: (value: unknown) => value,
}));
vi.mock("react-router", async (original) => ({
  ...await original<typeof import("react-router")>(),
  useNavigate: () => vi.fn(),
}));
vi.mock("@/listen/player", async (original) => ({
  ...await original<typeof import("@/listen/player")>(),
  usePlayer: () => ({ track: { bookTitle: state.title, bookCover: { color: state.color } }, queue: [], sleep: { mode: "off" } }),
  useNowPlaying: () => ({ expanded: true, setExpanded: vi.fn() }),
}));
import { NowPlaying } from "./PlayerViews";
import { coverStyle } from "@/shared/cover";

afterEach(() => vi.unstubAllGlobals());

/** Màu pha vào nền màn Đang nghe (biến --cover-tint trên chính màn, styles.css .now-playing-tint). */
function background(color: string): string {
  state.color = color;
  vi.stubGlobal("localStorage", { getItem: () => null });
  const provider = NowPlaying({ mobile: true }) as ReactElement<{ children: ReactElement<{ style: Record<string, string> }> }>;
  const view = provider.props.children;
  return view.props.style["--cover-tint"];
}

it("màn đang nghe lọc màu trước khi ghép CSS, kể cả chuỗi chèn thêm gradient", () => {
  const malicious = "red 42%, transparent) 0%, transparent 58%), url(https://tracker.invalid/a), linear-gradient(180deg, color-mix(in oklab, red";
  const css = background(malicious);
  expect(css).not.toContain("url(");
  expect(css).toBe(coverStyle(state.title).from);
});

it("màn đang nghe giữ màu hex hợp lệ và chuẩn hoá chữ hoa", () => {
  expect(background(" #AABBCC ")).toBe("#aabbcc");
});
