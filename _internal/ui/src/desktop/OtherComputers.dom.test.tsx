// @vitest-environment happy-dom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/shared/ui";
import { OtherComputers } from "./OtherComputers";
import type { PairedDevice } from "./computerRoutes";

vi.mock("@/studio/api", () => ({ api: vi.fn(() => new Promise(() => {})) }));
let root: Root, host: HTMLDivElement, client: QueryClient;
beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  vi.spyOn(HTMLElement.prototype, "animate").mockImplementation(() => ({ cancel: vi.fn(), finished: Promise.resolve() }) as unknown as Animation);
  localStorage.setItem("abook.fold.other-computers.pair", "1");
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
  client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
  client.setQueryData(["computers"], { name: "Máy này", computers: [] });
});
afterEach(async () => { await act(() => root.unmount()); client.clear(); localStorage.clear(); document.body.replaceChildren(); vi.restoreAllMocks(); });

it.each([
  { services: ["release"], release: true, dev: false },
  { services: ["dev"], release: false, dev: true },
  { services: ["release", "dev"], release: true, dev: true },
  { services: [], release: false, dev: false },
])("chỉ mời ghép dịch vụ đã quảng bá: $services", async ({ services, release, dev }) => {
  client.setQueryData(["computers", "bluetooth"], { devices: [
    { name: "Pixel", address: "AA:BB:CC:DD:EE:01", kind: "phone", services: services as PairedDevice["services"] },
  ] });
  await act(() => root.render(<QueryClientProvider client={client}><TooltipProvider><OtherComputers /></TooltipProvider></QueryClientProvider>));
  const buttons = () => [...host.querySelectorAll<HTMLButtonElement>("button")];
  const fold = buttons().find(button => button.textContent?.includes("Ghép máy"));
  if (fold?.getAttribute("aria-expanded") === "false") await act(() => fold.click());
  const releaseButton = buttons().find(button => button.textContent?.includes("Pixel · điện thoại"));
  const devButton = buttons().find(button => button.textContent?.includes("Pixel · bản thử"));
  expect(Boolean(releaseButton)).toBe(release);
  expect(Boolean(devButton)).toBe(dev);
  expect(buttons().filter(button => button.textContent?.includes("Pixel"))).toHaveLength(Number(release) + Number(dev));
  if (devButton) {
    await act(() => devButton.click());
    expect([...host.querySelectorAll("input")].find(input => input.value.includes("@dev"))?.value).toBe("AA:BB:CC:DD:EE:01@dev");
  }
  if (releaseButton) {
    await act(() => releaseButton.click());
    expect([...host.querySelectorAll("input")].some(input => input.value === "AA:BB:CC:DD:EE:01")).toBe(true);
  }
});
