// @vitest-environment happy-dom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as Tooltip from "@radix-ui/react-tooltip";
import { HandOffButton } from "@/desktop/RemotePhone";
import { BluetoothFallback } from "@/desktop/OtherComputers";

const h = vi.hoisted(() => ({ players: [] as unknown[], phones: [] as unknown[] }));
vi.mock("@tanstack/react-query", async (load) => ({ ...await load<typeof import("@tanstack/react-query")>(), useQueryClient: () => ({ invalidateQueries() {} }), useQuery: () => ({ data: { players: h.players, phones: h.phones }, isLoading: false }), useMutation: () => ({ mutate() {} }) }));
vi.mock("@/listen/player", () => ({ usePlayer: () => ({ track: { bookId: "b", chapterId: 1 }, pause() {} }) }));
vi.mock("@/listen/clock", () => ({ useClockReader: () => () => ({ time: 0 }) }));
vi.mock("@/listen/source", () => ({ useListenBook: () => ({ data: {} }), useSource: () => ({}) }));
vi.mock("@/studio/api", async (load) => ({ ...await load<typeof import("@/studio/api")>(), api: async () => ({}) }));
let root: ReturnType<typeof createRoot>;
let animate: ReturnType<typeof vi.spyOn>;
beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  h.players = []; h.phones = [];
  Object.defineProperty(CSSStyleDeclaration.prototype, Symbol.iterator, { configurable: true, value: function* (this: CSSStyleDeclaration) { for (let index = 0; index < this.length; index++) yield this.item(index); } });
  const host = document.createElement("div"); document.body.append(host); root = createRoot(host);
  animate = vi.spyOn(HTMLElement.prototype, "animate").mockImplementation(() => ({ cancel() {}, onfinish: null }) as Animation);
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({ x: 0, y: 0, top: 0, left: 0, right: 240, bottom: 80, width: 240, height: 80, toJSON() {} });
  const style = document.createElement("style"); style.textContent = '[role="menu"] { z-index: 50; }'; document.head.append(style);
});
afterEach(async () => { await act(() => root.unmount()); document.body.replaceChildren(); document.head.replaceChildren(); vi.restoreAllMocks(); });

it.each(["desktop", "bluetooth"])("V4 %s: kết quả đổi bên trong Portal, ảnh cũ trên menu và inert", async (kind) => {
  let devices: { address: string; name: string; kind: "computer" | "phone" }[] = [];
  const render = () => act(() => root.render(<Tooltip.Provider>{kind === "desktop" ? <HandOffButton /> : <BluetoothFallback computer={{ name: "Máy A", host: "192.168.1.1" } as Parameters<typeof BluetoothFallback>[0]["computer"]} devices={devices} busy={false} onChoose={() => {}} />}</Tooltip.Provider>));
  await render();
  await act(() => document.querySelector<HTMLButtonElement>("button")!.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowDown", bubbles: true })));
  const menu = document.querySelector<HTMLElement>('[role="menu"]')!;
  expect(menu).not.toBeNull();
  animate.mockClear();
  h.players = [{ device: "cast:a", via: "cast", kind: "speaker", name: "Loa A" }, { device: "cast:b", via: "cast", kind: "speaker", name: "Loa B" }];
  h.phones = h.players;
  devices = [{ address: "aa", name: "Loa A", kind: "computer" }];
  await render();
  const region = menu.querySelector<HTMLElement>("[data-motion-region]");
  expect(region).not.toBeNull();
  expect(animate.mock.contexts).toContain(region);
  const snapshot = document.querySelector<HTMLElement>(".motion-snapshot")!;
  expect(Number(snapshot.style.zIndex)).toBeGreaterThanOrEqual(51);
  expect(snapshot.hasAttribute("inert")).toBe(true);
  expect(snapshot.style.pointerEvents).toBe("none");
  expect(snapshot.parentElement).toBe(menu);
  h.players = h.players.slice(0, 1); h.phones = h.phones.slice(0, 1);
  await render();
  expect(menu.isConnected).toBe(true); // API chỉ còn một loa vẫn giữ menu đang mở.
});
