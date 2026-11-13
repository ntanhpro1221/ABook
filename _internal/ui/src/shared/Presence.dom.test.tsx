// @vitest-environment happy-dom
import { act, StrictMode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { hasPresentContent, Presence, usePresent } from "./MotionPresence";
import { Dialog } from "./ui";
import { MOTION } from "./motion";

let root: Root, host: HTMLDivElement;
let animate: ReturnType<typeof vi.fn>;
function Custom({ value }: { value: { name: string } }) {
  const present = usePresent();
  return <button data-present={present}>{value.name}</button>;
}
function View({ value }: { value: { name: string } | null }) {
  return <StrictMode><Presence>{value && <Custom value={value} />}</Presence></StrictMode>;
}
beforeEach(() => {
  vi.useFakeTimers();
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  animate = vi.fn(() => ({ cancel: vi.fn() }));
  Object.defineProperty(Element.prototype, "animate", { configurable: true, value: animate });
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
});
afterEach(async () => {
  await act(() => root.unmount()); host.remove(); vi.useRealTimers();
  Reflect.deleteProperty(Element.prototype, "animate");
  Reflect.deleteProperty(window, "matchMedia");
});

it.each([false, true])("retains narrowed custom content through exit, reduced=%s", async reduced => {
  Object.defineProperty(window, "matchMedia", { configurable: true, value: () => ({ matches: reduced }) });
  await act(() => root.render(<View value={null} />));
  expect(host.querySelector("button")).toBeNull();
  await act(() => root.render(<View value={{ name: "Lan" }} />));
  expect(host.querySelector("button")?.textContent).toBe("Lan");
  const enter = animate.mock.calls.at(-1)!;
  expect(enter[1].duration).toBe(reduced ? MOTION.fast : MOTION.medium);
  expect(enter[0][0].transform).toBe(reduced ? "none" : "translateY(8px)");
  await act(() => root.render(<View value={null} />));
  expect(host.querySelector("button")?.textContent).toBe("Lan");
  expect(host.querySelector("button")?.dataset.present).toBe("false");
  expect(host.querySelector("span")?.hasAttribute("inert")).toBe(true);
  const exit = animate.mock.calls.at(-1)!;
  expect(exit[1].duration).toBeGreaterThan(0);
  expect(exit[0].at(-1).opacity).toBe(0);
  await act(() => vi.advanceTimersByTime(MOTION.mediumOut + 100));
  expect(host.querySelector("button")).toBeNull();
});

it("reopening cancels removal and uses the newest value", async () => {
  await act(() => root.render(<View value={{ name: "Lan" }} />));
  await act(() => root.render(<View value={null} />));
  await act(() => vi.advanceTimersByTime(40));
  await act(() => root.render(<View value={{ name: "Mai" }} />));
  await act(() => vi.advanceTimersByTime(1000));
  expect(host.querySelector("button")?.textContent).toBe("Mai");
  expect(host.querySelector("span")?.hasAttribute("inert")).toBe(false);
});

it("native list roots retain valid HTML without a wrapper", async () => {
  await act(() => root.render(<ul><Presence>{true && <li>Lan</li>}</Presence></ul>));
  expect(host.querySelector("ul")?.firstElementChild?.tagName).toBe("LI");
  await act(() => root.render(<ul><Presence>{false && <li>Lan</li>}</Presence></ul>));
  expect(host.querySelector("ul")?.firstElementChild?.tagName).toBe("LI");
  expect(host.querySelector("li")?.hasAttribute("inert")).toBe(true);
  await act(() => vi.advanceTimersByTime(MOTION.mediumOut + 100));
  expect(host.querySelector("li")).toBeNull();
});

it("optional slots distinguish current presence from a truthy React element", async () => {
  const empty = <Presence>{false && <button>Action</button>}</Presence>;
  const full = <Presence><button>Action</button></Presence>;
  expect(hasPresentContent(<>{false}{empty}</>)).toBe(false);
  expect(hasPresentContent(<>{false}{full}</>)).toBe(true);
  await act(() => root.render(<Dialog open onOpenChange={() => {}} title="Title" footer={empty}>Body</Dialog>));
  expect(document.querySelector(".surface-footer")).toBeNull();
});
