// @vitest-environment happy-dom
// a139 V16: nút "Phát trên …" - chưa có nơi phát / một nơi (nút) / nhiều nơi (menu) là ba gốc khác nhau; một vỏ MotionRegion mờ chéo giữa chúng.
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as Tooltip from "@radix-ui/react-tooltip";

const h = vi.hoisted(() => ({ data: undefined as unknown }));
vi.mock("@tanstack/react-query", async (load) => ({ ...await load<typeof import("@tanstack/react-query")>(), useQueryClient: () => ({ invalidateQueries() {} }), useQuery: () => ({ data: h.data, isLoading: false }), useMutation: () => ({ mutate() {} }) }));
vi.mock("@/listen/player", () => ({ usePlayer: () => ({ track: { bookId: "b", chapterId: 1 }, pause() {} }) }));
vi.mock("@/listen/clock", () => ({ useClockReader: () => () => ({ time: 0 }) }));
vi.mock("@/listen/source", () => ({ useListenBook: () => ({ data: {} }), useSource: () => ({}) }));
vi.mock("@/android/plugins", () => ({ EbookLibrary: { scanPlayers: async () => {} } }));
import { PhoneHandOffButton } from "./RemotePlayers";

let root: Root, host: HTMLDivElement;
let animate: ReturnType<typeof vi.spyOn>;
beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  h.data = undefined;
  Object.defineProperty(CSSStyleDeclaration.prototype, Symbol.iterator, { configurable: true, value: function* (this: CSSStyleDeclaration) { for (let i = 0; i < this.length; i++) yield this.item(i); } });
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({ x: 0, y: 0, top: 0, left: 0, right: 40, bottom: 40, width: 40, height: 40, toJSON() {} });
  animate = vi.spyOn(HTMLElement.prototype, "animate").mockImplementation(() => ({ cancel() {}, onfinish: null }) as unknown as Animation);
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
});
afterEach(async () => { await act(() => root.unmount()); document.body.replaceChildren(); vi.restoreAllMocks(); });
const render = () => act(() => root.render(<Tooltip.Provider><PhoneHandOffButton /></Tooltip.Provider>));
const speaker = (name: string) => ({ device: `cast:${name}`, via: "cast", kind: "speaker", name });

it("V16 chưa có -> một nút -> menu: cùng một vỏ, mỗi lần đổi gốc có ảnh cũ inert và mờ chéo", async () => {
  await render();
  const shell = host.firstElementChild as HTMLElement;
  expect(shell.hasAttribute("data-motion-region")).toBe(true);
  h.data = { players: [speaker("Loa A")] };
  await render();
  expect(host.firstElementChild).toBe(shell);
  expect(host.querySelector('button[aria-label="Phát trên Loa A (DLNA)"], button[aria-label^="Phát trên Loa A"]')).not.toBeNull();
  expect((animate.mock.contexts as HTMLElement[]).filter((element) => element === shell)).toHaveLength(1);
  animate.mockClear();
  h.data = { players: [speaker("Loa A"), speaker("Loa B")] };
  await render();
  expect(host.firstElementChild).toBe(shell);
  expect(host.querySelector('button[aria-label="Phát trên thiết bị khác"]')).not.toBeNull();
  expect((animate.mock.contexts as HTMLElement[]).filter((element) => element === shell)).toHaveLength(1);
  const old = [...document.querySelectorAll<HTMLElement>(".motion-snapshot")].find((image) => image.querySelector('button[aria-label^="Phát trên Loa A"]'));
  expect(old?.hasAttribute("inert")).toBe(true);
});
