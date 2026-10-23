import { afterEach, expect, it, vi } from "vitest";
import type { ReactElement } from "react";

const state = vi.hoisted(() => ({ color: "", title: "Sách thử" }));
vi.mock("react", async (original) => ({
  ...await original<typeof import("react")>(),
  useState: (initial: unknown) => [typeof initial === "function" ? initial() : initial, vi.fn()],
  useRef: (value: unknown) => ({ current: value }),
  useEffect: () => undefined,
}));
vi.mock("@/listen/player", async (original) => ({
  ...await original<typeof import("@/listen/player")>(),
  usePlayer: () => ({ track: { bookTitle: state.title, bookCover: { color: state.color } }, queue: [], sleep: { mode: "off" } }),
  useNowPlaying: () => ({ expanded: true, setExpanded: vi.fn() }),
}));
import { NowPlaying } from "./PlayerViews";
import { coverStyle } from "@/shared/cover";

afterEach(() => vi.unstubAllGlobals());

function background(color: string): string {
  state.color = color;
  vi.stubGlobal("localStorage", { getItem: () => null });
  const view = NowPlaying({ mobile: true }) as ReactElement<{ children: ReactElement<{ style: { backgroundImage: string } }>[] }>;
  return view.props.children[0].props.style.backgroundImage;
}

it("màn đang nghe lọc màu trước khi ghép CSS, kể cả chuỗi chèn thêm gradient", () => {
  const malicious = "red 42%, transparent) 0%, transparent 58%), url(https://tracker.invalid/a), linear-gradient(180deg, color-mix(in oklab, red";
  const css = background(malicious);
  expect(css).not.toContain("url(");
  expect(css).toContain(coverStyle(state.title).from);
});

it("màn đang nghe giữ màu hex hợp lệ và chuẩn hoá chữ hoa", () => {
  expect(background(" #AABBCC ")).toContain("#aabbcc 42%");
});
