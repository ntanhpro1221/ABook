// @vitest-environment happy-dom
import { act } from "react";
import { eventually } from "@/testing/eventually";
import { createRoot, type Root } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/shared/ui";
import { OtherComputers } from "./OtherComputers";
import type { PairedDevice } from "./computerRoutes";
import { api, ApiError } from "@/studio/api";
import { S } from "@/shared/strings.generated";

vi.mock("@/studio/api", async (original) => ({ ...await original<typeof import("@/studio/api")>(), api: vi.fn(() => new Promise(() => {})) }));
let root: Root, host: HTMLDivElement, client: QueryClient;
beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  vi.spyOn(HTMLElement.prototype, "animate").mockImplementation(() => ({ cancel: vi.fn(), finished: Promise.resolve() }) as unknown as Animation);
  localStorage.setItem("abook.fold.other-computers.pair", "1");
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
  client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
  client.setQueryData(["computers"], { name: "Máy này", computers: [] });
});
afterEach(async () => { await act(() => root.unmount()); client.clear(); localStorage.clear(); document.body.replaceChildren(); vi.restoreAllMocks(); vi.mocked(api).mockReset(); });

async function enter(id: string, value: string) {
  const input = host.querySelector<HTMLInputElement>(id)!;
  await act(() => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(input, value);
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
}

it("shows the certificate before a manual code can be sent with confirmation", async () => {
  const fingerprint = "0123456789abcdef".repeat(4);
  vi.mocked(api).mockImplementation(async (path, options) => {
    if (path === "/api/computers" && options?.method === "POST") {
      throw new ApiError(409, S.s_pair_fingerprint_help, { confirm: { fingerprint, short: "0123 4567 89AB CDEF" } });
    }
    return new Promise(() => {});
  });
  await act(() => root.render(<QueryClientProvider client={client}><TooltipProvider><OtherComputers /></TooltipProvider></QueryClientProvider>));
  await enter("#other-computer-address", "192.168.1.20");
  await enter("#other-computer-code", "482913");
  await act(async () => { host.querySelector("form")!.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true })); });
  await act(() => eventually(() => expect(host.textContent).toContain("0123 4567 89AB CDEF")));
  const posts = () => vi.mocked(api).mock.calls.filter(([path, options]) => path === "/api/computers" && options?.method === "POST");
  expect(posts()).toHaveLength(1);
  expect(posts()[0][1]?.body).toEqual({ address: "192.168.1.20", code: "482913", fingerprint: "" });
  const confirm = [...host.querySelectorAll("button")].find(button => button.textContent === S.s_pair_fingerprint_confirm)!;
  await act(async () => confirm.click());
  expect(posts()[1][1]?.body).toEqual({ address: "192.168.1.20", code: "482913", fingerprint });
  await enter("#other-computer-address", "192.168.1.21");
  expect(host.textContent).not.toContain("0123 4567 89AB CDEF");
});

it("preserves the full SHA-256 when a pairing string is pasted", async () => {
  await act(() => root.render(<QueryClientProvider client={client}><TooltipProvider><OtherComputers /></TooltipProvider></QueryClientProvider>));
  await enter("#other-computer-address", "192.168.1.20");
  const full = "482913-" + "abcdef0123456789".repeat(4);
  await enter("#other-computer-code", full);
  expect(host.querySelector<HTMLInputElement>("#other-computer-code")!.value).toBe(full);
  expect(host.querySelector<HTMLButtonElement>('button[type="submit"]')!.disabled).toBe(false);
});

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
