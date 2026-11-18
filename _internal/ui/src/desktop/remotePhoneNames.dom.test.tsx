// @vitest-environment happy-dom
import { act, type ReactNode } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { S } from "@/shared/strings.generated";
import { MenuSlot } from "@/listen/menuSlot";
import { HandOffButton, RemoteBars } from "./RemotePhone";

const state = vi.hoisted(() => ({ data: undefined as unknown, setOffset: vi.fn(), disposeOffset: vi.fn() }));
vi.mock("@tanstack/react-query", () => ({
  useQuery: () => ({ data: state.data }),
  useQueryClient: () => ({ invalidateQueries: vi.fn(), setQueryData: vi.fn() }),
  useMutation: () => ({ mutate: vi.fn(), mutateAsync: vi.fn() }),
}));
vi.mock("@/listen/player", () => ({ usePlayer: () => ({ track: { bookId: "invented-book", chapterId: 1 }, playing: false }) }));
vi.mock("@/listen/clock", () => ({ useClockReader: () => () => ({ time: 0 }) }));
vi.mock("@/listen/castMusic", () => ({ noteCastHasNoMusic: vi.fn() }));
vi.mock("@/listen/source", () => ({ useListenBook: () => ({ data: undefined }), useSource: () => ({}) }));
vi.mock("@/listen/PlayerViews", () => ({ Back15: () => null, Forward15: () => null, RemoteSleepMenu: () => null }));
vi.mock("@/shared/BookCover", () => ({ BookCover: () => null }));
vi.mock("@/shared/toast", () => ({ toast: {}, toastOffset: () => ({ set: state.setOffset, dispose: state.disposeOffset }) }));
vi.mock("@/shared/ui", () => ({
  announce: vi.fn(), Dialog: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  Tooltip: ({ children }: { children: ReactNode }) => children,
  IconButton: ({ label }: { label: string }) => <button aria-label={label} />,
}));
vi.mock("@/shared/DropdownMenu", () => {
  const pass = ({ children }: { children: ReactNode }) => <div>{children}</div>;
  return { Root: pass, Portal: pass, Content: pass, Label: pass, Trigger: pass,
    Item: ({ children, className }: { children: ReactNode; className: string }) => <div role="menuitem" className={className}>{children}</div> };
});

const name = "Điện thoại OPPO Find X8 Ultra của Nguyễn Văn An";
const phone = { device: "invented-phone", name, kind: "phone", via: "remote", bookId: "invented-book", bookTitle: "Sách thử bố cục",
  chapterId: 1, chapterTitle: "Chương thử", position: 0, duration: 300, playing: true, buffering: false, rate: 1, books: [], stream: true,
  acks: [], age: 0, known: false };
let host: HTMLDivElement, root: ReturnType<typeof createRoot>, stripHeight: number;
const observers: { callback: () => void; targets: Set<Element> }[] = [];
beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  state.data = { receivedAt: Date.now(), phones: [phone] };
  state.setOffset.mockClear(); state.disposeOffset.mockClear();
  stripHeight = 64;
  observers.length = 0;
  vi.stubGlobal("ResizeObserver", class {
    entry: (typeof observers)[number];
    constructor(callback: () => void) { this.entry = { callback, targets: new Set() }; observers.push(this.entry); }
    observe(target: Element) { this.entry.targets.add(target); }
    disconnect() { this.entry.targets.clear(); }
  });
  const computed = window.getComputedStyle.bind(window);
  vi.spyOn(window, "getComputedStyle").mockImplementation(element => element.hasAttribute("data-one-line-fit")
    ? { fontSize: "14px", lineHeight: "20px" } as CSSStyleDeclaration : computed(element));
  vi.spyOn(HTMLElement.prototype, "clientWidth", "get").mockReturnValue(140);
  vi.spyOn(HTMLElement.prototype, "scrollWidth", "get").mockImplementation(function (this: HTMLElement) { return (this.textContent ?? "").length * 8; });
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(function (this: HTMLElement) {
    return { height: this.hasAttribute("data-remote-strip") ? stripHeight : 20, width: 140, x: 0, y: 0, top: 0, left: 0, right: 140, bottom: 20, toJSON() {} };
  });
  vi.spyOn(HTMLElement.prototype, "animate").mockImplementation(() => ({ cancel: vi.fn(), finished: Promise.resolve() }) as unknown as Animation);
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
});
afterEach(async () => { await act(() => root.unmount()); host.remove(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

it("wraps complete remote strip and target names while the fixed control row exposes its full tooltip", async () => {
  await act(() => root.render(<><RemoteBars /><HandOffButton /></>));
  const strip = host.querySelector<HTMLElement>("[data-remote-strip]")!;
  expect(strip.className).toContain("min-h-9");
  const stripName = strip.querySelector<HTMLElement>("[data-one-line-fit]")!;
  expect(stripName.textContent).toBe(S.s_dang_phat_tren_0_62a989a1(name));
  expect(stripName.dataset.fit).toBe("wrap");
  const target = host.querySelector<HTMLElement>('[role="menuitem"] [data-one-line-fit]')!;
  expect(target.textContent).toBe(name);
  expect(target.dataset.fit).toBe("wrap");
  expect(target.closest('[role="menuitem"]')!.className).toContain("min-h-9");
  expect(target.style.fontSize).toBe("");
  expect(target.style.whiteSpace).toBe("normal");
  expect(host.querySelector("span[title]")?.getAttribute("title")).toBe(name);
  expect(state.setOffset).toHaveBeenLastCalledWith("160px");
  stripHeight = 96;
  await act(() => { for (const observer of observers) if (observer.targets.has(strip)) observer.callback(); });
  expect(state.setOffset).toHaveBeenLastCalledWith("192px");
});

it("fits the only playback destination inside the player menu", async () => {
  await act(() => root.render(<MenuSlot label={S.s_phat_tren_681e16e1}><HandOffButton /></MenuSlot>));
  const label = host.querySelector<HTMLElement>("[data-one-line-fit]")!;
  expect(label.textContent).toBe(name);
  expect(label.dataset.fit).toBe("wrap");
  expect(label.style.fontSize).toBe("");
  expect(label.className).not.toMatch(/truncate|ellipsis|line-clamp/);
});
